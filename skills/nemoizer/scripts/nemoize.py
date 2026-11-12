# nonemo: NMO100
# nonemo: NMO901
"""Check prose and test candidates, rotate words, and collect exclusions."""

import argparse
import configparser
import json
import os
import queue
import re
import subprocess
import sys
import threading
import time
import tokenize
import tomllib
from concurrent.futures import FIRST_COMPLETED, Future, wait
from itertools import pairwise
from pathlib import Path

import nemo_config
from markers import (
  MARKER,
  MARKER_SPAN,
  audit_lines,
)
from nemo_assertions import is_test_file, review_tests
from nemo_config import (
  HEADING_SENTENCE_CAP,
  LIST_SENTENCE_CAP,
  MIN_THE_COUNT,
  PARAGRAPH_CAP,
  SENTENCE_CAPS,
  THE_DENSITY_CAP,
  exclusions,
  file_config,
  file_scope,
  load_config,
  suppressed,
)
from nemo_detectors import (
  DETECTORS,
  UI_STRING_DASH_RE,
  prose_semicolons,
  prose_the_density,
)
from nemo_files import text_file, walk
from nemo_markdown import (
  blank_inline_comments,
  fence_states,
  fenced_lines,
  prose_blocks,
  prose_counts,
)
from nemo_report import (
  describe_finding,
  format_finding,
  format_summary,
  is_advisory,
)
from nemo_rotate import (
  KEEP_LOWER,
  ROTATIONS,
  collapse_list_articles,
  mask_protected_spans,
  rotate,
  rotation_legend,
)
from nemo_rules import (
  ADVISORY_RULE_IDS,
  LINE_PROSE_RULE_IDS,
  NMU_RULE_IDS,
  PROSE_RULE_IDS,
  RULE_IDS,
  TEST_RULE_IDS,
)
from nemo_ui import NMU100_MAX_WORDS, NMU200_SUFFIXES, nmu100_findings, nmu200_findings
from prose import (
  COMMENT_BLOCK_CAP,
  comment_blocks,
  html_attr_spans,
  is_code_file,
  is_env_file,
  is_jinja_file,
  is_workflow_yaml,
  prose_spans,
  slash_comments,
  ui_label_spans,
  workflow_name_spans,
)


def _prose_line_map(path, text):
  """Map 1-based physical line numbers to extracted prose text for code files."""
  mapping = {}
  try:
    spans = prose_spans(path, text)
  except (
    SyntaxError,
    tokenize.TokenError,
    subprocess.SubprocessError,
    OSError,
    ValueError,
    RuntimeError,
  ):
    return mapping
  for span_text, first, last in spans:
    span_lines = span_text.splitlines()
    if len(span_lines) == last - first + 1:
      for offset, part in enumerate(span_lines):
        mapping.setdefault(first + offset, []).append(part)
    else:
      for ln in range(first, last + 1):
        mapping.setdefault(ln, []).append(span_text)
  return {ln: "\n".join(parts) for ln, parts in mapping.items()}


def scan(targets, ignores, audit=False, verbose=False):
  """Return findings and all exclusion markers with locations and rule IDs."""
  findings, marks = [], []
  for path in walk(targets, ignores):
    if verbose:
      print(f"scan {path}", file=sys.stderr, flush=True)
    text = text_file(path)
    if text is None:
      continue
    lines = text.splitlines()
    with file_scope(path, text):
      file_ids, line_ids, found = exclusions(path, lines, audit=audit)
    marks.extend(found)
    is_code = is_code_file(path)
    prose_map = _prose_line_map(path, text) if is_code else None
    suffix_lower = path.suffix.lower()
    if suffix_lower == ".jsonc":
      comment_map = {}
      for comment_text, first, _ in slash_comments(text):
        for offset, comment_line in enumerate(comment_text.splitlines()):
          comment_map.setdefault(first + offset, []).append(comment_line)
      line_pairs = sorted(
        (number, "\n".join(parts)) for number, parts in comment_map.items()
      )
    elif (
      suffix_lower in {".sql", ".dbml"} or is_jinja_file(path) or is_env_file(path)
    ) and prose_map is not None:
      line_pairs = sorted(prose_map.items())
    else:
      line_pairs = list(enumerate(lines, 1))
    fenced = (
      fenced_lines(lines) if path.suffix.lower() in {".md", ".markdown"} else set()
    )
    for number, line in line_pairs:
      if number in fenced or rotation_legend(line):
        continue
      excluded = file_ids | line_ids[number - 1]
      visible = mask_protected_spans(
        MARKER.sub(lambda match: " " * len(match[0]), line)
      )
      prose_visible = None
      if is_code and prose_map is not None:
        raw_prose = prose_map.get(number)
        if raw_prose is not None:
          prose_visible = mask_protected_spans(
            MARKER.sub(lambda match: " " * len(match[0]), raw_prose)
          )
      for name, pattern, use in ROTATIONS:
        code = RULE_IDS[name]
        if suppressed(code, excluded, name):
          continue
        target_line = prose_visible if is_code else visible
        if not target_line:
          continue
        for word in sorted(set(re.findall(pattern, target_line, flags=re.IGNORECASE))):
          if name in KEEP_LOWER and word == use:
            continue
          findings.append(format_finding(path, number, code, f"{word} -> {use}", line))
    if not is_code:
      for _, _, _, numbers in prose_blocks(text):
        for previous, current in pairwise(numbers):
          if current != previous + 1:
            continue
          if "NMO901" in file_ids | line_ids[previous - 1] | line_ids[current - 1]:
            continue
          left = mask_protected_spans(lines[previous - 1])
          right = mask_protected_spans(lines[current - 1])
          match = re.search(
            r"(?<![A-Za-z0-9])pull[ \t]*\n[ \t]*requests?(?![A-Za-z0-9])",
            left + "\n" + right,
            flags=re.IGNORECASE,
          )
          if match:
            word = " ".join(match.group(0).split())
            findings.append(
              format_finding(
                path, previous, "NMO901", f"{word} -> PR", lines[previous - 1]
              )
            )
  return findings, marks


def format_paths(targets, ignores, out=None):
  """Rewrite every rotation in place and print each changed line before and after."""
  out = out if out is not None else sys.stdout
  changed = 0
  for path in walk(targets, ignores):
    text = text_file(path)
    if text is None:
      continue
    lines = text.split("\n")
    with file_scope(path, text):
      file_ids, line_ids, _ = exclusions(path, lines)
      the_cap = nemo_config.ACTIVE_CONFIG.get("the_density_cap", THE_DENSITY_CAP)
      min_the = nemo_config.ACTIVE_CONFIG.get("min_the_count", MIN_THE_COUNT)
    is_code = is_code_file(path)
    prose_map = _prose_line_map(path, text) if is_code else None
    block_lines = {}
    for start_line, _, _, line_numbers in prose_blocks(text):
      block_lines.setdefault(start_line, set()).update(line_numbers)
    dense_lines = set()
    for row_line, _, _ in prose_the_density(text, cap=the_cap, min_the=min_the):
      group = block_lines.get(row_line, {row_line})
      if not any("NMO902" in (file_ids | line_ids[ln - 1]) for ln in group):
        dense_lines.update(group)
    rewritten, touched = [], False
    fenced = (
      fenced_lines(lines) if path.suffix.lower() in {".md", ".markdown"} else set()
    )
    for number, line in enumerate(lines, 1):
      if number in fenced or rotation_legend(line):
        rewritten.append(line)
        continue
      suppressed = set(file_ids | line_ids[number - 1])
      if is_code:
        prose = prose_map.get(number, "") if prose_map is not None else ""
        changed_line = line
        for fragment in prose.splitlines():
          if fragment and changed_line.count(fragment) == 1:
            rotated_fragment = rotate(fragment, suppressed)
            if number in dense_lines and "NMO902" not in suppressed:
              rotated_fragment = collapse_list_articles(rotated_fragment)
            changed_line = changed_line.replace(fragment, rotated_fragment, 1)
        if changed_line != line:
          print(f"{path}:{number}: -{line}", file=out)
          print(f"{path}:{number}: +{changed_line}", file=out)
          changed += 1
          touched = True
        rewritten.append(changed_line)
        continue
      collapse_the = number in dense_lines and "NMO902" not in suppressed
      parts, start = [], 0
      for marker in MARKER.finditer(line):
        seg = rotate(line[start : marker.start()], suppressed)
        if collapse_the:
          seg = collapse_list_articles(seg)
        parts.extend((seg, marker[0]))
        start = marker.end()
      tail = rotate(line[start:], suppressed)
      if collapse_the:
        tail = collapse_list_articles(tail)
      parts.append(tail)
      rotated = "".join(parts)
      if rotated != line:
        print(f"{path}:{number}: -{line}", file=out)
        print(f"{path}:{number}: +{rotated}", file=out)
        changed += 1
        touched = True
      rewritten.append(rotated)
    if touched:
      path.write_text("\n".join(rewritten), encoding="utf-8", newline="")
  return changed


def prose_review(path, text, context, paragraph_cap, min_the_override=None):
  """Return unsuppressed measurable candidates for one explicit text scope."""
  lines = text.splitlines()
  file_ids, line_ids, _ = exclusions(path, lines)
  block_lines = {}
  for start_line, _, _, line_numbers in prose_blocks(text):
    block_lines.setdefault(start_line, set()).update(line_numbers)

  def rule_suppressed(code, number):
    if code in LINE_PROSE_RULE_IDS:
      return 1 <= number <= len(line_ids) and suppressed(code, line_ids[number - 1])
    return any(
      suppressed(code, line_ids[ln - 1])
      for ln in block_lines.get(number, (number,))
      if 1 <= ln <= len(line_ids)
    )

  findings = []
  sentences, paragraphs = prose_counts(text)
  code = PROSE_RULE_IDS["semicolon"]
  if not suppressed(code, file_ids):
    for number, column, count in prose_semicolons(text):
      if not suppressed(code, line_ids[number - 1]):
        findings.append(
          {
            "rule": code,
            "path": str(path),
            "line": number,
            "column": column,
            "count": count,
            "cap": 0,
            "status": "review",
          }
        )
  sentence_caps = {
    "instruction": nemo_config.ACTIVE_CONFIG.get(
      "instruction_sentence_cap", SENTENCE_CAPS["instruction"]
    ),
    "description": nemo_config.ACTIVE_CONFIG.get(
      "description_sentence_cap", SENTENCE_CAPS["description"]
    ),
  }
  cap = sentence_caps.get(context, sentence_caps["instruction"])
  code = PROSE_RULE_IDS["sentence"]
  if not suppressed(code, file_ids):
    for number, column, count in sentences:
      if count > cap and not suppressed(code, line_ids[number - 1]):
        findings.append(
          {
            "rule": code,
            "path": str(path),
            "line": number,
            "column": column,
            "count": count,
            "cap": cap,
            "status": "review",
          }
        )
  for key, detector in DETECTORS:
    code = PROSE_RULE_IDS[key]
    status = "manual_review" if code in ADVISORY_RULE_IDS else "review"
    if not suppressed(code, file_ids):
      for number, column, count in detector(text):
        if not rule_suppressed(code, number):
          findings.append(
            {
              "rule": code,
              "path": str(path),
              "line": number,
              "column": column,
              "count": count,
              "cap": 0,
              "status": status,
            }
          )
  code = PROSE_RULE_IDS["paragraph"]
  if not suppressed(code, file_ids):
    for item in paragraphs:
      number, count, kind = item if len(item) == 3 else (*item, "paragraph")
      if kind == "heading":
        cap = nemo_config.ACTIVE_CONFIG.get(
          "heading_sentence_cap", HEADING_SENTENCE_CAP
        )
        status = "review"
      elif kind == "list":
        cap = nemo_config.ACTIVE_CONFIG.get("list_sentence_cap", LIST_SENTENCE_CAP)
        status = "review"
      elif kind == "blockquote":
        cap = paragraph_cap
        status = "manual_review"
      else:
        cap = paragraph_cap
        status = "review"
      if count > cap and not rule_suppressed(code, number):
        findings.append(
          {
            "rule": code,
            "path": str(path),
            "line": number,
            "column": 1,
            "count": count,
            "cap": cap,
            "kind": kind,
            "status": status,
          }
        )
  code = PROSE_RULE_IDS["the_density"]
  the_cap = nemo_config.ACTIVE_CONFIG.get("the_density_cap", THE_DENSITY_CAP)
  min_the = (
    min_the_override
    if min_the_override is not None
    else nemo_config.ACTIVE_CONFIG.get("min_the_count", MIN_THE_COUNT)
  )
  if not suppressed(code, file_ids):
    for number, column, density in prose_the_density(
      text, cap=the_cap, min_the=min_the
    ):
      if not rule_suppressed(code, number):
        findings.append(
          {
            "rule": code,
            "path": str(path),
            "line": number,
            "column": column,
            "count": density,
            "cap": the_cap,
            "status": "manual_review",
          }
        )
  return findings


MD_LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")


def docs_drift_findings(path, text, root=None):
  """Check Markdown files for broken local relative links during audits."""
  if path.suffix.lower() not in {".md", ".mdx"}:
    return []
  findings = []
  for index, line, state in fence_states(text.splitlines()):
    if state != "text":
      continue
    number = index + 1
    visible = re.sub(
      r"(`+)(?:(?!\1).)+?\1",
      lambda match: " " * len(match.group(0)),
      blank_inline_comments(line),
    )
    for match in MD_LINK_RE.finditer(visible):
      raw_target = match.group(1).strip()
      if not raw_target or raw_target.startswith("<"):
        continue
      target = raw_target.split()[0].split("#", 1)[0].split("?", 1)[0].strip()
      if (
        not target
        or "://" in target
        or target.startswith(("#", "mailto:", "data:", "javascript:", "/"))
        or "<" in target
        or ">" in target
      ):
        continue
      candidates = [path.parent / target]
      if root is not None:
        candidates.append(Path(root) / target)
      if not any(candidate.exists() for candidate in candidates):
        findings.append(
          format_finding(
            str(path),
            number,
            "docs-drift",
            f"missing link target: {target}",
            line,
            status="manual_review",
          )
        )
  return findings


def source_prose(path, text, context, paragraph_cap):
  """Check extracted code prose while retaining physical source locations."""
  with file_scope(path, text):
    return _source_prose(path, text, context, paragraph_cap)


def _source_prose(path, text, context, paragraph_cap):
  if context == "unknown" and (
    path.name in {"README.md", "CHANGELOG.md", "INSTALL.md"} or "docs" in path.parts
  ):
    context = "description"
  code_file = is_code_file(path)
  if code_file:
    spans = prose_spans(path, text)
  elif path.suffix in {".json", ".webmanifest", ".csv", ".lock"}:
    spans = []
  else:
    spans = [(text, 1, len(text.splitlines()))]
  wf_lines = (
    {ln for _, ln, _ in workflow_name_spans(text)}
    if is_workflow_yaml(path, text)
    else set()
  )
  lines = text.splitlines()
  file_ids, line_ids, _ = exclusions(path, lines)
  findings = []
  if code_file:
    code = PROSE_RULE_IDS["comment_block"]
    comment_cap = nemo_config.ACTIVE_CONFIG.get("comment_block_cap", COMMENT_BLOCK_CAP)
    if not suppressed(code, file_ids):
      for start, count in comment_blocks(path, text):
        if count > comment_cap and not suppressed(
          code, set().union(*line_ids[start - 1 : start - 1 + count])
        ):
          findings.append(
            {
              "rule": code,
              "path": str(path),
              "line": start,
              "column": 1,
              "count": count,
              "cap": comment_cap,
              "status": "review",
            }
          )
  for value, first, last in spans:
    cleaned_span = MARKER_SPAN.sub(lambda match: " " * len(match[0]), value)
    span_blocks = {}
    for start_line, _, _, line_numbers in prose_blocks(cleaned_span):
      span_blocks.setdefault(start_line, set()).update(line_numbers)
    span_min_the = 1 if (first == last and first in wf_lines) else None
    for row in prose_review(
      path, cleaned_span, context, paragraph_cap, min_the_override=span_min_the
    ):
      local_line = row["line"]
      if len(value.splitlines()) > last - first + 1:
        row["line"] = first
        phys_lines = range(first, last + 1)
      elif row["rule"] in LINE_PROSE_RULE_IDS:
        row["line"] = local_line + first - 1
        phys_lines = (row["line"],)
      else:
        row["line"] = local_line + first - 1
        phys_lines = [
          ln + first - 1 for ln in span_blocks.get(local_line, (local_line,))
        ]
      ids = set(file_ids)
      for ln in phys_lines:
        if 1 <= ln <= len(line_ids):
          ids |= line_ids[ln - 1]
      if not suppressed(row["rule"], ids):
        findings.append(row)
  if path.suffix.lower() in {".js", ".mjs", ".cjs"}:
    code = PROSE_RULE_IDS["prose_dash"]
    if not suppressed(code, file_ids):
      seen_lines = {row["line"] for row in findings if row["rule"] == code}
      for number, line in enumerate(lines, 1):
        if number in seen_lines or suppressed(code, line_ids[number - 1]):
          continue
        visible = MARKER_SPAN.sub(lambda match: " " * len(match[0]), line)
        matches = list(UI_STRING_DASH_RE.finditer(visible))
        if matches:
          findings.append(
            {
              "rule": code,
              "path": str(path),
              "line": number,
              "column": matches[0].start() + 1,
              "count": len(matches),
              "cap": 0,
              "status": "manual_review",
            }
          )
  suffix = path.suffix.lower()
  if suffix in {".js", ".mjs", ".cjs", ".html", ".htm"}:
    code = PROSE_RULE_IDS["padded_ui_label"]
    if not suppressed(code, file_ids):
      attr_spans = (
        html_attr_spans(text)
        if suffix in {".html", ".htm"} and not is_jinja_file(path)
        else []
      )
      seen_ui = set()
      ui_spans = []
      for label_text, first, last in [*attr_spans, *ui_label_spans(path, text)]:
        if (label_text, first) not in seen_ui:
          seen_ui.add((label_text, first))
          ui_spans.append((label_text, first, last))
      nmu_cap = int(
        nemo_config.ACTIVE_CONFIG.get("nmu100_max_words") or NMU100_MAX_WORDS
      )
      for ln, label_text, word, word_count in nmu100_findings(ui_spans, cap=nmu_cap):
        if 0 < ln <= len(line_ids) and suppressed(code, line_ids[ln - 1]):
          continue
        findings.append(
          {
            "rule": code,
            "path": str(path),
            "line": ln,
            "column": 1,
            "text": label_text,
            "word": word,
            "count": word_count,
            "cap": nmu_cap,
            "status": "review",
          }
        )
  if suffix in NMU200_SUFFIXES:
    code = NMU_RULE_IDS["byte_unit"]
    if not suppressed(code, file_ids):
      for ln, label_text, scale in nmu200_findings(path, text):
        if 0 < ln <= len(line_ids) and suppressed(code, line_ids[ln - 1]):
          continue
        findings.append(
          {
            "rule": code,
            "path": str(path),
            "line": ln,
            "column": 1,
            "text": label_text,
            "scale": scale,
            "count": 1,
            "cap": 0,
            "status": "review",
          }
        )
  return findings


def prose_main(argv=None):
  parser = argparse.ArgumentParser(description="Review explicitly scoped prose counts.")
  parser.add_argument("targets", nargs="+")
  parser.add_argument(
    "--context", choices=[*SENTENCE_CAPS, "unknown"], default="unknown"
  )
  parser.add_argument("--paragraph-cap", type=int, default=PARAGRAPH_CAP)
  arguments = parser.parse_args(argv)
  if not 0 < arguments.paragraph_cap <= PARAGRAPH_CAP:
    parser.error(f"--paragraph-cap must be between 1 and {PARAGRAPH_CAP}")
  for target in arguments.targets:
    if not Path(target).exists():
      parser.error(f"target does not exist: {target}")
  findings, coverage, errors = [], [], []
  for path in walk(arguments.targets, []):
    text = text_file(path)
    coverage.append(
      {
        "path": str(path),
        "context": arguments.context,
        "sentences": "checked"
        if text is not None and arguments.context in {*SENTENCE_CAPS, "unknown"}
        else "not_checked",
        "paragraphs": "checked" if text is not None else "not_checked",
      }
    )
    if text is not None:
      try:
        findings.extend(
          source_prose(path, text, arguments.context, arguments.paragraph_cap)
        )
      except (
        SyntaxError,
        tokenize.TokenError,
        OSError,
        ValueError,
        subprocess.SubprocessError,
        RuntimeError,
      ) as error:
        coverage[-1].update(
          sentences="not_checked", paragraphs="not_checked", reason="parse_error"
        )
        errors.append(f"{path}: {type(error).__name__}: {error}")
  print(json.dumps({"findings": findings, "coverage": coverage}))
  if errors:
    print("\n".join(errors), file=sys.stderr)
    return 2
  return int(bool(findings))


def review_tests_main(argv=None):
  parser = argparse.ArgumentParser(
    description="Review explicitly scoped test assertions and waits."
  )
  parser.add_argument("targets", nargs="+")
  args = parser.parse_args(argv)
  for target in args.targets:
    if not Path(target).exists():
      parser.error(f"target does not exist: {target}")
  try:
    result = review_tests(args.targets)
  except ValueError as error:
    parser.error(str(error))
  print(json.dumps(result))
  return (
    2
    if result["errors"]
    else int(any(row.get("status") != "manual_review" for row in result["findings"]))
  )


def main(argv=None):
  # Windows consoles default to cp1252. Force UTF-8 output so findings with any
  # decoded character print instead of crashing the report.
  for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
      stream.reconfigure(encoding="utf-8", errors="replace")
  argv = list(sys.argv[1:] if argv is None else argv)
  if argv[:1] == ["prose"]:
    return prose_main(argv[1:])
  if argv[:1] == ["review-tests"]:
    return review_tests_main(argv[1:])
  if argv[:1] in (["audit"], ["collect"]):
    argv = ["--audit", *argv[1:]]
  parser = argparse.ArgumentParser(description="Check prose and test candidates.")
  parser.add_argument("targets", nargs="*", default=["."])
  parser.add_argument(
    "--ignore",
    action="append",
    default=[],
    help="skip a directory or file, relative to the target",
  )
  parser.add_argument(
    "-v",
    "--verbose",
    action="store_true",
    help="print each file as it is scanned and processed",
  )
  parser.add_argument(
    "--ignores", action="store_true", help="list every nonemo marker instead"
  )
  parser.add_argument(
    "--audit",
    action="store_true",
    help="list every nonemo marker and manual-review finding",
  )
  parser.add_argument(
    "--format", action="store_true", help="apply the rotations in place"
  )
  parser.add_argument(
    "--selftest", action="store_true", help="run built-in self-tests and exit"
  )
  parser.add_argument("--context", choices=[*SENTENCE_CAPS, "unknown"], default=None)
  parser.add_argument("--paragraph-cap", type=int, default=None)
  parser.add_argument("--test-helper", action="append", type=Path, default=[])
  parser.add_argument("--config", type=Path, default=None)
  parser.add_argument("--no-config", action="store_true")
  arguments = parser.parse_args(argv)
  if arguments.selftest:
    assert rotate("Transmit the kind.") == "Send the type."
    sample = prose_review(
      Path("sample.md"), "Start; stop.\n", "description", PARAGRAPH_CAP
    )
    assert any(row["rule"] == "STE100" for row in sample)
    return 0
  targets = arguments.targets or ["."]
  for target in targets:
    if not Path(target).exists():
      parser.error(f"target does not exist: {target}")
  try:
    nemo_config.BASE_CONFIG = load_config(
      targets, arguments.config, arguments.no_config
    )
  except (OSError, ValueError, tomllib.TOMLDecodeError) as error:
    parser.error(str(error))
  nemo_config.ACTIVE_CONFIG = nemo_config.BASE_CONFIG
  context = (
    arguments.context
    if arguments.context is not None
    else (nemo_config.ACTIVE_CONFIG.get("context") or "unknown")
  )
  paragraph_cap = (
    arguments.paragraph_cap
    if arguments.paragraph_cap is not None
    else (nemo_config.ACTIVE_CONFIG.get("paragraph_cap") or PARAGRAPH_CAP)
  )
  if not 0 < paragraph_cap <= PARAGRAPH_CAP:
    parser.error(f"--paragraph-cap must be between 1 and {PARAGRAPH_CAP}")
  test_helpers = [
    *nemo_config.ACTIVE_CONFIG.get("test_helpers", ()),
    *arguments.test_helper,
  ]
  for helper in test_helpers:
    if not Path(helper).is_file():
      parser.error(f"test helper does not exist: {helper}")
  if arguments.format:
    try:
      changed = format_paths(targets, arguments.ignore)
    except ValueError as error:
      parser.error(str(error))
    print(f"{changed} lines rotated", file=sys.stderr)
    return 0
  try:
    findings, marks = scan(
      targets, arguments.ignore, audit=arguments.audit, verbose=arguments.verbose
    )
  except ValueError as error:
    parser.error(str(error))
  if arguments.ignores:
    print("\n".join(marks))
    return 0
  errors, tests = [], []
  helpers = {Path(path).resolve() for path in test_helpers}
  files = list(walk([*targets, *test_helpers], arguments.ignore))
  total = len(files)

  def process_one(path):
    result = {"test": None, "error": None, "rows": [], "text": None}
    text = text_file(path)
    result["text"] = text
    try:
      if is_test_file(path, text or "", helpers):
        result["test"] = str(path)
      if text is None:
        return result
      file_cfg = file_config(path, text)
      result["rows"] = source_prose(
        path,
        text,
        context
        if arguments.context is not None
        else (file_cfg.get("context") or "unknown"),
        paragraph_cap
        if arguments.paragraph_cap is not None
        else (file_cfg.get("paragraph_cap") or PARAGRAPH_CAP),
      )
    except (
      SyntaxError,
      tokenize.TokenError,
      OSError,
      ValueError,
      configparser.Error,
      subprocess.SubprocessError,
      RuntimeError,
      RecursionError,
    ) as error:
      result["error"] = f"{path}: {type(error).__name__}: {error}"
    return result

  results = {}
  skipped = []
  workers = min(8, (os.cpu_count() or 4))
  file_timeout = 10.0
  pending = {}
  next_index = 0
  jobs = queue.Queue(maxsize=workers)

  def worker():
    while True:
      job = jobs.get()
      if job is None:
        return
      future, path = job
      if not future.set_running_or_notify_cancel():
        continue
      try:
        future.set_result(process_one(path))
      except BaseException as error:
        future.set_exception(error)

  for _ in range(workers):
    threading.Thread(target=worker, daemon=True).start()

  def submit_more(count):
    nonlocal next_index
    for _ in range(count):
      if next_index >= len(files):
        return
      path = files[next_index]
      if arguments.verbose:
        print(f"start {path}", file=sys.stderr, flush=True)
      future = Future()
      jobs.put_nowait((future, path))
      pending[future] = (path, time.monotonic() + file_timeout)
      next_index += 1

  submit_more(workers)
  done_count = 0
  while pending:
    timeout = max(
      min(deadline for _, deadline in pending.values()) - time.monotonic(), 0
    )
    done, _ = wait(list(pending), timeout=timeout, return_when=FIRST_COMPLETED)
    now = time.monotonic()
    expired = [
      future
      for future, (_, deadline) in pending.items()
      if future not in done and deadline <= now
    ]
    for future in done | set(expired):
      path = pending[future][0]
      if arguments.verbose:
        outcome = "timeout" if future in expired else "done"
        print(f"{outcome} {path}", file=sys.stderr, flush=True)
      del pending[future]
      if future in expired:
        future.cancel()
        skipped.append(path)
      else:
        try:
          results[path] = future.result()
        except Exception as error:
          results[path] = {
            "test": None,
            "error": f"{path}: {type(error).__name__}: {error}",
            "rows": [],
            "text": None,
          }
      done_count += 1
      print(".", end="", file=sys.stderr, flush=True)
      if done_count % 25 == 0 or done_count == total:
        print(f" [{done_count * 100 // total:>3}%]", file=sys.stderr, flush=True)
    retained = []
    while True:
      try:
        job = jobs.get_nowait()
      except queue.Empty:
        break
      if not job[0].cancelled():
        retained.append(job)
    for job in retained:
      jobs.put_nowait(job)
    submit_more(len(done) + len(expired))
  if skipped:
    print(
      "\nSkipped (no result within 10s):\n" + "\n".join(str(path) for path in skipped),
      file=sys.stderr,
    )
  for _ in range(workers):
    jobs.put_nowait(None)
  for path in files:
    result = results.get(path) or {
      "test": None,
      "error": None,
      "rows": [],
      "text": None,
    }
    if result["test"]:
      tests.append(result["test"])
    if result["error"]:
      errors.append(result["error"])
      continue
    text = result["text"]
    if text is None:
      continue
    lines = text.splitlines()
    findings.extend(
      format_finding(
        row["path"],
        row["line"],
        row["rule"],
        describe_finding(row),
        lines[row["line"] - 1] if 0 < row["line"] <= len(lines) else None,
        status=row.get("status"),
      )
      for row in result["rows"]
    )
    if arguments.audit:
      findings.extend(
        docs_drift_findings(path, text, nemo_config.ACTIVE_CONFIG.get("root"))
      )
  try:
    result = review_tests(tests)
  except ValueError as error:
    parser.error(str(error))
  for row in result["findings"]:
    test_lines = (text_file(Path(row["path"])) or "").splitlines()
    findings.append(
      format_finding(
        row["path"],
        row["line"],
        row["rule"],
        row["evidence"],
        test_lines[row["line"] - 1] if 0 < row["line"] <= len(test_lines) else None,
        status=row.get("status"),
      )
    )
  for row in result["coverage"]:
    if row["status"] != "checked":
      errors.append(f"{row['path']}: tests not checked: {row['reason']}")
  errors.extend(f"{row['path']}: {row['type']}" for row in result["errors"])
  if arguments.audit:
    print(
      "\n".join(
        audit_lines(marks, findings, {*ADVISORY_RULE_IDS, *TEST_RULE_IDS.values()})
      )
    )
    if errors:
      print("\n".join(errors), file=sys.stderr)
      return 2
    return 0
  if tests:
    print(
      "Test scope: static paths and declarations. Dynamic helpers may be unresolved.",
      file=sys.stderr,
    )
  print("\n".join(findings) + ("\n" + format_summary(findings) if findings else ""))
  if errors:
    print("\n".join(errors), file=sys.stderr)
    return 2
  return int(any(not is_advisory(finding) for finding in findings))


if __name__ == "__main__":
  sys.exit(main())
