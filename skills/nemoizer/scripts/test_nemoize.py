# nonemo: NMO100
# nonemo: NMO901
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
    assert "note.md:1: [NMO901] (advisory) picked -> select" in result.stdout
    assert "note.md:1: [NMO100] (advisory-free) transmit -> send" in result.stdout
    assert "code.py:1: [NMO100] (advisory-free) kind -> type" in result.stdout
    assert "\n    He picked one. Do not transmit this." in result.stdout
    assert (
      nemoize.format_summary(
        [
          "note.md:1: [NMO100] (advisory-free) transmit -> send",
          "code.py:1: [NMO100] (advisory-free) kind -> type",
          "note.md:1: [NMO901] (advisory) picked -> select",
        ]
      )
      in result.stdout
    )


def test_a_line_marker_skips_that_line_and_a_head_marker_skips_the_file():
  import tempfile

  with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    (root / "marked.py").write_text(
      "value = 'kind'  # nonemo: NMO100\n# picked one\n", encoding="utf-8"
    )
    (root / "whole.md").write_text(
      "<!-- nonemo: NMO100 -->\nkind and picked stay\n", encoding="utf-8"
    )
    result = run(cwd=directory)
    assert "marked.py:1:" not in result.stdout
    assert "marked.py:2: [NMO901] (advisory) picked -> select" in result.stdout
    assert "whole.md:2: [NMO901] (advisory) picked -> select" in result.stdout
    assert "whole.md:2: [NMO100] (advisory-free) kind -> type" not in result.stdout
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
      "// picker widget\nconst var_pick = 2\n// repick item\n"
      "// pickle jar  nonemo: NMO901\n",
      encoding="utf-8",
    )
    result = run(cwd=directory)
    assert result.returncode == 0
    assert "ui.js:1: [NMO901] (advisory) picker -> select" in result.stdout
    assert "ui.js:2" not in result.stdout
    assert "ui.js:3" not in result.stdout
    assert "ui.js:4" not in result.stdout
    formatted = run("--format", cwd=directory)
    assert formatted.returncode == 0, formatted.stderr
    assert ui.read_text(encoding="utf-8") == (
      "// selector widget\nconst var_pick = 2\n// repick item\n"
      "// pickle jar  nonemo: NMO901\n"
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
      "kind stays  <!-- nonemo: NMO100 -->\npicked one\nkind moves\n",
      encoding="utf-8",
    )
    result = run("--format", cwd=directory)
    assert result.returncode == 0, result.stderr
    assert note.read_text(encoding="utf-8") == (
      "kind stays  <!-- nonemo: NMO100 -->\nselected one\ntype moves\n"
    )


def test_the_format_mode_replaces_the_word_inside_a_longer_one():
  import tempfile

  with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    note = root / "note.md"
    note.write_text(
      "the kind of jar\nKIND stays upper\nthe jar is pickle  # nonemo: NMO901\n",
      encoding="utf-8",
    )
    result = run("--format", cwd=directory)
    assert result.returncode == 0, result.stderr
    assert note.read_text(encoding="utf-8") == (
      "the type of jar\nTYPE stays upper\nthe jar is pickle  # nonemo: NMO901\n"
    )


def test_name_rotates_only_as_a_verb():
  import tempfile

  with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    note = root / "note.md"
    note.write_text(
      "Name the variable.\nIt names each field.\n"
      "Use the name of the file.\nRename the file later.\n",
      encoding="utf-8",
    )
    result = run(cwd=directory)
    for expected in (
      "note.md:1: [NMO901] (advisory) Name -> specify",
      "note.md:2: [NMO901] (advisory) names -> specify",
    ):
      assert expected in result.stdout
    for line_number in (3, 4):
      assert f"note.md:{line_number}: [NMO901]" not in result.stdout
    result = run("--format", cwd=directory)
    assert result.returncode == 0, result.stderr
    assert note.read_text(encoding="utf-8") == (
      "Specify the variable.\nIt specifies each field.\n"
      "Use the name of the file.\nRename the file later.\n"
    )


def test_rule_ids_suppress_only_the_named_rotation():
  import tempfile

  with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    note = root / "note.md"
    note.write_text(
      "kind and picked  # nonemo: NMO100\ntransmit # nonemo: N999\n", encoding="utf-8"
    )
    result = run(cwd=directory)
    assert result.returncode == 1
    assert "note.md:1: [NMO901] (advisory) picked -> select" in result.stdout
    assert "note.md:1: [NMO100] (advisory-free) kind -> type" not in result.stdout
    assert "note.md:2: [NMO100] (advisory-free) transmit -> send" in result.stdout
    result = run("--format", cwd=directory)
    assert result.returncode == 0
    assert (
      note.read_text() == "kind and selected  # nonemo: NMO100\nsend # nonemo: N999\n"
    )


def test_collect_keeps_all_markers_including_suppressed_files():
  import tempfile

  with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    note = root / "note.md"
    note.write_text(
      "# nonemo: NMO100\n# nonemo: NMO901\n# nonemo: HMN000\nkind # nonemo: NMO100 # nonemo: N999\n",
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
    assert "note.md:1: NMO100 file:" in result.stdout  # nonemo: NMT100
    assert "note.md:3: HMN000 file:" in result.stdout  # nonemo: NMT100
    assert "note.md:4: NMO100 line:" in result.stdout  # nonemo: NMT100
    assert "note.md:4: N999 unknown:" in result.stdout  # nonemo: NMT100
    legacy = run("--ignores", cwd=directory)
    assert legacy.returncode == 0 and legacy.stdout == result.stdout


def test_multiple_rule_exclusions_preserve_the_marker_text():
  import tempfile

  with tempfile.TemporaryDirectory() as directory:
    note = Path(directory) / "note.md"
    content = "picked kind # nonemo: NMO901 # nonemo: NMO100\nkind # nonemo: kind\n"
    note.write_text(content, encoding="utf-8")
    result = run(cwd=directory)
    assert "note.md:1:" not in result.stdout
    assert "note.md:2: [NMO100] (advisory-free) kind -> type" in result.stdout
    formatted = run("--format", cwd=directory)
    assert formatted.returncode == 0
    assert (
      note.read_text()
      == "picked kind # nonemo: NMO901 # nonemo: NMO100\ntype # nonemo: kind\n"
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
  assert "prose.md:1: [NMO901]" in result.stdout  # nonemo: NMT100
  assert ".pytest_cache" not in result.stdout


def test_prose_and_test_ids_have_separate_domains():
  assert set(nemoize.RULE_IDS.values()) == {"NMO100", "NMO901"}
  assert nemoize.PROSE_RULE_IDS == {
    "dangling_conjunction": "STE001",
    "semicolon": "STE100",
    "sentence": "STE200",
    "nominalization": "STE300",
    "wordy_phrase": "STE400",
    "archaic_connector": "STE401",
    "passive": "STE901",
    "phrasal": "STE902",
    "ellipsis": "STE903",
    "compound_instruction": "STE904",
    "noun_cluster": "STE905",
    "synonym_cluster": "STE906",
    "compound_tense": "STE908",
    "inline_list": "STE909",
    "double_negative": "STE910",
    "staged_frame": "HMN100",
    "stacked_qualifier": "HMN200",
    "ai_vocabulary": "HMN300",
    "arrow": "HMN400",
    "chatbot_courtesy": "HMN500",
    "curly_quote": "HMN600",
    "negative_contrast": "HMN901",
    "aphorism": "HMN902",
    "rhetorical_setup": "HMN903",
    "repeated_opener": "HMN904",
    "prose_dash": "HMN905",
    "vague_attribution": "HMN906",
    "copula_avoidance": "HMN907",
    "bold_label_bullet": "HMN908",
    "consecutive_emoji": "HMN909",
    "self_narration": "HMN910",
    "paragraph": "NMP100",
    "comment_block": "NMP101",
    "padded_ui_label": "NMU100",
    "serial_comma": "NMO003",
    "the_density": "NMO902",
  }
  assert nemoize.TEST_RULE_IDS == {"output_text": "NMT100", "measurement": "NMT200"}
  assert nemoize.RESERVED_RULE_IDS == {"HMN000"}
  assert "HMN000" in nemoize.KNOWN_RULE_IDS
  assert not (
    {
      "P001",
      "P002",
      "P003",
      "P004",
      "T001",
      "T002",
      "N001",
      "N002",
      "N003",
      "NMO001",
      "NMO002",
      "STE002",
      "STE003",
      "STE004",
      "STE005",
      "NMP001",
      "NMT001",
      "NMT002",
    }
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
  assert (
    f"note.md:1: [STE200] (advisory-free) {nemoize.describe_finding({'rule': 'STE200', 'count': 21, 'cap': 20})}"
    in result.stdout
  )
  assert (
    f"note.md:3: [NMP100] (advisory-free) {nemoize.describe_finding({'rule': 'NMP100', 'count': 5, 'cap': 4})}"
    in result.stdout
  )
  assert (
    f"note.md:5: [STE100] (advisory-free) {nemoize.RULE_DESCRIPTIONS['STE100']}"
    in result.stdout
  )
  description = run("--context", "description", cwd=tmp_path)
  assert description.returncode == 1, description.stderr
  assert "STE200" not in description.stdout
  assert "NMP100" in description.stdout and "STE100" in description.stdout
  code_file = tmp_path / "app.py"
  code_file.write_text("# Line one.\n# Line two.\n# Line three.\nx = 1\n")
  comment_res = run(str(code_file), cwd=tmp_path)
  assert comment_res.returncode == 1, comment_res.stderr
  assert (
    f"{code_file}:1: [NMP101] (advisory-free) {nemoize.describe_finding({'rule': 'NMP101', 'count': 3, 'cap': 2})}"
    in comment_res.stdout
  )


def test_cmd_and_bat_files_extract_only_batch_comments_and_enforce_ste001(tmp_path):
  cmd = tmp_path / "run.cmd"
  cmd.write_text(
    "@echo off\n"
    "set PATH=C:\\bin;C:\\tools\n"
    "REM First clause; second clause.\n"
    ":: Suppressed; clause. nonemo: STE100\n",
    encoding="utf-8",
  )
  result = run(str(cmd), cwd=tmp_path)
  assert result.returncode == 1, result.stderr
  assert (
    f"{cmd}:3: [STE100] (advisory-free) {nemoize.RULE_DESCRIPTIONS['STE100']}"
    in result.stdout
  )
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
  assert "example.py:2: [STE200]" in result.stdout  # nonemo: NMT100
  assert "example.py:1:" not in result.stdout


def test_rotation_group_markers_and_removed_legacy_aliases(tmp_path):
  source = tmp_path / "note.md"
  source.write_text(
    "kind picked transmit # nonemo: NMO100 # nonemo: NMO901\n"
    "kind picked transmit # nonemo: N003 # nonemo: P001\n"
  )
  result = run(cwd=tmp_path)
  assert result.returncode == 1, result.stderr
  assert "note.md:1:" not in result.stdout
  assert "note.md:2: [NMO901] (advisory) picked -> select" in result.stdout
  assert "note.md:2: [NMO100] (advisory-free) transmit -> send" in result.stdout
  assert "note.md:2: [NMO100] (advisory-free) kind -> type" in result.stdout


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
  assert "test_status.py:2: [NMT100]" in result.stdout  # nonemo: NMT100
  assert "app.py:1: [NMT100]" not in result.stdout  # nonemo: NMT100


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
  assert "scenario_status.py:1: [NMT100]" in result.stdout  # nonemo: NMT100
  assert "helper.py:1: [NMT100]" not in result.stdout  # nonemo: NMT100
  explicit = run("--test-helper", str(helper), cwd=tmp_path)
  assert explicit.returncode == 1, explicit.stderr
  assert "helper.py:1: [NMT100]" in explicit.stdout  # nonemo: NMT100


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
  assert "suite.js:1: [NMT100]" in result.stdout  # nonemo: NMT100
  assert "app.js:1: [NMT100]" not in result.stdout  # nonemo: NMT100


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
  assert f"example.js:{first}: [STE200]" in result.stdout
  source.write_text(
    prefix + "/*\n * " + sentence + " nonemo: STE200\n * " + sentence + "\n */\n"
  )
  result = run(cwd=tmp_path)
  assert result.returncode == 1, result.stderr
  assert f"example.js:{first}: [STE200]" not in result.stdout
  assert f"example.js:{first + 1}: [STE200]" in result.stdout


def test_escaped_docstring_newline_uses_a_physical_source_line(tmp_path):
  sentence = " ".join(["term"] * (nemoize.SENTENCE_CAPS["instruction"] + 1)) + "."
  source = tmp_path / "example.py"
  for prefix in ("Short.\\n", "\\n", "\\nShort.\\n"):
    source.write_text('"""' + prefix + sentence + '"""\n')
    result = run(cwd=tmp_path)
    assert result.returncode == 1, result.stderr
    assert "example.py:1: [STE200]" in result.stdout  # nonemo: NMT100


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
    sentence + " <!-- nonemo: STE200 -->",
  ]
  source.write_text("\n".join(lines) + "\n")
  result = run(cwd=tmp_path)
  first = lines.index(sentence) + 1
  second = len(lines)
  assert result.returncode == 1, result.stderr
  assert f"note.md:{first}: [STE200]" in result.stdout
  assert f"note.md:{second}: [STE200]" not in result.stdout


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
        assert f"{source}:{first}: [STE200]" in result.stdout
    lines[first - 1] += " nonemo: STE200"
    source.write_text("\n".join(lines) + "\n")
    assert run(str(source), cwd=tmp_path).returncode == 0


def test_soft_rotation_is_advisory_in_checks_and_explicit_in_format(tmp_path):
  source = tmp_path / "note.md"
  original = "Pick one.\n"
  source.write_text(original)
  result = run(str(source), cwd=tmp_path)
  assert result.returncode == 0, result.stderr
  assert "[NMO901] (advisory) Pick -> select" in result.stdout
  assert "manual review" in result.stdout
  assert source.read_text() == original
  formatted = run("--format", str(source), cwd=tmp_path)
  assert formatted.returncode == 0
  assert source.read_text() == "Select one.\n"
  source.write_text("Pick this kind.\n")
  assert run(str(source), cwd=tmp_path).returncode == 1
  source.write_text("Pick one. <!-- nonemo: NMO901 -->\n")
  assert not run(str(source), cwd=tmp_path).stdout.strip()


def test_repository_rotation_and_ste901_passive_voice_are_manual_review(tmp_path):
  source = tmp_path / "note.md"
  source.write_text(
    "Clone the Repository and both repositories. The report was published.\n"
  )
  result = run(str(source), cwd=tmp_path)
  assert result.returncode == 0, result.stderr
  assert "[NMO901] (advisory) Repository -> repo (manual review)" in result.stdout
  assert "[NMO901] (advisory) repositories -> repo (manual review)" in result.stdout
  assert (
    f"[STE901] (advisory) {nemoize.RULE_DESCRIPTIONS['STE901']} (manual review)"
    in result.stdout
  )
  formatted = run("--format", str(source), cwd=tmp_path)
  assert formatted.returncode == 0
  assert (
    source.read_text() == "Clone the Repo and both repos. The report was published.\n"
  )
  source.write_text("The report was published. <!-- nonemo: STE901 -->\n")
  assert not run(str(source), cwd=tmp_path).stdout.strip()
  source.write_text("Set up the server. The state is parsed and validated.\n")
  advisory = run(str(source), cwd=tmp_path)
  assert advisory.returncode == 0, advisory.stderr
  assert (
    f"[STE902] (advisory) {nemoize.RULE_DESCRIPTIONS['STE902']} (manual review)"
    in advisory.stdout
  )
  assert (
    f"[STE903] (advisory) {nemoize.RULE_DESCRIPTIONS['STE903']} (manual review)"
    in advisory.stdout
  )
  source.write_text("Check red, green and blue.\n")
  serial = run(str(source), cwd=tmp_path)
  assert serial.returncode == 1, serial.stderr
  assert (
    f"[NMO003] (advisory-free) {nemoize.RULE_DESCRIPTIONS['NMO003']}" in serial.stdout
  )
  assert "manual review" not in serial.stdout
  test_sample = tmp_path / "test_sample.py"
  test_sample.write_text(
    'def test_sample():\n  assert "three plain words" in result.stderr.strip()\n  assert check.measure(path) == 2\n'
  )
  reviewed = nemoize.review_tests([test_sample])
  assert {row["rule"] for row in reviewed["findings"]} == {"NMT100", "NMT200"}


def test_ste_and_hmn_rules_and_audit_mode(tmp_path):
  sys.path.insert(0, str(SCRIPT.parent))
  import markers

  note = tmp_path / "guide.md"
  note.write_text(
    "- First item, and\n"
    "Make a decision to delve into the very unique workflow \u2192 now.\n"
    "Let's dive in! As an AI, I suggest \u201cplain\u201d quotes.\n"
    "Click save, and then click close.\n"
    "Update the system server configuration management module.\n"
    "Check each and every rule. The task will have finished.\n"
    "It is not just fast, but also tiny. Key takeaway: ship it.\n"
    "You might be wondering why. The system runs. The system stops. The system waits.\n"
    "Wait\u2014now. Experts agree that it serves as a tool.\n"
    "- **Bold Label:** item \U0001f680\U0001f525\n"
    "This section covers the API. <!-- nonemo: HMN910 -->\n",
    encoding="utf-8",
  )
  result = run(str(note), cwd=tmp_path)
  assert result.returncode == 1, result.stderr
  for code in (
    "STE001",
    "STE300",
    "HMN100",
    "HMN200",
    "HMN300",
    "HMN400",
    "HMN500",
    "HMN600",
    "STE904",
    "STE905",
    "STE906",
    "STE908",
    "HMN901",
    "HMN902",
    "HMN903",
    "HMN904",
    "HMN905",
    "HMN906",
    "HMN907",
    "HMN908",
    "HMN909",
  ):
    assert code in result.stdout
  assert "HMN910" not in result.stdout

  quote_file = tmp_path / "quotes.md"
  quote_file.write_text(
    "Use \u201cstraight\u201d and \u2018plain\u2019 quotes.\n", encoding="utf-8"
  )
  assert run("--format", str(quote_file), cwd=tmp_path).returncode == 0
  assert (
    quote_file.read_text(encoding="utf-8") == "Use \"straight\" and 'plain' quotes.\n"
  )

  userscript = tmp_path / "demo.user.js"
  userscript.write_text('const label = " Foo \\u2014 Bar ";\n', encoding="utf-8")
  us_result = run(str(userscript), cwd=tmp_path)
  assert us_result.returncode == 0
  assert "HMN905" in us_result.stdout

  manifest = tmp_path / "site.webmanifest"
  manifest.write_text(
    '{\n  "name": "Demo",\n  "kind": "transmit",\n  "repository": "demo"\n}\n',
    encoding="utf-8",
  )
  manifest_result = run(str(manifest), cwd=tmp_path)
  assert manifest_result.returncode == 0
  assert manifest_result.stdout.strip() == ""

  json_file = tmp_path / "package.json"
  json_file.write_text(
    '{\n  "name": "demo",\n  "kind": "transmit",\n  "repository": "demo"\n}\n',
    encoding="utf-8",
  )
  json_result = run(str(json_file), cwd=tmp_path)
  assert json_result.returncode == 0
  assert json_result.stdout.strip() == ""

  jsonc_file = tmp_path / "config.jsonc"
  jsonc_file.write_text(
    '{\n  // Transmit the message.\n  "kind": "transmit",\n  "repository": "demo"\n}\n',
    encoding="utf-8",
  )
  jsonc_result = run(str(jsonc_file), cwd=tmp_path)
  assert jsonc_result.returncode == 1
  assert (
    "config.jsonc:2: [NMO100] (advisory-free) Transmit -> send" in jsonc_result.stdout
  )
  assert "kind" not in jsonc_result.stdout
  assert "repository" not in jsonc_result.stdout

  audit = subprocess.run(
    [sys.executable, str(SCRIPT.with_name("nemoizer")), "audit", str(note)],
    cwd=tmp_path,
    capture_output=True,
    text=True,
    check=False,
  )
  collect_alias = subprocess.run(
    [sys.executable, str(SCRIPT.with_name("nemoizer")), "collect", str(note)],
    cwd=tmp_path,
    capture_output=True,
    text=True,
    check=False,
  )
  assert audit.returncode == 0, audit.stderr
  assert collect_alias.returncode == 0, collect_alias.stderr
  assert collect_alias.stdout == audit.stdout
  assert "HMN910 line:" in audit.stdout
  assert "STE904" in audit.stdout
  assert "STE001" not in audit.stdout
  assert markers.main([str(note)]) == 0


def test_references_follow_markdownlint_doc_layout():
  refs_dir = SCRIPT.parent.parent / "references"
  rules_md = (refs_dir / "rules.md").read_text(encoding="utf-8")
  assert "\n# Rules\n" in rules_md
  for code in sorted(nemoize.KNOWN_RULE_IDS - nemoize.RESERVED_RULE_IDS):
    assert f"\n## `{code}` - " in rules_md
    rule_file = refs_dir / f"{code.lower()}.md"
    assert rule_file.is_file(), f"missing {rule_file.name}"
    text = rule_file.read_text(encoding="utf-8")
    assert f"\n# `{code}` - " in text
    assert "\nTags: " in text
    assert "\nAliases: " in text
    assert "\nRationale: " in text


def test_adopted_ste_rules_pull_request_and_license_exemption(tmp_path):
  sample = tmp_path / "sample.md"
  sample.write_text(
    "Save the file prior to closing the window.\n"
    "Update the aforementioned config.\n"
    "Check (1) formatting, (2) lint, and (3) tests.\n"
    "Timeouts are not uncommon on slow links.\n"
    "Open a pull request and merge pull requests.\n",
    encoding="utf-8",
  )
  result = run(str(sample), cwd=tmp_path)
  assert result.returncode == 1
  for code in ("STE400", "STE401", "STE909", "STE910", "NMO901"):
    assert code in result.stdout
  assert (
    nemoize.rotate("Open a pull request and merge Pull Requests.")
    == "Open a PR and merge PRs."
  )
  for license_name in (
    "LICENSE",
    "LICENSE.md",
    "LICENSE.txt",
    "lucide.LICENSE",
    "COPYING",
    "NOTICE",
  ):
    lic = tmp_path / license_name
    lic.write_text("Transmit this kind of repository.\n", encoding="utf-8")
    lic_res = run(str(lic), cwd=tmp_path)
    assert lic_res.returncode == 0
    assert lic_res.stdout.strip() == ""
  dense = tmp_path / "dense.md"
  dense.write_text(
    "Check the status of the server in the logs of the worker.\n",
    encoding="utf-8",
  )
  dense_res = run(str(dense), cwd=tmp_path)
  assert dense_res.returncode == 0
  assert "NMO902" in dense_res.stdout


def test_nemoizer_toml_and_pyproject_config_discovery(tmp_path):
  vendor = tmp_path / "vendor"
  vendor.mkdir()
  (vendor / "skipped.md").write_text("Transmit this kind.\n", encoding="utf-8")
  note = tmp_path / "note.md"
  sentence = " ".join(["term"] * (nemoize.SENTENCE_CAPS["instruction"] + 1)) + "."
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


def test_nmp100_counts_lists_tables_headings_and_blockquotes(tmp_path):
  doc = tmp_path / "doc.md"
  doc.write_text(
    "# First sentence. Second sentence.\n\n"
    "- One. Two. Three.\n"
    "- Valid one. Valid two.\n\n"
    "| Col A | Col B |\n"
    "| --- | --- |\n"
    "| One. Two. Three. Four. Five. | Short. |\n\n"
    "> Quote one. Quote two. Quote three. Quote four. Quote five.\n",
    encoding="utf-8",
  )
  res = run(str(doc), cwd=tmp_path)
  assert res.returncode == 1, res.stderr
  heading_msg = nemoize.describe_finding(
    {"rule": "NMP100", "count": 2, "cap": 1, "kind": "heading"}
  )
  list_msg = nemoize.describe_finding(
    {"rule": "NMP100", "count": 3, "cap": 2, "kind": "list"}
  )
  table_msg = nemoize.describe_finding(
    {"rule": "NMP100", "count": 5, "cap": 4, "kind": "table"}
  )
  quote_msg = nemoize.describe_finding(
    {"rule": "NMP100", "count": 5, "cap": 4, "kind": "blockquote"}
  )
  assert f"[NMP100] (advisory-free) {heading_msg}" in res.stdout
  assert f"[NMP100] (advisory-free) {list_msg}" in res.stdout
  assert f"[NMP100] (advisory-free) {table_msg}" in res.stdout
  assert f"[NMP100] (advisory) {quote_msg} (manual review)" in res.stdout

  quote_only = tmp_path / "quote.md"
  quote_only.write_text(
    "# Single sentence heading\n\n"
    "- Item one. Item two.\n\n"
    "> One. Two. Three. Four. Five.\n",
    encoding="utf-8",
  )
  quote_res = run(str(quote_only), cwd=tmp_path)
  assert quote_res.returncode == 0, quote_res.stderr
  assert f"[NMP100] (advisory) {quote_msg} (manual review)" in quote_res.stdout
  audit_res = run("--audit", str(quote_only), cwd=tmp_path)
  assert audit_res.returncode == 0, audit_res.stderr
  assert f"[NMP100] (advisory) {quote_msg} (manual review)" in audit_res.stdout


def test_config_caps_respect_gitignore_and_bundled_default_config(tmp_path):
  default_toml = SCRIPT.parent.parent / "references" / "nemoizer.toml"
  assert default_toml.is_file()
  cfg = nemoize.load_config(config_path=default_toml)
  assert cfg["respect_gitignore"] is True
  assert cfg["instruction_sentence_cap"] == nemoize.SENTENCE_CAPS["instruction"]
  assert cfg["description_sentence_cap"] == nemoize.SENTENCE_CAPS["description"]
  assert cfg["paragraph_cap"] == nemoize.PARAGRAPH_CAP
  assert cfg["list_sentence_cap"] == nemoize.LIST_SENTENCE_CAP
  assert cfg["heading_sentence_cap"] == nemoize.HEADING_SENTENCE_CAP
  assert cfg["comment_block_cap"] == nemoize.COMMENT_BLOCK_CAP
  assert cfg["the_density_cap"] == nemoize.THE_DENSITY_CAP
  assert cfg["min_the_count"] == nemoize.MIN_THE_COUNT
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
  assert "sub/AGENTS.md" in custom_run.stdout
  assert "sub/ARENA.md" in custom_run.stdout
  assert "NMP100" not in custom_run.stdout
  assert "NMO902" not in custom_run.stdout


def test_nemoizer_proper_name_rotation_and_nmo902_list_article_collapse(tmp_path):
  assert (
    nemoize.rotate("Use the nemoizer, The Nemoizer, THE NEMOIZER, and Nemoizer.")
    == "Use nemoizer, nemoizer, nemoizer, and nemoizer."
  )
  assert (
    nemoize.rotate("The prose linter runs the nemoizer rules.")
    == "The prose linter runs the nemoizer rules."
  )
  assert (
    nemoize.collapse_list_articles(
      "Supply the source text, the target, and the unit for the worker."
    )
    == "Supply the source text, target, and unit for the worker."
  )
  doc = tmp_path / "sample.md"
  doc.write_text(
    "Use The Nemoizer on the source text, the target, and the unit.\n",
    encoding="utf-8",
  )
  findings, _ = nemoize.scan([doc], [])
  assert any(
    "NMO100" in item and "The Nemoizer -> nemoizer" in item for item in findings
  )
  changed = nemoize.format_paths([doc], [])
  assert changed == 1
  assert (
    doc.read_text(encoding="utf-8")
    == "Use nemoizer on the source text, target, and unit.\n"
  )
  assert "--format" in nemoize.RULE_DESCRIPTIONS["NMO902"]


def test_prose_block_rules_evaluate_across_wrapped_lines(tmp_path):
  wrapped = (
    "The service reads the input\n"
    "and writes the output.\n\n"
    "- The server runs.\n"
    "  The server stops.\n"
    "  The server waits.\n\n"
    "Run in order\n"
    "to check red,\n"
    "green and blue.\n\n"
    "This section\n"
    "covers the API.\n"
  )
  assert nemoize.prose_the_density(wrapped) == [(1, 1, 33), (4, 1, 33)]
  assert nemoize.prose_repeated_openers(wrapped) == [(4, 1, 1)]
  assert [row[0] for row in nemoize.prose_wordy_phrases(wrapped)] == [8]
  assert [row[0] for row in nemoize.prose_serial_commas(wrapped)] == [8]
  assert [row[0] for row in nemoize.prose_self_narration(wrapped)] == [12]

  doc = tmp_path / "wrapped.md"
  doc.write_text(
    "Check the source, the target,\nand the unit for the worker.\n",
    encoding="utf-8",
  )
  assert nemoize.format_paths([doc], []) == 1
  assert (
    doc.read_text(encoding="utf-8")
    == "Check the source, target,\nand the unit for the worker.\n"
  )

  html_doc = tmp_path / "page.html"
  html_doc.write_text(
    "<!doctype html><html><body>\n"
    "<style>.btn { content: 'a; b'; }</style>\n"
    "<script>const x = 'a; b';</script>\n"
    '<button aria-label="First clause; second clause">Run</button>\n'
    "<small>Answers reach the agent inbox as one submission; resending makes a new one.</small>\n"
    "</body></html>\n",
    encoding="utf-8",
  )
  html_rows = [
    (row["line"], row["rule"])
    for row in nemoize.source_prose(
      html_doc, html_doc.read_text(encoding="utf-8"), "instruction", 4
    )
  ]
  assert (4, "STE100") in html_rows
  assert (5, "STE100") in html_rows
  assert not any(line in {2, 3} for line, _ in html_rows)

  pyproject_toml = SCRIPT.parent.parent / "pyproject.toml"
  assert pyproject_toml.is_file()
  pyproject_data = nemoize.tomllib.loads(pyproject_toml.read_text(encoding="utf-8"))
  assert pyproject_data["project"]["name"] == "nemoizer"
  assert pyproject_data["project"]["scripts"]["nemoizer"] == "nemoize:main"
  assert set(pyproject_data["tool"]["setuptools"]["py-modules"]) == {
    "nemoize",
    "prose",
    "markers",
  }


def test_workflow_name_spans_identifier_boundaries_and_mixed_determiner_lists(tmp_path):
  wf_dir = tmp_path / ".github" / "workflows"
  wf_dir.mkdir(parents=True)
  wf = wf_dir / "ci.yml"
  wf.write_text(
    "name: Build the image\n"
    "on: push\n"
    "jobs:\n"
    "  deploy:\n"
    "    name: Deploy the release\n"
    "    runs-on: ubuntu-latest\n"
    "    environment: { name: github-pages }\n"
    "    env:\n"
    "      name: the-env-var\n"
    "      repo_ref: ${{ github.repository }}\n"
    "    steps:\n"
    "      - name: Checkout the code\n"
    "        uses: actions/checkout@v4\n"
    "        with:\n"
    "          name: the-artifact\n"
    "          repository: ${{ github.repository }}\n"
    "      - name: build-slug\n"
    "        run: echo ok\n",
    encoding="utf-8",
  )
  wf_res = run(str(wf), cwd=tmp_path)
  assert wf_res.returncode == 0, wf_res.stderr
  for hit_ln in (1, 5, 12):
    assert f"{wf.name}:{hit_ln}: [NMO902]" in wf_res.stdout
  assert "NMO901" not in wf_res.stdout
  for skipped_ln in (7, 9, 10, 15, 16, 17):
    assert f"ci.yml:{skipped_ln}:" not in wf_res.stdout

  py_file = tmp_path / "mod.py"
  py_file.write_text(
    '""" Process items.\n\n'
    ":param repository: Target repo.\n"
    ":param picker: Widget selector.\n"
    '"""\n'
    "def run_task(user_repository, pick_mode):\n"
    '  url = "https://example.com/repository/pick"\n'
    "  picked = pick_mode  # Pick a file from the repository.\n"
    "  return picked, user_repository, url\n",
    encoding="utf-8",
  )
  md_file = tmp_path / "doc.md"
  md_file.write_text(
    "Use `pick_mode` and `github.repository` or `/repository/pick` in `user_repository`.\n"
    "Also skip snake_pick, $pick, cherry-pick, and ${{ github.repository }}.\n"
    "Pick a file from the repository.\n",
    encoding="utf-8",
  )
  id_res = run(str(py_file), str(md_file), cwd=tmp_path)
  assert id_res.returncode == 0, id_res.stderr
  assert f"{py_file}:8: [NMO901]" in id_res.stdout
  for safe_py_ln in (1, 3, 4, 6, 7, 9):
    assert f"{py_file}:{safe_py_ln}: [NMO901]" not in id_res.stdout
  assert f"{md_file}:3: [NMO901]" in id_res.stdout
  assert f"{md_file}:1: [NMO901]" not in id_res.stdout
  assert f"{md_file}:2: [NMO901]" not in id_res.stdout

  mixed_py = tmp_path / "mixed.py"
  mixed_py.write_text(
    "# The image ships the package, its config, the hooks, and the lock.\n"
    "# Keep the output in the cache directory after each build pass.\n"
    "x = 1\n",
    encoding="utf-8",
  )
  mixed_res = run(str(mixed_py), cwd=tmp_path)
  assert mixed_res.returncode == 0, mixed_res.stderr
  assert "NMO902" not in mixed_res.stdout

  slash_or = tmp_path / "slash_or.md"
  slash_or.write_text(
    "| Component / Property or Recipe | Reason |\n"
    "| --- | --- |\n"
    "| Button or Input / Select | Validated |\n"
    "| Component, Property, or Recipe | Consistent |\n"
    "| Component / Property / Recipe | Consistent |\n",
    encoding="utf-8",
  )
  slash_res = run(str(slash_or), cwd=tmp_path)
  assert slash_res.returncode == 1, slash_res.stderr
  assert f"{slash_or.name}:1: [NMO003]" in slash_res.stdout
  assert f"{slash_or.name}:3: [NMO003]" in slash_res.stdout
  assert f"{slash_or.name}:4:" not in slash_res.stdout
  assert f"{slash_or.name}:5:" not in slash_res.stdout


def test_sql_dbml_env_and_jinja_comment_extractors_and_ste903_guard(tmp_path):
  schema_sql = tmp_path / "schema.sql"
  schema_sql.write_text(
    "-- The service reads and writes rows.\n"
    "-- Start; stop.\n"
    "CREATE TABLE items (id INTEGER PRIMARY KEY, kind TEXT, repository TEXT);\n",
    encoding="utf-8",
  )
  schema_dbml = tmp_path / "schema.dbml"
  schema_dbml.write_text(
    "// The table is disabled and locked.\n"
    "// First clause; second clause.\n"
    "Table items {\n"
    "  id int [pk]\n"
    "  kind varchar\n"
    "}\n",
    encoding="utf-8",
  )
  env_example = tmp_path / ".env.example"
  env_example.write_text(
    "# Keep one token per line.\n"
    "# First token; second token.\n"
    "KIND=production\n"
    "REPOSITORY_URL=https://example.com\n",
    encoding="utf-8",
  )
  template_jinja = tmp_path / "view.jinja"
  template_jinja.write_text(
    "{# Render the card header. #}\n"
    "{# First part; second part. #}\n"
    "<div>{{ item.kind }}; {{ item.repository }}</div>\n",
    encoding="utf-8",
  )
  template_jinja_html = tmp_path / "card.jinja.html"
  template_jinja_html.write_text(
    "{# Name the source in the summary. #}\n"
    "<div>{{ item.kind }}; {{ item.name }}</div>\n",
    encoding="utf-8",
  )
  res = run(
    "--no-config",
    str(schema_sql),
    str(schema_dbml),
    str(env_example),
    str(template_jinja),
    str(template_jinja_html),
    cwd=tmp_path,
  )
  assert res.returncode == 1, res.stderr
  assert f"{schema_sql}:2: [STE100]" in res.stdout
  assert f"{schema_sql}:3:" not in res.stdout
  assert f"{schema_dbml}:2: [STE100]" in res.stdout
  assert f"{schema_dbml}:5:" not in res.stdout
  assert f"{env_example}:2: [STE100]" in res.stdout
  assert f"{env_example}:3:" not in res.stdout
  assert f"{template_jinja}:2: [STE100]" in res.stdout
  assert f"{template_jinja}:3:" not in res.stdout
  assert f"{template_jinja_html}:1: [NMO901]" in res.stdout
  assert f"{template_jinja_html}:2:" not in res.stdout
  assert "STE903" not in res.stdout
  assert "NMO100" not in res.stdout
  assert (
    nemoize.rotate(
      "- Name a relationship and the sheet names the single size, keeping role names."
    )
    == "- Specify a relationship and the sheet specifies the single size, keeping role names."
  )


def test_audit_includes_docs_drift(tmp_path):
  refs_dir = SCRIPT.parent.parent / "references"
  audit_template = (refs_dir / "audit-report.md").read_text(encoding="utf-8")
  skill_md = (SCRIPT.parent.parent / "SKILL.md").read_text(encoding="utf-8")
  assert "docs drift" in audit_template
  assert "docs-drift" in audit_template
  assert "docs drift" in skill_md

  existing = tmp_path / "existing.md"
  existing.write_text("# Existing\n", encoding="utf-8")
  doc = tmp_path / "README.md"
  doc.write_text(
    "Read [existing](existing.md), [anchor](#top), and [site](https://example.com).\n"
    "Read [missing](missing-guide.md).\n"
    "```markdown\n[ignored](not-a-real-file.md)\n```\n",
    encoding="utf-8",
  )
  audit_res = run("--audit", str(doc), cwd=tmp_path)
  assert audit_res.returncode == 0, audit_res.stderr
  assert "[docs-drift]" in audit_res.stdout
  assert "missing-guide.md" in audit_res.stdout
  assert "existing.md" not in audit_res.stdout
  assert "not-a-real-file.md" not in audit_res.stdout


def test_nmt100_taint_html_bytes_and_audit(tmp_path):
  # Acceptance test 1: HTML response variable binding
  t1 = tmp_path / "test_case1.py"
  t1.write_text(
    "def test_one(client):\n"
    '  opened = client.get("/?selected=1").data.decode()\n'
    '  assert "Back to the list" in opened\n',
    encoding="utf-8",
  )
  r1 = run(str(t1), cwd=tmp_path)
  assert r1.returncode == 1
  assert "[NMT100]" in r1.stdout

  t1_ok = tmp_path / "test_case1_ok.py"
  t1_ok.write_text(
    "def test_one_ok(client):\n"
    '  opened = client.get("/?selected=1").data.decode()\n'
    "  assert 'class=\"back-to-list\"' in opened\n",
    encoding="utf-8",
  )
  assert run(str(t1_ok), cwd=tmp_path).returncode == 0

  # Acceptance test 2: HTML-wrapped UI subtitle
  t2 = tmp_path / "test_case2.py"
  t2.write_text(
    "def test_two(admin):\n"
    '  body = admin.get("/settings").data.decode()\n'
    "  assert '<span class=\"set-sub\">System follows your device</span>' in body\n",
    encoding="utf-8",
  )
  r2 = run(str(t2), cwd=tmp_path)
  assert r2.returncode == 1
  assert "[NMT100]" in r2.stdout

  t2_ok = tmp_path / "test_case2_ok.py"
  t2_ok.write_text(
    "def test_two_ok(admin):\n"
    '  body = admin.get("/settings").data.decode()\n'
    "  assert 'aria-label=\"Theme\"' in body\n",
    encoding="utf-8",
  )
  assert run(str(t2_ok), cwd=tmp_path).returncode == 0

  # Acceptance test 3: Tuple-unpacked E2E response and bytes flash
  t3 = tmp_path / "test_case3.py"
  t3.write_text(
    "def test_three(guest, link, saved):\n"
    "  status, _, body = guest(link)\n"
    '  assert "This link no longer works" in body\n'
    '  assert b"Username saved." in saved.data\n',
    encoding="utf-8",
  )
  r3 = run(str(t3), cwd=tmp_path)
  assert r3.returncode == 1
  assert r3.stdout.count("[NMT100]") == 2

  # Acceptance test 4: Domain-model state and CSS rules
  t4 = tmp_path / "test_case4.py"
  t4.write_text(
    "def test_four(loaded, css):\n"
    '  assert loaded.title == "Fix the tap"\n'
    '  assert "grid-template-columns: minmax(0, 1fr);" in css\n',
    encoding="utf-8",
  )
  r4 = run(str(t4), cwd=tmp_path)
  assert r4.returncode == 0
  assert r4.stdout.strip() == ""

  # Piece 2: --audit reports NMT100 and per-file-ignores rejects NMT100 on test globs
  audit_t3 = run("--audit", str(t3), cwd=tmp_path)
  assert audit_t3.returncode == 0
  assert "[NMT100]" in audit_t3.stdout

  bad_cfg = tmp_path / "nemoizer.toml"
  bad_cfg.write_text(
    '[lint.per-file-ignores]\n"tests/**" = ["NMT100"]\n',
    encoding="utf-8",
  )
  bad_res = run("--config", str(bad_cfg), str(t4), cwd=tmp_path)
  assert bad_res.returncode == 2
  assert "NMT100" in bad_res.stderr


def test_nmu100_padded_ui_labels_and_cap_config(tmp_path):
  ui_dir = tmp_path / "ui" / "static"
  ui_dir.mkdir(parents=True)
  page = ui_dir / "index.html"
  page.write_text(
    "<!doctype html>\n"
    '<button title="Open the repo">Open</button>\n'
    '<button aria-label="Remove this repo">Remove</button>\n'
    '<button title="Delete this arena branch on origin">Delete</button>\n'
    "<p>Open the repo from this list.</p>\n"
    "<script>\n"
    'const item = { label: "Add a path to remove" };\n'
    'btn.title = "Stops this run";\n'
    'const tpl = { "aria-label": `Show the ${p.name} steps` };\n'
    "</script>\n",
    encoding="utf-8",
  )
  r1 = run(str(page), cwd=tmp_path)
  assert r1.returncode == 1, r1.stderr
  assert r1.stdout.count("[NMU100]") == 5
  expected = nemoize.describe_finding(
    {
      "rule": "NMU100",
      "text": "Open the repo",
      "word": "the",
      "count": 3,
      "cap": 6,
    }
  )
  assert f"[NMU100] (advisory-free) {expected}" in r1.stdout

  # Acceptance test 2: terse rewrites pass with exit code 0
  page.write_text(
    "<!doctype html>\n"
    '<button title="Open repo">Open</button>\n'
    '<button aria-label="Remove repo">Remove</button>\n'
    '<button title="Delete arena branch on origin">Delete</button>\n'
    "<script>\n"
    'const item = { label: "Add path to remove" };\n'
    'btn.title = "Stop run";\n'
    'const tpl = { "aria-label": `Show the ${p.name} steps` };\n'
    "</script>\n",
    encoding="utf-8",
  )
  r2 = run(str(page), cwd=tmp_path)
  assert r2.returncode == 0, r2.stderr
  assert "[NMU100]" not in r2.stdout

  # Acceptance test 3: sentence-ending tooltips stay silent
  sentence_js = ui_dir / "tooltip.js"
  sentence_js.write_text(
    'btn.title = "Pushes even when the PR still has running or failing checks.";\n'
    'btn.placeholder = "Stops here.";\n',
    encoding="utf-8",
  )
  r3 = run(str(sentence_js), cwd=tmp_path)
  assert r3.returncode == 0, r3.stderr
  assert "[NMU100]" not in r3.stdout

  # Acceptance test 4: nmu100_max_words = 3 under [tool.nemoizer.lint]
  pyproject = tmp_path / "pyproject.toml"
  pyproject.write_text(
    "[tool.nemoizer.lint]\nnmu100_max_words = 3\n",
    encoding="utf-8",
  )
  cap_js = ui_dir / "cap.js"
  cap_js.write_text(
    "const a = {}, b = {}, c = {};\n"
    'a.title = "Open the lint run";\n'
    'b.title = "Open the repo";\n'
    'c.title = "Stop this"; // nonemo: NMU100\n',
    encoding="utf-8",
  )
  r4 = run(str(cap_js), cwd=tmp_path)
  assert r4.returncode == 1, r4.stderr
  assert r4.stdout.count("[NMU100]") == 1
  expected_cap = nemoize.describe_finding(
    {
      "rule": "NMU100",
      "text": "Open the repo",
      "word": "the",
      "count": 3,
      "cap": 3,
    }
  )
  assert f"[NMU100] (advisory-free) {expected_cap}" in r4.stdout


def test_js_ui_prose_checks_run_beyond_nmu100_word_cap(tmp_path):
  ui_js = tmp_path / "ui.js"
  ui_js.write_text(
    'status.textContent = "Draft retained; check the log before resending.";\n'
    "panel.textContent = `Preview failed: ${error.message}; sending still works.`;\n"
    'btn.title = "Clipboard blocked; select code and copy it";\n',
    encoding="utf-8",
  )
  bad = run(str(ui_js), cwd=tmp_path)
  assert bad.returncode == 1, bad.stderr
  assert bad.stdout.count("[STE100]") == 3

  ui_js.write_text(
    'status.textContent = "Draft retained. Check the log before resending.";\n'
    "panel.textContent = `Preview failed: ${error.message}. Sending still works.`;\n"
    'btn.title = "Clipboard blocked. Select code and copy it";\n',
    encoding="utf-8",
  )
  clean = run(str(ui_js), cwd=tmp_path)
  assert clean.returncode == 0, clean.stderr
