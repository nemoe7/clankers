"""Lint covered prose and tracked code comments. Run: python maintenance/lint_prose.py"""

import importlib.util
import re
import sys
from pathlib import Path

from extract_prose import comment_lines, extract_files

LINTER = Path(".agents/skills/asd-ste100/scripts/ste-lint.py")
SKIP_PARTS = {".git", ".venv", "node_modules", ".agents", "arena-state", "__pycache__"}
ADR_REFERENCE = re.compile(r"\bADR[- ]?\d|docs/adr")
COMMENT_BLOCK_CAP = 2
DIRECTIVE_MARKER = re.compile(
  r"^\s*(?:#|//)\s*(?:arena-preview-[\w-]+|case:\s*[\w-]+|shellcheck\s+disable=\S+|"
  r"noqa(?::.*)?|type:\s*ignore(?:\[.*\])?|pragma:\s*no cover|region|endregion)\s*$",
  re.IGNORECASE,
)
_STE_LINTER = None


def directive_marker_lines(source: str) -> set[int]:
  """Return comment lines that carry required tool directives."""
  return {
    number
    for number, line in enumerate(source.splitlines(), start=1)
    if DIRECTIVE_MARKER.match(line)
  }


def comment_block_violations(path: Path, source: str) -> list[str]:
  """Report ordinary comment blocks that exceed the line cap."""
  violations: list[str] = []
  start = None
  previous = None
  numbers = sorted(comment_lines(path, source) - directive_marker_lines(source))
  for number in [*numbers, None]:
    if number is not None and (previous is None or number == previous + 1):
      start = number if start is None else start
      previous = number
      continue
    if start is not None and previous is not None:
      count = previous - start + 1
      if count > COMMENT_BLOCK_CAP:
        violations.append(
          f"{path}:{start}: comment block has {count} lines; the cap is {COMMENT_BLOCK_CAP}"
        )
    start = number
    previous = number
  return violations


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


def report(label: str, findings: list[dict], note: str | None = None) -> None:
  """Print one labelled finding list."""
  print(f"--- {label}")
  if note:
    print(note)
  for finding in findings:
    print(
      f"{finding['line']}:{finding['col']} {finding['level']} "
      f"{finding['rule']}: {finding['message']}"
    )


def lint(label: str, text: str, adr: bool, strict: bool = False) -> int:
  """Run the linter once, failing on a hard finding, or on any finding in strict mode."""
  if adr and ADR_REFERENCE.search(text):
    report(label, [], "A comment or docstring refers to an ADR.")
    return 1
  findings, _ = ste_linter().lint(text, filename=label)
  hard = any(item["level"] == "advisory-free" for item in findings)
  if not findings or not (strict or hard):
    return 0
  report(label, findings)
  return 1


def ste_linter():
  """Load the vendored STE linter without changing its code."""
  global _STE_LINTER
  if _STE_LINTER is None:
    spec = importlib.util.spec_from_file_location("ste_lint", LINTER)
    if spec is None or spec.loader is None:
      raise RuntimeError(f"Cannot load {LINTER}.")
    _STE_LINTER = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(_STE_LINTER)
  return _STE_LINTER


def strict_lint(label: str, sections: list[str], adr: bool) -> int:
  """Check sentences per prose section and synonyms across the file."""
  failures = 0
  module = ste_linter()
  for number, text in enumerate(sections, start=1):
    if adr and ADR_REFERENCE.search(text):
      report(
        f"{label} section {number}", [], "A comment or docstring refers to an ADR."
      )
      failures += 1
      continue
    findings, _ = module.lint(text, filename=label)
    findings = [item for item in findings if item["rule"] != "synonym-rotation"]
    if not findings:
      continue
    report(f"{label} section {number}", findings)
    failures += 1
  findings, _ = module.lint("\n\n".join(sections), filename=label)
  rotations = [item for item in findings if item["rule"] == "synonym-rotation"]
  if rotations:
    report(f"{label} file-wide synonyms", rotations)
    failures += 1
  return failures


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
  """Lint every target file and fail on every code finding."""
  failures = 0
  for label, sections in extract_files().items():
    path = Path(label)
    source = path.read_text(encoding="utf-8")
    if sections:
      failures += strict_lint(str(path), sections, path.suffix == ".py")
    violations = comment_block_violations(path, source)
    if violations:
      print(f"--- {path}")
      print("\n".join(violations))
      failures += len(violations)
  for path in markdown_targets():
    text = path.read_text(encoding="utf-8")
    failures += lint(str(path), text, False)
    if path.name == "CHANGELOG.md":
      failures += bullet_cap(str(path), text)
  if failures:
    print(f"{failures} lint findings")
    return 1
  print("ok: covered prose and tracked code comments are clean")
  return 0


if __name__ == "__main__":
  sys.exit(main())
