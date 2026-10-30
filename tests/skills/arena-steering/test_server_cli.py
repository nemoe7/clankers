"""Tests for Arena Steering HTTP router (`server.py`) and `steer` CLI (`cli.py`)."""

from __future__ import annotations

import io
from http import HTTPStatus
from pathlib import Path

from arena_steering import __version__
from arena_steering.cli import main as cli_main
from arena_steering.markdown import render_markdown
from arena_steering.server import SteeringApp
from arena_steering.store import SqliteStore

MSG_ID_CLI = "a0b1c2"
ACK_MARKDOWN = "ack-token-verified"
SECOND_DETAIL_TOKEN = "detail-token-two"
REPORT_ID_PORT = "port-report"
TASK_ID_CLI = "cli-task"
TASK_ID_BASE = "base-task"


def _run_cli(state_dir: Path, *args: str) -> tuple[int, str, str]:
  out = io.StringIO()
  err = io.StringIO()
  code = cli_main(["--state-dir", str(state_dir), *args], out=out, err=err)
  return code, out.getvalue(), err.getvalue()


def test_cli_version_flags() -> None:
  out = io.StringIO()
  code = cli_main(["--version"], out=out)
  assert code == 0
  assert out.getvalue().strip() == f"steer {__version__}"


def test_http_endpoints_for_messages_tasks_and_reports(tmp_path: Path) -> None:
  store = SqliteStore(tmp_path / "http.sqlite3")
  app = SteeringApp(store)

  status, created = app.dispatch(
    "POST",
    "/messages",
    {"id": "12ab34", "body": "Ship the router", "hidden": False, "blocking": True},
  )
  assert status == int(HTTPStatus.CREATED)
  assert created["message"]["id"] == "12ab34"

  status, unread = app.dispatch("GET", "/messages")
  assert status == int(HTTPStatus.OK)
  assert [item["id"] for item in unread["messages"]] == ["12ab34"]

  status, single = app.dispatch("GET", "/messages/12ab34")
  assert status == int(HTTPStatus.OK)
  assert single["message"]["body"] == "Ship the router"

  status, acked = app.dispatch(
    "POST", "/messages/12ab34/ack", {"markdown": "Router shipped."}
  )
  assert status == int(HTTPStatus.OK)
  assert acked["message"]["status"] == "acked"
  assert acked["message"]["acks"] == ["Router shipped."]

  status, t_created = app.dispatch(
    "POST",
    "/tasks",
    {"id": "build-router", "title": "Build HTTP router", "type": "code"},
  )
  assert status == int(HTTPStatus.CREATED)
  assert t_created["task"]["id"] == "build-router"

  status, t_patched = app.dispatch(
    "PATCH",
    "/tasks/build-router",
    {"status": "in_progress", "details": ["Registered REST endpoints."]},
  )
  assert status == int(HTTPStatus.OK)
  assert t_patched["task"]["status"] == "in_progress"

  status, r_created = app.dispatch(
    "POST",
    "/reports",
    {
      "id": "router-spec",
      "title": "Router Spec",
      "body": "We should bind to this host\n- (x) 0.0.0.0\n- ( ) 127.0.0.1\n",
    },
  )
  assert status == int(HTTPStatus.CREATED)
  assert len(r_created["report"]["fields"]) == 1

  status, r_ans = app.dispatch(
    "POST",
    "/reports/router-spec/answers",
    {"id": "cafe01", "values": {"we-should-bind-to-this-host": "0.0.0.0"}},
  )
  assert status == int(HTTPStatus.CREATED)
  assert r_ans["answer"]["id"] == "cafe01"

  status, r_acked = app.dispatch(
    "POST",
    "/reports/router-spec/answers/cafe01/ack",
    {"markdown": "Confirmed 0.0.0.0."},
  )
  assert status == int(HTTPStatus.OK)
  assert r_acked["answer"]["status"] == "acked"

  status, deleted = app.dispatch("DELETE", "/tasks/build-router")
  assert status == int(HTTPStatus.OK)
  assert deleted["deleted"] == "build-router"
  store.close()


def test_resolve_asset_serves_report_gifs_and_images(tmp_path: Path) -> None:
  state_dir = tmp_path / "state"
  reports_dir = state_dir / "reports"
  reports_dir.mkdir(parents=True)
  gif_bytes = (
    b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff"
    b"!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
  )
  png_bytes = b"\x89PNG\r\n\x1a\n"
  (reports_dir / "scroll-fade.gif").write_bytes(gif_bytes)
  (reports_dir / "board.png").write_bytes(png_bytes)

  store = SqliteStore(state_dir / "state.sqlite3")
  app = SteeringApp(store)
  resolved_gif = app.resolve_asset("/scroll-fade.gif")
  assert resolved_gif is not None
  assert resolved_gif == (gif_bytes, "image/gif")

  resolved_png = app.resolve_asset("/reports/board.png")
  assert resolved_png is not None
  assert resolved_png == (png_bytes, "image/png")

  assert app.resolve_asset("/../secret.gif") is None
  mermaid_asset = app.resolve_asset("/mermaid.min.js")
  assert mermaid_asset is not None
  assert mermaid_asset[1] == "application/javascript; charset=utf-8"
  store.close()


def test_server_markdown_it_diff_and_report_summary_cache(tmp_path: Path) -> None:
  headings: list[dict[str, object]] = []
  rendered = render_markdown(
    (
      "# Patch Notes\n\n"
      "Highlighted ==token== and ~~removed~~ and https://example.com:\n\n"
      "- [x] Ship task list\n- [ ] Pending item\n\n"
      "```diff\n@@ -1,2 +1,2 @@\n-old_line\n+new_line\n```\n"
    ),
    headings=headings,
  )
  assert '<h1 id="sec-patch-notes">Patch Notes</h1>' in rendered
  assert "<mark>token</mark>" in rendered
  assert "<s>removed</s>" in rendered
  assert 'href="https://example.com"' in rendered
  assert 'class="task-list-item-checkbox" disabled checked' in rendered
  assert '<span class="token coord">@@ -1,2 +1,2 @@</span>' in rendered
  assert '<span class="token deleted">-old_line</span>' in rendered
  assert '<span class="token inserted">+new_line</span>' in rendered
  assert headings == [{"id": "sec-patch-notes", "level": 1, "text": "Patch Notes"}]

  store = SqliteStore(tmp_path / "md.sqlite3")
  app = SteeringApp(store)
  app.dispatch(
    "POST",
    "/reports",
    {
      "id": "diff-report",
      "title": "Diff Report",
      "body": "# Diff Report\n\n```diff\n-old\n+new\n```\n",
    },
  )
  status_sum, summary_res = app.dispatch("GET", "/reports?summary=1")
  assert status_sum == int(HTTPStatus.OK)
  assert "blocks" not in summary_res["reports"][0]
  assert "body" not in summary_res["reports"][0]
  assert "modified_at" in summary_res["reports"][0]

  status_full, full_res = app.dispatch("GET", "/reports/diff-report")
  assert status_full == int(HTTPStatus.OK)
  assert "blocks" in full_res["report"]
  assert (
    '<span class="token inserted">+new</span>'
    in full_res["report"]["blocks"][0]["html"]
  )
  store.close()


def test_cli_end_to_end_messages_tasks_and_reports(tmp_path: Path) -> None:
  state_dir = tmp_path / "state"
  store = SqliteStore(state_dir / "state.sqlite3")
  app = SteeringApp(store)
  app.dispatch("POST", "/messages", {"id": MSG_ID_CLI, "body": "Add CLI tests"})
  store.close()

  code, out, _ = _run_cli(state_dir, "read")
  assert code == 0
  assert "Inbox " in out
  assert MSG_ID_CLI in out

  code, out, _ = _run_cli(
    state_dir,
    "ack",
    MSG_ID_CLI,
    ACK_MARKDOWN,
    "-i",
    TASK_ID_CLI,
    "-t",
    "Build steer CLI",
    "-T",
    "code",
    "-S",
    "skills/arena-steering/",
    "-d",
    "Initial CLI setup.",
  )
  assert code == 0
  assert MSG_ID_CLI in out
  assert TASK_ID_CLI in out

  code, out, _ = _run_cli(state_dir, "msg", "show", MSG_ID_CLI)
  assert code == 0
  assert ACK_MARKDOWN in out

  code, out, _ = _run_cli(state_dir, "task", "new", TASK_ID_BASE, "Base task")
  assert code == 0
  assert TASK_ID_BASE in out

  code, out, _ = _run_cli(state_dir, "task", "mod", TASK_ID_CLI, "deps", TASK_ID_BASE)
  assert code == 0
  assert TASK_ID_BASE in out

  code, out, _ = _run_cli(state_dir, "tasks")
  assert code == 0
  assert out.index(TASK_ID_BASE) < out.index(TASK_ID_CLI)

  code, out, _ = _run_cli(
    state_dir, "task", "mod", TASK_ID_CLI, "deets", SECOND_DETAIL_TOKEN
  )
  assert code == 0
  assert SECOND_DETAIL_TOKEN in out

  code, out, _ = _run_cli(state_dir, "task", "mod", TASK_ID_CLI, "deets", "rm", "2")
  assert code == 0
  assert SECOND_DETAIL_TOKEN not in out

  report_md = tmp_path / "sample.md"
  report_md.write_text(
    "# Sample\n\nWe should use this port\n- (x) 8000\n- ( ) 9000\n",
    encoding="utf-8",
  )
  code, out, _ = _run_cli(
    state_dir,
    "report",
    "pub",
    str(report_md),
    "-i",
    REPORT_ID_PORT,
    "-t",
    "Port Report",
  )
  assert code == 0
  assert REPORT_ID_PORT in out

  code, out, _ = _run_cli(
    state_dir, "task", "mod", TASK_ID_CLI, "links", REPORT_ID_PORT
  )
  assert code == 0
  assert REPORT_ID_PORT in out

  code, out, _ = _run_cli(
    state_dir,
    "task",
    "mod",
    TASK_ID_CLI,
    "links",
    "rm",
    "report",
    REPORT_ID_PORT,
  )
  assert code == 0
  assert REPORT_ID_PORT not in out

  code, out, _ = _run_cli(state_dir, "report", "rm", REPORT_ID_PORT)
  assert code == 0
  assert REPORT_ID_PORT in out

  # Dismissed report is evicted from active store while answers survive on republish.
  recheck_store = SqliteStore(state_dir / "state.sqlite3")
  assert recheck_store.get_report(REPORT_ID_PORT) is None
  recheck_store.close()

  code, out, _ = _run_cli(state_dir, "msg", "list", "--page", "1")
  assert code == 0
  assert MSG_ID_CLI in out

  code, out, _ = _run_cli(state_dir, "task", "mod", TASK_ID_BASE, "status", "finished")
  assert code == 0

  code, out_upcoming, _ = _run_cli(state_dir, "tasks")
  assert code == 0
  assert f"{TASK_ID_BASE} [" not in out_upcoming
  assert f"{TASK_ID_CLI} [" in out_upcoming

  code, out_finished, _ = _run_cli(state_dir, "tasks", "--finished", "--page", "1")
  assert code == 0
  assert f"{TASK_ID_BASE} [finished]" in out_finished
  assert f"{TASK_ID_CLI} [" not in out_finished

  code, out, _ = _run_cli(state_dir, "task", "rm", TASK_ID_CLI)
  assert code == 0
  assert TASK_ID_CLI in out


def test_websocket_upgrade_and_rpc() -> None:
  import base64
  import json
  import socket
  import threading

  from arena_steering.server import create_http_server

  store = SqliteStore(":memory:")
  app = SteeringApp(store)
  server = create_http_server(app, host="127.0.0.1", port=0)
  port = server.server_address[1]
  thread = threading.Thread(target=server.serve_forever, daemon=True)
  thread.start()
  try:
    with socket.create_connection(("127.0.0.1", port), timeout=5.0) as sock:
      key = base64.b64encode(b"0123456789abcdef").decode("ascii")
      req = (
        f"GET /api/ws HTTP/1.1\r\n"
        f"Host: 127.0.0.1:{port}\r\n"
        f"Upgrade: websocket\r\n"
        f"Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\n"
        f"Sec-WebSocket-Version: 13\r\n\r\n"
      )
      sock.sendall(req.encode("ascii"))
      resp = b""
      while b"\r\n\r\n" not in resp:
        resp += sock.recv(4096)
      header_part, leftover = resp.split(b"\r\n\r\n", 1)
      assert b"101 Switching Protocols" in header_part
      while len(leftover) < 2:
        leftover += sock.recv(4096)
      size = leftover[1] & 127
      while len(leftover) < 2 + size:
        leftover += sock.recv(4096)
      first_msg = json.loads(leftover[2 : 2 + size].decode("utf-8"))
      assert first_msg == {"type": "change"}

      rpc_payload = json.dumps({"id": "1", "method": "GET", "path": "/health"}).encode(
        "utf-8"
      )
      mask = b"\x01\x02\x03\x04"
      masked = bytes(b ^ mask[i % 4] for i, b in enumerate(rpc_payload))
      frame = bytes([0x81, 0x80 | len(rpc_payload)]) + mask + masked
      sock.sendall(frame)
      reply_buf = leftover[2 + size :]
      while len(reply_buf) < 2:
        reply_buf += sock.recv(4096)
      r_size = reply_buf[1] & 127
      offset = 2
      if r_size == 126:
        while len(reply_buf) < 4:
          reply_buf += sock.recv(4096)
        r_size = int.from_bytes(reply_buf[2:4], "big")
        offset = 4
      while len(reply_buf) < offset + r_size:
        reply_buf += sock.recv(4096)
      rpc_reply = json.loads(reply_buf[offset : offset + r_size].decode("utf-8"))
      assert rpc_reply["type"] == "response"
      assert rpc_reply["id"] == "1"
      assert rpc_reply["status"] == 200
      assert json.loads(rpc_reply["body"])["ok"] is True
  finally:
    server.shutdown()
    server.server_close()
    store.close()
