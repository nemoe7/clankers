"""Prove the CI browser requirement fails instead of skipping."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_a_MISSING_BROWSER_fails_when_the_run_requires_one(tmp_path: Path) -> None:
  conftest = Path(__file__).with_name("conftest.py").read_text(encoding="utf-8")
  stub = conftest.replace(
    'importlib.util.find_spec("playwright.sync_api") is None', "True"
  )
  assert stub != conftest
  package = tmp_path / "probe"
  package.mkdir()
  (package / "conftest.py").write_text(stub, encoding="utf-8")
  (package / "test_probe.py").write_text(
    "def test_probe():\n  pass\n", encoding="utf-8"
  )
  result = subprocess.run(
    [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(package)],
    cwd=Path(__file__).parents[3],
    env={
      "CI_REQUIRE_BROWSER": "1",
      "PATH": "/usr/bin:/bin",
      "PYTHONPATH": str(Path(__file__).parents[3] / "skills/arena-steering/scripts"),
    },
    capture_output=True,
    text=True,
    check=False,
  )
  assert result.returncode != 0, result.stdout
  assert "CI_REQUIRE_BROWSER=1 but playwright is not installed" in result.stdout
