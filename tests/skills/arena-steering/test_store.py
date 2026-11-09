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

EXPECTED_INITIAL_VERSION = "2.2.3"


def test_clause_quiz_survives_restart_model_and_snapshot_round_trips(
  tmp_path: Path,
) -> None:
  from arena_steering.models import ClauseQuiz
  from arena_steering.services import MessageService

  path = tmp_path / "quiz.sqlite3"
  store = SqliteStore(path)
  messages = MessageService(store, store, store, store)
  clause = "Preserve the original selected clause."
  quiz = messages.send_clause_quiz("Recall a clause", "AGENTS.md", 12, clause)
  snapshot = store.export_rows()
  store.close()
  store = SqliteStore(path)
  peer = SqliteStore()
  try:
    restored = store.get_message(quiz.id)
    assert isinstance(restored, ClauseQuiz)
    assert isinstance(Message.from_dict(restored.to_dict()), ClauseQuiz)
    peer.merge_rows(snapshot)
    merged = peer.get_message(quiz.id)
    assert isinstance(merged, ClauseQuiz)
    for target in (store, peer):
      before = target.get_message(quiz.id).to_dict()
      with pytest.raises(ValueError):
        target.append_message_ack(
          quiz.id, "AGENTS.md:12 Wrong clause", quiz.modified_at
        )
      assert target.get_message(quiz.id).to_dict() == before
      reply = f"AGENTS.md:12 {clause}"
      acked = target.append_message_ack(quiz.id, reply, quiz.modified_at)
      assert acked.acks == [reply]
  finally:
    peer.close()
    store.close()


@pytest.mark.parametrize("external", [False, True])
def test_data_version_ignores_poll_heartbeat_churn(
  tmp_path: Path, external: bool
) -> None:
  path = tmp_path / "heartbeat.sqlite3"
  reader = SqliteStore(path)
  writer = SqliteStore(path) if external else reader
  try:
    before = reader.data_version()
    writer.set_meta("polling_at", "2026-11-09T00:00:00Z")
    started = reader.data_version()
    assert started != before
    writer.set_meta("polling_at", "2026-11-09T00:00:01Z")
    assert reader.data_version() == started
    writer.set_meta("timezone", "UTC")
    changed = reader.data_version()
    assert changed != started
    writer.set_meta("polling_at", "")
    assert reader.data_version() != changed
    before_message = reader.data_version()
    writer.save_message(Message(id="aa0010", body="New content"))
    assert reader.data_version() != before_message
  finally:
    if external:
      writer.close()
    reader.close()


def test_reopening_current_schema_skips_schema_setup(
  tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  import sqlite3

  path = tmp_path / "current-schema.sqlite3"
  initial = SqliteStore(path)
  message = Message(id="ac0010", body="Keep the existing data")
  initial.save_message(message)
  initial.close()
  statements: list[str] = []
  connect = sqlite3.connect

  def traced_connect(*args, **kwargs):
    connection = connect(*args, **kwargs)
    connection.set_trace_callback(statements.append)
    return connection

  monkeypatch.setattr(sqlite3, "connect", traced_connect)
  reopened = SqliteStore(path)
  try:
    assert reopened.get_message(message.id).body == message.body
    assert not any(
      "CREATE " in sql.upper() or "TABLE_INFO" in sql.upper() for sql in statements
    ), statements
    assert not any("BEGIN IMMEDIATE" in sql.upper() for sql in statements), statements
    assert reopened._conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert reopened._conn.execute("PRAGMA synchronous").fetchone()[0] == 1
  finally:
    reopened.close()


@pytest.mark.parametrize("invalidation", ["revision", "schema", "missing-marker"])
def test_schema_setup_cache_invalidates_safely(
  tmp_path: Path, monkeypatch: pytest.MonkeyPatch, invalidation: str
) -> None:
  import sqlite3

  from arena_steering import store as store_module

  path = tmp_path / "invalidated-schema.sqlite3"
  initial = SqliteStore(path)
  initial.close()
  if invalidation == "revision":
    monkeypatch.setattr(
      store_module, "SCHEMA_REVISION", store_module.SCHEMA_REVISION + 1
    )
  else:
    with sqlite3.connect(path) as connection:
      if invalidation == "schema":
        connection.execute("DROP INDEX messages_written_at")
      else:
        connection.execute("DELETE FROM meta WHERE key = 'schema_ready'")
  calls: list[SqliteStore] = []
  initialize = SqliteStore._init_state_tracking

  def tracked_initialize(self):
    calls.append(self)
    initialize(self)

  monkeypatch.setattr(SqliteStore, "_init_state_tracking", tracked_initialize)
  reopened = SqliteStore(path)
  try:
    assert calls == [reopened]
    version = reopened._conn.execute("PRAGMA schema_version").fetchone()[0]
    assert (
      reopened.get_meta("schema_ready") == f"{store_module.SCHEMA_REVISION}:{version}"
    )
    assert reopened._conn.execute(
      "SELECT 1 FROM sqlite_master WHERE type = 'index' AND name = 'messages_written_at'"
    ).fetchone()
  finally:
    reopened.close()
  cached = SqliteStore(path)
  assert calls == [reopened]
  cached.close()


@pytest.mark.parametrize("change", ["none", "edit", "reorder", "remove"])
def test_task_queue_only_versions_changed_rows(change: str) -> None:
  store = SqliteStore()
  try:
    tasks = [
      Task(id=f"task-{index}", title=f"Task {index}", size=1) for index in range(3)
    ]
    store.save_task_queue(tasks)
    cursor = store.state_stamp()
    if change == "edit":
      tasks[0].title = "Edited task"
      expected_changed = {tasks[0].id}
    elif change == "reorder":
      tasks[0], tasks[1] = tasks[1], tasks[0]
      expected_changed = {tasks[0].id, tasks[1].id}
    else:
      expected_changed = set()
    removed = tasks.pop() if change == "remove" else None
    store.save_task_queue(tasks)
    delta = store.export_rows(since=cursor)
    assert {row["id"] for row in delta["tasks"]} == expected_changed
    assert [row["id"] for row in delta["deleted"]["tasks"]] == (
      [removed.id] if removed else []
    )
    assert [task.id for task in store.list_tasks()] == [task.id for task in tasks]
    if change == "none":
      assert store.state_stamp() == cursor
  finally:
    store.close()


def test_duplicate_new_task_ids_roll_back_queue_changes() -> None:
  import sqlite3

  store = SqliteStore()
  try:
    original = Task(id="existing", title="Existing task", size=1)
    store.save_task_queue([original])
    cursor = store.state_stamp()
    duplicates = [
      Task(id="duplicate", title="Duplicate task", size=1) for _ in range(2)
    ]
    with pytest.raises(sqlite3.IntegrityError):
      store.save_task_queue([original, *duplicates])
    assert [task.id for task in store.list_tasks()] == [original.id]
    assert store.state_stamp() == cursor
  finally:
    store.close()


def test_package_exposes_current_semver_version() -> None:
  assert __version__ == EXPECTED_INITIAL_VERSION


def test_retry_token_save_preserves_typed_message_metadata(tmp_path: Path) -> None:
  store = SqliteStore(tmp_path / "retry-metadata.sqlite3")
  messages = [
    Message(
      id="aa0011",
      body="Violation",
      hidden=True,
      violation_type="rule",
      violation_clause_file="ARENA.md",
    ),
    Message(
      id="aa0012",
      body="Answer",
      hidden=True,
      type="report_answer",
      answer_data={"report_id": "report", "values": {"choice": "yes"}},
    ),
  ]
  for message in messages:
    saved = store.save_message_once(message, message.id, "same-content")
    replay = store.save_message_once(message, message.id, "same-content")
    assert saved == message
    assert replay == message
    assert store.get_message(message.id) == message
    with pytest.raises(ValueError, match="different content"):
      store.save_message_once(message, message.id, "different-content")
  store.close()


def test_retry_token_insert_rolls_back_message_on_receipt_failure(
  tmp_path: Path,
) -> None:
  store = SqliteStore(tmp_path / "retry-rollback.sqlite3")
  with store.transaction():
    store._conn.execute(
      "CREATE TRIGGER fail_receipt BEFORE INSERT ON message_requests BEGIN SELECT RAISE(ABORT, 'receipt failed'); END"
    )
  import sqlite3

  with pytest.raises(sqlite3.IntegrityError, match="receipt failed"):
    store.save_message_once(
      Message(id="aa0013", body="Atomic"), "request", "fingerprint"
    )
  assert store.get_message("aa0013") is None
  store.close()


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
    size=3,
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
    Task(size=3, id="bad-detail", title="Too long", details=["x" * 121])

  with pytest.raises(ValueError, match="depend on itself"):
    Task(size=3, id="self-dep", title="Cycle", links={"task_ids": ["self-dep"]})


@pytest.mark.parametrize("status", ["in_progress", "blocked", "other"])
def test_task_status_rejects_other_values(status: str) -> None:
  with pytest.raises(ValueError, match="Invalid Task.status"):
    Task(size=3, id="work", title="Work", status=status, details=["Do work"])


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

  t1 = Task(size=3, id="task-a", title="First task", modified_at=now)
  t2 = Task(size=3, id="task-b", title="Second task", deps=["task-a"], modified_at=now)
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
  store.save_report_answer(report.answers[0])
  store.save_report(report)
  loaded_report = store.get_report("arch-report")
  assert loaded_report == report

  store.set_meta("skip_poll", "1")
  assert store.get_meta("skip_poll") == "1"
  store.close()


def test_report_answers_use_current_message_storage(tmp_path: Path) -> None:
  path = tmp_path / "answers.sqlite3"
  store = SqliteStore(path)
  report = Report(id="decision", title="Decision", body="")
  answer = ReportAnswer(id="ee1001", report_id=report.id, values={"choice": "A"})
  store.save_report(report)
  store.save_report_answer(answer)
  snapshot = store.export_rows()
  assert "answers_json" not in snapshot["reports"][0]
  assert any(row["id"] == answer.id for row in snapshot["messages"])
  store.close()
  reopened = SqliteStore(path)
  target = SqliteStore()
  try:
    assert reopened.get_report(report.id).answers == [answer]
    target.merge_rows(snapshot)
    assert target.get_report(report.id).answers == [answer]
  finally:
    reopened.close()
    target.close()


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
  messages = MessageService(first, first, first, first)
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
  service = MessageService(first, first, first, first)
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


def test_message_write_stamps_keep_pages_and_sync_stable_on_collision() -> None:
  stamp = "2026-01-01T00:00:00.000000Z"
  first, second = SqliteStore(), SqliteStore()
  first.save_message(Message(id="fe0001", body="First", modified_at=stamp))
  second.save_message_once(
    Message(id="0a0001", body="Second", modified_at=stamp), "request-1", "fingerprint"
  )
  first_row = first.export_rows()["messages"][0]
  second_row = second.export_rows()["messages"][0]
  assert first_row["written_at"] == second_row["written_at"] == stamp

  left, right = SqliteStore(), SqliteStore()
  left.merge_rows({"messages": [first_row, second_row]})
  right.merge_rows({"messages": [second_row, first_row]})
  for store in (left, right):
    assert [msg.id for msg in store.list_messages()] == ["0a0001", "fe0001"]
    page, total, has_more = store.list_message_page(
      unread_only=False, include_hidden=True, query="", before="fe0001", limit=1
    )
    assert [msg.id for msg in page] == ["0a0001"]
    assert total == 2 and not has_more

  cursor = second.state_stamp()
  second.append_message_ack("0a0001", "Read", stamp)
  changes = second.export_rows(since=cursor)["messages"]
  assert [row["id"] for row in changes] == ["0a0001"]
  assert changes[0]["written_at"] == stamp
  left.merge_rows({"messages": changes})
  assert [msg.id for msg in left.list_messages()] == ["0a0001", "fe0001"]
  assert left.get_message("0a0001").acks == ["Read"]
  for store in (first, second, left, right):
    store.close()


def test_old_task_answer_snapshots_are_not_migrated(tmp_path):
  import sqlite3

  from arena_steering.services import ReportService

  path = tmp_path / "old-linked.sqlite3"
  store = SqliteStore(path)
  reports = ReportService(store, store)
  reports.publish_report(
    "choice",
    "Decision",
    (
      '<!-- question {"id": "select", "label": "Select?"} -->\n'
      "Select?\n"
      '- (x) Yes <!-- option {"label": "Yes"} -->\n'
      '- ( ) No <!-- option {"label": "No"} -->\n'
    ),
  )
  reports.submit_answer("choice", {"select": "Yes"}, answer_id="ab1234")
  store.save_task_queue(
    [
      Task(
        size=3, id="linked", title="Linked", details=["Review"], report_ids=["choice"]
      )
    ]
  )
  store.close()
  conn = sqlite3.connect(path)
  conn.execute(
    "ALTER TABLE tasks ADD COLUMN answer_snapshots_json TEXT NOT NULL DEFAULT '[]'"
  )
  conn.execute(
    "UPDATE tasks SET answer_snapshots_json = ? WHERE id = ?",
    ('[{"id":"ab1234"}]', "linked"),
  )
  conn.commit()
  conn.close()
  reopened = SqliteStore(path)
  task = reopened.get_task("linked")
  assert task is not None and task.details == ["Review"]
  assert "answer_snapshots" not in task.to_dict()
  reopened.close()


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


def test_current_report_pin_survives_state_merge(tmp_path: Path) -> None:
  path = tmp_path / "current-report.sqlite3"
  source = SqliteStore(path)
  source.save_report(Report(id="old-report", title="Report", body="# Report"))
  report = source.get_report("old-report")
  assert report is not None
  assert "seq" not in source.export_rows()["reports"][0]
  assert report.last_viewed_at == "" and report.pinned is False
  assert report.source_file == ""
  report.pinned = True
  report.source_file = "arena-state/reports/old.md"
  report.modified_at = "2026-01-02T00:00:00Z"
  source.save_report(report)

  target = SqliteStore(":memory:")
  target.merge_rows(source.export_rows())
  assert target.get_report("old-report").pinned is True
  assert target.get_report("old-report").source_file == report.source_file
  report.pinned = False
  report.modified_at = "2026-01-03T00:00:00Z"
  source.save_report(report)
  target.merge_rows(source.export_rows())
  assert target.get_report("old-report").pinned is False
  source.close()
  target.close()


@pytest.mark.parametrize("status", ["other", "in_progress", "blocked"])
def test_merging_unsupported_task_status_is_atomic(status: str) -> None:
  source = SqliteStore()
  source.save_task_queue(
    [
      Task(size=3, id="first", title="First", details=["Do work"]),
      Task(size=3, id="work", title="Work", details=["Do work"]),
    ]
  )
  snapshot = source.export_rows()
  snapshot["tasks"][1]["status"] = status
  target = SqliteStore()
  with pytest.raises(ValueError, match="Invalid Task.status"):
    target.merge_rows(snapshot)
  assert target.list_tasks() == []
  source.close()
  target.close()


def test_state_deletions_survive_restart_and_later_edits_win(tmp_path: Path) -> None:
  from datetime import datetime, timedelta

  source_path = tmp_path / "source.sqlite3"
  source = SqliteStore(source_path)
  target = SqliteStore()
  future = "2099-01-01T00:00:00.000000Z"
  source.save_message(
    Message(id="de1001", body="Remove me", modified_at="2020-01-01T00:00:00Z")
  )
  source.save_task_queue(
    [Task(size=3, id="remove-task", title="Remove task", modified_at=future)]
  )
  source.save_report(
    Report(id="remove-report", title="Remove report", body="Old", modified_at=future)
  )
  original = source.export_rows()
  target.merge_rows(original)
  cursor = source.state_stamp()

  assert source.delete_task("remove-task") is True
  assert source.delete_report("remove-report") is True
  with source.transaction():
    source._conn.execute("DELETE FROM messages WHERE id = ?", ("de1001",))
  changed = source.export_rows(since=cursor)
  for table, row_id in (
    ("messages", "de1001"),
    ("tasks", "remove-task"),
    ("reports", "remove-report"),
  ):
    assert changed[table] == []
    assert [row["id"] for row in changed["deleted"][table]] == [row_id]
  assert source.export_rows()["deleted"] == changed["deleted"]
  assert changed["deleted"]["tasks"][0]["modified_at"] > future
  assert changed["deleted"]["reports"][0]["modified_at"] > future

  applied = target.merge_rows(changed)
  assert set(applied["deleted"]) == {"de1001", "remove-task", "remove-report"}
  assert target.get_message("de1001") is None
  assert target.get_task("remove-task") is None
  assert target.get_report("remove-report") is None
  assert set(target.merge_rows(original)["skipped"]) == set(applied["deleted"])
  source.close()
  source = SqliteStore(source_path)
  assert source.export_rows()["deleted"] == changed["deleted"]

  tombstone = changed["deleted"]["reports"][0]["modified_at"]
  assert target.merge_rows(
    {"reports": [{**original["reports"][0], "modified_at": tombstone}]}
  )["skipped"] == ["remove-report"]
  later = datetime.fromisoformat(tombstone) + timedelta(microseconds=1)
  later_row = {
    **original["reports"][0],
    "body": "Later edit",
    "modified_at": later.isoformat(),
  }
  assert target.merge_rows({"reports": [later_row]})["added"] == ["remove-report"]
  assert target.get_report("remove-report").body == "Later edit"
  assert target.export_rows()["deleted"]["reports"] == []
  source.close()
  target.close()


def test_stale_deletions_do_not_remove_later_edits() -> None:
  store = SqliteStore()
  future = "2099-01-01T00:00:00Z"
  store.save_message(Message(id="de1002", body="Later message", modified_at=future))
  store.save_task_queue(
    [Task(size=3, id="later-task", title="Later task", modified_at=future)]
  )
  store.save_report(
    Report(id="later-report", title="Later report", body="Later", modified_at=future)
  )
  deleted = {
    "messages": [{"id": "de1002", "modified_at": "2020-01-01T00:00:00Z"}],
    "tasks": [{"id": "later-task", "modified_at": "2020-01-01T00:00:00Z"}],
    "reports": [{"id": "later-report", "modified_at": "2020-01-01T00:00:00Z"}],
  }
  assert set(store.merge_rows({"deleted": deleted})["skipped"]) == {
    "de1002",
    "later-task",
    "later-report",
  }
  assert store.get_message("de1002").body == "Later message"
  assert store.get_task("later-task").title == "Later task"
  assert store.get_report("later-report").body == "Later"
  assert store.export_rows()["deleted"] == {table: [] for table in deleted}
  store.close()


def test_local_recreation_after_a_delete_uses_a_later_stamp() -> None:
  store = SqliteStore()
  future = "2099-01-01T00:00:00.000000Z"
  store.save_task_queue([Task(size=3, id="reused", title="Old", modified_at=future)])
  store.save_task_queue([])
  task_deleted_at = store.export_rows()["deleted"]["tasks"][0]["modified_at"]
  store.save_task_queue(
    [Task(size=3, id="reused", title="New", modified_at="2026-01-01T00:00:00Z")]
  )
  assert store.get_task("reused").modified_at > task_deleted_at

  store.save_report(Report(id="reused", title="Old", body="Old", modified_at=future))
  store.delete_report("reused")
  report_deleted_at = store.export_rows()["deleted"]["reports"][0]["modified_at"]
  store.save_report(
    Report(id="reused", title="New", body="New", modified_at="2026-01-01T00:00:00Z")
  )
  assert store.get_report("reused").modified_at > report_deleted_at
  store.close()


def test_message_revision_tracks_only_message_changes() -> None:
  store = SqliteStore()
  try:
    initial = store.message_revision()
    store.save_task_queue([Task(id="task", title="Task", size=1)])
    assert store.message_revision() == initial
    message = Message(id="aa0001", body="Hidden", hidden=True)
    store.save_message(message)
    created = store.message_revision()
    assert created > initial
    message.body = "Updated"
    store.save_message(message)
    updated = store.message_revision()
    assert updated > created
    with store.transaction():
      store._conn.execute("DELETE FROM messages WHERE id = ?", (message.id,))
    assert store.message_revision() > updated
  finally:
    store.close()


def test_fresh_schema_needs_no_column_upgrades(tmp_path, monkeypatch):
  import sqlite3

  statements = []
  connect = sqlite3.connect

  def traced_connect(*args, **kwargs):
    connection = connect(*args, **kwargs)
    connection.set_trace_callback(statements.append)
    return connection

  monkeypatch.setattr(sqlite3, "connect", traced_connect)
  store = SqliteStore(tmp_path / "fresh.sqlite3")
  try:
    assert not any("ALTER TABLE" in sql.upper() for sql in statements)
    assert not any("TABLE_INFO" in sql.upper() for sql in statements)
    message = Message(id="fed123", body="Current schema")
    store.save_message(message)
    assert store.get_message(message.id).body == message.body
  finally:
    store.close()


def test_older_schema_is_not_upgraded(tmp_path):
  import sqlite3

  path = tmp_path / "unsupported.sqlite3"
  with sqlite3.connect(path) as connection:
    connection.execute(
      "CREATE TABLE messages (id TEXT PRIMARY KEY, body TEXT, modified_at TEXT)"
    )
  with pytest.raises(sqlite3.OperationalError):
    SqliteStore(path)
  with sqlite3.connect(path) as connection:
    columns = {row[1] for row in connection.execute("PRAGMA table_info(messages)")}
  assert columns == {"id", "body", "modified_at"}
