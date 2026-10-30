"""Domain services for Messages, Tasks, and Reports in Arena Steering."""

from __future__ import annotations

import json
import re
import threading
from functools import wraps
from typing import Any

from . import survey as survey_mod
from .markdown import render_report_markdown, unparsed_strike_lines
from .markdown_fields import format_answer_for_task_detail, parse_report_markdown
from .models import (
  MESSAGE_ID_RE,
  Attachment,
  Message,
  Report,
  ReportAnswer,
  ReportField,
  Task,
  validate_entity_id,
  validate_hex_id,
)
from .ports import (
  Clock,
  GateStatus,
  IdGenerator,
  MessageRepository,
  MetaRepository,
  ReportRepository,
  SecretsHexIdGenerator,
  TaskRepository,
  UtcClock,
)

DEFAULT_SURVEY_QUESTIONS: tuple[dict[str, Any], ...] = tuple(
  {
    "id": q["id"],
    "prompt": q["question"],
    "question": q["question"],
    "deterministic": bool(q.get("deterministic")),
    "answer_fields": dict(q["answer_fields"]),
  }
  for q in survey_mod.SPEC["questions"]
)


def _append_snapshot(task: Task, report: Report, answer: ReportAnswer) -> None:
  if not any(
    item.get("id") == answer.id and item.get("report_id") == report.id
    for item in task.answer_snapshots
  ):
    task.answer_snapshots.append(json.loads(json.dumps(answer.snapshot(report))))


def _transactional_report_write(method: Any) -> Any:
  @wraps(method)
  def wrapped(self: Any, *args: Any, **kwargs: Any) -> Any:
    with self._reports.transaction():
      return method(self, *args, **kwargs)

  return wrapped


class MessageService:
  """Manage steering messages, status transitions, acknowledgements, and polling."""

  def __init__(
    self,
    messages: MessageRepository,
    reports: ReportRepository,
    meta: MetaRepository,
    clock: Clock | None = None,
    id_gen: IdGenerator | None = None,
  ) -> None:
    self._messages = messages
    self._reports = reports
    self._meta = meta
    self._clock = clock or UtcClock()
    self._id_gen = id_gen or SecretsHexIdGenerator()
    self._cond = threading.Condition()

  def send_message(
    self,
    body: str,
    *,
    hidden: bool = False,
    blocking: bool = True,
    attachments: list[Attachment] | None = None,
    parent_ids: list[str] | None = None,
    msg_id: str | None = None,
    request_id: str | None = None,
    fingerprint: str = "",
  ) -> Message:
    if not isinstance(body, str) or (not body.strip() and not attachments):
      raise ValueError("Message body or attachment is required")
    resolved_parent_ids: list[str] = []
    for parent_id in parent_ids or []:
      validate_hex_id(parent_id, "Message.parent_ids")
      if parent_id in resolved_parent_ids:
        continue
      if self._messages.get_message(parent_id) is None:
        raise KeyError(f"Unknown parent message ID: {parent_id}")
      resolved_parent_ids.append(parent_id)
    resolved_id = (
      validate_hex_id(msg_id, "Message.id")
      if msg_id is not None
      else self._unique_hex_id()
    )
    now = self._clock.now_iso()
    message = Message(
      id=resolved_id,
      body=body,
      hidden=hidden,
      blocking=blocking,
      attachments=list(attachments or []),
      parent_ids=resolved_parent_ids,
      status="sent",
      acks=[],
      modified_at=now,
    )
    with self._cond:
      if request_id is not None:
        message = self._messages.save_message_once(message, request_id, fingerprint)
      else:
        self._messages.save_message(message)
      self._cond.notify_all()
    return message

  def get_message(self, msg_id: str) -> Message:
    validate_hex_id(msg_id, "Message.id")
    msg = self._messages.get_message(msg_id)
    if msg is None:
      raise KeyError(f"Unknown message ID: {msg_id}")
    return msg

  def list_message_page(
    self,
    *,
    unread_only: bool,
    include_hidden: bool,
    query: str,
    before: str,
    limit: int,
  ) -> tuple[list[Message], int, bool]:
    return self._messages.list_message_page(
      unread_only=unread_only,
      include_hidden=include_hidden,
      query=query,
      before=before,
      limit=limit,
    )

  def list_messages(
    self,
    *,
    unread_only: bool = False,
    include_hidden: bool = True,
    newest_first: bool = False,
    page: int = 1,
    page_size: int | None = None,
  ) -> list[Message]:
    items = self._messages.list_messages(
      unread_only=unread_only, include_hidden=include_hidden
    )
    if newest_first:
      items = list(reversed(items))
    if page_size is not None:
      if page < 1 or page_size < 1:
        raise ValueError("page and page_size must be positive integers")
      start = (page - 1) * page_size
      items = items[start : start + page_size]
    return items

  def has_pending_deliverables(self) -> bool:
    for msg in self._messages.list_messages(unread_only=True, include_hidden=True):
      if msg.status == "sent" or msg.requires_ack:
        return True
    for report in self._reports.list_reports():
      if report.latest_unacked_answer is not None:
        return True
    return False

  @_transactional_report_write
  def read_pending(self, *, mark_seen: bool = True) -> dict[str, Any]:
    """Return pending unread messages and unacknowledged report answers."""
    now = self._clock.now_iso()
    delivered_messages: list[Message] = []
    for msg in self._messages.list_messages(unread_only=True, include_hidden=True):
      if mark_seen and msg.status == "sent":
        msg = self._messages.mark_message_seen(msg.id, now)
      delivered_messages.append(msg)

    delivered_answers: list[tuple[Report, ReportAnswer]] = []
    for report in self._reports.list_reports():
      latest = report.latest_unacked_answer
      if latest is not None:
        if mark_seen and latest.status == "sent":
          latest.status = "seen"
          latest.modified_at = now
          report.modified_at = now
          self._reports.save_report(report)
        delivered_answers.append((report, latest))

    return {
      "messages": delivered_messages,
      "report_answers": delivered_answers,
    }

  def resolve_ack_target(
    self, target_id: str | None
  ) -> tuple[str, Message | ReportAnswer]:
    """Resolve an acknowledgement target without changing it."""
    if target_id is None:
      target_id = self._resolve_single_pending_id()
    validate_hex_id(target_id, "Acknowledgement target ID")
    message = self._messages.get_message(target_id)
    if message is not None:
      return "message", message
    for report in self._reports.list_reports():
      for answer in report.answers:
        if answer.id == target_id:
          return "report_answer", answer
    raise KeyError(f"Unknown message or answer ID: {target_id}")

  @_transactional_report_write
  def ack(
    self, target_id: str | None, markdown: str
  ) -> tuple[str, Message | ReportAnswer]:
    """Acknowledge a message or report answer by appending a Markdown reply."""
    if not isinstance(markdown, str) or not markdown.strip():
      raise ValueError("Acknowledgement Markdown cannot be empty")
    reply = markdown.strip()
    now = self._clock.now_iso()

    if target_id is None:
      target_id = self._resolve_single_pending_id()

    validate_hex_id(target_id, "Acknowledgement target ID")
    msg = self._messages.get_message(target_id)
    if msg is not None:
      return ("message", self._messages.append_message_ack(target_id, reply, now))

    for report in self._reports.list_reports():
      for ans in report.answers:
        if ans.id == target_id:
          ans.acks.append(reply)
          ans.status = "acked"
          ans.modified_at = now
          report.ack_seen = False
          report.modified_at = now
          self._reports.save_report(report)
          return ("report_answer", ans)

    raise KeyError(f"Unknown message or answer ID: {target_id}")

  def mark_replies_seen(self, msg_id: str, revision: str) -> bool:
    validate_hex_id(msg_id, "Message.id")
    if not isinstance(revision, str) or not re.fullmatch(r"[0-9a-f]{64}", revision):
      raise ValueError("Reply revision must be a SHA-256 hex digest")
    return self._messages.mark_replies_seen(msg_id, revision)

  def trigger_skip_poll(self) -> None:
    with self._cond:
      self._meta.set_meta("skip_poll", "1")
      self._cond.notify_all()

  def consume_skip_poll(self) -> bool:
    with self._cond:
      flag = self._meta.get_meta("skip_poll", "0") == "1"
      if flag:
        self._meta.set_meta("skip_poll", "0")
      return flag

  def poll(self, timeout_seconds: float = 0.0) -> dict[str, Any]:
    """Wait up to timeout_seconds for pending deliverables or skip_poll."""
    deadline_remaining = max(0.0, min(float(timeout_seconds), 1799.0))
    with self._cond:
      if (
        not self.has_pending_deliverables()
        and not self.consume_skip_poll()
        and deadline_remaining > 0
      ):
        self._cond.wait(timeout=deadline_remaining)
        self.consume_skip_poll()
    return self.read_pending(mark_seen=True)

  def notify_new_work(self) -> None:
    with self._cond:
      self._cond.notify_all()

  def get_survey(self) -> dict[str, Any]:
    """Return current survey state, questions, template, and graded results."""
    raw_answers = self._meta.get_meta("survey_answers_json", "{}") or "{}"
    raw_results = self._meta.get_meta("survey_results_json", "[]") or "[]"
    try:
      answers = json.loads(raw_answers)
      if not isinstance(answers, dict):
        answers = {}
    except json.JSONDecodeError:
      answers = {}
    try:
      results = json.loads(raw_results)
      if not isinstance(results, list):
        results = []
    except json.JSONDecodeError:
      results = []
    checked_at = self._meta.get_meta("survey_checked_at", "") or ""
    return {
      "pending": self._meta.get_meta("bible_interrupt", "0") == "1",
      "checked_at": checked_at,
      "answered_at": checked_at,
      "questions": [dict(item) for item in DEFAULT_SURVEY_QUESTIONS],
      "template": survey_mod.template(),
      "results": results,
      "answers": {str(k): str(v) for k, v in answers.items()},
    }

  def submit_survey(self, values: Any) -> dict[str, Any]:
    """Grade and record agent survey answers, rejecting any null values."""
    current = self.get_survey()["answers"]
    results: list[dict[str, Any]] = self.get_survey()["results"]
    if isinstance(values, list):
      raw_text = json.dumps(values, ensure_ascii=False)
      results = survey_mod.grade(raw_text)
      for row in results:
        current[str(row["id"])] = json.dumps(row["answer"], ensure_ascii=False)
    elif isinstance(values, str):
      stripped = values.strip()
      if not stripped:
        raise ValueError("Survey submission must not be empty")
      results = survey_mod.grade(stripped)
      for row in results:
        current[str(row["id"])] = json.dumps(row["answer"], ensure_ascii=False)
    elif isinstance(values, dict) and values:
      for key, val in values.items():
        if val is None:
          raise ValueError(f"Survey answer for {key!r} must not be null; use 'unknown'")
        text = str(val).strip()
        if not text:
          raise ValueError(f"Survey answer for {key!r} cannot be empty")
        current[str(key).strip()] = text
    else:
      raise ValueError("Survey submission must be a JSON array or non-empty dictionary")
    now = self._clock.now_iso()
    with self._cond:
      self._meta.set_meta("survey_answers_json", json.dumps(current))
      self._meta.set_meta("survey_results_json", json.dumps(results))
      self._meta.set_meta("survey_checked_at", now)
      self._meta.set_meta("bible_interrupt", "0")
      self._cond.notify_all()
    return self.get_survey()

  def trigger_bible_check(self, active: bool | None = None) -> dict[str, Any]:
    """Toggle or set the bible check interrupt flag and wake any waiting poll."""
    with self._cond:
      cur = self._meta.get_meta("bible_interrupt", "0") == "1"
      next_state = (not cur) if active is None else bool(active)
      self._meta.set_meta("bible_interrupt", "1" if next_state else "0")
      if next_state:
        self._meta.set_meta("skip_poll", "1")
      self._cond.notify_all()
    return self.get_survey()

  def _resolve_single_pending_id(self) -> str:
    candidates: list[str] = [
      msg.id
      for msg in self._messages.list_messages(unread_only=True, include_hidden=True)
      if msg.requires_ack
    ]
    for report in self._reports.list_reports():
      latest = report.latest_unacked_answer
      if latest is not None:
        candidates.append(latest.id)
    if not candidates:
      raise ValueError("No pending message or report answer requires acknowledgement")
    if len(candidates) > 1:
      raise ValueError(
        f"Multiple items require acknowledgement ({', '.join(candidates)}); pass an explicit ID"
      )
    return candidates[0]

  def _unique_hex_id(self) -> str:
    for _ in range(64):
      candidate = self._id_gen.new_hex_id()
      if self._messages.get_message(candidate) is None:
        return candidate
    raise RuntimeError("Unable to allocate unique 6-character hex ID")


def _transactional_task_write(method: Any) -> Any:
  @wraps(method)
  def wrapped(self: Any, *args: Any, **kwargs: Any) -> Any:
    with self._tasks.transaction():
      return method(self, *args, **kwargs)

  return wrapped


class TaskService:
  """Manage the mutable task queue, dependency ordering, and derived blocking."""

  def __init__(
    self,
    tasks: TaskRepository,
    reports: ReportRepository,
    clock: Clock | None = None,
    gates: GateStatus | None = None,
  ) -> None:
    self._tasks = tasks
    self._reports = reports
    self._clock = clock or UtcClock()
    self._gates = gates

  def is_task_blocked(
    self,
    task: Task,
    *,
    task_map: dict[str, Task] | None = None,
    report_map: dict[str, Report] | None = None,
  ) -> bool:
    """Derive blocking from unanswered linked reports and unfinished dependencies."""
    if task.status == "finished":
      return False
    if task.status == "blocked":
      return True
    if self._gates is not None and any(
      self._gates.is_running(gate) for gate in task.gate_names
    ):
      return True
    tasks_by_id = (
      task_map
      if task_map is not None
      else {item.id: item for item in self._tasks.list_tasks()}
    )
    reports_by_id = (
      report_map
      if report_map is not None
      else {item.id: item for item in self._reports.list_reports()}
    )
    for dep_id in task.deps:
      dep_task = tasks_by_id.get(dep_id)
      if dep_task is not None and dep_task.status != "finished":
        return True
    for rep_id in task.report_ids:
      report = reports_by_id.get(rep_id)
      if report is not None and (
        report.needs_answer or report.latest_unacked_answer is not None
      ):
        return True
    return False

  def list_tasks(self, *, include_finished: bool = False) -> list[tuple[Task, bool]]:
    queue = self._tasks.list_tasks()
    task_map = {item.id: item for item in queue}
    report_map = {item.id: item for item in self._reports.list_reports()}
    result: list[tuple[Task, bool]] = []
    for item in queue:
      if not include_finished and item.status == "finished":
        continue
      blocked = self.is_task_blocked(item, task_map=task_map, report_map=report_map)
      result.append((item, blocked))
    return result

  def get_task(self, task_id: str) -> tuple[Task, bool]:
    validate_entity_id(task_id, "Task.id")
    task = self._tasks.get_task(task_id)
    if task is None:
      raise KeyError(f"Unknown task ID: {task_id}")
    return (task, self.is_task_blocked(task))

  @_transactional_task_write
  def create_task(
    self,
    task_id: str,
    title: str,
    *,
    type: str = "code",
    status: str = "upcoming",
    scope: str = "",
    details: list[str] | None = None,
    links: dict[str, list[str]] | None = None,
    msg_ids: list[str] | None = None,
    report_ids: list[str] | None = None,
    task_ids: list[str] | None = None,
    deps: list[str] | None = None,
    gate_names: list[str] | None = None,
  ) -> Task:
    if self._tasks.get_task(task_id) is not None:
      raise ValueError(f"Task {task_id!r} already exists")
    now = self._clock.now_iso()
    task = Task(
      id=task_id,
      title=title,
      type=type,
      status=status,
      scope=scope,
      details=list(details or []),
      links=links,
      msg_ids=list(msg_ids) if msg_ids is not None else None,
      report_ids=list(report_ids) if report_ids is not None else None,
      task_ids=list(task_ids) if task_ids is not None else None,
      deps=list(deps) if deps is not None else None,
      gate_names=list(gate_names) if gate_names is not None else None,
      modified_at=now,
    )
    self._validate_details(task)
    self._add_report_snapshots(task)
    queue = self._tasks.list_tasks()
    self._validate_deps_exist(task, queue)
    ordered = self._enforce_dependency_order([*queue, task])
    self._tasks.save_task_queue(ordered)
    return task

  @_transactional_task_write
  def remove_task(self, task_id: str) -> bool:
    validate_entity_id(task_id, "Task.id")
    queue = self._tasks.list_tasks()
    remaining = [item for item in queue if item.id != task_id]
    if len(remaining) == len(queue):
      return False
    now = self._clock.now_iso()
    for item in remaining:
      if task_id in item.task_ids:
        item.task_ids = [dep for dep in item.task_ids if dep != task_id]
        item.modified_at = now
    self._tasks.save_task_queue(remaining)
    return True

  @_transactional_task_write
  def rename_task(self, old_task_id: str, new_task_id: str) -> Task:
    validate_entity_id(old_task_id, "Task.id")
    validate_entity_id(new_task_id, "Task.id")
    if old_task_id == new_task_id:
      task, _blocked = self.get_task(old_task_id)
      return task
    queue, target = self._load_queue_and_target(old_task_id)
    if any(item.id == new_task_id for item in queue):
      raise ValueError(f"Task {new_task_id!r} already exists")
    now = self._clock.now_iso()
    renamed = Task(
      id=new_task_id,
      title=target.title,
      type=target.type,
      status=target.status,
      scope=target.scope,
      details=target.details,
      answer_snapshots=target.answer_snapshots,
      links=target.links,
      modified_at=now,
    )
    self._validate_details(renamed)
    updated_queue: list[Task] = []
    for item in queue:
      if item.id == old_task_id:
        updated_queue.append(renamed)
        continue
      if old_task_id in item.task_ids:
        item.task_ids = [
          new_task_id if dep_id == old_task_id else dep_id for dep_id in item.task_ids
        ]
        item.modified_at = now
      updated_queue.append(item)
    ordered = self._enforce_dependency_order(updated_queue)
    self._tasks.save_task_queue(ordered)
    return renamed

  @_transactional_task_write
  def unlink_task(
    self, task_id: str, link_id: str, *, link_type: str | None = None
  ) -> Task:
    if link_type is not None:
      return self.mod_links_rm(task_id, link_type, link_id)
    queue, target = self._load_queue_and_target(task_id)
    cleaned_id = link_id.strip()
    updated = Task(
      id=target.id,
      title=target.title,
      type=target.type,
      status=target.status,
      scope=target.scope,
      details=target.details,
      answer_snapshots=target.answer_snapshots,
      links={
        "msg_ids": [item for item in target.msg_ids if item != cleaned_id],
        "report_ids": [item for item in target.report_ids if item != cleaned_id],
        "task_ids": [item for item in target.task_ids if item != cleaned_id],
        "gate_names": [item for item in target.gate_names if item != cleaned_id],
      },
      modified_at=self._clock.now_iso(),
    )
    if updated.links == target.links:
      raise ValueError(f"Task {task_id!r} has no link {cleaned_id!r}")
    self._replace_in_queue(queue, updated)
    return updated

  @_transactional_task_write
  def mod_deets(self, task_id: str, detail: str) -> Task:
    queue, target = self._load_queue_and_target(task_id)
    updated = Task(
      id=target.id,
      title=target.title,
      type=target.type,
      status=target.status,
      scope=target.scope,
      details=[*target.details, detail],
      answer_snapshots=target.answer_snapshots,
      links=target.links,
      modified_at=self._clock.now_iso(),
    )
    self._replace_in_queue(queue, updated)
    return updated

  @_transactional_task_write
  def mod_deets_rm(self, task_id: str, number: int) -> Task:
    queue, target = self._load_queue_and_target(task_id)
    idx = number - 1 if number >= 1 else number
    if idx < 0 or idx >= len(target.details):
      raise IndexError(
        f"Detail number {number} out of range (1..{len(target.details)})"
      )
    new_details = [item for i, item in enumerate(target.details) if i != idx]
    updated = Task(
      id=target.id,
      title=target.title,
      type=target.type,
      status=target.status,
      scope=target.scope,
      details=new_details,
      answer_snapshots=target.answer_snapshots,
      links=target.links,
      modified_at=self._clock.now_iso(),
    )
    self._replace_in_queue(queue, updated)
    return updated

  @_transactional_task_write
  def mod_links_add(
    self, task_id: str, link_id: str, *, link_type: str | None = None
  ) -> Task:
    queue, target = self._load_queue_and_target(task_id)
    cleaned = link_id.strip()
    explicit_type = link_type.strip().lower() if link_type else None
    msg_ids = list(target.msg_ids)
    report_ids = list(target.report_ids)
    task_ids = list(target.task_ids)
    gate_names = list(target.gate_names)
    known_task_ids = {item.id for item in queue}

    if explicit_type == "gate":
      if cleaned not in gate_names:
        gate_names.append(cleaned)
    elif explicit_type in {"task", "dep", "deps"} or (
      explicit_type is None and cleaned in known_task_ids
    ):
      validate_entity_id(cleaned, "Dependency task ID")
      if cleaned not in task_ids:
        task_ids.append(cleaned)
    elif explicit_type == "msg" or (
      explicit_type is None
      and MESSAGE_ID_RE.fullmatch(cleaned)
      and self._reports.get_report(cleaned) is None
    ):
      if cleaned not in msg_ids:
        msg_ids.append(cleaned)
    elif explicit_type in {None, "report"}:
      validate_entity_id(cleaned, "Report or message link ID")
      if cleaned not in report_ids:
        report_ids.append(cleaned)
    else:
      raise ValueError(
        f"Link type must be 'msg', 'report', 'task', or 'gate', got {link_type!r}"
      )

    updated = Task(
      id=target.id,
      title=target.title,
      type=target.type,
      status=target.status,
      scope=target.scope,
      details=target.details,
      answer_snapshots=target.answer_snapshots,
      links={
        "msg_ids": msg_ids,
        "report_ids": report_ids,
        "task_ids": task_ids,
        "gate_names": gate_names,
      },
      modified_at=self._clock.now_iso(),
    )
    self._validate_deps_exist(updated, queue)
    self._replace_in_queue(queue, updated)
    return updated

  @_transactional_task_write
  def mod_links_rm(self, task_id: str, link_type: str, link_id: str) -> Task:
    queue, target = self._load_queue_and_target(task_id)
    cleaned_type = link_type.strip().lower()
    cleaned_id = link_id.strip()
    if cleaned_type not in {"msg", "report", "task", "dep", "deps", "gate"}:
      raise ValueError(
        f"Link type must be 'msg', 'report', 'task', or 'gate', got {link_type!r}"
      )
    msg_ids = (
      [item for item in target.msg_ids if item != cleaned_id]
      if cleaned_type == "msg"
      else list(target.msg_ids)
    )
    report_ids = (
      [item for item in target.report_ids if item != cleaned_id]
      if cleaned_type == "report"
      else list(target.report_ids)
    )
    task_ids = (
      [item for item in target.task_ids if item != cleaned_id]
      if cleaned_type in {"task", "dep", "deps"}
      else list(target.task_ids)
    )
    gate_names = (
      [item for item in target.gate_names if item != cleaned_id]
      if cleaned_type == "gate"
      else list(target.gate_names)
    )
    updated = Task(
      id=target.id,
      title=target.title,
      type=target.type,
      status=target.status,
      scope=target.scope,
      details=target.details,
      answer_snapshots=target.answer_snapshots,
      links={
        "msg_ids": msg_ids,
        "report_ids": report_ids,
        "task_ids": task_ids,
        "gate_names": gate_names,
      },
      modified_at=self._clock.now_iso(),
    )
    self._replace_in_queue(queue, updated)
    return updated

  @_transactional_task_write
  def mod_deps_add(self, task_id: str, dep_task_id: str) -> Task:
    return self.mod_links_add(task_id, dep_task_id, link_type="task")

  @_transactional_task_write
  def mod_deps_rm(self, task_id: str, dep_task_id: str) -> Task:
    return self.mod_links_rm(task_id, "task", dep_task_id)

  @_transactional_task_write
  def mod_scalar(self, task_id: str, field_name: str, value: str) -> Task:
    queue, target = self._load_queue_and_target(task_id)
    key = field_name.strip().lower()
    if key not in {"status", "title", "type", "scope"}:
      raise ValueError(f"Unsupported scalar task field: {field_name!r}")
    kwargs: dict[str, Any] = {
      "id": target.id,
      "title": target.title,
      "type": target.type,
      "status": target.status,
      "scope": target.scope,
      "details": target.details,
      "answer_snapshots": target.answer_snapshots,
      "links": target.links,
      "modified_at": self._clock.now_iso(),
    }
    kwargs[key] = value
    updated = Task(**kwargs)
    self._replace_in_queue(queue, updated)
    return updated

  @_transactional_task_write
  def patch_task(
    self, task_id: str, changes: dict[str, Any], *, position: int | None = None
  ) -> Task:
    """Apply partial updates and optional queue position change for HTTP PATCH."""
    queue, target = self._load_queue_and_target(task_id)
    raw_links = changes.get("links")
    merged_links = {
      "gate_names": list(
        changes.get(
          "gate_names",
          raw_links.get("gate_names", target.gate_names)
          if isinstance(raw_links, dict)
          else target.gate_names,
        )
      ),
      "msg_ids": list(
        changes.get(
          "msg_ids",
          raw_links.get("msg_ids", target.msg_ids)
          if isinstance(raw_links, dict)
          else target.msg_ids,
        )
      ),
      "report_ids": list(
        changes.get(
          "report_ids",
          raw_links.get("report_ids", target.report_ids)
          if isinstance(raw_links, dict)
          else target.report_ids,
        )
      ),
      "task_ids": list(
        changes.get(
          "task_ids",
          changes.get(
            "deps",
            raw_links.get("task_ids", target.task_ids)
            if isinstance(raw_links, dict)
            else target.task_ids,
          ),
        )
      ),
    }
    updated = Task(
      id=target.id,
      title=str(changes.get("title", target.title)),
      type=str(changes.get("type", target.type)),
      status=str(changes.get("status", target.status)),
      scope=str(changes.get("scope", target.scope)),
      details=list(changes.get("details", target.details)),
      answer_snapshots=target.answer_snapshots,
      links=merged_links,
      modified_at=self._clock.now_iso(),
    )
    self._validate_details(updated)
    self._add_report_snapshots(updated)
    self._validate_deps_exist(updated, queue)
    new_queue = [updated if item.id == task_id else item for item in queue]
    if position is not None:
      new_queue = [item for item in new_queue if item.id != task_id]
      clamped = max(0, min(int(position), len(new_queue)))
      new_queue.insert(clamped, updated)
    ordered = self._enforce_dependency_order(new_queue)
    self._tasks.save_task_queue(ordered)
    return updated

  def _load_queue_and_target(self, task_id: str) -> tuple[list[Task], Task]:
    validate_entity_id(task_id, "Task.id")
    queue = self._tasks.list_tasks()
    for item in queue:
      if item.id == task_id:
        return queue, item
    raise KeyError(f"Unknown task ID: {task_id}")

  def _add_report_snapshots(self, task: Task) -> None:
    for report_id in task.report_ids:
      report = self._reports.get_report(report_id)
      if report is not None:
        for answer in report.answers:
          _append_snapshot(task, report, answer)

  def _replace_in_queue(self, queue: list[Task], updated: Task) -> None:
    self._validate_details(updated)
    self._add_report_snapshots(updated)
    replaced = [updated if item.id == updated.id else item for item in queue]
    ordered = self._enforce_dependency_order(replaced)
    self._tasks.save_task_queue(ordered)

  @staticmethod
  def _validate_details(task: Task) -> None:
    if not task.details:
      raise ValueError("Task requires at least one detail")

  @staticmethod
  def _validate_deps_exist(task: Task, existing_queue: list[Task]) -> None:
    known_ids = {item.id for item in existing_queue if item.id != task.id}
    for dep_id in task.deps:
      if dep_id == task.id:
        raise ValueError(f"Task {task.id!r} cannot depend on itself")
      if dep_id not in known_ids:
        raise ValueError(f"Unknown dependency task ID: {dep_id!r}")

  @staticmethod
  def _enforce_dependency_order(tasks: list[Task]) -> list[Task]:
    """Place every dependent task behind all of its dependencies in the queue."""
    task_map = {item.id: item for item in tasks}
    visited: dict[str, int] = {}
    ordered: list[Task] = []

    def visit(task_id: str) -> None:
      state = visited.get(task_id, 0)
      if state == 2:
        return
      if state == 1:
        raise ValueError(f"Task dependency cycle detected at {task_id!r}")
      visited[task_id] = 1
      task = task_map[task_id]
      for dep_id in task.deps:
        if dep_id in task_map:
          visit(dep_id)
      visited[task_id] = 2
      ordered.append(task)

    for item in tasks:
      visit(item.id)
    return ordered


class ReportService:
  """Manage fielded Markdown reports, owner answer submissions, and dismissals."""

  def __init__(
    self,
    reports: ReportRepository,
    tasks: TaskRepository,
    clock: Clock | None = None,
    id_gen: IdGenerator | None = None,
    on_answer_callback: Any | None = None,
  ) -> None:
    self._reports = reports
    self._tasks = tasks
    self._clock = clock or UtcClock()
    self._id_gen = id_gen or SecretsHexIdGenerator()
    self._on_answer = on_answer_callback

  def publish_report(
    self, report_id: str, title: str, body: str, *, allow_unparsed_markers: bool = False
  ) -> Report:
    blocks, fields = parse_report_markdown(body)
    if any(not field.annotated for field in fields):
      raise ValueError("Fielded reports require question and option comments")
    warnings = unparsed_strike_lines(body)
    if warnings and not allow_unparsed_markers:
      raise ValueError(f"Possible unparsed strike markers on lines: {warnings}")
    rendered = [
      render_report_markdown(value)
      for block_type, value in blocks
      if block_type == "markdown"
    ]
    saved = self._publish_report(report_id, title, body, fields)
    verified = self._reports.get_report(report_id)
    if (
      verified is None
      or verified.id != saved.id
      or verified.modified_at != saved.modified_at
      or len(verified.fields) != len(fields)
      or verified.body != body
    ):
      raise RuntimeError("Report publication verification failed after saving")
    actual_blocks, _ = parse_report_markdown(verified.body)
    if [
      render_report_markdown(value)
      for block_type, value in actual_blocks
      if block_type == "markdown"
    ] != rendered:
      raise RuntimeError("Report rendered verification failed after saving")
    return verified

  @_transactional_task_write
  def _publish_report(
    self, report_id: str, title: str, body: str, fields: list[ReportField]
  ) -> Report:
    validate_entity_id(report_id, "Report.id")
    existing = self._reports.get_report(report_id)
    if existing is not None and existing.latest_unacked_answer is not None:
      raise ValueError("Report has an unacknowledged answer")
    preserved_answers: list[ReportAnswer] = []
    if existing is not None:
      preserved_answers = list(existing.answers)
    elif hasattr(self._reports, "get_archived_report_answers"):
      preserved_answers = list(self._reports.get_archived_report_answers(report_id))
    now = self._clock.now_iso()
    report = Report(
      id=report_id,
      title=title,
      body=body,
      fields=fields,
      status="published",
      answers=preserved_answers,
      seen=False,
      modified_at=now,
    )
    self._reports.save_report(report)
    return report

  @_transactional_task_write
  def mark_seen(self, report_id: str) -> Report:
    report = self.get_report(report_id)
    if not report.seen:
      report.seen = True
      self._reports.save_report(report)
    return report

  @_transactional_task_write
  def mark_ack_seen(self, report_id: str) -> Report:
    report = self.get_report(report_id)
    latest = report.answers[-1] if report.answers else None
    if latest is not None and latest.status == "acked" and not report.ack_seen:
      report.ack_seen = True
      report.modified_at = self._clock.now_iso()
      self._reports.save_report(report)
    return report

  def get_report(self, report_id: str) -> Report:
    validate_entity_id(report_id, "Report.id")
    report = self._reports.get_report(report_id)
    if report is None:
      raise KeyError(f"Unknown report ID: {report_id}")
    return report

  def list_reports(self, *, stale_only: bool = False) -> list[Report]:
    all_reports = self._reports.list_reports()
    if stale_only:
      return [
        rep
        for rep in all_reports
        if rep.status in {"answered", "dismissed"} and rep.latest_unacked_answer is None
      ]
    return [rep for rep in all_reports if rep.status != "dismissed"]

  def submit_answer(
    self, report_id: str, values: dict[str, Any], *, answer_id: str | None = None
  ) -> ReportAnswer:
    answer = self._submit_answer(report_id, values, answer_id=answer_id)
    if self._on_answer is not None:
      self._on_answer()
    return answer

  @_transactional_task_write
  def _submit_answer(
    self,
    report_id: str,
    values: dict[str, Any],
    *,
    answer_id: str | None = None,
  ) -> ReportAnswer:
    report = self.get_report(report_id)
    if not report.fields:
      raise ValueError(f"Report {report_id!r} has no interactive fields to answer")
    cleaned_values = self._validate_submission_values(report, values)
    for field in report.fields:
      value = cleaned_values[field.id]
      if field.type == "choice":
        if isinstance(value, dict) and value.get("custom"):
          cleaned_values[field.id] = value["custom"]
        elif isinstance(value, str):
          if value.lower().startswith("something else:"):
            cleaned_values[field.id] = value.partition(":")[2].strip()
          else:
            cleaned_values[field.id] = field.option_labels.get(value, value)
      elif field.type == "checkbox":
        if isinstance(value, dict):
          selected = [
            field.option_labels.get(item, item) for item in value.get("selected", [])
          ]
          custom = value.get("custom", "")
          cleaned_values[field.id] = selected + ([custom] if custom else [])
        elif isinstance(value, list):
          cleaned_values[field.id] = [
            field.option_labels.get(item, item) for item in value
          ]
    now = self._clock.now_iso()
    ans_id = (
      validate_hex_id(answer_id, "ReportAnswer.id")
      if answer_id is not None
      else self._id_gen.new_hex_id()
    )
    answer = ReportAnswer(
      id=ans_id,
      report_id=report.id,
      values=cleaned_values,
      report_title=report.title,
      field_labels={field.id: field.label for field in report.fields},
      status="sent",
      acks=[],
      modified_at=now,
    )
    report.answers.append(answer)
    report.status = "answered"
    report.seen = True
    report.ack_seen = False
    report.modified_at = now
    self._reports.save_report(report)
    self._append_answer_details_to_linked_tasks(report, answer, now)
    return answer

  @_transactional_task_write
  def ack_answer(self, report_id: str, answer_id: str, markdown: str) -> ReportAnswer:
    report = self.get_report(report_id)
    validate_hex_id(answer_id, "ReportAnswer.id")
    if not isinstance(markdown, str) or not markdown.strip():
      raise ValueError("Acknowledgement Markdown cannot be empty")
    now = self._clock.now_iso()
    for ans in report.answers:
      if ans.id == answer_id:
        ans.acks.append(markdown.strip())
        ans.status = "acked"
        ans.modified_at = now
        report.ack_seen = False
        report.modified_at = now
        self._reports.save_report(report)
        return ans
    raise KeyError(f"Unknown answer ID {answer_id!r} on report {report_id!r}")

  @_transactional_task_write
  def rename_report(self, old_report_id: str, new_report_id: str) -> Report:
    validate_entity_id(old_report_id, "Report.id")
    validate_entity_id(new_report_id, "Report.id")
    if old_report_id == new_report_id:
      return self.get_report(old_report_id)
    existing = self.get_report(old_report_id)
    if self._reports.get_report(new_report_id) is not None:
      raise ValueError(f"Report {new_report_id!r} already exists")
    now = self._clock.now_iso()
    renamed_answers = [
      ReportAnswer(
        id=answer.id,
        report_id=new_report_id,
        values=answer.values,
        status=answer.status,
        acks=answer.acks,
        modified_at=answer.modified_at,
        created_at=answer.created_at,
        report_title=answer.report_title,
        field_labels=answer.field_labels,
      )
      for answer in existing.answers
    ]
    renamed = Report(
      id=new_report_id,
      title=existing.title,
      body=existing.body,
      fields=existing.fields,
      status=existing.status,
      answers=renamed_answers,
      seen=existing.seen,
      ack_seen=existing.ack_seen,
      modified_at=now,
    )
    self._reports.save_report(renamed)
    if hasattr(self._reports, "delete_report"):
      self._reports.delete_report(old_report_id)
    queue = self._tasks.list_tasks()
    changed = False
    for task in queue:
      for snapshot in task.answer_snapshots:
        if snapshot.get("report_id") == old_report_id:
          snapshot["report_id"] = new_report_id
          changed = True
      if old_report_id in task.report_ids:
        task.report_ids = [
          new_report_id if report_id == old_report_id else report_id
          for report_id in task.report_ids
        ]
        task.modified_at = now
        changed = True
    if changed:
      self._tasks.save_task_queue(queue)
    return renamed

  @_transactional_task_write
  def remove_report(self, target: str) -> list[str]:
    """Dismiss one report by ID or all stale reports when target == '--stale'."""
    now = self._clock.now_iso()
    removed: list[str] = []
    if target == "--stale":
      candidates = self.list_reports(stale_only=True)
      for rep in candidates:
        if rep.status != "dismissed":
          if hasattr(self._reports, "delete_report"):
            self._reports.delete_report(rep.id)
          else:
            rep.status = "dismissed"
            rep.modified_at = now
            self._reports.save_report(rep)
          removed.append(rep.id)
    else:
      rep = self.get_report(target)
      if rep.latest_unacked_answer is not None:
        raise ValueError("Cannot remove a report with an unacknowledged answer")
      if hasattr(self._reports, "delete_report"):
        self._reports.delete_report(rep.id)
      else:
        rep.status = "dismissed"
        rep.modified_at = now
        self._reports.save_report(rep)
      removed.append(rep.id)

    if removed:
      removed_set = set(removed)
      queue = self._tasks.list_tasks()
      changed = False
      for task in queue:
        if any(rid in removed_set for rid in task.report_ids):
          task.report_ids = [rid for rid in task.report_ids if rid not in removed_set]
          task.modified_at = now
          changed = True
      if changed:
        self._tasks.save_task_queue(queue)
    return removed

  @staticmethod
  def _validate_submission_values(
    report: Report, raw_values: dict[str, Any]
  ) -> dict[str, Any]:
    if not isinstance(raw_values, dict) or not raw_values:
      raise ValueError("Submission values must be a non-empty dictionary")
    fields_by_id = {field.id: field for field in report.fields}
    unknown = sorted(set(raw_values) - set(fields_by_id))
    if unknown:
      raise ValueError(f"Submission contains unknown field IDs: {unknown}")
    cleaned: dict[str, Any] = {}
    for field in report.fields:
      if field.id not in raw_values:
        raise ValueError(f"Missing answer for required field {field.id!r}")
      val = raw_values[field.id]
      if field.type == "text":
        text = str(val or "").strip()
        if not text:
          raise ValueError(f"Text field {field.id!r} requires a non-empty response")
        cleaned[field.id] = text
      elif field.type == "choice":
        cleaned[field.id] = _validate_choice_value(field.id, field.options, val)
      else:
        cleaned[field.id] = _validate_checkbox_value(field.id, field.options, val)
    return cleaned

  def _append_answer_details_to_linked_tasks(
    self, report: Report, answer: ReportAnswer, now: str
  ) -> None:
    lines = [
      format_answer_for_task_detail(field, answer.values[field.id])
      for field in report.fields
      if field.id in answer.values
    ]
    if not lines:
      return
    queue = self._tasks.list_tasks()
    changed = False
    for task in queue:
      if report.id in task.report_ids:
        _append_snapshot(task, report, answer)
        for line in lines:
          if line not in task.details:
            task.details.append(line)
        task.modified_at = now
        changed = True
    if changed:
      self._tasks.save_task_queue(queue)


def _validate_choice_value(
  field_id: str, options: list[str], val: Any
) -> str | dict[str, str]:
  if isinstance(val, dict):
    custom = str(val.get("custom", "")).strip()
    selected = str(val.get("selected", "")).strip()
    if custom:
      return {"selected": selected or "Something else...", "custom": custom}
    val = selected
  text = str(val or "").strip()
  if not text:
    raise ValueError(f"Choice field {field_id!r} requires a selection")
  if text in options:
    return text
  if text.lower().startswith("something else"):
    _, _, custom_part = text.partition(":")
    if not custom_part.strip():
      raise ValueError(f"Choice field {field_id!r} custom option requires text")
    return text
  return {"selected": "Something else...", "custom": text}


def _validate_checkbox_value(
  field_id: str, options: list[str], val: Any
) -> list[str] | dict[str, Any]:
  if isinstance(val, dict):
    selected_raw = val.get("selected", [])
    selected = [
      str(item).strip() for item in selected_raw if str(item).strip() in options
    ]
    custom = str(val.get("custom", "")).strip()
    if not selected and not custom:
      raise ValueError(f"Checkbox field {field_id!r} requires at least one selection")
    if custom:
      return {"selected": selected, "custom": custom}
    return selected
  if not isinstance(val, list) or not val:
    raise ValueError(f"Checkbox field {field_id!r} requires a non-empty list")
  selected_list: list[str] = []
  custom_items: list[str] = []
  for raw_item in val:
    text = str(raw_item).strip()
    if not text:
      continue
    if text in options:
      selected_list.append(text)
    else:
      custom_items.append(text)
  if not selected_list and not custom_items:
    raise ValueError(f"Checkbox field {field_id!r} requires at least one selection")
  if custom_items:
    return {"selected": selected_list, "custom": ", ".join(custom_items)}
  return selected_list
