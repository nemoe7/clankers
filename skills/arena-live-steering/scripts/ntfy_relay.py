#!/usr/bin/env python3
"""Relay ntfy messages into the notes file, with a browser doing the listening.

The sandbox cannot reach ntfy.sh: the TLS handshake is closed for every process
in it, measured as curl exit 35 with HTTP 000 while TCP to port 443 connects. The
agent's page-fetch path can reach it, but that path is GET-only and each read
costs a network round trip inside a turn, so neither gives continuous capture,
which is the one thing the DNS fallback had going for it.

The user's browser can reach ntfy, and it can reach this server through the Arena
preview proxy, so the split is: the browser subscribes and forwards, the server
writes. That restores background capture on the ntfy route without the sandbox
ever contacting ntfy. Closing the tab loses nothing, since ntfy holds 12 hours of
messages and `?poll=1&since=all` returns all of them, so the agent's own fetch at
a turn boundary is still a complete read.

Serves the relay page at `/` and accepts one ntfy JSON message per POST to
`/note`, deduplicating by message id against the same log the other routes write.

  STEERING_NTFY_TOPIC=<topic> PORT=8765 \\
    STEERING_FILE=reports/STEERING.md LOG_FILE=reports/STEERING_LOG.md \\
    python3 scripts/ntfy_relay.py
"""

from __future__ import annotations

import json
import os
import pathlib
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from ntfy_steering import load_seen, note_text, parse_messages
from steering_notes import deliver

TOPIC = os.environ.get("STEERING_NTFY_TOPIC", "")
PORT = int(os.environ.get("PORT", "8765"))
STEERING_FILE = pathlib.Path(os.environ.get("STEERING_FILE", "reports/STEERING.md"))
LOG_FILE = pathlib.Path(os.environ.get("LOG_FILE", "reports/STEERING_LOG.md"))

LOCK = threading.Lock()
SEEN = load_seen(LOG_FILE)
RELAYED = 0

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ntfy steering relay</title>
<style>
 body{font:15px/1.5 system-ui,sans-serif;margin:0;padding:24px;background:#101828;color:#eaecf0}
 .card{max-width:640px;margin:0 auto;background:#1d2939;border:1px solid #344054;border-radius:12px;padding:20px}
 h1{font-size:18px;margin:0 0 4px} p{margin:6px 0;color:#98a2b3}
 #dot{display:inline-block;width:10px;height:10px;border-radius:50%;background:#667085;margin-right:8px}
 #dot.live{background:#12b76a} #dot.poll{background:#f79009} #dot.err{background:#f04438}
 code,pre{background:#101828;border-radius:6px;padding:2px 5px;color:#eaecf0}
 pre{padding:10px;white-space:pre-wrap;word-break:break-word;min-height:20px}
 #count{font-variant-numeric:tabular-nums;color:#eaecf0}
</style></head><body><div class="card">
<h1><span id="dot"></span>ntfy steering relay</h1>
<p>Topic <code>__TOPIC__</code>. This tab listens to ntfy and forwards every message to the
agent's sandbox, which writes it to <code>STEERING.md</code>. Keep it open while you steer;
closing it loses nothing, because ntfy holds 12 hours of messages and the agent can read them.</p>
<p>Relayed: <span id="count">0</span> &middot; <span id="state">connecting</span></p>
<p>Last note:</p><pre id="last">(none yet)</pre>
<p id="why"></p>
</div>
<script>
"use strict";
const TOPIC = "__TOPIC__";
const dot = document.getElementById("dot"), state = document.getElementById("state");
const count = document.getElementById("count"), last = document.getElementById("last");
const why = document.getElementById("why");
let relayed = 0, lastId = "all", source = null, poller = null;

function mark(cls, text) { dot.className = cls; state.textContent = text; }

async function forward(body) {
  const res = await fetch("/note", { method: "POST", body });
  const out = await res.json();
  relayed += out.delivered || 0;
  count.textContent = relayed;
  if (out.last) last.textContent = out.last;
  if (out.skipped) why.textContent = `${out.skipped} message(s) already delivered, skipped.`;
}

// The stream is the cheap path. If the browser or the network refuses it, fall
// back to polling the same topic, which needs the same permission and nothing more.
function startPoll(reason) {
  if (poller) return;
  mark("poll", "polling every 10s");
  why.textContent = reason;
  poller = setInterval(async () => {
    try {
      const res = await fetch(
        `https://ntfy.sh/${TOPIC}/json?poll=1&since=${encodeURIComponent(lastId)}`);
      const text = await res.text();
      if (!text.trim()) return;
      for (const line of text.trim().split("\\n")) {
        try { lastId = JSON.parse(line).id || lastId; } catch { /* a partial line */ }
      }
      await forward(text);
    } catch (error) { mark("err", "poll failed"); why.textContent = String(error); }
  }, 10000);
}

function startStream() {
  try { source = new EventSource(`https://ntfy.sh/${TOPIC}/sse`); }
  catch (error) { startPoll(`The stream could not be opened: ${error}`); return; }
  source.addEventListener("open", () => mark("live", "listening to ntfy"));
  source.addEventListener("keepalive", () => {});
  source.onmessage = (event) => {
    try {
      const record = JSON.parse(event.data);
      if (record.id) lastId = record.id;
      if (record.event && record.event !== "message") return;
    } catch { return; }
    forward(event.data).catch((error) => { mark("err", "forward failed"); why.textContent = String(error); });
  };
  source.onerror = () => {
    source.close(); source = null;
    startPoll("The stream to ntfy was refused, most likely by CORS, so this tab polls instead.");
  };
}
startStream();
</script></body></html>
"""


class Handler(BaseHTTPRequestHandler):
  """Serve the relay page and take one ntfy message per POST."""

  def log_message(self, *args) -> None:
    pass

  def _send(self, code: int, body: bytes, kind: str) -> None:
    self.send_response(code)
    self.send_header("Content-Type", kind)
    self.send_header("Content-Length", str(len(body)))
    self.end_headers()
    self.wfile.write(body)

  def do_GET(self) -> None:
    if self.path in ("/", "/index.html"):
      self._send(
        200, PAGE.replace("__TOPIC__", TOPIC).encode(), "text/html; charset=utf-8"
      )
    elif self.path == "/health":
      self._send(200, b"ok\n", "text/plain; charset=utf-8")
    else:
      self._send(404, b"not found\n", "text/plain; charset=utf-8")

  def do_POST(self) -> None:
    global RELAYED
    if self.path != "/note":
      self._send(404, b'{"error":"unknown path"}\n', "application/json")
      return

    length = int(self.headers.get("Content-Length") or 0)
    body = self.rfile.read(length).decode("utf-8", "replace") if length else ""
    delivered, skipped, last_text = 0, 0, ""

    with LOCK:
      for record in parse_messages(body):
        message_id = str(record.get("id") or "")
        if not message_id or message_id in SEEN:
          skipped += 1
          continue
        SEEN.add(message_id)
        text = note_text(record)
        deliver(
          text,
          f"ntfy {TOPIC}",
          f"ntfy {TOPIC} id={message_id}",
          STEERING_FILE,
          LOG_FILE,
        )
        delivered += 1
        last_text = text
        RELAYED += 1

    if delivered:
      print(f"relayed {delivered} note(s), {RELAYED} total", flush=True)
    payload = json.dumps(
      {"delivered": delivered, "skipped": skipped, "last": last_text}
    )
    self._send(200, payload.encode(), "application/json")


def main() -> int:
  if not TOPIC:
    print(
      "STEERING_NTFY_TOPIC is required, for example clankers-1a2b3c4d5e", flush=True
    )
    return 2

  server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
  print(f"ntfy relay listening on 0.0.0.0:{PORT} for topic {TOPIC}", flush=True)
  print(f"Notes file: {STEERING_FILE}", flush=True)
  print(
    f"Already delivered: {len(SEEN)} message id(s), recovered from {LOG_FILE}",
    flush=True,
  )
  print("Open the preview in a browser; that tab does the listening.", flush=True)
  try:
    server.serve_forever()
  except KeyboardInterrupt:
    pass
  finally:
    server.server_close()
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
