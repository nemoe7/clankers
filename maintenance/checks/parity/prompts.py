"""System prompts: the live copy compresses `system-prompts/refs/` and never adds a rule."""

from __future__ import annotations

from ..repo import Repo
from ..report import Notes
from .compare import compare_lines

# `system-prompts/refs/` holds the full wording and the live copy compresses it.
# The compression may merge or drop lines, but it NEVER adds a rule the refs lack.
SYSTEM_PROMPT_PAIRS = ("NEMOGPT.md",)

# Subdirectories to check for system prompt copies (live and wenyan)
SYSTEM_PROMPT_COPIES = (
  ("", "live"),
  ("wenyan", "wenyan"),
)
# A section header is a bare `##` line standing alone between blank lines.
HEADER_MAX = 40


def prompt_sections(
  text: str, header_prefix: str = "## "
) -> list[tuple[str, int, int]]:
  """Return (header, start, end) spans for a system prompt's bare-line sections."""
  lines = text.split("\n")
  marks: list[tuple[str, int]] = []

  for index, line in enumerate(lines):
    stripped = line.strip()
    if (
      not stripped
      or not stripped.startswith(header_prefix)
      or len(stripped) > HEADER_MAX
    ):
      continue

    before = lines[index - 1].strip() if index else ""

    # A header must have a blank line before it. It may be the last line (no after needed).
    if before != "":
      continue

    marks.append((stripped[len(header_prefix) :], index))

  return [
    (head, start, marks[i + 1][1] if i + 1 < len(marks) else len(lines))
    for i, (head, start) in enumerate(marks)
  ]


def _section_lines(
  text: str, sections: list[tuple[str, int, int]], head: str
) -> list[str]:
  """Return the non-empty lines under one section."""
  lines = text.split("\n")
  for h, start, end in sections:
    if h == head:
      return [line.strip() for line in lines[start + 1 : end] if line.strip()]
  return []


def _check_pair(
  label: str,
  ref_text: str,
  live_text: str,
  errors: list[str],
  wenyan: bool = False,
  notes: Notes | None = None,
) -> None:
  ref_sections = prompt_sections(ref_text)
  live_sections = prompt_sections(live_text)
  ref_names = [head for head, _, _ in ref_sections]
  live_names = [head for head, _, _ in live_sections]

  added = [head for head in live_names if head not in ref_names]
  missing = [head for head in ref_names if head not in live_names]
  if added or missing:
    if added:
      errors.append(f"{label}: sections absent from refs: {added}")
    if missing:
      errors.append(f"{label}: sections missing in live: {missing}")
    return

  for head in ref_names:
    ref_rules = _section_lines(ref_text, ref_sections, head)
    live_rules = _section_lines(live_text, live_sections, head)

    # Equal line count per section
    if len(live_rules) != len(ref_rules):
      reason = (
        "compression may merge lines but never add rules"
        if len(live_rules) > len(ref_rules)
        else "compression may merge lines but never drop them"
      )
      errors.append(
        f"{label} '{head}': {len(live_rules)} lines vs {len(ref_rules)} in refs; {reason}"
      )
      continue

    # Wenyan is a Chinese field copy. Keyword counts cannot transfer between
    # grammars, so its lines skip keyword parity (compare_lines keeps the rest).
    compare_lines(
      f"{label} '{head}'",
      ref_rules,
      live_rules,
      errors,
      keywords=not wenyan,
      notes=notes,
      file=label,
      section=head,
    )


def check_system_prompt_parity(
  repo: Repo, errors: list[str], notes: Notes | None = None
) -> None:
  """Check each system prompt against its refs source, including wenyan copies."""
  owned = notes is None
  notes = notes or Notes()
  for name in SYSTEM_PROMPT_PAIRS:
    reference = repo.system_prompts / "refs" / name
    if not reference.is_file():
      errors.append(f"system-prompts/refs/{name}: refs source missing")
      continue

    ref_text = reference.read_text(encoding="utf-8")
    for subdir, _ in SYSTEM_PROMPT_COPIES:
      live_dir = repo.system_prompts / subdir if subdir else repo.system_prompts
      live = live_dir / name
      shown = f"system-prompts/{subdir + '/' if subdir else ''}{name}"
      if not live.is_file():
        errors.append(f"{shown}: refs/live pair incomplete")
        continue
      _check_pair(
        shown,
        ref_text,
        live.read_text(encoding="utf-8"),
        errors,
        wenyan=(subdir == "wenyan"),
        notes=notes,
      )

  if owned:
    notes.flush()
