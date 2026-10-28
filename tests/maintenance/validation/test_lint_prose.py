"""Tests for code-comment prose coverage."""

import json
import subprocess
import sys
from pathlib import Path

import extract_prose
import lint_prose


def test_repository_soft_rotation_does_not_fail(tmp_path, capsys):
  source = tmp_path / "note.md"
  source.write_text("Pick one.\n")
  assert lint_prose.nemoizer_main([str(source)]) == 0
  output = capsys.readouterr().out
  assert "NMO901" in output and "manual review" in output
  source.write_text("Pick this kind.\n")  # nonemo: NMO100
  assert lint_prose.nemoizer_main([str(source)]) == 1


def test_userscript_sections_skip_metadata_and_keep_code_comments():
  source = """// ==UserScript==
// @name Example
// ==/UserScript==

// Prepare the state.
const url = "https://example.test";
// Write the state.
"""

  assert extract_prose.source_sections(Path("userscripts/example.user.js"), source) == [
    "Prepare the state.",
    "Write the state.",
  ]


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


def test_source_sections_skip_strings_and_userscript_metadata():
  source = """// ==UserScript==
// @name Example
// ==/UserScript==
const url = "https://example.test";
// Set the URL.
/* Read the state. */
"""

  assert extract_prose.source_sections(Path("userscripts/example.user.js"), source) == [
    "Set the URL.",
    "Read the state.",
  ]


def test_source_sections_read_hash_comments_outside_strings():
  source = """name: "#not-a-comment" # Read the name.
# Set the name.
"""

  assert extract_prose.source_sections(Path("example.yml"), source) == [
    "Read the name.",
    "Set the name.",
  ]


def test_lint_keeps_advisory_findings_non_blocking_and_fails_hard_findings():
  assert lint_prose.lint("example", "The state was saved.") == 0
  assert lint_prose.lint("example", "The state was saved.", strict=True) == 0
  assert (
    lint_prose.lint("example", "Read the state; write the state.", strict=True) == 1
  )


def test_lint_accepts_adr_references_and_three_line_comment_blocks(
  tmp_path, monkeypatch
):
  source = tmp_path / "example.py"
  source.write_text("# Read ADR-1.\n# Read the state.\n# Write the state.\n")
  monkeypatch.setattr(
    lint_prose,
    "extract_files",
    lambda: {str(source): ["Read ADR-1.", "Read the state.", "Write the state."]},
    raising=False,
  )
  monkeypatch.setattr(lint_prose, "markdown_targets", list)
  assert lint_prose.main() == 0
  assert lint_prose.lint("example.py", "Read ADR-1.") == 0
  assert lint_prose.strict_lint("example.py", ["Read ADR-1."]) == 0


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


def test_strict_lint_accepts_synonyms_without_rotation_report(capsys):
  assert (
    lint_prose.strict_lint("example", ["Check the state.", "Validate the state."]) == 0
  )
  assert lint_prose.strict_lint("example", ["Check and validate the state."]) == 0
  assert "synonym-rotation" not in capsys.readouterr().out
  assert lint_prose.strict_lint("example", ["Read the state; write the state."]) == 1


def test_strict_lint_keeps_passive_findings_advisory(capsys):
  assert lint_prose.strict_lint("passive.py", ["The state was saved."]) == 0
  assert "STE901" in capsys.readouterr().out


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


def test_linter_consumes_grouped_extractor_output(tmp_path, monkeypatch, capsys):
  source = tmp_path / "example.py"
  source.write_text("# Read the state.\n")
  monkeypatch.setattr(
    lint_prose,
    "extract_files",
    lambda: {str(source): ["Check the state.", "Validate the state."]},
    raising=False,
  )
  monkeypatch.setattr(lint_prose, "markdown_targets", list)
  assert lint_prose.main() == 0
  assert "synonym-rotation" not in capsys.readouterr().out
  monkeypatch.setattr(
    lint_prose,
    "extract_files",
    lambda: {str(source): ["Read the state; write the state."]},
    raising=False,
  )
  assert lint_prose.main() == 1


def test_javascript_regexes_keep_later_comments():
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


def test_repository_scope_exempts_agent_sources_including_metadata():
  source = "---\nname: example\ndescription: Keep the invocation clause unchanged.\n---\n\nKeep the body unchanged.\n"
  for name in (
    "skills/example/SKILL.md",
    "AGENTS.md",
    "ARENA.md",
    "rules/CORE.md",
    "system-prompts/test.md",
    "automations/test.md",
    "workflows/test.md",
    "skills/example/references/rules.md",
    "rules/refs/GUIDELINES.md",
    "example.py",
  ):
    context, scoped = lint_prose.nemoizer_scope(Path(name), source)
    assert context == "unknown"
    assert not scoped


def test_repository_scope_classifies_only_human_documentation():
  source = "The tool checks the saved state."
  for name in (
    "README.md",
    "skills/example/README.md",
    "INSTALL.md",
    "CHANGELOG.md",
    "docs/history.md",
  ):
    context, scoped = lint_prose.nemoizer_scope(Path(name), source)
    assert context == "description"
    assert scoped == source
  context, scoped = lint_prose.nemoizer_scope(Path("unknown.txt"), source)
  assert context == "unknown"
  assert not scoped
