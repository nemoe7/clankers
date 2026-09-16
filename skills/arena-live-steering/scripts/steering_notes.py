"""Note handling shared by the arena-live-steering transports.

Every transport appends attributed notes to one file, under one header, with
one tail cap, and reports the same directives, so the agent side never has to
know which channel delivered a note. Import this from a script in the same
directory; the script directory is already on `sys.path` when Python runs a
file directly.
"""

from __future__ import annotations

import hashlib
import pathlib
from datetime import datetime, timezone

NOTES_HEADER = "# LIVE STEERING NOTES\n\n## Current Notes:\n"
MAX_NOTES_CHARS = 8000
DIRECTIVES = ("STOP:", "PRIORITY:", "CONTEXT:")


def digest(text: str) -> str:
  """Return a short stable digest of `text`, for change detection."""
  return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


def read_notes(path: pathlib.Path) -> str:
  """Return the notes a transport wrote, or an empty string."""
  try:
    return path.read_text(encoding="utf-8")
  except OSError:
    return ""


def append_note(path: pathlib.Path, stamp: str, body: str) -> None:
  """Append one note under `## Current Notes:`, keeping the tail of the file.

  `stamp` is the attribution comment and `body` the note text. The head of the
  notes section is stripped on every append: `NOTES_HEADER` ends in a newline,
  which the split returns, so leaving it in place adds one blank line above the
  first note per append.
  """
  existing = read_notes(path)

  if "## Current Notes:" not in existing:
    existing = NOTES_HEADER

  notes = existing.split("## Current Notes:", 1)[1].lstrip("\n")
  notes += stamp.lstrip("\n") + body + "\n"
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_text(NOTES_HEADER + "\n" + notes[-MAX_NOTES_CHARS:], encoding="utf-8")


def append_log(path: pathlib.Path, stamp: str, body: str) -> None:
  """Append one entry to the append-only log, which the notes cap discards."""
  try:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as log:
      log.write(f"\n\n{stamp}\n{body}\n")
  except OSError as error:
    print(f"Could not write {path}: {error}", flush=True)


def added_lines(previous: str, current: str) -> str:
  """Return the lines of `current` after its shared line prefix with `previous`.

  Appending a line, replacing the whole text, and rewriting the middle all
  deliver the new tail, while deleting lines delivers nothing.
  """
  old = previous.splitlines()
  new = current.splitlines()
  index = 0

  while index < len(old) and index < len(new) and old[index] == new[index]:
    index += 1

  return "\n".join(new[index:]).strip()


def deliver(
  text: str,
  note_source: str,
  log_source: str,
  steering_file: pathlib.Path,
  log_file: pathlib.Path,
) -> None:
  """Write one note to both files and echo it with any directive it carries."""
  read_at = f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}"
  append_note(steering_file, f"\n<!-- from {note_source}, read {read_at} -->\n", text)
  append_log(log_file, f"--- {read_at} [{log_source}] ---", text)

  print(f"\nSteering from {note_source}", flush=True)
  print(text[:2000], flush=True)
  print("-" * 60, flush=True)

  upper = text.upper()

  for directive in DIRECTIVES:
    if directive in upper:
      print(f">> {directive} the agent must act on this note", flush=True)
