"""SQLite WAL store implementing Arena Steering repositories."""

from __future__ import annotations

import hashlib
import hmac
import json
import sqlite3
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
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
    self._conn.create_function(
      "casefold", 1, lambda value: str(value or "").casefold(), deterministic=True
    )
    self._init_schema()

  def _init_schema(self) -> None:
    with self._lock, self._conn:
      deadline = time.monotonic() + 5
      while True:
        try:
          self._conn.execute("PRAGMA journal_mode=WAL")
          break
        except sqlite3.OperationalError as exc:
          if getattr(exc, "sqlite_errorcode", None) != sqlite3.SQLITE_BUSY:
            raise
          if time.monotonic() >= deadline:
            raise
          time.sleep(0.01)
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
          replies_seen INTEGER NOT NULL DEFAULT 0,
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
          answer_snapshots_json TEXT NOT NULL DEFAULT '[]',
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

        CREATE TABLE IF NOT EXISTS message_requests (
          request_id TEXT PRIMARY KEY,
          fingerprint TEXT NOT NULL,
          message_id TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS browser_write_requests (
          request_id TEXT PRIMARY KEY,
          fingerprint TEXT NOT NULL,
          status INTEGER NOT NULL,
          response_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS meta (
          key TEXT PRIMARY KEY,
          value TEXT NOT NULL
        );
        """
      )
      self._conn.execute("BEGIN IMMEDIATE")
      message_cols = {
        row["name"]
        for row in self._conn.execute("PRAGMA table_info(messages)").fetchall()
      }
      if "parent_ids_json" not in message_cols:
        self._conn.execute(
          "ALTER TABLE messages ADD COLUMN parent_ids_json TEXT NOT NULL DEFAULT '[]'"
        )
      if "replies_seen" not in message_cols:
        self._conn.execute(
          "ALTER TABLE messages ADD COLUMN replies_seen INTEGER NOT NULL DEFAULT 0"
        )
      task_cols = {
        row["name"] for row in self._conn.execute("PRAGMA table_info(tasks)").fetchall()
      }
      if "answer_snapshots_json" not in task_cols:
        self._conn.execute(
          "ALTER TABLE tasks ADD COLUMN answer_snapshots_json TEXT NOT NULL DEFAULT '[]'"
        )
        for row in self._conn.execute("SELECT * FROM tasks").fetchall():
          links = (
            json.loads(row["links_json"] or "{}") if "links_json" in task_cols else {}
          )
          report_ids = (
            links.get("report_ids", links.get("report_id", []))
            if links
            else json.loads(row["report_ids_json"] or "[]")
          )
          if isinstance(report_ids, str):
            report_ids = [report_ids]
          snapshots = []
          for report_id in report_ids:
            report_row = self._conn.execute(
              "SELECT * FROM reports WHERE id = ?", (report_id,)
            ).fetchone()
            if report_row is not None:
              report = self._row_to_report(report_row)
              snapshots.extend(answer.snapshot(report) for answer in report.answers)
          if snapshots:
            self._conn.execute(
              "UPDATE tasks SET answer_snapshots_json = ? WHERE id = ?",
              (json.dumps(snapshots), row["id"]),
            )
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

  @contextmanager
  def transaction(self) -> Iterator[None]:
    """Run nested repository writes in one SQLite transaction."""
    with self._lock:
      if self._conn.in_transaction:
        self._conn.execute("SAVEPOINT nested")
        try:
          yield
        except BaseException:
          self._conn.execute("ROLLBACK TO nested")
          self._conn.execute("RELEASE nested")
          raise
        else:
          self._conn.execute("RELEASE nested")
        return
      self._conn.execute("BEGIN IMMEDIATE")
      try:
        yield
      except BaseException:
        self._conn.rollback()
        raise
      else:
        self._conn.commit()

  def execute_browser_write_once(
    self,
    request_id: str,
    fingerprint: str,
    action: Callable[[], tuple[int, dict]],
  ) -> tuple[int, dict]:
    """Commit a browser action and its replay result together."""
    with self.transaction():
      row = self._conn.execute(
        "SELECT fingerprint, status, response_json FROM browser_write_requests WHERE request_id = ?",
        (request_id,),
      ).fetchone()
      if row is not None:
        if row["fingerprint"] != fingerprint:
          raise ValueError("Request ID already used for a different action")
        return int(row["status"]), json.loads(row["response_json"])
      status, response = action()
      if 200 <= status < 300:
        self._conn.execute(
          "INSERT INTO browser_write_requests VALUES (?, ?, ?, ?)",
          (request_id, fingerprint, status, json.dumps(response)),
        )
      return status, response

  def browser_write_ids(self) -> list[str]:
    """Return IDs with committed browser write results."""
    with self._lock:
      return [
        row[0]
        for row in self._conn.execute("SELECT request_id FROM browser_write_requests")
      ]

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

  def list_message_page(
    self,
    *,
    unread_only: bool,
    include_hidden: bool,
    query: str,
    before: str,
    limit: int,
  ) -> tuple[list[Message], int, bool]:
    filters = []
    params: list[object] = []
    if not include_hidden:
      filters.append("hidden = 0")
    if unread_only:
      filters.append(
        "((blocking = 1 AND status != 'acked') OR (blocking = 0 AND status = 'sent'))"
      )
    if query:
      filters.append("""(
        instr(casefold(id), ?) > 0 OR instr(casefold(body), ?) > 0 OR
        EXISTS (SELECT 1 FROM json_each(parent_ids_json) WHERE instr(casefold(value), ?) > 0) OR
        EXISTS (SELECT 1 FROM json_each(acks_json) WHERE instr(casefold(value), ?) > 0)
      )""")
      params.extend([query.casefold()] * 4)
    where = " AND ".join(filters) if filters else "1"
    with self._lock:
      total = self._conn.execute(
        f"SELECT count(*) FROM messages WHERE {where}", params
      ).fetchone()[0]
      cursor = None
      if before:
        row = self._conn.execute(
          f"SELECT seq FROM messages WHERE id = ? AND {where}", [before, *params]
        ).fetchone()
        if row is None:
          raise ValueError(
            "Message page cursor is missing or does not match the filters"
          )
        cursor = row[0]
      page_where = where + (" AND seq < ?" if cursor is not None else "")
      page_params = [*params, *([cursor] if cursor is not None else []), limit + 1]
      rows = self._conn.execute(
        f"SELECT * FROM messages WHERE {page_where} ORDER BY seq DESC LIMIT ?",
        page_params,
      ).fetchall()
    has_more = len(rows) > limit
    return (
      [self._row_to_message(row) for row in reversed(rows[:limit])],
      total,
      has_more,
    )

  def save_message(self, message: Message) -> Message:
    with self.transaction():
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
              replies_seen = CASE WHEN acks_json = ? THEN replies_seen ELSE 0 END,
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
            acks_json,
            message.modified_at,
            message.id,
          ),
        )
    return message

  def save_message_once(
    self, message: Message, request_id: str, fingerprint: str
  ) -> Message:
    """Atomically create or retrieve a message for a client request."""
    with self.transaction():
      row = self._conn.execute(
        "SELECT fingerprint, message_id FROM message_requests WHERE request_id = ?",
        (request_id,),
      ).fetchone()
      if row is not None:
        if row["fingerprint"] != fingerprint:
          raise ValueError("Request ID was already used for different content")
        existing = self._conn.execute(
          "SELECT * FROM messages WHERE id = ?", (row["message_id"],)
        ).fetchone()
        if existing is None:
          raise ValueError("Original message for request ID is missing")
        return self._row_to_message(existing)
      self._conn.execute(
        """INSERT INTO messages
          (id, body, hidden, blocking, attachments_json, parent_ids_json, status, acks_json, modified_at)
          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
          message.id,
          message.body,
          int(message.hidden),
          int(message.blocking),
          json.dumps([item.to_dict() for item in message.attachments]),
          json.dumps(message.parent_ids),
          message.status,
          json.dumps(message.acks),
          message.modified_at,
        ),
      )
      self._conn.execute(
        "INSERT INTO message_requests (request_id, fingerprint, message_id) VALUES (?, ?, ?)",
        (request_id, fingerprint, message.id),
      )
      return message

  def append_message_ack(self, msg_id: str, reply: str, now: str) -> Message:
    """Append under a database write lock and reset the receipt atomically."""
    with self.transaction():
      row = self._conn.execute(
        "SELECT * FROM messages WHERE id = ?", (msg_id,)
      ).fetchone()
      if row is None:
        raise KeyError(f"Unknown message ID: {msg_id}")
      message = self._row_to_message(row)
      message.acks.append(reply)
      self._conn.execute(
        "UPDATE messages SET acks_json = ?, replies_seen = 0, status = 'acked', modified_at = ? WHERE id = ?",
        (json.dumps(message.acks), now, msg_id),
      )
      message.status = "acked"
      message.replies_seen = False
      message.modified_at = now
      return message

  def mark_message_seen(self, msg_id: str, now: str) -> Message:
    """Mark delivery without writing a stale reply list."""
    with self.transaction():
      self._conn.execute(
        "UPDATE messages SET status = 'seen', modified_at = ? WHERE id = ? AND status = 'sent'",
        (now, msg_id),
      )
      row = self._conn.execute(
        "SELECT * FROM messages WHERE id = ?", (msg_id,)
      ).fetchone()
      if row is None:
        raise KeyError(f"Unknown message ID: {msg_id}")
      return self._row_to_message(row)

  def mark_replies_seen(self, msg_id: str, revision: str) -> bool:
    """Mark replies seen only if the rendered revision is still current."""
    with self.transaction():
      row = self._conn.execute(
        "SELECT acks_json FROM messages WHERE id = ?", (msg_id,)
      ).fetchone()
      if row is None:
        raise KeyError(f"Unknown message ID: {msg_id}")
      raw = row["acks_json"] or "[]"
      canonical = json.dumps(json.loads(raw))
      actual = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
      if not hmac.compare_digest(actual, revision):
        return False
      self._conn.execute("UPDATE messages SET replies_seen = 1 WHERE id = ?", (msg_id,))
      return True

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
    with self.transaction():
      self._conn.execute("DELETE FROM tasks")
      for index, task in enumerate(tasks):
        self._conn.execute(
          """
          INSERT INTO tasks (
            position, id, title, type, status, scope,
            details_json, answer_snapshots_json, links_json, msg_ids_json, report_ids_json, deps_json, modified_at
          ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
          """,
          (
            index,
            task.id,
            task.title,
            task.type,
            task.status,
            task.scope,
            json.dumps(task.details),
            json.dumps(task.answer_snapshots),
            json.dumps(task.links),
            json.dumps(task.msg_ids),
            json.dumps(task.report_ids),
            json.dumps(task.task_ids),
            task.modified_at,
          ),
        )
    return list(tasks)

  def delete_task(self, task_id: str) -> bool:
    with self.transaction():
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
    with self.transaction():
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
    with self.transaction():
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
    with self.transaction():
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
      replies_seen=bool(row["replies_seen"]) if "replies_seen" in keys else False,
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
        answer_snapshots=json.loads(row["answer_snapshots_json"] or "[]"),
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
      answer_snapshots=json.loads(row["answer_snapshots_json"] or "[]"),
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
