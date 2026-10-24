"""Lint covered prose and tracked code comments. Run: python maintenance/lint_prose.py"""

import argparse
import configparser
import importlib.util
import re
import subprocess
import sys
import tokenize
from pathlib import Path

from extract_prose import (
  comment_lines,
  extract_files,
  python_comments,
  span_comments,
)

SKIP_PARTS = {".git", ".venv", "node_modules", ".agents", "arena-state", "__pycache__"}
ADR_REFERENCE = re.compile(r"\bADR[- ]?\d|docs/adr")
COMMENT_BLOCK_CAP = 2
DIRECTIVE_MARKER = re.compile(
  r"^\s*(?:#|//)\s*(?:arena-preview-[\w-]+|case:\s*[\w-]+|shellcheck\s+disable=\S+|"
  r"nonemo:\s*[A-Za-z0-9_-]+|noqa(?::.*)?|type:\s*ignore(?:\[.*\])?|pragma:\s*no cover|region|endregion)\s*$",
  re.IGNORECASE,
)
_NEMOIZER = None
STRICT_PASSIVE_RE = re.compile(
  r"\b(?:is|are|was|were|been|being)\s+[a-z]{3,}ed\b",
  re.IGNORECASE,
)
SYNONYM_GROUPS = (
  ("check", "validate"),
  ("delete", "remove"),
  ("start", "begin"),
  ("stop", "halt"),
  ("modify", "alter"),
)


def directive_marker_lines(source: str, path: Path | None = None) -> set[int]:
  """Return comment lines that carry required tool directives."""
  numbers = {
    number
    for number, line in enumerate(source.splitlines(), start=1)
    if DIRECTIVE_MARKER.match(line)
  }
  if path is not None:
    comments = (
      python_comments(source)
      if path.suffix == ".py"
      else span_comments(path, source) or []
    )
    numbers.update(
      first
      for text, first, last in comments
      if first == last and DIRECTIVE_MARKER.fullmatch("# " + text)
    )
  return numbers


def comment_block_violations(path: Path, source: str) -> list[str]:
  """Report ordinary comment blocks that exceed the line cap."""
  violations: list[str] = []
  start = None
  previous = None
  numbers = sorted(comment_lines(path, source) - directive_marker_lines(source, path))
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


def _nemoizer_findings(label: str, text: str, strict: bool = False) -> list[dict]:
  """Collect nemoizer findings for one prose block or section."""
  module = nemoizer_linter()
  blocking = {"STE001", "STE100", "STE300"}
  if not strict:
    blocking |= {"STE200", "NMP100", "NMO003"}
  findings: list[dict] = []
  for row in module.prose_review(
    Path(label), text, "description", module.PARAGRAPH_CAP
  ):
    rule = row["rule"]
    if rule in blocking:
      findings.append(
        {
          "line": row["line"],
          "col": row["column"],
          "level": "advisory-free",
          "rule": rule,
          "message": f"{row['count']} -> {row['cap']}",
        }
      )
  for line_no, line in enumerate(text.splitlines(), start=1):
    for match in STRICT_PASSIVE_RE.finditer(line):
      findings.append(
        {
          "line": line_no,
          "col": match.start() + 1,
          "level": "advisory",
          "rule": "STE901",
          "message": f"passive voice '{match.group(0)}'",
        }
      )
  words = set(re.findall(r"[a-z]+", text.lower()))
  for first, second in SYNONYM_GROUPS:
    if first in words and second in words:
      findings.append(
        {
          "line": 1,
          "col": 1,
          "level": "advisory",
          "rule": "synonym-rotation",
          "message": f"uses both '{first}' and '{second}'",
        }
      )
  return findings


def lint(label: str, text: str, adr: bool, strict: bool = False) -> int:
  """Run the linter once, failing on a hard finding, or on any finding in strict mode."""
  if adr and ADR_REFERENCE.search(text):
    report(label, [], "A comment or docstring refers to an ADR.")
    return 1
  findings = _nemoizer_findings(label, text, strict=strict)
  hard = any(item["level"] == "advisory-free" for item in findings)
  if not findings or not (strict or hard):
    return 0
  report(label, findings)
  return 1


def strict_lint(label: str, sections: list[str], adr: bool) -> int:
  """Check sentences per prose section and synonyms across the file."""
  failures = 0
  for number, text in enumerate(sections, start=1):
    if adr and ADR_REFERENCE.search(text):
      report(
        f"{label} section {number}", [], "A comment or docstring refers to an ADR."
      )
      failures += 1
      continue
    findings = _nemoizer_findings(label, text, strict=True)
    findings = [item for item in findings if item["rule"] != "synonym-rotation"]
    if not findings:
      continue
    report(f"{label} section {number}", findings)
    failures += 1
  combined = _nemoizer_findings(label, "\n\n".join(sections), strict=True)
  rotations = [item for item in combined if item["rule"] == "synonym-rotation"]
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


def nemoizer_scope(path: Path, text: str) -> tuple[str, str]:
  """Measure only declared human documentation in repository checks."""
  human = (
    path.name in {"README.md", "CHANGELOG.md", "INSTALL.md"} or "docs" in path.parts
  )
  return ("description", text) if human else ("unknown", "")


def nemoizer_linter():
  """Load the bundled scanner beside its shared prose parser."""
  path = Path(__file__).resolve().parents[1] / "skills/refs/nemoizer/scripts/nemoize.py"
  spec = importlib.util.spec_from_file_location("repository_nemoizer", path)
  module = importlib.util.module_from_spec(spec)
  sys.path.insert(0, str(path.parent))
  try:
    spec.loader.exec_module(module)
  finally:
    sys.path.pop(0)
  return module


def nemoizer_main(argv: list[str]) -> int:
  """Keep rotations and test checks while applying repository prose scopes."""
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("--ignore", action="append", default=[])
  parser.add_argument("targets", nargs="*", default=["."])
  args = parser.parse_args(argv)
  module = nemoizer_linter()
  findings, _ = module.scan(args.targets, args.ignore)
  errors, tests = [], []
  for path in module.walk(args.targets, args.ignore):
    text = module.text_file(path)
    if text is None:
      continue
    try:
      if module.is_test_file(path, text, set()):
        tests.append(str(path))
      context, scoped = nemoizer_scope(path, text)
      if not scoped:
        continue
      scoped_lines = scoped.splitlines()
      findings.extend(
        module.format_finding(
          row["path"],
          row["line"],
          row["rule"],
          module.describe_finding(row),
          scoped_lines[row["line"] - 1]
          if 0 < row["line"] <= len(scoped_lines)
          else None,
          status=row.get("status"),
        )
        for row in module.source_prose(path, scoped, context, module.PARAGRAPH_CAP)
      )
    except (
      SyntaxError,
      tokenize.TokenError,
      configparser.Error,
      RecursionError,
      ValueError,
      OSError,
      RuntimeError,
      subprocess.SubprocessError,
    ) as error:
      errors.append(f"{path}: {type(error).__name__}: {error}")
  result = module.review_tests(tests)
  for row in result["findings"]:
    test_lines = (module.text_file(Path(row["path"])) or "").splitlines()
    findings.append(
      module.format_finding(
        row["path"],
        row["line"],
        row["rule"],
        row["evidence"],
        test_lines[row["line"] - 1] if 0 < row["line"] <= len(test_lines) else None,
      )
    )
  errors.extend(
    f"{row['path']}: tests not checked: {row['reason']}"
    for row in result["coverage"]
    if row["status"] != "checked"
  )
  errors.extend(f"{row['path']}: {row['type']}" for row in result["errors"])
  print(
    "\n".join(findings) + ("\n" + module.format_summary(findings) if findings else "")
  )
  print(
    "Repository length scope: human documentation only, at 25 words and four sentences. Test discovery is static.",
    file=sys.stderr,
  )
  if errors:
    print("\n".join(errors), file=sys.stderr)
    return 2
  return int(any(not module.is_advisory(finding) for finding in findings))


def main() -> int:
  """Lint every target file and fail on every code finding."""
  if sys.argv[1:2] == ["--nemoizer"]:
    return nemoizer_main(sys.argv[2:])
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
