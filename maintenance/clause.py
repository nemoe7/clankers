"""Measure one clause line against its baseline and run per-clause parity checks.

Usage:
  python maintenance/clause.py <clause file path> <raw 1-indexed line> "<candidate clause>"

Reads the baseline line from the named clause file (refs, live, or a wenyan copy).
Measures candidate and baseline in o200k_base tokens.
Applies the per-clause token cap: rough count must not exceed the baseline.
Runs keyword parity: dropped or added MUST, NEVER, ALWAYS, or Prefer, and "do not" wording.

Exit codes: 0 when the candidate passes cap and keyword checks, 1 otherwise,
2 on usage errors. Nothing is written into the repo.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

from checks.measure import token_count
from checks.parity.compare import count_tokens
from checks.parity.keywords import compare_keyword_counts

EXIT_OK = 0
EXIT_FAIL = 1
EXIT_USAGE = 2


def _usage_error(message: str) -> int:
  print(f"clause.py: {message}", file=sys.stderr)
  return EXIT_USAGE


def main(argv: list[str] | None = None) -> int:
  parser = argparse.ArgumentParser(
    prog="maintenance/clause.py",
    description="Measure a candidate clause against a baseline line of a clause file.",
  )
  parser.add_argument(
    "file",
    help="Clause file whose baseline line is compared against (refs/live/wenyan).",
  )
  parser.add_argument(
    "line", type=int, help="Raw 1-indexed line of the baseline clause."
  )
  parser.add_argument("candidate", help="Candidate replacement clause text.")
  args = parser.parse_args(argv)

  path = Path(args.file)
  if not path.is_file():
    return _usage_error(f"file not found: {path}")

  lines = path.read_text(encoding="utf-8").splitlines()
  if args.line < 1 or args.line > len(lines):
    return _usage_error(f"line {args.line} out of range (file has {len(lines)} lines)")

  baseline_line = lines[args.line - 1]
  if not baseline_line.strip():
    return _usage_error(f"line {args.line} is blank")
  if baseline_line.lstrip().startswith("## "):
    return _usage_error(
      f"line {args.line} is a heading; parity checks apply to clause lines only"
    )

  errors: list[str] = []
  compare_keyword_counts(
    f"{path} line {args.line}",
    baseline_line,
    args.candidate,
    errors,
  )

  candidate_rough = count_tokens(args.candidate)
  baseline_rough = count_tokens(baseline_line)
  cap = "within cap" if candidate_rough <= baseline_rough else "exceeds cap"

  # o200k_base tokens: gpt-tokenizer reads files, so measure both through temp files.
  with tempfile.TemporaryDirectory() as scratch:
    scratch_path = Path(scratch)
    candidate_path = scratch_path / "candidate.md"
    baseline_path = scratch_path / "baseline.md"
    candidate_path.write_text(args.candidate, encoding="utf-8")
    baseline_path.write_text(baseline_line, encoding="utf-8")
    candidate_tokens = token_count(candidate_path)
    baseline_tokens = token_count(baseline_path)

  report = {
    "candidate": {"tokens": candidate_tokens, "rough": candidate_rough},
    "baseline": {"tokens": baseline_tokens, "rough": baseline_rough},
    "cap": cap,
    "keywords": errors,
  }
  print(json.dumps(report))

  return EXIT_OK if cap == "within cap" and not errors else EXIT_FAIL


if __name__ == "__main__":
  sys.exit(main())
