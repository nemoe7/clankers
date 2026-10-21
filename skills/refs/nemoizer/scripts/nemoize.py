# nemoizer: ignore — this file carries the table's words.
"""Flag the avoided words, rewrite them, and list every nemoizer ignore marker.

The linter reads every text file, comments and prose included. One rotation per
row: the avoided pattern on the left, the plain word on the right. The linter
skips a line that carries `nemoizer: ignore` and still lists it for review. A
marker in the first three lines skips the whole file.

`--format` applies the rotations in place and prints each changed line before and
after. Each row replaces its word as plain text, in lower, capital and upper case.
"""

import argparse
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
MARKER = "nemoizer: ignore"
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
  return raw.decode("utf-8", errors="ignore")


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


def head_marker(line):
  """A marker on a line that carries no rotation skips the whole file."""
  before = line.split(MARKER, 1)[0]
  return MARKER in line and not any(
    re.search(pattern, before, flags=re.IGNORECASE) for _, pattern, _ in ROTATIONS
  )


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


def rotate(line):
  """Swap each matched word for its plain word, and take the exception words first."""
  for name, pattern, use in ROTATIONS:
    line = re.sub(
      pattern,
      lambda match, name=name, use=use: plain(match.group(0), name, use),
      line,
      flags=re.IGNORECASE,
    )
  return line


def scan(targets, ignores):
  """Return (findings, ignore_lines) as `path:line: text` strings."""
  findings, marks = [], []
  for path in walk(targets, ignores):
    text = text_file(path)
    if text is None:
      continue
    lines = text.splitlines()
    if any(head_marker(line) for line in lines[:3]):
      marks.extend(
        f"{path}:{number}: {line.strip()}"
        for number, line in enumerate(lines[:3], 1)
        if head_marker(line)
      )
      continue
    for number, line in enumerate(lines, 1):
      if MARKER in line:
        marks.append(f"{path}:{number}: {line.strip()}")
        continue
      if TABLE_ROW.match(line.strip()):
        continue
      for _, pattern, use in ROTATIONS:
        for word in sorted(set(re.findall(pattern, line, flags=re.IGNORECASE))):
          findings.append(f"{path}:{number}: {word} -> {use} (nemoizer: ignore)")
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
    if any(head_marker(line) for line in lines[:3]):
      continue
    rewritten, touched = [], False
    for number, line in enumerate(lines, 1):
      if MARKER in line or TABLE_ROW.match(line.strip()):
        rewritten.append(line)
        continue
      rotated = rotate(line)
      if rotated != line:
        print(f"{path}:{number}: -{line}", file=out)
        print(f"{path}:{number}: +{rotated}", file=out)
        changed += 1
        touched = True
      rewritten.append(rotated)
    if touched:
      path.write_text("\n".join(rewritten), encoding="utf-8")
  return changed


def main():
  parser = argparse.ArgumentParser(description="Flag nemoizer rotations.")
  parser.add_argument("targets", nargs="*", default=["."])
  parser.add_argument(
    "--ignore",
    action="append",
    default=[],
    help="skip a directory or file, relative to the target",
  )
  parser.add_argument(
    "--ignores", action="store_true", help="list every ignore marker instead"
  )
  parser.add_argument(
    "--format", action="store_true", help="apply the rotations in place"
  )
  arguments = parser.parse_args()
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
