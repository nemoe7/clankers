"""Tests for stage reporting and the `Repo` tree."""

from __future__ import annotations

from pathlib import Path

from checks import report
from checks.repo import DEFAULT_ROOT, Repo


def test_run_check_prints_one_ok_line_for_a_clean_check(capsys):
  errors: list[str] = []
  assert report.run_check("sample", errors, lambda: "reported") == "reported"
  lines = capsys.readouterr().out.strip().splitlines()
  assert len(lines) == 1
  assert lines[0].startswith("sample: ok ") and lines[0].endswith("s")


def test_run_check_prints_one_fail_line_then_the_errors(capsys):
  errors: list[str] = []

  def failing() -> None:
    errors.extend(["one problem", "two problems"])

  assert report.run_check("sample", errors, failing) is None
  lines = capsys.readouterr().out.strip().splitlines()
  assert lines[0].startswith("sample: FAIL ")
  assert lines[1] == "- one problem"
  assert lines[2] == "- two problems"


def test_run_check_reports_warn_when_only_warnings_logged(capsys):
  errors: list[str] = []
  report.run_check("sample", errors, lambda: None, warnings=1)
  printed = capsys.readouterr().out
  assert printed.startswith("sample: warn ")
  assert "- " not in printed


def test_run_check_counts_only_the_problems_it_added(capsys):
  errors = ["an earlier problem"]
  report.run_check("sample", errors, lambda: errors.append("a new problem"))
  printed = capsys.readouterr().out
  assert "sample: FAIL " in printed
  assert "an earlier problem" not in printed


def test_notes_flush_groups_exact_and_reworded_lines_by_file(capsys):
  notes = report.Notes()
  notes.add("rules/X.md", "Style", 1, report.EXACT_COPY)
  notes.add("rules/X.md", "Style", 2, report.EXACT_COPY)
  notes.add("rules/X.md", "Style", 5, report.EQUAL_TOKENS_REWORDED)
  notes.add("rules/X.md", "Git", 10, report.EXACT_COPY)
  notes.add("skills/squash/SKILL.md", None, 1, report.EXACT_COPY)
  notes.flush()
  lines = capsys.readouterr().out.strip().splitlines()
  assert lines == [
    "- rules/X.md - Style 1, 2. Style 5*. Git 10",
    "- skills/squash/SKILL.md - 1",
  ]


def test_repo_derives_every_path_from_its_root(tmp_path: Path):
  repo = Repo(tmp_path)
  assert repo.readme == tmp_path / "README.md"
  assert repo.rule_refs == tmp_path / "rules" / "refs"
  assert repo.relative(tmp_path / "rules" / "CORE.md") == "rules/CORE.md"
  outside = tmp_path.parent / "elsewhere.md"
  assert repo.relative(outside) == str(outside)


def test_default_root_holds_this_repository():
  assert (DEFAULT_ROOT / "AGENTS.md").is_file()
  assert Repo(DEFAULT_ROOT).skills.is_dir()
