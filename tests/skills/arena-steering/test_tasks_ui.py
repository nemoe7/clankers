"""Steering browser regression tests."""

from __future__ import annotations

import base64
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from arena_steering.server import (
  SteeringApp,
  create_http_server,
)
from arena_steering.store import SqliteStore

ROOT = Path(__file__).resolve().parents[3]


SKILL_DIR = ROOT / "skills" / "arena-steering"


ASSETS_DIR = SKILL_DIR / "assets"


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
          def suffix_x() -> float:
            """Return the x of "detail", wherever the highlight splits text."""
            return detail.evaluate("""el => {
              const offset = el.textContent.indexOf('detail');
              const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
              let node, seen = 0;
              while ((node = walker.nextNode())) {
                if (seen + node.length > offset) {
                  const range = document.createRange();
                  range.setStart(node, offset - seen);
                  range.setEnd(node, offset - seen + 1);
                  return range.getBoundingClientRect().x;
                }
                seen += node.length;
              }
              return NaN;
            }""")

          original_suffix_x = suffix_x()

          search.fill("Alpha")
          highlighted_title_width = title.evaluate(
            "el => el.getBoundingClientRect().width"
          )
          highlighted_suffix_x = suffix_x()
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
  css = (ASSETS_DIR / "style.css").read_text(encoding="utf-8")
  rule = css.split('.task-title[data-gate-running="true"] {', 1)[1].split("}", 1)[0]
  assert "#90caf9" in rule
  assert "#42a5f5" in rule
  assert "#dcefff" not in rule


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


@pytest.mark.parametrize("transport", ["websocket", "poll"])
def test_task_link_and_ack_refresh_during_slow_pagination(
  tmp_path: Path, transport: str
) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  path = tmp_path / "state.sqlite3"
  server_store = SqliteStore(path)
  writer_store = SqliteStore(path)
  app = SteeringApp(server_store, repo_name="Slow acknowledgement")
  writer = SteeringApp(writer_store)
  for index in range(25):
    app.messages.send_message(
      f"Older message {index}", msg_id=f"{index:06x}", blocking=False
    )
  target_id = "ab0123"
  app.messages.send_message("Awaiting reply", msg_id=target_id, blocking=False)
  server = create_http_server(app, host="0.0.0.0", port=0)
  thread = threading.Thread(target=server.serve_forever, daemon=True)
  thread.start()
  try:
    with playwright.sync_playwright() as runner:
      browser = runner.chromium.launch(
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage"],
      )
      try:
        page = browser.new_page()
        sockets = []
        page.on("websocket", lambda socket: sockets.append(socket))
        page.add_init_script("""(() => {
          window.olderRequestHeld = false;
          window.taskRefreshResponses = 0;
          window.lastTaskRefreshAt = 0;
          const taskRequestIds = new Set();
          const isOlderPage = path => {
            if (typeof path !== 'string' || !path.startsWith('/messages?')) return false;
            return new URLSearchParams(path.split('?', 2)[1] || '').has('before');
          };
          const countTaskResponse = () => {
            window.taskRefreshResponses += 1;
            window.lastTaskRefreshAt = Date.now();
          };
          const originalFetch = window.fetch.bind(window);
          window.fetch = async (...args) => {
            const path = String(args[0]);
            if (isOlderPage(path) && !window.olderRequestHeld) {
              window.olderRequestHeld = true;
              await new Promise(resolve => { window.releaseOlder = resolve; });
            }
            const response = await originalFetch(...args);
            if (path.startsWith('/tasks?')) {
              const originalJson = response.json.bind(response);
              response.json = async (...jsonArgs) => {
                const payload = await originalJson(...jsonArgs);
                countTaskResponse();
                return payload;
              };
            }
            return response;
          };
          const prototype = window.WebSocket?.prototype;
          if (!prototype) return;
          const originalSend = prototype.send;
          prototype.send = function(data) {
            let request;
            try { request = JSON.parse(data); } catch {}
            const path = request?.path;
            if (request?.method === 'GET' && isOlderPage(path) && !window.olderRequestHeld) {
              window.olderRequestHeld = true;
              window.releaseOlder = () => originalSend.call(this, data);
              return;
            }
            if (request?.method === 'GET' && path?.startsWith('/tasks?')) {
              taskRequestIds.add(request.id);
            }
            return originalSend.call(this, data);
          };
          const originalAdd = prototype.addEventListener;
          prototype.addEventListener = function(type, listener, options) {
            if (type !== 'message' || typeof listener !== 'function') {
              return originalAdd.call(this, type, listener, options);
            }
            return originalAdd.call(this, type, function(event) {
              let response;
              try { response = JSON.parse(event.data); } catch {}
              const isTaskResponse = response?.type === 'response' && taskRequestIds.delete(response.id);
              const result = listener.call(this, event);
              if (isTaskResponse) countTaskResponse();
              return result;
            }, options);
          };
        })();""")
        query = "?transport=poll" if transport == "poll" else ""
        page.goto(f"http://127.0.0.1:{server.server_port}/{query}")
        card = page.locator(f'.message[data-msg-id="{target_id}"]')
        card.wait_for(state="visible")
        page.locator("#load-older-messages").wait_for(state="visible")
        page.wait_for_function(
          "() => window.taskRefreshResponses > 0 && Date.now() - window.lastTaskRefreshAt > 300"
        )
        if transport == "websocket":
          assert sockets, "the WebSocket transport must connect"
        else:
          assert not sockets, "the polling transport must not open a WebSocket"
        baseline = page.evaluate("window.taskRefreshResponses")
        page.locator("#load-older-messages").evaluate("element => element.click()")
        page.wait_for_function("window.olderRequestHeld === true")

        task_id = "slow-link-task"
        ack_text = "Delayed network acknowledgement"
        with writer_store.transaction():
          writer.tasks.create_task(
            task_id,
            "Slow link task",
            size=3,
            details=["Track the acknowledgement"],
            msg_ids=[target_id],
          )
          writer.messages.ack(target_id, ack_text)
        assert writer.messages.get_message(target_id).acks == [ack_text]
        page.wait_for_function(
          "baseline => window.taskRefreshResponses > baseline",
          arg=baseline,
          timeout=10000,
        )
        page.evaluate(
          "() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))"
        )
        chip = card.locator(
          '.receipt-task-links .reply-parent-chip[data-reference-id="slow-link-task"]'
        )
        chip.wait_for(state="visible", timeout=5000)
        card.locator(".reply").get_by_text(ack_text).wait_for(timeout=5000)
        page.wait_for_function(
          f"document.querySelector('.message[data-msg-id=\\\"{target_id}\\\"] .receipt-status')"
          ".getAttribute('data-state-label') === 'Status: acked'"
        )
        assert page.evaluate("window.olderRequestHeld") is True

        page.evaluate("window.releaseOlder?.()")
        page.wait_for_function(
          "document.querySelectorAll('#history .message').length === 26",
          timeout=10000,
        )
      finally:
        browser.close()
  finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)
    writer_store.close()
    server_store.close()


@pytest.mark.parametrize("query", ["?transport=poll", ""])
def test_finished_tasks_render_newest_completion_first(
  tmp_path: Path, query: str
) -> None:
  from arena_steering.models import Task

  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore(tmp_path / "state.sqlite3")
  task_ids = ["earlier", "latest"]
  store.save_task_queue(
    [
      Task(
        task_id,
        task_id,
        size=1,
        type="ops",
        status="finished",
        details=["Done"],
        finished_at=f"2026-11-09T0{index + 1}:00:00Z",
      )
      for index, task_id in enumerate(task_ids)
    ]
  )
  app = SteeringApp(store)
  server = create_http_server(app, host="0.0.0.0", port=0)
  thread = threading.Thread(target=server.serve_forever, daemon=True)
  thread.start()
  try:
    with playwright.sync_playwright() as runner:
      browser = runner.chromium.launch(
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage"],
      )
      try:
        page = browser.new_page(viewport={"width": 411, "height": 799})
        page.goto(f"http://127.0.0.1:{server.server_port}/{query}")
        page.locator("#tab-tasks").click()
        titles = page.locator("#tasks-finished-body .task-title")
        titles.first.wait_for()
        assert titles.evaluate_all("els => els.map(el => el.dataset.parentId)") == list(
          reversed(task_ids)
        )
        page.screenshot(path=str(tmp_path / "finished-order.png"))
      finally:
        browser.close()
  finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)
    store.close()
