"""Rule files: each live file holds no more rule lines than its refs baseline."""

from __future__ import annotations

from pathlib import Path

from ..repo import Repo

# Rule refs baselines hold full wording. Live files compress it. Compression may
# merge rule lines but never add them, so live counts stay at or below refs.
SECTIONED_PAIRS = ("CORE.md", "ARENA.md", "KILO.md")
# Kilo mode overrides and both ChatGPT fields compare plain non-empty line counts.
PLAIN_PAIRS = (
  *((f"kilo/{name}", f"kilo/{name}") for name in ("plan.md", "code.md", "debug.md")),
  ("CHATGPT-CUSTOM.txt", "CHATGPT.txt"),
  ("CHATGPT-MORE.txt", "CHATGPT.txt"),
  ("COMMIT-SPEC.txt", "COMMIT-SPEC.txt"),
)
NEVER_ADD = "compression may merge lines but never add rules"


def section_rule_counts(text: str) -> list[tuple[str, int]]:
  counts: list[tuple[str, int]] = []
  heading: str | None = None
  rules = 0

  for line in text.splitlines():
    if line.startswith("## "):
      if heading is not None:
        counts.append((heading, rules))

      heading = line[3:].strip()
      rules = 0
    elif heading is not None and line.strip():
      rules += 1

  if heading is not None:
    counts.append((heading, rules))

  return counts


def rule_line_count(path: Path) -> int:
  return sum(
    1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
  )


def _check_sectioned(repo: Repo, name: str, errors: list[str]) -> None:
  ref_counts = section_rule_counts((repo.rule_refs / name).read_text(encoding="utf-8"))
  live_counts = section_rule_counts((repo.rules / name).read_text(encoding="utf-8"))
  ref_headings = [heading for heading, _ in ref_counts]
  live_headings = [heading for heading, _ in live_counts]

  if ref_headings != live_headings:
    errors.append(
      f"rules/{name}: section headings diverge from rules/refs/{name}: "
      f"refs={ref_headings} live={live_headings}"
    )
    return

  ref_map = dict(ref_counts)

  for heading, live_rules in live_counts:
    if live_rules > ref_map[heading]:
      errors.append(
        f"rules/{name} '{heading}': {live_rules} rule lines vs {ref_map[heading]} in "
        f"rules/refs/{name}; {NEVER_ADD}"
      )


def _check_plain(repo: Repo, live_name: str, ref_name: str, errors: list[str]) -> None:
  ref_rules = rule_line_count(repo.rule_refs / ref_name)
  live_rules = rule_line_count(repo.rules / live_name)

  if live_rules > ref_rules:
    errors.append(
      f"rules/{live_name}: {live_rules} rule lines vs {ref_rules} in rules/refs/{ref_name}; {NEVER_ADD}"
    )


def check_rule_parity(repo: Repo, errors: list[str]) -> None:
  pairs = [(name, name, True) for name in SECTIONED_PAIRS]
  pairs += [(live, ref, False) for live, ref in PLAIN_PAIRS]

  for live_name, ref_name, sectioned in pairs:
    if (
      not (repo.rule_refs / ref_name).is_file()
      or not (repo.rules / live_name).is_file()
    ):
      errors.append(f"rules/{live_name}: refs/live pair incomplete")
    elif sectioned:
      _check_sectioned(repo, live_name, errors)
    else:
      _check_plain(repo, live_name, ref_name, errors)
