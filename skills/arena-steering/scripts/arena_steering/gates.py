"""Read named run state for task blocking."""

from __future__ import annotations

import json
from pathlib import Path


class FileGateStatus:
  """Use the run record and exit marker in the state directory."""

  def __init__(self, state_dir: str | Path) -> None:
    self._runs = Path(state_dir) / "runs"

  def is_running(self, name: str) -> bool:
    record_path = self._runs / f"{name}.json"
    if not record_path.is_file():
      return False
    record = json.loads(record_path.read_text(encoding="utf-8"))
    return not Path(record["exit_path"]).is_file()
