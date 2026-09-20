"""Shared preview runtime. Steering uses only Python's standard library."""

import argparse
import html
import json
import re
import secrets
import sqlite3
import sys
from contextlib import closing
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

try:
  import markdown_it  # noqa: F401

  HAS_RENDERER = True
except ImportError:
  HAS_RENDERER = False

ASSETS = Path(__file__).resolve().parents[1] / "assets"
IDENTIFIER = re.compile(r"[a-zA-Z0-9_-]{1,80}\Z")
MAX_REPORT = 2_000_000
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
    group += (
      f'<label class="option"><input type="{control}" name="{name}" '
      f'value="{value}"{checked}> {html.escape(option)}</label>'
    )
  return f"{body}{group}</div></div>"


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
  def __init__(self, directory, create=False):
    directory = Path(directory).resolve()
    self.path = directory / "state.sqlite3"
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
          ack_kind TEXT, ack_text TEXT
        );
        CREATE TABLE IF NOT EXISTS reports (
          id TEXT PRIMARY KEY, title TEXT NOT NULL,
          markdown TEXT NOT NULL, updated_at TEXT NOT NULL, seq INTEGER
        );
        CREATE TABLE IF NOT EXISTS submissions (
          seq INTEGER PRIMARY KEY, id TEXT UNIQUE NOT NULL,
          report_id TEXT NOT NULL, text TEXT NOT NULL, at TEXT NOT NULL,
          acknowledged_at TEXT, ack_kind TEXT, ack_text TEXT
        );
        CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
      """)
      columns = {row["name"] for row in db.execute("PRAGMA table_info(notes)")}
      for column in ("ack_kind", "ack_text"):
        if column not in columns:
          db.execute(f"ALTER TABLE notes ADD COLUMN {column} TEXT")
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

  def note(self, note_id, text, at=None):
    identifier(note_id)
    note_text(text)
    with closing(self.connect()) as db, db:
      db.execute("BEGIN IMMEDIATE")
      existing = db.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
      if existing:
        if existing["text"] != text:
          raise ValueError("This message ID already belongs to different text")
        return dict(existing)
      db.execute(
        "INSERT INTO notes (id, text, at) VALUES (?, ?, ?)",
        (note_id, text, at or now()),
      )
      return dict(db.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone())

  def submission(self, submission_id, report_id, text, at=None):
    """Record report answers apart from user messages; the log never shows them."""
    identifier(submission_id)
    identifier(report_id)
    note_text(text)
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
        "INSERT INTO submissions (id, report_id, text, at) VALUES (?, ?, ?, ?)",
        (submission_id, report_id, text, at or now()),
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
    with closing(self.connect()) as db:
      return {
        "notes": [dict(row) for row in db.execute("SELECT * FROM notes ORDER BY seq")],
        "reports": [
          dict(row)
          for row in db.execute(
            "SELECT id, title, updated_at, seq FROM reports ORDER BY seq, id"
          )
        ],
        "last_check": dict(db.execute("SELECT key, value FROM meta")).get("last_check"),
      }

  def read(self):
    with closing(self.connect()) as db, db:
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
               ack_kind = COALESCE(?, ack_kind), ack_text = COALESCE(?, ack_text)
               WHERE id = ?""",
            (stamp, kind, text, record_id),
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
    with closing(self.connect()) as db, db:
      highest = db.execute("SELECT COALESCE(MAX(seq), 0) FROM reports").fetchone()[0]
      db.execute(
        """INSERT INTO reports (id, title, markdown, updated_at, seq)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(id) DO UPDATE SET title = excluded.title,
             markdown = excluded.markdown, updated_at = excluded.updated_at,
             seq = COALESCE(reports.seq, excluded.seq)""",
        (report_id, title, text, now(), highest + 1),
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
        if value not in field["options"]:
          raise ValueError(f"{field_id}: choose one of " + ", ".join(field["options"]))
        rendered = value
      else:
        if (
          not isinstance(value, list)
          or len({item for item in value if isinstance(item, str)}) != len(value)
          or any(item not in field["options"] for item in value)
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


def render(markdown):
  try:
    from markdown_it import MarkdownIt
  except ImportError as error:
    raise RuntimeError(
      "Markdown rendering needs markdown-it-py. Install it in the preview's venv "
      "and restart the server with that venv's Python; steering still works."
    ) from error
  parser = MarkdownIt("commonmark", {"html": False}).enable("table")
  parser.add_render_rule("link_open", open_link)
  return parser.render(markdown)


def handler(store):
  token = secrets.token_urlsafe(32)

  class Handler(BaseHTTPRequestHandler):
    def setup(self):
      super().setup()
      self.connection.settimeout(15)

    def reply(
      self, status, body, content_type="application/json; charset=utf-8", filename=None
    ):
      data = body.encode("utf-8")
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
          try:
            for item in state["notes"]:
              item["html"] = render(item["text"])
              if item.get("ack_kind") == "reply" and item.get("ack_text"):
                item["ack_html"] = render(item["ack_text"])
          except RuntimeError as error:
            state["rendering_error"] = str(error)
          self.reply(200, json.dumps(state, ensure_ascii=False))
          return
        match = re.fullmatch(r"/api/reports/([a-zA-Z0-9_-]{1,80})/(html|source)", path)
        if match:
          report_id, kind = match.groups()
          report = store.report(report_id)
          if kind == "html":
            body, questions = render_report(report["markdown"])
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
      if path not in {"/api/notes", "/api/markdown"} and not report_submit:
        self.problem(404, "Not found")
        return
      supplied = self.headers.get("X-Preview-Token", "").encode("utf-8")
      if not secrets.compare_digest(supplied, token.encode("ascii")):
        self.problem(403, "Reload the preview, then retry; your draft is kept")
        return
      if self.headers.get("Content-Type") != "application/json":
        self.problem(415, "Expected application/json")
        return
      try:
        length = int(self.headers.get("Content-Length", "0"))
        if not 0 < length <= 32768:
          self.problem(413, "Note body is empty or too large")
          return
        payload = json.loads(self.rfile.read(length))
        if not isinstance(payload, dict):
          self.problem(400, "Expected a JSON object")
          return
        if path == "/api/markdown":
          self.reply(
            200, render(note_text(payload.get("text"))), "text/html; charset=utf-8"
          )
          return
        if report_submit:
          note = store.submit_report(
            report_submit.group(1), payload.get("id"), payload.get("answers")
          )
          self.reply(201, json.dumps(note, ensure_ascii=False))
          return
        note = store.note(payload.get("id"), payload.get("text"))
        self.reply(201, json.dumps(note, ensure_ascii=False))
      except (ValueError, TypeError, UnicodeDecodeError) as error:
        self.problem(400, error)
      except (OSError, sqlite3.Error, RuntimeError) as error:
        self.problem(503, error)

  return Handler


def main():
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("--state-dir", default="reports/arena-preview")
  commands = parser.add_subparsers(dest="command", required=True)
  serve = commands.add_parser("serve")
  serve.add_argument("--port", type=int, default=8000)
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
  legacy = commands.add_parser("import-notes")
  legacy.add_argument("source", type=Path)
  args = parser.parse_args()
  try:
    store = Store(args.state_dir, create=args.command in {"serve", "init"})
    if args.command == "serve":
      require_renderer()
      with ThreadingHTTPServer(("0.0.0.0", args.port), handler(store)) as server:
        print(
          f"Preview listening on 0.0.0.0:{server.server_port}; state: {store.path}",
          flush=True,
        )
        server.serve_forever()
    elif args.command == "read":
      print(json.dumps(store.read(), ensure_ascii=False, indent=2))
    elif args.command == "ack":
      if bool(args.reply) == bool(args.note):
        raise ValueError("Choose exactly one of --reply or --note")
      kind = "reply" if args.reply else "note"
      store.acknowledge(args.ids, kind, args.reply or args.note)
      print("Acknowledged: " + ", ".join(args.ids))
    elif args.command == "publish":
      store.publish(args.id, args.title, args.source)
      print(f"Published {args.id}; select it in the Reports tab")
    elif args.command == "import-notes":
      records = [
        json.loads(line)
        for line in args.source.read_text(encoding="utf-8").splitlines()
        if line.strip()
      ]
      for record in records:
        store.note(record["id"], record["text"], record.get("at"))
      print(
        f"Imported {len(records)} notes; existing IDs are not duplicated; receipts unchanged"
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
