"""Tests for the README budget table."""

from __future__ import annotations

from pathlib import Path

from checks import budgets
from checks.repo import Repo

TREE = (
  "rules/CORE.md",
  "rules/README.md",
  "rules/CHATGPT-CUSTOM.txt",
  "rules/CHATGPT-MORE.txt",
  "rules/kilo/plan.md",
  "rules/refs/CORE.md",
  "rules/wenyan/CHATGPT-MORE.txt",
  "skills/alpha/SKILL.md",
  "skills/refs/alpha/SKILL.md",
  "system-prompts/NEMOGPT.md",
  "system-prompts/README.md",
  "system-prompts/refs/NEMOGPT.md",
  "system-prompts/wenyan/NEMOGPT.md",
  "userscripts/fill.txt",
  "gpt-plugins/skills/gpt-x/SKILL.md",
)
TABLE = (
  "# Example\n\nLatest measurements as of 2000-01-01.\n\n"
  "| File | Measure | Current |\n| --- | --- | --- |\n"
  "| `retired.md` | `o200k_base` | 10 `tok` |\n\nKeep this paragraph.\n"
)


def make_repo(root: Path, text: str = "hello world") -> Repo:
  for relative in TREE:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
  (root / "README.md").write_text(TABLE, encoding="utf-8")
  return Repo(root)


def test_parse_budget_table_reads_linked_and_plain_pipe_rows():
  sample = (
    "# Heading\n\n"
    "| Other | Header |\n| --- | --- |\n| x | y |\n\n"
    "| File | Measure | Current |\n"
    "| --- | --- | --- |\n"
    "| [`rules/CORE.md`](rules/CORE.md) | `o200k_base` | 1,234 `tok` |\n"
    "| `plain.md` | `Unicode chars` | 42 `chars` |\n\n"
    "Trailing prose.\n"
  )
  assert budgets.parse_budget_table(sample) == [
    ["File", "Measure", "Current"],
    ["rules/CORE.md", "o200k_base", "1,234 tok"],
    ["plain.md", "Unicode chars", "42 chars"],
  ]


def test_parse_budget_table_rejects_a_missing_table():
  try:
    budgets.parse_budget_table("# No budget table\n")
  except RuntimeError as exc:
    assert "README budget table not found" in str(exc)
  else:
    raise AssertionError("Missing table was accepted")


def test_every_file_measures_tokens_except_the_chatgpt_fields():
  assert budgets.measure_type("rules/CORE.md") == "o200k_base"
  assert budgets.measure_type("skills/nuu/SKILL.md") == "o200k_base"
  for field in budgets.CHATGPT_FIELDS:
    assert budgets.measure_type(f"rules/{field}") == "Unicode chars"
  assert set(budgets.MEASURE_OVERRIDES) == {
    f"rules/{f}" for f in budgets.CHATGPT_FIELDS
  }


def test_budget_files_are_discovered_by_glob(tmp_path: Path):
  repo = make_repo(tmp_path)
  assert dict(budgets.budget_items(repo)) == {
    "gpt-plugins/skills/gpt-x/SKILL.md": "o200k_base",
    "rules/CHATGPT-CUSTOM.txt": "Unicode chars",
    "rules/CHATGPT-MORE.txt": "Unicode chars",
    "rules/CORE.md": "o200k_base",
    "rules/kilo/plan.md": "o200k_base",
    "skills/alpha/SKILL.md": "o200k_base",
    "system-prompts/NEMOGPT.md": "o200k_base",
    "system-prompts/wenyan/NEMOGPT.md": "o200k_base",
    "userscripts/fill.txt": "o200k_base",
  }
  paths = [relative for relative, _ in budgets.budget_items(repo)]
  assert paths == sorted(paths, key=str.casefold)


def test_update_rebuilds_the_table_and_follows_additions_and_removals(tmp_path: Path):
  repo = make_repo(tmp_path)
  assert budgets.update_readme_measurements(repo)
  text = repo.readme.read_text(encoding="utf-8")
  assert "retired.md" not in text
  assert text.endswith("Keep this paragraph.\n")
  assert list(budgets.read_budget_table(repo)) == [
    r for r, _ in budgets.budget_items(repo)
  ]
  assert "| [`rules/CORE.md`](rules/CORE.md) | `o200k_base` | 2 `tok` |" in text
  assert (
    "| [`rules/CHATGPT-MORE.txt`](rules/CHATGPT-MORE.txt) | `Unicode chars` | 11 `chars` |"
    in text
  )
  assert not budgets.update_readme_measurements(repo)
  (tmp_path / "userscripts/fill.txt").unlink()
  assert budgets.update_readme_measurements(repo)
  assert "userscripts/fill.txt" not in repo.readme.read_text(encoding="utf-8")


def test_update_refuses_a_readme_without_exactly_one_table(tmp_path: Path):
  repo = make_repo(tmp_path)
  repo.readme.write_text("# No table\n", encoding="utf-8")
  try:
    budgets.update_readme_measurements(repo)
  except RuntimeError as exc:
    assert "exactly one" in str(exc)
  else:
    raise AssertionError("A README without a table was accepted")


def test_check_budgets_passes_on_a_fresh_table(tmp_path: Path):
  repo = make_repo(tmp_path)
  budgets.update_readme_measurements(repo)
  errors: list[str] = []
  budgets.check_budgets(repo, errors)
  assert errors == []


def test_check_budgets_reports_stale_and_missing_rows(tmp_path: Path):
  repo = make_repo(tmp_path)
  budgets.update_readme_measurements(repo)
  (tmp_path / "rules/CORE.md").write_text(
    "hello world again and again", encoding="utf-8"
  )
  errors: list[str] = []
  budgets.check_budgets(repo, errors)
  assert len(errors) == 1 and errors[0].startswith(
    "README budget stale for rules/CORE.md"
  )
  (tmp_path / "skills/alpha/SKILL.md").unlink()
  errors.clear()
  budgets.check_budgets(repo, errors)
  assert len(errors) == 1 and errors[0].startswith(
    "README budget table entries mismatch"
  )


def test_check_budgets_reports_a_type_mismatch(tmp_path: Path):
  repo = make_repo(tmp_path)
  budgets.update_readme_measurements(repo)
  text = repo.readme.read_text(encoding="utf-8")
  repo.readme.write_text(
    text.replace("`Unicode chars` | 11 `chars`", "`o200k_base` | 2 `tok`"),
    encoding="utf-8",
  )
  errors: list[str] = []
  budgets.check_budgets(repo, errors)
  assert errors
  assert all(
    "README budget type mismatch for rules/CHATGPT-" in error for error in errors
  )


def test_chatgpt_fields_and_wenyan_copies_stay_under_the_character_cap(tmp_path: Path):
  repo = make_repo(tmp_path)
  budgets.update_readme_measurements(repo)
  over = "x" * (budgets.CHATGPT_CHAR_CAP + 1)
  (tmp_path / "rules/wenyan/CHATGPT-MORE.txt").write_text(over, encoding="utf-8")
  (tmp_path / "rules/CHATGPT-CUSTOM.txt").write_text(over, encoding="utf-8")
  errors: list[str] = []
  budgets.check_budgets(repo, errors)
  assert "rules/CHATGPT-CUSTOM.txt exceeds 1,500 Unicode chars" in errors
  assert "rules/wenyan/CHATGPT-MORE.txt exceeds 1,500 Unicode chars" in errors
