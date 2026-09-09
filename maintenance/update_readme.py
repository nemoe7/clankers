#!/usr/bin/env python3
"""Update the generated instruction-budget table in README.md."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"

# These are the repository's documented measurement contracts. Token counts use
# cl100k_base when tiktoken is installed; otherwise the script refuses to guess.
SPECS = [
  ("rules/AGENTS.md", "cl100k_base tokens"),
  ("rules/ARENA.md", "UTF-8 file size"),
  ("rules/CHATGPT.txt", "Unicode characters"),
  ("rules/CLINE.md", "cl100k_base tokens"),
  ("rules/COMMIT_SPEC.txt", "cl100k_base tokens"),
]
for path in sorted((ROOT / "skills").glob("*/SKILL.md")):
  SPECS.append((path.relative_to(ROOT).as_posix(), "cl100k_base tokens"))

ROW = re.compile(r"^(\| `[^`]+` \| `[^`]+` \| ).*( \|)$", re.MULTILINE)


def value(path: Path, kind: str) -> int:
  text = path.read_text(encoding="utf-8")
  if kind == "UTF-8 file size":
    return len(text.encode("utf-8"))
  if kind == "Unicode characters":
    return len(text)
  try:
    import tiktoken
  except ImportError as exc:
    raise SystemExit("tiktoken is required to update token measurements; install it or update those values manually") from exc
  return len(tiktoken.get_encoding("cl100k_base").encode(text))


def main() -> None:
  text = README.read_text(encoding="utf-8")
  start = text.index("| File | Measure | Current |")
  end = text.index("\n\nMeasurements cover complete files", start)
  header = "| File | Measure | Current |\n| --- | --- | --- |\n"
  rows = []
  for relative, kind in SPECS:
    path = ROOT / relative
    if not path.is_file():
      raise SystemExit(f"missing measurement target: {relative}")
    rows.append(f"| `{relative}` | `{kind}` | {value(path, kind)} |")
  replacement = header + "\n".join(rows)
  README.write_text(text[:start] + replacement + text[end:], encoding="utf-8")
  print("Updated README instruction-budget table.")


if __name__ == "__main__":
  main()
