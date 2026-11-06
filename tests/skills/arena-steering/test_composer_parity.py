"""Browser regressions for the message composer shared with v1."""

from __future__ import annotations

import base64
import os
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest
from arena_steering.server import SteeringApp, create_http_server
from arena_steering.store import SqliteStore

pytestmark = pytest.mark.skipif(
  not os.environ.get("ARENA_STEERING_CHROMIUM"),
  reason="Set ARENA_STEERING_CHROMIUM to run the browser regression",
)


@contextmanager
def composer_page(width: int) -> Iterator[object]:
  playwright = pytest.importorskip("playwright.sync_api")
  store = SqliteStore()
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
    assert page.locator("#msg").input_value() == ""
    page.screenshot(path=str(tmp_path / f"optimistic-send-{width}.png"))
    page.evaluate("window.releaseSend()")
    page.wait_for_function("!document.querySelector('#send')?.disabled")
    message = page.locator("#history .message").filter(has_text="Immediate message")
    assert message.count() == 1
    confirmed_id = message.locator("button.receipt-id code.msg-id")
    confirmed_id.wait_for()
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
    assert page.locator("#msg").input_value() == ""
    page.evaluate("window.releaseSendResponse()")
    page.wait_for_function("!document.querySelector('#send')?.disabled")
    assert matching.count() == 1


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
