"""Tests for the arena-extension backend: auth, forwarding, transfers and model jobs."""

import base64
import contextlib
import http.client
import importlib
import io
import json
import sys
import threading
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "skills/refs/arena-extension/scripts"
KEY = "test-agent-key-0123456789"
TOKEN = "test-provider-token"
BINARY = b"\x89PNG\r\n\x1a\n\x00binary payload"
sys.path.insert(0, str(SCRIPTS))
core = importlib.import_module("arena_extension.core")
github_api = importlib.import_module("arena_extension.github_api")
transfers = importlib.import_module("arena_extension.transfers")
llm_module = importlib.import_module("arena_extension.llm")


def log_zip():
  stream = io.BytesIO()
  with zipfile.ZipFile(stream, "w") as archive:
    archive.writestr("1_Set up job.txt", "setup line one\nsetup line two\n")
    archive.writestr("2_Run tests.txt", "test line one\ntest line two\n")
  return stream.getvalue()


class StubHandler(BaseHTTPRequestHandler):
  """Stand in for api.github.com, a file host and a model endpoint."""

  def do_GET(self):
    self.server.seen.append(
      {"path": self.path, "auth": self.headers.get("Authorization")}
    )
    if self.path.startswith("/repos/o/r/actions/runs/1/logs"):
      self._write(200, log_zip(), "application/zip")
    elif self.path.startswith("/repos/o/r/pulls/9"):
      self._write(200, b"diff --git a/x b/x\n+added line\n", "text/plain")
    elif self.path.startswith("/repos/o/r/code-scanning/alerts"):
      self._write(200, json.dumps([{"number": 7}]).encode(), "application/json")
    elif self.path.startswith("/blob"):
      self._write(200, BINARY, "image/png")
    elif self.path.startswith("/text"):
      self._write(200, b"plain words\n", "text/plain")
    else:
      self._write(404, b'{"message": "Not Found"}', "application/json")

  def do_POST(self):
    length = int(self.headers.get("Content-Length") or 0)
    self.server.posts.append(
      {
        "path": self.path,
        "auth": self.headers.get("Authorization"),
        "body": json.loads(self.rfile.read(length) or b"{}"),
      }
    )
    self._write(
      200,
      json.dumps({"choices": [{"message": {"content": "review text"}}]}).encode(),
      "application/json",
    )

  def _write(self, status, body, content_type):
    self.send_response(status)
    self.send_header("Content-Type", content_type)
    self.send_header("Content-Length", str(len(body)))
    self.end_headers()
    self.wfile.write(body)

  def log_message(self, format, *args):
    """Silence the stub: the tests assert on recorded requests, not on stub logs."""


class StubServer(ThreadingHTTPServer):
  daemon_threads = True

  def __init__(self, address):
    super().__init__(address, StubHandler)
    self.seen = []
    self.posts = []


@contextlib.contextmanager
def backend(tmp_path, **overrides):
  """Run the stub upstream and the extension server, and stop both on exit."""
  stub = StubServer(("127.0.0.1", 0))
  threading.Thread(target=stub.serve_forever, daemon=True).start()
  base = f"http://127.0.0.1:{stub.server_address[1]}"
  options = SimpleNamespace(
    host="127.0.0.1",
    port=0,
    key=KEY,
    token=TOKEN,
    repo="o/r",
    api=base,
    state_dir=str(tmp_path),
    llm_base=base,
    llm_key="model-key",
    llm_model="model-1",
    fetch_cap=transfers.DEFAULT_FETCH_CAP,
    stage_cap=transfers.DEFAULT_STAGE_CAP,
  )
  for name, value in overrides.items():
    setattr(options, name, value)
  extension = core.build_server(options)
  threading.Thread(target=extension.serve_forever, daemon=True).start()
  try:
    yield SimpleNamespace(stub=stub, port=extension.server_address[1], stub_url=base)
  finally:
    extension.shutdown()
    extension.server_close()
    stub.shutdown()
    stub.server_close()


def call(port, target, headers=None):
  connection = http.client.HTTPConnection("127.0.0.1", port, timeout=15)
  try:
    connection.request("GET", target, headers=headers or {})
    response = connection.getresponse()
    return response.status, response.read().decode("utf-8")
  finally:
    connection.close()


def wait_for_job(port, job):
  for _ in range(200):
    payload = json.loads(call(port, f"/v1/llm?key={KEY}&id={job}")[1])
    if payload["status"] in ("done", "error"):
      return payload
    threading.Event().wait(0.05)
  raise AssertionError(f"job {job} did not settle: {payload}")


def test_health_route_needs_no_key(tmp_path):
  with backend(tmp_path) as handle:
    status, body = call(handle.port, "/v1/health")
    assert status == 200
    assert json.loads(body)["ok"] is True


def test_missing_and_wrong_keys_are_rejected(tmp_path):
  with backend(tmp_path) as handle:
    assert call(handle.port, "/v1/ping")[0] == 401
    assert call(handle.port, "/v1/ping?key=wrong-key")[0] == 401


def test_header_key_and_ping_payload(tmp_path):
  with backend(tmp_path) as handle:
    status, body = call(handle.port, "/v1/ping", {"X-Extension-Key": KEY})
    assert status == 200
    payload = json.loads(body)
    assert (
      payload["repo"] == "o/r" and payload["token"] is True and payload["llm"] is True
    )


def test_github_forwards_path_query_and_token(tmp_path):
  with backend(tmp_path) as handle:
    status, body = call(
      handle.port,
      f"/v1/github?key={KEY}&path=repos/o/r/code-scanning/alerts&state=open&per_page=5",
    )
    assert status == 200
    assert json.loads(body) == [{"number": 7}]
    sent = handle.stub.seen[-1]
    assert sent["auth"] == f"Bearer {TOKEN}"
    assert "state=open" in sent["path"] and "per_page=5" in sent["path"]


def test_github_rejects_an_absolute_path(tmp_path):
  with backend(tmp_path) as handle:
    status, body = call(
      handle.port, f"/v1/github?key={KEY}&path=https://evil.example/steal"
    )
    assert status == 400
    assert "relative" in json.loads(body)["error"]


def test_logs_route_returns_a_text_tail(tmp_path):
  with backend(tmp_path) as handle:
    status, body = call(handle.port, f"/v1/logs?key={KEY}&run=1")
    assert status == 200
    assert "1_Set up job.txt" in body and "test line two" in body


def test_logs_route_validates_the_run_and_repo(tmp_path):
  with backend(tmp_path) as handle:
    assert call(handle.port, f"/v1/logs?key={KEY}&run=nope")[0] == 400
    assert call(handle.port, f"/v1/logs?key={KEY}&run=1&repo=bad//repo")[0] == 400


def test_fetch_returns_text_for_text_bytes(tmp_path):
  with backend(tmp_path) as handle:
    status, body = call(handle.port, f"/v1/fetch?key={KEY}&url={handle.stub_url}/text")
    assert status == 200
    assert body == "plain words\n"


def test_fetch_returns_base64_for_binary(tmp_path):
  with backend(tmp_path) as handle:
    status, body = call(
      handle.port, f"/v1/fetch?key={KEY}&url={handle.stub_url}/blob&mode=base64"
    )
    assert status == 200
    payload = json.loads(body)
    assert payload["encoding"] == "base64"
    assert base64.b64decode(payload["payload"]) == BINARY


def test_fetch_text_mode_refuses_binary(tmp_path):
  with backend(tmp_path) as handle:
    status, body = call(
      handle.port, f"/v1/fetch?key={KEY}&url={handle.stub_url}/blob&mode=text"
    )
    assert status == 415
    assert "mode=base64" in json.loads(body)["error"]


def test_fetch_refuses_a_public_http_url(tmp_path):
  with backend(tmp_path) as handle:
    status, body = call(handle.port, f"/v1/fetch?key={KEY}&url=http://example.com/x")
    assert status == 400
    assert "loopback" in json.loads(body)["error"]


def test_fetch_stages_and_serves_chunks(tmp_path):
  with backend(tmp_path) as handle:
    status, body = call(
      handle.port, f"/v1/fetch?key={KEY}&url={handle.stub_url}/blob&stage=1"
    )
    assert status == 200
    staged = json.loads(body)
    assert staged["bytes"] == len(BINARY) and staged["chunks"] == 1
    status, body = call(handle.port, f"/v1/fetch?key={KEY}&id={staged['id']}&index=0")
    assert status == 200
    piece = json.loads(body)
    assert base64.b64decode(piece["payload"]) == BINARY


def test_fetch_reports_an_expired_id(tmp_path):
  with backend(tmp_path) as handle:
    status, body = call(handle.port, f"/v1/fetch?key={KEY}&id=deadbeef&index=0")
    assert status == 404
    assert "expired" in json.loads(body)["error"]


def test_transfers_encode_base64_b85_and_gzip():
  data = BINARY * 3
  assert base64.b64decode(transfers.encode(data, "base64")[0]) == data
  payload, label = transfers.encode(data, "b85")
  assert label == "b85" and base64.b85decode(payload) == data
  payload, label = transfers.encode(data, "base64", compress=True)
  assert label == "base64+gzip"
  assert transfers.is_text(b"plain words\n") is True
  assert transfers.is_text(BINARY) is False


def test_transfers_chunking_round_trip():
  size = transfers.CHUNK_BYTES * 2 + 5
  data = bytes(range(256)) * (size // 256) + b"x" * (size % 256)
  pieces = [
    transfers.slice_for_chunk(data, index)
    for index in range(transfers.chunk_count(len(data)))
  ]
  assert len(pieces) == 3
  assert b"".join(pieces) == data
  assert transfers.slice_for_chunk(data, 3) is None
  assert transfers.slice_for_chunk(data, -1) is None


def test_repo_validation_accepts_the_owner_name_shape():
  assert github_api.valid_repo("o/r") is True
  assert github_api.valid_repo("owner-1/repo_2.name") is True
  assert github_api.valid_repo("o/r/extra") is False
  assert github_api.valid_repo("o//r") is False
  assert github_api.valid_repo("") is False


def test_log_tail_rejects_non_zip_bytes():
  assert github_api.log_tail(b"not a zip") is None


def test_llm_job_runs_and_returns_text(tmp_path):
  with backend(tmp_path) as handle:
    status, body = call(handle.port, f"/v1/llm?key={KEY}&prompt=review%20this")
    assert status == 202
    payload = wait_for_job(handle.port, json.loads(body)["job"])
    assert payload["status"] == "done", payload
    assert payload["text"] == "review text"
    post = handle.stub.posts[-1]
    assert post["auth"] == "Bearer model-key"
    assert post["body"]["model"] == "model-1"
    assert post["body"]["messages"][1]["content"][0]["text"].startswith("review this")


def test_llm_diff_context_reaches_the_endpoint(tmp_path):
  with backend(tmp_path) as handle:
    status, body = call(handle.port, f"/v1/llm?key={KEY}&prompt=check&diff=9&repo=o/r")
    assert status == 202
    payload = wait_for_job(handle.port, json.loads(body)["job"])
    assert payload["status"] == "done", payload
    system = handle.stub.posts[-1]["body"]["messages"][0]["content"]
    assert "diff --git a/x b/x" in system


def test_llm_image_url_becomes_a_data_uri(tmp_path):
  with backend(tmp_path) as handle:
    status, body = call(
      handle.port, f"/v1/llm?key={KEY}&prompt=see&image={handle.stub_url}/blob"
    )
    assert status == 202
    payload = wait_for_job(handle.port, json.loads(body)["job"])
    assert payload["status"] == "done", payload
    content = handle.stub.posts[-1]["body"]["messages"][1]["content"]
    assert content[1]["image_url"]["url"].startswith("data:image/png;base64,")


def test_llm_validates_the_prompt_and_image_count(tmp_path):
  with backend(tmp_path) as handle:
    assert call(handle.port, f"/v1/llm?key={KEY}")[0] == 400
    long_prompt = "x" * (llm_module.PROMPT_CAP_CHARS + 1)
    assert call(handle.port, f"/v1/llm?key={KEY}&prompt={long_prompt}")[0] == 400
    images = "".join(f"&image={handle.stub_url}/blob" for _ in range(5))
    assert call(handle.port, f"/v1/llm?key={KEY}&prompt=see{images}")[0] == 400


def test_llm_reports_a_missing_endpoint(tmp_path):
  with backend(tmp_path, llm_base="") as handle:
    status, body = call(handle.port, f"/v1/llm?key={KEY}&prompt=hello")
    assert status == 503
    assert "EXTENSION_LLM_BASE" in json.loads(body)["hint"]


def test_unknown_route_lists_the_routes(tmp_path):
  with backend(tmp_path) as handle:
    status, body = call(handle.port, "/v1/nothing")
    assert status == 404
    assert "/v1/llm" in json.loads(body)["routes"]


def test_log_line_drops_the_query_string():
  assert (
    core.log_line("GET", "/v1/github?key=SECRET&path=x", 200) == "GET /v1/github -> 200"
  )
