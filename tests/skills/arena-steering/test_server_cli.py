"""Tests for Arena Steering HTTP router (`server.py`) and `steer` CLI (`cli.py`)."""

from __future__ import annotations

import base64
import io
import json
from http import HTTPStatus
from pathlib import Path

import pytest
from arena_steering import __version__, cli
from arena_steering.cli import main as cli_main
from arena_steering.markdown import render_markdown
from arena_steering.server import (
  PASTE_ATTACHMENT_CHAR_THRESHOLD,
  PASTE_ATTACHMENT_LINE_THRESHOLD,
  SteeringApp,
)
from arena_steering.store import SqliteStore

MSG_ID_CLI = "a0b1c2"
ACK_MARKDOWN = "ack-token-verified"
SECOND_DETAIL_TOKEN = "detail-token-two"
REPORT_ID_PORT = "port-report"
TASK_ID_CLI = "cli-task"
TASK_ID_BASE = "base-task"


@pytest.fixture(autouse=True)
def _isolate_cli_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
  state_dir = tmp_path / "arena-state"
  monkeypatch.setattr(cli, "resolve_state_dir", lambda: state_dir)


def _run_cli(state_dir: Path, *args: str) -> tuple[int, str, str]:
  assert state_dir == cli.resolve_state_dir()
  out = io.StringIO()
  err = io.StringIO()
  code = cli_main(list(args), out=out, err=err)
  return code, out.getvalue(), err.getvalue()


def test_cli_version_flags() -> None:
  out = io.StringIO()
  code = cli_main(["--version"], out=out)
  assert code == 0
  assert out.getvalue().strip() == f"steer {__version__}"


def test_report_pin_cli_and_http_are_durable() -> None:
  state_dir = cli.resolve_state_dir()
  state_dir.mkdir(parents=True, exist_ok=True)
  store = SqliteStore(state_dir / "steering-v2.sqlite3")
  reports = cli.ReportService(store, store)
  reports.publish_report("pin-me", "Pin me", "# Pin me")
  store.close()

  code, _, error = _run_cli(state_dir, "report", "pin", "pin-me")
  assert code == 0, error
  store = SqliteStore(state_dir / "steering-v2.sqlite3")
  assert store.get_report("pin-me").pinned is True
  app = SteeringApp(store)
  status, result = app.dispatch("PATCH", "/reports/pin-me", {"pinned": False})
  assert status == HTTPStatus.OK and result["report"]["pinned"] is False
  status, _ = app.dispatch("PATCH", "/reports/pin-me", {"pinned": "false"})
  assert status == HTTPStatus.BAD_REQUEST
  store.close()

  code, _, error = _run_cli(state_dir, "report", "pin", "pin-me")
  assert code == 0, error
  code, _, error = _run_cli(state_dir, "report", "unpin", "pin-me")
  assert code == 0, error
  store = SqliteStore(state_dir / "steering-v2.sqlite3")
  assert store.get_report("pin-me").pinned is False
  store.close()


def test_cli_message_page_size(tmp_path: Path) -> None:
  state_dir = cli.resolve_state_dir()
  state_dir.mkdir(parents=True, exist_ok=True)
  store = SqliteStore(state_dir / "steering-v2.sqlite3")
  service = cli.MessageService(store, store, store)
  for index in range(12):
    service.send_message(f"message {index}", msg_id=f"{index:06x}")
  store.close()

  code, first, _ = _run_cli(state_dir, "msg", "list")
  assert code == 0 and len(first.splitlines()) == 5
  code, second, _ = _run_cli(state_dir, "msg", "list", "-p", "2")
  assert code == 0 and len(second.splitlines()) == 5
  assert set(first.splitlines()).isdisjoint(second.splitlines())
  for size, count in ((5, 5), (7, 7), (50, 12)):
    code, output, _ = _run_cli(state_dir, "msg", "list", "-s", str(size))
    assert code == 0 and len(output.splitlines()) == count
  for size in (4, 51):
    code, _, error = _run_cli(state_dir, "msg", "list", "-s", str(size))
    assert code != 0 and "between 5 and 50" in error


def test_http_message_pages_and_database_search(tmp_path: Path) -> None:
  store = SqliteStore(tmp_path / "search.sqlite3")
  app = SteeringApp(store)
  for index in range(43):
    body = "Old MATCH éLÉPHANT" if index == 0 else f"message {index}"
    app.messages.send_message(body, msg_id=f"{index:06x}", hidden=index == 1)
  first_status, first = app.dispatch("GET", "/messages?all=1&hidden=1&limit=2", None)
  assert first_status == HTTPStatus.OK
  assert first["total"] == 43 and len(first["messages"]) == 20 and first["has_more"]
  before = first["messages"][0]["id"]
  _, older = app.dispatch("GET", f"/messages?all=1&hidden=1&before={before}", None)
  assert len(older["messages"]) == 20 and older["has_more"]
  assert {m["id"] for m in first["messages"]}.isdisjoint(
    m["id"] for m in older["messages"]
  )
  _, search = app.dispatch("GET", "/messages?all=1&q=%C3%A9l%C3%A9phant", None)
  assert search["total"] == 1 and search["messages"][0]["id"] == "000000"
  _, hidden = app.dispatch("GET", "/messages?all=1&q=000001", None)
  assert hidden["total"] == 0
  _, hidden = app.dispatch("GET", "/messages?all=1&hidden=1&q=000001", None)
  assert hidden["total"] == 1
  status, _ = app.dispatch("GET", "/messages?all=1&before=ffffff", None)
  assert status == HTTPStatus.BAD_REQUEST
  store.close()


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
  old_revision = acked["message"]["replies_revision"]
  status, seen = app.dispatch(
    "POST", "/messages/12ab34/replies-seen", {"revision": old_revision}
  )
  assert status == int(HTTPStatus.OK) and seen["message"]["replies_seen"]
  app.dispatch("POST", "/messages/12ab34/ack", {"markdown": "Another reply."})
  status, stale = app.dispatch(
    "POST", "/messages/12ab34/replies-seen", {"revision": old_revision}
  )
  assert status == int(HTTPStatus.CONFLICT) and not stale["message"]["replies_seen"]

  status, _ = app.dispatch("POST", "/tasks", {"id": "empty-task", "title": "Empty"})
  assert status == int(HTTPStatus.BAD_REQUEST)

  status, t_created = app.dispatch(
    "POST",
    "/tasks",
    {
      "id": "build-router",
      "title": "Build HTTP router",
      "type": "code",
      "details": ["Build routes."],
    },
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
  status, _ = app.dispatch("PATCH", "/tasks/build-router", {"details": []})
  assert status == int(HTTPStatus.BAD_REQUEST)

  status, r_created = app.dispatch(
    "POST",
    "/reports",
    {
      "id": "router-spec",
      "title": "Router Spec",
      "body": (
        '<!-- question {"id": "we-should-bind-to-this-host", "label": "We should bind to this host"} -->\n'
        "We should bind to this host\n"
        '- (x) 0.0.0.0 <!-- option {"label": "0.0.0.0"} -->\n'
        '- ( ) 127.0.0.1 <!-- option {"label": "127.0.0.1"} -->\n'
      ),
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
  _, visible = app.dispatch("GET", "/messages?all=1")
  assert "cafe01" not in [item["id"] for item in visible["messages"]]
  _, hidden = app.dispatch("GET", "/messages?all=1&hidden=1")
  answer_message = next(item for item in hidden["messages"] if item["id"] == "cafe01")
  assert answer_message["hidden"] and answer_message["type"] == "report_answer"
  assert answer_message["answer_data"]["report_id"] == "router-spec"
  _, projected = app.dispatch("GET", "/reports/router-spec")
  assert projected["report"]["answers"][0]["id"] == "cafe01"
  status, _ = app.dispatch("POST", "/messages", {"id": "cafe01", "body": "Collision"})
  assert status == int(HTTPStatus.BAD_REQUEST)
  status, direct = app.dispatch(
    "POST", "/messages/cafe01/ack", {"markdown": "Direct reply"}
  )
  assert status == int(HTTPStatus.OK) and direct["answer"]["acks"] == ["Direct reply"]

  status, r_acked = app.dispatch(
    "POST",
    "/reports/router-spec/answers/cafe01/ack",
    {"markdown": "Confirmed 0.0.0.0."},
  )
  assert status == int(HTTPStatus.OK)
  assert r_acked["answer"]["status"] == "acked"
  _, projected = app.dispatch("GET", "/reports/router-spec")
  answer = projected["report"]["answers"][0]
  assert answer["ack"] == "Direct reply\n\nConfirmed 0.0.0.0."
  assert (
    "Direct reply" in answer["ack_html"] and "Confirmed 0.0.0.0." in answer["ack_html"]
  )

  status, r_ack_seen = app.dispatch("POST", "/reports/router-spec/ack-seen")
  assert status == int(HTTPStatus.OK)
  assert r_ack_seen["report"]["ack_seen"] is True

  status, deleted = app.dispatch("DELETE", "/tasks/build-router")
  assert status == int(HTTPStatus.OK)
  assert deleted["deleted"] == "build-router"
  store.close()


def test_state_changes_sync_same_second_messages_and_answers(tmp_path: Path) -> None:
  class FixedClock:
    def now_iso(self) -> str:
      return "2026-01-01T00:00:00Z"

  source = SqliteStore(tmp_path / "source.sqlite3")
  target = SqliteStore(tmp_path / "target.sqlite3")
  app = SteeringApp(source)
  app.messages._clock = FixedClock()
  app.reports._clock = FixedClock()
  app.dispatch("POST", "/messages", {"id": "aa1001", "body": "First"})
  _, snapshot = app.dispatch("GET", "/state/snapshot")
  target.merge_rows(snapshot)
  cursor = snapshot["state_version"]

  app.dispatch("POST", "/messages", {"id": "aa1002", "body": "Second"})
  app.dispatch("POST", "/messages/aa1001/ack", {"markdown": "Read"})
  body = (
    '<!-- question {"id":"choice","label":"Choice"} -->\n'
    "Choice\n"
    '- ( ) Yes <!-- option {"label":"Yes"} -->\n'
  )
  app.reports.publish_report("decision", "Decision", body)
  app.reports.submit_answer("decision", {"choice": "Yes"}, answer_id="aa1003")
  _, changes = app.dispatch("GET", "/state/changes?since=" + cursor)
  assert {row["id"] for row in changes["messages"]} == {"aa1001", "aa1002", "aa1003"}
  initial_message = snapshot["messages"][0]
  updated_message = next(row for row in changes["messages"] if row["id"] == "aa1001")
  assert updated_message["modified_at"] > initial_message["modified_at"]
  assert [row["id"] for row in changes["reports"]] == ["decision"]
  target.merge_rows(changes)
  assert target.get_message("aa1001").acks == ["Read"]
  assert target.get_report("decision").answers[0].id == "aa1003"

  app.dispatch("POST", "/messages/aa1003/ack", {"markdown": "Answer received"})
  _, answer_ack = app.dispatch(
    "GET", "/state/changes?since=" + changes["state_version"]
  )
  target.merge_rows(answer_ack)
  assert target.get_report("decision").answers[0].acks == ["Answer received"]
  _, quiet = app.dispatch("GET", "/state/changes?since=" + answer_ack["state_version"])
  assert quiet["messages"] == [] and quiet["reports"] == []
  source.close()
  target.close()


def test_state_syncs_same_second_task_and_report_updates(tmp_path: Path) -> None:
  class FixedClock:
    def now_iso(self) -> str:
      return "2026-01-01T00:00:00Z"

  source = SqliteStore(tmp_path / "task-source.sqlite3")
  target = SqliteStore(tmp_path / "task-target.sqlite3")
  app = SteeringApp(source)
  app.tasks._clock = FixedClock()
  app.reports._clock = FixedClock()
  app.tasks.create_task("work", "Work", details=["Review"])
  app.reports.publish_report("report", "Report", "# Report")
  _, snapshot = app.dispatch("GET", "/state/snapshot")
  target.merge_rows(snapshot)

  app.tasks.patch_task("work", {"title": "Updated"})
  app.reports.pin_report("report", True)
  _, changes = app.dispatch("GET", "/state/changes?since=" + snapshot["state_version"])
  target.merge_rows(changes)
  assert target.get_task("work").title == "Updated"
  assert target.get_report("report").pinned is True
  source.close()
  target.close()


def test_state_cursor_survives_clock_skew_older_imports_and_restart(
  tmp_path: Path,
) -> None:
  path = tmp_path / "clock-skew.sqlite3"
  store = SqliteStore(path)
  app = SteeringApp(store)
  store.merge_rows(
    {
      "messages": [
        {"id": "cc1001", "body": "Future", "modified_at": "2099-01-01T00:00:00Z"}
      ]
    }
  )
  _, snapshot = app.dispatch("GET", "/state/snapshot")
  store.merge_rows(
    {
      "messages": [
        {"id": "cc1002", "body": "Imported", "modified_at": "2020-01-01T00:00:00Z"}
      ]
    }
  )
  app.dispatch("POST", "/messages", {"id": "cc1003", "body": "Local"})
  _, changes = app.dispatch("GET", "/state/changes?since=" + snapshot["state_version"])
  assert {row["id"] for row in changes["messages"]} == {"cc1002", "cc1003"}
  cursor = changes["state_version"]
  store.close()

  store = SqliteStore(path)
  app = SteeringApp(store)
  _, quiet = app.dispatch("GET", "/state/changes?since=" + cursor)
  assert quiet["messages"] == []
  _, legacy_future = app.dispatch("GET", "/state/changes?since=9998-01-01T00:00:00Z")
  assert {row["id"] for row in legacy_future["messages"]} == {
    "cc1001",
    "cc1002",
    "cc1003",
  }
  app.dispatch("POST", "/messages", {"id": "cc1004", "body": "After restart"})
  _, after_restart = app.dispatch("GET", "/state/changes?since=" + cursor)
  assert [row["id"] for row in after_restart["messages"]] == ["cc1004"]
  store.close()


def test_legacy_state_cursor_resyncs_without_changing_old_rows(tmp_path: Path) -> None:
  import sqlite3

  path = tmp_path / "legacy.sqlite3"
  store = SqliteStore(path)
  store.merge_rows(
    {
      "messages": [
        {"id": "dd1001", "body": "Old", "modified_at": "2099-01-01T00:00:00Z"}
      ]
    }
  )
  before = store.export_rows()
  store.close()
  with sqlite3.connect(path) as connection:
    triggers = connection.execute(
      "SELECT name FROM sqlite_master WHERE type = 'trigger' AND name LIKE '%_state_%'"
    ).fetchall()
    for (name,) in triggers:
      connection.execute(f'DROP TRIGGER "{name}"')
    connection.execute("DROP TABLE state_row_versions")
    connection.execute("DROP TABLE state_clock")

  store = SqliteStore(path)
  app = SteeringApp(store)
  _, changes = app.dispatch("GET", "/state/changes?since=2099-01-01T00:00:00Z")
  assert changes["messages"] == before["messages"]
  assert store.export_rows() == before
  _, quiet = app.dispatch("GET", "/state/changes?since=" + changes["state_version"])
  assert quiet["messages"] == []
  store.close()


def test_state_merge_compares_timestamps_chronologically(tmp_path: Path) -> None:
  store = SqliteStore(tmp_path / "timestamp-merge.sqlite3")
  old = {"id": "ee1002", "body": "Old", "modified_at": "2030-01-01T00:00:00Z"}
  newer = {**old, "body": "New", "modified_at": "2030-01-01T00:00:00.000001Z"}
  equivalent = {
    **old,
    "body": "Equal",
    "modified_at": "2029-12-31T19:00:00.000001-05:00",
  }
  store.merge_rows({"messages": [old]})
  assert store.merge_rows({"messages": [newer]})["updated"] == ["ee1002"]
  assert store.merge_rows({"messages": [equivalent]})["skipped"] == ["ee1002"]
  assert store.get_message("ee1002").body == "New"
  store.close()


@pytest.mark.parametrize(
  "stamp",
  ["2030-01-01T00:00:00Z", "2030-01-01T00:00:00.5Z", "2030-01-01T05:30:00+05:30"],
)
def test_same_time_row_update_sorts_after_legacy_stamp(
  tmp_path: Path, stamp: str
) -> None:
  from datetime import datetime

  store = SqliteStore(tmp_path / "legacy-merge.sqlite3")
  store.merge_rows(
    {"messages": [{"id": "ee1003", "body": "Original", "modified_at": stamp}]}
  )
  first = store.append_message_ack("ee1003", "First", stamp)
  second = store.append_message_ack("ee1003", "Second", stamp)
  assert first.modified_at > stamp
  assert second.modified_at > first.modified_at
  assert datetime.fromisoformat(second.modified_at) > datetime.fromisoformat(
    first.modified_at
  )
  store.close()


def test_state_cursor_rolls_back_with_the_write(tmp_path: Path) -> None:
  store = SqliteStore(tmp_path / "rollback.sqlite3")
  app = SteeringApp(store)
  _, before = app.dispatch("GET", "/state/snapshot")
  with pytest.raises(RuntimeError, match="rollback"), store.transaction():
    app.messages.send_message("Pending", msg_id="ee1001")
    raise RuntimeError("rollback")
  _, after = app.dispatch("GET", "/state/changes?since=" + before["state_version"])
  assert after["state_version"] == before["state_version"]
  assert after["messages"] == []
  store.close()


def test_state_changes_include_concurrent_database_writers(tmp_path: Path) -> None:
  from concurrent.futures import ThreadPoolExecutor

  path = tmp_path / "writers.sqlite3"
  first, second = SqliteStore(path), SqliteStore(path)
  apps = [SteeringApp(first), SteeringApp(second)]
  _, snapshot = apps[0].dispatch("GET", "/state/snapshot")

  def write_batch(index: int) -> None:
    for number in range(10):
      msg_id = f"{index + 1:02x}aa{number:02x}"
      apps[index].messages.send_message("Concurrent", msg_id=msg_id)

  with ThreadPoolExecutor(max_workers=2) as pool:
    list(pool.map(write_batch, range(2)))
  _, changes = apps[0].dispatch(
    "GET", "/state/changes?since=" + snapshot["state_version"]
  )
  assert {row["id"] for row in changes["messages"]} == {
    f"{index + 1:02x}aa{number:02x}" for index in range(2) for number in range(10)
  }
  first.close()
  second.close()


def test_state_snapshot_cursor_covers_interleaved_sqlite_writes(
  tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  from threading import Event, Thread

  path = tmp_path / "concurrent.sqlite3"
  reader = SqliteStore(path)
  writer = SqliteStore(path)
  app = SteeringApp(reader)
  other = SteeringApp(writer)
  app.dispatch("POST", "/messages", {"id": "bb1001", "body": "Before"})
  exported, attempted, written = Event(), Event(), Event()
  original_export = reader.export_rows

  def export_then_pause(since: str | None = None) -> dict:
    rows = original_export(since)
    exported.set()
    assert attempted.wait(2)
    written.wait(0.5)
    return rows

  def write_during_export() -> None:
    assert exported.wait(2)
    attempted.set()
    other.dispatch("POST", "/messages", {"id": "bb1002", "body": "During"})
    written.set()

  monkeypatch.setattr(reader, "export_rows", export_then_pause)
  thread = Thread(target=write_during_export)
  thread.start()
  _, snapshot = app.dispatch("GET", "/state/snapshot")
  thread.join(timeout=5)
  assert not thread.is_alive() and written.is_set()
  monkeypatch.setattr(reader, "export_rows", original_export)
  _, changes = app.dispatch("GET", "/state/changes?since=" + snapshot["state_version"])
  received = {row["id"] for row in snapshot["messages"] + changes["messages"]}
  assert received == {"bb1001", "bb1002"}
  reader.close()
  writer.close()


def test_state_endpoints_snapshot_changes_merge_and_assets(tmp_path: Path) -> None:
  store = SqliteStore(tmp_path / "state-sync.sqlite3")
  app = SteeringApp(store)
  app.dispatch("POST", "/messages", {"id": "aa11bb", "body": "Snapshot me."})

  status, snapshot = app.dispatch("GET", "/state/snapshot")
  assert status == int(HTTPStatus.OK)
  assert snapshot["schema"] == 1
  assert [row["id"] for row in snapshot["messages"]] == ["aa11bb"]
  stamp = snapshot["state_version"]
  assert stamp

  status, quiet = app.dispatch("GET", "/state/changes?since=" + stamp)
  assert status == int(HTTPStatus.OK)
  assert quiet["messages"] == []

  incoming = {
    "schema": 1,
    "source": "test container",
    "messages": [
      {
        "id": "cc22dd",
        "body": "Merged from elsewhere.",
        "modified_at": "2099-01-01T00:00:00Z",
      },
      {
        "id": "aa11bb",
        "body": "Older copy.",
        "modified_at": "1999-01-01T00:00:00Z",
      },
    ],
  }
  status, merged = app.dispatch("POST", "/state/merge", incoming)
  assert status == int(HTTPStatus.OK)
  assert merged["added"] == ["cc22dd"]
  assert merged["skipped"] == ["aa11bb"]
  assert store.get_meta("state_restore_notice")

  status, later = app.dispatch("GET", "/state/changes?since=" + stamp)
  assert [row["id"] for row in later["messages"]] == ["cc22dd"]

  status, _bad = app.dispatch("POST", "/state/merge", {"schema": 99, "messages": []})
  assert status >= int(HTTPStatus.BAD_REQUEST)

  uploads = app._uploads_dir()
  (uploads / "note.txt").write_bytes(b"hello")
  status, listed = app.dispatch("GET", "/state/assets")
  assert status == int(HTTPStatus.OK)
  entry = next(item for item in listed["assets"] if item["path"] == "uploads/note.txt")
  assert entry["size"] == 5

  payload = {
    "path": "uploads/copy.txt",
    "sha256": entry["sha256"],
    "content": base64.b64encode(b"hello").decode("ascii"),
  }
  status, pushed = app.dispatch("POST", "/state/assets", payload)
  assert status == int(HTTPStatus.OK) and pushed["stored"] is True
  status, again = app.dispatch("POST", "/state/assets", payload)
  assert again["stored"] is False


def test_router_create_message_accepts_parent_ids() -> None:
  store = SqliteStore(":memory:")
  app = SteeringApp(store)

  status, _created = app.dispatch(
    "POST", "/messages", {"id": "aa1001", "body": "Parent note"}
  )
  assert status == int(HTTPStatus.CREATED)

  status, created = app.dispatch(
    "POST",
    "/messages",
    {"id": "bb2002", "body": "Child note", "parent_ids": ["aa1001"]},
  )
  assert status == int(HTTPStatus.CREATED)
  assert created["message"]["parent_ids"] == ["aa1001"]

  status, single = app.dispatch("GET", "/messages/bb2002")
  assert status == int(HTTPStatus.OK)
  assert single["message"]["parent_ids"] == ["aa1001"]
  store.close()


def test_report_acked_events_fire_once_per_ack() -> None:
  store = SqliteStore(":memory:")
  app = SteeringApp(store)
  app.reports.publish_report(
    "live-ack",
    "Live Ack",
    (
      '<!-- question {"id": "we-should-push-this-event", "label": "We should push this event"} -->\n'
      "We should push this event\n"
      '- (x) report.acked <!-- option {"label": "report.acked"} -->\n'
      '- ( ) Poll <!-- option {"label": "Poll"} -->\n'
    ),
  )
  app.reports.submit_answer(
    "live-ack", {"we-should-push-this-event": "report.acked"}, answer_id="cafe02"
  )
  snapshot = app.report_ack_snapshot()
  events, snapshot = app.report_acked_events(snapshot)
  assert events == []

  app.reports.ack_answer("live-ack", "cafe02", "Pushed live.")
  events, snapshot = app.report_acked_events(snapshot)
  assert len(events) == 1
  assert events[0]["type"] == "report.acked"
  assert events[0]["report"]["id"] == "live-ack"
  assert events[0]["report"]["ack_seen"] is False
  assert events[0]["report"]["answers"][-1]["status"] == "acked"

  events, snapshot = app.report_acked_events(snapshot)
  assert events == []

  app.reports.ack_answer("live-ack", "cafe02", "Second reply.")
  events, _snapshot = app.report_acked_events(snapshot)
  assert len(events) == 1
  store.close()


def test_resolve_asset_serves_report_gifs_and_images(tmp_path: Path) -> None:
  state_dir = tmp_path / "arena-state"
  reports_dir = state_dir / "reports"
  reports_dir.mkdir(parents=True)
  gif_bytes = (
    b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff"
    b"!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
  )
  png_bytes = b"\x89PNG\r\n\x1a\n"
  (reports_dir / "scroll-fade.gif").write_bytes(gif_bytes)
  (reports_dir / "board.png").write_bytes(png_bytes)

  store = SqliteStore(state_dir / "steering-v2.sqlite3")
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
  bundled = app.assets_dir / "mermaid.min.js"
  assert mermaid_asset[0] == bundled.read_bytes()
  assert app.resolve_asset("/static/assets/mermaid.LICENSE") is not None
  empty_assets = tmp_path / "empty-assets"
  empty_assets.mkdir()
  standalone_app = SteeringApp(store, assets_dir=empty_assets)
  assert standalone_app.resolve_asset("/static/assets/mermaid.min.js") is None
  assert standalone_app.resolve_asset("/mermaid.min.js") is None
  store.close()


def test_resolve_asset_serves_static_contract_paths(tmp_path: Path) -> None:
  state_dir = tmp_path / "arena-state"
  reports_dir = state_dir / "reports"
  uploads_dir = state_dir / "uploads"
  assets_dir = tmp_path / "assets"
  (assets_dir / "css").mkdir(parents=True)
  (assets_dir / "js").mkdir(parents=True)
  reports_dir.mkdir(parents=True)
  uploads_dir.mkdir(parents=True)
  (assets_dir / "index.html").write_text(
    "<title>Arena Steering</title>", encoding="utf-8"
  )
  (assets_dir / "css" / "site.css").write_text("body { color: red; }", encoding="utf-8")
  (assets_dir / "js" / "app.js").write_text("export {};", encoding="utf-8")
  png_bytes = b"\x89PNG\r\n\x1a\n"
  (reports_dir / "board.png").write_bytes(png_bytes)
  (uploads_dir / "shot.png").write_bytes(png_bytes)

  store = SqliteStore(state_dir / "steering-v2.sqlite3")
  app = SteeringApp(store, assets_dir=assets_dir)
  app.reports.publish_report("static-spec", "Static Spec", "# Static Spec\n")

  assert app.resolve_asset("/static/assets/css/site.css") == (
    b"body { color: red; }",
    "text/css; charset=utf-8",
  )
  assert app.resolve_asset("/static/assets/js/app.js") == (
    b"export {};",
    "application/javascript; charset=utf-8",
  )
  assert app.resolve_asset("/static/reports/board.png") == (png_bytes, "image/png")
  assert app.resolve_asset("/static/reports/static-spec.md") == (
    b"# Static Spec\n",
    "text/markdown; charset=utf-8",
  )
  assert app.resolve_asset("/static/uploads/shot.png") == (png_bytes, "image/png")
  assert app.resolve_asset("/static/assets/../secret.css") is None
  assert app.resolve_asset("/static/reports/../state.sqlite3") is None
  assert app.resolve_asset("/static/uploads/../reports/board.png") is None
  store.close()


def test_http_static_paths_do_not_collide_with_report_routes(tmp_path: Path) -> None:
  import http.client
  import threading

  from arena_steering.server import create_http_server

  state_dir = tmp_path / "arena-state"
  reports_dir = state_dir / "reports"
  reports_dir.mkdir(parents=True)
  png_bytes = b"\x89PNG\r\n\x1a\n"
  (reports_dir / "board.png").write_bytes(png_bytes)

  store = SqliteStore(state_dir / "steering-v2.sqlite3")
  app = SteeringApp(store)
  app.reports.publish_report("static-spec", "Static Spec", "# Static Spec\n")
  server = create_http_server(app, host="127.0.0.1", port=0)
  port = server.server_address[1]
  thread = threading.Thread(target=server.serve_forever, daemon=True)
  thread.start()
  try:

    def get(path: str) -> tuple[int, str | None, bytes]:
      conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5.0)
      try:
        conn.request("GET", path)
        response = conn.getresponse()
        return response.status, response.getheader("Content-Type"), response.read()
      finally:
        conn.close()

    status, content_type, body = get("/reports/board.png")
    assert status == int(HTTPStatus.OK)
    assert content_type == "image/png"
    assert body == png_bytes

    status, content_type, body = get("/static/reports/static-spec.md")
    assert status == int(HTTPStatus.OK)
    assert content_type == "text/markdown; charset=utf-8"
    assert body == b"# Static Spec\n"

    status, content_type, body = get("/static/assets/style.css")
    assert status == int(HTTPStatus.OK)
    assert content_type == "text/css; charset=utf-8"
    assert body

    status, content_type, body = get("/reports/static-spec")
    assert status == int(HTTPStatus.OK)
    assert content_type == "application/json; charset=utf-8"
    assert b"static-spec" in body
  finally:
    server.shutdown()
    server.server_close()
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
  state_dir = tmp_path / "arena-state"
  store = SqliteStore(state_dir / "steering-v2.sqlite3")
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

  code, out, _ = _run_cli(state_dir, "msg", MSG_ID_CLI)
  assert code == 0
  assert ACK_MARKDOWN in out
  with pytest.raises(SystemExit) as invalid_args:
    _run_cli(state_dir, "msg", "show", MSG_ID_CLI)
  assert invalid_args.value.code == 2

  code, _, err = _run_cli(state_dir, "task", "new", "empty-task", "Empty")
  expected_error = "at least one detail"
  assert code != 0 and expected_error in err
  code, out, _ = _run_cli(
    state_dir, "task", "new", TASK_ID_BASE, "Base task", "-d", "Build the base."
  )
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
    (
      "# Sample\n"
      "\n"
      '<!-- question {"id": "we-should-use-this-port", "label": "We should use this port"} -->\n'
      "We should use this port\n"
      '- (x) 8000 <!-- option {"label": "8000"} -->\n'
      '- ( ) 9000 <!-- option {"label": "9000"} -->\n'
    ),
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
  recheck_store = SqliteStore(state_dir / "steering-v2.sqlite3")
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


def test_upload_endpoints_store_files_and_paste_attachments(tmp_path: Path) -> None:
  import base64

  state_dir = tmp_path / "arena-state"
  state_dir.mkdir()
  store = SqliteStore(state_dir / "steering-v2.sqlite3")
  app = SteeringApp(store)

  payload = base64.b64encode(b"hello upload").decode("ascii")
  status, uploaded = app.dispatch(
    "POST",
    "/api/uploads",
    {"name": "../notes.txt", "content_base64": payload},
  )
  assert status == int(HTTPStatus.CREATED)
  attachment = uploaded["attachment"]
  assert attachment["name"] == "notes.txt"
  assert attachment["size_bytes"] == len(b"hello upload")
  assert attachment["url"].startswith("/static/uploads/")
  stored = Path(attachment["path"])
  assert stored.parent == state_dir / "uploads"
  assert stored.read_bytes() == b"hello upload"
  assert app.resolve_asset(attachment["url"].lstrip("/")) == (
    b"hello upload",
    "text/plain; charset=utf-8",
  )

  long_paste = "x" * (PASTE_ATTACHMENT_CHAR_THRESHOLD + 1)
  status, created = app.dispatch(
    "POST",
    "/api/messages/with-file",
    {"body": "See attached paste.", "pasted_text": long_paste},
  )
  assert status == int(HTTPStatus.CREATED)
  msg = created["message"]
  assert msg["body"] == "See attached paste."
  assert len(msg["attachments"]) == 1
  paste_attachment = msg["attachments"][0]
  assert paste_attachment["name"] == "pasted-text.txt"
  assert Path(paste_attachment["path"]).read_text(encoding="utf-8") == long_paste

  many_lines = "\n".join(
    f"line {idx}" for idx in range(PASTE_ATTACHMENT_LINE_THRESHOLD)
  )
  status, created = app.dispatch(
    "POST",
    "/api/messages/with-file",
    {"pasted_text": many_lines},
  )
  assert status == int(HTTPStatus.CREATED)
  assert created["message"]["body"] == "Pasted text attached."
  assert len(created["message"]["attachments"]) == 1

  status, created = app.dispatch(
    "POST",
    "/api/messages/with-file",
    {
      "file": {"name": "spec.md", "content_base64": payload},
      "parent_ids": [msg["id"]],
    },
  )
  assert status == int(HTTPStatus.CREATED)
  assert created["message"]["parent_ids"] == [msg["id"]]
  assert created["message"]["attachments"][0]["name"] == "spec.md"
  store.close()


def test_http_multipart_upload_and_message_with_file(tmp_path: Path) -> None:
  import http.client
  import json
  import threading

  from arena_steering.server import create_http_server

  state_dir = tmp_path / "arena-state"
  state_dir.mkdir()
  store = SqliteStore(state_dir / "steering-v2.sqlite3")
  app = SteeringApp(store)
  server = create_http_server(app, host="127.0.0.1", port=0)
  port = server.server_address[1]
  thread = threading.Thread(target=server.serve_forever, daemon=True)
  thread.start()

  def post_multipart(path: str, fields: dict[str, str], file_name: str, data: bytes):
    boundary = "arena-test-boundary"
    chunks: list[bytes] = []
    for key, value in fields.items():
      chunks.append(f"--{boundary}\r\n".encode())
      chunks.append(f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode())
      chunks.append(value.encode("utf-8") + b"\r\n")
    chunks.append(f"--{boundary}\r\n".encode())
    chunks.append(
      (
        'Content-Disposition: form-data; name="file"; '
        f'filename="{file_name}"\r\nContent-Type: text/plain\r\n\r\n'
      ).encode()
    )
    chunks.append(data + b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode())
    body = b"".join(chunks)
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5.0)
    try:
      conn.request(
        "POST",
        path,
        body=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
      )
      response = conn.getresponse()
      return response.status, json.loads(response.read().decode("utf-8"))
    finally:
      conn.close()

  try:
    status, uploaded = post_multipart("/api/uploads", {}, "multi.txt", b"multi body")
    assert status == int(HTTPStatus.CREATED)
    assert uploaded["attachment"]["name"] == "multi.txt"
    assert Path(uploaded["attachment"]["path"]).read_bytes() == b"multi body"

    status, created = post_multipart(
      "/api/messages/with-file",
      {"body": "Multipart note", "blocking": "false"},
      "note.txt",
      b"attached note",
    )
    assert status == int(HTTPStatus.CREATED)
    assert created["message"]["body"] == "Multipart note"
    assert created["message"]["blocking"] is False
    assert created["message"]["attachments"][0]["name"] == "note.txt"
  finally:
    server.shutdown()
    server.server_close()
    store.close()


def test_cli_rename_task_unlink_and_timezone_endpoint(tmp_path: Path) -> None:
  state_dir = tmp_path / "arena-state"
  state_dir.mkdir()

  code, out, _ = _run_cli(
    state_dir,
    "task",
    "new",
    "base-task",
    "Base task",
    "-T",
    "code",
    "-d",
    "Build the base.",
  )
  assert code == 0
  assert "base-task" in out
  code, out, _ = _run_cli(
    state_dir,
    "task",
    "new",
    "child-task",
    "Child task",
    "-d",
    "Build the child.",
    "-T",
    "code",
    "-k",
    "base-task",
    "-r",
    "spec-report",
  )
  assert code == 0
  assert "child-task" in out

  code, out, _ = _run_cli(state_dir, "rename", "base-task", "root-task")
  assert code == 0
  assert "root-task" in out
  code, out, _ = _run_cli(state_dir, "task", "child-task")
  assert code == 0
  assert "root-task" in out
  assert "base-task" not in out
  code, _, err = _run_cli(state_dir, "task", "base-task")
  assert code == 1
  expected_error = "Unknown task ID: base-task"
  assert expected_error in err

  code, out, _ = _run_cli(
    state_dir, "task", "unlink", "child-task", "report", "spec-report"
  )
  assert code == 0
  assert "spec-report" not in out
  code, out, _ = _run_cli(state_dir, "task", "unlink", "child-task", "root-task")
  assert code == 0
  assert "root-task" not in out

  store = SqliteStore(state_dir / "steering-v2.sqlite3")
  app = SteeringApp(store)
  status, payload = app.dispatch("POST", "/api/timezone", {"timezone": "Asia/Manila"})
  assert status == int(HTTPStatus.OK)
  assert payload == {"timezone": "Asia/Manila"}
  status, health = app.dispatch("GET", "/health")
  assert status == int(HTTPStatus.OK)
  assert health["timezone"] == "Asia/Manila"
  status, payload = app.dispatch("POST", "/api/timezone", {"timezone": "Not/AZone"})
  assert status == int(HTTPStatus.BAD_REQUEST)
  store.close()

  code, _, err = _run_cli(state_dir, "init", "--tz", "Asia/Manila")
  assert code == 1
  assert "--tz" in err or "init" in err


def test_cli_pr_update_and_job_log_use_gh_seam(tmp_path: Path, monkeypatch) -> None:
  import subprocess

  import arena_steering.cli as cli_module

  state_dir = tmp_path / "arena-state"
  state_dir.mkdir()
  body_file = tmp_path / "pr-body.md"
  body_file.write_text("## Summary\n\nBody text.\n", encoding="utf-8")
  calls: list[list[str]] = []

  def fake_run(args, **_kwargs):
    calls.append(list(args))
    if args[:3] == ["gh", "pr", "view"]:
      return subprocess.CompletedProcess(
        args,
        0,
        stdout='{"title":"New title","body":"## Summary\\n\\nBody text.\\n"}',
        stderr="",
      )
    if args[:3] == ["gh", "run", "view"] and "--json" in args:
      return subprocess.CompletedProcess(
        args, 0, stdout="https://github.com/o/r/actions/runs/1\n", stderr=""
      )
    if args[:2] == ["gh", "api"]:
      return subprocess.CompletedProcess(
        args, 0, stdout="https://github.com/o/r/actions/runs/1/job/9\n", stderr=""
      )
    if args[:3] == ["gh", "run", "view"]:
      return subprocess.CompletedProcess(args, 0, stdout="job log text\n", stderr="")
    return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

  monkeypatch.setattr(cli_module.subprocess, "run", fake_run)

  code, out, _ = _run_cli(
    state_dir,
    "pr-update",
    "-n",
    "122",
    "-t",
    "New title",
    "-f",
    str(body_file),
  )
  assert code == 0
  assert "Updated PR #122" in out
  assert calls[0][:3] == ["gh", "pr", "edit"]
  assert "--body-file" in calls[0]
  assert calls[1][:3] == ["gh", "pr", "view"]

  code, out, _ = _run_cli(state_dir, "job-log", "-r", "41000725677")
  assert code == 0
  assert out.strip() == "https://github.com/o/r/actions/runs/1"
  assert calls[-1] == [
    "gh",
    "run",
    "view",
    "41000725677",
    "--json",
    "url",
    "--jq",
    ".url",
  ]

  code, out, _ = _run_cli(state_dir, "job-log", "-j", "123877772372")
  assert code == 0
  assert out.strip() == "https://github.com/o/r/actions/runs/1/job/9"
  assert calls[-1] == [
    "gh",
    "api",
    "repos/{owner}/{repo}/actions/jobs/123877772372",
    "--jq",
    ".html_url",
  ]


def test_cli_job_log_falls_back_to_text(tmp_path: Path, monkeypatch) -> None:
  import subprocess

  import arena_steering.cli as cli_module

  state_dir = tmp_path / "arena-state"
  state_dir.mkdir()

  def fake_run(args, **_kwargs):
    if args[:3] == ["gh", "run", "view"] and "--json" in args:
      return subprocess.CompletedProcess(args, 1, stdout="", stderr="HTTP 404\n")
    if args[:3] == ["gh", "run", "view"]:
      return subprocess.CompletedProcess(args, 0, stdout="line one\n", stderr="")
    return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

  monkeypatch.setattr(cli_module.subprocess, "run", fake_run)

  code, out, _ = _run_cli(state_dir, "job-log", "-r", "77")
  assert code == 0
  assert "line one" in out
  assert "no URL" in out and "404" in out


def test_cli_worktree_lifecycle_uses_native_git(tmp_path: Path, monkeypatch) -> None:
  import subprocess

  repo = tmp_path / "repo"
  repo.mkdir()
  state_dir = tmp_path / "arena-state"
  state_dir.mkdir()

  def git(*args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)

  git("init", "-b", "main")
  git("config", "user.email", "steer@example.test")
  git("config", "user.name", "Steer Test")
  (repo / "README.md").write_text("readme\n", encoding="utf-8")
  git("add", "README.md")
  git("commit", "-m", "init")
  monkeypatch.chdir(repo)

  code, out, _ = _run_cli(
    state_dir, "worktree", "add", "feat-one", "-b", "feat/feat-one"
  )
  assert code == 0
  assert "feat-one" in out
  worktree_path = repo / ".worktrees" / "feat-one"
  assert (worktree_path / "README.md").is_file()

  code, out, _ = _run_cli(state_dir, "worktree", "list")
  assert code == 0
  assert str(worktree_path) in out
  assert "branch refs/heads/feat/feat-one" in out

  code, out, _ = _run_cli(state_dir, "worktree", "remove", "feat-one")
  assert code == 0
  assert "feat-one" in out
  assert not worktree_path.exists()


def _wait_for_run(state_dir: Path, name: str) -> str:
  import time

  for _ in range(50):
    code, out, _ = _run_cli(state_dir, "run", "logs", name)
    assert code == 0
    if "run " + name + " exit " in out:
      return out
    time.sleep(0.1)
  raise AssertionError(f"run {name} did not finish")


def test_cli_run_start_logs_and_after_chaining(tmp_path: Path) -> None:
  state_dir = tmp_path / "arena-state"
  state_dir.mkdir()

  code, out, _ = _run_cli(
    state_dir, "run", "start", "first", "--", "sh", "-c", "echo first-done"
  )
  assert code == 0
  expected_start = "Started run first"
  assert expected_start in out
  assert (_wait_for_run(state_dir, "first")).count("first-done") == 1

  code, out, _ = _run_cli(
    state_dir,
    "run",
    "start",
    "second",
    "--after",
    "first",
    "--",
    "sh",
    "-c",
    "echo second-done",
  )
  assert code == 0
  second_log = _wait_for_run(state_dir, "second")
  assert "second-done" in second_log
  assert "exit 0" in second_log

  code, _, _ = _run_cli(state_dir, "run", "start", "bad", "--", "sh", "-c", "exit 3")
  assert code == 0
  assert "exit 3" in _wait_for_run(state_dir, "bad")

  code, _, _ = _run_cli(
    state_dir,
    "run",
    "start",
    "never",
    "--after",
    "bad",
    "--",
    "sh",
    "-c",
    "echo should-not-run",
  )
  assert code == 0
  never_log = _wait_for_run(state_dir, "never")
  expected_marker = "should-not" + "-run"
  assert expected_marker not in never_log
  assert "exit 125" in never_log


def test_cli_run_pr_checks_uses_detached_gh_watch(tmp_path: Path, monkeypatch) -> None:
  import arena_steering.cli as cli_module

  state_dir = tmp_path / "arena-state"
  state_dir.mkdir()
  spawned: list[list[str]] = []

  class FakeProcess:
    pid = 4242

  def fake_popen(args, **_kwargs):
    spawned.append(list(args))
    return FakeProcess()

  monkeypatch.setattr(cli_module.subprocess, "Popen", fake_popen)

  code, out, _ = _run_cli(state_dir, "run", "pr-checks", "-n", "122")
  assert code == 0
  assert "Started run pr-checks" in out
  assert spawned
  assert "gh pr checks 122 --watch" in " ".join(spawned[0])
  assert (state_dir / "runs" / "pr-checks.json").is_file()


def test_run_rejects_missing_dependency_and_active_duplicate(tmp_path: Path) -> None:
  state_dir = tmp_path / "arena-state"
  state_dir.mkdir()
  code, _, error = _run_cli(
    state_dir, "run", "start", "child", "--after", "missing", "--", "true"
  )
  assert code != 0
  assert "missing" in error
  assert not (state_dir / "runs" / "child.json").exists()

  code, _, _ = _run_cli(
    state_dir, "run", "start", "active", "--", "sh", "-c", "sleep 2"
  )
  assert code == 0
  code, _, error = _run_cli(state_dir, "run", "start", "active", "--", "true")
  assert code != 0
  assert "active" in error


def test_run_records_shell_builtin_exit(tmp_path: Path) -> None:
  state_dir = tmp_path / "arena-state"
  state_dir.mkdir()
  code, _, _ = _run_cli(state_dir, "run", "start", "builtin", "--", "exit", "7")
  assert code == 0
  assert "exit 7" in _wait_for_run(state_dir, "builtin")


def test_run_concurrent_starts_have_one_winner(tmp_path: Path) -> None:
  from concurrent.futures import ThreadPoolExecutor

  state_dir = tmp_path / "arena-state"
  state_dir.mkdir()

  def start() -> int:
    return _run_cli(state_dir, "run", "start", "race", "--", "sleep", "2")[0]

  with ThreadPoolExecutor(max_workers=2) as pool:
    results = list(pool.map(lambda _: start(), range(2)))
  assert results.count(0) == 1
  assert sum(result != 0 for result in results) == 1


def test_fixed_state_location_preserves_v1_database(tmp_path: Path) -> None:
  import os
  import subprocess
  import sys

  state_dir = tmp_path / "arena-state"
  state_dir.mkdir()
  legacy = state_dir / "state.sqlite3"
  legacy.write_bytes(b"legacy state must not be opened")
  override = tmp_path / "override"
  entrypoint = (
    Path(__file__).resolve().parents[3] / "skills/arena-steering/scripts/steer"
  )
  env = {**os.environ, "ARENA_STATE_DIR": str(override)}
  result = subprocess.run(
    [sys.executable, str(entrypoint), "tasks"],
    cwd=tmp_path,
    env=env,
    capture_output=True,
    text=True,
    check=False,
  )
  assert result.returncode == 0, result.stderr
  assert legacy.read_bytes() == b"legacy state must not be opened"
  assert (state_dir / "steering-v2.sqlite3").is_file()
  assert not override.exists()
  rejected = subprocess.run(
    [sys.executable, str(entrypoint), "--state-dir", str(override), "tasks"],
    cwd=tmp_path,
    env=env,
    capture_output=True,
    text=True,
    check=False,
  )
  assert rejected.returncode != 0
  assert not override.exists()


def test_paste_attachment_threshold_boundaries() -> None:
  assert not SteeringApp._paste_needs_attachment("x" * 1500)
  assert SteeringApp._paste_needs_attachment("x" * 1501)
  assert not SteeringApp._paste_needs_attachment("😀" * 1500)
  assert SteeringApp._paste_needs_attachment("😀" * 1501)
  assert not SteeringApp._paste_needs_attachment("\n".join(["x"] * 14))
  assert SteeringApp._paste_needs_attachment("\n".join(["x"] * 15))
  assert SteeringApp._paste_needs_attachment("x\n" * 14)


def test_message_request_id_is_atomic_and_survives_restart(tmp_path: Path) -> None:
  from concurrent.futures import ThreadPoolExecutor
  from threading import Barrier

  path = tmp_path / "requests.sqlite3"
  stores = [SqliteStore(path), SqliteStore(path)]
  apps = [SteeringApp(store) for store in stores]
  barrier = Barrier(2)
  body = {"body": "Retry safely", "request_id": "request-1"}

  def send(app: SteeringApp) -> tuple[int, dict]:
    barrier.wait()
    return app.dispatch("POST", "/messages", body)

  with ThreadPoolExecutor(max_workers=2) as pool:
    results = list(pool.map(send, apps))
  assert all(status == HTTPStatus.CREATED for status, _ in results)
  ids = {payload["message"]["id"] for _, payload in results}
  assert len(ids) == 1
  assert len(stores[0].list_messages()) == 1
  for store in stores:
    store.close()

  store = SqliteStore(path)
  app = SteeringApp(store)
  status, result = app.dispatch("POST", "/messages", body)
  assert status == HTTPStatus.CREATED and result["message"]["id"] in ids
  status, _ = app.dispatch(
    "POST", "/messages", {"body": "Different content", "request_id": "request-1"}
  )
  assert status == HTTPStatus.BAD_REQUEST
  status, _ = app.dispatch("POST", "/messages", {"body": "Bad", "request_id": "bad id"})
  assert status == HTTPStatus.BAD_REQUEST
  app.dispatch("POST", "/messages", {"body": "Retry safely"})
  assert len(store.list_messages()) == 2
  store.close()


def test_attachment_message_retry_uses_original_message(tmp_path: Path) -> None:
  store = SqliteStore(tmp_path / "attachment-requests.sqlite3")
  app = SteeringApp(store)
  payload = {
    "body": "Attachment retry",
    "request_id": "attachment-request",
    "attachments": [{"name": "note.txt", "path": "uploads/note.txt", "size_bytes": 3}],
  }
  first_status, first = app.dispatch("POST", "/messages/with-file", payload)
  second_status, second = app.dispatch("POST", "/messages/with-file", payload)
  assert first_status == second_status == HTTPStatus.CREATED
  assert first["message"]["id"] == second["message"]["id"]
  assert len(store.list_messages()) == 1
  status, _ = app.dispatch("POST", "/messages", payload)
  assert status == HTTPStatus.BAD_REQUEST
  store.close()


def test_cli_lists_persisted_answer_details(tmp_path: Path) -> None:
  from arena_steering.services import ReportService, TaskService

  state_dir = cli.resolve_state_dir()
  store, _, tasks, reports = cli.open_services(state_dir)
  assert isinstance(tasks, TaskService) and isinstance(reports, ReportService)
  reports.publish_report(
    "decision",
    "Decision",
    (
      '<!-- question {"id": "select", "label": "Select?"} -->\n'
      "Select?\n"
      '- ( ) Yes <!-- option {"label": "Yes"} -->\n'
      '- ( ) No <!-- option {"label": "No"} -->\n'
    ),
  )
  tasks.create_task("work", "Work", details=["Review"], report_ids=["decision"])
  answer = reports.submit_answer("decision", {"select": "Yes"}, answer_id="aa5511")
  reports.ack_answer("decision", answer.id, "Read")
  reports.remove_report("decision")
  store.close()
  for args in [("tasks",), ("task", "work")]:
    code, out, err = _run_cli(state_dir, *args)
    assert code == 0, err
    assert "Select?: Yes" in out
    assert answer.id not in out


def test_ack_task_rolls_back_both_on_failure(
  tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  state_dir = cli.resolve_state_dir()
  store, messages, _, _ = cli.open_services(state_dir)
  messages.send_message("Need action", msg_id="ab7701")
  store.close()
  original = SqliteStore.append_message_ack

  def fail_after_task(self, msg_id, reply, now):
    assert self.get_task("new-task") is not None
    raise ValueError("Simulated acknowledgement failure")

  monkeypatch.setattr(SqliteStore, "append_message_ack", fail_after_task)
  code, out, _ = _run_cli(
    state_dir,
    "ack",
    "ab7701",
    "Received",
    "-i",
    "new-task",
    "-t",
    "Task",
    "-d",
    "Do work",
  )
  assert code != 0 and "ok ab7701" not in out
  monkeypatch.setattr(SqliteStore, "append_message_ack", original)
  store, messages, _, _ = cli.open_services(state_dir)
  assert messages.get_message("ab7701").acks == []
  assert store.get_task("new-task") is None
  store.close()


def test_ack_answer_creates_task_with_report_link(tmp_path: Path) -> None:
  state_dir = cli.resolve_state_dir()
  store, _, _, reports = cli.open_services(state_dir)
  reports.publish_report(
    "choice",
    "Choice",
    (
      '<!-- question {"id": "select", "label": "Select?"} -->\n'
      "Select?\n"
      '- ( ) Yes <!-- option {"label": "Yes"} -->\n'
      '- ( ) No <!-- option {"label": "No"} -->\n'
    ),
  )
  answer = reports.submit_answer("choice", {"select": "Yes"}, answer_id="ab7702")
  store.close()
  code, out, err = _run_cli(
    state_dir,
    "ack",
    answer.id,
    "Received",
    "-i",
    "new-task",
    "-t",
    "Task",
    "-d",
    "Do work",
  )
  assert code == 0, err
  assert answer.id in out
  store, _, tasks, reports = cli.open_services(state_dir)
  task = tasks.get_task("new-task")[0]
  assert task.msg_ids == [] and task.report_ids == ["choice"]
  assert task.details == ["Do work", "Select?: Yes"]
  assert "answer_snapshots" not in task.to_dict()
  assert reports.get_report("choice").answers[0].status == "acked"
  store.close()


def _seed_report_removal_batch(state_dir: Path) -> str:
  body = (
    '<!-- question {"id":"choice", "label":"Choice"} -->\n'
    "Choose one\n"
    '- ( ) Yes <!-- option {"label":"Yes"} -->\n'
    '- ( ) No <!-- option {"label":"No"} -->\n'
  )
  store, _, tasks, reports = cli.open_services(state_dir)
  reports.publish_report("ready", "Ready", body)
  reports.publish_report("protected", "Protected", body)
  reports.publish_report("empty", "Empty", "# Empty")
  tasks.create_task(
    "linked-work",
    "Linked work",
    details=["Review reports"],
    report_ids=["ready", "protected", "empty"],
  )
  reports.submit_answer("ready", {"choice": "Yes"}, answer_id="bc1001")
  reports.ack_answer("ready", "bc1001", "Read")
  reports.submit_answer("protected", {"choice": "No"}, answer_id="bc1002")
  store.close()
  return body


def test_cli_report_rm_batches_ids_and_preserves_answers(tmp_path: Path) -> None:
  state_dir = cli.resolve_state_dir()
  body = _seed_report_removal_batch(state_dir)
  code, out, err = _run_cli(state_dir, "report", "rm", "ready", "empty")
  assert code == 0, err
  assert "ready, empty" in out
  store, _, tasks, reports = cli.open_services(state_dir)
  assert store.get_report("ready") is None
  assert store.get_report("empty") is None
  assert store.get_report("protected") is not None
  assert tasks.get_task("linked-work")[0].report_ids == ["protected"]
  restored = reports.publish_report("ready", "Ready", body)
  assert restored.answers[-1].id == "bc1001"
  assert restored.answers[-1].acks == ["Read"]
  store.close()


@pytest.mark.parametrize("bad_id", ["protected", "missing"])
def test_cli_report_rm_batch_failure_rolls_back_all(
  tmp_path: Path, bad_id: str
) -> None:
  state_dir = cli.resolve_state_dir()
  _seed_report_removal_batch(state_dir)
  code, out, _ = _run_cli(state_dir, "report", "rm", "ready", bad_id, "empty")
  assert code != 0
  assert "Dismissed" not in out
  store, _, tasks, _ = cli.open_services(state_dir)
  assert all(
    store.get_report(report_id) is not None
    for report_id in ("ready", "protected", "empty")
  )
  assert tasks.get_task("linked-work")[0].report_ids == ["ready", "protected", "empty"]
  store.close()


def test_cli_report_rm_deduplicates_ids_and_keeps_stale_separate(
  tmp_path: Path,
) -> None:
  state_dir = cli.resolve_state_dir()
  _seed_report_removal_batch(state_dir)
  code, _, _ = _run_cli(state_dir, "report", "rm", "ready", "--stale")
  assert code != 0
  store, _, _, _ = cli.open_services(state_dir)
  assert store.get_report("ready") is not None
  store.close()
  code, out, err = _run_cli(state_dir, "report", "rm", "ready", "ready")
  assert code == 0, err
  assert out.count("ready") == 1
  code, _, _ = _run_cli(state_dir, "report", "rm")
  assert code != 0


def test_cli_report_rm_stale_keeps_unacknowledged_answers(tmp_path: Path) -> None:
  state_dir = cli.resolve_state_dir()
  _seed_report_removal_batch(state_dir)
  store, _, tasks, reports = cli.open_services(state_dir)
  tasks.mod_scalar("linked-work", "status", "finished")
  reports.pin_report("empty", True)
  store.close()
  code, out, err = _run_cli(state_dir, "report", "rm", "--stale")
  assert code == 0, err
  assert "ready" in out and "protected" in out and "empty" not in out
  store, messages, tasks, _ = cli.open_services(state_dir)
  assert store.get_report("ready") is None
  assert store.get_report("protected") is None
  assert store.get_report("empty").pinned is True
  assert tasks.get_task("linked-work")[0].report_ids == ["empty"]
  assert messages.pending_ids() == ["bc1002"]
  store.close()
  code, out, err = _run_cli(state_dir, "read")
  assert code == 0, err
  assert "bc1002" in out and "Protected" in out
  code, _, err = _run_cli(state_dir, "ack", "bc1002", "Noted")
  assert code == 0, err


def _seed_ack_batch(state_dir: Path) -> None:
  store, messages, _, reports = cli.open_services(state_dir)
  messages.send_message("First", msg_id="ab1001")
  messages.send_message("Second", msg_id="ab1002", hidden=True)
  reports.publish_report(
    "batch-choice",
    "Batch Choice",
    (
      '<!-- question {"id":"choice", "label":"Choice"} -->\n'
      "Choose one\n"
      '- ( ) Yes <!-- option {"label":"Yes"} -->\n'
      '- ( ) No <!-- option {"label":"No"} -->\n'
    ),
  )
  reports.submit_answer("batch-choice", {"choice": "Yes"}, answer_id="ab1003")
  store.close()


def test_cli_ack_batches_messages_and_report_answers(tmp_path: Path) -> None:
  state_dir = cli.resolve_state_dir()
  _seed_ack_batch(state_dir)
  code, out, err = _run_cli(
    state_dir, "ack", "ab1001", "ab1002", "ab1003", "One shared reply"
  )
  assert code == 0, err
  assert out == "ok ab1001 ab1002 ab1003\n"
  store, _, _, reports = cli.open_services(state_dir)
  assert store.get_message("ab1001").acks == ["One shared reply"]
  assert store.get_message("ab1002").acks == ["One shared reply"]
  assert reports.get_report("batch-choice").answers[-1].acks == ["One shared reply"]
  store.close()


@pytest.mark.parametrize("bad_id", ["abffff", "invalid-id"])
def test_cli_ack_batch_failure_rolls_back_every_target(
  tmp_path: Path, bad_id: str
) -> None:
  state_dir = cli.resolve_state_dir()
  _seed_ack_batch(state_dir)
  code, out, _ = _run_cli(
    state_dir, "ack", "ab1001", "ab1003", bad_id, "One shared reply"
  )
  assert code != 0
  assert "ok " not in out
  store, _, _, reports = cli.open_services(state_dir)
  assert store.get_message("ab1001").acks == []
  assert reports.get_report("batch-choice").answers[-1].acks == []
  store.close()


def test_cli_ack_without_id_still_requires_one_pending_item(tmp_path: Path) -> None:
  state_dir = cli.resolve_state_dir()
  store, messages, _, _ = cli.open_services(state_dir)
  messages.send_message("Only one", msg_id="ab1011")
  store.close()
  code, out, err = _run_cli(state_dir, "ack", "Received")
  assert code == 0, err
  assert out == "ok ab1011\n"
  store, messages, _, _ = cli.open_services(state_dir)
  assert store.get_message("ab1011").acks == ["Received"]
  messages.send_message("First pending", msg_id="ab1012")
  messages.send_message("Second pending", msg_id="ab1013")
  store.close()
  code, _, _ = _run_cli(state_dir, "ack", "Not sent")
  assert code != 0
  store, _, _, _ = cli.open_services(state_dir)
  assert store.get_message("ab1012").acks == []
  assert store.get_message("ab1013").acks == []
  store.close()


def test_cli_ack_batch_rejects_task_creation_without_changes(tmp_path: Path) -> None:
  state_dir = cli.resolve_state_dir()
  _seed_ack_batch(state_dir)
  code, _, err = _run_cli(
    state_dir,
    "ack",
    "ab1001",
    "ab1003",
    "One shared reply",
    "-i",
    "batch-task",
    "-t",
    "Batch task",
    "-d",
    "Do the work",
  )
  assert code != 0 and "one" in err.lower()
  store, _, _, reports = cli.open_services(state_dir)
  assert store.get_task("batch-task") is None
  assert store.get_message("ab1001").acks == []
  assert reports.get_report("batch-choice").answers[-1].acks == []
  store.close()


def test_concurrent_ack_task_creation_preserves_both(tmp_path: Path) -> None:
  from concurrent.futures import ThreadPoolExecutor
  from threading import Barrier

  state_dir = cli.resolve_state_dir()
  store, messages, _, _ = cli.open_services(state_dir)
  messages.send_message("First", msg_id="ab7703")
  messages.send_message("Second", msg_id="ab7704")
  store.close()
  start = Barrier(2)

  def create(pair):
    start.wait()
    msg_id, task_id = pair
    return _run_cli(
      state_dir, "ack", msg_id, "Received", "-i", task_id, "-t", "Task", "-d", "Do work"
    )

  with ThreadPoolExecutor(max_workers=2) as pool:
    results = list(
      pool.map(create, [("ab7703", "first-task"), ("ab7704", "second-task")])
    )
  assert all(code == 0 for code, _, _ in results), results
  store, messages, _, _ = cli.open_services(state_dir)
  assert {task.id for task in store.list_tasks()} == {"first-task", "second-task"}
  assert messages.get_message("ab7703").acks == ["Received"]
  assert messages.get_message("ab7704").acks == ["Received"]
  store.close()


def test_message_ack_route_returns_report_answer(tmp_path: Path) -> None:
  store = SqliteStore(tmp_path / "answer-ack.sqlite3")
  app = SteeringApp(store)
  app.reports.publish_report(
    "decision",
    "Decision",
    (
      '<!-- question {"id": "choice", "label": "Choose?"} -->\n'
      "Choose?\n"
      '- ( ) Yes <!-- option {"label": "Yes"} -->\n'
      '- ( ) No <!-- option {"label": "No"} -->\n'
    ),
  )
  answer = app.reports.submit_answer("decision", {"choice": "Yes"}, answer_id="ab9911")
  status, payload = app.dispatch(
    "POST", f"/messages/{answer.id}/ack", {"markdown": "Read"}
  )
  assert status == HTTPStatus.OK
  assert payload["answer"]["id"] == answer.id
  assert payload["answer"]["acks"] == ["Read"]
  assert app.reports.get_report("decision").answers[0].status == "acked"
  store.close()


def test_gate_links_block_only_while_run_is_active() -> None:
  state_dir = cli.resolve_state_dir()
  state_dir.mkdir(parents=True)
  runs = state_dir / "runs"
  runs.mkdir()
  marker = runs / "verify.exit"
  (runs / "verify.json").write_text(json.dumps({"exit_path": str(marker)}))
  store = SqliteStore(state_dir / "steering-v2.sqlite3")
  app = SteeringApp(store)
  status, created = app.dispatch(
    "POST",
    "/tasks",
    {
      "id": "gate-task",
      "title": "Gate task",
      "details": ["Check it"],
      "gate_names": ["verify"],
    },
  )
  assert status == HTTPStatus.CREATED and created["task"]["blocked"]
  status, patched = app.dispatch("PATCH", "/tasks/gate-task", {"scope": "code"})
  assert status == HTTPStatus.OK and patched["task"]["links"]["gate_names"] == [
    "verify"
  ]
  code, output, _ = _run_cli(state_dir, "task", "gate-task")
  assert code == 0 and "Gates: verify" in output and "blocked" in output.lower()
  for result in ("1", "0"):
    marker.write_text(result)
    assert not app.dispatch("GET", "/tasks/gate-task")[1]["task"]["blocked"]
  store.close()
  reopened = SqliteStore(state_dir / "steering-v2.sqlite3")
  assert reopened.get_task("gate-task").gate_names == ["verify"]
  reopened.close()
  assert (
    _run_cli(state_dir, "task", "mod", "gate-task", "links", "rm", "gate", "verify")[0]
    == 0
  )


def test_run_start_rolls_back_link_on_launch_failure(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  state_dir = cli.resolve_state_dir()
  assert (
    _run_cli(state_dir, "task", "new", "gate-task", "Gate task", "-d", "Check it")[0]
    == 0
  )

  def fail_start(*_args: object, **_kwargs: object) -> int:
    raise ValueError("launch failed")

  monkeypatch.setattr(cli, "_start_detached_run", fail_start)
  assert (
    _run_cli(state_dir, "run", "start", "-t", "gate-task", "verify", "--", "true")[0]
    != 0
  )
  store, _, tasks, _ = cli.open_services(state_dir)
  assert tasks.get_task("gate-task")[0].gate_names == []
  store.close()


@pytest.mark.parametrize("exit_code", [0, 7])
def test_linked_run_blocks_until_verdict(tmp_path: Path, exit_code: int) -> None:
  import sys
  import time

  state_dir = cli.resolve_state_dir()
  release = tmp_path / "release"
  assert (
    _run_cli(state_dir, "task", "new", "gate-task", "Gate task", "-d", "Check it")[0]
    == 0
  )
  command = (
    "import pathlib,time,sys; p=pathlib.Path(sys.argv[1]); "
    "exec('while not p.exists():\\n time.sleep(0.02)'); "
    "print('gate verdict'); sys.exit(int(sys.argv[2]))"
  )
  code, _, err = _run_cli(
    state_dir,
    "run",
    "start",
    "-t",
    "gate-task",
    "verify",
    "--",
    sys.executable,
    "-c",
    command,
    str(release),
    str(exit_code),
  )
  assert code == 0, err
  try:
    store, _, tasks, _ = cli.open_services(state_dir)
    assert tasks.get_task("gate-task")[1]
    store.close()
  finally:
    release.touch()
  record = json.loads((state_dir / "runs" / "verify.json").read_text())
  marker = Path(record["exit_path"])
  deadline = time.monotonic() + 10
  while not marker.exists() and time.monotonic() < deadline:
    time.sleep(0.02)
  assert marker.read_text().strip() == str(exit_code)
  store, _, tasks, _ = cli.open_services(state_dir)
  assert not tasks.get_task("gate-task")[1]
  store.close()
  code, output, _ = _run_cli(state_dir, "run", "logs", "verify")
  assert code == 0 and "gate verdict" in output and f"exit {exit_code}" in output


def test_gate_links_survive_concurrent_task_edits() -> None:
  from concurrent.futures import ThreadPoolExecutor
  from threading import Barrier

  state_dir = cli.resolve_state_dir()
  assert (
    _run_cli(state_dir, "task", "new", "gate-task", "Gate task", "-d", "Check it")[0]
    == 0
  )
  barrier = Barrier(2)

  def update(gate: bool) -> None:
    store, _, tasks, _ = cli.open_services(state_dir)
    barrier.wait()
    if gate:
      tasks.mod_links_add("gate-task", "verify", link_type="gate")
    else:
      tasks.mod_scalar("gate-task", "scope", "code")
    store.close()

  with ThreadPoolExecutor(max_workers=2) as pool:
    list(pool.map(update, [True, False]))
  store, _, tasks, _ = cli.open_services(state_dir)
  task, _ = tasks.get_task("gate-task")
  assert task.gate_names == ["verify"] and task.scope == "code"
  store.close()


def test_browser_write_replay_survives_restart(tmp_path: Path) -> None:
  db_path = tmp_path / "retry.sqlite3"
  store = SqliteStore(db_path)
  app = SteeringApp(store)
  app.reports.publish_report(
    "retry-report",
    "Retry",
    (
      '<!-- question {"id": "choice", "label": "Choose?"} -->\n'
      "Choose?\n"
      '- ( ) Yes <!-- option {"label": "Yes"} -->\n'
      '- ( ) No <!-- option {"label": "No"} -->\n'
    ),
  )
  request = {"_request_id": "action-001", "values": {"choice": "Yes"}}
  first = app.dispatch("POST", "/reports/retry-report/answers", request)
  assert first[0] == HTTPStatus.CREATED
  store.close()
  store = SqliteStore(db_path)
  app = SteeringApp(store)
  assert app.dispatch("POST", "/reports/retry-report/answers", request) == first
  assert len(app.reports.get_report("retry-report").answers) == 1
  answer_messages = [
    item for item in store.list_messages() if item.type == "report_answer"
  ]
  assert [item.id for item in answer_messages] == [first[1]["answer"]["id"]]
  changed = {"_request_id": "action-001", "values": {"choice": "No"}}
  assert (
    app.dispatch("POST", "/reports/retry-report/answers", changed)[0]
    == HTTPStatus.BAD_REQUEST
  )
  assert len(app.reports.get_report("retry-report").answers) == 1
  store.close()


def test_browser_write_replay_concurrent(tmp_path: Path) -> None:
  from concurrent.futures import ThreadPoolExecutor
  from threading import Barrier

  db_path = tmp_path / "retry.sqlite3"
  store = SqliteStore(db_path)
  app = SteeringApp(store)
  app.reports.publish_report(
    "retry-report",
    "Retry",
    (
      '<!-- question {"id": "choice", "label": "Choose?"} -->\n'
      "Choose?\n"
      '- ( ) Yes <!-- option {"label": "Yes"} -->\n'
      '- ( ) No <!-- option {"label": "No"} -->\n'
    ),
  )
  store.close()
  barrier = Barrier(2)

  def send() -> tuple[int, dict]:
    store = SqliteStore(db_path)
    app = SteeringApp(store)
    barrier.wait()
    result = app.dispatch(
      "POST",
      "/reports/retry-report/answers",
      {
        "_request_id": "action-001",
        "values": {"choice": "Yes"},
      },
    )
    store.close()
    return result

  with ThreadPoolExecutor(max_workers=2) as pool:
    first, second = list(pool.map(lambda _: send(), range(2)))
  assert first == second and first[0] == HTTPStatus.CREATED
  store = SqliteStore(db_path)
  assert len(SteeringApp(store).reports.get_report("retry-report").answers) == 1
  store.close()


def test_browser_upload_replay_and_orphan_cleanup(tmp_path: Path) -> None:
  import hashlib

  db_path = tmp_path / "retry.sqlite3"
  store = SqliteStore(db_path)
  app = SteeringApp(store)
  request = {
    "_request_id": "upload-001",
    "file": {"name": "sample.txt", "text": "hello"},
  }
  first = app.dispatch("POST", "/uploads", request)
  assert first[0] == HTTPStatus.CREATED
  upload_path = Path(first[1]["attachment"]["path"])
  assert upload_path.read_text() == "hello"
  assert app.dispatch("POST", "/uploads", request) == first
  assert len(list(upload_path.parent.iterdir())) == 1
  stale_id = hashlib.sha256(b"abandoned").hexdigest()
  orphan = upload_path.parent / f"request-{stale_id}-0-sample.txt"
  orphan.write_text("incomplete")
  store.close()
  store = SqliteStore(db_path)
  app = SteeringApp(store)
  assert not orphan.exists()
  assert upload_path.exists()
  assert app.dispatch("POST", "/uploads", request) == first
  long_name = "a" * 190 + ".txt"
  status, long_upload = app.dispatch(
    "POST",
    "/uploads",
    {
      "_request_id": "long-upload",
      "file": {"name": long_name, "text": "long name"},
    },
  )
  assert status == HTTPStatus.CREATED
  assert Path(long_upload["attachment"]["path"]).read_text() == "long name"
  store.close()


def test_annotated_report_submission_and_trusted_html(tmp_path: Path) -> None:
  store = SqliteStore(tmp_path / "report-contract.sqlite3")
  app = SteeringApp(store)
  body = (
    '<mark data-example="yes">trusted</mark> ==plain==\n\n'
    '<!-- question {"id":"decision","label":"Decision"} -->\n'
    "Which path?\n\n"
    '- ( ) A <!-- option {"label":"Use A"} -->\n'
    '- ( ) B <!-- option {"label":"Use B"} -->\n'
  )
  status, result = app.dispatch(
    "POST", "/reports", {"id": "new-contract", "title": "Contract", "body": body}
  )
  assert status == HTTPStatus.CREATED
  report = result["report"]
  assert report["fields"][0]["question"] == "Which path?"
  assert report["fields"][0]["label"] == "Decision"
  markup = "".join(block.get("html", "") for block in report["blocks"])
  assert '<mark data-example="yes">trusted</mark>' in markup
  assert "==plain==" in markup
  status, answer = app.dispatch(
    "POST", "/reports/new-contract/answers", {"values": {"decision": "A"}}
  )
  assert status == HTTPStatus.CREATED
  assert answer["answer"]["values"]["decision"] == "Use A"
  assert answer["answer"]["field_labels"]["decision"] == "Decision"
  status, custom = app.dispatch(
    "POST",
    "/reports/new-contract/answers",
    {"values": {"decision": {"selected": "Something else...", "custom": "Use C"}}},
  )
  assert status == HTTPStatus.CREATED
  assert custom["answer"]["values"]["decision"] == "Use C"
  store.close()


def test_annotated_report_rejects_bad_metadata_and_preserves_code_fences(
  tmp_path: Path,
) -> None:
  store = SqliteStore(tmp_path / "report-validation.sqlite3")
  app = SteeringApp(store)
  legacy = "Question?\n- ( ) Old\n- ( ) Other\n"
  status, _ = app.dispatch(
    "POST", "/reports", {"id": "legacy-new", "title": "Legacy", "body": legacy}
  )
  assert status == HTTPStatus.BAD_REQUEST
  mixed = (
    '<!-- question {"id":"choice","label":"Choice"} -->\nQuestion?\n'
    '- ( ) A <!-- option {"label":"A"} -->\n'
    '- [ ] B <!-- option {"label":"B"} -->\n'
  )
  status, _ = app.dispatch(
    "POST", "/reports", {"id": "mixed", "title": "Mixed", "body": mixed}
  )
  assert status == HTTPStatus.BAD_REQUEST
  text = "```diff\n+ ~~literal~~\n```\n\n<mark>Marked</mark> ==plain=="
  status, result = app.dispatch(
    "POST", "/reports", {"id": "code", "title": "Code", "body": text}
  )
  assert status == HTTPStatus.CREATED and result["report"]["fields"] == []
  store.close()


def test_report_marker_override_and_verification_failure(
  tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  store = SqliteStore(tmp_path / "report-marker.sqlite3")
  app = SteeringApp(store)
  body = "Safe ~~struck~~ and `~~ ignored ~~`.\n\n~~ unparsed ~~"
  request = {"id": "marker", "title": "Marker", "body": body}
  status, result = app.dispatch("POST", "/reports", request)
  assert status == HTTPStatus.BAD_REQUEST and "3" in result["error"]
  status, result = app.dispatch(
    "POST", "/reports", {**request, "allow_unparsed_markers": True}
  )
  assert status == HTTPStatus.CREATED
  status, _ = app.dispatch(
    "POST",
    "/reports",
    {**request, "id": "bad-override", "allow_unparsed_markers": "false"},
  )
  assert status == HTTPStatus.BAD_REQUEST
  monkeypatch.setattr(
    app, "_handle_get_report", lambda *_: (HTTPStatus.OK, {"report": {}})
  )
  status, result = app.dispatch(
    "POST", "/reports", {"id": "verification", "title": "Verify", "body": "text"}
  )
  assert status == HTTPStatus.INTERNAL_SERVER_ERROR
  assert "verification failed" in result["error"]
  assert store.get_report("verification") is not None
  store.close()


def test_annotated_checkbox_labels_and_legacy_saved_report(tmp_path: Path) -> None:
  from arena_steering.markdown_fields import parse_report_markdown
  from arena_steering.models import Report

  db = tmp_path / "old-report.sqlite3"
  store = SqliteStore(db)
  legacy = "Choice? {#choice}\n- ( ) Yes\n- ( ) No\n"
  _, fields = parse_report_markdown(legacy)
  store.save_report(Report(id="old", title="Old", body=legacy, fields=fields))
  app = SteeringApp(store)
  status, read = app.dispatch("GET", "/reports/old", None)
  assert status == HTTPStatus.OK and read["report"]["fields"][0]["options"] == [
    "Yes",
    "No",
  ]
  body = (
    '<!-- question {"id":"features","label":"Features"} -->\n'
    "Which features?\n"
    '- [ ] A <!-- option {"label":"Use A"} -->\n'
    '- [ ] B <!-- option {"label":"Use B"} -->\n'
  )
  status, _ = app.dispatch(
    "POST", "/reports", {"id": "features", "title": "Features", "body": body}
  )
  assert status == HTTPStatus.CREATED
  status, result = app.dispatch(
    "POST",
    "/reports/features/answers",
    {"values": {"features": {"selected": ["A", "B"], "custom": "Use C"}}},
  )
  assert status == HTTPStatus.CREATED
  assert result["answer"]["values"]["features"] == ["Use A", "Use B", "Use C"]
  store.close()
  store = SqliteStore(db)
  assert store.get_report("features").answers[-1].values["features"] == [
    "Use A",
    "Use B",
    "Use C",
  ]
  store.close()


def test_cli_removes_answer_detail_without_unlinking_report(tmp_path: Path) -> None:
  state_dir = cli.resolve_state_dir()
  store, _, tasks, reports = cli.open_services(state_dir)
  reports.publish_report(
    "decision",
    "Decision",
    (
      '<!-- question {"id": "select", "label": "Select?"} -->\n'
      "Select?\n"
      '- ( ) Yes <!-- option {"label": "Yes"} -->\n'
      '- ( ) No <!-- option {"label": "No"} -->\n'
    ),
  )
  tasks.create_task("work", "Work", details=["Review"], report_ids=["decision"])
  answer = reports.submit_answer("decision", {"select": "Yes"}, answer_id="ab8801")
  reports.ack_answer("decision", answer.id, "Read")
  store.close()

  code, out, err = _run_cli(state_dir, "task", "mod", "work", "deets", "rm", "2")
  assert code == 0, err
  assert "Select?: Yes" not in out

  code, out, _ = _run_cli(state_dir, "task", "work")
  assert code == 0 and "Select?: Yes" not in out

  store, _, tasks, reports = cli.open_services(state_dir)
  task = tasks.get_task("work")[0]
  assert task.details == ["Review"] and task.report_ids == ["decision"]
  assert [item.id for item in reports.get_report("decision").answers] == [answer.id]
  store.close()

  code, _, err = _run_cli(state_dir, "task", "unlink", answer.id)
  assert code == 1 and "Usage" in err


def test_cli_gate_blocks_until_the_inbox_is_acked() -> None:
  state_dir = cli.resolve_state_dir()
  state_dir.mkdir(parents=True, exist_ok=True)
  store = SqliteStore(state_dir / "steering-v2.sqlite3")
  service = cli.MessageService(store, store, store)
  service.send_message("gate me", msg_id="ab12cd")
  store.close()

  code, out, _ = _run_cli(state_dir, "gate", "-l", "git push origin main")
  assert code == 1
  assert "BASH BLOCKED" in out
  assert "ab12cd" in out
  assert "origin" in out

  _run_cli(state_dir, "ack", "ab12cd", "acked")

  code, out, _ = _run_cli(state_dir, "gate")
  assert code == 0 and out == ""


def test_cli_gate_names_a_push_block() -> None:
  state_dir = cli.resolve_state_dir()
  state_dir.mkdir(parents=True, exist_ok=True)
  store = SqliteStore(state_dir / "steering-v2.sqlite3")
  service = cli.MessageService(store, store, store)
  service.send_message("gate me", msg_id="ab12ce")
  store.close()

  code, out, _ = _run_cli(state_dir, "gate", "--push")
  assert code == 1
  assert "PUSH BLOCKED" in out
  assert "Pending: ab12ce" in out


def test_cli_skills_lists_repo_and_installed_skills(
  tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  root = tmp_path / "repo"
  (root / "skills" / "alpha-skill").mkdir(parents=True)
  (root / "skills" / "alpha-skill" / "SKILL.md").write_text(
    "---\nname: alpha-skill\ndescription: Alpha description.\n---\n\n# Alpha\n",
    encoding="utf-8",
  )
  (root / ".agents" / "skills" / "beta-skill").mkdir(parents=True)
  (root / ".agents" / "skills" / "beta-skill" / "SKILL.md").write_text(
    "---\nname: beta-skill\ndescription: Beta description.\n---\n", encoding="utf-8"
  )
  monkeypatch.setattr(cli, "_repo_root", lambda: root)

  code, out, _ = _run_cli(cli.resolve_state_dir(), "skills")
  assert code == 0
  assert "alpha-skill [repo]" in out and "Alpha description." in out
  assert "beta-skill [installed]" in out and "Beta description." in out

  code, out, _ = _run_cli(cli.resolve_state_dir(), "skills", "--json")
  assert code == 0
  entries = json.loads(out)
  assert [entry["name"] for entry in entries] == ["alpha-skill", "beta-skill"]
  assert all(
    set(entry) == {"name", "source", "path", "description"} for entry in entries
  )


def test_cli_worktree_collect_prints_the_patch(
  tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  import subprocess

  repo = tmp_path / "repo"
  repo.mkdir()
  (repo / "note.txt").write_text("one\n", encoding="utf-8")
  commits = (
    ["init"],
    ["add", "note.txt"],
    ["-c", "user.email=t@example.com", "-c", "user.name=T", "commit", "-m", "init"],
  )
  for args in commits:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)
  monkeypatch.chdir(repo)

  code, out, _ = _run_cli(cli.resolve_state_dir(), "worktree", "add", "probe")
  assert code == 0
  assert "probe" in out

  worktree = repo / ".worktrees" / "probe"
  (worktree / "note.txt").write_text("one\ntwo\n", encoding="utf-8")
  (worktree / "fresh.txt").write_text("new file\n", encoding="utf-8")

  code, out, _ = _run_cli(cli.resolve_state_dir(), "worktree", "collect", "probe")
  assert code == 0
  assert "+two" in out
  assert "Untracked" in out
  assert "fresh.txt" in out

  code, _, err = _run_cli(cli.resolve_state_dir(), "worktree", "collect", "missing")
  assert code == 1
  assert "missing" in err


def test_serve_binds_a_fixed_host_on_the_v1_port() -> None:
  """Serve keeps one host and defaults to v1's port."""
  assert cli.BIND_HOST == "0.0.0.0"
  assert cli.SERVE_PORT == 8000
  with pytest.raises(SystemExit):
    cli.main(["serve", "--host", "127.0.0.1"], out=io.StringIO(), err=io.StringIO())
