"""Upstream transfers: fetch a URL, and turn bytes into text the agent can carry.

The `fetch_page` tool fails on a binary response, so this module owns the
conversion. Base64 costs one third more characters, base85 costs one quarter,
and gzip before either shrinks text-like payloads further. Large bytes stage to
disk and leave in fixed-size chunks, so one request stays small.
"""

import base64
import gzip
import urllib.error
import urllib.parse
import urllib.request

CHUNK_BYTES = 49152
FETCH_TIMEOUT_SECONDS = 30
DEFAULT_FETCH_CAP = 8_000_000
DEFAULT_STAGE_CAP = 32_000_000
LOOPBACK_HOSTS = ("127.0.0.1", "localhost", "::1")
ENCODINGS = {
  "base64": lambda data: base64.b64encode(data).decode("ascii"),
  "b85": lambda data: base64.b85encode(data).decode("ascii"),
}


class TransferError(Exception):
  """A transfer failed, with the status the route should answer."""

  def __init__(self, status, message):
    super().__init__(message)
    self.status = status
    self.message = message


def allowed_url(url):
  """Accept HTTPS anywhere, and HTTP only for a loopback host, such as a local service."""
  parts = urllib.parse.urlsplit(url)
  if parts.scheme == "https":
    return True
  return parts.scheme == "http" and parts.hostname in LOOPBACK_HOSTS


def fetch_url(url, cap, timeout=FETCH_TIMEOUT_SECONDS):
  """Fetch one allowed URL and return its bytes and content type."""
  if not allowed_url(url):
    raise TransferError(400, "url must be https://, or http:// on a loopback host")
  request = urllib.request.Request(url, headers={"User-Agent": "arena-extension/2"})
  try:
    with urllib.request.urlopen(request, timeout=timeout) as response:
      declared = int(response.headers.get("Content-Length") or 0)
      if declared > cap:
        raise TransferError(
          413, f"the resource is {declared} bytes, over the {cap} byte cap"
        )
      return response.read(cap + 1), response.headers.get("Content-Type", "")
  except urllib.error.HTTPError as error:
    raise TransferError(502, f"upstream answered HTTP {error.code}") from error
  except TimeoutError as error:
    raise TransferError(504, "the upstream request timed out") from error
  except urllib.error.URLError as error:
    raise TransferError(502, f"upstream unreachable: {error.reason}") from error


def is_text(data):
  """Report whether the bytes are UTF-8 with no NUL byte."""
  if b"\x00" in data:
    return False
  try:
    data.decode("utf-8")
  except UnicodeDecodeError:
    return False
  return True


def encode(data, encoding="base64", compress=False):
  """Return the payload as text, optionally gzipped first, and its label."""
  payload = gzip.compress(data) if compress else data
  label = "text" if is_text(payload) and not compress else encoding
  if label == "text":
    return payload.decode("utf-8"), "text"
  return ENCODINGS[encoding](payload), f"{encoding}+gzip" if compress else encoding


def chunk_count(size):
  """Return how many fixed-size chunks a payload of this size needs."""
  return max(1, (size + CHUNK_BYTES - 1) // CHUNK_BYTES)


def slice_for_chunk(data, index):
  """Return one chunk of bytes, or None when the index is out of range."""
  start = index * CHUNK_BYTES
  if index < 0 or start >= len(data):
    return None
  return data[start : start + CHUNK_BYTES]
