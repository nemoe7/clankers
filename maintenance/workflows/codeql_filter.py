"""Select CodeQL languages conservatively from changes against the event base."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import PurePosixPath

LANGUAGES = {"python", "javascript", "actions"}
JS_EXTENSIONS = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".html", ".vue"}


def languages_for(paths: list[str]) -> set[str]:
  """Unknown inputs trigger all analyses. Shared configuration always selects every analysis."""
  selected: set[str] = set()
  for path in paths:
    name = PurePosixPath(path)
    if path.startswith((".github/", "maintenance/workflows/")):
      return LANGUAGES.copy()
    if name.suffix in {".py", ".pyi"}:
      selected.add("python")
    elif name.suffix in JS_EXTENSIONS:
      selected.add("javascript")
    else:
      # Manifests, build scripts, extensions not explicitly understood, and
      # even documentation may influence extraction or configuration.
      return LANGUAGES.copy()
  return selected


def main() -> None:
  for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
      stream.reconfigure(encoding="utf-8", errors="replace")
  event = os.environ.get("EVENT_NAME", "")
  base = (
    os.environ.get("PR_BASE_SHA", "")
    if event == "pull_request"
    else os.environ.get("PUSH_BEFORE", "")
  )
  selected = LANGUAGES.copy()
  if event in {"push", "pull_request"} and base and base.strip("0"):
    try:
      result = subprocess.run(
        ["git", "diff", "--no-renames", "--name-only", "-z", base, "HEAD"],
        check=True,
        capture_output=True,
      )
      selected = languages_for(os.fsdecode(result.stdout).strip("\0").split("\0"))
    except (OSError, subprocess.CalledProcessError):
      pass  # Missing history is not evidence that an analysis is unnecessary.
  output = os.environ["GITHUB_OUTPUT"]
  with open(output, "a", encoding="utf-8") as stream:
    stream.write(
      f"run={'true' if os.environ.get('LANGUAGE') in selected else 'false'}\n"
    )


if __name__ == "__main__":
  main()
