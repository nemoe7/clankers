"""Steering regression tests."""

from __future__ import annotations

import base64
import itertools
import os
import re
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


def test_draft_survives_a_new_browser_tab() -> None:
  with composer_page(1200) as page:
    page.locator("#msg").fill("Keep this draft across tabs")
    second = page.context.new_page()
    second.goto(page.url, wait_until="domcontentloaded")
    second.locator("#msg").wait_for()
    assert second.locator("#msg").input_value() == "Keep this draft across tabs"
    second.close()


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
    assert page.locator("[data-retry-composer-attachment]").count() == 0
    assert page.evaluate(
      "window.uploadIds.length === 4 && new Set(window.uploadIds.slice(0, 4)).size === 1"
    )
    page.locator("#send").click()
    page.wait_for_function("window.uploadIds.length === 8")
    page.get_by_role("status").filter(has_text="A file did not upload").wait_for()
    assert page.evaluate(
      "new Set(window.uploadIds.slice(4, 8)).size === 1 && window.uploadIds[0] !== window.uploadIds[4]"
    )
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
      window.sendRequestIds = [];
      window.sendAttempts = 0;
      window.fetch = async (...args) => {
        if (String(args[0]).endsWith('/messages') && args[1]?.method === 'POST') {
          window.sendAttempts += 1;
          window.sendRequestIds.push(JSON.parse(args[1].body || '{}')._request_id);
          const result = window.sendAttempts === 1 || window.sendAttempts === 4
            ? await original(...args)
            : null;
          if (window.sendAttempts <= 3) {
            return new Response(JSON.stringify({error: 'response lost'}), {
              status: 503, headers: {'content-type': 'application/json'}
            });
          }
          return result;
        }
        return original(...args);
      };
    }""")
    page.locator("#msg").fill("Reply once despite a lost response")
    page.locator("#send").click()
    page.wait_for_function(
      "Array.from(document.querySelectorAll('#history .message:not([data-msg-id^=\"pending-\"])'))"
      ".some(e => e.textContent.includes('Reply once despite a lost response'))"
    )
    assert page.locator("#retry-send").count() == 0
    assert page.locator("#discard-send").count() == 0
    assert page.evaluate(
      "window.sendRequestIds.length === 4 && new Set(window.sendRequestIds).size === 1"
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


def test_optimistic_send_failure_preserves_new_draft() -> None:
  with composer_page(1200) as page:
    page.evaluate("""() => {
      const original = window.fetch.bind(window);
      window.sendRequestIds = [];
      let held = false;
      window.fetch = async (...args) => {
        if (String(args[0]).endsWith('/messages') && args[1]?.method === 'POST') {
          window.sendRequestIds.push(JSON.parse(args[1].body || '{}')._request_id);
          if (!held) {
            held = true;
            await new Promise(resolve => { window.failSend = resolve; });
          }
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
    page.locator(".composer-send-status").filter(has_text="offline").wait_for()
    assert page.evaluate(
      "window.sendRequestIds.length === 4 && new Set(window.sendRequestIds).size === 1"
    )
    assert page.locator("#msg").input_value() == "A newer draft"
    assert page.locator("#retry-send").count() == 0
    assert page.locator("#discard-send").count() == 0
    assert page.evaluate("sessionStorage.getItem('steer:pendingSend')") is None


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
      window.sendRequestIds = [];
      window.allowSend = false;
      let held = false;
      window.fetch = async (...args) => {
        if (String(args[0]).endsWith('/messages') && args[1]?.method === 'POST') {
          window.sendRequestIds.push(JSON.parse(args[1].body || '{}')._request_id);
          if (!window.allowSend) {
            if (!held) {
              held = true;
              await new Promise(resolve => { window.failSend = resolve; });
            }
            return new Response(JSON.stringify({error: 'offline'}), {
              status: 503, headers: {'content-type': 'application/json'}
            });
          }
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
    page.locator(".composer-send-status").filter(has_text="offline").wait_for()
    assert page.evaluate(
      "window.sendRequestIds.length === 4 && new Set(window.sendRequestIds).size === 1"
    )
    assert page.locator("#retry-send").count() == 0
    assert (
      page.locator(
        '#composer-reply-bar .composer-reply-chip[data-parent-id="aaaa02"]'
      ).count()
      == 1
    )
    assert page.locator("#msg").input_value() == "Reply waiting"
    page.evaluate("window.allowSend = true")
    page.locator("#send").click()
    page.wait_for_function(
      "Array.from(document.querySelectorAll('#history .message:not([data-msg-id^=\"pending-\"])'))"
      ".some(e => e.textContent.includes('Reply waiting'))"
    )
    assert page.evaluate("window.sendRequestIds[4] !== window.sendRequestIds[0]")


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
          if (!window.skipRequestHeld) {
            window.skipRequestHeld = true;
            await new Promise(resolve => { window.releaseSkip = resolve; });
          }
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


def test_contained_buttons_hide_default_box_and_reveal_on_hover_and_press(
  tmp_path: Path,
) -> None:
  transparent = "rgba(0, 0, 0, 0)"
  style_probe = """el => {
    const s = getComputedStyle(el);
    const box = el.getBoundingClientRect().toJSON();
    return {
      background: s.backgroundColor,
      border: s.borderColor,
      width: box.width,
      height: box.height,
    };
  }"""
  with composer_page(1200) as page:
    page.locator("#msg").fill("Draft message")
    page.mouse.move(0, 0)
    for selector in (
      "#send",
      "#blocked-bash-open",
      "#agent-interrupt",
      "#skip-poll",
      "#quiet-msgs",
    ):
      btn = page.locator(selector)
      idle = btn.evaluate(style_probe)
      assert idle["background"] == transparent, f"{selector} idle bg"
      assert idle["border"] == transparent, f"{selector} idle border"

      btn.hover()
      page.wait_for_function(
        """([sel, clear]) => {
          const s = getComputedStyle(document.querySelector(sel));
          return s.backgroundColor !== clear;
        }""",
        arg=[selector, transparent],
      )
      hovered = btn.evaluate(style_probe)
      assert hovered["background"] != transparent, f"{selector} hover bg"
      assert hovered["border"] == transparent, f"{selector} hover border"
      assert hovered["width"] == pytest.approx(idle["width"])
      assert hovered["height"] == pytest.approx(idle["height"])

      box_rect = btn.bounding_box()
      assert box_rect is not None
      page.mouse.move(
        box_rect["x"] + box_rect["width"] / 2,
        box_rect["y"] + box_rect["height"] / 2,
      )
      page.mouse.down()
      assert btn.evaluate("el => el.matches(':active')")
      active = btn.evaluate(style_probe)
      assert active["background"] != transparent, f"{selector} active bg"
      assert active["border"] == transparent, f"{selector} active border"
      # Move off target before mouseup so we do not trigger modal/submit clicks.
      page.mouse.move(0, 0)
      page.mouse.up()
      page.wait_for_function(
        """([sel, clear]) => {
          const s = getComputedStyle(document.querySelector(sel));
          return s.backgroundColor === clear && s.borderColor === clear;
        }""",
        arg=[selector, transparent],
      )

    # Toggle-pressed state keeps background visible after pointer leaves.
    quiet = page.locator("#quiet-msgs")
    quiet.click()
    page.mouse.move(0, 0)
    assert quiet.get_attribute("aria-pressed") == "true"
    page.wait_for_function(
      """clear => {
        const s = getComputedStyle(document.querySelector('#quiet-msgs'));
        return s.backgroundColor !== clear;
      }""",
      arg=transparent,
    )
    quiet_pressed = quiet.evaluate(style_probe)
    assert quiet_pressed["background"] != transparent
    assert quiet_pressed["border"] == transparent

    interrupt = page.locator("#agent-interrupt")
    page.evaluate(
      "el => el.setAttribute('aria-pressed', 'true')", interrupt.element_handle()
    )
    page.mouse.move(0, 0)
    page.wait_for_function(
      """clear => {
        const s = getComputedStyle(document.querySelector('#agent-interrupt'));
        return s.backgroundColor !== clear;
      }""",
      arg=transparent,
    )
    interrupt_pressed = interrupt.evaluate(style_probe)
    assert interrupt_pressed["background"] != transparent

    # Publish a fielded report and verify rail icon buttons vs Submit Answer CTA.
    base_url = page.url.split("/?", 1)[0]
    report_md = (
      '# Button check\n\n<!-- question {"id":"action","label":"Pick an action"} -->\n'
      'Pick an action\n- (x) Keep current <!-- option {"label":"Keep current"} -->\n'
      '- ( ) Change later <!-- option {"label":"Change later"} -->\n'
    )
    assert page.request.post(
      f"{base_url}/reports",
      data={"id": "button-check", "title": "Button check", "body": report_md},
    ).ok
    page.locator("#tab-reports").click()
    page.locator("#report-submit-float").wait_for()
    page.mouse.move(0, 0)

    for rail_selector in ("#copy-report-btn", "#dismiss-report-btn"):
      rail_btn = page.locator(rail_selector)
      rail_idle = rail_btn.evaluate(style_probe)
      assert rail_idle["background"] == transparent
      assert rail_idle["border"] == transparent
      rail_btn.hover()
      page.wait_for_function(
        """([sel, clear]) => {
          const s = getComputedStyle(document.querySelector(sel));
          return s.backgroundColor !== clear;
        }""",
        arg=[rail_selector, transparent],
      )
      rail_hover = rail_btn.evaluate(style_probe)
      assert rail_hover["background"] != transparent
      assert rail_hover["border"] == transparent
      page.mouse.move(0, 0)

    submit_idle = page.locator("#report-submit-float").evaluate(style_probe)
    assert submit_idle["background"] != transparent
    page.screenshot(path=str(tmp_path / "reports-submit-unchanged.png"))

    mobile_context = page.context.browser.new_context(
      viewport={"width": 390, "height": 800},
      is_mobile=True,
      has_touch=True,
      reduced_motion="reduce",
    )
    try:
      mobile_page = mobile_context.new_page()
      mobile_page.goto(page.url, wait_until="domcontentloaded")
      mobile_page.locator("#msg").fill("Mobile touch draft")
      assert not mobile_page.evaluate(
        "() => matchMedia('(hover: hover) and (pointer: fine)').matches"
      )
      mobile_btn = mobile_page.locator("#skip-poll")
      rect = mobile_btn.bounding_box()
      assert rect is not None
      cx = round(rect["x"] + rect["width"] / 2)
      cy = round(rect["y"] + rect["height"] / 2)
      mobile_page.mouse.move(cx, cy)
      mobile_page.mouse.down()
      mobile_page.wait_for_function(
        """clear => {
          const s = getComputedStyle(document.querySelector('#skip-poll'));
          return s.backgroundColor !== clear;
        }""",
        arg=transparent,
      )
      mobile_page.mouse.up()
      # Releasing over the button arms the skip poll, so the armed state keeps
      # a background while its border stays clear.
      mobile_page.wait_for_function(
        """clear => {
          const button = document.querySelector('#skip-poll');
          const s = getComputedStyle(button);
          return button.dataset.armed === 'true'
            && s.backgroundColor !== clear && s.borderColor === clear;
        }""",
        arg=transparent,
      )
      # Cancelling the armed state clears the background again.
      mobile_page.touchscreen.tap(cx, cy)
      mobile_page.wait_for_function(
        """clear => {
          const s = getComputedStyle(document.querySelector('#skip-poll'));
          return s.backgroundColor === clear && s.borderColor === clear;
        }""",
        arg=transparent,
      )
    finally:
      mobile_context.close()


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
          ).all_text_contents() == ["notes.txt (lost)", "other.txt (lost)"]
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
      browser = runner.chromium.launch(args=["--no-sandbox"])
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
          page.locator('.message[data-msg-id="cc0001"] button.receipt-id').click()
          composer = page.locator("#composer-reply-bar .composer-reply-chip")
          parent = page.locator('.message[data-msg-id="cc0002"] .reply-parent-chip')
          assert page.locator("#composer-reply-bar").inner_text() == "cc0001"
          for chip in (composer, parent):
            chip.hover()
            chip.evaluate(
              "el => Promise.all(el.getAnimations().map(animation => animation.finished))"
            )
            style = chip.evaluate("""element => {
              const css = getComputedStyle(element);
              const text = getComputedStyle(element.querySelector('code'));
              const box = element.getBoundingClientRect();
              return [css.borderRadius, css.backgroundColor, css.borderColor, text.fontSize, box.width, box.height];
            }""")
            if chip == composer:
              composer_style = style
            else:
              assert style == composer_style, (composer_style, style)
          page.screenshot(path=str(tmp_path / f"chip-row-{width}.png"))
          page.close()
      finally:
        browser.close()
  finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)
    store.close()


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


def test_hidden_toggle_retains_visible_cards_during_fetch(tmp_path: Path) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore()
  app = SteeringApp(store)
  app.messages.send_message("Visible message", msg_id="aaaaaa", blocking=False)
  for index in range(25):
    app.messages.send_message(
      f"Hidden message {index}", msg_id=f"{index + 1:06x}", hidden=True, blocking=False
    )
  app.messages.send_message("Latest visible message", msg_id="cccccc", blocking=False)
  server = create_http_server(app, host="127.0.0.1", port=0)
  thread = threading.Thread(target=server.serve_forever, daemon=True)
  thread.start()
  try:
    with playwright.sync_playwright() as runner:
      browser = runner.chromium.launch(
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage"],
      )
      page = browser.new_page()
      page.add_init_script("""(() => {
        const original = window.fetch.bind(window);
        window.fetch = async (...args) => {
          if (!window.hiddenFetchStarted && String(args[0]).includes('/messages/hidden?')) {
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
    encoding="utf-8",
    check=False,
  )
  assert result.returncode == 0, result.stderr


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


def test_reply_seen_indicator_optimistic_rollback_and_revision_guard(
  tmp_path: Path,
) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore(tmp_path / "state.sqlite3")
  app = SteeringApp(store)
  for index in range(14):
    app.messages.send_message(
      f"History filler {index}\n\nExtra line to ensure scroll height.",
      msg_id=f"ff00{index:02x}",
    )
  target_id = "aa9999"
  app.messages.send_message("Target message for reply receipts", msg_id=target_id)

  server = create_http_server(app, host="127.0.0.1", port=0)
  thread = threading.Thread(target=server.serve_forever, daemon=True)
  thread.start()
  try:
    with playwright.sync_playwright() as runner:
      browser = runner.chromium.launch(
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage"],
      )
      context = browser.new_context(
        viewport={"width": 900, "height": 540}, reduced_motion="reduce"
      )
      page = context.new_page()
      page.goto(
        f"http://127.0.0.1:{server.server_port}/?transport=poll",
        wait_until="domcontentloaded",
      )
      page.locator(f'.message[data-msg-id="{target_id}"]').wait_for()
      page.locator("#history").evaluate("el => { el.scrollTop = 0; }")
      page.wait_for_function("() => document.querySelector('#history').scrollTop === 0")

      app.dispatch("POST", f"/messages/{target_id}/ack", {"markdown": "First reply."})
      rev1 = app.messages.get_message(target_id).replies_revision
      third_reply = "Third reply."
      indicator = page.locator("#log-edited")
      indicator.wait_for(state="visible")

      page.evaluate("""() => {
        const original = window.fetch.bind(window);
        window.seenCalls = [];
        window.seenMode = 'hold-fail';
        window.fetch = async (...args) => {
          const url = String(args[0]);
          if (url.includes('/replies-seen')) {
            const body = JSON.parse(args[1]?.body || '{}');
            window.seenCalls.push(body.revision);
            if (window.seenMode === 'hold-fail') {
              await new Promise(resolve => { window.releaseSeenFail = resolve; });
              return new Response(JSON.stringify({ error: 'Receipt storage failed' }), {
                status: 500,
                headers: { 'Content-Type': 'application/json' },
              });
            }
            if (window.seenMode === 'hold-ok') {
              const response = await original(...args);
              await new Promise(resolve => { window.releaseSeenOk = resolve; });
              return response;
            }
            if (window.seenMode === 'hold-stale-ok') {
              const stalePayload = await (await original(...args)).json();
              await new Promise(resolve => { window.releaseStaleOk = resolve; });
              return new Response(JSON.stringify(stalePayload), {
                status: 200,
                headers: { 'Content-Type': 'application/json' },
              });
            }
          }
          return original(...args);
        };
      }""")

      page.locator("#history").evaluate("el => { el.scrollTop = el.scrollHeight; }")
      page.wait_for_function("() => typeof window.releaseSeenFail === 'function'")
      assert indicator.is_hidden(), (
        "Indicator must hide immediately while receipt is pending"
      )
      page.screenshot(path=str(tmp_path / "reply-seen-optimistic.png"))

      page.evaluate("window.releaseSeenFail()")
      indicator.wait_for(state="visible")
      page.wait_for_timeout(150)
      assert page.evaluate("() => window.seenCalls") == [rev1]
      page.screenshot(path=str(tmp_path / "reply-seen-restored.png"))

      page.evaluate("() => { window.seenMode = 'hold-ok'; }")
      indicator.click()
      page.wait_for_function("() => typeof window.releaseSeenOk === 'function'")
      assert indicator.is_hidden()
      page.evaluate("window.releaseSeenOk()")
      page.locator(
        f'.message[data-msg-id="{target_id}"] .reply-seen-sentinel'
      ).wait_for(state="detached")
      assert app.messages.get_message(target_id).replies_seen

      page.locator("#history").evaluate("el => { el.scrollTop = 0; }")
      page.wait_for_function("() => document.querySelector('#history').scrollTop === 0")
      app.dispatch("POST", f"/messages/{target_id}/ack", {"markdown": "Second reply."})
      rev2 = app.messages.get_message(target_id).replies_revision
      indicator.wait_for(state="visible")

      page.evaluate("() => { window.seenMode = 'hold-stale-ok'; }")
      page.locator("#history").evaluate("el => { el.scrollTop = el.scrollHeight; }")
      page.wait_for_function("() => typeof window.releaseStaleOk === 'function'")
      assert indicator.is_hidden()

      page.locator("#history").evaluate("el => { el.scrollTop = 0; }")
      app.dispatch("POST", f"/messages/{target_id}/ack", {"markdown": third_reply})
      rev3 = app.messages.get_message(target_id).replies_revision
      assert rev3 != rev2
      page.wait_for_function(
        "rev => document.querySelector('.message[data-msg-id=\"aa9999\"] .reply-seen-sentinel')"
        "?.dataset.revision === rev",
        arg=rev3,
      )
      indicator.wait_for(state="visible")

      page.evaluate("window.releaseStaleOk()")
      page.wait_for_timeout(150)
      assert indicator.is_visible()
      assert (
        page.locator(
          f'.message[data-msg-id="{target_id}"] .reply-seen-sentinel'
        ).get_attribute("data-revision")
        == rev3
      )
      assert (
        page.locator(f'.message[data-msg-id="{target_id}"] .answer.reply')
        .filter(has_text=third_reply)
        .count()
        == 1
      )
      assert not app.messages.get_message(target_id).replies_seen
      page.screenshot(path=str(tmp_path / "reply-seen-newer-revision.png"))

      context.close()
      browser.close()
  finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)
    store.close()


EXPECTED_LINK_RGB = "rgb(41, 155, 255)"
EXPECTED_PORTRAIT_ORIENTATION = "portrait"
EXPECTED_LIST_MARKERS = ("disc", "circle", "square")
REMOVED_LANDSCAPE_VIEWPORT = "855x325"
REMOVED_LANDSCAPE_WIDTH = 855


def test_messages_links_bullet_hierarchy_mobile_offset_and_portrait_lock(
  tmp_path: Path,
) -> None:
  import json
  import tomllib
  import urllib.request

  playwright = pytest.importorskip("playwright.sync_api")
  nuu_cfg = tomllib.loads(
    (Path(__file__).resolve().parents[3] / "skills/arena-steering/nuu.toml").read_text(
      encoding="utf-8"
    )
  )
  assert REMOVED_LANDSCAPE_VIEWPORT not in nuu_cfg["audit"]["viewports"]
  assert REMOVED_LANDSCAPE_WIDTH not in nuu_cfg["audit"]["widths"]

  store = SqliteStore(tmp_path / "state.sqlite3")
  app = SteeringApp(store)
  for index in range(14):
    app.messages.send_message(
      f"Message {index}: [link](https://example.com/{index})\n\n"
      "- Top item\n"
      "  - Second item\n"
      "    - Third item\n\n"
      "- [x] Task item",
      msg_id=f"dd{index:04x}",
      blocking=False,
    )

  resolved_manifest = app.resolve_asset("/static/assets/manifest.webmanifest")
  assert resolved_manifest is not None
  manifest_json = json.loads(resolved_manifest[0].decode("utf-8"))
  assert manifest_json["orientation"] == EXPECTED_PORTRAIT_ORIENTATION

  server = create_http_server(app, host="127.0.0.1", port=0)
  thread = threading.Thread(target=server.serve_forever, daemon=True)
  thread.start()
  try:
    with urllib.request.urlopen(
      f"http://127.0.0.1:{server.server_port}/static/assets/manifest.webmanifest",
      timeout=5,
    ) as resp:
      assert "application/manifest+json" in resp.headers.get("Content-Type", "")
      assert json.loads(resp.read().decode("utf-8"))["orientation"] == (
        EXPECTED_PORTRAIT_ORIENTATION
      )

    with playwright.sync_playwright() as runner:
      browser = runner.chromium.launch(
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage"],
      )
      desktop = browser.new_page(viewport={"width": 1372, "height": 883})
      desktop.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
      desktop.locator("#history").evaluate("el => { el.scrollTop = 0; }")
      desktop.wait_for_function(
        "() => document.querySelector('#history').scrollTop === 0"
      )
      app.dispatch("POST", "/messages/dd000d/ack", {"markdown": "Unseen reply."})
      desktop.locator("#log-edited").wait_for(state="visible")
      desktop.locator("#log-newest").wait_for(state="visible")
      desktop_metrics = desktop.evaluate("""() => {
        const msg = document.querySelector('.message[data-msg-id="dd0000"] .message-text');
        const uls = [...msg.querySelectorAll('ul')];
        const edited = document.querySelector('#log-edited');
        const newest = document.querySelector('#log-newest').getBoundingClientRect();
        return {
          manifestHref: document.querySelector('link[rel="manifest"]')?.getAttribute('href'),
          linkColor: getComputedStyle(msg.querySelector('a')).color,
          markers: uls.slice(0, 3).map(ul => getComputedStyle(ul).listStyleType),
          taskItemMarker: getComputedStyle(msg.querySelector('.task-list-item')).listStyleType,
          editedTopCss: parseFloat(getComputedStyle(edited).top),
          newestWidth: newest.width,
          newestHeight: newest.height,
        };
      }""")
      assert desktop_metrics["manifestHref"] == "/static/assets/manifest.webmanifest"
      assert desktop_metrics["linkColor"] == EXPECTED_LINK_RGB
      assert tuple(desktop_metrics["markers"]) == EXPECTED_LIST_MARKERS
      assert desktop_metrics["taskItemMarker"] == "none"
      assert desktop_metrics["newestWidth"] > desktop_metrics["newestHeight"]

      mobile = browser.new_page(
        viewport={"width": 411, "height": 799},
        is_mobile=True,
        has_touch=True,
      )
      mobile.add_init_script("""(() => {
        window.__lockedOrientations = [];
        try {
          Object.defineProperty(window.screen, 'orientation', {
            configurable: true,
            value: {
              lock(mode) {
                window.__lockedOrientations.push(mode);
                return Promise.resolve();
              },
            },
          });
        } catch {}
      })();""")
      mobile.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
      mobile.locator("#history").evaluate("el => { el.scrollTop = 0; }")
      mobile.wait_for_function(
        "() => document.querySelector('#history').scrollTop === 0"
      )
      app.dispatch("POST", "/messages/dd000c/ack", {"markdown": "Second unseen reply."})
      mobile.locator("#log-edited").wait_for(state="visible")
      mobile_metrics = mobile.evaluate("""() => {
        const edited = document.querySelector('#log-edited');
        const toolbar = document.querySelector('.log-toolbar');
        return {
          locked: window.__lockedOrientations || [],
          editedTopCss: parseFloat(getComputedStyle(edited).top),
          editedTopRect: edited.getBoundingClientRect().top,
          toolbarBottomRect: toolbar.getBoundingClientRect().bottom,
        };
      }""")
      assert EXPECTED_PORTRAIT_ORIENTATION in mobile_metrics["locked"]
      assert mobile_metrics["editedTopCss"] > desktop_metrics["editedTopCss"]
      assert mobile_metrics["editedTopRect"] > mobile_metrics["toolbarBottomRect"]
      browser.close()
  finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)
    store.close()


def test_composer_paste_unnamed_templates_and_dynamic_lost_ui(tmp_path: Path) -> None:
  playwright = pytest.importorskip("playwright.sync_api")
  state_dir = tmp_path / "arena-state"
  store = SqliteStore(state_dir / "state.sqlite3")
  app = SteeringApp(store)
  png_bytes = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+ip1sAAAAASUVORK5CYII="
  )
  server = create_http_server(app, host="127.0.0.1", port=0)
  thread = threading.Thread(target=server.serve_forever, daemon=True)
  thread.start()
  try:
    with playwright.sync_playwright() as runner:
      browser = runner.chromium.launch(
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage"],
      )
      page = browser.new_page(viewport={"width": 1372, "height": 883})
      page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
      composer = page.locator("#msg")
      composer.wait_for(state="visible")

      # 1. Stage a named file via file input, a clipboard image paste, and pasted lines.
      named_path = tmp_path / "architecture.png"
      named_path.write_bytes(png_bytes)
      page.locator("#composer-file-input").set_input_files(str(named_path))
      page.wait_for_function(
        "() => document.querySelectorAll('.composer-attachment-chip').length === 1"
      )

      page.evaluate(
        """(b64) => {
          const bytes = Uint8Array.from(atob(b64), c => c.charCodeAt(0));
          const file = new File([bytes], 'image.png', { type: 'image/png' });
          const dt = new DataTransfer();
          dt.items.add(file);
          const ev = new ClipboardEvent('paste', { clipboardData: dt, bubbles: true, cancelable: true });
          document.querySelector('#msg').dispatchEvent(ev);
        }""",
        base64.b64encode(png_bytes).decode("ascii"),
      )
      page.wait_for_function(
        "() => document.querySelectorAll('.composer-attachment-chip').length === 2"
      )

      many_lines = "\\n".join(f"line {i}" for i in range(18))
      page.evaluate(
        f"""() => {{
          const dt = new DataTransfer();
          dt.setData('text/plain', '{many_lines}');
          const ev = new ClipboardEvent('paste', {{ clipboardData: dt, bubbles: true, cancelable: true }});
          document.querySelector('#msg').dispatchEvent(ev);
        }}"""
      )
      page.wait_for_function(
        "() => document.querySelectorAll('.composer-attachment-chip[data-upload-status=\"ready\"]').length === 3"
      )

      staged_names = page.evaluate(
        "() => Array.from(document.querySelectorAll('.composer-attachment-name'), el => el.getAttribute('title'))"
      )
      assert staged_names[0] == "architecture.png"
      assert re.fullmatch(r"[0-9]{10,}\.png", staged_names[1])
      assert re.fullmatch(r"18-pasted-lines-[0-9]{10,}\.txt", staged_names[2])

      composer.fill("Send three templates")
      page.locator("#send").click()
      page.wait_for_function(
        "() => document.querySelectorAll('.message:not([data-msg-id^=\"pending-\"])').length === 1"
      )

      sent = app.messages.list_messages(include_hidden=False)[0]
      assert [Path(att.path).name for att in sent.attachments] == [
        f"{sent.id}-architecture.png",
        f"{sent.id}-{staged_names[1]}",
        f"{sent.id}-{staged_names[2]}",
      ]

      # Link to task and delete the pasted-lines file on disk to verify dynamic (lost).
      app.tasks.create_task("ui-reloc-task", "UI relocation", size=3, msg_ids=[sent.id])
      relocated = (
        state_dir / "uploads" / "ui-reloc-task" / f"{sent.id}-{staged_names[2]}"
      )
      assert relocated.is_file()
      relocated.unlink()

      page.reload()
      page.locator(f'.message[data-msg-id="{sent.id}"]').wait_for(state="visible")
      assert page.locator(
        f'.message[data-msg-id="{sent.id}"] .receipt-filename'
      ).all_text_contents() == [f"{staged_names[2]} (lost)"]
      browser.close()
  finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)
    store.close()


@pytest.mark.parametrize("width", [1200, 390])
def test_skip_poll_armed_indicator_persists_and_cancels(
  tmp_path: Path, width: int
) -> None:
  with composer_page(width) as page:
    button = page.locator("#skip-poll")
    page.mouse.move(0, 0)
    page.wait_for_function(
      "document.querySelector('#skip-poll')?.dataset.armed === 'false'"
    )
    idle = button.evaluate(
      "el => { const s = getComputedStyle(el); return [s.color, s.backgroundColor]; }"
    )
    button.click()
    page.mouse.move(0, 0)
    page.wait_for_function(
      "document.querySelector('#skip-poll')?.dataset.armed === 'true'"
    )
    page.wait_for_function("!document.querySelector('#skip-poll')?.dataset.state")
    assert button.get_attribute("aria-label") == "Skip is armed. Press to cancel it."
    armed = button.evaluate(
      "el => { const s = getComputedStyle(el); return [s.color, s.backgroundColor]; }"
    )
    assert armed[0] != idle[0] and armed[1] != idle[1]
    page.screenshot(path=str(tmp_path / f"skip-armed-{width}.png"))
    button.click()
    page.mouse.move(0, 0)
    page.wait_for_function(
      "document.querySelector('#skip-poll')?.dataset.armed === 'false'"
    )
    page.wait_for_function("!document.querySelector('#skip-poll')?.dataset.state")
    assert button.get_attribute("aria-label") == "Ask the agent to end its wait now"
    page.wait_for_function(
      "expected => { const s = getComputedStyle(document.querySelector('#skip-poll')); "
      "return s.color === expected[0] && s.backgroundColor === expected[1]; }",
      arg=idle,
    )
    assert (
      button.evaluate(
        "el => { const s = getComputedStyle(el); return [s.color, s.backgroundColor]; }"
      )
      == idle
    )
    page.screenshot(path=str(tmp_path / f"skip-canceled-{width}.png"))


@pytest.mark.parametrize("width", [390, 1200])
def test_timestamps_use_regular_proportional_one(tmp_path: Path, width: int) -> None:
  with composer_page(width) as page:
    page.locator("#msg").fill("Timestamp numeral sample")
    page.locator("#send").click()
    stamp = page.locator("#history .message time[datetime]").first
    stamp.wait_for()
    stamp.evaluate("el => { el.textContent = '1 minute ago'; }")
    page.screenshot(path=str(tmp_path / f"timestamp-regular-{width}.png"))
    assert stamp.evaluate("el => getComputedStyle(el).fontVariantNumeric") == "normal"
    assert "mono" not in stamp.evaluate("el => getComputedStyle(el).fontFamily").lower()
    regular = stamp.evaluate("""el => {
      const range = document.createRange(); range.selectNodeContents(el);
      return range.getBoundingClientRect().width;
    }""")
    stamp.evaluate("el => { el.style.fontVariantNumeric = 'tabular-nums'; }")
    tabular = stamp.evaluate("""el => {
      const range = document.createRange(); range.selectNodeContents(el);
      return range.getBoundingClientRect().width;
    }""")
    assert regular < tabular
    page.screenshot(path=str(tmp_path / f"timestamp-tabular-{width}.png"))


@pytest.mark.parametrize("width", [390, 1200])
def test_hidden_reveal_keeps_new_regular_messages(tmp_path: Path, width: int):
  with composer_page(width) as page:
    page.locator("#msg").fill("Original regular message")
    page.locator("#send").click()
    page.get_by_text("Original regular message", exact=True).wait_for()
    page.request.post(
      page.url.split("?")[0] + "messages",
      data={
        "id": "abc123",
        "body": "Hidden window sample",
        "hidden": True,
        "blocking": False,
      },
    )
    page.locator("#msg").fill("Latest regular message")
    page.locator("#send").click()
    latest = page.get_by_text("Latest regular message", exact=True)
    latest.wait_for()
    page.get_by_role("button", name="Show hidden messages", exact=True).click()
    page.get_by_text("Hidden window sample", exact=True).wait_for()
    page.get_by_role("button", name="Hide hidden messages", exact=True).click()
    page.locator("#msg").fill("New regular message")
    page.locator("#send").click()
    new = page.get_by_text("New regular message", exact=True)
    new.wait_for()
    # The toggle reuses its cached hidden window, so a repeat reveal may issue
    # no request at all. The regular messages must survive it regardless.
    page.get_by_role("button", name="Show hidden messages", exact=True).click()
    # The reveal may render in two frames, so wait for the whole set.
    page.wait_for_function(
      """() => document.querySelector('[data-msg-id=abc123]')
        && document.body.innerText.includes('New regular message')
        && document.body.innerText.includes('Latest regular message')"""
    )
    assert new.is_visible() and latest.is_visible()
    assert page.get_by_text("Original regular message", exact=True).is_visible()
    page.screenshot(path=str(tmp_path / f"hidden-reveal-{width}.png"))
    page.get_by_role("button", name="Hide hidden messages", exact=True).click()
    assert new.is_visible() and latest.is_visible()


def test_survey_answers_open_by_touch_and_close_on_outside_tap(tmp_path: Path):
  from arena_steering import survey

  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore()
  app = SteeringApp(store)
  app.messages.submit_survey(survey.template())
  server = create_http_server(app, host="127.0.0.1", port=0)
  thread = threading.Thread(target=server.serve_forever, daemon=True)
  thread.start()
  try:
    with playwright.sync_playwright() as runner:
      browser = runner.chromium.launch(args=["--no-sandbox"])
      try:
        page = browser.new_page(
          viewport={"width": 390, "height": 800},
          is_mobile=True,
          has_touch=True,
          reduced_motion="reduce",
        )
        page.goto(f"http://127.0.0.1:{server.server_port}/?transport=poll")
        page.locator("#survey-open").tap()
        trigger = page.locator(".survey-id-trigger").first
        trigger.tap()
        tip = page.locator(".survey-answer-tooltip").first
        assert tip.is_visible()
        assert tip.locator(".survey-answer-row").count() > 0
        page.screenshot(path=str(tmp_path / "survey-touch-answer.png"))
        trigger.tap()
        assert tip.is_hidden()
        trigger.tap()
        assert tip.is_visible()
        page.get_by_role("heading", name="Survey Verification").tap()
        assert tip.is_hidden()
      finally:
        browser.close()
  finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)
    store.close()


@pytest.mark.parametrize("width", [390, 1200])
def test_survey_subtitle_stays_inside_scroll_clip(tmp_path: Path, width: int):
  from arena_steering import survey

  with composer_page(width) as page:
    response = page.request.post(
      page.url.split("?")[0] + "survey", data={"answers": survey.template()}
    )
    assert response.ok
    page.locator("#survey-open").click()
    page.locator(".survey-subtitle").wait_for()
    page.screenshot(path=str(tmp_path / f"survey-subtitle-{width}.png"))
    bounds = page.locator(".survey-subtitle").evaluate("""el => {
      const range = document.createRange();
      range.selectNodeContents(el);
      const text = range.getBoundingClientRect();
      const clip = el.closest('.modal-body').getBoundingClientRect();
      return {top: text.top, bottom: text.bottom, clipTop: clip.top, clipBottom: clip.bottom};
    }""")
    assert bounds["top"] >= bounds["clipTop"]
    assert bounds["bottom"] <= bounds["clipBottom"]
