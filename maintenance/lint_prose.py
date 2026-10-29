"""Lint covered prose and tracked code comments. Run: python maintenance/lint_prose.py"""

import argparse
import configparser
import importlib.util
import subprocess
import sys
import tokenize
from pathlib import Path

from extract_prose import extract_files

SKIP_PARTS = {".git", ".venv", "node_modules", ".agents", "arena-state", "__pycache__"}
_NEMOIZER = None


def markdown_targets() -> list[Path]:
  """Collect docs and every README outside the skip set."""
  found: list[Path] = []
  for path in sorted(Path(".").rglob("*.md")):
    if any(part in SKIP_PARTS for part in path.parts):
      continue
    if path.name in {"README.md", "CHANGELOG.md"} or path.parts[0] == "docs":
      found.append(path)
  return found


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
  with module.file_scope(Path(label), None if strict else text):
    rows = module.prose_review(
      Path(label),
      text,
      module.ACTIVE_CONFIG.get("context") or "description",
      module.ACTIVE_CONFIG.get("paragraph_cap") or module.PARAGRAPH_CAP,
    )
  for row in rows:
    rule = row["rule"]
    if rule not in blocking and rule != "STE901":
      continue
    findings.append(
      {
        "line": row["line"],
        "col": row["column"],
        "level": "advisory-free" if rule in blocking else "advisory",
        "rule": rule,
        "message": (
          f"{row['count']} -> {row['cap']}"
          if rule in blocking
          else "passive voice (manual review)"
        ),
      }
    )
  return findings


def lint(label: str, text: str, strict: bool = False) -> int:
  """Run the linter once, failing only on hard findings."""
  findings = _nemoizer_findings(label, text, strict=strict)
  hard = any(item["level"] == "advisory-free" for item in findings)
  if not findings or not hard:
    return 0
  report(label, findings)
  return 1


def strict_lint(label: str, sections: list[str]) -> int:
  """Check sentences per prose section."""
  failures = 0
  for number, text in enumerate(sections, start=1):
    findings = _nemoizer_findings(label, text, strict=True)
    if not findings:
      continue
    report(f"{label} section {number}", findings)
    if any(item["level"] == "advisory-free" for item in findings):
      failures += 1
  return failures


def nemoizer_scope(path: Path, text: str) -> tuple[str, str]:
  """Measure only declared human documentation in repository checks."""
  human = (
    path.name in {"README.md", "CHANGELOG.md", "INSTALL.md"} or "docs" in path.parts
  )
  return ("description", text) if human else ("unknown", "")


def nemoizer_linter():
  """Load the bundled scanner beside its shared prose parser."""
  global _NEMOIZER
  if _NEMOIZER is not None:
    return _NEMOIZER
  root = Path(__file__).resolve().parents[1]
  path = root / "skills/nemoizer/scripts/nemoize.py"
  spec = importlib.util.spec_from_file_location("repository_nemoizer", path)
  module = importlib.util.module_from_spec(spec)
  sys.path.insert(0, str(path.parent))
  try:
    spec.loader.exec_module(module)
  finally:
    sys.path.pop(0)
  module.BASE_CONFIG = module.load_config([str(root)])
  module.ACTIVE_CONFIG = module.BASE_CONFIG
  _NEMOIZER = module
  return module


def nemoizer_main(argv: list[str]) -> int:
  """Keep rotations and test checks while applying repository prose scopes."""
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("--ignore", action="append", default=[])
  parser.add_argument("targets", nargs="*", default=["."])
  args = parser.parse_args(argv)
  module = nemoizer_linter()
  module.BASE_CONFIG = module.load_config(args.targets)
  module.ACTIVE_CONFIG = module.BASE_CONFIG
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
      file_cfg = module.file_config(path, scoped)
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
        for row in module.source_prose(
          path,
          scoped,
          file_cfg.get("context") or context,
          file_cfg.get("paragraph_cap") or module.PARAGRAPH_CAP,
        )
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
    if sections:
      failures += strict_lint(str(Path(label)), sections)
  for path in markdown_targets():
    text = path.read_text(encoding="utf-8")
    failures += lint(str(path), text)
  if failures:
    print(f"{failures} lint findings")
    return 1
  print("ok: covered prose and tracked code comments are clean")
  return 0


if __name__ == "__main__":
  sys.exit(main())
