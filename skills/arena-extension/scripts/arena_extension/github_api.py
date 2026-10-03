"""GitHub reads through the owner's token, plus the log archive text tail."""

import io
import json
import urllib.error
import urllib.request
import zipfile

GITHUB_API = "https://api.github.com"
TIMEOUT_SECONDS = 30
LOG_CAP_BYTES = 200_000
LOG_TAIL_LINES = 400
REPO_CHARS = frozenset(
  "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-"
)


def valid_repo(value):
  """Accept owner/name only, with ASCII letters, digits, dot, dash and underscore."""
  parts = value.split("/")
  return len(parts) == 2 and all(part and set(part) <= REPO_CHARS for part in parts)


def request(
  path, token="", cap=1_000_000, api=GITHUB_API, accept="application/vnd.github+json"
):
  """Call one GitHub API path and return its status and body."""
  headers = {"Accept": accept, "User-Agent": "arena-extension/2"}
  if token:
    headers["Authorization"] = f"Bearer {token}"
  url = f"{api.rstrip('/')}/{path.lstrip('/')}"
  try:
    with urllib.request.urlopen(
      urllib.request.Request(url, headers=headers), timeout=TIMEOUT_SECONDS
    ) as response:
      return response.status, response.read(cap + 1)
  except urllib.error.HTTPError as error:
    return error.code, error.read(cap + 1) or b""
  except TimeoutError:
    return 504, json.dumps({"error": "github timed out"}).encode()
  except urllib.error.URLError as error:
    return 502, json.dumps({"error": f"github unreachable: {error.reason}"}).encode()


def log_tail(data, cap=LOG_CAP_BYTES, lines=LOG_TAIL_LINES):
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
          chunk = handle.read(65536)
          if not chunk:
            break
          buffer += chunk
          if len(buffer) > cap:
            del buffer[: len(buffer) - cap]
  return "\n".join(buffer.decode("utf-8", "replace").splitlines()[-lines:]) + "\n"


def pull_context(repo, pr=None, path=None, ref="", token="", api=GITHUB_API):
  """Fetch review context: a pull request diff, or one file at a ref."""
  if pr:
    status, body = request(
      f"repos/{repo}/pulls/{pr}",
      token,
      cap=2_000_000,
      api=api,
      accept="application/vnd.github.diff",
    )
    if status != 200:
      return None, f"the pull request diff answered HTTP {status}"
    return body.decode("utf-8", "replace"), None
  if path:
    suffix = f"?ref={ref}" if ref else ""
    status, body = request(
      f"repos/{repo}/contents/{path}{suffix}",
      token,
      cap=2_000_000,
      api=api,
      accept="application/vnd.github.raw",
    )
    if status != 200:
      return None, f"the file read answered HTTP {status}"
    return body.decode("utf-8", "replace"), None
  return None, "no context requested"
