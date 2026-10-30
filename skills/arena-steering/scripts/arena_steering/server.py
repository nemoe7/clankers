"""HTTP router and local steering server for Arena Steering."""

from __future__ import annotations

import base64
import hashlib
import html
import importlib
import importlib.util
import json
import mimetypes
import os
import re
import sqlite3
import sys
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
}

REPORT_IMAGE_EXTS = frozenset({".gif", ".png", ".jpg", ".jpeg", ".webp", ".svg"})


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
    default_assets = Path(__file__).resolve().parents[2] / "assets"
    self.assets_dir = Path(assets_dir) if assets_dir is not None else default_assets
    self.repo_name = repo_name or _detect_repo_name(store)
    self.messages = MessageService(store, store, store)
    self.tasks = TaskService(store, store)
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
    self.router.add("GET", "/messages/{id}", self._handle_get_message)
    self.router.add("POST", "/messages/{id}/ack", self._handle_ack_message)
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
      status, payload = handler(params, query, body or {})
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
    """Resolve a static file inside assets_dir or report images without path traversal."""
    clean = request_path.split("?", 1)[0].lstrip("/")
    if not clean or clean in {"index.html", "messages", "tasks", "reports"}:
      clean = "index.html"
    elif clean.startswith("assets/"):
      clean = clean[len("assets/") :]
    base = self.assets_dir.resolve()
    candidate = (base / clean).resolve()
    if not candidate.is_relative_to(base) or not candidate.is_file():
      candidate = self._resolve_shared_or_report_asset(clean)
      if candidate is None:
        return None
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

  def _resolve_shared_or_report_asset(self, clean_path: str) -> Path | None:
    """Resolve shared vendor assets (`mermaid.min.js`) or report images without path traversal."""
    if clean_path in {"mermaid.min.js", "mermaid.LICENSE"}:
      shared = (
        Path(__file__).resolve().parents[3] / "arena-skill" / "assets" / clean_path
      ).resolve()
      if shared.is_file():
        return shared
    return self._resolve_report_image(clean_path)

  def _resolve_report_image(self, clean_path: str) -> Path | None:
    """Resolve an image or GIF inside <state_dir>/reports/ without path traversal."""
    db_path = getattr(self.store, "db_path", "")
    if not db_path or db_path == ":memory:":
      return None
    rel = clean_path.removeprefix("reports/")
    suffix = Path(rel).suffix.lower()
    if suffix not in REPORT_IMAGE_EXTS:
      return None
    state_dir = Path(db_path).resolve().parent
    for root in (state_dir / "reports", state_dir):
      root_resolved = root.resolve()
      candidate = (root_resolved / rel).resolve()
      if candidate.is_relative_to(root_resolved) and candidate.is_file():
        return candidate
    return None

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
        "survey": survey,
      },
    )

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
    items = self.messages.list_messages(
      unread_only=not include_all,
      include_hidden=include_hidden,
    )
    total = len(items)
    before_id = (query.get("before", [""])[0] or "").strip()
    if before_id:
      for idx, item in enumerate(items):
        if item.id == before_id:
          items = items[:idx]
          break
    limit_raw = (query.get("limit", [""])[0] or "").strip()
    has_more = False
    if limit_raw.isdigit() and int(limit_raw) > 0:
      limit = int(limit_raw)
      if len(items) > limit:
        has_more = True
        items = items[-limit:]
    return (
      int(HTTPStatus.OK),
      {
        "messages": [self._serialize_message(item) for item in items],
        "total": total,
        "has_more": has_more,
      },
    )

  def _handle_create_message(
    self, _params: dict[str, str], _query: dict[str, list[str]], body: dict[str, Any]
  ) -> tuple[int, Any]:
    attachments = [Attachment.from_dict(raw) for raw in body.get("attachments", [])]
    msg = self.messages.send_message(
      str(body.get("body", "")),
      hidden=bool(body.get("hidden", False)),
      blocking=bool(body.get("blocking", True)),
      attachments=attachments,
      msg_id=body.get("id"),
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
    _, acked = self.messages.ack(params["id"], markdown)
    return (int(HTTPStatus.OK), {"message": self._serialize_message(acked)})

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
        body = self._read_json_body()
      except ValueError as exc:
        self._write_json(int(HTTPStatus.BAD_REQUEST), {"error": str(exc)})
        return
      status, payload = app.dispatch(method, self.path, body)
      self._write_json(status, payload)

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
