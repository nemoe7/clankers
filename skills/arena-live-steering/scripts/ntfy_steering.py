#!/usr/bin/env python3
"""Turn ntfy poll output into steering notes.

A process in an Arena sandbox cannot reach ntfy.sh at all: the TLS handshake is
closed on every attempt, measured as curl exit 35 with HTTP 000 while TCP to port
443 still connects, so it is a filter rather than a dead network. The agent's
page-fetch path is not behind that filter and reads a topic fine, but it is a
GET-only tool that runs when the agent acts. So the reading happens in a turn and
the writing happens here: feed this script the body of

    https://ntfy.sh/<topic>/json?poll=1&since=all

and it delivers every message it has not delivered before into the same notes and
log files the DNS poller writes, deduplicated by ntfy's own message id rather than
by a digest of the text, because ntfy hands out an id that cannot collide.

Two details of that read path are worth knowing before trusting a failure. An
empty topic makes the body empty, and a fetch tool can report an empty 200 as its
own error, which reads exactly like an unreachable host: `httpbin.org/status/200`
fails the same way, so the empty case is not evidence about ntfy. And the plain
`/json` endpoint without `poll=1` is a stream that stays open forever, which a
page fetch cannot return at all. Poll, with `since=all`, is the only form that
terminates.

Input may be the raw NDJSON body or that body wrapped in the markdown code fence a
page-fetch tool tends to return, since pasting the tool's output verbatim is the
normal way to use this.
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from steering_notes import append_log, deliver, digest

# The stamp ends in `id=<message id>]`, so anything annotating it goes before.
SEEN_RE = re.compile(r"\[ntfy [^\]]*id=([A-Za-z0-9_-]+)\]")
SKIP_EVENTS = frozenset({"open", "keepalive"})


def strip_fence(text: str) -> str:
  """Return `text` without a wrapping markdown code fence, if it has one."""
  body = text.strip()
  if not body.startswith("```"):
    return body
  lines = body.splitlines()
  if lines[0].startswith("```"):
    lines = lines[1:]
  if lines and lines[-1].strip() == "```":
    lines = lines[:-1]
  return "\n".join(lines).strip()


def parse_messages(body: str) -> list[dict]:
  """Return the message events in an ntfy poll body, oldest first.

  A line that is not JSON is reported rather than dropped, because a truncated
  fetch is the likely cause and silence would look like an empty topic.
  """
  messages = []
  for line in strip_fence(body).splitlines():
    line = line.strip()
    if not line:
      continue
    try:
      record = json.loads(line)
    except json.JSONDecodeError:
      print(f"Skipping a line that is not JSON: {line[:120]}", flush=True)
      continue
    if not isinstance(record, dict):
      continue
    if record.get("event", "message") in SKIP_EVENTS:
      continue
    if "message" not in record:
      continue
    messages.append(record)
  return sorted(messages, key=lambda m: m.get("time", 0))


def load_seen(log_file: pathlib.Path) -> set[str]:
  """Return the message ids already delivered, recovered from the log."""
  try:
    text = log_file.read_text(encoding="utf-8")
  except OSError:
    return set()
  return set(SEEN_RE.findall(text))


def note_text(record: dict) -> str:
  """Return the note a message carries, with its title kept if it had one."""
  message = str(record.get("message", ""))
  title = str(record.get("title", "")).strip()
  return f"[{title}]\n{message}" if title else message


def main() -> int:
  topic = os.environ.get("STEERING_NTFY_TOPIC", "ntfy topic")
  steering_file = pathlib.Path(os.environ.get("STEERING_FILE", "reports/STEERING.md"))
  log_file = pathlib.Path(os.environ.get("LOG_FILE", "reports/STEERING_LOG.md"))
  hold = os.environ.get("STEERING_NTFY_BASELINE", "empty") == "current"

  body = (
    pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")
    if len(sys.argv) > 1
    else sys.stdin.read()
  )

  messages = parse_messages(body)
  if not messages:
    print(f"No messages in that body for {topic}.", flush=True)
    print(
      "  An empty topic returns an empty body, which a page-fetch tool can report",
      flush=True,
    )
    print(
      "  as its own HTTP 500. That is not evidence ntfy is unreachable: publish",
      flush=True,
    )
    print("  one message and read the topic again.", flush=True)
    return 0

  seen = load_seen(log_file)
  delivered = 0

  for record in messages:
    # An id from ntfy is authoritative; a message without one falls back to a
    # digest of its text so the note is still deduplicated rather than replayed.
    message_id = str(record.get("id") or f"digest-{digest(note_text(record))}")
    if message_id in seen:
      continue
    seen.add(message_id)

    if hold:
      # A hold has to outlive this process, or the next run delivers exactly the
      # messages the baseline was meant to bury. The log is the durable record of
      # what was seen, so the id goes there with a marker instead of a note.
      append_log(
        log_file,
        f"--- held as the baseline [ntfy {topic} id={message_id}] ---",
        "(held, not delivered)",
      )
      continue

    text = note_text(record)
    deliver(
      text,
      f"ntfy {topic}",
      f"ntfy {topic} id={message_id}",
      steering_file,
      log_file,
    )
    delivered += 1

  print(
    f"{len(messages)} message(s) in the body, {delivered} delivered, "
    f"{len(messages) - delivered} already seen or held as the baseline.",
    flush=True,
  )
  if hold:
    print(
      "Baseline 'current' held them; their ids are in the log, so a later run",
      flush=True,
    )
    print("  will not deliver them either.", flush=True)
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
