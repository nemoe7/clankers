"""Skill files: each live file matches its `skills/` baseline line for line."""

from __future__ import annotations

from ..repo import Repo
from .compare import compare_lines
from .keywords import prose_lines
from .rules import rule_line_count


def check_skills_parity(repo: Repo, errors: list[str]) -> None:
  """Check each skill file against its refs baseline.

  Live files must match refs line for line: no merged or dropped clauses.
  """
  refs_root = repo.skills / "refs"
  if not refs_root.is_dir():
    return

  for baseline in sorted(refs_root.rglob("*")):
    if not baseline.is_file() or baseline.suffix not in {".md", ".txt"}:
      continue
    live = repo.skills / baseline.relative_to(refs_root)
    shown = repo.relative(live)
    if not live.is_file():
      errors.append(f"{shown}: refs counterpart exists without a live file")
      continue

    ref_lines = rule_line_count(baseline)
    live_lines = rule_line_count(live)
    if live_lines != ref_lines:
      errors.append(
        f"{shown}: {live_lines} lines vs {ref_lines} in "
        f"{repo.relative(baseline)}; must be equal"
      )
      continue

    # Clause checks run on prose lines, with fenced code and blanks dropped.
    ref_prose = [
      line
      for line in prose_lines(baseline.read_text(encoding="utf-8"))
      if line is not None and line.strip()
    ]
    live_prose = [
      line
      for line in prose_lines(live.read_text(encoding="utf-8"))
      if line is not None and line.strip()
    ]
    compare_lines(shown, ref_prose, live_prose, errors)
