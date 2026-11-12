"""Skill files: each live file holds no more lines than its `skills/refs/` baseline."""

from __future__ import annotations

from ..repo import Repo
from .rules import rule_line_count


def check_skill_refs_parity(repo: Repo, errors: list[str]) -> None:
  """Check each skill file against its refs baseline.

  Live files compress the refs wording, so a higher live line count flags a live-only rule.
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
    if live_lines > ref_lines:
      errors.append(
        f"{shown}: {live_lines} lines vs {ref_lines} in "
        f"{repo.relative(baseline)}; compression may merge lines but never add them"
      )
