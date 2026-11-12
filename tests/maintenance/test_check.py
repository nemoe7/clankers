"""Regression tests."""

from __future__ import annotations

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


def test_parse_budget_table_reads_linked_and_plain_pipe_rows():
  sample = (
    "# Heading\n\n"
    "| Other | Header |\n| --- | --- |\n| x | y |\n\n"
    "| File | Measure | Current |\n"
    "| --- | --- | --- |\n"
    "| [`rules/CORE.md`](rules/CORE.md) | `o200k_base` | 1,234 `tok` |\n"
    "| `plain.md` | `UTF-8 file size` | 42 `B` |\n\n"
    "Trailing prose.\n"
  )
  assert check.parse_budget_table(sample) == [
    ["File", "Measure", "Current"],
    ["rules/CORE.md", "o200k_base", "1,234 tok"],
    ["plain.md", "UTF-8 file size", "42 B"],
  ]
  try:
    check.parse_budget_table("# No budget table\n")
    raise AssertionError("Missing table was accepted")
  except RuntimeError as exc:
    assert "README budget table not found" in str(exc)


def test_root_arena_is_regular_copy_of_rule_source():
  root = check.ROOT / "ARENA.md"
  assert root.is_file()
  assert not root.is_symlink()
  assert root.read_bytes() == (check.RULES / "ARENA.md").read_bytes()


def test_skill_refs_parity_accepts_compressed_live_files(tmp_path, monkeypatch):
  skills = tmp_path / "skills"
  (skills / "refs" / "sample").mkdir(parents=True)
  (skills / "sample").mkdir(parents=True)
  (skills / "refs" / "sample" / "SKILL.md").write_text(
    "Name\n\nFirst rule.\nSecond rule.\n", encoding="utf-8"
  )
  (skills / "sample" / "SKILL.md").write_text(
    "Name\n\nFirst and second rule.\n", encoding="utf-8"
  )
  monkeypatch.setattr(check, "SKILLS", skills)
  monkeypatch.setattr(check, "ROOT", tmp_path)
  errors: list[str] = []
  check.check_skill_refs_parity(errors)
  assert errors == []


def test_skill_refs_parity_rejects_a_live_only_line(tmp_path, monkeypatch):
  skills = tmp_path / "skills"
  (skills / "refs" / "sample").mkdir(parents=True)
  (skills / "sample").mkdir(parents=True)
  (skills / "refs" / "sample" / "SKILL.md").write_text(
    "Name\n\nFirst rule.\nSecond rule.\n", encoding="utf-8"
  )
  (skills / "sample" / "SKILL.md").write_text(
    "Name\n\nFirst rule.\nSecond rule.\nThird rule.\n", encoding="utf-8"
  )
  monkeypatch.setattr(check, "SKILLS", skills)
  monkeypatch.setattr(check, "ROOT", tmp_path)
  errors: list[str] = []
  check.check_skill_refs_parity(errors)
  assert len(errors) == 1
  assert "compression may merge lines but never add them" in errors[0]


def test_validation_stages_continue_after_stale_budget(monkeypatch, capsys):
  budgets = check.read_budget_table()
  row = next(iter(budgets))
  budget_type, _ = budgets[row]
  budgets[row] = (budget_type, "999,999,999")
  monkeypatch.setattr(check, "read_budget_table", lambda: budgets)
  monkeypatch.setattr(check, "parse_args", lambda: SimpleNamespace(update=False))
  monkeypatch.setattr(check, "check_nemoizer", lambda errors: None)

  assert check.main() == 1
  output = capsys.readouterr().out
  for stage in ("skills", "links", "budgets", "parity", "paths"):
    assert f"== {stage} ..." in output
  assert "FAIL budgets:" in output
  assert f"README budget stale for {row}" in output
  assert (
    output.index("FAIL budgets:")
    < output.index("== parity ...")
    < output.index("== paths ...")
  )


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
    encoding="utf-8",
    check=False,
    cwd=tmp_path,
  )
  assert result.returncode == 0, result.stderr


def test_main_enforces_rotation_findings(monkeypatch, capsys):
  monkeypatch.setattr(check, "parse_args", lambda: SimpleNamespace(update=False))
  monkeypatch.setattr(check, "validate", lambda errors: 0)
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
  monkeypatch.setattr(check, "parse_args", lambda: SimpleNamespace(update=False))
  monkeypatch.setattr(check, "validate", lambda errors: 0)
  calls = []
  monkeypatch.setattr(check, "check_nemoizer", lambda errors: calls.append(True))
  assert check.main() == 0
  assert calls == [True]
  assert capsys.readouterr().out.count("== nemoize ...") == 1


def test_budget_updates_handle_additions_removals_and_measurements(
  tmp_path: Path, monkeypatch
):
  root = tmp_path
  monkeypatch.setattr(check, "ROOT", root)
  monkeypatch.setattr(check, "README", root / "README.md")
  monkeypatch.setattr(
    check,
    "EXPECTED_BUDGETS",
    {"Zed.md": "UTF-8 file size", "alpha.md": "UTF-8 file size"},
  )
  (root / "Zed.md").write_text("one", encoding="utf-8")
  (root / "alpha.md").write_text("two!", encoding="utf-8")
  check.README.write_text(
    "# Example\n\nLatest measurements as of 2000-01-01.\n\n"
    "| File | Measure | Current |\n| --- | --- | --- |\n"
    "| `retired.md` | `UTF-8 file size` | 10 `B` |\n\nKeep this paragraph.\n",
    encoding="utf-8",
  )
  assert check.update_readme_measurements()
  text = check.README.read_text(encoding="utf-8")
  assert "retired.md" not in text
  expected = sorted(check.EXPECTED_BUDGETS, key=str.casefold)
  assert list(check.read_budget_table()) == expected
  for relative in expected:
    type = check.EXPECTED_BUDGETS[relative]
    size = len((root / relative).read_bytes())
    assert f"| [`{relative}`]({relative}) | `{type}` | {size} `B` |" in text
    assert check.read_budget_table()[relative] == (type, f"{size} B")
  assert text.endswith("Keep this paragraph.\n")
  assert not check.update_readme_measurements()
  del check.EXPECTED_BUDGETS["Zed.md"]
  assert check.update_readme_measurements()
  assert "Zed.md" not in check.README.read_text(encoding="utf-8")
  before = check.README.read_bytes()
  check.EXPECTED_BUDGETS["missing.md"] = "UTF-8 file size"
  try:
    check.update_readme_measurements()
    raise AssertionError("A missing source was accepted")
  except RuntimeError:
    assert check.README.read_bytes() == before
  check.EXPECTED_BUDGETS = {"tok.md": "o200k_base"}
  (root / "tok.md").write_text("hello world", encoding="utf-8")
  assert check.measure(root / "tok.md", "o200k_base") > 0
  assert check.format_unit("o200k_base") == "tok"


def test_check_case_collisions_rejects_case_only_tracked_duplicates(
  tmp_path: Path, monkeypatch
):
  import subprocess

  (tmp_path / ".git").mkdir()

  def fake_run(cmd, **kwargs):
    assert cmd[:3] == ["git", "-C", str(tmp_path)]
    return subprocess.CompletedProcess(
      cmd,
      0,
      stdout=".github/PULL_REQUEST_TEMPLATE.md\n.github/pull_request_template.md\nREADME.md\n",
      stderr="",
    )

  monkeypatch.setattr(check.subprocess, "run", fake_run)
  errors: list[str] = []
  check.check_case_collisions(errors, root=tmp_path)
  assert errors == [
    "case-colliding tracked paths: .github/PULL_REQUEST_TEMPLATE.md, .github/pull_request_template.md"
  ]


def test_markdownlint_scope_includes_readmes_except_agents(tmp_path):
  cli = check.ROOT / "node_modules" / ".bin" / "markdownlint-cli2"
  if not cli.exists():
    import pytest

    pytest.skip("Install npm dependencies to run markdownlint")
  shutil.copy2(check.ROOT / ".markdownlint-cli2.jsonc", tmp_path)
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
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("Not a heading\n", encoding="utf-8")
  result = subprocess.run(
    [str(cli)],
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


def test_child_env_preserves_pythonutf8_flag() -> None:
  assert check.CHILD_ENV.get("PYTHONUTF8") == "1"
