"""SQLite WAL store implementing Arena Steering repositories."""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path

from .models import Attachment, Message, Report, ReportAnswer, ReportField, Task


class SqliteStore:
  """Thread-safe SQLite store for messages, tasks, reports, and metadata."""

  def __init__(self, db_path: str | Path = ":memory:") -> None:
    self.db_path = str(db_path)
    if self.db_path != ":memory:":
      Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
    self._lock = threading.RLock()
    self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
    self._conn.row_factory = sqlite3.Row
    self._init_schema()

  def _init_schema(self) -> None:
    with self._lock, self._conn:
      self._conn.execute("PRAGMA journal_mode=WAL")
      self._conn.execute("PRAGMA synchronous=NORMAL")
      self._conn.execute("PRAGMA foreign_keys=ON")
      self._conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS messages (
          seq INTEGER PRIMARY KEY AUTOINCREMENT,
          id TEXT UNIQUE NOT NULL,
          body TEXT NOT NULL,
          hidden INTEGER NOT NULL DEFAULT 0,
          blocking INTEGER NOT NULL DEFAULT 1,
          attachments_json TEXT NOT NULL DEFAULT '[]',
          parent_ids_json TEXT NOT NULL DEFAULT '[]',
          status TEXT NOT NULL DEFAULT 'sent',
          acks_json TEXT NOT NULL DEFAULT '[]',
          modified_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS tasks (
          position INTEGER NOT NULL,
          id TEXT PRIMARY KEY,
          title TEXT NOT NULL,
          type TEXT NOT NULL,
          status TEXT NOT NULL,
          scope TEXT NOT NULL,
          details_json TEXT NOT NULL DEFAULT '[]',
          links_json TEXT NOT NULL DEFAULT '{"msg_ids":[],"report_ids":[],"task_ids":[]}',
          msg_ids_json TEXT NOT NULL DEFAULT '[]',
          report_ids_json TEXT NOT NULL DEFAULT '[]',
          deps_json TEXT NOT NULL DEFAULT '[]',
          modified_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS reports (
          seq INTEGER PRIMARY KEY AUTOINCREMENT,
          id TEXT UNIQUE NOT NULL,
          title TEXT NOT NULL,
          body TEXT NOT NULL,
          fields_json TEXT NOT NULL DEFAULT '[]',
          status TEXT NOT NULL DEFAULT 'published',
          answers_json TEXT NOT NULL DEFAULT '[]',
          seen INTEGER NOT NULL DEFAULT 0,
          ack_seen INTEGER NOT NULL DEFAULT 0,
          modified_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS meta (
          key TEXT PRIMARY KEY,
          value TEXT NOT NULL
        );
        """
      )
      message_cols = {
        row["name"]
        for row in self._conn.execute("PRAGMA table_info(messages)").fetchall()
      }
      if "parent_ids_json" not in message_cols:
        self._conn.execute(
          "ALTER TABLE messages ADD COLUMN parent_ids_json TEXT NOT NULL DEFAULT '[]'"
        )
      task_cols = {
        row["name"] for row in self._conn.execute("PRAGMA table_info(tasks)").fetchall()
      }
      if "links_json" not in task_cols:
        self._conn.execute(
          "ALTER TABLE tasks ADD COLUMN links_json TEXT NOT NULL DEFAULT ''"
        )
      cols = {
        row["name"]
        for row in self._conn.execute("PRAGMA table_info(reports)").fetchall()
      }
      if "seen" not in cols:
        self._conn.execute(
          "ALTER TABLE reports ADD COLUMN seen INTEGER NOT NULL DEFAULT 0"
        )
      if "ack_seen" not in cols:
        self._conn.execute(
          "ALTER TABLE reports ADD COLUMN ack_seen INTEGER NOT NULL DEFAULT 0"
        )

  def close(self) -> None:
    """Close the underlying SQLite connection."""
    with self._lock:
      self._conn.close()

  def get_message(self, msg_id: str) -> Message | None:
    with self._lock:
      row = self._conn.execute(
        "SELECT * FROM messages WHERE id = ?", (msg_id,)
      ).fetchone()
    return self._row_to_message(row) if row is not None else None

  def list_messages(
    self, *, unread_only: bool = False, include_hidden: bool = True
  ) -> list[Message]:
    with self._lock:
      rows = self._conn.execute("SELECT * FROM messages ORDER BY seq ASC").fetchall()
    messages = [self._row_to_message(row) for row in rows]
    if not include_hidden:
      messages = [msg for msg in messages if not msg.hidden]
    if unread_only:
      messages = [msg for msg in messages if msg.is_unread]
    return messages

  def save_message(self, message: Message) -> Message:
    with self._lock, self._conn:
      existing = self._conn.execute(
        "SELECT seq FROM messages WHERE id = ?", (message.id,)
      ).fetchone()
      attachments_json = json.dumps([item.to_dict() for item in message.attachments])
      parent_ids_json = json.dumps(message.parent_ids)
      acks_json = json.dumps(message.acks)
      if existing is None:
        self._conn.execute(
          """
          INSERT INTO messages (
            id, body, hidden, blocking, attachments_json, parent_ids_json, status, acks_json, modified_at
          ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
          """,
          (
            message.id,
            message.body,
            int(message.hidden),
            int(message.blocking),
            attachments_json,
            parent_ids_json,
            message.status,
            acks_json,
            message.modified_at,
          ),
        )
      else:
        self._conn.execute(
          """
          UPDATE messages
          SET body = ?,
              hidden = ?,
              blocking = ?,
              attachments_json = ?,
              parent_ids_json = ?,
              status = ?,
              acks_json = ?,
              modified_at = ?
          WHERE id = ?
          """,
          (
            message.body,
            int(message.hidden),
            int(message.blocking),
            attachments_json,
            parent_ids_json,
            message.status,
            acks_json,
            message.modified_at,
            message.id,
          ),
        )
    return message

  def get_task(self, task_id: str) -> Task | None:
    with self._lock:
      row = self._conn.execute(
        "SELECT * FROM tasks WHERE id = ?", (task_id,)
      ).fetchone()
    return self._row_to_task(row) if row is not None else None

  def list_tasks(self) -> list[Task]:
    with self._lock:
      rows = self._conn.execute("SELECT * FROM tasks ORDER BY position ASC").fetchall()
    return [self._row_to_task(row) for row in rows]

  def save_task_queue(self, tasks: list[Task]) -> list[Task]:
    with self._lock, self._conn:
      self._conn.execute("DELETE FROM tasks")
      for index, task in enumerate(tasks):
        self._conn.execute(
          """
          INSERT INTO tasks (
            position, id, title, type, status, scope,
            details_json, links_json, msg_ids_json, report_ids_json, deps_json, modified_at
          ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
          """,
          (
            index,
            task.id,
            task.title,
            task.type,
            task.status,
            task.scope,
            json.dumps(task.details),
            json.dumps(task.links),
            json.dumps(task.msg_ids),
            json.dumps(task.report_ids),
            json.dumps(task.task_ids),
            task.modified_at,
          ),
        )
    return list(tasks)

  def delete_task(self, task_id: str) -> bool:
    with self._lock, self._conn:
      cur = self._conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
      if cur.rowcount == 0:
        return False
      rows = self._conn.execute("SELECT id FROM tasks ORDER BY position ASC").fetchall()
      for index, row in enumerate(rows):
        self._conn.execute(
          "UPDATE tasks SET position = ? WHERE id = ?", (index, row["id"])
        )
    return True

  def get_report(self, report_id: str) -> Report | None:
    with self._lock:
      row = self._conn.execute(
        "SELECT * FROM reports WHERE id = ?", (report_id,)
      ).fetchone()
    return self._row_to_report(row) if row is not None else None

  def list_reports(self) -> list[Report]:
    with self._lock:
      rows = self._conn.execute("SELECT * FROM reports ORDER BY seq ASC").fetchall()
    return [self._row_to_report(row) for row in rows]

  def delete_report(self, report_id: str) -> bool:
    """Evict a report row from `reports` while preserving its answers in `meta`."""
    with self._lock, self._conn:
      row = self._conn.execute(
        "SELECT answers_json FROM reports WHERE id = ?", (report_id,)
      ).fetchone()
      if row is None:
        return False
      answers_json = str(row["answers_json"] or "[]")
      self._conn.execute(
        """
        INSERT INTO meta (key, value) VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (f"report_answers:{report_id}", answers_json),
      )
      self._conn.execute("DELETE FROM reports WHERE id = ?", (report_id,))
    return True

  def get_archived_report_answers(self, report_id: str) -> list[ReportAnswer]:
    """Return preserved answers for a previously dismissed report."""
    raw = self.get_meta(f"report_answers:{report_id}", "[]") or "[]"
    try:
      items = json.loads(raw)
      if isinstance(items, list):
        return [ReportAnswer.from_dict(item) for item in items]
    except json.JSONDecodeError:
      pass
    return []

  def save_report(self, report: Report) -> Report:
    with self._lock, self._conn:
      existing = self._conn.execute(
        "SELECT seq FROM reports WHERE id = ?", (report.id,)
      ).fetchone()
      fields_json = json.dumps([item.to_dict() for item in report.fields])
      answers_json = json.dumps([item.to_dict() for item in report.answers])
      if existing is None:
        self._conn.execute(
          """
          INSERT INTO reports (
            id, title, body, fields_json, status, answers_json, seen, ack_seen,
            modified_at
          ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
          """,
          (
            report.id,
            report.title,
            report.body,
            fields_json,
            report.status,
            answers_json,
            int(report.seen),
            int(report.ack_seen),
            report.modified_at,
          ),
        )
      else:
        self._conn.execute(
          """
          UPDATE reports
          SET title = ?,
              body = ?,
              fields_json = ?,
              status = ?,
              answers_json = ?,
              seen = ?,
              ack_seen = ?,
              modified_at = ?
          WHERE id = ?
          """,
          (
            report.title,
            report.body,
            fields_json,
            report.status,
            answers_json,
            int(report.seen),
            int(report.ack_seen),
            report.modified_at,
            report.id,
          ),
        )
    return report

  def get_meta(self, key: str, default: str | None = None) -> str | None:
    with self._lock:
      row = self._conn.execute(
        "SELECT value FROM meta WHERE key = ?", (key,)
      ).fetchone()
    return str(row["value"]) if row is not None else default

  def set_meta(self, key: str, value: str) -> None:
    with self._lock, self._conn:
      self._conn.execute(
        """
        INSERT INTO meta (key, value) VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (key, str(value)),
      )

  @staticmethod
  def _row_to_message(row: sqlite3.Row) -> Message:
    keys = row.keys()
    parent_ids_json = row["parent_ids_json"] if "parent_ids_json" in keys else "[]"
    return Message(
      id=str(row["id"]),
      body=str(row["body"]),
      hidden=bool(row["hidden"]),
      blocking=bool(row["blocking"]),
      attachments=[
        Attachment.from_dict(item)
        for item in json.loads(row["attachments_json"] or "[]")
      ],
      parent_ids=[str(item) for item in json.loads(parent_ids_json or "[]")],
      status=str(row["status"]),
      acks=[str(item) for item in json.loads(row["acks_json"] or "[]")],
      modified_at=str(row["modified_at"]),
    )

  @staticmethod
  def _row_to_task(row: sqlite3.Row) -> Task:
    keys = row.keys()
    raw_links = row["links_json"] if "links_json" in keys else ""
    parsed_links = json.loads(raw_links) if raw_links else None
    if isinstance(parsed_links, dict):
      return Task(
        id=str(row["id"]),
        title=str(row["title"]),
        type=str(row["type"]),
        status=str(row["status"]),
        scope=str(row["scope"]),
        details=[str(item) for item in json.loads(row["details_json"] or "[]")],
        links=parsed_links,
        modified_at=str(row["modified_at"]),
      )
    return Task(
      id=str(row["id"]),
      title=str(row["title"]),
      type=str(row["type"]),
      status=str(row["status"]),
      scope=str(row["scope"]),
      details=[str(item) for item in json.loads(row["details_json"] or "[]")],
      msg_ids=[str(item) for item in json.loads(row["msg_ids_json"] or "[]")],
      report_ids=[str(item) for item in json.loads(row["report_ids_json"] or "[]")],
      task_ids=[str(item) for item in json.loads(row["deps_json"] or "[]")],
      modified_at=str(row["modified_at"]),
    )

  @staticmethod
  def _row_to_report(row: sqlite3.Row) -> Report:
    return Report(
      id=str(row["id"]),
      title=str(row["title"]),
      body=str(row["body"]),
      fields=[
        ReportField.from_dict(item) for item in json.loads(row["fields_json"] or "[]")
      ],
      status=str(row["status"]),
      answers=[
        ReportAnswer.from_dict(item) for item in json.loads(row["answers_json"] or "[]")
      ],
      seen=bool(dict(row).get("seen", 0)),
      ack_seen=bool(dict(row).get("ack_seen", 0)),
      modified_at=str(row["modified_at"]),
    )
