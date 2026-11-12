"""Tests for skill, link, and path checks."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from checks.links import check_links
from checks.paths import check_case_collisions
from checks.repo import DEFAULT_ROOT, Repo
from checks.skills import check_skills, parse_frontmatter

GOOD = "---\nname: {name}\ndescription: Does one thing.\n---\nBody\n"


def write(root: Path, relative: str, text: str) -> None:
  path = root / relative
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_text(text, encoding="utf-8")


def test_frontmatter_reads_scalars_and_blanks_nested_values():
  values, errors = parse_frontmatter("---\nname: a\nmetadata:\n  upstream: x\n---\n")
  assert errors == []
  assert values == {"name": "a", "metadata": ""}


@pytest.mark.parametrize(
  ("text", "message"),
  [
    ("no frontmatter", "missing YAML frontmatter"),
    ("---\nname: a\n", "unterminated YAML frontmatter"),
    ("---\n- a\n---\n", "YAML frontmatter must be a mapping"),
    ("---\nname: [\n---\n", "invalid YAML frontmatter"),
  ],
)
def test_frontmatter_reports_each_malformed_form(text: str, message: str):
  assert parse_frontmatter(text)[1][0].startswith(message)


def test_skills_pass_when_listed_and_well_formed(tmp_path: Path):
  write(tmp_path, "skills/alpha/SKILL.md", GOOD.format(name="alpha"))
  write(tmp_path, "skills/README.md", "- [alpha](alpha/SKILL.md)\n")
  errors: list[str] = []
  assert check_skills(Repo(tmp_path), errors) == 1
  assert errors == []


def test_skills_report_naming_listing_and_license_problems(tmp_path: Path):
  write(tmp_path, "skills/alpha/SKILL.md", GOOD.format(name="beta"))
  write(tmp_path, "skills/gamma/NOTES.md", "no skill file\n")
  write(
    tmp_path,
    "skills/delta/SKILL.md",
    "---\nname: delta\ndescription: x\nmetadata:\n  upstream: u\nextra: 1\n---\n",
  )
  write(tmp_path, "skills/README.md", "- [alpha](alpha/SKILL.md)\n")
  errors: list[str] = []
  assert check_skills(Repo(tmp_path), errors) == 3
  joined = "\n".join(errors)
  assert "skills/README.md list mismatch" in joined
  assert "skills/alpha/SKILL.md: invalid name 'beta'" in joined
  assert "skills/gamma: missing SKILL.md" in joined
  assert "skills/delta/SKILL.md: unknown frontmatter fields: ['extra']" in joined
  assert "adapted skill records metadata.upstream but declares no license" in joined


def test_skills_report_a_missing_readme_and_oversized_files(tmp_path: Path):
  write(tmp_path, "skills/alpha/SKILL.md", GOOD.format(name="alpha") + "line\n" * 500)
  errors: list[str] = []
  check_skills(Repo(tmp_path), errors)
  assert "skills/README.md is missing" in errors
  assert "skills/alpha/SKILL.md: SKILL.md exceeds 500 lines" in errors


def test_links_check_docs_and_skill_readmes_and_skip_code_and_urls(tmp_path: Path):
  write(
    tmp_path,
    "docs/note.md",
    "`![alt](src =320x200)` [ok](other.md) [web](https://example.com/x) "
    "[anchor](#top) [missing](missing.md)\n",
  )
  write(tmp_path, "docs/other.md", "text\n")
  write(tmp_path, "skills/s/README.md", "[gone](gone.md)\n")
  errors: list[str] = []
  check_links(Repo(tmp_path), errors)
  assert sorted(errors) == [
    "docs/note.md: broken internal link missing.md",
    "skills/s/README.md: broken internal link gone.md",
  ]


def test_case_collisions_reject_case_only_tracked_duplicates(
  tmp_path: Path, monkeypatch
):
  (tmp_path / ".git").mkdir()

  def fake_run(cmd, **kwargs):
    assert cmd[:3] == ["git", "-C", str(tmp_path)]
    return subprocess.CompletedProcess(
      cmd,
      0,
      stdout=".github/PULL_REQUEST_TEMPLATE.md\n.github/pull_request_template.md\nREADME.md\n",
      stderr="",
    )

  monkeypatch.setattr("checks.paths.subprocess.run", fake_run)
  errors: list[str] = []
  check_case_collisions(Repo(tmp_path), errors)
  assert errors == [
    "case-colliding tracked paths: .github/PULL_REQUEST_TEMPLATE.md, .github/pull_request_template.md"
  ]


def test_case_collisions_skip_a_tree_without_git(tmp_path: Path):
  errors: list[str] = []
  check_case_collisions(Repo(tmp_path), errors)
  assert errors == []


def test_markdownlint_scope_includes_readmes_except_agents(tmp_path: Path):
  cli = shutil.which(
    "markdownlint-cli2", path=str(DEFAULT_ROOT / "node_modules" / ".bin")
  )
  if cli is None:
    pytest.skip("Install npm dependencies to run markdownlint")
  shutil.copy2(DEFAULT_ROOT / ".markdownlint-cli2.jsonc", tmp_path)
  included = [
    "README.md",
    "docs/archive/old/README.md",
    "rules/README.md",
    "skills/example/README.md",
    "ordinary.md",
  ]
  excluded = [
    ".agents/README.md",
    ".agents/nested/README.md",
    "AGENTS.md",
    "docs/archive/old/notes.md",
    "skills/example/SKILL.md",
    "system-prompts/prompt.md",
  ]
  for name in included + excluded:
    write(tmp_path, name, "Not a heading\n")
  result = subprocess.run(
    [cli],
    cwd=tmp_path,
    capture_output=True,
    text=True,
    encoding="utf-8",
    check=False,
  )
  output = result.stdout + result.stderr
  assert result.returncode == 1, output
  errors = output.splitlines()
  for name in included:
    assert any(line.startswith(f"{name}:1 ") for line in errors), output
  for name in excluded:
    assert not any(line.startswith(f"{name}:1 ") for line in errors), output
