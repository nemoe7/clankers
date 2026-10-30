"""HTTP router and local steering server for Arena Steering."""

from __future__ import annotations

import base64
import binascii
import hashlib
import html
import importlib
import importlib.util
import json
import mimetypes
import os
import re
import secrets
import sqlite3
import sys
import tempfile
import threading
import time
from collections.abc import Callable, Iterable
from contextlib import closing
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse, urlsplit

from . import __version__
from .gates import FileGateStatus
from .markdown import render_markdown
from .markdown_fields import parse_report_markdown
from .models import Attachment
from .services import MessageService, ReportService, TaskService
from .store import SqliteStore

RouteHandler = Callable[[dict[str, str], dict[str, list[str]], Any], tuple[int, Any]]

WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
WS_TICK_SECONDS = 0.25
WS_HEARTBEAT_SECONDS = 10.0
WS_IDLE_SECONDS = 35.0
WS_MAX_MESSAGE = 16 * 1024 * 1024

MIME_OVERRIDES = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "application/javascript; charset=utf-8",
  ".mjs": "application/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
  ".gif": "image/gif",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".webp": "image/webp",
  ".woff2": "font/woff2",
  ".md": "text/markdown; charset=utf-8",
  ".txt": "text/plain; charset=utf-8",
}

REPORT_IMAGE_EXTS = frozenset({".gif", ".png", ".jpg", ".jpeg", ".webp", ".svg"})
REPORT_STATIC_EXTS = REPORT_IMAGE_EXTS | frozenset({".md", ".txt"})
STATIC_ASSETS_PREFIX = "static/assets/"
STATIC_REPORTS_PREFIX = "static/reports/"
STATIC_UPLOADS_PREFIX = "static/uploads/"
PASTE_ATTACHMENT_CHAR_THRESHOLD = 1500
PASTE_ATTACHMENT_LINE_THRESHOLD = 15
PASTE_ATTACHMENT_NAME = "pasted-text.txt"
PASTE_ATTACHMENT_BODY = "Pasted text attached."


def _body_bool(value: Any, default: bool) -> bool:
  if isinstance(value, bool):
    return value
  if isinstance(value, str):
    lowered = value.strip().lower()
    if lowered in {"true", "1", "yes", "on"}:
      return True
    if lowered in {"false", "0", "no", "off", ""}:
      return False
  if value is None:
    return default
  return bool(value)


class Router:
  """Small regex-based HTTP route dispatcher."""

  def __init__(self) -> None:
    self._routes: list[tuple[str, re.Pattern[str], RouteHandler]] = []

  def add(self, method: str, template: str, handler: RouteHandler) -> None:
    pattern_text = re.sub(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}", r"(?P<\1>[^/]+)", template)
    compiled = re.compile(f"^{pattern_text}$")
    self._routes.append((method.upper(), compiled, handler))

  def match(
    self, method: str, path: str
  ) -> tuple[RouteHandler | None, dict[str, str], list[str]]:
    verb = method.upper()
    allowed: list[str] = []
    for route_method, pattern, handler in self._routes:
      found = pattern.match(path)
      if found is not None:
        if route_method == verb:
          return handler, found.groupdict(), []
        allowed.append(route_method)
    return None, {}, allowed


def _detect_repo_name(store: SqliteStore) -> str:
  """Resolve repository directory name from store path or current working directory."""
  candidates: list[Path] = []
  db_path = getattr(store, "db_path", "")
  if db_path and db_path != ":memory:":
    candidates.append(Path(db_path).resolve())
  candidates.append(Path.cwd().resolve())
  for start in candidates:
    cur = start if start.is_dir() else start.parent
    for parent in (cur, *cur.parents):
      if (parent / ".git").exists():
        return parent.name
  return Path.cwd().resolve().name or "Workspace"


class SteeringApp:
  """Application facade wiring services and REST endpoints."""

  def __init__(
    self,
    store: SqliteStore,
    assets_dir: str | Path | None = None,
    repo_name: str | None = None,
  ) -> None:
    self.store = store
    self._browser_write = threading.local()
    self._clean_uncommitted_uploads()
    default_assets = Path(__file__).resolve().parents[2] / "assets"
    self.assets_dir = Path(assets_dir) if assets_dir is not None else default_assets
    self.repo_name = repo_name or _detect_repo_name(store)
    self.messages = MessageService(store, store, store)
    self.tasks = TaskService(
      store,
      store,
      gates=FileGateStatus(Path(store.db_path).parent)
      if store.db_path != ":memory:"
      else None,
    )
    self.reports = ReportService(
      store,
      store,
      on_answer_callback=self.messages.notify_new_work,
    )
    self.router = Router()
    self._register_routes()
    self._maybe_reseed_demo(store)

  @staticmethod
  def _maybe_reseed_demo(store: SqliteStore) -> None:
    """Re-seed the live demo SQLite store when demo.py changes on disk."""
    db_path_str = str(getattr(store, "db_path", ""))
    demo_script = Path(__file__).resolve().parents[1] / "demo.py"
    if (
      "arena-steering-demo-" not in db_path_str
      or not demo_script.is_file()
      or getattr(store, "_seeding_demo", False)
    ):
      return
    try:
      mtime = demo_script.stat().st_mtime_ns
    except OSError:
      return
    if getattr(store, "_demo_mtime_ns", None) == mtime:
      return
    store._seeding_demo = True  # type: ignore[attr-defined]
    store._demo_mtime_ns = mtime  # type: ignore[attr-defined]
    try:
      spec = importlib.util.spec_from_file_location("_arena_steering_demo", demo_script)
      if spec and spec.loader:
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        if hasattr(mod, "reseed_demo_store"):
          mod.reseed_demo_store(store)
    finally:
      store._seeding_demo = False  # type: ignore[attr-defined]

  def _register_routes(self) -> None:
    self.router.add("GET", "/health", self._handle_health)
    self.router.add("GET", "/messages", self._handle_list_messages)
    self.router.add("POST", "/messages", self._handle_create_message)
    self.router.add(
      "POST", "/messages/with-file", self._handle_create_message_with_file
    )
    self.router.add("POST", "/uploads", self._handle_upload_file)
    self.router.add("GET", "/messages/{id}", self._handle_get_message)
    self.router.add("POST", "/messages/{id}/ack", self._handle_ack_message)
    self.router.add("POST", "/messages/{id}/replies-seen", self._handle_replies_seen)
    self.router.add("GET", "/poll", self._handle_poll)
    self.router.add("POST", "/poll/skip", self._handle_skip_poll)

    self.router.add("GET", "/tasks", self._handle_list_tasks)
    self.router.add("POST", "/tasks", self._handle_create_task)
    self.router.add("GET", "/tasks/{id}", self._handle_get_task)
    self.router.add("PATCH", "/tasks/{id}", self._handle_patch_task)
    self.router.add("DELETE", "/tasks/{id}", self._handle_delete_task)

    self.router.add("GET", "/reports", self._handle_list_reports)
    self.router.add("POST", "/reports", self._handle_publish_report)
    self.router.add("GET", "/reports/{id}", self._handle_get_report)
    self.router.add("PATCH", "/reports/{id}", self._handle_patch_report)
    self.router.add("DELETE", "/reports/{id}", self._handle_delete_report)
    self.router.add("POST", "/reports/{id}/seen", self._handle_mark_report_seen)
    self.router.add("POST", "/reports/{id}/ack-seen", self._handle_mark_ack_seen)
    self.router.add("POST", "/reports/{id}/answers", self._handle_submit_answer)
    self.router.add(
      "POST",
      "/reports/{id}/answers/{answer_id}/ack",
      self._handle_ack_report_answer,
    )
    self.router.add("GET", "/survey", self._handle_get_survey)
    self.router.add("POST", "/survey", self._handle_submit_survey)
    self.router.add("POST", "/survey/interrupt", self._handle_survey_interrupt)
    self.router.add("POST", "/timezone", self._handle_set_timezone)
    self.router.add("POST", "/markdown", self._handle_render_markdown)

  def dispatch(
    self, method: str, raw_url: str, body: dict[str, Any] | None = None
  ) -> tuple[int, dict[str, Any]]:
    """Dispatch a request and return (status_code, json_payload)."""
    parsed = urlparse(raw_url)
    path = parsed.path.rstrip("/") or "/"
    if path.startswith("/api/") and path != "/api":
      path = path[len("/api") :] or "/"
    query = parse_qs(parsed.query)
    handler, params, allowed = self.router.match(method, path)
    if handler is None:
      if allowed:
        return (
          int(HTTPStatus.METHOD_NOT_ALLOWED),
          {"error": f"Method {method} not allowed; expected {allowed}"},
        )
      return (int(HTTPStatus.NOT_FOUND), {"error": f"Unknown route: {path}"})
    try:
      request_body = dict(body or {})
      request_id = request_body.pop("_request_id", None)
      if request_id is not None:
        if method.upper() not in {"POST", "PATCH", "DELETE"}:
          raise ValueError("Request ID requires a write action")
        if not isinstance(request_id, str) or not re.fullmatch(
          r"[a-zA-Z0-9_-]{1,128}", request_id
        ):
          raise ValueError("Invalid request ID")
        canonical = json.dumps(
          [method.upper(), path, parsed.query, request_body],
          sort_keys=True,
          separators=(",", ":"),
        )
        fingerprint = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

        def perform() -> tuple[int, dict[str, Any]]:
          self._browser_write.request_id = request_id
          self._browser_write.files = []
          try:
            status, payload = handler(params, query, request_body)
            if not 200 <= status < 300:
              for file_path in self._browser_write.files:
                file_path.unlink(missing_ok=True)
            return status, payload
          except BaseException:
            for file_path in self._browser_write.files:
              file_path.unlink(missing_ok=True)
            raise
          finally:
            del self._browser_write.request_id
            del self._browser_write.files

        status, payload = self.store.execute_browser_write_once(
          request_id, fingerprint, perform
        )
      else:
        status, payload = handler(params, query, request_body)
      if method.upper() in {"POST", "PATCH", "DELETE"} and 200 <= status < 300:
        self._state_version = getattr(self, "_state_version", 0) + 1
      return (status, payload)
    except KeyError as exc:
      return (
        int(HTTPStatus.NOT_FOUND),
        {"error": str(exc.args[0] if exc.args else exc)},
      )
    except ValueError as exc:
      return (int(HTTPStatus.BAD_REQUEST), {"error": str(exc)})

  def data_version(self) -> tuple[int, int]:
    """Return a version tuple reflecting SQLite PRAGMA data_version and in-process mutations."""
    in_proc = int(getattr(self, "_state_version", 0))
    db_path = str(getattr(self.store, "db_path", ""))
    if not db_path or db_path == ":memory:":
      return (0, in_proc)
    try:
      with closing(sqlite3.connect(db_path, timeout=2.0)) as conn:
        row = conn.execute("PRAGMA data_version").fetchone()
        pragma_ver = int(row[0]) if row else 0
        return (pragma_ver, in_proc)
    except sqlite3.Error:
      return (0, in_proc)

  def report_ack_snapshot(self) -> dict[str, tuple[str, str, int]]:
    """Return the latest answer ID, status, and ack count for each live report."""
    snapshot: dict[str, tuple[str, str, int]] = {}
    for report in self.reports.list_reports():
      if not report.answers:
        continue
      latest = report.answers[-1]
      snapshot[report.id] = (latest.id, latest.status, len(latest.acks))
    return snapshot

  def report_acked_events(
    self, previous: dict[str, tuple[str, str, int]]
  ) -> tuple[list[dict[str, Any]], dict[str, tuple[str, str, int]]]:
    """Return one `report.acked` event per report whose latest ack changed."""
    current_reports = {report.id: report for report in self.reports.list_reports()}
    current: dict[str, tuple[str, str, int]] = {}
    for report in current_reports.values():
      if not report.answers:
        continue
      latest = report.answers[-1]
      current[report.id] = (latest.id, latest.status, len(latest.acks))
    events: list[dict[str, Any]] = []
    for report_id, snap in current.items():
      if snap[1] != "acked":
        continue
      prev = previous.get(report_id)
      if (
        prev is not None
        and prev[0] == snap[0]
        and prev[1] == "acked"
        and prev[2] >= snap[2]
      ):
        continue
      events.append(
        {
          "type": "report.acked",
          "report": self._serialize_report(current_reports[report_id]),
        }
      )
    return (events, current)

  def resolve_asset(self, request_path: str) -> tuple[bytes, str] | None:
    """Resolve a static file inside assets_dir or state files without path traversal."""
    clean = request_path.split("?", 1)[0].lstrip("/")
    clean = clean.removeprefix("api/")
    if clean.startswith(STATIC_ASSETS_PREFIX):
      rel = clean[len(STATIC_ASSETS_PREFIX) :] or "index.html"
      candidate = self._resolve_under(self.assets_dir, rel)
      return self._file_response(candidate) if candidate is not None else None
    if clean.startswith(STATIC_REPORTS_PREFIX):
      rel = clean[len(STATIC_REPORTS_PREFIX) :]
      if Path(rel).suffix.lower() not in REPORT_STATIC_EXTS:
        return None
      candidate = self._resolve_state_file("reports", rel)
      if candidate is not None:
        return self._file_response(candidate)
      markdown = self._report_markdown_bytes(rel)
      return (markdown, MIME_OVERRIDES[".md"]) if markdown is not None else None
    if clean.startswith(STATIC_UPLOADS_PREFIX):
      rel = clean[len(STATIC_UPLOADS_PREFIX) :]
      candidate = self._resolve_state_file("uploads", rel)
      return self._file_response(candidate) if candidate is not None else None

    if not clean or clean in {"index.html", "messages", "tasks", "reports"}:
      clean = "index.html"
    elif clean.startswith("assets/"):
      clean = clean[len("assets/") :]
    candidate = self._resolve_under(self.assets_dir, clean)
    if candidate is None:
      candidate = self._resolve_report_asset(clean)
      if candidate is None:
        return None
    return self._file_response(candidate)

  @staticmethod
  def is_static_request(request_path: str) -> bool:
    """Return True for file paths that must not be routed as JSON resources."""
    clean = request_path.split("?", 1)[0].lstrip("/")
    clean = clean.removeprefix("api/")
    if clean.startswith("static/"):
      return True
    if clean.startswith("uploads/"):
      return True
    if clean.startswith("reports/"):
      return Path(clean).suffix.lower() in REPORT_STATIC_EXTS
    return False

  def _file_response(self, candidate: Path) -> tuple[bytes, str]:
    suffix = candidate.suffix.lower()
    content_type = (
      MIME_OVERRIDES.get(suffix)
      or mimetypes.guess_type(candidate.name)[0]
      or "application/octet-stream"
    )
    if candidate.name == "index.html":
      page = candidate.read_text(encoding="utf-8").replace(
        "<title>Arena Steering</title>",
        f"<title>{html.escape(self.repo_name)} - Steering</title>",
      )
      return page.encode("utf-8"), content_type
    return candidate.read_bytes(), content_type

  @staticmethod
  def _resolve_under(root: Path, rel_path: str) -> Path | None:
    if not rel_path:
      return None
    root_resolved = root.resolve()
    candidate = (root_resolved / rel_path).resolve()
    if candidate.is_relative_to(root_resolved) and candidate.is_file():
      return candidate
    return None

  def _resolve_state_file(self, directory_name: str, rel_path: str) -> Path | None:
    db_path = getattr(self.store, "db_path", "")
    if not db_path or db_path == ":memory:":
      return None
    state_dir = Path(db_path).resolve().parent
    return self._resolve_under(state_dir / directory_name, rel_path)

  def _uploads_dir(self) -> Path:
    db_path = getattr(self.store, "db_path", "")
    if db_path and db_path != ":memory:":
      uploads_dir = Path(db_path).resolve().parent / "uploads"
    else:
      cached = getattr(self, "_memory_uploads_dir", None)
      if cached is None:
        cached = Path(tempfile.mkdtemp(prefix="arena-steering-uploads-"))
        self._memory_uploads_dir = cached  # type: ignore[attr-defined]
      uploads_dir = cached
    uploads_dir.mkdir(parents=True, exist_ok=True)
    return uploads_dir

  def _clean_uncommitted_uploads(self) -> None:
    """Remove staged request files left by a crash before database commit."""
    with self.store.transaction():
      committed = {
        hashlib.sha256(request_id.encode("utf-8")).hexdigest()
        for request_id in self.store.browser_write_ids()
      }
      for file_path in self._uploads_dir().glob("request-*"):
        match = re.fullmatch(r"request-([0-9a-f]{64})-[0-9]+-.*", file_path.name)
        if match and match.group(1) not in committed:
          file_path.unlink(missing_ok=True)

  @staticmethod
  def _safe_upload_name(name: Any) -> str:
    raw_name = Path(str(name or "")).name.strip()
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "-", raw_name).strip(".-")
    return safe_name or "upload.bin"

  @staticmethod
  def _upload_bytes(file_body: dict[str, Any]) -> bytes:
    for field_name in ("content_base64", "base64", "data_base64"):
      encoded = file_body.get(field_name)
      if isinstance(encoded, str) and encoded:
        try:
          return base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError) as exc:
          raise ValueError("Upload content_base64 is invalid") from exc
    for field_name in ("text", "content"):
      text = file_body.get(field_name)
      if isinstance(text, str):
        return text.encode("utf-8")
    raise ValueError("Upload file content is required")

  def _store_upload(self, file_body: dict[str, Any]) -> Attachment:
    if not isinstance(file_body, dict):
      raise TypeError("Upload file must be an object")
    safe_name = self._safe_upload_name(
      file_body.get("name") or file_body.get("filename") or "upload.bin"
    )
    data = self._upload_bytes(file_body)
    request_id = getattr(self._browser_write, "request_id", None)
    if request_id is not None:
      digest = hashlib.sha256(request_id.encode("utf-8")).hexdigest()
      prefix = f"request-{digest}-{len(self._browser_write.files)}-"
      suffix = Path(safe_name).suffix[:20]
      stem = safe_name[: -len(suffix)] if suffix else safe_name
      stored_name = prefix + stem[: 255 - len(prefix) - len(suffix)] + suffix
    else:
      stored_name = f"{secrets.token_hex(3)}-{int(time.time())}-{safe_name}"
    stored_path = self._uploads_dir() / stored_name
    if request_id is not None:
      self._browser_write.files.append(stored_path)
    stored_path.write_bytes(data)
    return Attachment(
      name=safe_name,
      path=str(stored_path),
      size_bytes=len(data),
      present=True,
    )

  def _serialize_attachment(self, attachment: Attachment) -> dict[str, Any]:
    data = attachment.to_dict()
    stored_path = Path(attachment.path)
    try:
      relative = stored_path.resolve().relative_to(self._uploads_dir().resolve())
    except ValueError:
      return data
    data["url"] = f"/static/uploads/{relative.as_posix()}"
    return data

  @staticmethod
  def _paste_needs_attachment(text: str) -> bool:
    return (
      len(text) > PASTE_ATTACHMENT_CHAR_THRESHOLD
      or len(text.split("\n")) >= PASTE_ATTACHMENT_LINE_THRESHOLD
    )

  def _message_attachments_from_body(
    self, body: dict[str, Any]
  ) -> tuple[str, list[Attachment]]:
    attachments = [Attachment.from_dict(raw) for raw in body.get("attachments", [])]
    message_body = str(body.get("body", ""))
    file_body = body.get("file") or body.get("upload")
    if file_body is not None:
      attachments.append(self._store_upload(file_body))
    pasted_text = body.get("pasted_text", body.get("paste_text"))
    if isinstance(pasted_text, str) and pasted_text:
      if self._paste_needs_attachment(pasted_text):
        attachments.append(
          self._store_upload({"name": PASTE_ATTACHMENT_NAME, "text": pasted_text})
        )
        if not message_body.strip():
          message_body = PASTE_ATTACHMENT_BODY
      elif not message_body.strip():
        message_body = pasted_text
    return message_body, attachments

  def _report_markdown_bytes(self, rel_path: str) -> bytes | None:
    rel = Path(rel_path)
    if rel.suffix.lower() != ".md" or rel.parent != Path("."):
      return None
    try:
      report = self.reports.get_report(rel.stem)
    except (KeyError, ValueError):
      return None
    return report.body.encode("utf-8")

  def _resolve_report_asset(self, clean_path: str) -> Path | None:
    if clean_path.startswith("uploads/"):
      return self._resolve_state_file("uploads", clean_path[len("uploads/") :])
    return self._resolve_report_image(clean_path)

  def _resolve_report_image(self, clean_path: str) -> Path | None:
    """Resolve an image or GIF inside <state_dir>/reports/ without path traversal."""
    rel = clean_path.removeprefix("reports/")
    suffix = Path(rel).suffix.lower()
    if suffix not in REPORT_IMAGE_EXTS:
      return None
    candidate = self._resolve_state_file("reports", rel)
    if candidate is not None:
      return candidate
    db_path = getattr(self.store, "db_path", "")
    if not db_path or db_path == ":memory:":
      return None
    return self._resolve_under(Path(db_path).resolve().parent, rel)

  def asset_signature_hash(self) -> str:
    """Return a short hash of current asset file mtimes and sizes."""
    sig = assets_signature(self.assets_dir)
    digest = hashlib.sha256(repr(sig).encode("utf-8")).hexdigest()
    return digest[:12]

  def _handle_health(
    self, _params: dict[str, str], _query: dict[str, list[str]], _body: Any
  ) -> tuple[int, Any]:
    survey = self.messages.get_survey()
    return (
      int(HTTPStatus.OK),
      {
        "ok": True,
        "version": __version__,
        "repo": self.repo_name,
        "asset_version": self.asset_signature_hash(),
        "timezone": self.store.get_meta("timezone", "") or "",
        "survey": survey,
      },
    )

  def _handle_set_timezone(
    self, _params: dict[str, str], _query: dict[str, list[str]], body: dict[str, Any]
  ) -> tuple[int, Any]:
    timezone_name = str(body.get("timezone", "")).strip()
    if not timezone_name:
      raise ValueError("timezone is required")
    try:
      from zoneinfo import ZoneInfo

      ZoneInfo(timezone_name)
    except Exception as exc:
      raise ValueError(f"Unknown timezone: {timezone_name}") from exc
    self.store.set_meta("timezone", timezone_name)
    return (int(HTTPStatus.OK), {"timezone": timezone_name})

  def _handle_get_survey(
    self, _params: dict[str, str], _query: dict[str, list[str]], _body: Any
  ) -> tuple[int, Any]:
    return (int(HTTPStatus.OK), {"survey": self.messages.get_survey()})

  def _handle_submit_survey(
    self, _params: dict[str, str], _query: dict[str, list[str]], body: Any
  ) -> tuple[int, Any]:
    values = body.get("answers", body) if isinstance(body, dict) else body
    survey = self.messages.submit_survey(values)
    return (int(HTTPStatus.OK), {"survey": survey})

  def _handle_survey_interrupt(
    self, _params: dict[str, str], _query: dict[str, list[str]], body: dict[str, Any]
  ) -> tuple[int, Any]:
    active = body.get("active") if isinstance(body, dict) and "active" in body else None
    survey = self.messages.trigger_bible_check(active=active)
    return (int(HTTPStatus.OK), {"survey": survey})

  def _handle_render_markdown(
    self, _params: dict[str, str], _query: dict[str, list[str]], body: dict[str, Any]
  ) -> tuple[int, Any]:
    markdown = str(body.get("markdown", ""))
    breaks = bool(body.get("breaks", True))
    headings: list[dict[str, Any]] = []
    rendered = render_markdown(markdown, breaks=breaks, headings=headings)
    return (int(HTTPStatus.OK), {"html": rendered, "headings": headings})

  def _handle_list_messages(
    self, _params: dict[str, str], query: dict[str, list[str]], _body: Any
  ) -> tuple[int, Any]:
    include_all = query.get("all", ["0"])[0] in {"1", "true"}
    include_hidden = query.get("hidden", ["0"])[0] in {"1", "true"}
    items, total, has_more = self.messages.list_message_page(
      unread_only=not include_all,
      include_hidden=include_hidden,
      query=(query.get("q", [""])[0] or "").strip(),
      before=(query.get("before", [""])[0] or "").strip(),
      limit=20,
    )
    return (
      int(HTTPStatus.OK),
      {
        "messages": [self._serialize_message(item) for item in items],
        "total": total,
        "has_more": has_more,
      },
    )

  @staticmethod
  def _message_request_identity(
    body: dict[str, Any], route: str
  ) -> tuple[str | None, str]:
    request_id = body.get("request_id")
    if request_id is None:
      return None, ""
    if not isinstance(request_id, str) or not re.fullmatch(
      r"[a-zA-Z0-9_-]{1,128}", request_id
    ):
      raise ValueError("Invalid request ID")
    content = {key: value for key, value in body.items() if key != "request_id"}
    canonical = json.dumps([route, content], sort_keys=True, separators=(",", ":"))
    return request_id, hashlib.sha256(canonical.encode("utf-8")).hexdigest()

  def _handle_create_message(
    self, _params: dict[str, str], _query: dict[str, list[str]], body: dict[str, Any]
  ) -> tuple[int, Any]:
    request_id, fingerprint = self._message_request_identity(body, "/messages")
    attachments = [Attachment.from_dict(raw) for raw in body.get("attachments", [])]
    msg = self.messages.send_message(
      str(body.get("body", "")),
      hidden=bool(body.get("hidden", False)),
      blocking=bool(body.get("blocking", True)),
      attachments=attachments,
      parent_ids=[str(item) for item in (body.get("parent_ids") or [])],
      msg_id=body.get("id"),
      request_id=request_id,
      fingerprint=fingerprint,
    )
    return (int(HTTPStatus.CREATED), {"message": self._serialize_message(msg)})

  def _handle_upload_file(
    self, _params: dict[str, str], _query: dict[str, list[str]], body: dict[str, Any]
  ) -> tuple[int, Any]:
    file_body = body.get("file") or body.get("upload") or body
    attachment = self._store_upload(file_body)
    return (
      int(HTTPStatus.CREATED),
      {"attachment": self._serialize_attachment(attachment)},
    )

  def _handle_create_message_with_file(
    self, _params: dict[str, str], _query: dict[str, list[str]], body: dict[str, Any]
  ) -> tuple[int, Any]:
    request_id, fingerprint = self._message_request_identity(
      body, "/messages/with-file"
    )
    message_body, attachments = self._message_attachments_from_body(body)
    msg = self.messages.send_message(
      message_body,
      hidden=_body_bool(body.get("hidden", False), False),
      blocking=_body_bool(body.get("blocking", True), True),
      attachments=attachments,
      parent_ids=[str(item) for item in (body.get("parent_ids") or [])],
      msg_id=body.get("id"),
      request_id=request_id,
      fingerprint=fingerprint,
    )
    return (int(HTTPStatus.CREATED), {"message": self._serialize_message(msg)})

  def _handle_get_message(
    self, params: dict[str, str], _query: dict[str, list[str]], _body: Any
  ) -> tuple[int, Any]:
    msg = self.messages.get_message(params["id"])
    return (int(HTTPStatus.OK), {"message": self._serialize_message(msg)})

  def _handle_ack_message(
    self, params: dict[str, str], _query: dict[str, list[str]], body: dict[str, Any]
  ) -> tuple[int, Any]:
    markdown = str(body.get("markdown", body.get("ack", "")))
    target_type, acked = self.messages.ack(params["id"], markdown)
    if target_type == "report_answer":
      return (int(HTTPStatus.OK), {"answer": acked.to_dict()})
    return (int(HTTPStatus.OK), {"message": self._serialize_message(acked)})

  def _handle_replies_seen(
    self, params: dict[str, str], _query: dict[str, list[str]], body: dict[str, Any]
  ) -> tuple[int, Any]:
    revision = body.get("revision")
    matched = self.messages.mark_replies_seen(params["id"], revision)
    msg = self.messages.get_message(params["id"])
    return (
      int(HTTPStatus.OK if matched else HTTPStatus.CONFLICT),
      {"message": self._serialize_message(msg), "matched": matched},
    )

  def _handle_poll(
    self, _params: dict[str, str], query: dict[str, list[str]], _body: Any
  ) -> tuple[int, Any]:
    timeout_raw = query.get("timeout", ["0"])[0]
    timeout_sec = float(timeout_raw) if timeout_raw else 0.0
    delivered = self.messages.poll(timeout_seconds=timeout_sec)
    return (
      int(HTTPStatus.OK),
      {
        "messages": [item.to_dict() for item in delivered["messages"]],
        "report_answers": [
          {"report_id": rep.id, "title": rep.title, "answer": ans.to_dict()}
          for rep, ans in delivered["report_answers"]
        ],
      },
    )

  def _handle_skip_poll(
    self, _params: dict[str, str], _query: dict[str, list[str]], _body: Any
  ) -> tuple[int, Any]:
    self.messages.trigger_skip_poll()
    return (int(HTTPStatus.OK), {"skip_poll": True})

  def _handle_list_tasks(
    self, _params: dict[str, str], query: dict[str, list[str]], _body: Any
  ) -> tuple[int, Any]:
    include_finished = query.get("full", ["1"])[0] not in {"0", "false"}
    items = self.tasks.list_tasks(include_finished=include_finished)
    return (
      int(HTTPStatus.OK),
      {"tasks": [task.to_dict(blocked=blocked) for task, blocked in items]},
    )

  def _handle_create_task(
    self, _params: dict[str, str], _query: dict[str, list[str]], body: dict[str, Any]
  ) -> tuple[int, Any]:
    raw_links = body.get("links")
    task = self.tasks.create_task(
      str(body.get("id", "")),
      str(body.get("title", "")),
      type=str(body.get("type", "code")),
      status=str(body.get("status", "upcoming")),
      scope=str(body.get("scope", "")),
      details=[str(x) for x in body.get("details", [])],
      links=raw_links if isinstance(raw_links, dict) else None,
      msg_ids=[str(x) for x in body["msg_ids"]] if "msg_ids" in body else None,
      report_ids=[str(x) for x in body["report_ids"]] if "report_ids" in body else None,
      task_ids=[str(x) for x in body["task_ids"]] if "task_ids" in body else None,
      deps=[str(x) for x in body["deps"]] if "deps" in body else None,
      gate_names=[str(x) for x in body["gate_names"]] if "gate_names" in body else None,
    )
    _, blocked = self.tasks.get_task(task.id)
    return (int(HTTPStatus.CREATED), {"task": task.to_dict(blocked=blocked)})

  def _handle_get_task(
    self, params: dict[str, str], _query: dict[str, list[str]], _body: Any
  ) -> tuple[int, Any]:
    task, blocked = self.tasks.get_task(params["id"])
    return (int(HTTPStatus.OK), {"task": task.to_dict(blocked=blocked)})

  def _handle_patch_task(
    self, params: dict[str, str], _query: dict[str, list[str]], body: dict[str, Any]
  ) -> tuple[int, Any]:
    pos = body.get("position")
    task = self.tasks.patch_task(
      params["id"],
      body,
      position=int(pos) if pos is not None else None,
    )
    _, blocked = self.tasks.get_task(task.id)
    return (int(HTTPStatus.OK), {"task": task.to_dict(blocked=blocked)})

  def _handle_delete_task(
    self, params: dict[str, str], _query: dict[str, list[str]], _body: Any
  ) -> tuple[int, Any]:
    removed = self.tasks.remove_task(params["id"])
    if not removed:
      raise KeyError(f"Unknown task ID: {params['id']}")
    return (int(HTTPStatus.OK), {"deleted": params["id"]})

  def _handle_list_reports(
    self, _params: dict[str, str], query: dict[str, list[str]], _body: Any
  ) -> tuple[int, Any]:
    stale_only = query.get("stale", ["0"])[0] in {"1", "true"}
    summary_only = query.get("summary", ["0"])[0] in {"1", "true"}
    items = self.reports.list_reports(stale_only=stale_only)
    return (
      int(HTTPStatus.OK),
      {
        "reports": [
          self._serialize_report(item, include_body=not summary_only) for item in items
        ]
      },
    )

  def _handle_publish_report(
    self, _params: dict[str, str], _query: dict[str, list[str]], body: dict[str, Any]
  ) -> tuple[int, Any]:
    report = self.reports.publish_report(
      str(body.get("id", "")),
      str(body.get("title", "")),
      str(body.get("body", "")),
    )
    return (int(HTTPStatus.CREATED), {"report": self._serialize_report(report)})

  def _handle_get_report(
    self, params: dict[str, str], _query: dict[str, list[str]], _body: Any
  ) -> tuple[int, Any]:
    report = self.reports.get_report(params["id"])
    return (int(HTTPStatus.OK), {"report": self._serialize_report(report)})

  def _handle_patch_report(
    self, params: dict[str, str], _query: dict[str, list[str]], body: dict[str, Any]
  ) -> tuple[int, Any]:
    report = self.reports.get_report(params["id"])
    new_status = str(body.get("status", "")).strip()
    if new_status == "dismissed":
      self.reports.remove_report(report.id)
      _REPORT_RENDER_CACHE.pop(report.id, None)
      report.status = "dismissed"
      return (
        int(HTTPStatus.OK),
        {"report": self._serialize_report(report, include_body=False)},
      )
    return (int(HTTPStatus.OK), {"report": self._serialize_report(report)})

  def _handle_delete_report(
    self, params: dict[str, str], _query: dict[str, list[str]], _body: Any
  ) -> tuple[int, Any]:
    removed = self.reports.remove_report(params["id"])
    _REPORT_RENDER_CACHE.pop(params["id"], None)
    return (int(HTTPStatus.OK), {"dismissed": removed})

  def _handle_mark_report_seen(
    self, params: dict[str, str], _query: dict[str, list[str]], _body: Any
  ) -> tuple[int, Any]:
    report = self.reports.mark_seen(params["id"])
    return (int(HTTPStatus.OK), {"report": self._serialize_report(report)})

  def _handle_mark_ack_seen(
    self, params: dict[str, str], _query: dict[str, list[str]], _body: Any
  ) -> tuple[int, Any]:
    report = self.reports.mark_ack_seen(params["id"])
    return (int(HTTPStatus.OK), {"report": self._serialize_report(report)})

  def _handle_submit_answer(
    self, params: dict[str, str], _query: dict[str, list[str]], body: dict[str, Any]
  ) -> tuple[int, Any]:
    values = body.get("values", body)
    answer = self.reports.submit_answer(
      params["id"],
      values,
      answer_id=body.get("id") if isinstance(body, dict) else None,
    )
    report = self.reports.get_report(params["id"])
    return (
      int(HTTPStatus.CREATED),
      {"answer": answer.to_dict(), "report": self._serialize_report(report)},
    )

  def _handle_ack_report_answer(
    self, params: dict[str, str], _query: dict[str, list[str]], body: dict[str, Any]
  ) -> tuple[int, Any]:
    markdown = str(body.get("markdown", body.get("ack", "")))
    answer = self.reports.ack_answer(params["id"], params["answer_id"], markdown)
    return (int(HTTPStatus.OK), {"answer": answer.to_dict()})

  @staticmethod
  def _serialize_message(msg: Any) -> dict[str, Any]:
    payload = msg.to_dict()
    payload["body_html"] = render_markdown(msg.body, breaks=True)
    payload["acks_html"] = [render_markdown(ack, breaks=True) for ack in msg.acks]
    return payload

  @staticmethod
  def _serialize_report(report: Any, *, include_body: bool = True) -> dict[str, Any]:
    payload = report.to_dict()
    for ans in payload.get("answers", []):
      ans["ack_html"] = (
        render_markdown(ans["ack"], breaks=True) if ans.get("ack") else ""
      )
      ans["acks_html"] = [render_markdown(a, breaks=True) for a in ans.get("acks", [])]
    if getattr(report, "status", "") == "dismissed":
      _REPORT_RENDER_CACHE.pop(report.id, None)
    if not include_body:
      payload.pop("body", None)
      return payload
    cached = _REPORT_RENDER_CACHE.get(report.id)
    if cached is not None and cached[0] == report.body:
      payload["blocks"] = cached[1]
      return payload
    blocks, _ = parse_report_markdown(report.body)
    serialized_blocks: list[dict[str, Any]] = []
    for btype, val in blocks:
      if btype == "markdown":
        block_headings: list[dict[str, Any]] = []
        block_html = render_markdown(val, breaks=False, headings=block_headings)
        serialized_blocks.append(
          {
            "type": "markdown",
            "markdown": val,
            "html": block_html,
            "headings": block_headings,
          }
        )
      else:
        serialized_blocks.append({"type": "field", "field": val.to_dict()})
    if getattr(report, "status", "") != "dismissed":
      _REPORT_RENDER_CACHE[report.id] = (report.body, serialized_blocks)
    payload["blocks"] = serialized_blocks
    return payload


_REPORT_RENDER_CACHE: dict[str, tuple[str, list[dict[str, Any]]]] = {}


def file_signature(
  paths: Iterable[Path],
) -> tuple[tuple[str, int | None, int | None], ...]:
  """Return a tuple of (path, mtime_ns, size) for each target file."""
  entries: list[tuple[str, int | None, int | None]] = []
  for target in paths:
    try:
      st = target.stat()
      entries.append((str(target), st.st_mtime_ns, st.st_size))
    except OSError:
      entries.append((str(target), None, None))
  return tuple(entries)


def assets_signature(
  assets_dir: str | Path | None = None,
) -> tuple[tuple[str, int | None, int | None], ...]:
  """Return the hot-reload signature for bundled web assets."""
  base = (
    Path(assets_dir)
    if assets_dir is not None
    else Path(__file__).resolve().parents[2] / "assets"
  )
  if not base.is_dir():
    return ()
  targets = sorted(
    p for p in base.iterdir() if p.suffix.lower() in {".html", ".css", ".js", ".mjs"}
  )
  return file_signature(targets)


def scripts_signature(
  scripts_dir: str | Path | None = None,
) -> tuple[tuple[str, int | None, int | None], ...]:
  """Return the hot-reload signature for Arena Steering Python modules."""
  base = (
    Path(scripts_dir) if scripts_dir is not None else Path(__file__).resolve().parent
  )
  if not base.is_dir():
    return ()
  targets = sorted(base.glob("*.py"))
  demo_py = base.parent / "demo.py"
  if demo_py.is_file():
    targets.append(demo_py)
  return file_signature(targets)


def make_request_handler(app: SteeringApp) -> type[BaseHTTPRequestHandler]:
  """Create a BaseHTTPRequestHandler bound to `app`."""

  class SteeringRequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
      return

    def do_OPTIONS(self) -> None:
      self.send_response(int(HTTPStatus.NO_CONTENT))
      self._send_common_headers("text/plain; charset=utf-8", 0)
      self.end_headers()

    def do_GET(self) -> None:
      parsed = urlparse(self.path)
      path = parsed.path.rstrip("/") or "/"
      if path in {"/api/ws", "/ws"}:
        self._handle_websocket()
        return
      route_path = (
        (path[len("/api") :] or "/")
        if path.startswith("/api/") and path != "/api"
        else path
      )
      if app.is_static_request(route_path):
        asset = app.resolve_asset(route_path)
        if asset is None:
          self._write_json(
            int(HTTPStatus.NOT_FOUND), {"error": f"Asset not found: {parsed.path}"}
          )
          return
        raw_bytes, content_type = asset
        self.send_response(int(HTTPStatus.OK))
        self._send_common_headers(content_type, len(raw_bytes))
        self.end_headers()
        self.wfile.write(raw_bytes)
        return
      handler, _, allowed = app.router.match("GET", route_path)
      if handler is not None or allowed:
        status, payload = app.dispatch("GET", self.path)
        self._write_json(status, payload)
        return
      asset = app.resolve_asset(parsed.path)
      if asset is None:
        self._write_json(
          int(HTTPStatus.NOT_FOUND), {"error": f"Asset not found: {parsed.path}"}
        )
        return
      raw_bytes, content_type = asset
      self.send_response(int(HTTPStatus.OK))
      self._send_common_headers(content_type, len(raw_bytes))
      self.end_headers()
      self.wfile.write(raw_bytes)

    def ws_send(self, opcode: int, data: bytes) -> None:
      size = len(data)
      length = (
        bytes([size])
        if size < 126
        else (
          b"\x7e" + size.to_bytes(2, "big")
          if size < 65536
          else b"\x7f" + size.to_bytes(8, "big")
        )
      )
      self.connection.sendall(bytes([0x80 | opcode]) + length + data)

    def ws_dispatch(self, value: Any) -> None:
      if not isinstance(value, dict):
        raise TypeError("Expected an object")
      if value.get("type") == "pong":
        return
      request_id = value.get("id")
      method = str(value.get("method", "GET")).upper()
      path = str(value.get("path", ""))
      raw_body = value.get("body", "")
      if (
        type(request_id) not in (str, int)
        or len(str(request_id)) > 80
        or method not in ("GET", "POST", "PATCH", "DELETE")
        or not path.startswith("/")
        or urlsplit(path).path in {"/api/ws", "/ws"}
        or not isinstance(raw_body, str)
      ):
        raise ValueError("Invalid WebSocket request")
      body_dict: dict[str, Any] = {}
      if raw_body.strip():
        parsed_body = json.loads(raw_body)
        if not isinstance(parsed_body, dict):
          raise ValueError("JSON request body must be an object")
        body_dict = parsed_body
      status, payload = app.dispatch(method, path, body_dict)
      reply = json.dumps(
        {
          "type": "response",
          "id": request_id,
          "status": status,
          "contentType": "application/json; charset=utf-8",
          "body": json.dumps(payload),
        }
      ).encode("utf-8")
      self.ws_send(1, reply)

    def _handle_websocket(self) -> None:
      if (
        self.headers.get("Upgrade", "").lower() != "websocket"
        or "upgrade"
        not in {
          part.strip() for part in self.headers.get("Connection", "").lower().split(",")
        }
        or self.headers.get("Sec-WebSocket-Version") != "13"
      ):
        self._write_json(
          int(HTTPStatus.BAD_REQUEST),
          {"error": "Expected a version 13 WebSocket upgrade"},
        )
        return
      key = self.headers.get("Sec-WebSocket-Key", "")
      try:
        if len(base64.b64decode(key, validate=True)) != 16:
          raise ValueError("Invalid WebSocket key")
      except ValueError as exc:
        self._write_json(int(HTTPStatus.BAD_REQUEST), {"error": str(exc)})
        return
      self.protocol_version = "HTTP/1.1"
      self.send_response(101)
      self.send_header("Upgrade", "websocket")
      self.send_header("Connection", "Upgrade")
      accept = base64.b64encode(
        hashlib.sha1(
          (key + WS_GUID).encode("utf-8"),
          usedforsecurity=False,
        ).digest()
      ).decode("ascii")
      self.send_header("Sec-WebSocket-Accept", accept)
      self.end_headers()
      self.close_connection = True
      self.connection.settimeout(WS_TICK_SECONDS)
      buffer = bytearray()
      message = bytearray()
      fragmented = False
      last_seen = last_heartbeat = time.monotonic()
      try:
        version = app.data_version()
        ack_snapshot = app.report_ack_snapshot()
        asset_ver = assets_signature(app.assets_dir)
        self.ws_send(1, b'{"type":"change"}')
        while True:
          try:
            chunk = self.connection.recv(65536)
            if not chunk:
              return
            buffer.extend(chunk)
            last_seen = time.monotonic()
          except TimeoutError:
            pass
          while len(buffer) >= 2:
            first, second = buffer[:2]
            opcode, final = first & 15, bool(first & 128)
            if first & 112 or not (second & 128) or opcode not in (0, 1, 2, 8, 9, 10):
              raise ValueError("Invalid frame")
            size, offset = second & 127, 2
            if size in (126, 127):
              width = 2 if size == 126 else 8
              if len(buffer) < 2 + width:
                break
              size = int.from_bytes(buffer[2 : 2 + width], "big")
              offset += width
            if opcode >= 8 and (not final or size > 125):
              raise ValueError("Invalid control frame")
            if size + (len(message) if opcode < 8 else 0) > WS_MAX_MESSAGE:
              self.ws_send(8, (1009).to_bytes(2, "big"))
              return
            if len(buffer) < offset + 4 + size:
              break
            mask = buffer[offset : offset + 4]
            data = bytes(
              v ^ mask[i % 4]
              for i, v in enumerate(buffer[offset + 4 : offset + 4 + size])
            )
            del buffer[: offset + 4 + size]
            if opcode == 8:
              self.ws_send(8, data[:2] if len(data) >= 2 else b"")
              return
            if opcode == 9:
              self.ws_send(10, data)
              continue
            if opcode == 10:
              continue
            if opcode == 2:
              self.ws_send(8, (1003).to_bytes(2, "big"))
              return
            if (opcode == 0) != fragmented:
              raise ValueError("Invalid continuation")
            message.extend(data)
            fragmented = not final
            if final:
              self.ws_dispatch(json.loads(message.decode("utf-8")))
              message.clear()
          current = app.data_version()
          if current != version:
            version = current
            ack_events, ack_snapshot = app.report_acked_events(ack_snapshot)
            for ack_event in ack_events:
              self.ws_send(1, json.dumps(ack_event).encode("utf-8"))
            self.ws_send(1, b'{"type":"change"}')
          current_assets = assets_signature(app.assets_dir)
          if current_assets != asset_ver:
            asset_ver = current_assets
            self.ws_send(1, b'{"type":"reload"}')
          now = time.monotonic()
          if now - last_seen > WS_IDLE_SECONDS:
            self.ws_send(8, (1001).to_bytes(2, "big"))
            return
          if now - last_heartbeat >= WS_HEARTBEAT_SECONDS:
            self.ws_send(1, b'{"type":"heartbeat"}')
            last_heartbeat = now
      except (ValueError, TypeError) as error:
        code = 1007 if isinstance(error, UnicodeDecodeError) else 1002
        try:
          self.ws_send(8, code.to_bytes(2, "big"))
        except OSError:
          pass
      except (OSError, sqlite3.Error):
        return

    def do_POST(self) -> None:
      self._handle_json_method("POST")

    def do_PATCH(self) -> None:
      self._handle_json_method("PATCH")

    def do_DELETE(self) -> None:
      self._handle_json_method("DELETE")

    def _handle_json_method(self, method: str) -> None:
      try:
        content_type = self.headers.get("Content-Type", "")
        if content_type.lower().startswith("multipart/form-data"):
          body = self._read_multipart_body(content_type)
        else:
          body = self._read_json_body()
      except (TypeError, ValueError) as exc:
        self._write_json(int(HTTPStatus.BAD_REQUEST), {"error": str(exc)})
        return
      status, payload = app.dispatch(method, self.path, body)
      self._write_json(status, payload)

    def _read_multipart_body(self, content_type: str) -> dict[str, Any]:
      boundary_match = re.search(r"boundary=(?:\"([^\"]+)\"|([^;]+))", content_type)
      if boundary_match is None:
        raise ValueError("Multipart boundary is required")
      boundary = (boundary_match.group(1) or boundary_match.group(2)).strip()
      length = int(self.headers.get("Content-Length", "0") or "0")
      raw = self.rfile.read(length) if length > 0 else b""
      body: dict[str, Any] = {}
      marker = b"--" + boundary.encode("utf-8")
      for part in raw.split(marker):
        if part in (b"", b"--", b"--\r\n", b"\r\n"):
          continue
        if part.startswith(b"\r\n"):
          part = part[2:]
        if part.endswith(b"\r\n"):
          part = part[:-2]
        if part.endswith(b"--"):
          part = part[:-2].rstrip(b"\r\n")
        header_blob, separator, data = part.partition(b"\r\n\r\n")
        if not separator:
          continue
        headers = header_blob.decode("utf-8", errors="replace")
        disposition = ""
        for line in headers.split("\r\n"):
          if line.lower().startswith("content-disposition:"):
            disposition = line
            break
        name_match = re.search(r'name="([^"]+)"', disposition)
        if name_match is None:
          continue
        field_name = name_match.group(1)
        filename_match = re.search(r'filename="([^"]*)"', disposition)
        if filename_match is not None and filename_match.group(1):
          body["file"] = {
            "name": filename_match.group(1),
            "content_base64": base64.b64encode(data).decode("ascii"),
          }
        else:
          body[field_name] = data.decode("utf-8")
      return body

    def _read_json_body(self) -> dict[str, Any]:
      length = int(self.headers.get("Content-Length", "0") or "0")
      if length <= 0:
        return {}
      raw = self.rfile.read(length).decode("utf-8")
      if not raw.strip():
        return {}
      try:
        parsed = json.loads(raw)
      except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON request body: {exc}") from exc
      if not isinstance(parsed, dict):
        raise TypeError("JSON request body must be an object")
      return parsed

    def _write_json(self, status: int, payload: dict[str, Any]) -> None:
      encoded = json.dumps(payload).encode("utf-8")
      self.send_response(status)
      self._send_common_headers("application/json; charset=utf-8", len(encoded))
      self.end_headers()
      self.wfile.write(encoded)

    def _send_common_headers(self, content_type: str, length: int) -> None:
      self.send_header("Content-Type", content_type)
      self.send_header("Content-Length", str(length))
      self.send_header("Cache-Control", "no-store")
      self.send_header("Access-Control-Allow-Origin", "*")
      self.send_header(
        "Access-Control-Allow-Methods", "GET, POST, PATCH, DELETE, OPTIONS"
      )
      self.send_header("Access-Control-Allow-Headers", "Content-Type")

  return SteeringRequestHandler


def reload_server_handler(server: ThreadingHTTPServer, app: SteeringApp) -> SteeringApp:
  """Reload arena_steering modules and swap server.RequestHandlerClass in-process."""
  pkg = __package__ or "arena_steering"
  for sub in ("models", "ports", "store", "markdown_fields", "services", "server"):
    mod_name = f"{pkg}.{sub}"
    if mod_name in sys.modules:
      importlib.reload(sys.modules[mod_name])
  server_mod = sys.modules.get(f"{pkg}.server")
  store_mod = sys.modules.get(f"{pkg}.store")
  db_path = getattr(app.store, "db_path", ":memory:")
  new_store = (
    store_mod.SqliteStore(db_path)
    if store_mod is not None and db_path != ":memory:"
    else app.store
  )
  app_cls = getattr(server_mod, "SteeringApp", SteeringApp)
  handler_fn = getattr(server_mod, "make_request_handler", make_request_handler)
  new_app = app_cls(
    new_store,
    assets_dir=app.assets_dir,
    repo_name=app.repo_name,
  )
  server.RequestHandlerClass = handler_fn(new_app)
  return new_app


def watch_hot_reload(
  server: ThreadingHTTPServer,
  app: SteeringApp,
  stop: threading.Event | None = None,
  interval: float = 1.0,
  scripts_dir: str | Path | None = None,
) -> None:
  """Watch Python modules and swap server.RequestHandlerClass without closing TCP socket."""
  baseline = scripts_signature(scripts_dir)
  current_app = app
  while stop is None or not stop.is_set():
    if stop is None:
      time.sleep(interval)
    elif stop.wait(interval):
      return
    current = scripts_signature(scripts_dir)
    if current != baseline:
      baseline = current
      try:
        current_app = reload_server_handler(server, current_app)
      except Exception as exc:
        print(f"Hot-reload skipped: {exc}", file=sys.stderr, flush=True)


def create_http_server(
  app: SteeringApp,
  host: str = "0.0.0.0",
  port: int = 8100,
) -> ThreadingHTTPServer:
  """Create a ThreadingHTTPServer bound to host:port for SteeringApp."""
  server = ThreadingHTTPServer((host, port), make_request_handler(app))
  if not os.environ.get("PYTEST_CURRENT_TEST"):
    stop_event = threading.Event()
    server._hot_reload_stop = stop_event  # type: ignore[attr-defined]
    threading.Thread(
      target=watch_hot_reload,
      args=(server, app, stop_event),
      daemon=True,
    ).start()
  return server
