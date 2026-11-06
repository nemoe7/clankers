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
