"""Rule files: live files must match refs in headings, line count, and token count per clause."""

from __future__ import annotations

from pathlib import Path

from ..repo import Repo
from ..report import Notes
from .compare import compare_lines

SECTIONED_PAIRS = ("CORE.md", "ARENA.md", "KILO.md")
# Kilo mode overrides and both ChatGPT fields compare plain non-empty line counts.
PLAIN_PAIRS = (
  *((f"kilo/{name}", f"kilo/{name}") for name in ("plan.md", "code.md", "debug.md")),
  ("COMMIT-SPEC.txt", "COMMIT-SPEC.txt"),
)


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


def _check_sectioned(repo: Repo, name: str, errors: list[str], notes: Notes) -> None:
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
      continue

    compare_lines(
      f"rules/{name} '{heading}'",
      ref_rules,
      live_rules,
      errors,
      notes=notes,
      file=f"rules/{name}",
      section=heading,
    )


def _check_plain(
  repo: Repo, live_name: str, ref_name: str, errors: list[str], notes: Notes
) -> None:
  ref_lines = [
    l.strip()
    for l in (repo.rule_refs / ref_name).read_text(encoding="utf-8").splitlines()
    if l.strip()
  ]
  live_lines = [
    l.strip()
    for l in (repo.rules / live_name).read_text(encoding="utf-8").splitlines()
    if l.strip()
  ]

  compare_lines(
    f"rules/{live_name}",
    ref_lines,
    live_lines,
    errors,
    notes=notes,
    file=f"rules/{live_name}",
  )


def check_rule_parity(
  repo: Repo, errors: list[str], notes: Notes | None = None
) -> None:
  owned = notes is None
  notes = notes or Notes()
  pairs = [(name, name, True) for name in SECTIONED_PAIRS]
  pairs += [(live, ref, False) for live, ref in PLAIN_PAIRS]

  for live_name, ref_name, sectioned in pairs:
    if (
      not (repo.rule_refs / ref_name).is_file()
      or not (repo.rules / live_name).is_file()
    ):
      errors.append(f"rules/{live_name}: refs/live pair incomplete")
    elif sectioned:
      _check_sectioned(repo, live_name, errors, notes)
    else:
      _check_plain(repo, live_name, ref_name, errors, notes)

  if owned:
    notes.flush()
