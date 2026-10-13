"""Tests for README budget updates and measurements."""

from pathlib import Path

import check


def test_budget_updates_handle_additions_removals_and_measurements(
  tmp_path: Path, monkeypatch
):
  root = tmp_path
  monkeypatch.setattr(check, "ROOT", root)
  monkeypatch.setattr(check, "README", root / "README.md")
  monkeypatch.setattr(
    check,
    "EXPECTED_BUDGETS",
    {"one.md": "UTF-8 file size", "two.md": "UTF-8 file size"},
  )
  (root / "one.md").write_text("one", encoding="utf-8")
  (root / "two.md").write_text("two!", encoding="utf-8")
  check.README.write_text(
    "# Example\n\nLatest measurements as of 2000-01-01.\n\n"
    "| File | Measure | Current |\n| --- | --- | --- |\n"
    "| `retired.md` | `UTF-8 file size` | 10 `B` |\n\nKeep this paragraph.\n",
    encoding="utf-8",
  )
  assert check.update_readme_measurements()
  text = check.README.read_text(encoding="utf-8")
  assert "retired.md" not in text
  assert "| `one.md` | `UTF-8 file size` | 3 `B` |" in text
  assert "| `two.md` | `UTF-8 file size` | 4 `B` |" in text
  assert text.endswith("Keep this paragraph.\n")
  assert not check.update_readme_measurements()
  del check.EXPECTED_BUDGETS["one.md"]
  assert check.update_readme_measurements()
  assert "one.md" not in check.README.read_text(encoding="utf-8")
  before = check.README.read_bytes()
  check.EXPECTED_BUDGETS["missing.md"] = "UTF-8 file size"
  try:
    check.update_readme_measurements()
    raise AssertionError("A missing source was accepted")
  except RuntimeError:
    assert check.README.read_bytes() == before
  check.EXPECTED_BUDGETS = {"tok.md": "o200k_base"}
  (root / "tok.md").write_text("hello world", encoding="utf-8")
  assert check.measure(root / "tok.md", "o200k_base") == 2
  assert check.format_unit("o200k_base") == "tok"
