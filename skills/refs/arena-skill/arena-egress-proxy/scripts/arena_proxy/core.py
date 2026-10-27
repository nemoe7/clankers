"""HTTP server, routing and configuration for the Arena proxy backend.

One class owns the state, and one handler owns the routes. Every route answers
GET, because the calling tool sends nothing else. The agent key arrives in the
query string or the `X-Extension-Key` header, and each log line drops the query
string so no key lands in a log.
"""

import argparse
import gzip
import hmac
import json
import os
import secrets
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import VERSION, github_api, output, transfers
from .board import BoardStore
from .llm import LlmService
from .store import Store

API_CAP_BYTES = 1_000_000
BOARD_BODY_CAP_BYTES = 4 * 1024 * 1024
PUBLIC_ROUTES = ("/v1/health",)
# The key route carries its own master check instead of the agent key.
MASTER_ROUTES = ("/v1/key",)
# A hidden route answers by name and appears in no route list.
HIDDEN_ROUTES = ("/v1/rotate",)
PRIVATE_BOARD_ROUTES = ("/v1/board", "/v1/board/files")
ROUTES = (
  "/v1/health",
  "/v1/ping",
  "/v1/gh",
  "/v1/fetch",
  "/v1/llm",
  "/v1/key",
)


def rotation_line(key):
  """The rotate log line: the owner reads the new key here, as on a start."""
  return f"agent key (rotated): {key}"


def log_line(method, target, code, address=None):
  "Format one log line without its query string. This prevents keys in logs."
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
    board_store=None,
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
    self.board_store = board_store


class ExtensionHandler(BaseHTTPRequestHandler):
  """Answer the key-gated routes and private master-key board routes."""

  server_version = f"arena-proxy/{VERSION}"
  protocol_version = "HTTP/1.1"

  def do_OPTIONS(self):
    try:
      self.send_response(204)
      self.send_header("Access-Control-Allow-Origin", "*")
      self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
      self.send_header(
        "Access-Control-Allow-Headers",
        "Content-Type, X-Master-Key, X-Extension-Key",
      )
      self.send_header("Access-Control-Max-Age", "86400")
      self.send_header("Content-Length", "0")
      self.end_headers()
    except (BrokenPipeError, ConnectionResetError):
      self.close_connection = True

  def do_GET(self):
    self._dispatch(self._route)

  def do_POST(self):
    self._dispatch(self._route_post)

  def _dispatch(self, fn):
    try:
      fn()
    except (BrokenPipeError, ConnectionResetError):
      # A caller that leaves before the answer is not a fault: close without a traceback.
      self.close_connection = True
    except Exception as error:
      if isinstance(error, transfers.TransferError):
        status, message = error.status, error.message
      elif isinstance(error, output.OutputError):
        status, message = 400, str(error)
      else:
        status, message = 500, f"internal error: {type(error).__name__}"
      try:
        self._send_json(status, {"error": message})
      except (BrokenPipeError, ConnectionResetError):
        self.close_connection = True

  def _route(self):
    path, params = split_target(self.path)
    route = path.rstrip("/") or "/"
    if route in HIDDEN_ROUTES:
      self._rotate(params)
      return
    if route in PRIVATE_BOARD_ROUTES:
      self._board_get(route, params)
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
    elif route == "/v1/gh":
      self._gh(params)
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
    print(rotation_line(self.server.agent_key), flush=True)
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

  def _put_blob(self, data):
    if len(data) > self.server.stage_cap:
      raise transfers.TransferError(413, "response exceeds the configured stage cap")
    return self.server.store.put_blob(data)

  def _cache(self, value):
    return self._put_blob(output.serialize(value).encode())[0]

  def _gh(self, params):
    cached = None
    blob_id = params.get("id", [""])[0]
    if blob_id:
      blob = self.server.store.get_blob(blob_id)
      if blob is None:
        self._send_json(404, {"error": "unknown or expired id"})
        return
      try:
        cached = json.loads(blob["path"].read_bytes())
        if cached.get("kind") not in ("github", "github-text"):  # nonemo: NMO100
          raise ValueError()
      except (ValueError, AttributeError):
        raise output.OutputError("id is not a GitHub response") from None
      if params.get("advance", [""])[0] != "1":
        self._gh_page(cached, blob_id, params)
        return
      target = cached.get("next_target")
      if not target:
        self._send_json(404, {"error": "no next GitHub page"})
        return
      path = target.split("?", 1)[0]
    else:
      path = params.get("path", [""])[0].strip()
      if not path or "://" in path or path.startswith("/") or ".." in path.split("/"):
        self._send_json(400, {"error": "path must be a relative api.github.com path"})
        return
      controls = {
        "key",
        "path",
        "failed",
        "id",
        "offset",
        "view",
        "fields",
        "pointer",
        "advance",
      }
      query = urllib.parse.urlencode(
        [
          (name, value)
          for name, values in sorted(params.items())
          if name not in controls
          for value in values
        ]
      )
      target = path + ("?" + query if query else "")
    logs = (
      path.startswith("repos/") and path.endswith("/logs") and "/actions/runs/" in path
    )
    status, body, links = github_api.request(
      target,
      self.server.token,
      cap=transfers.DEFAULT_STAGE_CAP if logs else API_CAP_BYTES,
      api=self.server.api,
      with_links=True,
    )
    cap = transfers.DEFAULT_STAGE_CAP if logs else API_CAP_BYTES
    if len(body) > cap:
      self._send_json(
        502 if status == 200 else status,
        {
          "error": f"response exceeds {cap} bytes",
          "hint": "narrow the request, for example with per_page",
        },
      )
      return
    record = {
      "path": path,
      "status": status,
      "pointer": params.get("pointer", [cached.get("pointer", "") if cached else ""])[
        0
      ],
      "fields": params.get("fields", cached.get("fields", []) if cached else []),
      "view": params.get("view", [cached.get("view", "") if cached else ""])[0],
    }
    if logs and status == 200:
      failed = params.get("failed", [""])[0].strip().lower() in ("1", "true", "yes")
      text = github_api.log_tail(body, only_failed=failed)
      if text is None:
        self._send_json(502, {"error": "the log download was not a zip archive"})
        return
      record.update(kind="github-text", text=text)  # nonemo: NMO100
    else:
      try:
        value = json.loads(body)
      except ValueError:
        value = None
      if status != 200 or value is None:
        record.update(
          kind="github-text",  # nonemo: NMO100
          text=body.decode("utf-8", "replace"),
        )
      else:
        try:
          next_target = github_api.next_target(links, self.server.api)
        except ValueError as error:
          self._send_json(502, {"error": str(error)})
          return
        record.update(
          kind="github",  # nonemo: NMO100
          data=value,
          next_target=next_target,
        )
    blob_id = self._cache(record)
    self._gh_page(record, blob_id, dict(params, offset=["0"]))

  def _gh_page(self, record, blob_id, params):
    route = "/v1/gh"
    offset = output.number(params, "offset")
    metadata = {"id": blob_id, "source": "github"}
    status = record["status"]
    if record["kind"] == "github-text":  # nonemo: NMO100
      self._send_json(
        status,
        output.text_page(
          record["text"],
          offset,
          metadata,
          lambda end: output.link(route, id=blob_id, offset=end),
        ),
      )
      return
    selected = params.get("fields", record["fields"])
    view = params.get("view", ["items" if "fields" in params else record["view"]])[0]
    pointer = params.get("pointer", [record.get("pointer", "")])[0]
    changed = (
      selected != record["fields"]
      or view != record["view"]
      or pointer != record.get("pointer", "")
    )
    if changed and view != "value":
      record = dict(record, fields=selected, view=view, pointer=pointer)
      blob_id = self._cache(record)
      metadata["id"] = blob_id
    try:
      value = output.pointer(record["data"], pointer)
    except (KeyError, IndexError):
      self._send_json(404, {"error": "unknown field"})
      return
    if view == "value":
      text = output.serialize(value)
      self._send_json(
        status,
        output.text_page(
          text,
          offset,
          metadata,
          lambda end: output.link(
            route, id=blob_id, view="value", pointer=pointer, offset=end
          ),
        ),
      )
      return
    rows = output.records(value)
    profile = output.profile(record["path"])
    metadata.update(
      offset=offset,
      details=output.link(route, id=blob_id, view="fields", pointer=pointer),
      value=output.link(route, id=blob_id, view="value", pointer=pointer),
    )
    upstream = (
      output.link(route, id=blob_id, advance=1) if record.get("next_target") else None
    )

    def following(end):
      return output.link(route, id=blob_id, offset=end)

    if view == "fields" or (not view and not selected and not profile):
      available = sorted({field for row in rows for field in output.fields(row)})
      payload = output.item_page(
        available, offset, metadata, following, key="fields", upstream=upstream
      )
    elif view in ("", "items"):
      projected = (
        [output.project(row, selected or output.defaults(profile, row)) for row in rows]
        if selected or profile
        else []
      )
      items = [item for item, _ in projected]
      metadata["partial_values"] = any(partial for _, partial in projected)
      if not selected and not profile:
        raise output.OutputError(
          "discover fields before selecting an unknown response shape"
        )
      payload = output.item_page(items, offset, metadata, following, upstream=upstream)
    else:
      raise output.OutputError("view must be fields, items, or value")
    self._send_json(status, payload)

  def _fetch(self, params):
    if "id" in params:
      if "offset" in params:
        blob = self.server.store.get_blob(params["id"][0])
        if blob is None:
          self._send_json(404, {"error": "unknown or expired id"})
          return
        data = blob["path"].read_bytes()
        if not transfers.is_text(data):
          self._send_json(415, {"error": "the bytes are not UTF-8 text"})
          return
        self._fetch_text(data, params["id"][0], params)
      else:
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
      data, _content_type = transfers.fetch_url(url, self.server.fetch_cap)
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
      self._fetch_text(data, self._put_blob(data)[0], params)
      return
    if mode == "auto" and transfers.is_text(data) and not compress:
      self._fetch_text(data, self._put_blob(data)[0], params)
      return
    self._stage(params, data)

  def _fetch_text(self, data, blob_id, params):
    self._send_json(
      200,
      output.text_page(
        data.decode("utf-8"),
        output.number(params, "offset"),
        {"id": blob_id, "bytes": len(data)},
        lambda end: output.link("/v1/fetch", id=blob_id, offset=end),
      ),
    )

  def _stage(self, params, data):
    if len(data) > self.server.stage_cap:
      self._send_json(
        413,
        {"error": f"the resource is over the {self.server.stage_cap} byte stage cap"},
      )
      return
    encoding = params.get("encoding", ["base64"])[0]
    compress = params.get("gzip", ["0"])[0] in ("1", "true", "yes")
    blob_id, size = self._put_blob(data)
    self._send_json(
      200,
      {
        "id": blob_id,
        "bytes": size,
        "encoding": f"{encoding}+gzip" if compress else encoding,
        "chunk_bytes": transfers.CHUNK_BYTES,
        "chunks": transfers.chunk_count(size),
        "hint": output.link(
          "/v1/fetch", id=blob_id, index=0, encoding=encoding, gzip=int(compress)
        ),
      },
    )

  def _chunk(self, params):
    blob_id = params["id"][0]
    blob = self.server.store.get_blob(blob_id)
    if blob is None:
      self._send_json(404, {"error": "unknown or expired id"})
      return
    index = output.number(params, "index")
    data = blob["path"].read_bytes()
    piece = b"" if not data and index == 0 else transfers.slice_for_chunk(data, index)
    if piece is None:
      self._send_json(404, {"error": "index out of range"})
      return
    encoding = params.get("encoding", ["base64"])[0]
    if encoding not in transfers.ENCODINGS:
      self._send_json(400, {"error": "encoding must be base64 or b85"})
      return
    compress = params.get("gzip", ["0"])[0] in ("1", "true", "yes")
    if compress:
      piece = gzip.compress(piece)
    payload = transfers.ENCODINGS[encoding](piece)
    chunks = transfers.chunk_count(len(data))
    complete = index + 1 == chunks
    self._send_json(
      200,
      {
        "id": blob_id,
        "index": index,
        "chunks": chunks,
        "encoding": f"{encoding}+gzip" if compress else encoding,
        "payload": payload,
        "complete": complete,
        "next": None
        if complete
        else output.link(
          "/v1/fetch",
          id=blob_id,
          index=index + 1,
          encoding=encoding,
          gzip=int(compress),
        ),
      },
    )

  def _llm(self, params):
    if "id" in params:
      job = self.server.store.get_job(params["id"][0])
      if job is None:
        self._send_json(404, {"error": "unknown or expired job id"})
        return
      text = job["text"] or ""
      metadata = {"status": job["status"], "model": job["model"], "error": job["error"]}
      if metadata["error"] and len(output.serialize(metadata)) > output.MAX_CHARS // 2:
        text = metadata["error"]
        metadata["error"] = "read text for the complete error"
      self._send_json(
        200,
        output.text_page(
          text,
          output.number(params, "offset"),
          metadata,
          lambda end: output.link("/v1/llm", id=params["id"][0], offset=end),
        ),
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
    body = output.serialize(payload).encode("utf-8")
    route = urllib.parse.urlsplit(self.path).path.rstrip("/")
    if route in ("/v1/gh", "/v1/fetch", "/v1/llm") and len(body) > output.MAX_CHARS:
      status = 502 if 200 <= status < 300 else status
      body = output.serialize(
        {
          "error": "response metadata exceeds the output limit",
          "hint": "request fewer fields or a smaller resource",
        }
      ).encode()
    self._send(status, body)

  def _route_post(self):
    path, params = split_target(self.path)
    route = path.rstrip("/") or "/"
    if route in PRIVATE_BOARD_ROUTES:
      self._board_post(route, params)
      return
    self._send_json(404, {"error": "unknown route", "routes": list(ROUTES)})

  def _check_board_master(self, params):
    expected = getattr(self.server, "master_key", "")
    board_store = getattr(self.server, "board_store", None)
    if not expected or board_store is None:
      self._send_json(404, {"error": "unknown route", "routes": list(ROUTES)})
      return None
    supplied = (
      params.get("master", [""])[0].strip()
      or self.headers.get("X-Master-Key", "").strip()
    )
    if not supplied or not hmac.compare_digest(supplied, expected):
      self._send_json(401, {"error": "wrong master key"})
      return None
    return board_store

  def _read_json_body(self):
    try:
      length = int(self.headers.get("Content-Length") or "0")
    except ValueError:
      raise output.OutputError("invalid Content-Length") from None
    if length < 0 or length > BOARD_BODY_CAP_BYTES:
      raise transfers.TransferError(413, "request body exceeds board limit")
    raw = self.rfile.read(length) if length > 0 else b"{}"
    try:
      parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
      raise output.OutputError("request body must be valid JSON") from None
    if not isinstance(parsed, dict):
      raise output.OutputError("request body must be a JSON object")
    return parsed

  def _board_get(self, route, params):
    board_store = self._check_board_master(params)
    if board_store is None:
      return
    if route == "/v1/board":
      since_raw = params.get("since", [""])[0].strip()
      since = None
      if since_raw:
        try:
          since = int(since_raw)
        except ValueError:
          self._send_json(400, {"error": "since must be an integer"})
          return
      session_id = params.get("session_id", [""])[0].strip()
      repo = params.get("repo", [""])[0].strip()
      self._send_json(
        200, board_store.snapshot(since=since, session_id=session_id, repo=repo)
      )
      return
    session_id = params.get("session_id", [""])[0].strip()
    name = params.get("name", [""])[0].strip()
    try:
      found = board_store.get_file(session_id, name)
    except ValueError as error:
      self._send_json(400, {"error": str(error)})
      return
    if found is None:
      self._send_json(404, {"error": "board file not found"})
      return
    self._send_json(200, {"ok": True, "file": found})

  def _board_post(self, route, params):
    board_store = self._check_board_master(params)
    if board_store is None:
      return
    payload = self._read_json_body()
    if route == "/v1/board/files":
      session_id = str(payload.get("session_id") or "").strip()
      try:
        info = board_store.put_file(session_id, payload.get("file"))
      except ValueError as error:
        self._send_json(400, {"error": str(error)})
        return
      self._send_json(200, {"ok": True, "file": info})
      return
    mode = str(payload.get("action") or payload.get("type") or "sync").strip().lower()
    session_id = str(payload.get("session_id") or "").strip()
    repo = str(payload.get("repo") or "").strip()
    if mode == "sync" and isinstance(payload.get("board"), dict):
      result = board_store.sync(
        payload["board"],
        session_id=session_id,
        repo=repo,
        passive=bool(payload.get("passive")),
      )
      self._send_json(200, result)
      return
    action_body = (
      payload.get("board_action")
      if mode == "apply" and isinstance(payload.get("board_action"), dict)
      else payload
    )
    result = board_store.apply(action_body, session_id=session_id, repo=repo)
    self._send_json(200 if result.get("ok") else 400, result)

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
  board_store = BoardStore(os.path.join(options.state_dir, "board"))
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
    board_store=board_store,
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
  "Return a fresh agent key. Every start makes a new one."
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
