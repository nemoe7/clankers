"""Keep a failed older-page load visible until the user retries."""

import os
import threading

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
