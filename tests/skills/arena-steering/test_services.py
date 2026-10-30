"""Unit tests for Arena Steering Markdown parser and domain services."""

from __future__ import annotations

import pytest
from arena_steering.markdown_fields import (
  format_answer_for_task_detail,
  parse_report_markdown,
)
from arena_steering.services import (
  MessageService,
  ReportService,
  TaskService,
)
from arena_steering.store import SqliteStore


def test_parse_report_markdown_extracts_choice_checkbox_and_text_fields() -> None:
  md = """# Steering Report

We should use this execution mode
- (x) Fast mode
- ( ) Safe mode
- ( ) custom: ___

<!-- checks-to-run -->
We should run these checks
- [x] Unit tests
- [ ] Prose lint

Summary note: ___
"""
  blocks, fields = parse_report_markdown(md)
  assert len(fields) == 3

  f0 = fields[0]
  assert f0.id == "we-should-use-this-execution-mode"
  assert f0.label == "We should use this execution mode"
  assert f0.type == "choice"
  assert f0.options == ["Fast mode", "Safe mode"]
  assert f0.recommended == ["Fast mode"]

  f1 = fields[1]
  assert f1.id == "checks-to-run"
  assert f1.label == "We should run these checks"
  assert f1.type == "checkbox"
  assert f1.options == ["Unit tests", "Prose lint"]
  assert f1.recommended == ["Unit tests"]

  f2 = fields[2]
  assert f2.id == "summary-note"
  assert f2.type == "text"

  detail = format_answer_for_task_detail(f0, "Fast mode")
  assert detail == "We should use this execution mode: Fast mode."
  assert any(block_type == "field" for block_type, _ in blocks)


def test_message_service_lifecycle_and_acks() -> None:
  store = SqliteStore(":memory:")
  svc = MessageService(store, store, store)

  msg = svc.send_message("Please review the schema", msg_id="ab12cd")
  assert msg.id == "ab12cd"
  assert msg.status == "sent"

  pending = svc.read_pending(mark_seen=True)
  assert [item.id for item in pending["messages"]] == ["ab12cd"]
  assert svc.get_message("ab12cd").status == "seen"

  target_type, acked = svc.ack(None, "Reviewed and locked `ab12cd`.")
  assert target_type == "message"
  assert acked.status == "acked"
  assert acked.acks == ["Reviewed and locked `ab12cd`."]
  assert svc.has_pending_deliverables() is False
  store.close()


def test_message_service_stores_parent_ids_for_multi_message_replies() -> None:
  store = SqliteStore(":memory:")
  svc = MessageService(store, store, store)

  svc.send_message("First parent", msg_id="aa1001")
  svc.send_message("Second parent", msg_id="bb2002")
  reply = svc.send_message(
    "Reply to both",
    parent_ids=["bb2002", "aa1001", "bb2002"],
    msg_id="cc3003",
  )

  assert reply.parent_ids == ["bb2002", "aa1001"]
  assert svc.get_message("cc3003").parent_ids == ["bb2002", "aa1001"]

  with pytest.raises(KeyError, match="Unknown parent message ID"):
    svc.send_message("Missing parent", parent_ids=["dd4004"], msg_id="ee5005")

  store.close()


def test_task_service_mutable_dependency_queue_and_derived_blocking() -> None:
  store = SqliteStore(":memory:")
  tasks = TaskService(store, store)
  reports = ReportService(store, store)

  tasks.create_task("task-b", "Build consumer")
  tasks.create_task("task-a", "Build foundation")
  tasks.mod_deps_add("task-b", "task-a")

  ordered = tasks.list_tasks(include_finished=True)
  assert [item.id for item, _ in ordered] == ["task-a", "task-b"]
  assert ordered[0][1] is False
  assert ordered[1][1] is True

  tasks.mod_scalar("task-a", "status", "finished")
  assert tasks.get_task("task-b")[1] is False

  reports.publish_report(
    "design-doc",
    "Design Doc",
    "We should use this database\n- (x) SQLite\n- ( ) JSON\n",
  )
  tasks.mod_links_add("task-b", "design-doc")
  assert tasks.get_task("task-b")[1] is True

  ans = reports.submit_answer(
    "design-doc",
    {"we-should-use-this-database": "SQLite"},
    answer_id="dead01",
  )
  assert ans.status == "sent"
  assert "We should use this database: SQLite." in tasks.get_task("task-b")[0].details
  assert tasks.get_task("task-b")[1] is True

  reports.ack_answer("design-doc", "dead01", "Confirmed SQLite.")
  assert tasks.get_task("task-b")[1] is False

  tasks.mod_deets("task-b", "Added integration check.")
  count_before = len(tasks.get_task("task-b")[0].details)
  tasks.mod_deets_rm("task-b", count_before)
  assert len(tasks.get_task("task-b")[0].details) == count_before - 1

  with pytest.raises(ValueError, match="cycle"):
    tasks.mod_deps_add("task-a", "task-b")

  store.close()


def test_report_ack_seen_lifecycle() -> None:
  store = SqliteStore(":memory:")
  reports = ReportService(store, store)
  messages = MessageService(store, store, store)

  reports.publish_report(
    "ack-doc",
    "Ack Doc",
    "We should use this mode\n- (x) Live\n- ( ) Manual\n",
  )
  reports.submit_answer(
    "ack-doc", {"we-should-use-this-mode": "Live"}, answer_id="dead02"
  )
  assert reports.get_report("ack-doc").ack_seen is False
  assert reports.mark_ack_seen("ack-doc").ack_seen is False

  reports.ack_answer("ack-doc", "dead02", "Confirmed live.")
  assert reports.get_report("ack-doc").ack_seen is False
  assert reports.mark_ack_seen("ack-doc").ack_seen is True
  assert reports.mark_ack_seen("ack-doc").ack_seen is True

  reports.ack_answer("ack-doc", "dead02", "Second reply.")
  assert reports.get_report("ack-doc").ack_seen is False
  assert reports.mark_ack_seen("ack-doc").ack_seen is True

  target_type, _ = messages.ack("dead02", "Third reply.")
  assert target_type == "report_answer"
  assert reports.get_report("ack-doc").ack_seen is False
  assert reports.mark_ack_seen("ack-doc").ack_seen is True

  reports.submit_answer(
    "ack-doc", {"we-should-use-this-mode": "Manual"}, answer_id="dead03"
  )
  assert reports.get_report("ack-doc").ack_seen is False
  store.close()
