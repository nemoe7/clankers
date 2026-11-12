"""Shared fixtures and helpers for nemoizer tests."""

import subprocess
import sys
from pathlib import Path

import nemoize

SCRIPT = Path(nemoize.__file__).resolve()
SKIPPED_MESSAGE = "Skipped (no result within 10s)"


def copy_shipped_scripts(destination):
  import shutil

  shutil.copytree(
    SCRIPT.parent, destination, ignore=shutil.ignore_patterns("__pycache__")
  )


def run(*arguments, cwd):
  return subprocess.run(
    [sys.executable, str(SCRIPT), *arguments],
    capture_output=True,
    text=True,
    encoding="utf-8",
    check=False,
    cwd=cwd,
  )
