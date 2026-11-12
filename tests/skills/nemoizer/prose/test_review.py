"""nemoizer prose review tests."""

import tomllib

import config
import prose.detectors
import prose.review
import report
from conftest import SCRIPT, run

import rules


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
    f"{cmd}:3: [STE100] (violation) {rules.RULE_DESCRIPTIONS['STE100']}"
    in result.stdout
  )
  assert f"{cmd}:2:" not in result.stdout
  assert f"{cmd}:4:" not in result.stdout


def test_default_prose_scan_reports_parse_errors(tmp_path):
  source = tmp_path / "broken.py"
  source.write_text("def unfinished(\n", encoding="utf-8")
  result = run(cwd=tmp_path)
  assert result.returncode == 2
  assert str(source) in result.stderr or source.name in result.stderr


def test_default_scan_checks_semicolon_sentence_and_paragraph_caps(tmp_path):
  sentence = " ".join(["term"] * (config.SENTENCE_CAPS["instruction"] + 1)) + "."
  source = tmp_path / "note.md"
  source.write_text(
    sentence + "\n\n" + "Short. " * (config.PARAGRAPH_CAP + 1) + "\n\nFirst; second.\n",
    encoding="utf-8",
  )
  result = run(cwd=tmp_path)
  assert result.returncode == 1, result.stderr
  assert (
    f"note.md:1: [STE200] (violation) {report.describe_finding({'rule': 'STE200', 'count': 21, 'cap': 20})}"
    in result.stdout
  )
  assert (
    f"note.md:3: [NMP100] (violation) {report.describe_finding({'rule': 'NMP100', 'count': 5, 'cap': 4})}"
    in result.stdout
  )
  assert (
    f"note.md:5: [STE100] (violation) {rules.RULE_DESCRIPTIONS['STE100']}"
    in result.stdout
  )
  description = run("--context", "description", cwd=tmp_path)
  assert description.returncode == 1, description.stderr
  assert "STE200" not in description.stdout
  assert "NMP100" in description.stdout and "STE100" in description.stdout
  code_file = tmp_path / "app.py"
  code_file.write_text(
    "# Line one.\n# Line two.\n# Line three.\nx = 1\n", encoding="utf-8"
  )
  comment_res = run(str(code_file), cwd=tmp_path)
  assert comment_res.returncode == 1, comment_res.stderr
  assert (
    f"{code_file}:1: [NMP101] (violation) {report.describe_finding({'rule': 'NMP101', 'count': 3, 'cap': 2})}"
    in comment_res.stdout
  )


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
  assert prose.detectors.prose_the_density(wrapped) == [(1, 1, 33), (4, 1, 33)]
  assert prose.detectors.prose_repeated_openers(wrapped) == [(4, 1, 1)]
  assert [row[0] for row in prose.detectors.prose_wordy_phrases(wrapped)] == [8]
  assert [row[0] for row in prose.detectors.prose_serial_commas(wrapped)] == [8]
  assert [row[0] for row in prose.detectors.prose_self_narration(wrapped)] == [12]

  doc = tmp_path / "wrapped.md"
  doc.write_text(
    "Check the source, the target,\nand the unit for the worker.\n",
    encoding="utf-8",
  )
  assert prose.review.format_paths([doc], []) == 1
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
    for row in prose.review.source_prose(
      html_doc, html_doc.read_text(encoding="utf-8"), "instruction", 4
    )
  ]
  assert (4, "STE100") in html_rows
  assert (5, "STE100") in html_rows
  assert not any(line in {2, 3} for line, _ in html_rows)

  pyproject_toml = SCRIPT.parent.parent / "pyproject.toml"
  assert pyproject_toml.is_file()
  pyproject_data = tomllib.loads(pyproject_toml.read_text(encoding="utf-8"))
  assert pyproject_data["project"]["name"] == "nemoizer"
  assert pyproject_data["project"]["scripts"]["nemoizer"] == "nemoize:main"
  assert set(pyproject_data["tool"]["setuptools"]["py-modules"]) == {
    path.stem for path in SCRIPT.parent.glob("*.py")
  }
  assert pyproject_data["tool"]["setuptools"]["packages"] == ["prose"]
  assert "*.cjs" in pyproject_data["tool"]["setuptools"]["package-data"]["prose"]


def test_rotation_group_markers_and_removed_legacy_aliases(tmp_path):
  source = tmp_path / "note.md"
  source.write_text(
    "kind names the tool and transmit # nonemo: NMO100 # nonemo: NMO901\n"
    "kind names the tool and transmit # nonemo: N003 # nonemo: P001\n",
    encoding="utf-8",
  )
  result = run(cwd=tmp_path)
  assert result.returncode == 1, result.stderr
  assert "note.md:1:" not in result.stdout
  assert "note.md:2: [NMO901] (review) names -> specify" in result.stdout
  assert "note.md:2: [NMO100] (violation) transmit -> send" in result.stdout
  assert "note.md:2: [NMO100] (violation) kind -> type" in result.stdout


def test_wrapped_prose_counts_the_complete_sentence(tmp_path):
  cap = config.SENTENCE_CAPS["instruction"]
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
      source.write_text("\n".join(lines) + "\n", encoding="utf-8")
      result = run(str(source), cwd=tmp_path)
      assert result.returncode == int(count > cap), result.stderr
      if count > cap:
        assert f"{source}:{first}: [STE200]" in result.stdout
    lines[first - 1] += " nonemo: STE200"
    source.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert run(str(source), cwd=tmp_path).returncode == 0
