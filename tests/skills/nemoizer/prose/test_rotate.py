"""nemoizer rotation tests."""

from pathlib import Path

import assertions
import prose.review
import prose.rotate
import report
from conftest import run

import rules


def test_a_rotation_matches_the_stem_and_prose():
  import tempfile

  with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    (root / "note.md").write_text(
      "He names the tool. Do not transmit this.\n", encoding="utf-8"
    )
    (root / "code.py").write_text("kind = 'plain'\n", encoding="utf-8")
    result = run(cwd=directory)
    assert result.returncode == 1
    assert "note.md:1: [NMO901] (review) names -> specify" in result.stdout
    assert "note.md:1: [NMO100] (violation) transmit -> send" in result.stdout
    assert "code.py:1:" not in result.stdout
    assert "\n    He names the tool. Do not transmit this." in result.stdout
    assert (
      report.format_summary(
        [
          "note.md:1: [NMO100] (violation) transmit -> send",
          "note.md:1: [NMO901] (review) names -> specify",
        ]
      )
      in result.stdout
    )


def test_name_rotates_only_as_a_verb():
  import tempfile

  with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    note = root / "note.md"
    note.write_text(
      "Name the variable.\nIt names each field.\nNaming the variable matters.\n"
      "The field is named in the table.\nThe value is named under the rule.\n"
      "The value is named by the report.\nUse a file named note.md.\n"
      "Use a named tuple and named breakpoints.\nUse the name of the file.\n"
      "Rename the file; leave unnamed and nameless items.\n",
      encoding="utf-8",
    )
    result = run(cwd=directory)
    for expected in (
      "note.md:1: [NMO901] (review) Name -> specify",
      "note.md:2: [NMO901] (review) names -> specify",
      "note.md:3: [NMO901] (review) Naming -> specify",
      "note.md:4: [NMO901] (review) named -> specify",
      "note.md:5: [NMO901] (review) named -> specify",
      "note.md:6: [NMO901] (review) named -> specify",
    ):
      assert expected in result.stdout
    for line_number in (7, 8, 9, 10):
      assert f"note.md:{line_number}: [NMO901]" not in result.stdout
    result = run("--format", cwd=directory)
    assert result.returncode == 0, result.stderr
    assert note.read_text(encoding="utf-8") == (
      "Specify the variable.\nIt specifies each field.\nSpecifying the variable matters.\n"
      "The field is specified in the table.\nThe value is specified under the rule.\n"
      "The value is specified by the report.\nUse a file named note.md.\n"
      "Use a named tuple and named breakpoints.\nUse the name of the file.\n"
      "Rename the file; leave unnamed and nameless items.\n"
    )


def test_name_verb_rotation_leaves_python_identifiers_untouched():
  import tempfile

  with tempfile.TemporaryDirectory() as directory:
    source = Path(directory) / "example.py"
    original = "if named in the and naming:\n  pass\n"
    source.write_text(original, encoding="utf-8")
    result = run("--format", cwd=directory)
    assert result.returncode == 0, result.stderr
    assert source.read_text(encoding="utf-8") == original


def test_nemoizer_proper_name_rotation_and_nmo902_list_article_collapse(tmp_path):
  assert (
    prose.rotate.rotate("Use the nemoizer, The Nemoizer, THE NEMOIZER, and Nemoizer.")
    == "Use nemoizer, nemoizer, nemoizer, and nemoizer."
  )
  assert (
    prose.rotate.rotate("The prose linter runs the nemoizer rules.")
    == "The prose linter runs the nemoizer rules."
  )
  assert (
    prose.rotate.collapse_list_articles(
      "Supply the source text, the target, and the unit for the worker."
    )
    == "Supply the source text, target, and unit for the worker."
  )
  doc = tmp_path / "sample.md"
  doc.write_text(
    "Use The Nemoizer on the source text, the target, and the unit.\n",
    encoding="utf-8",
  )
  findings, _ = prose.review.scan([doc], [])
  assert any(
    "NMO100" in item and "The Nemoizer -> nemoizer" in item for item in findings
  )
  changed = prose.review.format_paths([doc], [])
  assert changed == 1
  assert (
    doc.read_text(encoding="utf-8")
    == "Use nemoizer on the source text, target, and unit.\n"
  )
  assert "--format" in rules.RULE_DESCRIPTIONS["NMO902"]


def test_pick_is_retired_and_the_stem_still_shields_identifiers():
  import tempfile

  with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    ui = root / "ui.js"
    ui.write_text(
      "// picker widget\nconst var_pick = 2\n// repick item\nconst other = 3\n"
      "// pickle jar  nonemo: NMO901\n"
      "// names the tool\n",
      encoding="utf-8",
    )
    result = run(cwd=directory)
    assert result.returncode == 0
    # The retired rotation must not flag any pick form.
    assert "picker -> select" not in result.stdout
    assert "ui.js:1" not in result.stdout
    assert "ui.js:2" not in result.stdout
    assert "ui.js:3" not in result.stdout
    assert "ui.js:4" not in result.stdout
    assert "ui.js:5" not in result.stdout
    assert "ui.js:6: [NMO901] (review) names -> specify" in result.stdout
    formatted = run("--format", cwd=directory)
    assert formatted.returncode == 0, formatted.stderr
    assert ui.read_text(encoding="utf-8") == (
      "// picker widget\nconst var_pick = 2\n// repick item\nconst other = 3\n"
      "// pickle jar  nonemo: NMO901\n"
      "// specifies the tool\n"
    )


def test_repository_rotation_and_ste901_passive_voice_are_manual_review(tmp_path):
  source = tmp_path / "note.md"
  source.write_text(
    "Clone the Repository and both repositories. The report was published.\n",
    encoding="utf-8",
  )
  result = run(str(source), cwd=tmp_path)
  assert result.returncode == 0, result.stderr
  assert "[NMO901] (review) Repository -> repo" in result.stdout
  assert "[NMO901] (review) repositories -> repo" in result.stdout
  assert f"[STE901] (review) {rules.RULE_DESCRIPTIONS['STE901']}" in result.stdout
  formatted = run("--format", str(source), cwd=tmp_path)
  assert formatted.returncode == 0
  assert (
    source.read_text(encoding="utf-8")
    == "Clone the Repo and both repos. The report was published.\n"
  )
  source.write_text(
    "The report was published. <!-- nonemo: STE901 -->\n", encoding="utf-8"
  )
  assert not run(str(source), cwd=tmp_path).stdout.strip()
  source.write_text(
    "Set up the server. The state is parsed and validated.\n", encoding="utf-8"
  )
  advisory = run(str(source), cwd=tmp_path)
  assert advisory.returncode == 0, advisory.stderr
  assert f"[STE902] (review) {rules.RULE_DESCRIPTIONS['STE902']}" in advisory.stdout
  assert f"[STE903] (review) {rules.RULE_DESCRIPTIONS['STE903']}" in advisory.stdout
  source.write_text("Check red, green and blue.\n", encoding="utf-8")
  serial = run(str(source), cwd=tmp_path)
  assert serial.returncode == 1, serial.stderr
  assert f"[NMO003] (violation) {rules.RULE_DESCRIPTIONS['NMO003']}" in serial.stdout
  assert "review" not in serial.stdout or "review finding" in serial.stdout
  test_sample = tmp_path / "test_sample.py"
  test_sample.write_text(
    'def test_sample():\n  assert "three plain words" in result.stderr.strip()\n  assert check.measure(path) == 2\n',
    encoding="utf-8",
  )
  reviewed = assertions.review_tests([test_sample])
  assert {row["rule"] for row in reviewed["findings"]} == {"NMT100", "NMT200"}


def test_rotation_irregular_forms_and_false_friends(tmp_path):
  doc = tmp_path / "forms.md"
  doc.write_text(
    "Data was transmitted by the transmitter. Pickle and picky. Be kind.\n",
    encoding="utf-8",
  )
  prose.review.format_paths([doc], [])
  assert doc.read_text(encoding="utf-8") == (
    "Data was sent by the sender. Pickle and picky. Be kind.\n"
  )


def test_rotation_respects_fences_links_tables_and_code(tmp_path):
  doc = tmp_path / "boundary.md"
  doc.write_text(
    "```python\ndef pick(x): pass\n```\n"
    "[API](https://example.com?kind=full&pick=1)\n"
    "| `check.py` | Transmit the kind of repository |\n",
    encoding="utf-8",
  )
  findings, _ = prose.review.scan([doc], [])
  assert any("NMO100" in item and "kind" in item for item in findings)
  assert any("NMO100" in item and "Transmit" in item for item in findings)
  prose.review.format_paths([doc], [])
  assert doc.read_text(encoding="utf-8") == (
    "```python\ndef pick(x): pass\n```\n"
    "[API](https://example.com?kind=full&pick=1)\n"
    "| `check.py` | Send the type of repo |\n"
  )
  code = tmp_path / "example.py"
  code.write_text("item = pick(items)  # Transmit the kind.\n", encoding="utf-8")
  prose.review.format_paths([code], [])
  assert code.read_text(encoding="utf-8") == ("item = pick(items)  # Send the type.\n")


def test_rule_ids_suppress_only_the_named_rotation():
  import tempfile

  with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    note = root / "note.md"
    note.write_text(
      "kind and names the tool  # nonemo: NMO100\ntransmit # nonemo: N999\n",
      encoding="utf-8",
    )
    result = run(cwd=directory)
    assert result.returncode == 1
    assert "note.md:1: [NMO901] (review) names -> specify" in result.stdout
    assert "note.md:1: [NMO100] (violation) kind -> type" not in result.stdout
    assert "note.md:2: [NMO100] (violation) transmit -> send" in result.stdout
    result = run("--format", cwd=directory)
    assert result.returncode == 0
    assert (
      note.read_text(encoding="utf-8")
      == "kind and specifies the tool  # nonemo: NMO100\nsend # nonemo: N999\n"
    )


def test_soft_rotation_is_advisory_in_checks_and_explicit_in_format(tmp_path):
  source = tmp_path / "note.md"
  original = "Repository one.\n"
  source.write_text(original, encoding="utf-8")
  result = run(str(source), cwd=tmp_path)
  assert result.returncode == 0, result.stderr
  assert "[NMO901] (review) Repository -> repo" in result.stdout
  assert "manual review" not in result.stdout
  assert source.read_text(encoding="utf-8") == original
  formatted = run("--format", str(source), cwd=tmp_path)
  assert formatted.returncode == 0
  assert source.read_text(encoding="utf-8") == "Repo one.\n"
  source.write_text("Pick this kind.\n", encoding="utf-8")
  assert run(str(source), cwd=tmp_path).returncode == 1
  source.write_text("Pick one. <!-- nonemo: NMO901 -->\n", encoding="utf-8")
  assert not run(str(source), cwd=tmp_path).stdout.strip()


def test_the_format_mode_honors_the_marker():
  import tempfile

  with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    note = root / "note.md"
    note.write_text(
      "kind stays  <!-- nonemo: NMO100 -->\nnames the tool\nkind moves\n",
      encoding="utf-8",
    )
    result = run("--format", cwd=directory)
    assert result.returncode == 0, result.stderr
    assert note.read_text(encoding="utf-8") == (
      "kind stays  <!-- nonemo: NMO100 -->\nspecifies the tool\ntype moves\n"
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


def test_the_format_mode_rewrites_every_form_and_keeps_case():
  import tempfile

  with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    note = root / "note.py"
    note.write_text("kind = 1  # kind KIND kinds\n", encoding="utf-8")
    result = run("--format", cwd=directory)
    assert result.returncode == 0, result.stderr
    assert note.read_text(encoding="utf-8") == "kind = 1  # type TYPE types\n"
    assert "note.py:1: -kind = 1  # kind KIND kinds" in result.stdout
    assert "note.py:1: +kind = 1  # type TYPE types" in result.stdout
    assert run(cwd=directory).returncode == 0


def test_the_rotation_table_never_flags_itself():
  import tempfile

  with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    (root / "SKILL.md").write_text(
      "| Avoid | Use |\n| --- | --- |\n| `kind` | type |\n", encoding="utf-8"
    )
    result = run(cwd=directory)
    assert result.returncode == 0, result.stdout


def test_wrapped_rotation_and_name_contexts(tmp_path):
  doc = tmp_path / "wrapped.md"
  doc.write_text(
    "Please name tasks. The widget names the item.\n"
    "Review the pull\nrequests before merging.\n",
    encoding="utf-8",
  )
  findings, _ = prose.review.scan([doc], [])
  assert any("name -> specify" in item for item in findings)
  assert any("names -> specify" in item for item in findings)
  assert any("pull requests -> PR" in item for item in findings)
  prose.review.format_paths([doc], [])
  assert doc.read_text(encoding="utf-8") == (
    "Please specify tasks. The widget specifies the item.\n"
    "Review the pull\nrequests before merging.\n"
  )
