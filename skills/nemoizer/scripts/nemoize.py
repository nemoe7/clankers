# nonemo: N001
# nonemo: N002
# nonemo: N003
"""Flag rotations, rewrite text, and list every exclusion marker."""

import argparse
import json
import re
import sys
from pathlib import Path

# (name, avoided pattern, plain word).
# A stem word that takes its own plain word.
EXCEPTIONS = {"picker": "selector", "pickers": "selectors"}
ROTATIONS = (
  ("pick", r"(?<![A-Za-z0-9])pick\w*(?![A-Za-z0-9])", "select"),
  ("transmit", r"(?<![A-Za-z0-9])transmit\w*(?![A-Za-z0-9])", "send"),
  ("kind", r"(?<![A-Za-z0-9])kinds?(?![A-Za-z0-9])", "type"),
)
RULE_IDS = {"transmit": "N001", "pick": "N002", "kind": "N003"}
SENTENCE_CAPS = {"instruction": 20, "description": 25}
PARAGRAPH_CAP = 6
PROSE_RULE_IDS = {"sentence": "N004", "paragraph": "N005"}
KNOWN_RULE_IDS = {*RULE_IDS.values(), *PROSE_RULE_IDS.values()}
MARKER = re.compile(r"\bnonemo:[ \t]*(.*?)(?=-->|\*/|;|\s|$|\bnonemo:)")
# The rotation table names the avoided words, so its own rows never flag.
TABLE_ROW = re.compile(r"^\|\s*`[^`]+`\s*\|")
SKIP_DIRS = {
  ".git",
  ".venv",
  "__pycache__",
  "build",
  "dist",
  "node_modules",
  "out",
}
SKIP_PATHS = (
  ".agents/skills",
  "arena-state",
)


def text_file(path):
  """Return the decoded text, or None when the file is not UTF-8 text."""
  try:
    raw = path.read_bytes()
  except OSError:
    return None
  if b"\0" in raw[:1024]:
    return None
  try:
    return raw.decode("utf-8")
  except UnicodeDecodeError:
    return None


def skipped(path, root, ignores):
  """True when a path sits under a skipped directory or an ignored prefix."""
  try:
    relative = path.resolve().relative_to(root.resolve())
  except ValueError:
    relative = path
  text = str(relative)
  if any(part in SKIP_DIRS for part in Path(text).parts):
    return True
  if any(text == item or text.startswith(item + "/") for item in SKIP_PATHS):
    return True
  return any(text == item or text.startswith(item + "/") for item in ignores)


def walk(targets, ignores):
  """Yield every text file under the targets that survives the skip rules."""
  for target in targets:
    path = Path(target)
    if path.is_file():
      yield path
      continue
    root = path if path.is_dir() else Path(".")
    for candidate in sorted(root.rglob("*")):
      if candidate.is_file() and not skipped(candidate, root, ignores):
        yield candidate


def head_marker(line, position=None):
  """Identify a header marker with no avoided word before it on the line."""
  marker = MARKER.search(line)
  if marker is None:
    return False
  before = line[: marker.start() if position is None else position]
  return not any(
    re.search(pattern, before, flags=re.IGNORECASE) for _, pattern, _ in ROTATIONS
  )


def exclusions(path, lines):
  """Collect every marker and the known rule IDs it suppresses."""
  file_ids, line_ids, marks = set(), [], []
  for number, line in enumerate(lines, 1):
    suppressed = set()
    for marker in MARKER.finditer(line):
      code = marker[1]
      scope = "unknown"
      if code in KNOWN_RULE_IDS:
        suppressed.add(code)
        scope = "file" if number <= 3 and head_marker(line, marker.start()) else "line"
        if scope == "file":
          file_ids.add(code)
      marks.append(f"{path}:{number}: {code or '<missing>'} {scope}: {line.strip()}")
    line_ids.append(suppressed)
  return file_ids, line_ids, marks


def plain(word, name, use):
  """Give the matched word its plain word, and keep the old word's case."""
  form = EXCEPTIONS.get(word.lower()) or re.sub(
    re.escape(name), use, word, flags=re.IGNORECASE
  )
  if word.isupper():
    return form.upper()
  if word[:1].isupper():
    return form[:1].upper() + form[1:]
  return form


def rotate(line, suppressed=frozenset()):
  """Swap each matched word for its plain word, and take the exception words first."""
  for name, pattern, use in ROTATIONS:
    if RULE_IDS[name] in suppressed:
      continue
    line = re.sub(
      pattern,
      lambda match, name=name, use=use: plain(match.group(0), name, use),
      line,
      flags=re.IGNORECASE,
    )
  return line


def scan(targets, ignores):
  """Return findings and all exclusion markers with locations and rule IDs."""
  findings, marks = [], []
  for path in walk(targets, ignores):
    text = text_file(path)
    if text is None:
      continue
    lines = text.splitlines()
    file_ids, line_ids, found = exclusions(path, lines)
    marks.extend(found)
    for number, line in enumerate(lines, 1):
      if TABLE_ROW.match(line.strip()):
        continue
      suppressed = file_ids | line_ids[number - 1]
      visible = MARKER.sub(lambda match: " " * len(match[0]), line)
      for name, pattern, use in ROTATIONS:
        code = RULE_IDS[name]
        if code in suppressed:
          continue
        for word in sorted(set(re.findall(pattern, visible, flags=re.IGNORECASE))):
          findings.append(f"{path}:{number}: {code} {word} -> {use}")
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
    file_ids, line_ids, _ = exclusions(path, lines)
    rewritten, touched = [], False
    for number, line in enumerate(lines, 1):
      if TABLE_ROW.match(line.strip()):
        rewritten.append(line)
        continue
      suppressed = file_ids | line_ids[number - 1]
      parts, start = [], 0
      for marker in MARKER.finditer(line):
        parts.extend((rotate(line[start : marker.start()], suppressed), marker[0]))
        start = marker.end()
      parts.append(rotate(line[start:], suppressed))
      rotated = "".join(parts)
      if rotated != line:
        print(f"{path}:{number}: -{line}", file=out)
        print(f"{path}:{number}: +{rotated}", file=out)
        changed += 1
        touched = True
      rewritten.append(rotated)
    if touched:
      path.write_text("\n".join(rewritten), encoding="utf-8")
  return changed


def prose_counts(text):
  """Measure prose outside code fences and within table cells."""
  lines = text.splitlines()
  sentences, paragraphs, block = [], [], []
  fence, width, divider_pending = None, 0, False

  def lengths(value):
    value = re.sub(r"(`+)(.*?)\1", "", value)
    return [
      len(part.split()) for part in re.split(r"[.!?](?:\s+|$)", value) if part.strip()
    ]

  def cells(value):
    if "|" not in value:
      return []
    row, part, escaped = [], [], False
    for character in value:
      if escaped:
        part.append(character)
        escaped = False
      elif character == "\\":
        escaped = True
      elif character == "|":
        row.append("".join(part))
        part.clear()
      else:
        part.append(character)
    if escaped:
      part.append("\\")
    row.append("".join(part))
    if row and not row[0].strip():
      row.pop(0)
    if row and not row[-1].strip():
      row.pop()
    return [cell.strip() for cell in row] if len(row) > 1 else []

  def flush():
    if block and not re.match(r"(?:[#>*+|-]|\d+[.)]\s)", block[0][1].lstrip()):
      paragraphs.append(
        (block[0][0], len(lengths(" ".join(value for _, value in block))))
      )
    block.clear()

  for index, line in enumerate(lines):
    number = index + 1
    marker = re.match(r"^\s*(`{3,}|~{3,})", line)
    if marker:
      flush()
      if fence is None:
        fence = marker[1]
      elif (
        marker[1][0] == fence[0]
        and len(marker[1]) >= len(fence)
        and not line[marker.end() :].strip()
      ):
        fence = None
      width, divider_pending = 0, False
      continue
    if fence is not None:
      continue
    if not line.strip():
      flush()
      width, divider_pending = 0, False
      continue
    if divider_pending:
      divider_pending = False
      continue
    row = cells(line)
    following = cells(lines[index + 1]) if index + 1 < len(lines) else []
    header = (
      row
      and len(row) == len(following)
      and all(re.fullmatch(r":?-{3,}:?", cell) for cell in following)
    )
    if header:
      flush()
      width, divider_pending = len(row), True
    elif not width or len(row) != width:
      width = 0
    if width:
      segments = row
    else:
      block.append((number, line))
      segments = [line]
    for segment in segments:
      sentences.extend((number, 1, count) for count in lengths(segment))
  flush()
  return sentences, paragraphs


def prose_review(path, text, context, paragraph_cap):
  """Return unsuppressed measurable candidates for one explicit text scope."""
  lines = text.splitlines()
  file_ids, line_ids, _ = exclusions(path, lines)
  findings = []
  sentences, paragraphs = prose_counts(text)
  cap = SENTENCE_CAPS.get(context)
  code = PROSE_RULE_IDS["sentence"]
  if cap is not None and code not in file_ids:
    for number, column, count in sentences:
      if count > cap and code not in line_ids[number - 1]:
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
  code = PROSE_RULE_IDS["paragraph"]
  if code not in file_ids:
    for number, count in paragraphs:
      if count > paragraph_cap and code not in line_ids[number - 1]:
        findings.append(
          {
            "rule": code,
            "path": str(path),
            "line": number,
            "column": 1,
            "count": count,
            "cap": paragraph_cap,
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
  findings, coverage = [], []
  for path in walk(arguments.targets, []):
    text = text_file(path)
    coverage.append(
      {
        "path": str(path),
        "context": arguments.context,
        "sentences": "checked"
        if text is not None and arguments.context in SENTENCE_CAPS
        else "not_checked",
        "paragraphs": "checked" if text is not None else "not_checked",
      }
    )
    if text is not None:
      findings.extend(
        prose_review(path, text, arguments.context, arguments.paragraph_cap)
      )
  print(json.dumps({"findings": findings, "coverage": coverage}))
  return int(bool(findings))


def main(argv=None):
  argv = list(sys.argv[1:] if argv is None else argv)
  if argv[:1] == ["prose"]:
    return prose_main(argv[1:])
  parser = argparse.ArgumentParser(description="Flag nemoizer rotations.")
  parser.add_argument("targets", nargs="*", default=["."])
  parser.add_argument(
    "--ignore",
    action="append",
    default=[],
    help="skip a directory or file, relative to the target",
  )
  parser.add_argument(
    "--ignores", action="store_true", help="list every nonemo marker instead"
  )
  parser.add_argument(
    "--format", action="store_true", help="apply the rotations in place"
  )
  arguments = parser.parse_args(argv)
  targets = arguments.targets or ["."]
  if arguments.format:
    changed = format_paths(targets, arguments.ignore)
    print(f"{changed} lines rotated", file=sys.stderr)
    return 0
  findings, marks = scan(targets, arguments.ignore)
  if arguments.ignores:
    print("\n".join(marks))
    return 0
  print("\n".join(findings))
  return 1 if findings else 0


if __name__ == "__main__":
  sys.exit(main())
