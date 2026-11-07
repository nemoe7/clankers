"""Steering regression tests."""

from __future__ import annotations

import base64
import io
import json
import os
import re
import runpy
import shutil
import struct
import subprocess
import threading
import time
import zlib
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from pathlib import Path

import pytest
from arena_steering import cli, survey
from arena_steering import server as steering_server
from arena_steering.blocked_bash import append_blocked_bash
from arena_steering.display_paths import home_relative
from arena_steering.server import (
  SteeringApp,
  create_http_server,
  reload_server_handler,
)
from arena_steering.services import BIBLE_READ, with_bible_read
from arena_steering.store import SqliteStore
from fixtures.reload_isolation import run_reload_in_child

ROOT = Path(__file__).resolve().parents[3]


SKILL_DIR = ROOT / "skills" / "arena-steering"


ASSETS_DIR = SKILL_DIR / "assets"


DEMO_PATH = ROOT / "maintenance" / "demo-arena-steer.py"


DEMO = runpy.run_path(str(DEMO_PATH))


SCROLLSPY_ZONES_SVG = DEMO["SCROLLSPY_ZONES_SVG"]


TOKENS_SWATCH_SVG = DEMO["TOKENS_SWATCH_SVG"]


seed_demo_store = DEMO["seed_demo_store"]


demo_main = DEMO["main"]


EXPECTED_FONTS = (
  "Basel_Grotesk_Bold.woff2",
  "Basel_Grotesk_Book.woff2",
  "Basel_Grotesk_Medium.woff2",
  "Basel_Grotesk_Mono_Regular.woff2",
  "Basel_Grotesk_Regular.woff2",
)


EXPECTED_JS_MODULES = (
  "api.js",
  "app.js",
  "dom.js",
  "messages-view.js",
  "markdown.js",
  "modal.js",
  "reports-view.js",
  "state.js",
  "tasks-view.js",
  "timestamps.js",
)


PRELOAD_ATTR = 'rel="preload"'


MODULEPRELOAD_ATTR = 'rel="modulepreload"'


MODAL_SHELL_ID = 'id="modal-shell"'


CONFIRM_DELETE_TPL = 'data-modal-template="confirm-delete"'


SURFACE_TOKEN = "--surface-primary:"


CTA_TOKEN = "--interactive-cta:"


CODE_BG_TOKEN = "--code-bg:"


INLINE_CODE_RULE = ":not(pre) > code:not(.msg-id)"


MAIN_MAX_WIDTH = "max-width: 900px;"


MESSAGE_TEXT_FONT_SIZE = "font-size: 16px;"


STATUS_BANNER_ID = "status-banner"


THEME_TOGGLE_ID = "theme-toggle"


TOPBAR_BRAND_CLASS = "topbar-brand"


ARENA_SCROLLBAR_RULE = (
  "scrollbar-color: hsl(var(--surface-raised-alt) / 0.4) transparent;"
)


SCROLLBAR_WIDTH_RULE = "::-webkit-scrollbar {\n  width: 15px;\n  height: 10px;\n}"


SCROLLBAR_FLAT_THUMB_RULE = (
  "border: 1px solid transparent;\n  background-clip: padding-box;\n  border-radius: 0;"
)


SCROLLBAR_HOVER_RULE = "::-webkit-scrollbar-thumb:hover"


FONT_DISPLAY_BLOCK = "font-display: block;"


EDGE_LOADING_KEYFRAME = "nuu-edge-loading"


CUSTOM_OPTION_MARKER = "__custom__"


HISTORY_LIST_ID = 'id="history"'


COMPOSER_SHELL_CLASS = 'class="composer-shell"'


MANUAL_BLOCKING_INPUT = "inbox-blocking"


MANUAL_HIDDEN_INPUT = "inbox-hidden"


LUCIDE_CLOSE_ICON = "lucide-x"


LUCIDE_LOCK_ICON = "lucide-lock"


LUCIDE_CHEVRON_DOWN_ICON = "lucide-chevron-down"


SELECT_CHEVRON_CLASS = "select-chevron"


LUCIDE_COPY_ICON = "lucide-copy"


LUCIDE_SEND_ICON = "lucide-send"


REPORT_TOC_ID = 'id="report-toc"'


REPORT_PICKER_ID = 'id="report-picker"'


REPORT_RAIL_ID = 'id="report-rail"'


OPTION_CUSTOM_CLASS = "option-custom"


ON_THIS_PAGE_TEXT = "On this page"


REPORT_PICKER_META_CLASS = "report-picker-meta"


TASK_SECTION_TITLE_FONT_SIZE = "font-size: 18px;"


NOTES_PIP_ID = 'id="notes-pip"'


REPORT_PIP_ID = 'id="report-pip"'


TAB_BADGE_CLASS = "tab-badge"


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


RECEIPT_ID_CLASS = "receipt-id"


REPLY_PARENT_CHIP_CLASS = "reply-parent-chip"


COMPOSER_REPLY_BAR_ID = 'id="composer-reply-bar"'


COMPOSER_REPLY_CHIP_CLASS = "composer-reply-chip"


PARENT_IDS_FIELD = "parent_ids"


PARENT_REFS_FIELD = "parent_refs"


REPLY_PARENT_REFS_STATE = "replyParentRefs"


TOGGLE_REPLY_PARENT_HANDLER = "onToggleReplyParent"


STATIC_ASSET_PREFIX = "/static/assets/"


STATIC_STYLE_HREF = 'href="/static/assets/style.css"'


STATIC_APP_SRC = 'src="/static/assets/app.js"'


ROOT_STYLE_HREF = 'href="/style.css"'


MARK_RULE = "mark {"


COMPOSER_ATTACHMENTS_ID = 'id="composer-attachments"'


ATTACH_FILE_ID = 'id="attach-file"'


COMPOSER_EXPAND_ID = 'id="composer-expand"'


COMPOSER_ATTACHMENTS_STATE = "composerAttachments"


COMPOSER_EXPANDED_STATE = "composerExpanded"


UPLOAD_FILE_API = "uploadFile"


SEND_MESSAGE_WITH_FILE_API = "sendMessageWithFile"


WARM_SURFACE_PRIMARY = "#252523"


WARM_SURFACE_SECONDARY = "#2c2b28"


WARM_SURFACE_TERTIARY = "#1b1a19"


WARM_SURFACE_RAISED_TERTIARY = "#292624"


WARM_TEXT_PRIMARY = "#f4f0eb"


WARM_TEXT_TERTIARY = "#c7c2bc"


WARM_BORDER_FAINT = "#413d39"


WARM_BORDER_MEDIUM = "#524c47"


WARM_ACCENT = "#e5bb8b"


WARM_DOT_SEEN = "#7fa7d1"


WARM_DOT_SAID = "#8dc07f"


WARM_ACCENT_RGB = "(229, 187, 139)"


WARM_SURFACE_PRIMARY_HSL = '"60 3% 14%"'


WARM_SURFACE_RAISED_HSL = '"24 6% 24%"'


SLATE_MERMAID_COLORS = (
  "#22252b",
  "#2b2f37",
  "#242830",
  "#68b5f8",
  "#4a505c",
  "#1b1e23",
  "#373b44",
  "#9da3ae",
  "#f3f4f6",
  "#f9fafb",
)


SLATE_DEMO_COLORS = (
  "#14171c",
  "#343944",
  "#242830",
  "#1c2026",
  "#171a20",
  "#191c22",
  "#2e3440",
  "#68b5f8",
  "#f59e0b",
  "#34d399",
  "#e5e7eb",
  '"220 15% 11%"',
  '"220 14% 16%"',
  "(20, 23, 28)",
  "(52, 57, 68)",
  "(36, 40, 48)",
  "(28, 32, 38)",
  "(104, 181, 248)",
  "(120, 128, 142)",
  "(24, 27, 32)",
  "(42, 47, 56)",
  "(245, 158, 11)",
  "(52, 211, 153)",
)


def test_reports_copy_uses_only_confirmed_selection_method() -> None:
  subprocess.run(
    ["node", str(ROOT / "tests/skills/arena-steering/fixtures/copy_report_unit.cjs")],
    cwd=ROOT,
    capture_output=True,
    check=True,
    text=True,
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


def test_assets_do_not_use_browser_owned_prompts() -> None:
  for script in ASSETS_DIR.glob("*.js"):
    if script.name.endswith(".min.js"):
      continue
    source = script.read_text(encoding="utf-8")
    assert not re.search(
      r"\b(?:window|globalThis)\.(?:alert|confirm|prompt)\s*\(", source
    )


@pytest.mark.skipif(
  not os.environ.get("ARENA_STEERING_CHROMIUM"),
  reason="Set ARENA_STEERING_CHROMIUM to run the browser regression",
)
@pytest.mark.parametrize("decision", ["retry", "new", "cancel"])
def test_unconfirmed_write_uses_html_dialog(tmp_path: Path, decision: str) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore(tmp_path / "state.sqlite3")
  app = SteeringApp(store)
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
        page = browser.new_page(viewport={"width": 411, "height": 799})
        page.add_init_script("""(() => {
          const key = JSON.stringify(['POST', '/poll/skip', {}]);
          sessionStorage.setItem('steer:pendingWrites', JSON.stringify([
            {key, id: '550e8400-e29b-41d4-a716-446655440000'}
          ]));
        })();""")
        writes = []
        page.route(
          "**/poll/skip",
          lambda route: (
            writes.append(route.request.post_data_json),
            route.fulfill(
              status=200, content_type="application/json", body='{"skip_poll":true}'
            ),
          ),
        )
        native = []
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("dialog", lambda dialog: (native.append(dialog.type), dialog.dismiss()))
        page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
        page.locator("#skip-poll").click()
        dialog = page.locator("#modal-shell[open]")
        dialog.wait_for()
        button = dialog.locator(f'#modal-actions button[value="{decision}"]')
        if decision == "cancel":
          button.click()
          page.wait_for_timeout(200)
          assert not writes
          assert page.locator("#skip-poll").get_attribute("data-state") != "good"
        else:
          with page.expect_response("**/poll/skip"):
            button.click()
          assert len(writes) == 1
          reused = writes[0]["_request_id"] == "550e8400-e29b-41d4-a716-446655440000"
          assert reused == (decision == "retry")
        assert not native
        assert not errors
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
def test_missing_reference_uses_html_dialog(tmp_path: Path) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore(tmp_path / "state.sqlite3")
  app = SteeringApp(store)
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
        page = browser.new_page(viewport={"width": 411, "height": 799})
        native = []
        page.on("dialog", lambda dialog: (native.append(dialog.type), dialog.dismiss()))
        page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
        page.evaluate("""() => {
          const button = document.createElement('button');
          button.dataset.referenceType = 'message';
          button.dataset.referenceId = 'ff0001';
          document.body.append(button);
          button.click();
        }""")
        dialog = page.locator("#modal-shell[open]")
        dialog.get_by_text("Could not open message ff0001.").wait_for(timeout=8000)
        assert not native
        dialog.get_by_role("button", name="Close", exact=True).click()
        assert not dialog.is_visible()
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
def test_survey_modal_survives_asset_hot_reload(tmp_path: Path) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  assets = tmp_path / "assets"
  shutil.copytree(ASSETS_DIR, assets)
  store = SqliteStore(tmp_path / "state.sqlite3")
  app = SteeringApp(store, assets_dir=assets)
  app.messages.submit_survey(survey.template())
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
        page = browser.new_page(viewport={"width": 411, "height": 799})
        page.goto(f"http://127.0.0.1:{server.server_port}/")
        page.locator('#connection-dot[data-state="ok"]').wait_for()
        page.locator("#survey-open").click()
        page.locator(".survey-cap-pill").first.wait_for()
        with (
          page.expect_navigation(wait_until="load", timeout=20000),
          (assets / "style.css").open("a", encoding="utf-8") as css,
        ):
          css.write("\n/* asset reload test */\n")
          css.flush()
        page.locator("#modal-shell[open]").wait_for(timeout=8000)
        assert page.locator(".survey-cap-pill").count() == 3
        page.locator('#modal-actions button[value="cancel"]').click()
        page.reload()
        assert not page.locator("#modal-shell").is_visible()
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
def test_survey_again_button_requests_hidden_reanswer(tmp_path: Path) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore(tmp_path / "state.sqlite3")
  app = SteeringApp(store)
  app.messages.submit_survey(survey.template())
  before = app.messages.get_survey()
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
        page = browser.new_page(viewport={"width": 411, "height": 799})
        page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
        page.locator("#survey-open").click()
        with page.expect_response(
          lambda response: "/survey/interrupt" in response.url
        ) as result:
          page.get_by_role("button", name="Survey again").click()
        assert result.value.status == 200
        assert app.messages.get_survey()["answers"] == before["answers"]
        messages = app.messages.list_messages(include_hidden=True)
        assert len(messages) == 1 and messages[0].hidden and messages[0].blocking
        assert app.messages.list_messages(include_hidden=False) == []
        page.locator("#survey-open").click()
        assert page.locator(".survey-cap-pill").count() == 3
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
def test_survey_modal_does_not_show_ungraded_answers(tmp_path: Path) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore(tmp_path / "state.sqlite3")
  app = SteeringApp(store)
  app.messages._survey_answers = {"R3S0N": '{"reasoning":true}'}
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
        page = browser.new_page(viewport={"width": 411, "height": 799})
        page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
        page.locator("#survey-open").click()
        assert page.locator(".survey-item").count() == 0
        assert "reasoning" not in page.locator(".survey-modal-content").inner_text()
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
@pytest.mark.parametrize(("width", "height"), [(411, 799), (855, 325), (1372, 883)])
def test_survey_modal_keeps_tooltip_and_actions_in_view(
  tmp_path: Path, width: int, height: int
) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore(tmp_path / "state.sqlite3")
  app = SteeringApp(store)
  app.messages.submit_survey(json.dumps(survey.template()))
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
        page.locator("#survey-open").click()
        page.locator(".survey-cap-pill").first.hover()
        first = page.evaluate("""() => {
          const rect = selector => document.querySelector(selector).getBoundingClientRect();
          const tip = document.querySelector('.survey-cap-pill:first-child .survey-answer-tooltip');
          const tooltip = tip.getBoundingClientRect();
          const pill = rect('.survey-cap-pill:first-child');
          const heading = rect('.survey-section-label');
          return {
            background: getComputedStyle(tip).backgroundColor,
            tooltipTop: tooltip.top, tooltipBottom: tooltip.bottom,
            pillTop: pill.top, headingTop: heading.top, headingBottom: heading.bottom
          };
        }""")
        assert first["background"] == "rgb(255, 255, 255)"
        first_tip = page.locator(".survey-cap-pill:first-child .survey-answer-tooltip")
        assert first_tip.evaluate("el => getComputedStyle(el).animationName") in (
          "tooltip-from-above",
          "tooltip-from-below",
        )
        page.emulate_media(reduced_motion="reduce")
        assert first_tip.evaluate("el => getComputedStyle(el).animationName") == "none"
        assert (
          page.locator(
            ".survey-cap-pill:first-child .survey-answer-val"
          ).first.evaluate("el => getComputedStyle(el).color")
          == "rgb(24, 24, 24)"
        )
        assert first["tooltipTop"] >= first["pillTop"] - 1
        assert (
          first["tooltipTop"] >= first["headingBottom"] - 1
          or first["tooltipBottom"] <= first["headingTop"] + 1
        )
        page.locator(".survey-cap-pill").last.hover()
        sizes = page.evaluate("""() => {
          const rect = selector => document.querySelector(selector).getBoundingClientRect();
          const shell = rect('#modal-shell');
          const tooltip = rect('.survey-cap-pill:last-child .survey-answer-tooltip');
          const footer = rect('#modal-actions');
          const body = document.querySelector('#modal-body');
          return {
            shellLeft: shell.left, shellRight: shell.right,
            tooltipLeft: tooltip.left, tooltipRight: tooltip.right,
            footerTop: footer.top, footerBottom: footer.bottom,
            bodyHeight: body.clientHeight, contentHeight: body.scrollHeight
          };
        }""")
        assert sizes["tooltipLeft"] >= sizes["shellLeft"] - 1
        assert sizes["tooltipRight"] <= sizes["shellRight"] + 1
        last_tip = page.locator(".survey-cap-pill:last-child .survey-answer-tooltip")
        assert last_tip.evaluate(
          "el => el.getBoundingClientRect().bottom <= innerHeight"
        )
        assert sizes["footerTop"] >= 0
        assert sizes["footerBottom"] <= height
        if height < 400:
          assert sizes["contentHeight"] > sizes["bodyHeight"]
        page.locator(".survey-id-trigger").last.hover()
        bounds = page.locator(".survey-id-wrap:hover .survey-answer-tooltip").evaluate(
          """el => {
            const tip = el.getBoundingClientRect();
            const body = el.closest('.modal-body').getBoundingClientRect();
            return {top: tip.top, bottom: tip.bottom, bodyTop: body.top, bodyBottom: body.bottom};
          }"""
        )
        assert bounds["top"] >= bounds["bodyTop"]
        assert bounds["bottom"] <= bounds["bodyBottom"]
        page.locator('#modal-actions button[value="cancel"]').click()
        assert not page.locator("#modal-shell").is_visible()
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
@pytest.mark.parametrize(("width", "height"), [(390, 844), (1200, 700), (855, 325)])
def test_blocked_bash_modal_shows_full_escaped_local_entries(
  tmp_path: Path, width: int, height: int
) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore(tmp_path / "state.sqlite3")
  line = '<img src=x onerror="window.__injected=true"> ' + "x" * 8192 + "\nnext line"
  command = 'printf "<script>alert(1)</script>"'
  append_blocked_bash(tmp_path, line=line, command=command, blocked_by="guard <reason>")
  app = SteeringApp(store)
  _, payload = app.dispatch("GET", "/blocked-bash")
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
        response = page.request.get(
          f"http://127.0.0.1:{server.server_port}/blocked-bash",
          headers={"Origin": "https://example.invalid"},
        )
        assert response.status == 200
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["cross-origin-resource-policy"] == "same-origin"
        assert "access-control-allow-origin" not in response.headers
        button = page.locator("#blocked-bash-open")
        button.click()
        row = page.locator("#blocked-bash-log .blocked-bash-entry").first
        row.wait_for()
        for field, expected in (
          ("at", payload["entries"][0]["at"]),
          ("line", line),
          ("command", command),
          ("blocked_by", "guard <reason>"),
        ):
          assert row.locator(f'[data-field="{field}"]').text_content() == expected
        assert (
          page.locator("#blocked-bash-log img, #blocked-bash-log script").count() == 0
        )
        assert page.evaluate("() => window.__injected ?? false") is False
        assert (
          button.bounding_box()["x"]
          < page.locator("#agent-interrupt").bounding_box()["x"]
        )
        assert page.locator("#modal-body").evaluate(
          "el => el.scrollHeight > el.clientHeight"
        )
        shell = page.locator("#modal-shell").bounding_box()
        footer = page.locator("#modal-actions").bounding_box()
        assert shell["x"] >= 0 and shell["x"] + shell["width"] <= width
        assert footer["y"] + footer["height"] <= height

        page.locator('#modal-actions button[value="cancel"]').click()
        assert not page.locator("#modal-shell").is_visible()
        assert button.evaluate("el => el === document.activeElement") is True
        append_blocked_bash(
          tmp_path, line="second call", command="second", blocked_by="other"
        )
        button.click()
        page.locator("#blocked-bash-log .blocked-bash-entry").nth(1).wait_for()
        assert page.locator("#blocked-bash-log .blocked-bash-entry").count() == 2
        delete_response = page.request.delete(
          f"http://127.0.0.1:{server.server_port}/blocked-bash/invalid",
          headers={"Origin": "https://example.invalid"},
        )
        assert delete_response.status == 400
        assert delete_response.headers["cross-origin-resource-policy"] == "same-origin"
        assert "access-control-allow-origin" not in delete_response.headers

        page.locator("#blocked-bash-log .blocked-bash-entry").first.locator(
          "button.audit-row-dismiss"
        ).click()
        page.wait_for_function(
          "() => document.querySelectorAll('#blocked-bash-log .blocked-bash-entry').length === 1"
        )
        remaining = page.locator("#blocked-bash-log .blocked-bash-entry").first
        page.wait_for_function(
          "document.querySelector('#blocked-bash-log button')?.disabled === false"
        )
        assert remaining.locator('[data-field="line"]').text_content() == "second call"
        assert remaining.locator("button.audit-row-dismiss").is_enabled()
        assert [
          entry["line"] for entry in app.dispatch("GET", "/blocked-bash")[1]["entries"]
        ] == ["second call"]
        remaining.locator("button.audit-row-dismiss").click()
        page.wait_for_function(
          "() => document.querySelectorAll('#blocked-bash-log .blocked-bash-entry').length === 0"
        )
        page.get_by_text("No blocked Bash calls recorded locally.").wait_for()
        assert app.dispatch("GET", "/blocked-bash") == (200, {"entries": []})

        page.locator('#modal-actions button[value="cancel"]').click()
        page.route(
          "**/blocked-bash",
          lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
              {
                "entries": [
                  {
                    "at": "stale",
                    "line": "stale",
                    "command": "stale",
                    "blocked_by": "gate",
                  }
                ]
              }
            ),
          ),
        )
        button.click()
        stale_row = page.locator("#blocked-bash-log .blocked-bash-entry").first
        stale_row.wait_for()
        assert not stale_row.locator("button.audit-row-dismiss").is_enabled()
        assert page.locator("#blocked-bash-status").text_content()
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
@pytest.mark.parametrize(("width", "height"), [(1372, 883), (411, 799)])
@pytest.mark.parametrize("source", ["message", "draft"])
def test_markdown_checklists_use_hanging_indent(
  tmp_path: Path, width: int, height: int, source: str
) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore()
  app = SteeringApp(store, repo_name="Checklist regression")
  long_text = (
    "Keep wrapped lines aligned with the first line of text when this checklist item "
    "is long enough to span several lines. "
  ) * 3
  body = (
    "- Plain bullet\n"
    + "- [x] "
    + long_text
    + "\n  - [ ] Nested "
    + long_text
    + "\n- [ ] Another task\n\n- [ ] A loose task\n\n- [x] Another loose task\n"
  )
  app.messages.send_message(body, msg_id="cb0001", blocking=False)
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
        message = page.locator('[data-msg-id="cb0001"] .message-text')
        message.wait_for()
        if source == "draft":
          page.locator("#msg").fill(body)
          page.locator("#preview-msg").click()
          target = page.locator("#draft-preview")
        else:
          target = message
        items = target.locator("li.task-list-item")
        items.first.wait_for()
        assert items.count() == 5
        page.evaluate("document.fonts.ready")
        page.screenshot(path=str(tmp_path / f"checklist-{source}-{width}.png"))
        for index in range(items.count()):
          metrics = items.nth(index).evaluate("""li => {
            const list = li.parentElement;
            const checkbox = li.querySelector('input[type=checkbox]');
            const listBox = list.getBoundingClientRect();
            const itemBox = li.getBoundingClientRect();
            const checkBox = checkbox.getBoundingClientRect();
            const probe = document.createElement('span');
            probe.textContent = '0';
            probe.style.cssText = 'position:absolute;visibility:hidden;white-space:pre';
            li.append(probe);
            const ch = probe.getBoundingClientRect().width;
            probe.remove();
            const starts = new Map();
            const walker = document.createTreeWalker(li, NodeFilter.SHOW_TEXT);
            for (let node = walker.nextNode(); node; node = walker.nextNode()) {
              if (node.parentElement.closest('li') !== li) continue;
              for (let i = 0; i < node.length; i++) {
                if (/\\s/.test(node.data[i])) continue;
                const range = document.createRange();
                range.setStart(node, i);
                range.setEnd(node, i + 1);
                const rect = range.getBoundingClientRect();
                const top = Math.round(rect.top);
                starts.set(top, Math.min(starts.get(top) ?? Infinity, rect.left));
              }
            }
            return {
              listLeft: listBox.left,
              itemLeft: itemBox.left,
              checkboxLeft: checkBox.left,
              checkboxRight: checkBox.right,
              padding: parseFloat(getComputedStyle(list).paddingInlineStart),
              ch,
              starts: [...starts.entries()].sort((a, b) => a[0] - b[0]).map(x => x[1]),
            };
          }""")
          assert metrics["padding"] == pytest.approx(2 * metrics["ch"], abs=1)
          assert metrics["itemLeft"] == pytest.approx(
            metrics["listLeft"] + metrics["padding"], abs=1
          )
          assert metrics["checkboxLeft"] >= metrics["listLeft"] - 1
          assert metrics["itemLeft"] - metrics["checkboxRight"] >= 2
          if index < 2:
            assert len(metrics["starts"]) >= 2
          assert all(
            start == pytest.approx(metrics["itemLeft"], abs=1)
            for start in metrics["starts"]
          ), (index, metrics)
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


def test_assets_bundle_fonts_styles_and_es_modules() -> None:
  for font in EXPECTED_FONTS:
    font_path = ASSETS_DIR / font
    assert font_path.is_file(), f"Missing font {font}"
    assert font_path.stat().st_size > 10_000

  for js_file in EXPECTED_JS_MODULES:
    js_path = ASSETS_DIR / js_file
    assert js_path.is_file(), f"Missing ES module {js_file}"
    proc = subprocess.run(
      ["node", "--check", str(js_path)],
      capture_output=True,
      text=True,
      check=False,
    )
    assert proc.returncode == 0, proc.stderr

  index_html = (ASSETS_DIR / "index.html").read_text(encoding="utf-8")
  assert PRELOAD_ATTR in index_html
  assert MODULEPRELOAD_ATTR in index_html
  for js_file in EXPECTED_JS_MODULES:
    assert f'rel="modulepreload" href="/static/assets/{js_file}"' in index_html
  assert MODAL_SHELL_ID in index_html
  assert CONFIRM_DELETE_TPL in index_html
  assert LUCIDE_CLOSE_ICON in index_html
  assert NOTES_PIP_ID not in index_html
  assert REPORT_PIP_ID in index_html
  assert TAB_BADGE_CLASS not in index_html
  assert STATUS_BANNER_ID not in index_html
  assert THEME_TOGGLE_ID not in index_html
  assert TOPBAR_BRAND_CLASS not in index_html

  app_js = (ASSETS_DIR / "app.js").read_text(encoding="utf-8")
  assert STATUS_BANNER_ID not in app_js
  assert THEME_TOGGLE_ID not in app_js

  style_css = (ASSETS_DIR / "style.css").read_text(encoding="utf-8")
  assert SURFACE_TOKEN in style_css
  assert CTA_TOKEN in style_css
  assert CODE_BG_TOKEN in style_css
  assert INLINE_CODE_RULE in style_css
  assert MAIN_MAX_WIDTH in style_css
  assert MESSAGE_TEXT_FONT_SIZE in style_css
  assert TASK_SECTION_TITLE_FONT_SIZE in style_css
  assert ARENA_SCROLLBAR_RULE in style_css
  assert SCROLLBAR_WIDTH_RULE in style_css
  assert SCROLLBAR_FLAT_THUMB_RULE in style_css
  assert SCROLLBAR_HOVER_RULE not in style_css
  assert "grid-auto-columns: 1fr;" in style_css
  assert ".main-content:has(> #view-messages:not([hidden]))" in style_css
  assert "margin-block: 0 8px;" in style_css
  assert STATUS_BANNER_ID not in style_css
  assert FONT_DISPLAY_BLOCK in style_css
  assert EDGE_LOADING_KEYFRAME in style_css
  assert SELECT_CHEVRON_CLASS in style_css

  messages_js = (ASSETS_DIR / "messages-view.js").read_text(encoding="utf-8")
  assert HISTORY_LIST_ID in messages_js
  assert COMPOSER_SHELL_CLASS in messages_js
  assert MANUAL_BLOCKING_INPUT not in messages_js
  assert MANUAL_HIDDEN_INPUT not in messages_js

  tasks_js = (ASSETS_DIR / "tasks-view.js").read_text(encoding="utf-8")
  assert LUCIDE_LOCK_ICON not in tasks_js
  assert "Report: " in tasks_js
  assert "Needs: " in tasks_js
  assert LUCIDE_CHEVRON_DOWN_ICON in tasks_js
  assert SELECT_CHEVRON_CLASS in tasks_js

  reports_js = (ASSETS_DIR / "reports-view.js").read_text(encoding="utf-8")
  assert CUSTOM_OPTION_MARKER in reports_js
  assert LUCIDE_COPY_ICON in reports_js
  assert LUCIDE_CLOSE_ICON in reports_js
  assert LUCIDE_SEND_ICON in reports_js
  assert REPORT_TOC_ID in reports_js
  assert REPORT_PICKER_ID in reports_js
  assert REPORT_RAIL_ID in reports_js
  assert OPTION_CUSTOM_CLASS in reports_js
  assert ON_THIS_PAGE_TEXT not in reports_js
  assert REPORT_PICKER_META_CLASS not in reports_js
  assert "report-picker-markers" in reports_js
  assert "report-picker-unseen-dot" in reports_js
  assert "report-picker-unanswered" in reports_js
  assert "reportCache" in app_js
  assert "ensureReportCached" in app_js
  assert "connectWebSocket" in app_js
  assert '#view-reports[data-loading="true"]:not([hidden])' in style_css
  assert "margin: -67px calc(50% - 50vw) -84px;" in style_css
  assert "hydrateMermaidBlocks" in app_js
  assert "toggleCodeMermaid" in app_js
  assert "/mermaid.min.js" in index_html

  timestamps_js = (ASSETS_DIR / "timestamps.js").read_text(encoding="utf-8")
  assert "nextRelativeDelay" in timestamps_js
  assert "node.textContent !== text" in timestamps_js
  assert "setInterval" not in timestamps_js

  # Finished runs arrive as a server change event. Only agent health is polled.
  intervals = re.findall(r"setInterval\(\(\) => \{(.*?)\},\s*\d+\)", app_js, re.DOTALL)
  assert len(intervals) == 1
  assert "getHealthWithConnection" in intervals[0]
  assert "refreshAll" not in intervals[0]
  assert "listTasks" not in intervals[0]

  markdown_js = (ASSETS_DIR / "markdown.js").read_text(encoding="utf-8")
  assert "const renderList = () =>" in markdown_js
  assert "listItems.push({" in markdown_js
  assert 'html.push("<hr>")' in markdown_js
  # Tables follow the GitHub shape: a single bottom rule per row, no vertical rules.
  assert "padding: 6px 13px;" in style_css
  assert "border-right: 1px solid hsl(var(--border-faint));" not in style_css
  assert "padding-inline-start: 2ch;" in style_css
  assert "inset-inline-start: -2ch;" in style_css

  reports_js = (ASSETS_DIR / "reports-view.js").read_text(encoding="utf-8")
  assert "storedValuesFor(" in reports_js
  assert "option-star" in reports_js
  assert "steer-report-drafts" in reports_js
  assert "clearDrafts(" in reports_js
  assert ".option-star {" in style_css


def test_served_app_pushes_finished_runs(tmp_path: Path) -> None:
  store = SqliteStore(tmp_path / "state.sqlite3")
  app = SteeringApp(store)
  before = app.data_version()
  runs = tmp_path / "runs"
  runs.mkdir()
  exit_path = runs / "gate-1.exit"
  exit_path.write_text("0\n", encoding="utf-8")
  assert app.data_version() != before

  after_first = app.data_version()
  (runs / "gate-2.exit").write_text("0\n", encoding="utf-8")
  assert app.data_version() != after_first


def test_hot_reload_waits_for_quiet_seconds_and_keeps_last_good_app(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  clock = [0.0]

  class ClockStop:
    def is_set(self) -> bool:
      return False

    def wait(self, interval: float) -> bool:
      clock[0] += interval
      return clock[0] >= 28

  def signature(_scripts_dir: object) -> str:
    if clock[0] >= 17:
      return "fourth"
    if clock[0] >= 5:
      return "third"
    if clock[0] >= 1:
      return "second"
    return "first"

  original_app = object()
  calls: list[tuple[float, object]] = []

  def reload_app(_server: object, app: object) -> object:
    calls.append((clock[0], app))
    if len(calls) == 1:
      raise RuntimeError("invalid module")
    return object()

  monkeypatch.setattr(steering_server, "scripts_signature", signature)
  monkeypatch.setattr(steering_server, "reload_server_handler", reload_app)
  monkeypatch.setattr(steering_server.time, "monotonic", lambda: clock[0])

  steering_server.watch_hot_reload(object(), original_app, ClockStop(), interval=1.0)

  expected_reload_times = [15.0, 27.0]
  assert [when for when, _app in calls] == expected_reload_times
  assert [app for _when, app in calls] == [original_app, original_app]


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


def test_mermaid_and_demo_media_use_warm_arena_tokens() -> None:
  markdown_js = (ASSETS_DIR / "markdown.js").read_text(encoding="utf-8")
  theme_start = markdown_js.index("themeVariables:")
  theme_end = markdown_js.index("flowchart:", theme_start)
  theme = markdown_js[theme_start:theme_end]
  for colour in (
    WARM_SURFACE_PRIMARY,
    WARM_SURFACE_SECONDARY,
    WARM_SURFACE_TERTIARY,
    WARM_SURFACE_RAISED_TERTIARY,
    WARM_TEXT_PRIMARY,
    WARM_TEXT_TERTIARY,
    WARM_BORDER_FAINT,
    WARM_BORDER_MEDIUM,
    WARM_ACCENT,
  ):
    assert colour in theme
  for colour in SLATE_MERMAID_COLORS:
    assert colour not in theme

  demo_py = DEMO_PATH.read_text(encoding="utf-8")
  for colour in (
    WARM_SURFACE_PRIMARY,
    WARM_SURFACE_SECONDARY,
    WARM_SURFACE_TERTIARY,
    WARM_TEXT_PRIMARY,
    WARM_BORDER_FAINT,
    WARM_ACCENT,
    WARM_ACCENT_RGB,
    WARM_SURFACE_PRIMARY_HSL,
    WARM_SURFACE_RAISED_HSL,
  ):
    assert colour in demo_py
  for colour in SLATE_DEMO_COLORS:
    assert colour not in demo_py

  assert WARM_SURFACE_PRIMARY in TOKENS_SWATCH_SVG
  assert WARM_ACCENT in TOKENS_SWATCH_SVG
  assert WARM_DOT_SEEN in TOKENS_SWATCH_SVG
  assert WARM_DOT_SAID in TOKENS_SWATCH_SVG
  assert WARM_ACCENT in SCROLLSPY_ZONES_SVG
  assert WARM_DOT_SAID in SCROLLSPY_ZONES_SVG


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


def test_multi_message_reply_assets() -> None:
  messages_js = (ASSETS_DIR / "messages-view.js").read_text(encoding="utf-8")
  assert RECEIPT_ID_CLASS in messages_js
  assert REPLY_PARENT_CHIP_CLASS in messages_js
  assert COMPOSER_REPLY_BAR_ID in messages_js
  assert COMPOSER_REPLY_CHIP_CLASS in messages_js
  assert PARENT_IDS_FIELD in messages_js
  assert PARENT_REFS_FIELD in messages_js
  assert "data-reference-type" in messages_js

  app_js = (ASSETS_DIR / "app.js").read_text(encoding="utf-8")
  assert REPLY_PARENT_REFS_STATE in app_js
  assert TOGGLE_REPLY_PARENT_HANDLER in app_js
  assert "event.shiftKey" in app_js

  api_js = (ASSETS_DIR / "api.js").read_text(encoding="utf-8")
  assert PARENT_IDS_FIELD in api_js
  assert PARENT_REFS_FIELD in api_js

  state_js = (ASSETS_DIR / "state.js").read_text(encoding="utf-8")
  assert REPLY_PARENT_REFS_STATE in state_js

  style_css = (ASSETS_DIR / "style.css").read_text(encoding="utf-8")
  assert ".composer-reply-bar" in style_css
  assert ".reply-parent-chip" in style_css
  assert ".parent-id-button" in style_css


def test_static_asset_contract_assets() -> None:
  index_html = (ASSETS_DIR / "index.html").read_text(encoding="utf-8")
  assert STATIC_STYLE_HREF in index_html
  assert STATIC_APP_SRC in index_html
  assert ROOT_STYLE_HREF not in index_html

  style_css = (ASSETS_DIR / "style.css").read_text(encoding="utf-8")
  assert STATIC_ASSET_PREFIX in style_css
  assert MARK_RULE in style_css
  assert "--dot-said" not in style_css

  markdown_js = (ASSETS_DIR / "markdown.js").read_text(encoding="utf-8")
  assert "<mark>$1</mark>" in markdown_js


@pytest.mark.skipif(
  not os.environ.get("ARENA_STEERING_CHROMIUM"),
  reason="Set ARENA_STEERING_CHROMIUM to run the browser regression",
)
@pytest.mark.parametrize("width", [390, 900])
def test_composer_hint_stays_on_one_line_without_fading_or_changing_draft(
  tmp_path: Path, width: int
) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore()
  app = SteeringApp(store)
  first_line = "First line " + "details " * 30
  app.messages.send_message(first_line + "\nSecond line must stay out", msg_id="abc123")
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
        composer = page.locator("#msg")
        composer.wait_for()
        assert composer.get_attribute("placeholder") == first_line
        geometry = composer.evaluate("""element => ({
          height: element.clientHeight,
          scrollHeight: element.scrollHeight,
          wrap: getComputedStyle(element).whiteSpace,
          mask: getComputedStyle(element).maskImage,
        })""")
        assert geometry["wrap"] == "nowrap", geometry
        assert geometry["scrollHeight"] <= geometry["height"] + 1, geometry
        assert geometry["mask"] == "none", geometry
        page.screenshot(path=str(tmp_path / f"composer-hint-{width}.png"))

        composer.fill("A draft that wraps as needed")
        assert (
          composer.evaluate("element => getComputedStyle(element).whiteSpace")
          != "nowrap"
        )
        assert composer.input_value() == "A draft that wraps as needed"
        assert composer.evaluate("element => document.activeElement === element")
      finally:
        browser.close()
  finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=3)
    store.close()


def test_composer_upload_drop_expand_assets() -> None:
  messages_js = (ASSETS_DIR / "messages-view.js").read_text(encoding="utf-8")
  assert "readComposerDraft" in messages_js
  assert "writeComposerDraft" in messages_js
  assert "submittedDraft" in messages_js
  assert "reply-seen-sentinel" in messages_js
  assert "replies_revision" in messages_js
  assert "seenAckCounts" not in messages_js
  assert COMPOSER_ATTACHMENTS_ID in messages_js
  assert ATTACH_FILE_ID in messages_js
  assert COMPOSER_EXPAND_ID in messages_js
  assert "data-remove-composer-attachment" in messages_js
  assert "composer-attachment-chip" in messages_js
  assert 'event.key === "Enter" && !event.shiftKey && !event.isComposing' in messages_js
  assert 'window.matchMedia?.("(pointer: coarse)")?.matches' in messages_js
  assert "PASTE_ATTACHMENT_CHAR_THRESHOLD = 1500" in messages_js
  assert "PASTE_ATTACHMENT_LINE_THRESHOLD = 15" in messages_js
  assert "pasted-text.txt" in messages_js
  assert 'listen(msgEl, "paste"' in messages_js
  assert 'addEventListener("drop"' in messages_js
  assert 'addEventListener("dragover"' in messages_js
  assert "attachments" in messages_js

  api_js = (ASSETS_DIR / "api.js").read_text(encoding="utf-8")
  assert UPLOAD_FILE_API in api_js
  assert SEND_MESSAGE_WITH_FILE_API in api_js
  assert '"/uploads"' in api_js
  assert '"/messages/with-file"' in api_js
  assert "FormData" in api_js

  app_js = (ASSETS_DIR / "app.js").read_text(encoding="utf-8")
  uploads_js = (ASSETS_DIR / "composer-uploads.js").read_text(encoding="utf-8")
  assert COMPOSER_ATTACHMENTS_STATE in uploads_js
  assert "onStageComposerFiles" in app_js
  assert "onRemoveComposerAttachment" in app_js
  assert "onToggleComposerExpanded" in app_js
  assert SEND_MESSAGE_WITH_FILE_API in app_js

  state_js = (ASSETS_DIR / "state.js").read_text(encoding="utf-8")
  assert COMPOSER_ATTACHMENTS_STATE in state_js
  assert COMPOSER_EXPANDED_STATE in state_js

  style_css = (ASSETS_DIR / "style.css").read_text(encoding="utf-8")
  assert ".composer-attachments" in style_css
  assert ".composer-attachment-chip" in style_css
  assert ".composer-expanded" in style_css
  assert ".composer-drop-active" in style_css


@pytest.mark.skipif(
  not os.environ.get("ARENA_STEERING_CHROMIUM"),
  reason="Set ARENA_STEERING_CHROMIUM to run the browser regression",
)
def test_task_age_updates_priority_and_current_in_browser(tmp_path: Path) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore(tmp_path / "age.sqlite3")
  app = SteeringApp(store)
  app.tasks.create_task("old", "Old", size=5, priority="P4", details=["Work"])
  app.tasks.create_task("new", "New", size=1, priority="P4", details=["Work"])
  created = (datetime.now(UTC) - timedelta(minutes=59, seconds=53)).isoformat()
  with store.transaction():
    store._conn.execute("UPDATE tasks SET created_at = ? WHERE id = 'old'", (created,))
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
        page.goto(f"http://127.0.0.1:{server.server_port}/?transport=ws")
        page.locator("#tab-tasks").click()
        page.locator('[data-task-id="old"] summary').click()
        page.locator('[data-task-id="old"] li').get_by_text("Priority: P3").wait_for(
          timeout=15000
        )
        assert store.get_task("old").priority == "P4"
        assert app.tasks.list_tasks()[0][0].id == "old"
        page.screenshot(path=str(tmp_path / "aged-task.png"))
      finally:
        browser.close()
  finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)
    store.close()


def test_linked_tasks_do_not_break_message_rendering() -> None:
  script = """
import assert from 'node:assert/strict';
import { renderMessagesView } from './skills/arena-steering/assets/messages-view.js';
globalThis.document = { activeElement: null };
const container = {
  innerHTML: '',
  querySelector() { return null; },
  querySelectorAll() { return []; },
  addEventListener() {},
};
renderMessagesView(container, {
  messages: [{ id: 'abc123', body: 'hello', acks: [], created_at: '2026-01-01T00:00:00Z' }],
  tasks: [{ id: 'linked-task', links: { msg_ids: ['abc123'] } }],
}, {});
assert.match(container.innerHTML, /linked-task/);
"""
  result = subprocess.run(
    ["node", "--experimental-default-type=module", "--input-type=module", "-e", script],
    cwd=SKILL_DIR.parents[1],
    capture_output=True,
    text=True,
    check=False,
  )
  assert result.returncode == 0, result.stderr


def test_messages_status_shows_native_tool_cadence() -> None:
  script = r"""
import assert from 'node:assert/strict';
import { renderMessagesView } from './skills/arena-steering/assets/messages-view.js';
globalThis.document = { activeElement: null };
const container = {
  innerHTML: '',
  querySelector() { return null; },
  querySelectorAll() { return []; },
  addEventListener() {},
};
const at = new Date(Date.now() - 3000).toISOString();
function render(lastTool, callsSinceMessage, survey = {}) {
  container.innerHTML = '';
  renderMessagesView(container, {
    messages: [], tasks: [], survey, lastTool, callsSinceMessage,
  }, {});
  return container.innerHTML;
}
let html = render({ tool: 'read', at }, 4);
assert.match(html, /<p id="last-check" class="muted">Read <time/);
assert.doesNotMatch(html, /Read 4/);
assert.match(html, /data-include-seconds="true"/);
assert.match(html, /data-compact="true"/);
for (const [tool, label] of [['edit', 'Edit'], ['write', 'Write']]) {
  html = render({ tool, at }, 3);
  assert.match(html, new RegExp(`<p id="last-check" class="muted">${label} <time`));
  assert.doesNotMatch(html, new RegExp(`${label} 3`));
}
html = render({ tool: 'bash', at }, 2);
assert.match(html, /<p id="last-check" class="muted">Bash 2 <time/);
html = render({ tool: 'bash', at }, 0);
assert.match(html, /<p id="last-check" class="muted">Bash <time/);
assert.doesNotMatch(html, /Bash 0/);
html = render(null, 0, { checked_at: at });
assert.match(html, /<p id="last-check" class="muted">Checked <time/);
html = render(null, 0);
assert.match(html, /<p id="last-check" class="muted"><\/p>/);
assert.doesNotMatch(html, /Live steering active/);
"""
  result = subprocess.run(
    ["node", "--experimental-default-type=module", "--input-type=module", "-e", script],
    cwd=SKILL_DIR.parents[1],
    capture_output=True,
    text=True,
    check=False,
  )
  assert result.returncode == 0, result.stderr

  app_js = (ASSETS_DIR / "app.js").read_text(encoding="utf-8")
  assert "health.last_tool" in app_js
  assert "health.calls_since_message" in app_js
  signature = app_js.partition("const nextSignature = JSON.stringify({")[2].partition(
    "});"
  )[0]
  assert "lastTool," in signature
  assert "callsSinceMessage," in signature
  state_update = app_js.partition("lastDataSignature = nextSignature;")[2].partition(
    "});"
  )[0]
  assert "lastTool," in state_update
  assert "callsSinceMessage," in state_update


def test_message_receipts_show_sent_and_seen_and_name_acked_state() -> None:
  script = r"""
import assert from 'node:assert/strict';
import { renderMessagesView } from './skills/arena-steering/assets/messages-view.js';
globalThis.document = { activeElement: null };
const container = {
  innerHTML: '',
  querySelector() { return null; },
  querySelectorAll() { return []; },
  addEventListener() {},
};
renderMessagesView(container, {
  showHidden: true,
  messages: [
    {id: 'aa0001', body: 'Hidden seen', status: 'seen', hidden: true, blocking: false},
    {id: 'aa0002', body: 'Seen', status: 'seen', hidden: false, blocking: true},
    {id: 'aa0003', body: 'Sent', status: 'sent', hidden: false, blocking: false},
    {id: 'aa0004', body: 'Acked', status: 'acked', hidden: false, blocking: true, acks: ['Done']},
  ],
}, {});
const card = id => container.innerHTML.match(
  new RegExp(`<li class="message" data-msg-id="${id}"[\\s\\S]*?</li>`)
)?.[0];
const hidden = card('aa0001'), seen = card('aa0002'), sent = card('aa0003'), acked = card('aa0004');
assert.ok(hidden && seen && sent && acked);
assert.match(hidden, /data-hidden="true"/);
assert.match(hidden, /data-state-label="Hidden message. Status: seen" data-prefix="Seen"/);
assert.doesNotMatch(hidden, /· hidden|· checkpoint/);
assert.match(seen, /data-state-label="Status: seen" data-prefix="Seen"/);
assert.match(sent, /data-state-label="Status: sent" data-prefix="Sent"/);
assert.doesNotMatch(sent, /· checkpoint/);
assert.match(acked, /data-state-label="Status: acked" data-prefix=""/);
for (const item of [hidden, seen, sent, acked]) {
  assert.doesNotMatch(item, /state-dot/);
  assert.match(item, /<time class="receipt-bottom receipt-status"[^>]*>[^<]*<\/time>/);
}
"""
  result = subprocess.run(
    ["node", "--experimental-default-type=module", "--input-type=module", "-e", script],
    cwd=SKILL_DIR.parents[1],
    capture_output=True,
    text=True,
    check=False,
  )
  assert result.returncode == 0, result.stderr


def test_image_lightbox_assets() -> None:
  index = (ASSETS_DIR / "index.html").read_text(encoding="utf-8")
  app = (ASSETS_DIR / "app.js").read_text(encoding="utf-8")
  css = (ASSETS_DIR / "style.css").read_text(encoding="utf-8")
  image_modal_id = 'id="image-modal"'
  assert image_modal_id in index
  assert "image-modal" in app
  assert "wheel" in app
  assert "pointerdown" in app
  assert ".mermaid-diagram svg" in app
  assert ".mermaid-block svg" in app
  assert ".image-modal" in css


def test_image_lightbox_interactions() -> None:
  script = r"""
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
const source = readFileSync('skills/arena-steering/assets/app.js', 'utf8');
const code = source.slice(source.indexOf('function initImageModal()'), source.indexOf('function initEvents()'));
function element() {
  return { handlers: {}, addEventListener(type, fn) { this.handlers[type] = fn; },
    setPointerCapture() {}, replaceChildren(...children) { this.firstElementChild = children[0] || null; } };
}
const dialog = element(), stage = element(), close = element(), doc = element();
dialog.showModal = () => { dialog.open = true; };
dialog.close = () => { dialog.open = false; dialog.handlers.close(); };
doc.getElementById = id => ({ 'image-modal': dialog, 'image-modal-stage': stage, 'image-modal-close': close })[id];
vm.runInNewContext(code + '\ninitImageModal();', { document: doc, Math });
const clone = { style: {}, removeAttribute() {}, setAttribute() {},
  getAttribute() { return null; }, querySelector() { return null; } };
const media = { tagName: 'IMG', cloneNode() { return clone; } };
const target = { closest(selector) { return selector.startsWith('#') ? {} : media; } };
doc.handlers.click({ target, preventDefault() {} });
assert.equal(dialog.open, true);
assert.equal(stage.firstElementChild, clone);
const initial = clone.style.transform;
stage.handlers.wheel({ preventDefault() {}, deltaY: -200 });
assert.notEqual(clone.style.transform, initial);
const zoomed = clone.style.transform;
stage.handlers.pointerdown({ button: 0, pointerId: 11, clientX: 100, clientY: 100 });
stage.handlers.pointerdown({ button: 0, pointerId: 12, clientX: 200, clientY: 100 });
stage.handlers.pointermove({ pointerId: 12, clientX: 300, clientY: 100 });
const pinched = clone.style.transform;
const wheelScale = Number(/scale\(([\d.]+)\)/.exec(zoomed)[1]);
const pinchScale = Number(/scale\(([\d.]+)\)/.exec(pinched)[1]);
assert.ok(Math.abs(pinchScale - wheelScale * 2) < 1e-9, `spreading two pointers doubles the scale, got ${pinched}`);
stage.handlers.pointerup({ pointerId: 11 });
stage.handlers.pointerup({ pointerId: 12 });
stage.handlers.wheel({ preventDefault() {}, deltaY: 0 });
stage.handlers.pointerdown({ button: 0, pointerId: 1, clientX: 10, clientY: 10 });
stage.handlers.pointermove({ pointerId: 1, clientX: 50, clientY: 35 });
assert.notEqual(clone.style.transform, zoomed);
let prevented = false;
stage.handlers.dragstart({ preventDefault() { prevented = true; } });
assert.equal(prevented, true);
stage.handlers.pointerdown({ button: 0, pointerId: 2, clientX: 200, clientY: 200 });
stage.handlers.pointermove({ pointerId: 2, clientX: 260, clientY: 240 });
stage.handlers.pointerup({ pointerId: 2 });
dialog.handlers.click({ target: stage });
assert.equal(dialog.open, true, 'a pan must not close the viewer');
const styleNode = { textContent: '#mermaid-x .node{fill:red}' };
const svgClone = { style: {}, removeAttribute() {}, setAttribute(name, value) { this[name] = value; },
  getAttribute(name) { return name === 'id' ? 'mermaid-x' : null; },
  querySelector(selector) { return selector === 'style' ? styleNode : null; } };
const svgMedia = { tagName: 'svg', getBoundingClientRect() { return { width: 866 }; },
  cloneNode() { return svgClone; } };
const svgTarget = { closest(selector) { return selector.startsWith('#') ? {} : svgMedia; } };
doc.handlers.click({ target: svgTarget, preventDefault() {} });
assert.equal(svgClone.class, 'mermaid-svg');
assert.equal(svgClone.style.width, '866px');
assert.equal(svgClone.id, 'mermaid-x-viewer-1');
assert.equal(styleNode.textContent, '#mermaid-x-viewer-1 .node{fill:red}');
close.handlers.click();
stage.handlers.pointerdown({ button: 0, pointerId: 3, clientX: 300, clientY: 300 });
stage.handlers.pointerup({ pointerId: 3 });
dialog.handlers.click({ target: stage });
assert.equal(dialog.open, false, 'a click on the backdrop closes the viewer');
dialog.showModal();
close.handlers.click();
assert.equal(dialog.open, false);
assert.equal(stage.firstElementChild, null);
"""
  result = subprocess.run(
    ["node", "--input-type=module", "-e", script],
    cwd=SKILL_DIR.parents[1],
    capture_output=True,
    text=True,
    check=False,
  )
  assert result.returncode == 0, result.stderr


@pytest.mark.skipif(
  not os.environ.get("ARENA_STEERING_CHROMIUM"),
  reason="Set ARENA_STEERING_CHROMIUM to run the browser regression",
)
@pytest.mark.parametrize("width", [390, 1200])
def test_message_image_attachment_uses_existing_modal_and_keeps_other_files(
  tmp_path: Path, width: int
) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore(tmp_path / "state.sqlite3")
  app = SteeringApp(store)

  def png_chunk(tag: bytes, data: bytes) -> bytes:
    return (
      struct.pack(">I", len(data))
      + tag
      + data
      + struct.pack(">I", zlib.crc32(tag + data))
    )

  png = (
    b"\x89PNG\r\n\x1a\n"
    + png_chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0))
    + png_chunk(b"IDAT", zlib.compress(b"\x00\xff\x80\x40\xff"))
    + png_chunk(b"IEND", b"")
  )
  _, uploaded = app.dispatch(
    "POST",
    "/uploads",
    {"name": "evidence.png", "content_base64": base64.b64encode(png).decode("ascii")},
  )
  image = {**uploaded["attachment"], "name": 'A "photo" <today>.png'}
  _, uploaded_text = app.dispatch(
    "POST", "/uploads", {"name": "notes.txt", "text": "Keep as text."}
  )
  _, created = app.dispatch(
    "POST",
    "/messages/with-file",
    {
      "body": "See attached files.",
      "attachments": [
        image,
        uploaded_text["attachment"],
        {"name": "gone.png", "path": image["path"], "present": False},
      ],
    },
  )
  msg_id = created["message"]["id"]
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
        card = page.locator(f'.message[data-msg-id="{msg_id}"]')
        thumb = card.get_by_role("button", name='View image A "photo" <today>.png')
        thumb.wait_for()
        assert thumb.get_attribute("title") is None
        assert card.locator(".message-attachment-file[title]").count() == 0
        assert card.locator(".parent-id-button[title]").count() == 0
        assert card.locator(".message-attachment-preview").count() == 1
        assert thumb.locator("img").evaluate(
          "image => image.complete && image.naturalWidth === 1"
        )
        assert card.locator(".receipt-filename").all_text_contents() == [
          "notes.txt",
          "gone.png (missing)",
        ]
        assert card.locator('img[src$=".txt"]').count() == 0
        assert thumb.locator(".attachment-name-tail").inner_text() == "ay>.png"
        assert (
          card.locator(".message-attachment-file")
          .first.locator(".attachment-name-tail")
          .inner_text()
          == "tes.txt"
        )
        assert thumb.locator(".attachment-name-head").evaluate(
          "el => el.scrollWidth > el.clientWidth"
        )
        bounds, card_bounds = thumb.bounding_box(), card.bounding_box()
        assert bounds and card_bounds
        assert bounds["width"] <= 100
        assert (
          card.locator(".message-attachment-file svg.lucide-file-text").count() == 2
        )
        assert card.locator(".message-attachment-file").count() == 2
        assert bounds["x"] >= card_bounds["x"] - 1
        assert (
          bounds["x"] + bounds["width"] <= card_bounds["x"] + card_bounds["width"] + 1
        )

        thumb.click()
        viewer = page.locator("#image-modal")
        viewer.wait_for(state="visible")
        assert (
          page.locator("#image-modal-stage > img").get_attribute("src") == image["url"]
        )
        page.keyboard.press("Escape")
        viewer.wait_for(state="hidden")
        thumb.focus()
        page.keyboard.press("Enter")
        viewer.wait_for(state="visible")
        page.locator("#image-modal-close").click()
        viewer.wait_for(state="hidden")
        page.screenshot(path=str(tmp_path / f"attachment-{width}.png"))
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
              inset: parseFloat(css.borderLeftWidth) + parseFloat(css.paddingLeft),
            };
          }
          return {text: measure('.field-text-input'), custom: measure('.custom-text-input')};
        }""")
        assert metrics["custom"]["inset"] == metrics["text"]["inset"]
        assert metrics["custom"]["height"] == 32
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
          "#report .field-id-chip": 12,
          "#report .field-id-chip > code": 11,
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
@pytest.mark.parametrize("width", [390, 855, 1372])
def test_fenced_markdown_code_uses_one_smaller_type_token(
  tmp_path: Path, width: int
) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore(tmp_path / "state.sqlite3")
  app = SteeringApp(store, repo_name="Fenced code ramp")
  app.messages.send_message(
    "Message prose with `inline`.\n\n```python\nprint('message')\n```",
    msg_id="fc0001",
    blocking=False,
  )
  app.messages.ack("fc0001", "Reply prose.\n\n```text\nreply line\n```")
  app.reports.publish_report(
    "fenced-code",
    "Fenced code",
    "Report prose with `inline`.\n\n```python\nprint('report')\n```\n\n"
    '<!-- question {"id":"note","label":"Note"} -->\nNote: ___\n',
  )
  answer = app.reports.submit_answer("fenced-code", {"note": "Answered"})
  app.reports.ack_answer(
    "fenced-code", answer.id, "Report reply prose.\n\n```text\nack line\n```"
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
        page.locator('.message[data-msg-id="fc0001"] .code-block').first.wait_for()
        page.evaluate("""async () => {
          const { renderMarkdownBlock } = await import('/static/assets/markdown.js');
          const holder = document.createElement('div');
          holder.id = 'client-markdown';
          holder.className = 'message-text';
          holder.innerHTML = renderMarkdownBlock('Client prose.\\n\\n```python\\nprint(1)\\n```');
          document.querySelector('#view-messages').append(holder);
          const loose = document.createElement('pre');
          loose.id = 'loose-code';
          loose.innerHTML = '<code>not Markdown fenced code</code>';
          holder.append(loose);
        }""")
        page.locator("#client-markdown .code-block").wait_for()
        selectors = {
          "body": ".message-bubble > .message-text p",
          "fence": ".message-bubble > .message-text .code-block pre > code",
          "label": ".message-bubble > .message-text .code-block-header",
          "inline": ".message-bubble > .message-text p > code",
          "client": "#client-markdown .code-block pre > code",
          "client_label": "#client-markdown .code-block-header",
          "reply": ".answer.reply .code-block pre > code",
          "reply_label": ".answer.reply .code-block-header",
          "reply_prose": ".answer.reply p",
          "loose": "#loose-code > code",
        }

        def sizes(wanted: dict[str, str]) -> dict[str, float]:
          return page.evaluate(
            """selectors => Object.fromEntries(
            Object.entries(selectors).map(([key, selector]) => {
              const element = document.querySelector(selector);
              if (!element) throw new Error(`Missing ${key}: ${selector}`);
              return [key, parseFloat(getComputedStyle(element).fontSize)];
            })
          )""",
            wanted,
          )

        measured = sizes(selectors)
        assert measured["body"] == 16
        assert (
          measured["fence"]
          == measured["label"]
          == measured["client"]
          == measured["client_label"]
          == 14
        )
        assert measured["fence"] < measured["body"]
        assert measured["inline"] == measured["loose"] == 14.4
        assert measured["reply_prose"] == 13
        assert measured["reply"] == measured["reply_label"] == 12
        assert measured["reply"] < measured["reply_prose"]
        page.screenshot(path=str(tmp_path / f"fenced-code-messages-{width}.png"))

        page.locator("#tab-reports").click()
        page.locator("#report .code-block pre > code").wait_for()
        page.locator("#report-ack-history .code-block").wait_for()
        report = sizes(
          {
            "prose": "#report p",
            "fence": "#report .code-block pre > code",
            "label": "#report .code-block-header",
            "inline": "#report p > code",
            "ack_prose": "#report-ack-history .report-ack-markdown p",
            "ack_fence": "#report-ack-history .code-block pre > code",
            "ack_label": "#report-ack-history .code-block-header",
          }
        )
        assert report["prose"] == 16
        assert report["fence"] == report["label"] == report["inline"] == 14
        assert report["fence"] < report["prose"]
        assert report["ack_prose"] == 13
        assert report["ack_fence"] == report["ack_label"] == 12
        assert report["ack_fence"] < report["ack_prose"]
        page.screenshot(path=str(tmp_path / f"fenced-code-{width}.png"))
      finally:
        browser.close()
  finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)
    store.close()


def test_composer_upload_manager_handles_failures_and_concurrent_changes():
  script = r"""
import assert from 'node:assert/strict';
import { createComposerUploads } from './skills/arena-steering/assets/composer-uploads.js';
let state = { composerAttachments: [] }, rejectFirst, calls = 0;
const store = { getState: () => state, setState: (patch) => { state = {...state, ...patch}; } };
const uploads = createComposerUploads(store, async (file) => {
  calls++;
  if (file.name === 'first' && calls === 1) return new Promise((resolve, reject) => { rejectFirst = reject; });
  return {name: file.name};
});
const first = uploads.stage([{name:'first'}]);
assert.equal(state.composerAttachments[0].status, 'uploading');
const firstId = state.composerAttachments[0].id;
await uploads.stage([{name:'second'}]);
const secondId = state.composerAttachments[1].id;
assert.deepEqual(state.composerAttachments.map(x => x.status), ['uploading', 'ready']);
rejectFirst(new Error('offline'));
await first;
assert.equal(state.composerAttachments[0].status, 'failed');
await uploads.retry(firstId);
assert.deepEqual(state.composerAttachments.map(x => x.status), ['ready', 'ready']);
uploads.clearSent([firstId]);
assert.deepEqual(state.composerAttachments.map(x => x.name), ['second']);
uploads.remove(secondId);
assert.equal(state.composerAttachments.length, 0);
const pending = uploads.stage([{name:'first'}]);
uploads.remove(state.composerAttachments[0].id);
await pending;
assert.equal(state.composerAttachments.length, 0);
"""
  result = subprocess.run(
    ["node", "--experimental-default-type=module", "--input-type=module", "-e", script],
    cwd=SKILL_DIR.parents[1],
    capture_output=True,
    text=True,
    check=False,
  )
  assert result.returncode == 0, result.stderr


def test_report_navigation_preloads_on_pointer_and_keyboard_intent():
  app_js = (ASSETS_DIR / "app.js").read_text(encoding="utf-8")
  assert 'addEventListener("pointerover", preloadReport)' in app_js
  assert 'addEventListener("focusin", preloadReport)' in app_js
  assert "pendingReportLoads" in app_js
  assert "quiet: true" in app_js


def test_message_search_narrows_loaded_results_without_requerying():
  script = r"""
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
const source = readFileSync('skills/arena-steering/assets/app.js', 'utf8');
const start = source.indexOf('export function messageMatchesQuery');
const end = source.indexOf('async function fetchMessagePage');
const code = source.slice(start, end).replace('export ', '');
const context = {};
vm.runInNewContext(`${code}\nthis.messageMatchesQuery = messageMatchesQuery;`, context);
const message = { id: 'a1b2c3', body: 'Refactor the composer', parent_ids: ['dd0001'], acks: ['Agreed'] };
assert.equal(context.messageMatchesQuery(message, ''), true);
assert.equal(context.messageMatchesQuery(message, 'C'), true);
assert.equal(context.messageMatchesQuery(message, 'KK'), false);
assert.equal(context.messageMatchesQuery(message, 'com'), true);
assert.equal(context.messageMatchesQuery(message, 'dd00'), true);
assert.equal(context.messageMatchesQuery(message, 'agreed'), true);
assert.equal(context.messageMatchesQuery(message, 'zzz'), false);
"""
  result = subprocess.run(
    ["node", "--input-type=module", "-e", script],
    cwd=SKILL_DIR.parents[1],
    capture_output=True,
    text=True,
    check=False,
  )
  assert result.returncode == 0, result.stderr
  app_js = (ASSETS_DIR / "app.js").read_text(encoding="utf-8")
  assert "searchBase && needle.startsWith(searchBase.query)" in app_js
  assert "searchBase = { query: activeQuery, messages: merged, hasMore }" in app_js


@pytest.mark.skipif(
  not os.environ.get("ARENA_STEERING_CHROMIUM"),
  reason="Set ARENA_STEERING_CHROMIUM to run the browser regression",
)
def test_task_answer_details_render_once_and_wrap_on_mobile(tmp_path: Path) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore()
  app = SteeringApp(store, repo_name="Task detail regression")
  answer = "A" * 180
  app.reports.publish_report(
    "choice",
    "Choice",
    (
      '<!-- question {"id": "choice", "label": "Choice?"} -->\n'
      "Choice?\n"
      f'- (x) {answer} <!-- option {{"label": "{answer}"}} -->\n'
    ),
  )
  task = app.tasks.create_task(
    "work", "Review choice", size=3, details=["Review"], report_ids=["choice"]
  )
  app.reports.submit_answer("choice", {"choice": answer}, answer_id="ba2001")
  app.reports.ack_answer("choice", "ba2001", "Read")
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
        for name, width, height in (("desktop", 1200, 700), ("mobile", 390, 844)):
          context = browser.new_context(viewport={"width": width, "height": height})
          page = context.new_page()
          errors: list[str] = []
          page.on("pageerror", lambda error, errors=errors: errors.append(str(error)))
          page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
          page.locator("#tab-tasks").click()
          row = page.locator('[data-task-id="work"]').first
          row.locator("summary").click()
          page.wait_for_function(
            """() => {
              const details = document.querySelector('details.task-details[open]');
              const list = details?.querySelector('.task-detail-list');
              return list && details.getBoundingClientRect().bottom >=
                list.getBoundingClientRect().bottom - 1;
            }"""
          )
          details = row.locator("li.task-detail").all_text_contents()
          assert details == [
            f"Priority: {task.priority}",
            f"Size: {task.size}",
            "Report: choice",
            "Review",
            f"Choice?: {answer}",
          ]
          assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
          assert not errors
          page.screenshot(path=str(tmp_path / f"task-details-{name}.png"))
          context.close()
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
  not os.environ.get("ARENA_STEERING_CHROMIUM"),
  reason="Set ARENA_STEERING_CHROMIUM to run the browser regression",
)
def test_task_search_highlights_matches_and_clear_collapses_details() -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore()
  app = SteeringApp(store, repo_name="Task search regression")
  app.tasks.create_task(
    "alpha-task",
    "Alpha <plan>",
    size=3,
    details=["Alpha detail", "Literal <manual> & safe"],
  )
  app.tasks.create_task("other-task", "Other work", size=3, details=["Other detail"])
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
        for width, height in ((1200, 700), (390, 844)):
          context = browser.new_context(viewport={"width": width, "height": height})
          page = context.new_page()
          page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
          page.locator("#tab-tasks").click()
          row = page.locator('li.task[data-task-id="alpha-task"]')
          search = page.locator("#task-search")
          details = row.locator("details.task-details")
          details.locator("summary").click()
          assert details.get_attribute("open") is not None
          title = row.locator(".task-title")
          detail = row.locator(".task-detail").filter(has_text="Alpha detail")
          original_title_width = title.evaluate(
            "el => el.getBoundingClientRect().width"
          )
          original_suffix_x = detail.evaluate("""el => {
            const range = document.createRange();
            range.setStart(el.firstChild, 6);
            range.setEnd(el.firstChild, 7);
            return range.getBoundingClientRect().x;
          }""")

          search.fill("Alpha")
          highlighted_title_width = title.evaluate(
            "el => el.getBoundingClientRect().width"
          )
          highlighted_suffix_x = detail.evaluate("""el => {
            const range = document.createRange();
            range.setStart(el.lastChild, 1);
            range.setEnd(el.lastChild, 2);
            return range.getBoundingClientRect().x;
          }""")
          assert abs(highlighted_title_width - original_title_width) <= 1
          assert abs(highlighted_suffix_x - original_suffix_x) <= 1
          assert row.locator(".task-title mark.search-hit").all_text_contents() == [
            "Alpha"
          ]
          assert row.locator(".task-detail mark.search-hit").all_text_contents() == [
            "Alpha"
          ]
          assert details.get_attribute("open") is not None

          search.fill("<manual>")
          assert details.get_attribute("open") is not None
          assert row.locator(".task-detail mark.search-hit").all_text_contents() == [
            "<manual>"
          ]
          assert row.locator("manual").count() == 0
          assert row.locator(".task-title mark.search-hit").count() == 0

          search.fill("")
          assert page.locator("details.task-details[open]").count() == 0
          search.fill("<manual>")
          assert details.get_attribute("open") is not None
          search.fill("")
          assert page.locator("details.task-details[open]").count() == 0
          details.locator("summary").click()
          assert details.get_attribute("open") is not None
          page.locator("#task-type-filter").select_option("code")
          assert details.get_attribute("open") is not None
          context.close()
      finally:
        browser.close()
  finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)
    store.close()


def test_task_gate_shimmer_uses_two_blue_shades() -> None:
  css = (ASSETS_DIR / "style.css").read_text()
  rule = css.split('.task-title[data-gate-running="true"] {', 1)[1].split("}", 1)[0]
  assert "#90caf9" in rule
  assert "#42a5f5" in rule
  assert "#dcefff" not in rule


@pytest.mark.skipif(
  not os.environ.get("ARENA_STEERING_CHROMIUM"),
  reason="Set ARENA_STEERING_CHROMIUM to run the browser regression",
)
@pytest.mark.parametrize("width", [390, 1200])
def test_task_marker_tracks_first_line_of_wrapped_title(
  tmp_path: Path, width: int
) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore()
  app = SteeringApp(store)
  app.tasks.create_task(
    "wrapped-title",
    "Investigate the alignment of task list bullets when a very long "
    "task title wraps across multiple lines even in a wide desktop viewport",
    size=3,
    details=["Review marker"],
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
        page = browser.new_page(viewport={"width": width, "height": 850})
        page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
        page.locator("#tab-tasks").click()
        title = page.locator('li.task[data-task-id="wrapped-title"] > .task-title')
        lines = title.evaluate("""element => {
          const text = element.firstChild;
          const range = document.createRange();
          range.setStart(text, 0);
          range.setEnd(text, 1);
          const first = range.getBoundingClientRect();
          range.setStart(text, text.length - 1);
          range.setEnd(text, text.length);
          const last = range.getBoundingClientRect();
          return {left: element.getBoundingClientRect().left,
            firstY: first.y, firstHeight: first.height, lastY: last.y};
        }""")
        assert lines["lastY"] - lines["firstY"] > lines["firstHeight"]
        screenshot = page.screenshot(path=str(tmp_path / f"task-marker-{width}.png"))
        marker = page.evaluate(
          """async ({png, left, firstY, firstHeight, lastY}) => {
          const image = new Image();
          image.src = `data:image/png;base64,${png}`;
          await image.decode();
          const canvas = document.createElement('canvas');
          canvas.width = image.width;
          canvas.height = image.height;
          const ctx = canvas.getContext('2d');
          ctx.drawImage(image, 0, 0);
          const pixels = ctx.getImageData(0, 0, image.width, image.height).data;
          const hits = [];
          for (let y = Math.floor(firstY) - 3; y <= Math.ceil(lastY + firstHeight) + 3; y++) {
            for (let x = Math.round(left) - 20; x <= Math.round(left) - 8; x++) {
              const index = (y * image.width + x) * 4;
              if (pixels[index] > 120 && pixels[index + 1] > 120 && pixels[index + 2] > 120) {
                hits.push(y);
                break;
              }
            }
          }
          return hits.length ? {top: hits[0], bottom: hits.at(-1)} : null;
        }""",
          {"png": base64.b64encode(screenshot).decode("ascii"), **lines},
        )
        assert marker is not None
        marker_center = (marker["top"] + marker["bottom"]) / 2
        first_center = lines["firstY"] + lines["firstHeight"] / 2
        assert abs(marker_center - first_center) < lines["firstHeight"] / 2, (
          width,
          marker_center,
          first_center,
        )
        title.click()
        page.locator('#tab-messages[aria-selected="true"]').wait_for()
        assert page.locator("#msg").evaluate("el => document.activeElement === el")
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
def test_main_panel_keeps_small_shared_header_gap(tmp_path: Path) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore(tmp_path / "state.sqlite3")
  app = SteeringApp(store, repo_name="Panel header gap")
  app.tasks.create_task("one-task", "One task", size=2, details=["Review"])
  app.reports.publish_report("one-report", "One report", "# One report")
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
        for width, height, expected_gap in (
          (1372, 883, 12),
          (855, 325, 4),
          (411, 799, 8),
        ):
          page = browser.new_page(
            viewport={"width": width, "height": height},
            reduced_motion="reduce",
          )
          page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
          for tab in ("messages", "reports", "tasks"):
            page.locator(f"#tab-{tab}").click()
            gap = page.evaluate("""() => {
              const header = document.querySelector('.topbar');
              const main = document.querySelector('.main-content');
              const panel = main.querySelector('section[role="tabpanel"]:not([hidden])');
              return {
                padding: parseFloat(getComputedStyle(main).paddingTop),
                distance: panel.getBoundingClientRect().top - header.getBoundingClientRect().bottom,
                overflow: document.documentElement.scrollWidth > innerWidth,
              };
            }""")
            assert gap["padding"] == expected_gap, (width, height, tab, gap)
            assert abs(gap["distance"] - expected_gap) < 1, (
              width,
              height,
              tab,
              gap,
            )
            assert not gap["overflow"], (width, height, tab, gap)
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
def test_tasks_toolbar_row_divider_and_fade_follow_scroll(tmp_path: Path) -> None:
  import base64

  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore()
  app = SteeringApp(store, repo_name="Task edge regression")
  for index in range(28):
    app.tasks.create_task(
      f"work-{index:02d}",
      f"Work item {index} with a longer title",
      size=3,
      details=["Review"],
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
        for name, width, height in (
          ("desktop", 1372, 883),
          ("landscape", 855, 325),
          ("mobile", 411, 799),
        ):
          page = browser.new_page(viewport={"width": width, "height": height})
          page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
          page.locator("#tab-tasks").click()
          toolbar = page.locator(".tasks-toolbar")
          rect = toolbar.bounding_box()
          assert rect is not None
          controls = page.evaluate("""() => {
            const box = selector => {
              const rect = document.querySelector(selector).getBoundingClientRect();
              return {left: rect.left, right: rect.right,
                middle: rect.top + rect.height / 2, width: rect.width};
            };
            return {status: box('#tasks-status'), search: box('#task-search'),
              filter: box('.task-filter'), toolbar: box('.tasks-toolbar')};
          }""")
          status, search, filter_box = (
            controls["status"],
            controls["search"],
            controls["filter"],
          )
          assert abs(status["middle"] - search["middle"]) < 1, controls
          assert abs(search["middle"] - filter_box["middle"]) < 1, controls
          assert status["right"] < search["left"], controls
          assert search["right"] < filter_box["left"], controls
          assert search["width"] >= 80, controls
          assert filter_box["right"] <= controls["toolbar"]["right"] + 1, controls
          page.locator("#task-search").focus()
          page.keyboard.press("Tab")
          assert page.evaluate("document.activeElement.id") == "task-type-filter"
          screenshot = page.screenshot(path=str(tmp_path / f"tasks-divider-{name}.png"))
          color = page.evaluate(
            """async ({png, x, y}) => {
              const image = new Image();
              image.src = `data:image/png;base64,${png}`;
              await image.decode();
              const canvas = document.createElement('canvas');
              canvas.width = image.width;
              canvas.height = image.height;
              const ctx = canvas.getContext('2d');
              ctx.drawImage(image, 0, 0);
              return Array.from(ctx.getImageData(x, y, 1, 1).data).slice(0, 3);
            }""",
            {
              "png": base64.b64encode(screenshot).decode("ascii"),
              "x": round(rect["x"] + rect["width"] / 2),
              "y": round(rect["y"] + rect["height"]) - 1,
            },
          )
          colors = toolbar.evaluate(
            """e => {
              const style = getComputedStyle(e);
              const rgb = value => value.match(/\\d+/g).slice(0, 3).map(Number);
              return {border: rgb(style.borderBottomColor), background: rgb(style.backgroundColor)};
            }"""
          )
          expected_contrast = sum(
            abs(border - background)
            for border, background in zip(colors["border"], colors["background"])
          )
          visible_contrast = sum(
            abs(actual - background)
            for actual, background in zip(color, colors["background"])
          )
          assert expected_contrast > 0
          assert visible_contrast >= expected_contrast / 2
          edge = page.evaluate("""() => {
            const pane = document.querySelector('#view-tasks');
            const toolbar = document.querySelector('.tasks-toolbar');
            const fade = getComputedStyle(toolbar, '::after');
            return {
              remaining: pane.scrollHeight - pane.clientHeight,
              opacity: Number(fade.opacity),
              fadeHeight: parseFloat(fade.height),
              fadeBottom: parseFloat(fade.bottom),
              paneTop: pane.getBoundingClientRect().top,
              toolbarTop: toolbar.getBoundingClientRect().top,
              bottomFade: getComputedStyle(document.querySelector('.tasks-layout'), '::after').content,
            };
          }""")
          assert edge["remaining"] >= 36, edge
          assert edge["opacity"] < 0.01, edge
          assert edge["fadeBottom"] == -edge["fadeHeight"], edge
          assert abs(edge["toolbarTop"] - edge["paneTop"]) < 1, edge
          assert edge["bottomFade"] != "none", edge
          page.locator("#view-tasks").evaluate("element => element.scrollTop = 260")
          page.wait_for_function("""() => {
            const pane = document.querySelector('#view-tasks');
            const toolbar = document.querySelector('.tasks-toolbar');
            const fade = getComputedStyle(toolbar, '::after');
            return pane.scrollTop >= 36 && Number(fade.opacity) > 0.99;
          }""")
          page.screenshot(path=str(tmp_path / f"tasks-fade-scrolled-{name}.png"))
          page.emulate_media(reduced_motion="reduce")
          assert (
            page.evaluate("""() =>
            getComputedStyle(document.querySelector('.tasks-toolbar'), '::after').content
          """)
            == "none"
          )
          assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
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
@pytest.mark.parametrize("width", [390, 1200])
def test_displayed_ids_choose_typed_composer_parents(
  width: int, tmp_path: Path
) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore(tmp_path / "state.sqlite3")
  app = SteeringApp(store, repo_name="Typed composer parents")
  app.messages.send_message(
    "Parent note. Plain task-parent stays text.", msg_id="aa1001", blocking=False
  )
  app.tasks.create_task("task-parent", "Task title", size=3, details=["Review"])
  app.reports.publish_report(
    "report-parent", "Report title", "# Report title\n\n`task-parent` stays code."
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
        page.locator("#tab-tasks").click()
        task_row = page.locator('.task[data-task-id="task-parent"]')
        assert "task-parent" not in task_row.inner_text()
        task_title = task_row.locator('button.task-title[data-parent-type="task"]')
        task_title.hover()
        assert page.get_by_role("tooltip").filter(has_text="task-parent").is_visible()
        page.evaluate("""() => {
          for (const [id, top] of [['tip-top', 2], ['tip-middle', 300], ['tip-bottom', 790]]) {
            const button = document.createElement('button');
            button.id = id; button.title = 'Placement test';
            button.textContent = id;
            Object.assign(button.style, {position: 'fixed', top: `${top}px`, left: '200px', zIndex: 10000});
            document.body.append(button);
          }
        }""")
        for button_id, above in [
          ("tip-top", False),
          ("tip-middle", True),
          ("tip-bottom", True),
        ]:
          button = page.locator(f"#{button_id}")
          button.hover()
          tooltip = page.locator("#arena-title-tooltip")
          assert tooltip.is_visible()
          button_box, tip_box = button.bounding_box(), tooltip.bounding_box()
          assert button_box and tip_box
          if above:
            assert tip_box["y"] + tip_box["height"] <= button_box["y"]
          else:
            assert tip_box["y"] >= button_box["y"] + button_box["height"]
        page.evaluate(
          "document.querySelectorAll('[id^=tip-]').forEach(el => el.remove())"
        )
        assert "task-parent" in (task_title.get_attribute("aria-label") or "")
        page.screenshot(path=str(tmp_path / f"task-id-hover-{width}.png"))
        task_title.click()
        page.locator('#tab-messages[aria-selected="true"]').wait_for()
        assert page.locator("#msg").evaluate("el => document.activeElement === el")
        page.locator("#tab-reports").click()
        report_button = page.locator(
          'button[data-parent-type="report"][data-parent-id="report-parent"]'
        )
        assert report_button.get_attribute("title") is None
        assert page.locator("#copy-report-btn").get_attribute("title") is None
        assert page.locator("#dismiss-report-btn").get_attribute("title") is None
        report_button.click(modifiers=["Shift"])
        assert page.locator('#tab-reports[aria-selected="true"]').count() == 1
        assert page.locator(
          "#composer-reply-bar .composer-reply-chip"
        ).all_text_contents() == ["task-parent"]
        report_button.click()
        page.locator('#tab-messages[aria-selected="true"]').wait_for()
        assert page.locator("#msg").evaluate("el => document.activeElement === el")
        page.locator("#tab-reports").click()
        assert (
          page.locator('article#report button[data-reference-id="task-parent"]').count()
          == 0
        )
        page.locator("#tab-messages").click()
        receipt_button = page.locator(
          'button[data-parent-type="message"][data-parent-id="aa1001"]'
        ).first
        receipt_button.click(modifiers=["Shift"])
        assert page.locator(
          "#composer-reply-bar .composer-reply-chip"
        ).all_text_contents() == [
          "task-parent",
          "report-parent",
        ]
        receipt_button.click()
        chips = page.locator("#composer-reply-bar .composer-reply-chip")
        assert chips.all_text_contents() == [
          "task-parent",
          "report-parent",
          "aa1001",
        ]
        message_text = page.locator('.message[data-msg-id="aa1001"] .message-text')
        assert message_text.get_by_text("task-parent", exact=False).count() == 1
        assert message_text.locator("button").count() == 0
        page.screenshot(path=str(tmp_path / f"typed-composer-parents-{width}.png"))
        page.locator("#msg").fill("Child from browser")
        page.locator("#send").click()
        page.locator(".message").filter(has_text="Child from browser").wait_for()
        child = next(
          msg
          for msg in app.messages.list_messages(unread_only=False, include_hidden=True)
          if msg.body == "Child from browser"
        )
        assert child.parent_refs == [
          {"type": "task", "id": "task-parent"},
          {"type": "report", "id": "report-parent"},
          {"type": "message", "id": "aa1001"},
        ]
        assert child.parent_ids == ["aa1001"]
        child_row = page.locator(f'.message[data-msg-id="{child.id}"]')
        child_row.wait_for()
        assert child_row.locator(
          ".message-parents .reply-parent-chip"
        ).all_text_contents() == [
          "task-parent",
          "report-parent",
          "aa1001",
        ]
        nav = child_row.locator(
          'button.reply-parent-chip[data-reference-type="task"][data-reference-id="task-parent"]'
        )
        assert nav.get_attribute("aria-label") == "Open task task-parent"
        nav.focus()
        page.keyboard.press("Enter")
        page.locator('#tab-tasks[aria-selected="true"]').wait_for()
        highlighted_task = page.locator(
          '.task[data-task-id="task-parent"][data-highlight="true"]'
        )
        highlighted_task.wait_for()
        highlighted_color = highlighted_task.evaluate(
          "el => getComputedStyle(el).backgroundColor"
        )
        page.screenshot(path=str(tmp_path / f"task-highlight-{width}.png"))
        highlighted_task.wait_for(state="detached")
        normal_color = task_row.evaluate("el => getComputedStyle(el).backgroundColor")
        assert highlighted_color != normal_color
        page.locator("#tab-messages").click()
        child_row.locator(
          'button.reply-parent-chip[data-reference-type="report"][data-reference-id="report-parent"]'
        ).click()
        page.locator('#tab-reports[aria-selected="true"]').wait_for()
        assert (
          page.locator(
            'button[data-parent-type="report"][data-parent-id="report-parent"]'
          ).count()
          == 1
        )
        page.locator("#tab-messages").click()
        child_row.locator(
          'button.reply-parent-chip[data-reference-type="message"][data-reference-id="aa1001"]'
        ).click()
        page.locator('.message[data-msg-id="aa1001"][data-highlight="true"]').wait_for()
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
@pytest.mark.parametrize("width,height", [(390, 844), (1200, 700)])
def test_messages_stay_at_bottom_after_send_and_reply_only_when_already_there(
  width: int, height: int, tmp_path: Path
) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore()
  app = SteeringApp(store, repo_name="Messages bottom pinning")
  for idx in range(12):
    app.messages.send_message(
      f"Older message {idx}. " + "Long scrolling content. " * 40,
      msg_id=f"{idx + 1:06x}",
      blocking=False,
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
        page.set_default_timeout(6000)
        page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
        history = page.locator("#history")
        history.locator(".message").last.wait_for()
        assert history.evaluate("el => el.scrollHeight > el.clientHeight")
        page.locator("#msg").fill("Sent at bottom")
        history.evaluate("el => { el.scrollTop = el.scrollHeight; }")
        assert (
          history.evaluate("el => el.scrollHeight - el.scrollTop - el.clientHeight")
          <= 1
        )
        page.locator("#send").click()
        sent = history.locator(".message").filter(has_text="Sent at bottom")
        sent.wait_for()
        assert (
          history.evaluate("el => el.scrollHeight - el.scrollTop - el.clientHeight")
          <= 24
        )
        sent_id = sent.get_attribute("data-msg-id")
        assert sent_id
        app.messages.ack(sent_id, "Reply at bottom. " + "Long reply content. " * 40)
        sent.locator(".reply").get_by_text("Reply at bottom", exact=False).wait_for()
        assert (
          history.evaluate("el => el.scrollHeight - el.scrollTop - el.clientHeight")
          <= 24
        )
        page.screenshot(path=str(tmp_path / f"messages-pinned-{width}.png"))

        page.locator("#msg").fill("Sent while reading earlier messages")
        history.evaluate("el => { el.scrollTop = el.scrollHeight / 2; }")
        assert history.evaluate("el => el.scrollTop") > 100
        anchor = history.evaluate("""element => {
          const viewport = element.getBoundingClientRect();
          const card = [...element.querySelectorAll('.message')].reverse().find(item => {
            const rect = item.getBoundingClientRect();
            return rect.bottom > viewport.top + 40 && rect.top < viewport.bottom - 40;
          });
          return card && {
            id: card.dataset.msgId,
            offset: card.getBoundingClientRect().top - viewport.top,
          };
        }""")
        assert anchor
        page.locator("#send").click()
        history.locator(".message").filter(
          has_text="Sent while reading earlier messages"
        ).wait_for()
        after = history.evaluate(
          """(element, id) => {
          const card = [...element.querySelectorAll('.message')].find(item => item.dataset.msgId === id);
          return {
            distance: element.scrollHeight - element.scrollTop - element.clientHeight,
            offset: card?.getBoundingClientRect().top - element.getBoundingClientRect().top,
          };
        }""",
          anchor["id"],
        )
        assert abs(after["offset"] - anchor["offset"]) <= 30, (anchor, after)
        assert after["distance"] > 100, after
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
@pytest.mark.parametrize("width,height", [(390, 844), (1200, 700)])
def test_message_content_growth_preserves_bottom_pin(
  tmp_path: Path, width: int, height: int
) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore(tmp_path / "state.sqlite3")
  app = SteeringApp(store)
  for idx in range(12):
    app.messages.send_message(
      f"Message {idx}. " + "Long content. " * 30, blocking=False
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
        history = page.locator("#history")
        bubble = history.locator(".message-bubble").last
        bubble.wait_for()
        history.evaluate("el => { el.scrollTop = el.scrollHeight; }")
        at_bottom = (
          "() => { const el = document.querySelector('#history'); "
          "return el.scrollHeight - el.scrollTop - el.clientHeight <= 1; }"
        )
        page.wait_for_function(at_bottom)
        bubble.evaluate("el => { el.style.minHeight = `${el.offsetHeight + 500}px`; }")
        page.wait_for_function(at_bottom, timeout=3000)
        history.evaluate("el => { el.scrollTop = el.scrollHeight / 2; }")
        page.wait_for_function(
          "() => { const el = document.querySelector('#history'); "
          "return el.scrollHeight - el.scrollTop - el.clientHeight > 100; }"
        )
        page.locator("#log-newest").wait_for(state="visible")
        old_top = history.evaluate("el => el.scrollTop")
        bubble.evaluate("el => { el.style.minHeight = `${el.offsetHeight + 500}px`; }")
        page.evaluate(
          "() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))"
        )
        assert abs(history.evaluate("el => el.scrollTop") - old_top) <= 2
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
def test_messages_keep_scroll_target_during_unchanged_polling() -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore()
  app = SteeringApp(store, repo_name="Message scroll regression")
  for index in range(20):
    app.messages.send_message(
      f"Message {index}\n\n" + "Long scrolling content. " * 40,
      msg_id=f"{index:06x}",
      blocking=False,
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
        page = browser.new_page(viewport={"width": 1200, "height": 700})
        page.add_init_script("""(() => {
          window.messageResponses = 0;
          const originalFetch = window.fetch.bind(window);
          window.fetch = async (...args) => {
            const response = await originalFetch(...args);
            if (String(args[0]).includes('/messages?')) {
              const json = response.json.bind(response);
              response.json = async () => {
                const value = await json();
                requestAnimationFrame(() => { window.messageResponses += 1; });
                return value;
              };
            }
            return response;
          };
        })();""")
        page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
        page.wait_for_function(
          "window.messageResponses > 0 && document.querySelectorAll('#history .message').length > 1"
        )
        page.wait_for_load_state("networkidle")
        history = page.locator("#history")
        bounds = history.bounding_box()
        assert bounds
        page.evaluate("""() => {
          const history = document.querySelector('#history');
          history.scrollTop = history.scrollHeight / 2;
        }""")
        start = history.evaluate("element => element.scrollTop")
        assert start > 320
        page.mouse.move(
          bounds["x"] + bounds["width"] / 2, bounds["y"] + bounds["height"] / 2
        )
        page.mouse.wheel(0, -120)
        page.wait_for_function(
          "before => document.querySelector('#history').scrollTop < before", arg=start
        )
        page.evaluate(
          "window.scrollTargetBeforePoll = document.querySelector('#history')"
        )
        count = page.evaluate("window.messageResponses")
        page.wait_for_function(
          "count => window.messageResponses > count", arg=count, timeout=6000
        )
        assert page.evaluate(
          "window.scrollTargetBeforePoll === document.querySelector('#history')"
        )
        start = history.evaluate("element => element.scrollTop")
        page.mouse.wheel(0, -120)
        page.wait_for_function(
          "before => document.querySelector('#history').scrollTop < before", arg=start
        )

        app.messages.send_message(
          "A new message arrives.", msg_id="aa1234", blocking=False
        )
        new_message = page.locator('.message[data-msg-id="aa1234"]')
        new_message.wait_for(timeout=6000)
        app.messages.ack("aa1234", "A reply arrives.")
        new_message.locator(".reply").get_by_text("A reply arrives.").wait_for(
          timeout=6000
        )
        assert page.evaluate(
          "window.scrollTargetBeforePoll === document.querySelector('#history')"
        )
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
  ("wait_for_poll", "gesture"),
  [(False, "wheel"), (True, "wheel"), (False, "scrollbar"), (False, "touch")],
  ids=["quick-wheel", "slow-wheel", "scrollbar-drag", "touch-swipe"],
)
def test_messages_keep_scroll_target_while_older_page_loads(
  wait_for_poll: bool,
  gesture: str,
  tmp_path: Path,
) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore()
  app = SteeringApp(store, repo_name="Older message scroll regression")
  for index in range(45):
    app.messages.send_message(
      f"Message {index}\n\n" + "Long scrolling content. " * 40,
      msg_id=f"{index:06x}",
      blocking=False,
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
        ignore_default_args=["--hide-scrollbars"],
      )
      try:
        page = browser.new_page(
          viewport={"width": 411, "height": 800}
          if gesture == "touch"
          else {"width": 1200, "height": 700},
          is_mobile=gesture == "touch",
          has_touch=gesture == "touch",
        )
        page.set_default_timeout(6000)
        page.add_init_script("""(() => {
          const originalFetch = window.fetch.bind(window);
          window.refreshesWhileOlder = 0;
          window.fetch = async (...args) => {
            const response = await originalFetch(...args);
            const url = String(args[0]);
            if (url.includes('/messages?') && url.includes('before=') && !window.olderWasHeld) {
              window.olderWasHeld = true;
              window.olderPending = true;
              await new Promise(resolve => {
                window.releaseOlderPage = () => { window.olderPending = false; resolve(); };
              });
            } else if (url.includes('/health') && window.olderPending) {
              window.refreshesWhileOlder += 1;
            }
            return response;
          };
        })();""")
        page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
        page.wait_for_function(
          "document.querySelectorAll('#history .message').length === 20"
        )
        page.wait_for_load_state("networkidle")
        history = page.locator("#history")
        bounds = history.bounding_box()
        assert bounds
        page.evaluate("""() => {
          const history = document.querySelector('#history');
          history.scrollTop = 400;
          window.olderScrollTarget = history;
        }""")
        page.mouse.move(
          bounds["x"] + bounds["width"] / 2, bounds["y"] + bounds["height"] / 2
        )
        page.mouse.wheel(0, -150)
        page.wait_for_function("typeof window.releaseOlderPage === 'function'")
        if wait_for_poll:
          page.wait_for_function("window.refreshesWhileOlder > 0")
          app.messages.send_message(
            "Arrived during pagination.", msg_id="aa1234", blocking=False
          )
        before_wheel = history.evaluate("element => element.scrollTop")
        page.mouse.wheel(0, 60)
        page.wait_for_function(
          "before => document.querySelector('#history').scrollTop > before",
          arg=before_wheel,
        )
        cdp = None
        drag_x = drag_y = touch_x = touch_y = 0.0
        if gesture in {"scrollbar", "touch"}:
          history.evaluate("element => { element.scrollTop = 1200; }")
          page.wait_for_function("document.querySelector('#history').scrollTop > 1000")
          start_gesture = history.evaluate("element => element.scrollTop")
          if gesture == "scrollbar":
            metrics = history.evaluate("""element => {
              const rect = element.getBoundingClientRect();
              const track = rect.height - 16;
              const thumb = Math.max(18, track * element.clientHeight / element.scrollHeight);
              return {x: rect.right - 5, y: rect.top + 8 + thumb / 2 +
                (track - thumb) * element.scrollTop / (element.scrollHeight - element.clientHeight)};
            }""")
            drag_x, drag_y = metrics["x"], metrics["y"]
            page.screenshot(path=str(tmp_path / "scrollbar-before.png"))
            page.mouse.move(drag_x, drag_y)
            page.mouse.down()
            page.mouse.move(drag_x, drag_y + 8, steps=4)
          else:
            cdp = page.context.new_cdp_session(page)
            touch_x = bounds["x"] + bounds["width"] / 2
            touch_y = max(150, min(bounds["y"] + bounds["height"] / 2, 650))
            cdp.send(
              "Input.dispatchTouchEvent",
              {"type": "touchStart", "touchPoints": [{"x": touch_x, "y": touch_y}]},
            )
            cdp.send(
              "Input.dispatchTouchEvent",
              {"type": "touchMove", "touchPoints": [{"x": touch_x, "y": touch_y - 60}]},
            )
          page.wait_for_function(
            "before => document.querySelector('#history').scrollTop > before",
            arg=start_gesture,
          )
          page.evaluate("""() => new Promise(resolve => {
            const history = document.querySelector('#history');
            let last = history.scrollTop;
            let stable = 0;
            let frames = 0;
            function tick() {
              stable = history.scrollTop === last ? stable + 1 : 0;
              last = history.scrollTop;
              if (stable >= 3 || ++frames >= 120) resolve(); else requestAnimationFrame(tick);
            }
            requestAnimationFrame(tick);
          })""")
        anchor = page.evaluate("""() => {
          const history = document.querySelector('#history');
          const rect = history.getBoundingClientRect();
          const card = Array.from(history.querySelectorAll('.message')).filter(item => {
            const box = item.getBoundingClientRect();
            return box.bottom > rect.top + 40 && box.top < rect.bottom - 40;
          }).at(-1);
          window.olderAnchorCard = card;
          return {id: card.dataset.msgId, top: card.getBoundingClientRect().top - rect.top};
        }""")
        page.evaluate("window.releaseOlderPage()")
        page.wait_for_function(
          "document.querySelectorAll('#history .message').length > 20"
        )
        assert page.evaluate(
          "window.olderScrollTarget === document.querySelector('#history')"
        )
        assert page.evaluate("window.olderAnchorCard.isConnected")
        after = page.evaluate(
          """id => {
          const history = document.querySelector('#history');
          const card = history.querySelector(`[data-msg-id="${id}"]`);
          return card.getBoundingClientRect().top - history.getBoundingClientRect().top;
        }""",
          anchor["id"],
        )
        assert abs(after - anchor["top"]) <= 2
        if wait_for_poll:
          page.locator('.message[data-msg-id="aa1234"]').wait_for(timeout=6000)
        if gesture in {"scrollbar", "touch"}:
          page.screenshot(path=str(tmp_path / f"scroll-{gesture}-after.png"))
        start = history.evaluate("element => element.scrollTop")
        if gesture == "scrollbar":
          page.mouse.move(drag_x, drag_y + 28, steps=4)
          page.wait_for_function(
            "before => document.querySelector('#history').scrollTop > before", arg=start
          )
          page.mouse.up()
        elif gesture == "touch":
          assert cdp is not None
          cdp.send(
            "Input.dispatchTouchEvent",
            {"type": "touchMove", "touchPoints": [{"x": touch_x, "y": touch_y - 130}]},
          )
          page.wait_for_function(
            "before => document.querySelector('#history').scrollTop > before", arg=start
          )
          cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
        else:
          page.mouse.wheel(0, -120)
          page.wait_for_function(
            "before => document.querySelector('#history').scrollTop < before", arg=start
          )
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
def test_message_search_can_page_while_an_old_query_is_loading() -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore()
  app = SteeringApp(store, repo_name="Message search paging regression")
  for index in range(45):
    app.messages.send_message(
      f"Searchable message {index}\n\n" + "Long scrolling content. " * 40,
      msg_id=f"{index:06x}",
      blocking=False,
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
        page = browser.new_page(viewport={"width": 1200, "height": 700})
        page.set_default_timeout(6000)
        page.add_init_script("""(() => {
          const originalFetch = window.fetch.bind(window);
          window.searchPagingRequests = [];
          window.fetch = async (...args) => {
            const url = String(args[0]);
            if (url.includes('/messages?') && url.includes('q=Searchable')) {
              window.searchPagingRequests.push(url);
            }
            const response = await originalFetch(...args);
            if (url.includes('/messages?') && url.includes('before=') && !window.heldOldPage) {
              window.heldOldPage = true;
              await new Promise(resolve => { window.releaseOldPage = resolve; });
              const json = response.json.bind(response);
              response.json = async () => {
                const result = await json();
                requestAnimationFrame(() => { window.oldPageConsumed = true; });
                return result;
              };
            }
            return response;
          };
        })();""")
        page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
        page.wait_for_function(
          "document.querySelectorAll('#history .message').length === 20"
        )
        page.wait_for_load_state("networkidle")
        page.locator("#history").evaluate("element => { element.scrollTop = 300; }")
        page.wait_for_function("typeof window.releaseOldPage === 'function'")
        page.locator("#log-search").fill("Searchable")
        page.wait_for_function(
          "document.querySelectorAll('#history .message').length === 20"
        )
        page.locator("#history").evaluate("element => { element.scrollTop = 300; }")
        page.wait_for_function(
          "document.querySelectorAll('#history .message').length > 20"
        )
        page.evaluate("window.releaseOldPage()")
        page.wait_for_function("window.oldPageConsumed")
        assert page.locator("#log-search").input_value() == "Searchable"
        assert page.locator("#history .message").count() == 40
        requests = page.evaluate("window.searchPagingRequests")
        assert requests and "before=" not in requests[0], requests
        ids = page.locator("#history .message").evaluate_all(
          "elements => elements.map(element => element.dataset.msgId)"
        )
        assert ids == [f"{index:06x}" for index in range(5, 45)]
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
def test_retained_id_like_markdown_stays_plain_as_history_pages_change() -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore()
  app = SteeringApp(store, repo_name="Message reference paging regression")
  app.tasks.create_task("00000a", "Referenced task", size=3, details=["Review"])
  for index in range(45):
    body = f"Message {index}\n\n" + "Long scrolling content. " * 40
    if index == 44:
      body += "\n\nReferences `00000a` and `00000b`; plain 00000a stays plain."
    app.messages.send_message(body, msg_id=f"{index:06x}", blocking=False)
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
        page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
        page.wait_for_function(
          "document.querySelectorAll('#history .message').length === 20"
        )
        card = page.locator('.message[data-msg-id="00002c"]')
        card.locator("code").filter(has_text=re.compile(r"^00000a$")).wait_for()
        assert card.locator(".message-text button").count() == 0
        assert card.locator(".message-text code").count() == 2
        page.evaluate(
          "window.retainedReferenceCard = document.querySelector('.message[data-msg-id=\"00002c\"]')"
        )
        page.locator("#history").evaluate("element => { element.scrollTop = 300; }")
        page.wait_for_function(
          "document.querySelectorAll('#history .message').length === 40"
        )
        assert page.evaluate("window.retainedReferenceCard.isConnected")
        assert card.locator(".message-text button").count() == 0
        assert card.locator(".message-text code").count() == 2
        app.tasks.remove_task("00000a")
        page.wait_for_timeout(200)
        assert card.locator(".message-text button").count() == 0
        assert "00000a" in card.inner_text()
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
def test_message_page_error_keeps_scroll_target_and_can_retry() -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore()
  app = SteeringApp(store, repo_name="Message page retry regression")
  for index in range(25):
    app.messages.send_message(
      f"Message {index}\n\n" + "Long scrolling content. " * 40,
      msg_id=f"{index:06x}",
      blocking=False,
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
        page = browser.new_page(viewport={"width": 1200, "height": 700})
        page.add_init_script("""(() => {
          const originalFetch = window.fetch.bind(window);
          window.fetch = async (...args) => {
            const url = String(args[0]);
            if (url.includes('/messages?') && url.includes('before=') && !window.failedOlderOnce) {
              window.failedOlderOnce = true;
              return new Response(JSON.stringify({error: 'try again'}), {
                status: 503, headers: {'content-type': 'application/json'}
              });
            }
            return originalFetch(...args);
          };
        })();""")
        page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
        page.wait_for_function(
          "document.querySelectorAll('#history .message').length === 20"
        )
        page.evaluate("""() => {
          window.retryScrollTarget = document.querySelector('#history');
          window.retryScrollTarget.scrollTop = 300;
        }""")
        error = page.locator('#history [role="alert"]')
        error.wait_for(timeout=6000)
        assert page.evaluate(
          "window.retryScrollTarget === document.querySelector('#history')"
        )
        page.evaluate("document.querySelector('#load-older-messages').click()")
        page.wait_for_function(
          "document.querySelectorAll('#history .message').length === 25"
        )
        assert page.locator('#history [role="alert"]').is_hidden()
        assert page.evaluate(
          "window.retryScrollTarget === document.querySelector('#history')"
        )
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
def test_reports_tab_shows_independent_attention_indicators(tmp_path: Path) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore()
  app = SteeringApp(store, repo_name="Report indicators")
  app.reports.publish_report(
    "decision",
    "Decision",
    '# Decision\n\n<!-- question {"id":"choice","label":"Choice"} -->\nChoice: ___\n',
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
        page = browser.new_page(viewport={"width": 1200, "height": 700})
        page.set_default_timeout(5000)
        page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
        pip = page.locator("#report-pip")
        question = page.locator("#report-needs-answer")
        pip.wait_for(state="visible")
        question.wait_for(state="visible")
        assert pip.get_attribute("aria-label") == "Unread report"
        assert question.get_attribute("aria-label") == "Reports need answers"
        assert "is-unseen-ack" not in (pip.get_attribute("class") or "")
        for width, height in (
          (1372, 883),
          (855, 325),
          (411, 799),
          (375, 700),
        ):
          page.set_viewport_size({"width": width, "height": height})
          tab_widths = page.locator(".tab-nav .tab-btn").evaluate_all(
            "tabs => tabs.map(tab => tab.getBoundingClientRect().width)"
          )
          assert max(tab_widths) - min(tab_widths) < 1, (width, tab_widths)
          geometry = page.locator("#tab-reports").evaluate("""tab => {
            const label = document.createRange();
            label.selectNodeContents(tab.firstChild);
            const text = label.getBoundingClientRect();
            const bounds = tab.getBoundingClientRect();
            const pip = tab.querySelector('#report-pip').getBoundingClientRect();
            const question = tab.querySelector('#report-needs-answer').getBoundingClientRect();
            const dotSample = document.createElement('span');
            dotSample.className = 'report-picker-unseen-dot';
            const iconSample = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
            iconSample.classList.add('report-picker-help-icon');
            document.body.append(dotSample, iconSample);
            const pickerDot = dotSample.getBoundingClientRect();
            const pickerIcon = iconSample.getBoundingClientRect();
            dotSample.remove();
            iconSample.remove();
            return {
              pickerDotWidth: pickerDot.width,
              pickerDotHeight: pickerDot.height,
              pickerIconWidth: pickerIcon.width,
              pickerIconHeight: pickerIcon.height,
              textCenter: (text.left + text.right) / 2,
              tabCenter: (bounds.left + bounds.right) / 2,
              textRight: text.right,
              textTop: text.top,
              navRight: document.querySelector('.tab-nav').getBoundingClientRect().right,
              actionsLeft: document.querySelector('.topbar-actions').getBoundingClientRect().left,
              overflow: document.documentElement.scrollWidth > innerWidth,
              pipLeft: pip.left,
              pipTop: pip.top,
              pipWidth: pip.width,
              pipHeight: pip.height,
              questionLeft: question.left,
              questionRight: question.right,
              questionTop: question.top,
              questionBottom: question.bottom,
              questionWidth: question.width,
              questionHeight: question.height,
              tabTop: bounds.top,
              tabBottom: bounds.bottom,
              pipBottom: pip.bottom,
              pipOffsetRight: bounds.right - pip.right,
            };
          }""")
          assert abs(geometry["textCenter"] - geometry["tabCenter"]) < 1
          assert geometry["pipWidth"] == geometry["pickerDotWidth"]
          assert geometry["pipHeight"] == geometry["pickerDotHeight"]
          assert geometry["questionWidth"] == geometry["pickerIconWidth"]
          assert geometry["questionHeight"] == geometry["pickerIconHeight"]
          assert (
            abs(
              geometry["questionTop"]
              + geometry["questionHeight"] / 2
              - geometry["pipTop"]
              - geometry["pipHeight"] / 2
            )
            < 1
          )
          assert geometry["questionRight"] < geometry["pipLeft"]
          assert geometry["tabTop"] <= geometry["questionTop"]
          assert geometry["questionBottom"] <= geometry["tabBottom"]
          assert geometry["tabTop"] <= geometry["pipTop"]
          assert geometry["pipBottom"] <= geometry["tabBottom"]
          assert geometry["pipOffsetRight"] == 6
          assert geometry["navRight"] + 8 <= geometry["actionsLeft"]
          assert not geometry["overflow"]
        page.locator("#tab-tasks").focus()
        page.keyboard.press("Tab")
        assert page.evaluate("document.activeElement.id") == "blocked-bash-open"
        page.locator("#tab-tasks").click()
        assert page.locator('#tab-tasks[aria-selected="true"]').count() == 1
        page.locator("#tab-messages").click()
        page.set_viewport_size({"width": 1200, "height": 700})
        page.screenshot(path=str(tmp_path / "report-both-indicators.png"))

        with page.expect_response("**/reports/decision/seen"):
          page.locator("#tab-reports").click()
        pip.wait_for(state="hidden")
        assert question.is_visible()
        for width in (1200, 375):
          page.set_viewport_size({"width": width, "height": 700})
          alone = page.locator("#tab-reports").evaluate("""tab => {
            const label = document.createRange();
            label.selectNodeContents(tab.firstChild);
            const text = label.getBoundingClientRect();
            const bounds = tab.getBoundingClientRect();
            const question = tab.querySelector('#report-needs-answer').getBoundingClientRect();
            return {
              textCenter: (text.left + text.right) / 2,
              tabCenter: (bounds.left + bounds.right) / 2,
              textRight: text.right,
              questionLeft: question.left,
              questionOffsetRight: bounds.right - question.right,
              questionTop: question.top - bounds.top,
              questionWidth: question.width,
              questionHeight: question.height,
            };
          }""")
          assert abs(alone["textCenter"] - alone["tabCenter"]) < 1
          assert alone["questionOffsetRight"] == 6
          assert alone["questionTop"] >= 0
          assert alone["questionWidth"] == alone["questionHeight"] == 14

        page.locator("#tab-messages").click()
        answer = app.reports.submit_answer("decision", {"choice": "Yes"})
        app.reports.ack_answer("decision", answer.id, "Received")
        page.reload()
        pip.wait_for(state="visible")
        question.wait_for(state="hidden")
        assert pip.get_attribute("aria-label") == "Unseen answer acknowledgement"
        assert "is-unseen-ack" in (pip.get_attribute("class") or "")
        green = pip.evaluate("element => getComputedStyle(element).backgroundColor")

        app.reports.publish_report(
          "pending",
          "Pending",
          '<!-- question {"id":"note","label":"Note"} -->\nNote: ___\n',
        )
        app.reports.mark_seen("pending")
        page.reload()
        pip.wait_for(state="visible")
        assert "is-unseen-ack" in (pip.get_attribute("class") or "")
        assert question.is_visible()

        app.reports.publish_report("other", "Other", "# Other")
        page.reload()
        pip.wait_for(state="visible")
        assert pip.get_attribute("aria-label") == "Unread report"
        assert "is-unseen-ack" not in (pip.get_attribute("class") or "")
        assert question.is_visible()
        assert (
          pip.evaluate("element => getComputedStyle(element).backgroundColor") != green
        )

        app.reports.mark_seen("other")
        page.reload()
        pip.wait_for(state="visible")
        assert "is-unseen-ack" in (pip.get_attribute("class") or "")
        app.reports.mark_ack_seen("decision")
        page.reload()
        question.wait_for(state="visible")
        assert pip.is_hidden()
        app.reports.submit_answer("pending", {"note": "Noted"})
        page.reload()
        question.wait_for(state="hidden")
        assert pip.is_hidden()
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


def test_external_sqlite_write_changes_websocket_data_version(tmp_path: Path) -> None:
  path = tmp_path / "state.sqlite3"
  server_store = SqliteStore(path)
  writer_store = SqliteStore(path)
  app = SteeringApp(server_store)
  try:
    before = app.data_version()
    assert app.data_version() == before
    writer_store.set_meta("test_external_write", "changed")
    after_external = app.data_version()
    assert after_external != before
    assert app.data_version() == after_external
    server_store.set_meta("test_local_write", "changed")
    after_local = app.data_version()
    assert after_local != after_external
    assert app.data_version() == after_local
  finally:
    writer_store.close()
    server_store.close()


@pytest.mark.skipif(
  not os.environ.get("ARENA_STEERING_CHROMIUM"),
  reason="Set ARENA_STEERING_CHROMIUM to run the browser regression",
)
def test_websocket_refreshes_after_external_store_write(tmp_path: Path) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  path = tmp_path / "state.sqlite3"
  server_store = SqliteStore(path)
  writer_store = SqliteStore(path)
  app = SteeringApp(server_store, repo_name="External change")
  writer = SteeringApp(writer_store)
  server_store.set_meta("timezone", "UTC")
  app.messages.send_message("Baseline", msg_id="ac0001")
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
        page = browser.new_page(timezone_id="UTC")
        sockets = []
        frames = []

        def record_socket(socket) -> None:
          sockets.append(socket)
          socket.on("framereceived", lambda frame: frames.append(frame))

        page.on("websocket", record_socket)
        page.goto(f"http://127.0.0.1:{server.server_port}/")
        page.locator('[data-msg-id="ac0001"]').first.wait_for(state="visible")
        assert sockets and '{"type":"change"}' in frames
        with sockets[0].expect_event(
          "framereceived",
          predicate=lambda frame: frame == '{"type":"change"}',
          timeout=6000,
        ):
          writer.messages.send_message("Added outside the server", msg_id="ac0002")
        page.locator('[data-msg-id="ac0002"]').first.wait_for(
          state="visible", timeout=6000
        )
      finally:
        browser.close()
  finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)
    writer_store.close()
    server_store.close()


@pytest.mark.skipif(
  not os.environ.get("ARENA_STEERING_CHROMIUM"),
  reason="Set ARENA_STEERING_CHROMIUM to run the browser regression",
)
def test_browser_repairs_preexisting_timezone_handoff(tmp_path: Path) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  path = tmp_path / "state.sqlite3"
  store = SqliteStore(path)
  store.set_meta("timezone", "Asia/Manila")
  app = SteeringApp(store, repo_name="Timezone")
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
        page = browser.new_page(timezone_id="Asia/Manila")
        with page.expect_response("**/timezone", timeout=6000) as response:
          page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
        assert response.value.status == 200
        assert (path.parent / "display_tz").read_text(
          encoding="utf-8"
        ) == "Asia/Manila\n"
        page.screenshot(path=str(tmp_path / "timezone-preview.png"))
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
def test_state_refresh_preserves_unaffected_view_controls(tmp_path: Path) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore()
  app = SteeringApp(store, repo_name="State refresh DOM preservation")
  app.tasks.create_task("initial-work", "Work already here", size=3, details=["Review"])
  app.reports.publish_report(
    "draft",
    "Draft answer",
    '# Draft\n\n<!-- question {"id":"note","label":"Note"} -->\nNote\n',
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
        page = browser.new_page(viewport={"width": 1200, "height": 700})
        page.clock.install()
        page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
        observations = {}

        message_draft = page.locator("#msg")
        message_draft.fill("Unsent message draft")
        message_draft.focus()
        original_message = message_draft.element_handle()
        original_composer = page.locator("#compose").element_handle()
        app.messages.send_message(
          "An external message", msg_id="e00001", blocking=False
        )
        page.clock.fast_forward(3100)
        page.locator('.message[data-msg-id="e00001"]').wait_for()
        observations["messages"] = {
          "composer": original_composer.evaluate("el => el.isConnected"),
          "draft": original_message.evaluate("el => el.isConnected"),
          "value": message_draft.input_value(),
          "focused": message_draft.evaluate("el => el === document.activeElement"),
        }
        page.screenshot(path=str(tmp_path / "messages-state-refresh.png"))
        page.locator("#send").click()
        page.locator(".message").filter(has_text="Unsent message draft").wait_for()
        page.wait_for_function("document.querySelector('#msg')?.value === ''")
        assert message_draft.evaluate("el => el === document.activeElement")

        page.locator("#tab-tasks").click()
        task_search = page.locator("#task-search")
        task_search.fill("Work")
        task_search.focus()
        original_search = task_search.element_handle()
        app.tasks.create_task(
          "external-work", "Work from elsewhere", size=3, details=["Review"]
        )
        page.clock.fast_forward(3100)
        page.locator('li.task[data-task-id="external-work"]').wait_for()
        observations["tasks"] = {
          "search": original_search.evaluate("el => el.isConnected"),
          "value": task_search.input_value(),
          "focused": task_search.evaluate("el => el === document.activeElement"),
        }
        page.screenshot(path=str(tmp_path / "tasks-state-refresh.png"))

        page.locator("#tab-reports").click()
        answer = page.locator(".field-text-input")
        answer.fill("Unsaved report answer")
        answer.focus()
        original_answer = answer.element_handle()
        app.reports.publish_report("other", "Other report", "# Other report")
        page.clock.fast_forward(3100)
        page.locator('[data-report-id="other"]').wait_for()
        observations["reports"] = {
          "answer": original_answer.evaluate("el => el.isConnected"),
          "value": answer.input_value(),
          "focused": answer.evaluate("el => el === document.activeElement"),
        }
        page.screenshot(path=str(tmp_path / "reports-state-refresh.png"))

        assert observations == {
          "messages": {
            "composer": True,
            "draft": True,
            "value": "Unsent message draft",
            "focused": True,
          },
          "tasks": {"search": True, "value": "Work", "focused": True},
          "reports": {
            "answer": True,
            "value": "Unsaved report answer",
            "focused": True,
          },
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
@pytest.mark.parametrize("width,height", [(1372, 883), (855, 325), (411, 799)])
def test_markdown_tables_match_github_across_views(
  width: int, height: int, tmp_path: Path
) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  markdown = (
    "| Label | Value |\n| :--- | ---: |\n| First | short |\n| Second | "
    + "a" * 200
    + " |\n"
  )
  store = SqliteStore()
  app = SteeringApp(store, repo_name="Markdown table styling")
  app.messages.send_message(markdown, blocking=False)
  app.reports.publish_report(
    "table-report",
    "Table report",
    "# Table report\n\n"
    + "A report paragraph uses the available width. " * 24
    + "\n\n"
    + markdown,
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
        for tab, selector in (
          ("messages", ".message-text table"),
          ("reports", ".report table"),
        ):
          if tab == "reports":
            page.locator("#tab-reports").click()
            paragraph = page.locator(".report .prose-block > p").first
            paragraph.wait_for()
            prose = paragraph.evaluate("""element => ({
              width: element.getBoundingClientRect().width,
              available: element.parentElement.getBoundingClientRect().width,
            })""")
            assert prose["width"] >= prose["available"] - 1, (width, prose)
          table = page.locator(selector).first
          table.wait_for()
          metrics = table.evaluate("""table => {
            const cell = table.querySelector('tbody td');
            const rows = table.querySelectorAll('tbody tr');
            const style = getComputedStyle(cell);
            const pane = table.closest('#history, #report-main');
            return {
              padding: [style.paddingTop, style.paddingLeft],
              borders: [style.borderTopWidth, style.borderRightWidth,
                style.borderBottomWidth, style.borderLeftWidth],
              whiteSpace: style.whiteSpace,
              striped: getComputedStyle(rows[0]).backgroundColor !==
                getComputedStyle(rows[1]).backgroundColor,
              headerWeight: Number(getComputedStyle(table.querySelector('th')).fontWeight),
              rightAligned: getComputedStyle(table.querySelector('th:last-child')).textAlign,
              overflow: getComputedStyle(table).overflowX,
              scrollable: table.scrollWidth > table.clientWidth + 1,
              contained: table.getBoundingClientRect().right <= pane.getBoundingClientRect().right + 1,
            };
          }""")
          assert metrics == {
            "padding": ["6px", "13px"],
            "borders": ["1px"] * 4,
            "whiteSpace": "normal",
            "striped": True,
            "headerWeight": 700,
            "rightAligned": "right",
            "overflow": "auto",
            "scrollable": True,
            "contained": True,
          }, (tab, width, metrics)
          page.screenshot(
            path=str(tmp_path / f"markdown-table-{tab}-{width}.png"),
            animations="disabled",
          )
          if tab == "reports":
            fade = table.evaluate("""element =>
              parseFloat(getComputedStyle(element).getPropertyValue('--edge-fade'))
            """)
            page.wait_for_function(
              """fade =>
              parseFloat(getComputedStyle(document.querySelector('#report table'))
                .getPropertyValue('--edge-end')) >= fade
            """,
              arg=fade,
            )
            start = table.evaluate("""element => {
              const style = getComputedStyle(element);
              return {start: parseFloat(style.getPropertyValue('--edge-start')),
                end: parseFloat(style.getPropertyValue('--edge-end')),
                gradients: style.maskImage.split('linear-gradient(').length - 1};
            }""")
            assert start == {"start": 0, "end": fade, "gradients": 2}, start
          assert (
            table.evaluate(
              "el => { el.scrollLeft = el.scrollWidth; return el.scrollLeft; }"
            )
            > 0
          )
          if tab == "reports":
            page.wait_for_function(
              """fade => {
              const table = document.querySelector('#report table');
              const style = getComputedStyle(table);
              return parseFloat(style.getPropertyValue('--edge-start')) >= fade &&
                parseFloat(style.getPropertyValue('--edge-end')) === 0;
            }""",
              arg=fade,
            )
            end = table.evaluate("""element => {
              const style = getComputedStyle(element);
              return {start: parseFloat(style.getPropertyValue('--edge-start')),
                end: parseFloat(style.getPropertyValue('--edge-end')),
                remaining: element.scrollWidth - element.clientWidth - element.scrollLeft,
                overflow: style.overflowX};
            }""")
            expected = {"start": fade, "end": 0, "remaining": 0, "overflow": "auto"}
            assert end == expected, end
            page.screenshot(path=str(tmp_path / f"markdown-table-end-{width}.png"))
            page.emulate_media(reduced_motion="reduce")
            assert table.evaluate("el => getComputedStyle(el).maskImage") == "none"
            assert table.evaluate("el => el.scrollLeft") > 0
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
@pytest.mark.parametrize("transport", ["ws", "poll"])
def test_seen_reply_receipt_keeps_message_height(
  tmp_path: Path, width: int, transport: str
) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore(tmp_path / "state.sqlite3")
  app = SteeringApp(store)
  msg_id = "aa1234"
  app.messages.send_message("Review the reply layout", msg_id=msg_id)
  receipt_requested = threading.Event()
  release_receipt = threading.Event()
  mark_seen = app.messages.mark_replies_seen

  def delayed_receipt(id_: str, revision: str) -> bool:
    receipt_requested.set()
    if not release_receipt.wait(10):
      raise RuntimeError("Seen receipt was not released")
    return mark_seen(id_, revision)

  app.messages.mark_replies_seen = delayed_receipt
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
        page = browser.new_page(
          viewport={"width": width, "height": 844},
          is_mobile=width == 390,
          has_touch=width == 390,
        )
        sockets: list[str] = []
        page.on("websocket", lambda socket: sockets.append(socket.url))
        url = f"http://127.0.0.1:{server.server_port}/"
        if transport == "poll":
          url += "?transport=poll"
        page.goto(url)
        card = page.locator(f'.message[data-msg-id="{msg_id}"]')
        card.wait_for()
        before = card.bounding_box()
        assert before is not None
        bottom = card.locator(".receipt-bottom")
        assert bottom.locator("*").count() == 0
        assert bottom.inner_text().startswith("Sent ")
        page.screenshot(path=str(tmp_path / f"receipt-bottom-{width}-{transport}.png"))
        assert (
          app.dispatch(
            "POST", f"/messages/{msg_id}/ack", {"markdown": "Acknowledged."}
          )[0]
          == HTTPStatus.OK
        )
        assert receipt_requested.wait(8), (
          "Reply intersection did not request a seen receipt"
        )
        sentinel = card.locator(".reply-seen-sentinel")
        sentinel.wait_for()
        pending = card.bounding_box()
        receipt_pending = card.locator(".receipt").bounding_box()
        assert pending is not None and receipt_pending is not None
        assert card.locator(".state-dot").count() == 0
        assert (
          card.locator(".receipt-status")
          .get_attribute("aria-label")
          .startswith("Status: acked, ")
        )
        assert (
          not card.locator(".receipt-status")
          .inner_text()
          .startswith(("Sent ", "Seen "))
        )
        release_receipt.set()
        sentinel.wait_for(state="detached")
        seen = card.bounding_box()
        receipt_seen = card.locator(".receipt").bounding_box()
        assert seen is not None and receipt_seen is not None
        assert app.messages.get_message(msg_id).replies_seen
        assert seen["height"] > before["height"]
        assert abs(pending["height"] - seen["height"]) < 0.5
        assert abs(receipt_pending["y"] - receipt_seen["y"]) < 0.5
        assert card.locator(".state-dot").count() == 0
        assert (
          card.locator(".receipt-status")
          .get_attribute("aria-label")
          .startswith("Status: acked, ")
        )
        card.locator(".receipt-status").hover()
        assert card.locator(".receipt-status").get_attribute("title") is None
        assert page.locator("#arena-title-tooltip").count() == 0
        page.screenshot(
          path=str(tmp_path / f"receipt-no-tooltip-{width}-{transport}.png")
        )
        assert bool(sockets) == (transport == "ws")
      finally:
        release_receipt.set()
        browser.close()
  finally:
    release_receipt.set()
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)
    store.close()


@pytest.mark.skipif(
  not os.environ.get("ARENA_STEERING_CHROMIUM"),
  reason="Set ARENA_STEERING_CHROMIUM to run the browser regression",
)
@pytest.mark.parametrize("width", [390, 1200])
def test_fallback_poll_refreshes_without_analytics_across_reload(
  tmp_path: Path, width: int
) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore(tmp_path / "state.sqlite3")
  app = SteeringApp(store)
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
        page.clock.install()
        analytics_requests = []
        page.on(
          "request",
          lambda request: (
            analytics_requests.append(request.url)
            if "/analytics/fallback" in request.url
            else None
          ),
        )
        page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
        page.locator("#compose").wait_for()
        app.messages.send_message("First fallback update", msg_id="ab7101")
        page.clock.fast_forward(3_100)
        page.locator('.message[data-msg-id="ab7101"]').wait_for()
        assert not analytics_requests
        assert (
          page.evaluate("sessionStorage.getItem('steer:fallbackAnalytics')") is None
        )

        page.reload()
        page.locator("#compose").wait_for()
        app.messages.send_message("Second fallback update", msg_id="ab7102")
        page.clock.fast_forward(3_100)
        page.locator('.message[data-msg-id="ab7102"]').wait_for()
        assert not analytics_requests
        assert (
          page.evaluate("sessionStorage.getItem('steer:fallbackAnalytics')") is None
        )
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
def test_mermaid_thumbnail_preserves_code_footprint(tmp_path: Path, width: int) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore(tmp_path / "state.sqlite3")
  app = SteeringApp(store)
  app.reports.publish_report(
    "diagram-preview",
    "Diagram preview",
    "# Diagram preview\n\n```mermaid\nflowchart TD\n"
    "  A[Start] --> B[Second] --> C[Third] --> D[Fourth] --> E[End]\n```\n",
  )
  server = create_http_server(app, host="127.0.0.1", port=0)
  thread = threading.Thread(target=server.serve_forever, daemon=True)
  thread.start()
  try:
    with playwright.sync_playwright() as runner:
      browser = runner.chromium.launch(
        executable_path=os.environ["ARENA_STEERING_CHROMIUM"],
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage"],
      )
      page = browser.new_page(viewport={"width": width, "height": 844})
      page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
      page.locator("#tab-reports").click()
      page.locator('#report .code-block[data-mermaid-state="rendered"]').wait_for()
      assert page.evaluate("""async () => {
        const {sanitizeMermaidSvg} = await import('/static/assets/markdown.js');
        const unsafe = [
          '<svg xmlns="http://www.w3.org/2000/svg" id="mermaid-steering-1"><rect onload="alert(1)"/></svg>',
          '<svg xmlns="http://www.w3.org/2000/svg" id="mermaid-steering-1"><style>body { display: none }</style></svg>',
          '<svg xmlns="http://www.w3.org/2000/svg" id="mermaid-steering-1">' +
            '<style>#mermaid-steering-1 ~ body { display: none }</style></svg>',
        ];
        return unsafe.every(input => sanitizeMermaidSvg(input) === null);
      }""")
      page.wait_for_function(
        "Object.keys(localStorage).some(key => key.startsWith('steer:mermaid:v2:'))"
      )
      block = page.locator("#report .code-block:has(code.language-mermaid)")
      diagram_box = block.bounding_box()
      assert diagram_box
      assert (
        block.locator(".mermaid-svg").evaluate(
          "element => getComputedStyle(element).userSelect"
        )
        == "none"
      )
      block.locator(".preview-code-mermaid").click()
      code_box = block.bounding_box()
      assert code_box
      assert abs(diagram_box["width"] - code_box["width"]) <= 1
      assert abs(diagram_box["height"] - code_box["height"]) <= 1
      block.locator(".preview-code-mermaid").click()
      thumbnail = block.locator(".mermaid-svg").bounding_box()
      page.screenshot(path=str(tmp_path / f"diagram-thumbnail-{width}.png"))
      block.locator(".mermaid-diagram").click(position={"x": 2, "y": 2})
      assert page.locator("#image-modal").evaluate("element => element.open")
      page.locator("#image-modal-close").click()
      block.locator(".mermaid-svg").click()
      assert page.locator("#image-modal").evaluate("element => element.open")
      modal = page.locator("#image-modal-stage svg").bounding_box()
      assert thumbnail and modal and modal["height"] > thumbnail["height"]
      page.screenshot(path=str(tmp_path / f"diagram-modal-{width}.png"))
      initial_key = page.evaluate(
        "Object.keys(localStorage).find(key => key.startsWith('steer:mermaid:v2:')).split(':').pop()"
      )
      page.add_init_script("""(() => {
        const original = window.fetch.bind(window);
        window.cacheReads = 0;
        window.cacheWrites = 0;
        window.cacheStatuses = [];
        window.cacheUrls = [];
        window.fetch = async (...args) => {
          if (String(args[0]).startsWith('/mermaid-cache/')) {
            window.cacheReads++;
            window.cacheUrls.push(String(args[0]));
          }
          if (String(args[0]) === '/mermaid-cache') window.cacheWrites++;
          const response = await original(...args);
          if (String(args[0]).startsWith('/mermaid-cache/')) window.cacheStatuses.push(response.status);
          return response;
        };
      })();""")
      page.reload()
      page.locator('#report .code-block[data-mermaid-state="rendered"]').wait_for()
      assert page.evaluate("window.cacheReads") == 0
      assert page.evaluate("window.cacheWrites") == 0
      page.evaluate("""() => {
        for (const key of Object.keys(localStorage)) {
          if (key.startsWith('steer:mermaid:v2:')) localStorage.removeItem(key);
        }
      }""")
      page.reload()
      page.locator('#report .code-block[data-mermaid-state="rendered"]').wait_for()
      assert page.evaluate("window.cacheReads") == 1
      assert page.evaluate("window.cacheWrites") == 0, (
        initial_key,
        page.evaluate("window.cacheUrls"),
        page.evaluate("window.cacheStatuses"),
      )
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
def test_mermaid_common_diagrams_persist_in_server_cache(tmp_path: Path) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore(tmp_path / "state.sqlite3")
  app = SteeringApp(store)
  app.reports.publish_report(
    "diagrams",
    "Diagrams",
    "# Diagrams\n\n"
    "```mermaid\nflowchart LR\n  A --> B\n```\n\n"
    "```mermaid\nsequenceDiagram\n  Alice->>Bob: Hello\n  Bob-->>Alice: Hi\n```\n\n"
    "```mermaid\nclassDiagram\n  Animal <|-- Duck\n```\n\n"
    "```mermaid\nstateDiagram-v2\n  [*] --> Ready\n```\n\n"
    '```mermaid\npie\n  "Cats" : 3\n  "Dogs" : 5\n```\n\n'
    "```mermaid\nerDiagram\n  CUSTOMER ||--o{ ORDER : places\n```\n\n"
    "```mermaid\ngantt\n  dateFormat YYYY-MM-DD\n  section Work\n  Task :a, 2026-01-01, 2d\n```\n\n"
    "```mermaid\nflowchart LR\n  A --> B\n```\n",
  )
  server = create_http_server(app, host="127.0.0.1", port=0)
  thread = threading.Thread(target=server.serve_forever, daemon=True)
  thread.start()
  try:
    with playwright.sync_playwright() as runner:
      browser = runner.chromium.launch(
        executable_path=os.environ["ARENA_STEERING_CHROMIUM"],
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage"],
      )
      page = browser.new_page(viewport={"width": 1200, "height": 844})
      page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
      page.locator("#tab-reports").click()
      page.wait_for_function(
        "document.querySelectorAll('#report [data-mermaid-state=rendered]').length === 8"
      )
      ids = page.locator(
        "#report .mermaid-diagram [id], #report .mermaid-diagram > svg[id]"
      ).evaluate_all("elements => elements.map(element => element.id)")
      assert len(ids) == len(set(ids))
      page.wait_for_function(
        "Object.keys(localStorage).filter(key => key.startsWith('steer:mermaid:v2:')).length === 7"
      )
      keys = page.evaluate(
        "Object.keys(localStorage).filter(key => key.startsWith('steer:mermaid:v2:')).map(key => key.split(':').pop())"
      )
      for key in keys:
        assert page.request.get(
          f"http://127.0.0.1:{server.server_port}/mermaid-cache/{key}"
        ).ok
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
def test_survey_refresh_preserves_focus_when_results_are_unchanged(
  tmp_path: Path,
) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore(tmp_path / "state.sqlite3")
  app = SteeringApp(store)
  app.messages.submit_survey(survey.template())
  server = create_http_server(app, host="127.0.0.1", port=0)
  thread = threading.Thread(target=server.serve_forever, daemon=True)
  thread.start()
  try:
    with playwright.sync_playwright() as runner:
      browser = runner.chromium.launch(
        executable_path=os.environ["ARENA_STEERING_CHROMIUM"],
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage"],
      )
      page = browser.new_page(viewport={"width": 411, "height": 799})
      page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
      page.locator("#last-check").get_by_text("Checked", exact=False).wait_for()
      page.evaluate("""() => {
        const original = window.fetch.bind(window);
        window.fetch = async (...args) => {
          if (String(args[0]) === '/survey') {
            await new Promise(resolve => { window.releaseSurvey = resolve; });
            const response = await original(...args);
            window.surveyReturned = true;
            return response;
          }
          return original(...args);
        };
      }""")
      page.locator("#survey-open").click()
      page.locator(".survey-cap-pill").first.wait_for()
      page.wait_for_function("typeof window.releaseSurvey === 'function'")
      page.locator(".survey-cap-pill").first.focus()
      focused = page.locator(".survey-cap-pill").first.element_handle()
      page.evaluate("window.releaseSurvey()")
      page.wait_for_function("window.surveyReturned === true")
      assert focused.evaluate("el => el.isConnected && document.activeElement === el")
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
@pytest.mark.parametrize("fail", [False, True])
@pytest.mark.parametrize("width", [390, 1200])
def test_blocked_bash_dismissal_is_immediate_and_recovers(
  tmp_path: Path, fail: bool, width: int
) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore(tmp_path / "state.sqlite3")
  append_blocked_bash(tmp_path, line="first", command="first", blocked_by="gate")
  append_blocked_bash(tmp_path, line="second", command="second", blocked_by="gate")
  app = SteeringApp(store)
  server = create_http_server(app, host="127.0.0.1", port=0)
  thread = threading.Thread(target=server.serve_forever, daemon=True)
  thread.start()
  try:
    with playwright.sync_playwright() as runner:
      browser = runner.chromium.launch(
        executable_path=os.environ["ARENA_STEERING_CHROMIUM"],
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage"],
      )
      page = browser.new_page(viewport={"width": width, "height": 800})
      page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
      page.locator("#blocked-bash-open").click()
      rows = page.locator("#blocked-bash-log .blocked-bash-entry")
      rows.nth(1).wait_for()
      page.evaluate(
        """fail => {
        const original = window.fetch.bind(window);
        window.fetch = async (...args) => {
          if (String(args[0]).startsWith('/blocked-bash/') && args[1]?.method === 'DELETE') {
            await new Promise(resolve => { window.releaseDismiss = resolve; });
            if (fail) return new Response(JSON.stringify({error:'offline'}), {
              status:503, headers:{'content-type':'application/json'}
            });
          }
          return original(...args);
        };
      }""",
        fail,
      )
      rows.first.locator("button.audit-row-dismiss").click()
      page.wait_for_function("typeof window.releaseDismiss === 'function'")
      assert rows.count() == 1
      assert rows.first.locator('[data-field="line"]').inner_text() == "second"
      if os.environ.get("ARENA_STEERING_SCREENSHOT") and not fail:
        page.screenshot(path=f"{os.environ['ARENA_STEERING_SCREENSHOT']}-{width}.png")
      page.evaluate("window.releaseDismiss()")
      if fail:
        page.locator("#blocked-bash-status").get_by_text(
          "Could not dismiss", exact=False
        ).wait_for()
        assert rows.count() == 2
        assert rows.first.locator('[data-field="line"]').inner_text() == "first"
        assert rows.first.locator("button.audit-row-dismiss").is_enabled()
      else:
        page.wait_for_function(
          "document.querySelector('#blocked-bash-log button')?.disabled === false"
        )
        assert [
          entry["line"] for entry in app.dispatch("GET", "/blocked-bash")[1]["entries"]
        ] == ["second"]
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
def test_report_header_tracks_linked_tasks_without_duplicate_title(
  tmp_path: Path, width: int
) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore(tmp_path / "state.sqlite3")
  app = SteeringApp(store)
  app.reports.publish_report("decision", "Decision", "# Decision\n\nReport body.")
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
        app.tasks.mod_links_rm("linked-two", "report", "decision")
        report.get_by_role("button", name="Open task linked-two").wait_for(
          state="detached", timeout=10000
        )
        title_box = report.locator("h1").bounding_box()
        chip_box = chip.bounding_box()
        id_box = report.locator('button[data-parent-id="decision"]').bounding_box()
        assert title_box and chip_box and id_box
        assert title_box["y"] + title_box["height"] <= chip_box["y"]
        assert chip_box["y"] + chip_box["height"] <= id_box["y"] + 1
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


def test_asset_version_waits_for_ten_quiet_seconds(
  tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  clock = [0.0]
  signature = [(("style.css", 1, 1),)]
  monkeypatch.setattr(steering_server.time, "monotonic", lambda: clock[0])
  monkeypatch.setattr(steering_server, "assets_signature", lambda _path: signature[0])
  store = SqliteStore(tmp_path / "state.sqlite3")
  app = SteeringApp(store)
  initial = app.asset_signature_hash()
  signature[0] = (("style.css", 2, 2),)
  clock[0] = 1
  assert app.asset_signature_hash() == initial
  signature[0] = (("style.css", 3, 3),)
  clock[0] = 8
  assert app.asset_signature_hash() == initial
  clock[0] = 17.9
  assert app.asset_signature_hash() == initial
  clock[0] = 18
  assert app.asset_signature_hash() != initial
  store.close()


@pytest.mark.skipif(
  not os.environ.get("ARENA_STEERING_CHROMIUM"),
  reason="Set ARENA_STEERING_CHROMIUM to run the browser regression",
)
@pytest.mark.parametrize("transport", ["websocket", "poll"])
def test_asset_reload_waits_for_quiet_period_while_state_updates(
  tmp_path: Path, transport: str
) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  assets = tmp_path / "assets"
  shutil.copytree(ASSETS_DIR, assets)
  store = SqliteStore(tmp_path / "state.sqlite3")
  app = SteeringApp(store, assets_dir=assets)
  server = create_http_server(app, host="127.0.0.1", port=0)
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
        page.goto(f"http://127.0.0.1:{server.server_port}/?transport={transport}")
        page.locator('#connection-dot[data-state="ok"]').wait_for()
        page.evaluate("window.reloadMarker = true")
        with (assets / "style.css").open("a", encoding="utf-8") as css:
          css.write("\n/* first change */\n")
        page.wait_for_timeout(4000)
        with (assets / "style.css").open("a", encoding="utf-8") as css:
          css.write("\n/* second change */\n")
        app.messages.send_message(
          "Live state during asset edits", msg_id="e01010", blocking=False
        )
        page.get_by_text("Live state during asset edits").wait_for(timeout=8000)
        page.wait_for_timeout(7500)
        assert page.evaluate("window.reloadMarker === true")
        page.wait_for_function("window.reloadMarker !== true", timeout=15000)
      finally:
        browser.close()
  finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)
    store.close()


def test_timestamp_timer_does_not_add_tooltips() -> None:
  script = r"""
import assert from 'node:assert/strict';
import { mountRelativeTimers } from './skills/arena-steering/assets/timestamps.js';

globalThis.window = { setTimeout: () => 1, clearTimeout: () => {} };
for (const stamp of ['2026-11-06T19:16:41Z', '2026-11-06T00:03:04Z']) {
  for (const state of [null, 'Status: acked']) {
    const attrs = { 'data-timestamp': stamp, 'data-state-label': state };
    const node = {
      title: '', textContent: '',
      getAttribute(name) { return attrs[name] || null; },
      setAttribute(name, value) { attrs[name] = value; },
    };
    const stop = mountRelativeTimers({ querySelectorAll: () => [node] });
    assert.equal(node.title, '');
    if (state) assert.ok(attrs['aria-label'].startsWith(`${state}, `));
    stop();
  }
}
"""
  result = subprocess.run(
    ["node", "--experimental-default-type=module", "--input-type=module", "-e", script],
    cwd=ROOT,
    env={**os.environ, "TZ": "UTC", "LANG": "en_US.UTF-8"},
    capture_output=True,
    text=True,
    check=False,
  )
  assert result.returncode == 0, result.stderr


@pytest.mark.skipif(
  not os.environ.get("ARENA_STEERING_CHROMIUM"),
  reason="Set ARENA_STEERING_CHROMIUM to run the browser regression",
)
@pytest.mark.parametrize("width", [390, 1200])
def test_selected_tooltips_are_absent_but_control_labels_remain(
  tmp_path: Path, width: int
) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore(tmp_path / "state.sqlite3")
  app = SteeringApp(store)
  app.messages.send_message("Tooltip test", msg_id="ab1234")
  app.reports.publish_report(
    "decision",
    "Decision",
    '<!-- question {"id":"q","label":"Question"} -->\nQuestion\n'
    '- (x) Yes <!-- option {"label":"Yes"} -->\n',
  )
  app.reports.publish_report("other", "Other", "# Other")
  server = create_http_server(app, host="0.0.0.0", port=0)
  thread = threading.Thread(target=server.serve_forever, daemon=True)
  thread.start()
  try:
    with playwright.sync_playwright() as runner:
      browser = runner.chromium.launch(
        executable_path=os.environ["ARENA_STEERING_CHROMIUM"], args=["--no-sandbox"]
      )
      try:
        page = browser.new_page(viewport={"width": width, "height": 800})
        page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
        page.locator('.message[data-msg-id="ab1234"]').wait_for()
        for selector in (
          "#connection-text",
          "#log-newest",
          "#report-needs-answer",
          "#report-pip",
          "#modal-close",
        ):
          assert page.locator(selector).get_attribute("title") is None, selector
        assert (
          page.locator("#log-newest").get_attribute("aria-label") == "Scroll to bottom"
        )
        assert (
          page.locator("#modal-close").get_attribute("aria-label") == "Close dialog"
        )
        assert page.locator(".receipt-status").get_attribute("title") is None
        page.locator("#tab-reports").click()
        page.locator(".report-picker-unanswered").wait_for()
        for selector in (
          ".report-picker-unanswered",
          ".report-picker-unseen-dot",
          ".report-scroll-top",
        ):
          assert page.locator(selector).get_attribute("title") is None, selector
        assert (
          page.locator(".report-picker-unanswered").get_attribute("aria-label")
          == "Needs answers"
        )
        for timestamp in page.locator("time").all():
          assert timestamp.get_attribute("title") is None
        page.screenshot(path=str(tmp_path / f"no-selected-tooltips-{width}.png"))
      finally:
        browser.close()
  finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)
    store.close()


def test_composer_storage_failure_prevents_unsafe_reload_state() -> None:
  script = r"""
import assert from 'node:assert/strict';
const values = new Map();
let broken = false;
globalThis.sessionStorage = {
  getItem: key => values.get(key) || null,
  setItem: (key, value) => { if (broken) throw new Error('quota'); values.set(key, value); },
  removeItem: key => { if (broken) throw new Error('quota'); values.delete(key); },
};
const { createStore } = await import('./skills/arena-steering/assets/state.js');
const store = createStore();
store.setState({ replyParentRefs: [{type: 'task', id: 'selected'}] });
assert.equal(store.getState().composerPersistenceError, false);
broken = true;
store.setState({ replyParentRefs: [] });
assert.equal(store.getState().composerPersistenceError, true);
broken = false;
store.setState({ replyParentRefs: [] });
assert.equal(store.getState().composerPersistenceError, false);
assert.equal(values.has('steer:composerState'), false);
"""
  result = subprocess.run(
    ["node", "--experimental-default-type=module", "--input-type=module", "-e", script],
    cwd=ROOT,
    capture_output=True,
    text=True,
    check=False,
  )
  assert result.returncode == 0, result.stderr


def _stamp(seconds_ago: float = 0) -> str:
  return (datetime.now(UTC) - timedelta(seconds=seconds_ago)).isoformat()


def test_health_exposes_native_tool_cadence(tmp_path: Path) -> None:
  store = SqliteStore(tmp_path / "state.sqlite3")
  app = SteeringApp(store)
  try:
    store.set_meta("last_tool_name", "bash")
    store.set_meta("last_tool_at", "2026-01-01T00:00:03Z")
    store.set_meta("pre_call_count", "4")
    status, health = app.dispatch("GET", "/health")
    assert status == 200
    assert health["last_tool"] == {
      "tool": "bash",
      "at": "2026-01-01T00:00:03Z",
    }
    assert health["calls_since_message"] == 4
  finally:
    store.close()


def test_poll_heartbeat_and_wake_across_store_connections(tmp_path: Path) -> None:
  db = tmp_path / "state.sqlite3"
  polling_store = SqliteStore(db)
  server_store = SqliteStore(db)
  polling_app = SteeringApp(polling_store)
  server_app = SteeringApp(server_store)
  delivered: list[dict] = []
  thread = threading.Thread(
    target=lambda: delivered.append(polling_app.messages.poll(timeout_seconds=5)),
    daemon=True,
  )
  thread.start()
  try:
    deadline = time.monotonic() + 0.8
    while not server_store.get_meta("polling_at") and time.monotonic() < deadline:
      time.sleep(0.02)
    status, health = server_app.dispatch("GET", "/health")
    assert status == 200
    assert health["polling"] is True
    assert health["polling_since"]
    server_app.messages.send_message("Wake the other process", msg_id="ac0001")
    thread.join(timeout=2.5)
    assert not thread.is_alive()
    assert [msg.id for msg in delivered[0]["messages"]] == ["ac0001"]
    assert server_app.dispatch("GET", "/health")[1]["polling"] is False
  finally:
    thread.join(timeout=6)
    polling_store.close()
    server_store.close()


def test_skip_poll_from_another_store_marks_turn_ended(tmp_path: Path) -> None:
  db = tmp_path / "state.sqlite3"
  polling_store = SqliteStore(db)
  server_store = SqliteStore(db)
  poller = SteeringApp(polling_store)
  sender = SteeringApp(server_store)
  thread = threading.Thread(
    target=lambda: poller.messages.poll(timeout_seconds=5), daemon=True
  )
  thread.start()
  try:
    deadline = time.monotonic() + 0.8
    while not server_store.get_meta("polling_at") and time.monotonic() < deadline:
      time.sleep(0.02)
    sender.messages.trigger_skip_poll()
    thread.join(timeout=2.5)
    assert not thread.is_alive()
    status, health = sender.dispatch("GET", "/health")
    assert status == 200
    assert health["polling"] is False
    assert health["turn_ended_at"]
  finally:
    thread.join(timeout=6)
    polling_store.close()
    server_store.close()


def test_skip_arriving_during_live_run_waits_until_run_ends(tmp_path: Path) -> None:
  db = tmp_path / "state.sqlite3"
  polling_store = SqliteStore(db)
  sender_store = SqliteStore(db)
  poller = SteeringApp(polling_store)
  sender = SteeringApp(sender_store)
  live = [True]
  delivered: list[dict] = []
  thread = threading.Thread(
    target=lambda: delivered.append(
      poller.messages.poll(timeout_seconds=0.25, live_run=lambda: live[0])
    ),
    daemon=True,
  )
  thread.start()
  try:
    deadline = time.monotonic() + 0.8
    while not sender_store.get_meta("polling_at") and time.monotonic() < deadline:
      time.sleep(0.02)
    assert sender_store.get_meta("polling_at")
    sender.messages.trigger_skip_poll()
    thread.join(timeout=1.5)
    assert not thread.is_alive()
    assert delivered[0]["status"] == "timeout"
    assert sender_store.get_meta("skip_poll") == "1"
    live[0] = False
    assert poller.messages.poll()["status"] == "skipped"
    assert sender_store.get_meta("skip_poll") == "0"
  finally:
    thread.join(timeout=2)
    polling_store.close()
    sender_store.close()


def test_answer_wakes_poll_without_lock_inversion() -> None:
  store = SqliteStore()
  app = SteeringApp(store)
  app.reports.publish_report(
    "choice",
    "Choice",
    '<!-- question {"id": "pick", "label": "Pick"} -->\n'
    'Pick\n- (x) Yes <!-- option {"label": "Yes"} -->\n',
  )
  delivered: list[dict] = []
  poller = threading.Thread(
    target=lambda: delivered.append(app.messages.poll(timeout_seconds=5)), daemon=True
  )
  poller.start()
  try:
    deadline = time.monotonic() + 0.8
    while not store.get_meta("polling_at") and time.monotonic() < deadline:
      time.sleep(0.02)
    app.reports.submit_answer("choice", {"pick": "Yes"}, answer_id="ac0003")
    poller.join(timeout=2.5)
    assert not poller.is_alive()
    assert [answer.id for _, answer in delivered[0]["report_answers"]] == ["ac0003"]
  finally:
    poller.join(timeout=6)
    store.close()


def test_health_expires_abandoned_poll_heartbeat() -> None:
  store = SqliteStore()
  app = SteeringApp(store)
  try:
    store.set_meta("polling_at", _stamp(6))
    store.set_meta("polling_since", _stamp(60))
    status, health = app.dispatch("GET", "/health")
    assert status == 200
    assert health["polling"] is False
    assert health["polling_since"] is None
  finally:
    store.close()


def test_timed_out_poll_marks_turn_end() -> None:
  store = SqliteStore()
  app = SteeringApp(store)
  try:
    result = app.messages.poll(timeout_seconds=0.05)
    assert result["status"] == "timeout"
    assert store.get_meta("turn_ended_at")
    assert not store.get_meta("polling_at")
    app.messages.touch_agent()
    assert not store.get_meta("turn_ended_at")
  finally:
    store.close()


def test_agent_poll_uses_initial_task_without_wait() -> None:
  store = SqliteStore()
  app = SteeringApp(store)
  try:
    task = app.tasks.create_task(
      "initial", "Initial task", size=2, details=["Do the first task."]
    )
    app.messages.trigger_skip_poll()
    delivered = app.messages.poll(timeout_seconds=0.4, initial_task=task)
    assert delivered["status"] == "ready"
    assert delivered["next_task"].id == "initial"
    assert store.get_meta("skip_poll") == "1"
    assert not store.get_meta("turn_ended_at")
  finally:
    store.close()


def test_agent_poll_does_not_recheck_gate_linked_task(tmp_path: Path) -> None:
  db = tmp_path / "state.sqlite3"
  polling_store = SqliteStore(db)
  other_store = SqliteStore(db)
  poller = SteeringApp(polling_store)
  sender = SteeringApp(other_store)
  runs = tmp_path / "runs"
  runs.mkdir()
  exit_path = runs / "verify.exit"
  (runs / "verify.json").write_text(
    json.dumps({"exit_path": str(exit_path)}), encoding="utf-8"
  )
  sender.tasks.create_task(
    "gate-task", "Gate task", size=3, gate_names=["verify"], details=["Wait for gate."]
  )
  gate_id = "gate-task"
  assert poller.tasks.has_running_gate(poller.tasks.get_task(gate_id)[0])
  delivered: list[dict] = []
  thread = threading.Thread(
    target=lambda: delivered.append(poller.messages.poll(timeout_seconds=0.25)),
    daemon=True,
  )
  thread.start()
  try:
    deadline = time.monotonic() + 0.8
    while not other_store.get_meta("polling_at") and time.monotonic() < deadline:
      time.sleep(0.02)
    assert other_store.get_meta("polling_at")
    exit_path.write_text("0", encoding="utf-8")
    thread.join(timeout=1.5)
    assert not thread.is_alive()
    assert delivered[0]["status"] == "timeout"
    assert delivered[0]["next_task"] is None
    assert not poller.tasks.get_task(gate_id)[1]
  finally:
    thread.join(timeout=3)
    polling_store.close()
    other_store.close()


def test_cli_agent_call_clears_turn_end(
  tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  monkeypatch.setattr(cli, "resolve_state_dir", lambda: tmp_path)
  store = SqliteStore(tmp_path / "state.sqlite3")
  try:
    old_seen = _stamp(2000)
    store.set_meta("agent_seen_at", old_seen)
    store.set_meta("turn_ended_at", _stamp(200))
    assert cli.main(["read"], out=io.StringIO(), err=io.StringIO()) == 0
    assert not store.get_meta("turn_ended_at")
    assert store.get_meta("agent_seen_at") != old_seen
  finally:
    store.close()


def test_cli_repeated_fast_poll_flags_once_without_flagging_browser(
  tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  state_dir = tmp_path / "arena-state"
  monkeypatch.setattr(cli, "resolve_state_dir", lambda: state_dir)
  store, messages, _, _ = cli.open_services(state_dir)
  messages.send_message("Pending work", blocking=True)
  assert cli.main(["poll"], out=io.StringIO(), err=io.StringIO()) == 0

  browser = SteeringApp(store)
  assert browser.dispatch("GET", "/poll?timeout=0")[0] == 200
  out = io.StringIO()
  assert cli.main(["poll"], out=out, err=io.StringIO()) == 2
  flag = messages.pending_violation()
  assert flag is not None and flag.hidden and flag.requires_ack
  assert flag.violation_type == "repeat-poll"
  assert flag.body == with_bible_read(
    "VIOLATION: Repeat poll. Use worktree if more task open."
  )
  assert cli.main(["poll"], out=io.StringIO(), err=io.StringIO()) == 2
  assert messages.pending_violation().id == flag.id
  store.close()


def test_cli_poll_repeat_uses_v1_timing_and_resets_after_read(
  tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  import arena_steering.services as service_module

  now = [1000]
  monkeypatch.setattr(service_module.time, "time", lambda: now[0])
  state_dir = tmp_path / "arena-state"
  monkeypatch.setattr(cli, "resolve_state_dir", lambda: state_dir)
  store, messages, _, _ = cli.open_services(state_dir)
  messages.send_message("Pending work", blocking=True)

  def poll() -> int:
    return cli.main(["poll"], out=io.StringIO(), err=io.StringIO())

  assert poll() == 0
  now[0] += 46
  assert poll() == 0
  assert cli.main(["read"], out=io.StringIO(), err=io.StringIO()) == 0
  now[0] += 1
  assert poll() == 0
  now[0] += 45
  assert poll() == 2
  flag = messages.pending_violation()
  assert flag is not None and flag.violation_type == "repeat-poll"
  messages.ack(flag.id, "Read; work resumed.")
  messages.record_poll_duration(1.0)
  now[0] += 1
  assert poll() == 0
  assert messages.pending_violation() is None
  store.close()


@pytest.mark.skipif(
  not os.environ.get("ARENA_STEERING_CHROMIUM"),
  reason="Set ARENA_STEERING_CHROMIUM to run the browser regression",
)
def test_connection_states_and_survey_modal(tmp_path: Path) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore(tmp_path / "state.sqlite3")
  app = SteeringApp(store, repo_name="Connection states")
  app.messages._survey_results = [{"id": "test", "correct": False}]
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
        page.add_init_script(
          """(() => {
            const realFetch = window.fetch;
            window.fetch = (...args) => {
              if (args[0] === '/health' && !window.releaseHealth) {
                return new Promise(resolve => { window.releaseHealth = () => resolve(realFetch(...args)); });
              }
              return realFetch(...args);
            };
          })()"""
        )
        page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
        dot = page.locator("#connection-dot")
        page.wait_for_function("() => !!window.releaseHealth", timeout=7000)
        assert dot.get_attribute("data-state") == "connecting"
        page.evaluate("window.releaseHealth()")
        page.wait_for_function(
          "() => document.querySelector('#connection-dot')?.dataset.state === 'ok'"
        )
        assert (
          dot.evaluate("el => getComputedStyle(el).backgroundColor")
          == "rgb(34, 197, 94)"
        )
        states = page.evaluate(
          """async () => {
            const { connectionPresentation } = await import('/messages-view.js');
            const now = Date.parse('2026-01-01T12:00:00Z');
            return [
              connectionPresentation({loaded: true, turn_ended_at: '2026-01-01T11:57:00Z'}, now).state,
              connectionPresentation({loaded: true, turn_ended_at: '2026-01-01T11:56:59Z'}, now).state,
              connectionPresentation({loaded: true, agent_seen_at: '2026-01-01T11:28:00Z'}, now).state,
              connectionPresentation({loaded: true, agent_seen_at: '2026-01-01T11:27:59Z'}, now).state,
              connectionPresentation({loaded: true, polling: true, turn_ended_at: '2026-01-01T11:00:00Z'}, now).state,
            ];
          }"""
        )
        assert states == ["ok", "idle", "ok", "idle", "polling"]
        page.locator("#survey-open").click()
        page.locator("#modal-shell").wait_for(state="visible")
        assert page.get_by_role("heading", name="Survey Verification").is_visible()
        page.get_by_role("button", name="Close dialog").click()

        store.set_meta("turn_ended_at", _stamp(181))
        page.wait_for_function(
          "() => document.querySelector('#connection-dot')?.dataset.state === 'idle'",
          timeout=7000,
        )
        store.set_meta("polling_at", _stamp())
        store.set_meta("polling_since", _stamp(10))
        page.wait_for_function(
          "() => document.querySelector('#connection-dot')?.dataset.state === 'polling'",
          timeout=7000,
        )
        store.set_meta("polling_at", _stamp(6))
        page.wait_for_function(
          "() => document.querySelector('#connection-dot')?.dataset.state === 'idle'",
          timeout=7000,
        )
        store.set_meta("turn_ended_at", "")
        store.set_meta("agent_seen_at", _stamp())
        page.wait_for_function(
          "() => document.querySelector('#connection-dot')?.dataset.state === 'ok'",
          timeout=7000,
        )
        store.set_meta("agent_seen_at", _stamp(1921))
        page.wait_for_function(
          "() => document.querySelector('#connection-dot')?.dataset.state === 'idle'",
          timeout=7000,
        )
        page.route("**/health", lambda route: route.abort())
        page.wait_for_function(
          "() => document.querySelector('#connection-dot')?.dataset.state === 'down'",
          timeout=7000,
        )
        assert dot.get_attribute("aria-label") == "Disconnected"
        page.unroute("**/health")
        page.wait_for_function(
          "() => document.querySelector('#connection-dot')?.dataset.state === 'idle'",
          timeout=7000,
        )
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
def test_title_tooltip_matches_arena_and_preserves_survey_click(tmp_path: Path) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore(tmp_path / "state.sqlite3")
  app = SteeringApp(store)
  server = create_http_server(app, host="127.0.0.1", port=0)
  thread = threading.Thread(target=server.serve_forever, daemon=True)
  thread.start()
  try:
    with playwright.sync_playwright() as runner:
      browser = runner.chromium.launch(
        executable_path=os.environ["ARENA_STEERING_CHROMIUM"], args=["--no-sandbox"]
      )
      try:
        page = browser.new_page(viewport={"width": 1200, "height": 800})
        page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
        button = page.locator("#survey-open")
        dot = page.locator("#connection-dot")
        dot_color = dot.evaluate("el => getComputedStyle(el).backgroundColor")
        button.hover()
        tip = page.get_by_role("tooltip").filter(has_text="Open survey results")
        assert tip.is_visible()
        page.screenshot(path=str(tmp_path / "animated-tooltip.png"))
        styles = tip.evaluate("""el => ({
          bg: getComputedStyle(el).backgroundColor,
          color: getComputedStyle(el).color,
          top: el.getBoundingClientRect().top,
          bottom: el.getBoundingClientRect().bottom,
          triggerTop: document.querySelector('#survey-open').getBoundingClientRect().top,
          triggerBottom: document.querySelector('#survey-open').getBoundingClientRect().bottom,
          above: el.classList.contains('above'),
          arrow: getComputedStyle(el, '::before')[
            el.classList.contains('above') ? 'borderTopColor' : 'borderBottomColor'
          ],
        })""")
        assert styles["bg"] == "rgb(255, 255, 255)"
        assert styles["color"] == "rgb(24, 24, 24)"
        if styles["above"]:
          assert styles["bottom"] <= styles["triggerTop"]
        else:
          assert styles["top"] >= styles["triggerBottom"]
        assert styles["arrow"] == styles["bg"]
        assert button.get_attribute("aria-describedby") == "arena-title-tooltip"
        assert dot.evaluate("el => getComputedStyle(el).backgroundColor") == dot_color
        button.evaluate("el => el.title = 'Updated survey status'")
        updated = page.get_by_role("tooltip").filter(has_text="Updated survey status")
        updated.wait_for()
        page.mouse.move(600, 700)
        assert not tip.is_visible()
        assert button.get_attribute("title") == "Updated survey status"
        button.evaluate("el => el.title = 'Open survey results'")
        button.click()
        page.get_by_role("heading", name="Survey Verification").wait_for()
        page.get_by_role("button", name="Close dialog").click()
        page.keyboard.press("Tab")
        button.focus()
        assert tip.is_visible()
        page.keyboard.press("Escape")
        assert tip.is_hidden()
        page.evaluate("""() => {
          const target = document.createElement('button');
          target.id = 'image-tooltip-probe';
          target.title = 'Helpful details';
          target.style.cssText = 'position:fixed;top:180px;left:180px';
          target.innerHTML = '<img alt="Existing name">';
          document.body.append(target);
        }""")
        image_button = page.get_by_role("button", name="Existing name")
        image_button.hover()
        assert page.get_by_role("button", name="Existing name").is_visible()
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
def test_tooltip_entrance_follows_placement_and_reduced_motion(tmp_path: Path) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore(tmp_path / "state.sqlite3")
  app = SteeringApp(store)
  server = create_http_server(app, host="127.0.0.1", port=0)
  thread = threading.Thread(target=server.serve_forever, daemon=True)
  thread.start()
  try:
    with playwright.sync_playwright() as runner:
      browser = runner.chromium.launch(
        executable_path=os.environ["ARENA_STEERING_CHROMIUM"], args=["--no-sandbox"]
      )
      try:
        page = browser.new_page(viewport={"width": 1200, "height": 800})
        page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
        page.evaluate("""() => {
          for (const [id, top] of [['low', 300], ['high', 0]]) {
            const target = document.createElement('button');
            target.id = id;
            target.title = id;
            target.style.cssText = `position:fixed;z-index:999;left:180px;top:${top}px`;
            document.body.append(target);
          }
        }""")
        for target, expected in (
          ("low", "tooltip-from-below"),
          ("high", "tooltip-from-above"),
        ):
          page.locator(f"#{target}").hover()
          tip = page.locator("#arena-title-tooltip")
          assert tip.evaluate("el => getComputedStyle(el).animationName") == expected
          assert tip.evaluate("el => getComputedStyle(el).animationDuration") == "0.15s"
        page.mouse.move(600, 700)
        page.emulate_media(reduced_motion="reduce")
        page.locator("#low").hover()
        assert (
          page.locator("#arena-title-tooltip").evaluate(
            "el => getComputedStyle(el).animationName"
          )
          == "none"
        )
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
def test_floating_controls_keep_neutral_shape_on_hover(tmp_path: Path) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore(tmp_path / "state.sqlite3")
  server = create_http_server(SteeringApp(store), host="0.0.0.0", port=0)
  thread = threading.Thread(target=server.serve_forever, daemon=True)
  thread.start()
  try:
    with playwright.sync_playwright() as runner:
      browser = runner.chromium.launch(
        executable_path=os.environ["ARENA_STEERING_CHROMIUM"],
        args=["--no-sandbox", "--disable-dev-shm-usage"],
      )
      try:
        page = browser.new_page(viewport={"width": 800, "height": 600})
        page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
        for index, name in enumerate(("log-edited", "log-newest", "report-scroll-top")):
          button = page.evaluate_handle(
            """([name, index]) => {
              const button = document.createElement('button');
              button.className = name;
              button.textContent = name;
              Object.assign(button.style, { position: 'fixed', left: '250px',
                top: `${120 + index * 80}px`, bottom: 'auto', transition: 'none' });
              document.body.appendChild(button);
              return button;
            }""",
            [name, index],
          ).as_element()
          assert button is not None
          style = """el => {
            const s = getComputedStyle(el);
            return {color: s.color, border: s.borderColor,
              radius: s.borderRadius, background: s.backgroundColor};
          }"""
          before = button.evaluate(style)
          button.hover()
          after = button.evaluate(style)
          assert after["color"] == before["color"]
          assert after["border"] == before["border"]
          assert after["radius"] == before["radius"]
          assert after["background"] != before["background"]
          page.screenshot(path=str(tmp_path / f"floating-hover-{name}.png"))
      finally:
        browser.close()
  finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)
    store.close()


SOURCE_FILE_UNAVAILABLE = "Source file: unavailable"


def test_violation_flag_lifecycle_and_validation(tmp_path: Path) -> None:
  db_path = tmp_path / "state.sqlite3"
  store = SqliteStore(db_path)
  try:
    app = SteeringApp(store)
    app.messages.send_message("Ordinary pending message", msg_id="ab0001")
    status, health = app.dispatch("GET", "/health")
    assert status == HTTPStatus.OK
    assert health["agent_interrupt_pending"] is False
    assert {"ARENA.md", "AGENTS.md"} <= set(health["read_set"])

    before = len(app.messages.list_messages())
    flag = {
      "armed": True,
      "tab": "messages",
      "reason": "bash-violation",
      "clause_file": "ARENA.md",
      "msg": "The command failed without an acknowledgement.",
    }
    status, result = app.dispatch("POST", "/agent-interrupt", flag)
    assert status == HTTPStatus.OK
    assert result["agent_interrupt_pending"] is True
    messages = app.messages.list_messages()
    assert len(messages) > before
    flagged = [message for message in messages if message.violation_type]
    assert len(flagged) == 1
    violation = flagged[0]
    assert violation.hidden and violation.blocking
    assert violation.violation_type == flag["reason"]
    assert violation.violation_clause_file == flag["clause_file"]
    assert "Cited: " + flag["msg"] in violation.body
    assert BIBLE_READ == "If full bible missing, use read_file for {paths}"
    assert violation.body.endswith(with_bible_read("").strip())
    root = Path(__file__).resolve().parents[3]
    for relative in (
      "AGENTS.md",
      "ARENA.md",
      ".agents/skills/arena-steering/SKILL.md",
    ):
      assert home_relative(root / relative) in violation.body
    assert violation.id in app.messages.pending_ids()

    status, duplicate = app.dispatch("POST", "/agent-interrupt", flag)
    assert status == HTTPStatus.OK and duplicate == result
    assert len(app.messages.list_messages()) == len(messages)
    for invalid in (
      {**flag, "armed": "false"},
      {**flag, "tab": "reports"},
      {**flag, "clause_file": "../outside.md"},
      {**flag, "clause_file": 0},
      {**flag, "msg": {"not": "text"}},
      {**flag, "note": "Legacy key is not supported"},
      {
        **{key: value for key, value in flag.items() if key != "msg"},
        "note": "Legacy key",
      },
    ):
      status, _ = app.dispatch("POST", "/agent-interrupt", invalid)
      assert status == HTTPStatus.BAD_REQUEST
    assert len(app.messages.list_messages()) == len(messages)
  finally:
    store.close()

  store = SqliteStore(db_path)
  try:
    app = SteeringApp(store)
    assert app.dispatch("GET", "/health")[1]["agent_interrupt_pending"] is True
    assert app.messages.get_message(violation.id).violation_type == flag["reason"]
    status, cancelled = app.dispatch(
      "POST", "/agent-interrupt", {"armed": False, "tab": "messages"}
    )
    assert status == HTTPStatus.OK
    assert cancelled["agent_interrupt_pending"] is False
    assert app.messages.get_message(violation.id).status == "acked"
    assert app.messages.pending_ids() == ["ab0001"]

    status, task = app.dispatch(
      "POST",
      "/tasks",
      {
        "id": "check-inbox",
        "title": "Check the inbox",
        "size": 3,
        "details": ["Read the current task."],
      },
    )
    assert status == HTTPStatus.CREATED
    status, result = app.dispatch(
      "POST", "/agent-interrupt", {"tab": "tasks", "reason": "current-task-violation"}
    )
    assert status == HTTPStatus.OK and result["agent_interrupt_pending"] is True
    task_flag = next(
      message
      for message in app.messages.list_messages()
      if message.violation_type == "current-task-violation"
    )
    assert task["task"]["id"] in task_flag.body
    app.dispatch(
      "POST", f"/messages/{task_flag.id}/ack", {"markdown": "Read the clause."}
    )
    assert app.dispatch("GET", "/health")[1]["agent_interrupt_pending"] is False

    app.reports.publish_report("review", "Review", "Report body.")
    status, result = app.dispatch(
      "POST",
      "/agent-interrupt",
      {"tab": "reports", "reason": "format-violation", "report_id": "review"},
    )
    assert status == HTTPStatus.OK and result["agent_interrupt_pending"] is True
    report_flag = next(
      message
      for message in app.messages.list_messages()
      if message.violation_type == "format-violation"
    )
    assert "review" in report_flag.body
    status, _ = app.dispatch(
      "POST",
      "/agent-interrupt",
      {"tab": "reports", "reason": "format-violation", "report_id": "missing"},
    )
    assert status == HTTPStatus.BAD_REQUEST
  finally:
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
@pytest.mark.parametrize(("width", "height"), [(1280, 800), (390, 844)])
def test_violation_form_and_cancel_in_browser(
  tmp_path: Path, width: int, height: int
) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore(tmp_path / "state.sqlite3")
  app = SteeringApp(store, repo_name="Violation form test")
  app.tasks.create_task(
    "fix-flag",
    "Fix violation flag",
    size=3,
    type="code",
    details=["Fix the violation form."],
  )
  app.reports.publish_report("review", "Review", "Report body.")
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
        page.evaluate("document.fonts.ready")
        page.screenshot(path=str(tmp_path / f"violation-before-{width}.png"))
        button = page.locator("#agent-interrupt")
        button.click()
        form = page.locator("#violation-form")
        form.wait_for(state="visible", timeout=5000)
        reason = page.locator("#violation-reason")
        assert reason.locator('option[value="bash-violation"]').count() > 0
        assert reason.locator('option[value="format-violation"]').count() == 0
        page.locator("#violation-clause-file").select_option("ARENA.md")
        cited_reason = "Wrong command."
        assert (
          page.locator('label[for="violation-msg"]').inner_text()  # nonemo: NMT100
          == "Cited reason (optional)"
        )
        page.locator("#violation-msg").fill(cited_reason)
        box = form.bounding_box()
        assert box and box["x"] >= 0 and box["x"] + box["width"] <= width
        page.screenshot(path=str(tmp_path / f"violation-form-{width}.png"))

        page.route(
          "**/agent-interrupt",
          lambda route: route.fulfill(
            status=503, body='{"error":"Try again"}', content_type="application/json"
          ),
          times=1,
        )
        with page.expect_request("**/agent-interrupt") as sent:
          page.locator("#violation-submit").click()
        assert sent.value.post_data_json["msg"] == cited_reason
        assert "note" not in sent.value.post_data_json
        page.locator("#violation-error").wait_for(state="visible", timeout=5000)
        assert form.is_visible()
        assert button.get_attribute("aria-pressed") == "false"
        page.locator("#violation-submit").click()
        page.get_by_role("button", name="Cancel", exact=True).click()
        page.locator("#violation-form").wait_for(state="visible", timeout=5000)
        assert page.locator("#violation-msg").input_value() == cited_reason
        page.locator("#violation-submit").click()
        with page.expect_response("**/agent-interrupt"):
          page.get_by_role("button", name="Retry same action").click()
        page.locator("#modal-shell").wait_for(state="hidden")
        page.wait_for_function(
          "document.querySelector('#agent-interrupt').getAttribute('aria-pressed') === 'true'"
        )
        violation = app.messages.pending_violation()
        assert violation is not None and violation.violation_clause_file == "ARENA.md"
        assert cited_reason in violation.body
        page.screenshot(path=str(tmp_path / f"violation-pending-{width}.png"))

        page.route(
          "**/agent-interrupt",
          lambda route: route.fulfill(
            status=503, body='{"error":"Try again"}', content_type="application/json"
          ),
          times=1,
        )
        button.click()
        page.locator("#violation-status").wait_for(state="visible", timeout=5000)
        assert button.get_attribute("aria-pressed") == "true"
        assert app.messages.pending_violation() is not None
        button.click()
        with page.expect_response("**/agent-interrupt"):
          page.get_by_role("button", name="Retry same action").click()
        page.wait_for_function(
          "document.querySelector('#agent-interrupt').getAttribute('aria-pressed') === 'false'"
        )
        assert app.messages.pending_violation() is None
        page.locator("#tab-reports").click()
        button.click()
        form.wait_for(state="visible", timeout=5000)
        assert reason.locator('option[value="format-violation"]').count() > 0
        reason.select_option("format-violation")
        with page.expect_response("**/agent-interrupt"):
          page.locator("#violation-submit").click()
        page.wait_for_function(
          "document.querySelector('#agent-interrupt').getAttribute('aria-pressed') === 'true'"
        )
        report_flag = app.messages.pending_violation()
        assert report_flag is not None and "Report: review" in report_flag.body
        app.messages.ack(report_flag.id, "Read the clause.")
        page.reload()
        assert button.get_attribute("aria-pressed") == "false"

        page.locator("#tab-tasks").click()
        button.click()
        form.wait_for(state="visible", timeout=5000)
        assert reason.locator('option[value="current-task-violation"]').count() > 0
        assert reason.locator('option[value="bash-violation"]').count() == 0
        reason.select_option("current-task-violation")
        with page.expect_response("**/agent-interrupt"):
          page.locator("#violation-submit").click()
        page.wait_for_function(
          "document.querySelector('#agent-interrupt').getAttribute('aria-pressed') === 'true'"
        )
        task_flag = app.messages.pending_violation()
        assert task_flag is not None and "Current task: fix-flag" in task_flag.body
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
@pytest.mark.parametrize("armed", [False, True])
@pytest.mark.parametrize("fail", [False, True])
def test_violation_flag_updates_before_write_and_restores_on_failure(
  tmp_path: Path, armed: bool, fail: bool
) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore(tmp_path / "state.sqlite3")
  app = SteeringApp(store)
  if not armed:
    assert (
      app.dispatch(
        "POST",
        "/agent-interrupt",
        {"armed": True, "tab": "messages", "reason": "bash-violation"},
      )[0]
      == 200
    )
  server = create_http_server(app, host="127.0.0.1", port=0)
  thread = threading.Thread(target=server.serve_forever, daemon=True)
  thread.start()
  try:
    with playwright.sync_playwright() as runner:
      browser = runner.chromium.launch(
        executable_path=os.environ["ARENA_STEERING_CHROMIUM"],
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage"],
      )
      page = browser.new_page()
      page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
      button = page.locator("#agent-interrupt")
      page.wait_for_function(
        "expected => document.querySelector('#agent-interrupt').getAttribute('aria-pressed') === expected",
        arg="false" if armed else "true",
      )
      if armed:
        button.click()
        page.locator("#violation-form").wait_for()
        page.locator("#violation-msg").fill("Keep this draft")
      page.evaluate(
        """fail => {
        const original = window.fetch.bind(window);
        window.fetch = async (...args) => {
          if (String(args[0]) === '/agent-interrupt' && args[1]?.method === 'POST') {
            await new Promise(resolve => { window.releaseFlag = resolve; });
            if (fail) return new Response(JSON.stringify({error:'offline'}), {
              status:503, headers:{'content-type':'application/json'}
            });
          }
          return original(...args);
        };
      }""",
        fail,
      )
      if armed:
        page.locator("#violation-submit").click()
      else:
        button.click()
      page.wait_for_function("typeof window.releaseFlag === 'function'")
      assert button.get_attribute("aria-pressed") == str(armed).lower()
      page.evaluate("window.releaseFlag()")
      if fail:
        page.locator("#violation-error" if armed else "#violation-status").wait_for(
          state="visible"
        )
        assert button.get_attribute("aria-pressed") == str(not armed).lower()
        if armed:
          assert page.locator("#violation-msg").input_value() == "Keep this draft"
      else:
        page.wait_for_function(
          "document.querySelector('#agent-interrupt').getAttribute('aria-busy') !== 'true'"
        )
        assert button.get_attribute("aria-pressed") == str(armed).lower()
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
def test_slow_send_confirmation_keeps_newer_live_ack(tmp_path: Path) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore(tmp_path / "state.sqlite3")
  app = SteeringApp(store)
  original_dispatch = app.dispatch
  send_ready = threading.Event()
  release_send = threading.Event()
  hold_pages = threading.Event()
  release_pages = threading.Event()
  result = {}

  def delayed_dispatch(method, url, body=None):
    if method == "GET" and url.startswith("/messages?") and hold_pages.is_set():
      release_pages.wait(10)
    response = original_dispatch(method, url, body)
    if method == "POST" and url == "/messages":
      result.update(response[1])
      send_ready.set()
      release_send.wait(10)
    return response

  app.dispatch = delayed_dispatch
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
        page.set_default_timeout(10000)
        page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
        page.locator("#msg").fill("A message with a quick reply")
        page.locator("#send").click()
        assert send_ready.wait(5)
        msg_id = result["message"]["id"]
        app.messages.ack(msg_id, "Acknowledged immediately")
        reply = page.locator(f'.message[data-msg-id="{msg_id}"] .reply').get_by_text(
          "Acknowledged immediately"
        )
        reply.wait_for()
        hold_pages.set()
        release_send.set()
        page.locator("#send").wait_for(state="visible")
        page.wait_for_function("() => !document.querySelector('#send').disabled")
        assert reply.is_visible()
      finally:
        release_send.set()
        release_pages.set()
        browser.close()
  finally:
    release_send.set()
    release_pages.set()
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)
    store.close()


@pytest.mark.skipif(
  not os.environ.get("ARENA_STEERING_CHROMIUM"),
  reason="Set ARENA_STEERING_CHROMIUM to run the browser regression",
)
@pytest.mark.parametrize("transport", ["websocket", "poll"])
def test_external_ack_appears_live(tmp_path: Path, transport: str) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  path = tmp_path / "state.sqlite3"
  server_store = SqliteStore(path)
  writer_store = SqliteStore(path)
  app = SteeringApp(server_store)
  writer = SteeringApp(writer_store)
  app.messages.send_message("Awaiting reply", msg_id="ab0123")
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
        query = "?transport=poll" if transport == "poll" else ""
        page.goto(f"http://127.0.0.1:{server.server_port}/{query}")
        card = page.locator('[data-msg-id="ab0123"]').first
        card.wait_for(state="visible")
        writer.messages.ack("ab0123", "Live acknowledgement")
        card.locator(".reply").get_by_text("Live acknowledgement").wait_for(
          timeout=10000
        )
      finally:
        browser.close()
  finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)
    writer_store.close()
    server_store.close()


@pytest.mark.skipif(
  not os.environ.get("ARENA_STEERING_CHROMIUM"),
  reason="Set ARENA_STEERING_CHROMIUM to run the browser regression",
)
@pytest.mark.parametrize("motion", ["no-preference", "reduce"])
def test_message_reference_highlights_bubble_not_row(
  tmp_path: Path, motion: str
) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore()
  app = SteeringApp(store)
  app.messages.send_message("Target message", msg_id="aa0001")
  app.messages.send_message("Child message", msg_id="aa0002", parent_ids=["aa0001"])
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
        page.emulate_media(reduced_motion=motion)
        page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
        row = page.locator('.message[data-msg-id="aa0001"]')
        bubble = row.locator(".message-bubble")
        bubble.wait_for()
        normal = bubble.evaluate("el => getComputedStyle(el).backgroundColor")
        row_color = row.evaluate("el => getComputedStyle(el).backgroundColor")
        page.locator(
          '.message[data-msg-id="aa0002"] .reply-parent-chip[data-reference-id="aa0001"]'
        ).click()
        row.locator(".message-bubble").wait_for()
        page.wait_for_function(
          """normal => getComputedStyle(document.querySelector(
            '.message[data-msg-id="aa0001"] .message-bubble'
          )).backgroundColor !== normal""",
          arg=normal,
        )
        assert row.evaluate("el => getComputedStyle(el).backgroundColor") == row_color
        duration = bubble.evaluate("el => getComputedStyle(el).transitionDuration")
        assert (duration != "0s") == (motion == "no-preference")
        page.screenshot(path=str(tmp_path / f"bubble-transition-{motion}.png"))
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
def test_hidden_messages_are_cached_across_toggles(tmp_path: Path) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore()
  app = SteeringApp(store)
  app.messages.send_message("Visible", msg_id="aa0001")
  app.messages.send_message("Hidden", msg_id="aa0002", hidden=True)
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
        calls: list[str] = []
        page.on(
          "request",
          lambda request: (
            calls.append(request.url) if "/messages?" in request.url else None
          ),
        )
        page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
        page.locator('.message[data-msg-id="aa0001"]').wait_for()
        toggle = page.locator("#quiet-msgs")
        toggle.click()
        hidden = page.locator('.message[data-msg-id="aa0002"]')
        hidden.wait_for()
        calls.clear()
        toggle.click()
        hidden.wait_for(state="detached")
        toggle.click()
        hidden.wait_for()
        assert calls == []
        toggle.click()
        hidden.wait_for(state="detached")
        with page.expect_response(lambda response: "/messages?" in response.url):
          pass
        calls.clear()
        toggle.click()
        hidden.wait_for()
        assert calls == []
        toggle.click()
        hidden.wait_for(state="detached")
        app.messages.send_message("New hidden", msg_id="aa0003", hidden=True)
        with page.expect_request(lambda request: "/messages?" in request.url):
          pass
        toggle.click()
        page.locator('.message[data-msg-id="aa0003"]').wait_for()
        page.screenshot(path=str(tmp_path / "hidden-cache.png"))
        toggle.click()
        page.locator('.message[data-msg-id="aa0003"]').wait_for(state="detached")
        page.evaluate("""() => {
          const original = window.fetch;
          window.holdNextMessage = true;
          window.fetch = async (url, options) => {
            if (window.holdNextMessage && String(url).startsWith('/messages?')) {
              window.holdNextMessage = false;
              await new Promise(resolve => { window.releaseMessage = resolve; });
            }
            return original(url, options);
          };
        }""")
        app.messages.send_message("Racing hidden", msg_id="aa0004", hidden=True)
        page.wait_for_function("() => typeof window.releaseMessage === 'function'")
        toggle.click()
        page.locator('.message[data-msg-id="aa0004"]').wait_for()
        page.evaluate("() => window.releaseMessage()")
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
def test_hidden_toggle_loads_visible_history_when_page_is_all_hidden() -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore()
  app = SteeringApp(store)
  app.messages.send_message("Older visible", msg_id="aa0001")
  for index in range(40):
    app.messages.send_message(f"Hidden {index}", msg_id=f"bb{index:04x}", hidden=True)
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
        page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
        page.locator('.message[data-msg-id="aa0001"]').wait_for()
        toggle = page.locator("#quiet-msgs")
        toggle.click()
        page.locator('.message[data-msg-id="bb0027"]').wait_for()
        toggle.click()
        page.locator('.message[data-msg-id="aa0001"]').wait_for()
      finally:
        browser.close()
  finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)
    store.close()
