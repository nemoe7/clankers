"""Tests for the paragraph cap gate."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

import check

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


def test_portable_workflows_directory_is_optional(tmp_path, monkeypatch):
  directory = tmp_path / "workflows"
  monkeypatch.setattr(check, "WORKFLOWS", directory)
  errors = []
  _, workflows = check.validate(errors)
  assert workflows == 0
  assert not any("workflows/README.md" in error for error in errors)
  directory.mkdir()
  errors = []
  check.validate(errors)
  assert "workflows/README.md is missing" in errors
