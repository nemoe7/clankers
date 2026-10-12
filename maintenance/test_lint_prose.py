"""Tests for userscript prose coverage."""

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
