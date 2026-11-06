"""Connection status and cross-process polling regressions."""

from __future__ import annotations

import io
import json
import os
import threading
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from arena_steering import cli
from arena_steering.server import SteeringApp, create_http_server
from arena_steering.services import with_bible_read
from arena_steering.store import SqliteStore


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
