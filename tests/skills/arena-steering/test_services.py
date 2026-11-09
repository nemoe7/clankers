"""Steering regression tests."""

from __future__ import annotations

import io
import json
import os
import sqlite3
import subprocess
import threading
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from pathlib import Path

import pytest
from arena_steering import cli
from arena_steering.markdown_fields import (
  format_answer_for_task_detail,
  parse_report_markdown,
)
from arena_steering.models import Attachment, Task
from arena_steering.server import SteeringApp, create_http_server
from arena_steering.services import (
  MessageService,
  ReportService,
  TaskService,
  with_bible_read,
)
from arena_steering.store import SqliteStore


@pytest.mark.parametrize(
  "markdown",
  [
    "Choice?\n- (x) Yes\n- ( ) No\n",
    "Checks\n- [x] Unit tests\n- [ ] Lint\n",
    "Summary note: ___\n",
    '```markdown\n<!-- question {"id":"sample","label":"Sample"} -->\nSample: ___\n```\n',
  ],
)
def test_unannotated_controls_remain_plain_markdown(markdown: str) -> None:
  blocks, fields = parse_report_markdown(markdown)
  assert fields == []
  assert blocks == [("markdown", markdown.rstrip("\n"))]


def test_parse_report_markdown_extracts_choice_checkbox_and_text_fields() -> None:
  md = """# Steering Report

<!-- question {"id":"we-should-use-this-execution-mode","label":"We should use this execution mode"} -->
We should use this execution mode
- (x) Fast mode <!-- option {"label":"Fast mode"} -->
- ( ) Safe mode <!-- option {"label":"Safe mode"} -->

<!-- question {"id":"checks-to-run","label":"We should run these checks"} -->
We should run these checks
- [x] Unit tests <!-- option {"label":"Unit tests"} -->
- [ ] Prose lint <!-- option {"label":"Prose lint"} -->

<!-- question {"id":"summary-note","label":"Summary note"} -->
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
      '- (x) A <!-- option {"label": "A"} -->\n'
      '- ( ) B <!-- option {"label": "B"} -->\n'
    ),
  )


def test_report_answers_are_hidden_messages_with_newest_only_delivery() -> None:
  store = SqliteStore(":memory:")
  reports = ReportService(store, store)
  messages = MessageService(store, store, store, store)
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


def test_removed_answers_stay_orphaned_after_republish() -> None:
  store = SqliteStore(":memory:")
  reports = ReportService(store, store)
  messages = MessageService(store, store, store, store)
  _publish_answer_message_report(reports)
  old_answer = reports.submit_answer("decision", {"choice": "A"}, answer_id="de2001")

  assert reports.remove_report("decision") == ["decision"]
  assert store.list_report_answers("decision") == []
  orphan = store.list_report_answers(include_orphaned=True)[0]
  assert orphan.id == old_answer.id and orphan.orphaned
  _publish_answer_message_report(reports)
  assert reports.get_report("decision").answers == []
  new_answer = reports.submit_answer("decision", {"choice": "B"}, answer_id="de2002")
  delivered = messages.read_pending(mark_seen=True)
  assert [
    (report.title, answer.id) for report, answer in delivered["report_answers"]
  ] == [
    ("A decision", old_answer.id),
    ("A decision", new_answer.id),
  ]
  assert messages.ack(old_answer.id, "Still available")[0] == "report_answer"
  assert reports.get_report("decision").answers[0].id == new_answer.id
  assert reports.get_report("decision").answers[0].acks == []
  assert messages.ack(new_answer.id, "New decision")[0] == "report_answer"
  assert reports.get_report("decision").answers[0].acks == ["New decision"]
  store.close()


def test_legacy_removed_report_answers_orphan_on_republication() -> None:
  store = SqliteStore(":memory:")
  reports = ReportService(store, store)
  _publish_answer_message_report(reports)
  body = reports.get_report("decision").body
  reports.submit_answer("decision", {"choice": "A"}, answer_id="de2006")
  with store.transaction():
    store._conn.execute("DELETE FROM reports WHERE id = 'decision'")
  assert [answer.id for answer in store.list_report_answers("decision")] == ["de2006"]

  assert reports.publish_report("decision", "New decision", body).answers == []
  assert store.list_report_answers("decision") == []
  assert store.list_report_answers(include_orphaned=True)[0].orphaned
  delivered = MessageService(store, store, store, store).read_pending(mark_seen=False)
  assert [report.title for report, _ in delivered["report_answers"]] == ["A decision"]
  store.close()


def test_repeated_same_id_removal_keeps_each_pending_orphan_deliverable() -> None:
  store = SqliteStore(":memory:")
  reports = ReportService(store, store)
  messages = MessageService(store, store, store, store)
  _publish_answer_message_report(reports)
  body = reports.get_report("decision").body
  reports.submit_answer("decision", {"choice": "A"}, answer_id="de2003")
  reports.remove_report("decision")
  reports.publish_report("decision", "Second", body)
  reports.submit_answer("decision", {"choice": "B"}, answer_id="de2004")
  reports.remove_report("decision")
  reports.publish_report("decision", "Third", body)
  reports.submit_answer("decision", {"choice": "A"}, answer_id="de2005")

  delivered = messages.read_pending(mark_seen=False)["report_answers"]
  assert [(report.title, answer.id) for report, answer in delivered] == [
    ("A decision", "de2003"),
    ("Second", "de2004"),
    ("Third", "de2005"),
  ]
  messages.ack("de2003", "Old")
  assert [answer.id for answer in reports.get_report("decision").answers] == ["de2005"]
  assert messages.pending_ids() == ["de2004", "de2005"]
  store.close()


def test_answered_report_body_is_locked_but_owner_can_revise_answers() -> None:
  store = SqliteStore(":memory:")
  reports = ReportService(store, store)
  _publish_answer_message_report(reports)
  body = reports.get_report("decision").body
  first = reports.submit_answer("decision", {"choice": "A"}, answer_id="de2011")
  with pytest.raises(ValueError, match="Cannot edit report body after an answer"):
    reports.publish_report("decision", "Changed", body + "\nNew instructions")
  assert reports.publish_report("decision", "Retitled", body).answers[0].id == first.id
  reports.ack_answer("decision", first.id, "Read")

  with pytest.raises(ValueError, match="Cannot edit report body after an answer"):
    reports.publish_report("decision", "Changed", body + "\nNew instructions")
  assert reports.get_report("decision").body == body
  reports.publish_report("decision", "Retitled", body)
  revised = reports.submit_answer("decision", {"choice": "B"}, answer_id="de2012")
  assert [answer.id for answer in reports.get_report("decision").answers] == [
    first.id,
    revised.id,
  ]
  store.close()


def test_unpublish_answered_report_detaches_task_links_without_losing_answers() -> None:
  store = SqliteStore(":memory:")
  reports = ReportService(store, store)
  tasks = TaskService(store, store)
  _publish_answer_message_report(reports)
  tasks.create_task(
    "work", "Do work", size=3, details=["Review"], report_ids=["decision"]
  )
  answer = reports.submit_answer("decision", {"choice": "A"}, answer_id="de2021")
  reports.ack_answer("decision", answer.id, "Read")
  details = tasks.get_task("work")[0].details
  assert details == ["Review", "Choice?: A"]

  unpublished = reports.unpublish_report("decision")
  assert unpublished.status == "dismissed"
  assert [item.id for item in unpublished.answers] == [answer.id]
  task = tasks.get_task("work")[0]
  assert task.report_ids == [] and task.details == details
  assert store.list_report_answers("decision")[0].acks == ["Read"]
  with pytest.raises(ValueError, match="Cannot edit report body after an answer"):
    reports.publish_report("decision", "Changed", unpublished.body + "\nNew")
  assert reports.remove_report("decision") == ["decision"]
  assert store.list_report_answers("decision") == []
  assert store.list_report_answers(include_orphaned=True)[0].orphaned
  _publish_answer_message_report(reports)
  assert reports.get_report("decision").answers == []
  store.close()


def test_superseded_orphan_answers_stay_stored_without_redelivery() -> None:
  store = SqliteStore(":memory:")
  reports = ReportService(store, store)
  messages = MessageService(store, store, store, store)
  _publish_answer_message_report(reports)
  first = reports.submit_answer("decision", {"choice": "A"}, answer_id="de2031")
  latest = reports.submit_answer("decision", {"choice": "B"}, answer_id="de2032")
  assert reports.remove_report("decision") == ["decision"]
  assert [answer.id for answer in store.list_report_answers(include_orphaned=True)] == [
    first.id,
    latest.id,
  ]
  assert [answer.id for _, answer in messages.read_pending()["report_answers"]] == [
    latest.id
  ]
  messages.ack(latest.id, "Read")
  assert not messages.has_pending_deliverables()
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
  messages = MessageService(target, target, target, target)
  delivered = messages.read_pending(mark_seen=False)
  assert [(report.id, item.id) for report, item in delivered["report_answers"]] == [
    ("decision", answer.id)
  ]
  assert messages.ack(answer.id, "Merged")[0] == "report_answer"
  _publish_answer_message_report(ReportService(target, target))
  assert ReportService(target, target).get_report("decision").answers == []
  assert target.list_report_answers(include_orphaned=True)[0].acks == ["Merged"]
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
  messages = MessageService(target, target, target, target)
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
  messages = MessageService(store, store, store, store)
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
  messages = MessageService(store, store, store, store)
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
  messages = MessageService(store, store, store, store)
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
  svc = MessageService(store, store, store, store)

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


def test_clause_quiz_rejects_wrong_ack_without_changing_pending_state() -> None:
  store = SqliteStore()
  messages = MessageService(store, store, store, store)
  clause = "Keep the selected clause unchanged."
  path, line = "ARENA.md", 86
  quiz = messages.send_clause_quiz("Recall the selected clause", path, line, clause)
  delivered = messages.read_pending()["messages"]
  assert [item.id for item in delivered] == [quiz.id]
  assert messages.pending_ids() == [quiz.id]
  before = store.get_message(quiz.id).to_dict()
  for reply in (
    f"{path}:{line}",
    f"AGENTS.md:{line} {clause}",
    f"{path}:{line + 1} {clause}",
    f"{path}:{line} Wrong clause",
  ):
    with pytest.raises(ValueError):
      messages.ack(quiz.id, reply)
    assert store.get_message(quiz.id).to_dict() == before
    assert messages.pending_ids() == [quiz.id]
  reply = f"{path}:{line} {clause}"
  kind, acked = messages.ack(None, reply)
  assert kind == "message"
  assert acked.acks == [reply]
  assert messages.pending_ids() == []
  store.close()


def test_message_service_stores_parent_ids_for_multi_message_replies() -> None:
  store = SqliteStore(":memory:")
  svc = MessageService(store, store, store, store)

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
  with pytest.raises(KeyError, match="Unknown parent task ID"):
    svc.send_message("Missing task", parent_refs=[{"type": "task", "id": "missing"}])
  with pytest.raises(ValueError, match="parent type"):
    svc.send_message("Wrong type", parent_refs=[{"type": "unknown", "id": "abc123"}])
  with pytest.raises(KeyError, match="Unknown parent report ID"):
    svc.send_message(
      "Missing report", parent_refs=[{"type": "report", "id": "missing"}]
    )
  with pytest.raises(ValueError, match="Message.parent_refs"):
    svc.send_message("Invalid ID", parent_refs=[{"type": "task", "id": "not safe"}])

  store.close()


def test_task_service_mutable_dependency_queue_and_derived_blocking() -> None:
  store = SqliteStore(":memory:")
  tasks = TaskService(store, store)
  reports = ReportService(store, store)

  tasks.create_task("task-b", "Build consumer", size=3, details=["Build consumer."])
  tasks.create_task(
    "task-a", "Build foundation", size=3, type="ops", details=["Build foundation."]
  )
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
  assert (
    "We should use this database: SQLite" not in tasks.get_task("task-b")[0].details
  )
  assert tasks.get_task("task-b")[1] is False

  reports.ack_answer("design-doc", "dead01", "Confirmed SQLite.")
  assert "We should use this database: SQLite" in tasks.get_task("task-b")[0].details
  assert tasks.get_task("task-b")[1] is False

  tasks.mod_deets("task-b", "Added integration check.", size=3)
  count_before = len(tasks.get_task("task-b")[0].details)
  tasks.mod_deets_rm("task-b", count_before, size=3)
  assert len(tasks.get_task("task-b")[0].details) == count_before - 1

  with pytest.raises(ValueError, match="cycle"):
    tasks.mod_deps_add("task-a", "task-b")

  store.close()


def test_report_ack_seen_lifecycle() -> None:
  store = SqliteStore(":memory:")
  reports = ReportService(store, store)
  messages = MessageService(store, store, store, store)

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
  store.save_task_queue([Task(size=3, id="legacy-task", title="Legacy", details=[])])
  store.close()
  store = SqliteStore(path)
  tasks = TaskService(store, store)
  assert tasks.get_task("legacy-task")[0].details == []
  with pytest.raises(ValueError, match="at least one detail"):
    tasks.create_task("empty-task", "Empty", size=3)
  with pytest.raises(ValueError, match="at least one detail"):
    tasks.patch_task("legacy-task", {"title": "Changed"})
  assert tasks.get_task("legacy-task")[0].title == "Legacy"
  tasks.mod_deets("legacy-task", "Add a detail", size=3)
  with pytest.raises(ValueError, match="at least one detail"):
    tasks.mod_deets_rm("legacy-task", 1, size=3)
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
      '- (x) A <!-- option {"label": "A"} -->\n'
      '- ( ) B <!-- option {"label": "B"} -->\n'
    ),
  )
  tasks.create_task(
    "work", "Do work", size=3, details=["Act on the answer"], report_ids=["decision"]
  )
  first = reports.submit_answer("decision", {"choice": "A"}, answer_id="ab0001")
  reports.ack_answer("decision", first.id, "Read")
  second = reports.submit_answer("decision", {"choice": "A"}, answer_id="ab0002")
  reports.ack_answer("decision", second.id, "Read")
  details = tasks.get_task("work")[0].details
  assert details == ["Act on the answer", "Choice?: A"]
  tasks.mod_scalar("work", "title", "Updated work")
  tasks.mod_deets("work", "Another detail", size=3)
  tasks.patch_task("work", {"scope": "test"})
  tasks.rename_task("work", "renamed")
  reports.remove_report("decision")
  store.close()

  reopened = SqliteStore(path)
  task = reopened.get_task("renamed")
  assert task is not None and task.details == [*details, "Another detail"]
  assert task.report_ids == []
  summary = StringIO()
  _print_task_list([(task, False)], summary)
  assert summary.getvalue().splitlines() == ["renamed - Updated work"]
  out = StringIO()
  _print_single_task(task, False, out)
  text = out.getvalue()
  assert text.count("Choice?: A") == 1
  assert first.id not in text and second.id not in text
  reopened.close()


def test_linking_an_answered_report_backfills_details(tmp_path) -> None:
  store = SqliteStore(tmp_path / "link.sqlite3")
  reports = ReportService(store, store)
  tasks = TaskService(store, store)
  reports.publish_report(
    "decision",
    "Decision",
    (
      '<!-- question {"id": "choice", "label": "Choice?"} -->\n'
      "Choice?\n"
      '- (x) A <!-- option {"label": "A"} -->\n'
      '- ( ) B <!-- option {"label": "B"} -->\n'
    ),
  )
  answer = reports.submit_answer("decision", {"choice": "B"}, answer_id="cd0001")
  reports.ack_answer("decision", answer.id, "Read")
  tasks.create_task("work", "Do work", size=3, details=["Act on the answer"])
  tasks.mod_links_add("work", "decision", link_type="report")
  expected_after_first = ["Act on the answer", "Choice?: B"]
  task = tasks.get_task("work")[0]
  assert task.report_ids == ["decision"]
  assert task.details == expected_after_first
  tasks.mod_links_add("work", "decision", link_type="report")
  assert tasks.get_task("work")[0].details == expected_after_first
  second = reports.submit_answer("decision", {"choice": "A"}, answer_id="cd0002")
  assert tasks.get_task("work")[0].details == expected_after_first
  reports.ack_answer("decision", second.id, "Read")
  expected_details = [*expected_after_first, "Choice?: A"]
  assert tasks.get_task("work")[0].details == expected_details
  tasks.mod_links_rm("work", "report", "decision")
  tasks.mod_links_add("work", "decision", link_type="report")
  assert tasks.get_task("work")[0].details == expected_details
  reports.rename_report("decision", "renamed-decision")
  assert tasks.get_task("work")[0].details == expected_details
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
      '- (x) A <!-- option {"label": "A"} -->\n'
      '- ( ) B <!-- option {"label": "B"} -->\n'
    ),
  )
  tasks.create_task(
    "work", "Do work", size=3, details=["Review"], report_ids=["decision"]
  )
  answer = reports.submit_answer("decision", {"field": "A"}, answer_id="ba1001")
  reports.ack_answer("decision", answer.id, "Read")
  assert reports.remove_report("decision") == ["decision"]
  assert tasks.get_task("work")[0].report_ids == []
  assert tasks.get_task("work")[0].details == ["Review", "Original label?: A"]
  reports.publish_report(
    "decision",
    "New title",
    (
      '<!-- question {"id": "field", "label": "New label?"} -->\n'
      "New label?\n"
      '- (x) A <!-- option {"label": "A"} -->\n'
      '- ( ) B <!-- option {"label": "B"} -->\n'
    ),
  )
  assert reports.get_report("decision").answers == []
  tasks.mod_links_add("work", "decision", link_type="report")
  second = reports.submit_answer("decision", {"field": "B"}, answer_id="ba1002")
  reports.ack_answer("decision", second.id, "Read")
  task = tasks.get_task("work")[0]
  assert task.details == ["Review", "Original label?: A", "New label?: B"]
  created = tasks.create_task(
    "created-later",
    "Created later",
    size=3,
    details=["Review"],
    report_ids=["decision"],
  )
  expected_backfill = ["Review", "New label?: B"]
  assert created.details == expected_backfill
  tasks.create_task("patched-later", "Patched later", size=3, details=["Review"])
  patched = tasks.patch_task("patched-later", {"links": {"report_ids": ["decision"]}})
  assert patched.details == expected_backfill
  patched = tasks.patch_task("patched-later", {"report_ids": ["decision"]})
  assert patched.details == expected_backfill
  tasks.patch_task("patched-later", {"report_ids": []})
  patched = tasks.patch_task("patched-later", {"report_ids": ["decision"]})
  assert patched.details == expected_backfill
  store.close()


def test_concurrent_report_answers_keep_unique_details(tmp_path) -> None:
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
      '- (x) Yes <!-- option {"label": "Yes"} -->\n'
      '- ( ) No <!-- option {"label": "No"} -->\n'
    ),
  )
  tasks.create_task("work", "Work", size=3, details=["Review"], report_ids=["choice"])
  barrier = Barrier(2)

  def submit(index):
    barrier.wait()
    return reports[index].submit_answer(
      "choice", {"select": "Yes"}, answer_id=f"ab44{index:02d}"
    )

  with ThreadPoolExecutor(max_workers=2) as pool:
    answers = list(pool.map(submit, range(2)))
  report = reports[0].get_report("choice")
  assert len(report.answers) == 1
  assert {item.id for item in answers} == {report.answers[0].id}
  assert tasks.get_task("work")[0].details == ["Review"]
  reports[0].ack_answer("choice", report.answers[0].id, "Read")
  assert tasks.get_task("work")[0].details == ["Review", "Select?: Yes"]
  for store in stores:
    store.close()


def test_relinking_backfills_removed_answer_details_and_keeps_answers(tmp_path) -> None:
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
      '- (x) Yes <!-- option {"label": "Yes"} -->\n'
      '- ( ) No <!-- option {"label": "No"} -->\n'
    ),
  )
  tasks.create_task("work", "Work", size=3, details=["Review"], report_ids=["decision"])
  first = reports.submit_answer("decision", {"select": "Yes"}, answer_id="ac0001")
  reports.ack_answer("decision", first.id, "Read")
  second = reports.submit_answer("decision", {"select": "No"}, answer_id="ac0002")
  reports.ack_answer("decision", second.id, "Read")
  assert tasks.get_task("work")[0].details == ["Review", "Select?: Yes", "Select?: No"]
  tasks.mod_deets_rm("work", 2, size=3)
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
  relinked_details = ["Review", "Select?: No", "Select?: Yes"]
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
      '- (x) Yes <!-- option {"label": "Yes"} -->\n'
    ),
  )
  tasks.create_task("work", "Work", size=3, details=["Review"], report_ids=["plain"])
  assert tasks.get_task("work")[1] is False
  tasks.mod_links_add("work", "question", link_type="report")
  assert tasks.get_task("work")[1] is True
  reports.submit_answer("question", {"choice": "Yes"}, answer_id="b20001")
  assert tasks.get_task("work")[1] is False
  assert reports.get_report("question").latest_unacked_answer is not None
  with pytest.raises(ValueError, match="Invalid Task.status"):
    tasks.mod_scalar("work", "status", "blocked")
  with pytest.raises(ValueError, match="Invalid Task.status"):
    tasks.create_task(
      "manual-block", "Manual", size=3, status="blocked", details=["Review"]
    )
  store.close()


def test_ack_adds_full_details_and_identical_submission_is_unchanged(tmp_path) -> None:
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
      f'- (x) {option} <!-- option {{"label": "{option}"}} -->\n'
      '\n<!-- question {"id": "second", "label": "Second?"} -->\n'
      "Second?\n"
      f'- (x) {other} <!-- option {{"label": "{other}"}} -->\n'
    ),
  )
  for task_id in ("one", "two"):
    tasks.create_task(
      task_id, task_id, size=3, details=["Review"], report_ids=["question"]
    )
  values = {"choice": option, "second": other}
  first = reports.submit_answer("question", values, answer_id="b20002")
  duplicate = reports.submit_answer("question", values, answer_id="b20003")
  assert duplicate.id == first.id
  assert tasks.get_task("one")[0].details == ["Review"]
  reports.ack_answer("question", first.id, "Read")
  expected = ["Review", f"Choice?: {option}", f"Second?: {other}"]
  for task_id in ("one", "two"):
    task = tasks.get_task(task_id)[0]
    assert task.details == expected
    assert "answer_snapshots" not in task.to_dict()
  tasks.mod_deets_rm("one", 2, size=3)
  tasks.mod_scalar("one", "title", "Renamed")
  tasks.mod_deets("one", "Short addition", size=3)
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
      f'- (x) {option} <!-- option {{"label": "{option}"}} -->\n'
    ),
  )
  with pytest.raises(ValueError, match="120"):
    tasks.create_task("bad", "Bad", size=3, details=["x" * 121])
  tasks.create_task("work", "Work", size=3, details=["Review"], report_ids=["choice"])
  answer = reports.submit_answer("choice", {"choice": option}, answer_id="b20004")
  reports.ack_answer("choice", answer.id, "Read")
  with pytest.raises(ValueError, match="120"):
    tasks.mod_deets("work", "x" * 121)
  with pytest.raises(ValueError, match="120"):
    tasks.patch_task("work", {"details": ["x" * 121]})
  details = tasks.get_task("work")[0].details
  assert details[1] == f"Choice: {option}"
  with pytest.raises(ValueError, match="120"):
    tasks.patch_task("work", {"details": [*details, details[1]], "size": 3})
  tasks.patch_task("work", {"details": [*details, "Short"], "size": 3})
  assert tasks.get_task("work")[0].details == [*details, "Short"]
  store.close()


class _ReportTestClock:
  def __init__(self) -> None:
    self.current = datetime(2026, 1, 1, tzinfo=UTC)

  def now_iso(self) -> str:
    return self.current.isoformat().replace("+00:00", "Z")

  def advance(self, **kwargs: int) -> None:
    self.current += timedelta(**kwargs)


def test_task_age_priority_uses_creation_time_once_and_preserves_base() -> None:
  store = SqliteStore(":memory:")
  clock = _ReportTestClock()
  tasks = TaskService(store, store, clock=clock)
  first = tasks.create_task("old", "Old", size=5, priority="P4", details=["Work"])
  created = clock.now_iso()
  assert first.created_at == created
  clock.advance(minutes=30)
  tasks.patch_task("old", {"title": "Updated"})
  tasks.create_task("new", "New", size=1, priority="P4", details=["Work"])
  clock.advance(minutes=29, seconds=59)
  assert [task.id for task, _ in tasks.list_tasks()] == ["new", "old"]
  clock.advance(seconds=1)
  ordered = [task for task, _ in tasks.list_tasks()]
  assert [task.id for task in ordered] == ["old", "new"]
  assert ordered[0].effective_priority == "P3"
  assert store.get_task("old").priority == "P4"
  assert store.get_task("old").created_at == created
  from arena_steering.server import SteeringApp

  app = SteeringApp(store)
  app.tasks = tasks
  status, payload = app.dispatch("GET", "/tasks", {})
  assert status == 200
  assert payload["tasks"][0]["effective_priority"] == "P3"
  assert payload["tasks"][0]["priority"] == "P4"
  from io import StringIO

  from arena_steering.cli import _print_single_task

  output = StringIO()
  _print_single_task(ordered[0], False, output)
  assert "Priority: P3" in output.getvalue()
  clock.advance(hours=3)
  assert tasks.get_task("old")[0].effective_priority == "P3"
  highest = tasks.create_task(
    "urgent", "Urgent", size=1, priority="P1", details=["Work"]
  )
  clock.advance(hours=1)
  assert tasks.get_task(highest.id)[0].effective_priority == "P1"
  store.close()


def test_task_age_priority_caps_at_p2() -> None:
  store = SqliteStore(":memory:")
  clock = _ReportTestClock()
  tasks = TaskService(store, store, clock=clock)
  created = tasks.create_task("p2", "P2", size=1, priority="P2", details=["Work"])
  clock.advance(hours=1)
  aged = tasks.get_task(created.id)[0]
  assert aged.priority == "P2"
  assert aged.effective_priority == "P2"
  store.close()


def test_task_creation_time_migrates_from_modified_time(tmp_path) -> None:
  path = tmp_path / "legacy.sqlite3"
  clock = _ReportTestClock()
  store = SqliteStore(path)
  task = TaskService(store, store, clock=clock).create_task(
    "legacy", "Legacy", size=1, details=["Work"]
  )
  with store.transaction():
    store._conn.execute("ALTER TABLE tasks DROP COLUMN created_at")
  store.close()
  reopened = SqliteStore(path)
  assert reopened.get_task("legacy").created_at == task.modified_at
  reopened.close()


def test_task_finish_time_migrates_from_modified_time(tmp_path) -> None:
  path = tmp_path / "legacy-finished.sqlite3"
  clock = _ReportTestClock()
  store = SqliteStore(path)
  tasks = TaskService(store, store, clock=clock)
  tasks.create_task("legacy", "Legacy", size=1, type="ops", details=["Work"])
  tasks.finish_phase("legacy")
  with store.transaction():
    store._conn.execute("ALTER TABLE tasks DROP COLUMN finished_at")
  store.close()

  reopened = SqliteStore(path)
  task = reopened.get_task("legacy")
  assert task.status == "finished"
  assert task.finished_at == task.modified_at
  reopened.close()


def test_report_publication_order_survives_republish_rename_and_sync() -> None:
  store = SqliteStore(":memory:")
  columns = {row["name"] for row in store._conn.execute("PRAGMA table_info(reports)")}
  assert "pub_at" in columns and "seq" not in columns
  clock = _ReportTestClock()
  reports = ReportService(store, store, clock=clock)
  first = reports.publish_report("z-report", "First", "# First")
  second = reports.publish_report("a-report", "Second", "# Second")
  assert first.pub_at < second.pub_at
  assert type(first).from_dict(first.to_dict()).pub_at == first.pub_at
  assert [report.id for report in reports.list_reports()] == ["z-report", "a-report"]

  peer = SqliteStore(":memory:")
  snapshot = store.export_rows()
  assert all("seq" not in row and row["pub_at"] for row in snapshot["reports"])
  peer.merge_rows(snapshot)
  assert [report.id for report in peer.list_reports()] == ["z-report", "a-report"]
  cursor = store.state_stamp()

  clock.advance(hours=1)
  republished = reports.publish_report("z-report", "Updated", "# Updated")
  assert republished.pub_at == first.pub_at
  renamed = reports.rename_report("z-report", "renamed-report")
  assert renamed.pub_at == first.pub_at
  assert [report.id for report in reports.list_reports()] == [
    "renamed-report",
    "a-report",
  ]
  changed = store.export_rows(since=cursor)["reports"]
  assert {row["id"] for row in changed} == {"renamed-report"}
  peer.merge_rows(store.export_rows())
  assert peer.get_report("renamed-report").pub_at == first.pub_at
  assert peer.get_report("a-report").pub_at == second.pub_at
  store.close()
  peer.close()


def test_unlinked_report_staleness_starts_when_ack_is_seen() -> None:
  store = SqliteStore(":memory:")
  clock = _ReportTestClock()
  reports = ReportService(store, store, clock=clock)
  reports.publish_report(
    "idle-report",
    "Idle report",
    '<!-- question {"id":"pick","label":"Pick"} -->\n'
    'Pick\n- (x) Yes <!-- option {"label":"Yes"} -->\n'
    '- ( ) No <!-- option {"label":"No"} -->\n',
  )
  reports.publish_report("fieldless-report", "Fieldless report", "# Fieldless")
  clock.advance(hours=2)
  reports.mark_seen("idle-report")
  assert reports.list_reports(stale_only=True) == []
  answer = reports.submit_answer("idle-report", {"pick": "Yes"}, answer_id="aa1001")
  clock.advance(hours=1)
  assert reports.list_reports(stale_only=True) == []
  reports.ack_answer("idle-report", answer.id, "Noted")
  clock.advance(hours=1)
  assert reports.list_reports(stale_only=True) == []
  seen_at = clock.now_iso()
  assert reports.mark_ack_seen("idle-report").ack_seen_at == seen_at
  clock.advance(minutes=29, seconds=59)
  reports.mark_seen("idle-report")
  assert reports.mark_ack_seen("idle-report").ack_seen_at == seen_at
  assert reports.list_reports(stale_only=True) == []
  clock.advance(seconds=1)
  assert [report.id for report in reports.list_reports(stale_only=True)] == [
    "idle-report"
  ]
  reports.ack_answer("idle-report", answer.id, "Another acknowledgement")
  assert reports.list_reports(stale_only=True) == []
  assert reports.get_report("idle-report").ack_seen_at == ""
  reports.mark_ack_seen("idle-report")
  clock.advance(minutes=30)
  assert [report.id for report in reports.list_reports(stale_only=True)] == [
    "idle-report"
  ]
  reports.submit_answer("idle-report", {"pick": "No"}, answer_id="aa1006")
  assert reports.get_report("idle-report").ack_seen_at == ""
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
  reports.publish_report(
    "idle-report",
    "Idle report",
    '<!-- question {"id":"pick","label":"Pick"} -->\n'
    'Pick\n- (x) Yes <!-- option {"label":"Yes"} -->\n',
  )
  answer = reports.submit_answer("idle-report", {"pick": "Yes"}, answer_id="aa1003")
  reports.ack_answer("idle-report", answer.id, "Read")
  reports.mark_ack_seen("idle-report")
  reports.publish_report("linked-report", "Linked report", "# Linked")
  reports.pin_report("idle-report", True)
  tasks.create_task(
    "first",
    "First",
    size=3,
    type="ops",
    details=["First"],
    report_ids=["linked-report"],
  )
  tasks.create_task(
    "second",
    "Second",
    size=3,
    type="ops",
    details=["Second"],
    report_ids=["linked-report"],
  )

  clock.advance(hours=2)
  tasks.mod_scalar("first", "status", "finished")
  assert reports.list_reports(stale_only=True) == []
  clock.advance(minutes=5)
  tasks.mod_scalar("second", "status", "finished")
  finished_at = tasks.get_task("second")[0].finished_at
  assert finished_at == clock.now_iso()
  assert reports.list_reports(stale_only=True) == []
  clock.advance(minutes=9, seconds=59)
  assert reports.list_reports(stale_only=True) == []
  clock.advance(seconds=2)
  assert [report.id for report in reports.list_reports(stale_only=True)] == [
    "linked-report"
  ]
  reports.pin_report("linked-report", True)
  reports.publish_report("linked-report", "Revised", "# Revised")
  assert reports.get_report("linked-report").pinned is True
  reports.rename_report("linked-report", "renamed-report")
  assert reports.get_report("renamed-report").pinned is True
  assert tasks.get_task("second")[0].finished_at == finished_at
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
  messages = MessageService(store, store, store, store, clock=clock)
  reports.publish_report(
    "answered-report",
    "Answered report",
    (
      '<!-- question {"id": "choice", "label": "Choice?"} -->\n'
      "Choice?\n"
      '- (x) Yes <!-- option {"label": "Yes"} -->\n'
    ),
  )
  reports.submit_answer("answered-report", {"choice": "Yes"}, answer_id="abc123")
  tasks = TaskService(store, store, clock=clock)
  tasks.create_task(
    "answer-work",
    "Answer work",
    size=3,
    type="ops",
    details=["Done"],
    report_ids=["answered-report"],
  )
  tasks.finish_phase("answer-work")
  assert reports.list_reports(stale_only=True) == []
  clock.advance(minutes=9, seconds=59)
  assert reports.list_reports(stale_only=True) == []
  clock.advance(seconds=2)
  assert [report.id for report in reports.list_reports(stale_only=True)] == [
    "answered-report"
  ]
  assert reports.remove_report("--stale") == ["answered-report"]
  assert store.list_report_answers("answered-report") == []
  assert store.list_report_answers(include_orphaned=True)[0].orphaned
  assert tasks.get_task("answer-work")[0].report_ids == []
  assert "abc123" in messages.pending_ids()
  delivered = messages.read_pending(mark_seen=False)
  assert [answer.id for _, answer in delivered["report_answers"]] == ["abc123"]
  messages.ack("abc123", "Noted.")
  assert "abc123" not in messages.pending_ids()
  assert tasks.get_task("answer-work")[0].details == ["Done"]
  store.close()


def test_ack_existing_long_answer_bypasses_manual_detail_limit() -> None:
  store = SqliteStore(":memory:")
  reports = ReportService(store, store)
  tasks = TaskService(store, store)
  reports.publish_report(
    "decision",
    "Decision",
    (
      '<!-- question {"id": "choice", "label": "Choice?"} -->\n'
      "Choice?\n"
      '- (x) A <!-- option {"label": "A"} -->\n'
    ),
  )
  long_answer = "a" * 180
  answer = reports.submit_answer(
    "decision", {"choice": long_answer}, answer_id="ab0099"
  )
  created = tasks.create_task(
    "work", "Work", size=3, details=["Review"], report_ids=["decision"]
  )
  assert created.details == ["Review"]
  reports.ack_answer("decision", answer.id, "Read")
  details = tasks.get_task("work")[0].details
  assert len(details[1]) > 120 and long_answer in details[1]
  tasks.patch_task("work", {"scope": "Updated"})
  with pytest.raises(ValueError, match="exceeds 120"):
    tasks.create_task("invalid", "Invalid", size=3, details=[long_answer])
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


def test_ack_seen_timestamp_syncs_and_old_seen_flag_does_not_migrate() -> None:
  source = SqliteStore(":memory:")
  target = SqliteStore(":memory:")
  clock = _ReportTestClock()
  reports = ReportService(source, source, clock=clock)
  reports.publish_report(
    "seen-report",
    "Seen report",
    '<!-- question {"id":"pick","label":"Pick"} -->\n'
    'Pick\n- (x) Yes <!-- option {"label":"Yes"} -->\n',
  )
  answer = reports.submit_answer("seen-report", {"pick": "Yes"}, answer_id="aa1002")
  reports.ack_answer("seen-report", answer.id, "Read")
  target.merge_rows(source.export_rows())
  before = source.state_stamp()
  clock.advance(minutes=1)
  reports.mark_ack_seen("seen-report")
  target.merge_rows(source.export_rows(since=before))
  assert target.get_report("seen-report").ack_seen_at == clock.now_iso()
  # An old true flag gets no synthetic timestamp, but an explicit view can start it.
  with source.transaction():
    source._conn.execute("UPDATE reports SET ack_seen_at = '' WHERE id = 'seen-report'")
  clock.advance(hours=1)
  assert reports.list_reports(stale_only=True) == []
  assert reports.mark_ack_seen("seen-report").ack_seen_at == clock.now_iso()
  source.close()
  target.close()


def test_acknowledging_an_older_answer_does_not_reset_latest_seen_timer() -> None:
  store = SqliteStore(":memory:")
  clock = _ReportTestClock()
  reports = ReportService(store, store, clock=clock)
  messages = MessageService(store, store, store, store, clock=clock)
  _publish_answer_message_report(reports)
  first = reports.submit_answer("decision", {"choice": "A"}, answer_id="aa1004")
  latest = reports.submit_answer("decision", {"choice": "B"}, answer_id="aa1005")
  reports.ack_answer("decision", latest.id, "Latest read")
  seen_at = reports.mark_ack_seen("decision").ack_seen_at
  clock.advance(minutes=15)
  messages.ack(first.id, "Older read")
  reports.ack_answer("decision", first.id, "Another older reply")
  report = reports.get_report("decision")
  assert report.ack_seen and report.ack_seen_at == seen_at
  clock.advance(minutes=15)
  assert [item.id for item in reports.list_reports(stale_only=True)] == ["decision"]
  store.close()


def test_task_details_are_unique_on_create_and_update() -> None:
  store = SqliteStore(":memory:")
  tasks = TaskService(store, store)
  task = tasks.create_task(
    "work", "Work", size=3, details=["Repeat", " Repeat ", "Other"]
  )
  assert task.details == ["Repeat", "Other"]
  assert tasks.mod_deets("work", "Repeat", size=3).details == ["Repeat", "Other"]
  task = tasks.patch_task(
    "work", {"details": ["Other", "Other", "New", "New"], "size": 3}
  )
  assert task.details == ["Other", "New"]
  assert store.get_task("work").details == ["Other", "New"]
  store.close()


def test_answer_copy_keeps_unique_details_when_relinked() -> None:
  store = SqliteStore(":memory:")
  reports = ReportService(store, store)
  tasks = TaskService(store, store)
  _publish_answer_message_report(reports)
  tasks.create_task("work", "Work", size=3, details=["Review"], report_ids=["decision"])
  answer = reports.submit_answer("decision", {"choice": "A"}, answer_id="ff0001")
  duplicate = reports.submit_answer("decision", {"choice": "A"}, answer_id="ff0002")
  assert duplicate.id == answer.id
  reports.ack_answer("decision", answer.id, "Read")
  assert tasks.get_task("work")[0].details == ["Review", "Choice?: A"]
  tasks.mod_links_rm("work", "report", "decision")
  tasks.mod_links_add("work", "decision", link_type="report")
  assert tasks.get_task("work")[0].details == ["Review", "Choice?: A"]
  store.close()


def test_state_merge_normalizes_duplicate_task_details() -> None:
  import json

  source = SqliteStore(":memory:")
  target = SqliteStore(":memory:")
  task = TaskService(source, source).create_task(
    "work", "Work", size=3, details=["Review"]
  )
  snapshot = source.export_rows()
  row = snapshot["tasks"][0]
  row["details_json"] = json.dumps(["Review", " Review ", "More", "More"])
  target.merge_rows(snapshot)
  assert target.get_task("work").details == ["Review", "More"]
  merged = target.export_rows()["tasks"][0]
  assert json.loads(merged["details_json"]) == ["Review", "More"]
  assert merged["modified_at"] > task.modified_at
  source.merge_rows(target.export_rows())
  assert source.get_task("work").details == ["Review", "More"]
  assert json.loads(source.export_rows()["tasks"][0]["details_json"]) == [
    "Review",
    "More",
  ]
  source.close()
  target.close()


def test_answer_details_backfill_on_report_link_and_task_creation() -> None:
  store = SqliteStore(":memory:")
  reports = ReportService(store, store)
  tasks = TaskService(store, store, messages=store)
  messages = MessageService(store, store, store, store)
  _publish_answer_message_report(reports)
  tasks.create_task("work", "Work", size=3, details=["Review"])
  first = reports.submit_answer("decision", {"choice": "A"}, answer_id="fa0001")
  _, acked = messages.ack(first.id, "Read")
  assert acked.task_details_added == {}
  assert tasks.get_task("work")[0].details == ["Review"]

  tasks.mod_links_add("work", "decision", link_type="report")
  assert tasks.get_task("work")[0].details == ["Review", "Choice?: A"]
  tasks.mod_links_add("work", "decision", link_type="report")
  assert tasks.get_task("work")[0].details == ["Review", "Choice?: A"]
  tasks.mod_deets_rm("work", 2, size=3)
  tasks.mod_links_rm("work", "report", "decision")
  _, repeated = messages.ack(first.id, "Read again")
  assert repeated.task_details_added == {}
  assert tasks.get_task("work")[0].details == ["Review"]
  tasks.mod_links_add("work", "decision", link_type="report")
  assert tasks.get_task("work")[0].details == ["Review", "Choice?: A"]

  later = reports.submit_answer("decision", {"choice": "B"}, answer_id="fa0002")
  tasks.create_task(
    "pending",
    "Pending",
    size=3,
    details=["Review"],
    report_ids=["decision"],
  )
  expected_before_later_ack = ["Review", "Choice?: A"]
  assert tasks.get_task("work")[0].details == expected_before_later_ack
  assert tasks.get_task("pending")[0].details == expected_before_later_ack
  acked_later = reports.ack_answer("decision", later.id, "Read later")
  assert acked_later.task_details_added == {
    "work": ["Choice?: B"],
    "pending": ["Choice?: B"],
  }
  expected_details = ["Review", "Choice?: A", "Choice?: B"]
  assert tasks.get_task("work")[0].details == expected_details
  assert tasks.get_task("pending")[0].details == expected_details

  tasks.create_task(
    "late",
    "Late",
    size=3,
    details=["Review"],
    report_ids=["decision"],
  )
  assert tasks.get_task("late")[0].details == expected_details

  regular_before_link = messages.send_message(
    "Choice?: C", msg_id="fa0003", blocking=False
  )
  _, regular_acked = messages.ack(regular_before_link.id, "Choice?: D")
  assert regular_acked.type == "message"
  assert tasks.get_task("late")[0].details == expected_details
  tasks.mod_links_add(
    "late",
    regular_before_link.id,
    link_type="msg",
    append_detail="Manual regular-message note",
    size=3,
  )
  expected_with_message_note = [*expected_details, "Manual regular-message note"]
  assert tasks.get_task("late")[0].details == expected_with_message_note

  regular_after_link = messages.send_message(
    "Choice?: E", msg_id="fa0004", blocking=False
  )
  tasks.mod_links_add(
    "late",
    regular_after_link.id,
    link_type="msg",
    append_detail="Manual second-message note",
    size=3,
  )
  expected_with_message_notes = [
    *expected_with_message_note,
    "Manual second-message note",
  ]
  _, regular_acked = messages.ack(regular_after_link.id, "Choice?: F")
  assert regular_acked.type == "message"
  assert tasks.get_task("late")[0].details == expected_with_message_notes
  store.close()


def test_identical_latest_report_submission_is_a_noop() -> None:
  store = SqliteStore(":memory:")
  notifications = []
  reports = ReportService(
    store, store, on_answer_callback=lambda: notifications.append(1)
  )
  _publish_answer_message_report(reports)
  first = reports.submit_answer("decision", {"choice": "A"}, answer_id="fb0001")
  duplicate = reports.submit_answer("decision", {"choice": "A"}, answer_id="fb0002")
  assert duplicate.id == first.id
  assert len(reports.get_report("decision").answers) == 1
  assert len(notifications) == 1
  reports.ack_answer("decision", first.id, "Read")
  reports.mark_ack_seen("decision")
  before = reports.get_report("decision")
  again = reports.submit_answer("decision", {"choice": "A"}, answer_id="fb0003")
  after = reports.get_report("decision")
  assert again.id == first.id and again.status == "acked"
  assert after.ack_seen and after.ack_seen_at == before.ack_seen_at
  assert after.modified_at == before.modified_at
  assert len(notifications) == 1
  newer = reports.submit_answer("decision", {"choice": "B"}, answer_id="fb0004")
  assert newer.id != first.id and len(notifications) == 2
  store.close()


def test_ack_answer_details_sync_without_repeating_on_receiver() -> None:
  source = SqliteStore(":memory:")
  target = SqliteStore(":memory:")
  reports = ReportService(source, source)
  tasks = TaskService(source, source)
  _publish_answer_message_report(reports)
  tasks.create_task("work", "Work", size=3, details=["Review"], report_ids=["decision"])
  answer = reports.submit_answer("decision", {"choice": "A"}, answer_id="fc0001")
  reports.ack_answer("decision", answer.id, "Read")
  target.merge_rows(source.export_rows())
  assert target.get_task("work").details == ["Review", "Choice?: A"]
  target_tasks = TaskService(target, target)
  target_tasks.mod_deets_rm("work", 2, size=3)
  repeated = ReportService(target, target).ack_answer("decision", answer.id, "Again")
  assert repeated.task_details_added == {}
  assert target.get_task("work").details == ["Review"]
  source.close()
  target.close()


def test_new_task_and_report_ids_enforce_length_and_cross_type_collisions() -> None:
  store = SqliteStore(":memory:")
  tasks = TaskService(store, store)
  reports = ReportService(store, store)
  max_id = "a" * 64
  long_id = "b" * 65
  tasks.create_task(max_id, "Allowed", size=1, details=["Work"])
  reports.publish_report("report", "Report", "# Report")
  with pytest.raises(ValueError):
    tasks.create_task(long_id, "Too long", size=1, details=["Work"])
  with pytest.raises(ValueError):
    reports.publish_report(long_id, "Too long", "# Report")
  with pytest.raises(ValueError):
    tasks.create_task("report", "Collision", size=1, details=["Work"])
  with pytest.raises(ValueError):
    reports.publish_report(max_id, "Collision", "# Report")
  with pytest.raises(ValueError):
    tasks.rename_task(max_id, "report")
  with pytest.raises(ValueError):
    reports.rename_report("report", max_id)
  with pytest.raises(ValueError):
    tasks.rename_task(max_id, long_id)
  with pytest.raises(ValueError):
    reports.rename_report("report", long_id)
  assert tasks.get_task(max_id)[0].id == max_id
  assert reports.get_report("report").id == "report"
  store.close()


def test_existing_long_and_colliding_ids_remain_usable() -> None:
  from arena_steering.models import Report, Task

  store = SqliteStore(":memory:")
  tasks = TaskService(store, store)
  reports = ReportService(store, store)
  legacy = "legacy-" + "x" * 65
  store.save_task_queue([Task(id=legacy, title="Old task", size=1, details=["Work"])])
  store.save_report(Report(id=legacy, title="Old report", body="# Old"))

  assert tasks.get_task(legacy)[0].title == "Old task"
  assert reports.get_report(legacy).title == "Old report"
  assert tasks.rename_task(legacy, legacy).id == legacy
  assert reports.rename_report(legacy, legacy).id == legacy
  assert reports.publish_report(legacy, "Updated", "# Updated").title == "Updated"
  assert tasks.rename_task(legacy, "short-task").id == "short-task"
  assert reports.rename_report(legacy, "short-report").id == "short-report"
  store.close()


def _attachments() -> list[Attachment]:
  home = Path.home() / "steer-fixture"
  return [
    Attachment("first.txt", str(home / "first.txt"), 4),
    Attachment("missing.png", str(home / "missing.png"), 0, present=False),
  ]


def test_task_defaults_and_linked_messages_preserve_explicit_priority(
  tmp_path: Path,
) -> None:
  db = tmp_path / "state.sqlite3"
  store = SqliteStore(db)
  app = SteeringApp(store)
  app.messages.send_message(
    "Inspect files", attachments=_attachments(), msg_id="ab1020"
  )
  tasks = app.tasks
  assert Task("default", "Default", size=2).priority == "P4"
  plain = tasks.create_task("plain", "Plain", size=2, details=["Inspect."])
  assert (plain.priority, plain.priority_explicit) == ("P4", False)

  paths = ["~/steer-fixture/first.txt", "~/steer-fixture/missing.png"]
  created = tasks.create_task(
    "linked", "Linked", size=2, details=["Inspect."], msg_ids=["ab1020"]
  )
  assert (created.priority, created.priority_explicit) == ("P4", False)
  assert created.details == ["Inspect.", *paths]

  tasks.create_task("explicit", "Explicit", size=2, priority="P4", details=["Inspect."])
  tasks.mod_links_add("explicit", "ab1020", link_type="msg", size=2)
  assert (
    tasks.get_task("explicit")[0].priority,
    tasks.get_task("explicit")[0].details,
  ) == ("P4", ["Inspect.", *paths])
  tasks.mod_links_add("plain", "ab1020", link_type="msg", size=2)
  tasks.mod_links_add("plain", "ab1020", link_type="msg")
  assert (tasks.get_task("plain")[0].priority, tasks.get_task("plain")[0].details) == (
    "P4",
    ["Inspect.", *paths],
  )

  patched = tasks.create_task("patched", "Patched", size=2, details=["Inspect."])
  tasks.patch_task(patched.id, {"msg_ids": ["ab1020"], "size": 2})
  assert (
    tasks.get_task("patched")[0].priority,
    tasks.get_task("patched")[0].details,
  ) == ("P4", ["Inspect.", *paths])
  tasks.patch_task("plain", {"priority": "P5"})
  assert tasks.get_task("plain")[0].priority_explicit
  store.close()

  reopened = SqliteStore(db)
  tasks = TaskService(reopened, reopened, messages=reopened)
  assert (
    tasks.get_task("explicit")[0].priority_explicit,
    tasks.get_task("plain")[0].priority,
  ) == (True, "P5")
  tasks.mod_links_rm("plain", "msg", "ab1020")
  tasks.mod_links_add(
    "plain", "ab1020", link_type="msg", append_detail="Relinked.", size=2
  )
  assert (tasks.get_task("plain")[0].priority, tasks.get_task("plain")[0].details) == (
    "P5",
    ["Inspect.", *paths, "Relinked."],
  )
  reopened.close()


def test_ack_and_api_add_multiple_attachment_paths_without_opt_in(
  tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  monkeypatch.setenv("HOME", str(tmp_path))
  fixture_dir = tmp_path / "steer-fixture"
  fixture_dir.mkdir(parents=True, exist_ok=True)
  (fixture_dir / "first.txt").write_text("four", encoding="utf-8")
  monkeypatch.setattr(cli, "resolve_state_dir", lambda: tmp_path)
  store = SqliteStore(tmp_path / "state.sqlite3")
  app = SteeringApp(store)
  for message_id in ("ab1021", "ab1022", "ab1023"):
    app.messages.send_message(
      "Inspect files", attachments=_attachments(), msg_id=message_id
    )
  store.close()

  def run(*args: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    code = cli.main(list(args), out=out, err=err)
    return code, out.getvalue(), err.getvalue()

  args = ("-t", "New work", "-z", "2", "-d", "Inspect.")
  code, output, error = run("ack", "ab1021", "Read", "-i", "via-ack", *args)
  assert code == 0, error
  assert "Priority: P4" in output

  code, _, error = run("ack", "ab1022", "Read", "-i", "explicit-ack", *args, "-p", "P5")
  assert code == 0, error
  code, _, error = run("task", "new", "-z", "2", "plain", "Plain", "-d", "Inspect.")
  assert code == 0, error

  store = SqliteStore(tmp_path / "state.sqlite3")
  assert store.get_message("ab1021").acks == ["Read"]
  assert store.get_task("via-ack").details == [
    "Inspect.",
    "~/steer-fixture/first.txt",
    "~/steer-fixture/missing.png",
  ]
  assert (
    store.get_task("via-ack").priority,
    store.get_task("explicit-ack").priority,
  ) == ("P4", "P5")
  assert store.get_task("plain").priority == "P4"

  app = SteeringApp(store)
  status, payload = app.dispatch(
    "POST",
    "/tasks",
    {"id": "via-api", "title": "Via API", "size": 2, "msg_ids": ["ab1023"]},
  )
  assert status == HTTPStatus.CREATED
  assert payload["task"]["priority"] == "P4"
  assert payload["task"]["details"] == [
    "~/steer-fixture/first.txt",
    "~/steer-fixture/missing.png (lost)",
  ]
  status, payload = app.dispatch(
    "POST",
    "/tasks",
    {"id": "api-plain", "title": "Plain API", "size": 2, "details": ["Inspect."]},
  )
  assert status == HTTPStatus.CREATED
  assert payload["task"]["priority"] == "P4"
  store.close()


def test_old_priority_override_survives_migration_and_later_links(
  tmp_path: Path,
) -> None:
  db = tmp_path / "legacy.sqlite3"
  store = SqliteStore(db)
  tasks = TaskService(store, store)
  tasks.create_task(
    "old-override", "Old override", size=2, priority="P4", details=["Inspect."]
  )
  tasks.create_task(
    "old-default", "Old default", size=2, priority="P3", details=["Inspect."]
  )
  store.close()

  with sqlite3.connect(db) as conn:
    conn.execute("ALTER TABLE tasks DROP COLUMN priority_explicit")

  reopened = SqliteStore(db)
  tasks = TaskService(reopened, reopened, messages=reopened)
  assert tasks.get_task("old-override")[0].priority_explicit
  assert not tasks.get_task("old-default")[0].priority_explicit
  SteeringApp(reopened).messages.send_message(
    "See attached file", attachments=_attachments(), msg_id="ab1024"
  )
  tasks.mod_links_add("old-override", "ab1024", link_type="msg", size=2)
  assert tasks.get_task("old-override")[0].priority == "P4"
  reopened.close()


def test_long_missing_attachment_path_is_kept_without_truncation() -> None:
  store = SqliteStore(":memory:")
  app = SteeringApp(store)
  long_path = Path.home() / "steer-fixture" / ("x" * 125 + ".txt")
  app.messages.send_message(
    "See attachment",
    attachments=[Attachment("long.txt", str(long_path), present=False)],
    msg_id="ab1025",
  )
  task = app.tasks.create_task("long-path", "Long path", size=2, msg_ids=["ab1025"])
  assert (task.priority, task.details) == ("P4", [f"~/steer-fixture/{long_path.name}"])
  app.tasks.patch_task("long-path", {"title": "Long path retained"})
  assert app.tasks.get_task("long-path")[0].details == task.details
  store.close()


QUESTION = (
  '<!-- question {"id":"choice","label":"Choice?"} -->\n'
  'Choice?\n- (x) Yes <!-- option {"label":"Yes"} -->\n'
)


FIRST_COMMIT = "a" * 40


SECOND_COMMIT = "b" * 40


def test_ordered_phases_survive_model_store_and_sync(tmp_path: Path) -> None:
  task = Task(size=3, id="chain", title="Report then code", types=["report", "code"])
  assert task.type == "report"
  assert task.to_dict()["current_phase"] == "report"
  assert task.to_dict()["remaining_phases"] == ["code"]
  assert Task.from_dict(task.to_dict()) == task
  with pytest.raises(ValueError, match="phase|type"):
    Task(size=3, id="empty", title="Empty", types=[])

  source = SqliteStore(tmp_path / "source.sqlite3")
  source.save_task_queue(
    [
      Task(
        size=3,
        id="chain",
        title="Report then code",
        types=["report", "code"],
        phase_index=1,
        phase_evidence=["decision", None],
      )
    ]
  )
  assert source.get_task("chain").to_dict()["phase_evidence"] == ["decision", None]
  replica = SqliteStore(tmp_path / "replica.sqlite3")
  replica.merge_rows(source.export_rows())
  restored = replica.get_task("chain")
  assert restored.types == ["report", "code"]
  assert restored.type == "code"
  assert restored.phase_index == 1
  assert restored.phase_evidence == ["decision", None]
  replica.close()
  source.close()

  legacy = SqliteStore(tmp_path / "legacy.sqlite3")
  with legacy.transaction():
    legacy._conn.execute(
      "INSERT INTO tasks (position, size, insertion_order, id, title, type, status, scope, modified_at) "
      "VALUES (0, 3, 0, 'old', 'Old task', 'docs', 'finished', '', '2026-11-01T00:00:00Z')"
    )
  old = legacy.get_task("old")
  assert old.types == ["docs"]
  assert old.phase_index == 1
  legacy.close()


def test_existing_task_table_migrates_to_single_phase(tmp_path: Path) -> None:
  database = tmp_path / "old.sqlite3"
  with sqlite3.connect(database) as conn:
    conn.execute(
      "CREATE TABLE tasks (position INTEGER NOT NULL, id TEXT PRIMARY KEY, "
      "title TEXT NOT NULL, type TEXT NOT NULL, status TEXT NOT NULL, scope TEXT NOT NULL, "
      "details_json TEXT NOT NULL DEFAULT '[]', links_json TEXT NOT NULL DEFAULT '', "
      "msg_ids_json TEXT NOT NULL DEFAULT '[]', report_ids_json TEXT NOT NULL DEFAULT '[]', "
      "deps_json TEXT NOT NULL DEFAULT '[]', modified_at TEXT NOT NULL)"
    )
    conn.execute(
      "INSERT INTO tasks (position, id, title, type, status, scope, details_json, modified_at) "
      "VALUES (0, 'old', 'Old task', 'code', 'upcoming', '', '[\"Review\"]', '2026-11-01T00:00:00Z')"
    )
  store = SqliteStore(database)
  with store.transaction():
    store._conn.execute("UPDATE tasks SET size=3 WHERE id='old'")
  assert store.get_task("old").types == ["code"]
  assert store.get_task("old").phase_index == 0
  store.save_task_queue(store.list_tasks())
  assert store.get_task("old").phase_evidence == [None]
  store.close()
  reopened = SqliteStore(database)
  assert reopened.get_task("old").types == ["code"]
  reopened.close()


def test_report_then_code_advances_without_waiting_for_its_old_report() -> None:
  store = SqliteStore(":memory:")
  reports = ReportService(store, store)
  tasks = TaskService(store, store, commit_verifier=lambda commit: commit)
  reports.publish_report("decision", "Decision", QUESTION)
  created = tasks.create_task(
    "chain",
    "Review and build",
    size=3,
    types=["report", "code"],
    details=["Build after the report."],
    report_ids=["decision"],
  )
  assert created.phase_index == 0
  assert tasks.get_task("chain")[1] is False
  advanced = tasks.finish_phase("chain")
  assert advanced.status == "upcoming"
  assert advanced.type == "code"
  assert advanced.phase_index == 1
  assert advanced.phase_evidence == ["decision", None]
  assert tasks.get_task("chain")[1] is False

  reports.publish_report("midphase", "Midphase question", QUESTION)
  linked = tasks.mod_links_add("chain", "midphase", link_type="report")
  assert linked.phase_index == 1
  assert tasks.get_task("chain")[1] is True
  with pytest.raises(ValueError, match="block"):
    tasks.finish_phase("chain", commit_hash=FIRST_COMMIT)
  assert tasks.get_task("chain")[0].phase_index == 1
  reports.submit_answer("midphase", {"choice": "Yes"}, answer_id="ac1001")
  assert tasks.get_task("chain")[1] is False
  done = tasks.finish_phase("chain", commit_hash=FIRST_COMMIT)
  assert done.status == "finished"
  assert done.phase_index == 2
  assert done.phase_evidence == ["decision", FIRST_COMMIT]
  store.close()


def test_phase_evidence_is_required_unique_and_immutable() -> None:
  store = SqliteStore(":memory:")
  reports = ReportService(store, store)
  tasks = TaskService(store, store, commit_verifier=lambda commit: commit)
  tasks.create_task(
    "work", "Code then docs", size=3, types=["code", "docs"], details=["Ship."]
  )
  with pytest.raises(ValueError, match="commit"):
    tasks.finish_phase("work")
  first = tasks.finish_phase("work", commit_hash=FIRST_COMMIT)
  assert first.status == "upcoming" and first.type == "docs"
  with pytest.raises(ValueError, match="unique|already"):
    tasks.finish_phase("work", commit_hash=FIRST_COMMIT)
  with pytest.raises(ValueError, match="phase|progress"):
    tasks.patch_task("work", {"phase_index": 0})
  with pytest.raises(ValueError, match="phase|progress"):
    tasks.patch_task("work", {"types": ["docs"]})
  tasks.mod_deets("work", "Write release notes.", size=3)
  assert tasks.get_task("work")[0].phase_evidence == [FIRST_COMMIT, None]
  done = tasks.patch_task("work", {"status": "finished", "commit_hash": SECOND_COMMIT})
  assert done.status == "finished"
  tasks.create_task("other", "Another change", size=3, type="code", details=["Ship."])
  with pytest.raises(ValueError, match="unique|already"):
    tasks.finish_phase("other", commit_hash=SECOND_COMMIT)
  assert tasks.get_task("other")[0].status == "upcoming"
  with pytest.raises(ValueError, match="upcoming|finish"):
    tasks.create_task(
      "bypass", "Bypass", size=3, type="code", status="finished", details=["Ship."]
    )
  reports.publish_report("decision", "Decision", QUESTION)
  tasks.create_task(
    "report-work", "Report first", size=3, type="report", details=["Review."]
  )
  with pytest.raises(ValueError, match="report"):
    tasks.finish_phase("report-work")
  tasks.mod_links_add("report-work", "decision", link_type="report")
  assert tasks.finish_phase("report-work").status == "finished"
  store.close()


def test_entity_rename_preserves_report_source_and_message_parent_refs() -> None:
  store = SqliteStore(":memory:")
  reports = ReportService(store, store, messages=store)
  tasks = TaskService(store, store, messages=store)
  messages = MessageService(store, store, store, store)
  reports.publish_report(
    "source-report", "Source report", "Report body.", source_file="docs/source.md"
  )
  tasks.create_task("source-task", "Source task", size=3, details=["Review."])
  parent = messages.send_message("Message parent", msg_id="dd0001")
  child = messages.send_message(
    "Child message",
    msg_id="ee0001",
    parent_refs=[
      {"type": "task", "id": "source-task"},
      {"type": "report", "id": "source-report"},
      {"type": "message", "id": parent.id},
    ],
  )

  tasks.rename_task("source-task", "renamed-task")
  child_after_task_rename = store.get_message(child.id)
  assert child_after_task_rename is not None
  assert child_after_task_rename.parent_refs == [
    {"type": "task", "id": "renamed-task"},
    {"type": "report", "id": "source-report"},
    {"type": "message", "id": parent.id},
  ]
  assert child_after_task_rename.parent_ids == [parent.id]

  renamed_report = reports.rename_report("source-report", "renamed-report")
  assert renamed_report.source_file == "docs/source.md"
  child_after_report_rename = store.get_message(child.id)
  assert child_after_report_rename is not None
  assert child_after_report_rename.parent_refs == [
    {"type": "task", "id": "renamed-task"},
    {"type": "report", "id": "renamed-report"},
    {"type": "message", "id": parent.id},
  ]
  assert child_after_report_rename.parent_ids == [parent.id]
  store.close()


def test_report_rename_preserves_finished_phase_evidence() -> None:
  store = SqliteStore(":memory:")
  reports = ReportService(store, store)
  tasks = TaskService(store, store)
  reports.publish_report("decision", "Decision", QUESTION)
  tasks.create_task(
    "chain",
    "Report then operate",
    size=3,
    types=["report", "ops"],
    details=["Review."],
    report_ids=["decision"],
  )
  tasks.finish_phase("chain")
  reports.rename_report("decision", "renamed-decision")
  updated, blocked = tasks.get_task("chain")
  assert updated.report_ids == ["renamed-decision"]
  assert updated.phase_evidence == ["renamed-decision", None]
  assert blocked is False
  assert tasks.finish_phase("chain").status == "finished"
  store.close()


def test_report_id_that_looks_like_commit_is_not_duplicate_commit() -> None:
  store = SqliteStore(":memory:")
  reports = ReportService(store, store)
  tasks = TaskService(store, store, commit_verifier=lambda commit: commit)
  reports.publish_report(FIRST_COMMIT, "Hash-shaped report ID", QUESTION)
  tasks.create_task(
    "report-work",
    "Report",
    size=3,
    type="report",
    details=["Review."],
    report_ids=[FIRST_COMMIT],
  )
  tasks.finish_phase("report-work")
  tasks.create_task("code-work", "Code", size=3, type="code", details=["Ship."])
  assert tasks.finish_phase("code-work", commit_hash=FIRST_COMMIT).status == "finished"
  store.close()


def test_http_task_create_and_patch_expose_phase_progress(tmp_path: Path) -> None:
  store = SqliteStore(tmp_path / "http.sqlite3")
  app = SteeringApp(store)
  app.tasks._commit_verifier = lambda commit: commit
  app.reports.publish_report("decision", "Decision", QUESTION)
  status, created = app.dispatch(
    "POST",
    "/tasks",
    {
      "id": "chain",
      "title": "Report then code",
      "size": 3,
      "types": ["report", "code"],
      "details": ["Build."],
      "report_ids": ["decision"],
    },
  )
  assert status == HTTPStatus.CREATED
  assert created["task"]["types"] == ["report", "code"]
  status, advanced = app.dispatch("PATCH", "/tasks/chain", {"status": "finished"})
  assert status == HTTPStatus.OK
  assert advanced["task"]["status"] == "upcoming"
  assert advanced["task"]["current_phase"] == "code"
  status, _ = app.dispatch("PATCH", "/tasks/chain", {"status": "finished"})
  assert status == HTTPStatus.BAD_REQUEST
  status, done = app.dispatch(
    "PATCH", "/tasks/chain", {"status": "finished", "commit_hash": FIRST_COMMIT}
  )
  assert status == HTTPStatus.OK
  assert done["task"]["status"] == "finished"
  status, listed = app.dispatch("GET", "/tasks")
  assert listed["tasks"][0]["phase_index"] == 2
  store.close()


def test_task_view_renders_all_phase_chips_in_order() -> None:
  repo = Path(__file__).resolve().parents[3]
  script = """
import assert from 'node:assert/strict';
import { renderTasksView } from './skills/arena-steering/assets/tasks-view.js';
const container = {
  innerHTML: '', scrollTop: 0,
  querySelector() { return null; },
  querySelectorAll() { return []; },
};
renderTasksView(container, { tasks: [{
  id: 'chain', title: 'Deliver', status: 'upcoming',
  type: 'code', types: ['report', 'code', 'docs'], phase_index: 1,
  details: [], links: {}, blocked: false,
}] });
const row = container.innerHTML.split('data-task-id="chain"')[1].split('</li>')[0];
assert.match(row, /data-task-type="report"[^>]*data-phase-state="finished"/);
assert.match(row, /data-task-type="code"[^>]*data-phase-state="current"/);
assert.match(row, /data-task-type="docs"[^>]*data-phase-state="upcoming"/);
assert.ok(row.indexOf('Report') < row.indexOf('Code'));
assert.ok(row.indexOf('Code') < row.indexOf('Docs'));
"""
  result = subprocess.run(
    ["node", "--experimental-default-type=module", "--input-type=module", "-e", script],
    cwd=repo,
    capture_output=True,
    text=True,
    encoding="utf-8",
    check=False,
  )
  assert result.returncode == 0, result.stderr
  style = (repo / "skills/arena-steering/assets/style.css").read_text(encoding="utf-8")
  assert '.task-type[data-phase-state="finished"]' in style
  assert "text-decoration: line-through" in style
  assert "opacity:" in style


@pytest.mark.skipif(
  not os.environ.get("ARENA_STEERING_CHROMIUM"),
  reason="Set ARENA_STEERING_CHROMIUM to run the browser regression",
)
def test_browser_shows_faded_finished_phase_chip(tmp_path: Path) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore(tmp_path / "browser.sqlite3")
  app = SteeringApp(store, repo_name="Task phases")
  app.reports.publish_report("decision", "Decision", "# Decision")
  app.tasks.create_task(
    "chain",
    "Review then operate",
    size=3,
    types=["report", "ops"],
    details=["Review."],
    report_ids=["decision"],
  )
  app.tasks.finish_phase("chain")
  server = create_http_server(app, host="0.0.0.0", port=0)
  thread = threading.Thread(target=server.serve_forever, daemon=True)
  thread.start()
  try:
    with playwright.sync_playwright() as runner:
      browser = runner.chromium.launch(
        executable_path=os.environ["ARENA_STEERING_CHROMIUM"],
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage"],
      )
      try:
        page = browser.new_page(viewport={"width": 1200, "height": 700})
        page.set_default_timeout(5000)
        page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
        page.locator("#tab-tasks").click()
        chips = page.locator('.task[data-task-id="chain"] .task-type')
        assert chips.count() == 2
        assert [chip.inner_text() for chip in chips.all()] == ["Report", "Ops"]
        assert [chip.get_attribute("data-phase-state") for chip in chips.all()] == [
          "finished",
          "current",
        ]
        assert (
          chips.nth(0).evaluate("el => getComputedStyle(el).textDecorationLine")
          == "line-through"
        )
        assert float(chips.nth(0).evaluate("el => getComputedStyle(el).opacity")) < 1
        screenshot = Path(".cache/v2-task-chain-browser.png")
        screenshot.parent.mkdir(exist_ok=True)
        page.screenshot(path=str(screenshot), full_page=True)
      finally:
        browser.close()
  finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)
    store.close()


@pytest.mark.skipif(
  not os.environ.get("ARENA_STEERING_CHROMIUM"),
  reason="Set ARENA_STEERING_CHROMIUM to run the browser regression",
)
def test_browser_shimmers_only_for_active_task_gates(tmp_path: Path) -> None:
  import json

  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore(tmp_path / "gates.sqlite3")
  app = SteeringApp(store, repo_name="Task gate indicators")
  runs = tmp_path / "runs"
  runs.mkdir()
  for name, exit_code in (("active", None), ("failed", "7"), ("passed", "0")):
    marker = runs / f"{name}.exit"
    (runs / f"{name}.json").write_text(
      json.dumps({"exit_path": str(marker)}), encoding="utf-8"
    )
    if exit_code is not None:
      marker.write_text(exit_code, encoding="utf-8")
    app.tasks.create_task(
      name, name.title(), size=3, details=["Verify."], gate_names=[name]
    )
  app.reports.publish_report("decision", "Decision", QUESTION)
  app.tasks.create_task(
    "waiting", "Waiting", size=3, details=["Answer."], report_ids=["decision"]
  )
  server = create_http_server(app, host="0.0.0.0", port=0)
  thread = threading.Thread(target=server.serve_forever, daemon=True)
  thread.start()
  try:
    with playwright.sync_playwright() as runner:
      browser = runner.chromium.launch(
        executable_path=os.environ["ARENA_STEERING_CHROMIUM"],
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage"],
      )
      try:
        page = browser.new_page(viewport={"width": 390, "height": 800})
        page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
        page.locator("#tab-tasks").click()
        for name in ("active", "failed", "passed", "waiting"):
          title = page.locator(f'.task[data-task-id="{name}"] .task-title')
          title.wait_for()
          expected = name == "active"
          assert title.get_attribute("data-gate-running") == str(expected).lower()
          animation = title.evaluate(
            "element => getComputedStyle(element).animationName"
          )
          assert (animation != "none") is expected, (name, animation)
        page.screenshot(path=str(tmp_path / "task-gate-shimmer.png"))
        page.emulate_media(reduced_motion="reduce")
        title = page.locator('.task[data-task-id="active"] .task-title')
        assert (
          title.evaluate("element => getComputedStyle(element).animationName") == "none"
        )
      finally:
        browser.close()
  finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)
    store.close()


def test_dirty_checkout_finish_raises_one_persisted_violation(
  tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  checkout = tmp_path / "checkout"
  checkout.mkdir()

  def git(*args: str) -> str:
    result = subprocess.run(
      ["git", *args],
      cwd=checkout,
      capture_output=True,
      text=True,
      encoding="utf-8",
      check=True,
    )
    return result.stdout.strip()

  git("init", "-b", "test")
  git("config", "user.name", "Test")
  git("config", "user.email", "test@example.com")
  (checkout / ".gitignore").write_text("arena-state/\n", encoding="utf-8")
  git("add", ".gitignore")
  git("commit", "-m", "test: ignore installed state")

  state_dir = checkout / "arena-state"
  from arena_steering.git_safety import DirtyTreeError

  store, messages, tasks, _ = cli.open_services(state_dir)
  tasks.create_task("review", "Review", size=3, type="misc", details=["Review."])
  for phase_type in ("ops", "report", "code", "docs"):
    tasks.create_task(
      phase_type, phase_type, size=3, type=phase_type, details=["Review."]
    )
  assert not git("status", "--porcelain=v1", "--untracked-files=all")
  (checkout / "unfinished.txt").write_text("dirty", encoding="utf-8")
  for task_id in ("review", "ops", "report", "code", "docs"):
    with pytest.raises(DirtyTreeError, match="clean Git tree"):
      tasks.finish_phase(task_id, commit_hash=FIRST_COMMIT)
  assert tasks.get_task("review")[0].status == "upcoming"
  flag = messages.pending_violation()
  assert flag is not None and flag.hidden and flag.requires_ack
  assert flag.violation_type == "dirty-task-finish"
  assert flag.body == with_bible_read(
    "VIOLATION: Finish task with dirty tree. Clean tree then retry."
  )

  with pytest.raises(DirtyTreeError, match="clean Git tree"):
    tasks.mod_scalar("review", "status", "finished")
  with pytest.raises(DirtyTreeError, match="clean Git tree"):
    tasks.patch_task("review", {"status": "finished"})
  assert messages.pending_ids() == [flag.id]
  messages.ack(flag.id, "Read; investigating the dirty tree.")
  app = SteeringApp(store)
  status, response = app.dispatch(
    "PATCH", "/tasks/review", {"status": "finished", "_request_id": "dirty-finish"}
  )
  assert status == HTTPStatus.BAD_REQUEST
  assert "clean Git tree" in response["error"]
  http_flag = messages.pending_violation()
  assert http_flag is not None and http_flag.id != flag.id
  other_store, other_messages, _, _ = cli.open_services(state_dir)
  assert other_messages.pending_violation().id == http_flag.id
  other_store.close()
  messages.ack(http_flag.id, "Read; checking the CLI finish.")
  monkeypatch.setattr(cli, "resolve_state_dir", lambda: state_dir)
  errors = io.StringIO()
  assert cli.main(["task", "finish", "review"], out=io.StringIO(), err=errors) == 1
  assert "clean Git tree" in errors.getvalue()
  cli_flag = messages.pending_violation()
  assert cli_flag is not None and cli_flag.id not in {flag.id, http_flag.id}
  assert messages.pending_ids() == [cli_flag.id]

  (checkout / "unfinished.txt").unlink()
  assert not git("status", "--porcelain=v1", "--untracked-files=all")
  messages.ack(cli_flag.id, "Read and corrected.")
  (checkout / ".gitignore").write_text(
    "arena-state/\n# tracked change\n", encoding="utf-8"
  )
  with pytest.raises(DirtyTreeError, match="clean Git tree"):
    tasks.finish_phase("review")
  tracked_flag = messages.pending_violation()
  assert tracked_flag is not None and tracked_flag.id != cli_flag.id
  git("restore", ".gitignore")
  messages.ack(tracked_flag.id, "Read and corrected.")
  assert tasks.finish_phase("review").status == "finished"
  store.close()


def test_git_completion_checks_clean_tree_and_remote(tmp_path: Path) -> None:
  from arena_steering.git_safety import GitCheckError, verify_completion_commit

  def git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
      ["git", *args],
      cwd=cwd,
      capture_output=True,
      text=True,
      encoding="utf-8",
      check=True,
    )
    return result.stdout.strip()

  remote = tmp_path / "remote.git"
  checkout = tmp_path / "checkout"
  git(tmp_path, "init", "--bare", str(remote))
  git(tmp_path, "init", "-b", "task-check", str(checkout))
  git(checkout, "config", "user.name", "Test")
  git(checkout, "config", "user.email", "test@example.com")
  (checkout / "work.txt").write_text("first", encoding="utf-8")
  git(checkout, "add", "work.txt")
  git(checkout, "commit", "-m", "test: first")
  first = git(checkout, "rev-parse", "HEAD")
  git(checkout, "remote", "add", "origin", str(remote))
  git(checkout, "push", "-u", "origin", "HEAD")
  assert verify_completion_commit(checkout, first) == first
  (checkout / "work.txt").write_text("dirty", encoding="utf-8")
  with pytest.raises(GitCheckError, match="clean|dirty"):
    verify_completion_commit(checkout, first)
  (checkout / "work.txt").write_text("first", encoding="utf-8")
  (checkout / "work.txt").write_text("second", encoding="utf-8")
  git(checkout, "add", "work.txt")
  git(checkout, "commit", "-m", "test: second")
  second = git(checkout, "rev-parse", "HEAD")
  with pytest.raises(GitCheckError, match="push|local-only|remote"):
    verify_completion_commit(checkout, second)
  git(checkout, "push", "origin", "HEAD")
  assert verify_completion_commit(checkout, second) == second
  git(checkout, "remote", "set-url", "origin", str(tmp_path / "missing.git"))
  with pytest.raises(GitCheckError, match="Remote branch comparison unavailable"):
    verify_completion_commit(checkout, second)


@pytest.mark.parametrize("size", [None, 0, 4, 35, "5", True, 3.0, -1])
def test_task_rejects_missing_or_non_deck_size(size: object) -> None:
  with pytest.raises(ValueError, match="Task.size"):
    Task("work", "Work", size=size)


@pytest.mark.parametrize("priority", ["P0", "P6", "p2", "urgent", 1, None])
def test_task_rejects_invalid_priority(priority: object) -> None:
  with pytest.raises(ValueError, match="Task.priority"):
    Task("work", "Work", size=3, priority=priority)


@pytest.mark.parametrize(
  ("task_type", "types", "priority", "expected"),
  [
    ("report", None, None, "P3"),
    ("report", ["report", "report"], None, "P3"),
    ("code", ["code", "report"], None, "P4"),
    ("code", ["report", "code"], None, "P4"),
    ("code", None, None, "P4"),
    ("report", None, "P5", "P5"),
    ("report", None, "P1", "P1"),
  ],
)
def test_new_task_priority_default(
  task_type: str, types: list[str] | None, priority: str | None, expected: str
) -> None:
  store = SqliteStore(":memory:")
  tasks = TaskService(store, store)
  task = tasks.create_task(
    "work",
    "Work",
    size=1,
    type=task_type,
    types=types,
    priority=priority,
    details=["Work."],
  )
  assert task.priority == expected
  assert task.priority_explicit is (priority is not None)
  store.close()


def test_mixed_phase_default_applies_to_task_api() -> None:
  store = SqliteStore(":memory:")
  app = SteeringApp(store)
  status, payload = app.dispatch(
    "POST",
    "/tasks",
    {
      "id": "work",
      "title": "Work",
      "size": 1,
      "types": ["code", "report"],
      "details": ["Work."],
    },
  )
  assert status == HTTPStatus.CREATED
  assert payload["task"]["priority"] == "P4"
  store.close()


def test_task_fields_round_trip_and_persist_across_edits_and_reopen(
  tmp_path: Path,
) -> None:
  path = tmp_path / "tasks.sqlite3"
  store = SqliteStore(path)
  tasks = TaskService(store, store)
  created = tasks.create_task("work", "Work", size=8, priority="P2", details=["Build."])
  assert created.to_dict()["size"] == 8
  assert created.to_dict()["priority"] == "P2"
  original_order = created.insertion_order
  assert Task.from_dict(created.to_dict()) == created
  tasks.mod_deets("work", "Test.", size=8)
  tasks.rename_task("work", "renamed")
  store.close()

  reopened = SqliteStore(path)
  renamed = reopened.get_task("renamed")
  assert renamed is not None
  assert (renamed.priority, renamed.size, renamed.insertion_order) == (
    "P2",
    8,
    original_order,
  )
  reopened.close()


def test_priority_then_size_then_insertion_order_with_dependency_precedence() -> None:
  store = SqliteStore(":memory:")
  tasks = TaskService(store, store)
  for task_id, priority, size in (
    ("big", "P3", 13),
    ("small-a", "P3", 3),
    ("small-b", "P3", 3),
    ("urgent", "P1", 21),
    ("second", "P2", 1),
  ):
    tasks.create_task(
      task_id, task_id, priority=priority, size=size, details=["Build."]
    )
  ids = lambda: [task.id for task, _ in tasks.list_tasks()]
  assert ids() == ["urgent", "second", "small-a", "small-b", "big"]
  original_order = tasks.get_task("small-b")[0].insertion_order
  tasks.patch_task("small-b", {"priority": "P1", "size": 1})
  assert ids() == ["small-b", "urgent", "second", "small-a", "big"]
  assert tasks.get_task("small-b")[0].insertion_order == original_order
  with pytest.raises(ValueError, match="lower-priority"):
    tasks.mod_deps_add("small-b", "big")
  tasks.patch_task("big", {"priority": "P1"})
  tasks.mod_deps_add("small-b", "big")
  assert ids().index("big") < ids().index("small-b")
  tasks.mod_deps_rm("small-b", "big")
  assert ids()[0] == "small-b"
  before_invalid_position = ids()
  with pytest.raises(ValueError, match="position"):
    tasks.patch_task("big", {"position": 0})
  assert ids() == before_invalid_position
  store.close()


@pytest.mark.parametrize(
  "finish_order", [("done-first", "done-second"), ("done-second", "done-first")]
)
@pytest.mark.parametrize("completion_spacing", [0, 1])
def test_finished_history_is_newest_first_when_active_rank_changes(
  tmp_path: Path,
  monkeypatch: pytest.MonkeyPatch,
  finish_order: tuple[str, str],
  completion_spacing: int,
) -> None:
  state_dir = tmp_path / "arena-state"
  store = SqliteStore(state_dir / "state.sqlite3")
  clock = _ReportTestClock()
  tasks = TaskService(store, store, clock=clock)
  tasks.create_task("done-first", "First", size=13, type="ops", details=["Ship."])
  tasks.create_task("done-second", "Second", size=1, type="ops", details=["Ship."])
  for task_id in finish_order:
    clock.advance(minutes=completion_spacing)
    tasks.finish_phase(task_id)
  clock.advance(minutes=1)
  tasks.patch_task(finish_order[0], {"title": "Edited after completion"})
  tasks.create_task("active", "Active", size=21, priority="P5", details=["Build."])
  tasks.patch_task("active", {"priority": "P1", "size": 1})
  expected_history = (
    list(reversed(finish_order))
    if completion_spacing
    else ["done-first", "done-second"]
  )
  expected = ["active", *expected_history]
  assert [task.id for task, _ in tasks.list_tasks(include_finished=True)] == expected
  app = SteeringApp(store)
  status, payload = app.dispatch("GET", "/tasks")
  assert status == HTTPStatus.OK
  assert [task["id"] for task in payload["tasks"]] == expected
  monkeypatch.setattr(cli, "resolve_state_dir", lambda: state_dir)
  monkeypatch.setattr(
    cli, "_healthy_server_url", lambda _state_dir: "http://127.0.0.1:8000"
  )
  out = io.StringIO()
  err = io.StringIO()
  assert cli.main(["tasks", "--finished"], out=out, err=err) == 0, err.getvalue()
  assert [
    line.split(" - ", 1)[0] for line in out.getvalue().splitlines()
  ] == expected_history
  store.close()


def test_new_insertion_order_never_reuses_deleted_high_water_mark(
  tmp_path: Path,
) -> None:
  path = tmp_path / "tasks.sqlite3"
  store = SqliteStore(path)
  tasks = TaskService(store, store)
  tasks.create_task("first", "First", size=3, details=["Build."])
  removed = tasks.create_task("removed", "Removed", size=3, details=["Build."])
  tasks.remove_task("removed")
  store.close()

  reopened = SqliteStore(path)
  tasks = TaskService(reopened, reopened)
  newest = tasks.create_task("newest", "Newest", size=3, details=["Build."])
  assert newest.insertion_order > removed.insertion_order
  assert [task.id for task, _ in tasks.list_tasks()] == ["first", "newest"]
  reopened.close()


def test_old_database_requires_individual_estimates_instead_of_a_generic_size(
  tmp_path: Path,
) -> None:
  path = tmp_path / "legacy.sqlite3"
  with sqlite3.connect(path) as conn:
    conn.execute(
      "CREATE TABLE tasks (position INTEGER NOT NULL, id TEXT PRIMARY KEY, "
      "title TEXT NOT NULL, type TEXT NOT NULL, status TEXT NOT NULL, scope TEXT NOT NULL, "
      "details_json TEXT NOT NULL DEFAULT '[]', msg_ids_json TEXT NOT NULL DEFAULT '[]', "
      "report_ids_json TEXT NOT NULL DEFAULT '[]', deps_json TEXT NOT NULL DEFAULT '[]', "
      "modified_at TEXT NOT NULL)"
    )
    conn.execute(
      "INSERT INTO tasks (position, id, title, type, status, scope, modified_at) "
      "VALUES (7, 'legacy', 'Legacy', 'ops', 'upcoming', '', '2026-11-01T00:00:00Z')"
    )
  store = SqliteStore(path)
  with pytest.raises(ValueError, match="size|estimate"):
    store.get_task("legacy")
  with store.transaction():
    store._conn.execute("UPDATE tasks SET size=5 WHERE id='legacy'")
  assert (store.get_task("legacy").priority, store.get_task("legacy").size) == ("P3", 5)
  assert store.get_task("legacy").insertion_order == 7
  store.close()


def test_api_requires_size_and_rejects_position_mutation() -> None:
  store = SqliteStore(":memory:")
  app = SteeringApp(store)
  body = {"id": "build", "title": "Build", "details": ["Do work."]}
  assert app.dispatch("POST", "/tasks", body)[0] == HTTPStatus.BAD_REQUEST
  for invalid in (None, 0, 4, 35, "5", True, 3.0):
    assert (
      app.dispatch("POST", "/tasks", {**body, "size": invalid})[0]
      == HTTPStatus.BAD_REQUEST
    )
  assert (
    app.dispatch("POST", "/tasks", {**body, "size": 5, "priority": "P0"})[0]
    == HTTPStatus.BAD_REQUEST
  )
  status, payload = app.dispatch("POST", "/tasks", {**body, "size": 5})
  assert status == HTTPStatus.CREATED
  assert (payload["task"]["priority"], payload["task"]["size"]) == ("P4", 5)
  assert (
    app.dispatch("PATCH", "/tasks/build", {"position": 0})[0] == HTTPStatus.BAD_REQUEST
  )
  assert (
    app.dispatch("PATCH", "/tasks/build", {"insertion_order": 10})[0]
    == HTTPStatus.BAD_REQUEST
  )
  for invalid in (0, 4, True, "3"):
    assert (
      app.dispatch("PATCH", "/tasks/build", {"size": invalid})[0]
      == HTTPStatus.BAD_REQUEST
    )
  status, changed = app.dispatch("PATCH", "/tasks/build", {"priority": "P1", "size": 8})
  assert status == HTTPStatus.OK
  assert changed["task"]["priority"] == "P1" and changed["task"]["size"] == 8
  status, fetched = app.dispatch("GET", "/tasks/build")
  assert status == HTTPStatus.OK and fetched["task"]["size"] == 8
  store.close()


def test_cli_requires_size_and_displays_values_only_in_details(
  tmp_path: Path,
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  monkeypatch.setattr(cli, "resolve_state_dir", lambda: tmp_path)

  def run(*args: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    code = cli.main(list(args), out=out, err=err)
    return code, out.getvalue(), err.getvalue()

  for options in ((), ("-z", "4"), ("-z", "5", "-p", "P0")):
    with pytest.raises(SystemExit) as exc:
      run("task", "new", "work", "Work", "-d", "Build.", *options)
    assert exc.value.code == 2
  code, created, err = run(
    "task", "new", "work", "Work", "-d", "Build.", "-z", "5", "-p", "P2"
  )
  assert code == 0, err
  assert "Priority: P2" in created and "Size: 5" in created
  assert run("tasks")[1].strip() == "work - Work"
  assert "Priority: P2" not in run("task")[1]
  assert "Priority: P2" in run("task", "-d")[1]
  assert run("task", "mod", "work", "size", "8")[0] == 0
  assert run("task", "mod", "work", "priority", "P1")[0] == 0
  assert "Priority: P1" in run("task", "work")[1]
  assert "Size: 8" in run("task", "work")[1]


def test_acknowledgement_task_creation_requires_a_size(
  tmp_path: Path,
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  monkeypatch.setattr(cli, "resolve_state_dir", lambda: tmp_path)
  store = SqliteStore(tmp_path / "state.sqlite3")
  SteeringApp(store).messages.send_message("Create a task", msg_id="ab1200")
  store.close()

  def run(*args: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    code = cli.main(list(args), out=out, err=err)
    return code, out.getvalue(), err.getvalue()

  options = (
    "ack",
    "ab1200",
    "Read",
    "-i",
    "new-work",
    "-t",
    "New work",
    "-d",
    "Build.",
  )
  code, _, err = run(*options)
  assert code != 0 and "-z/--size" in err
  store = SqliteStore(tmp_path / "state.sqlite3")
  assert store.get_task("new-work") is None
  assert store.get_message("ab1200").acks == []
  store.close()

  code, _, err = run(*options, "-z", "5", "-p", "P2")
  assert code == 0, err
  store = SqliteStore(tmp_path / "state.sqlite3")
  task = store.get_task("new-work")
  assert task is not None and (task.priority, task.size) == ("P2", 5)
  store.close()


def test_state_import_rejects_missing_estimate_but_preserves_it_on_old_peer_edit() -> (
  None
):
  source = SqliteStore(":memory:")
  TaskService(source, source).create_task(
    "work", "Work", size=8, priority="P2", details=["Build."]
  )
  document = source.export_rows()
  target = SqliteStore(":memory:")
  old_row = dict(document["tasks"][0])
  for field in ("size", "priority", "priority_explicit", "insertion_order"):
    old_row.pop(field)
  with pytest.raises(ValueError, match="size"):
    target.merge_rows({"tasks": [old_row]})
  assert target.get_task("work") is None

  target.merge_rows(document)
  before = target.get_task("work")
  assert before is not None
  old_row["modified_at"] = "2099-01-01T00:00:00Z"
  old_row["title"] = "Older client edited title"
  target.merge_rows({"tasks": [old_row]})
  after = target.get_task("work")
  assert after is not None
  assert (
    after.priority,
    after.priority_explicit,
    after.size,
    after.insertion_order,
  ) == (
    before.priority,
    before.priority_explicit,
    before.size,
    before.insertion_order,
  )
  assert after.title == "Older client edited title"
  target.close()
  source.close()


@pytest.mark.parametrize(
  "field,value",
  [
    ("size", 4),
    ("size", "3"),
    ("size", True),
    ("priority", "P0"),
    ("insertion_order", -1),
  ],
)
def test_state_import_rejects_invalid_rank_fields(field: str, value: object) -> None:
  source = SqliteStore(":memory:")
  TaskService(source, source).create_task("work", "Work", size=3, details=["Build."])
  row = dict(source.export_rows()["tasks"][0])
  row[field] = value
  target = SqliteStore(":memory:")
  with pytest.raises(ValueError, match=f"Task.{field}"):
    target.merge_rows({"tasks": [row]})
  assert target.get_task("work") is None
  target.close()
  source.close()


def test_ui_values_are_escaped_and_inside_details_only() -> None:
  task = Task("task", "Work <now>", size=5, priority="P2", details=["Build."])
  script = """
import assert from 'node:assert/strict';
import { renderTasksView } from './skills/arena-steering/assets/tasks-view.js';
const container = {
  innerHTML: '', scrollTop: 0,
  querySelector() { return null; },
  querySelectorAll() { return []; },
};
renderTasksView(container, { tasks: JSON.parse(process.argv[1]) });
const markup = container.innerHTML;
assert.doesNotMatch(markup.split('<details')[0], /Priority: P2|Size: 5/);
assert.match(markup, /<details[^>]*>[\\s\\S]*Priority: P2[\\s\\S]*Size: 5[\\s\\S]*<\\/details>/);
assert.match(markup, /Work &lt;now&gt;/);
"""
  result = subprocess.run(
    [
      "node",
      "--experimental-default-type=module",
      "--input-type=module",
      "-e",
      script,
      json.dumps([task.to_dict()]),
    ],
    cwd=Path(__file__).resolve().parents[3],
    check=False,
    capture_output=True,
    text=True,
    encoding="utf-8",
  )
  assert result.returncode == 0, result.stderr


def test_dependency_priority_rejects_lower_priority_but_not_larger_size():
  store = SqliteStore(":memory:")
  tasks = TaskService(store, store)
  tasks.create_task("urgent", "Urgent", priority="P2", size=1, details=["Work."])
  tasks.create_task("later", "Later", priority="P3", size=21, details=["Work."])
  with pytest.raises(ValueError, match="priority"):
    tasks.mod_deps_add("urgent", "later")
  with pytest.raises(ValueError, match="priority"):
    tasks.create_task(
      "new", "New", priority="P1", size=1, details=["Work."], deps=["later"]
    )
  tasks.mod_deps_add("later", "urgent")
  with pytest.raises(ValueError, match="priority"):
    tasks.patch_task("urgent", {"priority": "P4"})
  with pytest.raises(ValueError, match="priority"):
    tasks.patch_task("later", {"priority": "P1"})
  assert tasks.get_task("urgent")[0].priority == "P2"
  assert tasks.get_task("later")[0].priority == "P3"
  store.close()


def test_existing_task_message_links_require_atomic_detail_change(
  tmp_path: Path,
) -> None:
  store = SqliteStore(tmp_path / "state.sqlite3")
  app = SteeringApp(store)
  app.messages.send_message("New work", msg_id="abc123", blocking=False)
  tasks = app.tasks
  tasks.create_task("work", "Work", size=2, details=["First", "Second"])
  expected_error = (
    "Adding a message link requires an added or deleted task detail. "
    "Are you sure this message needs to be linked? "
    "Does it hold any new evidence for completing the task?"
  )
  with pytest.raises(ValueError) as exc_info:
    tasks.mod_links_add("work", "abc123", link_type="msg")
  assert str(exc_info.value) == expected_error
  with pytest.raises(ValueError) as patch_exc:
    tasks.patch_task("work", {"msg_ids": ["abc123"], "details": ["Second", "First"]})
  assert str(patch_exc.value) == expected_error
  unchanged = tasks.get_task("work")[0]
  assert unchanged.msg_ids == []
  assert unchanged.details == ["First", "Second"]
  linked = tasks.patch_task(
    "work", {"msg_ids": ["abc123"], "details": ["First"], "size": 2}
  )
  assert linked.msg_ids == ["abc123"]
  assert linked.details == ["First"]
  tasks.mod_links_add("work", "abc123", link_type="msg")
  app.messages.send_message("More work", msg_id="abc124", blocking=False)
  linked = tasks.mod_links_add(
    "work", "abc124", link_type="msg", append_detail="More", size=2
  )
  assert linked.msg_ids == ["abc123", "abc124"]
  assert linked.details == ["First", "More"]
  store.close()


def test_task_detail_changes_require_explicit_size(tmp_path: Path) -> None:
  store = SqliteStore(tmp_path / "state.sqlite3")
  app = SteeringApp(store)
  app.messages.send_message("Note", msg_id="ab2001", blocking=False)
  app.reports.publish_report("doc", "Doc", "# Plain\n")
  tasks = app.tasks
  tasks.create_task("work", "Work", size=3, details=["First", "Second"])

  with pytest.raises(ValueError, match="size"):
    tasks.mod_deets("work", "Third")
  with pytest.raises(ValueError, match="size"):
    tasks.mod_deets_rm("work", 2)
  with pytest.raises(ValueError, match="size"):
    tasks.mod_links_add("work", "ab2001", link_type="msg", append_detail="Added")
  with pytest.raises(ValueError, match="size"):
    tasks.mod_links_add("work", "doc", link_type="report", remove_detail=2)
  with pytest.raises(ValueError, match="size"):
    tasks.patch_task("work", {"details": ["First", "Second", "Third"]})
  with pytest.raises(ValueError, match="size"):
    tasks.patch_task("work", {"details": ["First"]})

  same_size = tasks.mod_deets("work", "Third", size=3)
  assert (same_size.size, same_size.details) == (3, ["First", "Second", "Third"])
  resized = tasks.mod_deets_rm("work", 2, size=5)
  assert (resized.size, resized.details) == (5, ["First", "Third"])
  linked = tasks.mod_links_add(
    "work", "ab2001", link_type="msg", append_detail="Linked", size=5
  )
  assert (linked.size, linked.details) == (5, ["First", "Third", "Linked"])
  patched = tasks.patch_task("work", {"details": ["First", "Linked"], "size": 8})
  assert (patched.size, patched.details) == (8, ["First", "Linked"])
  unchanged = tasks.patch_task("work", {"title": "Renamed"})
  assert unchanged.title == "Renamed"
  tasks.mod_links_add("work", "doc", link_type="report")
  store.close()


def test_skip_poll_health_cancel_and_explicit_arming() -> None:
  store = SqliteStore()
  app = SteeringApp(store)
  try:
    assert app.dispatch("GET", "/health")[1]["skip_poll"] is False
    assert app.dispatch("POST", "/poll/skip")[1] == {"skip_poll": True}
    assert app.messages.skip_poll_armed()
    assert app.dispatch("GET", "/health")[1]["skip_poll"] is True
    assert app.dispatch("DELETE", "/poll/skip") == (200, {"skip_poll": False})
    assert not app.messages.skip_poll_armed()
    assert app.messages.poll(timeout_seconds=0.01)["status"] == "timeout"
    app.messages.trigger_skip_poll()
    assert app.messages.consume_skip_poll()
    assert not app.messages.skip_poll_armed()
    app.messages.trigger_bible_check(True)
    assert app.messages.get_survey()["pending"]
    assert not app.messages.skip_poll_armed()
  finally:
    store.close()
