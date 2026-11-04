"""Nonblocking reminders for calls through the installed steering launcher."""

from __future__ import annotations

from pathlib import Path

import pytest
from arena_steering import pre

INSTALLED = Path.home() / ".local/bin/steer"


@pytest.mark.parametrize(
  ("line", "warn"),
  (
    (f"{INSTALLED} read", True),
    ("~/.local/bin/steer read", True),
    (f"env LANG=C {INSTALLED} read", True),
    (f"printf '{INSTALLED}'", False),
    ("steer read", False),
  ),
)
def test_installed_launcher_suggests_bare_steer_without_blocking(
  line: str, warn: bool
) -> None:
  result = pre.run_pipeline(pre.PreContext(line=line, command=line))
  assert result.verdict == pre.CONTINUE
  text = " ".join(result.messages)
  assert ("Use bare `steer`" in text) == warn
  if warn:
    assert "It works without the full path." in text
