"""Rule files: live files must match refs in headings, line count, and token count per clause."""

from __future__ import annotations

from pathlib import Path

from ..repo import Repo

SECTIONED_PAIRS = ("CORE.md", "ARENA.md", "KILO.md")
# Kilo mode overrides and both ChatGPT fields compare plain non-empty line counts.
PLAIN_PAIRS = (
  *((f"kilo/{name}", f"kilo/{name}") for name in ("plan.md", "code.md", "debug.md")),
  ("COMMIT-SPEC.txt", "COMMIT-SPEC.txt"),
)
NEVER_ADD = "compression may merge lines but never add rules"
NEVER_EXCEED_TOKENS = "live clause token count exceeds refs baseline"


def section_rule_lines(text: str) -> list[tuple[str, list[str]]]:
  """Return (heading, [rule_lines]) for each section. Rule lines are non-empty lines under a ## heading."""
  sections: list[tuple[str, list[str]]] = []
  heading: str | None = None
  rules: list[str] = []

  for line in text.splitlines():
    stripped = line.strip()
    if line.startswith("## "):
      if heading is not None:
        sections.append((heading, rules))
      heading = line[3:].strip()
      rules = []
    elif heading is not None and stripped:
      rules.append(stripped)

  if heading is not None:
    sections.append((heading, rules))

  return sections


def rule_line_count(path: Path) -> int:
  return sum(
    1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
  )


def count_tokens(text: str) -> int:
  """Rough token count: split on whitespace."""
  return len(text.split())
  """Rough token count: split on whitespace."""
  return len(text.split())


def _check_sectioned(repo: Repo, name: str, errors: list[str]) -> None:
  ref_sections = section_rule_lines((repo.rule_refs / name).read_text(encoding="utf-8"))
  live_sections = section_rule_lines((repo.rules / name).read_text(encoding="utf-8"))
  ref_headings = [heading for heading, _ in ref_sections]
  live_headings = [heading for heading, _ in live_sections]

  if ref_headings != live_headings:
    errors.append(
      f"rules/{name}: section headings diverge from rules/refs/{name}: "
      f"refs={ref_headings} live={live_headings}"
    )
    return

  ref_map = dict(ref_sections)

  for heading, live_rules in live_sections:
    ref_rules = ref_map[heading]

    # Equal line count per section
    if len(live_rules) != len(ref_rules):
      errors.append(
        f"rules/{name} '{heading}': live has {len(live_rules)} rule lines, refs has {len(ref_rules)}; "
        f"must be equal"
      )

    # Per-clause token check: each live rule must have <= tokens than corresponding refs rule
    for i, (live_rule, ref_rule) in enumerate(zip(live_rules, ref_rules)):
      live_tokens = count_tokens(live_rule)
      ref_tokens = count_tokens(ref_rule)
      if live_tokens > ref_tokens:
        errors.append(
          f"rules/{name} '{heading}' rule {i+1}: live={live_tokens} tokens, refs={ref_tokens} tokens; "
          f"{NEVER_EXCEED_TOKENS}"
        )


def _check_plain(repo: Repo, live_name: str, ref_name: str, errors: list[str]) -> None:
  ref_lines = [l.strip() for l in (repo.rule_refs / ref_name).read_text(encoding="utf-8").splitlines() if l.strip()]
  live_lines = [l.strip() for l in (repo.rules / live_name).read_text(encoding="utf-8").splitlines() if l.strip()]

  # Equal line count
  if len(live_lines) != len(ref_lines):
    errors.append(
      f"rules/{live_name}: live has {len(live_lines)} rule lines, refs has {len(ref_lines)}; "
      f"must be equal"
    )

  # Per-line token check
  for i, (live_line, ref_line) in enumerate(zip(live_lines, ref_lines)):
    live_tokens = count_tokens(live_line)
    ref_tokens = count_tokens(ref_line)
    if live_tokens > ref_tokens:
      errors.append(
        f"rules/{live_name} line {i+1}: live={live_tokens} tokens, refs={ref_tokens} tokens; "
        f"{NEVER_EXCEED_TOKENS}"
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