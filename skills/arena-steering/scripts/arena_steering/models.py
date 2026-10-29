"""Domain models and validation rules for Arena Steering."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

MESSAGE_ID_RE = re.compile(r"^[0-9a-f]{6}$")
ENTITY_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

MESSAGE_STATUSES = ("sent", "seen", "acked")
TASK_TYPES = ("report", "code", "docs", "ops", "misc")
TASK_STATUSES = ("upcoming", "in_progress", "blocked", "finished")
REPORT_STATUSES = ("published", "answered", "dismissed")
REPORT_FIELD_TYPES = ("choice", "checkbox", "text")

TASK_DETAIL_MAX_LEN = 120
OPTION_MIN_COUNT = 1
OPTION_MAX_COUNT = 20
OPTION_MAX_LEN = 200

_STATUS_RANK = {name: idx for idx, name in enumerate(MESSAGE_STATUSES)}
_REPORT_STATUS_RANK = {name: idx for idx, name in enumerate(REPORT_STATUSES)}


def kebab_slug(text: str, used: set[str] | None = None, max_len: int = 64) -> str:
  """Convert label text into a kebab-case ID with trailing hyphens stripped."""
  cleaned = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
  if max_len > 0 and len(cleaned) > max_len:
    cleaned = cleaned[:max_len].rstrip("-")
  base = cleaned or "field"
  if used is None or base not in used:
    return base
  suffix = 2
  while f"{base}-{suffix}" in used:
    suffix += 1
  return f"{base}-{suffix}"


def validate_hex_id(value: str, label: str = "Message ID") -> str:
  """Require a strict 6-character lowercase hex identifier."""
  if not isinstance(value, str) or not MESSAGE_ID_RE.fullmatch(value):
    raise ValueError(f"{label} must be 6 lowercase hex characters: {value!r}")
  return value


def validate_entity_id(value: str, label: str = "ID") -> str:
  """Require a non-empty kebab-case identifier with no trailing hyphen."""
  if not isinstance(value, str) or not ENTITY_ID_RE.fullmatch(value):
    raise ValueError(f"{label} must be kebab-case: {value!r}")
  return value


def can_advance_message_status(current: str, target: str) -> bool:
  """Check whether a message or answer status transition moves forward."""
  if current not in _STATUS_RANK or target not in _STATUS_RANK:
    return False
  return _STATUS_RANK[target] >= _STATUS_RANK[current]


def can_advance_report_status(current: str, target: str) -> bool:
  """Check whether a report status transition is valid."""
  if current not in _REPORT_STATUS_RANK or target not in _REPORT_STATUS_RANK:
    return False
  if target == "published":
    return True
  return _REPORT_STATUS_RANK[target] >= _REPORT_STATUS_RANK[current]


@dataclass(slots=True)
class Attachment:
  """File metadata attached to a steering message."""

  name: str
  path: str
  size_bytes: int = 0
  present: bool = True

  def __post_init__(self) -> None:
    if not self.name or not isinstance(self.name, str):
      raise ValueError("Attachment name is required")
    if not self.path or not isinstance(self.path, str):
      raise ValueError("Attachment path is required")
    if int(self.size_bytes) < 0:
      raise ValueError("Attachment size cannot be negative")
    self.size_bytes = int(self.size_bytes)
    self.present = bool(self.present)

  def to_dict(self) -> dict[str, Any]:
    return {
      "name": self.name,
      "path": self.path,
      "size_bytes": self.size_bytes,
      "present": self.present,
    }

  @classmethod
  def from_dict(cls, data: dict[str, Any]) -> Attachment:
    return cls(
      name=str(data["name"]),
      path=str(data["path"]),
      size_bytes=int(data.get("size_bytes", 0)),
      present=bool(data.get("present", True)),
    )


@dataclass(slots=True)
class Message:
  """Steering inbox message with a 6-character hex ID and status ladder."""

  id: str
  body: str
  hidden: bool = False
  blocking: bool = True
  attachments: list[Attachment] = field(default_factory=list)
  status: str = "sent"
  acks: list[str] = field(default_factory=list)
  modified_at: str = ""

  def __post_init__(self) -> None:
    validate_hex_id(self.id, "Message.id")
    if not isinstance(self.body, str):
      raise TypeError("Message.body must be a string")
    self.hidden = bool(self.hidden)
    self.blocking = bool(self.blocking)
    if self.status not in MESSAGE_STATUSES:
      raise ValueError(f"Invalid Message.status: {self.status!r}")
    self.attachments = [
      item if isinstance(item, Attachment) else Attachment.from_dict(item)
      for item in self.attachments
    ]
    if not isinstance(self.acks, list) or any(
      not isinstance(ack, str) or not ack.strip() for ack in self.acks
    ):
      raise ValueError("Message.acks must be a list of non-empty Markdown strings")
    self.acks = list(self.acks)
    self.modified_at = str(self.modified_at or "")

  @property
  def requires_ack(self) -> bool:
    """Return True when this message requires an acknowledgement."""
    return self.blocking and self.status != "acked"

  @property
  def is_unread(self) -> bool:
    """Return True when the message remains unread or lacks an acknowledgement."""
    if self.blocking:
      return self.status != "acked"
    return self.status == "sent"

  def to_dict(self) -> dict[str, Any]:
    return {
      "id": self.id,
      "body": self.body,
      "hidden": self.hidden,
      "blocking": self.blocking,
      "attachments": [item.to_dict() for item in self.attachments],
      "status": self.status,
      "acks": list(self.acks),
      "modified_at": self.modified_at,
    }

  @classmethod
  def from_dict(cls, data: dict[str, Any]) -> Message:
    return cls(
      id=str(data["id"]),
      body=str(data.get("body", "")),
      hidden=bool(data.get("hidden", False)),
      blocking=bool(data.get("blocking", True)),
      attachments=[Attachment.from_dict(raw) for raw in data.get("attachments", [])],
      status=str(data.get("status", "sent")),
      acks=[str(item) for item in data.get("acks", [])],
      modified_at=str(data.get("modified_at", "")),
    )


@dataclass(slots=True, init=False)
class Task:
  """Mutable-queue task item with unified links (msg_ids, report_ids, task_ids)."""

  id: str
  title: str
  type: str
  status: str
  scope: str
  details: list[str]
  links: dict[str, list[str]]
  modified_at: str

  def __init__(
    self,
    id: str,
    title: str,
    type: str = "code",
    status: str = "upcoming",
    scope: str = "",
    details: list[str] | None = None,
    links: dict[str, list[str]] | None = None,
    *,
    msg_ids: list[str] | None = None,
    report_ids: list[str] | None = None,
    task_ids: list[str] | None = None,
    deps: list[str] | None = None,
    modified_at: str = "",
  ) -> None:
    validate_entity_id(id, "Task.id")
    if not isinstance(title, str) or not title.strip():
      raise ValueError("Task.title must be a non-empty string")
    self.id = id
    self.title = title.strip()
    if type not in TASK_TYPES:
      raise ValueError(f"Invalid Task.type: {type!r}")
    self.type = type
    if status not in TASK_STATUSES:
      raise ValueError(f"Invalid Task.status: {status!r}")
    self.status = status
    self.scope = str(scope or "").strip()
    cleaned_details: list[str] = []
    for line in details or []:
      if not isinstance(line, str) or not line.strip():
        raise ValueError("Task detail line must be a non-empty string")
      text = line.strip()
      if len(text) > TASK_DETAIL_MAX_LEN:
        raise ValueError(
          f"Task detail exceeds {TASK_DETAIL_MAX_LEN} characters ({len(text)}): {text!r}"
        )
      cleaned_details.append(text)
    self.details = cleaned_details

    raw_links = dict(links) if isinstance(links, dict) else {}
    resolved_msgs = (
      msg_ids
      if msg_ids is not None
      else raw_links.get("msg_ids", raw_links.get("msg_id", []))
    )
    resolved_reports = (
      report_ids
      if report_ids is not None
      else raw_links.get("report_ids", raw_links.get("report_id", []))
    )
    resolved_tasks = (
      task_ids
      if task_ids is not None
      else (
        deps
        if deps is not None
        else raw_links.get(
          "task_ids", raw_links.get("task_id", raw_links.get("deps", []))
        )
      )
    )
    cleaned_msgs = _dedupe_strings([str(x) for x in (resolved_msgs or [])])
    cleaned_reports = _dedupe_strings([str(x) for x in (resolved_reports or [])])
    cleaned_tasks = _dedupe_strings([str(x) for x in (resolved_tasks or [])])
    if self.id in cleaned_tasks:
      raise ValueError(f"Task {self.id!r} cannot depend on itself")
    self.links = {
      "msg_ids": cleaned_msgs,
      "report_ids": cleaned_reports,
      "task_ids": cleaned_tasks,
    }
    self.modified_at = str(modified_at or "")

  @property
  def msg_ids(self) -> list[str]:
    return self.links["msg_ids"]

  @msg_ids.setter
  def msg_ids(self, value: list[str]) -> None:
    self.links["msg_ids"] = _dedupe_strings([str(x) for x in value])

  @property
  def report_ids(self) -> list[str]:
    return self.links["report_ids"]

  @report_ids.setter
  def report_ids(self, value: list[str]) -> None:
    self.links["report_ids"] = _dedupe_strings([str(x) for x in value])

  @property
  def task_ids(self) -> list[str]:
    return self.links["task_ids"]

  @task_ids.setter
  def task_ids(self, value: list[str]) -> None:
    cleaned = _dedupe_strings([str(x) for x in value])
    if self.id in cleaned:
      raise ValueError(f"Task {self.id!r} cannot depend on itself")
    self.links["task_ids"] = cleaned

  @property
  def deps(self) -> list[str]:
    return self.links["task_ids"]

  @deps.setter
  def deps(self, value: list[str]) -> None:
    self.task_ids = value

  def to_dict(self, *, blocked: bool | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
      "id": self.id,
      "title": self.title,
      "type": self.type,
      "status": self.status,
      "scope": self.scope,
      "details": list(self.details),
      "links": {
        "msg_ids": list(self.msg_ids),
        "report_ids": list(self.report_ids),
        "task_ids": list(self.task_ids),
      },
      "modified_at": self.modified_at,
    }
    if blocked is not None:
      payload["blocked"] = bool(blocked)
    return payload

  @classmethod
  def from_dict(cls, data: dict[str, Any]) -> Task:
    raw_links = data.get("links")
    return cls(
      id=str(data["id"]),
      title=str(data["title"]),
      type=str(data.get("type", "code")),
      status=str(data.get("status", "upcoming")),
      scope=str(data.get("scope", "")),
      details=[str(item) for item in data.get("details", [])],
      links=raw_links if isinstance(raw_links, dict) else None,
      msg_ids=([str(item) for item in data["msg_ids"]] if "msg_ids" in data else None),
      report_ids=(
        [str(item) for item in data["report_ids"]] if "report_ids" in data else None
      ),
      task_ids=(
        [str(item) for item in data["task_ids"]] if "task_ids" in data else None
      ),
      deps=([str(item) for item in data["deps"]] if "deps" in data else None),
      modified_at=str(data.get("modified_at", "")),
    )


@dataclass(slots=True)
class ReportField:
  """Interactive question field parsed from a report Markdown file."""

  label: str
  type: str
  id: str = ""
  options: list[str] = field(default_factory=list)
  recommended: list[str] = field(default_factory=list)

  def __post_init__(self) -> None:
    if not isinstance(self.label, str) or not self.label.strip():
      raise ValueError("ReportField.label is required")
    self.label = self.label.strip()
    if self.type not in REPORT_FIELD_TYPES:
      raise ValueError(f"Invalid ReportField.type: {self.type!r}")
    raw_id = self.id.strip().rstrip("-") if isinstance(self.id, str) else ""
    self.id = (
      validate_entity_id(raw_id, "ReportField.id") if raw_id else kebab_slug(self.label)
    )
    if self.type == "text":
      if self.options or self.recommended:
        raise ValueError("Text fields cannot define preset options or recommendations")
      self.options = []
      self.recommended = []
      return
    if not (OPTION_MIN_COUNT <= len(self.options) <= OPTION_MAX_COUNT):
      raise ValueError(
        f"{self.type} fields require {OPTION_MIN_COUNT}..{OPTION_MAX_COUNT} options"
      )
    cleaned_options: list[str] = []
    seen: set[str] = set()
    for opt in self.options:
      text = str(opt).strip()
      if not (1 <= len(text) <= OPTION_MAX_LEN):
        raise ValueError(f"Option must be 1..{OPTION_MAX_LEN} characters: {text!r}")
      if text in seen:
        raise ValueError(f"Field {self.id!r} repeats option {text!r}")
      seen.add(text)
      cleaned_options.append(text)
    self.options = cleaned_options
    cleaned_rec = [str(item).strip() for item in self.recommended if str(item).strip()]
    if any(item not in seen for item in cleaned_rec):
      raise ValueError(f"Field {self.id!r} recommends an unknown option")
    if self.type == "choice" and len(cleaned_rec) > 1:
      raise ValueError(f"Choice field {self.id!r} can recommend at most 1 option")
    self.recommended = _dedupe_strings(cleaned_rec)

  def to_dict(self) -> dict[str, Any]:
    return {
      "id": self.id,
      "label": self.label,
      "type": self.type,
      "options": list(self.options),
      "recommended": list(self.recommended),
    }

  @classmethod
  def from_dict(cls, data: dict[str, Any]) -> ReportField:
    return cls(
      id=str(data.get("id", "")),
      label=str(data["label"]),
      type=str(data["type"]),
      options=[str(item) for item in data.get("options", [])],
      recommended=[str(item) for item in data.get("recommended", [])],
    )


@dataclass(slots=True)
class ReportAnswer:
  """Owner form submission attached to a published report."""

  id: str
  report_id: str
  values: dict[str, Any]
  status: str = "sent"
  acks: list[str] = field(default_factory=list)
  modified_at: str = ""

  def __post_init__(self) -> None:
    validate_hex_id(self.id, "ReportAnswer.id")
    validate_entity_id(self.report_id, "ReportAnswer.report_id")
    if not isinstance(self.values, dict) or not self.values:
      raise ValueError("ReportAnswer.values must be a non-empty dictionary")
    self.values = dict(self.values)
    if self.status not in MESSAGE_STATUSES:
      raise ValueError(f"Invalid ReportAnswer.status: {self.status!r}")
    if not isinstance(self.acks, list) or any(
      not isinstance(ack, str) or not ack.strip() for ack in self.acks
    ):
      raise ValueError("ReportAnswer.acks must be a list of non-empty Markdown strings")
    self.acks = list(self.acks)
    self.modified_at = str(self.modified_at or "")

  def to_dict(self) -> dict[str, Any]:
    return {
      "id": self.id,
      "report_id": self.report_id,
      "values": dict(self.values),
      "status": self.status,
      "acks": list(self.acks),
      "modified_at": self.modified_at,
    }

  @classmethod
  def from_dict(cls, data: dict[str, Any]) -> ReportAnswer:
    return cls(
      id=str(data["id"]),
      report_id=str(data["report_id"]),
      values=dict(data.get("values", {})),
      status=str(data.get("status", "sent")),
      acks=[str(item) for item in data.get("acks", [])],
      modified_at=str(data.get("modified_at", "")),
    )


@dataclass(slots=True)
class Report:
  """Published Markdown report with parsed interactive fields and owner answers."""

  id: str
  title: str
  body: str
  fields: list[ReportField] = field(default_factory=list)
  status: str = "published"
  answers: list[ReportAnswer] = field(default_factory=list)
  seen: bool = False
  modified_at: str = ""

  def __post_init__(self) -> None:
    validate_entity_id(self.id, "Report.id")
    if not isinstance(self.title, str) or not self.title.strip():
      raise ValueError("Report.title must be a non-empty string")
    self.title = self.title.strip()
    if not isinstance(self.body, str):
      raise TypeError("Report.body must be a string")
    if self.status not in REPORT_STATUSES:
      raise ValueError(f"Invalid Report.status: {self.status!r}")
    self.fields = [
      item if isinstance(item, ReportField) else ReportField.from_dict(item)
      for item in self.fields
    ]
    seen_ids: set[str] = set()
    for item in self.fields:
      if item.id in seen_ids:
        raise ValueError(f"Report {self.id!r} has duplicate field ID {item.id!r}")
      seen_ids.add(item.id)
    self.answers = [
      ans if isinstance(ans, ReportAnswer) else ReportAnswer.from_dict(ans)
      for ans in self.answers
    ]
    self.seen = bool(self.seen)
    self.modified_at = str(self.modified_at or "")

  @property
  def needs_answer(self) -> bool:
    """Return True when the report is published, has fields, and has no answers."""
    return self.status == "published" and bool(self.fields) and not self.answers

  @property
  def latest_unacked_answer(self) -> ReportAnswer | None:
    """Return the newest answer if it has not yet been acknowledged."""
    if not self.answers:
      return None
    latest = self.answers[-1]
    return latest if latest.status != "acked" else None

  def to_dict(self) -> dict[str, Any]:
    return {
      "id": self.id,
      "title": self.title,
      "body": self.body,
      "fields": [item.to_dict() for item in self.fields],
      "status": self.status,
      "answers": [item.to_dict() for item in self.answers],
      "seen": self.seen,
      "needs_answer": self.needs_answer,
      "modified_at": self.modified_at,
    }

  @classmethod
  def from_dict(cls, data: dict[str, Any]) -> Report:
    return cls(
      id=str(data["id"]),
      title=str(data["title"]),
      body=str(data.get("body", "")),
      fields=[ReportField.from_dict(raw) for raw in data.get("fields", [])],
      status=str(data.get("status", "published")),
      answers=[ReportAnswer.from_dict(raw) for raw in data.get("answers", [])],
      seen=bool(data.get("seen", False)),
      modified_at=str(data.get("modified_at", "")),
    )


def _dedupe_strings(items: list[str]) -> list[str]:
  result: list[str] = []
  seen: set[str] = set()
  for raw in items:
    text = str(raw).strip()
    if text and text not in seen:
      seen.add(text)
      result.append(text)
  return result
