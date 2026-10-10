#!/usr/bin/env python3
"""Check version bumps for versioned userscripts.

Versioned modules in this repo:
- userscripts/arena.user.js
- userscripts/chatgpt.user.js

When a userscript file changes, its @version must be greater than the base.
Reports affected files first, then checks version ordering.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

VERSIONED_FILES = [
  ROOT / "userscripts" / "arena.user.js",
  ROOT / "userscripts" / "chatgpt.user.js",
]

VERSION_RE = re.compile(r"//\s*@version\s+([0-9]+(?:\.[0-9]+)+)")


def parse_userscript_version(text: str) -> tuple[int, ...] | None:
  """Extract dotted version from userscript header, or None."""
  for line in text.splitlines():
    m = VERSION_RE.search(line)
    if m:
      raw = m.group(1)
      parts = raw.split(".")
      if all(p.isdigit() for p in parts):
        return tuple(int(p) for p in parts)
      return None
  return None


def parse_version_string(value: str) -> tuple[int, ...] | None:
  """Parse dotted integer version string, or None."""
  if not isinstance(value, str) or not value:
    return None
  parts = value.split(".")
  if not parts or any(not p.isdigit() for p in parts):
    return None
  return tuple(int(p) for p in parts)


def _display_path(path: Path) -> str:
  try:
    # If path is relative, try to resolve against ROOT for display, else keep as is
    if not path.is_absolute():
      # For relative paths like userscripts/arena.user.js, keep relative
      return str(path)
    return str(path.relative_to(ROOT))
  except ValueError:
    return str(path)


def check_file(path: Path, errors: list[str]) -> tuple[int, ...] | None:
  if not path.is_file():
    errors.append(f"{_display_path(path)}: missing file")
    return None
  text = path.read_text(encoding="utf-8")
  ver = parse_userscript_version(text)
  if ver is None:
    # Try to display raw
    m = VERSION_RE.search(text)
    raw = m.group(1) if m else "<not found>"
    errors.append(f"{_display_path(path)}: version {raw!r} is not dotted integers")
    return None
  # Also check @name contains same version if present
  name_re = re.compile(r"//\s*@name\s+.*v([0-9]+(?:\.[0-9]+)+)")
  for line in text.splitlines():
    nm = name_re.search(line)
    if nm:
      name_ver = parse_version_string(nm.group(1))
      if name_ver is not None and name_ver != ver:
        errors.append(
          f"{_display_path(path)}: @name version {nm.group(1)} "
          f"differs from @version {'.'.join(map(str, ver))}"
        )
      break
  return ver


def check_version_bump(base_path: Path, current_path: Path, errors: list[str]) -> None:
  """Require current version > base version."""
  if not base_path.is_file():
    errors.append(f"{_display_path(base_path)}: missing base file")
    return
  if not current_path.is_file():
    errors.append(f"{_display_path(current_path)}: missing current file")
    return

  base_text = base_path.read_text(encoding="utf-8")
  cur_text = current_path.read_text(encoding="utf-8")

  base_ver = parse_userscript_version(base_text)
  cur_ver = parse_userscript_version(cur_text)

  base_raw_match = VERSION_RE.search(base_text)
  cur_raw_match = VERSION_RE.search(cur_text)
  base_raw = base_raw_match.group(1) if base_raw_match else "<not found>"
  cur_raw = cur_raw_match.group(1) if cur_raw_match else "<not found>"

  if base_ver is None:
    errors.append(
      f"{_display_path(base_path)}: version {base_raw!r} is not dotted integers"
    )
    return
  if cur_ver is None:
    errors.append(
      f"{_display_path(current_path)}: version {cur_raw!r} is not dotted integers"
    )
    return

  if cur_ver <= base_ver:
    errors.append(
      f"{_display_path(current_path)}: version {cur_raw} must be greater than base {base_raw}"
    )


def run_self_check() -> None:
  assert parse_userscript_version("// @version      1.10.16\n") == (1, 10, 16)
  assert parse_userscript_version("// @version 1.3.4\n") == (1, 3, 4)
  assert parse_userscript_version("// @version 2.0\n") == (2, 0)
  assert parse_userscript_version("no version") is None
  assert parse_version_string("1.2.0") == (1, 2, 0)
  assert parse_version_string("1.2.1") > parse_version_string("1.2.0")
  assert parse_version_string("2.0.0") > parse_version_string("1.9.9")
  assert parse_version_string("1.10.0") > parse_version_string("1.9.0")
  assert parse_version_string("") is None
  assert parse_version_string("1.2.a") is None
  # version bump
  import tempfile

  with tempfile.TemporaryDirectory() as td:
    base = Path(td) / "base.js"
    cur = Path(td) / "cur.js"
    base.write_text("// @version 1.10.16\n", encoding="utf-8")
    cur.write_text("// @version 1.10.17\n", encoding="utf-8")
    errs: list[str] = []
    check_version_bump(base, cur, errs)
    assert not errs, f"expected no errors, got {errs}"
    cur.write_text("// @version 1.10.16\n", encoding="utf-8")
    errs = []
    check_version_bump(base, cur, errs)
    assert errs, "expected error when version not bumped"
  print("ok version and bump checks")


def main() -> int:
  parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
  parser.add_argument(
    "--file",
    type=Path,
    help="Current userscript file to check (default: all versioned files)",
  )
  parser.add_argument(
    "--base-file",
    type=Path,
    help="Base userscript file to compare version against",
  )
  parser.add_argument(
    "--self-check",
    action="store_true",
    help="Run version-parser assertions and exit",
  )
  args = parser.parse_args()

  if args.self_check:
    run_self_check()
    return 0

  errors: list[str] = []

  if args.file and args.base_file:
    # Single file comparison mode
    # Report affected file first
    print(f"Affected file: {_display_path(args.file)}")
    check_version_bump(args.base_file, args.file, errors)
  elif args.file:
    print(f"Affected file: {_display_path(args.file)}")
    check_file(args.file, errors)
  else:
    # Default: check all versioned files, report list first
    existing = [p for p in VERSIONED_FILES if p.is_file()]
    if existing:
      print("Versioned modules checked:")
      for p in existing:
        print(f"- {_display_path(p)}")
    for path in VERSIONED_FILES:
      check_file(path, errors)

  if errors:
    for e in errors:
      print(e, file=sys.stderr)
    print(f"userscript version check failed: {len(errors)} problem(s)", file=sys.stderr)
    return 1

  if args.base_file:
    print(
      f"userscript version check passed: {_display_path(args.file) if args.file else 'all'} "
      f"version bumped against base."
    )
  else:
    print(
      f"userscript version check passed: {len(VERSIONED_FILES)} versioned modules checked."
    )
  return 0


if __name__ == "__main__":
  sys.exit(main())
