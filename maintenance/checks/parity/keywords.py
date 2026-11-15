"""Keyword parity: hard-rule keywords dropped from live or added against refs."""

from __future__ import annotations

import re

# GUIDELINES.md section 4: MUST, NEVER, ALWAYS for hard rules. Prefer for soft ones.
# Only the capitalized forms count.
KEYWORDS = ("ALWAYS", "MUST", "NEVER", "Prefer")
PATTERNS = {keyword: re.compile(rf"\b{re.escape(keyword)}\b") for keyword in KEYWORDS}

# Wenyan one-to-one map: English keyword -> single Chinese equivalent.
# Strictest force per keyword, all single chars measure 1 o200k_base token.
WENYAN_MAP = {
  "MUST": "須",
  "NEVER": "勿",
  "ALWAYS": "皆",
  "Prefer": "優先",
}
WENYAN_PATTERNS = {
  keyword: re.compile(chinese) for keyword, chinese in WENYAN_MAP.items()
}
DO_NOT = re.compile(r"\bdo not\b", re.IGNORECASE)
DO_NOT_LABEL = "do not"
# Fenced code blocks ```...``` and inline `...`
FENCED_CODE = re.compile(r"```.*?```", re.DOTALL)
INLINE_CODE = re.compile(r"`[^`]*`")


def _strip_code(text: str) -> str:
  """Remove fenced and inline code blocks so 'do not' in code is ignored."""
  text = FENCED_CODE.sub("", text)
  text = INLINE_CODE.sub("", text)
  return text


def prose_lines(text: str) -> list[str | None]:
  """Split into lines, blanking lines inside fenced code blocks.

  Headers stay: compare_keyword_counts skips them, so pairing survives.
  """
  inside = False
  lines: list[str | None] = []
  for line in text.split("\n"):
    if line.strip().startswith("```"):
      inside = not inside
      lines.append(None)
      continue
    lines.append(None if inside else line)
  return lines


def keyword_counts(text: str) -> dict[str, int]:
  """Count capitalized rule keywords and case-insensitive 'do not' occurrences outside code."""
  counts = {
    keyword: len(pattern.findall(text)) for keyword, pattern in PATTERNS.items()
  }
  prose = _strip_code(text)
  counts[DO_NOT_LABEL] = len(DO_NOT.findall(prose))
  return counts


def wenyan_keyword_counts(text: str) -> dict[str, int]:
  """Count wenyan equivalents of English keywords plus any literal English keywords."""
  counts = {keyword: 0 for keyword in KEYWORDS}
  for keyword, pattern in WENYAN_PATTERNS.items():
    counts[keyword] = len(pattern.findall(text))
  # Literal English keywords also count (wenyan is hybrid)
  english_counts = keyword_counts(text)
  for keyword in KEYWORDS:
    counts[keyword] += english_counts[keyword]
  return counts


def compare_keyword_counts(
  label: str,
  ref_text: str,
  live_text: str,
  errors: list[str],
  wenyan: bool = False,
) -> None:
  """Flag keywords dropped from live, added against refs, and 'do not' wording.

  Applies to clause lines only: headers and code never count.
  """
  if ref_text.lstrip().startswith("#") or live_text.lstrip().startswith("#"):
    return

  if wenyan:
    ref_counts = keyword_counts(ref_text)
    live_counts = wenyan_keyword_counts(live_text)
  else:
    ref_counts = keyword_counts(ref_text)
    live_counts = keyword_counts(live_text)

  for keyword in KEYWORDS:
    if ref_counts[keyword] > live_counts[keyword]:
      errors.append(
        f"{label}: '{keyword}' dropped from live "
        f"({ref_counts[keyword]} in refs, {live_counts[keyword]} in live); restore the keyword"
      )
    elif live_counts[keyword] > ref_counts[keyword]:
      errors.append(
        f"{label}: '{keyword}' added in live "
        f"({live_counts[keyword]} vs {ref_counts[keyword]} in refs); update the refs baseline"
      )

  # 'do not' check only for non-wenyan (English) copies
  if not wenyan and live_counts[DO_NOT_LABEL]:
    errors.append(
      f"{label}: 'do not' found ({live_counts[DO_NOT_LABEL]}x); replace it with NEVER"
    )
