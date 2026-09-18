#!/usr/bin/env python3
"""Turn ntfy poll output into steering notes.

A process in an Arena sandbox cannot reach ntfy.sh at all: the TLS handshake is
closed on every attempt, measured as curl exit 35 with HTTP 000 while TCP to port
443 still connects, so it is a filter rather than a dead network. The agent's
page-fetch path is not behind that filter and reads a topic fine, but it is a
GET-only tool that runs when the agent acts. So the reading happens in a turn and
the writing happens here: feed this script the body of

    https://ntfy.sh/<topic>/json?poll=1&since=<lastmessage>

and it delivers every message it has not delivered before into the notes and log
files the shared writer owns, deduplicated by ntfy's own message id rather than by
a digest of the text, because ntfy hands out an id that cannot collide. It then
prints the URL to pull next, so an id only has to survive in the log. A body that holds no messages still stamps one check line into the log, so the fact that the agent checked survives a quiet or mangled channel, and `STEERING_NTFY_ERROR` puts the error text into that line.

The anchor is what keeps a repeated read small: `since=<message id>` returns only
what came after that id, where `since=all` re-reads the topic's whole cache, which
ntfy's own docs tell a repeated poller not to do. So read with `since=all` only
until the log holds an id, and again after the log is lost, since the log is the
only record of the anchor. An anchor that has aged out of the cache is not a hole:
the server resolves an unknown id to the start of the cache, so the next read
returns everything it still holds and the id dedup makes that harmless.

Two details of that read path are worth knowing before trusting a failure. An
empty topic makes the body empty, and a fetch tool can report an empty 200 as its
own error, which reads exactly like an unreachable host: `httpbin.org/status/200`
fails the same way, so the empty case is not evidence about ntfy. And the plain
`/json` endpoint without `poll=1` is a stream that stays open forever, which a
page fetch cannot return at all. Poll, with `since=all` or `since=<message id>`,
is the only form that terminates.

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

from datetime import datetime, timezone

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


def log_ids(log_file: pathlib.Path) -> list[str]:
  """Return the message ids the log recorded, oldest first, without repeats."""
  try:
    text = log_file.read_text(encoding="utf-8")
  except OSError:
    return []
  return list(dict.fromkeys(SEEN_RE.findall(text)))


def pull_url(topic: str, log_file: pathlib.Path) -> str:
  """Return the poll URL for the next read, anchored on the newest real id.

  The log is append-only and written in delivery order, so its last id is the
  newest one seen. A message that carried no ntfy id is stamped `digest-...`,
  which the server cannot resolve, so `since=all` stands until a real id lands.
  """
  for message_id in reversed(log_ids(log_file)):
    if not message_id.startswith("digest-"):
      return f"https://ntfy.sh/{topic}/json?poll=1&since={message_id}"
  return f"https://ntfy.sh/{topic}/json?poll=1&since=all"


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
  url_topic = os.environ.get("STEERING_NTFY_TOPIC") or "<topic>"

  body = (
    pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")
    if len(sys.argv) > 1
    else sys.stdin.read()
  )

  messages = parse_messages(body)
  if not messages:
    # A quiet or mangled channel still has to leave proof the check happened:
    # the stamp carries no `id=`, so it never becomes an anchor.
    read_at = f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}"
    error = os.environ.get("STEERING_NTFY_ERROR", "").strip()
    append_log(
      log_file,
      f"--- {read_at} [ntfy {topic} checked, 0 delivered] ---",
      error or "(no messages in the body)",
    )
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
    print(f"Next pull: {pull_url(url_topic, log_file)}", flush=True)
    return 0

  seen = set(log_ids(log_file))
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
  print(f"Next pull: {pull_url(url_topic, log_file)}", flush=True)
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
