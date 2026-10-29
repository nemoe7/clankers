"""HTTP router and local steering server for Arena Steering."""

from __future__ import annotations

import json
import mimetypes
import re
from collections.abc import Callable
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from . import __version__
from .markdown_fields import parse_report_markdown
from .models import Attachment
from .services import MessageService, ReportService, TaskService
from .store import SqliteStore

RouteHandler = Callable[[dict[str, str], dict[str, list[str]], Any], tuple[int, Any]]

MIME_OVERRIDES = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "application/javascript; charset=utf-8",
  ".mjs": "application/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
  ".woff2": "font/woff2",
}


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


class SteeringApp:
  """Application facade wiring services and REST endpoints."""

  def __init__(
    self,
    store: SqliteStore,
    assets_dir: str | Path | None = None,
  ) -> None:
    self.store = store
    default_assets = Path(__file__).resolve().parents[2] / "assets"
    self.assets_dir = Path(assets_dir) if assets_dir is not None else default_assets
    self.messages = MessageService(store, store, store)
    self.tasks = TaskService(store, store)
    self.reports = ReportService(
      store,
      store,
      on_answer_callback=self.messages.notify_new_work,
    )
    self.router = Router()
    self._register_routes()

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
    self.router.add("POST", "/reports/{id}/answers", self._handle_submit_answer)
    self.router.add(
      "POST",
      "/reports/{id}/answers/{answer_id}/ack",
      self._handle_ack_report_answer,
    )

  def dispatch(
    self, method: str, raw_url: str, body: dict[str, Any] | None = None
  ) -> tuple[int, dict[str, Any]]:
    """Dispatch a request and return (status_code, json_payload)."""
    parsed = urlparse(raw_url)
    path = parsed.path.rstrip("/") or "/"
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
      return handler(params, query, body or {})
    except KeyError as exc:
      return (
        int(HTTPStatus.NOT_FOUND),
        {"error": str(exc.args[0] if exc.args else exc)},
      )
    except ValueError as exc:
      return (int(HTTPStatus.BAD_REQUEST), {"error": str(exc)})

  def resolve_asset(self, request_path: str) -> tuple[bytes, str] | None:
    """Resolve a static file inside assets_dir without path traversal."""
    clean = request_path.split("?", 1)[0].lstrip("/")
    if not clean or clean in {"index.html", "inbox", "tasks", "reports"}:
      clean = "index.html"
    elif clean.startswith("assets/"):
      clean = clean[len("assets/") :]
    base = self.assets_dir.resolve()
    candidate = (base / clean).resolve()
    if not candidate.is_relative_to(base) or not candidate.is_file():
      return None
    suffix = candidate.suffix.lower()
    content_type = (
      MIME_OVERRIDES.get(suffix)
      or mimetypes.guess_type(candidate.name)[0]
      or "application/octet-stream"
    )
    return candidate.read_bytes(), content_type

  def _handle_health(
    self, _params: dict[str, str], _query: dict[str, list[str]], _body: Any
  ) -> tuple[int, Any]:
    return (int(HTTPStatus.OK), {"ok": True, "version": __version__})

  def _handle_list_messages(
    self, _params: dict[str, str], query: dict[str, list[str]], _body: Any
  ) -> tuple[int, Any]:
    include_all = query.get("all", ["0"])[0] in {"1", "true"}
    include_hidden = query.get("hidden", ["0"])[0] in {"1", "true"}
    items = self.messages.list_messages(
      unread_only=not include_all,
      include_hidden=include_hidden,
    )
    return (
      int(HTTPStatus.OK),
      {"messages": [item.to_dict() for item in items]},
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
    return (int(HTTPStatus.CREATED), {"message": msg.to_dict()})

  def _handle_get_message(
    self, params: dict[str, str], _query: dict[str, list[str]], _body: Any
  ) -> tuple[int, Any]:
    msg = self.messages.get_message(params["id"])
    return (int(HTTPStatus.OK), {"message": msg.to_dict()})

  def _handle_ack_message(
    self, params: dict[str, str], _query: dict[str, list[str]], body: dict[str, Any]
  ) -> tuple[int, Any]:
    markdown = str(body.get("markdown", body.get("ack", "")))
    _, acked = self.messages.ack(params["id"], markdown)
    return (int(HTTPStatus.OK), {"message": acked.to_dict()})

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
    task = self.tasks.create_task(
      str(body.get("id", "")),
      str(body.get("title", "")),
      type=str(body.get("type", "code")),
      status=str(body.get("status", "upcoming")),
      scope=str(body.get("scope", "")),
      details=[str(x) for x in body.get("details", [])],
      msg_ids=[str(x) for x in body.get("msg_ids", [])],
      report_ids=[str(x) for x in body.get("report_ids", [])],
      deps=[str(x) for x in body.get("deps", [])],
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
    items = self.reports.list_reports(stale_only=stale_only)
    return (
      int(HTTPStatus.OK),
      {"reports": [self._serialize_report(item) for item in items]},
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
      report = self.reports.get_report(report.id)
    return (int(HTTPStatus.OK), {"report": self._serialize_report(report)})

  def _handle_delete_report(
    self, params: dict[str, str], _query: dict[str, list[str]], _body: Any
  ) -> tuple[int, Any]:
    removed = self.reports.remove_report(params["id"])
    return (int(HTTPStatus.OK), {"dismissed": removed})

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
  def _serialize_report(report: Any) -> dict[str, Any]:
    payload = report.to_dict()
    blocks, _ = parse_report_markdown(report.body)
    payload["blocks"] = [
      {"type": "markdown", "markdown": val}
      if btype == "markdown"
      else {"type": "field", "field": val.to_dict()}
      for btype, val in blocks
    ]
    return payload


def create_http_server(
  app: SteeringApp, host: str = "0.0.0.0", port: int = 8100
) -> ThreadingHTTPServer:
  """Create a ThreadingHTTPServer bound to host:port for SteeringApp."""

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
      handler, _, allowed = app.router.match("GET", path)
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

  return ThreadingHTTPServer((host, port), SteeringRequestHandler)
