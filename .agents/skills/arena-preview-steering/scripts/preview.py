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

ASSETS = Path(__file__).resolve().parents[1] / "assets"
IDENTIFIER = re.compile(r"[a-zA-Z0-9_-]{1,80}\Z")
MAX_REPORT = 2_000_000


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


class Store:
  def __init__(self, directory, create=False):
    directory = Path(directory).resolve()
    self.path = directory / "state.sqlite3"
    if not create and not self.path.is_file():
      raise FileNotFoundError(f"Inbox missing: {self.path}; start the preview first")
    if create:
      directory.mkdir(parents=True, exist_ok=True, mode=0o700)
      with closing(self.connect()) as db, db:
        db.executescript("""
          CREATE TABLE IF NOT EXISTS notes (
            seq INTEGER PRIMARY KEY, id TEXT UNIQUE NOT NULL,
            text TEXT NOT NULL, at TEXT NOT NULL, acknowledged_at TEXT
          );
          CREATE TABLE IF NOT EXISTS reports (
            id TEXT PRIMARY KEY, title TEXT NOT NULL,
            markdown TEXT NOT NULL, updated_at TEXT NOT NULL
          );
          CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        """)
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

  def state(self):
    with closing(self.connect()) as db:
      return {
        "notes": [dict(row) for row in db.execute("SELECT * FROM notes ORDER BY seq")],
        "reports": [
          dict(row)
          for row in db.execute(
            "SELECT id, title, updated_at FROM reports ORDER BY title, id"
          )
        ],
        "last_check": dict(db.execute("SELECT key, value FROM meta")).get("last_check"),
      }

  def read(self):
    with closing(self.connect()) as db, db:
      pending = [
        dict(row)
        for row in db.execute(
          "SELECT * FROM notes WHERE acknowledged_at IS NULL ORDER BY seq"
        )
      ]
      checked = now()
      db.execute("INSERT OR REPLACE INTO meta VALUES ('last_check', ?)", (checked,))
      return {"checked_at": checked, "pending": pending}

  def acknowledge(self, ids):
    with closing(self.connect()) as db, db:
      for note_id in ids:
        cursor = db.execute(
          "UPDATE notes SET acknowledged_at = COALESCE(acknowledged_at, ?) WHERE id = ?",
          (now(), identifier(note_id)),
        )
        if not cursor.rowcount:
          raise ValueError(f"Unknown note: {note_id}; no receipts written")

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
      db.execute(
        "INSERT OR REPLACE INTO reports VALUES (?, ?, ?, ?)",
        (report_id, title, text, now()),
      )

  def report(self, report_id):
    identifier(report_id)
    with closing(self.connect()) as db:
      row = db.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
      if row is None:
        raise FileNotFoundError("Report not found")
      return dict(row)


def open_link(renderer, tokens, index, options, env):
  token = tokens[index]
  href = token.attrGet("href") or ""
  if href and not href.startswith("#"):
    token.attrSet("target", "_blank")
    token.attrSet("rel", "noopener noreferrer")
  return renderer.renderToken(tokens, index, options, env)


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


def export(report):
  style = (ASSETS / "style.css").read_text(encoding="utf-8")
  return (
    '<!doctype html><html lang="en" data-theme="dark"><head><meta charset="utf-8">'
    '<meta name="viewport" content="width=device-width, initial-scale=1">'
    '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; '
    "style-src 'unsafe-inline'; script-src 'unsafe-inline'; base-uri 'none'\">"
    f"<title>{html.escape(report['title'])}</title><style>{style}</style></head>"
    '<body><main class="export"><button type="button" onclick="'
    "document.documentElement.dataset.theme = document.documentElement.dataset.theme "
    "=== 'dark' ? 'light' : 'dark'\">Toggle dark / light</button><article class=\"report\">"
    f"{render(report['markdown'])}</article></main></body></html>"
  )


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
          except RuntimeError as error:
            state["rendering_error"] = str(error)
          self.reply(200, json.dumps(state, ensure_ascii=False))
          return
        match = re.fullmatch(
          r"/api/reports/([a-zA-Z0-9_-]{1,80})/(html|source|export)", path
        )
        if match:
          report_id, kind = match.groups()
          report = store.report(report_id)
          if kind == "source":
            self.reply(
              200, report["markdown"], "text/plain; charset=utf-8", f"{report_id}.md"
            )
          elif kind == "export":
            self.reply(
              200, export(report), "text/html; charset=utf-8", f"{report_id}.html"
            )
          else:
            self.reply(200, render(report["markdown"]), "text/html; charset=utf-8")
          return
        self.problem(404, "Not found")
      except FileNotFoundError as error:
        self.problem(404, error)
      except (OSError, sqlite3.Error, RuntimeError) as error:
        self.problem(503, error)

    def do_POST(self):
      path = urlsplit(self.path).path
      if path not in {"/api/notes", "/api/markdown"}:
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
        note = store.note(payload.get("id"), payload.get("text"))
        self.reply(201, json.dumps(note, ensure_ascii=False))
      except (ValueError, UnicodeDecodeError) as error:
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
  publish = commands.add_parser("publish")
  publish.add_argument("source", type=Path)
  publish.add_argument("--id", required=True)
  publish.add_argument("--title", required=True)
  download = commands.add_parser("export")
  download.add_argument("id")
  download.add_argument("destination", type=Path)
  legacy = commands.add_parser("import-notes")
  legacy.add_argument("source", type=Path)
  args = parser.parse_args()
  try:
    store = Store(args.state_dir, create=args.command in {"serve", "init"})
    if args.command == "serve":
      with ThreadingHTTPServer(("0.0.0.0", args.port), handler(store)) as server:
        print(
          f"Preview listening on 0.0.0.0:{server.server_port}; state: {store.path}",
          flush=True,
        )
        server.serve_forever()
    elif args.command == "read":
      print(json.dumps(store.read(), ensure_ascii=False, indent=2))
    elif args.command == "ack":
      store.acknowledge(args.ids)
      print("Acknowledged: " + ", ".join(args.ids))
    elif args.command == "publish":
      store.publish(args.id, args.title, args.source)
      print(f"Published {args.id}; select it in the Reports tab")
    elif args.command == "export":
      output = export(store.report(args.id))
      args.destination.write_text(output, encoding="utf-8")
      print(f"Exported {args.destination}")
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
  except (OSError, ValueError, KeyError, sqlite3.Error, RuntimeError) as error:
    print(f"Preview error: {error}", file=sys.stderr)
    return 1
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
