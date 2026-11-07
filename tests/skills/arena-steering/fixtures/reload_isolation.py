"""Keep in-process module reload tests from changing other tests' class identities."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]
CHILD_ENV = "ARENA_STEERING_RELOAD_TEST_CHILD"


def run_reload_in_child(request: pytest.FixtureRequest) -> bool:
  """Return True in the parent after running this test in a fresh interpreter."""
  if os.environ.get(CHILD_ENV) == "1":
    return False
  result = subprocess.run(
    [sys.executable, "-m", "pytest", "-q", "-n", "0", request.node.nodeid],
    cwd=ROOT,
    env={**os.environ, CHILD_ENV: "1"},
    capture_output=True,
    text=True,
    encoding="utf-8",
    check=False,
    timeout=90,
  )
  assert result.returncode == 0, result.stdout + result.stderr
  return True
