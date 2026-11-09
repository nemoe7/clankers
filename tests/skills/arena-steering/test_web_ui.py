"""Steering browser regression tests."""

from __future__ import annotations

import io
import json
import os
import re
import runpy
import subprocess
import threading
import time
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
)
from arena_steering.services import BIBLE_READ, with_bible_read
from arena_steering.store import SqliteStore

ROOT = Path(__file__).resolve().parents[3]


SKILL_DIR = ROOT / "skills" / "arena-steering"


ASSETS_DIR = SKILL_DIR / "assets"


DEMO_PATH = ROOT / "maintenance" / "demo-arena-steer.py"


DEMO = runpy.run_path(str(DEMO_PATH))


SCROLLSPY_ZONES_SVG = DEMO["SCROLLSPY_ZONES_SVG"]


TOKENS_SWATCH_SVG = DEMO["TOKENS_SWATCH_SVG"]


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
  "icons.js",
  "messages-view.js",
  "markdown.js",
  "modal.js",
  "reports-view.js",
  "state.js",
  "tasks-view.js",
  "timestamps.js",
)


SHARED_SCROLL_JUMP_CLASS = "scroll-jump-btn"


SHARED_QUIET_BTN_CLASS = "quiet-btn"


SHARED_PARENT_CHIP_FN = "renderParentChip"


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


STATIC_ASSET_PREFIX = "/static/assets/"


STATIC_STYLE_HREF = 'href="/static/assets/style.css"'


STATIC_APP_SRC = 'src="/static/assets/app.js"'


ROOT_STYLE_HREF = 'href="/style.css"'


MARK_RULE = "mark {"


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
@pytest.mark.parametrize("failures_before_ok", [3, 4])
def test_unconfirmed_write_uses_html_dialog(
  tmp_path: Path, failures_before_ok: int
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
        page = browser.new_page(viewport={"width": 411, "height": 799})
        writes: list[dict[str, object]] = []

        def handle_skip(route: object) -> None:
          writes.append(route.request.post_data_json)
          if len(writes) <= failures_before_ok:
            route.fulfill(
              status=503,
              content_type="application/json",
              body='{"error":"offline"}',
            )
          else:
            route.fulfill(
              status=200,
              content_type="application/json",
              body='{"skip_poll":true}',
            )

        page.route("**/poll/skip", handle_skip)
        native = []
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("dialog", lambda dialog: (native.append(dialog.type), dialog.dismiss()))
        page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
        page.locator("#skip-poll").click()
        expected_state = "good" if failures_before_ok == 3 else "bad"
        page.wait_for_function(
          "expected => { const btn = document.querySelector('#skip-poll'); "
          "return btn && !btn.disabled && btn.getAttribute('data-state') === expected; }",
          arg=expected_state,
        )
        assert len(writes) == 4
        assert len({item["_request_id"] for item in writes}) == 1
        assert page.locator("#modal-shell[open]").count() == 0
        if failures_before_ok == 4:
          with page.expect_response("**/poll/skip"):
            page.locator("#skip-poll").click()
          assert len(writes) == 5
          assert writes[4]["_request_id"] != writes[0]["_request_id"]
          assert page.locator("#modal-shell[open]").count() == 0
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
  answers = survey.template()
  answers[2]["answer"].update(
    {
      "first_name": "Ada",
      "last_name": "Lovelace",
      "organization": "Example & <Sons>",
      "role": "Survey operator",
    }
  )
  answers[2]["confidence"] = 0.35
  app.messages.submit_survey(json.dumps(answers))
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
        page.locator(".survey-cap-pill").first.wait_for()
        assert page.locator(".survey-cap-pill .survey-answer-tooltip").count() == 0
        assert page.locator(".survey-cap-pill").first.get_attribute("tabindex") is None
        assert page.locator("table.survey-results th").all_inner_texts() == [
          "ID",
          "Confidence",
        ]
        assert page.locator(".survey-field-chip").count() == 0
        page.locator(".survey-id-trigger").first.scroll_into_view_if_needed()
        page.locator(".survey-id-trigger").first.hover()
        first_tip = page.locator(".survey-id-wrap").first.locator(
          ".survey-answer-tooltip"
        )
        first_tip.wait_for(state="visible")
        assert first_tip.locator(".survey-answer-val").all_inner_texts() == [
          "Ada",
          "Lovelace",
          "Example & <Sons>",
          "Survey operator",
        ]
        tip_bg = first_tip.evaluate("el => getComputedStyle(el).backgroundColor")
        assert tip_bg not in ("rgba(0, 0, 0, 0)", "transparent", "rgb(255, 255, 255)")
        assert first_tip.evaluate("el => getComputedStyle(el).animationName") in (
          "tooltip-from-above",
          "tooltip-from-below",
        )
        page.emulate_media(reduced_motion="reduce")
        assert first_tip.evaluate("el => getComputedStyle(el).animationName") == "none"
        val_color = first_tip.locator(".survey-answer-val").first.evaluate(
          "el => getComputedStyle(el).color"
        )
        assert val_color not in ("rgb(24, 24, 24)", tip_bg)
        sizes = page.evaluate("""() => {
          const rect = selector => document.querySelector(selector).getBoundingClientRect();
          const footer = rect('#modal-actions');
          const body = document.querySelector('#modal-body');
          return {
            footerTop: footer.top, footerBottom: footer.bottom,
            bodyHeight: body.clientHeight, contentHeight: body.scrollHeight
          };
        }""")
        assert sizes["footerTop"] >= 0
        assert sizes["footerBottom"] <= height
        if height < 400:
          assert sizes["contentHeight"] > sizes["bodyHeight"]
        page.locator(".survey-id-trigger").last.scroll_into_view_if_needed()
        page.mouse.move(0, 0)
        page.locator(".survey-id-trigger").last.hover()
        page.locator(".survey-id-wrap:hover .survey-answer-tooltip").wait_for(
          state="visible"
        )
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
      encoding="utf-8",
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

  icons_js = (ASSETS_DIR / "icons.js").read_text(encoding="utf-8")
  assert "lucide lucide-${name}" in icons_js
  assert LUCIDE_CHEVRON_DOWN_ICON.removeprefix("lucide-") in icons_js
  assert SELECT_CHEVRON_CLASS in icons_js
  assert LUCIDE_COPY_ICON.removeprefix("lucide-") in icons_js
  assert LUCIDE_CLOSE_ICON.removeprefix("lucide-") in icons_js
  assert LUCIDE_SEND_ICON.removeprefix("lucide-") in icons_js

  tasks_js = (ASSETS_DIR / "tasks-view.js").read_text(encoding="utf-8")
  assert LUCIDE_LOCK_ICON not in tasks_js
  assert "Report: " in tasks_js
  assert "Needs: " in tasks_js
  assert "CHEVRON_SELECT_SVG" in tasks_js

  reports_js = (ASSETS_DIR / "reports-view.js").read_text(encoding="utf-8")
  assert CUSTOM_OPTION_MARKER in reports_js
  assert "COPY_SVG" in reports_js
  assert "DISMISS_SVG" in reports_js
  assert "SEND_PLANE_SVG" in reports_js
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
  assert 'dropShadow: "none"' in theme

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
      parity = page.evaluate("""() => {
        const thumbDiag = document.querySelector('#report .mermaid-diagram');
        const thumbSvg = document.querySelector('#report .mermaid-svg');
        const modalSvg = document.querySelector('#image-modal-stage > svg');
        const thumbText = thumbSvg.querySelector('tspan, text');
        const modalText = modalSvg.querySelector('tspan, text');
        const thumbRect = thumbSvg.querySelector('.node rect');
        const modalRect = modalSvg.querySelector('.node rect');
        const allIds = [...document.querySelectorAll('[id]')].map(el => el.id);
        return {
          codeBg: getComputedStyle(thumbDiag).backgroundColor,
          modalBg: getComputedStyle(modalSvg).backgroundColor,
          thumbFontSize: getComputedStyle(thumbText).fontSize,
          modalFontSize: getComputedStyle(modalText).fontSize,
          thumbFill: getComputedStyle(thumbRect).fill,
          modalFill: getComputedStyle(modalRect).fill,
          thumbStroke: getComputedStyle(thumbRect).stroke,
          modalStroke: getComputedStyle(modalRect).stroke,
          thumbFilter: getComputedStyle(thumbRect).filter,
          modalFilter: getComputedStyle(modalRect).filter,
          hasFlowchartClass: modalSvg.classList.contains('flowchart'),
          duplicateIdCount: allIds.length - new Set(allIds).size,
        };
      }""")
      assert parity["modalBg"] == parity["codeBg"]
      assert parity["modalBg"] != "rgba(0, 0, 0, 0)"
      assert parity["modalFontSize"] == parity["thumbFontSize"]
      assert parity["modalFill"] == parity["thumbFill"]
      assert parity["modalStroke"] == parity["thumbStroke"]
      assert parity["thumbFilter"] == "none"
      assert parity["modalFilter"] == "none"
      assert parity["hasFlowchartClass"] is True
      assert parity["duplicateIdCount"] == 0
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
      page.locator(".survey-id-trigger").first.wait_for()
      page.wait_for_function("typeof window.releaseSurvey === 'function'")
      page.locator(".survey-id-trigger").first.focus()
      focused = page.locator(".survey-id-trigger").first.element_handle()
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


def test_timestamp_timer_tracks_viewport_and_cleans_up() -> None:
  script = r"""
import assert from 'node:assert/strict';
import { mountRelativeTimers, relativeTime } from './skills/arena-steering/assets/timestamps.js';
const now = Date.now();
const stamp = new Date(now - 2 * 60 * 60 * 1000).toISOString();
const listeners = new Set();
const timers = new Set();
const media = {
  matches: true,
  addEventListener(type, callback) { assert.equal(type, 'change'); listeners.add(callback); },
  removeEventListener(type, callback) { assert.equal(type, 'change'); listeners.delete(callback); },
};
globalThis.window = {
  matchMedia: () => media,
  setTimeout(callback) { timers.add(callback); return callback; },
  clearTimeout(callback) { timers.delete(callback); },
};
const attrs = { 'data-timestamp': stamp, 'data-compact': 'true', 'data-state-label': 'Status: acked' };
const node = {
  textContent: '',
  getAttribute(name) { return attrs[name] || null; },
  setAttribute(name, value) { attrs[name] = value; },
};
const stop = mountRelativeTimers({ querySelectorAll: () => [node] });
for (const compact of [true, false, true]) {
  media.matches = compact;
  for (const callback of listeners) callback();
  const expected = relativeTime(stamp, { compact, now });
  assert.equal(node.textContent, expected);
  assert.equal(attrs['aria-label'], `${attrs['data-state-label']}, ${expected}`);
  assert.equal(timers.size, 1);
}
assert.equal(listeners.size, 1);
stop();
assert.equal(timers.size, 0);
assert.equal(listeners.size, 0);
"""
  result = subprocess.run(
    ["node", "--experimental-default-type=module", "--input-type=module", "-e", script],
    cwd=ROOT,
    capture_output=True,
    text=True,
    encoding="utf-8",
    check=False,
  )
  assert result.returncode == 0, result.stderr


@pytest.mark.skipif(
  not os.environ.get("ARENA_STEERING_CHROMIUM"),
  reason="Set ARENA_STEERING_CHROMIUM to run the browser regression",
)
def test_relative_timestamps_follow_mobile_and_desktop_widths(tmp_path: Path) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore()
  app = SteeringApp(store)
  message = app.messages.send_message("Responsive timestamp", blocking=False)
  message.modified_at = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
  store.save_message(message)
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
        stamp = page.locator(f'[data-msg-id="{message.id}"] .receipt-status')
        stamp.wait_for()
        for width in (1200, 390, 1200):
          page.set_viewport_size({"width": width, "height": 700})
          expected = stamp.evaluate("""async node => {
            const { relativeTime } = await import('/static/assets/timestamps.js');
            const relative = relativeTime(node.dataset.timestamp, {
              compact: matchMedia('(max-width: 60em)').matches,
            });
            return node.dataset.prefix ? `${node.dataset.prefix} ${relative}` : relative;
          }""")
          playwright.expect(stamp).to_have_text(expected)
          assert stamp.get_attribute("title") is None
          page.screenshot(path=str(tmp_path / f"responsive-timestamp-{width}.png"))
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
    encoding="utf-8",
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
        tip.wait_for(state="visible")
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
        button.evaluate("el => el.blur()")
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
    assert violation.body.splitlines()[:3] == [
      "VIOLATION: Bash",
      "Cited: " + flag["msg"],
      "Book: ARENA.md",
    ]
    assert BIBLE_READ == (
      "If cannot recall clause from memory, use read_file for {paths} and answer the `steer survey`"
    )
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
    assert task_flag.body.splitlines()[0] == "VIOLATION: Current task"
    app.dispatch(
      "POST", f"/messages/{task_flag.id}/ack", {"markdown": "Read the clause."}
    )
    assert app.dispatch("GET", "/health")[1]["agent_interrupt_pending"] is False

    status, result = app.dispatch(
      "POST", "/agent-interrupt", {"tab": "tasks", "reason": "missing-details"}
    )
    assert status == HTTPStatus.OK and result["agent_interrupt_pending"] is True
    missing_details_flag = next(
      message
      for message in app.messages.list_messages()
      if message.violation_type == "missing-details"
    )
    assert (
      missing_details_flag.body.splitlines()[0] == "VIOLATION: Task missing details"
    )
    assert not any(
      line.startswith(("Cited:", "Book:"))
      for line in missing_details_flag.body.splitlines()
    )
    app.messages.ack(missing_details_flag.id, "Read the clause.")

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
    assert report_flag.body.splitlines()[0] == "VIOLATION: Format"
    status, _ = app.dispatch(
      "POST",
      "/agent-interrupt",
      {"tab": "reports", "reason": "format-violation", "report_id": "missing"},
    )
    assert status == HTTPStatus.BAD_REQUEST
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
        page.locator('label[for="violation-msg"]').click()
        assert page.locator("#violation-msg").evaluate(
          "element => element === document.activeElement && !element.required"
        )
        page.locator("#violation-msg").fill(cited_reason)
        box = form.bounding_box()
        assert box and box["x"] >= 0 and box["x"] + box["width"] <= width
        page.screenshot(path=str(tmp_path / f"violation-form-{width}.png"))

        interrupt_ids: list[str] = []

        def fail_interrupt(route: object) -> None:
          interrupt_ids.append(route.request.post_data_json["_request_id"])
          route.fulfill(
            status=503, body='{"error":"Try again"}', content_type="application/json"
          )

        page.route("**/agent-interrupt", fail_interrupt, times=4)
        with page.expect_request("**/agent-interrupt") as sent:
          page.locator("#violation-submit").click()
        assert sent.value.post_data_json["msg"] == cited_reason
        assert "note" not in sent.value.post_data_json
        page.locator("#violation-error").wait_for(state="visible", timeout=5000)
        assert len(interrupt_ids) == 4 and len(set(interrupt_ids)) == 1
        assert form.is_visible()
        assert button.get_attribute("aria-pressed") == "false"
        assert page.locator("#violation-msg").input_value() == cited_reason

        page.route("**/agent-interrupt", fail_interrupt, times=3)
        with page.expect_response("**/agent-interrupt"):
          page.locator("#violation-submit").click()
        page.locator("#modal-shell").wait_for(state="hidden")
        page.wait_for_function(
          "document.querySelector('#agent-interrupt').getAttribute('aria-pressed') === 'true'"
        )
        assert len(interrupt_ids) == 7 and len(set(interrupt_ids[4:])) == 1
        assert interrupt_ids[4] != interrupt_ids[0]
        violation = app.messages.pending_violation()
        assert violation is not None and violation.violation_clause_file == "ARENA.md"
        assert cited_reason in violation.body
        page.screenshot(path=str(tmp_path / f"violation-pending-{width}.png"))

        page.route("**/agent-interrupt", fail_interrupt, times=4)
        button.click()
        page.locator("#violation-status").wait_for(state="visible", timeout=5000)
        assert button.get_attribute("aria-pressed") == "true"
        assert app.messages.pending_violation() is not None
        with page.expect_response("**/agent-interrupt"):
          button.click()
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
        window.interruptIds = [];
        let held = false;
        window.fetch = async (...args) => {
          if (String(args[0]) === '/agent-interrupt' && args[1]?.method === 'POST') {
            window.interruptIds.push(JSON.parse(args[1].body || '{}')._request_id);
            if (!held) {
              held = true;
              await new Promise(resolve => { window.releaseFlag = resolve; });
            }
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
        assert page.evaluate(
          "window.interruptIds.length === 4 && new Set(window.interruptIds).size === 1"
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


@pytest.mark.skipif(
  not os.environ.get("ARENA_STEERING_CHROMIUM"),
  reason="Set ARENA_STEERING_CHROMIUM to run the browser regression",
)
def test_touch_tap_overlay_is_disabled_without_hiding_keyboard_focus(
  tmp_path: Path,
) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore(tmp_path / "state.sqlite3")
  server = create_http_server(SteeringApp(store), host="0.0.0.0", port=0)
  thread = threading.Thread(target=server.serve_forever, daemon=True)
  thread.start()
  try:
    with playwright.sync_playwright() as runner:
      browser = runner.chromium.launch(
        executable_path=os.environ["ARENA_STEERING_CHROMIUM"], args=["--no-sandbox"]
      )
      try:
        page = browser.new_page(viewport={"width": 411, "height": 799}, has_touch=True)
        page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
        page.evaluate("""() => {
          const box = document.createElement('div');
          box.innerHTML = '<button id="tap-probe">Button</button><a href="#">Link</a><input>';
          document.body.append(box);
        }""")
        colors = page.evaluate("""() => [...document.querySelectorAll('#tap-probe, #tap-probe ~ a, #tap-probe ~ input')]
          .map(el => getComputedStyle(el).webkitTapHighlightColor)""")
        assert colors == ["rgba(0, 0, 0, 0)"] * 3
        page.keyboard.press("Tab")
        page.locator("#tap-probe").focus()
        assert page.locator("#tap-probe").evaluate(
          "el => el.matches(':focus-visible') && parseFloat(getComputedStyle(el).outlineWidth) > 0"
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
def test_tooltip_hover_delay_switching_focus_and_close(tmp_path: Path) -> None:
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
        executable_path=os.environ["ARENA_STEERING_CHROMIUM"], args=["--no-sandbox"]
      )
      try:
        page = browser.new_page(viewport={"width": 1200, "height": 800})
        page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
        page.evaluate("""() => {
          for (const [id, left] of [['first', 100], ['second', 250]]) {
            const button = document.createElement('button');
            button.id = id; button.title = id;
            button.textContent = id;
            button.style.cssText = `position:fixed;top:200px;left:${left}px;z-index:1000`;
            document.body.append(button);
          }
        }""")
        first = page.locator("#first")
        first.hover()
        page.wait_for_timeout(200)
        assert page.locator("#arena-title-tooltip").count() == 0
        page.mouse.move(600, 700)
        page.wait_for_timeout(450)
        assert page.locator("#arena-title-tooltip").count() == 0
        first.hover()
        page.wait_for_timeout(200)
        assert page.locator("#arena-title-tooltip").count() == 0

        def wait_for_title_tooltip(text: str) -> None:
          page.wait_for_function(
            "expected => document.getElementById('arena-title-tooltip')?.textContent === expected",
            arg=text,
            timeout=1500,
          )

        wait_for_title_tooltip("first")
        page.locator("#second").hover()
        wait_for_title_tooltip("second")
        first.hover()
        wait_for_title_tooltip("first")
        page.wait_for_timeout(200)
        page.mouse.move(600, 700)
        closing = page.locator(".arena-tooltip.tooltip-closing")
        assert closing.count() == 1
        assert (
          closing.evaluate("el => getComputedStyle(el).animationDirection") == "reverse"
        )
        assert closing.evaluate(
          "el => el.getAnimations().some(animation => animation.playState === 'running')"
        )
        page.locator("#second").hover()
        wait_for_title_tooltip("second")
        page.mouse.move(600, 700)
        page.wait_for_timeout(650)
        first.hover()
        page.wait_for_timeout(200)
        assert page.locator("#arena-title-tooltip").count() == 0
        page.mouse.move(600, 700)
        page.keyboard.press("Tab")
        first.focus()
        wait_for_title_tooltip("first")
        page.keyboard.press("Escape")
        page.locator("#survey-open").click()
        trigger = page.locator(".survey-id-trigger").first
        page.mouse.move(600, 700)
        page.wait_for_timeout(650)
        trigger.hover()
        tip = page.locator(".survey-id-wrap").first.locator(".survey-answer-tooltip")
        page.wait_for_timeout(200)
        assert tip.is_hidden()
        tip.wait_for(state="visible", timeout=1000)
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
def test_shared_ui_helpers_icons_and_classes(tmp_path: Path) -> None:
  icons_js = (ASSETS_DIR / "icons.js").read_text(encoding="utf-8")
  assert "lucideSvg" in icons_js
  for js_name in (
    "app.js",
    "markdown.js",
    "messages-view.js",
    "reports-view.js",
    "tasks-view.js",
  ):
    src = (ASSETS_DIR / js_name).read_text(encoding="utf-8")
    assert "./icons.js" in src
    assert '<svg class="lucide' not in src

  dom_js = (ASSETS_DIR / "dom.js").read_text(encoding="utf-8")
  assert f"export function {SHARED_PARENT_CHIP_FN}" in dom_js
  for js_name in ("messages-view.js", "reports-view.js"):
    src = (ASSETS_DIR / js_name).read_text(encoding="utf-8")
    assert SHARED_PARENT_CHIP_FN in src

  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore(tmp_path / "state.sqlite3")
  app = SteeringApp(store)
  first = app.messages.send_message("Initial parent message")
  second = app.messages.send_message(
    "Follow-up with\n\n```js\nconsole.log(1);\n```",
    parent_refs=[{"type": "message", "id": first.id}],
  )
  app.messages.ack(second.id, "Acked reply")
  report_md = (
    "# Shared UI Check\n\n"
    "## Section One\n\n"
    '<!-- question {"id":"pick-one","label":"Pick one"} -->\n\n'
    "Which option should apply?\n"
    '- (x) Use shared classes <!-- option {"label":"Shared"} -->\n'
    '- ( ) Keep separate classes <!-- option {"label":"Separate"} -->\n'
  )
  app.reports.publish_report("shared-ui-check", "Shared UI Check", report_md)
  app.tasks.create_task(
    "linked-ui-task",
    "Linked UI task",
    size=3,
    details=["Verify shared parent chip"],
    links={"msg_ids": [second.id], "report_ids": ["shared-ui-check"]},
  )

  server = create_http_server(app, host="0.0.0.0", port=0)
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
        page.locator(f'.message[data-msg-id="{second.id}"]').wait_for()

        # Message parent chip renders left of message ID via shared helper.
        positions = page.locator(
          f'.message[data-msg-id="{second.id}"] .message-heading'
        ).evaluate(
          """heading => {
            const parent = heading.querySelector('.reply-parent-chip').getBoundingClientRect();
            const idBtn = heading.querySelector('.parent-id-button').getBoundingClientRect();
            return {parentRight: parent.right, idLeft: idBtn.left};
          }"""
        )
        assert positions["parentRight"] <= positions["idLeft"] + 1

        id_button = page.locator(
          f'.message[data-msg-id="{second.id}"] .parent-id-button'
        )
        bubble = page.locator(f'.message[data-msg-id="{second.id}"] .message-bubble')
        bubble_radius = bubble.evaluate("el => getComputedStyle(el).borderRadius")
        idle = id_button.evaluate("""el => {
          const style = getComputedStyle(el);
          return {borderRadius: style.borderRadius, background: style.backgroundColor};
        }""")
        assert idle["borderRadius"] == bubble_radius, (idle, bubble_radius)
        page.screenshot(path=str(tmp_path / "parent-id-chip-idle.png"))

        id_button.hover()
        page.wait_for_function(
          """([selector, background]) =>
            getComputedStyle(document.querySelector(selector)).backgroundColor !== background
          """,
          arg=[
            f'.message[data-msg-id="{second.id}"] .parent-id-button',
            idle["background"],
          ],
        )
        hovered = id_button.evaluate("""el => {
          const style = getComputedStyle(el);
          return {borderRadius: style.borderRadius, background: style.backgroundColor};
        }""")
        assert hovered["borderRadius"] == idle["borderRadius"] == bubble_radius, (
          idle,
          hovered,
          bubble_radius,
        )
        assert hovered["background"] != idle["background"], (idle, hovered)
        page.screenshot(path=str(tmp_path / "parent-id-chip-hover.png"))

        for selector in ("#log-edited", "#log-newest"):
          assert page.locator(selector).evaluate(
            f"el => el.classList.contains('{SHARED_SCROLL_JUMP_CLASS}')"
          )

        for selector in (
          "#blocked-bash-open",
          "#agent-interrupt",
          "#survey-open",
          "#skip-poll",
          "#quiet-msgs",
          "#attach-file",
          "#preview-msg",
          "#send",
          ".copy-code",
        ):
          assert page.locator(selector).first.evaluate(
            f"el => el.classList.contains('{SHARED_QUIET_BTN_CLASS}')"
          )

        page.locator("#tab-reports").click()
        page.locator("#report-scroll-top").wait_for(state="attached")
        assert page.locator("#report-scroll-top").evaluate(
          f"el => el.classList.contains('{SHARED_SCROLL_JUMP_CLASS}')"
        )
        assert (
          page.locator(".report-task-links .reply-parent-chip").get_attribute(
            "data-reference-id"
          )
          == "linked-ui-task"
        )
        for selector in (
          "#report-picker-toggle",
          "#copy-report-btn",
          "#dismiss-report-btn",
          ".report-toc-link",
          ".report-picker-link",
        ):
          assert page.locator(selector).first.evaluate(
            f"el => el.classList.contains('{SHARED_QUIET_BTN_CLASS}')"
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
def test_v2_nuu_recipe_conformance_surfaces(tmp_path: Path) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  index_html = (ASSETS_DIR / "index.html").read_text(encoding="utf-8")
  assert index_html.count("<!-- Lucide Icons - ISC License -->") >= 2

  store = SqliteStore(tmp_path / "state.sqlite3")
  app = SteeringApp(store, repo_name="V2 Nuu recipe conformance")
  app.messages.send_message("Alpha message", msg_id="aa0001", blocking=False)
  app.messages.send_message("Beta needle message", msg_id="bb0002", blocking=False)
  app.tasks.create_task(
    "alpha-code-task",
    "Alpha code task",
    size=3,
    types=["code"],
    details=["Code detail"],
  )
  app.tasks.create_task(
    "beta-docs-task",
    "Beta docs task",
    size=2,
    types=["docs"],
    details=["Docs detail"],
  )
  app.reports.publish_report("one", "First Report", "# First Report\n\nBody one.\n")
  app.reports.publish_report("two", "Second Report", "# Second Report\n\nBody two.\n")

  server = create_http_server(app, host="0.0.0.0", port=0)
  thread = threading.Thread(target=server.serve_forever, daemon=True)
  thread.start()
  try:
    with playwright.sync_playwright() as runner:
      browser = runner.chromium.launch(
        executable_path=os.environ["ARENA_STEERING_CHROMIUM"], args=["--no-sandbox"]
      )
      try:
        page = browser.new_page(viewport={"width": 960, "height": 760})
        page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
        page.locator('#connection-dot[data-state="ok"]').wait_for()

        # 1. Modal close button uses a 16x16 Lucide SVG instead of text x.
        assert "×" not in page.locator("#image-modal-close").inner_text()
        assert page.locator("#image-modal-close svg.lucide-x").count() == 1

        # 2. Relative timestamps render regular proportional numerals without tooltips.
        stamp_info = page.locator("#history .message time[datetime]").first.evaluate(
          """el => {
            const cs = getComputedStyle(el);
            return {
              title: el.getAttribute('title'),
              tabular: cs.fontVariantNumeric,
              family: cs.fontFamily.toLowerCase(),
            };
          }"""
        )
        assert stamp_info["title"] is None, stamp_info
        assert stamp_info["tabular"] == "normal", stamp_info
        assert "mono" not in stamp_info["family"], stamp_info

        # 3. Scroll-edge-fade tokens match 24px / 32px stops.
        fade_tokens = page.evaluate(
          """() => {
            const cs = getComputedStyle(document.documentElement);
            return {
              fade: cs.getPropertyValue('--edge-fade').trim(),
              ramp: cs.getPropertyValue('--edge-ramp').trim(),
            };
          }"""
        )
        assert fade_tokens == {"fade": "24px", "ramp": "32px"}, fade_tokens

        # 4. Connection live dot is 8x8 px and aria-hidden inside a 1lh slot.
        dot_info = page.evaluate(
          """() => {
            const dot = document.querySelector('#connection-dot');
            const btn = document.querySelector('#survey-open');
            const dRect = dot.getBoundingClientRect();
            const bRect = btn.getBoundingClientRect();
            const lh = parseFloat(getComputedStyle(btn).lineHeight);
            return {
              w: dRect.width,
              h: dRect.height,
              hidden: dot.getAttribute('aria-hidden'),
              role: dot.getAttribute('role'),
              btnH: bRect.height,
              lh,
            };
          }"""
        )
        assert dot_info["w"] == 8 and dot_info["h"] == 8, dot_info
        assert dot_info["hidden"] == "true" and dot_info["role"] is None, dot_info
        assert abs(dot_info["btnH"] - dot_info["lh"]) <= 1.0, dot_info

        # 5. Reports region toggles aria-busy while fetching report content.
        page.evaluate(
          """() => {
            const orig = window.fetch.bind(window);
            window.fetch = async (...args) => {
              if (String(args[0]).includes('/reports/two')) {
                await new Promise(resolve => { window.releaseReportTwo = resolve; });
              }
              return orig(...args);
            };
          }"""
        )
        page.locator("#tab-reports").click()
        page.locator('.report-picker-link[data-report-id="two"]').wait_for()
        page.locator('.report-picker-link[data-report-id="two"]').click()
        page.wait_for_function("typeof window.releaseReportTwo === 'function'")
        assert page.locator("#view-reports").get_attribute("aria-busy") == "true"
        page.evaluate("window.releaseReportTwo()")
        page.wait_for_function(
          "document.querySelector('#view-reports').getAttribute('aria-busy') === 'false'"
        )

        # 6. Message search and task filters persist across page reloads.
        page.locator("#tab-messages").click()
        page.locator("#log-search").fill("Beta needle")
        page.wait_for_function(
          "document.querySelectorAll('#history .message').length === 1"
        )
        page.locator("#tab-tasks").click()
        page.locator("#task-search").fill("Beta")
        page.locator("#task-type-filter").select_option("docs")
        assert page.locator(".tasks-layout .task").count() == 1

        page.reload()
        page.locator("#task-search").wait_for()
        assert page.locator("#task-search").input_value() == "Beta"
        assert page.locator("#task-type-filter").input_value() == "docs"
        assert page.locator(".tasks-layout .task").count() == 1

        page.locator("#tab-messages").click()
        page.locator("#log-search").wait_for()
        assert page.locator("#log-search").input_value() == "Beta needle"
        page.wait_for_function(
          "document.querySelectorAll('#history .message').length === 1"
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
def test_inline_code_wraps_without_changing_blocks_or_tables(tmp_path: Path) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore(tmp_path / "state.sqlite3")
  app = SteeringApp(store, repo_name="Inline code wrapping")
  token = "long_path_segment/" * 20
  markdown = f"`{token}`\n\n```text\n{token}\n```\n\n| Value |\n| --- |\n| Cell |\n"
  app.messages.send_message(markdown, msg_id="aa0001", blocking=False)
  app.reports.publish_report("code-wrapping", "Code wrapping", markdown)
  server = create_http_server(app, host="0.0.0.0", port=0)
  thread = threading.Thread(target=server.serve_forever, daemon=True)
  thread.start()
  try:
    with playwright.sync_playwright() as runner:
      browser = runner.chromium.launch(
        executable_path=os.environ["ARENA_STEERING_CHROMIUM"],
        args=["--no-sandbox", "--disable-dev-shm-usage"],
      )
      try:
        page = browser.new_page(viewport={"width": 390, "height": 844})
        page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
        for tab, container in (("messages", ".message-text"), ("reports", "#report")):
          if tab == "reports":
            page.locator("#tab-reports").click()
          inline = page.locator(f"{container} p > code").first
          inline.wait_for()
          page.screenshot(path=str(tmp_path / f"inline-code-{tab}.png"))
          metrics = inline.evaluate("""element => {
            const style = getComputedStyle(element);
            const fragments = [...element.getClientRects()];
            return {
              wrap: style.overflowWrap,
              decoration: style.boxDecorationBreak,
              fragmentCount: fragments.length,
              contained: fragments.every(rect => rect.left >= 0 &&
                rect.right <= document.documentElement.clientWidth),
            };
          }""")
          assert metrics["wrap"] == "anywhere", metrics
          assert metrics["decoration"] == "clone", metrics
          assert metrics["fragmentCount"] > 1, metrics
          assert metrics["contained"], metrics
          assert (
            page.locator(f"{container} pre > code").first.evaluate(
              "element => getComputedStyle(element).boxDecorationBreak"
            )
            != "clone"
          )
          assert (
            page.locator(f"{container} td").first.evaluate(
              "element => getComputedStyle(element).overflowWrap"
            )
            == "normal"
          )
      finally:
        browser.close()
  finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)
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
