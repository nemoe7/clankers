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
  lines = text[4:end].splitlines()
  index = 0
  while index < len(lines):
    line = lines[index]
    if not line.strip():
      index += 1
      continue
    if ":" not in line or line.startswith((" ", "\t")):
      errors.append(f"invalid frontmatter line: {line}")
      index += 1
      continue
    key, raw = line.split(":", 1)
    key = key.strip()
    raw = raw.strip()
    if raw in {">", "|"}:
      parts: list[str] = []
      index += 1
      while index < len(lines) and (lines[index].startswith((" ", "\t")) or not lines[index].strip()):
        parts.append(lines[index].strip())
        index += 1
      values[key] = " ".join(part for part in parts if part)
      continue
    values[key] = raw.strip('"').strip("'")
    index += 1
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
      if match:
        result[match.group(1)] = (match.group(2), match.group(3))
  return result


def measure(path: Path, kind: str) -> int | None:
  text = path.read_text(encoding="utf-8")
  if kind == "Unicode characters":
    return len(text)
  if kind == "UTF-8 file size":
    return len(text.encode("utf-8"))
  return None


def check_internal_links(path: Path, errors: list[str]) -> None:
  text = path.read_text(encoding="utf-8")
  for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", text):
    target = target.split("#", 1)[0]
    if not target or re.match(r"^[a-z][a-z0-9+.-]*://", target):
      continue
    candidate = (path.parent / target).resolve()
    if not candidate.exists():
      errors.append(f"{path.relative_to(ROOT)}: broken internal link {target}")


def main() -> int:
  errors: list[str] = []
  skills = sorted(p for p in SKILLS.iterdir() if p.is_dir() and not p.name.startswith("."))

  skills_readme = (SKILLS / "README.md").read_text(encoding="utf-8")
  readme_skills = set(re.findall(r"\[([a-z0-9-]+)\]\([a-z0-9-]+/SKILL\.md\)", skills_readme))
  actual_skills = {p.name for p in skills}
  if readme_skills != actual_skills:
    errors.append(f"skills/README.md list mismatch: documented={sorted(readme_skills)} actual={sorted(actual_skills)}")

  for skill in skills:
    path = skill / "SKILL.md"
    if not path.is_file():
      errors.append(f"{skill.relative_to(ROOT)}: missing SKILL.md")
      continue
    skill_text = path.read_text(encoding="utf-8")
    values, fm_errors = frontmatter(skill_text)
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
    if len(skill_text.splitlines()) > 500:
      errors.append(f"{path.relative_to(ROOT)}: SKILL.md exceeds 500 lines")
    for ref in re.findall(r"`([^`]+\.(?:md|py|txt|json|jsonc))`", skill_text):
      if ref.startswith(("http://", "https://")):
        continue
      candidate = skill / ref
      if "/" in ref and not candidate.exists():
        errors.append(f"{path.relative_to(ROOT)}: missing referenced file {ref}")

  for path in [README, SKILLS / "README.md", RULES / "README.md"]:
    check_internal_links(path, errors)

  budgets = read_budget_table()
  for relative, (kind, recorded) in budgets.items():
    path = ROOT / relative
    if not path.is_file():
      errors.append(f"README budget path missing: {relative}")
      continue
    value_now = measure(path, kind)
    if value_now is None:
      continue
    match = re.search(r"\d+", recorded)
    if not match or value_now != int(match.group()):
      errors.append(f"README budget stale for {relative}: recorded={recorded} actual={value_now}")

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
