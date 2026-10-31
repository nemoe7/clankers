"""Browser regressions for the message composer shared with v1."""

from __future__ import annotations

import base64
import os
import threading
from collections.abc import Iterator
from contextlib import contextmanager

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
    page.evaluate("window.releaseUpload()")
    page.wait_for_function("window.uploadCalls === 2")
    page.wait_for_function(
      "Array.from(document.querySelectorAll('#history .message'))"
      ".some(e => e.textContent.includes('Please inspect this file'))"
    )
    assert page.locator("#composer-attachments").is_hidden()
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
    assert preview.locator("p").first.locator("br").count() == 1
    assert preview.locator("p").first.inner_text() == "First line\nSecond line"
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
    page.wait_for_selector('code[data-msg-id="aaaa01"]', timeout=6000)
    page.locator('code[data-msg-id="aaaa01"]').click()
    assert page.locator('[data-remove-reply-parent="aaaa01"]').count() == 1
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
    assert matching.locator('[data-parent-id="aaaa01"]').count() == 1
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
