"""HTTP server, routing and configuration for the Arena proxy backend.

One class owns the state, and one handler owns the routes. Every route answers
GET, because the calling tool sends nothing else. The agent key arrives in the
query string or the `X-Extension-Key` header, and each log line drops the query
string so no key lands in a log.
"""

import argparse
import hmac
import json
import os
import secrets
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import VERSION, github_api, transfers
from .llm import LlmService
from .store import Store

API_CAP_BYTES = 1_000_000
PUBLIC_ROUTES = ("/v1/health",)
# The key route carries its own master check instead of the agent key.
MASTER_ROUTES = ("/v1/key",)
# A hidden route answers by name and appears in no route list.
HIDDEN_ROUTES = ("/v1/rotate",)
ROUTES = (
  "/v1/health",
  "/v1/ping",
  "/v1/github",
  "/v1/logs",
  "/v1/fetch",
  "/v1/llm",
  "/v1/key",
)


def log_line(method, target, code, address=None):
  """Format one log line with the query string removed, so no key is written."""
  line = f"{method} {urllib.parse.urlsplit(target).path} -> {code}"
  return f"{line} from {address}" if address else line


def split_target(target):
  """Split a request target into its path and its query parameters."""
  parts = urllib.parse.urlsplit(target)
  return parts.path, urllib.parse.parse_qs(parts.query, keep_blank_values=True)


class ExtensionServer(ThreadingHTTPServer):
  """HTTP server carrying the key, the token and the configured services."""

  daemon_threads = True
  allow_reuse_address = True

  def __init__(
    self,
    address,
    *,
    agent_key,
    master_key,
    token,
    repo,
    api,
    store,
    llm,
    fetch_cap,
    stage_cap,
  ):
    super().__init__(address, ExtensionHandler)
    self.agent_key = agent_key
    self.master_key = master_key
    self.key_changed = time.monotonic()
    self.token = token
    self.repo = repo
    self.api = api
    self.store = store
    self.llm = llm
    self.fetch_cap = fetch_cap
    self.stage_cap = stage_cap


class ExtensionHandler(BaseHTTPRequestHandler):
  """Answer the key-gated routes over GET only."""

  server_version = f"arena-proxy/{VERSION}"
  protocol_version = "HTTP/1.1"

  def do_GET(self):
    try:
      self._route()
    except (BrokenPipeError, ConnectionResetError):
      # A caller that leaves before the answer is not a fault: close without a traceback.
      self.close_connection = True
    except Exception as error:
      try:
        self._send_json(500, {"error": f"internal error: {type(error).__name__}"})
      except (BrokenPipeError, ConnectionResetError):
        self.close_connection = True

  def _route(self):
    path, params = split_target(self.path)
    route = path.rstrip("/") or "/"
    if route in HIDDEN_ROUTES:
      self._rotate(params)
      return
    if route not in ROUTES:
      self._send_json(404, {"error": "unknown route", "routes": list(ROUTES)})
      return
    if (
      route not in PUBLIC_ROUTES
      and route not in MASTER_ROUTES
      and not self._authorized(params)
    ):
      self._send_json(
        401,
        {
          "error": "unauthorized",
          "hint": "pass ?key=<agent key> or an X-Extension-Key header",
        },
      )
      return
    if route == "/v1/health":
      self._send_json(200, {"ok": True, "version": VERSION})
    elif route == "/v1/ping":
      self._ping()
    elif route == "/v1/github":
      self._github(params)
    elif route == "/v1/logs":
      self._logs(params)
    elif route == "/v1/fetch":
      self._fetch(params)
    elif route == "/v1/llm":
      self._llm(params)
    elif route == "/v1/key":
      self._key(params)

  def _key(self, params):
    """Return the live agent key to the holder of the master key."""
    expected = self.server.master_key
    if not expected:
      self._send_json(
        404,
        {
          "error": "the key route is off",
          "hint": "set ARENA_PROXY_MASTER_KEY to turn it on",
        },
      )
      return
    supplied = (
      params.get("master", [""])[0].strip()
      or self.headers.get("X-Master-Key", "").strip()
    )
    if not supplied or not hmac.compare_digest(supplied, expected):
      self._send_json(401, {"error": "wrong master key"})
      return
    self._send_json(
      200,
      {
        "ok": True,
        "version": VERSION,
        "key": self.server.agent_key,
        "age": int(time.monotonic() - self.server.key_changed),
      },
    )

  def _rotate(self, params):
    """Answer the live key, and replace it only when it is old enough."""
    expected = self.server.master_key
    if not expected:
      self._send_json(404, {"error": "unknown route", "routes": list(ROUTES)})
      return
    supplied = (
      params.get("master", [""])[0].strip()
      or self.headers.get("X-Master-Key", "").strip()
    )
    if not supplied or not hmac.compare_digest(supplied, expected):
      self._send_json(401, {"error": "wrong master key"})
      return
    try:
      minimum = max(0, int(params.get("min", ["600"])[0]))
    except ValueError:
      self._send_json(400, {"error": "min must be a whole number of seconds"})
      return
    age = int(time.monotonic() - self.server.key_changed)
    if age < minimum:
      self._send_json(200, {"ok": True, "rotated": False, "age": age})
      return
    self.server.agent_key = secrets.token_urlsafe(32)
    self.server.key_changed = time.monotonic()
    print("agent key (rotated): new key issued", flush=True)
    self._send_json(
      200, {"ok": True, "rotated": True, "age": 0, "key": self.server.agent_key}
    )

  def _authorized(self, params):
    supplied = params.get("key", [""])[0] or self.headers.get("X-Extension-Key", "")
    return bool(supplied) and hmac.compare_digest(supplied, self.server.agent_key)

  def _ping(self):
    self._send_json(
      200,
      {
        "ok": True,
        "version": VERSION,
        "github_api": self.server.api,
        "repo": self.server.repo or None,
        "token": bool(self.server.token),
        "routes": list(ROUTES),
        "llm": self.server.llm.enabled(),
        "fetch_cap": self.server.fetch_cap,
        "stage_cap": self.server.stage_cap,
      },
    )

  def _github(self, params):
    path = params.get("path", [""])[0].strip()
    if not path or "://" in path or path.startswith("/") or ".." in path.split("/"):
      self._send_json(
        400,
        {
          "error": "path must be a relative api.github.com path",
          "example": "path=repos/OWNER/REPO/code-scanning/alerts",
        },
      )
      return
    query = urllib.parse.urlencode(
      [
        (name, value)
        for name, values in sorted(params.items())
        if name not in ("key", "path")
        for value in values
      ]
    )
    status, body = github_api.request(
      f"{path}" + (f"?{query}" if query else ""),
      self.server.token,
      cap=API_CAP_BYTES,
      api=self.server.api,
    )
    if status == 200 and len(body) > API_CAP_BYTES:
      self._send_json(
        502,
        {
          "error": f"response exceeds {API_CAP_BYTES} bytes",
          "hint": "narrow the request, for example with per_page",
        },
      )
      return
    self._send(status, body)

  def _logs(self, params):
    run = params.get("run", [""])[0].strip()
    repo = params.get("repo", [""])[0].strip() or self.server.repo
    if not run.isdigit():
      self._send_json(
        400, {"error": "run must be a workflow run id", "example": "/v1/logs?run=123"}
      )
      return
    if not github_api.valid_repo(repo):
      self._send_json(
        400, {"error": "repo must look like owner/name", "hint": "set ARENA_PROXY_REPO"}
      )
      return
    status, body = github_api.request(
      f"repos/{repo}/actions/runs/{run}/logs",
      self.server.token,
      cap=transfers.DEFAULT_STAGE_CAP,
      api=self.server.api,
    )
    if status != 200:
      self._send(status, body)
      return
    tail = github_api.log_tail(body)
    if tail is None:
      self._send_json(502, {"error": "the log download was not a zip archive"})
      return
    self._send(200, tail.encode("utf-8"), "text/plain; charset=utf-8")

  def _fetch(self, params):
    if "id" in params:
      self._chunk(params)
      return
    url = params.get("url", [""])[0]
    if not url:
      self._send_json(
        400,
        {"error": "url is required", "example": "/v1/fetch?url=https://…&mode=base64"},
      )
      return
    mode = params.get("mode", ["auto"])[0]
    encoding = params.get("encoding", ["base64"])[0]
    compress = params.get("gzip", ["0"])[0] in ("1", "true", "yes")
    if mode not in ("auto", "text", "base64") or encoding not in transfers.ENCODINGS:
      self._send_json(
        400,
        {"error": "mode must be auto, text or base64; encoding must be base64 or b85"},
      )
      return
    try:
      data, content_type = transfers.fetch_url(url, self.server.fetch_cap)
    except transfers.TransferError as error:
      self._send_json(error.status, {"error": error.message})
      return
    if len(data) > self.server.fetch_cap:
      self._send_json(
        413, {"error": f"the resource is over the {self.server.fetch_cap} byte cap"}
      )
      return
    if params.get("stage", ["0"])[0] in ("1", "true", "yes"):
      self._stage(params, data)
      return
    if mode == "text":
      if not transfers.is_text(data):
        self._send_json(415, {"error": "the bytes are not UTF-8 text; use mode=base64"})
        return
      self._send(200, data, content_type or "text/plain; charset=utf-8")
      return
    if mode == "auto" and transfers.is_text(data) and not compress:
      self._send(200, data, content_type or "text/plain; charset=utf-8")
      return
    payload, label = transfers.encode(data, encoding, compress)
    self._send_json(200, {"encoding": label, "bytes": len(data), "payload": payload})

  def _stage(self, params, data):
    if len(data) > self.server.stage_cap:
      self._send_json(
        413,
        {"error": f"the resource is over the {self.server.stage_cap} byte stage cap"},
      )
      return
    encoding = params.get("encoding", ["base64"])[0]
    compress = params.get("gzip", ["0"])[0] in ("1", "true", "yes")
    blob_id, size = self.server.store.put_blob(data)
    self._send_json(
      200,
      {
        "id": blob_id,
        "bytes": size,
        "encoding": f"{encoding}+gzip" if compress else encoding,
        "chunk_bytes": transfers.CHUNK_BYTES,
        "chunks": transfers.chunk_count(size),
        "hint": f"/v1/fetch?id={blob_id}&index=0",
      },
    )

  def _chunk(self, params):
    blob = self.server.store.get_blob(params["id"][0])
    index = params.get("index", ["0"])[0]
    if blob is None:
      self._send_json(404, {"error": "unknown or expired id"})
      return
    if not index.isdigit():
      self._send_json(400, {"error": "index must be a chunk number"})
      return
    data = blob["path"].read_bytes()
    piece = transfers.slice_for_chunk(data, int(index))
    if piece is None:
      self._send_json(
        404,
        {
          "error": f"index out of range; this id holds {transfers.chunk_count(len(data))} chunks"
        },
      )
      return
    encoding = params.get("encoding", ["base64"])[0]
    compress = params.get("gzip", ["0"])[0] in ("1", "true", "yes")
    payload, label = transfers.encode(piece, encoding, compress)
    self._send_json(
      200,
      {
        "id": params["id"][0],
        "index": int(index),
        "chunks": transfers.chunk_count(len(data)),
        "encoding": label
        if label == "text"
        else f"{encoding}+gzip"
        if compress
        else encoding,
        "payload": payload,
      },
    )

  def _llm(self, params):
    if "id" in params:
      job = self.server.store.get_job(params["id"][0])
      if job is None:
        self._send_json(404, {"error": "unknown or expired job id"})
        return
      self._send_json(
        200,
        {
          "status": job["status"],
          "model": job["model"],
          "text": job["text"],
          "error": job["error"],
        },
      )
      return
    if not self.server.llm.enabled():
      self._send_json(
        503,
        {
          "error": "no model endpoint is configured",
          "hint": "set ARENA_PROXY_LLM_BASE, ARENA_PROXY_LLM_KEY and ARENA_PROXY_LLM_MODEL",
        },
      )
      return
    try:
      job_id = self.server.llm.submit(params)
    except ValueError as error:
      self._send_json(400, {"error": str(error)})
      return
    self._send_json(202, {"job": job_id, "poll": f"/v1/llm?id={job_id}"})

  def _send_json(self, status, payload):
    self._send(status, json.dumps(payload, indent=2).encode("utf-8") + b"\n")

  def _send(self, status, body, content_type="application/json; charset=utf-8"):
    self.send_response(status)
    self.send_header("Content-Type", content_type)
    # The owner's userscript calls this backend from the Arena page, so the
    # browser needs one cross-origin permission on every answer.
    self.send_header("Access-Control-Allow-Origin", "*")
    self.send_header("Content-Length", str(len(body)))
    self.send_header("Cache-Control", "no-store")
    self.end_headers()
    self.wfile.write(body)

  def log_request(self, code="-", size="-"):
    print(log_line(self.command, self.path, code, self._caller()), flush=True)

  def _caller(self):
    """The caller address: the first forwarded hop, else the socket peer."""
    forwarded = self.headers.get("X-Forwarded-For", "").split(",")[0].strip()
    return (
      forwarded
      or self.headers.get("CF-Connecting-IP", "").strip()
      or self.client_address[0]
    )

  def log_message(self, format, *args):
    """Stay silent: log_request already printed the line, and a key could leak."""


def build_server(options):
  """Wire the store, the model service and the HTTP server from parsed options."""
  store = Store(options.state_dir)
  llm = LlmService(
    store,
    options.llm_base,
    options.llm_key,
    options.llm_model,
    token=options.token,
    api=options.api,
  )
  return ExtensionServer(
    (options.host, options.port),
    agent_key=options.key,
    master_key=options.master,
    token=options.token,
    repo=options.repo,
    api=options.api,
    store=store,
    llm=llm,
    fetch_cap=options.fetch_cap,
    stage_cap=options.stage_cap,
  )


def parse_args(argv=None):
  """Read the command line and the environment into one options object."""
  parser = argparse.ArgumentParser(
    description="Arena proxy backend: read-only access for an Arena agent."
  )
  parser.add_argument("--host", default=os.environ.get("ARENA_PROXY_HOST", "127.0.0.1"))
  parser.add_argument(
    "--port", type=int, default=int(os.environ.get("ARENA_PROXY_PORT", "8787"))
  )
  parser.add_argument(
    "--generate-key", action="store_true", help="print a new agent key and exit"
  )
  options = parser.parse_args(argv)
  options.token = os.environ.get("ARENA_PROXY_GITHUB_TOKEN") or os.environ.get(
    "GITHUB_TOKEN", ""
  )
  options.repo = os.environ.get("ARENA_PROXY_REPO", "")
  options.master = os.environ.get("ARENA_PROXY_MASTER_KEY", "")
  options.api = os.environ.get("ARENA_PROXY_GITHUB_API", github_api.GITHUB_API)
  options.state_dir = os.environ.get("ARENA_PROXY_STATE_DIR", "arena-proxy-state")
  options.llm_base = os.environ.get("ARENA_PROXY_LLM_BASE", "")
  options.llm_key = os.environ.get("ARENA_PROXY_LLM_KEY", "")
  options.llm_model = os.environ.get("ARENA_PROXY_LLM_MODEL", "")
  options.fetch_cap = int(
    os.environ.get("ARENA_PROXY_FETCH_CAP", transfers.DEFAULT_FETCH_CAP)
  )
  options.stage_cap = int(
    os.environ.get("ARENA_PROXY_STAGE_CAP", transfers.DEFAULT_STAGE_CAP)
  )
  return options


def agent_key():
  """Return a fresh agent key; every start makes a new one."""
  return secrets.token_urlsafe(32)


def main(argv=None):
  """Run the backend, or print a generated key."""
  options = parse_args(argv)
  if options.generate_key:
    print(secrets.token_urlsafe(32))
    return 0
  options.key = agent_key()
  os.makedirs(options.state_dir, exist_ok=True)
  server = build_server(options)
  print(f"agent key (new on every start): {options.key}", flush=True)
  print(
    f"arena-proxy {VERSION} on http://{options.host}:{options.port};"
    f" github token {'set' if options.token else 'missing'};"
    f" llm {'set' if server.llm.enabled() else 'missing'};"
    f" routes: {' '.join(ROUTES)}",
    flush=True,
  )
  try:
    server.serve_forever()
  except KeyboardInterrupt:
    print("stopped", flush=True)
  return 0
