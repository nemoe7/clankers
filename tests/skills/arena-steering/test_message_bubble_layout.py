"""Browser geometry and receipt regressions for right-aligned Messages bubbles."""

from __future__ import annotations

import base64
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
          assert s["bubble"]["width"] <= s["row"]["width"] * 0.72, s
          assert s["ack"]["width"] <= s["row"]["width"] * 2 / 3 + 1, s
          assert abs(s["ack"]["width"] - (s["bubble"]["width"] - 30)) <= 1, s
          assert s["ackBorderLeft"] == "0px" and s["ackBorderRight"] == "2px", s
          assert abs(s["ack"]["right"] - (s["bubble"]["right"] - 15)) <= 1, s
          assert short.locator(
            ".message-parents .reply-parent-chip"
          ).all_text_contents() == ["bb0001", "reference"]
          assert short.locator(
            ".message-attachments .receipt-filename"
          ).all_inner_texts() == ["notes.txt (missing)", "other.txt (missing)"]
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
          assert full["bubble"]["width"] >= full["row"]["width"] - 2, full
          assert full["ack"]["width"] >= full["row"]["width"] * 0.8, full
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
          assert t["status"]["right"] <= t["stamp"]["x"], t
          assert sent.locator(".receipt-status").inner_text() == "Sent"
          assert seen.locator(".receipt-status").inner_text() == "Seen"
          assert short.locator(".receipt-status").inner_text() == ""
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
    app.messages.send_message(
      f"Message {idx}. " + "Earlier context stays on the page. " * 22,
      msg_id=f"ac{idx:04d}",
      blocking=False,
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
        anchor = page.locator('.message[data-msg-id="ac0008"]')
        source.wait_for()
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
        assert not errors, errors
      finally:
        browser.close()
  finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)
    store.close()
