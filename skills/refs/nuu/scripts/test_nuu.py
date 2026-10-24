"""Exercise the public UI workflow and preserve product authority."""

import json
import subprocess
import sys
from pathlib import Path

import annotate
import measure
import nuu
import uiux

SCRIPT = Path(__file__).with_name("nuu.py")


def test_ui_workflow_preserves_sources_and_reports_missing_evidence(tmp_path):
  root = tmp_path / "product"
  root.mkdir()
  css = root / "style.css"
  css.write_text(":root {--brand: #123456; --gap: 16px;}\n", encoding="utf-8")
  page = root / "index.html"
  page.write_text('<img src="art.svg"><input><button>Send</button>\n', encoding="utf-8")

  def run(*args, expected=0):
    process = subprocess.run(
      [sys.executable, str(SCRIPT), *args, "--project", str(root)],
      cwd=tmp_path,
      capture_output=True,
      text=True,
      check=False,
    )
    assert process.returncode == expected, process.stderr or process.stdout
    return json.loads(process.stdout)

  runtime = run("doctor")
  assert runtime["catalog"]["files"] > 0
  assert not runtime["catalog"]["mismatches"]
  exact = run("search", "healthcare dashboard", "-d", "products", "-l", "5")
  assert exact["results"] and not exact["fallback"]
  assert len(exact["results"]) <= 5
  assert all(row["matched_terms"] for row in exact["results"])
  fallback = run("search", "zzznomatchzzzx", "--dataset", "products")
  assert fallback["fallback"]
  assert not any(row["matched_terms"] for row in fallback["results"])

  before = {path: path.read_bytes() for path in (css, page)}
  findings = run("lint", expected=1)
  assert {row["rule"] for row in findings["findings"]} >= {"NUL001", "NUL002", "NUL004"}
  assert all(row["line"] > 0 and row["evidence"] for row in findings["findings"])
  page.write_text(
    '<img src="art.svg" alt=""><label>Field<input></label>\n', encoding="utf-8"
  )
  assert {row["rule"] for row in run("lint", expected=1)["findings"]} == {"NUL004"}
  missing_doc_audit = run("audit", expected=1)
  assert {row["rule"] for row in missing_doc_audit["findings"]} == {"NUL004"}
  design_doc = root / "docs" / "design.md"
  design_doc.parent.mkdir(exist_ok=True)
  design_doc.write_text("# Design\n", encoding="utf-8")
  assert not run("lint")["findings"]
  page.write_text('<img src="art.svg"> <!-- nonuu: NUL0010 -->\n', encoding="utf-8")
  assert run("lint", expected=1)["findings"]
  page.write_text('<img src="art.svg"> <!-- nonuu: NUL001 -->\n', encoding="utf-8")
  assert not run("lint")["findings"]
  css.write_text(before[css].decode() + "button:focus {outline: none !important;}\n")
  assert {row["rule"] for row in run("lint", expected=1)["findings"]} == {"NUL003"}
  css.write_text(
    before[css].decode() + "button:focus {outline: none;} /* nonuu: NUL003 */\n"
  )
  assert not run("lint")["findings"]
  css.write_bytes(before[css])
  before[page] = page.read_bytes()
  manifest = tmp_path / "assets.json"
  asset = root / "art.svg"
  asset.write_text('<svg xmlns="http://www.w3.org/2000/svg"/>', encoding="utf-8")
  manifest.write_text(
    json.dumps(
      [
        {
          "path": "art.svg",
          "source": "local original",
          "license": "MIT",
          "attribution": "test fixture",
        }
      ]
    ),
    encoding="utf-8",
  )
  assert not run("assets", "-m", str(manifest))["findings"]
  asset.write_text('<svg onload="alert(1)"/>', encoding="utf-8")
  assert run("assets", "--manifest", str(manifest), expected=1)["findings"]
  assert (
    run(
      "assets",
      "-f",
      "https://example.com/art.svg",
      "-d",
      "new.svg",
      expected=2,
    )["status"]
    == "error"
  )
  assert not (root / "new.svg").exists()
  assert run("extract")["tokens"]
  sheet_extract = subprocess.run(
    [
      sys.executable,
      str(SCRIPT),
      "extract",
      "--project",
      str(SCRIPT.parent.parent / "references"),
    ],
    cwd=tmp_path,
    capture_output=True,
    text=True,
    check=False,
  )
  assert sheet_extract.returncode == 0
  assert [row["value"] for row in json.loads(sheet_extract.stdout)["breakpoints"]] == [
    "75em",
    "60em",
    "40em",
    "30em",
  ]
  measured = tmp_path / "measured.json"
  measured.write_text(
    json.dumps(
      {
        "width": 1280,
        "elements": [{"selector": ".row", "values": {"height": "40px", "gap": "16px"}}],
      }
    ),
    encoding="utf-8",
  )
  check_proc = subprocess.run(
    [sys.executable, str(SCRIPT), "check", str(measured), "-k", "8"],
    cwd=tmp_path,
    capture_output=True,
    text=True,
    check=False,
  )
  assert check_proc.returncode == 0
  ruler_proc = subprocess.run(
    [sys.executable, str(SCRIPT), "ruler", "-f", "0,0", "-t", "16,24", "-k", "8"],
    cwd=tmp_path,
    capture_output=True,
    text=True,
    check=False,
  )
  assert ruler_proc.returncode == 0
  audit = run("audit", expected=3)
  assert audit["rendered"]["status"] == "not_checked"
  assert audit["real_device"] == "not_run"
  assert all(path.read_bytes() == value for path, value in before.items())


def test_browser_rejects_unsafe_requests_before_dependency_checks(tmp_path):
  import shutil

  import pytest

  if not shutil.which("node"):
    pytest.skip("Node is not available")
  driver = SCRIPT.with_name("browser.cjs")
  base = {
    "command": "inspect",
    "url": "https://example.com",
    "widths": [360],
    "timeout": 1,
    "engine": "auto",
    "flow": [],
    "output": str(tmp_path / "evidence"),
  }
  invalid = [
    {"url": "file:///etc/passwd"},
    {"url": "https://user:password@example.com"},
    {"widths": [0]},
    {"flow": [{"action": "offline", "value": "false"}]},
    {"flow": [{"action": "fill", "selector": "input"}]},
    {"flow": [{"action": "goto", "url": "javascript:alert(1)"}]},
    {"command": "live", "edit": {"selector": "body", "text": "changed"}},
    {
      "command": "live",
      "authorized_edit": True,
      "edit": {"selector": "body", "styles": []},
    },
    {"overlaps": "true"},
  ]
  for change in invalid:
    result = subprocess.run(
      ["node", str(driver)],
      input=json.dumps({**base, **change}),
      text=True,
      capture_output=True,
      check=False,
      cwd=tmp_path,
    )
    assert result.returncode == 2
    assert json.loads(result.stdout)["status"] == "error"
  assert not Path(base["output"]).exists()


def test_rendered_public_flow_and_live_evidence(tmp_path):
  import http.server
  import os
  import threading

  import pytest

  if not os.environ.get("NEMO_UI_BROWSER_TEST"):
    pytest.skip("Optional browser integration is not enabled")
  config = json.loads(Path(os.environ["NEMO_UI_BROWSER_CONFIG"]).read_text())
  markup = b"""<!doctype html><html><head><title>Tool fixture</title><style>
body {margin:16px;font:16px sans-serif;background:#fff;color:#111}
@media(prefers-color-scheme:dark){body{background:#111;color:#fff}}
input,button {font:inherit;min-height:44px;max-width:100%;box-sizing:border-box}
:focus-visible{outline:2px solid #08c;outline-offset:0}
main {max-width:640px} [hidden]{display:none}
</style></head><body><main><h1>Tool fixture</h1><form id="form">
<label for="entry">Value</label><input id="entry"><button id="send">Continue</button>
</form><p id="invalid" hidden>Value required</p><p id="pending" hidden>Pending</p>
<p id="failure" hidden>Request failed</p><button id="retry" hidden>Retry</button>
<p id="receipt" tabindex="-1" hidden>Saved</p></main><script>
let attempts = 0;
const byId = id => document.getElementById(id);
function submit(event) {
 event.preventDefault();
 if (!byId('entry').value.trim()) {byId('invalid').hidden=false;byId('entry').focus();return;}
 byId('invalid').hidden=true;byId('failure').hidden=true;byId('retry').hidden=true;
 byId('pending').hidden=false;byId('send').disabled=true;
 setTimeout(() => {
  byId('pending').hidden=true;byId('send').disabled=false;
  if (!attempts++) {byId('failure').hidden=false;byId('retry').hidden=false;byId('retry').focus();}
  else {byId('receipt').hidden=false;byId('receipt').focus();}
 }, 300);
}
byId('form').addEventListener('submit',submit);
byId('retry').addEventListener('click',submit);
</script></body></html>"""

  class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
      self.send_response(200)
      self.send_header("Content-Type", "text/html; charset=utf-8")
      self.end_headers()
      self.wfile.write(
        (project / "overlap.html").read_bytes()
        if self.path == "/overlap.html"
        else markup
      )

    def log_message(self, *_args):
      pass

  project = tmp_path / "project"
  project.mkdir()
  source = project / "index.html"
  source.write_bytes(markup)
  flow = [
    {"action": "focus", "selector": "#entry"},
    {"action": "press", "selector": "#entry", "key": "Enter"},
    {"action": "visible", "selector": "#invalid"},
    {"action": "focused", "selector": "#entry"},
    {"action": "fill", "selector": "#entry", "value": "fixture data"},
    {"action": "press", "selector": "#entry", "key": "Enter"},
    {"action": "visible", "selector": "#failure"},
    {"action": "focused", "selector": "#retry"},
    {"action": "press", "selector": "#retry", "key": "Enter"},
    {"action": "visible", "selector": "#receipt"},
    {"action": "focused", "selector": "#receipt"},
  ]
  flow_file = tmp_path / "flow.json"
  flow_file.write_text(json.dumps(flow))
  edit_file = tmp_path / "edit.json"
  edited = "Transient fixture edit"
  edit_file.write_text(
    json.dumps({"selector": "h1", "text": edited, "styles": {"color": "rgb(1, 2, 3)"}})
  )
  env = {**os.environ, **config.get("env", {})}

  with http.server.ThreadingHTTPServer(("0.0.0.0", 0), Handler) as server:
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_port}"

    def run(command, *args, expected=0):
      result = subprocess.run(
        [
          sys.executable,
          str(SCRIPT),
          command,
          "--project",
          str(project),
          "--url",
          url,
          "--engine",
          "chromium",
          "--executable",
          config["executable"],
          "--timeout",
          "5",
          "--artifacts",
          str(tmp_path / command),
          *args,
        ],
        text=True,
        capture_output=True,
        check=False,
        env=env,
      )
      assert result.returncode == expected, result.stderr or result.stdout
      return json.loads(result.stdout)

    try:
      report = run("flow", "--flow", str(flow_file))
      captures = report["captures"]
      required_widths = {360, 1280}
      assert {row["width"] for row in captures} >= required_widths
      assert {row["scheme"] for row in captures} == {"light", "dark"}
      assert {row["motion"] for row in captures} == {"no-preference", "reduce"}
      assert all(
        row["status"] == "captured" and Path(row["screenshot"]).is_file()
        for row in captures
      )
      assert captures[0]["flow"]["status"] == "passed"
      assert captures[0]["flow"]["assertions"] > 0
      assert captures[0]["measurements"]["active"]["id"] == flow[-1][
        "selector"
      ].removeprefix("#")
      assert all(row["flow"]["status"] == "not_run" for row in captures[1:])
      images_before = {
        Path(row["screenshot"]): Path(row["screenshot"]).read_bytes()
        for row in captures
      }
      report_file = tmp_path / "report.json"
      report_file.write_text(json.dumps(report))
      review = subprocess.run(
        [
          sys.executable,
          str(SCRIPT),
          "animate",
          "--project",
          str(project),
          "--evidence",
          str(report_file),
        ],
        text=True,
        capture_output=True,
        check=False,
      )
      assert review.returncode == 0
      assert json.loads(review.stdout)["rendered_evidence"]["values"]
      overlap_page = project / "overlap.html"
      overlap_page.write_text(
        "<!doctype html><style>body{margin:0}"
        "#under,#over{position:fixed;left:20px;top:20px;width:80px;height:80px}"
        "#under{z-index:1;background:#c00}#over{z-index:2;background:#080}"
        "#far{position:fixed;left:220px;top:20px;width:40px;height:40px}</style>"
        '<div id="under"><span id="inside">a</span></div>'
        '<div id="over">b</div><div id="far">c</div>',
        encoding="utf-8",
      )
      overlap_report = run(
        "inspect",
        "--overlaps",
        "--selector",
        "#under,#inside,#over,#far",
        "--url",
        f"{url}/overlap.html",
      )
      overlap_data = overlap_report["captures"][0]["overlaps"]
      assert overlap_data["status"] == "checked"
      assert overlap_data["limits"]["z_distance"].startswith("not_computed")
      pairs = {(row["first"], row["second"]): row for row in overlap_data["pairs"]}
      pair = pairs.get(("#under", "#over")) or pairs.get(("#over", "#under"))
      assert pair and pair["relation"] == "separate" and pair["topmost"] == "#over"
      assert pair["stacking"]["#over"][0]["zIndex"] == "2"
      nested = pairs.get(("#under", "#inside")) or pairs.get(("#inside", "#under"))
      assert nested and nested["relation"] in {"ancestor", "descendant"}
      assert all(
        "#far" not in (row["first"], row["second"]) for row in overlap_data["pairs"]
      )
      house = run("inspect", "--profile", "house", expected=1)
      assert any(row["house_measurements"] for row in house["captures"])
      assert any(row["rule"] == "NUM201" for row in house["findings"])
      live = run("live", "--edit", str(edit_file), "--authorize-edit")
      edit = live["captures"][0]["edit"]
      assert (
        edit["before"]["elements"][0]["text"] != edit["after"]["elements"][0]["text"]
      )
      assert edit["after"]["elements"][0]["text"] == edited
      assert (
        Path(edit["before_screenshot"]).is_file()
        and Path(edit["after_screenshot"]).is_file()
      )
      assert (
        edit["before"]["elements"][0]["values"]["color"]
        != edit["after"]["elements"][0]["values"]["color"]
      )
      assert source.read_bytes() == markup
      flow_file.write_text(json.dumps([{"action": "visible", "selector": "#absent"}]))
      failed = run("flow", "--flow", str(flow_file), expected=1)
      assert failed["findings"] and failed["captures"][0]["flow"]["status"] == "failed"
      assert all(
        path.read_bytes() == content for path, content in images_before.items()
      )
      artifact = Path(os.environ["NEMO_UI_BROWSER_ARTIFACTS"])
      artifact.mkdir(parents=True, exist_ok=True)
      import shutil

      for row in captures:
        screenshot = Path(row["screenshot"])
        shutil.copyfile(screenshot, artifact / screenshot.name)
      for name in ("before_screenshot", "after_screenshot"):
        screenshot = Path(edit[name])
        shutil.copyfile(screenshot, artifact / screenshot.name)
      (artifact / "report.json").write_text(json.dumps(report, indent=2))
    finally:
      server.shutdown()
      thread.join()


def test_authorized_asset_fetch_keeps_destinations_and_redirect_guards(tmp_path):
  import http.server
  import threading

  payload = b'<svg xmlns="http://www.w3.org/2000/svg"/>'
  requests = []

  class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
      requests.append(self.path)
      if self.path == "/unsafe":
        self.send_response(302)
        self.send_header("Location", "file:///etc/passwd")
        self.end_headers()
      else:
        self.send_response(200)
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *_args):
      pass

  with http.server.ThreadingHTTPServer(("0.0.0.0", 0), Handler) as server:
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_port}"

    def run(route, destination, expected):
      result = subprocess.run(
        [
          sys.executable,
          str(SCRIPT),
          "assets",
          "--project",
          str(tmp_path),
          "--fetch",
          url + route,
          "--destination",
          destination,
          "--authorize-fetch",
        ],
        text=True,
        capture_output=True,
        check=False,
      )
      assert result.returncode == expected, result.stderr or result.stdout
      return json.loads(result.stdout)

    try:
      result = run("/asset", "art.svg", 0)
      assert Path(result["path"]).read_bytes() == payload
      assert result["license"] == "unknown" and result["attribution"] == "unknown"
      before = list(requests)
      assert run("/asset", "art.svg", 2)["status"] == "error"
      assert requests == before
      assert (tmp_path / "art.svg").read_bytes() == payload
      assert run("/unsafe", "blocked.svg", 2)["status"] == "error"
      assert not (tmp_path / "blocked.svg").exists()
      before = list(requests)
      assert run("/asset", "../outside.svg", 2)["status"] == "error"
      assert requests == before
      assert not (tmp_path.parent / "outside.svg").exists()
    finally:
      server.shutdown()
      thread.join()


def test_ready_selector_and_rendered_a11y_pass_and_annotate(tmp_path):
  import shutil
  import sys

  import pytest

  sys.path.insert(0, str(SCRIPT.parent))
  from annotate import decode_png, encode_png

  src_png = tmp_path / "source.png"
  pixels = bytearray([240, 244, 248, 255] * (80 * 60))
  original_bytes = encode_png(80, 60, pixels)
  src_png.write_bytes(original_bytes)
  out_png = tmp_path / "annotated.png"
  spec_file = tmp_path / "spec.json"
  spec_file.write_text(
    json.dumps(
      {
        "boxes": [{"x": 4, "y": 4, "width": 30, "height": 20, "color": "#2563eb"}],
        "labels": [{"x": 8, "y": 28, "text": "CTA", "color": "amber"}],
      }
    ),
    encoding="utf-8",
  )
  proc = subprocess.run(
    [
      sys.executable,
      str(SCRIPT),
      "annotate",
      "--project",
      str(tmp_path),
      "--input",
      str(src_png),
      "--output",
      str(out_png),
      "--box",
      "10,10,40,25,red",
      "--label",
      "12,12,HERO,blue",
      "--arrow",
      "5,5,50,40,green",
      "--callout",
      "60,20,1,FIX,red",
      "--spec",
      str(spec_file),
    ],
    text=True,
    capture_output=True,
    check=False,
  )
  assert proc.returncode == 0, proc.stderr or proc.stdout
  payload = json.loads(proc.stdout)
  assert payload["status"] == "annotated"
  assert payload["scale"] == 2
  assert payload["annotations"] == {"boxes": 2, "labels": 2, "arrows": 1, "callouts": 1}
  assert src_png.read_bytes() == original_bytes
  out_w, out_h, out_rgba = decode_png(out_png.read_bytes())
  assert (out_w, out_h) == (80, 60)
  assert out_rgba != pixels

  scaled_png = tmp_path / "annotated-3.png"
  scaled_proc = subprocess.run(
    [
      sys.executable,
      str(SCRIPT),
      "annotate",
      "--project",
      str(tmp_path),
      "--input",
      str(src_png),
      "--output",
      str(scaled_png),
      "-S",
      "3",
      "-c",
      "40,30,1,BIG,red",
    ],
    text=True,
    capture_output=True,
    check=False,
  )
  assert scaled_proc.returncode == 0, scaled_proc.stderr or scaled_proc.stdout
  assert json.loads(scaled_proc.stdout)["scale"] == 3

  inplace = subprocess.run(
    [
      sys.executable,
      str(SCRIPT),
      "annotate",
      "--project",
      str(tmp_path),
      "--input",
      str(src_png),
      "--output",
      str(src_png),
      "--box",
      "1,1,10,10",
    ],
    text=True,
    capture_output=True,
    check=False,
  )
  assert inplace.returncode == 2
  assert src_png.read_bytes() == original_bytes

  if not shutil.which("node"):
    pytest.skip("Node is not available")
  driver = SCRIPT.with_name("browser.cjs")
  driver_src = driver.read_text(encoding="utf-8")
  assert "hasTouch: touch" in driver_src and "isMobile: touch" in driver_src
  assert "height <= 480" in driver_src
  assert "NUA307" in driver_src
  assert "NUA308" in driver_src
  bad_ready = subprocess.run(
    ["node", str(driver)],
    input=json.dumps(
      {
        "command": "inspect",
        "url": "https://example.com",
        "widths": [360],
        "timeout": 1,
        "engine": "auto",
        "ready": "   ",
        "flow": [],
        "output": str(tmp_path / "bad-ready"),
      }
    ),
    text=True,
    capture_output=True,
    check=False,
  )
  assert bad_ready.returncode == 2
  assert json.loads(bad_ready.stdout)["status"] == "error"

  fake_nm = tmp_path / "FakePlaywright"
  pw_dir = fake_nm / "node_modules" / "playwright"
  pw_dir.mkdir(parents=True)
  fake_bin = fake_nm / "chromium-bin"
  fake_bin.write_text("", encoding="utf-8")
  for name in ("browser.cjs",):
    shutil.copy2(SCRIPT.with_name(name), fake_nm / name)
  (pw_dir / "index.js").write_text(
    """
const fs = require('node:fs');
const PNG = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4z8DwHwAFAAH/iZk9HQAAAABJRU5ErkJggg==',
  'base64'
);
module.exports = {
  chromium: {
    executablePath: () => process.env.FAKE_CHROMIUM_PATH,
    launch: async () => ({
      newContext: async () => ({
        newPage: async () => ({
          on() {},
          goto: async () => ({ status: () => 200, ok: () => true }),
          locator: sel => ({
            first: () => ({
              waitFor: async () => {
                if (sel === '#missing-ready') throw new Error('Timeout waiting for #missing-ready');
              },
            }),
            count: async () => 1,
          }),
          evaluate: async fn => {
            const src = String(fn);
            if (src.includes('NUA301')) {
              if (process.env.FAKE_A11Y_MODE === 'clean') return { status: 'checked', findings: [] };
              return {
                status: 'checked',
                findings: [
                  { rule: 'NUA301', severity: 'review', criterion: '4.1.2', evidence: 'unlabeled' },
                  { rule: 'NUA302', severity: 'review', criterion: '1.3.1', evidence: 'missing ref' },
                  { rule: 'NUA303', severity: 'review', criterion: '4.1.2', evidence: 'nested' },
                  { rule: 'NUA304', severity: 'review', criterion: '4.1.1', evidence: 'duplicate id' },
                  { rule: 'NUA305', severity: 'review', criterion: '1.3.1', evidence: 'skipped h' },
                  { rule: 'NUA306', severity: 'review', criterion: '1.4.3', evidence: 'contrast' },
                ],
              };
            }
            return {
              width: 360,
              height: 900,
              elements: [],
              overflow: false,
              preference: { dark: false, reducedMotion: false },
              active: { tag: 'BODY', id: '', role: null },
            };
          },
          screenshot: async ({ path }) => fs.writeFileSync(path, PNG),
        }),
        close: async () => {},
      }),
      close: async () => {},
    }),
  },
};
""",
    encoding="utf-8",
  )

  def run_driver(req, mode="findings"):
    res = subprocess.run(
      ["node", str(fake_nm / "browser.cjs")],
      input=json.dumps(req),
      text=True,
      capture_output=True,
      check=False,
      env={
        **__import__("os").environ,
        "FAKE_CHROMIUM_PATH": str(fake_bin),
        "FAKE_A11Y_MODE": mode,
      },
    )
    return res.returncode, json.loads(res.stdout)

  base_req = {
    "command": "inspect",
    "url": "https://example.com",
    "widths": [360],
    "timeout": 1,
    "engine": "auto",
    "selector": "main",
    "flow": [],
    "output": str(tmp_path / "out"),
  }
  code_ok, ready_ok = run_driver({**base_req, "ready": "#app-ready"}, mode="clean")
  assert code_ok == 0 and ready_ok["status"] == "captured"

  code_timeout, ready_timeout = run_driver(
    {**base_req, "ready": "#missing-ready"}, mode="clean"
  )
  assert code_timeout == 0 and ready_timeout["status"] == "findings"
  assert {row["rule"] for row in ready_timeout["findings"]} == {"NUB104"}

  code_a11y, a11y_bad = run_driver(
    {**base_req, "command": "a11y", "a11y": True}, mode="findings"
  )
  assert code_a11y == 0 and a11y_bad["status"] == "findings"
  assert {row["rule"] for row in a11y_bad["findings"]} == {
    "NUA301",
    "NUA302",
    "NUA303",
    "NUA304",
    "NUA305",
    "NUA306",
  }

  code_clean, a11y_clean = run_driver(
    {**base_req, "command": "a11y", "a11y": True}, mode="clean"
  )
  assert code_clean == 0 and a11y_clean["status"] == "captured"
  assert not a11y_clean["findings"]

  code_wf, wf_res = run_driver(
    {**base_req, "command": "inspect", "wireframe": True}, mode="clean"
  )
  assert code_wf == 0 and wf_res["status"] == "captured"
  assert wf_res["captures"][0]["wireframe_screenshot"].endswith("-wireframe.png")
  assert Path(wf_res["captures"][0]["wireframe_screenshot"]).is_file()

  sheet = measure.parse_sheet(measure.DEFAULT_SHEET.read_text(encoding="utf-8"))
  assert sheet["font-mono"].startswith('"Monaspace Neon"')
  assert measure.MIN_INK_RATIO == 0.75
  density_report = {
    "width": 1280,
    "elements": [
      {
        "selector": "#header",
        "tag": "header",
        "bounds": {"width": 900, "height": 48},
        "inkRatio": 0.38,
        "values": {"height": "48px"},
      },
      {
        "selector": ".report-toolbar",
        "tag": "div",
        "bounds": {"width": 900, "height": 48},
        "inkRatio": 0.34,
        "values": {"height": "48px", "justify-content": "space-between"},
      },
      {
        "selector": ".step-row",
        "tag": "div",
        "bounds": {"width": 1200, "height": 40},
        "inkRatio": 0.60,
        "maxSiblingGap": 960,
        "values": {"height": "40px", "padding-left": "16px"},
      },
      {
        "selector": "#branch-select",
        "tag": "select",
        "bounds": {"width": 560, "height": 40},
        "values": {"height": "40px"},
      },
      {
        "selector": "#modal-close",
        "tag": "button",
        "iconOnly": True,
        "bounds": {"width": 32, "height": 44},
        "values": {"width": "32px", "height": "44px"},
      },
    ],
  }
  density_findings = measure.check_density(density_report)
  assert [row["rule"] for row in density_findings] == [
    "NUM205",
    "NUM206",
    "NUM207",
    "NUM208",
  ]
  assert density_findings[0]["selector"] == ".step-row"
  density_file = tmp_path / "density-report.json"
  density_file.write_text(json.dumps(density_report), encoding="utf-8")
  assert measure.main(["density", str(density_file)]) == 1
  assert measure.main(["check", "-d", str(density_file)]) == 1
  assert measure.main(["check", str(density_file)]) == 0
  clip_overlap_report = {
    "width": 1280,
    "elements": [
      {
        "selector": ".clipped-card",
        "tag": "div",
        "bounds": {"width": 200, "height": 40},
        "clientWidth": 200,
        "scrollWidth": 280,
        "clientHeight": 40,
        "scrollHeight": 40,
        "values": {"overflow": "hidden"},
      },
      {
        "selector": "#btn-a",
        "tag": "button",
        "bounds": {"width": 80, "height": 40},
        "siblingOverlap": "#btn-b",
        "values": {},
      },
    ],
  }
  co_findings = measure.check_density(clip_overlap_report)
  assert [row["rule"] for row in co_findings] == ["NUM209", "NUM210"]

  font_proj = tmp_path / "FontProject"
  font_proj.mkdir()
  (font_proj / "DemoSans.woff2").write_bytes(b"wOF2demo")
  (font_proj / "style.css").write_text(
    '@font-face { font-family: "Demo Sans"; src: url("/assets/DemoSans.woff2") format("woff2"); font-weight: 400; }\n'
    ':root { --font-sans: "Demo Sans", system-ui, sans-serif; --font-mono: "Demo Mono", monospace; }\n',
    encoding="utf-8",
  )
  typo = annotate.resolve_project_typography(font_proj)
  assert typo["font_sans"].startswith('"Demo Sans"')
  assert typo["font_mono"].startswith('"Demo Mono"')
  assert typo["embedded_fonts"] == 1
  assert "data:font/woff2;base64," in typo["font_faces_css"]

  panel_a = tmp_path / "panel-a.png"
  panel_b = tmp_path / "panel-b.png"
  panel_a.write_bytes(
    annotate.encode_png(80, 60, bytearray([24, 24, 28, 255] * (80 * 60)))
  )
  panel_b.write_bytes(
    annotate.encode_png(80, 60, bytearray([28, 36, 28, 255] * (80 * 60)))
  )
  board_out = tmp_path / "board-out.png"
  board_proc = subprocess.run(
    [
      sys.executable,
      str(SCRIPT),
      "board",
      "--project",
      str(font_proj),
      "-t",
      "Comparison Board",
      "-p",
      f"Before={panel_a}",
      "-p",
      f"After={panel_b}@0,0,60,50",
      "-c",
      "1,Updated layout,green",
      "-W",
      "-o",
      str(board_out),
    ],
    text=True,
    capture_output=True,
    check=False,
  )
  assert board_proc.returncode == 0, board_proc.stderr or board_proc.stdout
  board_res = json.loads(board_proc.stdout)
  assert board_res["tool"] == "board"
  assert board_res["status"] == "composed"
  assert board_res["panels"] == 2
  assert board_res["font_family"].startswith('"Demo Sans"')
  assert board_out.is_file()
  assert board_res["wireframe_output"].endswith("board-out-wireframe.png")
  assert Path(board_res["wireframe_output"]).is_file()
  bw, bh, _ = annotate.decode_png(board_out.read_bytes())
  assert bw > 80 and bh > 60
  assert nuu.DEVICE_BREAKPOINTS == uiux.DEVICE_BREAKPOINTS
  assert callable(nuu.main) and callable(uiux.main)


def test_design_boards_and_html_typography(tmp_path):
  html_font_proj = tmp_path / "HtmlFontProject"
  html_font_proj.mkdir()
  (html_font_proj / "Inter-Regular.woff2").write_bytes(b"wOF2inter400")
  (html_font_proj / "Inter-Bold.woff2").write_bytes(b"wOF2inter700")
  (html_font_proj / "index.html").write_text(
    "<!doctype html><html><head><style>\n"
    '@font-face { font-family: "Inter"; src: url("Inter-Regular.woff2") format("woff2"); font-weight: 400; }\n'
    '@font-face { font-family: "Inter"; src: url("Inter-Bold.woff2") format("woff2"); font-weight: 700; }\n'
    ':root { --sans: "Inter", system-ui, sans-serif; --mono: "JetBrains Mono", monospace; }\n'
    ".btn { padding: 6px 12px; border-radius: 6px; background: #2563eb; color: #fff; }\n"
    "</style></head><body><script>\n"
    'const svg = (d) => `<svg viewBox="0 0 16 16" width="16" height="16">${d}</svg>`;\n'
    "const ICONS = {\n"
    "  plus: svg('<path d=\"M8 3v10M3 8h10\"/>'),\n"
    "};\n"
    "</script></body></html>",
    encoding="utf-8",
  )
  typo = annotate.resolve_project_typography(html_font_proj)
  assert typo["embedded_fonts"] == 2
  assert typo["font_sans"].startswith('"Inter"')
  assert typo["font_mono"].startswith('"JetBrains Mono"')

  shots_dir = html_font_proj / "shots"
  shots_dir.mkdir()
  dash_png = shots_dir / "dashboard.png"
  dash_png.write_bytes(
    annotate.encode_png(1360, 200, bytearray([18, 22, 30, 255] * (1360 * 200)))
  )
  comp_dir = html_font_proj / "components"
  comp_dir.mkdir()
  (comp_dir / "buttons.html").write_text(
    '<button class="btn"><span data-icon="plus"></span>New repository</button>',
    encoding="utf-8",
  )

  spec_path = html_font_proj / "boards.json"
  spec_data = {
    "stylesheet": "index.html",
    "icons": {"file": "index.html", "table": "ICONS"},
    "shots": {"dashboard": "shots/dashboard.png"},
    "boards": [
      {
        "name": "views",
        "title": "Example views",
        "lede": "Full views at 1360 px, two to a row.",
        "wide": True,
        "frames": [
          {
            "label": "Default view",
            "sub": "Five remembered repos.",
            "shot": "dashboard",
            "width": 1360,
          },
          {
            "label": "Second view",
            "sub": "Native resolution preserved.",
            "shot": "dashboard",
          },
        ],
      },
      {
        "name": "components",
        "title": "Global components",
        "lede": "Every control in every state.",
        "frames": [
          {
            "label": "Buttons",
            "sub": "Primary, default, ghost, icon.",
            "html": "components/buttons.html",
          }
        ],
      },
    ],
  }
  spec_path.write_text(json.dumps(spec_data, indent=2), encoding="utf-8")

  out_dir = tmp_path / "design-out"
  proc = subprocess.run(
    [
      sys.executable,
      str(SCRIPT),
      "board",
      "--project",
      str(html_font_proj),
      "-T",
      "design",
      "-s",
      str(spec_path),
      "-o",
      str(out_dir),
    ],
    text=True,
    capture_output=True,
    check=False,
  )
  assert proc.returncode == 0, proc.stderr or proc.stdout
  res = json.loads(proc.stdout)
  assert res["status"] == "composed"
  assert res["type"] == "design"
  assert res["embedded_fonts"] == 2
  assert res["font_family"].startswith('"Inter"')
  assert len(res["boards"]) == 2
  views_png = out_dir / "views.png"
  comp_png = out_dir / "components.png"
  assert views_png.is_file() and comp_png.is_file()
  vw, vh, _ = annotate.decode_png(views_png.read_bytes())
  cw, ch, _ = annotate.decode_png(comp_png.read_bytes())
  assert vw == 2816 and vh > 200
  assert 200 < cw <= 1536 and ch > 80

  only_dir = tmp_path / "only-out"
  only_proc = subprocess.run(
    [
      sys.executable,
      str(SCRIPT),
      "board",
      "--project",
      str(html_font_proj),
      "--type",
      "design",
      "--only",
      "components",
      "--spec",
      str(spec_path),
      "--output",
      str(only_dir),
    ],
    text=True,
    capture_output=True,
    check=False,
  )
  assert only_proc.returncode == 0, only_proc.stderr or only_proc.stdout
  assert (only_dir / "components.png").is_file()
  assert not (only_dir / "views.png").exists()

  bad_shot_spec = html_font_proj / "bad-shot.json"
  bad_shot_spec.write_text(
    json.dumps(
      {
        **spec_data,
        "shots": {"missing_dash": "shots/does-not-exist.png"},
      }
    ),
    encoding="utf-8",
  )
  bad_shot_proc = subprocess.run(
    [
      sys.executable,
      str(SCRIPT),
      "board",
      "--project",
      str(html_font_proj),
      "-T",
      "design",
      "-s",
      str(bad_shot_spec),
      "-o",
      str(tmp_path / "bad-shot-out"),
    ],
    text=True,
    capture_output=True,
    check=False,
  )
  assert bad_shot_proc.returncode == 1
  assert "missing_dash" in bad_shot_proc.stdout

  no_style_html = html_font_proj / "nostyle.html"
  no_style_html.write_text(
    "<!doctype html><html><body>No style</body></html>", encoding="utf-8"
  )
  bad_style_spec = html_font_proj / "bad-style.json"
  bad_style_spec.write_text(
    json.dumps({**spec_data, "stylesheet": "nostyle.html"}),
    encoding="utf-8",
  )
  bad_style_proc = subprocess.run(
    [
      sys.executable,
      str(SCRIPT),
      "board",
      "--project",
      str(html_font_proj),
      "-T",
      "design",
      "-s",
      str(bad_style_spec),
      "-o",
      str(tmp_path / "bad-style-out"),
    ],
    text=True,
    capture_output=True,
    check=False,
  )
  assert bad_style_proc.returncode == 1
  assert "nostyle.html" in bad_style_proc.stdout
