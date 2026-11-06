"""Tests for the paragraph cap gate."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
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
  printed = capsys.readouterr().out
  assert printed.startswith("== sample ...\n")
  assert "FAIL sample: 2 problem(s) in " in printed


def test_run_check_counts_only_the_problems_it_added(capsys):
  errors = ["an earlier problem"]
  check.run_check("sample", errors, lambda: errors.append("a new problem"))
  printed = capsys.readouterr().out
  assert "FAIL sample: 1 problem(s) in " in printed


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


def test_run_logged_prints_command_and_exit(monkeypatch, capsys):
  monkeypatch.setattr(
    check.subprocess,
    "run",
    lambda *args, **kwargs: SimpleNamespace(returncode=0),
  )
  result = check.run_logged(["python", "script with spaces.py", "."], cwd=check.ROOT)
  assert result.returncode == 0
  printed = capsys.readouterr().out
  assert "$ python 'script with spaces.py' ." in printed
  assert "exit 0: python 'script with spaces.py' ." in printed


def test_lint_count_claims_include_root_agent_guide():
  root = check.ROOT / "AGENTS.md"
  assert any(document == root for document, _ in check.LINT_COUNT_CLAIMS)


def test_grouped_budgets_are_empty_after_v1_archive():
  assert check.EXPECTED_GROUPS == {}


def test_root_arena_symlinks_to_rule_source():
  root = check.ROOT / "ARENA.md"
  assert root.is_symlink()
  assert root.readlink() == Path("rules/ARENA.md")
  assert root.read_bytes() == (check.RULES / "ARENA.md").read_bytes()


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
  source = check.ROOT / check.NEMOIZE
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
  monkeypatch.setattr(
    check,
    "check_nemoizer",
    lambda errors: errors.append("rotation-data"),
    raising=False,
  )
  assert check.main() == 1
  assert "rotation-data" in capsys.readouterr().out


def test_nemoizer_scope_is_root_config_and_one_stage(monkeypatch, capsys):
  import tomllib

  config = tomllib.loads((check.ROOT / "nemoizer.toml").read_text(encoding="utf-8"))
  assert "!.agents/skills/README.md" in config["extend-exclude"]
  assert "!rules/README.md" in config["extend-exclude"]
  assert "!rules/refs/README.md" in config["extend-exclude"]
  import nemoize

  monkeypatch.setattr(nemoize, "ACTIVE_CONFIG", nemoize.load_config([str(check.ROOT)]))
  for path in (
    ".agents/skills/README.md",
    "rules/README.md",
    "rules/refs/README.md",
    "docs/CHANGELOG.md",
    "docs/nuu/README.md",
    "docs/nuu/CHANGELOG.md",
  ):
    assert not nemoize.skipped(check.ROOT / path, check.ROOT, ())
  assert nemoize.skipped(check.ROOT / "docs/archive/CHANGELOG.md", check.ROOT, ())
  assert nemoize.skipped(check.ROOT / ".agents/skills/other.md", check.ROOT, ())
  assert nemoize.skipped(check.ROOT / "rules/other.md", check.ROOT, ())
  monkeypatch.setattr(
    check, "parse_args", lambda: SimpleNamespace(update=False, ste=False)
  )
  monkeypatch.setattr(check, "validate", lambda errors: (0, 0))
  calls = []
  monkeypatch.setattr(check, "check_nemoizer", lambda errors: calls.append(True))
  assert check.main() == 0
  assert calls == [True]
  assert capsys.readouterr().out.count("== Nemoizer") == 1  # nonemo: NMO100
