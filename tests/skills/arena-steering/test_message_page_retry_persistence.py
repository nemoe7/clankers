"""Keep a failed older-page load visible until the user retries."""

import os
import threading
from pathlib import Path

import pytest
from arena_steering.server import SteeringApp, create_http_server
from arena_steering.store import SqliteStore


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
