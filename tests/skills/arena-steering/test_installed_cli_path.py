"""Nonblocking reminders for calls through the installed steering launcher."""

from __future__ import annotations

from pathlib import Path

import pytest
from arena_steering import pre

INSTALLED = Path.home() / ".local/bin/steer"
ROOT = Path(__file__).resolve().parents[3]


def test_browser_recipe_is_standard_tooling_without_installer_changes() -> None:
  skill = (ROOT / "skills/arena-steering/SKILL.md").read_text(encoding="utf-8")
  recipe = (ROOT / "skills/arena-steering/references/recipes/chromium.md").read_text(
    encoding="utf-8"
  )
  installer = (ROOT / "skills/arena-steering/scripts/install.sh").read_text(
    encoding="utf-8"
  )
  assert (
    "For any browser work, follow [the Chromium recipe]"
    "(references/recipes/chromium.md) as standard local tooling."
  ) in skill
  assert "Inflate `bin/al2023.tar.br`" in recipe
  assert "Call `setupLambdaEnvironment`" in recipe
  assert "NEVER use a Playwright-managed browser." in recipe
  assert "Python" not in recipe and "pip " not in recipe
  assert "@sparticuz/chromium" not in installer


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
