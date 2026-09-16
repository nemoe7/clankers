#!/usr/bin/env python3
"""Steer an agent through one GitHub issue or pull request.

Body mode, the default, reads the issue description, so steering leaves no
comments, no commits, and no notifications behind: the user edits one issue
from any browser or phone and each change becomes a note. Comment mode is
opt-in, for a channel where several people steer and attribution matters; it is
edit-aware, so one comment that the user keeps editing works there too.

Use this transport when the sandbox cannot reach ntfy.sh, for example behind an
egress allowlist that permits api.github.com only. Both modes need a token that
can read the repository, so only people with repository access can steer. Body
mode cannot say who edited: the REST issue resource carries its author, not its
last editor.

Environment:
  GH_TOKEN or GITHUB_TOKEN  required, any token that can read the repository
  STEERING_REPO             required, `owner/name`
  STEERING_ISSUE            required, issue or pull request number
  STEERING_SOURCE           `body` (default) or `comments`
  STEERING_FILE             default `STEERING.md` in the working directory
  LOG_FILE                  default `STEERING_LOG.md` beside it
  POLL_INTERVAL             seconds, default 5
  STEERING_IGNORE_AUTHORS   comment mode only: comma separated logins skipped
                            on top of the default rule that skips every `[bot]`
                            login, so the agent's own comments never steer it

Body mode baselines the description it finds at startup and ingests only what
changes after that, so notes written while the poller was down are not
replayed. Add a line rather than rewriting the lines above it: the poller
ingests everything after the longest line prefix it has already seen, which
also handles a description that is replaced outright.
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

from steering_notes import append_log, append_note

API = "https://api.github.com"
# The log line for an ingested comment carries the digest of the body that was
# ingested, which is what makes comment mode edit-aware across a restart.
SEEN_RE = re.compile(r"\[gh:(\d+) hash=([0-9a-f]{12})")
DIRECTIVES = ("STOP:", "PRIORITY:", "CONTEXT:")


def read_token() -> str:
  value = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""

  if not value:
    sys.exit("GH_TOKEN or GITHUB_TOKEN is required")

  return value


def digest(text: str) -> str:
  return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


def fetch(url: str, token: str, etag: str) -> tuple[int, str, str]:
  """Return status, body, and etag; a 304 keeps the caller's etag."""
  headers = {
    "Accept": "application/vnd.github+json",
    "Authorization": f"Bearer {token}",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "arena-live-steering",
  }

  if etag:
    headers["If-None-Match"] = etag

  request = urllib.request.Request(url, headers=headers)

  try:
    with urllib.request.urlopen(request, timeout=20) as response:
      return (
        response.status,
        response.read().decode("utf-8", "replace"),
        response.headers.get("ETag", ""),
      )
  except urllib.error.HTTPError as error:
    if error.code == 304:
      return 304, "", etag

    return error.code, error.read().decode("utf-8", "replace"), ""
  except OSError as error:
    return 0, str(error), etag


def ignored(author: str, extra: set[str]) -> bool:
  return author.endswith("[bot]") or author in extra


def load_seen(log_file: pathlib.Path) -> dict[str, str]:
  """Return comment ids mapped to the digest last ingested for each."""
  if not log_file.exists():
    return {}

  try:
    return dict(SEEN_RE.findall(log_file.read_text(encoding="utf-8")))
  except OSError as error:
    print(f"Could not read {log_file}: {error}", flush=True)
    return {}


def added_lines(previous: str, current: str) -> str:
  """Return the lines of `current` after its shared line prefix with `previous`."""
  old = previous.splitlines()
  new = current.splitlines()
  index = 0

  while index < len(old) and index < len(new) and old[index] == new[index]:
    index += 1

  return "\n".join(new[index:]).strip()


def deliver(
  text: str,
  note_source: str,
  log_source: str,
  steering_file: pathlib.Path,
  log_file: pathlib.Path,
) -> None:
  """Write one note to both files and echo it with any directive it carries."""
  read_at = f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}"
  append_note(steering_file, f"\n<!-- from {note_source}, read {read_at} -->\n", text)
  append_log(log_file, f"--- {read_at} [{log_source}] ---", text)

  print(f"\nSteering from {note_source}", flush=True)
  print(text[:2000], flush=True)
  print("-" * 60, flush=True)

  upper = text.upper()

  for directive in DIRECTIVES:
    if directive in upper:
      print(f">> {directive} the agent must act on this note", flush=True)


def wait(status: int, detail: str, url: str, failures: int, interval: float) -> int:
  """Apply the error policy and return the failure count to carry forward."""
  if status in (200, 304):
    return 0

  if status in (401, 404):
    print(f"GitHub answered {status} for {url}: {detail[:300]}", flush=True)
    sys.exit(f"Cannot read {url} with this token (HTTP {status})")

  failures += 1
  delay = 60 if status == 403 else min(interval * failures, 60)

  if status == 0:
    print(f"Network error, retrying in {delay:g}s: {detail[:200]}", flush=True)
  else:
    print(
      f"GitHub answered {status}, retrying in {delay:g}s: {detail[:200]}", flush=True
    )

  time.sleep(delay)
  return failures


def run_body(
  url: str,
  token: str,
  interval: float,
  steering_file: pathlib.Path,
  log_file: pathlib.Path,
) -> None:
  etag = ""
  baseline: str | None = None
  failures = 0

  while True:
    status, body, new_etag = fetch(url, token, etag)

    if status == 200:
      etag = new_etag

      try:
        current = str(json.loads(body).get("body") or "")
      except json.JSONDecodeError:
        print(f"Unparseable response from {url}", flush=True)
        current = ""

      if baseline is None:
        baseline = current
        count = len(current.splitlines())
        print(f"Baseline: {count} lines; edits from here on are notes", flush=True)
      elif digest(current) != digest(baseline):
        added = added_lines(baseline, current)
        baseline = current

        if added:
          deliver(added, "gh issue body", "gh issue body", steering_file, log_file)

    failures = wait(status, body, url, failures, interval)
    time.sleep(interval)


def run_comments(
  url: str,
  token: str,
  interval: float,
  steering_file: pathlib.Path,
  log_file: pathlib.Path,
  extra_ignored: set[str],
) -> None:
  etag = ""
  since = ""
  failures = 0
  seen = load_seen(log_file)

  print(f"Comment mode: {len(seen)} ids already seen", flush=True)

  while True:
    poll = f"{url}?per_page=50"

    if since:
      poll += f"&since={since}"

    status, body, new_etag = fetch(poll, token, etag)

    if status == 200:
      etag = new_etag

      try:
        comments = json.loads(body)
      except json.JSONDecodeError:
        print(f"Unparseable response from {poll}", flush=True)
        comments = []

      for comment in comments:
        comment_id = str(comment.get("id", ""))
        text = str(comment.get("body", "")).strip()

        if not comment_id or not text:
          continue

        author = str(comment.get("user", {}).get("login", "unknown"))
        since = max(since, str(comment.get("created_at", "")))
        changed = digest(text)

        if seen.get(comment_id) == changed:
          continue

        edited = comment_id in seen
        seen[comment_id] = changed

        if ignored(author, extra_ignored):
          continue

        suffix = " edited" if edited else ""
        deliver(
          text,
          f"gh:{comment_id} by {author}{suffix}",
          f"gh:{comment_id} hash={changed} by {author}{suffix}",
          steering_file,
          log_file,
        )

    failures = wait(status, body, poll, failures, interval)
    time.sleep(interval)


def main() -> None:
  token = read_token()
  repo = os.environ.get("STEERING_REPO", "")
  number = os.environ.get("STEERING_ISSUE", "")

  if not repo or not number:
    sys.exit("STEERING_REPO and STEERING_ISSUE are required")

  source = os.environ.get("STEERING_SOURCE", "body").strip().lower()

  if source not in {"body", "comments"}:
    sys.exit(f"STEERING_SOURCE must be body or comments, got {source!r}")

  interval = float(os.environ.get("POLL_INTERVAL", "5"))
  steering_file = pathlib.Path(os.environ.get("STEERING_FILE", "STEERING.md"))
  log_file = pathlib.Path(os.environ.get("LOG_FILE", "STEERING_LOG.md"))
  extra_ignored = {
    name.strip()
    for name in os.environ.get("STEERING_IGNORE_AUTHORS", "").split(",")
    if name.strip()
  }
  url = f"{API}/repos/{repo}/issues/{number}"
  page = f"https://github.com/{repo}/issues/{number}"

  print(f"GitHub steering active on {repo}#{number}, {source} mode", flush=True)
  print(f"Notes file: {steering_file.resolve()}", flush=True)
  print(f"Polling every {interval:g}s", flush=True)

  if source == "body":
    print(f"Steer by editing the description of {page}", flush=True)
    print("Add a line: no comment, commit, or notification is involved", flush=True)
    run_body(url, token, interval, steering_file, log_file)
  else:
    print(f"Steer by commenting on {page}, or by editing one comment", flush=True)
    run_comments(
      f"{url}/comments", token, interval, steering_file, log_file, extra_ignored
    )


if __name__ == "__main__":
  main()
