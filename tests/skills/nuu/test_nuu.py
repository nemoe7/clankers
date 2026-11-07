"""Exercise the public UI workflow and preserve product authority."""

import json
import subprocess
import sys
from pathlib import Path

import annotate
import measure
import nuu

SCRIPT = Path(nuu.__file__).resolve()


def _chromium_ready() -> str | None:
  try:
    import playwright.sync_api  # noqa: F401

    return nuu.resolve_chromium_executable()
  except Exception:
    return None


def test_ui_workflow_preserves_sources_and_reports_missing_evidence(tmp_path):
  root = tmp_path / "product"
  root.mkdir()
  css = root / "style.css"
  css.write_text(":root {--brand: #123456; --gap: 16px;}\n", encoding="utf-8")
  page = root / "index.html"
  page.write_text('<img src="art.svg"><input><button>Send</button>\n', encoding="utf-8")

  def run(*args, expected=0, cwd=root):
    process = subprocess.run(
      [sys.executable, str(SCRIPT), *args],
      cwd=cwd,
      capture_output=True,
      text=True,
      encoding="utf-8",
      check=False,
    )
    assert process.returncode == expected, process.stderr or process.stdout
    return process

  doc_res = nuu.doctor(root)
  assert doc_res["catalog"]["files"] > 0
  assert not doc_res["catalog"]["mismatches"]
  doc_cli = run("doctor")
  assert "# Nuu Doctor (`v0.2.0`)" in doc_cli.stdout

  exact = nuu.search("healthcare dashboard", dataset="products", limit=5)
  assert exact["results"] and not exact["fallback"]
  assert len(exact["results"]) <= 5
  assert all(row["matched_terms"] for row in exact["results"])
  search_cli = run("search", "healthcare dashboard", "-d", "products", "-l", "5")
  assert "# Catalog Search: `healthcare dashboard`" in search_cli.stdout
  assert "`fallback=False`" in search_cli.stdout
  fallback = nuu.search("zzznomatchzzzx", dataset="products")
  assert fallback["fallback"]
  assert not any(row["matched_terms"] for row in fallback["results"])

  before = {path: path.read_bytes() for path in (css, page)}
  lint_initial = nuu.lint(root)
  assert {row["rule"] for row in lint_initial["findings"]} >= {
    "ACC001",
    "ACC002",
    "DOC001",
  }
  assert all(row["line"] > 0 and row["evidence"] for row in lint_initial["findings"])
  lint_cli = run("lint", expected=1)
  assert "`ACC001`" in lint_cli.stdout and "`DOC001`" in lint_cli.stdout

  page.write_text(
    '<img src="art.svg" alt=""><label>Field<input></label>\n', encoding="utf-8"
  )
  assert {row["rule"] for row in nuu.lint(root)["findings"]} == {"DOC001"}
  missing_doc_audit = run("audit", expected=3)
  assert "`DOC001`" in missing_doc_audit.stdout

  nuu_toml = root / "nuu.toml"
  nuu_toml.write_text('[paths]\ndoc = "specs/ui-design.md"\n', encoding="utf-8")
  custom_missing = nuu.lint(root)["findings"]
  assert len(custom_missing) == 1 and custom_missing[0]["rule"] == "DOC001"
  assert custom_missing[0]["evidence"] == "Missing specs/ui-design.md"
  custom_doc = root / "specs" / "ui-design.md"
  custom_doc.parent.mkdir(exist_ok=True)
  custom_doc.write_text("# Custom Design\n", encoding="utf-8")
  assert not nuu.lint(root)["findings"]
  nuu_toml.unlink()
  custom_doc.unlink()
  design_doc = root / "docs" / "design.md"
  design_doc.parent.mkdir(exist_ok=True)
  design_doc.write_text("# Design\n", encoding="utf-8")
  assert not nuu.lint(root)["findings"]

  # Retired NU* codes are rejected as unknown suppression codes.
  page.write_text('<img src="art.svg"> <!-- nonuu: NUL0010 -->\n', encoding="utf-8")
  assert nuu.lint(root)["findings"]
  page.write_text('<img src="art.svg"> <!-- nonuu: ACC001 -->\n', encoding="utf-8")
  suppressed_lint = nuu.lint(root)
  assert not suppressed_lint["findings"]
  assert suppressed_lint["suppressions"] and suppressed_lint["marks"]
  assert suppressed_lint["suppressions"][0]["rule"] == "ACC001"

  collected = run("collect", expected=0)
  assert "# Marker Inventory" in collected.stdout
  assert "nonuu: ACC001" in collected.stdout

  # Recipe marker validation (nuurecipe: + RCP001)
  page.write_text(
    '<img src="art.svg"> <!-- nonuu: ACC001 -->\n'
    "<!-- nuurecipe: relative-timestamps -->\n",
    encoding="utf-8",
  )
  assert (
    run("collect", expected=0).stdout.count("`nuurecipe: relative-timestamps` (ok)")
    == 1
  )
  page.write_text(
    '<img src="art.svg"> <!-- nonuu: ACC001 -->\n'
    "<!-- nuurecipe: no-such-recipe-slug -->\n",
    encoding="utf-8",
  )
  bad_recipe = run("collect", expected=1)
  assert "`RCP001`" in bad_recipe.stdout
  page.write_text('<img src="art.svg"> <!-- nonuu: ACC001 -->\n', encoding="utf-8")

  css.write_text(
    before[css].decode() + "button:focus {outline: none !important;}\n",
    encoding="utf-8",
  )
  assert {row["rule"] for row in nuu.lint(root)["findings"]} == {"ACC201"}
  css.write_text(
    before[css].decode() + "button:focus {outline: none;} /* nonuu: ACC201 */\n",
    encoding="utf-8",
  )
  assert not nuu.lint(root)["findings"]
  css.write_text(
    before[css].decode() + "button:hover {padding: 12px 24px;}\n", encoding="utf-8"
  )
  assert {row["rule"] for row in nuu.lint(root)["findings"]} == {"ACC204"}
  css.write_text(
    before[css].decode() + "button:hover {padding: 12px 24px;} /* nonuu: ACC204 */\n",
    encoding="utf-8",
  )
  assert not nuu.lint(root)["findings"]
  css.write_bytes(before[css])

  page.write_text(
    '<button aria-label="Close">'
    '<svg class="lucide lucide-x" width="16" height="16" viewBox="0 0 24 24" '
    'stroke="currentColor" stroke-linecap="round"><path d="M18 6 6 18"/></svg>'
    "</button>"
    '<button aria-label="Custom">'
    '<svg width="20" height="20" viewBox="0 0 10 10"><circle cx="5" cy="5" r="4"/></svg>'
    "</button>\n",
    encoding="utf-8",
  )
  icon_lint = nuu.lint(root)
  assert icon_lint["icons"]["status"] == "checked"
  assert icon_lint["icons"]["ladder"] == ["lucide", "simple-icons", "phosphor"]
  assert icon_lint["icons"]["counts"] == {"lucide": 1, "custom": 1}
  assert {row["rule"] for row in icon_lint["icons"]["findings"]} == {
    "ICN001",
    "ICN002",
    "ICN101",
  }
  icon_audit_cli = run("audit", expected=3)
  assert "unrun (exit 3)" in icon_audit_cli.stdout

  css_icon = root / "select-icon.css"
  css_icon.write_text(
    "select { background-image: linear-gradient(to top right, transparent 38%, currentColor 38%); }\n"
    ".custom-icon { mask-image: url('data:image/svg+xml;utf8,<svg/>'); }\n",
    encoding="utf-8",
  )
  css_icon_lint = nuu.lint(root)
  css_nui002 = [
    row
    for row in css_icon_lint["icons"]["findings"]
    if row["rule"] == "ICN002" and row["path"].endswith("select-icon.css")
  ]
  assert len(css_nui002) == 2
  css_icon.unlink()

  page.write_text('<img src="art.svg"> <!-- nonuu: ACC001 -->\n', encoding="utf-8")
  before[page] = page.read_bytes()

  # [[assets]] validation in nuu.toml v2
  asset = root / "art.svg"
  asset.write_text('<svg xmlns="http://www.w3.org/2000/svg"/>', encoding="utf-8")
  nuu_toml.write_text(
    '[[assets]]\npath = "art.svg"\nsource = "local original"\n'
    'license = "MIT"\nattribution = "test fixture"\n',
    encoding="utf-8",
  )
  assert not nuu.lint(root)["findings"]
  asset.write_text('<svg onload="alert(1)"/>', encoding="utf-8")
  assert {r["rule"] for r in nuu.lint(root)["findings"]} == {"ICN001"}
  nuu_toml.unlink()
  asset.unlink()

  assert run(
    "search",
    "-f",
    "https://example.com/art.svg",
    "-o",
    str(root / "new.svg"),
    expected=2,
  )
  assert not (root / "new.svg").exists()

  # Internal Python extract helper remains available while retired from CLI
  assert nuu.extract(root)["tokens"]
  ref_extract = nuu.extract(SCRIPT.parent.parent / "references")
  assert [row["value"] for row in ref_extract["breakpoints"]] == [
    "68em",
    "60em",
    "30em",
    "24em",
  ]
  retired_extract = subprocess.run(
    [sys.executable, str(SCRIPT), "extract"],
    cwd=tmp_path,
    capture_output=True,
    text=True,
    encoding="utf-8",
    check=False,
  )
  assert retired_extract.returncode == 2

  ruler_proc = run("measure", "--from", "0,0", "--to", "16,24", "-k", "8")
  assert "# Measurement" in ruler_proc.stdout
  assert "`16 x 24 px`" in ruler_proc.stdout

  audit = run("audit", expected=3)
  assert "unrun (exit 3)" in audit.stdout
  assert all(path.read_bytes() == value for path, value in before.items())


def test_browser_rejects_unsafe_requests_before_dependency_checks(tmp_path):
  (tmp_path / "docs").mkdir()
  (tmp_path / "docs" / "design.md").write_text("# Design\n", encoding="utf-8")
  out_dir = tmp_path / "evidence"
  for bad_url in (
    "file:///etc/passwd",
    "https://user:password@example.com",
    "javascript:alert(1)",
  ):
    res = subprocess.run(
      [
        sys.executable,
        str(SCRIPT),
        "audit",
        "-u",
        bad_url,
        "-d",
        str(out_dir),
      ],
      cwd=tmp_path,
      text=True,
      encoding="utf-8",
      capture_output=True,
      check=False,
    )
    assert res.returncode == 2
  assert not out_dir.exists()

  help_res = subprocess.run(
    [sys.executable, str(SCRIPT), "--help"],
    cwd=tmp_path,
    text=True,
    encoding="utf-8",
    capture_output=True,
    check=False,
  )
  assert help_res.returncode == 0
  for cmd_name in (
    "audit",
    "walk",
    "measure",
    "annotate",
    "board",
    "lint",
    "collect",
    "search",
    "doctor",
  ):
    assert cmd_name in help_res.stdout
  assert not SCRIPT.with_name("browser.cjs").exists()
  assert not SCRIPT.with_name("uiux.py").exists()

  bad_toml = tmp_path / "nuu.toml"
  bad_toml.write_text("[project\nname = 'broken'\n", encoding="utf-8")
  syn = subprocess.run(
    [sys.executable, str(SCRIPT), "lint", "-c", str(bad_toml)],
    cwd=tmp_path,
    text=True,
    encoding="utf-8",
    capture_output=True,
    check=False,
  )
  assert syn.returncode == 1
  assert f"{bad_toml.resolve()}:1:" in syn.stderr

  unknown_project_warning = "unknown config key 'project'"
  bad_toml.write_text("[project]\nunknown_custom = 1\n", encoding="utf-8")
  unk = subprocess.run(
    [sys.executable, str(SCRIPT), "lint", "-c", str(bad_toml)],
    cwd=tmp_path,
    text=True,
    encoding="utf-8",
    capture_output=True,
    check=False,
  )
  assert unk.returncode == 0
  assert unknown_project_warning in unk.stderr

  bad_toml.write_text(
    '[project]\nunknown_custom = 1\n\n[checks.severity]\nTYP101 = "ignore"\n',
    encoding="utf-8",
  )
  sch = subprocess.run(
    [sys.executable, str(SCRIPT), "lint", "-c", str(bad_toml)],
    cwd=tmp_path,
    text=True,
    encoding="utf-8",
    capture_output=True,
    check=False,
  )
  assert sch.returncode == 1
  assert unknown_project_warning in sch.stderr
  assert "TYP101" in sch.stderr
  assert f"{bad_toml.resolve()}:5:" in sch.stderr


def test_live_python_playwright_audit_and_annotate(tmp_path):
  import http.server
  import threading

  import pytest

  chromium_bin = _chromium_ready()
  if not chromium_bin:
    pytest.skip("Playwright/Chromium runtime not configured")

  proj = tmp_path / "live-proj"
  (proj / "docs").mkdir(parents=True)
  (proj / "docs" / "design.md").write_text("# Design\n", encoding="utf-8")
  (proj / "nuu.toml").write_text(
    '[audit]\nschemes = ["dark"]\n'
    'viewports = [{ name = "desktop", width = 1920, height = 957, report = true },'
    ' { name = "phone", width = 411, height = 799, mobile = true, touch = true, report = true }]\n',
    encoding="utf-8",
  )
  html_bytes = (
    b"<!doctype html><html data-theme='dark'><head><title>Live</title><style>"
    b"body{margin:0;padding:16px;background:#08090b;color:#f3f4f6;font:16px/24px sans-serif}"
    b"#cta{min-width:80px;min-height:44px;padding:8px 16px;border-radius:6px;background:#2563eb;color:#fff;border:0}"
    b"</style></head><body><main><h1>Live Page</h1><button id='cta'>Save changes</button></main></body></html>"
  )

  class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
      self.send_response(200)
      self.send_header("Content-Type", "text/html; charset=utf-8")
      self.end_headers()
      self.wfile.write(html_bytes)

    def log_message(self, *_args):
      pass

  with http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_port}"
    try:
      art_dir = tmp_path / "live-artifacts"
      res = subprocess.run(
        [
          sys.executable,
          str(SCRIPT),
          "audit",
          "-c",
          str(proj / "nuu.toml"),
          "-u",
          url,
          "-d",
          str(art_dir),
          "-x",
          chromium_bin,
        ],
        cwd=proj,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
      )
      assert res.returncode in {0, 1}, res.stderr or res.stdout
      assert "# UI Audit" in res.stdout
      assert (art_dir / "1920x957-dark-no-preference.png").is_file()
      assert (art_dir / "411x799-dark-no-preference.png").is_file()

      live_ann_png = tmp_path / "live-cta-annotated.png"
      ann_res = subprocess.run(
        [
          sys.executable,
          str(SCRIPT),
          "annotate",
          "-c",
          str(proj / "nuu.toml"),
          "-u",
          url,
          "-s",
          "#cta",
          "-n",
          "#cta,1,Save button,green",
          "-o",
          str(live_ann_png),
          "-x",
          chromium_bin,
        ],
        cwd=proj,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
      )
      assert ann_res.returncode == 0, ann_res.stderr or ann_res.stdout
      assert live_ann_png.is_file()
    finally:
      server.shutdown()
      thread.join()


def test_rendered_public_flow_and_live_evidence(tmp_path):
  import http.server
  import threading

  import pytest

  chromium_bin = _chromium_ready()
  if not chromium_bin:
    pytest.skip("Playwright/Chromium runtime not configured")

  proj = tmp_path / "overlay-proj"
  (proj / "docs").mkdir(parents=True)
  (proj / "docs" / "design.md").write_text("# Design\n", encoding="utf-8")
  (proj / "nuu.toml").write_text(
    "[[audit.viewports]]\n"
    "width = 411\n"
    "height = 799\n"
    "mobile = true\n"
    "touch = true\n"
    "report = true\n",
    encoding="utf-8",
  )
  (proj / "index.html").write_text(
    """<!doctype html><html data-theme="dark"><head>
<meta name="viewport" content="width=device-width,initial-scale=1"><style>
body{margin:0;padding:16px;font:16px/24px Inter,sans-serif;background:#17171a;color:#f3f4f6}
#no-surface{position:fixed;top:40px;left:24px;width:120px;height:28px;background:transparent}
#edge-right{position:fixed;top:96px;left:360px;width:120px;height:28px;background:#202026}
#placeholder{margin-top:140px}
</style></head><body>
<h1>Overlay Check</h1>
<div id="no-surface" role="tooltip">No surface</div>
<div id="edge-right" role="tooltip">Clipped right</div>
<p id="placeholder">Lorem ipsum sample copy</p>
<button id="unlabeled" aria-labelledby="missing-ref"></button>
</body></html>""",
    encoding="utf-8",
  )

  class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
      super().__init__(*args, directory=str(proj), **kwargs)

    def log_message(self, *_args):
      pass

  with http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
      cfg_info = nuu.load_nuu_config(proj, proj / "nuu.toml")
      live_res = nuu.run_live_audit(
        f"http://127.0.0.1:{server.server_port}/index.html",
        cfg_info=cfg_info,
        artifacts_dir=tmp_path / "overlay-art",
        executable=chromium_bin,
        timeout_sec=10,
      )
      rules = {row["rule"] for row in live_res["findings"]}
      assert {"ACC003", "ACC004", "ACC203", "HRC203"} <= rules
      assert (tmp_path / "overlay-art" / ".gitignore").read_text(
        encoding="utf-8"
      ).strip() == "*"
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

  with http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_port}"

    def run(route, destination, expected):
      result = subprocess.run(
        [
          sys.executable,
          str(SCRIPT),
          "search",
          "-f",
          url + route,
          "-o",
          destination,
          "-A",
        ],
        cwd=tmp_path,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
      )
      assert result.returncode == expected, result.stderr or result.stdout
      return result

    try:
      ok_res = run("/asset", "art.svg", 0)
      assert "# Fetched Asset Receipt" in ok_res.stdout
      assert (tmp_path / "art.svg").read_bytes() == payload
      before = list(requests)
      run("/asset", "art.svg", 1)
      assert requests == before
      assert (tmp_path / "art.svg").read_bytes() == payload
      run("/unsafe", "blocked.svg", 1)
      assert not (tmp_path / "blocked.svg").exists()
      before = list(requests)
      run("/asset", "../outside.svg", 1)
      assert requests == before
      assert not (tmp_path.parent / "outside.svg").exists()
    finally:
      server.shutdown()
      thread.join()


def test_ready_selector_and_rendered_a11y_pass_and_annotate(tmp_path):
  from annotate import decode_png, encode_png

  src_png = tmp_path / "source.png"
  pixels = bytearray([240, 244, 248, 255] * (80 * 60))
  original_bytes = encode_png(80, 60, pixels)
  src_png.write_bytes(original_bytes)
  out_png = tmp_path / "annotated.png"
  proc = subprocess.run(
    [
      sys.executable,
      str(SCRIPT),
      "annotate",
      "-i",
      str(src_png),
      "-o",
      str(out_png),
      "-b",
      "4,4,30,20,#2563eb",
      "-b",
      "10,10,40,25,red",
      "-l",
      "8,28,CTA,amber",
      "-l",
      "12,12,HERO,blue",
      "-a",
      "5,5,50,40,green",
      "-n",
      "60,20,1,FIX,red",
    ],
    cwd=tmp_path,
    text=True,
    encoding="utf-8",
    capture_output=True,
    check=False,
  )
  assert proc.returncode == 0, proc.stderr or proc.stdout
  assert "# Annotation Complete" in proc.stdout
  assert "- Scale: `2`" in proc.stdout
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
      "-i",
      str(src_png),
      "-o",
      str(scaled_png),
      "-S",
      "3",
      "-n",
      "40,30,1,BIG,red",
    ],
    cwd=tmp_path,
    text=True,
    encoding="utf-8",
    capture_output=True,
    check=False,
  )
  assert scaled_proc.returncode == 0, scaled_proc.stderr or scaled_proc.stdout
  assert "- Scale: `3`" in scaled_proc.stdout

  inplace = subprocess.run(
    [
      sys.executable,
      str(SCRIPT),
      "annotate",
      "-i",
      str(src_png),
      "-o",
      str(src_png),
      "-b",
      "1,1,10,10",
    ],
    cwd=tmp_path,
    text=True,
    encoding="utf-8",
    capture_output=True,
    check=False,
  )
  assert inplace.returncode == 2
  assert src_png.read_bytes() == original_bytes

  ann_text = Path(annotate.__file__).read_text(encoding="utf-8")
  assert 'colorScheme: "dark"' in ann_text or 'color_scheme="dark"' in ann_text
  assert 'color_scheme="dark"' in (SCRIPT.parent / "walk.py").read_text(
    encoding="utf-8"
  )

  sheet = measure.parse_sheet(measure.DEFAULT_SHEET.read_text(encoding="utf-8"))
  assert sheet["font-mono"].startswith('"Monaspace Neon"')
  assert measure.MIN_INK_RATIO == 0.75
  assert measure.MAIN_MIN_INK_RATIO == 0.40
  for vp_w, main_pass_ratio in ((1920, 0.47), (1080, 0.83), (958, 0.94)):
    main_ok = measure.check_density(
      {
        "width": vp_w,
        "elements": [
          {
            "selector": "main#content",
            "tag": "main",
            "bounds": {"width": vp_w, "height": 640},
            "ink_ratio": main_pass_ratio,
          },
          {
            "selector": "#app-root",
            "tag": "div",
            "role": "main",
            "bounds": {"width": vp_w, "height": 640},
            "ink_ratio": 0.40,
          },
        ],
      }
    )
    assert main_ok == []
  main_sparse = measure.check_density(
    {
      "width": 1920,
      "elements": [
        {
          "selector": "main#content",
          "tag": "main",
          "bounds": {"width": 1920, "height": 640},
          "ink_ratio": 0.31,
        }
      ],
    }
  )
  assert len(main_sparse) == 1
  assert main_sparse[0]["rule"] == "SPC201"
  assert "< 0.40" in main_sparse[0]["evidence"]
  for narrow_w in (855, 411):
    assert (
      measure.check_density(
        {
          "width": narrow_w,
          "elements": [
            {
              "selector": "main#content",
              "tag": "main",
              "bounds": {"width": narrow_w, "height": 640},
              "ink_ratio": 0.25,
            }
          ],
        }
      )
      == []
    )
  density_report = {
    "width": 1280,
    "elements": [
      {
        "selector": "#header",
        "tag": "header",
        "bounds": {"width": 900, "height": 48},
        "ink_ratio": 0.38,
        "values": {"height": "48px"},
      },
      {
        "selector": ".report-toolbar",
        "tag": "div",
        "bounds": {"width": 900, "height": 48},
        "ink_ratio": 0.34,
        "values": {"height": "48px", "justify-content": "space-between"},
      },
      {
        "selector": ".step-row",
        "tag": "div",
        "bounds": {"width": 1200, "height": 40},
        "ink_ratio": 0.60,
        "max_sibling_gap": 960,
        "values": {"height": "40px", "padding-left": "16px"},
      },
      {
        "selector": "#branch-select",
        "tag": "select",
        "bounds": {"width": 560, "height": 40},
        "row_slack": 320,
        "values": {"height": "40px"},
      },
      {
        "selector": "#modal-close",
        "tag": "button",
        "icon_only": True,
        "bounds": {"width": 32, "height": 44},
        "values": {"width": "32px", "height": "44px"},
      },
    ],
  }
  density_findings = measure.check_density(density_report)
  assert [row["rule"] for row in density_findings] == [
    "SPC201",
    "SPC202",
    "SPC203",
    "HRC102",
  ]
  assert density_findings[0]["selector"] == ".step-row"
  assert (
    measure.check(
      density_report,
      measure.parse_sheet(measure.DEFAULT_SHEET.read_text(encoding="utf-8")),
    )
    == []
  )
  clip_overlap_report = {
    "width": 1280,
    "elements": [
      {
        "selector": ".clipped-card",
        "tag": "div",
        "bounds": {"width": 200, "height": 40},
        "client_width": 200,
        "scroll_width": 280,
        "client_height": 40,
        "scroll_height": 40,
        "values": {"overflow": "hidden"},
      },
      {
        "selector": "#btn-a",
        "tag": "button",
        "bounds": {"width": 80, "height": 40},
        "sibling_overlap": "#btn-b",
        "values": {},
      },
    ],
  }
  co_findings = measure.check_density(clip_overlap_report)
  assert [row["rule"] for row in co_findings] == ["SPC204", "SPC205"]

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
  (font_proj / "nuu.toml").write_text(
    '[paths]\nstylesheet = "style.css"\n', encoding="utf-8"
  )
  board_proc = subprocess.run(
    [
      sys.executable,
      str(SCRIPT),
      "board",
      "-c",
      str(font_proj / "nuu.toml"),
      "-t",
      "Comparison Board",
      "-p",
      f"Before={panel_a}",
      "-p",
      f"After={panel_b}@0,0,60,50",
      "-n",
      "1,Updated layout,green",
      "-W",
      "-o",
      str(board_out),
    ],
    cwd=font_proj,
    text=True,
    encoding="utf-8",
    capture_output=True,
    check=False,
  )
  assert board_proc.returncode == 0, board_proc.stderr or board_proc.stdout
  assert "# Board Composed" in board_proc.stdout
  assert '"Demo Sans"' in board_proc.stdout
  assert board_out.is_file()
  assert (tmp_path / "board-out-wireframe.png").is_file()
  bw, bh, _ = annotate.decode_png(board_out.read_bytes())
  assert bw > 80 and bh > 60
  assert callable(nuu.main)


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

  toml_proj = tmp_path / "TomlFontProject"
  toml_proj.mkdir()
  (toml_proj / "CustomFont.woff2").write_bytes(b"wOF2custom")
  (toml_proj / "nuu.toml").write_text(
    "[fonts]\n"
    "sans = '\"Custom Toml Sans\", sans-serif'\n"
    "mono = '\"Custom Toml Mono\", monospace'\n"
    'files = ["CustomFont.woff2"]\n\n'
    "[annotate]\n"
    "scale = 3\n\n"
    "[board]\n"
    "columns = 1\n"
    "wireframe = true\n",
    encoding="utf-8",
  )
  toml_typo = annotate.resolve_project_typography(toml_proj)
  assert toml_typo["font_sans"].startswith('"Custom Toml Sans"')
  assert toml_typo["font_mono"].startswith('"Custom Toml Mono"')
  assert toml_typo["embedded_fonts"] == 1
  assert toml_typo["config_path"] == str(toml_proj / "nuu.toml")
  toml_src = toml_proj / "shot.png"
  toml_src.write_bytes(
    annotate.encode_png(60, 40, bytearray([20, 24, 32, 255] * (60 * 40)))
  )
  toml_ann = annotate.annotate_image(
    toml_src,
    toml_proj / "shot-ann.png",
    boxes=["4,4,20,20,red"],
    project=toml_proj,
    renderer="bitmap",
  )
  assert toml_ann["scale"] == 3
  assert toml_ann["font_family"].startswith('"Custom Toml Sans"')
  doc_toml = nuu.doctor(toml_proj)
  assert doc_toml["configuration"]["status"] == "checked"
  assert doc_toml["configuration"]["path"] == str(toml_proj / "nuu.toml")

  trans_src = toml_proj / "transparent.png"
  trans_src.write_bytes(annotate.encode_png(20, 20, bytearray([0, 0, 0, 0] * 400)))
  trans_dst = toml_proj / "transparent-ann.png"
  annotate.annotate_image(
    trans_src,
    trans_dst,
    boxes=["2,2,10,10,red"],
    project=toml_proj,
    renderer="bitmap",
  )
  _, _, trans_rgba = annotate.decode_png(trans_dst.read_bytes())
  assert trans_rgba[3] == 0
  inside_idx = (5 * 20 + 5) * 4
  assert trans_rgba[inside_idx + 3] == 0
  border_idx = (2 * 20 + 2) * 4
  assert trans_rgba[border_idx] == 225 and trans_rgba[border_idx + 3] == 255
  assert not hasattr(annotate, "GLYPHS")

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

  spec_path = html_font_proj / "boards.toml"
  spec_toml = """stylesheet = "index.html"

[icons]
file = "index.html"
table = "ICONS"

[shots]
dashboard = "shots/dashboard.png"

[[boards]]
name = "views"
title = "Example views"
lede = "Full views at 1360 px, two to a row."
wide = true

[[boards.frames]]
label = "Default view"
sub = "Five remembered repos."
shot = "dashboard"
width = 1360

[[boards.frames]]
label = "Second view"
sub = "Native resolution preserved."
shot = "dashboard"

[[boards]]
name = "components"
title = "Global components"
lede = "Every control in every state."

[[boards.frames]]
label = "Buttons"
sub = "Primary, default, ghost, icon."
html = "components/buttons.html"
"""
  spec_path.write_text(spec_toml, encoding="utf-8")

  retired_design = subprocess.run(
    [
      sys.executable,
      str(SCRIPT),
      "board",
      "-T",
      "design",
      "-s",
      str(spec_path),
      "-o",
      str(tmp_path / "retired-design"),
    ],
    cwd=html_font_proj,
    text=True,
    encoding="utf-8",
    capture_output=True,
    check=False,
  )
  assert retired_design.returncode == 2

  out_dir = tmp_path / "design-out"
  proc = subprocess.run(
    [
      sys.executable,
      str(SCRIPT),
      "board",
      "-s",
      str(spec_path),
      "-o",
      str(out_dir),
    ],
    cwd=html_font_proj,
    text=True,
    encoding="utf-8",
    capture_output=True,
    check=False,
  )
  assert proc.returncode == 0, proc.stderr or proc.stdout
  assert "# Board Composed" in proc.stdout
  assert '"Inter"' in proc.stdout
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
      "--only",
      "components",
      "--spec",
      str(spec_path),
      "--output",
      str(only_dir),
    ],
    cwd=html_font_proj,
    text=True,
    encoding="utf-8",
    capture_output=True,
    check=False,
  )
  assert only_proc.returncode == 0, only_proc.stderr or only_proc.stdout
  assert (only_dir / "components.png").is_file()
  assert not (only_dir / "views.png").exists()

  bad_shot_spec = html_font_proj / "bad-shot.toml"
  bad_shot_spec.write_text(
    spec_toml.replace(
      'dashboard = "shots/dashboard.png"',
      'missing_dash = "shots/does-not-exist.png"',
    ),
    encoding="utf-8",
  )
  bad_shot_proc = subprocess.run(
    [
      sys.executable,
      str(SCRIPT),
      "board",
      "-s",
      str(bad_shot_spec),
      "-o",
      str(tmp_path / "bad-shot-out"),
    ],
    cwd=html_font_proj,
    text=True,
    encoding="utf-8",
    capture_output=True,
    check=False,
  )
  assert bad_shot_proc.returncode == 1
  assert "dashboard" in bad_shot_proc.stdout or "missing_dash" in bad_shot_proc.stdout

  no_style_html = html_font_proj / "nostyle.html"
  no_style_html.write_text(
    "<!doctype html><html><body>No style</body></html>", encoding="utf-8"
  )
  bad_style_spec = html_font_proj / "bad-style.toml"
  bad_style_spec.write_text(
    spec_toml.replace('stylesheet = "index.html"', 'stylesheet = "nostyle.html"'),
    encoding="utf-8",
  )
  bad_style_proc = subprocess.run(
    [
      sys.executable,
      str(SCRIPT),
      "board",
      "-s",
      str(bad_style_spec),
      "-o",
      str(tmp_path / "bad-style-out"),
    ],
    cwd=html_font_proj,
    text=True,
    encoding="utf-8",
    capture_output=True,
    check=False,
  )
  assert bad_style_proc.returncode == 1
  assert "nostyle.html" in bad_style_proc.stdout

  import walk

  walk.clear_steps()
  demo = walk.Demo("http://127.0.0.1:1500")
  demo.sign_in(False)
  demo.wait_until_checked(False)
  assert demo.signed_in is False
  assert demo.checked is False
  assert demo.url_for(1500) == "http://127.0.0.1:1500"
  assert demo.url_for("/settings") == "http://127.0.0.1:1500/settings"

  class FakePage:
    def __init__(self, viewport=(1280, 800)):
      self.viewport = viewport
      self.visited = []
      self._listeners = {}

    def on(self, event, callback):
      self._listeners[event] = callback

    def goto(self, url, wait_until="networkidle"):
      self.visited.append((url, wait_until))

    def screenshot(self, **_kwargs):
      return b"\x89PNG\r\n\x1a\nfake"

  @walk.step("desktop")
  def sample_step(w: walk.Walker, d: walk.Demo) -> None:
    w.goto(1500)
    assert d.url_for(2500) == "http://127.0.0.1:2500"

  walk_out = tmp_path / "walk-out"
  step_results = walk.run_steps_with_factory(
    lambda vp: FakePage(vp), demo, out_dir=walk_out
  )
  assert len(step_results) == 1
  assert step_results[0]["step"] == "sample_step"
  assert step_results[0]["device"] == "desktop"
  assert Path(step_results[0]["screenshot"]).is_file()

  views = walk.capture_views(
    walk.Walker(FakePage(), demo),
    demo,
    {"dashboard": 1500, "signed-out": lambda w, _d: w.goto(2500)},
  )
  assert set(views) == {"dashboard", "signed-out"}
  walk.clear_steps()

  default_nuu_toml = SCRIPT.parent.parent / "references" / "nuu.toml"
  assert default_nuu_toml.is_file()
  default_cfg = annotate.load_nuu_config(config_path=default_nuu_toml)
  assert default_cfg["path"] == str(default_nuu_toml)
  assert default_cfg["config"]["fonts"]["prefer_project_css"] is True
  assert default_cfg["config"]["fonts"]["sans"] == ""
  assert default_cfg["config"]["fonts"]["mono"] == ""
  vps = default_cfg["config"]["audit"]["viewports"]
  assert [vp["width"] for vp in vps] == [1920, 1080, 958, 855, 411]
  assert [vp["width"] for vp in vps if vp["report"]] == [1920, 411]
  assert nuu.REPORT_WIDTHS == (1920, 411)
  audit_report_md = (SCRIPT.parent.parent / "references" / "audit-report.md").read_text(
    encoding="utf-8"
  )
  assert "Desktop maximized (`1920x957`)" in audit_report_md
  assert "Phone portrait (`411x799`)" in audit_report_md
  assert "`1920x957` / `411x799`" in audit_report_md
  assert "| Location | Width | Before | After |" in audit_report_md
  assert "| Area | Before | After | Action / Disposition |" in audit_report_md
  assert "1080x2437" not in audit_report_md
  assert "`1280` / `360`" not in audit_report_md
  assert "finding-1-before-after-board.png" in audit_report_md
  assert "visual-1-before-after-board.png" in audit_report_md
  assert (
    "## Captures\n\nOmit this section unless full-viewport captures are needed."
    in audit_report_md
  )
  assert "## Captures (" not in audit_report_md

  bare_proj = tmp_path / "BareNoCssProject"
  bare_proj.mkdir()
  bare_typo = annotate.resolve_project_typography(bare_proj)
  assert "Inter" in bare_typo["font_sans"]
  assert "Monaspace Neon" in bare_typo["font_mono"]

  chromium_bin = _chromium_ready()
  if chromium_bin:
    chr_src = toml_proj / "chr-shot.png"
    chr_src.write_bytes(
      annotate.encode_png(120, 80, bytearray([20, 24, 32, 255] * (120 * 80)))
    )
    chr_dst = toml_proj / "chr-shot-ann.png"
    chr_ann = annotate.annotate_image(
      chr_src,
      chr_dst,
      boxes=["8,8,40,30,red"],
      labels=["8,44,Header gap,amber"],
      callouts=["60,24,1,Overflow,red"],
      project=toml_proj,
      renderer="auto",
    )
    assert chr_ann["renderer"] == "chromium"
    assert chr_ann["font_family"].startswith('"Custom Toml Sans"')

  crop_dst = toml_proj / "shot-cropped.png"
  crop_ann = annotate.annotate_image(
    toml_src,
    crop_dst,
    boxes=["4,4,20,20,red"],
    crop="4,4,30,20",
    project=toml_proj,
    renderer="bitmap",
  )
  assert crop_ann["width"] == 30
  assert crop_ann["height"] == 20
  cw_dec, ch_dec, _ = annotate.decode_png(crop_dst.read_bytes())
  assert (cw_dec, ch_dec) == (30, 20)

  (toml_proj / "dev.css").write_text(
    "/* nuu-deviation: compact-toolbar: single-row 34px controls */\n"
    "/* nuu-deviation: dense-log-header-row */\n"
    "/* nuu-deviation: keep 30px height on inline filter pills */\n"
    ".toolbar { height: 34px; outline: none; }\n",
    encoding="utf-8",
  )
  dev_lint = nuu.lint(toml_proj)
  assert any(
    "compact-toolbar" in d["reason"] and "34px" in d["reason"]
    for d in dev_lint["deviations"]
  )
  assert any("30px height" in d["reason"] for d in dev_lint["deviations"])
  sheet_tokens = measure.parse_sheet(
    (SCRIPT.parent.parent / "references" / "style.css").read_text(encoding="utf-8")
  )
  spacing_report = {
    "width": 1920,
    "elements": [
      {
        "selector": "a.nav-link",
        "values": {
          "width": "127.656px",
          "height": "18.5px",
          "line-height": "16.5px",
          "outline-width": "3px",
          "padding-top": "8px",
          "padding-left": "6px",
        },
      }
    ],
  }
  spacing_findings = measure.check(spacing_report, sheet_tokens)
  assert len(spacing_findings) == 1
  assert "padding-left" in spacing_findings[0]
  assert all(
    isinstance(f.get("rule_description"), str) and f["rule_description"]
    for f in dev_lint["findings"]
  )
  collect_dev = subprocess.run(
    [
      sys.executable,
      str(SCRIPT),
      "collect",
      "-c",
      str(toml_proj / "nuu.toml"),
    ],
    cwd=toml_proj,
    capture_output=True,
    text=True,
    encoding="utf-8",
    check=False,
  )
  assert collect_dev.returncode == 0, collect_dev.stdout + collect_dev.stderr
  assert "compact-toolbar" in collect_dev.stdout
  assert "34px" in collect_dev.stdout

  custom_focus_proj = tmp_path / "custom-focus-repo"
  (custom_focus_proj / ".git").mkdir(parents=True)
  (custom_focus_proj / "docs" / "sub").mkdir(parents=True)
  (custom_focus_proj / "docs" / "sub" / "design.md").write_text(
    "# Sub Design\n", encoding="utf-8"
  )
  sub_assets = custom_focus_proj / "skills" / "assets"
  sub_assets.mkdir(parents=True)
  (sub_assets / "style.css").write_text(
    ":focus-visible { outline: 2px solid #e5bb8b; border-color: #524d47; }\n"
    ".shell:focus-within { border-color: #524d47; }\n"
    ".shell textarea { outline: none; }\n"
    ":root:not([data-keyboard-nav='true']) :focus-visible { outline: 0; }\n",
    encoding="utf-8",
  )
  sub_lint = nuu.lint(sub_assets)
  assert not sub_lint["findings"], sub_lint["findings"]

  bounded_findings = measure.check_density(
    {
      "width": 640,
      "elements": [
        {
          "selector": "#log-search",
          "tag": "input",
          "input_type": "search",
          "row_slack": 58,
          "bounds": {"x": 16, "y": 95, "width": 566, "height": 34},
          "values": {"width": "566px", "height": "34px"},
        }
      ],
    }
  )
  assert len(bounded_findings) == 1
  assert bounded_findings[0]["rule"] == "SPC203"
  assert bounded_findings[0]["bounds"] == {
    "x": 16.0,
    "y": 95.0,
    "width": 566.0,
    "height": 34.0,
  }
  assert (
    measure.check_density(
      {
        "width": 1280,
        "elements": [
          {
            "selector": "#full-url",
            "tag": "input",
            "input_type": "text",
            "row_slack": 0,
            "bounds": {"x": 0, "y": 0, "width": 1280, "height": 40},
            "values": {"width": "1280px", "height": "40px"},
          }
        ],
      }
    )
    == []
  )
  slack_findings = measure.check_density(
    {
      "width": 1280,
      "elements": [
        {
          "selector": "#short-filter",
          "tag": "input",
          "input_type": "text",
          "row_slack": 400,
          "bounds": {"x": 0, "y": 0, "width": 320, "height": 40},
          "values": {"width": "320px", "height": "40px"},
        }
      ],
    }
  )
  assert len(slack_findings) == 1
  assert slack_findings[0]["rule"] == "SPC203"
  assert "400 px" in slack_findings[0]["evidence"]
  assert (
    measure.check_density(
      {
        "width": 1280,
        "elements": [
          {
            "selector": "#paired-input",
            "tag": "input",
            "input_type": "text",
            "row_slack": 0,
            "bounds": {"x": 0, "y": 0, "width": 320, "height": 40},
            "values": {"width": "320px", "height": "40px"},
          }
        ],
      }
    )
    == []
  )
  for exempt_type in ("checkbox", "button"):
    assert (
      measure.check_density(
        {
          "width": 1280,
          "elements": [
            {
              "selector": f"#exempt-{exempt_type}",
              "tag": "input",
              "input_type": exempt_type,
              "row_slack": 400,
              "bounds": {"x": 0, "y": 0, "width": 24, "height": 24},
              "values": {"width": "24px", "height": "24px"},
            }
          ],
        }
      )
      == []
    )

  auto_src = toml_proj / "auto-src.png"
  auto_src.write_bytes(
    annotate.encode_png(200, 140, bytearray([24, 24, 28, 255] * (200 * 140)))
  )
  auto_dst = toml_proj / "auto-cropped.png"
  auto_ann = annotate.annotate_image(
    auto_src,
    auto_dst,
    boxes=["20,16,120,36,amber"],
    callouts=["28,24,1,Search input width,amber"],
    crop="auto",
    project=toml_proj,
    renderer="bitmap",
  )
  assert auto_ann["width"] >= 120
  assert auto_ann["height"] >= 60
  assert auto_ann["crop"][0] <= 20
  assert auto_ann["crop"][1] <= 16
  assert auto_ann["crop"][0] + auto_ann["crop"][2] >= 140

  nuu_skill_dir = SCRIPT.resolve().parent.parent
  nuu_typo = annotate.resolve_project_typography(nuu_skill_dir)
  assert "Inter" in nuu_typo["font_sans"]
  assert "Basel Grotesk" not in nuu_typo["font_sans"]
  assert nuu_typo["embedded_fonts"] == 0
  assert nuu_typo["config_path"] == str(nuu_skill_dir / "nuu.toml")

  ts_proj = tmp_path / "ts-proj"
  (ts_proj / "docs").mkdir(parents=True)
  (ts_proj / "docs" / "design.md").write_text("# Design\n", encoding="utf-8")
  (ts_proj / "index.html").write_text(
    "<div><span>2026-10-26T02:20:06</span>"
    "<p>Updated 2026-10-26 02:20:06 UTC</p>"
    "<code>2026-10-26T02:20:06</code></div>\n",
    encoding="utf-8",
  )
  (ts_proj / "app.js").write_text(
    "stamp.textContent = entry.at || '';\n"
    "const fmt = new Intl.DateTimeFormat('en-US', { timeZone: 'UTC' });\n"
    "clock.textContent = `${clockTime(now.toISOString())}`;\n",
    encoding="utf-8",
  )
  ts_res = nuu.lint(ts_proj)
  ts_findings = [row for row in ts_res["findings"] if row["rule"] == "HRC201"]
  assert len(ts_findings) == 4
  (ts_proj / "index.html").write_text(
    "<div><span>5min ago</span><code>2026-10-26T02:20:06</code></div>\n",
    encoding="utf-8",
  )
  (ts_proj / "app.js").write_text(
    "stamp.textContent = entry.at ? time(entry.at) : '';\n",
    encoding="utf-8",
  )
  assert nuu.lint(ts_proj)["findings"] == []

  assert nuu.DEVICE_BREAKPOINTS == ("68em", "60em", "30em", "24em")
  walk_parsed = walk.build_parser().parse_args(
    ["-x", "/custom/chromium", "http://127.0.0.1:8000"]
  )
  assert walk_parsed.executable == "/custom/chromium"


def test_nuu_list_indent_and_overlap_rules(tmp_path):
  project = tmp_path / "list-project"
  docs = project / "docs"
  docs.mkdir(parents=True)
  (docs / "design.md").write_text("# Design\n", encoding="utf-8")
  css = project / "style.css"
  css.write_text(
    "ul#list { list-style-position: inside; padding-inline-start: 0; }\n",
    encoding="utf-8",
  )
  bad_lint = nuu.lint(project)
  assert any(row["rule"] == "TYP202" for row in bad_lint["findings"])
  css.write_text("ul#list { list-style-type: disc; }\n", encoding="utf-8")
  unreset_lint = nuu.lint(project)
  assert any(
    row["rule"] == "TYP202" and "lacks --indent" in row["evidence"]
    for row in unreset_lint["findings"]
  )
  css.write_text(
    "ul#list { --indent: 2ch; padding-inline-start: 2ch; "
    "list-style-position: outside; list-style-type: disc; }\n",
    encoding="utf-8",
  )
  assert nuu.lint(project)["findings"] == []
  assert "TYP202" in nuu.KNOWN_NUU_RULES
  assert "TYP203" in nuu.KNOWN_NUU_RULES

  tokens = measure.parse_sheet(measure.DEFAULT_SHEET.read_text(encoding="utf-8"))
  list_report = {
    "elements": [
      {
        "selector": "ul#list",
        "tag": "ul",
        "values": {
          "--indent": "2ch",
          "padding-inline-start": "18px",
          "padding-left": "18px",
        },
        "list_indent": {
          "indent": "2ch",
          "padding_inline_start": 18,
          "ch_px": 9,
          "list_style_position": "outside",
          "list_style_type": "disc",
          "direction": "ltr",
          "items": [{"selector": "li:first-child", "line_starts": [100, 100.4, 100.8]}],
        },
      }
    ]
  }
  assert measure.check(list_report, tokens) == []
  misaligned = json.loads(json.dumps(list_report))
  misaligned["elements"][0]["list_indent"]["items"][0]["line_starts"] = [100, 106]
  assert any(
    finding.startswith("TYP203 ") for finding in measure.check(misaligned, tokens)
  )
  unverified = {
    "elements": [{"selector": "ul#list", "values": {"padding-inline-start": "18px"}}]
  }
  assert any(
    "padding-inline-start is 18px" in finding
    for finding in measure.check(unverified, tokens)
  )

  clipping_findings = measure.check_density(
    {
      "elements": [
        {
          "selector": "#clip",
          "values": {"overflow": "hidden", "white-space": "nowrap"},
          "scroll_width": 300,
          "client_width": 120,
        }
      ]
    }
  )
  assert any(finding["rule"] == "SPC204" for finding in clipping_findings)

  overlap_findings = measure.check_density(
    {
      "elements": [],
      "overlaps": {
        "status": "checked",
        "pairs": [{"first": "#first", "second": "#second", "relation": "separate"}],
      },
    }
  )
  assert [finding["rule"] for finding in overlap_findings] == ["SPC205"]

  tokens = measure.parse_sheet(
    (SCRIPT.parent.parent / "references" / "style.css").read_text(encoding="utf-8")
  )
  lh_ok = measure.check(
    {
      "width": 1280,
      "elements": [
        {
          "selector": "h2",
          "tag": "h2",
          "values": {"font-size": "24px", "line-height": "28.8px"},
        },
        {
          "selector": "p",
          "tag": "p",
          "values": {"font-size": "14px", "line-height": "20.3px"},
        },
      ],
    },
    tokens,
  )
  assert lh_ok == []
  lh_bad = measure.check(
    {
      "width": 1280,
      "elements": [
        {
          "selector": "h2",
          "tag": "h2",
          "values": {"font-size": "20px", "line-height": "32px"},
        },
        {
          "selector": "p",
          "tag": "p",
          "values": {"font-size": "14px", "line-height": "15.4px"},
        },
      ],
    },
    tokens,
  )
  assert len([f for f in lh_bad if f.startswith("TYP101 ")]) == 2
  ls_ok = measure.check(
    {
      "width": 1280,
      "elements": [
        {
          "selector": "h1",
          "tag": "h1",
          "values": {"font-size": "24px", "letter-spacing": "-0.36px"},
        },
        {
          "selector": "p",
          "tag": "p",
          "values": {"font-size": "14px", "letter-spacing": "0px"},
        },
      ],
    },
    tokens,
  )
  assert ls_ok == []
  ls_bad = measure.check(
    {
      "width": 1280,
      "elements": [
        {
          "selector": "h1",
          "tag": "h1",
          "values": {"font-size": "24px", "letter-spacing": "-1.2px"},
        },
        {
          "selector": "p",
          "tag": "p",
          "values": {"font-size": "14px", "letter-spacing": "0.56px"},
        },
      ],
    },
    tokens,
  )
  assert len([f for f in ls_bad if f.startswith("TYP102 ")]) == 2
  align_ok = measure.check(
    {
      "width": 1280,
      "elements": [
        {
          "selector": "p.body",
          "tag": "p",
          "line_count": 5,
          "values": {"text-align": "start"},
        },
        {
          "selector": "p.hero",
          "tag": "p",
          "line_count": 2,
          "values": {"text-align": "center"},
        },
      ],
    },
    tokens,
  )
  assert align_ok == []
  align_bad = measure.check(
    {
      "width": 1280,
      "elements": [
        {
          "selector": "p.center",
          "tag": "p",
          "line_count": 4,
          "values": {"text-align": "center"},
        },
        {
          "selector": "p.just",
          "tag": "p",
          "line_count": 3,
          "values": {"text-align": "justify"},
        },
        {
          "selector": "h2.card-title",
          "tag": "h2",
          "heading_body_alignment": {"heading_align": "center", "body_align": "start"},
          "values": {"text-align": "center"},
        },
      ],
    },
    tokens,
  )
  assert len([f for f in align_bad if f.startswith("TYP103 ")]) == 3
  width_ok = measure.check(
    {
      "width": 1280,
      "elements": [
        {
          "selector": "article.prose",
          "tag": "article",
          "ch_px": 8.0,
          "bounds": {"width": 520.0, "height": 80.0},
          "values": {},
        },
        {
          "selector": "p.lead",
          "tag": "p",
          "line_count": 3,
          "ch_px": 8.0,
          "bounds": {"width": 520.0, "height": 60.0},
          "values": {},
        },
      ],
    },
    tokens,
  )
  assert width_ok == []
  width_bad = measure.check(
    {
      "width": 1280,
      "elements": [
        {
          "selector": "article.prose",
          "tag": "article",
          "ch_px": 8.0,
          "bounds": {"width": 840.0, "height": 80.0},
          "values": {},
        },
        {
          "selector": "p.narrow",
          "tag": "p",
          "line_count": 3,
          "ch_px": 8.0,
          "bounds": {"width": 280.0, "height": 60.0},
          "values": {},
        },
      ],
    },
    tokens,
  )
  assert len([f for f in width_bad if f.startswith("TYP201 ")]) == 2
  hier_ok = measure.check(
    {
      "width": 1280,
      "elements": [
        {
          "selector": "section.card",
          "tag": "section",
          "card_font_sizes": ["18px", "14px"],
          "heading_hierarchy": {
            "heading_size": 18.0,
            "heading_weight": 600.0,
            "sub_size": 14.0,
            "sub_weight": 400.0,
          },
          "values": {},
        }
      ],
    },
    tokens,
  )
  assert hier_ok == []
  hier_bad = measure.check(
    {
      "width": 1280,
      "elements": [
        {
          "selector": "dialog#settings",
          "tag": "dialog",
          "card_font_sizes": ["18px", "16px", "14px"],
          "values": {},
        },
        {
          "selector": "section.card-flat",
          "tag": "section",
          "heading_hierarchy": {
            "heading_size": 14.0,
            "heading_weight": 400.0,
            "sub_size": 14.0,
            "sub_weight": 400.0,
          },
          "values": {},
        },
      ],
    },
    tokens,
  )
  assert len([f for f in hier_bad if f.startswith("HRC101 ")]) == 2
  prox_ok = measure.check(
    {
      "width": 1280,
      "elements": [
        {
          "selector": "form.stack",
          "tag": "form",
          "group_proximity": {"inter_px": 16.0, "intra_px": 8.0},
          "values": {"gap": "16px"},
        }
      ],
    },
    tokens,
  )
  assert prox_ok == []
  prox_bad = measure.check(
    {
      "width": 1280,
      "elements": [
        {
          "selector": "form.stack",
          "tag": "form",
          "group_proximity": {"inter_px": 8.0, "intra_px": 8.0},
          "values": {"gap": "8px"},
        },
        {
          "selector": "section.card",
          "tag": "section",
          "group_proximity": {"inter_px": 0.0, "intra_px": 8.0},
          "values": {},
        },
      ],
    },
    tokens,
  )
  assert len([f for f in prox_bad if f.startswith("SPC101 ")]) == 2
  core_ok = measure.check(
    {
      "width": 1280,
      "elements": [
        {
          "selector": "section.card",
          "tag": "section",
          "card_inline_insets": [16.0, 16.0, 16.0],
          "values": {
            "font-family": "system-ui, sans-serif",
            "text-transform": "none",
            "padding-left": "16px",
            "padding-right": "16px",
          },
        },
        {
          "selector": "span.eyebrow",
          "tag": "span",
          "values": {"text-transform": "uppercase"},
        },
      ],
    },
    tokens,
  )
  assert core_ok == []
  core_bad = measure.check(
    {
      "width": 1280,
      "elements": [
        {
          "selector": "section.card",
          "tag": "section",
          "card_inline_insets": [16.0, 28.0],
          "button_fill_colors": ["rgb(43, 83, 214)", "rgb(28, 122, 63)"],
          "values": {
            "font-family": "Papyrus, fantasy",
            "text-transform": "uppercase",
            "padding-left": "32px",
            "padding-right": "16px",
          },
        },
        {
          "selector": "p.body",
          "tag": "p",
          "values": {"font-style": "italic"},
        },
      ],
    },
    tokens,
  )
  assert (
    len([f for f in core_bad if f.startswith(("SPC102 ", "TYP002 ", "TYP003 "))]) == 5
  )
  assert len([f for f in core_bad if f.startswith("HRC001 ")]) == 1

  lint_proj = tmp_path / "nul008_proj"
  (lint_proj / "docs").mkdir(parents=True)
  (lint_proj / "docs" / "design.md").write_text("# Design\n", encoding="utf-8")
  (lint_proj / "bad.html").write_text(
    '<dialog><button class="button primary">Yes</button>'
    '<button class="button button--accent">Delete repo</button></dialog>\n',
    encoding="utf-8",
  )
  (lint_proj / "good.html").write_text(
    '<dialog><button class="button">Cancel</button>'
    '<button class="button button--accent">Delete repo</button></dialog>\n',
    encoding="utf-8",
  )
  lint_payload = nuu.lint(lint_proj)
  nul008 = [f for f in lint_payload["findings"] if f["rule"] == "HRC001"]
  assert len(nul008) == 2
  assert all(Path(f["path"]).name == "bad.html" for f in nul008)
  lint_res = subprocess.run(
    [sys.executable, str(SCRIPT), "lint"],
    cwd=lint_proj,
    capture_output=True,
    text=True,
    encoding="utf-8",
    check=False,
  )
  assert lint_res.returncode == 1
  assert "`HRC001`" in lint_res.stdout


def test_house_style_amendments_stay_synced():
  live_root = SCRIPT.parent.parent
  ref_root = live_root.parent / "refs" / live_root.name
  for root in (live_root, ref_root):
    css = (root / "references/style.css").read_text(encoding="utf-8")
    assert css.count("--scrollbar-thumb: #767682;") == 2
    assert css.count("--scrollbar-thumb: #767686;") == 2
    assert "padding: var(--space-2) var(--space-4);" in css
    assert ".button--danger {" in css
    assert "min-height: var(--space-5);" in css
    assert "--radius-md: 6px;" in css
    assert "--font-sans: var(--font);" in css
    assert "*, *::before" not in css.split("@media (prefers-reduced-motion: reduce)")[1]
    assert "@media (pointer: coarse)" in css
    assert "min-height: var(--touch);" in css
    assert "border-radius: 50%;" not in css

    skill = (root / "SKILL.md").read_text(encoding="utf-8")
    assert "except .eyebrow labels at 0.06em" in skill
    assert "44x44 px hit areas" in skill
    assert (
      "33. On every live Nuu audit, inspect visible dialog and floating-overlay text "
      "and controls for clipping or occlusion at every edge across the five house "
      "viewports. Check tooltip and popover surfaces for missing effective "
      "backgrounds. Report selector, viewport, bounds, clipping ancestor, and "
      "computed surface color."
    ) in skill

    modal = (root / "references/recipes/modal-manager.md").read_text(encoding="utf-8")
    assert "padding: var(--space-5);" in modal
    assert "<!-- Lucide Icons - ISC License -->" in modal
    loading = (root / "references/recipes/loading-bar.md").read_text(encoding="utf-8")
    assert "cubic-bezier(0.16" not in loading
    assert "var(--ease)" in loading
    assert "width: 1lh;" in loading
    live_dot = (root / "references/recipes/live-dot.md").read_text(encoding="utf-8")
    assert "animation: none" in live_dot
    assert "width: 1lh;" in live_dot
    assert ".dot-sm { width: 4px;" in live_dot
    assert ".dot-lg { width: 12px;" in live_dot
    table_cards = (root / "references/recipes/table-to-cards.md").read_text(
      encoding="utf-8"
    )
    assert "max-width: 60em" in table_cards
    edge_fade = (root / "references/recipes/scroll-edge-fade.md").read_text(
      encoding="utf-8"
    )
    assert "--edge-fade: 24px; --edge-ramp: 32px; --scrollbar-carve: 15px;" in edge_fade
    timestamps = (root / "references/recipes/relative-timestamps.md").read_text(
      encoding="utf-8"
    )
    assert "font-variant-numeric: tabular-nums" in timestamps
    assert "without requiring `var(--font-mono)`" in timestamps
    page_mem = (root / "references/recipes/page-memory.md").read_text(encoding="utf-8")
    assert "ACC207" in page_mem
    ranges = (root / "references/recipes/range-sliders.md").read_text(encoding="utf-8")
    assert "at most 11 major-division ticks" in ranges


def test_num208_button_group_equal_size():
  ragged_report = {
    "width": 1280,
    "elements": [
      {
        "selector": ".tab-nav",
        "tag": "nav",
        "role": "tablist",
        "toolbar_exempt": True,
        "bounds": {"x": 0, "y": 0, "width": 300, "height": 32},
        "button_group_sizes": [
          {"width": 99, "height": 32},
          {"width": 84, "height": 32},
          {"width": 68, "height": 32},
        ],
      }
    ],
  }
  findings = measure.check_density(ragged_report)
  assert [row["rule"] for row in findings] == ["HRC102"]
  assert "buttons in group do not share identical size" in findings[0]["evidence"]

  equal_report = {
    "width": 1280,
    "elements": [
      {
        "selector": ".tab-nav",
        "tag": "nav",
        "role": "tablist",
        "toolbar_exempt": True,
        "bounds": {"x": 0, "y": 0, "width": 300, "height": 32},
        "button_group_sizes": [
          {"width": 99, "height": 32},
          {"width": 99, "height": 32},
          {"width": 99, "height": 32},
        ],
      }
    ],
  }
  assert measure.check_density(equal_report) == []


def test_measure_review_severity_and_heading_boundary(tmp_path):
  report_payload = {
    "width": 1280,
    "elements": [
      {
        "selector": "h1",
        "tag": "h1",
        "values": {
          "font-size": "32px",
          "line-height": "48px",
          "letter-spacing": "-0.96px",
        },
      },
      {
        "selector": "article.prose",
        "tag": "article",
        "ch_px": 8,
        "bounds": {"width": 320},
        "values": {},
      },
    ],
  }
  tokens = measure.parse_sheet(measure.DEFAULT_SHEET.read_text(encoding="utf-8"))
  found = measure.check(report_payload, tokens)
  codes = {f.split()[0] for f in found}
  assert codes == {"TYP101", "TYP201"}
  assert "TYP102" not in codes

  default_sev = nuu.check_severities(tmp_path)
  assert default_sev["TYP101"] == "review"
  assert default_sev["TYP201"] == "review"

  (tmp_path / "docs").mkdir()
  (tmp_path / "docs" / "design.md").write_text("# Design\n", encoding="utf-8")
  (tmp_path / "nuu.toml").write_text(
    '[checks.severity]\nTYP101 = "error"\n', encoding="utf-8"
  )
  strict_sev = nuu.check_severities(tmp_path)
  assert strict_sev["TYP101"] == "error"

  (tmp_path / "nuu.toml").write_text(
    '[checks.severity]\nTYP101 = "ignore"\n', encoding="utf-8"
  )
  invalid = subprocess.run(
    [sys.executable, str(SCRIPT), "lint", "-c", str(tmp_path / "nuu.toml")],
    cwd=tmp_path,
    capture_output=True,
    text=True,
    encoding="utf-8",
    check=False,
  )
  assert invalid.returncode == 1
  assert "TYP101" in invalid.stderr

  # Verify $CHROMIUM_FONTS directory -> FONTCONFIG_FILE + FONTCONFIG_PATH
  fake_fonts = tmp_path / "fonts"
  fake_fonts.mkdir()
  (fake_fonts / "fonts.conf").write_text("<fontconfig/>", encoding="utf-8")
  fake_lib = tmp_path / "lib"
  fake_lib.mkdir()
  env_map = nuu.chromium_launch_env(
    {"CHROMIUM_LIB": str(fake_lib), "CHROMIUM_FONTS": str(fake_fonts)}
  )
  assert env_map["LD_LIBRARY_PATH"].startswith(str(fake_lib.resolve()))
  assert env_map["FONTCONFIG_FILE"] == str((fake_fonts / "fonts.conf").resolve())
  assert env_map["FONTCONFIG_PATH"] == str(fake_fonts.resolve())


def test_study_ramp_and_contextual_prose_width():
  import sys

  sys.path.insert(0, str(SCRIPT.parent))
  import measure

  sheet = measure.parse_sheet(
    (SCRIPT.parent.parent / "references" / "style.css").read_text(encoding="utf-8")
  )
  assert measure.named_sizes(sheet, ramp=True) == {11, 12, 14, 16, 18, 22, 24, 28, 32}
  findings = measure.check(
    {
      "width": 1280,
      "elements": [
        {"selector": ".title", "values": {"font-size": "20px", "font-weight": "800"}}
      ],
    },
    sheet,
  )
  assert sum(f.startswith("TYP001 ") for f in findings) == 2
  assert measure.off_scale("font-size", "20px", sheet, 4)
  assert not measure.off_scale("font-size", "24px", sheet, 4)
  assert measure.off_scale("border-radius", "8px", sheet, 4)
  assert measure.off_scale("gap", "6px", sheet, 4)
  assert not measure.off_scale("gap", "8px", sheet, 4)
  assert measure.off_scale("gap", "12px", sheet, 8)
  prose = {
    "selector": ".prose",
    "tag": "p",
    "line_count": 2,
    "ch_px": 8,
    "bounds": {"width": 240},
    "values": {"max-width": "30ch"},
  }
  assert measure._body_width_finding(prose, 1280).startswith("TYP201")
  assert measure._body_width_finding({**prose, "in_card_or_dialog": True}, 1280) is None
  assert measure._body_width_finding(
    {**prose, "in_card_or_dialog": True, "values": {"max-width": "80ch"}}, 1280
  ).startswith("TYP201")


def test_severity_overrides_control_lint_and_audit_exit_codes(tmp_path):
  proj = tmp_path / "sev-proj"
  (proj / "docs").mkdir(parents=True)
  (proj / "docs" / "design.md").write_text("# Design\n", encoding="utf-8")
  (proj / "index.html").write_text(
    '<img src="hero.png"><button>Send</button>\n', encoding="utf-8"
  )
  err_run = subprocess.run(
    [sys.executable, str(SCRIPT), "lint"],
    cwd=proj,
    capture_output=True,
    text=True,
    encoding="utf-8",
    check=False,
  )
  assert err_run.returncode == 1
  (proj / "nuu.toml").write_text(
    '[checks.severity]\nACC001 = "review"\n', encoding="utf-8"
  )
  rev_run = subprocess.run(
    [sys.executable, str(SCRIPT), "lint"],
    cwd=proj,
    capture_output=True,
    text=True,
    encoding="utf-8",
    check=False,
  )
  assert rev_run.returncode == 0
  assert "`ACC001` (review)" in rev_run.stdout


def test_measure_drop_rays_and_contrast_fallback(tmp_path):
  import annotate

  # Contrast fallback ladder: (#ff3366) -> #00e5ff -> #111827 with 1 px halo.
  dark_pick = measure.select_redline_ink([(18, 19, 24)])
  assert dark_pick["hex"] == "#ff3366"
  assert dark_pick["halo"] is None
  assert not dark_pick["fallback"]
  assert dark_pick["min_contrast"] >= 3.0

  crimson_pick = measure.select_redline_ink([(225, 29, 72)])
  assert crimson_pick["hex"] == "#00e5ff"
  assert crimson_pick["halo"] == (17, 24, 39, 255)
  assert crimson_pick["fallback"]
  assert crimson_pick["min_contrast"] >= 3.0

  light_cyan_pick = measure.select_redline_ink([(180, 230, 240)])
  assert light_cyan_pick["hex"] == "#111827"
  assert light_cyan_pick["halo"] == (255, 255, 255, 255)
  assert light_cyan_pick["fallback"]
  assert light_cyan_pick["min_contrast"] >= 3.0

  custom_pick = measure.select_redline_ink([(18, 19, 24)], redline="#00e5ff")
  assert custom_pick["hex"] == "#00e5ff"
  assert custom_pick["halo"] is None

  # Synthesize a 120x80 dark PNG with an on-scale 40x24 box and an off-scale 37x19 box.
  w, h = 120, 80
  rgba = bytearray(w * h * 4)
  annotate.fill_rect(rgba, w, h, 0, 0, w, h, (18, 19, 24, 255))
  annotate.fill_rect(rgba, w, h, 12, 16, 40, 24, (40, 44, 56, 255))
  annotate.fill_rect(rgba, w, h, 64, 16, 37, 19, (225, 29, 72, 255))
  src_png = tmp_path / "source.png"
  src_png.write_bytes(annotate.encode_png(w, h, rgba))

  out_ok = tmp_path / "drop-ok.png"
  pass_status = "- Status: `pass` (exit 0)"
  pass_span = "| `drop` | `20,24,xy` | `40 x 24 px` | `True` | `#ff3366` |"
  ok_run = subprocess.run(
    [
      sys.executable,
      str(SCRIPT),
      "measure",
      "-i",
      str(src_png),
      "-d",
      "20,24",
      "-o",
      str(out_ok),
    ],
    cwd=tmp_path,
    capture_output=True,
    text=True,
    encoding="utf-8",
    check=False,
  )
  assert ok_run.returncode == 0
  assert pass_status in ok_run.stdout
  assert pass_span in ok_run.stdout
  ow, oh, _ = annotate.decode_png(out_ok.read_bytes())
  assert (ow, oh) == (w, h)

  out_bad = tmp_path / "drop-bad.png"
  fail_status = "- Status: `findings` (exit 1)"
  fallback_span = "| `drop` | `72,24,x` | `37 px` | `False` | `#00e5ff` |"
  spc_code = "`SPC001`"
  bad_run = subprocess.run(
    [
      sys.executable,
      str(SCRIPT),
      "measure",
      "-i",
      str(src_png),
      "-d",
      "72,24,x",
      "-o",
      str(out_bad),
    ],
    cwd=tmp_path,
    capture_output=True,
    text=True,
    encoding="utf-8",
    check=False,
  )
  assert bad_run.returncode == 1
  assert fail_status in bad_run.stdout
  assert fallback_span in bad_run.stdout
  assert spc_code in bad_run.stdout

  # Invalid CLI combinations exit 2. Overwriting input or out-of-bounds drop exits 1.
  missing_out = subprocess.run(
    [sys.executable, str(SCRIPT), "measure", "-i", str(src_png), "-d", "20,24"],
    cwd=tmp_path,
    capture_output=True,
    text=True,
    encoding="utf-8",
    check=False,
  )
  assert missing_out.returncode == 2

  same_io = subprocess.run(
    [
      sys.executable,
      str(SCRIPT),
      "measure",
      "-i",
      str(src_png),
      "-d",
      "20,24",
      "-o",
      str(src_png),
    ],
    cwd=tmp_path,
    capture_output=True,
    text=True,
    encoding="utf-8",
    check=False,
  )
  assert same_io.returncode == 1


def test_measure_live_devtools_tint_and_figma_guides(tmp_path):
  import http.server
  import threading

  import annotate
  import pytest

  if not _chromium_ready():
    pytest.skip("Playwright/Chromium runtime not configured")

  site = tmp_path / "measure-site"
  site.mkdir()
  (site / "index.html").write_text(
    "<!doctype html><html lang='en'><head><meta charset='utf-8'><title>Measure</title>"
    "<style>"
    "body { margin: 0; padding: 24px; background: #121318; color: #ededf2; "
    "font-family: system-ui, sans-serif; font-size: 16px; line-height: 24px; }"
    ".row { display: flex; gap: 16px; padding: 16px; background: #1a1b22; border-radius: 10px; }"
    ".btn-a, .btn-b { padding: 8px 16px; border: 0; border-radius: 6px; "
    "font-size: 14px; line-height: 20px; background: #22232c; color: #ededf2; }"
    ".bad-row { display: flex; gap: 13px; margin-top: 16px; }"
    ".icon-btn { display: inline-flex; align-items: center; gap: 8px; "
    "font-size: 14px; line-height: 20px; padding: 8px 12px; }"
    "</style></head><body>"
    "<div class='row'><button class='btn-a'>Save</button><button class='btn-b'>Cancel</button></div>"
    "<div class='bad-row'><button class='bad-a'>One</button><button class='bad-b'>Two</button></div>"
    "<button class='icon-btn'><svg width='12' height='12' viewBox='0 0 24 24'>"
    "<path d='M5 12h14'/></svg>Label</button>"
    "</body></html>\n",
    encoding="utf-8",
  )

  class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
      super().__init__(*args, directory=str(site), **kwargs)

    def log_message(self, format, *args):
      pass

  with http.server.ThreadingHTTPServer(("127.0.0.1", 0), QuietHandler) as server:
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
      url = f"http://127.0.0.1:{port}/"
      pair_png = tmp_path / "pair-ok.png"
      pair_row_expected = "| `pair-x` | `.btn-a` | `16 px` | `True` |"
      ok_res = subprocess.run(
        [
          sys.executable,
          str(SCRIPT),
          "measure",
          "-u",
          url,
          "-s",
          ".btn-a",
          "--to",
          ".btn-b",
          "-v",
          "640x360",
          "-o",
          str(pair_png),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
      )
      assert ok_res.returncode == 0
      assert pair_row_expected in ok_res.stdout
      pw, ph, _ = annotate.decode_png(pair_png.read_bytes())
      assert (pw, ph) == (640, 360)

      bad_png = tmp_path / "pair-bad.png"
      icn_code = "`ICN102`"
      bad_pair_res = subprocess.run(
        [
          sys.executable,
          str(SCRIPT),
          "measure",
          "-u",
          url,
          "-s",
          ".icon-btn",
          "--to",
          "400,203",
          "-v",
          "640x360",
          "-o",
          str(bad_png),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
      )
      assert bad_pair_res.returncode == 1
      assert icn_code in bad_pair_res.stdout
    finally:
      server.shutdown()
