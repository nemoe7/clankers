"""Tests for the arena-proxy backend: auth, forwarding, transfers and model jobs."""

import base64
import contextlib
import gzip
import http.client
import importlib
import io
import json
import sys
import threading
import urllib.parse
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "skills/refs/arena-skill/arena-egress-proxy/scripts"
KEY = "test-agent-key-0123456789"
MASTER = "test-master-key-0123456789"
TOKEN = "test-provider-token"
BINARY = b"\x89PNG\r\n\x1a\n\x00binary payload"
sys.path.insert(0, str(SCRIPTS))
core = importlib.import_module("arena_proxy.core")
github_api = importlib.import_module("arena_proxy.github_api")
transfers = importlib.import_module("arena_proxy.transfers")
llm_module = importlib.import_module("arena_proxy.llm")


def log_zip():
  stream = io.BytesIO()
  with zipfile.ZipFile(stream, "w") as archive:
    archive.writestr("1_Set up job.txt", "setup line one\nsetup line two\n")
    archive.writestr("2_Run tests.txt", "test line one\ntest line two\n")
    archive.writestr(
      "3_Run gate.txt", "gate line one\n##[error]the gate check failed\n"
    )
  return stream.getvalue()


class StubHandler(BaseHTTPRequestHandler):
  """Stand in for api.github.com, a file host and a model endpoint."""

  def do_GET(self):
    self.server.seen.append(
      {"path": self.path, "auth": self.headers.get("Authorization")}
    )
    resource = self.path.split("?", 1)[0]
    if resource in getattr(self.server, "github_replies", {}):
      self._write(
        200,
        json.dumps(self.server.github_replies[resource]).encode(),
        "application/json",
      )
    elif self.path.startswith("/repos/o/r/actions/runs/1/logs"):
      self._write(200, log_zip(), "application/zip")
    elif self.path.startswith("/repos/o/r/pulls/9"):
      self._write(200, b"diff --git a/x b/x\n+added line\n", "text/plain")
    elif self.path.startswith("/repos/o/r/code-scanning/alerts"):
      page = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query).get(
        "page", ["1"]
      )[0]
      alerts = getattr(self.server, "alert_pages", {}).get(
        page, getattr(self.server, "alerts", [{"number": 7}])
      )
      next_page = getattr(self.server, "alert_next", {}).get(page)
      headers = {}
      if next_page:
        host, port = self.server.server_address
        headers["Link"] = (
          f'<http://{host}:{port}/repos/o/r/code-scanning/alerts?page={next_page}&state=open>; rel="next"'
        )
      self._write(
        getattr(self.server, "alert_status", 200),
        json.dumps(alerts).encode(),
        "application/json",
        headers,
      )
    elif self.path.startswith("/repos/o/r/labels"):
      self._write(
        200,
        json.dumps(
          getattr(
            self.server,
            "labels",
            [
              {
                "name": "triage",
                "color": "ff0000",
                "description": "unused-detail" * 1000,
              }
            ],
          )
        ).encode(),
        "application/json",
      )
    elif self.path.startswith("/blob"):
      self._write(200, getattr(self.server, "blob_body", BINARY), "image/png")
    elif self.path.startswith("/text"):
      self._write(
        200, getattr(self.server, "text_body", b"plain words\n"), "text/plain"
      )
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
      json.dumps(
        {
          "choices": [
            {"message": {"content": getattr(self.server, "reply_text", "review text")}}
          ]
        }
      ).encode(),
      "application/json",
    )

  def _write(self, status, body, content_type, headers=None):
    self.send_response(status)
    self.send_header("Content-Type", content_type)
    self.send_header("Content-Length", str(len(body)))
    for name, value in (headers or {}).items():
      self.send_header(name, value)
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
  # `shutdown()` waits one poll interval for the select loop to notice it. The default
  # 0.5 s costs a second a test across these two servers, and no assertion needs it.
  threading.Thread(
    target=stub.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
  ).start()
  base = f"http://127.0.0.1:{stub.server_address[1]}"
  options = SimpleNamespace(
    host="127.0.0.1",
    port=0,
    key=KEY,
    master=MASTER,
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
  threading.Thread(
    target=extension.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
  ).start()
  try:
    yield SimpleNamespace(stub=stub, port=extension.server_address[1], stub_url=base)
  finally:
    extension.shutdown()
    extension.server_close()
    stub.shutdown()
    stub.server_close()


def call(port, target, headers=None):
  status, body, _ = call_with_headers(port, target, headers)
  return status, body


def call_with_headers(port, target, headers=None):
  connection = http.client.HTTPConnection("127.0.0.1", port, timeout=15)
  try:
    connection.request("GET", target, headers=headers or {})
    response = connection.getresponse()
    return response.status, response.read().decode("utf-8"), dict(response.getheaders())
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


def test_every_answer_allows_the_owner_page_to_read_it(tmp_path):
  with backend(tmp_path) as handle:
    status, _, headers = call_with_headers(handle.port, f"/v1/key?master={MASTER}")
    assert status == 200
    assert headers.get("Access-Control-Allow-Origin") == "*"


def test_key_route_serves_the_agent_key_to_the_master(tmp_path):
  with backend(tmp_path) as handle:
    status, body = call(handle.port, f"/v1/key?master={MASTER}")
    assert status == 200
    assert json.loads(body)["key"] == KEY
    status, _ = call(handle.port, f"/v1/key?key={KEY}")
    assert status == 401
    status, _ = call(handle.port, "/v1/key?master=wrong")
    assert status == 401
  with backend(tmp_path, master="") as closed:
    status, body = call(closed.port, f"/v1/key?master={MASTER}")
    assert status == 404
    assert "ARENA_PROXY_MASTER_KEY" in json.loads(body)["hint"]


def test_hidden_rotate_route_replaces_the_key_on_a_schedule(tmp_path):
  with backend(tmp_path) as handle:
    # The route list never names the hidden route, so a probe cannot find it.
    status, body = call(handle.port, "/v1/nothing")
    assert status == 404
    assert "rotate" not in body
    status, body = call(handle.port, f"/v1/ping?key={KEY}")
    assert "rotate" not in body
    # A wrong master key answers 401, and the live key keeps working.
    status, _ = call(handle.port, "/v1/rotate?master=wrong")
    assert status == 401
    status, _ = call(handle.port, f"/v1/ping?key={KEY}")
    assert status == 200
    # The default minimum age holds the key, and the answer says so.
    status, body = call(handle.port, f"/v1/rotate?master={MASTER}")
    assert status == 200
    assert json.loads(body)["rotated"] is False
    # A zero minimum rotates at once, and the old key stops working.
    status, body = call(handle.port, f"/v1/rotate?master={MASTER}&min=0")
    assert status == 200
    payload = json.loads(body)
    assert payload["rotated"] is True
    fresh = payload["key"]
    assert fresh != KEY
    status, _ = call(handle.port, f"/v1/ping?key={KEY}")
    assert status == 401
    status, _ = call(handle.port, f"/v1/ping?key={fresh}")
    assert status == 200
    status, body = call(handle.port, f"/v1/key?master={MASTER}")
    assert json.loads(body)["key"] == fresh
    # A bad minimum is a parameter error, not a rotation.
    status, _ = call(handle.port, f"/v1/rotate?master={MASTER}&min=soon")
    assert status == 400


def test_header_key_and_ping_payload(tmp_path):
  with backend(tmp_path) as handle:
    status, body = call(handle.port, "/v1/ping", {"X-Extension-Key": KEY})
    assert status == 200
    payload = json.loads(body)
    assert (
      payload["repo"] == "o/r" and payload["token"] is True and payload["llm"] is True
    )


def test_gh_forwards_path_query_and_token(tmp_path):
  with backend(tmp_path) as handle:
    status, body = call(
      handle.port,
      f"/v1/gh?key={KEY}&path=repos/o/r/code-scanning/alerts&state=open&per_page=5",
    )
    assert status == 200
    assert json.loads(body)["items"] == [{"number": 7}]
    sent = handle.stub.seen[-1]
    assert sent["auth"] == f"Bearer {TOKEN}"
    assert "state=open" in sent["path"] and "per_page=5" in sent["path"]


def test_gh_rejects_an_absolute_path(tmp_path):
  with backend(tmp_path) as handle:
    status, body = call(
      handle.port, f"/v1/gh?key={KEY}&path=https://evil.example/steal"
    )
    assert status == 400
    assert "relative" in json.loads(body)["error"]


def test_gh_folds_the_run_log_tail_into_the_route(tmp_path):
  with backend(tmp_path) as handle:
    logs = f"/v1/gh?key={KEY}&path=repos/o/r/actions/runs/1/logs"
    status, body = call(handle.port, logs)
    assert status == 200
    assert "1_Set up job.txt" in body and "test line two" in body
    # A non-log text answer keeps its text and does not enter the log parser.
    status, body = call(handle.port, f"/v1/gh?key={KEY}&path=repos/o/r/pulls/9")
    assert status == 200 and "added line" in body
    # A run log the token cannot reach answers the API status, not a tail.
    assert (
      call(handle.port, f"/v1/gh?key={KEY}&path=repos/o/r/actions/runs/2/logs")[0]
      == 404
    )


def test_gh_failed_param_keeps_only_the_error_steps(tmp_path):
  with backend(tmp_path) as handle:
    logs = f"/v1/gh?key={KEY}&failed=1&path=repos/o/r/actions/runs/1/logs"
    status, body = call(handle.port, logs)
    assert status == 200
    assert "3_Run gate.txt" in body and "##[error]" in body
    assert "1_Set up job.txt" not in body and "test line two" not in body
    # The control parameter never reaches the GitHub query.
    assert all("failed" not in seen["path"] for seen in handle.stub.seen)


def test_log_filter_keeps_early_errors_after_tail_truncation():
  stream = io.BytesIO()
  failed_tail = b"failed step tail\n"
  healthy_tail = b"healthy step tail\n"
  with zipfile.ZipFile(stream, "w") as archive:
    archive.writestr("1_failed.txt", b"##[error]early failure\n" + failed_tail * 100)
    archive.writestr("2_healthy.txt", healthy_tail * 100)
  text = github_api.log_tail(
    stream.getvalue(), cap=len(failed_tail) * 2, only_failed=True
  )
  assert failed_tail.decode().strip() in text
  assert healthy_tail.decode().strip() not in text


def test_fetch_returns_text_for_text_bytes(tmp_path):
  with backend(tmp_path) as handle:
    status, body = call(handle.port, f"/v1/fetch?key={KEY}&url={handle.stub_url}/text")
    assert status == 200
    assert json.loads(body)["text"] == "plain words\n"


def test_fetch_returns_base64_for_binary(tmp_path):
  with backend(tmp_path) as handle:
    status, body = call(
      handle.port, f"/v1/fetch?key={KEY}&url={handle.stub_url}/blob&mode=base64"
    )
    assert status == 200
    payload = json.loads(body)
    assert payload["encoding"] == "base64"
    assert "payload" not in payload
    pieces = list(compact_pages(handle.port, payload["hint"] + "&key=" + KEY))
    assert b"".join(base64.b64decode(piece["payload"]) for piece in pieces) == BINARY


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


def test_url_guard_blocks_private_and_internal_targets():
  for url in (
    "http://10.0.0.5/admin",
    "https://10.0.0.5/admin",
    "http://192.168.1.1/",
    "http://169.254.169.254/latest/meta-data/",
    "https://172.16.0.9/",
    "http://nas.local/file",
    "http://router.internal/",
    "http://printer/",
    "ftp://example.com/x",
    "file:///etc/passwd",
  ):
    assert transfers.allowed_url(url) is False, url
  for url in (
    "https://example.com/x",
    "https://raw.githubusercontent.com/o/r/main/f.bin",
    "http://127.0.0.1:8000/state",
    "http://localhost:8787/v1/health",
  ):
    assert transfers.allowed_url(url) is True, url


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
    assert "ARENA_PROXY_LLM_BASE" in json.loads(body)["hint"]


class DeadConnection:
  """A socket whose peer is gone: every write fails the way the owner's log showed."""

  def __init__(self, request):
    self.request = request

  def makefile(self, mode="rb", buffering=None):
    return io.BytesIO(self.request)

  def sendall(self, body):
    raise BrokenPipeError(32, "Broken pipe")

  def close(self):
    pass


def test_a_caller_that_leaves_early_is_no_fault(tmp_path):
  """A closed socket must not raise out of the handler, or the traceback floods the log."""
  store = core.Store(tmp_path)
  blob_id = store.put_blob(b"plain words")[0]
  for target in ("/v1/nothing", f"/v1/fetch?key={KEY}&id={blob_id}&offset=bad"):
    request = f"GET {target} HTTP/1.1\r\nHost: probe\r\n\r\n".encode()
    handler = core.ExtensionHandler(
      DeadConnection(request),
      ("127.0.0.1", 42440),
      SimpleNamespace(agent_key=KEY, store=store),
    )
    assert handler.close_connection is True


def test_unknown_route_lists_the_routes(tmp_path):
  with backend(tmp_path) as handle:
    status, body = call(handle.port, "/v1/nothing")
    assert status == 404
    assert "/v1/llm" in json.loads(body)["routes"]


def test_rotation_line_names_the_new_key():
  assert core.rotation_line("fresh-key") == "agent key (rotated): fresh-key"


def test_log_line_drops_the_query_string():
  assert core.log_line("GET", "/v1/gh?key=SECRET&path=x", 200) == "GET /v1/gh -> 200"
  assert (
    core.log_line("GET", "/v1/gh?key=SECRET", 200, "203.0.113.7")
    == "GET /v1/gh -> 200 from 203.0.113.7"
  )


def test_agent_key_is_fresh_on_every_call():
  first = core.agent_key()
  second = core.agent_key()
  assert first != second and len(first) >= 32


def compact_pages(port, target):
  for _ in range(100):
    status, body = call(port, target)
    assert status == 200
    assert len(body) <= 16_000
    payload = json.loads(body)
    assert isinstance(payload, dict)
    yield payload
    if payload["complete"]:
      return
    following = payload["next"]
    assert following.startswith("/v1/")
    assert "key=" not in following
    target = following + "&key=" + KEY
  raise AssertionError("a bounded continuation must complete")


def test_compact_gh_pages_keep_every_record_within_limits(tmp_path):
  with backend(tmp_path) as handle:
    handle.stub.alerts = [
      {
        "number": number,
        "state": "open",
        "rule": {"id": "test/rule", "description": "description" * 40},
        "most_recent_instance": {
          "ref": "refs/heads/main",
          "commit_sha": "a" * 40,
          "message": {"text": 'warning " λ' * 200},
          "location": {"path": "x.py", "start_line": number + 1},
        },
        "dismissed_by": {"login": "unused-detail" * 100},
      }
      for number in range(40)
    ]
    numbers = []
    target = f"/v1/gh?key={KEY}&path=repos/o/r/code-scanning/alerts"
    for payload in compact_pages(handle.port, target):
      assert len(payload["items"]) <= 20
      assert all("dismissed_by" not in item for item in payload["items"])
      numbers.extend(item["number"] for item in payload["items"])
    assert numbers == list(range(40))


def test_compact_fetch_text_pages_preserve_escaped_unicode(tmp_path):
  text = 'quote " slash \\ λ\n' * 2400
  with backend(tmp_path) as handle:
    handle.stub.text_body = text.encode()
    target = f"/v1/fetch?key={KEY}&url={handle.stub_url}/text"
    pieces = [payload["text"] for payload in compact_pages(handle.port, target)]
    assert "".join(pieces) == text


def test_compact_fetch_binary_starts_with_metadata(tmp_path):
  with backend(tmp_path) as handle:
    status, body = call(handle.port, f"/v1/fetch?key={KEY}&url={handle.stub_url}/blob")
    assert status == 200 and len(body) <= 16_000
    payload = json.loads(body)
    assert payload["bytes"] == len(BINARY)
    assert payload["id"] and payload["chunks"] >= 1
    assert "payload" not in payload


def test_compact_model_pages_keep_status_and_complete_text(tmp_path):
  text = "review λ\n" * 4000
  with backend(tmp_path) as handle:
    handle.stub.reply_text = text
    status, body = call(handle.port, f"/v1/llm?key={KEY}&prompt=review")
    assert status == 202
    job = json.loads(body)["job"]
    assert wait_for_job(handle.port, job)["status"] == "done"
    pieces = []
    for payload in compact_pages(handle.port, f"/v1/llm?key={KEY}&id={job}"):
      assert payload["status"] == "done"
      pieces.append(payload["text"])
    assert "".join(pieces) == text


def test_compact_unknown_gh_shape_needs_explicit_fields(tmp_path):
  with backend(tmp_path) as handle:
    target = f"/v1/gh?key={KEY}&path=repos/o/r/labels"
    status, body = call(handle.port, target + "&view=fields")
    assert status == 200 and len(body) <= 16_000
    payload = json.loads(body)
    assert "/name" in payload["fields"]
    assert "unused-detail" not in body
    selected = list(compact_pages(handle.port, target + "&fields=/name"))
    assert selected[0]["items"] == [{"name": "triage"}]
    assert "fields=" not in handle.stub.seen[-1]["path"]
    handle.stub.labels = [{"omitted": "source-value", "large": "x" * 2000}]
    selected = list(
      compact_pages(handle.port, target + "&fields=/omitted&fields=/large")
    )
    assert selected[0]["items"][0]["omitted"] == "source-value"
    assert selected[0]["partial_values"] is True


def test_gh_preserves_upstream_401_and_live_agent_key(tmp_path):
  with backend(tmp_path) as handle:
    handle.stub.alert_status = 401
    handle.stub.alerts = {"message": "Bad credentials"}
    target = f"/v1/gh?key={KEY}&path=repos/o/r/code-scanning/alerts"
    status, body = call(handle.port, target)
    assert status == 401 and len(body) <= 16_000
    assert "Bad credentials" in body
    assert call(handle.port, f"/v1/ping?key={KEY}")[0] == 200


def test_compact_gh_drains_cached_records_before_next_upstream_page(tmp_path):
  with backend(tmp_path) as handle:
    handle.stub.alert_pages = {
      "1": [{"number": i} for i in range(23)],
      "2": [{"number": i} for i in range(23, 30)],
    }
    handle.stub.alert_next = {"1": "2"}
    pages = list(
      compact_pages(
        handle.port, f"/v1/gh?key={KEY}&path=repos/o/r/code-scanning/alerts&state=open"
      )
    )
    assert [item["number"] for page in pages for item in page["items"]] == list(
      range(30)
    )
    assert [len(page["items"]) for page in pages] == [20, 3, 7]
    assert len(handle.stub.seen) == 2
    assert "state=open" in handle.stub.seen[-1]["path"]
    assert all(entry["auth"] == f"Bearer {TOKEN}" for entry in handle.stub.seen)


def test_compact_binary_chunks_keep_both_encodings_and_gzip(tmp_path):
  data = BINARY * 2000
  with backend(tmp_path) as handle:
    handle.stub.blob_body = data
    for encoding, decoder in (("base64", base64.b64decode), ("b85", base64.b85decode)):
      target = (
        f"/v1/fetch?key={KEY}&url={handle.stub_url}/blob&encoding={encoding}&gzip=1"
      )
      status, body = call(handle.port, target)
      assert status == 200
      metadata = json.loads(body)
      assert "payload" not in metadata and metadata["chunks"] > 1
      pieces = list(compact_pages(handle.port, metadata["hint"] + "&key=" + KEY))
      assert all(piece["encoding"] == encoding + "+gzip" for piece in pieces)
      assert (
        b"".join(gzip.decompress(decoder(piece["payload"])) for piece in pieces) == data
      )
    handle.stub.blob_body = b""
    status, body = call(
      handle.port, f"/v1/fetch?key={KEY}&url={handle.stub_url}/blob&mode=base64"
    )
    assert status == 200
    metadata = json.loads(body)
    pieces = list(compact_pages(handle.port, metadata["hint"] + "&key=" + KEY))
    assert len(pieces) == metadata["chunks"] == 1
    assert base64.b64decode(pieces[0]["payload"]) == b""


def test_compact_field_discovery_and_value_reads_keep_pointer_scope(tmp_path):
  nested = {f"field-{index:02}": "x" * 20000 for index in range(25)}
  with backend(tmp_path) as handle:
    handle.stub.labels = [{"a/b~": nested}]
    target = f"/v1/gh?key={KEY}&path=repos/o/r/labels"
    status, body = call(handle.port, target)
    assert status == 200
    blob_id = json.loads(body)["id"]
    scope = f"/v1/gh?key={KEY}&id={blob_id}&view=fields&pointer=/0/a~1b~0"
    pages = list(compact_pages(handle.port, scope))
    assert [field for page in pages for field in page["fields"]] == [
      "/" + key for key in sorted(nested)
    ]
    scope = f"/v1/gh?key={KEY}&id={blob_id}&view=value&pointer=/0/a~1b~0/field-00"
    text = "".join(page["text"] for page in compact_pages(handle.port, scope))
    assert json.loads(text) == nested["field-00"]
    assert (
      call(handle.port, f"/v1/gh?key={KEY}&id={blob_id}&fields=not-a-pointer")[0] == 400
    )


def test_compact_reads_keep_fetch_and_stage_caps_and_reject_bad_offsets(tmp_path):
  with backend(tmp_path, fetch_cap=2) as handle:
    assert (
      call(handle.port, f"/v1/fetch?key={KEY}&url={handle.stub_url}/blob")[0] == 413
    )
  with backend(tmp_path, stage_cap=2) as handle:
    assert (
      call(handle.port, f"/v1/fetch?key={KEY}&url={handle.stub_url}/blob")[0] == 413
    )
  with backend(tmp_path) as handle:
    status, body = call(handle.port, f"/v1/fetch?key={KEY}&url={handle.stub_url}/text")
    assert status == 200
    blob_id = json.loads(body)["id"]
    for offset in ("-1", "not-a-number", "1000000"):
      assert (
        call(handle.port, f"/v1/fetch?key={KEY}&id={blob_id}&offset={offset}")[0] == 400
      )


def test_compact_known_shapes_omit_bulk_and_secret_values(tmp_path):
  marker = "large-unused-or-secret-value"
  code = {"number": 8, "state": "open", "dismissed_by": marker}
  secret = {
    "number": 8,
    "state": "open",
    "secret_type": "test-token",
    "secret": marker,
    "html_url": "https://example.com/alert",
    "locations_url": "https://example.com/locations",
  }
  location = {
    "type": "commit",
    "details": {
      "path": "x.py",
      "start_line": 4,
      "blob_url": "https://example.com/blob",
      "commit_url": "https://example.com/commit",
      "unused": marker,
    },
  }
  instance = {
    "ref": "refs/heads/main",
    "location": {"path": "x.py", "start_line": 4},
    "unused": marker,
  }
  artifact = {
    "id": 2,
    "name": "bundle",
    "size_in_bytes": 42,
    "expired": False,
    "unused": marker,
  }
  job = {
    "id": 3,
    "name": "tests",
    "status": "completed",
    "conclusion": "failure",
    "steps": [{"name": marker}],
  }
  run = {
    "id": 4,
    "name": "CI",
    "status": "completed",
    "conclusion": "failure",
    "repository": {"description": marker},
  }
  cases = [
    ("code-scanning/alerts", [code], "number", 8),
    ("code-scanning/alerts/8", code, "number", 8),
    ("code-scanning/alerts/8/instances", [instance], "ref", "refs/heads/main"),
    ("secret-scanning/alerts", [secret], "number", 8),
    ("secret-scanning/alerts/8/locations", [location], "type", "commit"),
    ("actions/artifacts", {"total_count": 1, "artifacts": [artifact]}, "id", 2),
    ("actions/runs/4/jobs", {"total_count": 1, "jobs": [job]}, "id", 3),
    ("actions/runs", {"total_count": 1, "workflow_runs": [run]}, "id", 4),
  ]
  with backend(tmp_path) as handle:
    handle.stub.github_replies = {
      "/repos/o/r/" + path: value for path, value, _, _ in cases
    }
    for path, _, field, expected in cases:
      pages = list(
        compact_pages(handle.port, f"/v1/gh?key={KEY}&path=repos/o/r/{path}")
      )
      items = [item for page in pages for item in page["items"]]
      assert len(items) == 1 and items[0][field] == expected
      assert marker not in json.dumps(pages)
      if path.endswith("/locations"):
        assert len([name for name in items[0]["details"] if name.endswith("_url")]) == 1
    base = handle.stub_url
    status, raw = github_api.request(
      "repos/o/r/secret-scanning/alerts", TOKEN, api=base
    )
    assert status == 200 and json.loads(raw) == [secret]


def test_compact_github_links_stay_within_the_configured_api():
  api = "https://api.example.com/api/v3"
  assert (
    github_api.next_target(
      '<https://api.example.com/api/v3/repos/o/r?page=2>; rel="next"', api
    )
    == "repos/o/r?page=2"
  )
  assert (
    github_api.next_target(
      '<https://api.example.com/api/v3/repos/o/r?page=1>; rel="prev"', api
    )
    is None
  )
  for target in (
    "https://other.example.com/api/v3/repos/o/r",
    "http://api.example.com/api/v3/repos/o/r",
    "https://api.example.com/outside/repos/o/r",
  ):
    try:
      github_api.next_target(f'<{target}>; rel="next"', api)
    except ValueError:
      pass
    else:
      raise AssertionError("an upstream next link must stay within the configured API")


def post_json(port, target, payload, headers=None, method="POST"):
  body_bytes = json.dumps(payload).encode("utf-8") if payload is not None else b""
  req_headers = {"Content-Type": "application/json"}
  if headers:
    req_headers.update(headers)
  connection = http.client.HTTPConnection("127.0.0.1", port, timeout=15)
  try:
    connection.request(method, target, body=body_bytes, headers=req_headers)
    response = connection.getresponse()
    raw = response.read().decode("utf-8")
    return (
      response.status,
      (json.loads(raw) if raw else {}),
      dict(response.getheaders()),
    )
  finally:
    connection.close()


def test_private_board_routes_stay_hidden_and_require_master_key(tmp_path):
  with backend(tmp_path) as handle:
    assert "/v1/board" not in core.ROUTES
    assert "/v1/board/files" not in core.ROUTES
    status, ping_body = call(handle.port, f"/v1/ping?key={KEY}")
    assert status == 200 and "board" not in ping_body
    status, unknown_body = call(handle.port, "/v1/nothing")
    assert status == 404 and "board" not in unknown_body
    status, post_old, _ = post_json(handle.port, f"/v1/ping?key={KEY}", {})
    assert status == 404 and "board" not in json.dumps(post_old)
    assert call(handle.port, "/v1/board")[0] == 401
    assert call(handle.port, f"/v1/board?key={KEY}")[0] == 401
    assert call(handle.port, "/v1/board", {"X-Extension-Key": KEY})[0] == 401
    assert post_json(handle.port, "/v1/board", {}, {"X-Master-Key": "wrong"})[0] == 401
    opt_status, _, opt_headers = post_json(
      handle.port, "/v1/board", None, method="OPTIONS"
    )
    assert opt_status == 204
    assert opt_headers.get("Access-Control-Allow-Origin") == "*"
    assert "X-Master-Key" in (opt_headers.get("Access-Control-Allow-Headers") or "")
  with backend(tmp_path, master="") as closed:
    status, closed_body = call(closed.port, f"/v1/board?master={MASTER}")
    assert status == 404 and "board" not in closed_body


def test_private_board_sync_merges_persists_isolates_and_stages_files(tmp_path):
  alpha = "alpha111-clankers"
  delta = "delta222-clankers"
  unopted = "solo999-daedalus"
  headers = {"X-Master-Key": MASTER}
  with backend(tmp_path) as handle:
    st, init_snap = call(handle.port, "/v1/board", headers)
    assert st == 200
    assert json.loads(init_snap)["revision"] == 0

    st, res1, _ = post_json(
      handle.port,
      "/v1/board",
      {
        "action": "sync",
        "session_id": alpha,
        "repo": "clankers",
        "board": {
          "session_id": alpha,
          "repo": "clankers",
          "main_session_id": alpha,
          "allowed_sessions": [alpha, delta],
          "removed_sessions": [alpha],
          "worker_ids": {delta: "delta"},
          "sessions": [
            {"session_id": alpha, "repo": "clankers", "status": "active"},
            {
              "session_id": delta,
              "repo": "clankers",
              "status": "polling",
              "polling": True,
            },
          ],
          "entries": [
            {
              "id": "p-file-1",
              "session_id": alpha,
              "to": delta,
              "repo": "clankers",
              "at": "2026-10-27T05:00:00Z",
              "text": "@delta review patch",
              "file": {
                "name": "patches/fix.patch",
                "encoding": "utf-8",
                "content": "diff --git a/a b/a\n",
              },
            }
          ],
        },
      },
      headers,
    )
    assert st == 200 and res1["ok"] is True
    rev1 = res1["revision"]
    assert rev1 == 1
    assert alpha in res1["board"]["allowed_sessions"]
    assert alpha not in res1["board"]["removed_sessions"]
    stored_entry = res1["board"]["entries"][0]
    assert stored_entry["file"]["staged"] is True
    assert "content" not in stored_entry["file"]

    st, unchanged_raw = call(handle.port, f"/v1/board?since={rev1}", headers)
    assert st == 200 and json.loads(unchanged_raw) == {
      "ok": True,
      "unchanged": True,
      "revision": rev1,
    }

    st, file_raw = call(
      handle.port,
      f"/v1/board/files?session_id={alpha}&name=patches/fix.patch",
      headers,
    )
    assert st == 200
    file_payload = json.loads(file_raw)["file"]
    assert file_payload["content"] == "diff --git a/a b/a\n"
    assert (
      call(handle.port, f"/v1/board/files?session_id={alpha}&name=../secret", headers)[
        0
      ]
      == 400
    )

    st, unopted_res, _ = post_json(
      handle.port,
      "/v1/board",
      {
        "action": "sync",
        "session_id": unopted,
        "repo": "daedalus",
        "board": {
          "session_id": unopted,
          "repo": "daedalus",
          "sessions": [{"session_id": unopted, "repo": "daedalus", "status": "active"}],
        },
      },
      headers,
    )
    assert st == 200
    assert unopted_res["scoped_board"]["entries"] == []
    assert unopted_res["scoped_board"]["main_session_id"] == ""

    st, act_res, _ = post_json(
      handle.port,
      "/v1/board",
      {
        "action": "apply",
        "board_action": {
          "action": "worker-task",
          "session_id": alpha,
          "target": "delta",
          "op": "set",
          "task_id": "t-delta",
          "title": "Audit rule",
        },
      },
      headers,
    )
    assert st == 200 and act_res["ok"] is True
    assert delta in act_res["board"]["wakes"]

    # Userscript v1.12.1 compatibility aliases ("merge", "action", "?sha256=", unopted heartbeat):
    st, merge_res, _ = post_json(
      handle.port,
      "/v1/board",
      {
        "action": "merge",
        "session_id": alpha,
        "repo": "clankers",
        "board": {"session_id": alpha, "repo": "clankers"},
      },
      headers,
    )
    assert st == 200 and merge_res["ok"] is True
    st, hb_res, _ = post_json(
      handle.port,
      "/v1/board",
      {
        "action": "action",
        "board_action": {
          "type": "heartbeat",
          "session_id": "fresh888-daedalus",
          "repo": "daedalus",
          "status": "active",
        },
      },
      headers,
    )
    assert st == 200 and hb_res["ok"] is True
    assert "fresh888-daedalus" not in {
      s["session_id"] for s in hb_res["board"]["sessions"] if isinstance(s, dict)
    }
    sha = file_payload["sha256"]
    st, sha_raw = call(handle.port, f"/v1/board/files?sha256={sha}", headers)
    assert st == 200
    sha_body = json.loads(sha_raw)
    assert sha_body["content"] == "diff --git a/a b/a\n"
    assert sha_body["file"]["content"] == "diff --git a/a b/a\n"

  with backend(tmp_path) as restarted:
    st, snap_raw = call(
      restarted.port, f"/v1/board?session_id={delta}&repo=clankers", headers
    )
    assert st == 200
    snap = json.loads(snap_raw)
    assert snap["revision"] >= 2
    assert len(snap["scoped_board"]["entries"]) == 1
    assert snap["scoped_board"]["main_session_id"] == alpha

    # Revoking a worker persists across stale peer syncs and revoked self-syncs:
    beta = "beta2222-clankers"
    st, opt_res, _ = post_json(
      restarted.port,
      "/v1/board",
      {"action": "apply", "board_action": {"action": "allow", "session_id": beta}},
      headers,
    )
    assert st == 200 and beta in opt_res["board"]["allowed_sessions"]
    st, rev_res, _ = post_json(
      restarted.port,
      "/v1/board",
      {"action": "apply", "board_action": {"action": "revoke", "session_id": beta}},
      headers,
    )
    assert st == 200 and beta not in rev_res["board"]["allowed_sessions"]
    assert beta in rev_res["board"]["removed_sessions"]
    st, peer_sync, _ = post_json(
      restarted.port,
      "/v1/board",
      {
        "action": "sync",
        "session_id": delta,
        "repo": "clankers",
        "board": {
          "session_id": delta,
          "repo": "clankers",
          "allowed_sessions": [alpha, delta, beta],
          "main_session_id": alpha,
          "sessions": [{"session_id": delta, "repo": "clankers"}],
        },
      },
      headers,
    )
    assert st == 200 and beta not in peer_sync["board"]["allowed_sessions"]
    assert beta in peer_sync["board"]["removed_sessions"]
    st, self_sync, _ = post_json(
      restarted.port,
      "/v1/board",
      {
        "action": "sync",
        "session_id": beta,
        "repo": "clankers",
        "board": {
          "session_id": beta,
          "repo": "clankers",
          "allowed_sessions": [alpha, beta],
          "main_session_id": alpha,
          "sessions": [{"session_id": beta, "repo": "clankers"}],
        },
      },
      headers,
    )
    assert st == 200 and beta not in self_sync["board"]["allowed_sessions"]
    assert beta not in self_sync["board"]["worker_ids"]

    # Advancing main's remote_head or origin_main_head wakes opted-in workers:
    sha_1 = "1" * 40
    sha_2 = "2" * 40
    st, seed_heads, _ = post_json(
      restarted.port,
      "/v1/board",
      {
        "action": "sync",
        "session_id": alpha,
        "repo": "clankers",
        "board": {
          "session_id": alpha,
          "repo": "clankers",
          "allowed_sessions": [alpha, delta],
          "main_session_id": alpha,
          "sessions": [
            {
              "session_id": alpha,
              "repo": "clankers",
              "remote_head": sha_1,
              "origin_main_head": sha_1,
              "updated_at": "2026-10-27T08:00:00Z",
            },
            {"session_id": delta, "repo": "clankers"},
          ],
        },
      },
      headers,
    )
    assert st == 200
    assert delta not in seed_heads["board"]["wakes"]
    st, moved_heads, _ = post_json(
      restarted.port,
      "/v1/board",
      {
        "action": "sync",
        "session_id": alpha,
        "repo": "clankers",
        "board": {
          "session_id": alpha,
          "repo": "clankers",
          "allowed_sessions": [alpha, delta],
          "main_session_id": alpha,
          "sessions": [
            {
              "session_id": alpha,
              "repo": "clankers",
              "remote_head": sha_2,
              "origin_main_head": sha_1,
              "updated_at": "2026-10-27T08:01:00Z",
            },
            {"session_id": delta, "repo": "clankers"},
          ],
        },
      },
      headers,
    )
    assert st == 200
    assert moved_heads["board"]["wakes"].get(delta) == f"main-moved:{sha_2[:12]}"
