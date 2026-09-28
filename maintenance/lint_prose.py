"""Lint the prose in the covered scope and Python comments. Run: python maintenance/lint_prose.py"""

import ast
import io
import re
import subprocess
import sys
import tokenize
from pathlib import Path

LINTER = Path(".agents/skills/asd-ste100/scripts/ste-lint.py")
TARGETS = ("maintenance", "rules")
SKIP_PARTS = {".git", ".venv", "node_modules", ".agents", "arena-state", "__pycache__"}
GENERATED = {Path("skills/arena-preview-steering/scripts/preview.py")}
ADR_REFERENCE = re.compile(r"\bADR[- ]?\d|docs/adr")


def prose(path: Path) -> str:
  """Collect the comments and docstrings of one file, one line each."""
  source = path.read_text(encoding="utf-8")
  lines: list[str] = []
  for node in ast.walk(ast.parse(source)):
    if isinstance(
      node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
    ):
      body = node.body
      first = body[0] if body else None
      if (
        isinstance(first, ast.Expr)
        and isinstance(first.value, ast.Constant)
        and isinstance(first.value.value, str)
      ):
        lines.extend(first.value.value.strip().splitlines())
  for token in tokenize.generate_tokens(io.StringIO(source).readline):
    if token.type == tokenize.COMMENT:
      lines.append(token.string.lstrip("# ").strip())
  return "\n".join(line for line in lines if line)


def markdown_targets() -> list[Path]:
  """Collect docs, CHANGELOG and every README outside the skip set."""
  found: list[Path] = []
  for path in sorted(Path(".").rglob("*.md")):
    if any(part in SKIP_PARTS for part in path.parts):
      continue
    if path.name in {"README.md", "CHANGELOG.md"} or path.parts[0] == "docs":
      found.append(path)
  return found


BULLET_SENTENCE_CAP = 3


def lint(label: str, text: str, adr: bool) -> int:
  """Run the linter on one text blob. Return 1 on failure."""
  if adr and ADR_REFERENCE.search(text):
    print(f"--- {label}\nA comment or docstring refers to an ADR.")
    return 1
  run = subprocess.run(
    [sys.executable, str(LINTER)],
    input=text,
    capture_output=True,
    text=True,
    check=False,
  )
  if run.returncode != 0:
    print(f"--- {label}")
    print(run.stdout.strip())
    return 1
  return 0


def bullet_cap(label: str, text: str) -> int:
  """Fail when a bullet line carries more than 3 sentences."""
  failures = 0
  for line in text.splitlines():
    if not line.startswith("- "):
      continue
    sentences = [part for part in re.split(r"(?<=[.!?])\s+", line) if part.strip()]
    if len(sentences) > BULLET_SENTENCE_CAP:
      failures += 1
      print(f"--- {label}\nA bullet exceeds {BULLET_SENTENCE_CAP} sentences.")
  return failures


def main() -> int:
  """Lint every target file, and fail when the linter fails."""
  failures = 0
  for folder in TARGETS:
    for path in sorted(Path(folder).rglob("*.py")):
      if path in GENERATED:
        continue
      text = prose(path)
      if not text:
        continue
      failures += lint(str(path), text, True)
  for path in markdown_targets():
    text = path.read_text(encoding="utf-8")
    failures += lint(str(path), text, False)
    if path.name == "CHANGELOG.md":
      failures += bullet_cap(str(path), text)
  if failures:
    print(f"{failures} lint findings")
    return 1
  print("ok: covered scope and code comments lint clean")
  return 0


if __name__ == "__main__":
  sys.exit(main())
