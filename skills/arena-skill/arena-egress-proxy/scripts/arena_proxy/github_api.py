"""GitHub reads through the owner's token, plus the log archive text tail."""

import io
import json
import re
import urllib.error
import urllib.parse
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
  path,
  token="",
  cap=1_000_000,
  api=GITHUB_API,
  accept="application/vnd.github+json",
  with_links=False,
):
  """Call one GitHub API path and return its status and body."""

  def result(status, body, headers=None):
    if with_links:
      return status, body, headers.get("Link", "") if headers else ""
    return status, body

  headers = {"Accept": accept, "User-Agent": "arena-proxy/3"}
  if token:
    headers["Authorization"] = f"Bearer {token}"
  url = f"{api.rstrip('/')}/{path.lstrip('/')}"
  try:
    with urllib.request.urlopen(
      urllib.request.Request(url, headers=headers), timeout=TIMEOUT_SECONDS
    ) as response:
      return result(response.status, response.read(cap + 1), response.headers)
  except urllib.error.HTTPError as error:
    return result(error.code, error.read(cap + 1) or b"", error.headers)
  except TimeoutError:
    return result(504, json.dumps({"error": "github timed out"}).encode())
  except urllib.error.URLError as error:
    return result(
      502, json.dumps({"error": f"github unreachable: {error.reason}"}).encode()
    )


def log_tail(data, cap=LOG_CAP_BYTES, lines=LOG_TAIL_LINES, only_failed=False):
  """Return the tail of a run log zip as text, or None when the bytes are not a zip.

  With `only_failed`, keep the tails of step files that contain an error marker.
  """
  try:
    archive = zipfile.ZipFile(io.BytesIO(data))
  except (zipfile.BadZipFile, OSError):
    return None
  buffer = bytearray()
  with archive:
    for name in sorted(archive.namelist()):
      if not name.endswith(".txt"):
        continue
      block = bytearray()
      has_error = False
      with archive.open(name) as handle:
        while True:
          chunk = handle.read(65536)
          if not chunk:
            break
          block += chunk
          has_error = has_error or b"##[error]" in block
          if len(block) > cap:
            del block[: len(block) - cap]
      if only_failed and not has_error:
        continue
      buffer += f"\n===== {name} =====\n".encode()
      buffer += block
      if len(buffer) > cap:
        del buffer[: len(buffer) - cap]
  text = buffer.decode("utf-8", "replace")
  if only_failed:
    return text.strip("\n") + "\n"
  return "\n".join(text.splitlines()[-lines:]) + "\n"


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


def next_target(header, api):
  match = re.search(r'<([^>]+)>;\s*rel="next"', header)
  if not match:
    return None
  target, base = urllib.parse.urlsplit(match[1]), urllib.parse.urlsplit(api)
  prefix = base.path.rstrip("/") + "/"
  if (target.scheme, target.netloc) != (
    base.scheme,
    base.netloc,
  ) or not target.path.startswith(prefix):
    raise ValueError("GitHub next link is outside the configured API")
  return target.path[len(prefix) :] + ("?" + target.query if target.query else "")
