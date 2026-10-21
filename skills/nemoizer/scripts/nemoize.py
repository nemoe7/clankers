"""Flag the avoided words and list every nemoizer ignore marker.

The linter reads every text file, comments and prose included. One rotation per
row: the avoided pattern on the left, the plain word on the right. A line that
carries `nemoizer: ignore` is skipped and still listed for review, and a marker
in the first three lines skips the whole file.
"""

import argparse
import re
import sys
from pathlib import Path

ROTATIONS = (
  (r"\bpick\w*\b", "select"),
  (r"\btransmit\w*\b", "send"),
  (r"\bkind\b", "type"),
)
MARKER = "nemoizer: ignore"
SKIP_DIRS = {
  ".git",
  ".venv",
  "__pycache__",
  "build",
  "dist",
  "node_modules",
  "out",
}
SKIP_PATHS = ("skills/refs", ".agents/skills")


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


def scan(targets, ignores):
  """Return (findings, ignore_lines) as `path:line: text` strings."""
  findings, marks = [], []
  for path in walk(targets, ignores):
    text = text_file(path)
    if text is None:
      continue
    lines = text.splitlines()

    def head_marker(line):
      """A marker on a line that carries no rotation skips the whole file."""
      before = line.split(MARKER, 1)[0]
      return MARKER in line and not any(
        re.search(pattern, before, flags=re.I) for pattern, _ in ROTATIONS
      )

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
      for pattern, use in ROTATIONS:
        for word in sorted(set(re.findall(pattern, line, flags=re.I))):
          findings.append(f"{path}:{number}: {word} -> {use} (nemoizer: ignore)")
  return findings, marks


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
  arguments = parser.parse_args()
  findings, marks = scan(arguments.targets or ["."], arguments.ignore)
  if arguments.ignores:
    print("\n".join(marks))
    return 0
  print("\n".join(findings))
  return 1 if findings else 0


if __name__ == "__main__":
  sys.exit(main())
