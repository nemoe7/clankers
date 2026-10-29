"""Markdown report form parser and task-detail answer formatter for Arena Steering."""

from __future__ import annotations

import re
from typing import Any

from .models import TASK_DETAIL_MAX_LEN, ReportField, kebab_slug

FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")
ANCHOR_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
INLINE_ANCHOR_RE = re.compile(r"\{#([a-z0-9]+(?:-[a-z0-9]+)*)\}\s*$")

CHOICE_ITEM_RE = re.compile(r"^\s*[-*]\s+\(([ xX])\)\s+(.+?)\s*$")
CHECKBOX_ITEM_RE = re.compile(r"^\s*[-*]\s+\[([ xX])\]\s+(.+?)\s*$")
TEXT_BLANK_RE = re.compile(r"^\s*(?:[-*]\s+)?(?:(.+?):\s*)?_{3,}\s*$")
CONTINUATION_RE = re.compile(r"^\s{2,}(?![-*]\s+[\(\[])(\S.+?)\s*$")
CUSTOM_SLOT_RE = re.compile(
  r"^(?:custom|something else\.{0,3})\s*:\s*_{3,}\s*$", re.IGNORECASE
)
HEADING_PREFIX_RE = re.compile(r"^\s*#{1,6}\s+")


def _split_comments(line: str) -> tuple[str, str | None]:
  """Strip inline comment spans and extract the first valid anchor slug."""
  anchor: str | None = None
  parts: list[str] = []
  pos = 0
  while True:
    start = line.find("<!--", pos)
    if start < 0:
      parts.append(line[pos:])
      break
    end = line.find("-->", start + 4)
    if end < 0:
      parts.append(line[pos:])
      break
    parts.append(line[pos:start])
    inner = line[start + 4 : end].strip()
    if anchor is None and ANCHOR_SLUG_RE.match(inner):
      anchor = inner
    pos = end + 3
  return "".join(parts), anchor


def strip_md_comments(line: str) -> str:
  """Remove inline HTML comments from one line."""
  cleaned, _ = _split_comments(line)
  return cleaned


def clean_label_text(raw: str) -> str:
  """Clean a Markdown prompt line into a plain field label."""
  without_comments = strip_md_comments(raw).strip()
  without_anchor = INLINE_ANCHOR_RE.sub("", without_comments).strip()
  without_heading = HEADING_PREFIX_RE.sub("", without_anchor).strip()
  if without_heading.startswith(("- ", "* ")):
    without_heading = without_heading[2:].strip()
  return without_heading


def parse_report_markdown(
  markdown: str,
) -> tuple[list[tuple[str, Any]], list[ReportField]]:
  """Parse report Markdown into interleaved prose/field blocks and ReportField items."""
  lines = markdown.splitlines()
  blocks: list[tuple[str, Any]] = []
  chunk: list[str] = []
  fields: list[ReportField] = []
  used_ids: set[str] = set()

  fence: str | None = None
  pending_anchor: str | None = None
  last_prompt: str = ""
  idx = 0

  while idx < len(lines):
    line = lines[idx]
    if fence is not None:
      chunk.append(line)
      if line.strip().startswith(fence):
        fence = None
      idx += 1
      continue

    fence_match = FENCE_RE.match(line)
    if fence_match:
      fence = fence_match.group(1)
      chunk.append(line)
      idx += 1
      continue

    cleaned, comment_anchor = _split_comments(line)
    if not cleaned.strip():
      if comment_anchor:
        pending_anchor = comment_anchor.rstrip("-")
      else:
        chunk.append(line)
      idx += 1
      continue

    choice_match = CHOICE_ITEM_RE.match(cleaned)
    checkbox_match = None if choice_match else CHECKBOX_ITEM_RE.match(cleaned)
    field_type = "choice" if choice_match else "checkbox" if checkbox_match else None
    blank_match = None if field_type else TEXT_BLANK_RE.match(cleaned)

    if field_type is None and blank_match is None:
      inline_anchor = INLINE_ANCHOR_RE.search(cleaned)
      if inline_anchor:
        pending_anchor = inline_anchor.group(1).rstrip("-")
        cleaned = INLINE_ANCHOR_RE.sub("", cleaned).rstrip()
      elif comment_anchor:
        pending_anchor = comment_anchor.rstrip("-")
      chunk.append(cleaned)
      candidate_label = clean_label_text(cleaned)
      if candidate_label:
        last_prompt = candidate_label
      idx += 1
      continue

    if field_type is not None:
      pattern = CHOICE_ITEM_RE if field_type == "choice" else CHECKBOX_ITEM_RE
      options: list[str] = []
      recommended: list[str] = []
      while idx < len(lines):
        item_line = strip_md_comments(lines[idx])
        item_match = pattern.match(item_line)
        if not item_match:
          break
        is_rec = item_match.group(1).lower() == "x"
        opt_text = item_match.group(2).strip()
        idx += 1
        while idx < len(lines):
          cont = CONTINUATION_RE.match(strip_md_comments(lines[idx]))
          if not cont:
            break
          opt_text = f"{opt_text} {cont.group(1).strip()}"
          idx += 1
        if CUSTOM_SLOT_RE.match(opt_text):
          continue
        options.append(opt_text)
        if is_rec:
          recommended.append(opt_text)

      label = last_prompt or f"Field {len(fields) + 1}"
      field_id = _resolve_field_id(pending_anchor, label, used_ids)
      pending_anchor = None
      report_field = ReportField(
        id=field_id,
        label=label,
        type=field_type,
        options=options,
        recommended=recommended,
      )
    else:
      assert blank_match is not None
      inline_label = (blank_match.group(1) or "").strip()
      if inline_label:
        inline_anchor = INLINE_ANCHOR_RE.search(inline_label)
        if inline_anchor:
          pending_anchor = inline_anchor.group(1).rstrip("-")
        label = clean_label_text(inline_label)
      else:
        label = last_prompt or f"Field {len(fields) + 1}"
      if comment_anchor:
        pending_anchor = comment_anchor.group(1).rstrip("-")
      field_id = _resolve_field_id(pending_anchor, label, used_ids)
      pending_anchor = None
      report_field = ReportField(
        id=field_id,
        label=label,
        type="text",
        options=[],
        recommended=[],
      )
      idx += 1

    blocks.append(("markdown", "\n".join(chunk)))
    blocks.append(("field", report_field))
    chunk = []
    fields.append(report_field)

  blocks.append(("markdown", "\n".join(chunk)))
  return blocks, fields


def format_answer_for_task_detail(field: ReportField, value: Any) -> str:
  """Format a field's label and submitted value as a single task detail string."""
  label = field.label.rstrip(":?.! ")
  if isinstance(value, dict):
    selected = value.get("selected")
    custom = str(value.get("custom", "")).strip()
    parts: list[str] = []
    if isinstance(selected, list):
      parts.extend(str(item).strip() for item in selected if str(item).strip())
    elif selected:
      parts.append(str(selected).strip())
    if custom:
      parts.append(custom)
    answer_str = ", ".join(parts)
  elif isinstance(value, list):
    answer_str = ", ".join(str(item).strip() for item in value if str(item).strip())
  else:
    answer_str = str(value or "").strip()

  if not answer_str:
    answer_str = "(none)"
  line = f"{label}: {answer_str}"
  if not line.endswith("."):
    line += "."
  if len(line) > TASK_DETAIL_MAX_LEN:
    line = line[: TASK_DETAIL_MAX_LEN - 3].rstrip() + "..."
  return line


def _resolve_field_id(
  explicit_anchor: str | None, label: str, used_ids: set[str]
) -> str:
  if explicit_anchor:
    candidate = kebab_slug(explicit_anchor, used_ids)
  else:
    candidate = kebab_slug(label, used_ids)
  used_ids.add(candidate)
  return candidate
