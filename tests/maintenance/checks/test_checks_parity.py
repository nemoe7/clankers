"""Tests for the refs/live parity gates."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from pathlib import Path

import pytest
from checks.parity import check_parity
from checks.parity.keywords import compare_keyword_counts, prose_lines
from checks.parity.prompts import check_system_prompt_parity, prompt_sections
from checks.parity.root_copies import check_root_copies
from checks.parity.rules import check_rule_parity, section_rule_lines
from checks.parity.skills import check_skills_parity
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


def test_skill_refs_parity_accepts_compressed_wording_per_line(tmp_path: Path):
  write(tmp_path, "skills/refs/sample/SKILL.md", "Name\n\nFirst rule.\nSecond rule.\n")
  write(tmp_path, "skills/sample/SKILL.md", "Name\n\nFirst rule.\nSecond.\n")
  errors: list[str] = []
  check_skills_parity(Repo(tmp_path), errors)
  assert errors == []


def test_skill_refs_parity_rejects_a_merged_line(tmp_path: Path):
  write(tmp_path, "skills/refs/sample/SKILL.md", "Name\n\nFirst rule.\nSecond rule.\n")
  write(tmp_path, "skills/sample/SKILL.md", "Name\n\nFirst and second rule.\n")
  errors: list[str] = []
  check_skills_parity(Repo(tmp_path), errors)
  assert len(errors) == 1
  assert "must be equal" in errors[0]


def test_skill_refs_parity_rejects_a_live_only_line(tmp_path: Path):
  write(tmp_path, "skills/refs/sample/SKILL.md", "Name\n\nFirst rule.\nSecond rule.\n")
  write(
    tmp_path,
    "skills/sample/SKILL.md",
    "Name\n\nFirst rule.\nSecond rule.\nThird rule.\n",
  )
  errors: list[str] = []
  check_skills_parity(Repo(tmp_path), errors)
  assert len(errors) == 1
  assert "must be equal" in errors[0]


def test_skill_refs_parity_rejects_a_baseline_without_a_live_file(tmp_path: Path):
  write(tmp_path, "skills/refs/sample/SKILL.md", "Name\n")
  errors: list[str] = []
  check_skills_parity(Repo(tmp_path), errors)
  assert errors == [
    "skills/sample/SKILL.md: refs counterpart exists without a live file"
  ]


def test_section_rule_lines_split_on_second_level_headings():
  text = "# T\n\n## A\n\n- one\n- two\n\n## B\n- three\n"
  result = section_rule_lines(text)
  assert [(h, len(r)) for h, r in result] == [("A", 2), ("B", 1)]


def rule_tree(root: Path, live: str) -> Repo:
  for name in ("CORE.md", "ARENA.md", "KILO.md"):
    write(root, f"rules/refs/{name}", "## A\n- one\n- two\n")
    write(root, f"rules/{name}", "## A\n- one\n- two\n")
  for live_name, ref_name in (
    ("kilo/plan.md", "kilo/plan.md"),
    ("kilo/code.md", "kilo/code.md"),
    ("kilo/debug.md", "kilo/debug.md"),
    ("COMMIT-SPEC.txt", "COMMIT-SPEC.txt"),
  ):
    write(root, f"rules/refs/{ref_name}", "one\ntwo\n")
    write(root, f"rules/{live_name}", "one\ntwo\n")
  write(root, "rules/CORE.md", live)
  return Repo(root)


def test_rule_parity_accepts_merged_lines(tmp_path: Path):
  errors: list[str] = []
  check_rule_parity(rule_tree(tmp_path, "## A\n- one\n- two\n"), errors)
  assert errors == []


@contextmanager
def captured_parity_warnings(caplog: pytest.LogCaptureFixture):
  """Capture warnings from the 'checks' logger, which does not propagate."""
  logger = logging.getLogger("checks")
  logger.addHandler(caplog.handler)
  previous = logger.level
  logger.setLevel(logging.WARNING)
  try:
    with caplog.at_level(logging.WARNING, logger="checks"):
      yield
  finally:
    logger.removeHandler(caplog.handler)
    logger.setLevel(previous)


def test_rule_parity_warns_when_a_clause_matches_refs_exactly(
  tmp_path: Path, caplog: pytest.LogCaptureFixture
):
  with captured_parity_warnings(caplog):
    check_rule_parity(rule_tree(tmp_path, "## A\n- one\n- two\n"), [])
  assert "rules/CORE.md 'A' line 1: live clause matches refs exactly" in caplog.text


def test_rule_parity_warns_when_a_clause_rewords_at_the_same_token_count(
  tmp_path: Path, caplog: pytest.LogCaptureFixture
):
  with captured_parity_warnings(caplog):
    check_rule_parity(rule_tree(tmp_path, "## A\n- uno\n- two\n"), [])
  assert (
    "rules/CORE.md 'A' line 1: live clause reworded at the same token count"
    in caplog.text
  )


def test_rule_parity_does_not_warn_when_compression_shrinks_tokens(
  tmp_path: Path, caplog: pytest.LogCaptureFixture
):
  with captured_parity_warnings(caplog):
    check_rule_parity(rule_tree(tmp_path, "## A\n-1\n-2\n"), [])
  assert "rules/CORE.md 'A' line 1: live clause matches refs exactly" not in caplog.text
  assert (
    "rules/CORE.md 'A' line 1: live clause reworded at the same token count"
    not in caplog.text
  )


def test_rule_parity_rejects_an_added_rule_and_a_moved_heading(tmp_path: Path):
  errors: list[str] = []
  check_rule_parity(rule_tree(tmp_path, "## A\n- one\n- two\n- three\n"), errors)
  assert len(errors) == 1 and "live has 3 rule lines, refs has 2" in errors[0]
  errors.clear()
  check_rule_parity(rule_tree(tmp_path, "## B\n- one\n"), errors)
  assert len(errors) == 1 and "section headings diverge" in errors[0]


def test_rule_parity_reports_an_incomplete_pair(tmp_path: Path):
  repo = rule_tree(tmp_path, "## A\n- one\n- two\n")
  (tmp_path / "rules/kilo/plan.md").unlink()
  errors: list[str] = []
  check_rule_parity(repo, errors)
  assert errors == ["rules/kilo/plan.md: refs/live pair incomplete"]


PROMPT = "## Intro\n\nYou are NemoGPT.\n\n## Rules\n\nDo one.\nDo two.\n"


def test_system_prompt_sections_are_hash_lines_between_blanks():
  text = "## A\n\n- one\n- two\n\n## B\n- three\n"
  assert [head for head, _, _ in prompt_sections(text)] == ["A", "B"]


def test_system_prompt_parity_accepts_compression(tmp_path: Path):
  write(tmp_path, "system-prompts/refs/NEMOGPT.md", PROMPT)
  write(
    tmp_path,
    "system-prompts/NEMOGPT.md",
    "## Intro\n\nYou are NemoGPT.\n\n## Rules\n\nGo one.\nGo two.\n",
  )
  write(
    tmp_path,
    "system-prompts/wenyan/NEMOGPT.md",
    "## Intro\n\nYou are NemoGPT.\n\n## Rules\n\nGo one.\nGo two.\n",
  )
  errors: list[str] = []
  check_system_prompt_parity(Repo(tmp_path), errors)
  assert errors == []


def prompt_errors(root: Path, ref: str, live: str) -> list[str]:
  write(root, "system-prompts/refs/NEMOGPT.md", ref)
  write(root, "system-prompts/NEMOGPT.md", live)
  write(root, "system-prompts/wenyan/NEMOGPT.md", live)
  errors: list[str] = []
  check_system_prompt_parity(Repo(root), errors)
  return errors


def test_system_prompt_parity_rejects_an_added_line(tmp_path: Path):
  errors = prompt_errors(tmp_path, PROMPT, PROMPT + "Do three.\n")
  assert any("'Rules': 3 lines vs 2 in refs" in error for error in errors)
  assert any("never add rules" in error for error in errors)


def test_system_prompt_parity_rejects_a_section_absent_from_refs(tmp_path: Path):
  errors = prompt_errors(
    tmp_path, PROMPT, "## Intro\n\nYou are NemoGPT.\n\n## Extra\n\nDo.\n"
  )
  assert "system-prompts/NEMOGPT.md: sections absent from refs: ['Extra']" in errors
  assert (
    "system-prompts/wenyan/NEMOGPT.md: sections absent from refs: ['Extra']" in errors
  )


def test_system_prompt_parity_rejects_a_section_with_fewer_lines_than_refs(
  tmp_path: Path,
):
  errors = prompt_errors(
    tmp_path,
    "## Intro\n\nYou are NemoGPT.\n\n## Rules\n\nA.\nB.\n",
    "## Intro\n\nYou are NemoGPT.\n\n## Rules\n\nA and B.\n",
  )
  assert any("'Rules': 1 lines vs 2 in refs" in error for error in errors)


def test_system_prompt_parity_rejects_a_section_with_more_lines_than_refs(
  tmp_path: Path,
):
  errors = prompt_errors(
    tmp_path,
    "## Intro\n\nYou are NemoGPT.\n\n## Rules\n\nA.\n",
    "## Intro\n\nYou are NemoGPT.\n\n## Rules\n\nA.\nB.\n",
  )
  assert any("'Rules': 2 lines vs 1 in refs" in error for error in errors)


def test_system_prompt_parity_reports_an_incomplete_pair(tmp_path: Path):
  write(tmp_path, "system-prompts/refs/NEMOGPT.md", PROMPT)
  errors: list[str] = []
  check_system_prompt_parity(Repo(tmp_path), errors)
  assert "system-prompts/NEMOGPT.md: refs/live pair incomplete" in errors
  assert "system-prompts/wenyan/NEMOGPT.md: refs/live pair incomplete" in errors


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


def test_keyword_compare_flags_a_dropped_and_an_added_keyword():
  errors: list[str] = []
  compare_keyword_counts("x", "MUST run it.", "Run it.", errors)
  assert (
    len(errors) == 1 and "dropped from live" in errors[0] and "restore" in errors[0]
  )
  errors.clear()
  compare_keyword_counts("x", "Run it.", "MUST run it.", errors)
  assert (
    len(errors) == 1 and "added in live" in errors[0] and "refs baseline" in errors[0]
  )


def test_keyword_compare_skips_headers():
  errors: list[str] = []
  compare_keyword_counts("x", "# MUST stop\n", "# stop\n", errors)
  assert errors == []


def test_prose_lines_blanks_fenced_code():
  lines = prose_lines("A\n```text\nDo not commit.\n```\nB\n")
  assert lines == ["A", None, None, None, "B", ""]


def test_keyword_compare_flags_do_not_in_live_prose():
  errors: list[str] = []
  compare_keyword_counts("x", "Do Not stop.", "do not stop.", errors)
  assert len(errors) == 1 and "replace it with NEVER" in errors[0]


def test_keyword_compare_ignores_inline_code():
  errors: list[str] = []
  compare_keyword_counts(
    "x", "Use `do not` literally.", "Use `do not` literally. Run.", errors
  )
  assert errors == []


def test_wenyan_keyword_compare_accepts_mapped_equivalents():
  errors: list[str] = []
  compare_keyword_counts(
    "x", "MUST NEVER run it. Prefer x.", "須勿運行。優先x。", errors, wenyan=True
  )
  assert errors == []


def test_wenyan_keyword_compare_flags_a_dropped_and_an_added_keyword():
  errors: list[str] = []
  compare_keyword_counts("x", "MUST run it.", "run it.", errors, wenyan=True)
  assert (
    len(errors) == 1
    and "'MUST' dropped from live" in errors[0]
    and "restore" in errors[0]
  )
  errors.clear()
  compare_keyword_counts("x", "Run it.", "勿run it.", errors, wenyan=True)
  assert (
    len(errors) == 1
    and "'NEVER' added in live" in errors[0]
    and "refs baseline" in errors[0]
  )


def test_check_parity_invokes_every_subcheck(
  tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
  from checks import parity

  called: list[str] = []

  def record(name: str):
    def fake(repo: Repo, errors: list[str]) -> None:
      called.append(name)

    return fake

  monkeypatch.setattr(parity, "check_rule_parity", record("rules"))
  monkeypatch.setattr(parity, "check_system_prompt_parity", record("prompts"))
  monkeypatch.setattr(parity, "check_skills_parity", record("skills"))
  monkeypatch.setattr(parity, "check_root_copies", record("root"))
  parity.check_parity(Repo(tmp_path), [])
  assert called == ["rules", "prompts", "skills", "root"]
