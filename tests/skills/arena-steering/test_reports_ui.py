"""Steering regression tests."""

from __future__ import annotations

import os
import threading
from pathlib import Path

import pytest
from arena_steering.server import SteeringApp, create_http_server
from arena_steering.store import SqliteStore


@pytest.mark.skipif(
  not os.environ.get("CHROMIUM_BIN"), reason="Set CHROMIUM_BIN for browser tests"
)
@pytest.mark.parametrize("populated", [False, True])
def test_report_states_without_external_audit(tmp_path: Path, populated: bool) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore(tmp_path / "state.sqlite3")
  app = SteeringApp(store)
  if populated:
    body = "# Report\n\n" + ("Enough text to scroll. " * 20 + "\n\n") * 25
    body += '<!-- question {"id":"note","label":"Note"} -->\nNote: ___\n'
    app.reports.publish_report("audit", "Report", body)
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
        for width, height in ((411, 799), (855, 325), (1372, 883)):
          for scheme in ("light", "dark"):
            for motion in ("reduce", "no-preference"):
              page = browser.new_page(
                viewport={"width": width, "height": height},
                color_scheme=scheme,
                reduced_motion=motion,
              )
              page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
              page.locator("#tab-reports").click()
              pane = page.locator("#view-reports")
              if not populated:
                page.locator("#report-status").get_by_text(
                  "No report published yet."
                ).wait_for()
                assert pane.get_attribute("data-scrollable") == "false"
              else:
                page.locator("#report-answer-form").wait_for()
                page.wait_for_function(
                  "document.querySelector('#view-reports').dataset.scrollable === 'true'"
                )
                assert page.locator("#report-scroll-top").is_hidden()
                field = page.locator("#report .field-text-input")
                field.focus()
                assert field.evaluate("el => document.activeElement === el")
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
@pytest.mark.parametrize("transport", ["poll", "ws"])
def test_saved_report_answer_can_be_edited_during_refresh(
  tmp_path: Path, transport: str
) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore(tmp_path / "state.sqlite3")
  app = SteeringApp(store)
  app.reports.publish_report(
    "decision",
    "Decision",
    '<!-- question {"id": "choice", "label": "Choice?"} -->\n'
    "Choice?\n"
    '- (x) A <!-- option {"label": "A"} -->\n'
    '- ( ) B <!-- option {"label": "B"} -->\n',
  )
  app.reports.submit_answer("decision", {"choice": "A"}, answer_id="ab9002")
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
        page.goto(f"http://127.0.0.1:{server.server_port}/?transport={transport}")
        page.locator("#tab-reports").click()
        a = page.locator('#field-choice input[value="A"]')
        b = page.locator('#field-choice input[value="B"]')
        a.wait_for()
        assert a.is_checked()
        b.check()
        status, _ = app.dispatch(
          "POST", "/messages/ab9002/ack", {"markdown": "First refresh"}
        )
        assert status == 200
        page.locator("#report-ack-history").get_by_text("First refresh").wait_for(
          timeout=8000
        )
        assert b.is_checked()
        assert not a.is_checked()
        a.check()
        status, _ = app.dispatch(
          "POST", "/messages/ab9002/ack", {"markdown": "Second refresh"}
        )
        assert status == 200
        page.locator("#report-ack-history").get_by_text("Second refresh").wait_for(
          timeout=8000
        )
        assert a.is_checked()
        assert not b.is_checked()
        b.check()
        page.locator("#report-submit-float").click()
        page.locator("#report-ack-history").get_by_text(
          "Choice?: B", exact=False
        ).wait_for(timeout=8000)
        page.wait_for_function(
          "document.querySelector('#report-submit-float')?.disabled === false"
        )
        assert app.reports.get_report("decision").answers[-1].values == {"choice": "B"}
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
def test_hidden_answer_and_live_report_replies(tmp_path: Path, width: int) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore()
  app = SteeringApp(store, repo_name="Answer storage check")
  app.messages.send_message("Visible note", msg_id="ab9001")
  app.reports.publish_report(
    "decision",
    "Decision",
    (
      '<!-- question {"id": "choice", "label": "Choice?"} -->\n'
      "Choice?\n"
      '- (x) A <!-- option {"label": "A"} -->\n'
      '- ( ) B <!-- option {"label": "B"} -->\n'
    ),
  )
  app.reports.submit_answer("decision", {"choice": "A"}, answer_id="ab9002")
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
        page = browser.new_page(viewport={"width": width, "height": 760})
        errors: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(
          f"http://127.0.0.1:{server.server_port}/?transport=poll",
          wait_until="domcontentloaded",
        )
        page.locator('.message[data-msg-id="ab9001"]').wait_for()
        assert page.locator('.message[data-msg-id="ab9002"]').count() == 0
        page.locator("#quiet-msgs").click()
        answer = page.locator('.message[data-msg-id="ab9002"]')
        answer.wait_for()
        assert "Choice?: A" in answer.inner_text()
        page.locator("#tab-reports").click()
        history = page.locator("#report-ack-history")
        history.get_by_text("Choice?: A", exact=False).wait_for()
        entry = history.locator('.report-answer-entry[data-answer-id="ab9002"]')
        assert entry.locator(".answer.reply").count() == 0
        status, _ = app.dispatch(
          "POST", "/messages/ab9002/ack", {"markdown": "Reviewed answer"}
        )
        assert status == 200
        history.get_by_text("Reviewed answer").wait_for(timeout=8000)
        entry = history.locator('.report-answer-entry[data-answer-id="ab9002"]')
        assert entry.locator(".message-heading .msg-id").inner_text() == "ab9002"
        assert (
          "Choice?: A"
          in entry.locator(".message-bubble > .message-text").first.inner_text()
        )
        assert (
          "Reviewed answer"
          in entry.locator(".message-bubble > .answer.reply").inner_text()
        )
        assert entry.locator(".receipt time").count() == 1
        page.screenshot(path=str(tmp_path / "report-answer.png"))
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
@pytest.mark.parametrize("width", [390, 1200])
def test_report_answer_appears_before_the_network_reply(
  tmp_path: Path, width: int
) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore(tmp_path / "state.sqlite3")
  app = SteeringApp(store)
  app.reports.publish_report(
    "decision",
    "Decision",
    '<!-- question {"id":"choice","label":"Choice?"} -->\n'
    'Choice?\n- (x) A <!-- option {"label":"A"} -->\n'
    '- ( ) B <!-- option {"label":"B"} -->\n',
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
      page = browser.new_page(viewport={"width": width, "height": 800})
      page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
      page.locator("#tab-reports").click()
      page.locator('#field-choice input[value="B"]').check()
      page.evaluate("""() => {
        const original = window.fetch.bind(window);
        window.fetch = async (...args) => {
          if (String(args[0]) === '/reports/decision/answers' && args[1]?.method === 'POST') {
            await new Promise(resolve => { window.releaseAnswer = resolve; });
          }
          return original(...args);
        };
      }""")
      page.locator("#report-submit-float").click()
      page.wait_for_function("typeof window.releaseAnswer === 'function'")
      assert (
        page.locator("#report-ack-history")
        .get_by_text("Choice?: B", exact=False)
        .is_visible()
      )
      if os.environ.get("ARENA_STEERING_SCREENSHOT"):
        page.screenshot(path=f"{os.environ['ARENA_STEERING_SCREENSHOT']}-{width}.png")
      page.evaluate("window.releaseAnswer()")
      page.locator("#report-ack-history").get_by_text(
        "Choice?: B", exact=False
      ).wait_for()
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
def test_pending_answer_reconciles_exact_request_and_preserves_edits(
  tmp_path: Path,
) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore(tmp_path / "state.sqlite3")
  app = SteeringApp(store)
  app.reports.publish_report(
    "decision",
    "Decision",
    '<!-- question {"id":"choice","label":"Choice?"} -->\n'
    'Choice?\n- (x) A <!-- option {"label":"A"} -->\n'
    '- ( ) B <!-- option {"label":"B"} -->\n',
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
      page.locator("#tab-reports").click()
      page.locator('#field-choice input[value="B"]').check()
      page.evaluate("""() => {
        const original = window.fetch.bind(window);
        window.fetch = async (...args) => {
          const response = await original(...args);
          if (String(args[0]) === '/reports/decision/answers' && args[1]?.method === 'POST') {
            await new Promise(resolve => { window.releaseAnswer = resolve; });
          }
          return response;
        };
      }""")
      page.locator("#report-submit-float").click()
      page.wait_for_function("typeof window.releaseAnswer === 'function'")
      app.reports.submit_answer("decision", {"choice": "A"}, answer_id="ab9003")
      app.reports.submit_answer("decision", {"choice": "B"}, answer_id="ab9004")
      page.wait_for_function(
        "document.querySelectorAll('#report-ack-history strong').length === 3",
        timeout=8000,
      )
      assert (
        page.locator("#report-ack-history")
        .get_by_text("Choice?: B", exact=False)
        .count()
        == 2
      )
      page.locator('#field-choice input[value="A"]').check()
      page.evaluate("window.releaseAnswer()")
      page.wait_for_function(
        "document.querySelector('#report-submit-float')?.disabled === false"
      )
      page.reload()
      page.locator("#tab-reports").click()
      assert page.locator('#field-choice input[value="A"]').is_checked()
      browser.close()
  finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)
    store.close()


def test_answer_request_lookup_matches_report_and_committed_request() -> None:
  store = SqliteStore()
  app = SteeringApp(store)
  app.reports.publish_report(
    "decision",
    "Decision",
    '<!-- question {"id":"choice","label":"Choice?"} -->\n'
    'Choice?\n- (x) A <!-- option {"label":"A"} -->\n'
    '- ( ) B <!-- option {"label":"B"} -->\n',
  )
  status, result = app.dispatch(
    "POST",
    "/reports/decision/answers",
    {"values": {"choice": "B"}, "_request_id": "req-one"},
  )
  assert status == 201
  assert app.dispatch("GET", "/reports/decision/answer-requests/req-one")[1] == {
    "answer_id": result["answer"]["id"]
  }
  assert app.dispatch("GET", "/reports/other/answer-requests/req-one")[1] == {
    "answer_id": None
  }
  assert app.dispatch("GET", "/reports/decision/answer-requests/missing")[1] == {
    "answer_id": None
  }
  store.close()


@pytest.mark.skipif(
  not os.environ.get("ARENA_STEERING_CHROMIUM"),
  reason="Set ARENA_STEERING_CHROMIUM to run the browser regression",
)
@pytest.mark.parametrize("committed", [False, True])
def test_failed_answer_retains_draft_and_retry_is_idempotent(
  tmp_path: Path, committed: bool
) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore(tmp_path / "state.sqlite3")
  app = SteeringApp(store)
  app.reports.publish_report(
    "decision",
    "Decision",
    '<!-- question {"id":"choice","label":"Choice?"} -->\n'
    'Choice?\n- (x) A <!-- option {"label":"A"} -->\n'
    '- ( ) B <!-- option {"label":"B"} -->\n',
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
      page.locator("#tab-reports").click()
      page.locator('#field-choice input[value="B"]').check()
      page.evaluate(
        """committed => {
        const original = window.fetch.bind(window);
        let fail = true;
        window.fetch = async (...args) => {
          if (String(args[0]) === '/reports/decision/answers' && args[1]?.method === 'POST') {
            if (fail) {
              fail = false;
              if (committed) await original(...args);
              throw new Error('Connection lost');
            }
            await new Promise(resolve => { window.releaseRetry = resolve; });
          }
          return original(...args);
        };
      }""",
        committed,
      )
      page.locator("#report-submit-float").click()
      page.get_by_role("alert").get_by_text("Connection lost").wait_for()
      assert page.locator('#field-choice input[value="B"]').is_checked()
      if committed:
        page.locator("#report-ack-history").get_by_text(
          "Choice?: B", exact=False
        ).wait_for(timeout=8000)
      page.locator("#report-submit-float").click()
      page.get_by_role("button", name="Retry same action").click()
      page.wait_for_function("typeof window.releaseRetry === 'function'")
      if committed:
        assert (
          page.locator("#report-ack-history")
          .get_by_text("Choice?: B", exact=False)
          .count()
          == 1
        )
      page.evaluate("window.releaseRetry()")
      page.wait_for_function(
        "document.querySelector('#report-submit-float')?.disabled === false"
      )
      assert len(app.reports.get_report("decision").answers) == 1
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
def test_submit_and_scroll_top_clear_report_at_required_viewports() -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore()
  app = SteeringApp(store)
  body = (
    "# Report controls\n\n"
    + (
      "Readable report text needs to stay clear of the floating Submit button. " * 6
      + "\n\n"
    )
    * 24
    + "## Decision\n\n"
    + '<!-- question {"id":"decision","label":"Decision"} -->\n'
    + "Choose one.\n"
    + '- (x) Continue <!-- option {"label":"Continue"} -->\n'
  )
  app.reports.publish_report("controls", "Report controls", body)
  for idx in range(4):
    app.reports.publish_report(f"short-{idx}", f"Short {idx}", f"# Short {idx}")
  app.reports.publish_report("no-toc", "No TOC", "A plain paragraph.\n\n" * 80)
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
        for width, height in ((1372, 883), (855, 325), (411, 799)):
          for motion in ("reduce", "no-preference"):
            page = browser.new_page(
              viewport={"width": width, "height": height}, reduced_motion=motion
            )
            errors: list[str] = []
            page.on("pageerror", lambda error, errors=errors: errors.append(str(error)))
            page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
            page.locator("#tab-reports").click()
            float_button = page.locator("#report-submit-float")
            native_button = page.locator("#report-submit")
            top_button = page.locator("#report-scroll-top")
            float_button.wait_for()
            assert page.locator("#report-picker .report-picker-link").count() == 6
            assert float_button.inner_text().strip() == "Submit"
            assert native_button.text_content().strip() == "Submit"
            for button in (float_button, native_button):
              assert button.locator("svg.lucide-send").count() == 1
            assert top_button.is_hidden()
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            pane = page.locator("#view-reports")
            assert pane.evaluate("el => el.scrollHeight > el.clientHeight * 3")
            scroll_ratio = pane.evaluate("""el => {
              const maxScroll = el.scrollHeight - el.clientHeight;
              el.scrollTop = maxScroll / 2;
              return el.scrollTop / maxScroll;
            }""")
            assert 0.4 < scroll_ratio < 0.6
            toc_available = page.locator("#report-toc").is_visible()
            assert toc_available == (width >= 1200)
            if toc_available:
              assert top_button.is_hidden()
            else:
              top_button.wait_for(state="visible")
              assert top_button.text_content().strip() == ""
              assert top_button.get_attribute("aria-label") == "Scroll to top"
            styles = page.evaluate("""() => {
              const pane = document.querySelector('#view-reports');
              const layout = document.querySelector('.reports-layout');
              const main = document.querySelector('#report-main');
              const fade = getComputedStyle(main, '::after');
              const submit = getComputedStyle(document.querySelector('#report-submit-float'));
              const top = getComputedStyle(document.querySelector('#report-scroll-top'));
              const newest = getComputedStyle(document.querySelector('#log-newest'));
              const root = getComputedStyle(document.documentElement);
              return {
                bottomFade: parseFloat(fade.height),
                bottomContent: fade.content,
                bottomPosition: fade.position,
                bottomInset: fade.bottom,
                bottomBackground: fade.backgroundImage,
                bottomPointerEvents: fade.pointerEvents,
                bottomZ: parseInt(fade.zIndex),
                layoutBottomContent: getComputedStyle(layout, '::after').content,
                topFade: parseFloat(getComputedStyle(main, '::before').height),
                edgeFade: parseFloat(root.getPropertyValue('--edge-fade')),
                row: parseFloat(root.getPropertyValue('--row')),
                space4: parseFloat(root.getPropertyValue('--space-4')),
                submitInset: parseFloat(submit.bottom),
                submitZ: parseInt(submit.zIndex),
                panePaddingBottom: parseFloat(getComputedStyle(pane).paddingBottom),
                paneMarginBottom: getComputedStyle(pane).marginBottom,
                topPadding: top.padding,
                messagePadding: newest.padding,
                topBlur: top.backdropFilter,
                messageBlur: newest.backdropFilter,
              };
            }""")
            if motion == "no-preference":
              assert styles["bottomContent"] == '""', styles
              assert styles["bottomPosition"] == "sticky", styles
              assert styles["bottomInset"] == "0px", styles
              assert "linear-gradient" in styles["bottomBackground"], styles
              assert styles["bottomPointerEvents"] == "none", styles
              assert styles["bottomZ"] < styles["submitZ"], styles
              assert styles["layoutBottomContent"] == "none", styles
              assert styles["bottomFade"] == (
                styles["edgeFade"] + styles["row"] + styles["submitInset"]
              ), styles
              assert styles["topFade"] == styles["edgeFade"], styles
              assert styles["paneMarginBottom"] == "0px", styles
              assert styles["panePaddingBottom"] == (
                styles["submitInset"] + styles["space4"]
              ), styles
            else:
              assert styles["bottomContent"] == "none", styles
              assert float(styles["paneMarginBottom"].removesuffix("px")) > 0, styles
            assert styles["topPadding"] == styles["messagePadding"], styles
            assert styles["topBlur"] == styles["messageBlur"], styles
            if not toc_available:
              top_button.evaluate("el => { el.style.transition = 'none'; }")
              border_color = top_button.evaluate(
                "el => getComputedStyle(el).borderColor"
              )
              top_button.hover()
              assert (
                top_button.evaluate("el => getComputedStyle(el).borderColor")
                == border_color
              )
            geometry = page.evaluate("""() => {
              const box = selector => {
                const {x, y, width, height} = document.querySelector(selector).getBoundingClientRect();
                return {x, y, width, height};
              };
              return {
                pane: box('#view-reports'), submit: box('#report-submit-float'),
                top: box('#report-scroll-top'), report: box('#report'),
              };
            }""")
            pane_box, submit, top = (geometry[key] for key in ("pane", "submit", "top"))
            pane_bottom = pane_box["y"] + pane_box["height"]
            if motion == "no-preference":
              assert abs(pane_bottom - height) <= 1, geometry
              assert pane_bottom - styles["bottomFade"] < submit["y"], geometry
              assert submit["y"] < pane_bottom, geometry
            else:
              assert submit["y"] >= pane_bottom + 4, geometry
            assert (
              abs(height - (submit["y"] + submit["height"]) - styles["submitInset"])
              <= 1
            ), geometry
            assert submit["x"] >= 0 and submit["x"] + submit["width"] <= width, geometry
            if not toc_available:
              assert abs(top["x"] + top["width"] / 2 - width / 2) <= 2, geometry
              assert pane_box["y"] + 4 <= top["y"] <= pane_box["y"] + 80, geometry
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            pane.evaluate("el => { el.scrollTop = el.scrollHeight - el.clientHeight; }")
            end_report = page.locator("#report").bounding_box()
            assert (
              end_report and end_report["y"] + end_report["height"] <= submit["y"] - 4
            ), (
              end_report,
              submit,
            )
            if width == 411 and motion == "no-preference":
              # Simulate a taller device safe area without claiming physical-device coverage.
              pane.evaluate("""el => {
                el.style.setProperty('--reports-submit-bottom', '34px');
                el.scrollTop = el.scrollHeight - el.clientHeight;
              }""")
              safe_button = float_button.bounding_box()
              safe_report = page.locator("#report").bounding_box()
              safe_fade = page.locator("#report-main").evaluate(
                "el => parseFloat(getComputedStyle(el, '::after').height)"
              )
              assert safe_button and safe_report
              assert abs(height - safe_button["y"] - safe_button["height"] - 34) <= 1
              assert safe_fade == styles["edgeFade"] + styles["row"] + 34
              assert safe_report["y"] + safe_report["height"] <= safe_button["y"] - 4
            if toc_available:
              page.locator('#report-picker [data-report-id="no-toc"]').click()
              page.locator("#report-toc").wait_for(state="hidden")
              pane.evaluate("el => { el.scrollTop = Math.floor(el.scrollHeight / 2); }")
              top_button.wait_for(state="visible")
              assert top_button.text_content().strip() == ""
            top_button.click()
            page.wait_for_function(
              "document.querySelector('#view-reports').scrollTop <= 2"
            )
            top_button.wait_for(state="hidden")
            page.close()
            assert not errors
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
def test_submit_preserves_label_and_disables_during_request() -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore()
  app = SteeringApp(store)
  app.reports.publish_report(
    "choice",
    "Choice",
    '# Choice\n\n<!-- question {"id":"choice","label":"Choice"} -->\n'
    'Choose one.\n- (x) Yes <!-- option {"label":"Yes"} -->\n',
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
        page = browser.new_page(viewport={"width": 411, "height": 799})
        page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
        page.locator("#tab-reports").click()
        page.evaluate("""() => {
          const orig = window.fetch.bind(window);
          window.fetch = (input, options) => {
            if (!String(input).includes('/reports/choice/answers')) return orig(input, options);
            return new Promise(resolve => {
              window.releaseAnswerRequest = () => resolve(orig(input, options));
            });
          };
        }""")
        button = page.locator("#report-submit-float")
        base = button.bounding_box()
        assert base
        idle_color = button.evaluate("el => getComputedStyle(el).backgroundColor")
        button.hover()
        page.wait_for_function(
          "idle => getComputedStyle(document.querySelector('#report-submit-float')).backgroundColor !== idle",
          arg=idle_color,
        )
        page.keyboard.press("Tab")
        button.focus()
        assert button.evaluate("el => getComputedStyle(el).outlineWidth") == "2px"
        focus_box = button.bounding_box()
        assert focus_box and focus_box["width"] == base["width"]
        assert focus_box["height"] == base["height"]
        selected = page.locator('.question input[type="radio"][value="Yes"]')
        selected.check()
        assert selected.is_checked()
        page.mouse.move(base["x"] + base["width"] / 2, base["y"] + base["height"] / 2)
        page.mouse.down()
        assert button.evaluate("el => el.matches(':active')")
        pressed_box = button.bounding_box()
        assert pressed_box and pressed_box["width"] == base["width"]
        assert pressed_box["height"] == base["height"]
        assert app.reports.get_report("choice").answers == []
        page.mouse.up()
        page.wait_for_function("typeof window.releaseAnswerRequest === 'function'")
        assert button.is_disabled()
        assert page.locator("#report-submit").is_disabled()
        assert button.evaluate("el => getComputedStyle(el).opacity") == "0.55"
        assert button.inner_text().strip() == "Submit"
        page.locator("#tab-messages").click()
        page.locator("#tab-reports").click()
        button.wait_for(state="visible")
        assert button.is_disabled(), "a tab rerender must not permit duplicate writes"
        with page.expect_response("**/reports/choice/answers") as response:
          page.evaluate("window.releaseAnswerRequest()")
        assert response.value.status == 201, (
          response.value.text(),
          response.value.request.post_data,
        )
        page.wait_for_function(
          "document.querySelector('#report-submit-float:not(:disabled)') !== null"
        )
        assert len(app.reports.get_report("choice").answers) == 1
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
def test_report_picker_content_and_toc_fades_stay_in_their_own_regions() -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore()
  app = SteeringApp(store)
  long_body = (
    "# Long report\n\n"
    + "".join(
      f"## Section {index}\n\n"
      + "A paragraph to make this section scroll. " * 8
      + "\n\n"
      for index in range(45)
    )
    + '<!-- question {"id":"note","label":"Note"} -->\nNote: ___\n'
  )
  app.reports.publish_report("long", "Long report", long_body)
  for index in range(25):
    body = (
      "# Other\n\n" + "A long unfielded report.\n\n" * 75 if index == 0 else "# Other"
    )
    app.reports.publish_report(f"other-{index:02d}", f"Other report {index}", body)
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
        for width, height, motion in (
          (1372, 883, "no-preference"),
          (855, 325, "no-preference"),
          (411, 799, "no-preference"),
          (411, 799, "reduce"),
        ):
          page = browser.new_page(
            viewport={"width": width, "height": height},
            reduced_motion=motion,
          )
          page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
          page.locator("#tab-reports").click()
          pane = page.locator("#view-reports")
          picker = page.locator("#report-picker")
          assert picker.evaluate("el => el.scrollHeight > el.clientHeight + 1")
          assert picker.get_attribute("data-scrolled-end") is not None
          assert "linear-gradient(" in picker.evaluate(
            "el => getComputedStyle(el).maskImage"
          )
          pane.evaluate("el => { el.scrollTop = 18; }")
          page.wait_for_function(
            "document.querySelector('#view-reports').scrollTop >= 17"
          )
          fades = page.evaluate("""() => {
            const pane = document.querySelector('#view-reports');
            const layout = document.querySelector('.reports-layout');
            const main = document.querySelector('#report-main');
            return {
              panelBottom: getComputedStyle(pane, '::after').content,
              layoutTop: getComputedStyle(layout, '::before').content,
              mainTop: getComputedStyle(main, '::before').content,
              mainBottom: getComputedStyle(main, '::after').content,
              mainTopWidth: getComputedStyle(main, '::before').width,
              mainBottomWidth: getComputedStyle(main, '::after').width,
              mainWidth: main.getBoundingClientRect().width,
            };
          }""")
          assert fades["panelBottom"] == "none", fades
          assert fades["layoutTop"] == "none", fades
          if motion == "no-preference":
            assert fades["mainTop"] == '""', fades
            assert fades["mainBottom"] == '""', fades
            assert (
              float(fades["mainTopWidth"].removesuffix("px")) <= fades["mainWidth"] + 1
            )
            assert (
              float(fades["mainBottomWidth"].removesuffix("px"))
              <= fades["mainWidth"] + 1
            )
          else:
            assert fades["mainTop"] == fades["mainBottom"] == "none", fades
          if motion == "no-preference":
            # Scroll the *report* to its start, rather than the picker/answer
            # rail to its start. Their scroll edges must remain independent.
            pane.evaluate("""el => {
              const main = document.querySelector('#report-main');
              el.scrollTop += main.getBoundingClientRect().top -
                el.getBoundingClientRect().top - 8;
            }""")
            page.wait_for_timeout(80)
            report_start = page.evaluate("""() => {
              const pane = document.querySelector('#view-reports');
              const main = document.querySelector('#report-main');
              return { paneTop: pane.getBoundingClientRect().top,
                mainTop: main.getBoundingClientRect().top,
                scrollTop: pane.scrollTop };
            }""")
            assert report_start["mainTop"] >= report_start["paneTop"] - 2, (
              width,
              height,
              report_start,
            )
            assert (
              page.locator("#report-main").get_attribute("data-scrolled-start") is None
            )
            assert (
              page.evaluate("""() => getComputedStyle(
              document.querySelector('#report-main'), '::before').opacity""")
              == "0"
            )
            pane.evaluate("""el => {
              const main = document.querySelector('#report-main');
              el.scrollTop += main.getBoundingClientRect().top -
                el.getBoundingClientRect().top + 16;
            }""")
            page.wait_for_function("""() => document.querySelector(
              '#report-main')?.hasAttribute('data-scrolled-start')""")
            assert (
              page.evaluate("""() => getComputedStyle(
              document.querySelector('#report-main'), '::before').opacity""")
              == "1"
            )
            for at_bottom in (False, True):
              if at_bottom:
                pane.evaluate("el => { el.scrollTop = el.scrollHeight; }")
              # A temporary element with the pseudo-element's geometry makes
              # the sticky fade's *painted* bottom measurable in Chromium.
              fade_bottom = page.evaluate("""() => {
                const pane = document.querySelector('#view-reports');
                const main = document.querySelector('#report-main');
                const css = getComputedStyle(main, '::after');
                const marker = document.createElement('div');
                Object.assign(marker.style, {
                  display: 'block', position: css.position,
                  bottom: css.bottom, height: css.height,
                  marginTop: css.marginTop, transform: css.transform,
                });
                main.append(marker);
                const value = marker.getBoundingClientRect().bottom -
                  pane.getBoundingClientRect().bottom;
                marker.remove();
                return value;
              }""")
              assert abs(fade_bottom) <= 1, (width, height, at_bottom, fade_bottom)
          if width >= 1200:
            toc = page.locator("#report-toc")
            assert toc.is_visible()
            assert toc.evaluate("el => el.scrollHeight > el.clientHeight + 100")
            assert toc.get_attribute("data-scrolled-end") is not None
            toc.evaluate(
              "el => { el.scrollTop = (el.scrollHeight - el.clientHeight) / 2; }"
            )
            page.wait_for_function("""() => document.querySelector('#report-toc')
              ?.hasAttribute('data-scrolled-start')""")
            assert toc.get_attribute("data-scrolled-end") is not None
            assert "linear-gradient(" in toc.evaluate(
              "el => getComputedStyle(el).maskImage"
            )
            toc.evaluate("el => { el.scrollTop = el.scrollHeight; }")
            page.wait_for_function("""() => !document.querySelector('#report-toc')
              ?.hasAttribute('data-scrolled-end')""")
          else:
            assert page.locator("#report-toc").is_hidden()
          page.locator('#report-picker [data-report-id="other-00"]').click()
          page.wait_for_function("""() => document.querySelector('#report-picker [aria-current="true"]')
            ?.dataset.reportId === 'other-00'""")
          assert page.locator("#report-submit-float").count() == 0
          pane.evaluate("el => { el.scrollTop = 18; }")
          no_fields = page.evaluate("""() => ({
            shared: getComputedStyle(document.querySelector('.reports-layout'), '::after').content,
            main: getComputedStyle(document.querySelector('#report-main'), '::after').content,
          })""")
          assert no_fields["shared"] == "none", no_fields
          assert no_fields["main"] == ('""' if motion == "no-preference" else "none"), (
            no_fields
          )
          page.close()
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
def test_reports_bottom_fade_only_hides_for_mobile_keyboard() -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore()
  app = SteeringApp(store)
  body = (
    "# Keyboard fade\n\n"
    + ("A real report needs enough text for scrolling. " * 10 + "\n\n") * 28
    + '<!-- question {"id":"note","label":"Note"} -->\nNote: ___\n'
  )
  app.reports.publish_report("keyboard", "Keyboard fade", body)
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
        for width, height, motion in (
          (411, 799, "no-preference"),
          (855, 325, "no-preference"),
          (1372, 883, "no-preference"),
          (411, 799, "reduce"),
        ):
          page = browser.new_page(
            viewport={"width": width, "height": height},
            is_mobile=width < 1200,
            has_touch=width < 1200,
            reduced_motion=motion,
          )
          page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
          page.locator("#tab-reports").click()
          page.locator(".field-text-input").focus()
          pane = page.locator("#view-reports")
          pane.evaluate("el => { el.scrollTop = el.scrollHeight / 2; }")
          assert pane.evaluate("el => el.scrollHeight > el.clientHeight * 2")
          assert pane.evaluate("el => el.scrollTop > 36")

          def fades(page=page):
            return page.evaluate("""() => {
              const pane = document.querySelector('#view-reports');
              const layout = document.querySelector('.reports-layout');
              const main = document.querySelector('#report-main');
              return {
                panel: getComputedStyle(pane, '::after').content,
                layoutBottom: getComputedStyle(layout, '::after').content,
                mainBottom: getComputedStyle(main, '::after').content,
                mainTop: getComputedStyle(main, '::before').content,
                topOpacity: getComputedStyle(main, '::before').opacity,
                scrollTop: pane.scrollTop,
                keyboard: document.documentElement.hasAttribute('data-mobile-keyboard-open'),
                inputFocused: document.activeElement?.classList.contains('field-text-input'),
              };
            }""")

          closed = fades()
          assert closed["inputFocused"], closed
          assert not closed["keyboard"], closed
          assert closed["panel"] == closed["layoutBottom"] == "none", closed
          assert closed["mainBottom"] == (
            '""' if motion == "no-preference" else "none"
          ), closed
          page.evaluate("""() => {
            const viewport = window.visualViewport;
            window.originalVisualHeight = viewport.height;
            Object.defineProperty(viewport, 'height', {
              configurable: true, value: viewport.height - 60,
            });
            viewport.dispatchEvent(new Event('resize'));
          }""")
          assert fades()["mainBottom"] == closed["mainBottom"], fades()
          page.evaluate(
            """height => {
            const viewport = window.visualViewport;
            Object.defineProperty(viewport, 'height', {
              configurable: true, value: window.originalVisualHeight - height,
            });
            viewport.dispatchEvent(new Event('resize'));
          }""",
            min(240, height // 2),
          )
          pane.evaluate("el => { el.scrollTop = el.scrollHeight / 2; }")
          opened = fades()
          assert opened["scrollTop"] > 36, opened
          assert opened["mainTop"] == closed["mainTop"], (closed, opened)
          assert opened["panel"] == opened["layoutBottom"] == "none", opened
          if motion == "no-preference":
            assert float(opened["topOpacity"]) > 0.99, opened
          if width < 1200 and motion == "no-preference":
            assert opened["mainBottom"] == "none", opened
            assert opened["keyboard"], opened
          else:
            assert opened["mainBottom"] == closed["mainBottom"], (closed, opened)
            if width >= 1200:
              assert not opened["keyboard"], opened
          page.evaluate("""() => {
            delete window.visualViewport.height;
            window.visualViewport.dispatchEvent(new Event('resize'));
          }""")
          pane.evaluate("el => { el.scrollTop = el.scrollHeight / 2; }")
          restored = fades()
          assert restored["mainBottom"] == closed["mainBottom"], (closed, restored)
          assert not restored["keyboard"], restored
          assert restored["scrollTop"] > 36, restored
          page.close()
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
def test_switching_reports_keeps_picker_mounted_without_panel_flash() -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore()
  app = SteeringApp(store)
  for index in range(12):
    report_id = f"report-{index:02d}"
    body = f"# Report {index:02d}\n\nContent {index}."
    if index < 2:
      body += '\n\n<!-- question {"id":"note","label":"Note"} -->\nWhat changed?\n'
    app.reports.publish_report(report_id, f"Report {index:02d}", body)
  for index, value in ((0, "Stored zero"), (1, "Stored one")):
    report_id = f"report-{index:02d}"
    answer = app.reports.submit_answer(report_id, {"note": value})
    app.reports.ack_answer(report_id, answer.id, "Acknowledged detail. " * 100)
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
        for width, height in ((1372, 883), (855, 325), (411, 799)):
          page = browser.new_page(
            viewport={"width": width, "height": height},
            is_mobile=width < 1200,
            has_touch=width < 1200,
            reduced_motion="no-preference",
          )
          errors: list[str] = []
          page.on("pageerror", lambda error, errors=errors: errors.append(str(error)))
          page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
          page.locator("#tab-reports").click()
          page.wait_for_function("""() => !document.querySelector('#view-reports')
            .getAnimations().some(a => a.animationName === 'panel-enter')""")
          picker = page.locator("#report-picker")
          picker.evaluate(
            "el => { el.scrollTop = 25; el.dispatchEvent(new Event('scroll')); }"
          )
          before = page.evaluate("""() => {
            window.initialPicker = document.querySelector('#report-picker');
            window.initialLink = window.initialPicker.querySelector('[data-report-id="report-00"]');
            window.panelRestarts = 0;
            document.querySelector('#view-reports').addEventListener('animationstart', e => {
              if (e.animationName === 'panel-enter') window.panelRestarts += 1;
            });
            return {mask:getComputedStyle(window.initialPicker).maskImage,
              scroll:window.initialPicker.scrollTop};
          }""")
          assert before["scroll"] > 0, before
          assert before["mask"].count("linear-gradient(") == 1, before
          assert page.locator(".field-text-input").input_value() == "Stored zero"
          page.locator(".field-text-input").fill("Draft zero")
          previous_ack = page.locator("#report-ack-history")
          previous_ack.evaluate(
            "el => { el.scrollTop = 80; el.dispatchEvent(new Event('scroll')); }"
          )
          assert previous_ack.evaluate("el => el.scrollTop") > 0
          page.locator('#report-picker [data-report-id="report-01"]').click()
          page.wait_for_function("""() => document.querySelector(
            '#report-picker [aria-current="true"]')?.dataset.reportId === 'report-01'""")
          assert page.locator("#report-ack-history").evaluate("el => el.scrollTop") == 0
          page.wait_for_timeout(50)
          after = page.evaluate("""() => {
            const picker = document.querySelector('#report-picker');
            const pane = document.querySelector('#view-reports');
            return {samePicker:picker === window.initialPicker,
              sameLink:picker.querySelector('[data-report-id="report-00"]') === window.initialLink,
              restarts:window.panelRestarts,
              opacity:getComputedStyle(pane).opacity,
              mask:getComputedStyle(picker).maskImage};
          }""")
          assert after["samePicker"] and after["sameLink"], after
          assert after["restarts"] == 0 and after["opacity"] == "1", after
          assert after["mask"].count("linear-gradient(") == 1, after
          assert page.locator(".field-text-input").input_value() == "Stored one"
          page.locator(".field-text-input").fill("Draft one")
          page.locator('#report-picker [data-report-id="report-00"]').click()
          assert page.locator(".field-text-input").input_value() == "Draft zero"
          ack = page.locator("#report-ack-history")
          assert ack.locator("p").count() > 0
          ack.evaluate(
            "el => { el.scrollTop = 80; el.dispatchEvent(new Event('scroll')); }"
          )
          assert ack.evaluate("el => el.scrollTop") > 0
          assert page.evaluate("window.panelRestarts") == 0
          assert not errors, errors
          page.close()
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
@pytest.mark.parametrize("fail", [False, True])
@pytest.mark.parametrize("width", [1200, 390])
def test_report_selection_is_immediate_during_delayed_fetch(
  fail: bool, width: int, tmp_path: Path
) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore()
  app = SteeringApp(store)
  for name in ("first", "second"):
    app.reports.publish_report(
      name,
      name.title(),
      f"# {name.title()}\n\n{name.title()} body\n\n"
      '<!-- question {"id":"decision","label":"Decision"} -->\n'
      'Choose one.\n- (x) Continue <!-- option {"label":"Continue"} -->\n',
    )
  server = create_http_server(app, host="127.0.0.1", port=0)
  thread = threading.Thread(target=server.serve_forever, daemon=True)
  thread.start()
  try:
    with playwright.sync_playwright() as runner:
      browser = runner.chromium.launch(
        executable_path=os.environ["CHROMIUM_BIN"],
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage"],
      )
      page = browser.new_page(viewport={"width": width, "height": 800})
      page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
      page.locator("#tab-reports").click()
      current = page.locator('#report-picker [aria-current="true"]')
      current.wait_for()
      original_id = current.get_attribute("data-report-id")
      target = "second" if original_id == "first" else "first"
      page.evaluate(
        """({target, fail}) => {
        const original = window.fetch.bind(window);
        window.targetSeenCalls = 0;
        window.fetch = async (...args) => {
          if (String(args[0]) === `/reports/${target}/seen`) window.targetSeenCalls++;
          if (String(args[0]) === `/reports/${target}`) {
            await new Promise(resolve => { window.releaseReport = resolve; });
            if (fail) return new Response(JSON.stringify({error:'offline'}), {
              status:503, headers:{'content-type':'application/json'}
            });
          }
          return original(...args);
        };
      }""",
        {"target": target, "fail": fail},
      )
      page.locator(f'#report-picker [data-report-id="{target}"]').evaluate(
        "el => el.click()"
      )
      page.wait_for_function("typeof window.releaseReport === 'function'")
      assert (
        page.locator(f'#report-picker [data-report-id="{target}"]').get_attribute(
          "aria-current"
        )
        == "true"
      )
      assert page.get_by_role("status").filter(has_text="Loading report").is_visible()
      assert (
        page.locator(f'#report-picker [data-report-id="{target}"]')
        .get_attribute("class")
        .find("is-unseen")
        >= 0
      )
      assert page.locator("#report-submit-float").count() == 0
      assert page.evaluate("window.targetSeenCalls") == 0
      page.screenshot(path=str(tmp_path / f"report-selection-{width}.png"))
      page.evaluate("window.releaseReport()")
      if fail:
        page.get_by_role("alert").filter(has_text="Could not load report").wait_for()
        assert (
          page.locator(
            f'#report-picker [data-report-id="{original_id}"]'
          ).get_attribute("aria-current")
          == "true"
        )
      else:
        page.locator("#report").get_by_text(f"{target.title()} body").wait_for()
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
def test_report_selection_ignores_out_of_order_fetches() -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore()
  app = SteeringApp(store)
  for report_id in ("first", "second", "third"):
    app.reports.publish_report(
      report_id, report_id.title(), f"# {report_id.title()}\n\n{report_id} body"
    )
  server = create_http_server(app, host="127.0.0.1", port=0)
  thread = threading.Thread(target=server.serve_forever, daemon=True)
  thread.start()
  try:
    with playwright.sync_playwright() as runner:
      browser = runner.chromium.launch(
        executable_path=os.environ["CHROMIUM_BIN"],
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage"],
      )
      page = browser.new_page(viewport={"width": 1200, "height": 800})
      page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
      page.locator("#tab-reports").click()
      current = page.locator('#report-picker [aria-current="true"]')
      current.wait_for()
      targets = [
        item
        for item in ("first", "second", "third")
        if item != current.get_attribute("data-report-id")
      ]
      page.evaluate(
        """targets => {
        const original = window.fetch.bind(window);
        window.releaseReports = {};
        window.finishedReports = {};
        window.fetch = async (...args) => {
          const id = targets.find(item => String(args[0]) === `/reports/${item}`);
          if (id) await new Promise(resolve => { window.releaseReports[id] = resolve; });
          const response = await original(...args);
          if (id) window.finishedReports[id] = true;
          return response;
        };
      }""",
        targets,
      )
      for target in targets:
        page.locator(f'#report-picker [data-report-id="{target}"]').evaluate(
          "el => el.click()"
        )
        page.wait_for_function(
          "target => typeof window.releaseReports[target] === 'function'", arg=target
        )
      page.evaluate("target => window.releaseReports[target]()", targets[1])
      page.locator("#report").get_by_text(f"{targets[1]} body").wait_for()
      page.evaluate("target => window.releaseReports[target]()", targets[0])
      page.wait_for_function("target => window.finishedReports[target]", arg=targets[0])
      assert (
        page.locator(f'#report-picker [data-report-id="{targets[1]}"]').get_attribute(
          "aria-current"
        )
        == "true"
      )
      assert page.locator("#report").get_by_text(f"{targets[1]} body").is_visible()
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
def test_stretched_report_picker_pads_its_bottom_without_changing_compact_modes() -> (
  None
):
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore()
  app = SteeringApp(store)
  body = (
    '<!-- question {"id":"choice","label":"Choice?"} -->\n'
    'Choice?\n- (x) A <!-- option {"label":"A"} -->\n'
  )
  app.reports.publish_report("r-00", "Report 0", body)
  for index in range(1, 30):
    app.reports.publish_report(f"r-{index:02d}", f"Report {index}", "Report text.")
  server = create_http_server(app, host="127.0.0.1", port=0)
  thread = threading.Thread(target=server.serve_forever, daemon=True)
  thread.start()
  try:
    with playwright.sync_playwright() as runner:
      browser = runner.chromium.launch(
        executable_path=os.environ["CHROMIUM_BIN"],
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage"],
      )
      for width in (390, 1372):
        page = browser.new_page(viewport={"width": width, "height": 800})
        page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
        page.locator("#tab-reports").click()
        picker = page.locator("#report-picker")
        picker.locator(".report-picker-link").last.wait_for()
        geometry = picker.evaluate("""el => {
          el.scrollTop = el.scrollHeight;
          const last = el.querySelector('.report-picker-link:last-child').getBoundingClientRect();
          const rect = el.getBoundingClientRect();
          return {padding: parseFloat(getComputedStyle(el).paddingBottom),
                  gap: rect.bottom - last.bottom, scrollable: el.scrollHeight > el.clientHeight};
        }""")
        assert geometry["scrollable"]
        if width >= 1200:
          assert geometry["padding"] >= 20
          assert geometry["gap"] >= geometry["padding"] - 1
        else:
          assert geometry["padding"] == 0
        if os.environ.get("ARENA_STEERING_SCREENSHOT"):
          page.screenshot(path=f"{os.environ['ARENA_STEERING_SCREENSHOT']}-{width}.png")
        page.close()
      app.reports.submit_answer("r-00", {"choice": "A"})
      page = browser.new_page(viewport={"width": 1372, "height": 800})
      page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
      page.locator("#tab-reports").click()
      page.locator('#report-picker [data-report-id="r-00"]').click()
      page.locator("#report-ack-history").wait_for()
      assert (
        page.locator("#report-picker").evaluate(
          "el => parseFloat(getComputedStyle(el).paddingBottom)"
        )
        == 0
      )
      page.close()
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
@pytest.mark.parametrize("motion", ["reduce", "no-preference"])
def test_report_loading_bar_respects_reduced_motion(motion: str) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore()
  app = SteeringApp(store)
  app.reports.publish_report("test", "Test", "A report.")
  server = create_http_server(app, host="127.0.0.1", port=0)
  thread = threading.Thread(target=server.serve_forever, daemon=True)
  thread.start()
  try:
    with playwright.sync_playwright() as runner:
      browser = runner.chromium.launch(
        executable_path=os.environ["CHROMIUM_BIN"],
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage"],
      )
      page = browser.new_page(reduced_motion=motion)
      page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
      page.locator("#tab-reports").click()
      page.locator("#report").wait_for()
      for phase in ("true", "done"):
        content = page.evaluate(
          """phase => {
          document.querySelector('#view-reports').dataset.loading = phase;
          return getComputedStyle(document.querySelector('.topbar'), '::after').content;
        }""",
          phase,
        )
        assert (content == "none") == (motion == "reduce")
        if phase == "true" and os.environ.get("ARENA_STEERING_SCREENSHOT"):
          page.wait_for_timeout(300)
          page.screenshot(
            path=f"{os.environ['ARENA_STEERING_SCREENSHOT']}-{motion}.png"
          )
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
@pytest.mark.parametrize("fail", [False, True])
@pytest.mark.parametrize("width", [390, 1200])
@pytest.mark.parametrize("change_selection", [False, True])
def test_report_dismissal_is_immediate_and_preserves_new_selection(
  width: int,
  fail: bool,
  change_selection: bool,
) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore()
  app = SteeringApp(store)
  for name in ("first", "second", "third"):
    app.reports.publish_report(name, name.title(), f"# {name.title()}\n")
  server = create_http_server(app, host="127.0.0.1", port=0)
  thread = threading.Thread(target=server.serve_forever, daemon=True)
  thread.start()
  try:
    with playwright.sync_playwright() as runner:
      browser = runner.chromium.launch(
        executable_path=os.environ["CHROMIUM_BIN"],
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage"],
      )
      page = browser.new_page(viewport={"width": width, "height": 800})
      page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
      page.locator("#tab-reports").click()
      page.locator('#report-picker [data-report-id="first"]').wait_for()
      page.evaluate(
        """fail => {
        const original = window.fetch.bind(window);
        window.fetch = async (...args) => {
          if (String(args[0]) === '/reports/first' && args[1]?.method === 'DELETE') {
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
      page.locator("#dismiss-report-btn").click()
      page.locator('#modal-actions button[value="confirm"]').click()
      page.wait_for_function("typeof window.releaseDismiss === 'function'")
      assert page.locator('#report-picker [data-report-id="first"]').count() == 0
      app.reports.publish_report("fourth", "Fourth", "# Fourth\n")
      page.locator('#report-picker [data-report-id="fourth"]').wait_for(timeout=8000)
      assert page.locator('#report-picker [data-report-id="first"]').count() == 0
      if change_selection:
        page.locator('#report-picker [data-report-id="third"]').evaluate(
          "el => el.click()"
        )
        page.wait_for_function(
          "document.querySelector('#report-picker [aria-current=true]')?.dataset.reportId === 'third'"
        )
      else:
        page.get_by_role("heading", name="Second", exact=True).wait_for()
      if os.environ.get("ARENA_STEERING_SCREENSHOT") and not fail and change_selection:
        page.screenshot(path=f"{os.environ['ARENA_STEERING_SCREENSHOT']}-{width}.png")
      page.evaluate("window.releaseDismiss()")
      if fail:
        page.get_by_role("alert").filter(has_text="Could not dismiss").wait_for()
        assert page.locator('#report-picker [data-report-id="first"]').count() == 1
      else:
        page.wait_for_function(
          "document.querySelector('#report-picker [data-report-id=first]') === null"
        )
      assert page.locator('#report-picker [aria-current="true"]').get_attribute(
        "data-report-id"
      ) == ("third" if change_selection else "first" if fail else "second")
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
def test_lost_report_dismissal_response_reconciles_server_state() -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore()
  app = SteeringApp(store)
  app.reports.publish_report("only", "Only", "# Only\n")
  server = create_http_server(app, host="127.0.0.1", port=0)
  thread = threading.Thread(target=server.serve_forever, daemon=True)
  thread.start()
  try:
    with playwright.sync_playwright() as runner:
      browser = runner.chromium.launch(
        executable_path=os.environ["CHROMIUM_BIN"],
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage"],
      )
      page = browser.new_page()
      page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
      page.locator("#tab-reports").click()
      page.locator("#dismiss-report-btn").wait_for()
      page.evaluate("""() => {
        const original = window.fetch.bind(window);
        window.fetch = async (...args) => {
          if (String(args[0]) === '/reports/only' && args[1]?.method === 'DELETE') {
            await original(...args);
            throw new Error('Connection lost');
          }
          return original(...args);
        };
      }""")
      page.locator("#dismiss-report-btn").click()
      page.locator('#modal-actions button[value="confirm"]').click()
      page.get_by_role("alert").filter(has_text="Connection lost").wait_for()
      page.get_by_text("No report published yet.").wait_for(timeout=8000)
      assert page.get_by_role("alert").filter(has_text="Connection lost").is_visible()
      browser.close()
  finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)
    store.close()


CHOICE = (
  '<!-- question {"id":"choice","label":"Choice"} -->\n'
  "Choose one\n"
  '- (x) A <!-- option {"label":"A"} -->\n'
  '- ( ) B <!-- option {"label":"B"} -->\n'
)


CHECKBOX = (
  '<!-- question {"id":"checks","label":"Checks"} -->\n'
  "Choose any\n"
  '- [x] C <!-- option {"label":"C"} -->\n'
  '- [ ] D <!-- option {"label":"D"} -->\n'
)


TEXT = '<!-- question {"id":"note","label":"Note"} -->\nYour note\n'


def test_each_option_field_needs_a_default_without_changing_saved_answers(
  tmp_path: Path,
) -> None:
  store = SqliteStore(tmp_path / "state.sqlite3")
  app = SteeringApp(store)
  body = CHOICE + "\n" + CHECKBOX + "\n" + TEXT
  app.reports.publish_report("decision", "Decision", body)
  app.reports.submit_answer("decision", {"choice": "B", "checks": ["D"], "note": "ok"})
  for invalid in (
    body.replace("(x) A", "( ) A"),
    body.replace("[x] C", "[ ] C"),
  ):
    with pytest.raises(ValueError, match="preselected"):
      app.reports.publish_report("new-decision", "Decision", invalid)
    status, payload = app.dispatch(
      "POST", "/reports", {"id": "api-decision", "title": "Decision", "body": invalid}
    )
    assert status == 400 and "preselected" in payload["error"]
    with pytest.raises(ValueError, match="preselected"):
      app.reports.publish_report("decision", "Decision", invalid)
    report = app.reports.get_report("decision")
    assert report.body == body
    assert report.answers[-1].values == {"choice": "B", "checks": ["D"], "note": "ok"}
  app.reports.publish_report("text-only", "Text", TEXT)
  app.reports.publish_report("unfielded", "Unfielded", "# No fields")
  store.close()


@pytest.mark.skipif(
  not os.environ.get("CHROMIUM_BIN"), reason="Set CHROMIUM_BIN for browser tests"
)
def test_report_keyboard_viewport_offset_keeps_shell_at_visible_bottom(
  tmp_path: Path,
) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore()
  app = SteeringApp(store)
  app.reports.publish_report(
    "keyboard",
    "Keyboard",
    '<!-- question {"id":"note","label":"Note"} -->\nNote: ___\n',
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
        page = browser.new_page(
          viewport={"width": 411, "height": 799}, is_mobile=True, has_touch=True
        )
        page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
        page.locator("#tab-reports").click()
        page.locator(".field-text-input").focus()
        page.evaluate("""() => {
          const viewport = window.visualViewport;
          Object.defineProperty(viewport, 'height', {configurable: true, value: 559});
          Object.defineProperty(viewport, 'offsetTop', {configurable: true, value: 80});
          viewport.dispatchEvent(new Event('resize'));
        }""")
        geometry = page.evaluate("""() => ({
          shellBottom: document.querySelector('.app-shell').getBoundingClientRect().bottom,
          visibleBottom: visualViewport.offsetTop + visualViewport.height,
          keyboard: document.documentElement.hasAttribute('data-mobile-keyboard-open'),
        })""")
        assert geometry["keyboard"], geometry
        assert abs(geometry["shellBottom"] - geometry["visibleBottom"]) < 1, geometry
        page.screenshot(path=str(tmp_path / "keyboard-offset.png"))
        page.evaluate("""() => {
          delete visualViewport.height;
          delete visualViewport.offsetTop;
          visualViewport.dispatchEvent(new Event('resize'));
        }""")
        assert page.locator(".app-shell").evaluate(
          "el => Math.abs(el.getBoundingClientRect().top) < 1"
        )
      finally:
        browser.close()
  finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)
    store.close()
