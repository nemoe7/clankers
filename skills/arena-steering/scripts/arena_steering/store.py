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
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .models import (
  TASK_STATUSES,
  Attachment,
  Message,
  Report,
  ReportAnswer,
  ReportField,
  Task,
)

STATE_TABLES = ("messages", "tasks", "reports")
LEGACY_TASK_STATUSES = frozenset({"in_progress", "blocked"})
_STATE_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


def _timestamp_us(value: str) -> int:
  if not value:
    return 0
  stamp = datetime.fromisoformat(value)
  stamp = stamp.replace(tzinfo=UTC) if stamp.tzinfo is None else stamp.astimezone(UTC)
  delta = stamp - _STATE_EPOCH
  return (delta.days * 86400 + delta.seconds) * 1_000_000 + delta.microseconds


def _timestamp_iso(value: int) -> str:
  return (
    (_STATE_EPOCH + timedelta(microseconds=value))
    .isoformat(timespec="microseconds")
    .replace("+00:00", "Z")
  )


def _message_write_stamp(previous: str, proposed: str) -> str:
  return _timestamp_iso(max(_timestamp_us(previous) + 1, _timestamp_us(proposed)))


def _advance_stamp(previous: str, proposed: str) -> str:
  old, new = _timestamp_us(previous), _timestamp_us(proposed)
  if new > old and proposed > previous:
    return proposed
  previous_time = datetime.fromisoformat(previous) if previous else _STATE_EPOCH
  zone = previous_time.tzinfo or UTC
  advanced = (_STATE_EPOCH + timedelta(microseconds=max(old + 1, new))).astimezone(zone)
  candidate = advanced.isoformat(timespec="microseconds").replace("+00:00", "Z")
  # Older peers compare stamps as text, including second-only timestamps.
  if candidate <= previous:
    advanced = advanced.replace(microsecond=0) + timedelta(seconds=1, microseconds=1)
    candidate = advanced.isoformat(timespec="microseconds").replace("+00:00", "Z")
  return candidate


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
          id TEXT PRIMARY KEY NOT NULL,
          written_at TEXT NOT NULL,
          body TEXT NOT NULL,
          hidden INTEGER NOT NULL DEFAULT 0,
          blocking INTEGER NOT NULL DEFAULT 1,
          attachments_json TEXT NOT NULL DEFAULT '[]',
          parent_ids_json TEXT NOT NULL DEFAULT '[]',
          status TEXT NOT NULL DEFAULT 'sent',
          acks_json TEXT NOT NULL DEFAULT '[]',
          replies_seen INTEGER NOT NULL DEFAULT 0,
          modified_at TEXT NOT NULL,
          message_type TEXT NOT NULL DEFAULT 'message',
          violation_type TEXT NOT NULL DEFAULT '',
          violation_clause_file TEXT NOT NULL DEFAULT '',
          answer_json TEXT NOT NULL DEFAULT '{}'
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
          ack_seen_at TEXT NOT NULL DEFAULT '',
          modified_at TEXT NOT NULL,
          updated_at TEXT NOT NULL DEFAULT '',
          last_viewed_at TEXT NOT NULL DEFAULT '',
          pinned INTEGER NOT NULL DEFAULT 0
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
      if "message_type" not in message_cols:
        self._conn.execute(
          "ALTER TABLE messages ADD COLUMN message_type TEXT NOT NULL DEFAULT 'message'"
        )
      if "answer_json" not in message_cols:
        self._conn.execute(
          "ALTER TABLE messages ADD COLUMN answer_json TEXT NOT NULL DEFAULT '{}'"
        )
      if "violation_type" not in message_cols:
        self._conn.execute(
          "ALTER TABLE messages ADD COLUMN violation_type TEXT NOT NULL DEFAULT ''"
        )
      if "violation_clause_file" not in message_cols:
        self._conn.execute(
          "ALTER TABLE messages ADD COLUMN violation_clause_file TEXT NOT NULL DEFAULT ''"
        )
      if "written_at" not in message_cols:
        self._conn.execute(
          "ALTER TABLE messages ADD COLUMN written_at TEXT NOT NULL DEFAULT ''"
        )
        last = ""
        for row in self._conn.execute(
          "SELECT id, modified_at FROM messages ORDER BY seq"
        ).fetchall():
          last = _message_write_stamp(last, str(row["modified_at"]))
          self._conn.execute(
            "UPDATE messages SET written_at = ? WHERE id = ?", (last, row["id"])
          )
      self._conn.execute(
        "CREATE INDEX IF NOT EXISTS messages_written_at ON messages(written_at, id)"
      )
      self._conn.execute(
        "CREATE INDEX IF NOT EXISTS messages_report_answer "
        "ON messages(message_type, json_extract(answer_json, '$.report_id'))"
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
      if "ack_seen_at" not in cols:
        self._conn.execute(
          "ALTER TABLE reports ADD COLUMN ack_seen_at TEXT NOT NULL DEFAULT ''"
        )
      if "updated_at" not in cols:
        self._conn.execute(
          "ALTER TABLE reports ADD COLUMN updated_at TEXT NOT NULL DEFAULT ''"
        )
      if "last_viewed_at" not in cols:
        self._conn.execute(
          "ALTER TABLE reports ADD COLUMN last_viewed_at TEXT NOT NULL DEFAULT ''"
        )
      if "pinned" not in cols:
        self._conn.execute(
          "ALTER TABLE reports ADD COLUMN pinned INTEGER NOT NULL DEFAULT 0"
        )
      self._init_state_tracking()
      now = datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
      legacy = self._conn.execute(
        "SELECT id, modified_at FROM tasks WHERE status IN ('in_progress', 'blocked')"
      ).fetchall()
      for row in legacy:
        self._conn.execute(
          "UPDATE tasks SET status = 'upcoming', modified_at = ? WHERE id = ?",
          (_advance_stamp(str(row["modified_at"]), now), row["id"]),
        )

  def _init_state_tracking(self) -> None:
    # Arrival order stays independent of the clocks in merged rows.
    self._conn.execute(
      "CREATE TABLE IF NOT EXISTS state_clock "
      "(singleton INTEGER PRIMARY KEY CHECK (singleton = 1), revision_us INTEGER NOT NULL)"
    )
    self._conn.execute(
      "CREATE TABLE IF NOT EXISTS state_row_versions "
      "(table_name TEXT NOT NULL, row_id TEXT NOT NULL, revision_us INTEGER NOT NULL, "
      "PRIMARY KEY (table_name, row_id)) WITHOUT ROWID"
    )
    if (
      self._conn.execute("SELECT 1 FROM state_clock WHERE singleton = 1").fetchone()
      is None
    ):
      initial = time.time_ns() // 1_000
      for table in STATE_TABLES:
        for row in self._conn.execute(f"SELECT modified_at FROM {table}"):
          initial = max(initial, _timestamp_us(str(row[0] or "")))
      initial += 1
      self._conn.execute("INSERT INTO state_clock VALUES (1, ?)", (initial,))
      for table in STATE_TABLES:
        self._conn.execute(
          f"INSERT INTO state_row_versions SELECT ?, id, ? FROM {table}",
          (table, initial),
        )
    now_us = (
      "CAST(strftime('%s', 'now') AS INTEGER) * 1000000 + "
      "CAST(substr(strftime('%f', 'now'), 4, 3) AS INTEGER) * 1000"
    )
    for table in STATE_TABLES:
      for action in ("INSERT", "UPDATE"):
        self._conn.execute(
          f"""
          CREATE TRIGGER IF NOT EXISTS {table}_state_{action.lower()} AFTER {action} ON {table}
          BEGIN
            UPDATE state_clock SET revision_us = MAX(revision_us + 1, {now_us}) WHERE singleton = 1;
            INSERT INTO state_row_versions VALUES ('{table}', NEW.id,
              (SELECT revision_us FROM state_clock WHERE singleton = 1))
            ON CONFLICT(table_name, row_id) DO UPDATE SET revision_us = excluded.revision_us;
          END
          """
        )
      self._conn.execute(
        f"""
        CREATE TRIGGER IF NOT EXISTS {table}_state_delete AFTER DELETE ON {table}
        BEGIN
          UPDATE state_clock SET revision_us = MAX(revision_us + 1, {now_us}) WHERE singleton = 1;
          DELETE FROM state_row_versions WHERE table_name = '{table}' AND row_id = OLD.id;
        END
        """
      )

  def close(self) -> None:
    """Close the underlying SQLite connection."""
    with self._lock:
      self._conn.close()

  def data_version(self) -> tuple[int, int]:
    """Count commits from other connections and changes on this connection."""
    with self._lock:
      row = self._conn.execute("PRAGMA data_version").fetchone()
      return (int(row[0]) if row else 0, self._conn.total_changes)

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
      rows = self._conn.execute(
        "SELECT * FROM messages ORDER BY written_at ASC, id ASC"
      ).fetchall()
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
          f"SELECT written_at FROM messages WHERE id = ? AND {where}", [before, *params]
        ).fetchone()
        if row is None:
          raise ValueError(
            "Message page cursor is missing or does not match the filters"
          )
        cursor = row[0]
      page_where = where + (
        " AND (written_at, id) < (?, ?)" if cursor is not None else ""
      )
      page_params = [
        *params,
        *([cursor, before] if cursor is not None else []),
        limit + 1,
      ]
      rows = self._conn.execute(
        f"SELECT * FROM messages WHERE {page_where} "
        "ORDER BY written_at DESC, id DESC LIMIT ?",
        page_params,
      ).fetchall()
    has_more = len(rows) > limit
    return (
      [self._row_to_message(row) for row in reversed(rows[:limit])],
      total,
      has_more,
    )

  def _message_written_at(self, proposed: str) -> str:
    row = self._conn.execute(
      "SELECT written_at FROM messages ORDER BY written_at DESC, id DESC LIMIT 1"
    ).fetchone()
    return _message_write_stamp(str(row[0]) if row is not None else "", proposed)

  def save_message(self, message: Message) -> Message:
    with self.transaction():
      existing = self._conn.execute(
        "SELECT modified_at FROM messages WHERE id = ?", (message.id,)
      ).fetchone()
      if existing is not None:
        message.modified_at = _advance_stamp(
          str(existing["modified_at"]), message.modified_at
        )
      attachments_json = json.dumps([item.to_dict() for item in message.attachments])
      parent_ids_json = json.dumps(message.parent_ids)
      acks_json = json.dumps(message.acks)
      if existing is None:
        self._conn.execute(
          """
          INSERT INTO messages (
            id, written_at, body, hidden, blocking, attachments_json, parent_ids_json,
            status, acks_json, modified_at, message_type, violation_type,
            violation_clause_file, answer_json
          ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
          """,
          (
            message.id,
            self._message_written_at(message.modified_at),
            message.body,
            int(message.hidden),
            int(message.blocking),
            attachments_json,
            parent_ids_json,
            message.status,
            acks_json,
            message.modified_at,
            message.type,
            message.violation_type,
            message.violation_clause_file,
            json.dumps(message.answer_data),
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
              modified_at = ?,
              message_type = ?,
              violation_type = ?,
              violation_clause_file = ?,
              answer_json = ?
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
            message.type,
            message.violation_type,
            message.violation_clause_file,
            json.dumps(message.answer_data),
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
      if self._conn.execute(
        "SELECT 1 FROM messages WHERE id = ?", (message.id,)
      ).fetchone():
        raise ValueError(f"Message ID {message.id!r} already exists")
      self._conn.execute(
        """INSERT INTO messages
          (id, written_at, body, hidden, blocking, attachments_json, parent_ids_json,
           status, acks_json, modified_at)
          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
          message.id,
          self._message_written_at(message.modified_at),
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
      now = _advance_stamp(message.modified_at, now)
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
      row = self._conn.execute(
        "SELECT * FROM messages WHERE id = ?", (msg_id,)
      ).fetchone()
      if row is None:
        raise KeyError(f"Unknown message ID: {msg_id}")
      if row["status"] == "sent":
        now = _advance_stamp(str(row["modified_at"]), now)
        self._conn.execute(
          "UPDATE messages SET status = 'seen', modified_at = ? WHERE id = ?",
          (now, msg_id),
        )
        row = self._conn.execute(
          "SELECT * FROM messages WHERE id = ?", (msg_id,)
        ).fetchone()
      return self._row_to_message(row)

  def mark_replies_seen(self, msg_id: str, revision: str) -> bool:
    """Mark replies seen only if the rendered revision is still current."""
    with self.transaction():
      row = self._conn.execute(
        "SELECT acks_json, replies_seen, modified_at FROM messages WHERE id = ?",
        (msg_id,),
      ).fetchone()
      if row is None:
        raise KeyError(f"Unknown message ID: {msg_id}")
      raw = row["acks_json"] or "[]"
      canonical = json.dumps(json.loads(raw))
      actual = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
      if not hmac.compare_digest(actual, revision):
        return False
      if not row["replies_seen"]:
        now = _advance_stamp(str(row["modified_at"]), datetime.now(UTC).isoformat())
        self._conn.execute(
          "UPDATE messages SET replies_seen = 1, modified_at = ? WHERE id = ?",
          (now, msg_id),
        )
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
      previous = {
        str(row["id"]): row for row in self._conn.execute("SELECT * FROM tasks")
      }
      self._conn.execute("DELETE FROM tasks")
      for index, task in enumerate(tasks):
        task.details = list(dict.fromkeys(line.strip() for line in task.details))
        row = previous.get(task.id)
        if row is not None and (
          int(row["position"]) != index
          or json.loads(row["details_json"] or "[]") != task.details
          or self._row_to_task(row).to_dict() != task.to_dict()
        ):
          task.modified_at = _advance_stamp(str(row["modified_at"]), task.modified_at)
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
    with self.transaction():
      cur = self._conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
      if cur.rowcount == 0:
        return False
      rows = self._conn.execute(
        "SELECT id, position, modified_at FROM tasks ORDER BY position ASC"
      ).fetchall()
      for index, row in enumerate(rows):
        if int(row["position"]) != index:
          now = _advance_stamp(str(row["modified_at"]), datetime.now(UTC).isoformat())
          self._conn.execute(
            "UPDATE tasks SET position = ?, modified_at = ? WHERE id = ?",
            (index, now, row["id"]),
          )
      return True

  def list_report_answers(self, report_id: str | None = None) -> list[ReportAnswer]:
    """Project report answers from their hidden messages in submission order."""
    where = "message_type = 'report_answer'"
    params: tuple[str, ...] = ()
    if report_id is not None:
      where += " AND json_extract(answer_json, '$.report_id') = ?"
      params = (report_id,)
    with self._lock:
      rows = self._conn.execute(
        f"SELECT * FROM messages WHERE {where} "
        "ORDER BY json_extract(answer_json, '$.created_at'), id",
        params,
      ).fetchall()
      return [self._row_to_message(row).as_report_answer() for row in rows]

  def save_report_answer(self, answer: ReportAnswer) -> ReportAnswer:
    """Store an answer as a typed hidden message."""
    with self.transaction():
      message = Message.from_report_answer(answer)
      existing = self.get_message(answer.id)
      if existing is not None:
        message.blocking = existing.blocking
      self.save_message(message)
    return answer

  def rename_report_answers(self, old_id: str, new_id: str, now: str) -> None:
    """Move answer references with a report rename."""
    with self.transaction():
      for answer in self.list_report_answers(old_id):
        answer.report_id = new_id
        answer.modified_at = now
        self.save_report_answer(answer)

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
    """Remove the report row while retaining its answer messages."""
    with self.transaction():
      cursor = self._conn.execute("DELETE FROM reports WHERE id = ?", (report_id,))
      return cursor.rowcount > 0

  def save_report(self, report: Report) -> Report:
    with self.transaction():
      existing = self._conn.execute(
        "SELECT seq, modified_at FROM reports WHERE id = ?", (report.id,)
      ).fetchone()
      if existing is not None:
        report.modified_at = _advance_stamp(
          str(existing["modified_at"]), report.modified_at
        )
      fields_json = json.dumps([item.to_dict() for item in report.fields])
      # The compatibility column is not authoritative and old answers are not migrated.
      answers_json = "[]"
      if existing is None:
        self._conn.execute(
          """
          INSERT INTO reports (
            id, title, body, fields_json, status, answers_json, seen, ack_seen, ack_seen_at,
            modified_at, updated_at, last_viewed_at, pinned
          ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            report.ack_seen_at,
            report.modified_at,
            report.updated_at,
            report.last_viewed_at,
            int(report.pinned),
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
              seen = ?,
              ack_seen = ?,
              ack_seen_at = ?,
              modified_at = ?,
              updated_at = ?,
              last_viewed_at = ?,
              pinned = ?
          WHERE id = ?
          """,
          (
            report.title,
            report.body,
            fields_json,
            report.status,
            int(report.seen),
            int(report.ack_seen),
            report.ack_seen_at,
            report.modified_at,
            report.updated_at,
            report.last_viewed_at,
            int(report.pinned),
            report.id,
          ),
        )
    return report

  def export_rows(self, since: str | None = None) -> dict[str, list[dict[str, object]]]:
    """Return rows changed after this database's cursor, or a full snapshot."""
    with self._lock:
      cursor = _timestamp_us(since) if since else None
      latest = int(
        self._conn.execute(
          "SELECT revision_us FROM state_clock WHERE singleton = 1"
        ).fetchone()[0]
      )
      if cursor is not None and cursor > latest:
        cursor = None
      out: dict[str, list[dict[str, object]]] = {}
      for table in STATE_TABLES:
        if cursor is not None:
          rows = self._conn.execute(
            f"SELECT source.* FROM {table} source JOIN state_row_versions version "
            "ON version.table_name = ? AND version.row_id = source.id "
            "WHERE version.revision_us > ? ORDER BY source.rowid",
            (table, cursor),
          ).fetchall()
        else:
          rows = self._conn.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall()
        out[table] = [dict(row) for row in rows]
        if table == "messages":
          for row in out[table]:
            row.pop("seq", None)
      return out

  def state_stamp(self) -> str:
    """Return the database's monotonic state cursor as a UTC timestamp."""
    with self._lock:
      row = self._conn.execute(
        "SELECT revision_us FROM state_clock WHERE singleton = 1"
      ).fetchone()
      return _timestamp_iso(int(row[0]))

  def export_state(
    self, since: str | None = None
  ) -> tuple[dict[str, list[dict[str, object]]], str]:
    """Capture rows and their cursor in one database transaction."""
    with self.transaction():
      return self.export_rows(since), self.state_stamp()

  def merge_rows(
    self, document: dict[str, list[dict[str, object]]]
  ) -> dict[str, list[str]]:
    """Merge rows by ID in one transaction, keeping the newer `modified_at`."""
    result: dict[str, list[str]] = {"added": [], "updated": [], "skipped": []}
    with self.transaction():
      for table in STATE_TABLES:
        columns = [
          str(row["name"])
          for row in self._conn.execute(f"PRAGMA table_info({table})").fetchall()
          if str(row["name"]) not in {"seq"}
        ]
        allowed = set(columns)
        for raw in document.get(table, []) or []:
          data = {key: value for key, value in dict(raw).items() if key in allowed}
          row_id = str(data.get("id") or "")
          if not row_id:
            result["skipped"].append("")
            continue
          current = self._conn.execute(
            f"SELECT modified_at FROM {table} WHERE id=?", (row_id,)
          ).fetchone()
          incoming_stamp = str(data.get("modified_at") or "")
          if current is not None and _timestamp_us(incoming_stamp) <= _timestamp_us(
            str(current["modified_at"])
          ):
            result["skipped"].append(row_id)
            continue
          if table == "messages":
            if current is None:
              stamp = data.get("written_at")
              data["written_at"] = (
                _timestamp_iso(_timestamp_us(str(stamp)))
                if stamp
                else self._message_written_at(incoming_stamp)
              )
            else:
              data.pop("written_at", None)
          if table == "tasks" and "details_json" in data:
            raw_details = json.loads(data["details_json"])
            unique_details = list(
              dict.fromkeys(str(line).strip() for line in raw_details)
            )
            if unique_details != raw_details:
              data["details_json"] = json.dumps(unique_details)
              now = (
                datetime.now(UTC)
                .isoformat(timespec="microseconds")
                .replace("+00:00", "Z")
              )
              data["modified_at"] = _advance_stamp(incoming_stamp, now)
          if table == "tasks" and "status" in data:
            status = data["status"]
            if isinstance(status, str) and status in LEGACY_TASK_STATUSES:
              data["status"] = "upcoming"
              now = (
                datetime.now(UTC)
                .isoformat(timespec="microseconds")
                .replace("+00:00", "Z")
              )
              data["modified_at"] = _advance_stamp(incoming_stamp, now)
            elif status not in TASK_STATUSES:
              raise ValueError(f"Invalid Task.status: {status!r}")
          if current is None:
            names = ",".join(data)
            marks = ",".join("?" for _ in data)
            self._conn.execute(
              f"INSERT INTO {table} ({names}) VALUES ({marks})", tuple(data.values())
            )
            result["added"].append(row_id)
          else:
            sets = ",".join(f"{key}=?" for key in data if key != "id")
            values = [value for key, value in data.items() if key != "id"]
            self._conn.execute(
              f"UPDATE {table} SET {sets} WHERE id=?", (*values, row_id)
            )
            result["updated"].append(row_id)
    return result

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
      type=str(row["message_type"]) if "message_type" in keys else "message",
      violation_type=str(row["violation_type"]) if "violation_type" in keys else "",
      violation_clause_file=str(row["violation_clause_file"])
      if "violation_clause_file" in keys
      else "",
      answer_data=json.loads(row["answer_json"] or "{}")
      if "answer_json" in keys
      else {},
    )

  @staticmethod
  def _row_to_task(row: sqlite3.Row) -> Task:
    keys = row.keys()
    status = "upcoming" if row["status"] in LEGACY_TASK_STATUSES else str(row["status"])
    raw_links = row["links_json"] if "links_json" in keys else ""
    parsed_links = json.loads(raw_links) if raw_links else None
    if isinstance(parsed_links, dict):
      return Task(
        id=str(row["id"]),
        title=str(row["title"]),
        type=str(row["type"]),
        status=status,
        scope=str(row["scope"]),
        details=[str(item) for item in json.loads(row["details_json"] or "[]")],
        allow_long_details=True,
        links=parsed_links,
        modified_at=str(row["modified_at"]),
      )
    return Task(
      id=str(row["id"]),
      title=str(row["title"]),
      type=str(row["type"]),
      status=status,
      scope=str(row["scope"]),
      details=[str(item) for item in json.loads(row["details_json"] or "[]")],
      allow_long_details=True,
      msg_ids=[str(item) for item in json.loads(row["msg_ids_json"] or "[]")],
      report_ids=[str(item) for item in json.loads(row["report_ids_json"] or "[]")],
      task_ids=[str(item) for item in json.loads(row["deps_json"] or "[]")],
      modified_at=str(row["modified_at"]),
    )

  def _row_to_report(self, row: sqlite3.Row) -> Report:
    return Report(
      id=str(row["id"]),
      title=str(row["title"]),
      body=str(row["body"]),
      fields=[
        ReportField.from_dict(item) for item in json.loads(row["fields_json"] or "[]")
      ],
      status=str(row["status"]),
      answers=self.list_report_answers(str(row["id"])),
      seen=bool(dict(row).get("seen", 0)),
      ack_seen=bool(dict(row).get("ack_seen", 0)),
      ack_seen_at=str(dict(row).get("ack_seen_at", "")),
      modified_at=str(row["modified_at"]),
      updated_at=str(dict(row).get("updated_at", "")),
      last_viewed_at=str(dict(row).get("last_viewed_at", "")),
      pinned=bool(dict(row).get("pinned", 0)),
    )
