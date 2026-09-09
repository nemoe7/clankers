#!/usr/bin/env python3
"""Validate repository structure and generated README measurements."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / "skills"
RULES = ROOT / "rules"
README = ROOT / "README.md"

EXPECTED_SKILL_FIELDS = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
README_ROW_RE = re.compile(r"^\| `([^`]+)` \| `([^`]+)` \| (.+) \|$")


def frontmatter(text: str) -> tuple[dict[str, str], list[str]]:
  errors: list[str] = []
  if not text.startswith("---\n"):
    return {}, ["missing YAML frontmatter"]
  end = text.find("\n---", 4)
  if end < 0:
    return {}, ["unterminated YAML frontmatter"]
  values: dict[str, str] = {}
  for line in text[4:end].splitlines():
    if not line.strip():
      continue
    if ":" not in line:
      errors.append(f"invalid frontmatter line: {line}")
      continue
    key, value = line.split(":", 1)
    values[key.strip()] = value.strip().strip('"').strip("'")
  return values, errors


def read_budget_table() -> dict[str, tuple[str, str]]:
  result: dict[str, tuple[str, str]] = {}
  in_table = False
  for line in README.read_text(encoding="utf-8").splitlines():
    if line == "| File | Measure | Current |":
      in_table = True
      continue
    if in_table and not line.startswith("|"):
      break
    if in_table:
      match = README_ROW_RE.match(line)
      if match and match.group(1) != "File":
        result[match.group(1)] = (match.group(2), match.group(3))
  return result


def measure(path: Path, kind: str) -> int | None:
  text = path.read_text(encoding="utf-8")
  if kind == "Unicode characters":
    return len(text)
  if kind == "UTF-8 file size":
    return len(text.encode("utf-8"))
  return None


def main() -> int:
  errors: list[str] = []
  skills = sorted(p for p in SKILLS.iterdir() if p.is_dir() and not p.name.startswith("."))

  readme_skills = set(re.findall(r"\[([a-z0-9-]+)\]\([a-z0-9-]+/SKILL\.md\)", (SKILLS / "README.md").read_text(encoding="utf-8")))
  actual_skills = {p.name for p in skills}
  if readme_skills != actual_skills:
    errors.append(f"skills/README.md list mismatch: documented={sorted(readme_skills)} actual={sorted(actual_skills)}")

  for skill in skills:
    path = skill / "SKILL.md"
    if not path.is_file():
      errors.append(f"{skill.relative_to(ROOT)}: missing SKILL.md")
      continue
    values, fm_errors = frontmatter(path.read_text(encoding="utf-8"))
    errors.extend(f"{path.relative_to(ROOT)}: {error}" for error in fm_errors)
    unknown = set(values) - EXPECTED_SKILL_FIELDS
    if unknown:
      errors.append(f"{path.relative_to(ROOT)}: unknown frontmatter fields: {sorted(unknown)}")
    name = values.get("name", "")
    description = values.get("description", "")
    if name != skill.name or not NAME_RE.fullmatch(name):
      errors.append(f"{path.relative_to(ROOT)}: invalid name {name!r}")
    if not 1 <= len(description) <= 1024:
      errors.append(f"{path.relative_to(ROOT)}: description length is {len(description)}, expected 1..1024")
    for ref in re.findall(r"`([^`]+\.(?:md|py|txt|json|jsonc))`", path.read_text(encoding="utf-8")):
      if ref.startswith(("http://", "https://")):
        continue
      candidate = skill / ref
      if not candidate.exists() and ("/" in ref or ref.startswith(("references/", "templates/", "scripts/", "assets/"))):
        errors.append(f"{path.relative_to(ROOT)}: missing referenced file {ref}")

  budgets = read_budget_table()
  for relative, (kind, recorded) in budgets.items():
    path = ROOT / relative
    if not path.is_file():
      errors.append(f"README budget path missing: {relative}")
      continue
    value = measure(path, kind)
    if value is None:
      continue
    recorded_value = int(re.search(r"\d+", recorded).group())
    if value != recorded_value:
      errors.append(f"README budget stale for {relative}: recorded={recorded_value} actual={value}")

  chat = RULES / "CHATGPT.txt"
  if len(chat.read_text(encoding="utf-8")) > 1500:
    errors.append("rules/CHATGPT.txt exceeds 1,500 Unicode characters")

  if errors:
    print("Validation failed:")
    for error in errors:
      print(f"- {error}")
    return 1
  print(f"Validation passed: {len(skills)} skills and README measurements checked.")
  return 0


if __name__ == "__main__":
  sys.exit(main())
