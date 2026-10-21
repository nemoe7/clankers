# nemoizer: ignore — this file keeps the avoided words as fixtures.
"""The nemoizer linter reads every text file, honors markers, and lists them."""

import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).with_name("nemoize.py")


def run(*arguments, cwd):
  return subprocess.run(
    [sys.executable, str(SCRIPT), *arguments],
    capture_output=True,
    text=True,
    check=False,
    cwd=cwd,
  )


def test_a_rotation_matches_the_stem_and_prose():
  import tempfile

  with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    (root / "note.md").write_text(
      "He picked one. Do not transmit this.\n", encoding="utf-8"
    )
    (root / "code.py").write_text("kind = 'plain'\n", encoding="utf-8")
    result = run(cwd=directory)
    assert result.returncode == 1
    assert "note.md:1: picked -> select" in result.stdout
    assert "note.md:1: transmit -> send" in result.stdout
    assert "code.py:1: kind -> type" in result.stdout


def test_a_line_marker_skips_that_line_and_a_head_marker_skips_the_file():
  import tempfile

  with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    (root / "marked.py").write_text(
      "value = 'kind'  # nemoizer: ignore\npicked = 1\n", encoding="utf-8"
    )
    (root / "whole.md").write_text(
      "<!-- nemoizer: ignore -->\nkind and picked stay\n", encoding="utf-8"
    )
    result = run(cwd=directory)
    assert "marked.py:1:" not in result.stdout
    assert "marked.py:2: picked -> select" in result.stdout
    assert "whole.md" not in result.stdout
    listing = run("--ignores", cwd=directory)
    assert listing.returncode == 0
    assert "marked.py:1:" in listing.stdout
    assert "whole.md:1:" in listing.stdout


def test_an_ignored_path_is_skipped():
  import tempfile

  with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    vendor = root / "vendor"
    vendor.mkdir()
    (vendor / "third.py").write_text("kind = 1\n", encoding="utf-8")
    result = run("--ignore", "vendor", cwd=directory)
    assert result.returncode == 0, result.stdout
    assert "third.py" not in result.stdout


def test_the_rotation_table_never_flags_itself():
  import tempfile

  with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    (root / "SKILL.md").write_text(
      "| Avoid | Use |\n| --- | --- |\n| `kind` | type |\n", encoding="utf-8"
    )
    result = run(cwd=directory)
    assert result.returncode == 0, result.stdout


def test_a_picker_is_a_rotation_and_a_marked_pickle_is_not():
  import tempfile

  with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    ui = root / "ui.js"
    ui.write_text(
      "const picker = 1\nconst var_pick = 2\nconst repick = 3\n"
      "const jar = pickle  # nemoizer: ignore\n",
      encoding="utf-8",
    )
    result = run(cwd=directory)
    assert result.returncode == 1
    assert "ui.js:1: picker -> select" in result.stdout
    assert "ui.js:2: pick -> select" in result.stdout
    assert "ui.js:3" not in result.stdout
    assert "ui.js:4" not in result.stdout
    formatted = run("--format", cwd=directory)
    assert formatted.returncode == 0, formatted.stderr
    assert ui.read_text(encoding="utf-8") == (
      "const selector = 1\nconst var_select = 2\nconst repick = 3\n"
      "const jar = pickle  # nemoizer: ignore\n"
    )


def test_the_format_mode_rewrites_every_form_and_keeps_case():
  import tempfile

  with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    note = root / "note.py"
    note.write_text("kind = 1\nKIND = 2\nkinds = 3\n", encoding="utf-8")
    result = run("--format", cwd=directory)
    assert result.returncode == 0, result.stderr
    assert note.read_text(encoding="utf-8") == "type = 1\nTYPE = 2\ntypes = 3\n"
    assert "note.py:1: -kind = 1" in result.stdout
    assert "note.py:1: +type = 1" in result.stdout
    assert run(cwd=directory).returncode == 0


def test_the_format_mode_honors_the_marker():
  import tempfile

  with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    note = root / "note.md"
    note.write_text(
      "kind stays  <!-- nemoizer: ignore -->\npicked one\nkind moves\n",
      encoding="utf-8",
    )
    result = run("--format", cwd=directory)
    assert result.returncode == 0, result.stderr
    assert note.read_text(encoding="utf-8") == (
      "kind stays  <!-- nemoizer: ignore -->\nselected one\ntype moves\n"
    )


def test_the_format_mode_replaces_the_word_inside_a_longer_one():
  import tempfile

  with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    note = root / "note.md"
    note.write_text(
      "the kind of jar\nKIND stays upper\nthe jar is pickle  # nemoizer: ignore\n",
      encoding="utf-8",
    )
    result = run("--format", cwd=directory)
    assert result.returncode == 0, result.stderr
    assert note.read_text(encoding="utf-8") == (
      "the type of jar\nTYPE stays upper\nthe jar is pickle  # nemoizer: ignore\n"
    )


def test_format_preserves_invalid_utf8_and_still_formats_valid_text(tmp_path):
  invalid = tmp_path / "invalid.txt"
  original = b"\xffkind\n"
  invalid.write_bytes(original)
  valid = tmp_path / "valid.txt"
  valid.write_text("caf\u00e9 kind\n", encoding="utf-8")
  result = run("--format", ".", cwd=tmp_path)
  assert result.returncode == 0, result.stderr
  assert invalid.read_bytes() == original
  assert valid.read_text(encoding="utf-8") == "caf\u00e9 type\n"
