"""Steering browser regression tests."""

from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import threading
import time
from pathlib import Path

import pytest
from arena_steering import cli, survey
from arena_steering import server as steering_server
from arena_steering.server import (
  SteeringApp,
  create_http_server,
)
from arena_steering.services import with_bible_read
from arena_steering.store import SqliteStore

ROOT = Path(__file__).resolve().parents[3]


SKILL_DIR = ROOT / "skills" / "arena-steering"


ASSETS_DIR = SKILL_DIR / "assets"


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
def test_websocket_refreshes_after_external_store_write(
  tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  monkeypatch.setattr("arena_steering.server.WS_HEARTBEAT_SECONDS", 0.05)
  monkeypatch.setattr("arena_steering.server.WS_TICK_SECONDS", 0.02)
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
          writer_store.set_meta("polling_at", "2026-11-09T00:00:00Z")
        frames.clear()
        with sockets[0].expect_event(
          "framereceived",
          predicate=lambda frame: frame == '{"type":"heartbeat"}',
          timeout=6000,
        ):
          writer_store.set_meta("polling_at", "2026-11-09T00:00:01Z")
        assert '{"type":"change"}' not in frames
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
    encoding="utf-8",
    check=False,
  )
  assert result.returncode == 0, result.stderr


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
