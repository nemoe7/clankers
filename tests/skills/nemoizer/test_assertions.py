"""nemoizer test-assertion review tests."""

import subprocess
import sys

import assertions
import pytest
from conftest import SCRIPT, copy_shipped_scripts, run


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
  source.write_text(original, encoding="utf-8")

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
  assert source.read_text(encoding="utf-8") == original
  measurement = next(
    row["rule"] for row in data["findings"] if row["category"] == "measurement"
  )
  source.write_text(
    f"# nonemo: {measurement}\n# nonemo: N999\n" + original, encoding="utf-8"
  )
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
  source.write_text("assert (\n", encoding="utf-8")
  failed, malformed = inspect(source)
  assert failed.returncode == 2
  assert malformed["errors"][0]["path"] == str(source)
  assert malformed["errors"][0]["type"] == "SyntaxError"
  assert malformed["errors"][0]["line"] > 0
  other = tmp_path / "fixture.txt"
  other.write_text(original, encoding="utf-8")
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

  missing_parser = subprocess.run(
    [sys.executable, str(SCRIPT), "review-tests", str(js)],
    cwd=tmp_path,
    capture_output=True,
    text=True,
    encoding="utf-8",
    env={**os.environ, "PATH": ""},
    check=False,
  )
  assert missing_parser.returncode == 0, missing_parser.stderr
  assert (
    json.loads(missing_parser.stdout)["coverage"][0]["reason"] == "parser_unavailable"
  )

  portable = tmp_path / "portable"
  copy_shipped_scripts(portable)
  shipped = subprocess.run(
    [sys.executable, str(portable / "nemoizer"), "review-tests", str(source)],
    cwd=tmp_path,
    capture_output=True,
    text=True,
    encoding="utf-8",
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


@pytest.mark.parametrize("language", ["py", "js"])
def test_local_aliases_do_not_cross_helper_or_parameter_scopes(language):
  source = (
    """
def helper():
  expected = "Helper prose is not tracked"
  assert expected in result.stdout
def test_shadow(expected):
  assert expected in result.stdout
  local = "Locally copied output prose"
  def nested(local):
    assert local in result.stdout
  local = module.EXPECTED_TEXT
  assert local in result.stdout
"""
    if language == "py"
    else """
function helper() {
  const expected = "Helper prose is not tracked";
  assert.ok(result.stdout.includes(expected));
}
test('shadow', (expected) => {
  assert.ok(result.stdout.includes(expected));
  let local = "Locally copied output prose";
  function nested(local) { assert.ok(result.stdout.includes(local)); }
  local = module.EXPECTED_TEXT;
  assert.ok(result.stdout.includes(local));
});
"""
  )
  parsed = (
    assertions.python_pairs(source)
    if language == "py"
    else assertions.javascript_pairs(source)
  )
  assert not [
    pair for pair in parsed["pairs"] if assertions.category(pair) == "output_text"
  ]


@pytest.mark.parametrize("language", ["py", "js"])
def test_local_prose_aliases_preserve_input_and_scope(language):
  source = (
    """
TEXT = "Production text stays valid"
async def test_alias():
  expected = "Copied output prose here"
  alias = expected
  assert alias in result.stdout
  supplied = "User supplied input prose"
  await client.post("/messages", json={"body": supplied})
  assert supplied in result.stdout
  expected = module.EXPECTED_TEXT
  assert expected in result.stdout
  assert TEXT in result.stdout
"""
    if language == "py"
    else """
const TEXT = "Production text stays valid";
test('aliases', async () => {
  let expected = "Copied output prose here";
  const alias = expected;
  assert.ok(result.stdout.includes(alias));
  const supplied = "User supplied input prose";
  await client.post('/messages', {body: supplied});
  assert.ok(result.stdout.includes(supplied));
  expected = module.EXPECTED_TEXT;
  assert.ok(result.stdout.includes(expected));
  assert.ok(result.stdout.includes(TEXT));
});
"""
  )
  parsed = (
    assertions.python_pairs(source)
    if language == "py"
    else assertions.javascript_pairs(source)
  )
  found = [
    pair for pair in parsed["pairs"] if assertions.category(pair) == "output_text"
  ]
  assert [pair["value"] for pair in found] == ["Copied output prose here"]


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


@pytest.mark.parametrize(
  ("setup", "assertion", "flagged"),
  [
    ("set_height(200);", "height", False),
    ("panel.set_height(200);", "panel.height", False),
    ("let height = 200;", "height", False),
    ("set_height(300);", "height", True),
    ("other.set_height(200);", "panel.height", True),
    ("set_height(200); set_height(dynamic);", "height", True),
  ],
)
def test_nmt200_explicit_javascript_setup(tmp_path, setup, assertion, flagged):
  source = tmp_path / "measurements.test.js"
  source.write_text(
    "test('size', () => { " + setup + " expect(" + assertion + ").toBe(200); });\n",
    encoding="utf-8",
  )
  reviewed = assertions.review_tests([source])
  assert not reviewed["errors"]
  assert bool(reviewed["findings"]) is flagged


@pytest.mark.parametrize(
  ("setup", "assertion", "flagged"),
  [
    ("set_height(200)", "height == 200", False),
    ("panel.set_height(200)", "panel.height == 200", False),
    ("height = 200", "height == 200", False),
    ("set_height(200)", "height == 201", True),
    ("set_width(200)", "height == 200", True),
    ("other.set_height(200)", "panel.height == 200", True),
    ("set_height(200)\nset_height(300)", "height == 200", True),
    ("set_height(200)\nset_height(dynamic)", "height == 200", True),
    ("height = 200\nheight = dynamic", "height == 200", True),
    ("height = 200\nheight += 1", "height == 200", True),
  ],
)
def test_nmt200_explicit_measurement_setup(tmp_path, setup, assertion, flagged):
  source = tmp_path / "test_measurements.py"
  body = "\n".join(
    "  " + line for line in (setup + "\nassert " + assertion).splitlines()
  )
  source.write_text("def test_size():\n" + body + "\n", encoding="utf-8")
  reviewed = assertions.review_tests([source])
  assert not reviewed["errors"]
  assert bool(reviewed["findings"]) is flagged


def test_nmt200_explicit_setup_stays_local_and_precedes_assertion(tmp_path):
  source = tmp_path / "test_measurements.py"
  source.write_text(
    "def test_setup():\n  set_height(200)\n"
    "def test_other():\n  assert height == 200\n  set_height(200)\n",
    encoding="utf-8",
  )
  reviewed = assertions.review_tests([source])
  assert [(row["rule"], row["line"]) for row in reviewed["findings"]] == [("NMT200", 4)]


@pytest.mark.parametrize(
  ("suffix", "assertion"),
  [
    ("py", 'assert element.width == "42px"'),
    ("py", "assert check.measure(path.name) == 42"),
    ("py", "assert check.measure(make_path(path.name)) == 42"),
    ("py", 'assert metrics["width"] == 42'),
    ("py", 'assert element.bounding_box()["width"] == 42'),
    ("js", "expect(element.width).toBe(42);"),
    ("js", 'expect(element).toHaveCSS("width", "42px");'),
    ("js", "assert.equal(element.getBoundingClientRect().width, 42);"),
    ("js", 'assert.equal(metrics["width"], 42);'),
  ],
)
def test_nmt200_measurement_forms(tmp_path, suffix, assertion):
  source = tmp_path / f"test_measurements.{suffix}"
  source.write_text(assertion + "\n", encoding="utf-8")
  reviewed = assertions.review_tests([source])
  assert not reviewed["errors"]
  assert [(row["rule"], row["line"]) for row in reviewed["findings"]] == [("NMT200", 1)]


@pytest.mark.parametrize(
  ("suffix", "assertion"),
  [
    ("py", 'assert metrics["width"] >= 42'),
    ("py", 'assert metrics["width"] == 0'),
    ("py", 'assert metrics["width"] == "0px"'),
    ("py", 'assert metrics["width"] == config.WIDTH'),
    ("py", 'assert metrics["status"] == 42'),
    ("js", "expect(element.width).toBe(0);"),
    ("js", "expect(element.width).toBe(config.WIDTH);"),
    ("js", "expect(element.width).toBeGreaterThan(42);"),
    ("js", 'expect(element).toHaveCSS("width", "0px");'),
    ("js", 'expect(element).toHaveCSS("color", "42px");'),
    ("js", "assert.equal(metrics[dynamicKey], 42);"),
  ],
)
def test_nmt200_measurement_forms_keep_relations_and_constants(
  tmp_path, suffix, assertion
):
  source = tmp_path / f"test_measurements.{suffix}"
  source.write_text(assertion + "\n", encoding="utf-8")
  reviewed = assertions.review_tests([source])
  assert not reviewed["errors"]
  assert not reviewed["findings"]


@pytest.mark.parametrize(
  ("suffix", "source_text"),
  [
    ("py", "height = 200\ndef test_default():\n  assert height == 200\n"),
    (
      "js",
      "const height = 200;\ntest('default', () => { expect(height).toBe(200); });\n",
    ),
  ],
)
def test_nmt200_module_defaults_are_not_explicit_test_inputs(
  tmp_path, suffix, source_text
):
  source = tmp_path / f"test_defaults.{suffix}"
  source.write_text(source_text, encoding="utf-8")
  reviewed = assertions.review_tests([source])
  assert not reviewed["errors"]
  assert [row["rule"] for row in reviewed["findings"]] == ["NMT200"]


def test_nmt200_setup_does_not_leak_between_conditional_branches(tmp_path):
  source = tmp_path / "test_measurements.py"
  source.write_text(
    "def test_size():\n  if flag:\n    set_height(200)\n  else:\n    assert height == 200\n",
    encoding="utf-8",
  )
  reviewed = assertions.review_tests([source])
  assert [(row["rule"], row["line"]) for row in reviewed["findings"]] == [("NMT200", 5)]


def test_nmt200_zero_measurements_are_exempt(tmp_path):
  source = tmp_path / "test_measurements.py"
  source.write_text(
    "assert panel.width == 0\nassert panel.width == 0.0\nassert panel.width == 1\n",
    encoding="utf-8",
  )
  reviewed = assertions.review_tests([source])
  assert [(row["rule"], row["line"]) for row in reviewed["findings"]] == [("NMT200", 3)]


def test_nmt300_detects_real_sleeps_and_exempts_bounded_polling(tmp_path):
  source = tmp_path / "test_waits.py"
  source.write_text(
    "import asyncio\n"
    "import time\n"
    "from unittest import mock\n"
    "from time import sleep\n"
    "def test_real_sleep():\n"
    "  time.sleep(0.01)\n"
    "def test_imported_sleep():\n"
    "  sleep(0.01)\n"
    "async def test_async_sleep():\n"
    "  await asyncio.sleep(0.01)\n"
    "def test_bounded_poll():\n"
    "  deadline = time.monotonic() + 1\n"
    "  while not ready() and time.monotonic() < deadline:\n"
    "    time.sleep(0.01)\n"
    "def test_mocked_sleep(monkeypatch):\n"
    "  monkeypatch.setattr(time, 'sleep', lambda _delay: None)\n"
    "  time.sleep(0.01)\n"
    "@mock.patch('time.sleep')\n"
    "def test_decorated_patch(_sleep):\n"
    "  time.sleep(0.01)\n"
    "def test_browser_wait(page):\n"
    "  page.wait_for_timeout(4000)\n",
    encoding="utf-8",
  )
  reviewed = assertions.review_tests([source])
  assert [(row["rule"], row["line"]) for row in reviewed["findings"]] == [
    ("NMT300", 6),
    ("NMT300", 8),
    ("NMT300", 10),
  ]
  result = run(str(source), cwd=tmp_path)
  assert result.returncode == 0, result.stderr
  assert "test_waits.py:6: [NMT300] (review)" in result.stdout


def test_nmt300_javascript_exempts_fake_timers_and_bounded_polling(tmp_path):
  source = tmp_path / "test_waits.cjs"
  source.write_text(
    'const { test } = require("node:test");\n'
    'test("real delay", async () => {\n'
    "  await new Promise((resolve) => setTimeout(resolve, 5));\n"
    "});\n"
    'test("real sleep", async () => {\n'
    "  await sleep(5);\n"
    "});\n"
    'test("fake timer", async () => {\n'
    "  vi.useFakeTimers();\n"
    "  const pending = new Promise((resolve) => setTimeout(resolve, 5));\n"
    "  vi.advanceTimersByTime(5);\n"
    "  await pending;\n"
    "});\n"
    'test("bounded poll", async () => {\n'
    "  const deadline = Date.now() + 50;\n"
    "  while (!ready() && Date.now() < deadline) {\n"
    "    await new Promise((resolve) => setTimeout(resolve, 5));\n"
    "  }\n"
    "});\n"
    'describe("suite fake timer", () => {\n'
    "  beforeEach(() => jest.useFakeTimers());\n"
    '  test("inherited fake timer", async () => {\n'
    "    await new Promise((resolve) => setTimeout(resolve, 5));\n"
    "  });\n"
    "});\n"
    'test("browser wait", async () => {\n'
    "  await page.waitForTimeout(4000);\n"
    "});\n",
    encoding="utf-8",
  )
  reviewed = assertions.review_tests([source])
  assert [(row["rule"], row["line"]) for row in reviewed["findings"]] == [
    ("NMT300", 3),
    ("NMT300", 6),
  ]


def test_prose_context_counts_and_rule_exclusions(tmp_path):
  import importlib.util
  import json

  source = tmp_path / "example.md"
  source.write_text("Run.\n", encoding="utf-8")
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
  source.write_text(sentence + "\n", encoding="utf-8")

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
  assert (
    finding["line"]
    == source.read_text(encoding="utf-8").splitlines().index(sentence) + 1
  )
  assert inspect("unknown")["coverage"][0]["sentences"] == "checked"
  assert inspect("unknown")["findings"]
  code = finding["rule"]
  source.write_text(f"<!-- nonemo: {code} -->\n{sentence}\n", encoding="utf-8")
  assert not inspect("instruction")["findings"]
  listing = run("--ignores", str(source), cwd=tmp_path)
  assert listing.returncode == 0 and code in listing.stdout

  cap = limits.PARAGRAPH_CAP
  source.write_text(" ".join("Short." for _ in range(cap + 1)) + "\n", encoding="utf-8")
  paragraphs = inspect("description")["findings"]
  assert paragraphs and paragraphs[0]["count"] > paragraphs[0]["cap"] == cap
  source.write_text(" ".join("Short." for _ in range(cap)) + "\n", encoding="utf-8")
  assert not inspect("description")["findings"]
  stricter = cap - 1
  assert inspect("description", "--paragraph-cap", str(stricter))["findings"]
  relaxed = run("prose", "--paragraph-cap", str(cap + 1), str(source), cwd=tmp_path)
  assert relaxed.returncode == 2
  source.write_text("```\n" + sentence + "\n```\n", encoding="utf-8")
  assert not inspect("instruction")["findings"]
  source.write_text("~~~\n" + sentence + "\n~~~\n", encoding="utf-8")
  assert not inspect("instruction")["findings"]
  source.write_text("`" + sentence + "`\n", encoding="utf-8")
  assert not inspect("instruction")["findings"]
  cell = " ".join("term" for _ in range(instruction_cap // 2 + 1))
  source.write_text(
    f"| Left | Right |\n| --- | --- |\n| {cell} | {cell} |\n", encoding="utf-8"
  )
  assert not inspect("instruction")["findings"]
  source.write_text(
    f"| Left | Right |\n| --- | --- |\n| {sentence} | Short |\n", encoding="utf-8"
  )
  assert inspect("instruction")["findings"]
  import csv

  source.write_text(
    "term" * (csv.field_size_limit() + 1) + " | term\n", encoding="utf-8"
  )
  assert not inspect("instruction")["findings"]

  portable = tmp_path / "portable"
  copy_shipped_scripts(portable / "scripts")
  source.write_text("Run.\n", encoding="utf-8")
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
    encoding="utf-8",
    check=False,
    cwd=tmp_path,
  )
  assert shipped.returncode == 0, shipped.stderr
  assert not json.loads(shipped.stdout)["findings"]


@pytest.mark.parametrize(
  ("setup", "expression", "expected"),
  [
    ("", "settings.LIMIT == 42", True),
    ("", "42 == settings.LIMIT", True),
    ("", "settings.NEGATIVE == -2", True),
    ("", "LIMIT == 42", True),
    ("settings.LIMIT = 42", "settings.LIMIT == 42", False),
    ("monkeypatch.setattr(settings, 'LIMIT', 42)", "settings.LIMIT == 42", False),
    ("settings = object()", "settings.LIMIT == 42", False),
    ("import other as settings", "settings.LIMIT == 42", False),
    ("", "settings.SCHEMA_VERSION == 1", False),
    ("", "settings.COMPUTED == 42", False),
    ("", "settings.MUTABLE == 42", False),
    ("", "result == settings.LIMIT", False),
    ("", "result == 42", False),
  ],
)
def test_source_numeric_advisory_boundary(tmp_path, setup, expression, expected):
  (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
  (tmp_path / "settings.py").write_text(
    "LIMIT = 42\nNEGATIVE = -2\nSCHEMA_VERSION = 1\n"
    "COMPUTED = int('42')\nMUTABLE = 42\nMUTABLE = 43\n",
    encoding="utf-8",
  )
  source = tmp_path / "test_numeric.py"
  source.write_text(
    "import settings\nfrom settings import LIMIT\n\ndef test_setting():\n"
    + (f"  {setup}\n" if setup else "")
    + f"  assert {expression}\n",
    encoding="utf-8",
  )
  findings = assertions.review_tests([source])["findings"]
  numeric = [row for row in findings if row["category"] == "numeric_setting"]
  assert bool(numeric) == expected
  if expected:
    assert numeric[0]["status"] == "manual_review"
    assert numeric[0]["source_path"] == str(tmp_path / "settings.py")
    assert numeric[0]["source_line"] > 0
    assert "settings.py:" in numeric[0]["evidence"]
    result = run(str(source), cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert "(review)" in result.stdout


@pytest.mark.parametrize("prefix", ["settings = object()\n", ""])
def test_source_numeric_advisory_skips_uncertain_scope(tmp_path, prefix):
  (tmp_path / "settings.py").write_text("LIMIT = 42\n", encoding="utf-8")
  source = tmp_path / "test_numeric.py"
  source.write_text(
    "import settings\n"
    + prefix
    + "def test_setting(settings=None):\n  assert settings.LIMIT == 42\n",
    encoding="utf-8",
  )
  assert not assertions.numeric_setting_findings(source, source.read_text())
