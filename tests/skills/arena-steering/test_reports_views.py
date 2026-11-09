"""Steering browser regression tests."""

from __future__ import annotations

import base64
import os
import re
import runpy
import struct
import subprocess
import threading
import zlib
from http import HTTPStatus
from pathlib import Path

import pytest
from arena_steering.display_paths import home_relative
from arena_steering.server import (
  SteeringApp,
  create_http_server,
  reload_server_handler,
)
from arena_steering.store import SqliteStore
from fixtures.reload_isolation import run_reload_in_child

ROOT = Path(__file__).resolve().parents[3]


SKILL_DIR = ROOT / "skills" / "arena-steering"


ASSETS_DIR = SKILL_DIR / "assets"


DEMO_PATH = ROOT / "maintenance" / "demo-arena-steer.py"


DEMO = runpy.run_path(str(DEMO_PATH))


seed_demo_store = DEMO["seed_demo_store"]


demo_main = DEMO["main"]


REPORT_ACKED_EVENT = "report.acked"


REPORT_ACK_SEEN_API = "markReportAckSeen"


REPORT_ACK_SEEN_PATH = "/ack-seen"


REPORT_ACKED_HANDLER = "onReportAcked"


REPORT_SUBMIT_ID = 'id="report-submit"'


REPORT_SUBMIT_FLOAT_ID = 'id="report-submit-float"'


REPORT_SUBMIT_FLOAT_CLASS = "report-submit-float"


REPORT_SUBMIT_SPACER_RULE = ".report-submit-row > #report-submit"


REPORT_SUBMIT_FLOAT_RULE = ".report-submit-float {"


CLOCK_ID = 'id="clock"'


SOURCE_FILE_UNAVAILABLE = "Source file: unavailable"


def test_reports_copy_uses_only_confirmed_selection_method() -> None:
  subprocess.run(
    ["node", str(ROOT / "tests/skills/arena-steering/fixtures/copy_report_unit.cjs")],
    cwd=ROOT,
    capture_output=True,
    check=True,
    text=True,
    encoding="utf-8",
  )


@pytest.mark.skipif(
  not os.environ.get("ARENA_STEERING_CHROMIUM"),
  reason="Set ARENA_STEERING_CHROMIUM to run the browser regression",
)
@pytest.mark.parametrize("width", [390, 1200])
def test_reports_copy_in_isolated_browser_selects_full_markdown(
  tmp_path: Path, width: int
) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore(tmp_path / "state.sqlite3")
  app = SteeringApp(store, repo_name="Reports Copy browser probe")
  body = "# Browser Copy probe\n\nPlain *Markdown* text.\n"
  app.reports.publish_report("copy-probe", "Copy probe", body)
  server = create_http_server(app, host="0.0.0.0", port=0)
  thread = threading.Thread(target=server.serve_forever, daemon=True)
  thread.start()
  try:
    with playwright.sync_playwright() as runner:
      browser = runner.chromium.launch(
        executable_path=os.environ["ARENA_STEERING_CHROMIUM"],
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage"],
      )
      try:
        page = browser.new_page(viewport={"width": width, "height": 750})
        page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
        page.locator("#tab-reports").click()
        copy_btn = page.locator("#copy-report-btn")
        copy_btn.wait_for()
        page.evaluate("""() => {
          window.__copiedSelection = null;
          document.addEventListener('copy', () => {
            const field = document.activeElement;
            window.__copiedSelection = field?.value?.slice(
              field.selectionStart, field.selectionEnd
            ) || null;
          }, { once: true });
        }""")
        copy_btn.click()
        assert page.evaluate("window.__copiedSelection") == body
        assert copy_btn.get_attribute("data-state") == "good"
        assert page.locator("textarea[readonly]").count() == 0
      finally:
        browser.close()
  finally:
    server.shutdown()
    server.server_close()
    store.close()


@pytest.mark.skipif(
  not os.environ.get("ARENA_STEERING_CHROMIUM"),
  reason="Set ARENA_STEERING_CHROMIUM to run the browser regression",
)
@pytest.mark.parametrize(("width", "height"), [(411, 799), (855, 325), (1372, 883)])
def test_nuu_repairs_checklists_reference_contrast_and_report_media(
  tmp_path: Path, width: int, height: int
) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore()
  app = SteeringApp(store, repo_name="Nuu UI repairs")
  app.tasks.create_task(
    "ref012", "Reference task", size=3, details=["Review reference"]
  )
  checklist = (
    '- [ ] Review **one** & "two" &lt;three&gt; [details](https://example.com) `ref012`\n'
    "  - [x] Nested `item`\n\nPlain ref012 and `ref012/extra` stay unlinked."
  )
  app.messages.send_message("Parent message", msg_id="cc0400", blocking=False)
  app.messages.send_message(
    checklist, msg_id="cc0401", parent_ids=["cc0400"], blocking=False
  )
  app.tasks.create_task(
    "ref013",
    "Linked task",
    size=3,
    details=["See `ref012`, plain ref012, `ref012/extra`, and ``ref012``"],
    msg_ids=["cc0401"],
  )

  def png_chunk(tag: bytes, data: bytes) -> bytes:
    return (
      struct.pack(">I", len(data))
      + tag
      + data
      + struct.pack(">I", zlib.crc32(tag + data))
    )

  row = b"\0" + b"\x64\x8c\xbe" * 240 + b"\xfa\xa0\x50" * 240
  png = (
    b"\x89PNG\r\n\x1a\n"
    + png_chunk(b"IHDR", struct.pack(">IIBBBBB", 480, 200, 8, 2, 0, 0, 0))
    + png_chunk(b"IDAT", zlib.compress(row * 200))
    + png_chunk(b"IEND", b"")
  )
  image = "data:image/png;base64," + base64.b64encode(png).decode("ascii")
  app.reports.publish_report(
    "repair",
    "Repair evidence",
    f"# Repair evidence\n\n{checklist}\n\n![Wide evidence]({image})\n\n"
    '<!-- question {"id":"note","label":"Note"} -->\nNote: ___',
  )
  server = create_http_server(app, host="0.0.0.0", port=0)
  thread = threading.Thread(target=server.serve_forever, daemon=True)
  thread.start()
  try:
    with playwright.sync_playwright() as runner:
      browser = runner.chromium.launch(
        executable_path=os.environ["ARENA_STEERING_CHROMIUM"],
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage"],
      )
      try:
        page = browser.new_page(viewport={"width": width, "height": height})
        page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
        message = page.locator('[data-msg-id="cc0401"] .message-text')
        message.wait_for()
        assert (
          message.get_by_role(
            "checkbox", name=re.compile(r'Review one & "two" <three> details ref012')
          ).count()
          == 1
        ), message.aria_snapshot()
        assert message.get_by_role("checkbox", name="Nested item").count() == 1
        assert message.get_by_role("link", name="details").count() == 1
        assert message.locator('button[data-reference-id="ref012"]').count() == 0
        assert (
          message.locator("code").filter(has_text=re.compile(r"^ref012$")).count() == 1
        )
        receipt = page.locator('.message[data-msg-id="cc0401"] .receipt')
        reference = receipt.locator(
          'button.reply-parent-chip[data-reference-id="ref013"]'
        )
        reference.wait_for()
        assert reference.get_attribute("aria-label") == "Open task ref013"
        assert reference.inner_text() == "ref013"
        assert (
          receipt.locator(
            '.reply-parent-chip[data-reference-type="task"] > code'
          ).count()
          == 1
        )
        assert (
          page.locator(
            '.message[data-msg-id="cc0401"] .message-parents '
            '.reply-parent-chip[data-reference-type="message"] > code'
          ).count()
          == 1
        )
        for interaction in (None, "hover", "focus"):
          if interaction == "hover":
            reference.hover()
          elif interaction == "focus":
            reference.focus()
          contrast = reference.evaluate("""element => {
            const rgb = color => (color.match(/[\\d.]+/g) || []).slice(0, 3).map(Number);
            const luminance = color => rgb(color).reduce((sum, value, i) => {
              const channel = value / 255;
              const linear = channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4;
              return sum + linear * [0.2126, 0.7152, 0.0722][i];
            }, 0);
          const code = element.querySelector('code');
          const color = getComputedStyle(code).color;
          const background = getComputedStyle(code).backgroundColor;
          const a = luminance(color), b = luminance(background);
          return {color, background, ratio: (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05)};
        }""")
        assert contrast["ratio"] >= 4.5, (interaction, contrast)
        page.screenshot(path=str(tmp_path / f"checklist-message-{width}.png"))

        page.locator("#tab-reports").click()
        report = page.locator("article#report.report")
        report.wait_for()
        report_checkbox = report.get_by_role(
          "checkbox", name=re.compile(r'Review one & "two" <three> details ref012')
        )
        report_checkbox.wait_for()
        assert report_checkbox.count() == 1
        assert report.get_by_role("checkbox", name="Nested item").count() == 1
        assert report.get_by_role("link", name="details").count() == 1
        assert report.locator('button[data-reference-id="ref012"]').count() == 0
        assert (
          report.locator("code").filter(has_text=re.compile(r"^ref012$")).count() == 1
        )
        assert (
          report.locator(
            'button[data-parent-type="report"][data-parent-id="repair"]'
          ).count()
          == 1
        )
        image_el = report.locator('img[alt="Wide evidence"]')
        image_el.wait_for(state="visible")
        page.wait_for_function(
          "() => document.querySelector('article#report.report img')?.naturalWidth === 480"
        )
        media = image_el.evaluate("""img => {
          const panel = img.closest('article#report.report');
          const rect = img.getBoundingClientRect(), bounds = panel.getBoundingClientRect();
          const style = getComputedStyle(img);
          return {width: rect.width, height: rect.height, right: rect.right,
            borderWidth: parseFloat(style.borderLeftWidth) + parseFloat(style.borderRightWidth),
            borderHeight: parseFloat(style.borderTopWidth) + parseFloat(style.borderBottomWidth),
            naturalWidth: img.naturalWidth, naturalHeight: img.naturalHeight,
            panelWidth: bounds.width, panelRight: bounds.right,
            scrollWidth: panel.scrollWidth, clientWidth: panel.clientWidth};
        }""")
        assert media["width"] - media["borderWidth"] <= media["naturalWidth"] + 1, media
        assert media["width"] <= media["panelWidth"] + 1, media
        assert media["right"] <= media["panelRight"] + 1, media
        assert media["scrollWidth"] <= media["clientWidth"] + 1, media
        assert (media["height"] - media["borderHeight"]) / (
          media["width"] - media["borderWidth"]
        ) == pytest.approx(media["naturalHeight"] / media["naturalWidth"], abs=0.01)
        page.screenshot(path=str(tmp_path / f"checklist-report-{width}.png"))

        page.locator("#tab-tasks").click()
        page.locator('[data-task-id="ref013"] details.task-details > summary').click()
        detail = page.locator('[data-task-id="ref013"] .task-detail').filter(
          has_text="See `ref012`"
        )
        detail.wait_for(state="visible")
        assert detail.locator('[data-reference-id="ref012"]').count() == 0
        assert "`ref012`" in detail.inner_text()
        assert (
          page.locator(
            'button[data-parent-type="task"][data-parent-id="ref013"]'
          ).count()
          == 1
        )
      finally:
        browser.close()
  finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)
    store.close()


def test_demo_script_seeds_messages_tasks_and_reports(
  tmp_path: Path, monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> None:
  if run_reload_in_child(request):
    return
  monkeypatch.chdir(tmp_path)
  code = demo_main(["--seed-only"])
  assert code == 0

  store = SqliteStore(tmp_path / "arena-state/demo/state.sqlite3")
  app = seed_demo_store(store)
  assert len(app.messages.list_messages(unread_only=False, include_hidden=True)) >= 35
  assert len(app.tasks.list_tasks(include_finished=True)) >= 40
  survey = app.messages.get_survey()
  assert len(survey["results"]) == 6
  reports = app.reports.list_reports(stale_only=False)
  assert len(reports) >= 4
  assert reports[0].seen is False
  assert reports[0].needs_answer is True
  assert reports[1].seen is True
  assert reports[1].needs_answer is False
  assert app.resolve_asset("/reports/layout-board.png") is not None
  assert app.resolve_asset("/reports/scroll-fade-demo.gif") is not None
  assert app.resolve_asset("/reports/loading-bar-demo.gif") is not None
  assert app.resolve_asset("/reports/tokens-swatch.svg") is not None
  assert app.resolve_asset("/reports/scrollspy-zones.svg") is not None
  assert app.resolve_asset("/uploads/inbox-capture.png") is not None
  assert app.resolve_asset("/uploads/ui-motion-preview.gif") is not None
  status_seen, payload_seen = app.dispatch("POST", f"/reports/{reports[0].id}/seen")
  assert status_seen == 200
  assert payload_seen["report"]["seen"] is True
  root_asset = app.resolve_asset("/")
  assert root_asset is not None
  assert f"<title>{tmp_path.name} - Steering</title>".encode() in root_asset[0]

  server = create_http_server(app, host="127.0.0.1", port=0)
  try:
    sock_fd = server.socket.fileno()
    reloaded_app = reload_server_handler(server, app)
    assert server.socket.fileno() == sock_fd
    status, health = reloaded_app.dispatch("GET", "/health")
    assert status == 200
    assert health["ok"] is True
    assert "asset_version" in health
  finally:
    server.server_close()
  store.close()


def test_report_ack_seen_live_update_assets() -> None:
  api_js = (ASSETS_DIR / "api.js").read_text(encoding="utf-8")
  assert REPORT_ACKED_EVENT in api_js
  assert REPORT_ACK_SEEN_API in api_js
  assert REPORT_ACK_SEEN_PATH in api_js
  assert REPORT_ACKED_HANDLER in api_js

  app_js = (ASSETS_DIR / "app.js").read_text(encoding="utf-8")
  assert REPORT_ACKED_HANDLER in app_js
  assert REPORT_ACK_SEEN_API in app_js
  assert "ack_seen" in app_js


def test_report_floating_submit_assets() -> None:
  reports_js = (ASSETS_DIR / "reports-view.js").read_text(encoding="utf-8")
  assert REPORT_SUBMIT_ID in reports_js
  assert REPORT_SUBMIT_FLOAT_ID in reports_js
  assert REPORT_SUBMIT_FLOAT_CLASS in reports_js
  assert "requestSubmit" in reports_js

  style_css = (ASSETS_DIR / "style.css").read_text(encoding="utf-8")
  assert REPORT_SUBMIT_SPACER_RULE in style_css
  assert "visibility: hidden;" in style_css
  assert REPORT_SUBMIT_FLOAT_RULE in style_css
  assert "position: fixed;" in style_css

  index_html = (ASSETS_DIR / "index.html").read_text(encoding="utf-8")
  assert CLOCK_ID not in index_html


@pytest.mark.skipif(
  not os.environ.get("ARENA_STEERING_CHROMIUM"),
  reason="Set ARENA_STEERING_CHROMIUM to run the browser regression",
)
@pytest.mark.parametrize("width", [390, 1200])
def test_report_answer_textareas_grow_and_enter_never_submits(
  tmp_path: Path, width: int
) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore(tmp_path / "state.sqlite3")
  app = SteeringApp(store)
  app.reports.publish_report(
    "multiline",
    "Multiline answers",
    "# Multiline answers\n\n"
    '<!-- question {"id":"text","label":"Text response"} -->\n'
    "Text response: ___\n\n"
    '<!-- question {"id":"choice","label":"Choose"} -->\n'
    'Choose one:\n- (x) First <!-- option {"label":"First"} -->\n',
  )
  server = create_http_server(app, host="0.0.0.0", port=0)
  thread = threading.Thread(target=server.serve_forever, daemon=True)
  thread.start()
  try:
    with playwright.sync_playwright() as runner:
      browser = runner.chromium.launch(
        executable_path=os.environ["ARENA_STEERING_CHROMIUM"],
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage"],
      )
      try:
        page = browser.new_page(viewport={"width": width, "height": 844})
        page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
        page.locator("#tab-reports").click()
        text = page.locator(".field-text-input")
        custom = page.locator(".custom-text-input")
        assert text.evaluate("el => el.tagName") == "TEXTAREA"
        assert custom.evaluate("el => el.tagName") == "TEXTAREA"

        text.fill("Line one")
        initial_height = text.evaluate("el => el.getBoundingClientRect().height")
        text.press("Enter")
        page.keyboard.type("Line two")
        assert text.input_value() == "Line one\nLine two"
        assert text.evaluate("el => el.getBoundingClientRect().height") > initial_height
        assert app.reports.get_report("multiline").answers == []

        custom.fill("Option one")
        custom_height = custom.evaluate("el => el.getBoundingClientRect().height")
        custom.press("Enter")
        page.keyboard.type("Option two")
        assert custom.input_value() == "Option one\nOption two"
        assert (
          custom.evaluate("el => el.getBoundingClientRect().height") > custom_height
        )
        assert app.reports.get_report("multiline").answers == []

        with page.expect_response("**/reports/multiline/answers") as response:
          page.locator("#report-submit-float").click()
        assert response.value.status == HTTPStatus.CREATED
        assert app.reports.get_report("multiline").answers[-1].values == {
          "text": "Line one\nLine two",
          "choice": "Option one\nOption two",
        }
        page.reload()
        page.locator("#tab-reports").click()
        assert text.input_value() == "Line one\nLine two"
        assert custom.input_value() == "Option one\nOption two"
        assert text.evaluate("el => el.scrollHeight <= el.clientHeight + 1")
        assert custom.evaluate("el => el.scrollHeight <= el.clientHeight + 1")
      finally:
        browser.close()
  finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)
    store.close()


@pytest.mark.skipif(
  not os.environ.get("ARENA_STEERING_CHROMIUM"),
  reason="Set ARENA_STEERING_CHROMIUM to run the browser regression",
)
@pytest.mark.parametrize("width", [390, 1200])
def test_report_custom_answer_caret_matches_text_answer_padding(
  tmp_path: Path, width: int
) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore(tmp_path / "state.sqlite3")
  app = SteeringApp(store)
  app.reports.publish_report(
    "caret-layout",
    "Caret layout",
    "# Caret layout\n\n"
    '<!-- question {"id":"text","label":"Text response"} -->\n'
    "Text response: ___\n\n"
    '<!-- question {"id":"choice","label":"Choose"} -->\n'
    'Choose one:\n- (x) First <!-- option {"label":"First"} -->\n',
  )
  server = create_http_server(app, host="0.0.0.0", port=0)
  thread = threading.Thread(target=server.serve_forever, daemon=True)
  thread.start()
  try:
    with playwright.sync_playwright() as runner:
      browser = runner.chromium.launch(
        executable_path=os.environ["ARENA_STEERING_CHROMIUM"],
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage"],
      )
      try:
        page = browser.new_page(viewport={"width": width, "height": 844})
        page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
        page.locator("#tab-reports").click()
        text = page.locator(".field-text-input")
        custom = page.locator(".custom-text-input")
        custom.wait_for()
        metrics = page.evaluate("""() => {
          function measure(selector) {
            const element = document.querySelector(selector);
            const css = getComputedStyle(element);
            return {
              left: element.getBoundingClientRect().left,
              height: element.getBoundingClientRect().height,
              minHeight: parseFloat(css.minHeight),
              inset: parseFloat(css.borderLeftWidth) + parseFloat(css.paddingLeft),
            };
          }
          return {text: measure('.field-text-input'), custom: measure('.custom-text-input')};
        }""")
        assert metrics["custom"]["inset"] == metrics["text"]["inset"]
        assert metrics["custom"]["height"] == metrics["custom"]["minHeight"]
        assert metrics["custom"]["left"] > metrics["text"]["left"] + 16
        custom.fill("An answer")
        assert custom.evaluate("element => document.activeElement === element")
        assert page.locator(".custom-toggle").is_checked()
        assert text.input_value() == ""
        page.screenshot(path=str(tmp_path / f"reports-caret-aligned-{width}.png"))
      finally:
        browser.close()
  finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=3)
    store.close()


@pytest.mark.skipif(
  not os.environ.get("ARENA_STEERING_CHROMIUM"),
  reason="Set ARENA_STEERING_CHROMIUM to run the browser regression",
)
@pytest.mark.parametrize("width", [390, 855, 1372])
def test_report_content_uses_next_nuu_type_step_without_resizing_chrome(
  tmp_path: Path, width: int
) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore(tmp_path / "state.sqlite3")
  app = SteeringApp(store)
  app.reports.publish_report(
    "type-ramp",
    "Report type ramp",
    "# Main `code` title\n\n"
    "## Section with `code`\n\n"
    "### Subheading `code`\n\n#### Minor `code`\n\n"
    "##### Smaller `code`\n\n###### Smallest `code`\n\n"
    "Body text with `inline code`.\n\n"
    "| Name | Value |\n| --- | --- |\n| One | Two |\n\n"
    "```python\nprint('hello')\n```\n\n"
    "```mermaid\nflowchart LR\n  A[Start] --> B[End]\n```\n\n"
    '<!-- question {"id":"text","label":"Text response"} -->\n'
    "Text response: ___\n\n"
    '<!-- question {"id":"choice","label":"Choose one"} -->\n'
    'Choose one:\n- (x) First <!-- option {"label":"First"} -->\n',
  )
  answer = app.reports.submit_answer("type-ramp", {"text": "Reply", "choice": "First"})
  app.reports.ack_answer("type-ramp", answer.id, "Acknowledged with `code`.")
  server = create_http_server(app, host="0.0.0.0", port=0)
  thread = threading.Thread(target=server.serve_forever, daemon=True)
  thread.start()
  try:
    with playwright.sync_playwright() as runner:
      browser = runner.chromium.launch(
        executable_path=os.environ["ARENA_STEERING_CHROMIUM"],
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage"],
      )
      try:
        page = browser.new_page(viewport={"width": width, "height": 844})
        page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
        page.locator("#tab-reports").click()
        page.locator("#report .mermaid-svg tspan").first.wait_for()
        assert page.locator("#report .field-id-chip").count() == 0
        expected = {
          "#report": 16,
          "#report h1": 32,
          "#report h2": 22,
          "#report h3": 18,
          "#report h4": 16,
          "#report h5": 12,
          "#report h6": 11,
          "#report h1 > code": 28,
          "#report h2 > code": 22,
          "#report h3 > code": 16,
          "#report h4 > code": 14,
          "#report h5 > code": 11,
          "#report h6 > code": 11,
          "#report p": 16,
          "#report p > code": 14,
          "#report table": 16,
          "#report .code-block-header": 14,
          "#report pre > code": 14,
          "#report .field-label": 16,
          "#report .option-row": 16,
          "#report .field-text-input": 16,
          "#report .custom-text-input": 16,
          "#report .mermaid-svg tspan": 14,
          "#tab-reports": 14,
          "#tab-messages": 14,
          "#tab-tasks": 14,
          ".report-toc-title": 12,
          ".report-picker-link": 12,
          "#report-status": 12,
          "#report-ack-history": 14,
          "#report-ack-history .answer.reply": 13,
          "#report-submit-float": 14,
        }
        measured = page.evaluate(
          """selectors => Object.fromEntries(
          selectors.map(selector => [selector, getComputedStyle(
            document.querySelector(selector)).fontSize])
        )""",
          list(expected),
        )
        assert measured == {
          selector: f"{size}px" for selector, size in expected.items()
        }, measured
        page.screenshot(
          path=str(tmp_path / f"report-type-ramp-{width}.png"), full_page=True
        )
        if width == 390:
          page.locator("#report .field-card.question").nth(1).screenshot(
            path=str(tmp_path / "report-field-card-390.png")
          )
      finally:
        browser.close()
  finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)
    store.close()


def test_report_navigation_preloads_on_pointer_and_keyboard_intent():
  app_js = (ASSETS_DIR / "app.js").read_text(encoding="utf-8")
  assert 'addEventListener("pointerover", preloadReport)' in app_js
  assert 'addEventListener("focusin", preloadReport)' in app_js
  assert "pendingReportLoads" in app_js
  assert "quiet: true" in app_js


@pytest.mark.skipif(
  not os.environ.get("ARENA_STEERING_CHROMIUM"),
  reason="Set ARENA_STEERING_CHROMIUM to run the browser regression",
)
def test_report_view_staleness_tracks_visible_browser_activity(tmp_path: Path) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore()
  app = SteeringApp(store, repo_name="Report view regression")
  app.reports.publish_report("one", "First report", "# First report")
  app.reports.publish_report("two", "Second report", "# Second report")

  class Clock:
    stamp = "2027-01-01T00:00:00Z"

    def now_iso(self) -> str:
      return self.stamp

  clock = Clock()
  app.reports._clock = clock
  server = create_http_server(app, host="0.0.0.0", port=0)
  thread = threading.Thread(target=server.serve_forever, daemon=True)
  thread.start()
  try:
    with playwright.sync_playwright() as runner:
      browser = runner.chromium.launch(
        executable_path=os.environ["ARENA_STEERING_CHROMIUM"],
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage"],
      )
      try:
        page = browser.new_page(viewport={"width": 1200, "height": 700})
        page.clock.install()
        page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")

        def update_before_view(route) -> None:
          body = (
            "# Latest report body\n\n"
            '<!-- question {"id":"note","label":"Note"} -->\n'
            "Note\n"
          )
          app.reports.publish_report("one", "First report", body)
          route.continue_()

        page.route("**/reports/one/seen", update_before_view, times=1)
        with page.expect_response("**/reports/one/seen", timeout=2500):
          page.locator("#tab-reports").click()
        assert store.get_report("one").last_viewed_at == clock.stamp
        page.locator('[data-report-id="one"].is-seen').wait_for(
          state="attached", timeout=1500
        )
        page.get_by_role("heading", name="Latest report body", exact=True).wait_for(
          timeout=1500
        )

        field = page.locator(".field-text-input")
        field.fill("Draft answer")
        field.focus()
        clock.stamp = "2027-01-01T00:20:00Z"
        with page.expect_response("**/reports/one/seen", timeout=2500):
          page.clock.fast_forward(31_000)
        assert store.get_report("one").last_viewed_at == clock.stamp
        page.evaluate(
          "() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))"
        )
        assert field.evaluate("element => element === document.activeElement")
        assert field.input_value() == "Draft answer"
        assert (
          page.locator("#report-status time").get_attribute("datetime")
          == "2027-01-01T00:00:00Z"
        )
        with page.expect_response("**/reports/two/seen", timeout=2500):
          page.locator('[data-report-id="two"]').click()
        with page.expect_response("**/reports/one/seen", timeout=2500):
          page.locator('[data-report-id="one"]').click()
        page.locator("#tab-messages").click()
        clock.stamp = "2027-01-01T00:40:00Z"
        page.clock.fast_forward(31_000)
        assert store.get_report("one").last_viewed_at == "2027-01-01T00:20:00Z"
        with page.expect_response("**/reports/one/seen", timeout=2500):
          page.locator("#tab-reports").click()
        assert store.get_report("one").last_viewed_at == clock.stamp
        page.screenshot(path=str(tmp_path / "report-view.png"))
      finally:
        browser.close()
  finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)
    store.close()


@pytest.mark.skipif(
  not os.environ.get("CHROMIUM_BIN"),
  reason="Set CHROMIUM_BIN for the extracted browser",
)
def test_report_toc_jump_and_top_fade_follow_scroll(tmp_path: Path) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore()
  app = SteeringApp(store, repo_name="Report TOC regression")
  text = "\n\n".join(
    ["A paragraph with enough content to make the report scroll."] * 25
  )
  app.reports.publish_report(
    "long-report",
    "Long report",
    f"# First section\n\n{text}\n\n## Middle section\n\n{text}",
  )
  server = create_http_server(app, host="0.0.0.0", port=0)
  thread = threading.Thread(target=server.serve_forever, daemon=True)
  thread.start()
  try:
    with playwright.sync_playwright() as runner:
      browser = runner.chromium.launch(
        executable_path=os.environ["CHROMIUM_BIN"],
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage"],
      )
      try:
        for name, width, height in (
          ("desktop", 1372, 883),
          ("landscape", 855, 325),
          ("mobile", 411, 799),
        ):
          page = browser.new_page(viewport={"width": width, "height": height})
          page.add_init_script("""(() => {
            const original = Element.prototype.scrollIntoView;
            Element.prototype.scrollIntoView = function(options) {
              return original.call(this, {...options, behavior: 'instant'});
            };
          })();""")
          page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
          page.locator("#tab-reports").click()
          link = page.locator(".report-toc-link").filter(has_text="Middle section")
          link.wait_for(state="attached")
          top = page.evaluate("""() => {
            const pane = document.querySelector('#view-reports');
            const fade = getComputedStyle(document.querySelector('#report-main'), '::before');
            return { remaining: pane.scrollHeight - pane.clientHeight, opacity: Number(fade.opacity) };
          }""")
          assert top["remaining"] >= 36, top
          assert top["opacity"] < 0.01, top
          target = link.get_attribute("data-toc-target")
          assert target
          if name == "desktop":
            link.click()
          else:
            link.evaluate("element => element.click()")
          page.wait_for_function("""() => {
            const pane = document.querySelector('#view-reports');
            const fade = getComputedStyle(document.querySelector('#report-main'), '::before');
            return pane.scrollTop >= 36 && Number(fade.opacity) > 0.99;
          }""")
          result = page.evaluate(
            """id => {
            const pane = document.querySelector('#view-reports');
            const heading = document.getElementById(id);
            return {
              offset: heading.getBoundingClientRect().top - pane.getBoundingClientRect().top,
              fade: parseFloat(getComputedStyle(pane).getPropertyValue('--edge-fade')),
              scrollTop: pane.scrollTop,
              topOpacity: Number(getComputedStyle(document.querySelector('#report-main'), '::before').opacity),
            };
          }""",
            target,
          )
          assert result["scrollTop"] >= 36, result
          assert result["offset"] >= result["fade"] - 1
          assert result["topOpacity"] > 0.99, result
          assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
          page.screenshot(path=str(tmp_path / f"report-toc-{name}.png"))
          page.emulate_media(reduced_motion="reduce")
          assert (
            page.evaluate("""() =>
            getComputedStyle(document.querySelector('#report-main'), '::before').content
          """)
            == "none"
          )
          page.emulate_media(reduced_motion="no-preference")
          page.evaluate("""async () => {
            const { renderReportsView } = await import('/static/assets/reports-view.js');
            renderReportsView(document.querySelector('#view-reports'), { reports: [] }, {});
          }""")
          empty = page.evaluate("""() => {
            const pane = document.querySelector('#view-reports');
            return {
              remaining: pane.scrollHeight - pane.clientHeight,
              mainExists: Boolean(document.querySelector('#report-main')),
              layoutFade: getComputedStyle(document.querySelector('.reports-layout'), '::before').content,
            };
          }""")
          assert empty["remaining"] == 0, empty
          assert not empty["mainExists"] and empty["layoutFade"] == "none", empty
          page.close()
      finally:
        browser.close()
  finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)
    store.close()


@pytest.mark.skipif(
  not os.environ.get("ARENA_STEERING_CHROMIUM"),
  reason="Set ARENA_STEERING_CHROMIUM to run the browser regression",
)
def test_reports_tab_prioritizes_attention_inside_compact_header(
  tmp_path: Path,
) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore()
  app = SteeringApp(store, repo_name="Report indicators")
  app.reports.publish_report(
    "decision",
    "Decision",
    '<!-- question {"id":"choice","label":"Choice"} -->\nChoice: ___\n',
  )
  server = create_http_server(app, host="0.0.0.0", port=0)
  thread = threading.Thread(target=server.serve_forever, daemon=True)
  thread.start()
  try:
    with playwright.sync_playwright() as runner:
      browser = runner.chromium.launch(
        executable_path=os.environ["ARENA_STEERING_CHROMIUM"],
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage"],
      )
      try:
        page = browser.new_page()
        page.set_default_timeout(5000)
        page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
        question = page.locator("#report-needs-answer")
        pip = page.locator("#report-pip")
        question.wait_for(state="visible")
        assert pip.is_hidden()

        def check_layout(state):
          for width, height in ((1372, 883), (855, 325), (411, 799), (375, 700)):
            page.set_viewport_size({"width": width, "height": height})
            geometry = page.locator("#tab-reports").evaluate("""tab => {
              const label = document.createRange();
              label.selectNodeContents(tab.firstChild);
              const text = label.getBoundingClientRect();
              const bounds = tab.getBoundingClientRect();
              const header = document.querySelector('.topbar').getBoundingClientRect();
              const hover = getComputedStyle(tab, '::before');
              const oldHeader = document.querySelector('.topbar').cloneNode(true);
              oldHeader.style.cssText = 'position:fixed;visibility:hidden;height:auto';
              const oldNav = oldHeader.querySelector('.tab-nav');
              oldNav.style.cssText = 'align-self:center;margin-block:0;align-items:center';
              document.body.append(oldHeader);
              const oldHeaderHeight = oldHeader.getBoundingClientRect().height;
              oldHeader.remove();
              const indicator = [...tab.querySelectorAll('[role="img"]')].find(el => !el.hidden);
              const icon = indicator?.getBoundingClientRect();
              const hoverHeight = parseFloat(hover.height);
              const hoverTop = bounds.top + tab.clientTop + parseFloat(hover.top) - hoverHeight / 2;
              return {
                headerHeight: header.height, oldHeaderHeight,
                textLeft: text.left, textRight: text.right,
                iconLeft: icon?.left, iconRight: icon?.right,
                tabLeft: bounds.left, tabRight: bounds.right,
                textCenter: (text.left + text.right) / 2,
                tabCenter: (bounds.left + bounds.right) / 2,
                tabTop: bounds.top, tabBottom: bounds.bottom,
                headerTop: header.top, headerBottom: header.bottom,
                hoverHeight,
                iconInsideHover: !icon || (icon.top >= hoverTop
                  && icon.bottom <= hoverTop + hoverHeight),
                iconInside: !icon || (icon.top >= bounds.top && icon.bottom <= bounds.bottom
                  && icon.left >= bounds.left && icon.right <= bounds.right),
                iconOutsideText: !icon || icon.left >= text.right || icon.right <= text.left
                  || icon.bottom <= text.top || icon.top >= text.bottom,
                topHit: document.elementFromPoint(
                  bounds.x + bounds.width / 2, bounds.top + 1)?.closest('button') === tab,
                bottomHit: document.elementFromPoint(
                  bounds.x + bounds.width / 2, bounds.bottom - 1)?.closest('button') === tab,
                tabWidths: [...document.querySelectorAll('.tab-btn')].map(el => el.getBoundingClientRect().width),
                navRight: document.querySelector('.tab-nav').getBoundingClientRect().right,
                actionsLeft: document.querySelector('.topbar-actions').getBoundingClientRect().left,
                overflow: document.documentElement.scrollWidth > innerWidth,
              };
            }""")
            assert geometry["headerHeight"] <= geometry["oldHeaderHeight"], geometry
            assert abs(geometry["textCenter"] - geometry["tabCenter"]) < 1
            assert geometry["tabTop"] == geometry["headerTop"]
            assert geometry["headerBottom"] - geometry["tabBottom"] <= 1
            assert geometry["topHit"] and geometry["bottomHit"]
            assert geometry["hoverHeight"] < geometry["tabBottom"] - geometry["tabTop"]
            assert geometry["iconInside"] and geometry["iconOutsideText"], (
              geometry["textLeft"],
              geometry["textRight"],
              geometry["iconLeft"],
              geometry["iconRight"],
              geometry["tabLeft"],
              geometry["tabRight"],
            )
            assert geometry["iconInsideHover"], geometry
            assert max(geometry["tabWidths"]) - min(geometry["tabWidths"]) < 1
            assert geometry["navRight"] < geometry["actionsLeft"]
            assert not geometry["overflow"]
            page.locator("#tab-reports").hover()
            page.screenshot(path=str(tmp_path / f"header-{state}-{width}.png"))

        check_layout("question")
        page.locator("#tab-reports").click()
        pip.wait_for(state="hidden")
        assert question.is_visible()
        check_layout("seen-question")
        page.locator("#tab-messages").click()
        answer = app.reports.submit_answer("decision", {"choice": "Yes"})
        app.reports.ack_answer("decision", answer.id, "Received")
        page.reload()
        pip.wait_for(state="visible")
        question.wait_for(state="hidden")
        assert pip.get_attribute("aria-label") == "Unseen answer acknowledgement"
        check_layout("ack")
        app.reports.publish_report("other", "Other", "# Other")
        page.reload()
        pip.wait_for(state="visible")
        assert question.is_hidden()
        assert pip.get_attribute("aria-label") == "Unread report"
        check_layout("unread")
        app.reports.publish_report(
          "pending",
          "Pending",
          '<!-- question {"id":"note","label":"Note"} -->\nNote: ___\n',
        )
        page.reload()
        question.wait_for(state="visible")
        assert pip.is_hidden()
        check_layout("priority")
        app.reports.submit_answer("pending", {"note": "Noted"})
        app.reports.mark_seen("pending")
        app.reports.mark_seen("other")
        app.reports.mark_ack_seen("decision")
        page.reload()
        question.wait_for(state="hidden")
        assert pip.is_hidden()
        check_layout("clear")
        page.locator("#tab-tasks").focus()
        page.keyboard.press("Tab")
        assert page.evaluate("document.activeElement.id") == "blocked-bash-open"
      finally:
        browser.close()
  finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)
    app._retire_store()


@pytest.mark.skipif(
  not os.environ.get("ARENA_STEERING_CHROMIUM"),
  reason="Set ARENA_STEERING_CHROMIUM to run the browser regression",
)
@pytest.mark.parametrize(
  "width,height,report_count", [(390, 844, 15), (1372, 700, 15), (1372, 900, 3)]
)
def test_long_report_acknowledgements_do_not_hide_the_report_picker(
  width: int, height: int, report_count: int, tmp_path: Path
) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore()
  app = SteeringApp(store, repo_name="Long report acknowledgement regression")
  for idx in range(1, report_count):
    app.reports.publish_report(
      f"report-{idx:02d}", f"Report {idx:02d}", f"# Report {idx:02d}"
    )
  app.reports.publish_report(
    "long-ack",
    "Long acknowledgement",
    '<!-- question {"id":"note","label":"Note"} -->\nNote: ___\n',
  )
  answer = app.reports.submit_answer("long-ack", {"note": "Reviewed"})
  app.reports.ack_answer(
    "long-ack", answer.id, "Acknowledged the report details. " * 100
  )
  server = create_http_server(app, host="0.0.0.0", port=0)
  thread = threading.Thread(target=server.serve_forever, daemon=True)
  thread.start()
  try:
    with playwright.sync_playwright() as runner:
      browser = runner.chromium.launch(
        executable_path=os.environ["ARENA_STEERING_CHROMIUM"],
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage"],
      )
      try:
        page = browser.new_page(viewport={"width": width, "height": height})
        page.set_default_timeout(5000)
        page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
        page.locator("#tab-reports").click()
        picker = page.locator("#report-picker")
        picker.locator('[data-report-id="long-ack"]').click()
        page.locator("#report-ack-history").wait_for(state="visible")
        divider = page.locator("#report-picker + .report-rail-divider")
        assert divider.count() == 1
        divider_before = divider.bounding_box()
        assert (
          page.locator("#report-ack-history").evaluate(
            "element => getComputedStyle(element).borderTopStyle"
          )
          == "none"
        )
        geometry = picker.evaluate("""element => {
          const rail = element.closest('#report-rail');
          const ack = rail.querySelector('#report-ack-history');
          return {
            height: element.clientHeight,
            rowHeight: element.querySelector('button').getBoundingClientRect().height,
            scrollHeight: element.scrollHeight,
            pickerTop: element.getBoundingClientRect().top,
            pickerBottom: element.getBoundingClientRect().bottom,
            activeTop: element.querySelector('[aria-current="true"]').getBoundingClientRect().top,
            activeBottom: element.querySelector('[aria-current="true"]').getBoundingClientRect().bottom,
            railHeight: rail.clientHeight,
            railScrollHeight: rail.scrollHeight,
            railOverflow: getComputedStyle(rail).overflowY,
            railBottom: rail.getBoundingClientRect().bottom,
            ackHeight: ack.clientHeight,
            ackScrollHeight: ack.scrollHeight,
            ackOverflow: getComputedStyle(ack).overflowY,
            ackBottom: ack.getBoundingClientRect().bottom,
            ackEndFade: ack.hasAttribute('data-scrolled-end'),
            ackMask: getComputedStyle(ack).maskImage,
          };
        }""")
        if report_count > 3:
          page.evaluate("""() => {
            document.querySelector('#report-picker').scrollTop = 0;
            document.querySelector('#report-ack-history').scrollTop = 0;
          }""")
          page.wait_for_function("""() => {
            const picker = document.querySelector('#report-picker');
            const answers = document.querySelector('#report-ack-history');
            return picker.hasAttribute('data-scrolled-end') && !picker.hasAttribute('data-scrolled-start') &&
              answers.hasAttribute('data-scrolled-end') && !answers.hasAttribute('data-scrolled-start');
          }""")
          masks = page.evaluate("""() => [
            getComputedStyle(document.querySelector('#report-picker')).maskImage,
            getComputedStyle(document.querySelector('#report-ack-history')).maskImage,
          ]""")
          assert masks[0] == masks[1], masks
          page.evaluate("""() => {
            for (const selector of ['#report-picker', '#report-ack-history']) {
              const element = document.querySelector(selector);
              element.scrollTop = (element.scrollHeight - element.clientHeight) / 2;
            }
          }""")
          page.wait_for_function("""() => ['#report-picker', '#report-ack-history'].every(selector => {
            const element = document.querySelector(selector);
            return element.hasAttribute('data-scrolled-start') && element.hasAttribute('data-scrolled-end');
          })""")
          masks = page.evaluate("""() => [
            getComputedStyle(document.querySelector('#report-picker')).maskImage,
            getComputedStyle(document.querySelector('#report-ack-history')).maskImage,
          ]""")
          assert masks[0] == masks[1], masks
        assert divider.bounding_box() == divider_before
        page.screenshot(path=str(tmp_path / f"report-switch-long-ack-{width}.png"))
        assert geometry["rowHeight"] > 0, geometry
        assert geometry["height"] >= geometry["rowHeight"], geometry
        assert geometry["activeTop"] >= geometry["pickerTop"] - 1, geometry
        assert geometry["activeBottom"] <= geometry["pickerBottom"] + 1, geometry
        if report_count > 3:
          assert geometry["scrollHeight"] > geometry["height"], geometry
        assert geometry["ackHeight"] > geometry["rowHeight"], geometry
        assert geometry["ackScrollHeight"] > geometry["ackHeight"], geometry
        assert geometry["ackOverflow"] == "auto", geometry
        assert geometry["ackEndFade"], geometry
        assert "linear-gradient" in geometry["ackMask"], geometry
        if width >= 1200:
          assert geometry["railOverflow"] == "hidden", geometry
          assert geometry["railScrollHeight"] <= geometry["railHeight"] + 1, geometry
          assert geometry["railBottom"] >= height - 1, geometry
          assert geometry["ackBottom"] >= height - 1, geometry
          if report_count == 3:
            assert geometry["ackHeight"] > 320, geometry
        scrolls = picker.evaluate("""element => {
          const ack = element.closest('#report-rail').querySelector('#report-ack-history');
          element.scrollTop = 0;
          ack.scrollTop = ack.scrollHeight;
          return { picker: element.scrollTop, ack: ack.scrollTop };
        }""")
        assert scrolls["picker"] == 0, scrolls
        assert scrolls["ack"] > 0, scrolls
        page.wait_for_function("""() => {
          const ack = document.querySelector('#report-ack-history');
          return ack?.hasAttribute('data-scrolled-start') && !ack.hasAttribute('data-scrolled-end');
        }""")
        picker.locator('[data-report-id="report-02"]').click()
        page.wait_for_function(
          "document.querySelector('#report-picker [aria-current=true]')?.dataset.reportId === 'report-02'"
        )
        assert page.locator("#report h1").inner_text() == "Report 02"
        assert page.locator("#report-ack-history").count() == 0
        if width >= 1200:
          expanded = picker.evaluate("""element => ({
            height: element.clientHeight,
            railHeight: element.closest('#report-rail').clientHeight,
            bottom: element.getBoundingClientRect().bottom,
          })""")
          assert expanded["height"] >= expanded["railHeight"] - 60, expanded
          assert expanded["bottom"] >= height - 1, expanded
      finally:
        browser.close()
  finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)
    store.close()


@pytest.mark.skipif(
  not os.environ.get("CHROMIUM_BIN"),
  reason="Set CHROMIUM_BIN for the extracted browser",
)
@pytest.mark.parametrize("width,height", [(390, 844), (855, 700), (1372, 700)])
def test_report_picker_keeps_selected_item_visible_and_fades_edges(
  width: int, height: int, tmp_path: Path
) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore()
  app = SteeringApp(store, repo_name="Report picker scroll regression")
  report_count = 30
  for idx in range(1, report_count + 1):
    app.reports.publish_report(f"report-{idx:02d}", f"Report {idx}", f"# Report {idx}")
  server = create_http_server(app, host="0.0.0.0", port=0)
  thread = threading.Thread(target=server.serve_forever, daemon=True)
  thread.start()
  try:
    with playwright.sync_playwright() as runner:
      browser = runner.chromium.launch(
        executable_path=os.environ["CHROMIUM_BIN"],
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage"],
      )
      try:
        page = browser.new_page(viewport={"width": width, "height": height})
        page.set_default_timeout(5000)
        page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
        page.locator("#tab-reports").click()
        picker = page.locator("#report-picker")
        items = picker.locator(".report-picker-link")
        items.first.wait_for(state="visible")
        assert items.count() == report_count
        last = items.nth(report_count - 1)
        last_id = last.get_attribute("data-report-id")
        assert last_id
        assert picker.evaluate("element => element.scrollHeight > element.clientHeight")
        assert picker.get_attribute("data-scrolled-start") is None
        assert picker.get_attribute("data-scrolled-end") is not None
        top_mask = picker.evaluate("element => getComputedStyle(element).maskImage")
        assert top_mask.count("linear-gradient(") == 1, top_mask
        page.screenshot(path=str(tmp_path / f"report-picker-top-{width}.png"))

        picker.evaluate("element => { element.scrollTop = element.scrollHeight; }")
        page.wait_for_function(
          "document.querySelector('#report-picker')?.hasAttribute('data-scrolled-start')"
        )
        before = picker.evaluate("element => element.scrollTop")
        assert before > 0
        assert picker.get_attribute("data-scrolled-end") is None
        last.click()
        page.wait_for_function(
          "id => document.querySelector('#report-picker [aria-current=true]')?.dataset.reportId === id",
          arg=last_id,
        )
        after = picker.evaluate("""element => {
          const selected = element.querySelector('[aria-current="true"]');
          const viewport = element.getBoundingClientRect();
          const row = selected.getBoundingClientRect();
          return {
            top: element.scrollTop,
            selectedVisible: row.top >= viewport.top - 1 && row.bottom <= viewport.bottom + 1,
            topFade: element.hasAttribute('data-scrolled-start'),
            bottomFade: element.hasAttribute('data-scrolled-end'),
            mask: getComputedStyle(element).maskImage,
          };
        }""")
        assert after["top"] >= before - 2, (before, after)
        assert after["selectedVisible"], after
        assert after["topFade"] and not after["bottomFade"], after
        assert after["mask"].count("linear-gradient(") == 1, after
        if width < 1200:
          toggle = page.locator("#report-picker-toggle")
          toggle.click()
          assert picker.is_hidden()
          toggle.click()
          assert picker.is_visible()
          assert picker.evaluate("element => element.scrollTop") >= before - 2
          assert picker.get_attribute("data-scrolled-start") is not None
        page.screenshot(path=str(tmp_path / f"report-picker-{width}.png"))
      finally:
        browser.close()
  finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)
    store.close()


@pytest.mark.skipif(
  not os.environ.get("ARENA_STEERING_CHROMIUM"),
  reason="Set ARENA_STEERING_CHROMIUM to run the browser regression",
)
def test_report_picker_identifies_unseen_acknowledgements() -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore()
  app = SteeringApp(store, repo_name="Report picker indicators")
  app.reports.publish_report("viewer", "Viewer", "# Viewer")
  app.reports.mark_seen("viewer")
  app.reports.publish_report(
    "decision",
    "Decision",
    '<!-- question {"id":"choice","label":"Choice"} -->\nChoice: ___\n',
  )
  answer = app.reports.submit_answer("decision", {"choice": "Yes"})
  app.reports.ack_answer("decision", answer.id, "Received")
  app.reports.publish_report("unread", "Unread", "# Unread")
  server = create_http_server(app, host="0.0.0.0", port=0)
  thread = threading.Thread(target=server.serve_forever, daemon=True)
  thread.start()
  try:
    with playwright.sync_playwright() as runner:
      browser = runner.chromium.launch(
        executable_path=os.environ["ARENA_STEERING_CHROMIUM"],
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage"],
      )
      try:
        page = browser.new_page(viewport={"width": 1200, "height": 700})
        page.set_default_timeout(5000)
        page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
        page.locator("#tab-reports").click()
        decision = page.locator('[data-report-id="decision"]')
        unread = page.locator('[data-report-id="unread"]')
        ack_dot = decision.locator(".report-picker-unseen-dot")
        unread_dot = unread.locator(".report-picker-unseen-dot")
        ack_dot.wait_for(state="visible")
        unread_dot.wait_for(state="visible")
        assert ack_dot.get_attribute("aria-label") == "Unseen answer acknowledgement"
        assert "is-unseen-ack" in (ack_dot.get_attribute("class") or "")
        assert "is-unseen-ack" not in (unread_dot.get_attribute("class") or "")
        assert ack_dot.evaluate("el => getComputedStyle(el).backgroundColor") != (
          unread_dot.evaluate("el => getComputedStyle(el).backgroundColor")
        )
        with page.expect_response("**/reports/decision/ack-seen"):
          decision.click()
        ack_dot.wait_for(state="hidden")
        assert unread_dot.is_visible()
      finally:
        browser.close()
  finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)
    store.close()


@pytest.mark.skipif(
  not os.environ.get("ARENA_STEERING_CHROMIUM"),
  reason="Set ARENA_STEERING_CHROMIUM to run the browser regression",
)
@pytest.mark.parametrize(
  ("first_stamp", "next_stamp"),
  [
    ("2027-01-01T00:00:00Z", "2027-01-01T00:20:00Z"),
    ("2027-01-01T00:00:00.000001Z", "2027-01-01T00:00:00.000002Z"),
  ],
)
def test_report_refresh_preserves_focus_after_stale_list_response(
  first_stamp: str, next_stamp: str
) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore()
  app = SteeringApp(store, repo_name="Report refresh race")
  app.reports.publish_report(
    "decision",
    "Decision",
    '<!-- question {"id":"note","label":"Note"} -->\nNote: ___\n',
  )

  class Clock:
    stamp = first_stamp

    def now_iso(self) -> str:
      return self.stamp

  clock = Clock()
  app.reports._clock = clock
  server = create_http_server(app, host="0.0.0.0", port=0)
  thread = threading.Thread(target=server.serve_forever, daemon=True)
  thread.start()
  try:
    with playwright.sync_playwright() as runner:
      browser = runner.chromium.launch(
        executable_path=os.environ["ARENA_STEERING_CHROMIUM"],
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage"],
      )
      try:
        page = browser.new_page(viewport={"width": 1200, "height": 700})
        page.set_default_timeout(5000)
        page.clock.install()
        page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
        with page.expect_response("**/reports/decision/seen"):
          page.locator("#tab-reports").click()
        field = page.locator(".field-text-input")
        field.fill("Draft")
        field.focus()
        original = field.element_handle()
        held = []

        def delay_list(route) -> None:
          response = route.fetch()
          held.append((route, response))
          page.evaluate("console.log('report-list-held')")

        page.route("**/reports?*", delay_list, times=1)
        with page.expect_console_message(
          lambda message: message.text == "report-list-held"
        ):
          page.clock.fast_forward(3_000)
        clock.stamp = next_stamp
        with page.expect_response("**/reports/decision/seen"):
          page.clock.fast_forward(31_000)
        page.evaluate(
          "() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))"
        )
        assert original.evaluate("el => el === document.activeElement")
        with page.expect_response("**/reports?*"):
          held[0][0].fulfill(response=held[0][1])
        page.evaluate(
          "() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))"
        )
        assert original.evaluate(
          "el => el.isConnected && el === document.activeElement"
        )
        assert original.input_value() == "Draft"
      finally:
        browser.close()
  finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)
    store.close()


@pytest.mark.skipif(
  not os.environ.get("ARENA_STEERING_CHROMIUM"),
  reason="Set ARENA_STEERING_CHROMIUM to run the browser regression",
)
def test_report_refresh_ignores_delayed_older_detail_response() -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore()
  app = SteeringApp(store, repo_name="Report detail race")
  field_md = '<!-- question {"id":"note","label":"Note"} -->\nNote: ___\n'
  app.reports.publish_report(
    "decision", "Decision", "# First report body\n\n" + field_md
  )

  class Clock:
    stamp = "2027-01-01T00:00:00.000001Z"

    def now_iso(self) -> str:
      return self.stamp

  clock = Clock()
  app.reports._clock = clock
  server = create_http_server(app, host="0.0.0.0", port=0)
  thread = threading.Thread(target=server.serve_forever, daemon=True)
  thread.start()
  try:
    with playwright.sync_playwright() as runner:
      browser = runner.chromium.launch(
        executable_path=os.environ["ARENA_STEERING_CHROMIUM"],
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage"],
      )
      try:
        page = browser.new_page(viewport={"width": 1200, "height": 700})
        page.set_default_timeout(5000)
        page.clock.install()
        page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
        with page.expect_response("**/reports/decision/seen"):
          page.locator("#tab-reports").click()
        page.get_by_role("heading", name="First report body").wait_for()
        held = []

        def delay_detail(route) -> None:
          response = route.fetch()
          held.append((route, response))
          page.evaluate("console.log('report-detail-held')")

        page.route("**/reports/decision", delay_detail, times=1)
        clock.stamp = "2027-01-01T00:00:00.000002Z"
        app.reports.publish_report(
          "decision", "Decision", "# Older report body\n\n" + field_md
        )
        with page.expect_console_message(
          lambda message: message.text == "report-detail-held"
        ):
          page.clock.fast_forward(3_000)
        clock.stamp = "2027-01-01T00:00:00.000003Z"
        app.reports.publish_report(
          "decision", "Decision", "# Newest report body\n\n" + field_md
        )
        page.clock.fast_forward(3_000)
        page.get_by_role("heading", name="Newest report body").wait_for()
        field = page.locator(".field-text-input")
        field.fill("Draft")
        field.focus()
        original = field.element_handle()
        with page.expect_response("**/reports/decision"):
          held[0][0].fulfill(response=held[0][1])
        page.evaluate(
          "() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))"
        )
        assert original.evaluate(
          "el => el.isConnected && el === document.activeElement"
        )
        assert original.input_value() == "Draft"
        assert page.get_by_role("heading", name="Newest report body").is_visible()
        assert page.get_by_role("heading", name="Older report body").count() == 0
      finally:
        browser.close()
  finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)
    store.close()


@pytest.mark.skipif(
  not os.environ.get("ARENA_STEERING_CHROMIUM"),
  reason="Set ARENA_STEERING_CHROMIUM to run the browser regression",
)
@pytest.mark.parametrize("width", [390, 1200])
def test_report_recommendations_submit_only_after_explicit_submit(
  tmp_path: Path, width: int
) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore(tmp_path / "state.sqlite3")
  app = SteeringApp(store)
  body = (
    '<!-- question {"id":"route","label":"Route"} -->\n'
    "Choose a route\n"
    '- (x) Guided review <!-- option {"label":"Guided"} -->\n'
    '- ( ) Manual review <!-- option {"label":"Manual"} -->\n\n'
    '<!-- question {"id":"signal","label":"Signal"} -->\n'
    "Choose signals\n"
    '- [x] First signal <!-- option {"label":"First"} -->\n'
    '- [ ] Second signal <!-- option {"label":"Second"} -->\n'
  )
  app.reports.publish_report("recommend-only", "Recommended choices", body)
  server = create_http_server(app, host="0.0.0.0", port=0)
  thread = threading.Thread(target=server.serve_forever, daemon=True)
  thread.start()
  try:
    with playwright.sync_playwright() as runner:
      browser = runner.chromium.launch(
        executable_path=os.environ["ARENA_STEERING_CHROMIUM"],
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage"],
      )
      try:
        page = browser.new_page(viewport={"width": width, "height": 844})
        page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
        page.locator("#tab-reports").click()
        assert page.locator(
          '[data-field-id="route"] input[value="Guided review"]'
        ).is_checked()
        assert page.locator(
          '[data-field-id="signal"] input[value="First signal"]'
        ).is_checked()
        assert app.reports.get_report("recommend-only").answers == []
        page.screenshot(path=str(tmp_path / f"recommend-before-{width}.png"))
        with (
          page.expect_request("**/reports/recommend-only/answers") as request,
          page.expect_response("**/reports/recommend-only/answers") as response,
        ):
          page.locator("#report-submit-float").click()
        assert request.value.post_data_json["values"] == {
          "route": "Guided review",
          "signal": ["First signal"],
        }
        assert response.value.status == HTTPStatus.CREATED
        assert app.reports.get_report("recommend-only").answers[-1].values == {
          "route": "Guided",
          "signal": ["First"],
        }
        page.locator("#report-picker .report-picker-unanswered").wait_for(
          state="detached", timeout=6000
        )
        page.screenshot(path=str(tmp_path / f"recommend-after-{width}.png"))
      finally:
        browser.close()
  finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)
    store.close()


@pytest.mark.skipif(
  not os.environ.get("ARENA_STEERING_CHROMIUM"),
  reason="Set ARENA_STEERING_CHROMIUM to run the browser regression",
)
@pytest.mark.parametrize("width", [390, 1200])
def test_report_recommendations_preselect_without_becoming_owner_answers(
  tmp_path: Path, width: int
) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore(tmp_path / "state.sqlite3")
  app = SteeringApp(store)
  body = (
    "# Recommendations\n\n"
    '<!-- question {"id":"route","label":"Route"} -->\n'
    "Choose a route\n"
    '- (x) Guided review <!-- option {"label":"Guided"} -->\n'
    '- ( ) Manual review <!-- option {"label":"Manual"} -->\n\n'
    '<!-- question {"id":"signals","label":"Signals"} -->\n'
    "Choose signals\n"
    '- [x] First signal <!-- option {"label":"First"} -->\n'
    '- [ ] Second <!-- option {"label":"Second"} -->\n\n'
    '<!-- question {"id":"note","label":"Note"} -->\n'
    "Your note: ___\n"
  )
  app.reports.publish_report("recommend", "Recommendations", body)
  server = create_http_server(app, host="0.0.0.0", port=0)
  thread = threading.Thread(target=server.serve_forever, daemon=True)
  thread.start()
  try:
    with playwright.sync_playwright() as runner:
      browser = runner.chromium.launch(
        executable_path=os.environ["ARENA_STEERING_CHROMIUM"],
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage"],
      )
      try:
        page = browser.new_page(viewport={"width": width, "height": 844})
        page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
        page.locator("#tab-reports").click()
        route = page.locator('[data-field-id="route"] input[value="Guided review"]')
        signal = page.locator('[data-field-id="signals"] input[value="First signal"]')
        route.wait_for()
        assert route.is_checked()
        assert signal.is_checked()
        assert app.reports.get_report("recommend").answers == []
        page.locator('[data-field-id="note"] .field-text-input').fill("Only my note")
        with (
          page.expect_request("**/reports/recommend/answers") as first_request,
          page.expect_response("**/reports/recommend/answers") as first_response,
        ):
          page.locator("#report-submit-float").click()
        assert first_request.value.post_data_json["values"] == {
          "route": "Guided review",
          "signals": ["First signal"],
          "note": "Only my note",
        }
        assert first_response.value.status == HTTPStatus.CREATED
        assert app.reports.get_report("recommend").answers[-1].values == {
          "route": "Guided",
          "signals": ["First"],
          "note": "Only my note",
        }
        page.reload()
        page.locator("#tab-reports").click()
        assert route.is_checked()
        assert signal.is_checked()
        route.click()
        signal.click()
        assert not signal.is_checked()
        page.reload()
        page.locator("#tab-reports").click()
        assert not signal.is_checked()
        signal.click()
        page.reload()
        page.locator("#tab-reports").click()
        assert route.is_checked()
        assert signal.is_checked()
        assert not page.locator('[data-field-id="route"] .custom-toggle').is_checked()
        page.locator('[data-field-id="route"] input[value="Manual review"]').click()
        with page.expect_response("**/reports/recommend/answers") as revised_response:
          page.locator("#report-submit-float").click()
        assert revised_response.value.status == HTTPStatus.CREATED
        revisions = app.reports.get_report("recommend").answers
        assert len(revisions) == 2
        assert revisions[-1].values == {
          "route": "Manual",
          "signals": ["First"],
          "note": "Only my note",
        }
      finally:
        browser.close()
  finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)
    store.close()


@pytest.mark.skipif(
  not os.environ.get("ARENA_STEERING_CHROMIUM"),
  reason="Set ARENA_STEERING_CHROMIUM to run the browser regression",
)
@pytest.mark.parametrize("width", [390, 1200])
@pytest.mark.parametrize("with_heading", [True, False])
def test_report_header_tracks_linked_tasks_without_duplicate_title(
  tmp_path: Path, width: int, with_heading: bool
) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore(tmp_path / "state.sqlite3")
  app = SteeringApp(store)
  body = "# Decision\n\nReport body." if with_heading else "Report body."
  app.reports.publish_report("decision", "Decision", body)
  server = create_http_server(app, host="0.0.0.0", port=0)
  thread = threading.Thread(target=server.serve_forever, daemon=True)
  thread.start()
  try:
    with playwright.sync_playwright() as runner:
      browser = runner.chromium.launch(
        executable_path=os.environ["ARENA_STEERING_CHROMIUM"],
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage"],
      )
      try:
        page = browser.new_page(viewport={"width": width, "height": 800})
        page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
        page.locator("#tab-reports").click()
        report = page.locator("#report")
        report.locator("h1").first.wait_for()
        assert report.locator("h1").count() == 1
        assert report.locator(".report-task-links").count() == 0
        app.tasks.create_task(
          "linked-one",
          "Linked task",
          size=3,
          report_ids=["decision"],
          details=["Review"],
        )
        chip = report.get_by_role("button", name="Open task linked-one")
        chip.wait_for(timeout=10000)
        assert (
          chip.locator("code").evaluate("el => getComputedStyle(el).fontSize") == "11px"
        )
        assert report.locator("h1").count() == 1
        assert report.locator(".report-task-links button").count() == 1
        app.tasks.create_task(
          "linked-two",
          "Another task",
          size=3,
          report_ids=["decision"],
          details=["Review"],
        )
        report.get_by_role("button", name="Open task linked-two").wait_for(
          timeout=10000
        )
        assert report.locator(".report-task-links button").count() == 2
        assert report.locator(".report-task-links").inner_text().startswith("Tasks:")
        app.tasks.mod_links_rm("linked-two", "report", "decision")
        report.get_by_role("button", name="Open task linked-two").wait_for(
          state="detached", timeout=10000
        )
        title_box = report.locator("h1").bounding_box()
        chip_box = chip.bounding_box()
        id_box = report.locator('button[data-parent-id="decision"]').bounding_box()
        assert title_box and chip_box and id_box
        assert id_box["y"] + id_box["height"] <= title_box["y"], (id_box, title_box)
        assert title_box["y"] + title_box["height"] <= chip_box["y"], (
          title_box,
          chip_box,
        )
        stamp_box = report.locator("#report-status time").bounding_box()
        assert stamp_box and stamp_box["y"] + stamp_box["height"] <= id_box["y"]
        id_chip = report.locator('button[data-parent-id="decision"]')
        assert (
          id_chip.evaluate("el => parseFloat(getComputedStyle(el).borderTopWidth)") > 0
        )
        assert (
          id_chip.evaluate("el => parseFloat(getComputedStyle(el).borderRadius)") > 0
        )
        assert report.locator(".report-task-links").inner_text().startswith("Task:")
        page.screenshot(path=str(tmp_path / f"report-linked-task-{width}.png"))
        chip.click()
        page.locator('#tab-tasks[aria-selected="true"]').wait_for()
      finally:
        browser.close()
  finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)
    store.close()


def test_flagged_report_unlinks_tasks_without_losing_answers_or_details(
  tmp_path: Path,
) -> None:
  store = SqliteStore(tmp_path / "state.sqlite3")
  try:
    app = SteeringApp(store)
    body = '<!-- question {"id":"note","label":"Note"} -->\nNote: ___\n'
    app.reports.publish_report("flagged", "Flagged", body)
    app.reports.publish_report("other", "Other", body)
    app.tasks.create_task(
      "waiting",
      "Waiting",
      size=3,
      details=["Review the answer"],
      report_ids=["flagged"],
    )
    assert app.tasks.get_task("waiting")[1] is True

    status, result = app.dispatch(
      "POST",
      "/agent-interrupt",
      {"tab": "reports", "reason": "format-violation", "report_id": "flagged"},
    )
    assert status == HTTPStatus.OK and result["agent_interrupt_pending"] is True
    assert app.reports.get_report("flagged").status == "dismissed"
    assert app.tasks.get_task("waiting")[1] is False
    assert app.tasks.get_task("waiting")[0].report_ids == []
    assert app.tasks.get_task("waiting")[0].details == ["Review the answer"]
    assert app.reports.get_report("other").status == "published"
    assert [report.id for report in app.reports.list_reports()] == ["other"]
    flag = app.messages.pending_violation()
    assert flag is not None and SOURCE_FILE_UNAVAILABLE in flag.body

    app.messages.ack(flag.id, "Read the clause.")
    app.tasks.create_task(
      "answered-work", "Answered work", size=3, details=["Review"], report_ids=["other"]
    )
    answer = app.reports.submit_answer("other", {"note": "keep"}, answer_id="aa1201")
    answer = app.reports.ack_answer("other", answer.id, "Read the answer.")
    original_details = app.tasks.get_task("answered-work")[0].details
    assert original_details == ["Review", "Note: keep"]
    app.reports.publish_report("other", "Other", body)
    status, _ = app.dispatch(
      "POST",
      "/agent-interrupt",
      {"tab": "reports", "reason": "wall-of-text", "report_id": "other"},
    )
    assert status == HTTPStatus.OK
    assert app.reports.get_report("other").status == "dismissed"
    assert app.reports.get_report("other").answers == [answer]
    assert app.tasks.get_task("answered-work")[0].report_ids == []
    assert app.tasks.get_task("answered-work")[0].details == original_details
    assert store.get_message(answer.id) is not None
  finally:
    store.close()


def test_report_flag_failure_keeps_report_published(
  tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  store = SqliteStore(tmp_path / "state.sqlite3")
  try:
    app = SteeringApp(store)
    app.reports.publish_report("review", "Review", "Report body.")
    earlier = app.messages.send_message(
      "Previous flag", hidden=True, blocking=True, violation_type="bash-violation"
    )
    status, _ = app.dispatch(
      "POST",
      "/agent-interrupt",
      {"tab": "reports", "reason": "format-violation", "report_id": "review"},
    )
    assert status == HTTPStatus.BAD_REQUEST
    assert app.reports.get_report("review").status == "published"
    app.messages.ack(earlier.id, "Read the earlier flag.")

    def fail_message(*_args: object, **_kwargs: object) -> None:
      raise RuntimeError("Could not save the flag")

    monkeypatch.setattr(app.messages, "send_message", fail_message)
    status, result = app.dispatch(
      "POST",
      "/agent-interrupt",
      {"tab": "reports", "reason": "format-violation", "report_id": "review"},
    )
    assert status == HTTPStatus.INTERNAL_SERVER_ERROR
    assert result["error"] == "Could not save the flag"
    assert app.reports.get_report("review").status == "published"
  finally:
    store.close()


def test_report_flag_names_the_persisted_source_file(tmp_path: Path) -> None:
  db_path = tmp_path / "state.sqlite3"
  store = SqliteStore(db_path)
  try:
    app = SteeringApp(store)
    app.reports.publish_report(
      "source-report",
      "Source report",
      "Report body.",
      source_file="arena-state/reports/source.md",
    )
  finally:
    store.close()

  store = SqliteStore(db_path)
  try:
    app = SteeringApp(store)
    assert app.reports.get_report("source-report").source_file == (
      "arena-state/reports/source.md"
    )
    app.reports.publish_report(
      "source-report",
      "Source report",
      "Revised body.",
      source_file="arena-state/reports/revised.md",
    )
    status, _ = app.dispatch(
      "POST",
      "/agent-interrupt",
      {"tab": "reports", "reason": "format-violation", "report_id": "source-report"},
    )
    assert status == HTTPStatus.OK
    flag = app.messages.pending_violation()
    assert flag is not None
    assert (
      f"Source file: {home_relative(Path.cwd() / 'arena-state/reports/revised.md')}"
      in flag.body
    )
    assert app.reports.get_report("source-report").status == "dismissed"
    app.messages.ack(flag.id, "Read the clause.")
    absolute = tmp_path / "reports" / "absolute.md"
    app.reports.publish_report(
      "absolute-report", "Absolute report", "Report body.", source_file=str(absolute)
    )
    status, _ = app.dispatch(
      "POST",
      "/agent-interrupt",
      {"tab": "reports", "reason": "format-violation", "report_id": "absolute-report"},
    )
    assert status == HTTPStatus.OK
    second = app.messages.pending_violation()
    assert (
      second is not None and f"Source file: {home_relative(absolute)}" in second.body
    )
  finally:
    store.close()


@pytest.mark.skipif(
  not os.environ.get("ARENA_STEERING_CHROMIUM"),
  reason="Set ARENA_STEERING_CHROMIUM to run the browser regression",
)
def test_report_options_parse_inline_code_and_align_radio_with_first_line(
  tmp_path: Path,
) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore(tmp_path / "state.sqlite3")
  app = SteeringApp(store, repo_name="Report option code and radio alignment")
  raw_long_option = (
    'Accept `"codex"` or `"product"` (`Codex Lead` and `Head of Core Products`)'
  )
  report_md = (
    "# Matcher Contract\n\n"
    '<!-- question {"id":"survey-s2e5p-role","label":"S2E5P role"} -->\n\n'
    "Which hashed substring(s) should pass `S2E5P.role`?\n"
    f'- (x) {raw_long_option} <!-- option {{"label":"codex or product"}} -->\n'
    '- ( ) Require `"codex"` only <!-- option {"label":"codex only"} -->\n'
  )
  app.reports.publish_report("matcher-contract", "Matcher Contract", report_md)

  server = create_http_server(app, host="0.0.0.0", port=0)
  thread = threading.Thread(target=server.serve_forever, daemon=True)
  thread.start()
  try:
    with playwright.sync_playwright() as runner:
      browser = runner.chromium.launch(
        executable_path=os.environ["ARENA_STEERING_CHROMIUM"], args=["--no-sandbox"]
      )
      try:
        page = browser.new_page(viewport={"width": 440, "height": 760})
        page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
        page.locator("#tab-reports").click()
        page.locator("#field-survey-s2e5p-role").wait_for()

        label_codes = page.locator(
          "#field-survey-s2e5p-role .field-label code"
        ).all_inner_texts()
        assert label_codes == ["S2E5P.role"]
        assert (
          "`" not in page.locator("#field-survey-s2e5p-role .field-label").inner_text()
        )

        first_row = page.locator("#field-survey-s2e5p-role .option-row").first
        option_codes = first_row.locator("span code").all_inner_texts()
        assert option_codes == [
          '"codex"',
          '"product"',
          "Codex Lead",
          "Head of Core Products",
        ]
        assert "`" not in first_row.locator("span").last.inner_text()
        assert first_row.locator("input").get_attribute("value") == raw_long_option

        # Wrapped option text spans at least 2 lines, and the radio centers on line 1.
        metrics = first_row.evaluate(
          """row => {
            const input = row.querySelector('input').getBoundingClientRect();
            const span = row.querySelector('span:last-child');
            const spanRect = span.getBoundingClientRect();
            const range = document.createRange();
            range.selectNodeContents(span);
            const rects = [...range.getClientRects()].filter(r => r.width > 0 && r.height > 0);
            const topY = Math.min(...rects.map(r => r.top));
            const firstLine = rects.filter(r => Math.abs(r.top - topY) < 6);
            const line1Top = Math.min(...firstLine.map(r => r.top));
            const line1Bottom = Math.max(...firstLine.map(r => r.bottom));
            return {
              inputCenter: (input.top + input.bottom) / 2,
              line1Center: (line1Top + line1Bottom) / 2,
              spanCenter: (spanRect.top + spanRect.bottom) / 2,
              spanHeight: spanRect.height,
            };
          }"""
        )
        assert metrics["spanHeight"] >= 36, metrics
        assert abs(metrics["inputCenter"] - metrics["line1Center"]) <= 3.0, metrics
        assert metrics["spanCenter"] - metrics["inputCenter"] >= 6.0, metrics

        # Multi-line custom textarea also keeps its radio aligned with line 1.
        custom_row = page.locator("#field-survey-s2e5p-role .option-custom")
        custom_row.locator("textarea").fill(
          "First line of custom notes\nSecond line of custom notes\nThird line of custom notes"
        )
        custom_row.locator("textarea").evaluate(
          "el => { el.style.height = 'auto'; el.style.height = el.scrollHeight + 'px'; }"
        )
        custom_metrics = custom_row.evaluate(
          """row => {
            const input = row.querySelector('input').getBoundingClientRect();
            const ta = row.querySelector('textarea').getBoundingClientRect();
            return {
              inputCenter: (input.top + input.bottom) / 2,
              firstLineCenter: ta.top + 16,
              taHeight: ta.height,
            };
          }"""
        )
        assert custom_metrics["taHeight"] >= 50, custom_metrics
        assert (
          abs(custom_metrics["inputCenter"] - custom_metrics["firstLineCenter"]) <= 3.0
        ), custom_metrics
      finally:
        browser.close()
  finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)
    store.close()
