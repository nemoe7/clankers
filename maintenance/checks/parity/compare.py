"""Shared line-by-line comparison core for all parity checks."""

from __future__ import annotations

from ..report import EQUAL_TOKENS_REWORDED, EXACT_COPY, LOG, Notes
from .keywords import compare_keyword_counts

NEVER_EXCEED_TOKENS = "live clause token count exceeds refs baseline"


def count_tokens(text: str) -> int:
  """Rough token count: split on whitespace."""
  return len(text.split())


def compare_lines(
  label: str,
  ref_lines: list[str],
  live_lines: list[str],
  errors: list[str],
  keywords: bool = True,
  notes: Notes | None = None,
  file: str | None = None,
  section: str | None = None,
) -> None:
  """Compare paired lines: equal count, token cap, keyword parity, warnings.

  Pass `notes` with a `file` name to collect warnings for grouped flushing.
  Without `notes`, warnings log one line per clause.
  """
  # Equal line count
  if len(live_lines) != len(ref_lines):
    errors.append(
      f"{label}: live has {len(live_lines)} rule lines, refs has {len(ref_lines)}; "
      f"must be equal"
    )
    return

  # Per-line token cap and warnings
  for i, (live_line, ref_line) in enumerate(zip(live_lines, ref_lines)):
    line_label = f"{label} line {i + 1}"
    live_tokens = count_tokens(live_line)
    ref_tokens = count_tokens(ref_line)

    if live_tokens > ref_tokens:
      errors.append(
        f"{line_label}: live={live_tokens} tokens, refs={ref_tokens} tokens; "
        f"{NEVER_EXCEED_TOKENS}"
      )

    if notes is not None and file is not None:
      if live_line == ref_line:
        notes.add(file, section, i + 1, EXACT_COPY)
      elif live_tokens == ref_tokens:
        notes.add(file, section, i + 1, EQUAL_TOKENS_REWORDED)
    elif live_line == ref_line:
      LOG.warning("%s: %s", line_label, EXACT_COPY)
    elif live_tokens == ref_tokens:
      LOG.warning("%s: %s", line_label, EQUAL_TOKENS_REWORDED)

  # Hard-rule keyword parity per line, only when line pairing is known
  if keywords:
    for i, (live_line, ref_line) in enumerate(zip(live_lines, ref_lines)):
      compare_keyword_counts(f"{label} line {i + 1}", ref_line, live_line, errors)
