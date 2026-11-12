"""Owner skills: `SKILL.md` frontmatter, naming, licenses, and the `skills/README.md` list."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from .repo import Repo

EXPECTED_SKILL_FIELDS = {
  "name",
  "description",
  "license",
  "compatibility",
  "metadata",
  "allowed-tools",
}
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
DOCUMENTED_SKILL_RE = re.compile(r"\[([a-z0-9-]+)\]\([a-z0-9-]+/SKILL\.md\)")
UPSTREAM_RE = re.compile(r"^[ \t]+upstream:", re.MULTILINE)
DESCRIPTION_LIMIT = 1024
SKILL_LINE_LIMIT = 500


def parse_frontmatter(text: str) -> tuple[dict[str, str], list[str]]:
  """Read a YAML frontmatter block. A nested mapping or list reads as empty text."""
  if not text.startswith("---\n"):
    return {}, ["missing YAML frontmatter"]

  end = text.find("\n---", 4)

  if end < 0:
    return {}, ["unterminated YAML frontmatter"]

  try:
    loaded = yaml.safe_load(text[4:end])
  except yaml.YAMLError as error:
    return {}, [f"invalid YAML frontmatter: {error}"]

  if loaded is None:
    return {}, []

  if not isinstance(loaded, dict):
    return {}, ["YAML frontmatter must be a mapping"]

  return {
    str(key): "" if isinstance(value, (dict, list)) else str(value)
    for key, value in loaded.items()
  }, []


def _skill_dirs(repo: Repo) -> list[Path]:
  return sorted(
    path
    for path in repo.skills.iterdir()
    if path.is_dir() and not path.name.startswith(".") and path.name != "refs"
  )


def _check_readme_list(repo: Repo, skills: list[Path], errors: list[str]) -> None:
  readme = repo.skills / "README.md"

  if not readme.is_file():
    errors.append("skills/README.md is missing")
    return

  documented = set(DOCUMENTED_SKILL_RE.findall(readme.read_text(encoding="utf-8")))
  actual = {path.name for path in skills}

  if documented != actual:
    errors.append(
      f"skills/README.md list mismatch: documented={sorted(documented)} actual={sorted(actual)}"
    )


def _check_license(
  skill: Path, label: str, text: str, values: dict[str, str], errors: list[str]
) -> None:
  license_value = str(values.get("license", ""))
  adapted = UPSTREAM_RE.search(text[: text.find("\n---", 4)])

  if adapted and not license_value:
    errors.append(
      f"{label}: adapted skill records metadata.upstream but declares no license"
    )

  if "LICENSE.txt" in license_value and not (skill / "LICENSE.txt").is_file():
    errors.append(f"{label}: license points at a missing LICENSE.txt")


def _check_skill(repo: Repo, skill: Path, errors: list[str]) -> None:
  path = skill / "SKILL.md"
  label = repo.relative(path)

  if not path.is_file():
    errors.append(f"{repo.relative(skill)}: missing SKILL.md")
    return

  text = path.read_text(encoding="utf-8")
  values, frontmatter_errors = parse_frontmatter(text)
  errors.extend(f"{label}: {error}" for error in frontmatter_errors)

  unknown = set(values) - EXPECTED_SKILL_FIELDS
  if unknown:
    errors.append(f"{label}: unknown frontmatter fields: {sorted(unknown)}")

  _check_license(skill, label, text, values, errors)

  name = values.get("name", "")
  if name != skill.name or not NAME_RE.fullmatch(name):
    errors.append(f"{label}: invalid name {name!r}")

  length = len(values.get("description", ""))
  if not 1 <= length <= DESCRIPTION_LIMIT:
    errors.append(
      f"{label}: description length is {length}, expected 1..{DESCRIPTION_LIMIT}"
    )

  if len(text.splitlines()) > SKILL_LINE_LIMIT:
    errors.append(f"{label}: SKILL.md exceeds {SKILL_LINE_LIMIT} lines")


def check_skills(repo: Repo, errors: list[str]) -> int:
  """Check every owner skill and return how many there are."""
  skills = _skill_dirs(repo)
  _check_readme_list(repo, skills, errors)

  for skill in skills:
    _check_skill(repo, skill, errors)

  return len(skills)
