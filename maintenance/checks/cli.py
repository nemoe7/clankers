"""Command line: run every stage in order and report one verdict."""

from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Callable, Sequence
from typing import Any

from .budgets import check_budgets, update_readme_measurements
from .links import check_links
from .parity import check_parity
from .paths import check_case_collisions
from .prose import check_nemoize
from .repo import DEFAULT_ROOT, Repo
from .report import LOG, Notes, run_check
from .skills import check_skills

Stage = tuple[str, Callable[[Repo, list[str]], Any]]

# Stages that collect grouped warnings instead of logging per line.
NOTED_STAGES = {"parity"}

# Run order. A stage appends to the shared error list, so one failure never hides the rest.
STAGES: tuple[Stage, ...] = (
  ("skills", check_skills),
  ("links", check_links),
  ("budgets", check_budgets),
  ("parity", check_parity),
  ("paths", check_case_collisions),
  ("nemoize", check_nemoize),
)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
  parser = argparse.ArgumentParser(
    description="Validate the repository and optionally update README measurements."
  )
  parser.add_argument(
    "--update",
    action="store_true",
    help="Update README measurements before validation.",
  )
  return parser.parse_args(argv)


def run_stages(
  repo: Repo, errors: list[str], stages: Sequence[Stage]
) -> dict[str, Any]:
  """Run each stage and return what it reported, keyed by stage name."""
  reported: dict[str, Any] = {}
  for name, check in stages:
    notes = Notes() if name in NOTED_STAGES else None

    def run(check=check, notes=notes) -> Any:
      if notes is None:
        return check(repo, errors)
      return check(repo, errors, notes)

    reported[name] = run_check(name, errors, run, warnings=notes.count if notes else 0)
  return reported


def update_readme(repo: Repo) -> None:
  changed = run_check("README update", [], lambda: update_readme_measurements(repo))
  LOG.info(
    "Updated README measurements."
    if changed
    else "README measurements already up to date."
  )


def main(argv: Sequence[str] | None = None, repo: Repo | None = None) -> int:
  # Windows consoles default to cp1252. Force UTF-8 output so any decoded
  # replacement character prints instead of crashing the report.
  for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
      stream.reconfigure(encoding="utf-8", errors="replace")

  repo = repo or Repo(DEFAULT_ROOT)
  args = parse_args(argv)
  started = time.perf_counter()

  if args.update:
    try:
      update_readme(repo)
    except (RuntimeError, OSError) as exc:
      LOG.error("README update failed: %s", exc)
      return 1

  errors: list[str] = []
  run_stages(repo, errors, STAGES)
  span = time.perf_counter() - started

  if errors:
    LOG.error("check: fail %.2fs", span)
    for error in errors:
      LOG.error("- %s", error)
    return 1

  LOG.info("check: pass %.2fs", span)
  return 0
