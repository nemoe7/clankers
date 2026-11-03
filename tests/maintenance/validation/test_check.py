"""Tests for the paragraph cap gate."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from types import SimpleNamespace

import check


def test_run_check_prints_start_and_verdict_for_a_clean_check(capsys):
  errors: list[str] = []
  assert check.run_check("sample", errors, lambda: "reported") == "reported"
  lines = capsys.readouterr().out.strip().splitlines()
  assert lines[0] == "== sample ..."
  assert lines[1].startswith("ok sample in ") and lines[1].endswith("s")


def test_run_check_prints_start_line_before_a_failing_check(capsys):
  errors: list[str] = []

  def failing() -> None:
    errors.extend(["one problem", "two problems"])

  assert check.run_check("sample", errors, failing) is None
  out = capsys.readouterr().out
  assert out.startswith("== sample ...\n")
  assert "FAIL sample: 2 problem(s) in " in out


def test_run_check_counts_only_the_problems_it_added(capsys):
  errors = ["an earlier problem"]
  check.run_check("sample", errors, lambda: errors.append("a new problem"))
  out = capsys.readouterr().out
  assert "FAIL sample: 1 problem(s) in " in out


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
  errors: list[str] = []
  check.run_check("sample", errors, lambda: None)
  assert flushed == [True]


def test_lint_count_claims_include_root_agent_guide():
  root = check.ROOT / "AGENTS.md"
  assert any(document == root for document, _ in check.LINT_COUNT_CLAIMS)


def test_arena_budget_includes_survey_runtime():
  _, files = check.EXPECTED_GROUPS["skills/arena-skill"]
  assert {
    "skills/arena-skill/scripts/survey.py",
    "skills/arena-skill/references/survey.json",
  } <= set(files)


def test_core_source_installs_to_agents(tmp_path):
  rules = tmp_path / "rules"
  rules.mkdir()
  shutil.copy2(check.RULES / "apply.py", rules / "apply.py")
  core = rules / "CORE.md"
  core.write_text("Generic rules\n", encoding="utf-8")
  overlay = rules / "CLINE.md"
  overlay.write_text("Cline rules\n", encoding="utf-8")
  base = tmp_path / "profile"
  result = subprocess.run(
    [sys.executable, str(rules / "apply.py"), "--yes"],
    env={**os.environ, "APPLY_RULES_BASE": str(base)},
    capture_output=True,
    text=True,
    check=False,
  )
  assert result.returncode == 0, result.stdout + result.stderr
  assert (base / ".agents" / "AGENTS.md").read_bytes() == core.read_bytes()
  assert (
    base / "Documents" / "Cline" / "Rules" / "CLINE.md"
  ).read_bytes() == overlay.read_bytes()
  assert not (base / ".agents" / core.name).exists()


def test_internal_links_checks_docs_and_skill_readmes(tmp_path, monkeypatch):
  docs = tmp_path / "docs"
  docs.mkdir()
  (docs / "note.md").write_text(
    "```text\nexample\n```\n`![alt](src =320x200)` and [missing](missing.md)\n",
    encoding="utf-8",
  )
  monkeypatch.setattr(check, "DOCS", docs)
  errors = []
  check.validate(errors)
  assert any("broken internal link missing.md" in error for error in errors)
  assert not any("src =320x200" in error for error in errors)


def test_ste_linter_keeps_the_tool_standalone(tmp_path):
  source = check.ROOT / check.STE_LINT
  standalone = tmp_path / "standalone"
  shutil.copytree(
    source.parent, standalone, ignore=shutil.ignore_patterns("__pycache__")
  )
  result = subprocess.run(
    [sys.executable, str(standalone / source.name), "--selftest"],
    capture_output=True,
    text=True,
    check=False,
    cwd=tmp_path,
  )
  assert result.returncode == 0, result.stderr


def test_main_enforces_rotation_findings(monkeypatch, capsys):
  monkeypatch.setattr(
    check, "parse_args", lambda: SimpleNamespace(update=False, ste=False)
  )
  monkeypatch.setattr(check, "validate", lambda errors: (0, 0))
  monkeypatch.setattr(check, "check_ste", lambda errors: None)
  monkeypatch.setattr(
    check,
    "check_nemoizer",
    lambda errors: errors.append("rotation-data"),
    raising=False,
  )
  assert check.main() == 1
  assert "rotation-data" in capsys.readouterr().out


def test_ste_docs_cover_moved_module_docs_and_changelogs():
  expected = {
    "docs/CHANGELOG.md",
    "docs/archive/CHANGELOG.md",
    "docs/arena-skill/README.md",
    "docs/arena-skill/CHANGELOG.md",
    "docs/nemoizer/README.md",
    "docs/nemoizer/CHANGELOG.md",
    "docs/nuu/README.md",
    "docs/nuu/CHANGELOG.md",
    "docs/squash/README.md",
    "docs/squash/CHANGELOG.md",
    "docs/gpt-plugins/README.md",
    "docs/gpt-plugins/CHANGELOG.md",
    "docs/userscripts/arena/README.md",
    "docs/userscripts/arena/CHANGELOG.md",
    "docs/userscripts/chatgpt/README.md",
    "docs/userscripts/chatgpt/CHANGELOG.md",
    "docs/workflows/gemini-release/README.md",
    "docs/workflows/gemini-release/CHANGELOG.md",
  }
  assert expected <= set(check.STE_DOCS)
  assert "CHANGELOG.md" not in check.STE_DOCS
  assert not (check.ROOT / "CHANGELOG.md").exists()
  assert all((check.ROOT / doc).is_file() for doc in check.STE_DOCS)
