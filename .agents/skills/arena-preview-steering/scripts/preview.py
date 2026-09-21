"""Shared preview runtime. Steering uses only Python's standard library."""

import argparse
import hashlib
import html
import json
import re
import secrets
import sqlite3
import sys
import uuid
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

try:
  import markdown_it  # noqa: F401

  HAS_RENDERER = True
except ImportError:
  HAS_RENDERER = False

ASSETS = Path(__file__).resolve().parents[1] / "assets"
IDENTIFIER = re.compile(r"[a-zA-Z0-9_-]{1,80}\Z")
MAX_REPORT = 2_000_000
# A report holds at most 50 fields of at most 2000 characters each, so its answers legitimately
# reach past the 4000 a note is capped at. Submissions get their own bound, with room to spare
# for the prompts and wrapper around them, and it refuses rather than truncating.
MAX_SUBMISSION = 150_000
# A submission is limited in characters and its request body in bytes, and the two are not the
# same size: 150,000 characters can be 900,000 bytes once each one is escaped as \uXXXX, so a
# body limit below that makes the documented maximum unreachable over HTTP, which is what a
# single 32 KiB limit for every POST did. Notes and rendered Markdown keep the small limit,
# since nothing about them is allowed to be that large.
MAX_BODY = 32_768
MAX_SUBMISSION_BODY = 1_000_000
# An upload is the size of a report submission, on the owner's answer in report submission c27a4dd5.
MAX_UPLOAD = 1_000_000
# Bytes land beside the database, never inside it, and the record carries the file name under this
# directory rather than an absolute path, so a state directory that moves still resolves.
UPLOAD_DIR = "uploads"
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
CHOICE = re.compile(r"^\s*[-*]\s+\(([ xX]?)\)\s+(\S.*?)\s*$")
CHECKBOX = re.compile(r"^\s*[-*]\s+\[([ xX]?)\]\s+(\S.*?)\s*$")
BLANK = re.compile(r"^(?:(.*?)[\s:])?_{3,}\s*$")
ANCHOR = re.compile(r"\s*\{#([a-zA-Z0-9_-]{1,80})\}\s*$")


def now():
  return datetime.now(timezone.utc).isoformat()


def identifier(value):
  if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
    raise ValueError("ID must contain 1–80 letters, digits, underscores or hyphens")
  return value


def note_text(text):
  if not isinstance(text, str) or not text.strip() or len(text) > 4000:
    raise ValueError("Enter a note of 1–4000 characters")
  return text


def when(value):
  """Return a timestamp a restore carried exactly as it arrived, once it parses."""
  try:
    datetime.fromisoformat(str(value))
  except ValueError as error:
    raise ValueError(f"Not a timestamp: {value!r}") from error
  return str(value)


def restore_receipt(acknowledged_at, ack_kind, ack_text):
  """Validate the receipt a restored line carries: all three fields, or none of them.

  A partial receipt is refused rather than filled in, because supplying the missing half
  is how a note comes back answered when nobody answered it.
  """
  carried = (acknowledged_at, ack_kind, ack_text)
  if all(value is None for value in carried):
    return (None, None, None)
  if any(value is None for value in carried):
    raise ValueError(
      "A restored receipt carries its stamp, kind and text, or none of them"
    )
  if ack_kind not in {"note", "reply"}:
    raise ValueError("Every acknowledgement is a note or a reply, with its text")
  return (when(acknowledged_at), ack_kind, note_text(ack_text))


def submission_text(text):
  """Report answers are not notes, so they carry their own cap and their own wording."""
  if not isinstance(text, str) or not text.strip():
    raise ValueError("A report submission carries at least one answer")
  if len(text) > MAX_SUBMISSION:
    raise ValueError(
      f"A report submission must be under {MAX_SUBMISSION:,} characters;"
      " answer fewer fields or shorten them"
    )
  return text


def slug(text, used):
  base = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60] or "field"
  candidate, suffix = base, 2
  while candidate in used:
    candidate = f"{base}-{suffix}"
    suffix += 1
  used.add(candidate)
  return candidate


def prompt_text(line):
  text = re.sub(r"^\s*(?:[-*+]\s+|#+\s+|>\s+|\d+[.)]\s+)", "", line).strip()
  return text.strip("*_` ").rstrip(":").strip()


def custom_label(option):
  """The label of a free-text option, or None for a plain one.

  `Label: ___` means free text whether it is a whole field or one option in a group, so the
  same BLANK pattern decides both; a bare `___` option falls back to the label `Other`.
  """
  found = BLANK.match(option)
  return None if not found else prompt_text(found.group(1) or "") or "Other"


def custom_answer(field, value):
  """True when `value` is typed text for one of this field's free-text options."""
  if not isinstance(value, str):
    return False
  for option in field["options"]:
    label = custom_label(option)
    if label is None or not value.startswith(f"{label}: "):
      continue
    typed = value[len(label) + 2 :]
    if typed.strip() and len(typed) <= 2000:
      return True
  return False


def parse_fields(markdown):
  """Split Markdown into prose blocks and answer fields written as list markers."""
  lines = markdown.splitlines()
  blocks, chunk, questions, used = [], [], [], set()
  fence, prompt, anchor, index, position = None, "", None, 0, 0
  while position < len(lines):
    line = lines[position]
    if fence is not None:
      chunk.append(line)
      if line.strip().startswith(fence):
        fence = None
      position += 1
      continue
    opening = FENCE.match(line)
    if opening:
      fence = opening.group(1)
      chunk.append(line)
      position += 1
      continue
    kind = (
      "choice" if CHOICE.match(line) else "checkbox" if CHECKBOX.match(line) else None
    )
    blank = None if kind else BLANK.match(line)
    if not kind and not blank:
      chunk.append(line)
      if line.strip():
        prompt, anchor = prompt_text(ANCHOR.sub("", line)), None
        found = ANCHOR.search(line)
        if found:
          anchor = found.group(1)
          chunk[-1] = ANCHOR.sub("", line)
      position += 1
      continue
    index += 1
    if kind:
      pattern = CHOICE if kind == "choice" else CHECKBOX
      options, default = [], []
      while position < len(lines):
        item = pattern.match(lines[position])
        if not item:
          break
        options.append(item.group(2))
        if item.group(1).lower() == "x":
          default.append(item.group(2))
        position += 1
      if len(set(options)) != len(options):
        raise ValueError(
          f"Field '{prompt or index}' repeats an option; make each unique"
        )
      question = {"type": kind, "options": options, "default": default}
    else:
      label = (blank.group(1) or "").strip()
      question = {"type": "text", "default": []}
      if label:
        prompt, anchor = prompt_text(ANCHOR.sub("", label)), None
        found = ANCHOR.search(label)
        if found:
          anchor = found.group(1)
      position += 1
    question["prompt"] = prompt or f"Field {index}"
    question["id"] = (
      anchor if anchor and anchor not in used else slug(question["prompt"], used)
    )
    used.add(question["id"])
    anchor = None
    blocks.append(("markdown", "\n".join(chunk)))
    blocks.append(("field", question))
    chunk = []
    questions.append(question)
  blocks.append(("markdown", "\n".join(chunk)))
  if questions:
    Store.validate_fields(questions)
  return blocks, questions


def field_html(question):
  prompt = html.escape(question["prompt"], quote=True)
  body = f'<div class="question" data-field="{html.escape(question["id"], quote=True)}"'
  body += f' data-type="{question["type"]}">'
  if question["type"] == "text":
    return (
      f'{body}<input type="text" maxlength="2000" placeholder="Answer" '
      f'aria-label="{prompt}"></div>'
    )
  control = "radio" if question["type"] == "choice" else "checkbox"
  group = f'<div class="options" role="group" aria-label="{prompt}">'
  name = html.escape(question["id"], quote=True)
  for option in question["options"]:
    value = html.escape(option, quote=True)
    checked = " checked" if option in question["default"] else ""
    label = custom_label(option)
    if label is None:
      group += (
        f'<label class="option"><input type="{control}" name="{name}" '
        f'value="{value}"{checked}> {html.escape(option)}</label>'
      )
      continue
    named = html.escape(label, quote=True)
    group += (
      f'<label class="option"><input type="{control}" name="{name}" '
      f'value="{value}"{checked} data-label="{named}" aria-label="{named}">'
      f'<textarea class="custom-text" rows="1" maxlength="2000" data-custom="{named}" '
      f'placeholder="{named}:" aria-label="{named}, your own answer"></textarea></label>'
    )
  return f"{body}{group}</div></div>"


TASK_STATUSES = ("upcoming", "finished")
TASK_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
MAX_TASK_TITLE = 200
MAX_TASK_DETAIL = 2000
MAX_TASK_DETAILS = 40
ECHO_DETAIL = 200
TASK_COLUMNS = "id, title, details, status, position, updated_at"
# The save button writes one file the importers read: a note line carries `text`, a task line
# carries `title`, an answer line carries `report_id`, and each importer takes its own lines and
# skips the rest. Keys are named here so the writer and the readers cannot drift apart.
#
# The file sits untracked at the repository root, on the owner's answer to the save-state report
# (report submission c0fcfad9): a restore keeps the repository, so the copy survives the event it
# exists for, and only explicit paths are staged, so it stays out of every commit.
SAVED_STATE = "saved-state.ndjson"
NOTE_LINE_KEYS = (
  "id",
  "text",
  "at",
  "acknowledged_at",
  "ack_kind",
  "ack_text",
  "seen_at",
  "origin",
  "task_id",
)
TASK_LINE_KEYS = ("id", "title", "details", "status", "order")
SUBMISSION_LINE_KEYS = (
  "id",
  "report_id",
  "text",
  "at",
  "acknowledged_at",
  "ack_kind",
  "ack_text",
  "seen_at",
  "task_id",
)


def task_row(row):
  """Shape one stored task for the state payload, keeping its details a list."""
  return {
    "id": row[0],
    "title": row[1],
    "details": json.loads(row[2]),
    "status": row[3],
    "order": row[4],
    "updated_at": row[5],
  }


def echo_task(record, before=None, after=None):
  """The confirmation an agent gets back: whole title, details cut, neighbours named."""
  return {
    "id": record["id"],
    "title": record["title"],
    "status": record["status"],
    "order": record["order"],
    "prev": before,
    "next": after,
    "details": [
      detail[:ECHO_DETAIL] + ("\u2026" if len(detail) > ECHO_DETAIL else "")
      for detail in record["details"]
    ],
  }


def saved_note_line(record):
  """Return the keys a saved note line carries, and nothing else."""
  if not isinstance(record, dict):
    raise TypeError("Every saved note is an object")
  return {key: record.get(key) for key in NOTE_LINE_KEYS}


def saved_answer_line(record):
  """Return the keys a saved report answer line carries, so a restore keeps the answer."""
  if not isinstance(record, dict):
    raise TypeError("Every saved answer is an object")
  return {key: record.get(key) for key in SUBMISSION_LINE_KEYS}


def saved_task_line(record):
  """Return the keys a saved task line carries; details keep their list shape."""
  if not isinstance(record, dict):
    raise TypeError("Every saved task is an object")
  line = {key: record.get(key) for key in TASK_LINE_KEYS}
  line["details"] = [str(item) for item in record.get("details") or []]
  return line


def upload_name(name):
  """The owner's file name, kept for display and for the download header."""
  cleaned = Path(str(name or "")).name.strip()
  if not cleaned:
    raise ValueError("An upload needs a file name")
  if len(cleaned) > 200:
    raise ValueError("A file name must be 200 characters or fewer")
  return cleaned


def upload_type(content_type):
  """The content type the browser sent, or a neutral one; it never decides how the bytes are read."""
  cleaned = str(content_type or "").split(";")[0].strip()[:120]
  return cleaned or "application/octet-stream"


def upload_row(row, directory):
  """A stored upload, plus the two things the row cannot say: where the bytes are and whether they are there."""
  path = directory / UPLOAD_DIR / row["file"]
  return dict(row) | {"path": str(path), "present": path.exists()}


def cli_json(value, pretty=False):
  """Print agent-facing JSON minified; the agent pays for every space it reads.

  `--pretty` is the human escape hatch: indentation costs tokens, and the tokens are the point.
  """
  if pretty:
    return json.dumps(value, ensure_ascii=False, indent=2)
  return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def parse_task_import(text):
  """Accept either a JSON array of tasks or one task per line."""
  stripped = text.strip()
  if not stripped:
    raise ValueError("Nothing to import")
  records = (
    json.loads(stripped)
    if stripped.startswith("[")
    else [json.loads(line) for line in stripped.splitlines() if line.strip()]
  )
  if not isinstance(records, list) or not all(
    isinstance(item, dict) for item in records
  ):
    raise ValueError("Import a JSON array of task objects, or one task object per line")
  return records


def check_task(task_id, title, details):
  """Validate one task's fields before anything is written."""
  if not TASK_ID.match(task_id or ""):
    raise ValueError(
      "A task ID is 1-64 characters of lowercase letters, digits and hyphens,"
      " and starts with a letter or digit"
    )
  if title is not None and len(title) > MAX_TASK_TITLE:
    raise ValueError(f"A task title must be {MAX_TASK_TITLE} characters or fewer")
  if len(details or ()) > MAX_TASK_DETAILS:
    raise ValueError(f"A task carries at most {MAX_TASK_DETAILS} details")
  for detail in details or ():
    if len(detail) > MAX_TASK_DETAIL:
      raise ValueError(f"A task detail must be {MAX_TASK_DETAIL} characters or fewer")


def render_report(markdown):
  blocks, questions = parse_fields(markdown)
  parts = []
  for kind, item in blocks:
    if kind == "markdown":
      if item.strip():
        parts.append(render(item))
    else:
      parts.append(field_html(item))
  return "".join(parts), questions


class Store:
  def __init__(self, directory, create=False, save_path=None):
    directory = Path(directory).resolve()
    self.path = directory / "state.sqlite3"
    # The save file is not the database: it outlives a restore, so by default it is written
    # where the agent runs the command, which is the repository root (report c0fcfad9).
    self.save_path = Path(save_path) if save_path else Path(SAVED_STATE)
    existed = self.path.is_file()
    if not create and not existed:
      raise FileNotFoundError(f"Inbox missing: {self.path}; start the preview first")
    if create and not existed:
      directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    with closing(self.connect()) as db, db:
      db.executescript("""
        CREATE TABLE IF NOT EXISTS notes (
          seq INTEGER PRIMARY KEY, id TEXT UNIQUE NOT NULL,
          text TEXT NOT NULL, at TEXT NOT NULL, acknowledged_at TEXT,
          ack_kind TEXT, ack_text TEXT, seen_at TEXT, origin TEXT
        );
        CREATE TABLE IF NOT EXISTS reports (
          id TEXT PRIMARY KEY, title TEXT NOT NULL,
          markdown TEXT NOT NULL, updated_at TEXT NOT NULL, seq INTEGER, seen_at TEXT
        );
        CREATE TABLE IF NOT EXISTS submissions (
          seq INTEGER PRIMARY KEY, id TEXT UNIQUE NOT NULL,
          report_id TEXT NOT NULL, text TEXT NOT NULL, at TEXT NOT NULL,
          acknowledged_at TEXT, ack_kind TEXT, ack_text TEXT, seen_at TEXT
        );
        CREATE TABLE IF NOT EXISTS uploads (
          seq INTEGER PRIMARY KEY, id TEXT UNIQUE NOT NULL,
          name TEXT NOT NULL, type TEXT NOT NULL, size INTEGER NOT NULL,
          sha256 TEXT NOT NULL, file TEXT NOT NULL, at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS tasks (
          id TEXT PRIMARY KEY,
          title TEXT NOT NULL,
          details TEXT NOT NULL DEFAULT '[]',
          status TEXT NOT NULL DEFAULT 'upcoming'
            CHECK (status IN ('upcoming', 'finished')),
          position INTEGER NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
      """)
      columns = {row["name"] for row in db.execute("PRAGMA table_info(notes)")}
      for column in ("ack_kind", "ack_text", "seen_at", "origin", "task_id"):
        if column not in columns:
          db.execute(f"ALTER TABLE notes ADD COLUMN {column} TEXT")
      if "seen_at" not in columns:
        db.execute(
          "UPDATE notes SET seen_at = acknowledged_at"
          " WHERE seen_at IS NULL AND acknowledged_at IS NOT NULL"
        )
      columns = {row["name"] for row in db.execute("PRAGMA table_info(submissions)")}
      if "seen_at" not in columns:
        db.execute("ALTER TABLE submissions ADD COLUMN seen_at TEXT")
      if "task_id" not in columns:
        db.execute("ALTER TABLE submissions ADD COLUMN task_id TEXT")
      columns = {row["name"] for row in db.execute("PRAGMA table_info(reports)")}
      if "seen_at" not in columns:
        db.execute("ALTER TABLE reports ADD COLUMN seen_at TEXT")
        db.execute(
          "UPDATE submissions SET seen_at = acknowledged_at"
          " WHERE seen_at IS NULL AND acknowledged_at IS NOT NULL"
        )
      columns = {row["name"] for row in db.execute("PRAGMA table_info(reports)")}
      if "seq" not in columns:
        db.execute("ALTER TABLE reports ADD COLUMN seq INTEGER")
        db.execute("UPDATE reports SET seq = rowid WHERE seq IS NULL")
    if not existed:
      self.path.chmod(0o600)

  def connect(self):
    db = sqlite3.connect(self.path, timeout=5)
    db.row_factory = sqlite3.Row
    return db

  def note(
    self,
    note_id,
    text,
    at=None,
    acknowledged_at=None,
    ack_kind=None,
    ack_text=None,
    seen_at=None,
    origin=None,
    task_id=None,
  ):
    """Record a message; a restore carries its receipt and it is written as given.

    `origin` is `agent` for a message the agent wrote through the CLI and None for the owner's,
    which is what lets the log say who wrote a line instead of showing every message in the
    owner's voice. Anything else is refused rather than stored as a third kind of author.

    Nothing here stamps a receipt with now(), because a restored acknowledgement has to
    say when it was actually written. Read state rides along on the same terms and answers
    to nobody, so a line seen but never answered comes back seen and unacknowledged. An ID
    that is already stored keeps the record it has, so importing the same log twice
    changes nothing.
    """
    identifier(note_id)
    note_text(text)
    if origin not in (None, "agent"):
      raise ValueError("A message is the owner's or the agent's")
    receipt = restore_receipt(acknowledged_at, ack_kind, ack_text)
    seen = when(seen_at) if seen_at is not None else None
    with closing(self.connect()) as db, db:
      db.execute("BEGIN IMMEDIATE")
      existing = db.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
      if existing:
        if existing["text"] != text:
          raise ValueError("This message ID already belongs to different text")
        return dict(existing)
      db.execute(
        "INSERT INTO notes"
        " (id, text, at, acknowledged_at, ack_kind, ack_text, seen_at, origin, task_id)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (note_id, text, at or now(), *receipt, seen, origin, task_id),
      )
      return dict(db.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone())

  def submission(
    self,
    submission_id,
    report_id,
    text,
    at=None,
    acknowledged_at=None,
    ack_kind=None,
    ack_text=None,
    seen_at=None,
    task_id=None,
  ):
    """Record report answers apart from user messages; the log never shows them.

    `import-notes` restores a saved answer through here too, receipt and all, for the same
    reason a note keeps its own: the save file exists so a restore returns what the owner
    sent, and an answer that comes back unread was read when the agent read it (report
    submission c0fcfad9, note 120fe358). An ID already stored keeps its record.
    """
    identifier(submission_id)
    identifier(report_id)
    submission_text(text)
    with closing(self.connect()) as db, db:
      db.execute("BEGIN IMMEDIATE")
      existing = db.execute(
        "SELECT * FROM submissions WHERE id = ?", (submission_id,)
      ).fetchone()
      if existing:
        if existing["text"] != text:
          raise ValueError("This message ID already belongs to different text")
        return dict(existing)
      db.execute(
        "INSERT INTO submissions"
        " (id, report_id, text, at, acknowledged_at, ack_kind, ack_text, seen_at, task_id)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
          submission_id,
          report_id,
          text,
          at or now(),
          *restore_receipt(acknowledged_at, ack_kind, ack_text),
          when(seen_at) if seen_at is not None else None,
          task_id,
        ),
      )
      return dict(
        db.execute(
          "SELECT * FROM submissions WHERE id = ?", (submission_id,)
        ).fetchone()
      )

  def submissions(self):
    with closing(self.connect()) as db:
      return [dict(row) for row in db.execute("SELECT * FROM submissions ORDER BY seq")]

  def state(self):
    tasks = self.tasks()
    with closing(self.connect()) as db:
      meta = dict(db.execute("SELECT key, value FROM meta"))
      return {
        "notes": [dict(row) for row in db.execute("SELECT * FROM notes ORDER BY seq")],
        "reports": [
          dict(row)
          for row in db.execute(
            "SELECT id, title, updated_at, seq, seen_at FROM reports ORDER BY seq, id"
          )
        ],
        "tasks": tasks,
        "uploads": self.uploads(),
        "last_check": meta.get("last_check"),
      }

  def tasks(self):
    """Both divs as records in order, or None while nothing is stored."""
    with closing(self.connect()) as db:
      rows = db.execute(
        f"SELECT {TASK_COLUMNS} FROM tasks ORDER BY status DESC, position, id"
      ).fetchall()
    records = [task_row(row) for row in rows]
    if not records:
      return None
    return {
      "finished": [item for item in records if item["status"] == "finished"],
      "upcoming": [item for item in records if item["status"] == "upcoming"],
      "updated_at": max(item["updated_at"] for item in records),
    }

  def list_tasks(self):
    """Every task as stored, for an agent to read the list back."""
    with closing(self.connect()) as db:
      rows = db.execute(
        f"SELECT {TASK_COLUMNS} FROM tasks ORDER BY status DESC, position, id"
      ).fetchall()
    return [task_row(row) for row in rows]

  @contextmanager
  def transaction(self, db=None):
    """One commit for this call's work, or a caller's open transaction when it passes one.

    An import needs the second form: a delete and several writes that all land or none do.
    """
    if db is not None:
      yield db
      return
    with closing(self.connect()) as own, own:
      yield own

  def write_task(
    self, task_id, title=None, details=None, status=None, order=None, shared=None
  ):
    """Insert or update one task and return it as stored.

    A title or details left out keep the stored ones, so moving a task between
    the two divs is one short command rather than a rewrite of the whole list.
    A transaction passed in is written into rather than committed separately,
    which is what lets an import be one atomic replacement.
    """
    details = [str(item) for item in details if str(item).strip()] if details else None
    check_task(task_id, title, details)
    if status is not None and status not in TASK_STATUSES:
      raise ValueError(f"A task is either {' or '.join(TASK_STATUSES)}")
    stamp = now()
    with self.transaction(shared) as db:
      row = db.execute(
        f"SELECT {TASK_COLUMNS} FROM tasks WHERE id = ?", (task_id,)
      ).fetchone()
      stored = task_row(row) if row else None
      if stored is None and title is None:
        raise ValueError("A new task needs a title")
      title = title if title is not None else stored["title"]
      if details is None:
        details = stored["details"] if stored else []
      status = status or (stored["status"] if stored else "upcoming")
      siblings = [
        task_row(item)
        for item in db.execute(
          f"SELECT {TASK_COLUMNS} FROM tasks WHERE status = ? AND id != ?"
          " ORDER BY position, id",
          (status, task_id),
        ).fetchall()
      ]
      record = {
        "id": task_id,
        "title": title,
        "details": details,
        "status": status,
        "order": len(siblings) + 1,
        "updated_at": stamp,
      }
      if order is not None:
        index = max(0, min(order - 1, len(siblings)))
      elif stored and stored["status"] == status:
        index = max(0, min(stored["order"] - 1, len(siblings)))
      else:
        index = len(siblings)
      siblings.insert(index, record)
      record["order"] = index + 1
      db.execute(
        "INSERT INTO tasks VALUES (?, ?, ?, ?, ?, ?, ?)"
        " ON CONFLICT(id) DO UPDATE SET title = excluded.title,"
        " details = excluded.details, status = excluded.status,"
        " position = excluded.position, updated_at = excluded.updated_at",
        (
          task_id,
          title,
          json.dumps(details, ensure_ascii=False),
          status,
          index + 1,
          stamp,
          stamp,
        ),
      )
      # Positions are written from the computed list, because the row just upserted can tie
      # with a sibling it was inserted before, and a tie would reorder them by ID.
      for position, item in enumerate(siblings, 1):
        db.execute("UPDATE tasks SET position = ? WHERE id = ?", (position, item["id"]))
      self.renumber(db)
    return record

  def remove_task(self, task_id):
    """Delete one task and return what was stored, so the echo can confirm it."""
    with closing(self.connect()) as db, db:
      row = db.execute(
        f"SELECT {TASK_COLUMNS} FROM tasks WHERE id = ?", (task_id,)
      ).fetchone()
      if row is None:
        raise ValueError(f"No task is stored under {task_id}")
      db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
      self.renumber(db)
    return task_row(row)

  def neighbours(self, task_id):
    """The IDs either side of one task inside its own div, or None at the ends."""
    with closing(self.connect()) as db:
      row = db.execute(
        "SELECT status, position FROM tasks WHERE id = ?", (task_id,)
      ).fetchone()
      if row is None:
        return None, None
      status, position = row
      before = db.execute(
        "SELECT id FROM tasks WHERE status = ? AND position < ?"
        " ORDER BY position DESC, id DESC LIMIT 1",
        (status, position),
      ).fetchone()
      after = db.execute(
        "SELECT id FROM tasks WHERE status = ? AND position > ?"
        " ORDER BY position, id LIMIT 1",
        (status, position),
      ).fetchone()
    return (before[0] if before else None, after[0] if after else None)

  def amend_task(self, prev_id, task_id):
    """Move a stored task to a new ID and keep the rest, so a typo costs no deletion."""
    check_task(task_id, None, None)
    stamp = now()
    with closing(self.connect()) as db, db:
      row = db.execute(
        "SELECT id, title, details, status, position, created_at FROM tasks WHERE id = ?",
        (prev_id,),
      ).fetchone()
      if row is None:
        raise ValueError(f"No task is stored under {prev_id}")
      if db.execute("SELECT 1 FROM tasks WHERE id = ?", (task_id,)).fetchone():
        raise ValueError(f"A task is already stored under {task_id}")
      db.execute("DELETE FROM tasks WHERE id = ?", (prev_id,))
      db.execute(
        "INSERT INTO tasks VALUES (?, ?, ?, ?, ?, ?, ?)",
        (task_id, row[1], row[2], row[3], row[4], row[5], stamp),
      )
      self.renumber(db)

  def save_state(self, payload):
    """Write the page's cached state to the save file, in the shape the importers read.

    The browser cannot write the sandbox filesystem, so it posts what it holds and this writes it.
    Note lines keep their receipts, read stamps and task markers, because a restore that drops any
    of them is the failure this exists to prevent; task lines keep their status and order, so the
    queue comes back in the same shape. Answer lines come from the database rather than from the
    page, because the owner's report answers are stored here the moment they are sent, and an
    answer that a restore drops is an answer the owner has to type again (note 120fe358).

    The file lands at the repository root and stays untracked (report submission c0fcfad9): a
    restore keeps the checkout, so the copy outlives the database beside it.
    """
    if not isinstance(payload, dict):
      raise TypeError("Save a state object")
    notes = payload.get("notes")
    tasks = payload.get("tasks")
    if not isinstance(notes, list) or not isinstance(tasks, dict):
      raise TypeError("Save a state object with notes and tasks")
    lines = [saved_note_line(record) for record in notes]
    for status in TASK_STATUSES:
      for record in tasks.get(status) or []:
        lines.append(saved_task_line(record))
    answers = [saved_answer_line(record) for record in self.submissions()]
    lines.extend(answers)
    path = self.save_path
    if path.parent != Path("."):
      path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
      "".join(json.dumps(line, ensure_ascii=False) + "\n" for line in lines),
      encoding="utf-8",
    )
    return {
      "path": str(path),
      "notes": len(notes),
      "tasks": len(lines) - len(notes) - len(answers),
      "answers": len(answers),
    }

  def uploads(self):
    """Every upload, newest last, with `present` saying whether its bytes are still on disk."""
    with closing(self.connect()) as db:
      rows = db.execute("SELECT * FROM uploads ORDER BY seq").fetchall()
    return [upload_row(row, self.path.parent) for row in rows]

  def upload(self, upload_id):
    """One upload by ID, or None; the bytes are read separately so a missing file is a 404."""
    identifier(upload_id)
    with closing(self.connect()) as db:
      row = db.execute("SELECT * FROM uploads WHERE id = ?", (upload_id,)).fetchone()
    return None if row is None else upload_row(row, self.path.parent)

  def save_upload(self, name, content_type, data):
    """Write the bytes under the state directory and keep the record in the database.

    Disk first, on the owner's answer in report submission `c27a4dd5`: the bytes never pass through the
    database, and the row carries the file name, the size, the hash and the content type. A record
    outlives its file by design, because a restore deletes what is under the state directory, so
    `present` reports that instead of an entry that silently opens nothing. Any bytes are accepted,
    so a screenshot and an archive arrive as themselves.
    """
    if not isinstance(data, (bytes, bytearray)):
      raise TypeError("An upload is bytes")
    if not data:
      raise ValueError("An upload must not be empty")
    if len(data) > MAX_UPLOAD:
      raise ValueError(f"An upload must be {MAX_UPLOAD:,} bytes or fewer")
    cleaned = upload_name(name)
    upload_id = str(uuid.uuid4())
    directory = self.path.parent / UPLOAD_DIR
    directory.mkdir(parents=True, exist_ok=True)
    # The id names the file on disk and the owner's name only reaches the record, so no path the owner
    # types can escape the uploads directory.
    target = directory / f"{upload_id}{Path(cleaned).suffix[:16]}"
    target.write_bytes(bytes(data))
    stamp = now()
    with closing(self.connect()) as db, db:
      db.execute(
        "INSERT INTO uploads (id, name, type, size, sha256, file, at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
          upload_id,
          cleaned,
          upload_type(content_type),
          len(data),
          hashlib.sha256(bytes(data)).hexdigest(),
          target.name,
          stamp,
        ),
      )
      row = db.execute("SELECT * FROM uploads WHERE id = ?", (upload_id,)).fetchone()
    return upload_row(row, self.path.parent)

  def import_tasks(self, records, replace=False):
    """Rebuild a list from the JSON a copy button or task-list produced.

    Every record is validated before anything is written, and the whole import is one
    transaction, so an invalid record costs nothing. Deleting first, as this did, meant a
    bad record later in the list took the existing list with it and left the replacement
    half applied, which is data loss rather than an error.
    """
    if not isinstance(records, list):
      # parse_task_import already refuses anything but a list of objects, so this only fires
      # for a caller that skipped it, and a wrong type is not a value problem.
      raise TypeError("Import a list of task objects")
    prepared = []
    for index, record in enumerate(records, 1):
      if not isinstance(record, dict):
        raise TypeError("Import a list of task objects")
      details = [str(item) for item in record.get("details") or [] if str(item).strip()]
      status = record.get("status")
      # The checks write_task applies, run over every record up front: an import that can
      # only fail on its fortieth record should fail before it touches the first.
      check_task(record.get("id"), record.get("title"), details)
      if status is not None and status not in TASK_STATUSES:
        raise ValueError(f"A task is either {' or '.join(TASK_STATUSES)}")
      prepared.append(
        (
          record.get("id"),
          record.get("title"),
          details,
          status,
          record.get("order") or index,
        )
      )
    with self.transaction() as db:
      if replace:
        # A replacement makes every record new, so a title cannot be inherited from a stored
        # row. Refusing before the delete names the offending record; refusing after it would
        # still roll back, but the error would arrive with the table emptied inside the
        # transaction and the record that caused it already written.
        for task_id, title, _, _, _ in prepared:
          stored = db.execute("SELECT 1 FROM tasks WHERE id = ?", (task_id,)).fetchone()
          if title is None and not stored:
            raise ValueError(f"A new task needs a title: {task_id}")
        db.execute("DELETE FROM tasks")
      written = [self.write_task(*item, shared=db) for item in prepared]
    return written

  def renumber(self, db):
    """Keep positions dense inside each div after a move, an insert or a removal."""
    for status in TASK_STATUSES:
      rows = db.execute(
        "SELECT id FROM tasks WHERE status = ? ORDER BY position, id", (status,)
      ).fetchall()
      for position, row in enumerate(rows, 1):
        db.execute("UPDATE tasks SET position = ? WHERE id = ?", (position, row[0]))

  def read(self):
    with closing(self.connect()) as db, db:
      stamp = now()
      for table in ("notes", "submissions"):
        db.execute(
          f"UPDATE {table} SET seen_at = ?"
          " WHERE acknowledged_at IS NULL AND seen_at IS NULL",
          (stamp,),
        )
      pending = [
        dict(row) | {"kind": "note"}
        for row in db.execute(
          "SELECT * FROM notes WHERE acknowledged_at IS NULL ORDER BY seq"
        )
      ]
      pending += [
        dict(row) | {"kind": "report"}
        for row in db.execute(
          "SELECT * FROM submissions WHERE acknowledged_at IS NULL ORDER BY seq"
        )
      ]
      pending.sort(key=lambda item: item["at"])
      checked = now()
      db.execute("INSERT OR REPLACE INTO meta VALUES ('last_check', ?)", (checked,))
      return {"checked_at": checked, "pending": pending}

  def mark_task(self, record_id, task_id, shared=None):
    """Record that a message has a task, on whichever table holds that message.

    The receipt then says so in the log, which is what the owner asked for (note fe00a32d):
    a line without a marker leaves the reader unable to tell whether it was read and dropped
    or read and queued. An unknown message ID raises, and a caller's transaction takes the
    task with it, so a mistyped ID costs no half-written task.
    """
    identifier(record_id)
    identifier(task_id)
    with self.transaction(shared) as db:
      for table in ("notes", "submissions"):
        cursor = db.execute(
          f"UPDATE {table} SET task_id = ? WHERE id = ?", (task_id, record_id)
        )
        if cursor.rowcount:
          return
    raise ValueError(f"Unknown note: {record_id}; no task marker written")

  def acknowledge(self, ids, kind, text):
    if kind not in {"note", "reply"}:
      raise ValueError("Every acknowledgement is a note or a reply, with its text")
    text = note_text(text)
    stamp = now()
    with closing(self.connect()) as db, db:
      for record_id in ids:
        identifier(record_id)
        for table in ("notes", "submissions"):
          cursor = db.execute(
            f"""UPDATE {table} SET acknowledged_at = COALESCE(acknowledged_at, ?),
               ack_kind = COALESCE(?, ack_kind), ack_text = COALESCE(?, ack_text),
               seen_at = COALESCE(seen_at, ?)
               WHERE id = ?""",
            (stamp, kind, text, stamp, record_id),
          )
          if cursor.rowcount:
            break
        else:
          raise ValueError(f"Unknown note: {record_id}; no receipts written")

  def publish(self, report_id, title, source):
    identifier(report_id)
    if not isinstance(title, str) or not title.strip() or len(title) > 200:
      raise ValueError("Report title must contain 1–200 characters")
    source = Path(source)
    if source.suffix.lower() != ".md":
      raise ValueError("Publish a UTF-8 .md source file")
    with source.open("rb") as stream:
      data = stream.read(MAX_REPORT + 1)
    if len(data) > MAX_REPORT:
      raise ValueError("Report exceeds the 2 MB limit; split it into reports")
    text = data.decode("utf-8")
    # A report whose fields fail validation used to publish happily and then break its own html
    # route at render time, so the owner could never open it. Refusing here costs the agent one
    # command and names the offending field; refusing there cost the report and, until the guard
    # below existed, the HTTP connection with it.
    parse_fields(text)
    with closing(self.connect()) as db, db:
      highest = db.execute("SELECT COALESCE(MAX(seq), 0) FROM reports").fetchone()[0]
      db.execute(
        """INSERT INTO reports (id, title, markdown, updated_at, seq)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(id) DO UPDATE SET title = excluded.title,
             markdown = excluded.markdown, updated_at = excluded.updated_at,
             seq = COALESCE(reports.seq, excluded.seq), seen_at = NULL""",
        (report_id, title, text, now(), highest + 1),
      )

  def mark_report_seen(self, report_id):
    """Stamp the moment the owner reached the end of a report, and only the first one.

    The stamp records when the report was actually read, so reopening it in another browser
    keeps that moment instead of moving it. Republishing clears it, which is what makes a
    changed report unread in fact rather than unread by a comparison the client has to get right.
    """
    identifier(report_id)
    with closing(self.connect()) as db, db:
      row = db.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
      if row is None:
        raise FileNotFoundError("Report not found")
      db.execute(
        "UPDATE reports SET seen_at = COALESCE(seen_at, ?) WHERE id = ?",
        (now(), report_id),
      )
      return dict(
        db.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
      )

  def report(self, report_id):
    identifier(report_id)
    with closing(self.connect()) as db:
      row = db.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
      if row is None:
        raise FileNotFoundError("Report not found")
      return dict(row)

  @staticmethod
  def validate_fields(fields):
    if not 1 <= len(fields) <= 50:
      raise ValueError("A report holds 1–50 fields")
    seen = set()
    for field in fields:
      field_id = field["id"]
      identifier(field_id)
      if field_id in seen:
        raise ValueError(f"Duplicate field ID: {field_id}")
      seen.add(field_id)
      prompt = field["prompt"]
      if not prompt.strip() or len(prompt) > 500:
        raise ValueError("Each prompt is 1–500 characters")
      if field["type"] == "text":
        continue
      options = field["options"]
      if (
        not 1 <= len(options) <= 20
        or len(set(options)) != len(options)
        or any(not option.strip() or len(option) > 200 for option in options)
      ):
        raise ValueError(
          f"{field['type']} fields take 1–20 unique options of 1–200 characters"
        )
      labels = [custom_label(option) for option in options]
      labels = [label for label in labels if label is not None]
      if len(set(labels)) != len(labels):
        raise ValueError(
          f"{field['type']} fields give each free-text option its own label"
        )

  def submit_report(self, report_id, note_id, answers):
    report = self.report(report_id)
    fields = parse_fields(report["markdown"])[1]
    if not fields:
      raise ValueError("This report has no fields to answer")
    return self.submit(report_id, report["title"], fields, note_id, answers)

  def submit(self, report_id, title, fields, note_id, answers):
    if not isinstance(answers, dict):
      raise TypeError("Answers is a JSON object keyed by field ID")
    known = {field["id"] for field in fields}
    unknown = set(answers) - known
    if unknown:
      raise ValueError(f"Unknown field IDs: {', '.join(sorted(unknown))}")
    lines = [f"REPORT {report_id} {title}:"]
    for field in fields:
      field_id = field["id"]
      value = answers.get(field_id)
      if field["type"] == "text":
        if value is None:
          rendered = "(skipped)"
        elif not isinstance(value, str) or len(value) > 2000:
          raise ValueError(f"{field_id}: text answers are 1–2000 characters")
        else:
          rendered = value if value.strip() else "(skipped)"
      elif value is None:
        rendered = "(skipped)"
      elif field["type"] == "choice":
        if value not in field["options"] and not custom_answer(field, value):
          raise ValueError(f"{field_id}: choose one of " + ", ".join(field["options"]))
        rendered = value
      else:
        if (
          not isinstance(value, list)
          or len({item for item in value if isinstance(item, str)}) != len(value)
          or any(
            item not in field["options"] and not custom_answer(field, item)
            for item in value
          )
        ):
          raise ValueError(
            f"{field_id}: pick options only: " + ", ".join(field["options"])
          )
        rendered = ", ".join(value) if value else "(skipped)"
      lines.append(f"  {field_id}: {rendered}")
    return self.submission(note_id, report_id, "\n".join(lines))


def open_link(renderer, tokens, index, options, env):
  token = tokens[index]
  href = token.attrGet("href") or ""
  if href and not href.startswith("#"):
    token.attrSet("target", "_blank")
    token.attrSet("rel", "noopener noreferrer")
  return renderer.renderToken(tokens, index, options, env)


def require_renderer():
  if not HAS_RENDERER:
    raise SystemExit(
      "serve needs markdown-it-py: install it into the preview venv with "
      "`python -m pip install markdown-it-py`, then start the server with that "
      "venv's Python. read, ack and publish work without it."
    )


CODE_BLOCK = re.compile(r"<pre>(.*?)</pre>", re.DOTALL)
CODE_TAG = re.compile(r"<[^>]+>")


def add_copy_buttons(rendered):
  """Give every code block a copy button.

  The button carries the code in `data-code`, because rendered HTML is assigned with
  `innerHTML` and so cannot hold a listener of its own; the client copies from the attribute.
  Newlines become `&#10;` to survive attribute parsing unchanged.
  """

  def replace(match):
    inner = match.group(1)
    code = html.unescape(CODE_TAG.sub("", inner))
    payload = html.escape(code, quote=True).replace("\n", "&#10;")
    button = (
      f'<button type="button" class="copy-code" aria-label="Copy code" title="Copy code" '
      f'data-code="{payload}">⧉</button>'
    )
    return f'<div class="code-block">{button}<pre>{inner}</pre></div>'

  return CODE_BLOCK.sub(replace, rendered)


ESCAPED_FENCE = re.compile(
  r"^(?P<indent>[ \t]*)\\(?P<fence>(?:`{3,}|~{3,}))", re.MULTILINE
)


def unescape_fences(source):
  """Give a fence back the backslash that hid it.

  A backslash before a line-leading fence makes markdown-it read a literal ``` inside a
  paragraph, so the block never reaches the rule that carries the code background. The owner
  reported exactly that (note 850de5a1): the fence was meant as a block, and the marker is
  unescaped here so it opens one. A tilde fence is a fence too, so the run takes either marker. An escape anywhere else is left alone, because inline
  backticks are the other thing an escape can mean.
  """
  return ESCAPED_FENCE.sub(
    lambda match: match.group("indent") + match.group("fence"), source
  )


PARAGRAPH = re.compile(r"<p>.*?</p>", re.DOTALL)
# Only the tag goes: the newline beside it stays, so a pre-wrap paragraph keeps its line break
PARAGRAPH_BREAK = re.compile(r"<br\s*/?>")


def drop_paragraph_breaks(rendered):
  """Take the `<br>` out of a paragraph, on the owner's suggestion in note 0d1d1123.

  With breaks on, markdown-it turns each newline into a `<br>` and the owner found the result too
  airy next to the message log, where a line breaks through `white-space: pre-wrap` and needs no
  tag. A paragraph now keeps its source newlines and no break; a `<br>` inside any other element,
  a list item for one, stays as it was.
  """
  return PARAGRAPH.sub(lambda match: PARAGRAPH_BREAK.sub("", match.group(0)), rendered)


def render(markdown, breaks=False):
  try:
    from markdown_it import MarkdownIt
  except ImportError as error:
    raise RuntimeError(
      "Markdown rendering needs markdown-it-py. Install it in the preview's venv "
      "and restart the server with that venv's Python; steering still works."
    ) from error
  parser = MarkdownIt("commonmark", {"html": False, "breaks": breaks}).enable(
    ["table", "strikethrough"]
  )
  parser.add_render_rule("link_open", open_link)
  rendered = drop_paragraph_breaks(parser.render(unescape_fences(markdown)))
  return add_copy_buttons(rendered)


def handler(store):
  token = secrets.token_urlsafe(32)

  class Handler(BaseHTTPRequestHandler):
    def setup(self):
      super().setup()
      self.connection.settimeout(15)

    def reply(
      self, status, body, content_type="application/json; charset=utf-8", filename=None
    ):
      # An upload answers with the bytes it stored, so this takes bytes as well as text.
      data = body if isinstance(body, (bytes, bytearray)) else body.encode("utf-8")
      self.send_response(status)
      self.send_header("Content-Type", content_type)
      self.send_header("Content-Length", str(len(data)))
      self.send_header("Cache-Control", "no-store")
      self.send_header("X-Content-Type-Options", "nosniff")
      self.send_header(
        "Content-Security-Policy",
        "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
        "connect-src 'self'; base-uri 'none'; form-action 'self'",
      )
      if filename:
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
      self.end_headers()
      self.wfile.write(data)

    def problem(self, status, error):
      self.reply(status, json.dumps({"error": str(error)}))

    def do_GET(self):
      path = urlsplit(self.path).path
      try:
        if path == "/":
          page = (ASSETS / "index.html").read_text(encoding="utf-8")
          page = page.replace(
            "__STYLE__", (ASSETS / "style.css").read_text(encoding="utf-8")
          )
          page = page.replace(
            "__SCRIPT__", (ASSETS / "app.js").read_text(encoding="utf-8")
          )
          self.reply(200, page.replace("__TOKEN__", token), "text/html; charset=utf-8")
          return
        if path == "/api/state":
          state = store.state()
          # The page keeps its write token fresh from the poll, so a save pressed after a server
          # restart lands without a browser refresh (owner note 2647459f). The token is CSRF
          # resistance rather than authentication, and this page already carries it.
          state["token"] = token
          try:
            for item in state["notes"]:
              # No `breaks`: the log sets `white-space: pre-wrap`, so the newline the source
              # carries is the line break. A `<br>` beside it doubled every gap, which is what
              # the owner saw and removed by hand in the browser (note 0d1d1123).
              item["html"] = render(item["text"])
              if item.get("ack_kind") == "reply" and item.get("ack_text"):
                item["ack_html"] = render(item["ack_text"])
          except RuntimeError as error:
            state["rendering_error"] = str(error)
          self.reply(200, json.dumps(state, ensure_ascii=False))
          return
        upload = re.fullmatch(r"/api/uploads/([a-zA-Z0-9_-]{1,80})", path)
        if upload:
          record = store.upload(upload.group(1))
          if record is None:
            self.problem(404, "No upload with that ID")
            return
          try:
            data = Path(record["path"]).read_bytes()
          except OSError:
            # The record outlives the bytes by design on the owner's answer in report submission
            # c27a4dd5: a restore deletes what is under the state directory, and the tab shows that
            # row as one whose file is gone rather than as an entry that opens nothing.
            self.problem(
              404, "This upload's bytes are gone; the record survived a restore"
            )
            return
          # An attachment with nosniff, so an uploaded page cannot run in this origin.
          self.reply(200, data, record["type"], record["name"])
          return
        match = re.fullmatch(r"/api/reports/([a-zA-Z0-9_-]{1,80})/(html|source)", path)
        if match:
          report_id, kind = match.groups()
          report = store.report(report_id)
          if kind == "html":
            try:
              body, questions = render_report(report["markdown"])
            except ValueError as error:
              # A report stored before publish validated its fields can still be unrenderable.
              # do_GET catches OSError, sqlite3.Error and RuntimeError but not ValueError, so
              # this used to escape the handler and close the connection with no response at
              # all: the browser saw a failed fetch and the tab had nothing to explain it with.
              self.problem(500, f"This report cannot be rendered: {error}")
              return
            self.reply(
              200,
              json.dumps({"html": body, "fields": len(questions)}, ensure_ascii=False),
            )
            return
          self.reply(
            200, report["markdown"], "text/plain; charset=utf-8", f"{report_id}.md"
          )
          return
        self.problem(404, "Not found")
      except FileNotFoundError as error:
        self.problem(404, error)
      except (OSError, sqlite3.Error, RuntimeError) as error:
        self.problem(503, error)

    def do_POST(self):
      path = urlsplit(self.path).path
      report_submit = re.fullmatch(r"/api/reports/([a-zA-Z0-9_-]{1,80})/submit", path)
      report_seen = re.fullmatch(r"/api/reports/([a-zA-Z0-9_-]{1,80})/seen", path)
      save_state = path == "/api/save-state"
      upload_post = path == "/api/uploads"
      if (
        path not in {"/api/notes", "/api/markdown"}
        and not report_submit
        and not report_seen
        and not save_state
        and not upload_post
      ):
        self.problem(404, "Not found")
        return
      supplied = self.headers.get("X-Preview-Token", "").encode("utf-8")
      if not secrets.compare_digest(supplied, token.encode("ascii")):
        self.problem(403, "Reload the preview, then retry; your draft is kept")
        return
      # An upload carries the file itself, so its content type is the browser's and any type is legal;
      # every other route takes a JSON object.
      if self.headers.get("Content-Type") != "application/json" and not upload_post:
        self.problem(415, "Expected application/json")
        return
      try:
        length = int(self.headers.get("Content-Length", "0"))
        limit = (
          MAX_UPLOAD
          if upload_post
          else MAX_BODY
          if not (report_submit or save_state)
          else MAX_SUBMISSION_BODY
        )
        if not 0 < length <= limit:
          subject = (
            "An upload is"
            if upload_post
            else "Report answers are"
            if report_submit
            else "Note body is"
          )
          # The refusal has to reach the client. Answering before the body is read is what keeps a
          # wide body from being buffered, but a client still writing into a socket this side is
          # about to close sees a broken pipe instead of the answer, which is how this test failed
          # once in a way that looked like flakiness. Discarding what it sends, in bounded chunks
          # that are never kept or parsed, delivers the refusal and costs nothing.
          bound = MAX_UPLOAD + 1 if upload_post else MAX_SUBMISSION_BODY + 1
          remaining = length if 0 < length <= bound else 0
          while remaining > 0:
            chunk = self.rfile.read(min(65536, remaining))
            if not chunk:
              break
            remaining -= len(chunk)
          self.problem(413, f"{subject} empty or too large")
          return
        data = self.rfile.read(length)
        if upload_post:
          # The file name rides the query string because the body is the file itself. The bytes are
          # stored exactly as they arrived, and the record carries the type, size and hash.
          name = parse_qs(urlsplit(self.path).query).get("name", [""])[0]
          record = store.save_upload(name, self.headers.get("Content-Type", ""), data)
          self.reply(201, json.dumps(record, ensure_ascii=False))
          return
        payload = json.loads(data)
        if not isinstance(payload, dict):
          self.problem(400, "Expected a JSON object")
          return
        if path == "/api/markdown":
          self.reply(
            200,
            render(note_text(payload.get("text")), breaks=True),
            "text/html; charset=utf-8",
          )
          return
        if save_state:
          self.reply(200, json.dumps(store.save_state(payload), ensure_ascii=False))
          return
        if report_seen:
          report = store.mark_report_seen(report_seen.group(1))
          self.reply(200, json.dumps(report, ensure_ascii=False))
          return
        if report_submit:
          note = store.submit_report(
            report_submit.group(1), payload.get("id"), payload.get("answers")
          )
          self.reply(201, json.dumps(note, ensure_ascii=False))
          return
        note = store.note(payload.get("id"), payload.get("text"))
        self.reply(201, json.dumps(note, ensure_ascii=False))
      except FileNotFoundError as error:
        self.problem(404, error)
      except (ValueError, TypeError, UnicodeDecodeError) as error:
        self.problem(400, error)
      except (OSError, sqlite3.Error, RuntimeError) as error:
        self.problem(503, error)

  return Handler


def main():
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("--state-dir", default="reports/arena-preview")
  parser.add_argument(
    "--save-path",
    default=SAVED_STATE,
    help="Where the save button writes its file; untracked, and at the repository root by default",
  )
  parser.add_argument(
    "--pretty",
    action="store_true",
    help="Indent the JSON this CLI prints; agent-facing output is minified by default",
  )
  commands = parser.add_subparsers(dest="command", required=True)
  serve = commands.add_parser("serve")
  serve.add_argument(
    "--port", type=int, default=8000, help="Port to bind (default: 8000)"
  )
  commands.add_parser("init")
  commands.add_parser("read")
  ack = commands.add_parser("ack")
  ack.add_argument("ids", nargs="+")
  ack.add_argument("--reply", help="Markdown answer shown in the message log")
  ack.add_argument("--note", help="Short plain answer shown in the message log")
  publish = commands.add_parser("publish")
  publish.add_argument("source", type=Path)
  publish.add_argument("--id", required=True)
  publish.add_argument("--title", required=True)
  task = commands.add_parser("task")
  task.add_argument("id_arg", nargs="?", metavar="TASK-ID")
  task.add_argument("title_arg", nargs="?", metavar="TASK-TITLE")
  task.add_argument("detail_arg", nargs="*", metavar="TASK-DETAIL")
  task.add_argument("--task-id", help="The ID the first positional takes")
  task.add_argument("--task-title", help="The title the second positional takes")
  task.add_argument(
    "--task-details",
    action="append",
    help="One detail line, repeatable; an empty string clears the list",
  )
  task.add_argument(
    "--msg-id",
    help="Message this task answers; marks that message as having a task",
  )
  task.add_argument(
    "--amend",
    metavar="PREV-ID",
    help="Rename the task stored under this ID to the one given",
  )
  task.add_argument("--status", choices=TASK_STATUSES, default=None)
  task.add_argument(
    "--order", type=int, default=None, help="1-based place in its div, not the end"
  )
  task_remove = commands.add_parser("task-remove")
  task_remove.add_argument("task_id")
  commands.add_parser("task-list")
  task_import = commands.add_parser("task-import")
  task_import.add_argument(
    "source",
    nargs="?",
    type=Path,
    help="JSON array or one task per line; stdin if omitted",
  )
  task_import.add_argument(
    "--replace", action="store_true", help="Clear the stored list before importing"
  )
  legacy = commands.add_parser("import-notes")
  legacy.add_argument("source", type=Path)
  args = parser.parse_args()
  try:
    store = Store(
      args.state_dir, create=args.command in {"serve", "init"}, save_path=args.save_path
    )
    if args.command == "serve":
      require_renderer()
      with ThreadingHTTPServer(("0.0.0.0", args.port), handler(store)) as server:
        print(
          f"Preview listening on 0.0.0.0:{server.server_port}; state: {store.path}",
          flush=True,
        )
        server.serve_forever()
    elif args.command == "read":
      print(cli_json(store.read(), args.pretty))
    elif args.command == "ack":
      if bool(args.reply) == bool(args.note):
        raise ValueError("Choose exactly one of --reply or --note")
      kind = "reply" if args.reply else "note"
      store.acknowledge(args.ids, kind, args.reply or args.note)
      print("Acknowledged: " + ", ".join(args.ids))
    elif args.command == "publish":
      store.publish(args.id, args.title, args.source)
      print(f"Published {args.id}; select it in the Reports tab")
    elif args.command == "task":
      task_id = args.task_id or args.id_arg
      if not task_id:
        raise ValueError("A task needs an ID")
      details = args.task_details
      if details is None and args.detail_arg:
        details = args.detail_arg
      if args.amend:
        store.amend_task(args.amend, task_id)
      if args.msg_id:
        # One transaction: a message ID that matches nothing takes the task with it, rather than
        # leaving a task whose marker never landed.
        with store.transaction() as shared:
          record = store.write_task(
            task_id,
            args.task_title or args.title_arg,
            details,
            args.status,
            args.order,
            shared=shared,
          )
          store.mark_task(args.msg_id, task_id, shared=shared)
      else:
        record = store.write_task(
          task_id,
          args.task_title or args.title_arg,
          details,
          args.status,
          args.order,
        )
      before, after = store.neighbours(task_id)
      echo = echo_task(record, before, after)
      if args.msg_id:
        echo["msg_id"] = args.msg_id
      print(cli_json(echo, args.pretty))
    elif args.command == "task-remove":
      print(cli_json(echo_task(store.remove_task(args.task_id)), args.pretty))
    elif args.command == "task-list":
      print(cli_json(store.list_tasks(), args.pretty))
    elif args.command == "task-import":
      text = (
        args.source.read_text(encoding="utf-8") if args.source else sys.stdin.read()
      )
      written = store.import_tasks(
        [
          record
          for record in parse_task_import(text)
          # The same file the log writes carries notes as well; a task line has a title, and a note
          # line is skipped here the way a task line is skipped by the importer above.
          if not (
            isinstance(record, dict) and "text" in record and "title" not in record
          )
        ],
        args.replace,
      )
      print(
        cli_json(
          {
            "imported": len(written),
            "replaced": args.replace,
            "ids": [item["id"] for item in written],
          },
          args.pretty,
        )
      )
    elif args.command == "import-notes":
      saved = [
        json.loads(line)
        for line in args.source.read_text(encoding="utf-8").splitlines()
        if line.strip()
      ]
      # A save file holds three kinds of line, and one reader takes two of them. A task carries a
      # title and no text; a note carries text and no report ID; the owner's report answers carry
      # a report ID. Each line is then validated by the writer it belongs to, so a restore cannot
      # store a shape the preview itself would refuse.
      answers = [
        record for record in saved if isinstance(record, dict) and "report_id" in record
      ]
      records = [
        record
        for record in saved
        if not (
          isinstance(record, dict)
          and (("title" in record and "text" not in record) or "report_id" in record)
        )
      ]
      for record in answers:
        store.submission(
          record["id"],
          record["report_id"],
          record["text"],
          record.get("at"),
          acknowledged_at=record.get("acknowledged_at"),
          ack_kind=record.get("ack_kind"),
          ack_text=record.get("ack_text"),
          seen_at=record.get("seen_at"),
          task_id=record.get("task_id"),
        )
      for record in records:
        store.note(
          record["id"],
          record["text"],
          record.get("at"),
          origin=record.get("origin"),
          acknowledged_at=record.get("acknowledged_at"),
          ack_kind=record.get("ack_kind"),
          ack_text=record.get("ack_text"),
          seen_at=record.get("seen_at"),
          task_id=record.get("task_id"),
        )
      receipts = sum(1 for record in records if record.get("acknowledged_at"))
      print(
        f"Imported {len(records)} notes, {receipts} with a receipt restored verbatim,"
        f" {len(answers)} report answers;"
        " existing IDs are not duplicated and keep the receipt they have"
      )
  except (
    OSError,
    ValueError,
    TypeError,
    KeyError,
    sqlite3.Error,
    RuntimeError,
  ) as error:
    print(f"Preview error: {error}", file=sys.stderr)
    return 1
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
