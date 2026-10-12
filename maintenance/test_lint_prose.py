"""Tests for code-comment prose coverage."""

from pathlib import Path

import lint_prose


def test_userscript_prose_skips_metadata_and_keeps_code_comments():
  source = """// ==UserScript==
// @name Example
// ==/UserScript==

// Prepare the state.
const url = "https://example.test";
// Write the state.
"""

  assert lint_prose.userscript_prose(source) == "Prepare the state.\nWrite the state."


def test_userscript_metadata_sections_collect_required_prose():
  source = """// ==UserScript==
// @name Example utility
// @description Hide panels.
// @version 1.0.0
// ==/UserScript==
"""

  assert lint_prose.userscript_metadata_sections(source) == [
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

  assert lint_prose.source_prose(Path("userscripts/example.user.js"), source) == (
    "Set the URL.\nRead the state."
  )


def test_source_prose_reads_hash_comments_outside_strings():
  source = """name: "#not-a-comment" # Read the name.
# Set the name.
"""

  assert (
    lint_prose.source_prose(Path("example.yml"), source)
    == "Read the name.\nSet the name."
  )


def test_lint_fails_advisory_findings_in_strict_mode():
  assert lint_prose.lint("example", "The state was saved.", False) == 0
  assert lint_prose.lint("example", "The state was saved.", False, strict=True) == 1


def test_code_targets_skip_vendored_content():
  targets = lint_prose.code_targets()

  assert Path("maintenance/lint_prose.py") in targets
  assert Path(".agents/skills/asd-ste100/scripts/ste-lint.py") not in targets


def test_vendored_agent_skills_stay_out_of_code_targets():
  assert lint_prose.is_vendored(Path(".agents/skills/ponytail/scripts/example.py"))
  assert not lint_prose.is_vendored(
    Path(".agents/skills/arena-skill/scripts/preview.py")
  )


def test_strict_lint_checks_comment_sections_individually():
  assert (
    lint_prose.strict_lint(
      "example", ["Check the state.", "Validate the state."], False
    )
    == 0
  )
  assert (
    lint_prose.strict_lint("example", ["Check and validate the state."], False) == 1
  )
