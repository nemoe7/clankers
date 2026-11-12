"""nemoizer configuration discovery and file-config tests."""

import subprocess
import tomllib
from pathlib import Path

import config
import files
import prose.extract
import pytest
from conftest import SCRIPT, run


def test_a_file_header_beats_files_globs_inside_three_lines(tmp_path):
  (tmp_path / "nemoizer.toml").write_text(
    '[[files]]\npaths = ["*.md"]\nlist-sentence-cap = 9\n',
    encoding="utf-8",
  )
  item = "- Alpha one. Beta two. Gamma three.\n"
  (tmp_path / "plain.md").write_text(item, encoding="utf-8")
  (tmp_path / "strict.md").write_text(
    "<!-- nemoizer: list-sentence-cap=2 -->\n\n" + item, encoding="utf-8"
  )
  (tmp_path / "late.md").write_text(
    "<!-- One. -->\n\n<!-- Two. -->\n<!-- nemoizer: list-sentence-cap=2 -->\n\n" + item,
    encoding="utf-8",
  )
  (tmp_path / "kind.md").write_text(
    "<!-- kind nemoizer: list-sentence-cap=2 -->\n\n" + item, encoding="utf-8"
  )
  result = run(cwd=tmp_path)
  assert result.returncode == 1, result.stdout + result.stderr
  assert "plain.md:1: [NMP100]" not in result.stdout
  assert "strict.md:3: [NMP100]" in result.stdout
  assert "late.md:6: [NMP100]" not in result.stdout
  assert "kind.md:3: [NMP100]" not in result.stdout


def test_a_file_header_reads_lines_one_to_three_only(tmp_path):
  assert config.header_config("# nemoizer: list-sentence-cap=4\n") == {
    "list_sentence_cap": 4
  }
  assert config.header_config("<!-- nemoizer: list-sentence-cap=4 --!>\n") == {
    "list_sentence_cap": 4
  }
  assert (
    config.header_config("Return overrides from a `nemoizer:` header on lines 1-3.\n")
    == {}
  )
  assert config.header_config(
    "One.\nTwo.\nThree.\n# nemoizer: list-sentence-cap=4\n"
  ) == ({})
  with pytest.raises(ValueError):
    config.header_config("# nemoizer: paragraph-cap=9\n")
  with pytest.raises(ValueError):
    config.header_config("# nemoizer: select=STE100\n")


def test_config_caps_respect_gitignore_and_bundled_default_config(tmp_path):
  default_toml = SCRIPT.parent.parent / "references" / "nemoizer.toml"
  assert default_toml.is_file()
  cfg = config.load_config(config_path=default_toml)
  assert cfg["respect_gitignore"] is True
  assert cfg["instruction_sentence_cap"] == config.SENTENCE_CAPS["instruction"]
  assert cfg["description_sentence_cap"] == config.SENTENCE_CAPS["description"]
  assert cfg["paragraph_cap"] == config.PARAGRAPH_CAP
  assert cfg["list_sentence_cap"] == config.LIST_SENTENCE_CAP
  assert cfg["heading_sentence_cap"] == config.HEADING_SENTENCE_CAP
  assert cfg["comment_block_cap"] == prose.extract.COMMENT_BLOCK_CAP
  assert cfg["the_density_cap"] == config.THE_DENSITY_CAP
  assert cfg["min_the_count"] == config.MIN_THE_COUNT
  for expected_item in ("AGENTS.md", "**/AGENTS.md", "ARENA.md", "**/ARENA.md"):
    assert expected_item in cfg["exclude"]

  repo = tmp_path / "gitrepo"
  repo.mkdir()
  subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
  (repo / ".gitignore").write_text("ignored.md\n", encoding="utf-8")
  (repo / "ignored.md").write_text("Do not transmit this.\n", encoding="utf-8")
  (repo / "AGENTS.md").write_text("Do not transmit this.\n", encoding="utf-8")
  (repo / "ARENA.md").write_text("Do not transmit this.\n", encoding="utf-8")
  sub = repo / "sub"
  sub.mkdir()
  (sub / "AGENTS.md").write_text("Do not transmit this.\n", encoding="utf-8")
  (sub / "ARENA.md").write_text("Do not transmit this.\n", encoding="utf-8")
  (repo / "tracked.md").write_text(
    "# Heading one. Heading two.\n\n"
    "- List one. List two. List three.\n\n"
    "The cat chased the mouse across the floor.\n",
    encoding="utf-8",
  )
  default_run = run(cwd=repo)
  assert default_run.returncode == 1
  assert "ignored.md" not in default_run.stdout
  assert "AGENTS.md" not in default_run.stdout
  assert "ARENA.md" not in default_run.stdout
  assert "NMP100" in default_run.stdout
  assert "NMO902" in default_run.stdout

  (repo / "nemoizer.toml").write_text(
    "exclude = []\n"
    "respect-gitignore = false\n"
    "heading-sentence-cap = 2\n"
    "list-sentence-cap = 3\n"
    "the-density-cap = 50\n"
    "min-the-count = 4\n",
    encoding="utf-8",
  )
  custom_run = run(cwd=repo)
  assert custom_run.returncode == 1
  assert "ignored.md" in custom_run.stdout
  assert "AGENTS.md" in custom_run.stdout
  assert "ARENA.md" in custom_run.stdout
  assert str(Path("sub", "AGENTS.md")) in custom_run.stdout
  assert str(Path("sub", "ARENA.md")) in custom_run.stdout
  assert "NMP100" not in custom_run.stdout
  assert "NMO902" not in custom_run.stdout


def test_extend_exclude_supports_globstar_and_negation(tmp_path, monkeypatch):
  monkeypatch.setitem(
    config.ACTIVE_CONFIG,
    "extend_exclude",
    ("skills/**/*.md", "!skills/**/README.md", "rules/**"),
  )
  assert files.skipped(tmp_path / "skills" / "demo" / "SKILL.md", tmp_path, ())
  assert not files.skipped(tmp_path / "skills" / "README.md", tmp_path, ())
  assert not files.skipped(tmp_path / "skills" / "demo" / "README.md", tmp_path, ())
  assert not files.skipped(
    tmp_path / "skills" / "demo" / "scripts" / "tool.py", tmp_path, ()
  )
  assert files.skipped(tmp_path / "rules" / "CORE.md", tmp_path, ())


def test_file_config_merges_a_glob_entry_then_a_file_header(tmp_path, monkeypatch):
  config_file = tmp_path / "nemoizer.toml"
  (tmp_path / "docs").mkdir()
  config_file.write_text(
    "list-sentence-cap = 2\n"
    "\n"
    "[[files]]\n"
    'paths = ["docs/*.md"]\n'
    "list-sentence-cap = 3\n"
    'context = "description"\n',
    encoding="utf-8",
  )
  loaded = config.load_config(config_path=config_file)
  assert loaded["files"] == (
    {
      "paths": ("docs/*.md",),
      "overrides": {"list_sentence_cap": 3, "context": "description"},
    },
  )
  monkeypatch.setattr(config, "BASE_CONFIG", loaded)
  page = tmp_path / "docs" / "page.md"
  merged = config.file_config(page)
  assert merged["list_sentence_cap"] == 3
  assert merged["context"] == "description"
  headed = config.file_config(page, "# nemoizer: list-sentence-cap=5\n\nText.\n")
  assert headed["list_sentence_cap"] == 5
  assert headed["context"] == "description"
  elsewhere = config.file_config(tmp_path / "elsewhere.md")
  assert elsewhere["list_sentence_cap"] == config.LIST_SENTENCE_CAP
  assert elsewhere["context"] is None


def test_files_globs_scope_caps_rules_and_context(tmp_path):
  (tmp_path / "nemoizer.toml").write_text(
    "[[files]]\n"
    'paths = ["relaxed.md"]\n'
    "list-sentence-cap = 3\n"
    "\n"
    "[[files]]\n"
    'path = "quiet.md"\n'
    "\n"
    "[files.lint]\n"
    'ignore = ["STE100"]\n'
    "\n"
    "[[files]]\n"
    'paths = ["long.md"]\n'
    'context = "description"\n',
    encoding="utf-8",
  )
  list_item = "- Alpha one. Beta two. Gamma three.\n"
  (tmp_path / "relaxed.md").write_text(list_item, encoding="utf-8")
  (tmp_path / "tight.md").write_text(list_item, encoding="utf-8")
  (tmp_path / "quiet.md").write_text("Alpha; beta.\n", encoding="utf-8")
  (tmp_path / "semi.md").write_text("Alpha; beta.\n", encoding="utf-8")
  sentence = " ".join(["term"] * (config.SENTENCE_CAPS["instruction"] + 1)) + ".\n"
  (tmp_path / "long.md").write_text(sentence, encoding="utf-8")
  (tmp_path / "brief.md").write_text(sentence, encoding="utf-8")
  result = run(cwd=tmp_path)
  assert result.returncode == 1, result.stdout + result.stderr
  assert "relaxed.md:1: [NMP100]" not in result.stdout
  assert "tight.md:1: [NMP100]" in result.stdout
  assert "quiet.md" not in result.stdout
  assert "semi.md:1: [STE100]" in result.stdout
  assert "long.md:1: [STE200]" not in result.stdout
  assert "brief.md:1: [STE200]" in result.stdout


def test_invalid_header_and_files_keys_exit_two(tmp_path):
  bad_key = tmp_path / "bad_key.md"
  bad_key.write_text("<!-- nemoizer: bogus=1 -->\n\nText.\n", encoding="utf-8")
  result = run(str(bad_key), cwd=tmp_path)
  assert result.returncode == 2
  assert "bogus" in result.stderr

  bad_value = tmp_path / "bad_value.md"
  bad_value.write_text(
    "<!-- nemoizer: paragraph-cap=wide -->\n\nText.\n", encoding="utf-8"
  )
  value_result = run(str(bad_value), cwd=tmp_path)
  assert value_result.returncode == 2
  assert "paragraph-cap" in value_result.stderr

  (tmp_path / "nemoizer.toml").write_text(
    '[[files]]\npaths = ["*.md"]\nexclude = ["vendor"]\n',
    encoding="utf-8",
  )
  unknown = run(cwd=tmp_path)
  assert unknown.returncode == 2
  assert "exclude" in unknown.stderr

  (tmp_path / "nemoizer.toml").write_text(
    "[[files]]\nlist-sentence-cap = 3\n", encoding="utf-8"
  )
  missing = run(cwd=tmp_path)
  assert missing.returncode == 2
  assert "paths" in missing.stderr


def test_nemoizer_toml_and_pyproject_config_discovery(tmp_path):
  vendor = tmp_path / "vendor"
  vendor.mkdir()
  (vendor / "skipped.md").write_text("Transmit this kind.\n", encoding="utf-8")
  note = tmp_path / "note.md"
  sentence = " ".join(["term"] * (config.SENTENCE_CAPS["instruction"] + 1)) + "."
  note.write_text(f"{sentence}\nStart; stop.\n", encoding="utf-8")
  code = tmp_path / "app.py"
  code.write_text("# One.\n# Two.\n# Three.\nx = 1\n", encoding="utf-8")
  (tmp_path / "nemoizer.toml").write_text(
    'extend-exclude = ["vendor"]\n'
    'context = "description"\n'
    "paragraph-cap = 4\n"
    "comment-block-cap = 3\n"
    "\n"
    "[lint]\n"
    'select = ["ALL"]\n'
    'ignore = ["STE9"]\n'
    "\n"
    "[lint.per-file-ignores]\n"
    '"note.md" = ["STE100"]\n',
    encoding="utf-8",
  )
  res = run(cwd=tmp_path)
  assert res.returncode == 0, res.stdout + res.stderr
  no_cfg = run("--no-config", cwd=tmp_path)
  assert no_cfg.returncode == 1
  assert "STE200" in no_cfg.stdout and "STE100" in no_cfg.stdout
  (tmp_path / "nemoizer.toml").unlink()
  (tmp_path / "pyproject.toml").write_text(
    "[tool.nemoizer]\n"
    'extend-exclude = ["vendor"]\n'
    'context = "description"\n'
    "comment-block-cap = 3\n"
    "\n"
    "[tool.nemoizer.lint.per-file-ignores]\n"
    '"note.md" = ["STE100"]\n',
    encoding="utf-8",
  )
  py_res = run(cwd=tmp_path)
  assert py_res.returncode == 0, py_res.stdout + py_res.stderr


def test_pyproject_files_table_scopes_rules(tmp_path):
  (tmp_path / "pyproject.toml").write_text(
    "[tool.nemoizer]\n"
    "\n"
    "[[tool.nemoizer.files]]\n"
    'paths = ["quiet.md"]\n'
    "\n"
    "[tool.nemoizer.files.lint]\n"
    'ignore = ["STE100"]\n',
    encoding="utf-8",
  )
  (tmp_path / "quiet.md").write_text("Alpha; beta.\n", encoding="utf-8")
  (tmp_path / "noisy.md").write_text("Alpha; beta.\n", encoding="utf-8")
  result = run(cwd=tmp_path)
  assert result.returncode == 1, result.stdout + result.stderr
  assert "quiet.md" not in result.stdout
  assert "noisy.md:1: [STE100]" in result.stdout


def test_root_config_excludes_bundled_material(tmp_path, monkeypatch):
  root = SCRIPT.parents[3]
  config_data = tomllib.loads((root / "nemoizer.toml").read_text(encoding="utf-8"))
  monkeypatch.setitem(
    config.ACTIVE_CONFIG, "extend_exclude", tuple(config_data["extend-exclude"])
  )
  for name in (
    "app.min.js",
    "nested/site.min.css",
    "nested/code.min.mjs",
    "docs/archive/README.md",
    "archive/note.py",
    "other/archives/old.md",
    "vendor/library.js",
    "nested/vendor/README.md",
    "third_party/module.py",
    "nested/third-party/module.py",
    "vendored/module.py",
    "files/source.tar.gz",
  ):
    assert files.skipped(tmp_path / name, tmp_path, ()), name
  for name in (
    "src/app.js",
    "docs/README.md",
    "src/archive_helper.py",
    "src/vendor_helper.py",
  ):
    assert not files.skipped(tmp_path / name, tmp_path, ()), name


@pytest.mark.parametrize(
  ("subcommand", "name"), [("prose", "note.md"), ("review-tests", "test_note.py")]
)
def test_subcommands_apply_discovered_config_exclusions(tmp_path, subcommand, name):
  import json

  (tmp_path / ".git").mkdir()
  (tmp_path / "nemoizer.toml").write_text(
    'extend-exclude = ["archive"]\n', encoding="utf-8"
  )
  text = 'def test_note():\n  assert result.stdout == "Saved the report."\n'
  for folder in ("docs", "docs/archive"):
    (tmp_path / folder).mkdir(exist_ok=True)
    (tmp_path / folder / name).write_text(text, encoding="utf-8")
  result = run(subcommand, "docs", cwd=tmp_path)
  assert result.returncode in (0, 1), result.stderr
  scanned = {
    Path(row["path"]).as_posix() for row in json.loads(result.stdout)["coverage"]
  }
  assert scanned == {f"docs/{name}"}

  unconfigured = run(subcommand, "--no-config", "docs", cwd=tmp_path)
  assert unconfigured.returncode in (0, 1), unconfigured.stderr
  assert {
    Path(row["path"]).as_posix() for row in json.loads(unconfigured.stdout)["coverage"]
  } == {f"docs/{name}", f"docs/archive/{name}"}

  named = tmp_path / "named.toml"
  named.write_text(f'extend-exclude = ["docs/{name}"]\n', encoding="utf-8")
  configured = run(subcommand, "--config", str(named), "docs", cwd=tmp_path)
  assert configured.returncode in (0, 1), configured.stderr
  assert {
    Path(row["path"]).as_posix() for row in json.loads(configured.stdout)["coverage"]
  } == {f"docs/archive/{name}"}

  absent = "missing.toml"
  missing = run(subcommand, "--config", absent, "docs", cwd=tmp_path)
  assert missing.returncode == 2
  assert absent in missing.stderr
