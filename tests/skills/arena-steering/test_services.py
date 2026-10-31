"""Unit tests for Arena Steering Markdown parser and domain services."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

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
  assert detail == "We should use this execution mode: Fast mode"
  assert any(block_type == "field" for block_type, _ in blocks)


def _publish_answer_message_report(reports: ReportService) -> None:
  reports.publish_report(
    "decision",
    "A decision",
    (
      '<!-- question {"id": "choice", "label": "Choice?"} -->\n'
      "Choice?\n"
      '- ( ) A <!-- option {"label": "A"} -->\n'
      '- ( ) B <!-- option {"label": "B"} -->\n'
    ),
  )


def test_report_answers_are_hidden_messages_with_newest_only_delivery() -> None:
  store = SqliteStore(":memory:")
  reports = ReportService(store, store)
  messages = MessageService(store, store, store)
  _publish_answer_message_report(reports)
  ordinary = messages.send_message("Quiet note", hidden=True, msg_id="de1000")
  first = reports.submit_answer("decision", {"choice": "A"}, answer_id="de1001")
  latest = reports.submit_answer("decision", {"choice": "B"}, answer_id="de1002")

  first_message = store.get_message(first.id)
  latest_message = store.get_message(latest.id)
  assert (
    first_message is not None and first_message.hidden and not first_message.blocking
  )
  assert (
    latest_message is not None and latest_message.hidden and latest_message.blocking
  )
  assert latest.id in messages.pending_ids() and first.id not in messages.pending_ids()
  delivered = messages.read_pending(mark_seen=True)
  assert [item.id for item in delivered["messages"]] == [ordinary.id]
  assert [answer.id for _, answer in delivered["report_answers"]] == [latest.id]
  assert messages.ack(ordinary.id, "Quiet note read")[0] == "message"
  assert store.get_message(first.id).status == "sent"
  assert store.get_message(latest.id).status == "seen"
  assert reports.get_report("decision").answers[-1].status == "seen"

  target_type, answer = messages.ack(None, "Reviewed")
  assert target_type == "report_answer" and answer.id == latest.id
  assert store.get_message(latest.id).acks == ["Reviewed"]
  assert reports.get_report("decision").answers[-1].acks == ["Reviewed"]
  assert not messages.has_pending_deliverables()
  store.close()


def test_report_answer_survives_report_deletion_and_republication() -> None:
  store = SqliteStore(":memory:")
  reports = ReportService(store, store)
  messages = MessageService(store, store, store)
  _publish_answer_message_report(reports)
  answer = reports.submit_answer("decision", {"choice": "A"}, answer_id="de2001")

  # Simulate removal without the service's existing pending-answer guard.
  assert store.delete_report("decision")
  delivered = messages.read_pending(mark_seen=True)
  assert [
    (report.id, report.title, item.id) for report, item in delivered["report_answers"]
  ] == [("decision", "A decision", answer.id)]
  assert messages.ack(answer.id, "Still available")[0] == "report_answer"
  _publish_answer_message_report(reports)
  restored = reports.get_report("decision").answers
  assert [item.id for item in restored] == [answer.id]
  assert restored[0].acks == ["Still available"]
  store.close()


def test_report_answer_survives_snapshot_merge_after_report_deletion() -> None:
  source = SqliteStore(":memory:")
  reports = ReportService(source, source)
  _publish_answer_message_report(reports)
  answer = reports.submit_answer("decision", {"choice": "B"}, answer_id="de3001")
  assert source.delete_report("decision")
  snapshot = source.export_rows()
  assert any(row["id"] == answer.id for row in snapshot["messages"])

  target = SqliteStore(":memory:")
  target.merge_rows(snapshot)
  messages = MessageService(target, target, target)
  delivered = messages.read_pending(mark_seen=False)
  assert [(report.id, item.id) for report, item in delivered["report_answers"]] == [
    ("decision", answer.id)
  ]
  assert messages.ack(answer.id, "Merged")[0] == "report_answer"
  _publish_answer_message_report(ReportService(target, target))
  assert ReportService(target, target).get_report("decision").answers[0].acks == [
    "Merged"
  ]
  source.close()
  target.close()


def test_snapshot_merge_preserves_newest_answer_order() -> None:
  source = SqliteStore(":memory:")
  reports = ReportService(source, source)
  _publish_answer_message_report(reports)
  first = reports.submit_answer("decision", {"choice": "A"}, answer_id="de3101")
  newest = reports.submit_answer("decision", {"choice": "B"}, answer_id="de3102")
  rows = source.export_rows()
  answer_rows = {row["id"]: row for row in rows["messages"]}

  target = SqliteStore(":memory:")
  target.merge_rows({"reports": rows["reports"], "messages": [answer_rows[newest.id]]})
  target.merge_rows({"messages": [answer_rows[first.id]]})
  assert [item.id for item in target.get_report("decision").answers] == [
    first.id,
    newest.id,
  ]
  messages = MessageService(target, target, target)
  assert [
    item.id for _, item in messages.read_pending(mark_seen=False)["report_answers"]
  ] == [newest.id]
  source.close()
  target.close()


def test_snapshot_answer_order_is_stable_for_equal_creation_times() -> None:
  import json

  source = SqliteStore(":memory:")
  reports = ReportService(source, source)
  _publish_answer_message_report(reports)
  reports.submit_answer("decision", {"choice": "A"}, answer_id="de3151")
  reports.submit_answer("decision", {"choice": "B"}, answer_id="de3152")
  rows = source.export_rows()["messages"]
  for row in rows:
    data = json.loads(row["answer_json"])
    data["created_at"] = "2026-01-01T00:00:00.000000Z"
    row["answer_json"] = json.dumps(data)

  left, right = SqliteStore(":memory:"), SqliteStore(":memory:")
  left.merge_rows({"messages": rows})
  right.merge_rows({"messages": list(reversed(rows))})
  assert [answer.id for answer in left.list_report_answers()] == [
    answer.id for answer in right.list_report_answers()
  ]
  source.close()
  left.close()
  right.close()


def test_snapshot_merge_uses_newer_answer_row_even_if_a_reply_is_lost() -> None:
  import json
  from copy import deepcopy

  source = SqliteStore(":memory:")
  reports = ReportService(source, source)
  _publish_answer_message_report(reports)
  answer = reports.submit_answer("decision", {"choice": "A"}, answer_id="de3201")
  snapshot = source.export_rows()
  older = deepcopy(snapshot["messages"][0])
  older["modified_at"] = "2030-01-01T00:00:00Z"
  acked = deepcopy(older)
  acked.update(
    status="acked", acks_json=json.dumps(["Read"]), modified_at="2031-01-01T00:00:00Z"
  )
  newer_without_reply = deepcopy(older)
  newer_without_reply["modified_at"] = "2032-01-01T00:00:00Z"

  target = SqliteStore(":memory:")
  target.merge_rows({"reports": snapshot["reports"], "messages": [older]})
  target.merge_rows({"messages": [acked]})
  target.merge_rows({"messages": [older]})
  assert target.get_report("decision").answers[0].acks == ["Read"]
  target.merge_rows({"messages": [newer_without_reply]})
  merged = target.get_report("decision").answers[0]
  assert merged.id == answer.id and merged.acks == [] and merged.status == "sent"
  source.close()
  target.close()


def test_report_answer_rename_preserves_its_hidden_message() -> None:
  class Clock:
    value = "2026-01-01T00:00:00Z"

    def now_iso(self) -> str:
      return self.value

  clock = Clock()
  store = SqliteStore(":memory:")
  reports = ReportService(store, store, clock=clock)
  messages = MessageService(store, store, store)
  _publish_answer_message_report(reports)
  answer = reports.submit_answer("decision", {"choice": "A"}, answer_id="de3501")
  clock.value = "2026-01-01T00:01:00Z"
  renamed = reports.rename_report("decision", "renamed")
  assert renamed.answers == reports.get_report("renamed").answers

  message = store.get_message(answer.id)
  assert message is not None and message.hidden and message.type == "report_answer"
  assert message.as_report_answer().report_id == "renamed"
  delivered = messages.read_pending(mark_seen=False)["report_answers"]
  assert [(report.id, item.id) for report, item in delivered] == [
    ("renamed", answer.id)
  ]
  assert messages.ack(answer.id, "Read after rename")[0] == "report_answer"
  assert reports.get_report("renamed").answers[0].acks == ["Read after rename"]
  _publish_answer_message_report(reports)
  assert reports.get_report("decision").answers == []
  store.close()


def test_report_answers_share_the_message_id_namespace() -> None:
  store = SqliteStore(":memory:")
  reports = ReportService(store, store)
  messages = MessageService(store, store, store)
  _publish_answer_message_report(reports)
  messages.send_message("Ordinary", msg_id="de4001")
  with pytest.raises(ValueError):
    reports.submit_answer("decision", {"choice": "A"}, answer_id="de4001")
  assert messages.get_message("de4001").body == "Ordinary"
  assert reports.get_report("decision").answers == []

  reports.submit_answer("decision", {"choice": "B"}, answer_id="de4002")
  with pytest.raises(ValueError):
    messages.send_message("Do not overwrite an answer", msg_id="de4002")
  assert reports.get_report("decision").answers[0].values == {"choice": "B"}
  store.close()


def test_generated_report_answer_ids_skip_existing_messages() -> None:
  class Ids:
    values = iter(["de5001", "de5002"])

    def new_hex_id(self) -> str:
      return next(self.values)

  store = SqliteStore(":memory:")
  messages = MessageService(store, store, store)
  reports = ReportService(store, store, id_gen=Ids())
  _publish_answer_message_report(reports)
  messages.send_message("Existing message", msg_id="de5001")
  answer = reports.submit_answer("decision", {"choice": "A"})
  assert answer.id == "de5002"
  assert store.get_message("de5001").body == "Existing message"
  assert store.get_message(answer.id).type == "report_answer"
  store.close()


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
    (
      '<!-- question {"id": "we-should-use-this-database", "label": "We should use this database"} -->\n'
      "We should use this database\n"
      '- (x) SQLite <!-- option {"label": "SQLite"} -->\n'
      '- ( ) JSON <!-- option {"label": "JSON"} -->\n'
    ),
  )
  tasks.mod_links_add("task-b", "design-doc")
  assert tasks.get_task("task-b")[1] is True

  ans = reports.submit_answer(
    "design-doc",
    {"we-should-use-this-database": "SQLite"},
    answer_id="dead01",
  )
  assert ans.status == "sent"
  assert "We should use this database: SQLite" in tasks.get_task("task-b")[0].details
  assert tasks.get_task("task-b")[1] is False

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
    (
      '<!-- question {"id": "we-should-use-this-mode", "label": "We should use this mode"} -->\n'
      "We should use this mode\n"
      '- (x) Live <!-- option {"label": "Live"} -->\n'
      '- ( ) Manual <!-- option {"label": "Manual"} -->\n'
    ),
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


def test_task_answer_details_survive_report_removal_and_edits(tmp_path) -> None:
  from io import StringIO

  from arena_steering.cli import _print_single_task, _print_task_list

  path = tmp_path / "snapshots.sqlite3"
  store = SqliteStore(path)
  reports = ReportService(store, store)
  tasks = TaskService(store, store)
  reports.publish_report(
    "decision",
    "Original decision",
    (
      '<!-- question {"id": "choice", "label": "Choice?"} -->\n'
      "Choice?\n"
      '- ( ) A <!-- option {"label": "A"} -->\n'
      '- ( ) B <!-- option {"label": "B"} -->\n'
    ),
  )
  tasks.create_task(
    "work", "Do work", details=["Act on the answer"], report_ids=["decision"]
  )
  first = reports.submit_answer("decision", {"choice": "A"}, answer_id="ab0001")
  reports.ack_answer("decision", first.id, "Read")
  second = reports.submit_answer("decision", {"choice": "A"}, answer_id="ab0002")
  reports.ack_answer("decision", second.id, "Read")
  details = tasks.get_task("work")[0].details
  assert details == ["Act on the answer", "Choice?: A", "Choice?: A"]
  tasks.mod_scalar("work", "title", "Updated work")
  tasks.mod_deets("work", "Another detail")
  tasks.patch_task("work", {"scope": "test"})
  tasks.rename_task("work", "renamed")
  reports.remove_report("decision")
  store.close()

  reopened = SqliteStore(path)
  task = reopened.get_task("renamed")
  assert task is not None and task.details == [*details, "Another detail"]
  assert task.report_ids == []
  out = StringIO()
  _print_task_list([(task, False)], out)
  _print_single_task(task, False, out)
  text = out.getvalue()
  assert text.count("Choice?: A") == 4
  assert first.id not in text and second.id not in text
  reopened.close()


def test_linking_an_answered_report_copies_details_each_time(tmp_path) -> None:
  store = SqliteStore(tmp_path / "link.sqlite3")
  reports = ReportService(store, store)
  tasks = TaskService(store, store)
  reports.publish_report(
    "decision",
    "Decision",
    (
      '<!-- question {"id": "choice", "label": "Choice?"} -->\n'
      "Choice?\n"
      '- ( ) A <!-- option {"label": "A"} -->\n'
      '- ( ) B <!-- option {"label": "B"} -->\n'
    ),
  )
  answer = reports.submit_answer("decision", {"choice": "B"}, answer_id="cd0001")
  reports.ack_answer("decision", answer.id, "Read")
  tasks.create_task("work", "Do work", details=["Act on the answer"])
  tasks.mod_links_add("work", "decision", link_type="report")
  task = tasks.get_task("work")[0]
  assert task.report_ids == ["decision"]
  assert task.details == ["Act on the answer", "Choice?: B"]
  tasks.mod_links_add("work", "decision", link_type="report")
  assert tasks.get_task("work")[0].details == task.details
  reports.submit_answer("decision", {"choice": "A"}, answer_id="cd0002")
  assert tasks.get_task("work")[0].details == [
    "Act on the answer",
    "Choice?: B",
    "Choice?: A",
  ]
  tasks.mod_links_rm("work", "report", "decision")
  tasks.mod_links_add("work", "decision", link_type="report")
  assert tasks.get_task("work")[0].details == [
    "Act on the answer",
    "Choice?: B",
    "Choice?: A",
    "Choice?: B",
    "Choice?: A",
  ]
  reports.rename_report("decision", "renamed-decision")
  assert tasks.get_task("work")[0].details == [
    "Act on the answer",
    "Choice?: B",
    "Choice?: A",
    "Choice?: B",
    "Choice?: A",
  ]
  store.close()


def test_task_details_keep_original_labels_after_republish(tmp_path) -> None:
  store = SqliteStore(tmp_path / "labels.sqlite3")
  reports = ReportService(store, store)
  tasks = TaskService(store, store)
  reports.publish_report(
    "decision",
    "Original title",
    (
      '<!-- question {"id": "field", "label": "Original label?"} -->\n'
      "Original label?\n"
      '- ( ) A <!-- option {"label": "A"} -->\n'
      '- ( ) B <!-- option {"label": "B"} -->\n'
    ),
  )
  tasks.create_task("work", "Do work", details=["Review"], report_ids=["decision"])
  answer = reports.submit_answer("decision", {"field": "A"}, answer_id="ba1001")
  reports.ack_answer("decision", answer.id, "Read")
  reports.publish_report(
    "decision",
    "New title",
    (
      '<!-- question {"id": "field", "label": "New label?"} -->\n'
      "New label?\n"
      '- ( ) A <!-- option {"label": "A"} -->\n'
      '- ( ) B <!-- option {"label": "B"} -->\n'
    ),
  )
  reports.submit_answer("decision", {"field": "B"}, answer_id="ba1002")
  task = tasks.get_task("work")[0]
  assert task.details == ["Review", "Original label?: A", "New label?: B"]
  created = tasks.create_task(
    "created-later", "Created later", details=["Review"], report_ids=["decision"]
  )
  assert created.details == ["Review", "Original label?: A", "New label?: B"]
  tasks.create_task("patched-later", "Patched later", details=["Review"])
  patched = tasks.patch_task("patched-later", {"links": {"report_ids": ["decision"]}})
  assert patched.details == ["Review", "Original label?: A", "New label?: B"]
  patched = tasks.patch_task("patched-later", {"report_ids": ["decision"]})
  assert patched.details == ["Review", "Original label?: A", "New label?: B"]
  tasks.patch_task("patched-later", {"report_ids": []})
  patched = tasks.patch_task("patched-later", {"report_ids": ["decision"]})
  assert patched.details == [
    "Review",
    "Original label?: A",
    "New label?: B",
    "Original label?: A",
    "New label?: B",
  ]
  store.close()


def test_concurrent_report_answers_append_distinct_details(tmp_path) -> None:
  from concurrent.futures import ThreadPoolExecutor
  from threading import Barrier

  path = tmp_path / "parallel-answers.sqlite3"
  stores = [SqliteStore(path), SqliteStore(path)]
  reports = [ReportService(store, store) for store in stores]
  tasks = TaskService(stores[0], stores[0])
  reports[0].publish_report(
    "choice",
    "Choice",
    (
      '<!-- question {"id": "select", "label": "Select?"} -->\n'
      "Select?\n"
      '- ( ) Yes <!-- option {"label": "Yes"} -->\n'
      '- ( ) No <!-- option {"label": "No"} -->\n'
    ),
  )
  tasks.create_task("work", "Work", details=["Review"], report_ids=["choice"])
  barrier = Barrier(2)

  def submit(index):
    barrier.wait()
    return reports[index].submit_answer(
      "choice", {"select": "Yes"}, answer_id=f"ab44{index:02d}"
    )

  with ThreadPoolExecutor(max_workers=2) as pool:
    answers = list(pool.map(submit, range(2)))
  report = reports[0].get_report("choice")
  task = tasks.get_task("work")[0]
  assert {item.id for item in report.answers} == {item.id for item in answers}
  assert task.details == ["Review", "Select?: Yes", "Select?: Yes"]
  for store in stores:
    store.close()


def test_removing_answer_details_keeps_answers_and_report_links(tmp_path) -> None:
  path = tmp_path / "unlink-answer.sqlite3"
  store = SqliteStore(path)
  reports = ReportService(store, store)
  tasks = TaskService(store, store)
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
  first = reports.submit_answer("decision", {"select": "Yes"}, answer_id="ac0001")
  second = reports.submit_answer("decision", {"select": "No"}, answer_id="ac0002")
  reports.ack_answer("decision", second.id, "Read")
  assert tasks.get_task("work")[0].details == ["Review", "Select?: Yes", "Select?: No"]
  tasks.mod_deets_rm("work", 2)
  task = tasks.get_task("work")[0]
  assert task.report_ids == ["decision"]
  assert task.details == ["Review", "Select?: No"]
  stored = reports.get_report("decision").answers
  assert [item.id for item in stored] == [first.id, second.id]
  assert stored[0].created_at == first.created_at
  assert stored[1].acks == ["Read"]

  tasks.mod_scalar("work", "title", "Renamed work")
  tasks.mod_links_rm("work", "report", "decision")
  tasks.mod_links_add("work", "decision", link_type="report")
  relinked_details = ["Review", "Select?: No", "Select?: Yes", "Select?: No"]
  assert tasks.get_task("work")[0].details == relinked_details
  store.close()

  reopened = SqliteStore(path)
  task = TaskService(reopened, reopened).get_task("work")[0]
  assert task.details == relinked_details
  assert task.report_ids == ["decision"]
  reopened.close()


def test_report_blocking_follows_answer_need_not_acknowledgement() -> None:
  store = SqliteStore(":memory:")
  tasks = TaskService(store, store)
  reports = ReportService(store, store)
  reports.publish_report("plain", "Plain", "# No questions")
  reports.publish_report(
    "question",
    "Question",
    (
      '<!-- question {"id": "choice", "label": "Choice?"} -->\n'
      "Choice?\n"
      '- ( ) Yes <!-- option {"label": "Yes"} -->\n'
    ),
  )
  tasks.create_task("work", "Work", details=["Review"], report_ids=["plain"])
  assert tasks.get_task("work")[1] is False
  tasks.mod_links_add("work", "question", link_type="report")
  assert tasks.get_task("work")[1] is True
  reports.submit_answer("question", {"choice": "Yes"}, answer_id="b20001")
  assert tasks.get_task("work")[1] is False
  assert reports.get_report("question").latest_unacked_answer is not None
  with pytest.raises(ValueError, match="Invalid Task.status"):
    tasks.mod_scalar("work", "status", "blocked")
  with pytest.raises(ValueError, match="Invalid Task.status"):
    tasks.create_task("manual-block", "Manual", status="blocked", details=["Review"])
  store.close()


def test_report_answers_append_full_details_for_each_submission(tmp_path) -> None:
  path = tmp_path / "details.sqlite3"
  store = SqliteStore(path)
  tasks = TaskService(store, store)
  reports = ReportService(store, store)
  option = "A" * 180
  other = "B" * 170
  reports.publish_report(
    "question",
    "Question",
    (
      '<!-- question {"id": "choice", "label": "Choice?"} -->\n'
      "Choice?\n"
      f'- ( ) {option} <!-- option {{"label": "{option}"}} -->\n'
      '\n<!-- question {"id": "second", "label": "Second?"} -->\n'
      "Second?\n"
      f'- ( ) {other} <!-- option {{"label": "{other}"}} -->\n'
    ),
  )
  for task_id in ("one", "two"):
    tasks.create_task(task_id, task_id, details=["Review"], report_ids=["question"])
  values = {"choice": option, "second": other}
  reports.submit_answer("question", values, answer_id="b20002")
  reports.submit_answer("question", values, answer_id="b20003")
  expected = ["Review", f"Choice?: {option}", f"Second?: {other}"]
  expected.extend([f"Choice?: {option}", f"Second?: {other}"])
  for task_id in ("one", "two"):
    task = tasks.get_task(task_id)[0]
    assert task.details == expected
    assert "answer_snapshots" not in task.to_dict()
  tasks.mod_deets_rm("one", 2)
  tasks.mod_scalar("one", "title", "Renamed")
  tasks.mod_deets("one", "Short addition")
  tasks.patch_task("one", {"scope": "checked"})
  tasks.rename_task("one", "renamed")
  store.close()
  reopened = SqliteStore(path)
  task = reopened.get_task("renamed")
  assert task is not None
  assert task.details == [*expected[:1], *expected[2:], "Short addition"]
  reopened.close()


def test_manual_task_detail_limit_survives_generated_long_detail(tmp_path) -> None:
  store = SqliteStore(tmp_path / "manual-limit.sqlite3")
  tasks = TaskService(store, store)
  reports = ReportService(store, store)
  option = "A" * 180
  reports.publish_report(
    "choice",
    "Choice",
    (
      '<!-- question {"id": "choice", "label": "Choice"} -->\n'
      "Choice\n"
      f'- ( ) {option} <!-- option {{"label": "{option}"}} -->\n'
    ),
  )
  with pytest.raises(ValueError, match="120"):
    tasks.create_task("bad", "Bad", details=["x" * 121])
  tasks.create_task("work", "Work", details=["Review"], report_ids=["choice"])
  reports.submit_answer("choice", {"choice": option}, answer_id="b20004")
  with pytest.raises(ValueError, match="120"):
    tasks.mod_deets("work", "x" * 121)
  with pytest.raises(ValueError, match="120"):
    tasks.patch_task("work", {"details": ["x" * 121]})
  details = tasks.get_task("work")[0].details
  assert details[1] == f"Choice: {option}"
  with pytest.raises(ValueError, match="120"):
    tasks.patch_task("work", {"details": [*details, details[1]]})
  tasks.patch_task("work", {"details": [*details, "Short"]})
  assert tasks.get_task("work")[0].details == [*details, "Short"]
  store.close()


class _ReportTestClock:
  def __init__(self) -> None:
    self.current = datetime(2026, 1, 1, tzinfo=UTC)

  def now_iso(self) -> str:
    return self.current.isoformat().replace("+00:00", "Z")

  def advance(self, **kwargs: int) -> None:
    self.current += timedelta(**kwargs)


def test_unlinked_report_staleness_uses_latest_publication_or_view() -> None:
  store = SqliteStore(":memory:")
  clock = _ReportTestClock()
  reports = ReportService(store, store, clock=clock)
  reports.publish_report("idle-report", "Idle report", "# Idle")

  clock.advance(minutes=29, seconds=59)
  assert reports.list_reports(stale_only=True) == []
  clock.advance(seconds=1)
  assert [report.id for report in reports.list_reports(stale_only=True)] == [
    "idle-report"
  ]

  reports.mark_seen("idle-report")
  clock.advance(minutes=30)
  assert [report.id for report in reports.list_reports(stale_only=True)] == [
    "idle-report"
  ]
  reports.mark_seen("idle-report")
  assert reports.list_reports(stale_only=True) == []
  clock.advance(minutes=30)
  reports.publish_report("idle-report", "Updated report", "# Updated")
  assert reports.list_reports(stale_only=True) == []
  store.close()


def test_report_view_timestamp_syncs_with_incremental_state() -> None:
  source = SqliteStore(":memory:")
  target = SqliteStore(":memory:")
  clock = _ReportTestClock()
  reports = ReportService(source, source, clock=clock)
  reports.publish_report("idle-report", "Idle report", "# Idle")
  before_view = clock.now_iso()
  target.merge_rows(source.export_rows())

  clock.advance(minutes=1)
  reports.mark_seen("idle-report")
  changes = source.export_rows(since=before_view)
  assert [row["id"] for row in changes["reports"]] == ["idle-report"]
  target.merge_rows(changes)
  assert target.get_report("idle-report").last_viewed_at == clock.now_iso()
  source.close()
  target.close()


def test_report_pin_and_linked_task_staleness_survive_restart(tmp_path) -> None:
  db_file = tmp_path / "stale.sqlite3"
  store = SqliteStore(db_file)
  clock = _ReportTestClock()
  reports = ReportService(store, store, clock=clock)
  tasks = TaskService(store, store, clock=clock)
  reports.publish_report("idle-report", "Idle report", "# Idle")
  reports.publish_report("linked-report", "Linked report", "# Linked")
  reports.pin_report("idle-report", True)
  tasks.create_task("first", "First", details=["First"], report_ids=["linked-report"])
  tasks.create_task(
    "second", "Second", details=["Second"], report_ids=["linked-report"]
  )

  clock.advance(hours=2)
  tasks.mod_scalar("first", "status", "finished")
  assert reports.list_reports(stale_only=True) == []
  tasks.mod_scalar("second", "status", "finished")
  assert [report.id for report in reports.list_reports(stale_only=True)] == [
    "linked-report"
  ]
  reports.pin_report("linked-report", True)
  reports.publish_report("linked-report", "Revised", "# Revised")
  assert reports.get_report("linked-report").pinned is True
  reports.rename_report("linked-report", "renamed-report")
  assert reports.get_report("renamed-report").pinned is True
  assert reports.list_reports(stale_only=True) == []
  store.close()

  store = SqliteStore(db_file)
  reports = ReportService(store, store, clock=clock)
  assert reports.get_report("idle-report").pinned is True
  assert reports.get_report("renamed-report").pinned is True
  reports.pin_report("idle-report", False)
  assert [report.id for report in reports.list_reports(stale_only=True)] == [
    "idle-report"
  ]
  reports.pin_report("renamed-report", False)
  assert {report.id for report in reports.list_reports(stale_only=True)} == {
    "idle-report",
    "renamed-report",
  }
  store.close()


def test_stale_report_removal_retains_a_pending_answer() -> None:
  store = SqliteStore(":memory:")
  clock = _ReportTestClock()
  reports = ReportService(store, store, clock=clock)
  messages = MessageService(store, store, store, clock=clock)
  reports.publish_report(
    "answered-report",
    "Answered report",
    (
      '<!-- question {"id": "choice", "label": "Choice?"} -->\n'
      "Choice?\n"
      '- ( ) Yes <!-- option {"label": "Yes"} -->\n'
    ),
  )
  reports.submit_answer("answered-report", {"choice": "Yes"}, answer_id="abc123")
  clock.advance(minutes=30)
  assert [report.id for report in reports.list_reports(stale_only=True)] == [
    "answered-report"
  ]
  assert reports.remove_report("--stale") == ["answered-report"]
  assert "abc123" in messages.pending_ids()
  delivered = messages.read_pending(mark_seen=False)
  assert [answer.id for _, answer in delivered["report_answers"]] == ["abc123"]
  messages.ack("abc123", "Noted.")
  assert "abc123" not in messages.pending_ids()
  store.close()


def test_linking_existing_long_answer_bypasses_manual_detail_limit() -> None:
  store = SqliteStore(":memory:")
  reports = ReportService(store, store)
  tasks = TaskService(store, store)
  reports.publish_report(
    "decision",
    "Decision",
    (
      '<!-- question {"id": "choice", "label": "Choice?"} -->\n'
      "Choice?\n"
      '- ( ) A <!-- option {"label": "A"} -->\n'
    ),
  )
  long_answer = "a" * 180
  reports.submit_answer("decision", {"choice": long_answer}, answer_id="ab0099")
  created = tasks.create_task(
    "work", "Work", details=["Review"], report_ids=["decision"]
  )
  assert len(created.details[1]) > 120 and long_answer in created.details[1]
  tasks.patch_task("work", {"scope": "Updated"})
  with pytest.raises(ValueError, match="exceeds 120"):
    tasks.create_task("invalid", "Invalid", details=[long_answer])
  store.close()


def test_replaced_answer_stays_nonblocking_after_report_rename() -> None:
  store = SqliteStore(":memory:")
  reports = ReportService(store, store)
  _publish_answer_message_report(reports)
  first = reports.submit_answer("decision", {"choice": "A"}, answer_id="de4001")
  newest = reports.submit_answer("decision", {"choice": "B"}, answer_id="de4002")
  reports.rename_report("decision", "renamed-decision")
  assert not store.get_message(first.id).blocking
  assert store.get_message(newest.id).blocking
  store.close()
