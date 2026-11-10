"""Resolve the Chromium binary the browser regression tests launch."""

from __future__ import annotations

import os
from pathlib import Path


def chromium_executable() -> str | None:
  """Return the Playwright default Chromium binary, or None when absent."""
  try:
    from playwright.sync_api import sync_playwright
  except ImportError:
    return None
  try:
    with sync_playwright() as runner:
      candidate = Path(runner.chromium.executable_path)
  except Exception:
    return None
  if candidate.is_file() and os.access(candidate, os.X_OK):
    return str(candidate)
  return None


def require_chromium() -> str:
  """Return the Chromium binary, skipping the test when it is absent."""
  executable = chromium_executable()
  if executable is None:
    import pytest

    pytest.skip("Run the Chromium installer to place the Playwright default browser")
  return executable
