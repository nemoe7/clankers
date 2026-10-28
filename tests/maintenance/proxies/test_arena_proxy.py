"""Tests for the arena-proxy backend: auth, forwarding, transfers and model jobs."""

import base64
import contextlib
import gzip
import hashlib
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

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "skills/arena-skill/arena-egress-proxy/scripts"
KEY = "test-agent-key-0123456789"
MASTER = "test-master-key-0123456789"
TOKEN = "test-provider-token"
BINARY = b"\x89PNG\r\n\x1a\n\x00binary payload"
sys.path.insert(0, str(SCRIPTS))
board_module = importlib.import_module("arena_proxy.board")
core = importlib.import_module("arena_proxy.core")
github_api = importlib.import_module("arena_proxy.github_api")
transfers = importlib.import_module("arena_proxy.transfers")


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
  log_lines = []
  options = SimpleNamespace(
    host="127.0.0.1",
    port=0,
    key=KEY,
    master=MASTER,
    token=TOKEN,
    api=base,
    state_dir=str(tmp_path),
    fetch_cap=transfers.DEFAULT_FETCH_CAP,
    stage_cap=transfers.DEFAULT_STAGE_CAP,
    quiet_polls=False,
    log_sink=log_lines.append,
  )
  for name, value in overrides.items():
    setattr(options, name, value)
  extension = core.build_server(options)
  threading.Thread(
    target=extension.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
  ).start()
  try:
    yield SimpleNamespace(
      stub=stub, port=extension.server_address[1], stub_url=base, logs=log_lines
    )
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
    assert payload["token"] is True
    assert "repo" not in payload
    assert "llm" not in payload
    assert "/v1/llm" not in payload["routes"]


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
    bare_status, bare_body = call(handle.port, f"/v1/gh?key={KEY}&path=pulls/9")
    assert bare_status == 400
    assert "repos/OWNER/REPO/" in json.loads(bare_body)["error"]


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


def test_llm_route_is_removed(tmp_path):
  with backend(tmp_path) as handle:
    status, body = call(handle.port, f"/v1/llm?key={KEY}&prompt=review")
    assert status == 404
    assert "/v1/llm" not in json.loads(body)["routes"]


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
      SimpleNamespace(agent_key=KEY, store=store, log_sink=lambda _: None),
    )
    assert handler.close_connection is True


def test_unknown_route_lists_the_routes(tmp_path):
  with backend(tmp_path) as handle:
    status, body = call(handle.port, "/v1/nothing")
    assert status == 404
    assert "/v1/fetch" in json.loads(body)["routes"]
    assert "/v1/llm" not in json.loads(body)["routes"]


def test_rotation_line_names_the_new_key():
  assert core.rotation_line("fresh-key") == "agent key (rotated): fresh-key"


def test_startup_and_log_lines_use_plain_human_format_without_secrets():
  assert core.startup_lines("k-1", "tok", quiet_polls=False) == [
    f"version: {core.VERSION}",
    "agent key: k-1",
    "GH token: OK",
  ]
  assert core.startup_lines("k-1", "", quiet_polls=True) == [
    f"version: {core.VERSION}",
    "agent key: k-1",
    "GH token: missing",
    "quiet polls: OK",
  ]
  assert core.format_bytes(0) == "0 B"
  assert core.format_bytes(1023) == "1023 B"
  assert core.format_bytes(1024) == "1 KiB"
  assert core.format_bytes(1536) == "1.5 KiB"
  assert core.format_bytes(2047) == "1.9 KiB"
  assert core.format_bytes(1024 * 1024) == "1 MiB"
  assert core.format_bytes(int(2.79 * 1024 * 1024)) == "2.7 MiB"
  assert core.format_bytes(1024**3 + 512 * 1024**2) == "1.5 GiB"
  assert core.log_line("GET", "/v1/gh?key=SECRET&path=x", 200) == "GET 200 /v1/gh"
  assert (
    core.log_line(
      "GET", "/v1/gh?key=SECRET", 200, "203.0.113.7", "repos/o/r/pulls/1 -> github 200"
    )
    == "GET 200 /v1/gh from 203.0.113.7: repos/o/r/pulls/1 -> github 200"
  )
  assert (
    core.safe_url_label("https://user:secret@example.com/file.bin?sig=SECRET#frag")
    == "https://example.com/file.bin"
  )


def test_exhaustive_logging_loopback_health_suppression_and_quiet_polls(tmp_path):
  headers = {"X-Master-Key": MASTER, "X-Forwarded-For": "100.64.0.2"}
  with backend(tmp_path) as handle:
    # Loopback /v1/health stays silent, while forwarded /v1/health logs cleanly.
    assert call(handle.port, "/v1/health")[0] == 200
    assert handle.logs == []
    assert call(handle.port, "/v1/health", {"X-Forwarded-For": "100.64.0.2"})[0] == 200
    assert handle.logs[-1] == "GET 200 /v1/health from 100.64.0.2"

    # Auth, ping, gh, fetch, and board interactions log without leaking secrets.
    assert (
      call(handle.port, "/v1/gh?key=wrong-secret", {"X-Forwarded-For": "198.51.100.9"})[
        0
      ]
      == 401
    )
    assert (
      handle.logs[-1]
      == "GET 401 /v1/gh from 198.51.100.9: missing or invalid agent key"
    )
    assert (
      call(
        handle.port,
        f"/v1/gh?key={KEY}&path=repos/o/r/code-scanning/alerts",
        {"X-Forwarded-For": "198.51.100.9"},
      )[0]
      == 200
    )
    assert handle.logs[-1].startswith(
      "GET 200 /v1/gh from 198.51.100.9: repos/o/r/code-scanning/alerts -> github 200"
    )
    assert (
      call(
        handle.port,
        f"/v1/fetch?key={KEY}&url={handle.stub_url}/text%3Fsig%3DSIGNED_SECRET",
        {"X-Forwarded-For": "198.51.100.9"},
      )[0]
      == 200
    )
    assert "SIGNED_SECRET" not in "\n".join(handle.logs)
    assert KEY not in "\n".join(handle.logs)
    assert MASTER not in "\n".join(handle.logs)
    assert TOKEN not in "\n".join(handle.logs)

    # Default mode logs unchanged /v1/board polls.
    st, snap_raw = call(
      handle.port, "/v1/board?session_id=alpha-clankers&repo=clankers", headers
    )
    assert st == 200
    rev = json.loads(snap_raw)["revision"]
    assert (
      call(
        handle.port,
        f"/v1/board?since={rev}&session_id=alpha-clankers&repo=clankers",
        headers,
      )[0]
      == 200
    )
    assert f"unchanged at rev {rev} for alpha-clankers (clankers)" in handle.logs[-1]

  with backend(tmp_path / "quiet", quiet_polls=True) as quiet:
    assert (
      post_json(
        quiet.port,
        "/v1/board",
        {
          "action": "sync",
          "passive": True,
          "session_id": "alpha-clankers",
          "repo": "clankers",
          "board": {},
        },
        headers,
      )[0]
      == 200
    )
    st, snap_raw = call(
      quiet.port, "/v1/board?session_id=alpha-clankers&repo=clankers", headers
    )
    assert st == 200
    rev = json.loads(snap_raw)["revision"]
    logged_after_initial = len(quiet.logs)
    assert (
      call(
        quiet.port,
        f"/v1/board?since={rev}&session_id=alpha-clankers&repo=clankers",
        headers,
      )[0]
      == 200
    )
    assert (
      post_json(
        quiet.port,
        "/v1/board",
        {
          "action": "sync",
          "passive": True,
          "session_id": "alpha-clankers",
          "repo": "clankers",
          "board": {},
        },
        headers,
      )[0]
      == 200
    )
    assert len(quiet.logs) == logged_after_initial
    assert (
      post_json(
        quiet.port,
        "/v1/board",
        {
          "action": "apply",
          "board_action": {"action": "allow", "session_id": "alpha-clankers"},
        },
        headers,
      )[0]
      == 200
    )
    assert len(quiet.logs) == logged_after_initial + 1
    assert "allow by alpha-clankers -> rev" in quiet.logs[-1]


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


def test_board_normalization_redacts_unallowlisted_survey_answers():
  allowed = "alpha111-clankers"
  unopted = "solo999-clankers"
  answer = {"id": "Q1", "correct": True, "confidence": 1, "answer": {"value": "Secret"}}
  legacy = {"id": "Q2", "correct": None, "confidence": 0}
  survey = {"results": [answer, legacy], "answered_at": "2026-01-01T00:00:00Z"}
  raw = {
    "allowed_sessions": [allowed],
    "main_session_id": allowed,
    "sessions": [
      {"session_id": allowed, "survey": survey},
      {"session_id": unopted, "survey": survey},
    ],
  }

  normalized = board_module.normalize_board(raw)
  rows = {row["session_id"]: row for row in normalized["sessions"]}
  assert rows[allowed]["survey"] == survey
  assert rows[unopted]["survey"]["results"] == [
    {"id": "Q1", "correct": True, "confidence": 1},
    legacy,
  ]
  assert raw["sessions"][1]["survey"]["results"][0] == answer


def test_board_sync_keeps_unallowlisted_survey_answers_private(tmp_path):
  allowed = "alpha111-clankers"
  unopted = "solo999-clankers"
  answer = {"id": "Q1", "correct": True, "confidence": 1, "answer": {"value": "Secret"}}
  headers = {"X-Master-Key": MASTER}
  with backend(tmp_path) as handle:
    for sid in (allowed, unopted):
      status, result, _ = post_json(
        handle.port,
        "/v1/board",
        {
          "action": "sync",
          "session_id": sid,
          "repo": "clankers",
          "board": {
            "session_id": sid,
            "allowed_sessions": [allowed],
            "main_session_id": allowed,
            "sessions": [{"session_id": sid, "survey": {"results": [answer]}}],
          },
        },
        headers,
      )
      assert status == 200
    for key in ("board", "scoped_board"):
      rows = {row["session_id"]: row for row in result[key]["sessions"]}
      assert rows[allowed]["survey"]["results"] == [answer]
      assert rows[unopted]["survey"]["results"] == [
        {"id": "Q1", "correct": True, "confidence": 1}
      ]


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

    # Expired unopted disconnected rows prune past TTL and cross-repo rows hide when multi_repo=False:
    import time as _time
    from datetime import UTC as _UTC
    from datetime import datetime as _dt

    from arena_proxy import board as board_mod

    now_sec = _time.time()
    expired_iso = (
      _dt.fromtimestamp(now_sec - (board_mod.BOARD_SESSION_TTL_SECONDS + 30), tz=_UTC)
      .isoformat()
      .replace("+00:00", "Z")
    )
    fresh_iso = (
      _dt.fromtimestamp(now_sec - (board_mod.BOARD_SESSION_TTL_SECONDS // 3), tz=_UTC)
      .isoformat()
      .replace("+00:00", "Z")
    )
    expired_daedalus = "dead1111-daedalus"
    fresh_clankers_unopted = "fresh222-clankers"
    opted_otherrepo = "opt33333-otherrepo"
    norm_pruned = board_mod.normalize_board(
      {
        "multi_repo": False,
        "allowed_sessions": [alpha, opted_otherrepo],
        "main_session_id": alpha,
        "sessions": [
          {"session_id": alpha, "repo": "clankers", "updated_at": fresh_iso},
          {
            "session_id": expired_daedalus,
            "repo": "daedalus",
            "status": "disconnected",
            "disconnected": True,
            "updated_at": expired_iso,
          },
          {
            "session_id": fresh_clankers_unopted,
            "repo": "clankers",
            "status": "disconnected",
            "disconnected": True,
            "updated_at": fresh_iso,
          },
          {
            "session_id": opted_otherrepo,
            "repo": "otherrepo",
            "status": "disconnected",
            "disconnected": True,
            "updated_at": expired_iso,
          },
        ],
      }
    )
    norm_sids = {row["session_id"] for row in norm_pruned["sessions"]}
    assert expired_daedalus not in norm_sids
    assert fresh_clankers_unopted in norm_sids
    assert opted_otherrepo in norm_sids

    scoped_single = board_mod.scope_board_for_target(
      norm_pruned, session_id=alpha, repo_hint="clankers"
    )
    scoped_sids = {row["session_id"] for row in scoped_single["sessions"]}
    assert opted_otherrepo not in scoped_sids
    assert len(scoped_single["sessions"]) < len(norm_pruned["sessions"])
    assert "otherrepo" in scoped_single["known_repos"]
    assert "daedalus" not in scoped_single["known_repos"]

    scoped_linked = board_mod.scope_board_for_target(
      dict(norm_pruned, multi_repo=True, linked_repos=["otherrepo"]),
      session_id=alpha,
      repo_hint="clankers",
    )
    assert opted_otherrepo in {row["session_id"] for row in scoped_linked["sessions"]}


def test_private_board_routes_accept_uncapped_script_sync_and_files(tmp_path):
  alpha = "alpha111-clankers"
  headers = {"X-Master-Key": MASTER}
  big_file_text = "f" * (600 * 1024)
  big_report_md = "r" * (2_200_000)
  extra_sessions = [
    {"session_id": f"{idx:08x}-clankers", "repo": "clankers", "status": "active"}
    for idx in range(1, 70)
  ]
  extra_entries = [
    {
      "id": f"e-{idx}",
      "session_id": alpha,
      "to": "*",
      "repo": "clankers",
      "at": f"2026-10-27T09:{idx // 60:02d}:{idx % 60:02d}Z",
      "text": "m" * 9_000,
    }
    for idx in range(210)
  ]
  extra_entries[0]["file"] = {
    "name": "reports/large.txt",
    "encoding": "utf-8",
    "content": big_file_text,
  }
  sync_payload = {
    "action": "sync",
    "session_id": alpha,
    "repo": "clankers",
    "board": {
      "session_id": alpha,
      "repo": "clankers",
      "main_session_id": alpha,
      "allowed_sessions": [alpha, *(row["session_id"] for row in extra_sessions)],
      "sessions": [
        {"session_id": alpha, "repo": "clankers", "status": "active"},
        *extra_sessions,
      ],
      "entries": extra_entries,
      "worker_reports": {
        alpha: [{"id": "big-rep", "title": "Big", "markdown": big_report_md}]
      },
    },
  }
  assert len(json.dumps(sync_payload).encode("utf-8")) > 4 * 1024 * 1024

  with backend(tmp_path) as handle:
    st, res, _ = post_json(handle.port, "/v1/board", sync_payload, headers)
    assert st == 200 and res["ok"] is True
    assert len(res["board"]["entries"]) == 210
    assert len(res["board"]["sessions"]) == 70
    assert len(res["board"]["worker_reports"][alpha][0]["markdown"]) == len(
      big_report_md
    )

    st_file, file_res, _ = post_json(
      handle.port,
      "/v1/board/files",
      {
        "session_id": alpha,
        "file": {
          "name": "reports/direct-large.txt",
          "encoding": "utf-8",
          "content": big_file_text,
        },
      },
      headers,
    )
    assert st_file == 200 and file_res["file"]["size"] == len(big_file_text)
    st_get, raw_get = call(
      handle.port,
      f"/v1/board/files?session_id={alpha}&name=reports/direct-large.txt",
      headers,
    )
    assert st_get == 200 and json.loads(raw_get)["file"]["content"] == big_file_text

  with backend(tmp_path) as restarted:
    st_snap, snap_raw = call(restarted.port, "/v1/board", headers)
    assert st_snap == 200
    snap_board = json.loads(snap_raw)["board"]
    assert len(snap_board["entries"]) == 210
    assert len(snap_board["sessions"]) == 70


def test_sqlite_wal_storage_legacy_migration_and_board_diff_sync(tmp_path):
  import sqlite3

  alpha = "alpha111-clankers"
  beta = "beta2222-clankers"
  headers = {"X-Master-Key": MASTER}
  board_dir = tmp_path / "board"
  files_dir = board_dir / "files" / alpha / "patches"
  files_dir.mkdir(parents=True, exist_ok=True)
  legacy_patch = "diff --git a/x.py b/x.py\n+migrated\n"
  (files_dir / "legacy.patch").write_text(legacy_patch, encoding="utf-8")
  (files_dir / "legacy.patch.meta.json").write_text(
    json.dumps({"encoding": "utf-8"}), encoding="utf-8"
  )
  legacy_sha = hashlib.sha256(legacy_patch.encode("utf-8")).hexdigest()
  (board_dir / "board.json").write_text(
    json.dumps(
      {
        "revision": 7,
        "board": {
          "main_session_id": alpha,
          "allowed_sessions": [alpha, beta],
          "sessions": [{"session_id": alpha, "repo": "clankers", "status": "active"}],
          "entries": [
            {
              "id": "e-leg",
              "session_id": alpha,
              "to": "*",
              "repo": "clankers",
              "at": "2026-10-27T01:00:00Z",
              "text": "migrated entry",
              "file": {
                "name": "patches/legacy.patch",
                "encoding": "utf-8",
                "sha256": legacy_sha,
                "size": len(legacy_patch.encode("utf-8")),
              },
            }
          ],
        },
      }
    ),
    encoding="utf-8",
  )

  with backend(tmp_path) as handle:
    db_path = tmp_path / "proxy.sqlite3"
    assert db_path.is_file()
    assert (board_dir / "board.json.migrated").is_file()
    assert not (board_dir / "board.json").exists()
    with sqlite3.connect(str(db_path)) as check_conn:
      mode = check_conn.execute("PRAGMA journal_mode").fetchone()[0]
      assert mode.lower() == "wal"

    st, raw_snap = call(handle.port, "/v1/board", headers)
    assert st == 200
    snap = json.loads(raw_snap)
    assert snap["revision"] == 7
    assert snap["board"]["entries"][0]["id"] == "e-leg"

    st_f, raw_f = call(handle.port, f"/v1/board/files?sha256={legacy_sha}", headers)
    assert st_f == 200
    assert json.loads(raw_f)["content"] == legacy_patch

    # Unchanged diff poll at revision 7:
    st_u, raw_u = call(handle.port, "/v1/board?since=7&mode=diff", headers)
    assert st_u == 200
    u_body = json.loads(raw_u)
    assert u_body["unchanged"] is True
    assert u_body["revision"] == 7

    # Stale client_rev board_diff without prior cursor returns 409 need_full:
    st_409, err_409, _ = post_json(
      handle.port,
      "/v1/board",
      {
        "action": "sync",
        "session_id": alpha,
        "repo": "clankers",
        "board_diff": {"base_rev": 3, "rev": 4, "upserts": [], "tombstones": []},
      },
      headers,
    )
    assert st_409 == 409 and err_409["need_full"] is True

    # Seed client cursor via full sync with client_rev=1, then push incremental board_diff:
    base_member = {
      "session_id": alpha,
      "repo": "clankers",
      "main_session_id": alpha,
      "allowed_sessions": [alpha, beta],
      "sessions": [{"session_id": alpha, "repo": "clankers", "status": "active"}],
      "entries": snap["board"]["entries"],
      "worker_tasks": {beta: [{"id": "t-a", "title": "First", "status": "upcoming"}]},
    }
    st_seed, seed_res, _ = post_json(
      handle.port,
      "/v1/board",
      {
        "action": "sync",
        "session_id": alpha,
        "repo": "clankers",
        "client_rev": 1,
        "board": base_member,
      },
      headers,
    )
    assert st_seed == 200
    rev_after_seed = seed_res["revision"]

    next_member = {
      **base_member,
      "entries": [
        *base_member["entries"],
        {
          "id": "e-diff-2",
          "session_id": alpha,
          "to": beta,
          "repo": "clankers",
          "at": "2026-10-27T02:00:00Z",
          "text": "delta post",
        },
      ],
      "worker_tasks": {},
    }
    from arena_proxy.sqlite_store import apply_board_diff, compute_board_diff

    member_diff = compute_board_diff(base_member, next_member, 1, 2)
    st_diff, diff_res, _ = post_json(
      handle.port,
      "/v1/board",
      {
        "action": "sync",
        "session_id": alpha,
        "repo": "clankers",
        "board_diff": member_diff,
        "reply_since": rev_after_seed,
        "reply_mode": "diff",
      },
      headers,
    )
    assert st_diff == 200
    assert diff_res["mode"] == "diff"
    reconstructed = apply_board_diff(seed_res["board"], diff_res["diff"])
    assert any(e["id"] == "e-diff-2" for e in reconstructed["entries"])

    # GET /v1/board?since=<rev_after_seed>&mode=diff returns the exact record diff:
    st_pull, raw_pull = call(
      handle.port, f"/v1/board?since={rev_after_seed}&mode=diff", headers
    )
    assert st_pull == 200
    pull_body = json.loads(raw_pull)
    assert pull_body["mode"] == "diff"
    assert any(
      u["type"] == "entry" and u["key"] == "e-diff-2"
      for u in pull_body["diff"]["upserts"]
    )


def test_private_state_route_master_auth_diff_sync_and_ndjson_hydration(tmp_path):
  headers = {"X-Master-Key": MASTER}
  with backend(tmp_path) as handle:
    # Omit /v1/state from /v1/ping and reject agent keys without X-Master-Key:
    st_ping, raw_ping = call(handle.port, f"/v1/ping?key={KEY}")
    assert st_ping == 200
    ping_routes = json.loads(raw_ping)["routes"]
    assert "/v1/state" not in ping_routes
    assert "/v1/board" not in ping_routes

    st_unauth, _ = call(handle.port, f"/v1/state?key={KEY}&repo=clankers")
    assert st_unauth == 401

    st_empty, raw_empty = call(
      handle.port, "/v1/state?repo=clankers&branch=arena/11111111-clankers", headers
    )
    assert st_empty == 200
    empty_body = json.loads(raw_empty)
    assert empty_body["exists"] is False
    assert empty_body["revision"] == 0

    scope = {"repo": "clankers", "branch": "arena/11111111-clankers"}
    core_v1 = [
      {"id": "n-1", "text": "note one", "at": "2026-10-27T01:00:00Z"},
      {"id": "t-1", "title": "Task one", "status": "upcoming"},
      {"id": "rep-1", "markdown": "# Report\n\nBody\n"},
    ]
    digest_v1 = hashlib.sha256(json.dumps(core_v1).encode("utf-8")).hexdigest()
    st_put1, put1, _ = post_json(
      handle.port,
      "/v1/state",
      {
        "action": "put",
        "scope": scope,
        "save_id": "11111111-1111-4111-8111-111111111111",
        "digest": digest_v1,
        "stamp": "2026-10-27T01:00:00Z",
        "lastsave": "2026-10-27T01:00:00Z",
        "beforelastsave": None,
        "counts": {"notes": 1, "tasks": 1, "reports": 1, "answers": 0},
        "core": core_v1,
      },
      headers,
    )
    assert st_put1 == 200 and put1["revision"] == 1

    # Stale diff base_rev returns 409 need_full:
    st_stale, stale_res, _ = post_json(
      handle.port,
      "/v1/state",
      {
        "action": "put",
        "scope": scope,
        "save_id": "22222222-2222-4222-8222-222222222222",
        "digest": "x",
        "diff": {"base_rev": 9, "rev": 10, "upserts": [], "tombstones": []},
      },
      headers,
    )
    assert st_stale == 409 and stale_res["need_full"] is True

    # Incremental diff update (upsert n-2, delete t-1):
    from arena_proxy.sqlite_store import apply_state_diff, compute_state_diff

    core_v2 = [
      {"id": "n-1", "text": "note one", "at": "2026-10-27T01:00:00Z"},
      {"id": "n-2", "text": "note two", "at": "2026-10-27T02:00:00Z"},
      {"id": "rep-1", "markdown": "# Report\n\nBody\n"},
    ]
    digest_v2 = hashlib.sha256(json.dumps(core_v2).encode("utf-8")).hexdigest()
    state_diff = compute_state_diff(core_v1, core_v2, 1, 2)
    assert len(state_diff["upserts"]) == 1 and state_diff["upserts"][0]["id"] == "n-2"
    assert state_diff["tombstones"] == [{"group": "tasks", "key": "t-1"}]

    st_put2, put2, _ = post_json(
      handle.port,
      "/v1/state",
      {
        "action": "put",
        "scope": scope,
        "save_id": "22222222-2222-4222-8222-222222222222",
        "digest": digest_v2,
        "stamp": "2026-10-27T02:00:00Z",
        "lastsave": "2026-10-27T02:00:00Z",
        "beforelastsave": "2026-10-27T01:00:00Z",
        "counts": {"notes": 2, "tasks": 0, "reports": 1, "answers": 0},
        "diff": state_diff,
      },
      headers,
    )
    assert st_put2 == 200 and put2["revision"] == 2

    # Incremental GET /v1/state?since=1&mode=diff returns only the delta:
    st_get_diff, raw_get_diff = call(
      handle.port,
      "/v1/state?repo=clankers&branch=arena/11111111-clankers&since=1&mode=diff",
      headers,
    )
    assert st_get_diff == 200
    get_diff_body = json.loads(raw_get_diff)
    assert get_diff_body["mode"] == "diff"
    rebuilt_v2 = apply_state_diff(core_v1, get_diff_body["diff"])
    assert {r["id"] for r in rebuilt_v2} == {"n-1", "n-2", "rep-1"}

    # Fallback repo lookup + include_text=1 hydrates NDJSON with history core records:
    st_text, raw_text = call(
      handle.port,
      "/v1/state?repo=clankers&branch=arena/99999999-clankers&fallback_repo=1&include_text=1",
      headers,
    )
    assert st_text == 200
    text_body = json.loads(raw_text)
    assert text_body["exists"] is True
    lines = [
      json.loads(line) for line in text_body["text"].splitlines() if line.strip()
    ]
    hist_rows = [row for row in lines if row.get("type") == "userscript-autosave"]
    assert len(hist_rows) == 2
    assert isinstance(hist_rows[-1]["core"], list) and len(hist_rows[-1]["core"]) == 3
