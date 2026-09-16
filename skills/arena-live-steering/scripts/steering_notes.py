"""Note writing shared by the arena-live-steering transports.

Every transport appends attributed notes to one file, under one header, with
one tail cap, so the agent side never has to know which channel delivered a
note. Import this from a script in the same directory; the script directory is
already on `sys.path` when Python runs a file directly.
"""

from __future__ import annotations

import pathlib

NOTES_HEADER = "# LIVE STEERING NOTES\n\n## Current Notes:\n"
MAX_NOTES_CHARS = 8000


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
      log.write(f"\n\n{stamp}{body}\n")
  except OSError as error:
    print(f"Could not write {path}: {error}", flush=True)
