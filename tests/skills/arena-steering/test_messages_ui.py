"""Steering regression tests."""

from __future__ import annotations

import base64
import itertools
import os
import subprocess
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest
from arena_steering.models import Attachment
from arena_steering.server import SteeringApp, create_http_server
from arena_steering.store import SqliteStore


@contextmanager
def composer_page(width: int, state_path: Path | None = None) -> Iterator[object]:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore(state_path) if state_path else SqliteStore()
  server = create_http_server(SteeringApp(store), host="127.0.0.1", port=0)
  thread = threading.Thread(target=server.serve_forever, daemon=True)
  thread.start()
  try:
    with playwright.sync_playwright() as runner:
      browser = runner.chromium.launch(
        executable_path=os.environ["ARENA_STEERING_CHROMIUM"],
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage"],
      )
      context = browser.new_context(
        viewport={"width": width, "height": 800}, reduced_motion="reduce"
      )
      page = context.new_page()
      page.goto(
        f"http://127.0.0.1:{server.server_port}/?transport=poll",
        wait_until="domcontentloaded",
      )
      page.locator("#msg").wait_for()
      yield page
      context.close()
      browser.close()
  finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)
    store.close()


def box(page: object, selector: str) -> dict[str, float]:
  return page.locator(selector).bounding_box()


@pytest.mark.skipif(
  not os.environ.get("ARENA_STEERING_CHROMIUM"),
  reason="Set ARENA_STEERING_CHROMIUM to run the browser regression",
)
@pytest.mark.parametrize("width", [1200, 390])
def test_composer_grows_previews_and_expands_like_v1(width: int) -> None:
  with composer_page(width) as page:
    draft = page.locator("#msg")
    expand = page.locator("#composer-expand")
    preview = page.locator("#preview-msg")
    assert expand.is_hidden()
    preview.click()
    assert draft.is_visible()
    assert preview.get_attribute("aria-pressed") == "false"
    assert preview.get_attribute("data-tooltip") == "Write something first"

    text = (
      "A long line that wraps on narrow screens. " * 4
    ) + "\nSecond **line**.\nThird line."
    draft.fill(text)
    assert not expand.is_hidden()
    assert box(page, "#msg")["height"] > 65
    assert box(page, "#msg")["x"] - box(page, "#compose")["x"] < 20
    assert (
      box(page, "#attach-file")["y"]
      >= box(page, "#msg")["y"] + box(page, "#msg")["height"]
    )
    assert box(page, "#send")["y"] == pytest.approx(
      box(page, "#attach-file")["y"], abs=1
    )
    assert box(page, "#composer-expand")["y"] < box(page, "#attach-file")["y"]

    preview.click()
    panel = page.locator("#draft-preview")
    assert draft.is_hidden() and panel.is_visible()
    assert panel.locator("strong").inner_text() == "line"
    assert box(page, "#draft-preview")["height"] >= 112
    assert box(page, "#draft-preview")["width"] > box(page, "#compose")["width"] - 25
    assert (
      page.evaluate(
        "getComputedStyle(document.querySelector('#draft-preview')).borderTopWidth"
      )
      == "1px"
    )
    assert (
      box(page, "#send")["y"]
      >= box(page, "#draft-preview")["y"] + box(page, "#draft-preview")["height"]
    )

    # A store update and expansion must not switch a preview back to write mode.
    page.locator("#quiet-msgs").click()
    assert (
      panel.is_visible()
      and page.locator("#preview-msg").get_attribute("aria-pressed") == "true"
    )
    expand.click()
    assert page.locator("#composer-expand").get_attribute("aria-expanded") == "true"
    assert panel.is_visible() and draft.is_hidden()
    assert not page.locator("#history").is_visible()
    assert box(page, "#compose")["height"] > 400
    assert page.locator("#composer-expand .lucide-minimize-2").count() == 1
    expand.click()
    assert panel.is_visible()
    preview.click()
    assert draft.is_visible() and draft.input_value() == text
    assert page.evaluate("document.activeElement.id") == "msg"
    draft.fill("")
    assert expand.is_hidden()


@pytest.mark.skipif(
  not os.environ.get("ARENA_STEERING_CHROMIUM"),
  reason="Set ARENA_STEERING_CHROMIUM to run the browser regression",
)
@pytest.mark.parametrize("width", [1200, 390])
def test_composer_scrolls_only_when_content_overflows(width: int) -> None:
  with composer_page(width) as page:
    draft = page.locator("#msg")
    draft.fill("One line")
    assert draft.evaluate("el => el.scrollHeight <= el.clientHeight")
    assert draft.evaluate("el => getComputedStyle(el).overflowY") == "hidden"
    draft.fill("Long line\n" * 100)
    assert draft.evaluate("el => el.scrollHeight > el.clientHeight")
    assert draft.evaluate("el => getComputedStyle(el).overflowY") == "auto"
    page.locator("#composer-expand").click()
    assert draft.evaluate("el => el.scrollHeight > el.clientHeight")
    assert draft.evaluate("el => getComputedStyle(el).overflowY") == "auto"
    draft.fill("One line")
    assert draft.evaluate("el => el.scrollHeight <= el.clientHeight")
    assert draft.evaluate("el => getComputedStyle(el).overflowY") == "hidden"


@pytest.mark.skipif(
  not os.environ.get("ARENA_STEERING_CHROMIUM"),
  reason="Set ARENA_STEERING_CHROMIUM to run the browser regression",
)
def test_composer_reflows_when_the_viewport_narrows() -> None:
  with composer_page(1200) as page:
    draft = page.locator("#msg")
    draft.fill("A sentence that fits on a wide screen but wraps on a narrow screen.")
    page.set_viewport_size({"width": 390, "height": 800})
    page.wait_for_function(
      """() => {
        const el = document.querySelector('#msg');
        return el.scrollHeight <= el.clientHeight || getComputedStyle(el).overflowY === 'auto';
      }"""
    )


@pytest.mark.skipif(
  not os.environ.get("ARENA_STEERING_CHROMIUM"),
  reason="Set ARENA_STEERING_CHROMIUM to run the browser regression",
)
@pytest.mark.parametrize("width", [1200, 390])
def test_staged_files_use_v1_layout_and_image_thumbnails(width: int) -> None:
  image = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+lmGQAAAAASUVORK5CYII="
  )
  with composer_page(width) as page:
    page.locator("#composer-file-input").set_input_files(
      {"name": "example.png", "mimeType": "image/png", "buffer": image}
    )
    chip = page.locator(".composer-attachment-chip")
    chip.wait_for()
    page.wait_for_function(
      "document.querySelector('.composer-attachment-chip')?.dataset.uploadStatus === 'ready'"
    )
    assert chip.locator("img").get_attribute("alt") == "example.png"
    assert box(page, ".composer-attachment-chip")["height"] == pytest.approx(40, abs=1)
    assert box(page, "#composer-attachments")["y"] < box(page, "#msg")["y"]
    assert box(page, "#attach-file")["y"] > box(page, "#msg")["y"]
    chip.locator("button[aria-label='Remove example.png']").click()
    assert page.locator("#composer-attachments").is_hidden()


@pytest.mark.skipif(
  not os.environ.get("ARENA_STEERING_CHROMIUM"),
  reason="Set ARENA_STEERING_CHROMIUM to run the browser regression",
)
def test_send_waits_for_an_inflight_upload_and_retries_a_failure() -> None:
  with composer_page(1200) as page:
    page.evaluate("""() => {
      const original = window.fetch.bind(window);
      window.uploadCalls = 0;
      window.fetch = async (...args) => {
        if (String(args[0]).endsWith('/uploads')) {
          window.uploadCalls++;
          if (window.uploadCalls === 1) {
            await new Promise(resolve => { window.releaseUpload = resolve; });
            return new Response(JSON.stringify({error: 'offline'}), {status: 503});
          }
        }
        return original(...args);
      };
    }""")
    page.locator("#msg").fill("Please inspect this file")
    page.locator("#composer-file-input").set_input_files(
      {"name": "file.txt", "mimeType": "text/plain", "buffer": b"file contents"}
    )
    page.wait_for_function("typeof window.releaseUpload === 'function'")
    assert page.locator("#send").is_enabled()
    page.locator("#send").click()
    assert page.locator("#send").is_disabled()
    assert page.locator("#send").get_attribute("aria-busy") == "true"
    assert page.locator("#send .lucide-loader-circle").count() == 1
    assert (
      page.locator("#send svg").evaluate("e => getComputedStyle(e).animationName")
      == "none"
    )
    assert (
      page.locator("#history .message")
      .filter(has_text="Please inspect this file")
      .is_visible()
    )
    page.evaluate("window.releaseUpload()")
    page.wait_for_function("window.uploadCalls === 2")
    page.wait_for_function(
      "Array.from(document.querySelectorAll('#history .message'))"
      ".some(e => e.textContent.includes('Please inspect this file'))"
    )
    page.locator("#composer-attachments").wait_for(state="hidden")
    page.wait_for_function("document.querySelector('#msg')?.value === ''")


@pytest.mark.skipif(
  not os.environ.get("ARENA_STEERING_CHROMIUM"),
  reason="Set ARENA_STEERING_CHROMIUM to run the browser regression",
)
def test_pasting_an_image_with_text_preserves_the_text() -> None:
  image = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+lmGQAAAAASUVORK5CYII="
  )
  with composer_page(1200) as page:
    prevented = page.locator("#msg").evaluate(
      """(target, bytes) => {
      const data = new DataTransfer();
      data.items.add(new File([new Uint8Array(bytes)], 'image.png', {type: 'image/png'}));
      data.setData('text/plain', 'Keep this text');
      const event = new ClipboardEvent('paste', {clipboardData: data, bubbles: true, cancelable: true});
      target.dispatchEvent(event);
      return event.defaultPrevented;
    }""",
      list(image),
    )
    assert not prevented
    page.locator(".composer-attachment-chip img").wait_for()


@pytest.mark.skipif(
  not os.environ.get("ARENA_STEERING_CHROMIUM"),
  reason="Set ARENA_STEERING_CHROMIUM to run the browser regression",
)
def test_preview_matches_server_markdown_and_paragraph_breaks() -> None:
  with composer_page(1200) as page:
    page.locator("#msg").fill("First line\nSecond **line**\n\nSeparate paragraph")
    page.locator("#preview-msg").click()
    preview = page.locator("#draft-preview")
    page.wait_for_function(
      "document.querySelector('#draft-preview strong')?.textContent === 'line'"
    )
    assert preview.locator("p").count() == 2
    first = preview.locator("p").first
    assert first.locator("br").count() == 0
    assert first.inner_text() == "First line\nSecond line"
    spacing = first.evaluate("""p => {
      const text = p.firstChild;
      const at = text.textContent.indexOf('\\n');
      const firstLine = document.createRange();
      firstLine.setStart(text, 0); firstLine.setEnd(text, at);
      const secondLine = document.createRange();
      secondLine.setStart(text, at + 1); secondLine.setEnd(text, text.textContent.length);
      return {
        gap: secondLine.getBoundingClientRect().top - firstLine.getBoundingClientRect().top,
        lineHeight: parseFloat(getComputedStyle(p).lineHeight),
      };
    }""")
    assert spacing["gap"] == pytest.approx(spacing["lineHeight"], abs=1)
    assert preview.locator("p").nth(1).inner_text() == "Separate paragraph"


@pytest.mark.skipif(
  not os.environ.get("ARENA_STEERING_CHROMIUM"),
  reason="Set ARENA_STEERING_CHROMIUM to run the browser regression",
)
def test_draft_survives_a_new_browser_tab() -> None:
  with composer_page(1200) as page:
    page.locator("#msg").fill("Keep this draft across tabs")
    second = page.context.new_page()
    second.goto(page.url, wait_until="domcontentloaded")
    second.locator("#msg").wait_for()
    assert second.locator("#msg").input_value() == "Keep this draft across tabs"
    second.close()


@pytest.mark.skipif(
  not os.environ.get("ARENA_STEERING_CHROMIUM"),
  reason="Set ARENA_STEERING_CHROMIUM to run the browser regression",
)
def test_failed_upload_does_not_send_or_discard_the_draft() -> None:
  with composer_page(1200) as page:
    page.evaluate("""() => {
      const original = window.fetch.bind(window);
      window.uploadIds = [];
      window.allowUploads = false;
      window.fetch = async (...args) => {
        if (String(args[0]).endsWith('/uploads')) {
          window.uploadIds.push(args[1].body.get('_request_id'));
          if (!window.allowUploads) return new Response(JSON.stringify({error: 'offline'}), {
            status: 503, headers: {'content-type': 'application/json'}
          });
        }
        return original(...args);
      };
    }""")
    page.locator("#msg").fill("Do not lose this draft")
    page.locator("#composer-file-input").set_input_files(
      {"name": "file.txt", "mimeType": "text/plain", "buffer": b"contents"}
    )
    page.wait_for_function(
      "document.querySelector('.composer-attachment-chip')?.dataset.uploadStatus === 'failed'"
    )
    page.locator("#send").click()
    page.wait_for_function("window.uploadIds.length >= 2")
    page.get_by_role("status").filter(has_text="A file did not upload").wait_for()
    assert page.evaluate("window.uploadIds[0] === window.uploadIds[1]")
    assert page.locator("#msg").input_value() == "Do not lose this draft"
    assert page.locator(".composer-attachment-chip").count() == 1
    assert page.locator("#history .message").count() == 0
    assert page.locator("#retry-send").count() == 0
    page.evaluate("window.allowUploads = true")
    page.locator("#send").click()
    page.wait_for_function(
      "Array.from(document.querySelectorAll('#history .message'))"
      ".some(e => e.textContent.includes('Do not lose this draft'))"
    )
    page.wait_for_function("document.querySelector('#msg')?.value === ''")


@pytest.mark.skipif(
  not os.environ.get("ARENA_STEERING_CHROMIUM"),
  reason="Set ARENA_STEERING_CHROMIUM to run the browser regression",
)
def test_unconfirmed_send_retries_without_duplicate_or_losing_reply() -> None:
  with composer_page(1200) as page:
    response = page.request.post(
      page.url.split("/?", 1)[0] + "/messages",
      data={"id": "aaaa01", "body": "Parent message"},
    )
    assert response.ok
    page.wait_for_selector('button.receipt-id[data-parent-id="aaaa01"]', timeout=6000)
    page.locator('button.receipt-id[data-parent-id="aaaa01"]').click()
    assert (
      page.locator(
        '#composer-reply-bar .composer-reply-chip[data-parent-id="aaaa01"]'
      ).count()
      == 1
    )
    page.evaluate("""() => {
      const original = window.fetch.bind(window);
      window.firstSend = true;
      window.fetch = async (...args) => {
        const result = await original(...args);
        if (window.firstSend && String(args[0]).endsWith('/messages') && args[1]?.method === 'POST') {
          window.firstSend = false;
          return new Response(JSON.stringify({error: 'response lost'}), {
            status: 503, headers: {'content-type': 'application/json'}
          });
        }
        return result;
      };
    }""")
    page.locator("#msg").fill("Reply once despite a lost response")
    page.locator("#send").click()
    page.locator("#retry-send").wait_for(timeout=6000)
    assert (
      page.locator(
        '#composer-reply-bar .composer-reply-chip[data-parent-id="aaaa01"]'
      ).count()
      == 1
    )
    assert page.locator("#msg").input_value() == "Reply once despite a lost response"
    page.locator("#retry-send").click()
    page.wait_for_function("!document.querySelector('#retry-send')")
    page.wait_for_function(
      "Array.from(document.querySelectorAll('#history .message'))"
      ".some(e => e.textContent.includes('Reply once despite a lost response'))"
    )
    matching = page.locator("#history .message").filter(
      has_text="Reply once despite a lost response"
    )
    assert matching.count() == 1
    assert (
      matching.locator(
        '.reply-parent-chip[data-reference-type="message"][data-reference-id="aaaa01"]'
      ).count()
      == 1
    )
    assert page.locator("#msg").input_value() == ""


@pytest.mark.skipif(
  not os.environ.get("ARENA_STEERING_CHROMIUM"),
  reason="Set ARENA_STEERING_CHROMIUM to run the browser regression",
)
def test_drop_anywhere_in_messages_stages_one_file_after_rerenders() -> None:
  with composer_page(1200) as page:
    page.locator("#quiet-msgs").click()
    page.locator("#quiet-msgs").click()
    prevented = page.locator("#history").evaluate("""target => {
      const data = new DataTransfer();
      data.items.add(new File(['text'], 'dropped.txt', {type: 'text/plain'}));
      const event = new DragEvent('drop', {dataTransfer: data, bubbles: true, cancelable: true});
      target.dispatchEvent(event);
      return event.defaultPrevented;
    }""")
    assert prevented
    page.locator(".composer-attachment-chip").wait_for()
    assert page.locator(".composer-attachment-chip").count() == 1


@pytest.mark.skipif(
  not os.environ.get("ARENA_STEERING_CHROMIUM"),
  reason="Set ARENA_STEERING_CHROMIUM to run the browser regression",
)
def test_stale_preview_response_cannot_replace_the_new_draft() -> None:
  with composer_page(1200) as page:
    page.evaluate("""() => {
      const original = window.fetch.bind(window);
      window.fetch = async (...args) => {
        if (String(args[0]).endsWith('/markdown') && JSON.parse(args[1].body).markdown === 'old draft') {
          await new Promise(resolve => { window.releaseOldPreview = resolve; });
        }
        return original(...args);
      };
    }""")
    page.locator("#msg").fill("old draft")
    page.locator("#preview-msg").click()
    page.wait_for_function("typeof window.releaseOldPreview === 'function'")
    page.locator("#preview-msg").click()
    page.locator("#msg").fill("new draft")
    page.locator("#preview-msg").click()
    preview = page.locator("#draft-preview")
    preview.get_by_text("new draft").wait_for()
    page.evaluate("window.releaseOldPreview()")
    page.evaluate(
      "new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))"
    )
    assert "new draft" in preview.inner_text()
    assert "old draft" not in preview.inner_text()


@pytest.mark.skipif(
  not os.environ.get("ARENA_STEERING_CHROMIUM"),
  reason="Set ARENA_STEERING_CHROMIUM to run the browser regression",
)
def test_confirmed_send_clears_draft_without_waiting_for_refresh() -> None:
  with composer_page(1200) as page:
    page.evaluate("""() => {
      const original = window.fetch.bind(window);
      window.afterSend = false;
      window.fetch = async (...args) => {
        const url = String(args[0]);
        if (window.afterSend && url.endsWith('/health')) {
          await new Promise(resolve => { window.releaseHealth = resolve; });
        }
        const result = await original(...args);
        if (url.endsWith('/messages') && args[1]?.method === 'POST' && result.ok) {
          window.afterSend = true;
        }
        return result;
      };
    }""")
    page.locator("#msg").fill("Sent while refresh is slow")
    page.locator("#send").click()
    page.wait_for_function('typeof window.releaseHealth === "function"')
    try:
      page.wait_for_function(
        "document.querySelector('#msg')?.value === ''", timeout=3000
      )
    finally:
      page.evaluate("window.releaseHealth()")


@pytest.mark.skipif(
  not os.environ.get("ARENA_STEERING_CHROMIUM"),
  reason="Set ARENA_STEERING_CHROMIUM to run the browser regression",
)
@pytest.mark.parametrize("width", [1200, 390])
def test_send_shows_message_before_network_response(tmp_path: Path, width: int) -> None:
  with composer_page(width) as page:
    page.evaluate("""() => {
      const original = window.fetch.bind(window);
      window.releaseSend = null;
      window.fetch = async (...args) => {
        if (String(args[0]).endsWith('/messages') && args[1]?.method === 'POST') {
          await new Promise(resolve => { window.releaseSend = resolve; });
        }
        return original(...args);
      };
    }""")
    page.locator("#msg").fill("Immediate message")
    page.locator("#send").click()
    page.wait_for_function("window.releaseSend !== null")
    assert (
      page.locator("#history .message")
      .filter(has_text="Immediate message")
      .is_visible()
    )
    assert (
      page.locator("#history .message")
      .filter(has_text="Immediate message")
      .get_by_text("Sending")
      .is_visible()
    )
    pending_id = (
      page.locator("#history .message")
      .filter(has_text="Immediate message")
      .locator(".msg-id")
    )
    assert pending_id.inner_text() == "xxxxxx"
    pending_font = pending_id.evaluate("el => getComputedStyle(el).fontFamily")
    pending_width = pending_id.bounding_box()["width"]
    page.evaluate("""() => {
      window.pendingCard = document.querySelector('#history .message:last-child');
      window.pendingBubble = window.pendingCard.querySelector('.message-bubble');
      window.pendingBackground = getComputedStyle(window.pendingBubble).backgroundColor;
    }""")
    assert page.locator("#msg").input_value() == ""
    page.screenshot(path=str(tmp_path / f"optimistic-send-{width}.png"))
    page.evaluate("window.releaseSend()")
    page.wait_for_function("!document.querySelector('#send')?.disabled")
    message = page.locator("#history .message").filter(has_text="Immediate message")
    assert message.count() == 1
    confirmed_id = message.locator("button.receipt-id code.msg-id")
    confirmed_id.wait_for()
    page.screenshot(path=str(tmp_path / f"confirmed-send-{width}.png"))
    assert message.evaluate(
      "el => el === window.pendingCard && "
      "el.querySelector('.message-bubble') === window.pendingBubble && "
      "getComputedStyle(window.pendingBubble).backgroundColor === window.pendingBackground"
    )
    assert (
      confirmed_id.evaluate("el => getComputedStyle(el).fontFamily") == pending_font
    )
    assert abs(confirmed_id.bounding_box()["width"] - pending_width) < 1


@pytest.mark.skipif(
  not os.environ.get("ARENA_STEERING_CHROMIUM"),
  reason="Set ARENA_STEERING_CHROMIUM to run the browser regression",
)
def test_optimistic_send_reconciles_refresh_before_delayed_response() -> None:
  with composer_page(1200) as page:
    page.evaluate("""() => {
      const original = window.fetch.bind(window);
      window.sendCommitted = false;
      window.fetch = async (...args) => {
        const response = await original(...args);
        if (String(args[0]).endsWith('/messages') && args[1]?.method === 'POST') {
          window.pendingCard = document.querySelector('#history .message:last-child');
          window.sendCommitted = true;
          await new Promise(resolve => { window.releaseSendResponse = resolve; });
        }
        return response;
      };
    }""")
    page.locator("#msg").fill("Only one copy while a response is delayed")
    page.locator("#send").click()
    page.wait_for_function("window.sendCommitted")
    page.wait_for_timeout(4000)
    matching = page.locator("#history .message").filter(
      has_text="Only one copy while a response is delayed"
    )
    assert matching.count() == 1
    assert matching.evaluate("el => el === window.pendingCard")
    assert page.locator("#msg").input_value() == ""
    page.evaluate("window.releaseSendResponse()")
    page.wait_for_function("!document.querySelector('#send')?.disabled")
    assert matching.count() == 1


@pytest.mark.skipif(
  not os.environ.get("ARENA_STEERING_CHROMIUM"),
  reason="Set ARENA_STEERING_CHROMIUM to run the browser regression",
)
def test_optimistic_send_failure_preserves_new_draft() -> None:
  with composer_page(1200) as page:
    page.evaluate("""() => {
      const original = window.fetch.bind(window);
      window.fetch = async (...args) => {
        if (String(args[0]).endsWith('/messages') && args[1]?.method === 'POST') {
          await new Promise(resolve => { window.failSend = resolve; });
          return new Response(JSON.stringify({error: 'offline'}), {
            status: 503, headers: {'content-type': 'application/json'}
          });
        }
        return original(...args);
      };
    }""")
    page.locator("#msg").fill("First draft")
    page.locator("#send").click()
    page.wait_for_function("typeof window.failSend === 'function'")
    assert page.locator("#msg").input_value() == ""
    page.locator("#msg").fill("A newer draft")
    page.evaluate("window.failSend()")
    page.locator("#retry-send").wait_for()
    assert page.locator("#msg").input_value() == "A newer draft"
    assert page.locator("#retry-send").is_visible()


@pytest.mark.skipif(
  not os.environ.get("ARENA_STEERING_CHROMIUM"),
  reason="Set ARENA_STEERING_CHROMIUM to run the browser regression",
)
def test_optimistic_send_clears_reply_selection_and_restores_on_failure() -> None:
  with composer_page(1200) as page:
    response = page.request.post(
      page.url.split("/?", 1)[0] + "/messages",
      data={"id": "aaaa02", "body": "A parent"},
    )
    assert response.ok
    parent = page.locator('button.receipt-id[data-parent-id="aaaa02"]')
    parent.wait_for(timeout=6000)
    parent.click()
    page.evaluate("""() => {
      const original = window.fetch.bind(window);
      window.fetch = async (...args) => {
        if (String(args[0]).endsWith('/messages') && args[1]?.method === 'POST') {
          await new Promise(resolve => { window.failSend = resolve; });
          return new Response(JSON.stringify({error: 'offline'}), {
            status: 503, headers: {'content-type': 'application/json'}
          });
        }
        return original(...args);
      };
    }""")
    page.locator("#msg").fill("Reply waiting")
    page.locator("#send").click()
    page.wait_for_function("typeof window.failSend === 'function'")
    assert (
      page.locator(
        '#composer-reply-bar .composer-reply-chip[data-parent-id="aaaa02"]'
      ).count()
      == 0
    )
    assert (
      page.locator("#history .message").filter(has_text="Reply waiting").is_visible()
    )
    page.evaluate("window.failSend()")
    page.locator("#retry-send").wait_for()
    assert (
      page.locator(
        '#composer-reply-bar .composer-reply-chip[data-parent-id="aaaa02"]'
      ).count()
      == 1
    )
    assert page.locator("#msg").input_value() == "Reply waiting"


@pytest.mark.skipif(
  not os.environ.get("ARENA_STEERING_CHROMIUM"),
  reason="Set ARENA_STEERING_CHROMIUM to run the browser regression",
)
def test_send_during_delayed_pagination_preserves_older_messages() -> None:
  with composer_page(1200) as page:
    url = page.url.split("/?", 1)[0]
    for index in range(25):
      response = page.request.post(
        url + "/messages", data={"id": f"{index:06x}", "body": f"Old message {index}"}
      )
      assert response.ok
    page.reload()
    page.locator("#load-older-messages").wait_for()
    page.evaluate("""() => {
      const original = window.fetch.bind(window);
      window.heldOlder = false;
      window.fetch = async (...args) => {
        if (!window.heldOlder && String(args[0]).includes('/messages?') && String(args[0]).includes('before=')) {
          window.heldOlder = true;
          await new Promise(resolve => { window.releaseOlder = resolve; });
        }
        return original(...args);
      };
    }""")
    page.evaluate("document.querySelector('#load-older-messages').click()")
    page.wait_for_function("typeof window.releaseOlder === 'function'")
    page.locator("#msg").fill("Send while loading older")
    page.locator("#send").click()
    assert (
      page.locator("#history .message")
      .filter(has_text="Send while loading older")
      .is_visible()
    )
    page.evaluate("window.releaseOlder()")
    page.wait_for_function("!document.querySelector('#send')?.disabled")
    page.wait_for_function(
      "Array.from(document.querySelectorAll('#history .message')).some(e => e.textContent.includes('Old message 0'))"
    )
    assert (
      page.locator("#history .message")
      .filter(has_text="Send while loading older")
      .count()
      == 1
    )


@pytest.mark.skipif(
  not os.environ.get("ARENA_STEERING_CHROMIUM"),
  reason="Set ARENA_STEERING_CHROMIUM to run the browser regression",
)
@pytest.mark.parametrize("fail", [False, True])
@pytest.mark.parametrize("width", [1200, 390])
def test_skip_poll_feedback_is_immediate_and_recovers(
  fail: bool, width: int, tmp_path: Path
) -> None:
  with composer_page(width) as page:
    page.evaluate(
      """fail => {
      const original = window.fetch.bind(window);
      window.fetch = async (...args) => {
        if (String(args[0]) === '/poll/skip' && args[1]?.method === 'POST') {
          await new Promise(resolve => { window.releaseSkip = resolve; });
          if (fail) return new Response(JSON.stringify({error:'offline'}), {
            status:503, headers:{'content-type':'application/json'}
          });
        }
        return original(...args);
      };
    }""",
      fail,
    )
    page.locator("#skip-poll").click()
    page.wait_for_function("typeof window.releaseSkip === 'function'")
    assert page.locator("#skip-poll").get_attribute("data-state") == "good"
    page.screenshot(path=str(tmp_path / f"skip-poll-{width}.png"))
    page.evaluate("window.releaseSkip()")
    if fail:
      page.wait_for_function(
        "document.querySelector('#skip-poll')?.dataset.state === 'bad'"
      )
      assert "offline" in page.locator("#skip-poll").get_attribute("title")
      page.locator("#quiet-msgs").click()
      assert page.locator("#skip-poll").get_attribute("data-state") == "bad"
    else:
      page.wait_for_function(
        "document.querySelector('#skip-poll')?.dataset.state === 'good'"
      )


@pytest.mark.skipif(
  not os.environ.get("ARENA_STEERING_CHROMIUM"),
  reason="Set ARENA_STEERING_CHROMIUM to run the browser regression",
)
@pytest.mark.parametrize("width", [1200, 390])
def test_survey_modal_opens_before_fetch_and_stays_closed_after_release(
  tmp_path: Path, width: int
) -> None:
  with composer_page(width) as page:
    page.evaluate("""() => {
      const original = window.fetch.bind(window);
      window.fetch = async (...args) => {
        if (String(args[0]) === '/survey') {
          await new Promise(resolve => { window.releaseSurvey = resolve; });
          const response = await original(...args);
          window.surveyFinished = true;
          return response;
        }
        return original(...args);
      };
    }""")
    page.locator("#survey-open").click()
    page.wait_for_function("typeof window.releaseSurvey === 'function'")
    assert page.get_by_role("heading", name="Survey Verification").is_visible()
    page.screenshot(path=str(tmp_path / f"survey-loading-{width}.png"))
    page.locator('#modal-actions button[value="cancel"]').click()
    page.evaluate("window.releaseSurvey()")
    page.wait_for_function("window.surveyFinished === true")
    assert page.locator("#modal-shell").is_hidden()


@pytest.mark.skipif(
  not os.environ.get("ARENA_STEERING_CHROMIUM"),
  reason="Set ARENA_STEERING_CHROMIUM to run the browser regression",
)
def test_survey_modal_reports_fetch_failure_without_closing() -> None:
  with composer_page(390) as page:
    page.evaluate("""() => {
      const original = window.fetch.bind(window);
      window.fetch = async (...args) => {
        if (String(args[0]) === '/survey') {
          await new Promise(resolve => { window.failSurvey = resolve; });
          return new Response(JSON.stringify({error:'offline'}), {
            status:503, headers:{'content-type':'application/json'}
          });
        }
        return original(...args);
      };
    }""")
    page.locator("#survey-open").click()
    page.wait_for_function("typeof window.failSurvey === 'function'")
    assert page.get_by_role("heading", name="Survey Verification").is_visible()
    page.evaluate("window.failSurvey()")
    page.get_by_role("alert").filter(
      has_text="Could not refresh survey: offline"
    ).wait_for()
    assert page.get_by_role("status").filter(has_text="Loading survey").count() == 0
    assert page.locator("#modal-shell").is_visible()


@pytest.mark.skipif(
  not os.environ.get("ARENA_STEERING_CHROMIUM"),
  reason="Set ARENA_STEERING_CHROMIUM to run the browser regression",
)
def test_survey_old_fetch_does_not_replace_a_reopened_modal() -> None:
  with composer_page(1200) as page:
    page.evaluate("""() => {
      const original = window.fetch.bind(window);
      window.releaseSurveys = [];
      window.finishedSurveys = [];
      window.fetch = async (...args) => {
        if (String(args[0]) !== '/survey') return original(...args);
        const index = window.releaseSurveys.length;
        await new Promise(resolve => window.releaseSurveys.push(resolve));
        const id = index ? 'NEW' : 'OLD';
        window.finishedSurveys[index] = true;
        return new Response(JSON.stringify({survey:{results:[{id,correct:true,answer:{value:id}}]}}), {
          status:200, headers:{'content-type':'application/json'}
        });
      };
    }""")
    page.locator("#survey-open").click()
    page.wait_for_function("window.releaseSurveys.length === 1")
    page.locator('#modal-actions button[value="cancel"]').click()
    page.locator("#survey-open").click()
    page.wait_for_function("window.releaseSurveys.length === 2")
    page.evaluate("window.releaseSurveys[1]()")
    page.locator(".survey-modal-content").get_by_text(
      "NEW", exact=True
    ).first.wait_for()
    page.evaluate("window.releaseSurveys[0]()")
    page.wait_for_function("window.finishedSurveys[0] === true")
    assert (
      page.locator(".survey-modal-content").get_by_text("NEW", exact=True).count() > 0
    )
    assert (
      page.locator(".survey-modal-content").get_by_text("OLD", exact=True).count() == 0
    )


@pytest.mark.skipif(
  not os.environ.get("ARENA_STEERING_CHROMIUM"),
  reason="Set ARENA_STEERING_CHROMIUM to run the browser regression",
)
def test_markdown_dom_cache_preserves_nodes_and_invalidates() -> None:
  with composer_page(1200) as page:
    result = page.evaluate("""async () => {
      const { createMarkdownBatch } = await import('/static/assets/markdown-dom-cache.js');
      const { reconcileView } = await import('/static/assets/dom.js');
      const root = document.createElement('div');
      document.body.append(root);
      function render(html, variant = '') {
        const batch = createMarkdownBatch();
        const markup = batch.slot(html, 'prose-block', variant);
        reconcileView(root, markup, node => batch.mount(node));
        return root.firstElementChild;
      }
      const original = render('<p>Hello <strong>world</strong></p>');
      const strong = original.querySelector('strong');
      strong.dataset.retained = 'yes';
      const unchanged = render('<p>Hello <strong>world</strong></p>');
      const reused = unchanged.querySelector('strong') === strong;
      const changed = render('<p>Hello <strong>other</strong></p>');
      const invalidated = changed.querySelector('strong') !== strong && changed.textContent === 'Hello other';
      const changedStrong = changed.querySelector('strong');
      const differentOption = render('<p>Hello <strong>other</strong></p>', 'different');
      const variantInvalidated = differentOption.querySelector('strong') !== changedStrong;
      const batch = createMarkdownBatch();
      const large = batch.slot('x'.repeat(32769), 'prose-block');
      const copies = createMarkdownBatch();
      const holder = document.createElement('div');
      holder.innerHTML = copies.slot('<b>independent</b>', 'prose-block') +
        copies.slot('<b>independent</b>', 'prose-block');
      copies.mount(holder);
      holder.firstElementChild.firstElementChild.textContent = 'mutated';
      const isolated = holder.lastElementChild.textContent === 'independent';
      const first = createMarkdownBatch().slot('evict-me', 'prose-block');
      for (let i = 0; i < 128; i++) createMarkdownBatch().slot(`unique-${i}`, 'prose-block');
      const afterEviction = createMarkdownBatch().slot('evict-me', 'prose-block');
      root.remove();
      return { reused, invalidated, variantInvalidated, isolated,
        evicted: first !== afterEviction, largeBypassed: !large.includes('data-markdown-key') };
    }""")
    assert result == {
      "reused": True,
      "invalidated": True,
      "variantInvalidated": True,
      "isolated": True,
      "evicted": True,
      "largeBypassed": True,
    }


@pytest.mark.skipif(
  not os.environ.get("ARENA_STEERING_CHROMIUM"),
  reason="Set ARENA_STEERING_CHROMIUM to run the browser regression",
)
def test_server_html_required_except_for_optimistic_messages() -> None:
  with composer_page(1200) as page:
    result = page.evaluate("""async () => {
      const { renderMessagesView } = await import('/static/assets/messages-view.js');
      const { renderReportsView } = await import('/static/assets/reports-view.js');
      const root = document.createElement('div');
      document.body.append(root);
      const message = {id: 'abc123', body: '**client fallback**', acks: [],
        status: 'sent', modified_at: '2026-01-01T00:00:00Z'};
      renderMessagesView(root, {messages: [message], tasks: []}, {});
      const confirmedFallback = !!root.querySelector('.message-text strong');
      const messageAlert = !!root.querySelector('.message-text [role=alert]');
      message.optimistic = true;
      renderMessagesView(root, {messages: [message], tasks: []}, {});
      const optimisticFallback = !!root.querySelector('.message-text strong');
      const report = {id: 'report-test', title: 'Test', body: '**report fallback**',
        blocks: [{type: 'markdown', markdown: '**report fallback**'}], fields: [], answers: []};
      renderReportsView(root, {reports: [report], selectedReportId: report.id}, {});
      const reportFallback = !!root.querySelector('.prose-block strong');
      const reportAlert = !!root.querySelector('.prose-block [role=alert]');
      root.remove();
      return {confirmedFallback, messageAlert, optimisticFallback, reportFallback, reportAlert};
    }""")
    assert result == {
      "confirmedFallback": False,
      "messageAlert": True,
      "optimisticFallback": True,
      "reportFallback": False,
      "reportAlert": True,
    }


@pytest.mark.skipif(
  not os.environ.get("ARENA_STEERING_CHROMIUM"),
  reason="Set ARENA_STEERING_CHROMIUM to run the browser regression",
)
def test_markdown_dom_reused_on_message_updates_and_search() -> None:
  with composer_page(1200) as page:
    result = page.evaluate("""async () => {
      const { renderMessagesView } = await import('/static/assets/messages-view.js');
      const root = document.createElement('div');
      document.body.append(root);
      const msg = {id: 'abc123', body: 'hello world',
        body_html: '<p>hello <strong>world</strong></p>', acks: [],
        status: 'sent', modified_at: '2026-01-01T00:00:00Z'};
      const state = {messages: [msg], tasks: []};
      renderMessagesView(root, state, {});
      const original = root.querySelector('.message-text strong');
      msg.status = 'seen';
      renderMessagesView(root, state, {});
      const retained = root.querySelector('.message-text strong') === original;
      state.searchQuery = 'world';
      renderMessagesView(root, state, {});
      const searchHit = root.querySelector('.message-text mark.search-hit')?.textContent === 'world';
      state.searchQuery = '';
      renderMessagesView(root, state, {});
      const cleared = !root.querySelector('.message-text mark.search-hit');
      msg.body = 'hello changed'; msg.body_html = '<p>hello <strong>changed</strong></p>';
      renderMessagesView(root, state, {});
      const changed = root.querySelector('.message-text strong')?.textContent === 'changed';
      root.remove();
      return { retained, searchHit, cleared, changed };
    }""")
    assert result == {
      "retained": True,
      "searchHit": True,
      "cleared": True,
      "changed": True,
    }


@pytest.mark.skipif(
  not os.environ.get("ARENA_STEERING_CHROMIUM"),
  reason="Set ARENA_STEERING_CHROMIUM to run the browser regression",
)
def test_markdown_dom_reused_in_report_refresh() -> None:
  with composer_page(1200) as page:
    result = page.evaluate("""async () => {
      const { renderReportsView } = await import('/static/assets/reports-view.js');
      const root = document.createElement('div');
      document.body.append(root);
      const report = {id: 'cache-report', title: 'Cache', body: 'hello **world**',
        blocks: [{type: 'markdown', html: '<p>hello <strong>world</strong></p>'}],
        fields: [], answers: []};
      const state = {reports: [report], selectedReportId: report.id};
      renderReportsView(root, state, {});
      const original = root.querySelector('.prose-block strong');
      report.answers.push({id: 'abc123', values: {}, ack: 'reply **ok**',
        ack_html: '<p>reply <strong>ok</strong></p>'});
      renderReportsView(root, state, {});
      const retained = root.querySelector('.prose-block strong') === original;
      const ack = root.querySelector('.report-ack-markdown strong');
      renderReportsView(root, state, {});
      const retainedAck = !!ack && root.querySelector('.report-ack-markdown strong') === ack;
      report.body = 'hello **changed**';
      report.blocks[0].html = '<p>hello <strong>changed</strong></p>';
      renderReportsView(root, state, {});
      const changed = root.querySelector('.prose-block strong')?.textContent === 'changed';
      root.remove();
      return {retained, retainedAck, changed};
    }""")
    assert result == {"retained": True, "retainedAck": True, "changed": True}


@pytest.mark.skipif(
  not os.environ.get("ARENA_STEERING_CHROMIUM"),
  reason="Set ARENA_STEERING_CHROMIUM to run the browser regression",
)
def test_code_and_id_copy_use_textarea_and_report_failures() -> None:
  with composer_page(1200) as page:
    page.evaluate("""() => {
      window.copyCalls = [];
      document.execCommand = command => {
        const field = document.activeElement;
        window.copyCalls.push({command, value: field.value,
          selected: field.value.slice(field.selectionStart, field.selectionEnd)});
        return [true, false, true, false][window.copyCalls.length - 1];
      };
      const code = document.createElement('button');
      code.className = 'copy-code'; code.dataset.code = 'first\\nsecond';
      code.setAttribute('aria-label', 'Copy code'); code.textContent = 'copy';
      code.style.cssText = 'position:fixed;top:100px;left:100px;z-index:10000';
      document.body.append(code);
      const parent = document.createElement('button');
      parent.dataset.parentType = 'message'; parent.dataset.parentId = 'abc123';
      parent.setAttribute('aria-label', 'Message abc123 as message parent');
      parent.style.cssText = 'position:fixed;top:150px;left:100px;z-index:10000';
      parent.innerHTML = '<code class="msg-id">abc123</code>';
      document.body.append(parent);
    }""")
    code = page.locator(".copy-code").last
    code.click()
    assert code.get_attribute("data-state") == "good"
    assert page.evaluate("window.copyCalls[0].selected") == "first\nsecond"
    code.click()
    assert code.get_attribute("data-state") == "bad"
    assert "failed" in (code.get_attribute("aria-label") or "").lower()
    parent = page.locator('button[data-parent-id="abc123"]')
    parent.click(modifiers=["Shift"])
    assert page.evaluate("window.copyCalls[2].selected") == "abc123"
    assert parent.locator("code").get_attribute("data-state") == "good"
    parent.click(modifiers=["Shift"])
    assert parent.locator("code").get_attribute("data-state") == "bad"
    assert "failed" in (parent.get_attribute("aria-label") or "").lower()
    assert page.locator("textarea[readonly]").count() == 0


@pytest.mark.skipif(
  not os.environ.get("ARENA_STEERING_CHROMIUM"),
  reason="Set ARENA_STEERING_CHROMIUM to run the browser regression",
)
@pytest.mark.parametrize("width", [390, 1200])
def test_send_hover_changes_background_without_resizing(
  tmp_path: Path, width: int
) -> None:
  with composer_page(width) as page:
    page.locator("#msg").fill("Draft message")
    send = page.locator("#send")
    before = send.evaluate("""el => ({
      background: getComputedStyle(el).backgroundColor,
      box: el.getBoundingClientRect().toJSON()
    })""")
    send.hover()
    page.wait_for_timeout(250)
    after = send.evaluate("""el => ({
      background: getComputedStyle(el).backgroundColor,
      box: el.getBoundingClientRect().toJSON()
    })""")
    assert before["background"] != after["background"]
    assert after["box"]["width"] == pytest.approx(before["box"]["width"])
    assert after["box"]["height"] == pytest.approx(before["box"]["height"])
    page.screenshot(path=str(tmp_path / f"send-hover-{width}.png"))


@pytest.mark.skipif(
  not os.environ.get("ARENA_STEERING_CHROMIUM"),
  reason="Set ARENA_STEERING_CHROMIUM to run the browser regression",
)
@pytest.mark.parametrize("width", [390, 1200])
def test_reload_preserves_parents_and_completed_uploads_only(width: int) -> None:
  with composer_page(width) as page:
    assert page.request.post(
      page.url.split("/?", 1)[0] + "/messages",
      data={"id": "aa0199", "body": "Parent"},
    ).ok
    page.locator('.message[data-msg-id="aa0199"] .parent-id-button').click()
    page.locator("#composer-file-input").set_input_files(
      {"name": "ready.txt", "mimeType": "text/plain", "buffer": b"ready bytes"}
    )
    page.wait_for_function(
      "document.querySelector('.composer-attachment-chip')?.dataset.uploadStatus === 'ready'"
    )
    page.evaluate("""() => {
      const original = window.fetch.bind(window);
      window.fetch = async (...args) => {
        if (String(args[0]).endsWith('/uploads')) {
          if (args[1].body.get('file').name === 'failed.txt') {
            return new Response(JSON.stringify({error: 'failed'}), {status: 400});
          }
          await new Promise(() => {});
        }
        return original(...args);
      };
    }""")
    page.locator("#composer-file-input").set_input_files(
      {"name": "failed.txt", "mimeType": "text/plain", "buffer": b"failed bytes"}
    )
    page.locator('.composer-attachment-chip[data-upload-status="failed"]').wait_for()
    page.locator("#composer-file-input").set_input_files(
      {"name": "pending.txt", "mimeType": "text/plain", "buffer": b"pending bytes"}
    )
    page.locator('.composer-attachment-chip[data-upload-status="uploading"]').wait_for()
    page.reload()
    page.locator('#composer-reply-bar [data-parent-id="aa0199"]').wait_for(timeout=5000)
    page.locator('.composer-attachment-chip[data-upload-status="ready"]').wait_for()
    assert "ready.txt" in page.locator("#composer-attachments").inner_text()
    assert "pending.txt" not in page.locator("#composer-attachments").inner_text()
    assert "failed.txt" not in page.locator("#composer-attachments").inner_text()
    page.locator("#msg").fill("Send restored attachment")
    page.locator("#send").click()
    page.locator("#composer-attachments").wait_for(state="hidden")
    page.wait_for_function(
      "document.querySelector('#send')?.getAttribute('aria-busy') !== 'true'"
    )
    page.reload()
    assert page.locator("#composer-attachments").is_hidden()
    assert page.locator('#composer-reply-bar [data-parent-id="aa0199"]').count() == 0
    sent = page.locator("#history .message").filter(has_text="Send restored attachment")
    sent.wait_for()
    assert "ready.txt" in sent.text_content()


@pytest.mark.skipif(
  not os.environ.get("ARENA_STEERING_CHROMIUM"),
  reason="Set ARENA_STEERING_CHROMIUM to run the browser regression",
)
def test_restored_image_preview_and_removal_survive_reload(tmp_path: Path) -> None:
  image = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+lmGQAAAAASUVORK5CYII="
  )
  with composer_page(390, tmp_path / "state.sqlite3") as page:
    page.locator("#composer-file-input").set_input_files(
      {"name": "example.png", "mimeType": "image/png", "buffer": image}
    )
    page.locator('.composer-attachment-chip[data-upload-status="ready"]').wait_for()
    page.reload()
    preview = page.locator('.composer-attachment-chip img[alt="example.png"]')
    preview.wait_for()
    assert preview.get_attribute("src").startswith("/static/uploads/")
    page.wait_for_function(
      "document.querySelector('.composer-attachment-chip img')?.naturalWidth > 0"
    )
    page.screenshot(path=str(tmp_path / "restored-image.png"))
    page.locator('[aria-label="Remove example.png"]').click()
    page.reload()
    assert page.locator("#composer-attachments").is_hidden()


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
            const parent = el('cc0002', '.reply-parent-chip');
            const task = el('cc0003', '.reply-parent-chip');
            const sharedHeight = chip => {
              const shared = chip.cloneNode(true);
              document.body.append(shared);
              const result = height(shared);
              shared.remove();
              return result;
            };
            return {
              parentChip: height(parent),
              parentShared: sharedHeight(parent),
              taskChip: height(task),
              taskShared: sharedHeight(task),
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
          assert geometry["parentChip"] == pytest.approx(
            geometry["parentShared"], abs=0.5
          )
          assert geometry["taskChip"] == pytest.approx(geometry["taskShared"], abs=0.5)
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


@pytest.mark.skipif(
  not os.environ.get("ARENA_STEERING_CHROMIUM"),
  reason="Set ARENA_STEERING_CHROMIUM to run the browser regression",
)
def test_pagination_error_survives_refresh_until_manual_retry() -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore()
  app = SteeringApp(store)
  for index in range(25):
    app.messages.send_message(
      f"Message {index}\n\n" + "Scrolling content. " * 40,
      msg_id=f"{index:06x}",
      blocking=False,
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
      page = browser.new_page(viewport={"width": 1200, "height": 700})
      page.add_init_script("""(() => {
        const fetchOriginal = window.fetch.bind(window);
        window.firstPages = 0;
        window.olderRequests = 0;
        window.allowOlder = false;
        window.fetch = async (...args) => {
          const url = String(args[0]);
          if (url.includes('/messages?')) {
            if (!url.includes('before=')) window.firstPages++;
            else {
              window.olderRequests++;
              if (!window.allowOlder) return new Response(JSON.stringify({error: 'try again'}), {
                status: 503, headers: {'content-type': 'application/json'}
              });
            }
          }
          return fetchOriginal(...args);
        };
      })();""")
      page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
      page.wait_for_function(
        "document.querySelectorAll('#history .message').length === 20"
      )
      page.locator("#load-older-messages").evaluate("element => element.click()")
      error = page.locator('#history [role="alert"]')
      error.wait_for(timeout=6000)
      page.evaluate(
        "new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))"
      )
      older_requests = page.evaluate("window.olderRequests")
      page.locator("#history").evaluate(
        "element => element.dispatchEvent(new Event('scroll'))"
      )
      app.messages.send_message("Fresh refresh marker", msg_id="eeeeee", blocking=False)
      page.wait_for_function(
        "Array.from(document.querySelectorAll('#history .message'))"
        ".some(element => element.textContent.includes('Fresh refresh marker'))",
        timeout=6000,
      )
      assert error.is_visible(), (
        "a successful routine refresh erased the older-page error"
      )
      assert page.evaluate("window.olderRequests") == older_requests
      page.evaluate("window.allowOlder = true")
      page.locator("#load-older-messages").evaluate("element => element.click()")
      page.wait_for_function(
        "document.querySelectorAll('#history .message').length === 26"
      )
      assert error.is_hidden()
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
def test_hidden_toggle_retains_visible_cards_during_fetch(tmp_path: Path) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore()
  app = SteeringApp(store)
  app.messages.send_message("Visible message", msg_id="aaaaaa", blocking=False)
  for index in range(25):
    app.messages.send_message(
      f"Hidden message {index}", msg_id=f"{index + 1:06x}", hidden=True, blocking=False
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
      page.add_init_script("""(() => {
        const original = window.fetch.bind(window);
        window.fetch = async (...args) => {
          if (!window.hiddenFetchStarted && String(args[0]).includes('/messages?') &&
              String(args[0]).includes('hidden=1')) {
            window.hiddenFetchStarted = true;
            await new Promise(resolve => { window.releaseHidden = resolve; });
          }
          return original(...args);
        };
      })();""")
      page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
      visible = page.locator('#history .message[data-msg-id="aaaaaa"]')
      visible.wait_for()
      page.evaluate(
        "window.visibleCard = document.querySelector('[data-msg-id=aaaaaa]')"
      )
      page.get_by_role("button", name="Show hidden messages").click()
      page.wait_for_function("window.hiddenFetchStarted")
      assert visible.count() == 1
      assert visible.evaluate("el => el === window.visibleCard")
      page.screenshot(path=str(tmp_path / "hidden-toggle-loading.png"))
      page.evaluate("window.releaseHidden()")
      page.locator('#history .message[data-msg-id="000019"]').wait_for()
      assert visible.evaluate("el => el === window.visibleCard")
      assert page.locator('#history .message[data-hidden="true"]').count() == 25
      page.screenshot(path=str(tmp_path / "hidden-toggle-loaded.png"))
      page.get_by_role("button", name="Hide hidden messages").click()
      assert page.locator('#history .message[data-hidden="true"]').count() == 0
      assert visible.evaluate("el => el === window.visibleCard")
      browser.close()
  finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)
    store.close()


ROOT = Path(__file__).resolve().parents[3]


SKILL = ROOT / "skills" / "arena-steering"


def test_reduced_motion_has_static_message_edge_masks() -> None:
  css = (SKILL / "assets" / "style.css").read_text(encoding="utf-8")
  reduced = css.split("@media (prefers-reduced-motion: reduce) {", 1)[1]
  reduced = reduced.split("\n}\n", 1)[0]
  assert "#history {" in reduced
  assert "mask-image:" in reduced
  assert "--edge-start: var(--edge-stop-start);" in reduced
  assert "--edge-end: var(--edge-stop-end);" in reduced
  assert "#history[data-scrolled-start]" in reduced
  assert "--edge-start: var(--edge-fade-start);" in reduced
  assert "#history[data-scrolled-end]" in reduced
  assert "--edge-end: var(--edge-fade-end);" in reduced


def test_message_edge_flags_follow_scroll_and_resize() -> None:
  script = r"""
import assert from 'node:assert/strict';
import { renderMessagesView } from './skills/arena-steering/assets/messages-view.js';
globalThis.document = {
  activeElement: null,
  createElement() { return { content: { querySelector() { return null; } } }; },
};
const observers = [];
globalThis.ResizeObserver = class {
  constructor(callback) { this.callback = callback; observers.push(this); }
  observe(target) { this.target = target; }
  disconnect() { this.disconnected = true; }
};
const attrs = new Set();
let pos = 0;
const history = {
  scrollHeight: 1000, clientHeight: 200, handlers: {},
  get scrollTop() { return pos; },
  set scrollTop(value) { pos = Math.max(0, Math.min(value, this.scrollHeight - this.clientHeight)); },
  toggleAttribute(name, value) { if (value) attrs.add(name); else attrs.delete(name); },
  addEventListener(type, callback) { this.handlers[type] = callback; },
  removeEventListener(type, callback) {
    assert.equal(this.handlers[type], callback);
    delete this.handlers[type];
    this.removed = (this.removed || 0) + 1;
  },
  getBoundingClientRect() { return { top: 0, bottom: 200 }; },
  querySelectorAll() { return []; },
};
let rendered = false;
const container = {
  set innerHTML(value) { rendered = true; },
  replaceChildren() { rendered = true; },
  querySelector(selector) { return rendered && selector === '#history' ? history : null; },
  querySelectorAll() { return []; },
  addEventListener() {},
};
const edges = () => [attrs.has('data-scrolled-start'), attrs.has('data-scrolled-end')];
renderMessagesView(container, { messages: [], tasks: [] }, {});
assert.deepEqual(edges(), [true, false], 'initially pinned at the bottom');
assert.equal(observers[0].target, history);
history.scrollTop = 0;
history.handlers.scroll();
assert.deepEqual(edges(), [false, true], 'top keeps first content unfaded');
history.scrollTop = 1;
history.handlers.scroll();
assert.deepEqual(edges(), [true, true], 'fade snaps on after leaving the top');
history.scrollTop = history.scrollHeight;
history.handlers.scroll();
assert.deepEqual(edges(), [true, false], 'bottom keeps last content unfaded');
history.clientHeight = history.scrollHeight;
history.scrollTop = 0;
observers[0].callback();
assert.deepEqual(edges(), [false, false], 'resize removes fades when content fits');
history.clientHeight = 200;
observers[0].callback();
assert.deepEqual(edges(), [true, false], 'resize keeps a pinned view at the bottom');
history.scrollTop = 0;
history.handlers.scroll();
assert.deepEqual(edges(), [false, true], 'scrolling to top restores the end fade');
renderMessagesView(container, { messages: [], tasks: [] }, {});
assert.equal(observers[0].disconnected, true, 'rerender disconnects the old observer');
assert.equal(history.removed, 1, 'rerender replaces the old scroll listener');
"""
  result = subprocess.run(
    ["node", "--experimental-default-type=module", "--input-type=module", "-e", script],
    cwd=ROOT,
    capture_output=True,
    text=True,
    check=False,
  )
  assert result.returncode == 0, result.stderr


@pytest.mark.skipif(
  not os.environ.get("ARENA_STEERING_CHROMIUM"),
  reason="Set ARENA_STEERING_CHROMIUM to run the browser regression",
)
def test_message_edge_fades_in_both_motion_preferences() -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore()
  app = SteeringApp(store, repo_name="Synthetic scroll regression")
  for index in range(10):
    status, payload = app.dispatch(
      "POST",
      "/messages",
      {"body": f"Message {index}\n\n" + "A synthetic line of readable text.\n\n" * 5},
    )
    assert status == 201, payload
  server = create_http_server(app, host="127.0.0.1", port=0)
  thread = threading.Thread(target=server.serve_forever, daemon=True)
  thread.start()
  url = f"http://127.0.0.1:{server.server_port}/?transport=poll"
  try:
    with playwright.sync_playwright() as runner:
      browser = runner.chromium.launch(
        executable_path=os.environ["ARENA_STEERING_CHROMIUM"],
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage"],
      )
      try:
        for motion in ("reduce", "no-preference"):
          context = browser.new_context(
            viewport={"width": 1200, "height": 700}, reduced_motion=motion
          )
          page = context.new_page()
          errors: list[str] = []
          page.on("pageerror", lambda error, errors=errors: errors.append(str(error)))
          page.goto(url, wait_until="domcontentloaded")
          page.wait_for_function(
            "() => { const e = document.querySelector('#history'); "
            "return e && e.querySelector('.message') && e.scrollHeight > e.clientHeight + 100; }"
          )

          def position(which: str, page=page) -> dict[str, object]:
            return page.evaluate(
              """async which => {
                const e = document.querySelector('#history');
                const max = e.scrollHeight - e.clientHeight;
                e.scrollTop = { top: 0, nearTop: 1, middle: max / 2, bottom: max }[which];
                await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
                const css = getComputedStyle(e), rect = e.getBoundingClientRect();
                const messages = e.querySelectorAll('.message');
                const length = name => parseFloat(css.getPropertyValue(name));
                return {
                  mask: css.maskImage, animation: css.animationName,
                  start: length('--edge-start'), stopStart: length('--edge-stop-start'),
                  fadeStart: length('--edge-fade-start'), end: length('--edge-end'),
                  stopEnd: length('--edge-stop-end'), fadeEnd: length('--edge-fade-end'),
                  firstTop: messages[0].getBoundingClientRect().top - rect.top,
                  lastBottom: rect.bottom - messages[messages.length - 1].getBoundingClientRect().bottom,
                };
              }""",
              which,
            )

          top = position("top")
          near_top = position("nearTop")
          middle = position("middle")
          bottom = position("bottom")
          for snapshot in (top, near_top, middle, bottom):
            assert "linear-gradient" in str(snapshot["mask"]), (motion, snapshot)
          assert top["start"] == top["stopStart"], (motion, top)
          assert top["end"] == top["fadeEnd"], (motion, top)
          assert top["firstTop"] >= top["start"], (motion, top)
          assert middle["start"] == middle["fadeStart"], (motion, middle)
          assert middle["end"] == middle["fadeEnd"], (motion, middle)
          assert bottom["start"] == bottom["fadeStart"], (motion, bottom)
          assert bottom["end"] == bottom["stopEnd"], (motion, bottom)
          assert bottom["lastBottom"] >= bottom["end"], (motion, bottom)
          if motion == "reduce":
            assert near_top["start"] == near_top["fadeStart"], near_top
            assert top["animation"] == "none", top
            page.set_viewport_size({"width": 1200, "height": 4000})
            page.wait_for_function(
              "() => { const e = document.querySelector('#history'); "
              "return e.scrollHeight <= e.clientHeight && "
              "!e.hasAttribute('data-scrolled-start') && !e.hasAttribute('data-scrolled-end'); }"
            )
            page.set_viewport_size({"width": 1200, "height": 700})
            page.wait_for_function(
              "() => { const e = document.querySelector('#history'); "
              "return e.scrollHeight > e.clientHeight && !e.hasAttribute('data-scrolled-end'); }"
            )
            page.locator("#history").evaluate("el => { el.scrollTop = 0; }")
            page.wait_for_function(
              "() => document.querySelector('#history').hasAttribute('data-scrolled-end')"
            )
          else:
            assert "edge-start" in str(top["animation"]), top
            assert near_top["stopStart"] < near_top["start"] < near_top["fadeStart"], (
              near_top
            )
          assert not errors, errors
          context.close()
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
def test_multiline_optimistic_paragraph_matches_confirmed_render(
  tmp_path: Path,
) -> None:
  with composer_page(390) as page:
    boundary_html = page.evaluate("""async () => {
      const { renderMarkdownBlock } = await import('/static/assets/markdown.js');
      return renderMarkdownBlock('one\\ntwo\\n\\nthree\\n# Heading\\n- item\\nlast');
    }""")
    assert boundary_html.startswith("<p>one\ntwo</p>\n<p>three</p>")
    assert boundary_html.index("<h1") < boundary_html.index("<ul>")
    assert boundary_html.endswith("<p>last</p>")
    page.evaluate("""() => {
      const original = window.fetch.bind(window);
      window.fetch = async (...args) => {
        if (String(args[0]).endsWith('/messages') && args[1]?.method === 'POST') {
          await new Promise(resolve => { window.releaseSend = resolve; });
        }
        return original(...args);
      };
    }""")
    page.locator("#msg").fill("first line\nsecond **line**\nthird line")
    page.locator("#send").click()
    page.wait_for_function("typeof window.releaseSend === 'function'")
    text = page.locator("#history .message:last-child .message-text")
    pending_html = text.inner_html()
    pending_height = text.bounding_box()["height"]
    assert text.locator("p").count() == 1
    page.screenshot(path=str(tmp_path / "multiline-pending.png"))
    page.evaluate("window.releaseSend()")
    page.locator("#history .message:last-child button.receipt-id").wait_for()
    assert text.inner_html() == pending_html
    assert abs(text.bounding_box()["height"] - pending_height) < 1
    page.screenshot(path=str(tmp_path / "multiline-confirmed.png"))
