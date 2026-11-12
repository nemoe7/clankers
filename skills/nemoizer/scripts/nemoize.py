# nonemo: NMO100
# nonemo: NMO901
"""Check prose and test candidates, rotate words, and collect exclusions."""

import argparse
import ast
import configparser
import fnmatch
import json
import os
import queue
import re
import shutil
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
  collect_markers,
)
from nemo_config import (
  HEADING_SENTENCE_CAP,
  LIST_SENTENCE_CAP,
  MIN_THE_COUNT,
  PARAGRAPH_CAP,
  SENTENCE_CAPS,
  THE_DENSITY_CAP,
  config_file_exclusions,
  file_config,
  file_scope,
  load_config,
)
from nemo_files import text_file, walk
from nemo_markdown import (
  blank_inline_comments,
  fence_states,
  fenced_lines,
  prose_block_matches,
  prose_blocks,
  prose_counts,
  prose_line_matches,
  prose_lines,
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
  KNOWN_RULE_IDS,
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
  run_node,
  slash_comments,
  ui_label_spans,
  workflow_name_spans,
)


def exclusions(path, lines, audit=False):
  """Collect every marker and the known rule IDs it suppresses."""
  file_ids, line_ids, marks = collect_markers(
    path, lines, KNOWN_RULE_IDS, ROTATIONS, audit=audit
  )
  return file_ids | config_file_exclusions(path), line_ids, marks


def suppressed(code, ids, name=None):
  """Return whether the active marker set suppresses a rule ID."""
  return code in ids


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


PASSIVE_VOICE_RE = re.compile(
  r"\b(?:am|is|are|was|were|be|been|being)\s+"
  r"(?:(?:not|never|always|only|also|still|often|already)\s+)?"
  r"([a-z]{3,}ed|written|taken|given|made|done|kept|held|found|chosen|"
  r"known|shown|seen|built|sent|run|broken|spoken|stolen|hidden|driven|drawn|"
  r"forgiven|forgotten|frozen|grown|thrown|worn|torn)\b",
  re.IGNORECASE,
)
PASSIVE_STATE_ADJECTIVES = {
  "able",
  "alleged",
  "armed",
  "ashamed",
  "complicated",
  "concerned",
  "crowded",
  "disabled",
  "enabled",
  "expected",
  "experienced",
  "fixed",
  "interested",
  "isolated",
  "limited",
  "locked",
  "mixed",
  "needed",
  "pleased",
  "prepared",
  "related",
  "required",
  "reserved",
  "restricted",
  "satisfied",
  "scoped",
  "shared",
  "signed",
  "sorted",
  "staged",
  "structured",
  "supported",
  "supposed",
  "tired",
  "tracked",
  "trusted",
  "typed",
  "unchanged",
  "unexpected",
  "unmodified",
  "unsupported",
  "unused",
}


def prose_passives(text):
  """Find passive-voice constructions across prose blocks outside code fences and code spans."""
  return prose_block_matches(
    text,
    lambda clean: [
      match
      for match in PASSIVE_VOICE_RE.finditer(clean)
      if match.group(1).lower() not in PASSIVE_STATE_ADJECTIVES
      or re.match(r"\s+by\b", clean[match.end() :], re.IGNORECASE)
    ],
  )


PHRASAL_VERB_RE = re.compile(
  r"\b(?:carry\s+out|set\s+up|tear\s+down|spin\s+up|hand\s+over|fill\s+out|"
  r"find\s+out|figure\s+out|point\s+out|turn\s+on|turn\s+off|look\s+up|"
  r"back\s+up|clean\s+up|plug\s+in|bail\s+out|opt\s+in|opt\s+out|roll\s+back|"
  r"wire\s+up|hook\s+up|boot\s+up|shut\s+down)\b",
  re.IGNORECASE,
)
ELLIPSIS_RE = re.compile(
  r",\s+(?:and|or)\s+(?:is|are|was|were|has|have|had)\b|"
  r"\b(?:the|a|an|this|that|these|those|its|their|our|your)\s+[a-z]{3,}\s+is\s+([a-z]{3,}ed)\s+and\s+([a-z]{3,}ed)\b",
  re.IGNORECASE,
)
SERIAL_COMMA_RE = re.compile(
  r"\b([A-Za-z0-9_'-]+), ([A-Za-z0-9_'-]+) (?:and|or) "
  r"([A-Za-z0-9_'-]+)(?=[.!?:;)]|\s|$)"
)
MIXED_SLASH_OR_RE = re.compile(
  r"\b([A-Za-z0-9_'-]+) / ([A-Za-z0-9_'-]+),? (?:and|or) "
  r"([A-Za-z0-9_'-]+)(?=[.!?:;)]|\s|$)|"
  r"\b([A-Za-z0-9_'-]+) (?:and|or) ([A-Za-z0-9_'-]+) / "
  r"([A-Za-z0-9_'-]+)(?=[.!?:;)]|\s|$)",
  re.IGNORECASE,
)
CLAUSE_OPENERS = {
  "when",
  "if",
  "after",
  "before",
  "while",
  "because",
  "since",
  "unless",
  "where",
  "once",
  "in",
  "on",
  "for",
  "from",
  "with",
  "without",
  "by",
  "at",
  "to",
  "under",
  "during",
  "and",
  "or",
  "not",
  "the",
  "a",
  "an",
  "that",
  "which",
  "who",
  "whose",
  "whether",
  "never",
  "always",
  "only",
  "also",
  "either",
  "neither",
  "both",
  "such",
  "as",
  "so",
  "yet",
  "but",
  "nor",
  "then",
  "thus",
  "instead",
  "rather",
  "directly",
  "indented",
  "all",
  "them",
}


def prose_phrasal_verbs(text):
  return prose_block_matches(text, lambda clean: list(PHRASAL_VERB_RE.finditer(clean)))


def prose_ellipsis(text):
  return prose_block_matches(
    text,
    lambda clean: [
      match
      for match in ELLIPSIS_RE.finditer(clean)
      if not (
        match.group(1)
        and match.group(2)
        and (
          match.group(1).lower() in PASSIVE_STATE_ADJECTIVES
          or match.group(2).lower() in PASSIVE_STATE_ADJECTIVES
        )
      )
    ],
  )


def _serial_comma_hits(clean):
  stripped = re.sub(r"\[[^\]]*\]\([^)]*\)", lambda item: " " * len(item[0]), clean)
  hits = [
    match
    for match in SERIAL_COMMA_RE.finditer(stripped)
    if not (
      {match.group(1).lower(), match.group(2).lower(), match.group(3).lower()}
      & CLAUSE_OPENERS
    )
    and not clean[: match.start()].rstrip().lower().endswith("to")
  ]
  hits.extend(
    match
    for match in MIXED_SLASH_OR_RE.finditer(stripped)
    if not ({word.lower() for word in match.groups() if word} & CLAUSE_OPENERS)
  )
  hits.sort(key=lambda match: match.start())
  return hits


def prose_serial_commas(text):
  return prose_block_matches(text, _serial_comma_hits)


def prose_semicolons(text):
  """Find semicolons on prose lines outside code fences, code spans, and comments."""
  semicolons = []
  for number, clean in prose_lines(text):
    clean = re.sub(
      r"&(?:#\d+|#x[0-9a-fA-F]+|[A-Za-z][A-Za-z0-9]*);",
      lambda match: " " * len(match[0]),
      clean,
    )
    if ";" in clean:
      semicolons.append((number, clean.index(";") + 1, clean.count(";")))
  return semicolons


DANGLING_CONJUNCTION_RE = re.compile(
  r"^\s*(?:[-*+]|\d+[.)])\s+.*[,;]\s+(?:and|or)[.;:]?\s*$",
  re.IGNORECASE,
)
NOMINALIZATION_RE = re.compile(
  r"\b(?:make|made|makes|making)\s+(?:a\s+|an\s+|the\s+)?"
  r"(?:decision|determination|adjustment|modification|selection|recommendation|assumption)\b|"
  r"\b(?:perform|performed|performs|performing|conduct|conducted|conducts|conducting)\s+"
  r"(?:a\s+|an\s+|the\s+)?"
  r"(?:validation|verification|investigation|analysis|assessment|evaluation|examination|inspection|comparison)\b|"
  r"\b(?:provide|provided|provides|providing|give|gave|gives|giving)\s+"
  r"(?:a\s+|an\s+|the\s+)?(?:description|explanation|indication|illustration)\b|"
  r"\b(?:is|are|was|were)\s+indicative\s+of\b|"
  r"\b(?:for\s+the\s+purpose\s+of|with\s+the\s+aim\s+of)\b",
  re.IGNORECASE,
)
COMPOUND_INSTRUCTION_RE = re.compile(
  r"\b(?:click|press|tap|select|open|close|save|delete|run|execute)\s+"
  r"[^.!?;,]{2,40},\s+and\s+then\s+"
  r"(?:click|press|tap|select|open|close|save|delete|run|execute)\b",
  re.IGNORECASE,
)
NOUN_CLUSTER_WORD = (
  r"(?:system|server|client|user|interface|configuration|management|process|service|"
  r"module|component|pipeline|workflow|database|connection|request|response|handler|"
  r"controller|policy|validation|execution|parameter|environment|storage|session|"
  r"token|state|schema|gateway|proxy|adapter|provider|registry)"
)
NOUN_CLUSTER_RE = re.compile(
  rf"\b{NOUN_CLUSTER_WORD}(?:\s+{NOUN_CLUSTER_WORD}){{3,}}\b",
  re.IGNORECASE,
)
SYNONYM_CLUSTER_RE = re.compile(
  r"\b(?:rules?\s+(?:and|or)\s+regulations?|null\s+and\s+void|each\s+and\s+every|"
  r"first\s+and\s+foremost|basic\s+and\s+fundamental|various\s+and\s+sundry|"
  r"checks?\s+and\s+validations?)\b",
  re.IGNORECASE,
)
COMPOUND_TENSE_RE = re.compile(
  r"\b(?:will\s+have\s+[a-z]{3,}ed|would\s+have\s+[a-z]{3,}ed|"
  r"(?:has|have|had)\s+been\s+[a-z]{3,}ing)\b",
  re.IGNORECASE,
)
STAGED_FRAME_RE = re.compile(
  r"\b(?:let's\s+dive\s+in|without\s+further\s+ado|in\s+today's\s+fast-paced\s+world|"
  r"in\s+conclusion,\s+by\s+leveraging|all\s+things\s+considered,\s+it\s+is\s+clear|"
  r"hope\s+this\s+helps)\b",
  re.IGNORECASE,
)
STACKED_QUALIFIER_RE = re.compile(
  r"\b(?:very\s+unique|completely\s+essential|absolutely\s+critical|"
  r"truly\s+remarkable|undeniably\s+important|extremely\s+crucial|highly\s+pivotal)\b",
  re.IGNORECASE,
)
AI_VOCABULARY_RE = re.compile(
  r"\b(?:delve|delves|delved|delving|tapestry|testament\s+to|beacon\s+of|"
  r"paradigm\s+shift|game-changer|groundbreaking|synergy|unleash(?:ing)?|"
  r"elevate\s+your|foster(?:ing)?\s+innovation|realm\s+of)\b",
  re.IGNORECASE,
)
ARROW_RE = re.compile(r"\u2192")
CHATBOT_COURTESY_RE = re.compile(
  r"\b(?:as\s+an\s+ai(?:\s+language\s+model)?|"
  r"as\s+of\s+my\s+last\s+(?:knowledge\s+)?(?:update|cutoff)|"
  r"i\s+don't\s+have\s+access\s+to\s+real-time|certainly!\s+here\s+is|"
  r"sure\s+thing!\s+here)\b",
  re.IGNORECASE,
)
CURLY_QUOTE_RE = re.compile(r"[\u201c\u201d\u2018\u2019]")
NEGATIVE_CONTRAST_RE = re.compile(
  r"\bnot\s+(?:just|merely|simply)\s+[^,.!?;]{2,40},\s+but\s+"
  r"(?:rather|instead|also)?\s*[A-Za-z]",
  re.IGNORECASE,
)
APHORISM_RE = re.compile(
  r"\b(?:at\s+the\s+end\s+of\s+the\s+day\b|the\s+bottom\s+line\s+is\b|"
  r"it\s+goes\s+without\s+saying\b|key\s+takeaway:|why\s+this\s+matters:)",
  re.IGNORECASE,
)
RHETORICAL_SETUP_RE = re.compile(
  r"\b(?:you\s+might\s+be\s+wondering|have\s+you\s+ever\s+wondered|"
  r"some\s+critics\s+might\s+argue|what\s+if\s+i\s+told\s+you)\b",
  re.IGNORECASE,
)
PROSE_DASH_RE = re.compile(
  r"(?:[A-Za-z0-9]\u2014[A-Za-z0-9]|\s\u2013\s|\\u201[34])",
  re.IGNORECASE,
)
UI_STRING_DASH_RE = re.compile(
  r"""(['"`])(?:\\.|(?!\1)[^\r\n])*?(?:[\u2013\u2014]|\\u201[34])(?:\\.|(?!\1)[^\r\n])*?\1""",
  re.IGNORECASE,
)
VAGUE_ATTRIBUTION_RE = re.compile(
  r"\b(?:experts\s+agree\s+that|studies\s+have\s+shown\s+that|"
  r"researchers\s+say\s+that|industry\s+leaders\s+believe|"
  r"many\s+people\s+think\s+that)\b",
  re.IGNORECASE,
)
COPULA_AVOIDANCE_RE = re.compile(
  r"\b(?:serves\s+as\s+a|stands\s+as\s+a|boasts\s+a|"
  r"features\s+a\s+wide\s+array\s+of)\b",
  re.IGNORECASE,
)
BOLD_LABEL_BULLET_RE = re.compile(
  r"^\s*[-*+]\s+\*\*[A-Z][A-Za-z0-9]*(?:\s+[A-Z][A-Za-z0-9]*)?:\*\*"
)
EMOJI_CHAR = r"[\U0001F300-\U0001FAFF\u2600-\u27BF]"
CONSECUTIVE_EMOJI_RE = re.compile(rf"{EMOJI_CHAR}\s*{EMOJI_CHAR}")
SELF_NARRATION_RE = re.compile(
  r"\b(?:this\s+section\s+(?:covers|explains|describes|outlines)|"
  r"in\s+this\s+(?:document|section|guide),\s+we\s+will)\b",
  re.IGNORECASE,
)
WORDY_PHRASE_RE = re.compile(
  r"\b(?:in\s+order\s+to\s+[a-z]{2,}|prior\s+to|subsequent\s+to|"
  r"due\s+to\s+the\s+fact\s+that|in\s+the\s+event\s+that|by\s+means\s+of|"
  r"at\s+this\s+point\s+in\s+time|at\s+the\s+present\s+time|"
  r"(?:is|are|was|were)\s+(?:able\s+to|capable\s+of))\b",
  re.IGNORECASE,
)
ARCHAIC_CONNECTOR_RE = re.compile(
  r"\b(?:heretofore|herein(?:after)?|there(?:of|in|by)|where(?:by|in|of)|"
  r"aforementioned|pursuant\s+to|inter\s+alia)\b",
  re.IGNORECASE,
)
INLINE_LIST_RE = re.compile(
  r"(?:(?<!\w)\(1\)\s+\S.*?\s+\(2\)\s+\S.*?\s+\(3\)\s+\S|"
  r"(?<!\w)\(a\)\s+\S.*?\s+\(b\)\s+\S.*?\s+\(c\)\s+\S)",
  re.IGNORECASE,
)
DOUBLE_NEGATIVE_RE = re.compile(
  r"\b(?:not\s+(?:uncommon|unlikely|impossible|insignificant|unreasonable|"
  r"infrequent(?:ly)?|unavailable|unlike|unaware)|never\s+fails\s+to)\b",
  re.IGNORECASE,
)


def prose_dangling_conjunctions(text):
  return prose_line_matches(
    text, lambda clean: list(DANGLING_CONJUNCTION_RE.finditer(clean))
  )


def prose_nominalizations(text):
  return prose_block_matches(
    text, lambda clean: list(NOMINALIZATION_RE.finditer(clean))
  )


def prose_wordy_phrases(text):
  return prose_block_matches(
    text,
    lambda clean: list(WORDY_PHRASE_RE.finditer(clean)),
    skip_kinds=frozenset({"blockquote"}),
  )


def prose_archaic_connectors(text):
  return prose_block_matches(
    text, lambda clean: list(ARCHAIC_CONNECTOR_RE.finditer(clean))
  )


def prose_inline_lists(text):
  return prose_block_matches(text, lambda clean: list(INLINE_LIST_RE.finditer(clean)))


def prose_double_negatives(text):
  return prose_block_matches(
    text, lambda clean: list(DOUBLE_NEGATIVE_RE.finditer(clean))
  )


def prose_compound_instructions(text):
  return prose_block_matches(
    text, lambda clean: list(COMPOUND_INSTRUCTION_RE.finditer(clean))
  )


def prose_noun_clusters(text):
  return prose_block_matches(text, lambda clean: list(NOUN_CLUSTER_RE.finditer(clean)))


def prose_synonym_clusters(text):
  return prose_block_matches(
    text, lambda clean: list(SYNONYM_CLUSTER_RE.finditer(clean))
  )


def prose_compound_tenses(text):
  return prose_block_matches(
    text, lambda clean: list(COMPOUND_TENSE_RE.finditer(clean))
  )


def prose_staged_frames(text):
  return prose_block_matches(text, lambda clean: list(STAGED_FRAME_RE.finditer(clean)))


def prose_stacked_qualifiers(text):
  return prose_block_matches(
    text, lambda clean: list(STACKED_QUALIFIER_RE.finditer(clean))
  )


def prose_ai_vocabulary(text):
  return prose_block_matches(text, lambda clean: list(AI_VOCABULARY_RE.finditer(clean)))


def prose_arrows(text):
  return prose_line_matches(text, lambda clean: list(ARROW_RE.finditer(clean)))


def prose_chatbot_courtesy(text):
  return prose_block_matches(
    text, lambda clean: list(CHATBOT_COURTESY_RE.finditer(clean))
  )


def prose_curly_quotes(text):
  return prose_line_matches(text, lambda clean: list(CURLY_QUOTE_RE.finditer(clean)))


def prose_negative_contrasts(text):
  return prose_block_matches(
    text, lambda clean: list(NEGATIVE_CONTRAST_RE.finditer(clean))
  )


def prose_aphorisms(text):
  return prose_block_matches(text, lambda clean: list(APHORISM_RE.finditer(clean)))


def prose_rhetorical_setups(text):
  return prose_block_matches(
    text, lambda clean: list(RHETORICAL_SETUP_RE.finditer(clean))
  )


def prose_repeated_openers(text):
  """Find three consecutive sentences in a prose block with the same two-word opener."""
  rows = []
  for start_line, _, clean, _ in prose_blocks(text):
    sentences = [
      part.strip() for part in re.split(r"(?<=[.!?])\s+", clean) if part.strip()
    ]
    openers = []
    for sentence in sentences:
      words = re.findall(r"[A-Za-z]+", sentence)
      openers.append(
        f"{words[0].lower()} {words[1].lower()}" if len(words) >= 2 else ""
      )
    for pos in range(len(openers) - 2):
      if openers[pos] and openers[pos] == openers[pos + 1] == openers[pos + 2]:
        rows.append((start_line, 1, 1))
        break
  return rows


def prose_dashes(text):
  return prose_line_matches(text, lambda clean: list(PROSE_DASH_RE.finditer(clean)))


def prose_vague_attributions(text):
  return prose_block_matches(
    text, lambda clean: list(VAGUE_ATTRIBUTION_RE.finditer(clean))
  )


def prose_copula_avoidance(text):
  return prose_block_matches(
    text, lambda clean: list(COPULA_AVOIDANCE_RE.finditer(clean))
  )


def prose_bold_label_bullets(text):
  return prose_line_matches(
    text, lambda clean: list(BOLD_LABEL_BULLET_RE.finditer(clean))
  )


def prose_consecutive_emojis(text):
  return prose_line_matches(
    text, lambda clean: list(CONSECUTIVE_EMOJI_RE.finditer(clean))
  )


def prose_self_narration(text):
  return prose_block_matches(
    text, lambda clean: list(SELF_NARRATION_RE.finditer(clean))
  )


LIST_DETERMINER = r"(?:the|its|their|our|your|this|that|these|those)"
LIST_ITEM_TAIL = (
  r"(?:(?:[ \t]+(?!(?:the|its|their|our|your|this|that|these|those|and|or)\b)"
  r"[A-Za-z0-9_'/-]+){1,5}|[ \t]{2,})"
)
LIST_ITEM_PATTERN = rf"\b{LIST_DETERMINER}{LIST_ITEM_TAIL}"
MIXED_DETERMINER_LIST_RE = re.compile(
  rf"{LIST_ITEM_PATTERN}(?:,[ \t]+{LIST_ITEM_PATTERN})+"
  rf"(?:,?[ \t]+(?:and|or)[ \t]+{LIST_ITEM_PATTERN}|,[ \t]+{LIST_ITEM_PATTERN})",
  re.IGNORECASE,
)
LEADING_DETERMINER_RE = re.compile(
  rf"(?:^|,[ \t]+(?:(?:and|or)[ \t]+)?|[ \t]+(?:and|or)[ \t]+)({LIST_DETERMINER})\b",
  re.IGNORECASE,
)


def _mixed_list_the_discount(clean):
  """Return the number of leading 'the' hits discounted by 3+ item mixed-determiner lists."""
  discount = 0
  for match in MIXED_DETERMINER_LIST_RE.finditer(clean):
    determiners = [
      det.group(1).lower() for det in LEADING_DETERMINER_RE.finditer(match.group(0))
    ]
    if len(determiners) >= 3 and any(d != "the" for d in determiners):
      the_count = sum(1 for d in determiners if d == "the")
      if the_count > 1:
        discount += the_count - 1
  return discount


def prose_the_density(text, cap=THE_DENSITY_CAP, min_the=MIN_THE_COUNT):
  """Find prose blocks where 'the' appears at least min_the times and >= cap% of words."""
  rows = []
  for start_line, _, clean, _ in prose_blocks(text):
    words = re.findall(r"[A-Za-z0-9_'-]+", clean)
    hits = list(re.finditer(r"\bthe\b", clean, re.IGNORECASE))
    effective_hits = max(0, len(hits) - _mixed_list_the_discount(clean))
    if effective_hits >= min_the and words and hits:
      density = round(effective_hits * 100 / len(words))
      if density >= cap:
        rows.append((start_line, hits[0].start() + 1, density))
  return rows


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
  for key, detector in (
    ("dangling_conjunction", prose_dangling_conjunctions),
    ("nominalization", prose_nominalizations),
    ("wordy_phrase", prose_wordy_phrases),
    ("archaic_connector", prose_archaic_connectors),
    ("passive", prose_passives),
    ("phrasal", prose_phrasal_verbs),
    ("ellipsis", prose_ellipsis),
    ("compound_instruction", prose_compound_instructions),
    ("noun_cluster", prose_noun_clusters),
    ("synonym_cluster", prose_synonym_clusters),
    ("compound_tense", prose_compound_tenses),
    ("inline_list", prose_inline_lists),
    ("double_negative", prose_double_negatives),
    ("staged_frame", prose_staged_frames),
    ("stacked_qualifier", prose_stacked_qualifiers),
    ("ai_vocabulary", prose_ai_vocabulary),
    ("arrow", prose_arrows),
    ("chatbot_courtesy", prose_chatbot_courtesy),
    ("curly_quote", prose_curly_quotes),
    ("negative_contrast", prose_negative_contrasts),
    ("aphorism", prose_aphorisms),
    ("rhetorical_setup", prose_rhetorical_setups),
    ("repeated_opener", prose_repeated_openers),
    ("prose_dash", prose_dashes),
    ("vague_attribution", prose_vague_attributions),
    ("copula_avoidance", prose_copula_avoidance),
    ("bold_label_bullet", prose_bold_label_bullets),
    ("consecutive_emoji", prose_consecutive_emojis),
    ("self_narration", prose_self_narration),
    ("serial_comma", prose_serial_commas),
  ):
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


MEASUREMENTS = {
  "width",
  "clientwidth",
  "clientheight",
  "offsetwidth",
  "offsetheight",
  "scrollwidth",
  "scrollheight",
  "bytelength",
  "byte_length",
  "height",
  "timeout",
  "duration",
  "elapsed",
  "measure",
  "token_count",
  "byte_count",
  "size_bytes",
  "poll_wait_seconds",
  "timeout_seconds",
}
REAL_WAIT_CALLS = {"sleep", "time.sleep", "asyncio.sleep"}
CHANNELS = {"stdout", "stderr", "output", "out", "err"}
WEB_CHANNELS = {
  "stdout",
  "stderr",
  "output",
  "out",
  "err",
  "body",
  "html",
  "text",
  "data",
  "content",
  "get_data",
  "decode",
  "readouterr",
  "inner_text",
  "text_content",
  "innerHTML",
  "textContent",
}
CLIENT_CALLS = {"get", "post", "put", "patch", "delete", "open", "walk", "guest"}
BARE_CLIENT_CALLS = {"open", "walk", "guest"}
TAINT_SOURCES = (WEB_CHANNELS - CHANNELS - {"readouterr"}) | CLIENT_CALLS
ASSERT_METHODS = {"assertEqual", "assertNotEqual", "assertIn", "assertNotIn"}
NODE_TIMEOUT = 10
JS_REVIEW = r"""
let acorn;
try { acorn = require(require.resolve('acorn', {paths:[process.argv[1]]})); }
catch { console.log(JSON.stringify({reason:'parser_unavailable'})); process.exit(0); }
const text = require('node:fs').readFileSync(0, 'utf8');
let tree;
try {
  try { tree = acorn.parse(text, {ecmaVersion:'latest', sourceType:'module', locations:true}); }
  catch { tree = acorn.parse(text, {ecmaVersion:'latest', sourceType:'script', locations:true}); }
} catch (error) {
  console.log(JSON.stringify({error:'SyntaxError', line:error.loc.line, column:error.loc.column + 1}));
  process.exit(0);
}
const MEASUREMENTS = new Set(__MEASUREMENTS__);
function shape(node) {
  if (node?.type === 'Identifier') return node.name;
  if (node?.type === 'MemberExpression') {
    if (!node.computed) return `${shape(node.object)}.${node.property.name}`;
    if (node.property.type === 'Literal' && typeof node.property.value === 'string' &&
      MEASUREMENTS.has(node.property.value.toLowerCase()))
      return `${shape(node.object)}.${node.property.value}`;
  }
  if (node?.type === 'CallExpression') return `${shape(node.callee)}(${node.arguments.map(shape).join(',')})`;
  return '<expression>';
}
const CHANNELS = new Set(['stdout', 'stderr', 'output', 'out', 'err']);
const WEB_CHANNELS = new Set([
  'stdout', 'stderr', 'output', 'out', 'err',
  'body', 'html', 'text', 'data', 'content',
  'get_data', 'decode', 'readouterr',
  'inner_text', 'text_content', 'innerHTML', 'textContent',
]);
const CLIENT_CALLS = new Set(['get', 'post', 'put', 'patch', 'delete', 'open', 'walk', 'guest']);
const BARE_CLIENT_CALLS = new Set(['open', 'walk', 'guest']);
const TAINT_SOURCES = new Set([
  'body', 'html', 'text', 'data', 'content',
  'get_data', 'decode', 'inner_text', 'text_content', 'innerHTML', 'textContent',
  ...CLIENT_CALLS,
]);
const TAINT_RECEIVERS = new Set(['response', 'res', 'resp', 'page', 'result', 'proc', 'client', 'app']);
const tainted = new Set();
function isTaintRhs(name) {
  if (!name || name === '<expression>' || name.startsWith('len(')) return false;
  const parts = name.split('.').map(p => p.split('(')[0]);
  if (parts[0] === '<expression>') return false;
  if (tainted.has(parts[0]) || BARE_CLIENT_CALLS.has(parts[0])) return true;
  if (parts.length > 1 && CLIENT_CALLS.has(parts[1])) return true;
  return TAINT_RECEIVERS.has(parts[0]) && parts.slice(1).some(p => TAINT_SOURCES.has(p));
}
function collectTargets(pattern, out) {
  if (!pattern || typeof pattern !== 'object') return;
  if (pattern.type === 'Identifier') out.push(pattern.name);
  else if (pattern.type === 'ArrayPattern') pattern.elements.forEach(el => collectTargets(el, out));
  else if (pattern.type === 'ObjectPattern') {
    pattern.properties.forEach(p => collectTargets(p.value || p.argument, out));
  }
  else if (pattern.type === 'RestElement') collectTargets(pattern.argument, out);
  else if (pattern.type === 'AssignmentPattern') collectTargets(pattern.left, out);
}
function taintPass(node) {
  if (!node || typeof node !== 'object') return;
  if (node.type === 'VariableDeclarator' && node.init && isTaintRhs(shape(node.init))) {
    const names = [];
    collectTargets(node.id, names);
    names.forEach(n => tainted.add(n));
  } else if (node.type === 'AssignmentExpression' && isTaintRhs(shape(node.right))) {
    const names = [];
    collectTargets(node.left, names);
    names.forEach(n => tainted.add(n));
  }
  for (const value of Object.values(node)) {
    if (Array.isArray(value)) value.forEach(taintPass);
    else if (value && typeof value === 'object') taintPass(value);
  }
}
for (let i = 0; i < 3; i++) taintPass(tree);
const pairs = [];
const waits = [];
let testScope = false;
const lines = text.split("\n");
function containsNode(node, predicate) {
  if (!node || typeof node !== 'object') return false;
  if (predicate(node)) return true;
  return Object.values(node).some(value => Array.isArray(value)
    ? value.some(child => containsNode(child, predicate))
    : value && typeof value === 'object' && containsNode(value, predicate));
}
function rootCallName(node) {
  return node.type === 'CallExpression' ? shape(node.callee).split('.')[0] : '';
}
const fakeTimerMethods = new Set([
  'useFakeTimers',
  'advanceTimersByTime',
  'advanceTimersToNextTimer',
  'runAllTimers',
  'runOnlyPendingTimers',
  'clearAllTimers',
]);
function fakeTimerControl(node) {
  if (node.type !== 'CallExpression') return false;
  const name = shape(node.callee);
  return fakeTimerMethods.has(name.split('.').pop()) ||
    /^(?:sinon|clock)\.(?:install|tick)$/.test(name);
}
function hasTestDeclaration(node) {
  return containsNode(node, child => ['test','it','specify'].includes(rootCallName(child)));
}
function hasSuiteFakeTimerControl(node) {
  if (!node || typeof node !== 'object') return false;
  if (node.type === 'CallExpression' &&
    ['test','it','specify','describe','suite'].includes(rootCallName(node))) return false;
  if (fakeTimerControl(node)) return true;
  return Object.values(node).some(value => Array.isArray(value)
    ? value.some(child => hasSuiteFakeTimerControl(child))
    : value && typeof value === 'object' && hasSuiteFakeTimerControl(value));
}
const fakeTimerScopes = [];
function collectFakeTimerScopes(node) {
  if (!node || typeof node !== 'object') return;
  if (node.type === 'CallExpression') {
    const root = rootCallName(node);
    const callbacks = node.arguments.filter(arg =>
      ['FunctionExpression','ArrowFunctionExpression'].includes(arg.type));
    if (['test','it','specify'].includes(root)) {
      callbacks.forEach(callback => {
        if (containsNode(callback.body, fakeTimerControl)) {
          fakeTimerScopes.push({start:callback.start, end:callback.end});
        }
      });
    } else if (['describe','suite'].includes(root)) {
      callbacks.forEach(callback => {
        if (hasSuiteFakeTimerControl(callback.body)) {
          fakeTimerScopes.push({start:callback.start, end:callback.end});
        }
      });
    }
  }
  for (const value of Object.values(node)) {
    if (Array.isArray(value)) value.forEach(child => collectFakeTimerScopes(child));
    else if (value && typeof value === 'object') collectFakeTimerScopes(value);
  }
}
collectFakeTimerScopes(tree);
const moduleFakeTimers = tree.body.some(statement =>
  !hasTestDeclaration(statement) && containsNode(statement, fakeTimerControl));
function fakeTimerControlled(node) {
  return moduleFakeTimers || fakeTimerScopes.some(scope =>
    scope.start <= node.start && node.end <= scope.end);
}
function timerCall(node) {
  if (node?.type !== 'CallExpression') return false;
  return ['sleep','timersPromises.setTimeout','timersPromises.sleep'].includes(shape(node.callee));
}
function promiseTimer(node) {
  if (node?.type !== 'NewExpression' || shape(node.callee) !== 'Promise') return null;
  let found = null;
  containsNode(node, child => {
    if (!found && child.type === 'CallExpression' && shape(child.callee) === 'setTimeout') {
      found = child;
    }
    return Boolean(found);
  });
  return found;
}
function awaitedTimer(node) {
  if (node.type !== 'AwaitExpression') return null;
  if (timerCall(node.argument)) return node.argument;
  return promiseTimer(node.argument);
}
function boundedPoll(node) {
  if (node.type !== 'WhileStatement') return false;
  const condition = text.slice(node.test.start, node.test.end);
  return /(?:Date\.now|performance\.now|(?:time\.)?(?:monotonic|perf_counter))\s*\(/.test(condition) &&
    /\b(?:deadline|timeout|timeout_at|end_time|expires_at)\b/i.test(condition);
}
const LOCAL_SCOPE = Symbol('local test scope');
const testCallbacks = new WeakSet();
function pair(left, right, node, operator, explicit) {
  for (let [actual, expected] of [[left,right],[right,left]]) {
    if (expected?.type === 'Identifier' && explicit.get(LOCAL_SCOPE) &&
        typeof explicit.get(expected.name) === 'string')
      expected = {type:'Literal', value:explicit.get(expected.name)};
    if (expected?.type === 'Literal' && ['string','number'].includes(typeof expected.value)) {
      const column = Array.from(lines[node.loc.start.line - 1].slice(0, node.loc.start.column)).length + 1;
      const actShape = shape(actual);
      pairs.push({actual:actShape, value:expected.value, operator, lang:'js',
        explicit_input:explicit.has(actShape) && explicit.get(actShape) === expected.value,
        web_taint:isTaintRhs(actShape), tainted:[...tainted],
        line:node.loc.start.line, column});
    }
  }
}
function checkIncludes(expr, node, explicit) {
  if (expr?.type === 'CallExpression' && expr.callee?.type === 'MemberExpression' &&
    expr.callee.property?.name === 'includes') {
    pair(expr.callee.object, expr.arguments[0], node, 'membership', explicit);
  }
}
function recordInput(name, value, explicit) {
  if (value?.type === 'Identifier' && explicit.get(LOCAL_SCOPE) &&
      typeof explicit.get(value.name) === 'string')
    value = {type:'Literal', value:explicit.get(value.name)};
  for (const key of explicit.keys()) {
    if (typeof key === 'string' && (key === name || key.startsWith(name + '.'))) explicit.delete(key);
  }
  if (value?.type === 'Literal' && ['string','number'].includes(typeof value.value))
    explicit.set(name, value.value);
}
function visit(node, isBoundedPoll=false, explicit=new Map()) {
  if (!node || typeof node !== 'object') return;
  if (['FunctionDeclaration','FunctionExpression','ArrowFunctionExpression'].includes(node.type))
    explicit = new Map([[LOCAL_SCOPE, testCallbacks.has(node) || /^test_/.test(node.id?.name || '')]]);
  if (node.type === 'IfStatement') {
    visit(node.test, isBoundedPoll, new Map(explicit));
    visit(node.consequent, isBoundedPoll, new Map(explicit));
    visit(node.alternate, isBoundedPoll, new Map(explicit));
    explicit.clear();
    return;
  }
  if (['ForStatement','ForOfStatement','ForInStatement','WhileStatement','DoWhileStatement',
    'TryStatement','SwitchStatement','SwitchCase'].includes(node.type)) {
    explicit.clear();
    explicit = new Map();
  }
  if (node.type === 'VariableDeclarator') recordInput(shape(node.id), node.init, explicit);
  if (node.type === 'AssignmentExpression')
    recordInput(shape(node.left), node.operator === '=' ? node.right : null, explicit);
  if (node.type === 'UpdateExpression') recordInput(shape(node.argument), null, explicit);
  if (node.type === 'ExpressionStatement' &&
      (node.expression?.type === 'CallExpression' ||
       (node.expression?.type === 'AwaitExpression' && node.expression.argument?.type === 'CallExpression'))) {
    const call = node.expression.type === 'AwaitExpression' ? node.expression.argument : node.expression;
    const callName = shape(call.callee);
    if (!callName.startsWith('assert') && !callName.startsWith('expect')) {
      const used = new Set();
      function inputNames(item) {
        if (!item || typeof item !== 'object') return;
        if (item.type === 'Identifier' && typeof explicit.get(item.name) === 'string')
          used.add(explicit.get(item.name));
        for (const value of Object.values(item)) {
          if (Array.isArray(value)) value.forEach(inputNames);
          else if (value && typeof value === 'object') inputNames(value);
        }
      }
      call.arguments.forEach(inputNames);
      for (const [key, value] of explicit) if (typeof key === 'string' && used.has(value)) explicit.delete(key);
    }
    const setter = /^(.*\.)?set_([A-Za-z_][A-Za-z_0-9]*)$/.exec(shape(call.callee));
    if (setter && call.arguments.length === 1)
      recordInput((setter[1] || '') + setter[2], call.arguments[0], explicit);
  }
  if (boundedPoll(node)) isBoundedPoll = true;
  if (node.type === 'AwaitExpression') {
    const delay = awaitedTimer(node);
    if (delay && !isBoundedPoll && !fakeTimerControlled(delay)) {
      const column = Array.from(lines[delay.loc.start.line - 1].slice(0, delay.loc.start.column)).length + 1;
      waits.push({actual:shape(delay.callee), line:delay.loc.start.line, column});
    }
  }
  if (node.type === 'ImportDeclaration' && node.source.value === 'node:test') testScope = true;
  if (node.type === 'CallExpression') {
    const name = shape(node.callee);
    if (name === 'require' && node.arguments[0]?.value === 'node:test') testScope = true;
    if (['test','it','describe','suite'].includes(name)) {
      for (const arg of node.arguments) {
        if (['FunctionExpression','ArrowFunctionExpression'].includes(arg.type)) {
          testScope = true;
          testCallbacks.add(arg);
        }
      }
    }
    if (['assert.equal','assert.strictEqual','assert.deepEqual',
      'assert.deepStrictEqual','assert.notEqual','assert.notStrictEqual'].includes(name)) {
      pair(node.arguments[0], node.arguments[1], node, 'equality', explicit);
      checkIncludes(node.arguments[0], node, explicit);
      checkIncludes(node.arguments[1], node, explicit);
    } else if (node.callee?.type === 'MemberExpression' &&
      node.callee.object?.type === 'CallExpression' &&
      shape(node.callee.object.callee) === 'expect') {
      const actual = node.callee.object.arguments[0];
      if (node.callee.property.name === 'toBe') {
        pair(actual, node.arguments[0], node, 'equality', explicit);
      } else if (node.callee.property.name === 'toHaveCSS' &&
        typeof node.arguments[0]?.value === 'string') {
        pair({type:'MemberExpression', object:actual,
          property:{type:'Identifier', name:node.arguments[0].value}, computed:false},
          node.arguments[1], node, 'equality', explicit);
      }
    } else if (name === 'assert' || name === 'assert.ok') {
      const expression = node.arguments[0];
      if (expression?.type === 'BinaryExpression' && ['==','===','!=','!=='].includes(expression.operator)) {
        pair(expression.left, expression.right, node, 'equality', explicit);
      } else {
        checkIncludes(expression, node, explicit);
      }
    }
  }
  for (const value of Object.values(node)) {
    if (Array.isArray(value)) value.forEach(child => visit(child, isBoundedPoll, explicit));
    else if (value && typeof value === 'object') visit(value, isBoundedPoll, explicit);
  }
}
visit(tree);
console.log(JSON.stringify({pairs, waits, test_scope:testScope}));
""".replace("__MEASUREMENTS__", json.dumps(sorted(MEASUREMENTS)))


def shape(node):
  if isinstance(node, ast.Name):
    return node.id
  if isinstance(node, ast.Attribute):
    return f"{shape(node.value)}.{node.attr}"
  if (
    isinstance(node, ast.Subscript)
    and isinstance(node.slice, ast.Constant)
    and isinstance(node.slice.value, str)
    and node.slice.value.lower() in MEASUREMENTS
  ):
    return f"{shape(node.value)}.{node.slice.value}"
  if isinstance(node, ast.Call):
    return f"{shape(node.func)}({','.join(map(shape, node.args))})"
  return "<expression>"


def _is_taint_rhs(name, tainted=frozenset()):
  if not name or name == "<expression>" or name.startswith("len("):
    return False
  parts = [part.split("(")[0] for part in name.split(".")]
  if parts[0] == "<expression>":
    return False
  if parts[0] in tainted or parts[0] in BARE_CLIENT_CALLS:
    return True
  return len(parts) > 1 and any(part in TAINT_SOURCES for part in parts[1:])


def _iter_scope_nodes(scope_node):
  for child in ast.iter_child_nodes(scope_node):
    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
      continue
    yield child
    yield from _iter_scope_nodes(child)


def _collect_scope_taint(scope_node):
  tainted = set()
  nodes = list(_iter_scope_nodes(scope_node))
  for _ in range(3):
    changed = False
    for node in nodes:
      if isinstance(node, ast.Assign) and _is_taint_rhs(shape(node.value), tainted):
        for target in node.targets:
          for sub in ast.walk(target):
            if isinstance(sub, ast.Name) and sub.id not in tainted:
              tainted.add(sub.id)
              changed = True
      elif (
        isinstance(node, ast.AnnAssign)
        and node.value is not None
        and _is_taint_rhs(shape(node.value), tainted)
      ):
        for sub in ast.walk(node.target):
          if isinstance(sub, ast.Name) and sub.id not in tainted:
            tainted.add(sub.id)
            changed = True
    if not changed:
      break
  return tainted


def extract_prose_candidate(raw):
  """Extract a plain prose candidate from str or bytes after stripping HTML tags."""
  text = raw.decode("utf-8", "ignore") if isinstance(raw, bytes) else raw
  if not isinstance(text, str) or "{" in text or "}" in text or "\n" in text:
    return None
  has_html = bool(
    re.search(r"</[A-Za-z][A-Za-z0-9-]*>|<[A-Za-z][A-Za-z0-9-]*\s+[^>]*>", text)
  )
  stripped = re.sub(r"<[^>]+>", " ", text).strip() if has_html else text.strip()
  if (
    not stripped
    or re.search(r"[<>{}=\\/;]", stripped)
    or stripped.startswith((".", "#", "@", "/", "http://", "https://"))
  ):
    return None
  words = re.findall(r"(?<![A-Za-z0-9_-])[A-Za-z']+(?![A-Za-z0-9_-])", stripped)
  if len(words) >= 3 and not stripped.isupper() and re.search(r"\s", stripped):
    return stripped
  if (
    len(words) >= 2
    and stripped[-1] in ".?!"
    and stripped[0].isupper()
    and not stripped.isupper()
  ):
    return stripped
  return None


def _has_bounded_poll_limit(condition):
  names = {
    node.id.lower() for node in ast.walk(condition) if isinstance(node, ast.Name)
  }
  clocks = {
    shape(node.func).lower()
    for node in ast.walk(condition)
    if isinstance(node, ast.Call)
  }
  return bool(
    clocks
    & {"time.monotonic", "time.perf_counter", "time.time", "monotonic", "perf_counter"}
  ) and bool(names & {"deadline", "timeout", "timeout_at", "end_time", "expires_at"})


def _patches_real_wait(node):
  if not isinstance(node, ast.Call):
    return False
  name = shape(node.func)
  if not name.endswith(("patch", "patch.object", "setattr")):
    return False
  targets = {
    child.value
    for child in ast.walk(node)
    if isinstance(child, ast.Constant) and isinstance(child.value, str)
  }
  if any(target in REAL_WAIT_CALLS or target.endswith(".sleep") for target in targets):
    return True
  return (
    name.endswith(("patch.object", "setattr"))
    and len(node.args) >= 2
    and shape(node.args[0]) in {"time", "asyncio"}
    and isinstance(node.args[1], ast.Constant)
    and node.args[1].value == "sleep"
  )


def _python_waits(tree, lines):
  parents = {
    child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)
  }

  def enclosing(node, types):
    parent = parents.get(node)
    while parent:
      if isinstance(parent, types):
        return parent
      parent = parents.get(parent)
    return None

  waits = []
  for node in ast.walk(tree):
    if not isinstance(node, ast.Call):
      continue
    actual = shape(node.func)
    if actual not in REAL_WAIT_CALLS:
      continue
    if actual == "asyncio.sleep" and not enclosing(node, ast.Await):
      continue
    ancestor = parents.get(node)
    bounded = False
    fake_timed = False
    while ancestor:
      if isinstance(ancestor, ast.While) and _has_bounded_poll_limit(ancestor.test):
        bounded = True
      if isinstance(ancestor, (ast.With, ast.AsyncWith)) and any(
        _patches_real_wait(item.context_expr) for item in ancestor.items
      ):
        fake_timed = True
      if isinstance(
        ancestor, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)
      ) and any(_patches_real_wait(candidate) for candidate in ast.walk(ancestor)):
        fake_timed = True
      ancestor = parents.get(ancestor)
    if bounded or fake_timed:
      continue
    waits.append(
      {
        "actual": actual,
        "line": node.lineno,
        "column": len(
          lines[node.lineno - 1].encode("utf-8")[: node.col_offset].decode("utf-8")
        )
        + 1,
      }
    )
  return waits


def python_pairs(text):
  pairs = []
  lines = text.splitlines()
  tree = ast.parse(text)
  module_tainted = _collect_scope_taint(tree)
  func_taint = {
    id(node): _collect_scope_taint(node)
    for node in ast.walk(tree)
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
  }

  local_scope = object()

  def pair(left, right, node, operator, tainted, explicit):
    for actual, expected in ((left, right), (right, left)):
      if isinstance(expected, ast.Name) and explicit.get(local_scope):
        value = explicit.get(expected.id)
        if isinstance(value, (str, bytes)):
          expected = ast.Constant(value=value)
      if isinstance(expected, ast.Constant) and type(expected.value) in (
        str,
        bytes,
        int,
        float,
      ):
        act_shape = shape(actual)
        raw_val = expected.value
        val = (
          raw_val.decode("utf-8", "ignore") if isinstance(raw_val, bytes) else raw_val
        )
        pairs.append(
          {
            "actual": act_shape,
            "explicit_input": act_shape in explicit and explicit[act_shape] == raw_val,
            "value": val,
            "raw_value": raw_val,
            "tainted": sorted(tainted),
            "web_taint": _is_taint_rhs(act_shape, tainted)
            or isinstance(raw_val, bytes),
            "operator": operator,
            "line": node.lineno,
            "column": len(
              lines[node.lineno - 1].encode("utf-8")[: node.col_offset].decode("utf-8")
            )
            + 1,
          }
        )

  def record_input(node, explicit):
    targets, value = [], None
    if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
      targets = node.targets if isinstance(node, ast.Assign) else [node.target]
      value = None if isinstance(node, ast.AugAssign) else node.value
    elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
      call = node.value
      setter = shape(call.func).rsplit(".", 1)
      if setter[-1].startswith("set_") and len(call.args) == 1:
        target = setter[-1][4:]
        if len(setter) > 1:
          target = setter[0] + "." + target
        targets = [target]
        value = call.args[0]
    if isinstance(value, ast.Name) and explicit.get(local_scope):
      resolved = explicit.get(value.id)
      value = (
        ast.Constant(value=resolved) if isinstance(resolved, (str, bytes)) else value
      )
    for target in targets:
      name = target if isinstance(target, str) else shape(target)
      for key in list(explicit):
        if isinstance(key, str) and (key == name or key.startswith(name + ".")):
          explicit.pop(key)
      if isinstance(value, ast.Constant) and type(value.value) is not bool:
        explicit[name] = value.value

  def walk_scope(scope_node, active_taint, explicit=None):
    if explicit is None:
      explicit = {}
    for child in ast.iter_child_nodes(scope_node):
      if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
        walk_scope(
          child,
          active_taint | func_taint.get(id(child), set()),
          {local_scope: child.name.startswith("test_")},
        )
        continue
      if isinstance(
        child,
        (
          ast.If,
          ast.For,
          ast.AsyncFor,
          ast.While,
          ast.Try,
          ast.With,
          ast.AsyncWith,
          ast.Match,
        ),
      ):
        incoming = dict(explicit) if isinstance(child, ast.If) else {}
        for _, branch in ast.iter_fields(child):
          if isinstance(branch, list):
            statements = [item for item in branch if isinstance(item, ast.stmt)]
            if statements:
              walk_scope(
                ast.Module(body=statements, type_ignores=[]),
                active_taint,
                dict(incoming),
              )
            for handler in branch:
              if isinstance(handler, (ast.ExceptHandler, ast.match_case)):
                walk_scope(handler, active_taint, {})
        explicit.clear()
        continue
      expression = getattr(child, "value", None)
      if isinstance(expression, ast.Await):
        expression = expression.value
      if isinstance(child, (ast.Expr, ast.Assign, ast.AnnAssign)) and isinstance(
        expression, ast.Call
      ):
        call = expression
        if not shape(call.func).rsplit(".", 1)[-1].startswith("assert"):
          used = {
            explicit[name.id]
            for arg in [*call.args, *(kw.value for kw in call.keywords)]
            for name in ast.walk(arg)
            if isinstance(name, ast.Name)
            and isinstance(explicit.get(name.id), (str, bytes))
          }
          for key in list(explicit):
            if isinstance(key, str) and explicit[key] in used:
              explicit.pop(key)
      record_input(child, explicit)
      if isinstance(child, ast.Assert):
        for expression in ast.walk(child.test):
          if isinstance(expression, ast.Compare):
            left = expression.left
            for operator, right in zip(expression.ops, expression.comparators):
              if isinstance(operator, (ast.Eq, ast.NotEq, ast.In, ast.NotIn)):
                pair(
                  left,
                  right,
                  expression,
                  "equality"
                  if isinstance(operator, (ast.Eq, ast.NotEq))
                  else "membership",
                  active_taint,
                  explicit,
                )
              left = right
      if (
        isinstance(child, ast.Call)
        and isinstance(child.func, ast.Attribute)
        and shape(child.func.value) in ("self", "cls")
        and child.func.attr in ASSERT_METHODS
        and len(child.args) >= 2
      ):
        pair(
          child.args[0],
          child.args[1],
          child,
          "membership"
          if child.func.attr in {"assertIn", "assertNotIn"}
          else "equality",
          active_taint,
          explicit,
        )
      walk_scope(child, active_taint, explicit)

  walk_scope(tree, module_tainted)
  return {"pairs": pairs, "waits": _python_waits(tree, lines)}


def output_channel(name, tainted=(), lang="py", web_taint=False):
  if not name or name == "<expression>" or name.startswith("len("):
    return False
  taint_set = set(tainted)
  parts = [part.split("(")[0] for part in name.split(".")]
  if parts[0] == "<expression>":
    return False
  if parts[0] in taint_set or parts[0] in CHANNELS or parts[0] in BARE_CLIENT_CALLS:
    return True
  if lang == "js" and not web_taint:
    return any(part in CHANNELS for part in parts)
  return len(parts) > 1 and any(
    part in (WEB_CHANNELS | CLIENT_CALLS) for part in parts[1:]
  )


def category(pair):
  value, actual = pair["value"], pair["actual"]
  raw_val = pair.get("raw_value", value)
  tainted = pair.get("tainted", ())
  lang = pair.get("lang", "py")
  web_taint = bool(pair.get("web_taint"))
  if isinstance(raw_val, (str, bytes)) and output_channel(
    actual, tainted, lang=lang, web_taint=web_taint
  ):
    candidate = extract_prose_candidate(raw_val)
    if candidate is not None:
      words = re.findall(r"(?<![A-Za-z0-9_-])[A-Za-z']+(?![A-Za-z0-9_-])", candidate)
      if web_taint or len(words) >= 3:
        return "output_text"
  measurement_value = value
  if isinstance(value, str):
    pixels = re.fullmatch(r"([+]?(?:\d+(?:\.\d*)?|\.\d+))px", value)
    measurement_value = float(pixels[1]) if pixels else None
  if (
    type(measurement_value) in (int, float)
    and measurement_value > 0
    and pair["operator"] == "equality"
    and not pair.get("explicit_input")
    and (
      actual.split("(")[0].split(".")[-1].lower() in MEASUREMENTS
      or actual.rsplit(".", 1)[-1].split("(")[0].lower() in MEASUREMENTS
      or actual.startswith("px(")
      or actual.startswith("len(")
      and any(word in CHANNELS for word in re.findall(r"\w+", actual))
    )
  ):
    return "measurement"
  return None


def javascript_pairs(text):
  """Parse JavaScript assertions and test declarations through the bundled resolver."""
  if not shutil.which("node"):
    return {"reason": "parser_unavailable"}
  returncode, stdout = run_node(
    ["-e", JS_REVIEW, str(Path(__file__).resolve().parent)],
    text,
    timeout=NODE_TIMEOUT,
    check=False,
  )
  if returncode:
    raise RuntimeError("parser_process_failed")
  return json.loads(stdout)


def numeric_setting_findings(path, text):
  """Review direct numeric copies of statically resolved production settings."""
  tree = ast.parse(text)
  root = next(
    (
      parent
      for parent in path.resolve().parents
      if (parent / ".git").exists() or (parent / "pyproject.toml").exists()
    ),
    path.resolve().parent,
  )
  bindings = {}
  sources = {}

  def source(module, level=0):
    parts = module.split(".") if module else []
    base = path.resolve().parent
    if level:
      for _ in range(level - 1):
        base = base.parent
      candidates = [base.joinpath(*parts).with_suffix(".py")]
    else:
      candidates = [
        parent.joinpath(*parts).with_suffix(".py")
        for parent in path.resolve().parents
        if parent.is_relative_to(root)
      ]
    found = {
      candidate.resolve()
      for candidate in candidates
      if candidate.is_file()
      and candidate.resolve().is_relative_to(root)
      and not any(
        part in {"tests", "test", ".venv"} for part in candidate.relative_to(root).parts
      )
    }
    return next(iter(found)) if len(found) == 1 else None

  for node in tree.body:
    if isinstance(node, ast.Import):
      for alias in node.names:
        if resolved := source(alias.name):
          bindings[alias.asname or alias.name] = (resolved, None)
    elif isinstance(node, ast.ImportFrom) and (
      resolved := source(node.module, node.level)
    ):
      for alias in node.names:
        bindings[alias.asname or alias.name] = (resolved, alias.name)
  for node in tree.body:
    if isinstance(
      node,
      (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef),
    ):
      continue
    for child in ast.walk(node):
      if isinstance(child, ast.Name) and child.id in bindings:
        bindings.pop(child.id)
  for resolved, _ in bindings.values():
    if resolved in sources:
      continue
    try:
      parsed = ast.parse(resolved.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeError):
      sources[resolved] = {}
      continue
    settings = {}
    writes = {}
    for node in ast.walk(parsed):
      if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
        writes[node.id] = writes.get(node.id, 0) + 1
    for node in parsed.body:
      targets = (
        node.targets
        if isinstance(node, ast.Assign)
        else ([node.target] if isinstance(node, ast.AnnAssign) else [])
      )
      for target in targets:
        if not isinstance(target, ast.Name) or not target.id.isupper():
          continue
        if re.search(
          r"(?:SCHEMA|STATUS|EXIT|PERMISSION|FRAME|DIGEST|MODE|INDEX|VERSION)",
          target.id,
        ):
          continue
        value = getattr(node, "value", None)
        if isinstance(value, ast.UnaryOp) and isinstance(
          value.op, (ast.USub, ast.UAdd)
        ):
          value = value.operand
        if (
          isinstance(value, ast.Constant)
          and type(value.value) in (int, float)
          and writes[target.id] == 1
        ):
          settings[target.id] = node.lineno
    sources[resolved] = settings
  findings = []
  for function in ast.walk(tree):
    if not isinstance(
      function, (ast.FunctionDef, ast.AsyncFunctionDef)
    ) or not function.name.startswith("test_"):
      continue
    if (
      function.args.args
      or function.args.posonlyargs
      or function.args.kwonlyargs
      or function.args.vararg
      or function.args.kwarg
      or function.decorator_list
    ):
      continue
    nodes = list(_iter_scope_nodes(function))
    shadowed = {
      node.id
      for node in nodes
      if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del))
    }
    shadowed.update(
      arg.arg for arg in ast.walk(function.args) if isinstance(arg, ast.arg)
    )
    for node in nodes:
      if isinstance(node, (ast.Import, ast.ImportFrom)):
        shadowed.update(
          alias.asname or alias.name.split(".")[0] for alias in node.names
        )
      if isinstance(node, ast.Call):
        for argument in [*node.args, *(kw.value for kw in node.keywords)]:
          shadowed.update(
            child.id for child in ast.walk(argument) if isinstance(child, ast.Name)
          )
        if isinstance(node.func, ast.Attribute):
          shadowed.update(
            child.id
            for child in ast.walk(node.func.value)
            if isinstance(child, ast.Name)
          )
      if isinstance(node, ast.Attribute) and isinstance(node.ctx, (ast.Store, ast.Del)):
        shadowed.update(
          child.id for child in ast.walk(node.value) if isinstance(child, ast.Name)
        )
    for node in nodes:
      if not isinstance(node, ast.Assert) or not isinstance(node.test, ast.Compare):
        continue
      comparison = node.test
      if len(comparison.ops) != 1 or not isinstance(comparison.ops[0], ast.Eq):
        continue
      for actual, expected in (
        (comparison.left, comparison.comparators[0]),
        (comparison.comparators[0], comparison.left),
      ):
        literal = (
          expected.operand
          if isinstance(expected, ast.UnaryOp)
          and isinstance(expected.op, (ast.USub, ast.UAdd))
          else expected
        )
        if not isinstance(literal, ast.Constant) or type(literal.value) not in (
          int,
          float,
        ):
          continue
        name = (
          actual.id
          if isinstance(actual, ast.Name)
          else (
            actual.value.id
            if isinstance(actual, ast.Attribute) and isinstance(actual.value, ast.Name)
            else None
          )
        )
        if name not in bindings or name in shadowed:
          continue
        resolved, imported = bindings[name]
        setting = (
          imported
          if isinstance(actual, ast.Name)
          else actual.attr
          if imported is None
          else None
        )
        line = sources[resolved].get(setting)
        if line is None:
          continue
        findings.append(
          {
            "rule": TEST_RULE_IDS["numeric_setting"],
            "category": "numeric_setting",
            "path": str(path),
            "line": node.lineno,
            "column": node.col_offset + 1,
            "source_path": str(resolved),
            "source_line": line,
            "evidence": f"copied numeric setting {setting} from {resolved}:{line}",
            "status": "manual_review",
          }
        )
  return findings


def review_tests(targets):
  findings, coverage, errors, visited = [], [], [], set()
  for path in walk(targets, []):
    if path.resolve() in visited:
      continue
    visited.add(path.resolve())
    row = {"path": str(path), "status": "not_checked"}
    coverage.append(row)
    text = text_file(path)
    if text is None:
      row["reason"] = "unreadable_or_non_text"
      continue
    try:
      if path.suffix.lower() == ".py":
        parsed = python_pairs(text)
        row["parser"] = "python_ast"
      elif path.suffix.lower() in {".js", ".cjs", ".mjs"}:
        parsed = javascript_pairs(text)
        row["parser"] = "acorn"
      else:
        row["reason"] = "unsupported_language"
        continue
    except SyntaxError as error:
      parsed = {"error": "SyntaxError", "line": error.lineno, "column": error.offset}
    except (
      OSError,
      subprocess.TimeoutExpired,
      ValueError,
      RuntimeError,
      RecursionError,
    ) as error:
      parsed = {"error": type(error).__name__}
    if "reason" in parsed:
      row["reason"] = parsed["reason"]
      continue
    if "error" in parsed:
      row["reason"] = "parse_error"
      errors.append(
        {
          "path": str(path),
          "type": parsed["error"],
          "line": parsed.get("line"),
          "column": parsed.get("column"),
        }
      )
      continue
    row["status"] = "checked"
    with file_scope(path, text):
      file_ids, line_ids, _ = exclusions(path, text.splitlines())
    if path.suffix.lower() == ".py":
      for finding in numeric_setting_findings(path, text):
        if not suppressed(finding["rule"], file_ids | line_ids[finding["line"] - 1]):
          findings.append(finding)
    for pair in parsed["pairs"]:
      role = category(pair)
      if role is None:
        continue
      code = TEST_RULE_IDS[role]
      if suppressed(code, file_ids | line_ids[pair["line"] - 1]):
        continue
      findings.append(
        {
          "rule": code,
          "category": role,
          "path": str(path),
          "line": pair["line"],
          "column": pair["column"],
          "evidence": f"{pair['actual']} {pair['operator']} <literal>",
          "status": "review",
        }
      )
    for wait_finding in parsed.get("waits", ()):
      code = TEST_RULE_IDS["timing_wait"]
      if suppressed(code, file_ids | line_ids[wait_finding["line"] - 1]):
        continue
      findings.append(
        {
          "rule": code,
          "category": "timing_wait",
          "path": str(path),
          "line": wait_finding["line"],
          "column": wait_finding["column"],
          "evidence": f"unconditional wait via {wait_finding['actual']}",
          "status": "review",
        }
      )
  return {"findings": findings, "coverage": coverage, "errors": errors}


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


def is_test_file(path, text, helpers):
  """Recognize test paths and declarations without running supplied code."""
  if path.resolve() in helpers:
    return True
  suffix = path.suffix.lower()
  if suffix not in {".py", ".js", ".cjs", ".mjs"}:
    return False
  if any(
    fnmatch.fnmatchcase(path.name, pattern)
    for pattern in (
      "test_*.py",
      "*_test.py",
      "test_*.js",
      "test_*.cjs",
      "test_*.mjs",
      "*.test.*",
      "*.spec.*",
      "*.checks.cjs",
      "conftest.py",
    )
  ) or any(part in {"test", "tests"} for part in path.parts[:-1]):
    return True
  if suffix == ".py":
    for parent in path.resolve().parents:
      config = parent / "pytest.ini"
      pyproject = parent / "pyproject.toml"
      patterns, roots = None, None
      if config.is_file():
        settings = configparser.ConfigParser(interpolation=None)
        settings.read(config, encoding="utf-8")
        patterns = settings.get("pytest", "python_files", fallback="test_*.py").split()
        roots = settings.get("pytest", "testpaths", fallback=".").split()
      elif pyproject.is_file():
        raw = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        ini = raw.get("tool", {}).get("pytest", {}).get("ini_options")
        if isinstance(ini, dict):
          pf = ini.get("python_files", ["test_*.py"])
          tp = ini.get("testpaths", ["."])
          patterns = [pf] if isinstance(pf, str) else list(pf)
          roots = [tp] if isinstance(tp, str) else list(tp)
      if patterns is not None and roots is not None:
        if any(fnmatch.fnmatchcase(path.name, pattern) for pattern in patterns) and any(
          path.resolve().is_relative_to((parent / root).resolve()) for root in roots
        ):
          return True
        break
    return any(
      isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
      and node.name.startswith("test_")
      or isinstance(node, ast.ClassDef)
      and any(ast.unparse(base).endswith("TestCase") for base in node.bases)
      for node in ast.walk(ast.parse(text))
    )
  parsed = javascript_pairs(text)
  if "reason" in parsed or "error" in parsed:
    raise ValueError(parsed.get("reason") or parsed["error"])
  return parsed["test_scope"]


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
