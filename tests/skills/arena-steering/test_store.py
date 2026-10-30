"""Unit tests for Arena Steering models, ports, and SQLite store."""

from __future__ import annotations

from pathlib import Path

import pytest
from arena_steering import __version__
from arena_steering.models import (
  Attachment,
  Message,
  Report,
  ReportAnswer,
  ReportField,
  Task,
  kebab_slug,
)
from arena_steering.ports import SecretsHexIdGenerator, UtcClock
from arena_steering.store import SqliteStore

EXPECTED_INITIAL_VERSION = "2.0.0"


def test_package_exposes_semver_version() -> None:
  assert __version__ == EXPECTED_INITIAL_VERSION


def test_message_strict_hex_id_and_status_ladder() -> None:
  msg = Message(
    id="a1b2c3",
    body="Check inbox contract",
    hidden=False,
    blocking=True,
    attachments=[Attachment(name="spec.md", path="/tmp/spec.md", size_bytes=42)],
    parent_ids=["beef01", "cafe02", "beef01"],
    status="sent",
    acks=["Initial ack"],
    modified_at="2026-10-29T06:00:00Z",
  )
  assert msg.parent_ids == ["beef01", "cafe02"]
  assert msg.requires_ack is True
  assert msg.is_unread is True
  round_trip = Message.from_dict(msg.to_dict())
  assert round_trip == msg

  with pytest.raises(ValueError, match="6 lowercase hex"):
    Message(id="abc12", body="Too short")

  with pytest.raises(ValueError, match="6 lowercase hex"):
    Message(id="A1B2C3", body="Uppercase hex rejected")

  with pytest.raises(ValueError, match="6 lowercase hex"):
    Message(id="a1b2c3", body="Bad parent", parent_ids=["nope"])

  with pytest.raises(ValueError, match="cannot reply to itself"):
    Message(id="a1b2c3", body="Self parent", parent_ids=["a1b2c3"])


def test_task_validation_and_detail_limit() -> None:
  task = Task(
    id="core-models",
    title="Build models and store",
    type="code",
    status="upcoming",
    scope="skills/arena-steering/",
    details=["Define models.py and store.py."],
    links={
      "msg_ids": ["a1b2c3", "a1b2c3"],
      "report_ids": ["steering-spec"],
      "task_ids": ["prep-task"],
    },
    modified_at="2026-10-29T06:00:00Z",
  )
  assert task.msg_ids == ["a1b2c3"]
  assert task.links == {
    "msg_ids": ["a1b2c3"],
    "report_ids": ["steering-spec"],
    "task_ids": ["prep-task"],
    "gate_names": [],
  }
  assert task.to_dict()["links"] == {
    "msg_ids": ["a1b2c3"],
    "report_ids": ["steering-spec"],
    "task_ids": ["prep-task"],
    "gate_names": [],
  }
  assert Task.from_dict(task.to_dict()) == task

  with pytest.raises(ValueError, match="120 characters"):
    Task(id="bad-detail", title="Too long", details=["x" * 121])

  with pytest.raises(ValueError, match="depend on itself"):
    Task(id="self-dep", title="Cycle", links={"task_ids": ["self-dep"]})


def test_report_field_auto_kebab_id_and_choice_rules() -> None:
  field = ReportField(
    label="We should use this mode?",
    type="choice",
    options=["Fast mode", "Safe mode"],
    recommended=["Fast mode"],
  )
  assert field.id == "we-should-use-this-mode"
  assert kebab_slug("Trailing --- punctuation?!") == "trailing-punctuation"

  with pytest.raises(ValueError, match="at most 1 option"):
    ReportField(
      label="Select one",
      type="choice",
      options=["One", "Two"],
      recommended=["One", "Two"],
    )


def test_sqlite_store_crud_for_messages_tasks_reports_and_meta(tmp_path: Path) -> None:
  db_file = tmp_path / "steering.sqlite3"
  store = SqliteStore(db_file)
  clock = UtcClock()
  id_gen = SecretsHexIdGenerator()
  now = clock.now_iso()
  msg_id = id_gen.new_hex_id()

  msg = Message(
    id=msg_id,
    body="Hello steering store",
    hidden=False,
    blocking=True,
    parent_ids=["a1b2c3", "d4e5f6"],
    status="sent",
    acks=[],
    modified_at=now,
  )
  store.save_message(msg)
  loaded_msg = store.get_message(msg_id)
  assert loaded_msg == msg
  assert [item.id for item in store.list_messages(unread_only=True)] == [msg_id]

  msg.status = "acked"
  msg.acks.append("Acknowledged in test.")
  store.save_message(msg)
  assert store.list_messages(unread_only=True) == []

  t1 = Task(id="task-a", title="First task", modified_at=now)
  t2 = Task(id="task-b", title="Second task", deps=["task-a"], modified_at=now)
  store.save_task_queue([t1, t2])
  assert [item.id for item in store.list_tasks()] == ["task-a", "task-b"]
  assert store.delete_task("task-a") is True
  assert [item.id for item in store.list_tasks()] == ["task-b"]

  report = Report(
    id="arch-report",
    title="Architecture Report",
    body="# Arch\n",
    fields=[
      ReportField(
        label="We should use this storage mode",
        type="choice",
        options=["SQLite WAL", "Memory"],
        recommended=["SQLite WAL"],
      )
    ],
    status="published",
    answers=[
      ReportAnswer(
        id="beef01",
        report_id="arch-report",
        values={"we-should-use-this-storage-mode": "SQLite WAL"},
        status="sent",
        acks=[],
        modified_at=now,
      )
    ],
    ack_seen=True,
    modified_at=now,
  )
  store.save_report(report)
  loaded_report = store.get_report("arch-report")
  assert loaded_report == report

  store.set_meta("skip_poll", "1")
  assert store.get_meta("skip_poll") == "1"
  store.close()


def test_concurrent_first_store_opens(tmp_path: Path) -> None:
  from concurrent.futures import ThreadPoolExecutor
  from threading import Barrier

  for attempt in range(20):
    db = tmp_path / f"race-{attempt}.sqlite3"
    barrier = Barrier(4)

    def open_store(path: Path = db, start: Barrier = barrier) -> None:
      start.wait()
      store = SqliteStore(path)
      store.close()

    with ThreadPoolExecutor(max_workers=4) as pool:
      list(pool.map(lambda _: open_store(), range(4)))


def test_store_retries_busy_wal_initialization(
  tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  import sqlite3

  real_connect = sqlite3.connect
  attempts = 0

  class BusyOnceConnection(sqlite3.Connection):
    def execute(self, sql, *args, **kwargs):
      nonlocal attempts
      if sql == "PRAGMA journal_mode=WAL":
        attempts += 1
        if attempts == 1:
          error = sqlite3.OperationalError("database is locked")
          error.sqlite_errorcode = sqlite3.SQLITE_BUSY
          raise error
      return super().execute(sql, *args, **kwargs)

  def connect(*args, **kwargs):
    return real_connect(*args, factory=BusyOnceConnection, **kwargs)

  monkeypatch.setattr(sqlite3, "connect", connect)
  store = SqliteStore(tmp_path / "busy.sqlite3")
  store.close()
  assert attempts == 2


def test_store_wal_retry_stops_on_persistent_lock(
  tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  import sqlite3
  from types import SimpleNamespace

  import arena_steering.store as store_module

  real_connect = sqlite3.connect
  ticks = iter([0.0, 6.0])
  attempts = 0

  class AlwaysBusyConnection(sqlite3.Connection):
    def execute(self, sql, *args, **kwargs):
      nonlocal attempts
      if sql == "PRAGMA journal_mode=WAL":
        attempts += 1
        error = sqlite3.OperationalError("database is locked")
        error.sqlite_errorcode = sqlite3.SQLITE_BUSY
        raise error
      return super().execute(sql, *args, **kwargs)

  def connect(*args, **kwargs):
    return real_connect(*args, factory=AlwaysBusyConnection, **kwargs)

  monkeypatch.setattr(sqlite3, "connect", connect)
  monkeypatch.setattr(
    store_module, "time", SimpleNamespace(monotonic=lambda: next(ticks))
  )
  with pytest.raises(sqlite3.OperationalError, match="database is locked"):
    SqliteStore(tmp_path / "locked.sqlite3")
  assert attempts == 1


def test_reply_seen_revision_rejects_stale_views_and_survives_restart(tmp_path):
  from arena_steering.services import MessageService

  path = tmp_path / "replies.sqlite3"
  first = SqliteStore(path)
  second = SqliteStore(path)
  messages = MessageService(first, first, first)
  messages.send_message("Review", msg_id="aa1234")
  messages.ack("aa1234", "First reply")
  old = first.get_message("aa1234")
  assert old is not None and not old.replies_seen
  assert second.mark_replies_seen("aa1234", old.replies_revision)
  assert first.get_message("aa1234").replies_seen
  messages.ack("aa1234", "Second reply")
  assert not second.mark_replies_seen("aa1234", old.replies_revision)
  newest = second.get_message("aa1234")
  assert newest is not None and not newest.replies_seen
  assert second.mark_replies_seen("aa1234", newest.replies_revision)
  first.close()
  second.close()
  reopened = SqliteStore(path)
  assert reopened.get_message("aa1234").replies_seen
  reopened.close()


def test_concurrent_reply_and_seen_never_hide_the_new_reply(tmp_path):
  from concurrent.futures import ThreadPoolExecutor
  from threading import Barrier

  from arena_steering.services import MessageService

  path = tmp_path / "race.sqlite3"
  first, second = SqliteStore(path), SqliteStore(path)
  service = MessageService(first, first, first)
  service.send_message("Review", msg_id="aa1234")
  service.ack("aa1234", "Initial")
  for index in range(10):
    revision = first.get_message("aa1234").replies_revision
    barrier = Barrier(2)

    def mark(barrier=barrier, revision=revision):
      barrier.wait()
      return second.mark_replies_seen("aa1234", revision)

    def reply(barrier=barrier, index=index):
      barrier.wait()
      service.ack("aa1234", f"Reply {index}")

    with ThreadPoolExecutor(max_workers=2) as pool:
      futures = [pool.submit(mark), pool.submit(reply)]
      for future in futures:
        future.result()
    assert not first.get_message("aa1234").replies_seen
  first.close()
  second.close()


def test_reply_seen_migration_marks_legacy_replies_unseen(tmp_path):
  import sqlite3

  path = tmp_path / "legacy.sqlite3"
  conn = sqlite3.connect(path)
  conn.execute(
    """CREATE TABLE messages (
      seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE NOT NULL, body TEXT NOT NULL,
      hidden INTEGER NOT NULL DEFAULT 0, blocking INTEGER NOT NULL DEFAULT 1,
      attachments_json TEXT NOT NULL DEFAULT '[]', parent_ids_json TEXT NOT NULL DEFAULT '[]',
      status TEXT NOT NULL DEFAULT 'sent', acks_json TEXT NOT NULL DEFAULT '[]', modified_at TEXT NOT NULL
    )"""
  )
  conn.execute(
    "INSERT INTO messages (id, body, status, acks_json, modified_at) VALUES (?, ?, ?, ?, ?)",
    ("aa1234", "Legacy", "acked", '[ "Prior reply" ]', "2026-01-01T00:00:00Z"),
  )
  conn.commit()
  conn.close()
  store = SqliteStore(path)
  message = store.get_message("aa1234")
  assert message is not None and message.acks == ["Prior reply"]
  assert not message.replies_seen
  assert store.mark_replies_seen("aa1234", message.replies_revision)
  store.close()


def test_task_snapshot_column_migrates_legacy_database(tmp_path):
  import sqlite3

  path = tmp_path / "legacy-tasks.sqlite3"
  conn = sqlite3.connect(path)
  conn.execute(
    """CREATE TABLE tasks (
    position INTEGER NOT NULL, id TEXT PRIMARY KEY,
    title TEXT NOT NULL, type TEXT NOT NULL, status TEXT NOT NULL, scope TEXT NOT NULL,
    details_json TEXT NOT NULL DEFAULT '[]', links_json TEXT NOT NULL DEFAULT '',
    msg_ids_json TEXT NOT NULL DEFAULT '[]', report_ids_json TEXT NOT NULL DEFAULT '[]',
    deps_json TEXT NOT NULL DEFAULT '[]', modified_at TEXT NOT NULL
  )""".replace("seq INTEGER PRIMARY KEY AUTOINCREMENT, ", "")
  )
  conn.execute(
    "INSERT INTO tasks (position, id, title, type, status, scope, details_json, modified_at) "
    "VALUES (0, ?, ?, ?, ?, ?, ?, ?)",
    (
      "legacy",
      "Old task",
      "code",
      "upcoming",
      "",
      '["A detail"]',
      "2026-01-01T00:00:00Z",
    ),
  )
  conn.commit()
  conn.close()
  store = SqliteStore(path)
  task = store.get_task("legacy")
  assert (
    task is not None and task.answer_snapshots == [] and task.details == ["A detail"]
  )
  store.save_task_queue([task])
  store.close()
  reopened = SqliteStore(path)
  assert reopened.get_task("legacy").answer_snapshots == []
  reopened.close()


def test_snapshot_migration_backfills_linked_report_answers(tmp_path):
  import sqlite3

  from arena_steering.services import ReportService, TaskService

  path = tmp_path / "old-linked.sqlite3"
  store = SqliteStore(path)
  reports = ReportService(store, store)
  tasks = TaskService(store, store)
  reports.publish_report(
    "choice", "Decision", "Select? {#select}\n- ( ) Yes\n- ( ) No\n"
  )
  answer = reports.submit_answer("choice", {"select": "Yes"}, answer_id="ab1234")
  tasks.create_task("linked", "Linked", details=["Review"], report_ids=["choice"])
  store.close()
  conn = sqlite3.connect(path)
  conn.execute("ALTER TABLE tasks DROP COLUMN answer_snapshots_json")
  conn.commit()
  conn.close()
  migrated = SqliteStore(path)
  task = migrated.get_task("linked")
  assert task is not None
  assert task.answer_snapshots[0]["id"] == answer.id
  assert task.answer_snapshots[0]["fields"][0]["value"] == "Yes"
  migrated.close()


def test_nested_store_transaction_rolls_back_only_inner_changes():
  store = SqliteStore()
  with store.transaction():
    store.set_meta("outer", "saved")
    try:
      with store.transaction():
        store.set_meta("inner", "discarded")
        raise ValueError("rollback")
    except ValueError:
      pass
  assert store.get_meta("outer") == "saved"
  assert store.get_meta("inner") is None
  store.close()
