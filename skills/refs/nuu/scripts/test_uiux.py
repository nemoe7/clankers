"""Exercise the public UI workflow and preserve product authority."""

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).with_name("uiux.py")


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
  context = tmp_path / "brief.json"
  result = run(
    "brief", "--task", "Review a healthcare dashboard", "--output", str(context)
  )
  assert result["unknowns"]
  assert json.loads(context.read_text(encoding="utf-8"))["task"] == result["task"]
  exact = run("search", "healthcare dashboard", "--dataset", "products")
  assert exact["results"] and not exact["fallback"]
  assert all(row["matched_terms"] for row in exact["results"])
  fallback = run("search", "zzznomatchzzzx", "--dataset", "products")
  assert fallback["fallback"]
  assert not any(row["matched_terms"] for row in fallback["results"])

  before = {path: path.read_bytes() for path in (css, page)}
  proposal = run("system", "--brief", str(context))
  assert proposal["status"] == "proposed"
  assert proposal["existing_authority"]["tokens"]
  assert not proposal["writes"]
  record = run("teach", "--create")
  authority = Path(record["authority"])
  content = authority.read_bytes()
  assert content
  repeated = run("teach", "--create")
  assert not repeated["writes"]
  assert authority.read_bytes() == content
  rejected = run("teach", "--record", "../outside.md", "--create", expected=2)
  assert rejected["status"] == "error"
  assert not (tmp_path / "outside.md").exists()

  findings = run("lint", expected=1)
  assert {row["rule"] for row in findings["findings"]} >= {"UIX001", "UIX002"}
  assert all(row["line"] > 0 and row["evidence"] for row in findings["findings"])
  page.write_text(
    '<img src="art.svg" alt=""><label>Field<input></label>\n', encoding="utf-8"
  )
  assert not run("lint")["findings"]
  page.write_text('<img src="art.svg"> <!-- noui: UIX0010 -->\n', encoding="utf-8")
  assert run("lint", expected=1)["findings"]
  page.write_text('<img src="art.svg"> <!-- noui: UIX001 -->\n', encoding="utf-8")
  assert not run("lint")["findings"]
  css.write_text(before[css].decode() + "button:focus {outline: none !important;}\n")
  assert {row["rule"] for row in run("lint", expected=1)["findings"]} == {"UIX003"}
  css.write_text(
    before[css].decode() + "button:focus {outline: none;} /* noui: UIX003 */\n"
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
  assert not run("assets", "--manifest", str(manifest))["findings"]
  asset.write_text('<svg onload="alert(1)"/>', encoding="utf-8")
  assert run("assets", "--manifest", str(manifest), expected=1)["findings"]
  assert (
    run(
      "assets",
      "--fetch",
      "https://example.com/art.svg",
      "--destination",
      "new.svg",
      expected=2,
    )["status"]
    == "error"
  )
  assert not (root / "new.svg").exists()
  assert run("extract")["tokens"]
  for mode in (
    "critique",
    "polish",
    "harden",
    "normalize",
    "animate",
    "delight",
    "distill",
    "onboard",
  ):
    report = run(mode)
    assert report["review_dimensions"]
    assert not report["writes"]
    assert report["visual_judgment"] == "not_run"
  page.write_text('<img src="art.svg">', encoding="utf-8")
  assert run("critique", expected=1)["findings"]
  page.write_bytes(before[page])
  malformed = tmp_path / "malformed.json"
  for evidence in (
    {"captures": [{"measurements": {"elements": [None]}}]},
    {"captures": [{"measurements": {"elements": [{"values": []}]}}]},
    {"captures": [{"flow": {"steps": "invalid"}}]},
  ):
    malformed.write_text(json.dumps(evidence))
    assert run("animate", "--evidence", str(malformed), expected=2)["status"] == "error"
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
:focus-visible{outline:2px solid #08c;outline-offset:2px}
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
      assert any(row["rule"] == "UIX201" for row in house["findings"])
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
