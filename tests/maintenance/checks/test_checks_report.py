"""Tests for stage reporting and the `Repo` tree."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

from checks import report
from checks.repo import DEFAULT_ROOT, Repo


def test_run_check_logs_start_and_verdict_for_a_clean_check(capsys):
  errors: list[str] = []
  assert report.run_check("sample", errors, lambda: "reported") == "reported"
  lines = capsys.readouterr().out.strip().splitlines()
  assert lines[0] == "== sample ..."
  assert lines[1].startswith("ok sample in ") and lines[1].endswith("s")


def test_run_check_logs_the_start_line_before_a_failing_check(capsys):
  errors: list[str] = []

  def failing() -> None:
    errors.extend(["one problem", "two problems"])

  assert report.run_check("sample", errors, failing) is None
  printed = capsys.readouterr().out
  assert printed.startswith("== sample ...\n")
  assert "FAIL sample: 2 problem(s) in " in printed
  assert "- one problem\n- two problems\n" in printed


def test_run_check_counts_only_the_problems_it_added(capsys):
  errors = ["an earlier problem"]
  report.run_check("sample", errors, lambda: errors.append("a new problem"))
  printed = capsys.readouterr().out
  assert "FAIL sample: 1 problem(s) in " in printed
  assert "an earlier problem" not in printed


def test_run_check_flushes_the_start_line(monkeypatch):
  flushed = []
  real_stdout = sys.stdout

  class Wrapper:
    def write(self, data: str) -> int:
      return real_stdout.write(data)

    def flush(self) -> None:
      flushed.append(True)
      real_stdout.flush()

  monkeypatch.setattr(sys, "stdout", Wrapper())
  report.run_check("sample", [], lambda: None)
  assert flushed


def test_run_logged_logs_command_and_exit(monkeypatch, capsys):
  monkeypatch.setattr(
    report.subprocess,
    "run",
    lambda *args, **kwargs: SimpleNamespace(returncode=0),
  )
  result = report.run_logged(["python", "script with spaces.py", "."])
  assert result.returncode == 0
  printed = capsys.readouterr().out
  assert "$ python 'script with spaces.py' ." in printed
  assert "exit 0: python 'script with spaces.py' ." in printed


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
