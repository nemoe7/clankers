"""System prompts: the live copy compresses `system-prompts/refs/` and never adds a rule."""

from __future__ import annotations

from ..repo import Repo

# `system-prompts/refs/` holds the full wording and the live copy compresses it.
# The compression may merge or drop lines, but it NEVER adds a rule the refs lack.
SYSTEM_PROMPT_PAIRS = ("NEMOGPT.md",)
# A section header is a short bare line standing alone between blank lines.
HEADER_MAX = 40


def prompt_sections(text: str) -> list[tuple[str, int, int]]:
  """Return (header, start, end) spans for a system prompt's bare-line sections."""
  lines = text.split("\n")
  marks: list[tuple[str, int]] = []

  for index, line in enumerate(lines):
    head = line.strip()

    if not head or len(head) > HEADER_MAX or head.endswith((".", ":", ";", ",")):
      continue

    before = lines[index - 1].strip() if index else ""
    after = lines[index + 1].strip() if index + 1 < len(lines) else ""

    if before == "" and after == "":
      marks.append((head, index))

  return [
    (head, start, marks[i + 1][1] if i + 1 < len(marks) else len(lines))
    for i, (head, start) in enumerate(marks)
  ]


def _count(lines: list[str], span: tuple[int, int]) -> int:
  start, end = span
  return sum(1 for line in lines[start + 1 : end] if line.strip())


def _spans(sections: list[tuple[str, int, int]]) -> dict[str, tuple[int, int]]:
  """Map each header to its span. A repeated header keeps its first span."""
  return {head: (start, end) for head, start, end in reversed(sections)}


def _check_pair(label: str, ref_text: str, live_text: str, errors: list[str]) -> None:
  if len(live_text.encode()) > len(ref_text.encode()):
    errors.append(
      f"{label}: {len(live_text.encode())} bytes vs "
      f"{len(ref_text.encode())} in refs; compression may shrink but never grow"
    )

  ref_sections = prompt_sections(ref_text)
  live_sections = prompt_sections(live_text)
  ref_names = [head for head, _, _ in ref_sections]
  live_names = [head for head, _, _ in live_sections]

  added = [head for head in live_names if head not in ref_names]
  if added:
    errors.append(f"{label}: sections absent from refs: {added}")
    return

  # A caption may repeat a section name, so refs "Prompt transparency" is both a section and a worked-example caption.
  # Compare only the unambiguous names both copies carry, so a compressed-away caption does not read as a divergence.
  repeated = {head for head in ref_names if ref_names.count(head) > 1}
  shared = [
    head
    for head in dict.fromkeys(live_names)
    if head in ref_names and head not in repeated
  ]
  ref_span = _spans(ref_sections)
  live_span = _spans(live_sections)
  ref_lines = ref_text.split("\n")
  live_lines = live_text.split("\n")

  for position, head in enumerate(shared):
    # Widen each span to the next shared header, so refs may carry
    # sub-labels the live copy compressed away.
    following = shared[position + 1] if position + 1 < len(shared) else None
    ref_end = ref_span[following][0] if following else ref_span[head][1]
    live_end = live_span[following][0] if following else live_span[head][1]
    ref_rules = _count(ref_lines, (ref_span[head][0], ref_end))
    live_rules = _count(live_lines, (live_span[head][0], live_end))

    if live_rules > ref_rules:
      errors.append(
        f"{label} '{head}': {live_rules} lines vs {ref_rules} in refs; "
        "compression may merge lines but never add rules"
      )


def check_system_prompt_parity(repo: Repo, errors: list[str]) -> None:
  """Check each system prompt against its refs source."""
  for name in SYSTEM_PROMPT_PAIRS:
    reference = repo.system_prompts / "refs" / name
    live = repo.system_prompts / name

    if not reference.is_file() or not live.is_file():
      errors.append(f"system-prompts/{name}: refs/live pair incomplete")
      continue

    _check_pair(
      f"system-prompts/{name}",
      reference.read_text(encoding="utf-8"),
      live.read_text(encoding="utf-8"),
      errors,
    )
