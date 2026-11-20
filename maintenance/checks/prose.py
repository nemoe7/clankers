"""The `nemoize` stage: run the root prose linter. Exclusions live in `nemoizer.toml`."""

from __future__ import annotations

import os
import subprocess
import sys

from .repo import Repo
from .report import LOG

NEMOIZE = "skills/nemoizer/scripts/nemoize.py"
# Windows consoles default to cp1252. UTF-8 mode makes every Python child
# emit UTF-8, so `encoding="utf-8"` readers never lose characters.
CHILD_ENV = {**os.environ, "PYTHONUTF8": "1"}


def check_nemoize(repo: Repo, errors: list[str]) -> None:
  result = subprocess.run(
    [sys.executable, str(repo.root / NEMOIZE), "."],
    cwd=repo.root,
    capture_output=True,
    text=True,
    encoding="utf-8",
    errors="replace",
    env=CHILD_ENV,
    check=False,
  )
  output = (result.stdout + result.stderr).strip()
  if result.returncode:
    errors.append(f"nemoize failed:\n{output}")
  elif output:
    LOG.info(output)
