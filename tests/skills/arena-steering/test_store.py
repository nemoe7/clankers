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
    status="sent",
    acks=["Initial ack"],
    modified_at="2026-10-29T06:00:00Z",
  )
  assert msg.requires_ack is True
  assert msg.is_unread is True
  round_trip = Message.from_dict(msg.to_dict())
  assert round_trip == msg

  with pytest.raises(ValueError, match="6 lowercase hex"):
    Message(id="abc12", body="Too short")

  with pytest.raises(ValueError, match="6 lowercase hex"):
    Message(id="A1B2C3", body="Uppercase hex rejected")


def test_task_validation_and_detail_limit() -> None:
  task = Task(
    id="core-models",
    title="Build models and store",
    type="code",
    status="upcoming",
    scope="skills/arena-steering/",
    details=["Define models.py and store.py."],
    msg_ids=["a1b2c3", "a1b2c3"],
    report_ids=["steering-spec"],
    deps=["prep-task"],
    modified_at="2026-10-29T06:00:00Z",
  )
  assert task.msg_ids == ["a1b2c3"]
  assert Task.from_dict(task.to_dict()) == task

  with pytest.raises(ValueError, match="120 characters"):
    Task(id="bad-detail", title="Too long", details=["x" * 121])

  with pytest.raises(ValueError, match="depend on itself"):
    Task(id="self-dep", title="Cycle", deps=["self-dep"])


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
    modified_at=now,
  )
  store.save_report(report)
  loaded_report = store.get_report("arch-report")
  assert loaded_report == report

  store.set_meta("skip_poll", "1")
  assert store.get_meta("skip_poll") == "1"
  store.close()
