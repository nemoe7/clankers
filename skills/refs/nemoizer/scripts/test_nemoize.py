# nonemo: NMO001
# nonemo: NMO002
"""The nemoizer linter reads every text file, honors markers, and lists them."""

import subprocess
import sys
from pathlib import Path, PureWindowsPath

import nemoize

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
    assert "note.md:1: NMO002 picked -> select" in result.stdout
    assert "note.md:1: NMO001 transmit -> send" in result.stdout
    assert "code.py:1: NMO001 kind -> type" in result.stdout


def test_a_line_marker_skips_that_line_and_a_head_marker_skips_the_file():
  import tempfile

  with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    (root / "marked.py").write_text(
      "value = 'kind'  # nonemo: NMO001\npicked = 1\n", encoding="utf-8"
    )
    (root / "whole.md").write_text(
      "<!-- nonemo: NMO001 -->\nkind and picked stay\n", encoding="utf-8"
    )
    result = run(cwd=directory)
    assert "marked.py:1:" not in result.stdout
    assert "marked.py:2: NMO002 picked -> select" in result.stdout
    assert "whole.md:2: NMO002 picked -> select" in result.stdout
    assert "whole.md:2: NMO001 kind -> type" not in result.stdout
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
      "const jar = pickle  // nonemo: NMO002\n",
      encoding="utf-8",
    )
    result = run(cwd=directory)
    assert result.returncode == 0
    assert "ui.js:1: NMO002 picker -> select" in result.stdout
    assert "ui.js:2: NMO002 pick -> select" in result.stdout
    assert "ui.js:3" not in result.stdout
    assert "ui.js:4" not in result.stdout
    formatted = run("--format", cwd=directory)
    assert formatted.returncode == 0, formatted.stderr
    assert ui.read_text(encoding="utf-8") == (
      "const selector = 1\nconst var_select = 2\nconst repick = 3\n"
      "const jar = pickle  // nonemo: NMO002\n"
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
      "kind stays  <!-- nonemo: NMO001 -->\npicked one\nkind moves\n",
      encoding="utf-8",
    )
    result = run("--format", cwd=directory)
    assert result.returncode == 0, result.stderr
    assert note.read_text(encoding="utf-8") == (
      "kind stays  <!-- nonemo: NMO001 -->\nselected one\ntype moves\n"
    )


def test_the_format_mode_replaces_the_word_inside_a_longer_one():
  import tempfile

  with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    note = root / "note.md"
    note.write_text(
      "the kind of jar\nKIND stays upper\nthe jar is pickle  # nonemo: NMO002\n",
      encoding="utf-8",
    )
    result = run("--format", cwd=directory)
    assert result.returncode == 0, result.stderr
    assert note.read_text(encoding="utf-8") == (
      "the type of jar\nTYPE stays upper\nthe jar is pickle  # nonemo: NMO002\n"
    )


def test_rule_ids_suppress_only_the_named_rotation():
  import tempfile

  with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    note = root / "note.md"
    note.write_text(
      "kind and picked  # nonemo: NMO001\ntransmit # nonemo: N999\n", encoding="utf-8"
    )
    result = run(cwd=directory)
    assert result.returncode == 1
    assert "note.md:1: NMO002 picked -> select" in result.stdout
    assert "note.md:1: NMO001 kind -> type" not in result.stdout
    assert "note.md:2: NMO001 transmit -> send" in result.stdout
    result = run("--format", cwd=directory)
    assert result.returncode == 0
    assert (
      note.read_text() == "kind and selected  # nonemo: NMO001\nsend # nonemo: N999\n"
    )


def test_collect_keeps_all_markers_including_suppressed_files():
  import tempfile

  with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    note = root / "note.md"
    note.write_text(
      "# nonemo: NMO001\n# nonemo: NMO002\n# nonemo: HMN000\nkind # nonemo: NMO001 # nonemo: N999\n",
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
    assert "note.md:1: NMO001 file:" in result.stdout  # nonemo: NMT001
    assert "note.md:3: HMN000 file:" in result.stdout  # nonemo: NMT001
    assert "note.md:4: NMO001 line:" in result.stdout  # nonemo: NMT001
    assert "note.md:4: N999 unknown:" in result.stdout  # nonemo: NMT001
    legacy = run("--ignores", cwd=directory)
    assert legacy.returncode == 0 and legacy.stdout == result.stdout


def test_multiple_rule_exclusions_preserve_the_marker_text():
  import tempfile

  with tempfile.TemporaryDirectory() as directory:
    note = Path(directory) / "note.md"
    content = "picked kind # nonemo: NMO002 # nonemo: NMO001\nkind # nonemo: kind\n"
    note.write_text(content, encoding="utf-8")
    result = run(cwd=directory)
    assert "note.md:1:" not in result.stdout
    assert "note.md:2: NMO001 kind -> type" in result.stdout
    formatted = run("--format", cwd=directory)
    assert formatted.returncode == 0
    assert (
      note.read_text()
      == "picked kind # nonemo: NMO002 # nonemo: NMO001\ntype # nonemo: kind\n"
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

  helper = SCRIPT
  spec = importlib.util.spec_from_file_location("nemoizer_limits", helper)
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
  assert inspect("unknown")["coverage"][0]["sentences"] == "checked"
  assert inspect("unknown")["findings"]
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
  source.write_text("~~~\n" + sentence + "\n~~~\n")
  assert not inspect("instruction")["findings"]
  source.write_text("`" + sentence + "`\n")
  assert not inspect("instruction")["findings"]
  cell = " ".join("term" for _ in range(instruction_cap // 2 + 1))
  source.write_text(f"| Left | Right |\n| --- | --- |\n| {cell} | {cell} |\n")
  assert not inspect("instruction")["findings"]
  source.write_text(f"| Left | Right |\n| --- | --- |\n| {sentence} | Short |\n")
  assert inspect("instruction")["findings"]
  import csv

  source.write_text("term" * (csv.field_size_limit() + 1) + " | term\n")
  assert not inspect("instruction")["findings"]
  import shutil

  portable = tmp_path / "portable"
  (portable / "scripts").mkdir(parents=True)
  for entry in (
    SCRIPT,
    SCRIPT.with_name("nemoizer"),
    SCRIPT.with_name("prose.py"),
    SCRIPT.with_name("javascript-comments.cjs"),
  ):
    shutil.copy2(entry, portable / "scripts" / entry.name)
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


def test_explicit_assertion_review_keeps_contracts_and_reports_coverage(tmp_path):
  import json

  source = tmp_path / "test_example.py"
  original = """
assert result.stdout == "Saved the report successfully."
assert panel.width == 320
assert panel.width >= config.MIN_WIDTH
assert panel.width == config.MIN_WIDTH
assert len(writes) == 1
assert recovered == "User text stays exact."
assert result.stdout == "POLL AGAIN"
assert result.stdout == expected
assert panel.width == 0
assert lint("The state was saved.")
assert valid, "This explanation is not an expectation."
self.assertEqual(result.stderr, "The report was saved.")
self.assertIn("The report was saved.", result.stdout)
cls.assertEqual(panel.clientWidth, 320.5)
"""
  source.write_text(original)

  def inspect(*paths, cwd=tmp_path):
    result = run("review-tests", *map(str, paths), cwd=cwd)
    assert result.returncode in (0, 1, 2), result.stderr
    return result, json.loads(result.stdout)

  probe = run("review-tests", str(source), cwd=tmp_path)
  assert probe.returncode == 1, probe.stderr
  result, data = inspect(source)
  assert result.returncode == 1
  assert {row["category"] for row in data["findings"]} == {"output_text", "measurement"}
  expected_lines = {
    original.splitlines().index(line) + 1
    for line in original.splitlines()
    if line.startswith(
      (
        'assert result.stdout == "Saved',
        "assert panel.width == 320",
        "self.assertEqual",
        "self.assertIn",
        "cls.assertEqual",
      )
    )
  }
  assert {row["line"] for row in data["findings"]} == expected_lines
  assert all(
    row["path"] == str(source) and row["status"] == "review" for row in data["findings"]
  )
  assert source.read_text() == original
  measurement = next(
    row["rule"] for row in data["findings"] if row["category"] == "measurement"
  )
  source.write_text(f"# nonemo: {measurement}\n# nonemo: N999\n" + original)
  _, suppressed = inspect(source)
  assert suppressed["findings"]
  assert all(row["rule"] != measurement for row in suppressed["findings"])
  listing = run("--ignores", str(source), cwd=tmp_path)
  assert listing.returncode == 0
  assert (
    measurement in listing.stdout
    and "N999" in listing.stdout
    and "unknown" in listing.stdout
  )

  js = tmp_path / "test_example.cjs"
  js.write_text(
    'const 𐐀 = 0; assert.equal(result.stdout, "Saved the report successfully.");\n'
    "assert.equal(panel.width, 320);\n"
    'assert.equal(recovered, "User text stays exact.");\n',
    encoding="utf-8",
  )
  _, javascript = inspect(js, cwd=SCRIPT.parents[3])
  coverage = javascript["coverage"][0]
  if coverage["status"] == "checked":
    position = next(
      row for row in javascript["findings"] if row["category"] == "output_text"
    )
    assert (
      position["column"] == js.read_text(encoding="utf-8").index("assert.equal") + 1
    )
  if coverage["status"] == "checked":
    assert {row["category"] for row in javascript["findings"]} == {
      "output_text",
      "measurement",
    }
  else:
    assert (
      coverage["status"] == "not_checked" and coverage["reason"] == "parser_unavailable"
    )
  source.write_text("assert (\n")
  failed, malformed = inspect(source)
  assert failed.returncode == 2
  assert malformed["errors"][0]["path"] == str(source)
  assert malformed["errors"][0]["type"] == "SyntaxError"
  assert malformed["errors"][0]["line"] > 0
  other = tmp_path / "fixture.txt"
  other.write_text(original)
  _, unsupported = inspect(other)
  assert unsupported["coverage"][0]["status"] == "not_checked"
  assert not unsupported["findings"]

  unicode_line = "λ = 0; assert panel.width == 320\n"
  source.write_text(unicode_line, encoding="utf-8")
  _, unicode_data = inspect(source)
  _, repeated = inspect(source, source)
  assert repeated["findings"] == unicode_data["findings"]
  assert len(repeated["coverage"]) == len({row["path"] for row in repeated["coverage"]})
  position = next(
    row for row in unicode_data["findings"] if row["category"] == "measurement"
  )
  assert position["column"] == unicode_line.index("panel.width") + 1

  invalid_bytes = tmp_path / "invalid.py"
  invalid_bytes.write_bytes(b"\xff")
  skipped, unreadable = inspect(invalid_bytes)
  assert skipped.returncode == 0
  assert unreadable["coverage"][0]["reason"] == "unreadable_or_non_text"
  assert invalid_bytes.read_bytes() == b"\xff"

  import os
  import shutil

  missing_parser = subprocess.run(
    [sys.executable, str(SCRIPT), "review-tests", str(js)],
    cwd=tmp_path,
    capture_output=True,
    text=True,
    env={**os.environ, "PATH": ""},
    check=False,
  )
  assert missing_parser.returncode == 0, missing_parser.stderr
  assert (
    json.loads(missing_parser.stdout)["coverage"][0]["reason"] == "parser_unavailable"
  )

  portable = tmp_path / "portable"
  portable.mkdir()
  for filename in ("nemoizer", "nemoize.py", "prose.py", "javascript-comments.cjs"):
    shutil.copy2(SCRIPT.with_name(filename), portable / filename)
  shipped = subprocess.run(
    [sys.executable, str(portable / "nemoizer"), "review-tests", str(source)],
    cwd=tmp_path,
    capture_output=True,
    text=True,
    check=False,
  )
  assert shipped.returncode == 1, shipped.stderr
  assert any(
    row["category"] == "measurement" for row in json.loads(shipped.stdout)["findings"]
  )
  absent = run("review-tests", str(tmp_path / "missing.py"), cwd=tmp_path)
  assert absent.returncode == 2
  assert not absent.stdout

  project = tmp_path / "other-project"
  dependency = project / "node_modules" / "acorn"
  dependency.mkdir(parents=True)
  marker = project / "executed"
  (dependency / "index.js").write_text(
    "require('node:fs').writeFileSync(" + json.dumps(str(marker)) + ", 'executed');\n"
    "module.exports = {parse(){return {type:'Program', body:[]};}};\n",
    encoding="utf-8",
  )
  target = project / "test_sample.cjs"
  target_text = "assert.equal(panel.width, 320);\n"
  target.write_text(target_text, encoding="utf-8")
  _, isolated = inspect(target, cwd=project)
  assert not marker.exists(), "A target project supplied executable parser code"
  assert target.read_text(encoding="utf-8") == target_text
  if isolated["coverage"][0]["status"] == "checked":
    assert any(row["category"] == "measurement" for row in isolated["findings"])

    target.write_text("assert.equal(\n", encoding="utf-8")
    failed_js, syntax = inspect(target, cwd=project)
    assert failed_js.returncode == 2
    assert syntax["errors"][0]["path"] == str(target)
    assert syntax["errors"][0]["type"] == "SyntaxError"
    assert syntax["errors"][0]["line"] > 0
    assert not marker.exists()


def test_ignore_prefixes_accept_windows_paths():
  class WindowsPath(PureWindowsPath):
    def resolve(self):
      return self

  root = WindowsPath("C:/repo")
  assert nemoize.skipped(root / "vendor" / "file.txt", root, ["vendor"])
  assert nemoize.skipped(root / ".agents" / "skills" / "tool" / "SKILL.md", root, [])
  assert nemoize.skipped(root / "node_modules" / "lib" / "file.js", root, [])
  assert not nemoize.skipped(root / "app" / "code.py", root, ["vendor"])


def test_generated_pytest_cache_is_not_scanned(tmp_path):
  cache = tmp_path / ".pytest_cache" / "v" / "cache"
  cache.mkdir(parents=True)
  (cache / "nodeids").write_text("picked fixture\n", encoding="utf-8")
  (tmp_path / "prose.md").write_text("picked wording\n", encoding="utf-8")
  result = run(cwd=tmp_path)
  assert result.returncode == 0
  assert "prose.md:1: NMO002" in result.stdout  # nonemo: NMT001
  assert ".pytest_cache" not in result.stdout


def test_prose_and_test_ids_have_separate_domains():
  assert set(nemoize.RULE_IDS.values()) == {"NMO001", "NMO002"}
  assert nemoize.PROSE_RULE_IDS == {
    "semicolon": "STE001",
    "sentence": "STE002",
    "passive": "STE003",
    "phrasal": "STE004",
    "ellipsis": "STE005",
    "paragraph": "NMP001",
    "serial_comma": "NMO003",
  }
  assert nemoize.TEST_RULE_IDS == {"output_text": "NMT001", "measurement": "NMT002"}
  assert nemoize.RESERVED_RULE_IDS == {"HMN000"}
  assert "HMN000" in nemoize.KNOWN_RULE_IDS
  assert not (
    {"P001", "P002", "P003", "P004", "T001", "T002", "N001", "N002", "N003"}
    & nemoize.KNOWN_RULE_IDS
  )


def test_default_scan_checks_semicolon_sentence_and_paragraph_caps(tmp_path):
  sentence = " ".join(["term"] * (nemoize.SENTENCE_CAPS["instruction"] + 1)) + "."
  source = tmp_path / "note.md"
  source.write_text(
    sentence + "\n\n" + "Short. " * (nemoize.PARAGRAPH_CAP + 1) + "\n\nFirst; second.\n"
  )
  result = run(cwd=tmp_path)
  assert result.returncode == 1, result.stderr
  assert "note.md:1: STE002" in result.stdout  # nonemo: NMT001
  assert "note.md:3: NMP001" in result.stdout  # nonemo: NMT001
  assert "note.md:5: STE001 1 -> 0" in result.stdout  # nonemo: NMT001
  description = run("--context", "description", cwd=tmp_path)
  assert description.returncode == 1, description.stderr
  assert "STE002" not in description.stdout
  assert "NMP001" in description.stdout and "STE001" in description.stdout


def test_cmd_and_bat_files_extract_only_batch_comments_and_enforce_ste001(tmp_path):
  cmd = tmp_path / "run.cmd"
  cmd.write_text(
    "@echo off\n"
    "set PATH=C:\\bin;C:\\tools\n"
    "REM First clause; second clause.\n"
    ":: Suppressed; clause. nonemo: STE001\n",
    encoding="utf-8",
  )
  result = run(str(cmd), cwd=tmp_path)
  assert result.returncode == 1, result.stderr
  assert f"{cmd}:3: STE001 1 -> 0" in result.stdout
  assert f"{cmd}:2:" not in result.stdout
  assert f"{cmd}:4:" not in result.stdout


def test_default_prose_checks_extract_python_comments_not_literals(tmp_path):
  sentence = " ".join(["term"] * (nemoize.SENTENCE_CAPS["instruction"] + 1)) + "."
  source = tmp_path / "example.py"
  source.write_text(f'value = "{sentence}"\n')
  assert run(cwd=tmp_path).returncode == 0
  source.write_text(f'value = "{sentence}"\n# {sentence}\n')
  result = run(cwd=tmp_path)
  assert result.returncode == 1, result.stderr
  assert "example.py:2: STE002" in result.stdout  # nonemo: NMT001
  assert "example.py:1:" not in result.stdout


def test_rotation_group_markers_and_removed_legacy_aliases(tmp_path):
  source = tmp_path / "note.md"
  source.write_text(
    "kind picked transmit # nonemo: NMO001 # nonemo: NMO002\n"
    "kind picked transmit # nonemo: N003 # nonemo: P001\n"
  )
  result = run(cwd=tmp_path)
  assert result.returncode == 1, result.stderr
  assert "note.md:1:" not in result.stdout
  assert "note.md:2: NMO002 picked -> select" in result.stdout
  assert "note.md:2: NMO001 transmit -> send" in result.stdout
  assert "note.md:2: NMO001 kind -> type" in result.stdout


def test_default_prose_scan_reports_parse_errors(tmp_path):
  source = tmp_path / "broken.py"
  source.write_text("def unfinished(\n")
  result = run(cwd=tmp_path)
  assert result.returncode == 2
  assert str(source) in result.stderr or source.name in result.stderr


def test_default_test_scope_excludes_imported_production_files(tmp_path):
  (tmp_path / "app.py").write_text('assert result.stdout == "Saved the report."\n')
  (tmp_path / "test_status.py").write_text(
    'import app\nassert result.stdout == "Saved the report."\n'
  )
  result = run(cwd=tmp_path)
  assert result.returncode == 1, result.stderr
  assert "test_status.py:2: NMT001" in result.stdout  # nonemo: NMT001
  assert "app.py:1: NMT001" not in result.stdout  # nonemo: NMT001


def test_default_test_scope_uses_configured_patterns_and_explicit_helpers(tmp_path):
  (tmp_path / "pytest.ini").write_text(
    "[pytest]\ntestpaths = specs\npython_files = scenario_*.py\n"
  )
  specs = tmp_path / "specs"
  specs.mkdir()
  (specs / "scenario_status.py").write_text(
    'assert result.stdout == "Saved the report."\n'
  )
  helper = tmp_path / "helper.py"
  helper.write_text('assert result.stdout == "Saved the report."\n')
  result = run(cwd=tmp_path)
  assert result.returncode == 1, result.stderr
  assert "scenario_status.py:1: NMT001" in result.stdout  # nonemo: NMT001
  assert "helper.py:1: NMT001" not in result.stdout  # nonemo: NMT001
  explicit = run("--test-helper", str(helper), cwd=tmp_path)
  assert explicit.returncode == 1, explicit.stderr
  assert "helper.py:1: NMT001" in explicit.stdout  # nonemo: NMT001


def test_default_javascript_test_scope_uses_declarations_not_string_examples(tmp_path):
  app = tmp_path / "app.js"
  app.write_text(
    'const example = "from \'node:test\'"; assert.equal(result.stdout, "Saved the report.");\n'
  )
  assert run(cwd=tmp_path).returncode == 0
  suite = tmp_path / "suite.js"
  suite.write_text(
    'const { test } = require("node:test"); '
    'test("status", () => { assert.equal(result.stdout, "Saved the report."); });\n'
  )
  result = run(cwd=tmp_path)
  assert result.returncode == 1, result.stderr
  assert "suite.js:1: NMT001" in result.stdout  # nonemo: NMT001
  assert "app.js:1: NMT001" not in result.stdout  # nonemo: NMT001


def test_explicit_prose_mode_uses_shared_source_extraction(tmp_path):
  import json

  sentence = " ".join(["term"] * (nemoize.SENTENCE_CAPS["instruction"] + 1)) + "."
  source = tmp_path / "example.py"
  source.write_text(f'value = "{sentence}"\n')
  result = run("prose", str(source), cwd=tmp_path)
  assert result.returncode == 0, result.stderr
  source.write_text(f'value = "{sentence}"\n# {sentence}\n')
  result = run("prose", str(source), cwd=tmp_path)
  assert result.returncode == 1, result.stderr
  assert {row["line"] for row in json.loads(result.stdout)["findings"]} == {2}


def test_unreadable_detected_test_is_not_silently_checked(tmp_path):
  source = tmp_path / "test_bytes.py"
  content = b"\xff"
  source.write_bytes(content)
  result = run(cwd=tmp_path)
  assert result.returncode == 2
  assert str(source) in result.stderr or source.name in result.stderr
  assert "unreadable_or_non_text" in result.stderr
  assert source.read_bytes() == content


def test_block_comment_prose_keeps_its_source_line_and_exclusion(tmp_path):
  sentence = " ".join(["term"] * (nemoize.SENTENCE_CAPS["instruction"] + 1)) + "."
  source = tmp_path / "example.js"
  prefix = "\n" * 4
  source.write_text(prefix + "/*\n * " + sentence + "\n */\n")
  first = source.read_text().splitlines().index(" * " + sentence) + 1
  result = run(cwd=tmp_path)
  assert result.returncode == 1, result.stderr
  assert f"example.js:{first}: STE002" in result.stdout
  source.write_text(
    prefix + "/*\n * " + sentence + " nonemo: STE002\n * " + sentence + "\n */\n"
  )
  result = run(cwd=tmp_path)
  assert result.returncode == 1, result.stderr
  assert f"example.js:{first}: STE002" not in result.stdout
  assert f"example.js:{first + 1}: STE002" in result.stdout


def test_escaped_docstring_newline_uses_a_physical_source_line(tmp_path):
  sentence = " ".join(["term"] * (nemoize.SENTENCE_CAPS["instruction"] + 1)) + "."
  source = tmp_path / "example.py"
  for prefix in ("Short.\\n", "\\n", "\\nShort.\\n"):
    source.write_text('"""' + prefix + sentence + '"""\n')
    result = run(cwd=tmp_path)
    assert result.returncode == 1, result.stderr
    assert "example.py:1: STE002" in result.stdout  # nonemo: NMT001


def test_source_extractors_skip_module_and_yaml_data_literals(tmp_path):
  sentence = " ".join(["term"] * (nemoize.SENTENCE_CAPS["instruction"] + 1)) + "."
  for filename, code in (
    ("example.mjs", 'const value = "' + sentence + '";\n'),
    ("example.yaml", 'value: "' + sentence + '"\n'),
  ):
    source = tmp_path / filename
    source.write_text(code)
    result = run(str(source), cwd=tmp_path)
    assert result.returncode == 0, (filename, result.stdout, result.stderr)


def test_explicit_prose_reports_parser_runtime_failures(tmp_path, monkeypatch, capsys):
  import json

  source = tmp_path / "example.py"
  source.write_text('"""Short."""\n')
  for error in (RuntimeError, RecursionError):

    def fail(*arguments, error=error):
      raise error("parser failed")

    monkeypatch.setattr(nemoize, "source_prose", fail)
    assert nemoize.prose_main([str(source)]) == 2
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert result["findings"] == []
    assert result["coverage"][0]["sentences"] == "not_checked"
    assert result["coverage"][0]["paragraphs"] == "not_checked"
    assert result["coverage"][0]["reason"] == "parse_error"
    assert error.__name__ in captured.err


def test_markdown_trailing_newline_keeps_source_lines_and_local_exclusions(tmp_path):
  sentence = " ".join(["term"] * (nemoize.SENTENCE_CAPS["instruction"] + 1)) + "."
  source = tmp_path / "note.md"
  lines = [
    "# Note",
    "",
    "Short.",
    "",
    sentence,
    "",
    sentence + " <!-- nonemo: STE002 -->",
  ]
  source.write_text("\n".join(lines) + "\n")
  result = run(cwd=tmp_path)
  first = lines.index(sentence) + 1
  second = len(lines)
  assert result.returncode == 1, result.stderr
  assert f"note.md:{first}: STE002" in result.stdout
  assert f"note.md:{second}: STE002" not in result.stdout


def test_wrapped_prose_counts_the_complete_sentence(tmp_path):
  cap = nemoize.SENTENCE_CAPS["instruction"]
  for filename, prefix in (("note.md", ""), ("note.py", "# ")):
    source = tmp_path / filename
    first = 5
    for count in (cap, cap + 1):
      words = ["term"] * count
      middle = len(words) // 2
      lines = [""] * (first - 1) + [
        prefix + " ".join(words[:middle]),
        prefix + " ".join(words[middle:]) + ".",
      ]
      source.write_text("\n".join(lines) + "\n")
      result = run(str(source), cwd=tmp_path)
      assert result.returncode == int(count > cap), result.stderr
      if count > cap:
        assert f"{source}:{first}: STE002" in result.stdout
    lines[first - 1] += " nonemo: STE002"
    source.write_text("\n".join(lines) + "\n")
    assert run(str(source), cwd=tmp_path).returncode == 0


def test_soft_rotation_is_advisory_in_checks_and_explicit_in_format(tmp_path):
  source = tmp_path / "note.md"
  original = "Pick one.\n"
  source.write_text(original)
  result = run(str(source), cwd=tmp_path)
  assert result.returncode == 0, result.stderr
  assert "NMO002 Pick -> select" in result.stdout
  assert "advisory" in result.stdout
  assert source.read_text() == original
  formatted = run("--format", str(source), cwd=tmp_path)
  assert formatted.returncode == 0
  assert source.read_text() == "Select one.\n"
  source.write_text("Pick this kind.\n")
  assert run(str(source), cwd=tmp_path).returncode == 1
  source.write_text("Pick one. <!-- nonemo: NMO002 -->\n")
  assert not run(str(source), cwd=tmp_path).stdout.strip()


def test_repository_rotation_and_ste003_passive_voice_are_advisory(tmp_path):
  source = tmp_path / "note.md"
  source.write_text(
    "Clone the Repository and both repositories. The report was published.\n"
  )
  result = run(str(source), cwd=tmp_path)
  assert result.returncode == 0, result.stderr
  assert "NMO002 Repository -> repo (advisory)" in result.stdout
  assert "NMO002 repositories -> repo (advisory)" in result.stdout
  assert "STE003 1 -> 0 (advisory)" in result.stdout
  formatted = run("--format", str(source), cwd=tmp_path)
  assert formatted.returncode == 0
  assert (
    source.read_text() == "Clone the Repo and both repos. The report was published.\n"
  )
  source.write_text("The report was published. <!-- nonemo: STE003 -->\n")
  assert not run(str(source), cwd=tmp_path).stdout.strip()
  source.write_text(
    "Set up the server. The state is parsed and validated. Check red, green and blue.\n"
  )
  advisory = run(str(source), cwd=tmp_path)
  assert advisory.returncode == 0, advisory.stderr
  assert "STE004 1 -> 0 (advisory)" in advisory.stdout
  assert "STE005 1 -> 0 (advisory)" in advisory.stdout
  assert "NMO003 1 -> 0 (advisory)" in advisory.stdout
  test_sample = tmp_path / "test_sample.py"
  test_sample.write_text(
    'def test_sample():\n  assert "three plain words" in result.stderr.strip()\n  assert check.measure(path) == 2\n'
  )
  reviewed = nemoize.review_tests([test_sample])
  assert {row["rule"] for row in reviewed["findings"]} == {"NMT001", "NMT002"}
