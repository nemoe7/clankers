"""Browser coverage for hidden report answers and acknowledgements."""

from __future__ import annotations

import os
import threading
from pathlib import Path

import pytest
from arena_steering.server import SteeringApp, create_http_server
from arena_steering.store import SqliteStore


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
def test_hidden_answer_and_live_report_replies(tmp_path: Path) -> None:
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
        page = browser.new_page(viewport={"width": 1200, "height": 760})
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
        status, _ = app.dispatch(
          "POST", "/messages/ab9002/ack", {"markdown": "Reviewed answer"}
        )
        assert status == 200
        history.get_by_text("Reviewed answer").wait_for(timeout=8000)
        page.screenshot(path=str(tmp_path / "report-answer.png"))
        assert not errors
      finally:
        browser.close()
  finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)
    store.close()
