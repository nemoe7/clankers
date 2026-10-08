"""Check the preview proxy always serves an installable HTML main page.

The proxy injects the manifest link into the preview HTML, and the viewer root carries the
same link on its own page. The root once answered a plain-text line with an empty DOM, so no
manifest ever landed and Chrome never offered the install (owner notes 59ec9e1 and fd9315b).
This test starts the real server on a loopback port and reads what it answers.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "skills" / "arena-skill" / "preview-proxy" / "server.js"
MANIFEST = '<link rel="manifest" href="/pwa/manifest.webmanifest">'
REGISTER = '<script src="/pwa/register.js" defer></script>'
SECRET = "test-secret-that-is-at-least-thirty-two-characters"


def free_port() -> int:
  with socket.socket() as probe:
    probe.bind(("127.0.0.1", 0))
    return probe.getsockname()[1]


def node(script: str) -> str:
  """Run one expression against the server module and return its stdout."""
  result = subprocess.run(
    ["node", "-e", script],
    capture_output=True,
    text=True,
    check=True,
    cwd=str(SERVER.parent),
  )
  return result.stdout.strip()


def get(port: int, path: str, cookie: str = "") -> tuple[int, str, str]:
  request = urllib.request.Request(f"http://127.0.0.1:{port}{path}")
  if cookie:
    request.add_header("Cookie", cookie)
  try:
    with urllib.request.urlopen(request, timeout=10) as answer:
      return (
        answer.status,
        answer.headers.get("content-type", ""),
        answer.read().decode(),
      )
  except urllib.error.HTTPError as error:
    return error.code, error.headers.get("content-type", ""), error.read().decode()


def test_the_viewer_root_serves_an_installable_page():
  """The root page carries the manifest link and a URL box, in HTML, with no target set."""
  port = free_port()
  server = subprocess.Popen(
    ["node", "server.js"],
    cwd=str(SERVER.parent),
    env={
      "PATH": "/usr/local/bin:/usr/bin:/bin",
      "PORT": str(port),
      "PROXY_COOKIE_SECRET": SECRET,
    },
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
  )
  try:
    deadline = time.time() + 15
    while time.time() < deadline:
      try:
        status, kind, body = get(port, "/healthz")
        if status == 200:
          break
      except OSError:
        time.sleep(0.1)
    else:
      raise AssertionError(f"The proxy never answered: {server.stdout.read()}")

    # The root carries a real page: HTML, the manifest link in it, and the URL form.
    status, kind, body = get(port, "/")
    assert status == 200, status
    assert "text/html" in kind, kind
    assert MANIFEST in body, "the main page must carry the manifest link"
    assert REGISTER in body, "the main page must carry the worker registration"
    assert 'name="url"' in body, "the main page must offer the preview URL box"
    assert body.index(MANIFEST) < body.index("</head>"), "the link belongs in the head"
    # A rejected URL still answers the page, so the DOM never loses the manifest.
    status, kind, body = get(port, "/?url=https%3A%2F%2Fexample.com%2F")
    assert status == 400, status
    assert "text/html" in kind, kind
    assert MANIFEST in body, "a rejected URL must keep the manifest link"
    # A page under the proxy that is not the root keeps its short plain-text refusal.
    status, kind, _ = get(port, "/somewhere?url=https%3A%2F%2Fexample.com%2F")
    assert status == 400 and "text/plain" in kind, (status, kind)
    # The health check keeps its bare text answer.
    assert get(port, "/healthz") == (200, "text/plain; charset=utf-8", "ok")
  finally:
    server.terminate()
    server.wait(timeout=10)


def test_injection_survives_a_page_without_a_head():
  """The injected tags ride any served page shape, and a compressed body still rewrites."""
  script = (
    "const proxy = require('./server.js');"
    "const shapes = {"
    "head: '<!doctype html><html><head><title>t</title></head><body>x</body></html>',"
    "body: '<!doctype html><html><body>x</body></html>',"
    "fragment: '<p>x</p>'"
    "};"
    "const out = {};"
    "for (const [name, html] of Object.entries(shapes)) out[name] = proxy.injectPwa(html);"
    "const zlib = require('node:zlib');"
    "out.gzip = proxy.decodeBody(zlib.gzipSync(Buffer.from('<html></html>')), 'gzip').toString();"
    "out.broken = proxy.decodeBody(Buffer.from('not gzip'), 'gzip');"
    "console.log(JSON.stringify(out));"
  )
  result = json.loads(node(script))
  assert MANIFEST in result["head"] and result["head"].index(MANIFEST) < result[
    "head"
  ].index("</head>")
  opener = result["body"].index("<body>") + len("<body>")
  assert result["body"].index(MANIFEST) == opener, (
    "a head-less page takes the tags at its body"
  )
  assert result["fragment"].startswith(MANIFEST), result["fragment"]
  assert result["gzip"] == "<html></html>", result["gzip"]
  assert result["broken"] is None, "a body that will not decode must stay untouched"


def sign_origin(origin: str) -> str:
  """The cookie the proxy hands a viewer, signed the way the server signs it."""
  payload = base64.urlsafe_b64encode(origin.encode()).decode().rstrip("=")
  signature = (
    base64.urlsafe_b64encode(
      hmac.new(SECRET.encode(), payload.encode(), hashlib.sha256).digest()
    )
    .decode()
    .rstrip("=")
  )
  return f"{payload}.{signature}"


def test_the_installed_app_opens_the_proxy_home():
  """The installed app opens on the URL box, never on the sandbox the install came from.

  The manifest's start URL carried the preview origin, so opening the app without a shared link
  reopened a sandbox whose address was dead. Every open lands on the home page, and the URL box
  or the share sheet picks the preview from there (owner note ec56b4d).
  """
  port = free_port()
  server = subprocess.Popen(
    ["node", "server.js"],
    cwd=str(SERVER.parent),
    env={
      "PATH": "/usr/local/bin:/usr/bin:/bin",
      "PORT": str(port),
      "PROXY_COOKIE_SECRET": SECRET,
    },
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
  )
  try:
    deadline = time.time() + 15
    while time.time() < deadline:
      try:
        if get(port, "/healthz")[0] == 200:
          break
      except OSError:
        time.sleep(0.1)
    else:
      raise AssertionError(f"The proxy never answered: {server.stdout.read()}")

    status, kind, body = get(port, "/pwa/manifest.webmanifest")
    assert status == 200 and "manifest" in kind, (status, kind)
    assert json.loads(body)["start_url"] == "/", (
      "a fresh install starts on the home page"
    )
    cookie = f"arena_preview_target={sign_origin('https://sbx-demo.arena.site')}"
    status, _, body = get(port, "/pwa/manifest.webmanifest", cookie=cookie)
    assert status == 200, status
    manifest = json.loads(body)
    assert manifest["start_url"] == "/", "a signed target still starts on the home page"
    assert manifest["id"] == "/", "the installed app keeps one identity across targets"
    assert manifest["scope"] == "/"
  finally:
    server.terminate()
    server.wait(timeout=10)
