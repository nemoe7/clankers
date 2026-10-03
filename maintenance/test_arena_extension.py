"""Tests for the arena-extension backend: auth, forwarding, log tail and key redaction."""

import contextlib
import http.client
import importlib.util
import io
import json
import threading
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
SERVER_PATH = ROOT / "skills/refs/arena-extension/scripts/server.py"
KEY = "test-agent-key-0123456789"
TOKEN = "test-provider-token"


def load_server():
  spec = importlib.util.spec_from_file_location("arena_extension_server", SERVER_PATH)
  module = importlib.util.module_from_spec(spec)
  spec.loader.exec_module(module)
  return module


def log_zip():
  stream = io.BytesIO()
  with zipfile.ZipFile(stream, "w") as archive:
    archive.writestr("1_Set up job.txt", "setup line one\nsetup line two\n")
    archive.writestr("2_Run tests.txt", "test line one\ntest line two\n")
  return stream.getvalue()


class StubHandler(BaseHTTPRequestHandler):
  """Stand in for api.github.com and record what the backend sent it."""

  def do_GET(self):
    self.server.seen.append(
      {"path": self.path, "auth": self.headers.get("Authorization")}
    )
    if self.path.startswith("/repos/o/r/actions/runs/1/logs"):
      self._write(200, log_zip(), "application/zip")
    elif self.path.startswith("/repos/o/r/code-scanning/alerts"):
      self._write(200, json.dumps([{"number": 7}]).encode(), "application/json")
    else:
      self._write(404, b'{"message": "Not Found"}', "application/json")

  def _write(self, status, body, content_type):
    self.send_response(status)
    self.send_header("Content-Type", content_type)
    self.send_header("Content-Length", str(len(body)))
    self.end_headers()
    self.wfile.write(body)

  def log_message(self, format, *args):
    """Silence the stub: the tests assert on recorded requests, not on stub logs."""


class StubGitHub(ThreadingHTTPServer):
  daemon_threads = True

  def __init__(self, address):
    super().__init__(address, StubHandler)
    self.seen = []


@contextlib.contextmanager
def backend():
  """Run the stub upstream and the extension server, and stop both on exit."""
  module = load_server()
  stub = StubGitHub(("127.0.0.1", 0))
  threading.Thread(target=stub.serve_forever, daemon=True).start()
  extension = module.ExtensionServer(
    ("127.0.0.1", 0),
    agent_key=KEY,
    token=TOKEN,
    github_api=f"http://127.0.0.1:{stub.server_address[1]}",
    repo="o/r",
  )
  threading.Thread(target=extension.serve_forever, daemon=True).start()
  try:
    yield SimpleNamespace(module=module, stub=stub, port=extension.server_address[1])
  finally:
    extension.shutdown()
    extension.server_close()
    stub.shutdown()
    stub.server_close()


def call(port, target, headers=None):
  connection = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
  try:
    connection.request("GET", target, headers=headers or {})
    response = connection.getresponse()
    return response.status, response.read().decode("utf-8")
  finally:
    connection.close()


def test_missing_and_wrong_keys_are_rejected():
  with backend() as handle:
    status, body = call(handle.port, "/v1/ping")
    assert status == 401
    assert json.loads(body)["error"] == "unauthorized"
    status, _ = call(handle.port, "/v1/ping?key=wrong-key")
    assert status == 401


def test_header_key_and_ping_payload():
  with backend() as handle:
    status, body = call(handle.port, "/v1/ping", {"X-Extension-Key": KEY})
    assert status == 200
    payload = json.loads(body)
    assert payload["ok"] is True
    assert payload["repo"] == "o/r"
    assert payload["token"] is True


def test_github_forwards_path_query_and_token():
  with backend() as handle:
    status, body = call(
      handle.port,
      "/v1/github?key="
      + KEY
      + "&path=repos/o/r/code-scanning/alerts&state=open&per_page=5",
    )
    assert status == 200
    assert json.loads(body) == [{"number": 7}]
    sent = handle.stub.seen[-1]
    assert sent["auth"] == f"Bearer {TOKEN}"
    assert "state=open" in sent["path"] and "per_page=5" in sent["path"]


def test_github_rejects_an_absolute_path():
  with backend() as handle:
    status, body = call(
      handle.port, "/v1/github?key=" + KEY + "&path=https://evil.example/steal"
    )
    assert status == 400
    assert "relative" in json.loads(body)["error"]


def test_upstream_errors_pass_through():
  with backend() as handle:
    status, body = call(
      handle.port, "/v1/github?key=" + KEY + "&path=repos/o/r/missing"
    )
    assert status == 404
    assert json.loads(body)["message"] == "Not Found"


def test_logs_route_returns_a_text_tail():
  with backend() as handle:
    status, body = call(handle.port, "/v1/logs?key=" + KEY + "&run=1")
    assert status == 200
    assert "1_Set up job.txt" in body
    assert "test line two" in body


def test_logs_route_validates_the_run_id():
  with backend() as handle:
    status, body = call(handle.port, "/v1/logs?key=" + KEY + "&run=nope")
    assert status == 400
    assert "run id" in json.loads(body)["error"]


def test_unknown_route_lists_the_routes():
  with backend() as handle:
    status, body = call(handle.port, "/v1/nothing?key=" + KEY)
    assert status == 404
    assert json.loads(body)["routes"] == ["/v1/ping", "/v1/github", "/v1/logs"]


def test_log_line_drops_the_query_string():
  module = load_server()
  assert module.log_line("GET", "/v1/github?key=SECRET&path=x", 200) == (
    "GET /v1/github -> 200"
  )


def test_log_tail_rejects_non_zip_bytes():
  module = load_server()
  assert module.log_tail(b"not a zip") is None
