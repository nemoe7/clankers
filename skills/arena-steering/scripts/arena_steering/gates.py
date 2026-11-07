"""Read named run state for task blocking."""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path


def process_identity(pid: int) -> tuple[str, str, str] | None:
  """Return Linux process state, start time, and boot ID when available."""
  try:
    fields = (
      Path(f"/proc/{pid}/stat").read_text(encoding="utf-8").rsplit(") ", 1)[1].split()
    )
    boot = Path("/proc/sys/kernel/random/boot_id").read_text(encoding="utf-8").strip()
    return fields[0], fields[19], boot
  except (OSError, IndexError):
    return None


def run_is_running(record: dict) -> bool:
  """Mark a missing verdict as failed when its recorded process is dead."""
  exit_path = Path(record["exit_path"])
  if exit_path.is_file():
    return False
  pid = record.get("pid")
  if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
    return True
  try:
    os.kill(pid, 0)
  except ProcessLookupError:
    pass
  except PermissionError:
    return True
  else:
    identity = process_identity(pid)
    recorded = record.get("process_identity")
    if identity is None or (
      identity[0] != "Z" and (not recorded or list(identity[1:]) == recorded)
    ):
      return True
  # Link a fully written marker without replacing a verdict from the runner.
  fd, name = tempfile.mkstemp(prefix=".dead-run-", dir=exit_path.parent)
  try:
    with os.fdopen(fd, "w", encoding="utf-8") as marker:
      marker.write("1\n")
    try:
      os.link(name, exit_path)
    except FileExistsError:
      pass
  finally:
    os.unlink(name)
  return False


class FileGateStatus:
  """Use the run record and exit marker in the state directory."""

  def __init__(self, state_dir: str | Path) -> None:
    self._runs = Path(state_dir) / "runs"

  def is_running(self, name: str) -> bool:
    record_path = self._runs / f"{name}.json"
    if not record_path.is_file():
      return False
    record = json.loads(record_path.read_text(encoding="utf-8"))
    return run_is_running(record)

  def running_names(self) -> tuple[str, ...]:
    """List live named runs without inspecting temporary record files."""
    return tuple(
      path.stem
      for path in sorted(self._runs.glob("*.json"))
      if not path.name.startswith(".") and self.is_running(path.stem)
    )


class RunCompletionWatcher:
  """Watch atomic exit markers created after this poll starts."""

  def __init__(self, state_dir: str | Path) -> None:
    self._runs = Path(state_dir) / "runs"
    self._seen = {path.name for path in self._runs.glob("*.exit")}

  def finished(self) -> list[tuple[str, int]]:
    verdicts: list[tuple[str, int]] = []
    for path in sorted(self._runs.glob("*.exit")):
      if path.name in self._seen or path.is_symlink():
        continue
      code = int(path.read_text(encoding="utf-8").strip())
      self._seen.add(path.name)
      # Strip the generated run ID suffix without changing short legacy names.
      name = re.sub(r"-[0-9a-f]{32}$", "", path.stem)
      verdicts.append((name, code))
    return verdicts
