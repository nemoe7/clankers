"""Root copies stay byte-identical to their `rules/` source."""

from __future__ import annotations

from ..repo import Repo

# Root `ARENA.md` copies the source that distribution pushes to target repos.
# The byte check guards against drift.
ROOT_COPIES = ("ARENA.md",)


def check_root_copies(repo: Repo, errors: list[str]) -> None:
  for name in ROOT_COPIES:
    source = repo.rules / name
    copy = repo.root / name
    fix = f"run `cp rules/{name} {name}`"

    if not source.is_file():
      errors.append(f"rules/{name} is missing")
    elif not copy.is_file():
      errors.append(f"{name}: root copy missing; {fix}")
    elif copy.read_bytes() != source.read_bytes():
      errors.append(f"{name}: root copy differs from rules/{name}; {fix}")
