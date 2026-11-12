# nonemo: NMU200
"""nemoizer UI-label and byte-unit tests."""

from pathlib import Path

import config
import prose.review
import report
from conftest import run


def _nmu200_rows(path, source):
  findings = prose.review.source_prose(Path(path), source, "unknown", 4)
  return [row for row in findings if row["rule"] == "NMU200"]


def test_js_html_template_extracts_ui_prose_and_flags_em_dash(tmp_path):
  view = tmp_path / "reports-view.js"
  source = (
    "export function render(ans) {\n"
    "  return `<p><strong>Submission ${ans.id}</strong> · <time>${ans.time}</time> — ${ans.entries}</p>`;\n"
    "}\n"
  )
  view.write_text(source, encoding="utf-8")
  rows = prose.review.source_prose(view, source, "description", config.PARAGRAPH_CAP)
  assert any(row["rule"] == "HMN905" and row["line"] == 2 for row in rows)


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
  expected = report.describe_finding(
    {
      "rule": "NMU100",
      "text": "Open the repo",
      "word": "the",
      "count": 3,
      "cap": 6,
    }
  )
  assert f"[NMU100] (violation) {expected}" in r1.stdout

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
  expected_cap = report.describe_finding(
    {
      "rule": "NMU100",
      "text": "Open the repo",
      "word": "the",
      "count": 3,
      "cap": 3,
    }
  )
  assert f"[NMU100] (violation) {expected_cap}" in r4.stdout


def test_nmu200_accepts_matching_labels_bitrates_and_non_divisors():
  rows = _nmu200_rows(
    "matching.py",
    'binary = f"{size / 1024:.1f} KiB"\n'
    'decimal = f"{size / 1_000_000:.1f} MB"\n'
    'rate = f"{size / 1024:.1f} Mbps"\n'
    'raw = f"{max(1024, size)} KB"\n',
  )
  assert rows == []


def test_nmu200_flags_javascript_template_literal():
  rows = _nmu200_rows(
    "sizes.js", "const label = `${bytes / 1024} KB`;\n"
  )  # nonemo: NMU200
  assert [(row["line"], row["scale"]) for row in rows] == [(1, "binary")]


def test_nmu200_flags_python_binary_and_decimal_mismatches(tmp_path):
  # nonemo: NMU200
  sample = (
    'label = f"{size / 1024:.1f} KB"\n'
    'label = f"{size / (1024 * 1024)} MB"\n'
    'label = f"{size / (1 << 20)} MB"\n'
    'label = f"{size / 1_000_000:.1f} MiB"\n'
    'label = f"{size / 1048576} GB"\n'
    'label = f"{size / 1073741824} TB"\n'
    'label = f"{size / 1e6} GiB"\n'
    'label = f"{size / 1e9} TiB"\n'
  )
  rows = _nmu200_rows("sizes.py", sample)
  assert [(row["line"], row["scale"]) for row in rows] == [
    (1, "binary"),
    (2, "binary"),
    (3, "binary"),
    (4, "decimal"),
    (5, "binary"),
    (6, "binary"),
    (7, "decimal"),
    (8, "decimal"),
  ]
  sample_py = tmp_path / "sizes.py"
  sample_py.write_text(sample, encoding="utf-8")
  cli = run(str(sample_py), cwd=tmp_path)
  assert cli.returncode == 1, cli.stderr
  assert cli.stdout.count("[NMU200] (violation)") == 8


def test_nmu200_honors_inline_and_file_suppressions():
  # nonemo: NMU200
  inline = _nmu200_rows(
    "inline.py",
    "first = 0\nsecond = 0\nthird = 0\n"
    'hidden = f"{size / 1024} KB"  # nonemo: NMU200\n'
    'visible = f"{size / 1_000_000} MiB"\n',
  )
  assert [row["line"] for row in inline] == [5]

  file_level = _nmu200_rows(
    "file_level.py",
    '# nonemo: NMU200\nvalue = f"{size / 1024} KB"\n',
  )
  assert file_level == []
