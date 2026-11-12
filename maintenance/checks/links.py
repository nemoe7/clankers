"""Internal Markdown links must resolve."""

from __future__ import annotations

import re
from pathlib import Path

from .repo import Repo

CODE_SPAN_RE = re.compile(r"(`+)[^`\n]*?\1")
LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
URL_RE = re.compile(r"^[a-z][a-z0-9+.-]*://", re.IGNORECASE)


def check_internal_links(repo: Repo, path: Path, errors: list[str]) -> None:
  text = CODE_SPAN_RE.sub("", path.read_text(encoding="utf-8"))

  for target in LINK_RE.findall(text):
    target = target.split("#", 1)[0].strip()

    if not target or URL_RE.match(target):
      continue

    if not (path.parent / target).resolve().exists():
      errors.append(f"{repo.relative(path)}: broken internal link {target}")


def check_links(repo: Repo, errors: list[str]) -> None:
  documents = [
    repo.readme,
    repo.rules / "README.md",
    *(sorted(repo.docs.rglob("*.md")) if repo.docs.is_dir() else ()),
    *(sorted(repo.skills.rglob("README.md")) if repo.skills.is_dir() else ()),
  ]

  for path in documents:
    if path.is_file():
      check_internal_links(repo, path, errors)
