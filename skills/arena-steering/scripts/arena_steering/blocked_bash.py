"""Append blocked shell calls to a local, unredacted JSONL audit."""

from __future__ import annotations

import json
import os
import stat
from datetime import UTC, datetime
from pathlib import Path

LOG_NAME = "blocked-bash.jsonl"


def append_blocked_bash(
  state_dir: Path, *, line: str, command: str, blocked_by: str
) -> None:
  """Record the full line and blocked command without altering the guard's verdict."""
  state_dir.mkdir(parents=True, exist_ok=True)
  row = {
    "at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    "line": line,
    "command": command,
    "blocked_by": blocked_by,
  }
  flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0)
  fd = os.open(state_dir / LOG_NAME, flags, 0o600)
  try:
    os.fchmod(fd, 0o600)
    with os.fdopen(fd, "a", encoding="utf-8") as log:
      fd = -1
      log.write(json.dumps(row, ensure_ascii=False) + "\n")
  finally:
    if fd >= 0:
      os.close(fd)


def read_blocked_bash(state_dir: Path) -> list[dict[str, str]]:
  """Read every local audit entry without following links or hiding bad rows."""
  flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_NOFOLLOW", 0)
  try:
    fd = os.open(state_dir / LOG_NAME, flags)
  except FileNotFoundError:
    return []
  except OSError as exc:
    raise RuntimeError("Blocked Bash log is unavailable") from exc
  try:
    if not stat.S_ISREG(os.fstat(fd).st_mode):
      raise RuntimeError("Blocked Bash log is not a regular file")
    with os.fdopen(fd, "r", encoding="utf-8") as log:
      fd = -1
      entries: list[dict[str, str]] = []
      try:
        for number, line in enumerate(log, start=1):
          try:
            entry = json.loads(line)
          except json.JSONDecodeError as exc:
            raise RuntimeError(
              f"Invalid blocked Bash log entry at line {number}"
            ) from exc
          if not isinstance(entry, dict) or any(
            not isinstance(entry.get(field), str)
            for field in ("at", "line", "command", "blocked_by")
          ):
            raise RuntimeError(f"Invalid blocked Bash log entry at line {number}")
          entries.append(entry)
      except UnicodeError as exc:
        raise RuntimeError("Blocked Bash log is not UTF-8") from exc
      return entries
  finally:
    if fd >= 0:
      os.close(fd)


if __name__ == "__main__":
  import sys

  if len(sys.argv) != 4:
    raise SystemExit("Expected state directory, full line, and blocked command")
  append_blocked_bash(
    Path(sys.argv[1]),
    line=sys.argv[2],
    command=sys.argv[3],
    blocked_by="hook-unavailable",
  )
