"""Connection status and cross-process polling regressions."""

from __future__ import annotations

import io
import os
import threading
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from arena_steering import cli
from arena_steering.server import SteeringApp, create_http_server
from arena_steering.store import SqliteStore


def _stamp(seconds_ago: float = 0) -> str:
  return (datetime.now(UTC) - timedelta(seconds=seconds_ago)).isoformat()


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


def test_answer_wakes_poll_without_lock_inversion() -> None:
  store = SqliteStore()
  app = SteeringApp(store)
  app.reports.publish_report(
    "choice",
    "Choice",
    '<!-- question {"id": "pick", "label": "Pick"} -->\n'
    'Pick\n- ( ) Yes <!-- option {"label": "Yes"} -->\n',
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
    app.messages.poll(timeout_seconds=0.05)
    assert store.get_meta("turn_ended_at")
    assert not store.get_meta("polling_at")
    app.messages.touch_agent()
    assert not store.get_meta("turn_ended_at")
  finally:
    store.close()


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
