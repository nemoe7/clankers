"""Tracked Git paths must stay unique on case-insensitive filesystems."""

from __future__ import annotations

import subprocess

from .repo import Repo


def check_case_collisions(repo: Repo, errors: list[str]) -> None:
  """Reject tracked Git paths that collide on case-insensitive filesystems."""
  if not (repo.root / ".git").exists():
    return

  proc = subprocess.run(
    ["git", "-C", str(repo.root), "ls-files"],
    capture_output=True,
    text=True,
    encoding="utf-8",
    errors="replace",
    check=False,
  )
  if proc.returncode != 0:
    return

  seen: dict[str, list[str]] = {}
  for line in filter(None, proc.stdout.splitlines()):
    seen.setdefault(line.casefold(), []).append(line)

  for paths in seen.values():
    if len(paths) > 1:
      errors.append(f"case-colliding tracked paths: {', '.join(sorted(paths))}")
