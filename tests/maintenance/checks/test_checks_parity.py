"""Tests for the refs/live parity gates."""

from __future__ import annotations

from pathlib import Path

from checks.parity import check_parity
from checks.parity.prompts import check_system_prompt_parity, prompt_sections
from checks.parity.root_copies import check_root_copies
from checks.parity.rules import check_rule_parity, section_rule_counts
from checks.parity.skill_refs import check_skill_refs_parity
from checks.repo import DEFAULT_ROOT, Repo


def write(root: Path, relative: str, text: str) -> None:
  path = root / relative
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_text(text, encoding="utf-8")


def test_root_arena_is_a_regular_copy_of_the_rule_source():
  root = DEFAULT_ROOT / "ARENA.md"
  assert root.is_file()
  assert not root.is_symlink()
  assert root.read_bytes() == (DEFAULT_ROOT / "rules" / "ARENA.md").read_bytes()


def test_this_repository_passes_every_parity_gate():
  errors: list[str] = []
  check_parity(Repo(DEFAULT_ROOT), errors)
  assert errors == []


def test_skill_refs_parity_accepts_compressed_live_files(tmp_path: Path):
  write(tmp_path, "skills/refs/sample/SKILL.md", "Name\n\nFirst rule.\nSecond rule.\n")
  write(tmp_path, "skills/sample/SKILL.md", "Name\n\nFirst and second rule.\n")
  errors: list[str] = []
  check_skill_refs_parity(Repo(tmp_path), errors)
  assert errors == []


def test_skill_refs_parity_rejects_a_live_only_line(tmp_path: Path):
  write(tmp_path, "skills/refs/sample/SKILL.md", "Name\n\nFirst rule.\nSecond rule.\n")
  write(
    tmp_path,
    "skills/sample/SKILL.md",
    "Name\n\nFirst rule.\nSecond rule.\nThird rule.\n",
  )
  errors: list[str] = []
  check_skill_refs_parity(Repo(tmp_path), errors)
  assert len(errors) == 1
  assert "compression may merge lines but never add them" in errors[0]


def test_skill_refs_parity_rejects_a_baseline_without_a_live_file(tmp_path: Path):
  write(tmp_path, "skills/refs/sample/SKILL.md", "Name\n")
  errors: list[str] = []
  check_skill_refs_parity(Repo(tmp_path), errors)
  assert errors == [
    "skills/sample/SKILL.md: refs counterpart exists without a live file"
  ]


def test_section_rule_counts_split_on_second_level_headings():
  text = "# T\n\n## A\n\n- one\n- two\n\n## B\n- three\n"
  assert section_rule_counts(text) == [("A", 2), ("B", 1)]


def rule_tree(root: Path, live: str) -> Repo:
  for name in ("CORE.md", "ARENA.md", "KILO.md"):
    write(root, f"rules/refs/{name}", "## A\n- one\n- two\n")
    write(root, f"rules/{name}", "## A\n- one\n- two\n")
  for live_name, ref_name in (
    ("kilo/plan.md", "kilo/plan.md"),
    ("kilo/code.md", "kilo/code.md"),
    ("kilo/debug.md", "kilo/debug.md"),
    ("CHATGPT-CUSTOM.txt", "CHATGPT.txt"),
    ("CHATGPT-MORE.txt", "CHATGPT.txt"),
    ("COMMIT-SPEC.txt", "COMMIT-SPEC.txt"),
  ):
    write(root, f"rules/refs/{ref_name}", "one\ntwo\n")
    write(root, f"rules/{live_name}", "one\n")
  write(root, "rules/CORE.md", live)
  return Repo(root)


def test_rule_parity_accepts_merged_lines(tmp_path: Path):
  errors: list[str] = []
  check_rule_parity(rule_tree(tmp_path, "## A\n- one and two\n"), errors)
  assert errors == []


def test_rule_parity_rejects_an_added_rule_and_a_moved_heading(tmp_path: Path):
  errors: list[str] = []
  check_rule_parity(rule_tree(tmp_path, "## A\n- one\n- two\n- three\n"), errors)
  assert len(errors) == 1 and "3 rule lines vs 2" in errors[0]
  errors.clear()
  check_rule_parity(rule_tree(tmp_path, "## B\n- one\n"), errors)
  assert len(errors) == 1 and "section headings diverge" in errors[0]


def test_rule_parity_reports_an_incomplete_pair(tmp_path: Path):
  repo = rule_tree(tmp_path, "## A\n- one\n")
  (tmp_path / "rules/kilo/plan.md").unlink()
  errors: list[str] = []
  check_rule_parity(repo, errors)
  assert errors == ["rules/kilo/plan.md: refs/live pair incomplete"]


PROMPT = "Intro\n\nRules\n\nDo one.\nDo two.\n"


def test_system_prompt_sections_are_bare_lines_between_blanks():
  assert [head for head, _, _ in prompt_sections(PROMPT)] == ["Intro", "Rules"]


def test_system_prompt_parity_accepts_compression(tmp_path: Path):
  write(tmp_path, "system-prompts/refs/NEMOGPT.md", PROMPT)
  write(tmp_path, "system-prompts/NEMOGPT.md", "Intro\n\nRules\n\nDo one and two.\n")
  errors: list[str] = []
  check_system_prompt_parity(Repo(tmp_path), errors)
  assert errors == []


def prompt_errors(root: Path, ref: str, live: str) -> list[str]:
  write(root, "system-prompts/refs/NEMOGPT.md", ref)
  write(root, "system-prompts/NEMOGPT.md", live)
  errors: list[str] = []
  check_system_prompt_parity(Repo(root), errors)
  return errors


def test_system_prompt_parity_rejects_growth(tmp_path: Path):
  errors = prompt_errors(tmp_path, PROMPT, PROMPT + "Do three.\n")
  assert any("compression may shrink but never grow" in error for error in errors)


def test_system_prompt_parity_rejects_a_section_absent_from_refs(tmp_path: Path):
  errors = prompt_errors(tmp_path, PROMPT, "Intro\n\nExtra\n\nDo.\n")
  assert errors == ["system-prompts/NEMOGPT.md: sections absent from refs: ['Extra']"]


def test_system_prompt_parity_rejects_a_section_with_more_lines_than_refs(
  tmp_path: Path,
):
  errors = prompt_errors(
    tmp_path, "Intro\n\nRules\n\nA.\n", "Intro\n\nRules\n\nA.\nB.\n"
  )
  assert any("'Rules': 2 lines vs 1 in refs" in error for error in errors)


def test_system_prompt_parity_reports_an_incomplete_pair(tmp_path: Path):
  write(tmp_path, "system-prompts/refs/NEMOGPT.md", PROMPT)
  errors: list[str] = []
  check_system_prompt_parity(Repo(tmp_path), errors)
  assert errors == ["system-prompts/NEMOGPT.md: refs/live pair incomplete"]


def test_root_copy_must_match_its_rule_source(tmp_path: Path):
  repo = Repo(tmp_path)
  errors: list[str] = []
  check_root_copies(repo, errors)
  assert errors == ["rules/ARENA.md is missing"]
  write(tmp_path, "rules/ARENA.md", "rule\n")
  errors.clear()
  check_root_copies(repo, errors)
  assert errors == ["ARENA.md: root copy missing; run `cp rules/ARENA.md ARENA.md`"]
  write(tmp_path, "ARENA.md", "other\n")
  errors.clear()
  check_root_copies(repo, errors)
  assert errors == [
    "ARENA.md: root copy differs from rules/ARENA.md; run `cp rules/ARENA.md ARENA.md`"
  ]
  write(tmp_path, "ARENA.md", "rule\n")
  errors.clear()
  check_root_copies(repo, errors)
  assert errors == []
