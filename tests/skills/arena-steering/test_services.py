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

  tasks.create_task("task-b", "Build consumer", details=["Build consumer."])
  tasks.create_task("task-a", "Build foundation", details=["Build foundation."])
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


def test_task_details_required_for_create_and_legacy_update(tmp_path) -> None:
  from arena_steering.models import Task

  path = tmp_path / "legacy.sqlite3"
  store = SqliteStore(path)
  store.save_task_queue([Task(id="legacy-task", title="Legacy", details=[])])
  store.close()
  store = SqliteStore(path)
  tasks = TaskService(store, store)
  assert tasks.get_task("legacy-task")[0].details == []
  with pytest.raises(ValueError, match="at least one detail"):
    tasks.create_task("empty-task", "Empty")
  with pytest.raises(ValueError, match="at least one detail"):
    tasks.patch_task("legacy-task", {"title": "Changed"})
  assert tasks.get_task("legacy-task")[0].title == "Legacy"
  tasks.mod_deets("legacy-task", "Add a detail")
  with pytest.raises(ValueError, match="at least one detail"):
    tasks.mod_deets_rm("legacy-task", 1)
  assert tasks.get_task("legacy-task")[0].details == ["Add a detail"]
  store.close()


def test_task_answer_snapshots_survive_report_removal_and_edits(tmp_path) -> None:
  from io import StringIO

  from arena_steering.cli import _print_single_task, _print_task_list

  path = tmp_path / "snapshots.sqlite3"
  store = SqliteStore(path)
  reports = ReportService(store, store)
  tasks = TaskService(store, store)
  reports.publish_report(
    "decision", "Original decision", "Choice? {#choice}\n- ( ) A\n- ( ) B\n"
  )
  tasks.create_task(
    "work", "Do work", details=["Act on the answer"], report_ids=["decision"]
  )
  first = reports.submit_answer("decision", {"choice": "A"}, answer_id="ab0001")
  reports.ack_answer("decision", first.id, "Read")
  second = reports.submit_answer("decision", {"choice": "A"}, answer_id="ab0002")
  reports.ack_answer("decision", second.id, "Read")
  snapshots = tasks.get_task("work")[0].answer_snapshots
  assert [item["id"] for item in snapshots] == [first.id, second.id]
  assert all(item["fields"][0]["value"] == "A" for item in snapshots)
  assert snapshots[0]["created_at"] == first.created_at
  tasks.mod_scalar("work", "title", "Updated work")
  tasks.mod_deets("work", "Another detail")
  tasks.patch_task("work", {"scope": "test"})
  tasks.rename_task("work", "renamed")
  reports.remove_report("decision")
  store.close()

  reopened = SqliteStore(path)
  task = reopened.get_task("renamed")
  assert task is not None and task.answer_snapshots == snapshots
  assert task.report_ids == []
  out = StringIO()
  _print_task_list([(task, False)], out)
  _print_single_task(task, False, out)
  text = out.getvalue()
  assert first.id in text and second.id in text and "Original decision" in text
  assert "Choice" in text and '"A"' in text and first.created_at in text
  reopened.close()


def test_existing_report_answers_are_snapshotted_when_linked(tmp_path) -> None:
  store = SqliteStore(tmp_path / "link.sqlite3")
  reports = ReportService(store, store)
  tasks = TaskService(store, store)
  reports.publish_report(
    "decision", "Decision", "Choice? {#choice}\n- ( ) A\n- ( ) B\n"
  )
  answer = reports.submit_answer("decision", {"choice": "B"}, answer_id="cd0001")
  reports.ack_answer("decision", answer.id, "Read")
  tasks.create_task("work", "Do work", details=["Act on the answer"])
  tasks.mod_links_add("work", "decision", link_type="report")
  assert tasks.get_task("work")[0].answer_snapshots[0]["id"] == answer.id
  store.close()


def test_snapshot_keeps_original_report_labels_after_republish(tmp_path) -> None:
  store = SqliteStore(tmp_path / "labels.sqlite3")
  reports = ReportService(store, store)
  tasks = TaskService(store, store)
  reports.publish_report(
    "decision", "Original title", "Original label? {#field}\n- ( ) A\n- ( ) B\n"
  )
  answer = reports.submit_answer("decision", {"field": "A"}, answer_id="ba1001")
  reports.ack_answer("decision", answer.id, "Read")
  reports.publish_report(
    "decision", "New title", "New label? {#field}\n- ( ) A\n- ( ) B\n"
  )
  task = tasks.create_task(
    "work", "Do work", details=["Review"], report_ids=["decision"]
  )
  assert task.answer_snapshots[0]["report_title"] == "Original title"
  assert task.answer_snapshots[0]["fields"][0]["label"] == "Original label?"
  assert task.answer_snapshots[0]["created_at"] == answer.created_at
  store.close()
