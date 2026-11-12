"""nemoizer command-line behavior tests."""

import subprocess
import sys
from pathlib import Path

import config
import files
import nemoize
import prose.review
import prose.rotate
import pytest
import report
from conftest import copy_shipped_scripts, run


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
    prose.rotate.rotate("Open a pull request and merge Pull Requests.")
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


def test_default_javascript_test_scope_uses_declarations_not_string_examples(tmp_path):
  app = tmp_path / "app.js"
  app.write_text(
    'const example = "from \'node:test\'"; assert.equal(result.stdout, "Saved the report.");\n',
    encoding="utf-8",
  )
  assert run(cwd=tmp_path).returncode == 0
  suite = tmp_path / "suite.js"
  suite.write_text(
    'const { test } = require("node:test"); '
    'test("status", () => { assert.equal(result.stdout, "Saved the report."); });\n',
    encoding="utf-8",
  )
  result = run(cwd=tmp_path)
  assert result.returncode == 1, result.stderr
  assert "suite.js:1: [NMT100]" in result.stdout  # nonemo: NMT100
  assert "app.js:1: [NMT100]" not in result.stdout  # nonemo: NMT100


def test_default_test_scope_excludes_imported_production_files(tmp_path):
  (tmp_path / "app.py").write_text(
    'assert result.stdout == "Saved the report."\n', encoding="utf-8"
  )
  (tmp_path / "test_status.py").write_text(
    'import app\nassert result.stdout == "Saved the report."\n', encoding="utf-8"
  )
  result = run(cwd=tmp_path)
  assert result.returncode == 1, result.stderr
  assert "test_status.py:2: [NMT100]" in result.stdout  # nonemo: NMT100
  assert "app.py:1: [NMT100]" not in result.stdout  # nonemo: NMT100


def test_default_test_scope_uses_configured_patterns_and_explicit_helpers(tmp_path):
  (tmp_path / "pytest.ini").write_text(
    "[pytest]\ntestpaths = specs\npython_files = scenario_*.py\n", encoding="utf-8"
  )
  specs = tmp_path / "specs"
  specs.mkdir()
  (specs / "scenario_status.py").write_text(
    'assert result.stdout == "Saved the report."\n', encoding="utf-8"
  )
  helper = tmp_path / "helper.py"
  helper.write_text('assert result.stdout == "Saved the report."\n', encoding="utf-8")
  result = run(cwd=tmp_path)
  assert result.returncode == 1, result.stderr
  assert "scenario_status.py:1: [NMT100]" in result.stdout  # nonemo: NMT100
  assert "helper.py:1: [NMT100]" not in result.stdout  # nonemo: NMT100
  explicit = run("--test-helper", str(helper), cwd=tmp_path)
  assert explicit.returncode == 1, explicit.stderr
  assert "helper.py:1: [NMT100]" in explicit.stdout  # nonemo: NMT100


def test_explicit_prose_mode_uses_shared_source_extraction(tmp_path):
  import json

  sentence = " ".join(["term"] * (config.SENTENCE_CAPS["instruction"] + 1)) + "."
  source = tmp_path / "example.py"
  source.write_text(f'value = "{sentence}"\n', encoding="utf-8")
  result = run("prose", str(source), cwd=tmp_path)
  assert result.returncode == 0, result.stderr
  source.write_text(f'value = "{sentence}"\n# {sentence}\n', encoding="utf-8")
  result = run("prose", str(source), cwd=tmp_path)
  assert result.returncode == 1, result.stderr
  assert {row["line"] for row in json.loads(result.stdout)["findings"]} == {2}


def test_explicit_prose_reports_parser_runtime_failures(tmp_path, monkeypatch, capsys):
  import json

  source = tmp_path / "example.py"
  source.write_text('"""Short."""\n', encoding="utf-8")
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


def test_format_keeps_each_file_line_ending_bytes(tmp_path):
  crlf = tmp_path / "crlf.md"
  crlf.write_bytes(b"kind one\r\nkind two\r\n")
  lf = tmp_path / "lf.md"
  lf.write_bytes(b"kind one\nkind two\n")
  assert prose.review.format_paths([crlf, lf], []) == 4
  assert crlf.read_bytes() == b"type one\r\ntype two\r\n"
  assert lf.read_bytes() == b"type one\ntype two\n"


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


def test_missing_targets_fail_before_scanning_or_formatting(tmp_path):
  note = tmp_path / "note.md"
  original = "Transmit this.\n"
  note.write_text(original, encoding="utf-8")
  missing = tmp_path / "missing.md"
  for arguments in (
    ("--no-config", str(missing)),
    ("--format", str(note), str(missing)),
  ):
    result = run(*arguments, cwd=tmp_path)
    assert result.returncode == 2
    assert f"target does not exist: {missing}" in result.stderr
    assert note.read_text(encoding="utf-8") == original
  with pytest.raises(ValueError, match="target does not exist"):
    list(files.walk([missing], ()))


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
  heading_msg = report.describe_finding(
    {"rule": "NMP100", "count": 2, "cap": 1, "kind": "heading"}
  )
  list_msg = report.describe_finding(
    {"rule": "NMP100", "count": 3, "cap": 2, "kind": "list"}
  )
  table_msg = report.describe_finding(
    {"rule": "NMP100", "count": 5, "cap": 4, "kind": "table"}
  )
  quote_msg = report.describe_finding(
    {"rule": "NMP100", "count": 5, "cap": 4, "kind": "blockquote"}
  )
  assert f"[NMP100] (violation) {heading_msg}" in res.stdout
  assert f"[NMP100] (violation) {list_msg}" in res.stdout
  assert f"[NMP100] (violation) {table_msg}" in res.stdout
  assert f"[NMP100] (review) {quote_msg}" in res.stdout

  quote_only = tmp_path / "quote.md"
  quote_only.write_text(
    "# Single sentence heading\n\n"
    "- Item one. Item two.\n\n"
    "> One. Two. Three. Four. Five.\n",
    encoding="utf-8",
  )
  quote_res = run(str(quote_only), cwd=tmp_path)
  assert quote_res.returncode == 0, quote_res.stderr
  assert f"[NMP100] (review) {quote_msg}" in quote_res.stdout
  audit_res = run("--audit", str(quote_only), cwd=tmp_path)
  assert audit_res.returncode == 0, audit_res.stderr
  assert f"[NMP100] (review) {quote_msg}" in audit_res.stdout


def test_prose_extract_package_ships_javascript_parser(tmp_path):
  from prose.extract import javascript_comment_spans, javascript_comments

  source = "// comment line\ncode;\n"
  comments = list(javascript_comments(source))
  assert comments == [("comment line", 1, 1)]
  spans = list(javascript_comment_spans(source))
  assert spans[0][0] == (1, 0) and spans[0][1] == (1, 15)

  portable = tmp_path / "portable"
  copy_shipped_scripts(portable / "scripts")
  test_md = portable / "test.md"
  test_md.write_text("transmit the report.\n", encoding="utf-8")
  for entry in ("nemoize.py", "nemoizer"):
    result = subprocess.run(
      [sys.executable, str(portable / "scripts" / entry), str(test_md)],
      capture_output=True,
      text=True,
      encoding="utf-8",
      check=False,
      cwd=tmp_path,
    )
    assert result.returncode == 1, result.stderr
    assert "[NMO100]" in result.stdout
    assert "transmit -> send" in result.stdout


def test_unreadable_detected_test_is_not_silently_checked(tmp_path):
  source = tmp_path / "test_bytes.py"
  content = b"\xff"
  source.write_bytes(content)
  result = run(cwd=tmp_path)
  assert result.returncode == 2
  assert str(source) in result.stderr or source.name in result.stderr
  assert "unreadable_or_non_text" in result.stderr
  assert source.read_bytes() == content


def test_verbose_logs_scan_and_worker_progress(tmp_path):
  note = tmp_path / "note.md"
  note.write_text("Short.\n", encoding="utf-8")
  quiet = run(str(note), cwd=tmp_path)
  assert quiet.returncode == 0
  for phase in ("scan", "start", "done"):
    assert f"{phase} {note}" not in quiet.stderr
  for flag in ("-v", "--verbose"):
    result = run(flag, str(note), cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert f"scan {note}" in result.stderr
    assert f"start {note}" in result.stderr
    assert f"done {note}" in result.stderr
