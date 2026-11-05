"""Browser regressions for Report controls against real scroll geometry."""

from __future__ import annotations

import os
import threading

import pytest
from arena_steering.server import SteeringApp, create_http_server
from arena_steering.store import SqliteStore


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
    + '- ( ) Continue <!-- option {"label":"Continue"} -->\n'
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
            assert pane.evaluate("el => el.scrollHeight > el.clientHeight + 180")
            pane.evaluate("el => { el.scrollTop = Math.floor(el.scrollHeight / 2); }")
            toc_available = page.locator("#report-toc").is_visible()
            assert toc_available == (width >= 1200)
            if toc_available:
              assert top_button.is_hidden()
            else:
              top_button.wait_for(state="visible")
              assert top_button.text_content().strip() == ""
              assert top_button.get_attribute("aria-label") == "Scroll to top"
            styles = page.evaluate("""() => {
              const layout = document.querySelector('.reports-layout');
              const top = getComputedStyle(document.querySelector('#report-scroll-top'));
              const newest = getComputedStyle(document.querySelector('#log-newest'));
              const root = getComputedStyle(document.documentElement);
              return {
                bottomFade: parseFloat(getComputedStyle(layout, '::after').height),
                topFade: parseFloat(getComputedStyle(layout, '::before').height),
                edgeFade: parseFloat(root.getPropertyValue('--edge-fade')),
                compactFade: parseFloat(root.getPropertyValue('--space-4')),
                topPadding: top.padding,
                messagePadding: newest.padding,
                topBlur: top.backdropFilter,
                messageBlur: newest.backdropFilter,
              };
            }""")
            if motion == "no-preference":
              assert (
                0 < styles["bottomFade"] <= styles["compactFade"] < styles["edgeFade"]
              ), styles
              assert styles["topFade"] == styles["edgeFade"], styles
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
            assert submit["y"] >= pane_box["y"] + pane_box["height"] + 4, geometry
            assert submit["x"] >= 0 and submit["x"] + submit["width"] <= width, geometry
            if not toc_available:
              assert abs(top["x"] + top["width"] / 2 - width / 2) <= 2, geometry
              assert pane_box["y"] + 4 <= top["y"] <= pane_box["y"] + 80, geometry
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
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
    'Choose one.\n- ( ) Yes <!-- option {"label":"Yes"} -->\n',
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
