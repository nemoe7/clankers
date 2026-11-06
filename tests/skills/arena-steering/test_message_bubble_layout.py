"""Browser geometry and receipt regressions for right-aligned Messages bubbles."""

from __future__ import annotations

import base64
import itertools
import os
import threading
from pathlib import Path

import pytest
from arena_steering.models import Attachment
from arena_steering.server import SteeringApp, create_http_server
from arena_steering.store import SqliteStore


@pytest.mark.skipif(
  not os.environ.get("CHROMIUM_BIN"),
  reason="Set CHROMIUM_BIN for the extracted browser",
)
def test_message_bubble_reference_across_required_viewports(tmp_path: Path) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore(tmp_path / "state.sqlite3")
  app = SteeringApp(store)
  app.reports.publish_report("reference", "Reference", "# Reference")
  image = tmp_path / "uploads" / "layout.png"
  image.parent.mkdir(exist_ok=True)
  image.write_bytes(
    base64.b64decode(
      "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+ip1sAAAAASUVORK5CYII="
    )
  )
  app.messages.send_message("Parent message", msg_id="bb0001", blocking=False)
  app.messages.send_message(
    "Short message.",
    msg_id="bb0002",
    blocking=False,
    parent_refs=[
      {"type": "message", "id": "bb0001"},
      {"type": "report", "id": "reference"},
    ],
    attachments=[
      Attachment(name="layout.png", path=str(image)),
      Attachment(name="notes.txt", path=str(tmp_path / "missing.txt"), present=False),
      Attachment(name="other.txt", path=str(tmp_path / "other.txt"), present=False),
    ],
  )
  app.messages.ack("bb0002", "An agent response with more content. " * 45)
  app.messages.send_message(
    "A long message needs to fill the row. " * 110,
    msg_id="bb0003",
    blocking=False,
  )
  app.messages.ack("bb0003", "A long acknowledgement can fill this row. " * 95)
  app.messages.send_message(
    "A message wider than an acknowledgement cap.",
    msg_id="bb0006",
    blocking=False,
  )
  app.messages.ack(
    "bb0006", "A longer acknowledgement should fill its wider bubble. " * 36
  )
  app.messages.send_message("Awaiting the agent.", msg_id="bb0004")
  app.tasks.create_task(
    "linked-task", "Linked task", size=1, details=["Review"], msg_ids=["bb0004"]
  )
  seen = app.messages.send_message("Already seen.", msg_id="bb0005", blocking=False)
  store.mark_message_seen(seen.id, seen.modified_at)
  app.messages.send_message(
    "Multiple acknowledgements.", msg_id="bb0007", blocking=False
  )
  app.messages.ack("bb0007", "An earlier paragraph.")
  app.messages.ack("bb0007", "The final paragraph.")
  app.messages.send_message(
    "First line  \nSecond line.", msg_id="bb0008", blocking=False
  )
  app.messages.ack("bb0008", "An agent response with more content. " * 45)
  app.messages.send_message(
    "First paragraph.\n\nSecond paragraph.", msg_id="bb0009", blocking=False
  )
  app.messages.ack("bb0009", "An agent response with more content. " * 45)
  app.messages.send_message("Short line.\n", msg_id="bb0010", blocking=False)
  app.messages.ack("bb0010", "An agent response with more content. " * 45)
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
            viewport={"width": width, "height": height}, reduced_motion="reduce"
          )
          page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
          page.add_style_tag(
            content=""".message[data-msg-id="bb0006"] .message-text {
              width: calc(var(--message-row-width) * 0.78 - 30px);
            }"""
          )
          short = page.locator('.message[data-msg-id="bb0002"]')
          long = page.locator('.message[data-msg-id="bb0003"]')
          middle = page.locator('.message[data-msg-id="bb0006"]')
          sent = page.locator('.message[data-msg-id="bb0004"]')
          seen = page.locator('.message[data-msg-id="bb0005"]')
          for card in (short, long, middle, sent, seen):
            card.wait_for()
          if os.environ.get("ARENA_STEERING_SCREENSHOT"):
            sent.scroll_into_view_if_needed()
            page.screenshot(
              path=f"{os.environ['ARENA_STEERING_SCREENSHOT']}-{width}.png"
            )

          def boxes(card):
            return card.evaluate("""element => {
              const rect = selector => {
                const target = element.querySelector(selector);
                if (!target) return null;
                const {x, y, width, height, right, bottom} = target.getBoundingClientRect();
                return {x, y, width, height, right, bottom};
              };
              return {
                row: element.getBoundingClientRect().toJSON(),
                id: rect('.receipt-id'), bubble: rect('.message-bubble'),
                body: rect('.message-bubble > .message-text'),
                ack: rect('.message-bubble > .answer.reply'),
                parents: rect('.message-parents'),
                files: rect('.message-attachments'),
                receipt: rect('.receipt'),
                task: rect('.receipt .reply-parent-chip[data-reference-type="task"]'),
                status: rect('.receipt-status'), stamp: rect('.receipt time'),
                attachments: [...element.querySelectorAll('.message-attachments .receipt-file > *')]
                  .map(node => node.getBoundingClientRect().toJSON()),
                parentChips: [...element.querySelectorAll('.message-parents .reply-parent-chip')]
                  .map(node => node.getBoundingClientRect().toJSON()),
                bubbleOverflow: element.querySelector('.message-bubble').scrollWidth
                  - element.querySelector('.message-bubble').clientWidth,
                ackBorderLeft: getComputedStyle(element.querySelector('.answer.reply') || element).borderLeftWidth,
                ackBorderRight: getComputedStyle(element.querySelector('.answer.reply') || element).borderRightWidth,
                bodyAlign: getComputedStyle(
                  element.querySelector('.message-bubble > .message-text') || element
                ).textAlign,
                bodyLines: (() => {
                  const body = element.querySelector('.message-bubble > .message-text');
                  const walker = document.createTreeWalker(body, NodeFilter.SHOW_TEXT);
                  const lines = new Set();
                  while (walker.nextNode()) {
                    if (!walker.currentNode.textContent.trim()) continue;
                    const range = document.createRange();
                    range.selectNodeContents(walker.currentNode);
                    for (const rect of range.getClientRects()) lines.add(Math.round(rect.y));
                  }
                  return lines.size;
                })(),
              };
            }""")

          for card in (short, long, middle, sent, seen):
            card.scroll_into_view_if_needed()
            shape = boxes(card)
            assert shape["bubble"] and shape["id"] and shape["receipt"], shape
            assert abs(shape["bubble"]["right"] - shape["row"]["right"]) <= 1, shape
            assert abs(shape["id"]["right"] - shape["body"]["right"]) <= 1, shape
            assert shape["id"]["bottom"] <= shape["bubble"]["y"] + 1, shape
            if shape["files"]:
              assert shape["files"]["bottom"] <= shape["id"]["y"] + 1, shape
            assert shape["receipt"]["y"] >= shape["bubble"]["bottom"] - 1, shape
            assert abs(shape["stamp"]["right"] - shape["body"]["right"]) <= 1, shape
            assert shape["bodyAlign"] == "left", shape
            assert shape["bubbleOverflow"] <= 1, shape
          s = boxes(short)
          assert s["bodyLines"] == 1, s
          assert s["body"]["x"] > s["bubble"]["x"] + 19, s
          assert abs(s["body"]["right"] - (s["bubble"]["right"] - 15)) <= 1, s
          trailing_newline = page.locator('.message[data-msg-id="bb0010"]')
          trailing_newline.scroll_into_view_if_needed()
          trailing = boxes(trailing_newline)
          assert trailing["bodyLines"] == 1, trailing
          assert "message-text-multiline" not in (
            trailing_newline.locator(
              ".message-bubble > .message-text:first-child"
            ).get_attribute("class")
            or ""
          )
          assert (
            abs(trailing["body"]["right"] - (trailing["bubble"]["right"] - 15)) <= 1
          ), trailing
          log_max = 900
          reply_cap = log_max * 2 / 3
          assert s["bubble"]["width"] <= min(s["row"]["width"] - 20, reply_cap) + 1, s
          assert s["ack"]["width"] <= reply_cap - 30 + 1, s
          assert abs(s["ack"]["width"] - (s["bubble"]["width"] - 30)) <= 1, s
          assert s["ackBorderLeft"] == "0px" and s["ackBorderRight"] == "2px", s
          assert abs(s["ack"]["right"] - (s["bubble"]["right"] - 15)) <= 1, s
          final_paragraph = short.locator(
            ".answer.reply > div:last-child > p:last-child"
          )
          assert (
            final_paragraph.evaluate("el => getComputedStyle(el).marginBottom") == "0px"
          )
          multiple = page.locator('.message[data-msg-id="bb0007"]')
          multiple.scroll_into_view_if_needed()
          paragraphs = multiple.locator(".answer.reply > div > p:last-child")
          assert paragraphs.count() == 2
          page.wait_for_function("""() => {
            const nodes = document.querySelectorAll('[data-msg-id=bb0007] .answer.reply > div > p:last-child');
            return nodes.length === 2 && getComputedStyle(nodes[0]).marginBottom === '8px'
              && getComputedStyle(nodes[1]).marginBottom === '0px';
          }""")
          assert short.locator(
            ".message-parents .reply-parent-chip"
          ).all_text_contents() == ["bb0001", "reference"]
          assert short.locator(
            ".message-attachments .receipt-filename"
          ).all_text_contents() == ["notes.txt (missing)", "other.txt (missing)"]
          image_button = short.get_by_role("button", name="View image layout.png")
          image_button.scroll_into_view_if_needed()
          page.wait_for_function(
            "selector => document.querySelector(selector)?.naturalWidth === 1",
            arg='.message[data-msg-id="bb0002"] .message-attachment-preview img',
          )
          assert s["parents"]["bottom"] <= s["bubble"]["y"] + 1, s
          assert (
            abs(
              s["parents"]["y"]
              + s["parents"]["height"] / 2
              - s["id"]["y"]
              - s["id"]["height"] / 2
            )
            <= 1
          ), s
          assert s["parentChips"][-1]["right"] <= s["id"]["x"] - 5, s
          assert abs(s["files"]["right"] - s["row"]["right"]) <= 1, s
          assert abs(s["attachments"][-1]["right"] - s["files"]["right"]) <= 1, s
          assert all(
            s["row"]["x"] <= attachment["x"]
            and attachment["right"] <= s["row"]["right"] + 1
            for attachment in s["attachments"]
          ), s
          full = boxes(long)
          assert full["bodyLines"] > 1, full
          assert abs(full["body"]["x"] - (full["bubble"]["x"] + 15)) <= 1, full
          assert full["bodyAlign"] == "left", full
          # A wrapped, body-driven bubble remains wide, with the small left
          # gutter shown in the correct long-message reference.
          assert full["bubble"]["width"] >= full["row"]["width"] - 22, full
          assert full["bubble"]["width"] <= full["row"]["width"] - 18, full
          assert full["ack"]["width"] >= full["row"]["width"] * 0.8, full
          for msg_id in ("bb0008", "bb0009"):
            forced_multiline = page.locator(f'.message[data-msg-id="{msg_id}"]')
            forced_multiline.scroll_into_view_if_needed()
            lines = boxes(forced_multiline)
            assert lines["bodyLines"] >= 2, lines
            assert abs(lines["body"]["x"] - (lines["bubble"]["x"] + 15)) <= 1, lines
            assert lines["bodyAlign"] == "left", lines
          intermediate = boxes(middle)
          assert (
            intermediate["row"]["width"] * 0.72 < intermediate["bubble"]["width"]
          ), intermediate
          assert (
            intermediate["bubble"]["width"] < intermediate["row"]["width"] * 0.85
          ), intermediate
          assert intermediate["ack"]["width"] >= intermediate["bubble"]["width"] - 31, (
            intermediate
          )
          assert (
            abs(intermediate["ack"]["right"] - (intermediate["bubble"]["right"] - 15))
            <= 1
          ), intermediate
          t = boxes(sent)
          assert t["task"]["right"] <= t["status"]["x"], t
          assert t["status"] == t["stamp"], t
          assert sent.locator(".receipt-status").inner_text().startswith("Sent ")
          assert seen.locator(".receipt-status").inner_text().startswith("Seen ")
          assert (
            not short.locator(".receipt-status")
            .inner_text()
            .startswith(("Sent ", "Seen "))
          )
          image_button.click()
          page.locator("#image-modal[open]").wait_for(state="visible")
          page.wait_for_function(
            "document.querySelector('#image-modal-stage > img')?.naturalWidth === 1"
          )
          page.keyboard.press("Escape")
          page.locator("#image-modal").wait_for(state="hidden")
          assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
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
@pytest.mark.parametrize("transport", ("poll", "ws"))
def test_wider_live_ack_keeps_reading_position(transport: str) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore()
  app = SteeringApp(store)
  for idx in range(10):
    body = (
      "First line  \nSecond line."
      if idx == 7
      else f"Message {idx}. " + "Earlier context stays on the page. " * 22
    )
    app.messages.send_message(body, msg_id=f"ac{idx:04d}", blocking=False)
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
        page.set_default_timeout(10000)
        errors: list[str] = []
        sockets: list[object] = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("websocket", lambda socket: sockets.append(socket))
        query = "?transport=poll" if transport == "poll" else ""
        page.goto(f"http://127.0.0.1:{server.server_port}/{query}")
        page.add_style_tag(
          content=""".message[data-msg-id="ac0006"] .message-text {
            width: calc(var(--message-row-width) * 0.78 - 30px);
          }"""
        )
        source = page.locator('.message[data-msg-id="ac0006"]')
        multiline = page.locator('.message[data-msg-id="ac0007"]')
        anchor = page.locator('.message[data-msg-id="ac0008"]')
        source.wait_for()
        assert "message-text-multiline" not in (
          source.locator(".message-bubble > .message-text:first-child").get_attribute(
            "class"
          )
          or ""
        )
        assert "message-text-multiline" in (
          multiline.locator(
            ".message-bubble > .message-text:first-child"
          ).get_attribute("class")
          or ""
        )
        anchor.scroll_into_view_if_needed()
        history = page.locator("#history")
        assert (
          history.evaluate("el => el.scrollHeight - el.scrollTop - el.clientHeight")
          > 100
        )
        if transport == "ws":
          assert sockets, "the websocket path must actually connect"
        else:
          assert not sockets, "the polling path must not open a websocket"
        offset = anchor.evaluate("""element =>
          element.getBoundingClientRect().top - document.querySelector('#history').getBoundingClientRect().top
        """)
        app.messages.ack("ac0006", "A new acknowledgement arrives. " * 75)
        source.locator(".answer.reply").get_by_text(
          "A new acknowledgement arrives.", exact=False
        ).wait_for()
        after = anchor.evaluate("""element =>
          element.getBoundingClientRect().top - document.querySelector('#history').getBoundingClientRect().top
        """)
        geometry = source.evaluate("""element => {
          const bubble = element.querySelector('.message-bubble').getBoundingClientRect();
          const ack = element.querySelector('.answer.reply').getBoundingClientRect();
          return {bubbleWidth:bubble.width, ackWidth:ack.width};
        }""")
        assert abs(after - offset) <= 30, (transport, offset, after)
        assert geometry["ackWidth"] >= geometry["bubbleWidth"] - 31, geometry
        assert "message-text-multiline" in (
          multiline.locator(
            ".message-bubble > .message-text:first-child"
          ).get_attribute("class")
          or ""
        )
        assert not errors, errors
      finally:
        browser.close()
  finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)
    store.close()


@pytest.mark.skipif(not os.environ.get("CHROMIUM_BIN"), reason="Set CHROMIUM_BIN")
@pytest.mark.parametrize("width", [390, 1050])
def test_short_message_acknowledgement_does_not_expand_bubble_to_full_row(
  tmp_path: Path,
  width: int,
) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore(tmp_path / "state.sqlite3")
  app = SteeringApp(store)
  app.messages.send_message(
    "ren it then to resume-turn", msg_id="ab1234", blocking=False
  )
  app.messages.ack(
    "ab1234",
    "I will rename the recipe to resume-turn.md and update its references without changing its instructions.",
  )
  app.messages.send_message("Body-driven width.", msg_id="ab1235", blocking=False)
  app.messages.ack("ab1235", "A longer acknowledgement. " * 30)
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
          viewport={"width": width, "height": 500}, reduced_motion="reduce"
        )
        page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
        card = page.locator('.message[data-msg-id="ab1234"]')
        card.wait_for()
        widths = page.wait_for_function("""() => {
          const el = document.querySelector('[data-msg-id=ab1234]');
          const bubble = el?.querySelector('.message-bubble')?.getBoundingClientRect();
          const row = el?.getBoundingClientRect();
          return bubble?.width && row?.width &&
            {bubble: bubble.width, row: row.width, right: bubble.right, rowRight: row.right};
        }""").json_value()
        assert abs(widths["right"] - widths["rowRight"]) <= 1, widths
        log_reply_cap = 900 * 2 / 3
        if width == 390:
          assert widths["bubble"] > widths["row"] * 0.8, widths
        else:
          assert widths["bubble"] <= log_reply_cap + 1, widths
          assert widths["bubble"] > widths["row"] * 0.6, widths
        page.screenshot(path=str(tmp_path / f"ack-cap-{width}.png"))
        page.add_style_tag(
          content=(
            '.message[data-msg-id="ab1235"] .message-text '
            "{ width: calc(var(--message-row-width) * 0.78 - 30px); }"
          )
        )
        wide = page.locator('.message[data-msg-id="ab1235"]')
        wide.wait_for()
        if width == 1050:
          page.wait_for_function(
            "document.querySelector('[data-msg-id=ab1235]')?.hasAttribute('data-message-wide')"
          )
        wide_widths = wide.evaluate("""el => ({
          bubble: el.querySelector('.message-bubble').getBoundingClientRect().width,
          ack: el.querySelector('.answer.reply').getBoundingClientRect().width,
        })""")
        assert wide_widths["ack"] >= wide_widths["bubble"] - 31, wide_widths
      finally:
        browser.close()
  finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)
    store.close()


@pytest.mark.skipif(
  not os.environ.get("CHROMIUM_BIN"), reason="Set CHROMIUM_BIN for Chromium"
)
def test_wrapped_task_chips_have_vertical_spacing(tmp_path: Path) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore(tmp_path / "state.sqlite3")
  app = SteeringApp(store)
  app.messages.send_message("Linked work.", msg_id="bb1010", blocking=False)
  for i in range(8):
    app.tasks.create_task(
      f"linked-task-{i}", f"Task {i}", size=1, details=["Review"], msg_ids=["bb1010"]
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
        chips = page.locator(
          '.message[data-msg-id="bb1010"] .receipt-task-links button'
        )
        chips.first.wait_for()
        assert chips.count() == 8
        assert (
          chips.first.locator("code").evaluate("el => getComputedStyle(el).fontSize")
          == "11px"
        )
        first = chips.first
        before = first.evaluate(
          "el => ({radius: getComputedStyle(el).borderRadius, box: el.getBoundingClientRect().toJSON()})"
        )
        first.hover()
        after = first.evaluate(
          "el => ({radius: getComputedStyle(el).borderRadius, box: el.getBoundingClientRect().toJSON()})"
        )
        assert after["radius"] == before["radius"]
        assert after["box"]["width"] == pytest.approx(before["box"]["width"])
        assert after["box"]["height"] == pytest.approx(before["box"]["height"])
        rects = chips.evaluate_all(
          "els => els.map(el => el.getBoundingClientRect().toJSON())"
        )
        rows = {}
        for rect in rects:
          rows.setdefault(round(rect["y"]), []).append(rect)
        assert len(rows) > 1
        ordered = [rows[y] for y in sorted(rows)]
        for before, after in itertools.pairwise(ordered):
          assert (
            min(item["y"] for item in after) - max(item["bottom"] for item in before)
            >= 3
          )
        assert any(len(row) > 1 for row in ordered)
        for row in ordered:
          for left, right in itertools.pairwise(row):
            assert 0 < right["x"] - left["right"] < 8
        page.screenshot(path=str(tmp_path / "wrapped-task-chips.png"))
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
def test_message_chip_rows_keep_height_and_align_text(tmp_path: Path) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore(tmp_path / "state.sqlite3")
  app = SteeringApp(store)
  app.messages.send_message("No chips", msg_id="cc0001", blocking=False)
  app.messages.send_message(
    "Parent chip",
    msg_id="cc0002",
    blocking=False,
    parent_refs=[{"type": "message", "id": "cc0001"}],
  )
  app.messages.send_message("Task chip", msg_id="cc0003", blocking=False)
  app.tasks.create_task(
    "chip-task", "Chip task", size=1, details=["Review"], msg_ids=["cc0003"]
  )
  server = create_http_server(app, host="0.0.0.0", port=0)
  thread = threading.Thread(target=server.serve_forever, daemon=True)
  thread.start()
  try:
    with playwright.sync_playwright() as runner:
      browser = runner.chromium.launch(
        executable_path=os.environ["CHROMIUM_BIN"], args=["--no-sandbox"]
      )
      try:
        for width in (390, 1200):
          page = browser.new_page(viewport={"width": width, "height": 800})
          page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
          page.locator('.message[data-msg-id="cc0003"] .reply-parent-chip').wait_for()
          geometry = page.evaluate("""() => {
            const el = (id, selector) => document.querySelector(`[data-msg-id="${id}"] ${selector}`);
            const height = node => node.getBoundingClientRect().height;
            const textCenter = node => {
              const range = document.createRange();
              range.selectNodeContents(node);
              const box = range.getBoundingClientRect();
              return box.top + box.height / 2;
            };
            return {
              plainHeading: height(el('cc0001', '.message-heading')),
              parentHeading: height(el('cc0002', '.message-heading')),
              plainReceipt: height(el('cc0001', '.receipt')),
              taskReceipt: height(el('cc0003', '.receipt')),
              parentDelta: Math.abs(textCenter(el('cc0002', '.reply-parent-chip code')) -
                textCenter(el('cc0002', '.msg-id code'))),
              taskDelta: Math.abs(textCenter(el('cc0003', '.reply-parent-chip code')) -
                textCenter(el('cc0003', '.receipt-status'))),
            };
          }""")
          assert abs(geometry["plainHeading"] - geometry["parentHeading"]) <= 0.5, (
            geometry
          )
          assert abs(geometry["plainReceipt"] - geometry["taskReceipt"]) <= 0.5, (
            geometry
          )
          assert geometry["parentDelta"] <= 1, geometry
          assert geometry["taskDelta"] <= 1, geometry
          page.screenshot(path=str(tmp_path / f"chip-row-{width}.png"))
          page.close()
      finally:
        browser.close()
  finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)
    store.close()
