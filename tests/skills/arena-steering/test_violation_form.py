"""Browser violation flags remain blocking until cancelled or acknowledged."""

from __future__ import annotations

import os
import threading
from http import HTTPStatus
from pathlib import Path

import pytest
from arena_steering.server import SteeringApp, create_http_server
from arena_steering.store import SqliteStore


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
      "note": "The command failed without an acknowledgement.",
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
    assert "Cited: " + flag["note"] in violation.body
    assert violation.id in app.messages.pending_ids()

    status, duplicate = app.dispatch("POST", "/agent-interrupt", flag)
    assert status == HTTPStatus.OK and duplicate == result
    assert len(app.messages.list_messages()) == len(messages)
    for invalid in (
      {**flag, "armed": "false"},
      {**flag, "tab": "reports"},
      {**flag, "clause_file": "../outside.md"},
      {**flag, "clause_file": 0},
      {**flag, "note": {"not": "text"}},
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
    "fix-flag", "Fix violation flag", type="code", details=["Fix the violation form."]
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
        page.locator("#violation-note").fill(cited_reason)
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
        page.locator("#violation-submit").click()
        page.locator("#violation-error").wait_for(state="visible", timeout=5000)
        assert form.is_visible()
        assert button.get_attribute("aria-pressed") == "false"
        page.once("dialog", lambda dialog: dialog.accept())
        page.locator("#violation-submit").click()
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
        page.once("dialog", lambda dialog: dialog.accept())
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
