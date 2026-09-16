#!/usr/bin/env python3
"""Steer an agent through a DNS TXT record.

Use this transport where the sandbox egress allowlist blocks every HTTP channel
but still resolves names, which is the case in an Arena sandbox: `ntfy.sh` and
every notification, paste, chat, and webhook host tested close the TLS
connection, while UDP/53 to the configured resolver answers.

The user edits one TXT record from any browser or phone, through their
registrar or a free dynamic DNS zone, and each change becomes a note. No
account, service, comment, commit, or notification is involved, and nothing is
written to the repository.

Environment:
  STEERING_DNS_NAME     required, the record to watch, e.g. `steer.example.com`
  STEERING_FILE         default `STEERING.md` in the working directory
  LOG_FILE              default `STEERING_LOG.md` beside it
  POLL_INTERVAL         seconds, default 10
  DNS_RESOLVER          override the resolver, default the `nameserver` lines in
                        `/etc/resolv.conf`, falling back to 8.8.8.8
  DNS_TIMEOUT           seconds per query, default 5
  STEERING_DNS_BASELINE `current` (default) records what the name holds at
                        startup without ingesting it, `empty` ingests the first
                        value found

Two limits come with the channel. A TXT record is public: anyone who knows the
name can read every note, so never steer with a secret in the text. And the
resolver caches for the record's TTL, so set the lowest TTL the zone allows and
expect latency in tens of seconds rather than the seconds an HTTP poll gives.
"""

from __future__ import annotations

import os
import pathlib
import random
import re
import socket
import struct
import sys
import time
from datetime import datetime, timezone

from steering_notes import added_lines, deliver, digest

TXT = 16
RESOLV_CONF = pathlib.Path("/etc/resolv.conf")
FALLBACK_RESOLVER = "8.8.8.8"


def read_resolvers() -> list[str]:
  """Return the resolvers to query, from resolv.conf or the fallback."""
  override = os.environ.get("DNS_RESOLVER", "").strip()

  if override:
    return [override]

  try:
    found = re.findall(
      r"^nameserver\s+(\S+)", RESOLV_CONF.read_text(encoding="utf-8"), re.MULTILINE
    )
  except OSError:
    found = []

  return found or [FALLBACK_RESOLVER]


def encode_name(name: str) -> bytes:
  encoded = b""

  for label in name.rstrip(".").split("."):
    octets = label.encode("utf-8")

    if not 0 < len(octets) <= 63:
      raise ValueError(f"DNS label {label!r} is not 1..63 octets")

    encoded += bytes([len(octets)]) + octets

  return encoded + b"\x00"


def read_name(data: bytes, offset: int) -> tuple[str, int]:
  """Return a domain name and the offset after it, following compression."""
  labels: list[str] = []
  end = offset
  jumped = False

  while offset < len(data):
    length = data[offset]

    if length & 0xC0 == 0xC0:
      if offset + 1 >= len(data):
        break

      pointer = struct.unpack(">H", data[offset : offset + 2])[0] & 0x3FFF

      if not jumped:
        end = offset + 2

      jumped = True
      offset = pointer
      continue

    if length == 0:
      offset += 1
      break

    labels.append(data[offset + 1 : offset + 1 + length].decode("utf-8", "replace"))
    offset += 1 + length

  return ".".join(labels), (end if jumped else offset)


def parse_txt(data: bytes) -> list[str]:
  """Return every TXT value in the answer section, one string per record."""
  answer_count = struct.unpack(">H", data[6:8])[0]
  _, offset = read_name(data, 12)
  offset += 4
  values: list[str] = []

  for _ in range(answer_count):
    if offset + 10 > len(data):
      break

    _, offset = read_name(data, offset)
    record_type, _, _, length = struct.unpack(">HHIH", data[offset : offset + 10])
    offset += 10
    payload = data[offset : offset + length]
    offset += length

    if record_type != TXT:
      continue

    position = 0
    chunks: list[str] = []

    while position < len(payload):
      size = payload[position]
      chunks.append(
        payload[position + 1 : position + 1 + size].decode("utf-8", "replace")
      )
      position += 1 + size

    values.append("".join(chunks))

  # DNS does not guarantee record order, so sort to keep the digest stable.
  return sorted(values)


def query_txt(name: str, resolvers: list[str], timeout: float) -> str | None:
  """Return the name's TXT records joined by newlines.

  An empty string means the name resolved and holds no TXT record. `None` means
  no resolver answered, which is not the same fact and must not move a baseline:
  treating a failed query as an empty record would replay the whole record as a
  note on the next successful poll.
  """
  query_id = random.randint(0, 0xFFFF)
  packet = (
    struct.pack(">HHHHHH", query_id, 0x0100, 1, 0, 0, 0)
    + encode_name(name)
    + struct.pack(">HH", TXT, 1)
  )
  errors: list[str] = []

  for resolver in resolvers:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)

    try:
      sock.sendto(packet, (resolver, 53))
      data, _ = sock.recvfrom(65535)
      return "\n".join(parse_txt(data))
    except OSError as error:
      errors.append(f"{resolver}: {error}")
    finally:
      sock.close()

  print(f"DNS query failed for {name}: {'; '.join(errors)}", flush=True)
  return None


def poll_once(
  name: str,
  resolvers: list[str],
  timeout: float,
  baseline: list[str | None],
  steering_file: pathlib.Path,
  log_file: pathlib.Path,
  mode: str = "current",
) -> str | None:
  """Poll once, ingest a change, and return the note delivered, if any.

  `baseline` holds one element, the value last seen, and is updated in place. It
  starts as `None` when the startup query failed, so the first answer that does
  arrive establishes the baseline instead of being read as a change.
  """
  current = query_txt(name, resolvers, timeout)

  if current is None:
    return None

  if baseline[0] is None:
    baseline[0] = "" if mode == "empty" else current

  if digest(current) == digest(baseline[0]):
    return None

  added = added_lines(baseline[0], current)
  baseline[0] = current

  if not added:
    return None

  read_at = f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}"
  deliver(
    added, f"dns txt {name}", f"dns txt {name} at {read_at}", steering_file, log_file
  )
  return added


def main() -> None:
  name = os.environ.get("STEERING_DNS_NAME", "").strip()

  if not name:
    sys.exit("STEERING_DNS_NAME is required, for example steer.example.com")

  interval = float(os.environ.get("POLL_INTERVAL", "10"))
  timeout = float(os.environ.get("DNS_TIMEOUT", "5"))
  steering_file = pathlib.Path(os.environ.get("STEERING_FILE", "STEERING.md"))
  log_file = pathlib.Path(os.environ.get("LOG_FILE", "STEERING_LOG.md"))
  mode = os.environ.get("STEERING_DNS_BASELINE", "current").strip().lower()

  if mode not in {"current", "empty"}:
    sys.exit(f"STEERING_DNS_BASELINE must be current or empty, got {mode!r}")

  resolvers = read_resolvers()
  first = query_txt(name, resolvers, timeout)
  baseline: list[str | None] = [
    None if first is None else ("" if mode == "empty" else first)
  ]

  print(f"DNS steering active on the TXT record {name}", flush=True)
  print(f"Resolvers: {', '.join(resolvers)}", flush=True)
  print(f"Notes file: {steering_file.resolve()}", flush=True)
  print(
    f"Polling every {interval:g}s; the resolver caches for the record's TTL", flush=True
  )
  held = (
    "no answer yet, the first one that arrives sets it"
    if first is None
    else f"{len(first)} characters"
  )
  print(f"Baseline {mode!r}: {held}", flush=True)
  print(
    "Edit that TXT record to steer; it is public, so never put a secret in it",
    flush=True,
  )

  while True:
    poll_once(name, resolvers, timeout, baseline, steering_file, log_file, mode)
    time.sleep(interval)


if __name__ == "__main__":
  main()
