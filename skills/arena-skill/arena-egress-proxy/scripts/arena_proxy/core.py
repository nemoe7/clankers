"""HTTP server, routing, and plain-English logging for the Arena proxy backend.

One class owns the state, and one handler owns the routes. Agent routes answer
GET, and private master-key board routes answer GET and POST. Secrets never
appear in request log lines.
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
from .sqlite_store import ProxySqliteEngine, StateStore
from .store import Store

API_CAP_BYTES = 1_000_000
LOOPBACK_CALLERS = frozenset({"127.0.0.1", "::1", "::ffff:127.0.0.1"})
PUBLIC_ROUTES = ("/v1/health",)
# The key route carries its own master check instead of the agent key.
MASTER_ROUTES = ("/v1/key",)
# A hidden route answers by name and appears in no route list.
HIDDEN_ROUTES = ("/v1/rotate",)
PRIVATE_BOARD_ROUTES = ("/v1/board", "/v1/board/files", "/v1/state")
ROUTES = (
  "/v1/health",
  "/v1/ping",
  "/v1/gh",
  "/v1/fetch",
  "/v1/key",
)


def format_bytes(count):
  """Format a byte count as a floored binary size with at most one decimal."""
  n = max(0, int(count))
  if n < 1024:
    return f"{n} B"
  for unit_bytes, unit_name in (
    (1024**4, "TiB"),
    (1024**3, "GiB"),
    (1024**2, "MiB"),
    (1024, "KiB"),
  ):
    if n >= unit_bytes:
      tenths = (n * 10) // unit_bytes
      whole, frac = divmod(tenths, 10)
      return f"{whole} {unit_name}" if frac == 0 else f"{whole}.{frac} {unit_name}"
  return f"{n} B"


def startup_lines(key, token, quiet_polls=False):
  """Format startup status lines without timestamps or secret token values."""
  lines = [
    f"version: {VERSION}",
    f"agent key: {key}",
    f"GH token: {'OK' if token else 'missing'}",
  ]
  if quiet_polls:
    lines.append("quiet polls: OK")
  return lines


def rotation_line(key):
  """The rotate log line: the owner reads the new key here, as on a start."""
  return f"agent key (rotated): {key}"


def log_line(method, target, code, address=None, detail=""):
  """Format one plain-English log line without query parameters or secrets."""
  route = urllib.parse.urlsplit(target).path.rstrip("/") or "/"
  line = f"{method} {code} {route}"
  if address:
    line = f"{line} from {address}"
  if detail:
    line = f"{line}: {detail}"
  return line


def safe_url_label(raw_url):
  """Return scheme, host, and path without credentials, query, or fragment."""
  try:
    parts = urllib.parse.urlsplit(str(raw_url or "").strip())
  except ValueError:
    return "invalid-url"
  host = parts.hostname or ""
  if ":" in host and not host.startswith("["):
    host = f"[{host}]"
  if parts.port:
    host = f"{host}:{parts.port}"
  path = parts.path or "/"
  if parts.scheme and host:
    return f"{parts.scheme}://{host}{path}"
  return path or "invalid-url"


def split_target(target):
  """Split a request target into its path and its query parameters."""
  parts = urllib.parse.urlsplit(target)
  return parts.path, urllib.parse.parse_qs(parts.query, keep_blank_values=True)


def _truthy_env(value):
  return str(value or "").strip().lower() in ("1", "true", "yes", "on")


class ExtensionServer(ThreadingHTTPServer):
  """HTTP server carrying the keys, token, and configured services."""

  daemon_threads = True
  allow_reuse_address = True

  def __init__(
    self,
    address,
    *,
    agent_key,
    master_key,
    token,
    api,
    store,
    fetch_cap,
    stage_cap,
    board_store=None,
    state_store=None,
    sqlite_engine=None,
    quiet_polls=False,
    log_sink=None,
  ):
    super().__init__(address, ExtensionHandler)
    self.agent_key = agent_key
    self.master_key = master_key
    self.key_changed = time.monotonic()
    self.token = token
    self.api = api
    self.store = store
    self.fetch_cap = fetch_cap
    self.stage_cap = stage_cap
    self.board_store = board_store
    self.state_store = state_store
    self.sqlite_engine = sqlite_engine
    self.quiet_polls = bool(quiet_polls)
    self.log_sink = log_sink

  def server_close(self):
    try:
      if self.board_store is not None and hasattr(self.board_store, "close"):
        self.board_store.close()
      if self.sqlite_engine is not None and hasattr(self.sqlite_engine, "close"):
        self.sqlite_engine.close()
    finally:
      super().server_close()


class ExtensionHandler(BaseHTTPRequestHandler):
  """Answer the key-gated routes and private master-key board routes."""

  server_version = f"arena-proxy/{VERSION}"
  protocol_version = "HTTP/1.1"

  def _emit_log(self, text):
    sink = getattr(self.server, "log_sink", None)
    if sink is not None:
      sink(text)
    else:
      print(text, flush=True)

  def do_OPTIONS(self):
    self._log_detail = ""
    self._suppress_poll_log = False
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
    self._log_detail = ""
    self._suppress_poll_log = False
    try:
      fn()
    except (BrokenPipeError, ConnectionResetError):
      # A caller that leaves before the answer is not a fault: close without a traceback.
      self.close_connection = True
    except Exception as error:
      if isinstance(error, transfers.TransferError):
        status, message = error.status, error.message
        self._log_detail = self._log_detail or message
      elif isinstance(error, output.OutputError):
        status, message = 400, str(error)
        self._log_detail = self._log_detail or message
      else:
        status, message = 500, f"internal error: {type(error).__name__}"
        self._log_detail = f"internal error {type(error).__name__}"
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
      self._log_detail = "unknown route"
      self._send_json(404, {"error": "unknown route", "routes": list(ROUTES)})
      return
    if (
      route not in PUBLIC_ROUTES
      and route not in MASTER_ROUTES
      and not self._authorized(params)
    ):
      self._log_detail = "missing or invalid agent key"
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
    elif route == "/v1/key":
      self._key(params)

  def _key(self, params):
    """Return the live agent key to the holder of the master key."""
    expected = self.server.master_key
    if not expected:
      self._log_detail = "master key not configured"
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
      self._log_detail = "wrong master key"
      self._send_json(401, {"error": "wrong master key"})
      return
    age = int(time.monotonic() - self.server.key_changed)
    self._log_detail = f"returned live agent key (age {age} s)"
    self._send_json(
      200,
      {
        "ok": True,
        "version": VERSION,
        "key": self.server.agent_key,
        "age": age,
      },
    )

  def _rotate(self, params):
    """Answer the live key, and replace it only when it is old enough."""
    expected = self.server.master_key
    if not expected:
      self._log_detail = "unknown route"
      self._send_json(404, {"error": "unknown route", "routes": list(ROUTES)})
      return
    supplied = (
      params.get("master", [""])[0].strip()
      or self.headers.get("X-Master-Key", "").strip()
    )
    if not supplied or not hmac.compare_digest(supplied, expected):
      self._log_detail = "wrong master key"
      self._send_json(401, {"error": "wrong master key"})
      return
    try:
      minimum = max(0, int(params.get("min", ["600"])[0]))
    except ValueError:
      self._log_detail = "min must be a whole number of seconds"
      self._send_json(400, {"error": "min must be a whole number of seconds"})
      return
    age = int(time.monotonic() - self.server.key_changed)
    if age < minimum:
      self._log_detail = f"kept current agent key (age {age} s below min {minimum} s)"
      self._send_json(
        200, {"ok": True, "version": VERSION, "rotated": False, "age": age}
      )
      return
    self.server.agent_key = secrets.token_urlsafe(32)
    self.server.key_changed = time.monotonic()
    self._emit_log(rotation_line(self.server.agent_key))
    self._log_detail = f"rotated agent key after {age} s"
    self._send_json(
      200,
      {
        "ok": True,
        "version": VERSION,
        "rotated": True,
        "age": 0,
        "key": self.server.agent_key,
      },
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
        "token": bool(self.server.token),
        "routes": list(ROUTES),
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
    advanced = False
    if blob_id:
      blob = self.server.store.get_blob(blob_id)
      if blob is None:
        self._log_detail = f"unknown or expired blob {blob_id[:16]}"
        self._send_json(404, {"error": "unknown or expired id"})
        return
      try:
        cached = json.loads(blob["path"].read_bytes())
        if cached.get("kind") not in ("github", "github-text"):  # nonemo: NMO100
          raise ValueError()
      except (ValueError, AttributeError):
        raise output.OutputError("id is not a GitHub response") from None
      if params.get("advance", [""])[0] != "1":
        offset = output.number(params, "offset")
        view = params.get("view", [cached.get("view", "")])[0] or "items"
        self._log_detail = f"cached blob {blob_id} ({view} view, offset {offset})"
        self._gh_page(cached, blob_id, params)
        return
      target = cached.get("next_target")
      if not target:
        self._log_detail = f"no next GitHub page for blob {blob_id}"
        self._send_json(404, {"error": "no next GitHub page"})
        return
      path = target.split("?", 1)[0]
      advanced = True
    else:
      path = params.get("path", [""])[0].strip()
      if not path or "://" in path or path.startswith("/") or ".." in path.split("/"):
        self._log_detail = "path must be a relative api.github.com path"
        self._send_json(400, {"error": "path must be a relative api.github.com path"})
        return
      parts = path.split("/")
      if (
        len(parts) < 3
        or parts[0] != "repos"
        or not github_api.valid_repo(f"{parts[1]}/{parts[2]}")
      ):
        self._log_detail = "repository path must start with repos/OWNER/REPO/"
        self._send_json(
          400, {"error": "repository path must start with repos/OWNER/REPO/"}
        )
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
      self._log_detail = f"{path} -> upstream response exceeded {format_bytes(cap)} cap"
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
    source_prefix = f"advanced pagination from blob {blob_id}" if advanced else path
    if logs and status == 200:
      failed = params.get("failed", [""])[0].strip().lower() in ("1", "true", "yes")
      text = github_api.log_tail(body, only_failed=failed)
      if text is None:
        self._log_detail = f"{path} -> log download was not a zip archive"
        self._send_json(502, {"error": "the log download was not a zip archive"})
        return
      record.update(kind="github-text", text=text)  # nonemo: NMO100
      new_blob = self._cache(record)
      scope_note = " (failed steps only)" if failed else ""
      self._log_detail = (
        f"{source_prefix}{scope_note} -> github {status}"
        f" ({format_bytes(len(text.encode('utf-8')))} tail, blob {new_blob})"
      )
      self._gh_page(record, new_blob, dict(params, offset=["0"]))
      return
    try:
      value = json.loads(body)
    except ValueError:
      value = None
    if status != 200 or value is None:
      text_body = body.decode("utf-8", "replace")
      record.update(kind="github-text", text=text_body)  # nonemo: NMO100
      new_blob = self._cache(record)
      self._log_detail = f"{source_prefix} -> github {status} ({format_bytes(len(body))} text, blob {new_blob})"
      self._gh_page(record, new_blob, dict(params, offset=["0"]))
      return
    try:
      next_target = github_api.next_target(links, self.server.api)
    except ValueError as error:
      self._log_detail = f"{path} -> invalid pagination link ({error})"
      self._send_json(502, {"error": str(error)})
      return
    record.update(
      kind="github",  # nonemo: NMO100
      data=value,
      next_target=next_target,
    )
    new_blob = self._cache(record)
    row_count = len(output.records(value))
    noun = "item" if row_count == 1 else "items"
    self._log_detail = (
      f"{source_prefix} -> github {status} ({row_count} {noun}, blob {new_blob})"
    )
    self._gh_page(record, new_blob, dict(params, offset=["0"]))

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
      self._log_detail = f"unknown pointer field on blob {blob_id}"
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
      blob_id = params["id"][0]
      if "offset" in params:
        blob = self.server.store.get_blob(blob_id)
        if blob is None:
          self._log_detail = f"unknown or expired blob {blob_id[:16]}"
          self._send_json(404, {"error": "unknown or expired id"})
          return
        data = blob["path"].read_bytes()
        if not transfers.is_text(data):
          self._log_detail = f"blob {blob_id} is binary, not UTF-8 text"
          self._send_json(415, {"error": "the bytes are not UTF-8 text"})
          return
        offset = output.number(params, "offset")
        self._log_detail = f"cached text blob {blob_id} at offset {offset}"
        self._fetch_text(data, blob_id, params)
      else:
        self._chunk(params)
      return
    url = params.get("url", [""])[0]
    if not url:
      self._log_detail = "missing url parameter"
      self._send_json(
        400,
        {"error": "url is required", "example": "/v1/fetch?url=https://…&mode=base64"},
      )
      return
    url_label = safe_url_label(url)
    mode = params.get("mode", ["auto"])[0]
    encoding = params.get("encoding", ["base64"])[0]
    compress = params.get("gzip", ["0"])[0] in ("1", "true", "yes")
    if mode not in ("auto", "text", "base64") or encoding not in transfers.ENCODINGS:
      self._log_detail = "invalid mode or encoding parameter"
      self._send_json(
        400,
        {"error": "mode must be auto, text or base64; encoding must be base64 or b85"},
      )
      return
    try:
      data, _content_type = transfers.fetch_url(url, self.server.fetch_cap)
    except transfers.TransferError as error:
      self._log_detail = f"{url_label} -> {error.message}"
      self._send_json(error.status, {"error": error.message})
      return
    if len(data) > self.server.fetch_cap:
      self._log_detail = (
        f"{url_label} exceeded {format_bytes(self.server.fetch_cap)} fetch cap"
      )
      self._send_json(
        413, {"error": f"the resource is over the {self.server.fetch_cap} byte cap"}
      )
      return
    if params.get("stage", ["0"])[0] in ("1", "true", "yes"):
      self._stage(params, data, url_label=url_label)
      return
    if mode == "text":
      if not transfers.is_text(data):
        self._log_detail = f"{url_label} rejected under mode=text (binary payload)"
        self._send_json(415, {"error": "the bytes are not UTF-8 text; use mode=base64"})
        return
      blob_id = self._put_blob(data)[0]
      self._log_detail = (
        f"{url_label} -> upstream 200 text ({format_bytes(len(data))}, blob {blob_id})"
      )
      self._fetch_text(data, blob_id, params)
      return
    if mode == "auto" and transfers.is_text(data) and not compress:
      blob_id = self._put_blob(data)[0]
      self._log_detail = (
        f"{url_label} -> upstream 200 text ({format_bytes(len(data))}, blob {blob_id})"
      )
      self._fetch_text(data, blob_id, params)
      return
    self._stage(params, data, url_label=url_label)

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

  def _stage(self, params, data, url_label=""):
    if len(data) > self.server.stage_cap:
      self._log_detail = f"{url_label or 'resource'} exceeded {format_bytes(self.server.stage_cap)} stage cap"
      self._send_json(
        413,
        {"error": f"the resource is over the {self.server.stage_cap} byte stage cap"},
      )
      return
    encoding = params.get("encoding", ["base64"])[0]
    compress = params.get("gzip", ["0"])[0] in ("1", "true", "yes")
    enc_label = f"{encoding}+gzip" if compress else encoding
    blob_id, size = self._put_blob(data)
    chunks = transfers.chunk_count(size)
    noun = "chunk" if chunks == 1 else "chunks"
    if url_label:
      self._log_detail = (
        f"{url_label} -> staged {format_bytes(size)} in {chunks} {enc_label} {noun}"
        f" (blob {blob_id})"
      )
    self._send_json(
      200,
      {
        "id": blob_id,
        "bytes": size,
        "encoding": enc_label,
        "chunk_bytes": transfers.CHUNK_BYTES,
        "chunks": chunks,
        "hint": output.link(
          "/v1/fetch", id=blob_id, index=0, encoding=encoding, gzip=int(compress)
        ),
      },
    )

  def _chunk(self, params):
    blob_id = params["id"][0]
    blob = self.server.store.get_blob(blob_id)
    if blob is None:
      self._log_detail = f"unknown or expired blob {blob_id[:16]}"
      self._send_json(404, {"error": "unknown or expired id"})
      return
    index = output.number(params, "index")
    data = blob["path"].read_bytes()
    piece = b"" if not data and index == 0 else transfers.slice_for_chunk(data, index)
    if piece is None:
      self._log_detail = f"chunk index {index} out of range for blob {blob_id}"
      self._send_json(404, {"error": "index out of range"})
      return
    encoding = params.get("encoding", ["base64"])[0]
    if encoding not in transfers.ENCODINGS:
      self._log_detail = "invalid encoding parameter"
      self._send_json(400, {"error": "encoding must be base64 or b85"})
      return
    compress = params.get("gzip", ["0"])[0] in ("1", "true", "yes")
    enc_label = f"{encoding}+gzip" if compress else encoding
    if compress:
      piece = gzip.compress(piece)
    payload = transfers.ENCODINGS[encoding](piece)
    chunks = transfers.chunk_count(len(data))
    complete = index + 1 == chunks
    self._log_detail = f"staged blob {blob_id} chunk {index + 1}/{chunks} ({enc_label})"
    self._send_json(
      200,
      {
        "id": blob_id,
        "index": index,
        "chunks": chunks,
        "encoding": enc_label,
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

  def _send_json(self, status, payload):
    body = output.serialize(payload).encode("utf-8")
    route = urllib.parse.urlsplit(self.path).path.rstrip("/")
    if route in ("/v1/gh", "/v1/fetch") and len(body) > output.MAX_CHARS:
      status = 502 if 200 <= status < 300 else status
      self._log_detail = "response metadata exceeded 16000 char output cap"
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
    self._log_detail = "unknown route"
    self._send_json(404, {"error": "unknown route", "routes": list(ROUTES)})

  def _check_board_master(self, params):
    expected = getattr(self.server, "master_key", "")
    board_store = getattr(self.server, "board_store", None)
    if not expected or board_store is None:
      self._log_detail = "unknown route"
      self._send_json(404, {"error": "unknown route", "routes": list(ROUTES)})
      return None
    supplied = (
      params.get("master", [""])[0].strip()
      or self.headers.get("X-Master-Key", "").strip()
    )
    if not supplied or not hmac.compare_digest(supplied, expected):
      self._log_detail = "wrong master key"
      self._send_json(401, {"error": "wrong master key"})
      return None
    return board_store

  def _check_state_master(self, params):
    expected = getattr(self.server, "master_key", "")
    state_store = getattr(self.server, "state_store", None)
    board_store = getattr(self.server, "board_store", None)
    if (
      state_store is None and board_store is not None and hasattr(board_store, "engine")
    ):
      state_store = StateStore(board_store.engine)
      self.server.state_store = state_store
    if not expected or state_store is None:
      self._log_detail = "unknown route"
      self._send_json(404, {"error": "unknown route", "routes": list(ROUTES)})
      return None
    supplied = (
      params.get("master", [""])[0].strip()
      or self.headers.get("X-Master-Key", "").strip()
    )
    if not supplied or not hmac.compare_digest(supplied, expected):
      self._log_detail = "wrong master key"
      self._send_json(401, {"error": "wrong master key"})
      return None
    return state_store

  def _read_json_body(self):
    try:
      length = int(self.headers.get("Content-Length") or "0")
    except ValueError:
      raise output.OutputError("invalid Content-Length") from None
    if length < 0:
      raise output.OutputError("invalid Content-Length")
    raw = self.rfile.read(length) if length > 0 else b"{}"
    try:
      parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
      raise output.OutputError("request body must be valid JSON") from None
    if not isinstance(parsed, dict):
      raise output.OutputError("request body must be a JSON object")
    return parsed

  def _board_get(self, route, params):
    if route == "/v1/state":
      state_store = self._check_state_master(params)
      if state_store is None:
        return
      repo = params.get("repo", [""])[0].strip()
      branch = params.get("branch", [""])[0].strip()
      fallback_repo = _truthy_env(params.get("fallback_repo", [""])[0])
      include_text = _truthy_env(params.get("include_text", [""])[0])
      mode = params.get("mode", ["full"])[0].strip().lower() or "full"
      since_raw = params.get("since", [""])[0].strip()
      since = None
      if since_raw:
        try:
          since = int(since_raw)
        except ValueError:
          self._log_detail = "since must be an integer"
          self._send_json(400, {"error": "since must be an integer"})
          return
      try:
        snap = state_store.get_state(
          repo,
          branch,
          fallback_repo=fallback_repo,
          since=since,
          mode=mode,
          include_text=include_text,
        )
      except (ValueError, TypeError) as error:
        self._log_detail = str(error)
        self._send_json(400, {"error": str(error)})
        return
      scope_label = f"{repo}/{branch}" if branch else repo
      rev = snap.get("revision", 0)
      if not snap.get("found"):
        self._log_detail = f"no saved state for {scope_label}"
      elif snap.get("unchanged"):
        self._suppress_poll_log = bool(getattr(self.server, "quiet_polls", False))
        self._log_detail = f"state unchanged at rev {rev} for {scope_label}"
      elif snap.get("mode") == "diff":
        diff = snap.get("diff") or {}
        up_n = len(diff.get("upserts") or [])
        del_n = len(diff.get("tombstones") or [])
        self._log_detail = (
          f"served state diff rev {rev} for {scope_label}"
          f" ({up_n} upserts, {del_n} tombstones)"
        )
      else:
        core_n = len(snap.get("core") or [])
        self._log_detail = f"served state rev {rev} for {scope_label} ({core_n} rows)"
      self._send_json(200, snap)
      return

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
          self._log_detail = "since must be an integer"
          self._send_json(400, {"error": "since must be an integer"})
          return
      branch = params.get("branch", [""])[0].strip()
      repo = params.get("repo", [""])[0].strip()
      snap_mode = params.get("mode", ["full"])[0].strip().lower() or "full"
      snap = board_store.snapshot(since=since, branch=branch, repo=repo, mode=snap_mode)
      rev = snap.get("revision", 0)
      who = branch or "anonymous"
      repo_note = f" ({repo})" if repo else ""
      if snap.get("unchanged"):
        self._suppress_poll_log = bool(getattr(self.server, "quiet_polls", False))
        self._log_detail = f"unchanged at rev {rev} for {who}{repo_note}"
      elif snap.get("mode") == "diff":
        diff = snap.get("diff") or {}
        up_n = len(diff.get("upserts") or [])
        del_n = len(diff.get("tombstones") or [])
        self._log_detail = (
          f"served diff rev {rev} to {who}{repo_note}"
          f" ({up_n} upserts, {del_n} tombstones)"
        )
      else:
        board = snap.get("scoped_board") or snap.get("board") or {}
        sessions = len(board.get("sessions") or [])
        entries = len(board.get("entries") or [])
        wakes = len(board.get("wakes") or {})
        extra = f"{repo + ', ' if repo else ''}{sessions} sessions, {entries} entries, {wakes} wakes"
        self._log_detail = f"served rev {rev} to {who} ({extra})"
      self._send_json(200, {**snap, "egress_version": VERSION})
      return
    branch = params.get("branch", [""])[0].strip()
    name = params.get("name", [""])[0].strip()
    sha256 = params.get("sha256", [""])[0].strip().lower()
    try:
      if branch and name:
        found = board_store.get_file(branch, name)
      elif sha256:
        found = board_store.get_file_by_sha256(sha256)
      else:
        found = board_store.get_file(branch, name)
    except (ValueError, TypeError) as error:
      self._log_detail = str(error)
      self._send_json(400, {"error": str(error)})
      return
    if found is None:
      target_label = name or (sha256[:12] if sha256 else "file")
      owner_label = f" for {branch}" if branch else ""
      self._log_detail = f"{target_label} not found{owner_label}"
      self._send_json(404, {"error": "board file not found"})
      return
    file_name = found.get("name") or name or "file"
    owner_branch = found.get("branch") or branch or "board"
    size = found.get("size", 0)
    digest = str(found.get("sha256") or "")[:12]
    self._log_detail = (
      f"served {file_name} from {owner_branch} ({format_bytes(size)}, sha256 {digest})"
    )
    self._send_json(200, {"ok": True, **found, "file": found})

  def _board_post(self, route, params):
    if route == "/v1/state":
      state_store = self._check_state_master(params)
      if state_store is None:
        return
      payload = self._read_json_body()
      try:
        result = state_store.put_state(payload)
      except (ValueError, TypeError) as error:
        self._log_detail = str(error)
        self._send_json(400, {"error": str(error)})
        return
      scope = result.get("scope") or {}
      scope_label = (
        f"{scope.get('repo')}/{scope.get('branch')}"
        if scope.get("branch")
        else str(scope.get("repo") or payload.get("repo") or "state")
      )
      rev = result.get("revision", 0)
      if not result.get("ok") and result.get("need_full"):
        self._log_detail = f"stale state diff for {scope_label} at rev {rev}"
        self._send_json(409, result)
        return
      if result.get("unchanged"):
        self._suppress_poll_log = bool(getattr(self.server, "quiet_polls", False))
        self._log_detail = f"state unchanged for {scope_label} at rev {rev}"
      else:
        self._log_detail = f"saved state for {scope_label} -> rev {rev}"
      self._send_json(200, result)
      return

    board_store = self._check_board_master(params)
    if board_store is None:
      return
    payload = self._read_json_body()
    if route == "/v1/board/files":
      branch = str(payload.get("branch") or "").strip()
      try:
        info = board_store.put_file(branch, payload.get("file"))
      except (ValueError, TypeError) as error:
        self._log_detail = str(error)
        self._send_json(400, {"error": str(error)})
        return
      file_name = info.get("name") or "file"
      size = info.get("size", 0)
      digest = str(info.get("sha256") or "")[:12]
      rev = board_store.snapshot().get("revision", 0)
      self._log_detail = f"staged {file_name} for {branch} ({format_bytes(size)}, sha256 {digest}, rev {rev})"
      self._send_json(200, {"ok": True, "file": info})
      return
    mode = str(payload.get("action") or payload.get("type") or "sync").strip().lower()
    branch = str(payload.get("branch") or "").strip()
    repo = str(payload.get("repo") or "").strip()
    reply_mode = str(payload.get("reply_mode") or "full").strip().lower() or "full"
    reply_since = None
    if payload.get("reply_since") is not None:
      try:
        reply_since = int(payload["reply_since"])
      except (ValueError, TypeError):
        self._log_detail = "reply_since must be an integer"
        self._send_json(400, {"error": "reply_since must be an integer"})
        return
    if mode in ("sync", "merge") and (
      isinstance(payload.get("board"), dict)
      or isinstance(payload.get("board_diff"), dict)
    ):
      passive = bool(payload.get("passive"))
      client_rev = payload.get("client_rev")
      if client_rev is not None:
        try:
          client_rev = int(client_rev)
        except (ValueError, TypeError):
          self._log_detail = "client_rev must be an integer"
          self._send_json(400, {"error": "client_rev must be an integer"})
          return
      before_rev = board_store.snapshot().get("revision", 0)
      try:
        result = board_store.sync(
          payload.get("board"),
          branch=branch,
          repo=repo,
          passive=passive,
          board_diff=payload.get("board_diff"),
          client_rev=client_rev,
          reply_since=reply_since,
          reply_mode=reply_mode,
        )
      except (ValueError, TypeError) as error:
        self._log_detail = str(error)
        self._send_json(400, {"error": str(error)})
        return
      if not result.get("ok") and result.get("need_full"):
        who = branch or "anonymous"
        self._log_detail = (
          f"stale board diff from {who} at rev {result.get('revision', before_rev)}"
        )
        self._send_json(409, {**result, "egress_version": VERSION})
        return
      after_rev = result.get("revision", before_rev)
      who = branch or "anonymous"
      repo_note = f" ({repo})" if repo else ""
      if passive and after_rev == before_rev:
        self._suppress_poll_log = bool(getattr(self.server, "quiet_polls", False))
        self._log_detail = (
          f"passive sync from {who}{repo_note} unchanged at rev {after_rev}"
        )
      elif result.get("mode") == "diff":
        diff = result.get("diff") or {}
        up_n = len(diff.get("upserts") or [])
        del_n = len(diff.get("tombstones") or [])
        self._log_detail = (
          f"synced {who}{repo_note} -> rev {after_rev}"
          f" ({up_n} upserts, {del_n} tombstones)"
        )
      else:
        board = result.get("board") or {}
        sessions = len(board.get("sessions") or [])
        entries = len(board.get("entries") or [])
        wakes = len(board.get("wakes") or {})
        extra = f"{repo + ', ' if repo else ''}{sessions} sessions, {entries} entries, {wakes} wakes"
        self._log_detail = f"synced {who} -> rev {after_rev} ({extra})"
      self._send_json(200, {**result, "egress_version": VERSION})
      return
    action_body = (
      payload.get("board_action")
      if mode in ("apply", "action") and isinstance(payload.get("board_action"), dict)
      else payload
    )
    act_name = (
      str(action_body.get("action") or action_body.get("type") or "action")
      .strip()
      .lower()
    )
    actor = str(action_body.get("branch") or branch or "caller").strip()
    target = str(action_body.get("target") or action_body.get("to") or "").strip()
    result = board_store.apply(
      action_body,
      branch=branch,
      repo=repo,
      reply_since=reply_since,
      reply_mode=reply_mode,
    )
    if result.get("ok"):
      rev = result.get("revision", 0)
      target_note = f" targeting {target}" if target else ""
      repo_note = f" ({repo})" if repo else ""
      self._log_detail = f"{act_name} by {actor}{target_note}{repo_note} -> rev {rev}"
      self._send_json(200, {**result, "egress_version": VERSION})
    else:
      reason = result.get("error") or "rejected"
      self._log_detail = f"{act_name} by {actor} rejected ({reason})"
      self._send_json(400, {**result, "egress_version": VERSION})

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
    route = urllib.parse.urlsplit(self.path).path.rstrip("/") or "/"
    caller = self._caller()
    if route == "/v1/health" and caller in LOOPBACK_CALLERS:
      return
    if getattr(self.server, "quiet_polls", False) and getattr(
      self, "_suppress_poll_log", False
    ):
      return
    status_code = code.value if hasattr(code, "value") else code
    detail = getattr(self, "_log_detail", "")
    self._emit_log(log_line(self.command, self.path, status_code, caller, detail))

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
  """Wire the store, SQLite WAL board/state stores, and HTTP server."""
  store = Store(options.state_dir)
  sqlite_engine = ProxySqliteEngine(options.state_dir)
  board_store = BoardStore(
    os.path.join(options.state_dir, "board"),
    engine=sqlite_engine,
  )
  state_store = StateStore(sqlite_engine)
  return ExtensionServer(
    (options.host, options.port),
    agent_key=options.key,
    master_key=options.master,
    token=options.token,
    api=options.api,
    store=store,
    fetch_cap=options.fetch_cap,
    stage_cap=options.stage_cap,
    board_store=board_store,
    state_store=state_store,
    sqlite_engine=sqlite_engine,
    quiet_polls=getattr(options, "quiet_polls", False),
    log_sink=getattr(options, "log_sink", None),
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
  parser.add_argument(
    "--quiet-polls",
    action="store_true",
    default=_truthy_env(os.environ.get("ARENA_PROXY_QUIET_POLLS", "")),
    help="suppress unchanged /v1/board poll log lines",
  )
  options = parser.parse_args(argv)
  options.token = os.environ.get("ARENA_PROXY_GITHUB_TOKEN") or os.environ.get(
    "GITHUB_TOKEN", ""
  )
  options.master = os.environ.get("ARENA_PROXY_MASTER_KEY", "")
  options.api = os.environ.get("ARENA_PROXY_GITHUB_API", github_api.GITHUB_API)
  options.state_dir = os.environ.get("ARENA_PROXY_STATE_DIR", "arena-proxy-state")
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
  for line in startup_lines(options.key, options.token, options.quiet_polls):
    print(line, flush=True)
  try:
    server.serve_forever()
  except KeyboardInterrupt:
    print("stopped", flush=True)
  return 0
