"""Tests for the paragraph cap gate."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from types import SimpleNamespace

import check
import pytest

FIVE_SENTENCES = "One. Two. Three. Four. Five."
FOUR_SENTENCES = "One. Two. Three. Four."


def test_sentence_count_splits_on_terminators():
  assert check.sentence_count(FIVE_SENTENCES) == 5
  assert check.sentence_count(FOUR_SENTENCES) == 4


def test_sentence_count_ignores_code_spans_and_decimals():
  assert check.sentence_count("Run `check.py --update` after 1.2 s. Then stop.") == 2


def test_prose_paragraphs_skips_lists_tables_headings_and_fences():
  text = """# Heading

Prose that stays. Two sentences.

- a list item with five sentences. Two. Three. Four. Five.

| a | b |
| --- | --- |
| 1 | 2 |

```text
Code with five sentences. Two. Three. Four. Five.
```

> a quote with five sentences. Two. Three. Four. Five.
"""
  assert check.prose_paragraphs(text) == [(3, "Prose that stays. Two sentences.")]


def test_paragraph_violations_names_line_and_count():
  text = f"{FOUR_SENTENCES}\n\n{FIVE_SENTENCES}\n"
  assert check.paragraph_violations("docs/x.md", text) == [
    "docs/x.md:3: paragraph holds 5 sentences; the cap is 4"
  ]


def test_clean_text_reports_nothing():
  assert check.paragraph_violations("docs/x.md", f"{FOUR_SENTENCES}\n") == []


def test_run_check_prints_one_line_for_a_clean_check(capsys):
  errors: list[str] = []
  assert check.run_check("sample", errors, lambda: "reported") == "reported"
  line = capsys.readouterr().out.strip()
  assert line.startswith("ok sample in ") and line.endswith("s")


def test_run_check_names_the_check_that_found_problems(capsys):
  errors: list[str] = []

  def failing() -> None:
    errors.extend(["one problem", "two problems"])

  assert check.run_check("sample", errors, failing) is None
  assert capsys.readouterr().out.startswith("FAIL sample: 2 problem(s) in ")


def test_run_check_counts_only_the_problems_it_added(capsys):
  errors = ["an earlier problem"]
  check.run_check("sample", errors, lambda: errors.append("a new problem"))
  assert capsys.readouterr().out.startswith("FAIL sample: 1 problem(s) in ")


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
  (docs / "note.md").write_text("[missing](missing.md)\n", encoding="utf-8")
  monkeypatch.setattr(check, "DOCS", docs)
  errors = []
  check.validate(errors)
  assert any("broken internal link missing.md" in error for error in errors)


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


@pytest.mark.parametrize("status", (0, 1, 2))
def test_rotation_gate_preserves_scanner_findings_and_errors(monkeypatch, status):
  calls = []

  def scan(command, **kwargs):
    calls.append((command, kwargs))
    return subprocess.CompletedProcess(command, status, "finding-data", "parser-data")

  monkeypatch.setattr(check.subprocess, "run", scan)
  errors = ["earlier-data"]
  check.check_nemoizer(errors)
  command, kwargs = calls[0]
  assert command[:2] == [
    sys.executable,
    str(check.ROOT / check.PROSE_LINT),
  ]
  assert command[2] == "--nemoizer"
  assert command[-1] == "."
  assert "review-tests" not in command and "prose" not in command
  for path in (
    "skills/amending-violations/LICENSE.txt",
    "skills/refs/amending-violations/LICENSE.txt",
    "skills/arena-skill/assets/markdown-it.LICENSE",
    "skills/refs/arena-skill/assets/markdown-it.LICENSE",
    "skills/arena-skill/assets/sortable.LICENSE",
    "skills/refs/arena-skill/assets/sortable.LICENSE",
    "skills/nuu/data/vendor",
    "skills/refs/nuu/data/vendor",
  ):
    assert any(
      command[index : index + 2] == ["--ignore", path]
      for index in range(len(command) - 1)
    )
  assert kwargs == {
    "cwd": check.ROOT,
    "capture_output": True,
    "text": True,
    "check": False,
  }
  assert errors[0] == "earlier-data"
  if status:
    assert len(errors) == 2
    assert "finding-data" in errors[-1] and "parser-data" in errors[-1]
  else:
    assert errors == ["earlier-data"]


def test_main_enforces_rotation_findings(monkeypatch, capsys):
  monkeypatch.setattr(
    check, "parse_args", lambda: SimpleNamespace(update=False, ste=False)
  )
  monkeypatch.setattr(check, "validate", lambda errors: (0, 0))
  for name in ("check_ste", "check_prose", "check_paragraph_caps"):
    monkeypatch.setattr(check, name, lambda errors: None)
  monkeypatch.setattr(
    check,
    "check_nemoizer",
    lambda errors: errors.append("rotation-data"),
    raising=False,
  )
  assert check.main() == 1
  assert "rotation-data" in capsys.readouterr().out
