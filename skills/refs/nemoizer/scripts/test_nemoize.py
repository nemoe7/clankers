# nonemo: N001
# nonemo: N002
# nonemo: N003
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
    assert "note.md:1: N002 picked -> select" in result.stdout
    assert "note.md:1: N001 transmit -> send" in result.stdout
    assert "code.py:1: N003 kind -> type" in result.stdout


def test_a_line_marker_skips_that_line_and_a_head_marker_skips_the_file():
  import tempfile

  with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    (root / "marked.py").write_text(
      "value = 'kind'  # nonemo: N003\npicked = 1\n", encoding="utf-8"
    )
    (root / "whole.md").write_text(
      "<!-- nonemo: N003 -->\nkind and picked stay\n", encoding="utf-8"
    )
    result = run(cwd=directory)
    assert "marked.py:1:" not in result.stdout
    assert "marked.py:2: N002 picked -> select" in result.stdout
    assert "whole.md:2: N002 picked -> select" in result.stdout
    assert "whole.md:2: N003" not in result.stdout
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
      "const jar = pickle  # nonemo: N002\n",
      encoding="utf-8",
    )
    result = run(cwd=directory)
    assert result.returncode == 1
    assert "ui.js:1: N002 picker -> select" in result.stdout
    assert "ui.js:2: N002 pick -> select" in result.stdout
    assert "ui.js:3" not in result.stdout
    assert "ui.js:4" not in result.stdout
    formatted = run("--format", cwd=directory)
    assert formatted.returncode == 0, formatted.stderr
    assert ui.read_text(encoding="utf-8") == (
      "const selector = 1\nconst var_select = 2\nconst repick = 3\n"
      "const jar = pickle  # nonemo: N002\n"
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
      "kind stays  <!-- nonemo: N003 -->\npicked one\nkind moves\n",
      encoding="utf-8",
    )
    result = run("--format", cwd=directory)
    assert result.returncode == 0, result.stderr
    assert note.read_text(encoding="utf-8") == (
      "kind stays  <!-- nonemo: N003 -->\nselected one\ntype moves\n"
    )


def test_the_format_mode_replaces_the_word_inside_a_longer_one():
  import tempfile

  with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    note = root / "note.md"
    note.write_text(
      "the kind of jar\nKIND stays upper\nthe jar is pickle  # nonemo: N002\n",
      encoding="utf-8",
    )
    result = run("--format", cwd=directory)
    assert result.returncode == 0, result.stderr
    assert note.read_text(encoding="utf-8") == (
      "the type of jar\nTYPE stays upper\nthe jar is pickle  # nonemo: N002\n"
    )


def test_rule_ids_suppress_only_the_named_rotation():
  import tempfile

  with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    note = root / "note.md"
    note.write_text(
      "kind and picked  # nonemo: N003\ntransmit # nonemo: N999\n", encoding="utf-8"
    )
    result = run(cwd=directory)
    assert result.returncode == 1
    assert "note.md:1: N002 picked -> select" in result.stdout
    assert "note.md:1: N003" not in result.stdout
    assert "note.md:2: N001 transmit -> send" in result.stdout
    result = run("--format", cwd=directory)
    assert result.returncode == 0
    assert (
      note.read_text() == "kind and selected  # nonemo: N003\nsend # nonemo: N999\n"
    )


def test_collect_keeps_all_markers_including_suppressed_files():
  import tempfile

  with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    note = root / "note.md"
    note.write_text(
      "# nonemo: N001\n# nonemo: N002\n# nonemo: N003\nkind # nonemo: N003 # nonemo: N999\n",
      encoding="utf-8",
    )
    result = subprocess.run(
      [sys.executable, str(SCRIPT.with_name("nemoizer")), "collect", "."],
      cwd=directory,
      capture_output=True,
      text=True,
      check=False,
    )
    assert result.returncode == 0, result.stderr
    expected_markers = note.read_text().count("nonemo:")
    assert len(result.stdout.splitlines()) == expected_markers
    assert "note.md:1: N001 file:" in result.stdout
    assert "note.md:4: N003 line:" in result.stdout
    assert "note.md:4: N999 unknown:" in result.stdout
    legacy = run("--ignores", cwd=directory)
    assert legacy.returncode == 0 and legacy.stdout == result.stdout


def test_multiple_rule_exclusions_preserve_the_marker_text():
  import tempfile

  with tempfile.TemporaryDirectory() as directory:
    note = Path(directory) / "note.md"
    content = "picked kind # nonemo: N002 # nonemo: N003\nkind # nonemo: kind\n"
    note.write_text(content, encoding="utf-8")
    result = run(cwd=directory)
    assert "note.md:1:" not in result.stdout
    assert "note.md:2: N003 kind -> type" in result.stdout
    formatted = run("--format", cwd=directory)
    assert formatted.returncode == 0
    assert (
      note.read_text()
      == "picked kind # nonemo: N002 # nonemo: N003\ntype # nonemo: kind\n"
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


def test_prose_context_counts_and_rule_exclusions(tmp_path):
  import importlib.util
  import json

  source = tmp_path / "example.md"
  source.write_text("Run.\n")
  probe = run("prose", "--context", "instruction", str(source), cwd=tmp_path)
  assert probe.returncode == 0, probe.stderr

  helper = SCRIPT.with_name("prose_limits.py")
  spec = importlib.util.spec_from_file_location("prose_limits", helper)
  limits = importlib.util.module_from_spec(spec)
  spec.loader.exec_module(limits)
  instruction_cap = limits.SENTENCE_CAPS["instruction"]
  description_cap = limits.SENTENCE_CAPS["description"]
  assert instruction_cap < description_cap
  source = tmp_path / "example.md"
  sentence = " ".join("term" for _ in range(instruction_cap + 1)) + "."
  source.write_text(sentence + "\n")

  def inspect(context, *extra):
    result = run("prose", "--context", context, *extra, str(source), cwd=tmp_path)
    assert result.returncode in (0, 1), result.stderr
    return json.loads(result.stdout)

  instruction = inspect("instruction")
  description = inspect("description")
  assert instruction["findings"]
  assert not description["findings"]
  finding = instruction["findings"][0]
  assert finding["count"] > finding["cap"] == instruction_cap
  assert finding["path"] == str(source)
  assert finding["line"] == source.read_text().splitlines().index(sentence) + 1
  assert inspect("unknown")["coverage"][0]["sentences"] == "not_checked"
  code = finding["rule"]
  source.write_text(f"<!-- nonemo: {code} -->\n{sentence}\n")
  assert not inspect("instruction")["findings"]
  listing = run("--ignores", str(source), cwd=tmp_path)
  assert listing.returncode == 0 and code in listing.stdout

  cap = limits.PARAGRAPH_CAP
  source.write_text(" ".join("Short." for _ in range(cap + 1)) + "\n")
  paragraphs = inspect("description")["findings"]
  assert paragraphs and paragraphs[0]["count"] > paragraphs[0]["cap"] == cap
  source.write_text(" ".join("Short." for _ in range(cap)) + "\n")
  assert not inspect("description")["findings"]
  stricter = cap - 1
  assert inspect("description", "--paragraph-cap", str(stricter))["findings"]
  relaxed = run("prose", "--paragraph-cap", str(cap + 1), str(source), cwd=tmp_path)
  assert relaxed.returncode == 2
  source.write_text("```\n" + sentence + "\n```\n")
  assert not inspect("instruction")["findings"]
  import shutil

  portable = tmp_path / "portable"
  shutil.copytree(
    SCRIPT.parent.parent, portable, ignore=shutil.ignore_patterns("__pycache__")
  )
  source.write_text("Run.\n")
  shipped = subprocess.run(
    [
      sys.executable,
      str(portable / "scripts/nemoizer"),
      "prose",
      "--context",
      "instruction",
      str(source),
    ],
    capture_output=True,
    text=True,
    check=False,
    cwd=tmp_path,
  )
  assert shipped.returncode == 0, shipped.stderr
  assert not json.loads(shipped.stdout)["findings"]
