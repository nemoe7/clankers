"""Shared line-by-line comparison core for all parity checks."""

from __future__ import annotations

from ..report import LOG
from .keywords import compare_keyword_counts

NEVER_EXCEED_TOKENS = "live clause token count exceeds refs baseline"
EXACT_COPY = "live clause matches refs exactly; compression or review may be missing"
EQUAL_TOKENS_REWORDED = (
  "live clause reworded at the same token count as refs; compression did not shrink it"
)


def count_tokens(text: str) -> int:
  """Rough token count: split on whitespace."""
  return len(text.split())


def compare_lines(
  label: str,
  ref_lines: list[str],
  live_lines: list[str],
  errors: list[str],
  keywords: bool = True,
) -> None:
  """Compare paired lines: equal count, token cap, keyword parity, warnings."""
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

    if live_line == ref_line:
      LOG.warning("%s: %s", line_label, EXACT_COPY)
    elif live_tokens == ref_tokens:
      LOG.warning("%s: %s", line_label, EQUAL_TOKENS_REWORDED)

  # Hard-rule keyword parity per line, only when line pairing is known
  if keywords:
    for i, (live_line, ref_line) in enumerate(zip(live_lines, ref_lines)):
      compare_keyword_counts(f"{label} line {i + 1}", ref_line, live_line, errors)
