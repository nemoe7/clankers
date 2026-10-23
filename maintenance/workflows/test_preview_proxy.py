"""Check that the preview proxy serves an installable HTML main page.

The proxy injects a manifest link into preview HTML. The viewer root also carries this link.
Start the server on a loopback port and check its responses.
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

ROOT = Path(__file__).resolve().parents[2]
SERVER = ROOT / "skills" / "arena-skill" / "arena-preview-proxy" / "server.js"
MANIFEST = '<link rel="manifest" href="/pwa/manifest.webmanifest">'
REGISTER = '<script src="/pwa/register.js" defer></script>'
RECENT = '<script src="/pwa/recent.js" defer></script>'
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
    },
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
  )
  try:
    deadline = time.time() + 15
    while time.time() < deadline:
      try:
        status, type, body = get(port, "/healthz")
        if status == 200:
          break
      except OSError:
        time.sleep(0.1)
    else:
      raise AssertionError(f"The proxy never answered: {server.stdout.read()}")

    # The root carries a real page: HTML, the manifest link in it, and the URL form.
    status, type, body = get(port, "/")
    assert status == 200, status
    assert "text/html" in type, type
    assert MANIFEST in body, "the main page must carry the manifest link"
    assert REGISTER in body, "the main page must carry the worker registration"
    assert 'name="url"' in body, "the main page must offer the preview URL box"
    assert body.index(MANIFEST) < body.index("</head>"), "the link belongs in the head"
    assert RECENT in body and 'id="recent"' in body, (
      "the main page must hold the recent list"
    )
    status, type, _ = get(port, "/pwa/recent.js")
    assert status == 200 and "javascript" in type, (status, type)
    # A rejected URL still answers the page, so the DOM never loses the manifest.
    status, type, body = get(port, "/?url=https%3A%2F%2Fexample.com%2F")
    assert status == 400, status
    assert "text/html" in type, type
    assert MANIFEST in body, "a rejected URL must keep the manifest link"
    assert RECENT in body, "a rejected URL must keep the recent list"
    # A page under the proxy that is not the root keeps its short plain-text refusal.
    status, type, _ = get(port, "/somewhere?url=https%3A%2F%2Fexample.com%2F")
    assert status == 400 and "text/plain" in type, (status, type)
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
  assert "recent.js" not in result["head"], (
    "a proxied preview never loads the chooser list"
  )
  assert result["gzip"] == "<html></html>", result["gzip"]
  assert result["broken"] is None, "a body that will not decode must stay untouched"


def test_the_root_always_opens_the_chooser():
  """The root serves the chooser every time. The proxy remembers nothing.

  A signed target once let a later open skip straight to a stored preview, and a stale
  address sent the owner to a dead site. Every open lands on the chooser now, whatever
  the request carries.
  """
  port = free_port()
  server = subprocess.Popen(
    ["node", "server.js"],
    cwd=str(SERVER.parent),
    env={
      "PATH": "/usr/local/bin:/usr/bin:/bin",
      "PORT": str(port),
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

    # A plain open lands on the chooser.
    status, type, body = get(port, "/")
    assert status == 200 and "text/html" in type, (status, type)
    assert 'name="url"' in body, "the root must open the chooser"
    assert MANIFEST in body, "the chooser keeps the manifest link"
    # Even a request that still carries the old target cookie lands on the chooser.
    cookie = f"arena_preview_target={sign_origin('https://sbx-demo.arena.site')}"
    status, type, body = get(port, "/", cookie=cookie)
    assert status == 200 and "text/html" in type, (status, type)
    assert 'name="url"' in body, "a carried target must not skip the chooser"
  finally:
    server.terminate()
    server.wait(timeout=10)


def sign_origin(origin: str) -> str:
  """Build the retired target cookie, signed the way the old proxy signed it.

  The proxy no longer sets this cookie. The checks send it to prove that the proxy ignores it.
  """
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
  or the share sheet selects the preview from there.
  """
  port = free_port()
  server = subprocess.Popen(
    ["node", "server.js"],
    cwd=str(SERVER.parent),
    env={
      "PATH": "/usr/local/bin:/usr/bin:/bin",
      "PORT": str(port),
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

    status, type, body = get(port, "/pwa/manifest.webmanifest")
    assert status == 200 and "manifest" in type, (status, type)
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


def test_a_page_call_takes_its_target_from_the_referer():
  """A page's own calls carry no url, so the proxy reads the target from the page's Referer.

  Without that target a bare path gets the chooser as HTML, and the page fails to parse it.
  Only a viewer page with a valid preview url counts. The viewer root keeps its chooser.
  """
  script = (
    "const proxy = require('./server.js');"
    "const at = path => new URL(path, 'http://proxy.invalid');"
    "const viewer = 'https://proxy.example/?url=https%3A%2F%2Fsbx-demo.arena.site%2F';"
    "const out = {};"
    "const target = (path, referer) => {"
    "  const found = proxy.targetFromReferer(at(path), referer);"
    "  return found ? found.href : null;"
    "};"
    "out.api = target('/api/reports/a/submit?name=a%20b&x=1', viewer);"
    "out.noReferer = target('/api/state', undefined);"
    "out.garbage = target('/api/state', 'not a url');"
    "out.rejected = target('/api/state', 'https://proxy.example/?url=https%3A%2F%2Fexample.com%2F');"
    "out.otherPath = target('/api/state', 'https://proxy.example/x?url=https%3A%2F%2Fsbx-demo.arena.site%2F');"
    "console.log(JSON.stringify(out));"
  )
  result = json.loads(node(script))
  assert result["api"] == (
    "https://sbx-demo.arena.site/api/reports/a/submit?name=a%20b&x=1"
  ), result
  assert result["noReferer"] is None, result
  assert result["garbage"] is None, result
  assert result["rejected"] is None, (
    "a target outside sbx-*.arena.site must stay refused"
  )
  assert result["otherPath"] is None, "only the viewer root names a target"


def test_the_chooser_keeps_the_last_ten_previews():
  """The chooser lists the last ten preview roots opened from it, newest first.

  The list lives in the browser's storage, so the server still keeps no memory. Every page on the
  proxy origin can write that storage, so a read keeps valid preview roots only.
  """
  script = (
    "const recent = require('./assets/recent.js');"
    "const roots = n => Array.from({ length: n }, (_, i) => `https://sbx-p${i}.arena.site`);"
    "const out = {};"
    "out.accepted = ['https://sbx-demo.arena.site/', 'https://SBX-Demo.arena.site',"
    " 'https://sbx-demo.arena.site:443/'].map(recent.previewRoot);"
    "out.refused = ['https://example.com/', 'http://sbx-demo.arena.site/',"
    " 'https://sbx-demo.arena.site/x', 'https://sbx-demo.arena.site/?a=1',"
    " 'https://sbx-demo.arena.site/#x', 'https://u:p@sbx-demo.arena.site/',"
    " 'https://sbx-demo.arena.site:444/', 'javascript:alert(1)', 'not a url', 42, null]"
    ".map(recent.previewRoot);"
    "out.capped = roots(12).reduce(recent.remember, []);"
    "out.moved = recent.remember(roots(3).reduce(recent.remember, []), 'https://sbx-p0.arena.site');"
    "out.forgot = recent.forget(roots(3), 'https://sbx-p1.arena.site');"
    "out.cleaned = recent.clean(['https://sbx-a.arena.site', 'https://sbx-a.arena.site',"
    " 'javascript:x', 7, ...roots(12)]);"
    "out.notList = recent.clean({ a: 1 });"
    "console.log(JSON.stringify(out));"
  )
  result = json.loads(node(script))
  root = "https://sbx-p{}.arena.site".format
  assert result["accepted"] == ["https://sbx-demo.arena.site"] * 3, result["accepted"]
  assert result["refused"] == [None] * 11, "only HTTPS preview roots enter the list"
  assert result["capped"] == [root(i) for i in range(11, 1, -1)], (
    "ten entries, newest first"
  )
  assert result["moved"] == [root(0), root(2), root(1)], (
    "a reopened root moves to the top"
  )
  assert result["forgot"] == [root(0), root(2)], result["forgot"]
  assert result["cleaned"] == [
    "https://sbx-a.arena.site",
    *[root(i) for i in range(9)],
  ], "a stored list drops junk and duplicates and keeps ten entries"
  assert result["notList"] == [], result["notList"]


class _NoRedirect(urllib.request.HTTPRedirectHandler):
  """Refuse redirects so a share response shows its own status and Location header."""

  def redirect_request(self, req, fp, code, msg, headers, newurl):
    return None


def test_a_share_rides_through_the_chooser_into_the_recent_list():
  """A share target lands on the chooser, which saves the root before the preview opens.

  The share sheet jumps straight into a preview, so the chooser never sees the open and the
  root joins no recent list. The share endpoint now redirects to the chooser with the root in
  a `shared` parameter. The chooser script checks that parameter, saves the root among the
  ten most recent, and replaces the page with the preview URL. The preview itself still loads
  no chooser list.
  """
  port = free_port()
  server = subprocess.Popen(
    ["node", "server.js"],
    cwd=str(SERVER.parent),
    env={
      "PATH": "/usr/local/bin:/usr/bin:/bin",
      "PORT": str(port),
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

    opener = urllib.request.build_opener(_NoRedirect)

    def share(path):
      try:
        with opener.open(f"http://127.0.0.1:{port}{path}", timeout=10) as answer:
          return answer.status, answer.headers.get("location", "")
      except urllib.error.HTTPError as error:
        return error.code, error.headers.get("location", "")

    # A shared URL answers with a redirect that carries the root to the chooser.
    status, location = share("/pwa/share?url=https%3A%2F%2Fsbx-shared.arena.site%2F")
    assert status == 302, status
    assert location == "/?shared=https%3A%2F%2Fsbx-shared.arena.site%2F", location
    # The share can also carry the link inside its text field.
    status, location = share(
      "/pwa/share?text=See+https%3A%2F%2Fsbx-text.arena.site%2F+now"
    )
    assert status == 302, status
    assert location == "/?shared=https%3A%2F%2Fsbx-text.arena.site%2F", location
    # The landing request keeps the chooser: `shared` names no proxy target.
    status, type, body = get(port, location)
    assert status == 200 and "text/html" in type, (status, type)
    assert 'name="url"' in body, "the shared landing opens the chooser"
    assert RECENT in body, "the shared landing carries the recent list"
    # A rejected share still answers with its plain-text refusal.
    status, _ = share("/pwa/share?url=https%3A%2F%2Fexample.com%2F")
    assert status == 400, status
  finally:
    server.terminate()
    server.wait(timeout=10)

  # The chooser script reads a valid root from `shared`, refuses junk, and builds the
  # preview URL the form uses. A plain preview link carries `url` and adds no entry.
  script = (
    "const recent = require('./assets/recent.js');"
    "const roots = n => Array.from({ length: n }, (_, i) => `https://sbx-p${i}.arena.site`);"
    "const out = {};"
    "out.fromShared = recent.fromShare('?shared=https%3A%2F%2Fsbx-shared.arena.site%2F');"
    "out.fromJunk = recent.fromShare('?shared=javascript%3Aalert(1)');"
    "out.fromLink = recent.fromShare('?url=https%3A%2F%2Fsbx-shared.arena.site%2F');"
    "out.href = recent.viewerHref('https://sbx-shared.arena.site');"
    "out.joined = recent.remember(roots(10).reduce(recent.remember, []),"
    " recent.fromShare('?shared=https%3A%2F%2Fsbx-shared.arena.site%2F'));"
    "console.log(JSON.stringify(out));"
  )
  result = json.loads(node(script))
  assert result["fromShared"] == "https://sbx-shared.arena.site", result["fromShared"]
  assert result["fromJunk"] is None, result["fromJunk"]
  assert result["fromLink"] is None, "a plain preview link still adds no entry"
  assert result["href"] == "/?url=https%3A%2F%2Fsbx-shared.arena.site%2F", result[
    "href"
  ]
  assert result["joined"] == [
    "https://sbx-shared.arena.site",
    *[f"https://sbx-p{i}.arena.site" for i in range(9, 0, -1)],
  ], "the shared root joins the ten stored roots at the top"


def test_renaming_a_recent_entry_changes_its_label_only():
  """A rename stores a label beside the root and leaves the destination alone.

  The chooser shows each recent root as its host. An owner label replaces that text while the
  stored root, and every link built from it, keep the exact preview origin. Labels trim their
  edges, drop control characters, cap at 48 characters and vanish when the root leaves the list.
  """
  script = (
    "const recent = require('./assets/recent.js');"
    "const rootA = 'https://sbx-a.arena.site';"
    "const out = {};"
    "out.applied = recent.applyName({}, rootA, '  My Box  ');"
    "out.stripped = recent.applyName({}, rootA, 'bad\\u0000name\\nhere');"
    "out.capped = recent.applyName({}, rootA, 'x'.repeat(60));"
    "out.cleared = recent.applyName({ [rootA]: 'Box' }, rootA, '   ');"
    "out.kept = recent.applyName({ 'https://sbx-b.arena.site': 'Other' }, rootA, 'Box');"
    "out.pruned = recent.cleanNames([rootA], {"
    " [rootA]: 'Box', 'https://sbx-gone.arena.site': 'Ghost',7: 'junk'});"
    "out.labeled = recent.displayName({ [rootA]: 'My Box' }, rootA);"
    "out.defaulted = recent.displayName({}, rootA);"
    "out.href = recent.viewerHref(rootA);"
    "console.log(JSON.stringify(out));"
  )
  result = json.loads(node(script))
  root = "https://sbx-a.arena.site"
  assert result["applied"] == {"https://sbx-a.arena.site": "My Box"}, result["applied"]
  assert result["stripped"] == {"https://sbx-a.arena.site": "badnamehere"}, result[
    "stripped"
  ]
  assert len(result["capped"][root]) == 48, result["capped"]
  assert result["cleared"] == {}, "an empty label falls back to the host"
  assert result["kept"] == {
    "https://sbx-b.arena.site": "Other",
    "https://sbx-a.arena.site": "Box",
  }, "renaming one root keeps the other labels"
  assert result["pruned"] == {"https://sbx-a.arena.site": "Box"}, (
    "labels outside the stored list drop"
  )
  assert result["labeled"] == "My Box", result["labeled"]
  assert result["defaulted"] == "sbx-a.arena.site", "an unlabeled root shows its host"
  assert result["href"] == "/?url=https%3A%2F%2Fsbx-a.arena.site%2F", (
    "the destination URL never carries a label"
  )


def test_recent_root_writes_prune_stored_labels():
  """Remove labels only after their roots leave the stored list."""
  script = (
    "const fs = require('node:fs');"
    "const vm = require('node:vm');"
    "const a = 'https://sbx-a.arena.site', b = 'https://sbx-b.arena.site';"
    "const values = new Map(); let fail = false;"
    "const context = { URL, module: { exports: {} }, localStorage: {"
    " getItem: key => values.get(key) ?? null,"
    " setItem: (key, value) => {"
    "  if (fail) throw new Error('storage unavailable'); values.set(key, value);"
    " } } };"
    "vm.runInNewContext(fs.readFileSync('assets/recent.js', 'utf8'), context);"
    "context.save([a, b]); context.writeNames({ [a]: 'A', [b]: 'B' });"
    "fail = true; context.save([b]);"
    "const failed = { roots: context.load(), names: context.readNames() };"
    "fail = false; context.save([b]); const pruned = context.readNames();"
    "context.save([]); const empty = context.readNames();"
    "console.log(JSON.stringify({ a, b, failed, pruned, empty }));"
  )
  result = json.loads(node(script))
  a, b = result["a"], result["b"]
  assert result["failed"] == {"roots": [a, b], "names": {a: "A", b: "B"}}
  assert result["pruned"] == {b: "B"}
  assert result["empty"] == {}


def test_an_open_recent_list_resets_and_rearms_at_the_boundary():
  """Clear stored roots, labels, and rendered rows when the boundary callback runs."""
  script = (
    "const fs = require('node:fs'), vm = require('node:vm');"
    "const root = 'https://sbx-a.arena.site';"
    "const first = Date.parse('2026-10-15T17:59:00Z'); let at = first;"
    "const boundary = Date.parse('2026-10-15T18:00:00Z');"
    "const values = new Map(); let timer, rendered, scheduled = 0;"
    "class Clock extends Date {"
    " constructor(...args) { super(...(args.length ? args : [at])); }"
    " static now() { return at; } }"
    "const target = { addEventListener() {} };"
    "const context = { URL, URLSearchParams, Date: Clock, module: { exports: {} },"
    " location: { search: '' }, document: {"
    " getElementById: () => target, querySelector: () => target },"
    " setTimeout: (callback, delay) => { timer = { callback, delay }; scheduled++; },"
    " localStorage: { getItem: key => values.get(key) ?? null,"
    " setItem: (key, value) => values.set(key, value) } };"
    "vm.runInNewContext(fs.readFileSync('assets/recent.js', 'utf8'), context);"
    "context.show = () => { rendered = context.load(); };"
    "context.save([root]); context.writeNames({ [root]: 'A' });"
    "context.start();"
    "const before = { roots: context.load(), delay: timer.delay, scheduled };"
    "at = boundary; timer.callback();"
    "const after = { roots: context.load(), names: context.readNames(), rendered,"
    " stamp: Number(values.get('arena-preview-recent-reset')), scheduled };"
    "context.save([root]); at = Date.parse('2026-10-16T12:01:00Z');"
    "timer.callback();"
    "const missed = { roots: context.load(), rendered,"
    " stamp: Number(values.get('arena-preview-recent-reset')), delay: timer.delay };"
    "console.log(JSON.stringify({ root, first, boundary, before, after, missed }));"
  )
  result = json.loads(node(script))
  assert result["before"]["roots"] == [result["root"]]
  assert result["before"]["delay"] == result["boundary"] - result["first"]
  assert result["after"]["roots"] == result["after"]["rendered"] == []
  assert result["after"]["names"] == {}
  assert result["after"]["stamp"] == result["boundary"]
  assert result["after"]["scheduled"] > result["before"]["scheduled"]
  assert result["missed"]["roots"] == result["missed"]["rendered"] == []
  assert result["missed"]["stamp"] > result["after"]["stamp"]
  assert result["missed"]["delay"] > 0


def test_the_recent_list_clears_at_pht_reset_boundaries():
  """A boundary at 02:00, 08:00, 14:00 or 20:00 PHT clears the stored list once crossed.

  The reset stamps the boundary it cleared, so a boundary passed with the app closed clears on
  the next open and several missed boundaries still clear once. PHT holds UTC+8 all year, so the
  boundary math runs in fixed offsets.
  """
  script = (
    "const recent = require('./assets/recent.js');"
    "const out = {};"
    # 14:59 PHT sits after the 14:00 boundary.
    "out.after14 = recent.previousBoundary(new Date('2026-10-15T06:59:00Z'));"
    # Exactly 14:00 PHT counts as having reached that boundary.
    "out.at14 = recent.previousBoundary(new Date('2026-10-15T06:00:00Z'));"
    # 01:30 PHT falls back to the previous day's 20:00 boundary.
    "out.before02 = recent.previousBoundary(new Date('2026-10-14T17:30:00Z'));"
    # 04:00 PHT sits after 02:00 the same PHT day.
    "out.after02 = recent.previousBoundary(new Date('2026-10-14T20:00:00Z'));"
    "out.missed = recent.needsReset(0, 1000);"
    "out.fresh = recent.needsReset(null, 1000);"
    "out.same = recent.needsReset(1000, 1000);"
    "out.ahead = recent.needsReset(2000, 1000);"
    "console.log(JSON.stringify(out));"
  )
  result = json.loads(node(script))
  assert result["after14"] == "2026-10-15T06:00:00.000Z", result["after14"]
  assert result["at14"] == "2026-10-15T06:00:00.000Z", result["at14"]
  assert result["before02"] == "2026-10-14T12:00:00.000Z", result["before02"]
  assert result["after02"] == "2026-10-14T18:00:00.000Z", result["after02"]
  assert result["missed"] is True, "a boundary behind the stamp clears the list"
  assert result["fresh"] is False, "a first open without a stamp keeps the list"
  assert result["same"] is False, (
    "the boundary the stamp already recorded clears nothing"
  )
  assert result["ahead"] is False, "a clock behind the stamp clears nothing"


def test_pwa_recent_endpoint_accepts_posted_previews_and_merges_into_chooser():
  """POST /pwa/recent records { url, name } and GET /pwa/recent returns entries for recent.js."""
  port = free_port()
  server = subprocess.Popen(
    ["node", "server.js"],
    cwd=str(SERVER.parent),
    env={
      "PATH": "/usr/local/bin:/usr/bin:/bin",
      "PORT": str(port),
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

    def post_json(path: str, payload: dict) -> tuple[int, str, dict]:
      data = json.dumps(payload).encode("utf-8")
      req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
      )
      try:
        with urllib.request.urlopen(req, timeout=10) as answer:
          return (
            answer.status,
            answer.headers.get("access-control-allow-origin", ""),
            json.loads(answer.read().decode()),
          )
      except urllib.error.HTTPError as error:
        return (
          error.code,
          error.headers.get("access-control-allow-origin", ""),
          {},
        )

    status, cors, body = post_json(
      "/pwa/recent",
      {"url": "https://sbx-port3000.arena.site/", "name": "clankers - Web App"},
    )
    assert status == 200, status
    assert cors == "*", cors
    assert body["entries"] == [
      {"url": "https://sbx-port3000.arena.site", "name": "clankers - Web App"}
    ]

    status, _, body = post_json(
      "/",
      {
        "url": "https://sbx-port8000.arena.site/app?tab=notes",
        "name": "clankers - Steering",
      },
    )
    assert status == 200, status
    assert body["entries"][0] == {
      "url": "https://sbx-port8000.arena.site",
      "name": "clankers - Steering",
    }

    status, _, raw = get(port, "/pwa/recent")
    assert status == 200, status
    fetched = json.loads(raw)
    assert len(fetched["entries"]) == 2

    bad_status, _, _ = post_json(
      "/pwa/recent", {"url": "https://example.com/", "name": "bad"}
    )
    assert bad_status == 400, bad_status
  finally:
    server.terminate()
    server.wait(timeout=10)

  script = (
    "const recent = require('./assets/recent.js');"
    "const merged = recent.mergeRemote("
    "  ['https://sbx-existing.arena.site', 'https://sbx-dead.arena.site'],"
    "  { 'https://sbx-existing.arena.site': 'Existing', 'https://sbx-dead.arena.site': 'Dead' },"
    "  ["
    "    { url: 'https://sbx-port8000.arena.site/', name: 'clankers - Steering' },"
    "    { url: 'https://sbx-port3000.arena.site/', name: 'clankers - Web App' }"
    "  ],"
    "  ['https://sbx-dead.arena.site']"
    ");"
    "console.log(JSON.stringify(merged));"
  )
  merged = json.loads(node(script))
  assert merged["list"] == [
    "https://sbx-port8000.arena.site",
    "https://sbx-port3000.arena.site",
    "https://sbx-existing.arena.site",
  ]
  assert merged["names"]["https://sbx-port8000.arena.site"] == "clankers - Steering"
  assert merged["names"]["https://sbx-port3000.arena.site"] == "clankers - Web App"
  assert "https://sbx-dead.arena.site" not in merged["names"]
