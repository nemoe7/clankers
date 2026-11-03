"""Keep a live, deduplicated report of Bash gate observations in v2 state."""

from __future__ import annotations

import fcntl
import json
import re
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from .services import ReportService
from .store import SqliteStore

REPORT_TITLE = "Bash gate observations"
REPORT_ID = re.sub(r"[^a-z0-9]+", "-", REPORT_TITLE.lower()).strip("-")
SOURCE_NAME = f"{REPORT_ID}.md"
EVENTS_NAME = f"{REPORT_ID}.jsonl"
_HEADER = (
  "# Bash gate observations\n\n"
  "Each row is the first observed verdict for one full Bash line. "
  "Counted means eligible for the pending-inbox six-call budget. "
  "Blocked is this hook's actual verdict, not an outer tool-layer block. "
  "Repeated lines keep their first pair. "
  "Older calls and blocks that never reach this hook cannot be reconstructed.\n\n"
  "| command | counted | blocked |\n"
  "| --- | --- | --- |\n"
)


def _command_cell(command: str) -> str:
  """Represent the full line in a Markdown code span without splitting its row."""
  longest = max(
    (len(match.group()) for match in re.finditer(r"`+", command)), default=0
  )
  fence = "`" * max(1, longest + 1)
  escaped = command.replace("|", r"\|").replace("\r", r"\r").replace("\n", r"\n")
  return f"{fence} {escaped} {fence}"


def _report_body(rows: list[dict[str, object]]) -> str:
  return _HEADER + "".join(
    f"| {_command_cell(str(row['command']))} | "
    f"{'yes' if row['counted'] else 'no'} | "
    f"{'yes' if row['blocked'] else 'no'} |\n"
    for row in rows
  )


def record(
  state_dir: Path,
  store: SqliteStore,
  reports: ReportService,
  *,
  command: str,
  counted: bool,
  blocked: bool,
) -> None:
  """Append only unseen full lines, then publish their current table atomically.

  The file lock spans reading, deduplicating, and saving across separate hook
  processes. The JSONL file keeps the unredacted input even when Markdown needs
  escaped table delimiters. It stays under the ignored state directory.
  """
  if not command:
    return
  directory = state_dir / "reports"
  directory.mkdir(parents=True, exist_ok=True)
  events_file = directory / EVENTS_NAME
  source_file = directory / SOURCE_NAME
  with (state_dir / "bash-probe.lock").open("a+", encoding="utf-8") as lock:
    fcntl.flock(lock, fcntl.LOCK_EX)
    rows = (
      [
        json.loads(line)
        for line in events_file.read_text(encoding="utf-8").splitlines()
      ]
      if events_file.exists()
      else []
    )
    if not any(row["command"] == command for row in rows):
      rows.append(
        {
          "command": command,
          "counted": counted,
          "blocked": blocked,
          "first_seen": datetime.now(UTC).isoformat(),
        }
      )
      events_file.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
      )
    body = _report_body(rows)
    existing = store.get_report(REPORT_ID)
    if (
      existing is not None and existing.body == body and existing.status == "published"
    ):
      if not source_file.exists():
        source_file.write_text(body, encoding="utf-8")
      return
    source_file.write_text(body, encoding="utf-8")
    if existing is None:
      reports.publish_report(
        REPORT_ID, REPORT_TITLE, body, source_file=str(source_file)
      )
    else:
      now = datetime.now(UTC).isoformat()
      store.save_report(
        replace(
          existing,
          body=body,
          status="published",
          seen=False,
          modified_at=now,
          updated_at=now,
          source_file=str(source_file),
        )
      )
