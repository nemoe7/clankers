"""Owner-run backend that gives an Arena agent read access to data the sandbox cannot reach.

The agent calls this server with the `fetch_page` tool. That tool runs outside the
sandbox, so it reaches a public HTTPS host, but it sends no credentials and reads text
only. This server holds the provider credential, checks an agent key, and answers JSON
or text.

Run it on the owner's machine or a private host, expose it over HTTPS, and give the
agent the public URL plus a generated key.

  python3 server.py --generate-key
  EXTENSION_KEY=<key> GITHUB_TOKEN=<pat> EXTENSION_REPO=<owner>/<repo> python3 server.py --port 8787

Routes, all key-gated:

  GET /v1/ping                      server status
  GET /v1/github?path=<api path>    GitHub API JSON through the owner's token
  GET /v1/logs?run=<id>             text tail of a workflow run log

Every request prints one line with the query string removed, so the agent key never
lands in a log.
"""

import argparse
import hmac
import io
import json
import os
import secrets
import sys
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

VERSION = "1.0.0"
DEFAULT_GITHUB_API = "https://api.github.com"
MIN_KEY_LENGTH = 16
API_CAP_BYTES = 1_000_000
DOWNLOAD_CAP_BYTES = 32_000_000
LOG_CAP_BYTES = 200_000
LOG_TAIL_LINES = 400
TIMEOUT_SECONDS = 30
CHUNK_BYTES = 1_048_576
REPO_CHARS = frozenset(
  "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-"
)


def valid_repo(value: str) -> bool:
  """Accept owner/name only, with ASCII letters, digits, dot, dash and underscore."""
  parts = value.split("/")
  return len(parts) == 2 and all(part and set(part) <= REPO_CHARS for part in parts)


def request_target(target: str) -> tuple[str, dict[str, list[str]]]:
  """Split a request target into its path and its query parameters."""
  parts = urllib.parse.urlsplit(target)
  return parts.path, urllib.parse.parse_qs(parts.query, keep_blank_values=True)


def log_line(method: str, target: str, code: object) -> str:
  """Format one log line with the query string removed, so no key is written."""
  return f"{method} {urllib.parse.urlsplit(target).path} -> {code}"


def log_tail(data: bytes) -> str | None:
  """Return the tail of a run log zip as text, or None when the bytes are not a zip."""
  try:
    archive = zipfile.ZipFile(io.BytesIO(data))
  except (zipfile.BadZipFile, OSError):
    return None
  buffer = bytearray()
  with archive:
    for name in sorted(archive.namelist()):
      if not name.endswith(".txt"):
        continue
      buffer += f"\n===== {name} =====\n".encode()
      with archive.open(name) as handle:
        while True:
          chunk = handle.read(CHUNK_BYTES)
          if not chunk:
            break
          buffer += chunk
          if len(buffer) > LOG_CAP_BYTES:
            del buffer[: len(buffer) - LOG_CAP_BYTES]
  lines = buffer.decode("utf-8", "replace").splitlines()
  return "\n".join(lines[-LOG_TAIL_LINES:]) + "\n"


def is_json(data: bytes) -> bool:
  """Report whether the bytes decode as one JSON value."""
  try:
    json.loads(data.decode("utf-8"))
  except (UnicodeDecodeError, ValueError):
    return False
  return True


class ExtensionServer(ThreadingHTTPServer):
  """HTTP server carrying the agent key, the provider token, and the defaults."""

  daemon_threads = True
  allow_reuse_address = True

  def __init__(self, address, *, agent_key, token, github_api, repo):
    super().__init__(address, ExtensionHandler)
    self.agent_key = agent_key
    self.token = token
    self.github_api = github_api.rstrip("/")
    self.repo = repo


class ExtensionHandler(BaseHTTPRequestHandler):
  """Answer the three key-gated routes over GET only."""

  server_version = f"arena-extension/{VERSION}"
  protocol_version = "HTTP/1.1"

  def do_GET(self):
    try:
      self._route()
    except Exception as error:
      self._send_json(500, {"error": f"internal error: {type(error).__name__}"})

  def _route(self):
    path, params = request_target(self.path)
    if not self._authorized(params):
      self._send_json(
        401,
        {
          "error": "unauthorized",
          "hint": "pass ?key=<agent key> or an X-Extension-Key header",
        },
      )
      return
    route = path.rstrip("/") or "/"
    if route == "/v1/ping":
      self._send_json(
        200,
        {
          "ok": True,
          "version": VERSION,
          "github_api": self.server.github_api,
          "repo": self.server.repo or None,
          "token": bool(self.server.token),
        },
      )
    elif route == "/v1/github":
      self._github(params)
    elif route == "/v1/logs":
      self._logs(params)
    else:
      self._send_json(
        404,
        {
          "error": "unknown route",
          "routes": ["/v1/ping", "/v1/github", "/v1/logs"],
        },
      )

  def _authorized(self, params):
    supplied = params.get("key", [""])[0] or self.headers.get("X-Extension-Key", "")
    return bool(supplied) and hmac.compare_digest(supplied, self.server.agent_key)

  def _github(self, params):
    path = params.get("path", [""])[0].strip()
    if not path or "://" in path or path.startswith("/") or ".." in path.split("/"):
      self._send_json(
        400,
        {
          "error": "path must be a relative api.github.com path",
          "example": "path=repos/OWNER/REPO/code-scanning/alerts",
        },
      )
      return
    query = urllib.parse.urlencode(
      [
        (name, value)
        for name, values in sorted(params.items())
        if name not in ("key", "path")
        for value in values
      ]
    )
    url = f"{self.server.github_api}/{path}" + (f"?{query}" if query else "")
    status, body = self._upstream(url, API_CAP_BYTES)
    if status == 200 and len(body) > API_CAP_BYTES:
      self._send_json(
        502,
        {
          "error": f"response exceeds {API_CAP_BYTES} bytes",
          "hint": "narrow the request, for example with per_page",
        },
      )
      return
    self._send(status, body)

  def _logs(self, params):
    run = params.get("run", [""])[0].strip()
    repo = params.get("repo", [""])[0].strip() or self.server.repo
    if not run.isdigit():
      self._send_json(
        400,
        {"error": "run must be a workflow run id", "example": "/v1/logs?run=123456789"},
      )
      return
    if not valid_repo(repo):
      self._send_json(
        400,
        {
          "error": "repo must look like owner/name",
          "hint": "set EXTENSION_REPO or pass ?repo=",
        },
      )
      return
    status, body = self._upstream(
      f"{self.server.github_api}/repos/{repo}/actions/runs/{run}/logs",
      DOWNLOAD_CAP_BYTES,
    )
    if status != 200:
      self._send(status, body)
      return
    tail = log_tail(body)
    if tail is None:
      self._send_json(502, {"error": "the log download was not a zip archive"})
      return
    self._send(200, tail.encode("utf-8"), "text/plain; charset=utf-8")

  def _upstream(self, url, cap):
    request = urllib.request.Request(
      url,
      headers={
        "Authorization": f"Bearer {self.server.token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": f"arena-extension/{VERSION}",
      },
    )
    try:
      with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        return response.status, response.read(cap + 1)
    except urllib.error.HTTPError as error:
      return error.code, error.read(cap + 1) or b""
    except TimeoutError:
      return 504, b'{"error": "upstream timeout"}'
    except urllib.error.URLError as error:
      return 502, json.dumps(
        {"error": f"upstream unreachable: {error.reason}"}
      ).encode()

  def _send_json(self, status, payload):
    body = json.dumps(payload, indent=2).encode("utf-8") + b"\n"
    self._send(status, body, "application/json; charset=utf-8")

  def _send(self, status, body, content_type=None):
    if content_type is None:
      content_type = (
        "application/json; charset=utf-8"
        if is_json(body)
        else "text/plain; charset=utf-8"
      )
    self.send_response(status)
    self.send_header("Content-Type", content_type)
    self.send_header("Content-Length", str(len(body)))
    self.send_header("Cache-Control", "no-store")
    self.end_headers()
    self.wfile.write(body)

  def log_request(self, code="-", size="-"):
    print(log_line(self.command, self.path, code), flush=True)

  def log_message(self, format, *args):
    """Stay silent: log_request already printed the line, and a default line could leak the key."""


def main(argv=None):
  parser = argparse.ArgumentParser(
    description="Arena extension backend: read-only access for an Arena agent."
  )
  parser.add_argument(
    "--host",
    default=os.environ.get("EXTENSION_HOST", "127.0.0.1"),
    help="bind address (default: %(default)s)",
  )
  parser.add_argument(
    "--port",
    type=int,
    default=int(os.environ.get("EXTENSION_PORT", "8787")),
    help="bind port (default: %(default)s)",
  )
  parser.add_argument(
    "--generate-key", action="store_true", help="print a new agent key and exit"
  )
  args = parser.parse_args(argv)

  if args.generate_key:
    print(secrets.token_urlsafe(32))
    return 0

  key = os.environ.get("EXTENSION_KEY", "")
  if len(key) < MIN_KEY_LENGTH:
    print(
      f"EXTENSION_KEY must hold at least {MIN_KEY_LENGTH} characters."
      " Make one with --generate-key.",
      file=sys.stderr,
    )
    return 2
  token = os.environ.get("EXTENSION_GITHUB_TOKEN") or os.environ.get("GITHUB_TOKEN", "")
  server = ExtensionServer(
    (args.host, args.port),
    agent_key=key,
    token=token,
    github_api=os.environ.get("EXTENSION_GITHUB_API", DEFAULT_GITHUB_API),
    repo=os.environ.get("EXTENSION_REPO", ""),
  )
  print(
    f"arena-extension {VERSION} on http://{args.host}:{args.port};"
    f" github token {'set' if token else 'missing'};"
    " routes: /v1/ping /v1/github /v1/logs",
    flush=True,
  )
  try:
    server.serve_forever()
  except KeyboardInterrupt:
    print("stopped", flush=True)
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
