"""nemoizer marker and exclusion tests."""

import subprocess
import sys
from pathlib import Path

import prose.review
from conftest import SCRIPT, run


def test_a_line_marker_skips_that_line_and_a_head_marker_skips_the_file():
  import tempfile

  with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    (root / "marked.py").write_text(
      "value = 'kind'  # nonemo: NMO100\n# names the tool\n", encoding="utf-8"
    )
    (root / "whole.md").write_text(
      "<!-- nonemo: NMO100 -->\nkind and names the tool stay\n", encoding="utf-8"
    )
    result = run(cwd=directory)
    assert "marked.py:1:" not in result.stdout
    assert "marked.py:2: [NMO901] (review) names -> specify" in result.stdout
    assert "whole.md:2: [NMO901] (review) names -> specify" in result.stdout
    assert "whole.md:2: [NMO100] (violation) kind -> type" not in result.stdout
    listing = run("--ignores", cwd=directory)
    assert listing.returncode == 0
    assert "marked.py:1:" in listing.stdout
    assert "whole.md:1:" in listing.stdout


def test_audit_markers_skip_inline_code_and_test_fixture_strings(tmp_path):
  note = tmp_path / "note.md"
  note.write_text(
    "Use `nonemo: NMO100` or ``nonemo: NMO901``.\n<!-- nonemo: NMO100 -->\n",
    encoding="utf-8",
  )
  python_fixture = tmp_path / "test_fixture.py"
  python_fixture.write_text(
    'TEXT = """fixture\nnonemo: NMO100\nend"""\nvalue = "kind"  # nonemo: NMO100\n',
    encoding="utf-8",
  )
  javascript_fixture = tmp_path / "sample.test.cjs"
  javascript_fixture.write_text(
    'const text = "nonemo: NMO100"; // nonemo: NMO901\n'
    "const pattern = /nonemo:\\s*NMO100/;\n"
    "// nonemo: NMO100\n",
    encoding="utf-8",
  )
  _, raw_marks = prose.review.scan([tmp_path], [])
  _, audit_marks = prose.review.scan([tmp_path], [], audit=True)
  assert any(mark.startswith(f"{note}:1:") for mark in raw_marks)
  assert any(mark.startswith(f"{python_fixture}:2:") for mark in raw_marks)
  assert any(mark.startswith(f"{javascript_fixture}:1:") for mark in raw_marks)
  assert any(mark.startswith(f"{javascript_fixture}:2:") for mark in raw_marks)
  assert not any(mark.startswith(f"{note}:1:") for mark in audit_marks)
  assert not any(mark.startswith(f"{python_fixture}:2:") for mark in audit_marks)
  javascript_line_one = [
    mark for mark in audit_marks if mark.startswith(f"{javascript_fixture}:1:")
  ]
  assert len(javascript_line_one) == 1
  assert javascript_line_one[0].startswith(f"{javascript_fixture}:1: NMO901 ")
  assert not any(mark.startswith(f"{javascript_fixture}:2:") for mark in audit_marks)
  assert any(mark.startswith(f"{note}:2: NMO100 file:") for mark in audit_marks)
  assert any(
    mark.startswith(f"{python_fixture}:4: NMO100 line:") for mark in audit_marks
  )
  assert any(
    mark.startswith(f"{javascript_fixture}:3: NMO100 file:") for mark in audit_marks
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
      encoding="utf-8",
      check=False,
    )
    assert result.returncode == 0, result.stderr
    expected_markers = note.read_text(encoding="utf-8").count("nonemo:")
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
    content = "names kind # nonemo: NMO901 # nonemo: NMO100\nkind # nonemo: kind\n"
    note.write_text(content, encoding="utf-8")
    result = run(cwd=directory)
    assert "note.md:1:" not in result.stdout
    assert "note.md:2: [NMO100] (violation) kind -> type" in result.stdout
    formatted = run("--format", cwd=directory)
    assert formatted.returncode == 0
    assert (
      note.read_text(encoding="utf-8")
      == "names kind # nonemo: NMO901 # nonemo: NMO100\ntype # nonemo: kind\n"
    )


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
  assert "config.jsonc:2: [NMO100] (violation) Transmit -> send" in jsonc_result.stdout
  assert "kind" not in jsonc_result.stdout
  assert "repository" not in jsonc_result.stdout

  audit = subprocess.run(
    [sys.executable, str(SCRIPT.with_name("nemoizer")), "audit", str(note)],
    cwd=tmp_path,
    capture_output=True,
    text=True,
    encoding="utf-8",
    check=False,
  )
  collect_alias = subprocess.run(
    [sys.executable, str(SCRIPT.with_name("nemoizer")), "collect", str(note)],
    cwd=tmp_path,
    capture_output=True,
    text=True,
    encoding="utf-8",
    check=False,
  )
  assert audit.returncode == 0, audit.stderr
  assert collect_alias.returncode == 0, collect_alias.stderr
  assert collect_alias.stdout == audit.stdout
  assert "HMN910 line:" in audit.stdout
  assert "STE904" in audit.stdout
  assert "STE001" not in audit.stdout
  assert markers.main([str(note)]) == 0
