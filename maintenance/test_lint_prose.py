"""Tests for code-comment prose coverage."""

import json
import subprocess
import sys
from pathlib import Path

import extract_prose
import lint_prose


def test_userscript_prose_skips_metadata_and_keeps_code_comments():
  source = """// ==UserScript==
// @name Example
// ==/UserScript==

// Prepare the state.
const url = "https://example.test";
// Write the state.
"""

  assert (
    extract_prose.userscript_prose(source) == "Prepare the state.\nWrite the state."
  )


def test_userscript_metadata_sections_collect_required_prose():
  source = """// ==UserScript==
// @name Example utility
// @description Hide panels.
// @version 1.0.0
// ==/UserScript==
"""

  assert extract_prose.userscript_metadata_sections(source) == [
    "Example utility",
    "Hide panels.",
  ]


def test_userscript_comment_blocks_exempt_only_metadata():
  source = """// ==UserScript==
// @name Example
// ==/UserScript==

// Prepare the state.
//
// Read the state.
"""

  assert lint_prose.userscript_comment_block_violations(
    "userscripts/example.user.js", source
  ) == ["userscripts/example.user.js:5: comment block has 3 lines; the cap is 2"]


def test_comment_blocks_cap_all_code_types():
  source = """// Prepare the state.
// Read the state.
// Write the state.
const url = "https://example.test";
"""

  assert lint_prose.comment_block_violations(Path("example.js"), source) == [
    "example.js:1: comment block has 3 lines; the cap is 2"
  ]


def test_comment_blocks_exempt_required_directive_markers():
  source = """# arena-preview-path
# Pin the root at install time.
# A source lookup could miss the command.
"""

  assert lint_prose.comment_block_violations(Path("install.sh"), source) == []


def test_source_prose_skips_strings_and_userscript_metadata():
  source = """// ==UserScript==
// @name Example
// ==/UserScript==
const url = "https://example.test";
// Set the URL.
/* Read the state. */
"""

  assert extract_prose.source_prose(Path("userscripts/example.user.js"), source) == (
    "Set the URL.\nRead the state."
  )


def test_source_prose_reads_hash_comments_outside_strings():
  source = """name: "#not-a-comment" # Read the name.
# Set the name.
"""

  assert (
    extract_prose.source_prose(Path("example.yml"), source)
    == "Read the name.\nSet the name."
  )


def test_lint_fails_advisory_findings_in_strict_mode():
  assert lint_prose.lint("example", "The state was saved.", False) == 0
  assert lint_prose.lint("example", "The state was saved.", False, strict=True) == 1


def test_code_targets_skip_vendored_content():
  targets = extract_prose.code_targets()

  assert Path("maintenance/lint_prose.py") in targets
  assert Path(".agents/skills/asd-ste100/scripts/ste-lint.py") not in targets


def test_vendored_agent_skills_stay_out_of_code_targets():
  assert extract_prose.is_vendored(Path(".agents/skills/ponytail/scripts/example.py"))
  assert not extract_prose.is_vendored(
    Path(".agents/skills/arena-skill/scripts/preview.py")
  )


def test_markdown_bundle_is_vendored_without_excluding_first_party_assets():
  for root in (
    Path("skills/refs/arena-skill"),
    Path("skills/arena-skill"),
    Path(".agents/skills/arena-skill"),
  ):
    assert extract_prose.is_vendored(root / "assets/markdown-it.min.js")
    assert not extract_prose.is_vendored(root / "assets/app.js")
    assert not extract_prose.is_vendored(root / "assets/message-markdown.js")


def test_strict_lint_checks_synonyms_across_sections():
  assert (
    lint_prose.strict_lint(
      "example", ["Check the state.", "Validate the state."], False
    )
    == 1
  )
  assert (
    lint_prose.strict_lint("example", ["Check and validate the state."], False) == 1
  )


def test_file_synonyms_use_only_extracted_prose():
  source = '# Check the state.\ndef validate_state():\n  return "Validate the state."'
  sections = extract_prose.source_sections(Path("example.py"), source)
  assert lint_prose.strict_lint("example.py", sections, False) == 0
  assert lint_prose.strict_lint("first.py", ["Check the state."], False) == 0
  assert lint_prose.strict_lint("second.py", ["Validate the state."], False) == 0
  assert lint_prose.strict_lint("passive.py", ["The state was saved."], False) == 1


def test_extract_prose_cli_groups_comments_and_docstrings(tmp_path):
  first = tmp_path / "first.py"
  first.write_text(
    '"""Check the state."""\nordinary = "Do not collect this string"\n# Read the state.\n'
  )
  second = tmp_path / "second.js"
  second.write_text(
    'const ordinary = "Do not collect this string";\n// Write the state.\n'
  )
  script = Path(lint_prose.__file__).with_name("extract_prose.py")
  result = subprocess.run(
    [sys.executable, str(script), str(first), str(second)],
    capture_output=True,
    text=True,
    check=False,
  )
  assert result.returncode == 0, result.stderr
  assert json.loads(result.stdout) == {
    str(first): ["Check the state.", "Read the state."],
    str(second): ["Write the state."],
  }


def test_linter_consumes_grouped_extractor_output(tmp_path, monkeypatch):
  source = tmp_path / "example.py"
  source.write_text("# Read the state.\n")
  monkeypatch.setattr(
    lint_prose,
    "extract_files",
    lambda: {str(source): ["Check the state.", "Validate the state."]},
    raising=False,
  )
  monkeypatch.setattr(lint_prose, "markdown_targets", list)
  assert lint_prose.main() == 1


def test_javascript_regexes_keep_later_comments_and_line_caps():
  for prefix in (
    'const pattern = /"/;\n',
    "const pattern = /[/*`]/;\n",
    "const value = total / count / scale;\n",
  ):
    source = prefix + "// Read the state.\n// Write the state.\n// Reset the state.\n"
    assert extract_prose.source_sections(Path("example.js"), source) == [
      "Read the state.",
      "Write the state.",
      "Reset the state.",
    ]
    assert lint_prose.comment_block_violations(Path("example.js"), source) == [
      "example.js:2: comment block has 3 lines; the cap is 2"
    ]


def test_javascript_template_expressions_keep_real_comments():
  source = 'const value = `text ${ /"/.test(value) /* Read the state. */ }`;\n'
  source += "// Write the state.\n"
  assert extract_prose.source_sections(Path("example.js"), source) == [
    "Read the state.",
    "Write the state.",
  ]


def test_javascript_script_fallback_keeps_comments_once_and_skips_hashbang():
  source = (
    "#!/usr/bin/env node\n// Read the state.\nwith (state) { /* Write the state. */ }\n"
  )
  for suffix in (".js", ".cjs"):
    path = Path("example" + suffix)
    assert extract_prose.source_sections(path, source) == [
      "Read the state.",
      "Write the state.",
    ]
    assert extract_prose.comment_lines(path, source) == {2, 3}


def test_css_and_jsonc_keep_their_comment_scanner():
  for name, source in (
    ("example.css", "a { color: #fff; } /* Read the state. */"),
    ("example.jsonc", '{"name": "value", /* Read the state. */ "enabled": true}'),
  ):
    assert extract_prose.source_sections(Path(name), source) == ["Read the state."]
