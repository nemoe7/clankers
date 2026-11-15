"""Skill files: each live file matches its `skills/refs/` baseline line for line."""

from __future__ import annotations

from ..repo import Repo
from .keywords import compare_keyword_counts, prose_lines
from .rules import rule_line_count


def check_skill_refs_parity(repo: Repo, errors: list[str]) -> None:
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

    # Hard-rule keyword parity per line, only when line pairing is known
    ref_text = baseline.read_text(encoding="utf-8")
    live_text = live.read_text(encoding="utf-8")
    if ref_lines == live_lines:
      for i, (ref_line, live_line) in enumerate(
        zip(prose_lines(ref_text), prose_lines(live_text))
      ):
        if ref_line is None or live_line is None:
          continue
        compare_keyword_counts(f"{shown} line {i + 1}", ref_line, live_line, errors)
