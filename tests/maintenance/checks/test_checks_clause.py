"""Tests for the single-clause measure tool."""

from __future__ import annotations

from pathlib import Path

import clause

REF_FILE = "## Rules\n\n- MUST keep it small.\n- NEVER guess the count.\n"


def run(tmp_path: Path, text: str, line: int, candidate: str) -> int:
  path = tmp_path / "ref.md"
  path.write_text(text, encoding="utf-8")
  return clause.main([str(path), str(line), candidate])


def test_reports_tokens_and_passes_a_smaller_clause(tmp_path: Path, capsys):
  code = run(tmp_path, REF_FILE, 3, "MUST stay small.")
  assert code == 0
  report = __import__("json").loads(capsys.readouterr().out)
  assert report["candidate"]["tokens"] > 0
  assert report["baseline"]["tokens"] > 0
  assert report["baseline"]["rough"] >= report["candidate"]["rough"]
  assert report["cap"] == "within cap"
  assert report["keywords"] == []


def test_flags_a_clause_that_exceeds_the_baseline_cap(tmp_path: Path, capsys):
  code = run(tmp_path, REF_FILE, 3, "MUST always keep every single part very small.")
  assert code == 1
  report = __import__("json").loads(capsys.readouterr().out)
  assert report["cap"] == "exceeds cap"


def test_flags_dropped_and_added_keywords(tmp_path: Path, capsys):
  code = run(tmp_path, REF_FILE, 4, "MUST avoid guessing.")
  assert code == 1
  report = __import__("json").loads(capsys.readouterr().out)
  assert any("NEVER" in error for error in report["keywords"])


def test_flags_do_not_wording(tmp_path: Path, capsys):
  code = run(tmp_path, REF_FILE, 3, "do not keep it small.")
  assert code == 1
  report = __import__("json").loads(capsys.readouterr().out)
  assert any("do not" in error for error in report["keywords"])


def test_blank_line_is_a_usage_error(tmp_path: Path, capsys):
  assert run(tmp_path, REF_FILE, 2, "MUST keep it small.") == 2
  assert "blank" in capsys.readouterr().err


def test_heading_line_is_a_usage_error(tmp_path: Path, capsys):
  assert run(tmp_path, REF_FILE, 1, "MUST keep it small.") == 2
  assert "heading" in capsys.readouterr().err


def test_out_of_range_line_is_a_usage_error(tmp_path: Path, capsys):
  assert run(tmp_path, REF_FILE, 99, "MUST keep it small.") == 2


def test_missing_file_is_a_usage_error():
  assert clause.main([str(Path("absent.md")), "1", "MUST keep it small."]) == 2
