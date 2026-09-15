#!/usr/bin/env python3
"""Steer an agent through GitHub issue or pull request comments.

Use this transport when the sandbox cannot reach ntfy.sh, for example behind an
egress allowlist that permits api.github.com only. Comments are authenticated,
so only people with access to the repository can steer, and every note records
who sent it.

Environment:
  GH_TOKEN or GITHUB_TOKEN   required, any token that can read the repository
  STEERING_REPO              required, `owner/name`
  STEERING_ISSUE             required, issue or pull request number
  STEERING_FILE              default `STEERING.md` in the working directory
  LOG_FILE                   default `STEERING_LOG.md` beside it
  POLL_INTERVAL              seconds, default 5
  STEERING_IGNORE_AUTHORS    comma separated logins to skip, on top of the
                             default rule that skips every `[bot]` login, so
                             the agent's own comments never steer it
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

API = "https://api.github.com"
NOTES_HEADER = "# LIVE STEERING NOTES\n\n## Current Notes:\n"
MAX_NOTES_CHARS = 8000
SEEN_RE = re.compile(r"\[gh:(\d+)\]")


def read_token() -> str:
  value = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""

  if not value:
    sys.exit("GH_TOKEN or GITHUB_TOKEN is required")

  return value


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


def load_seen(log_file: pathlib.Path) -> set[str]:
  if not log_file.exists():
    return set()

  try:
    return set(SEEN_RE.findall(log_file.read_text(encoding="utf-8")))
  except OSError as error:
    print(f"Could not read {log_file}: {error}", flush=True)
    return set()


def append_note(path: pathlib.Path, stamp: str, body: str) -> None:
  """Append one note, keeping the tail of the file within MAX_NOTES_CHARS."""
  existing = ""

  if path.exists():
    try:
      existing = path.read_text(encoding="utf-8")
    except OSError:
      existing = ""

  if "## Current Notes:" not in existing:
    existing = NOTES_HEADER

  # The header's own trailing newline is part of the split remainder, so strip
  # the head: without this, every append adds one more blank line above the
  # first note and eats the tail budget.
  notes = existing.split("## Current Notes:", 1)[1].lstrip("\n")
  notes += stamp.lstrip("\n") + body + "\n"
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_text(NOTES_HEADER + "\n" + notes[-MAX_NOTES_CHARS:], encoding="utf-8")


def append_log(path: pathlib.Path, stamp: str, body: str) -> None:
  try:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as log:
      log.write(f"\n\n{stamp}{body}\n")
  except OSError as error:
    print(f"Could not write {path}: {error}", flush=True)


def main() -> None:
  token = read_token()
  repo = os.environ.get("STEERING_REPO", "")
  number = os.environ.get("STEERING_ISSUE", "")

  if not repo or not number:
    sys.exit("STEERING_REPO and STEERING_ISSUE are required")

  interval = float(os.environ.get("POLL_INTERVAL", "5"))
  steering_file = pathlib.Path(os.environ.get("STEERING_FILE", "STEERING.md"))
  log_file = pathlib.Path(os.environ.get("LOG_FILE", "STEERING_LOG.md"))
  extra_ignored = {
    name.strip()
    for name in os.environ.get("STEERING_IGNORE_AUTHORS", "").split(",")
    if name.strip()
  }
  base = f"{API}/repos/{repo}/issues/{number}/comments"

  seen = load_seen(log_file)
  since = ""
  etag = ""
  failures = 0

  print(f"GitHub steering active on {repo}#{number}", flush=True)
  print(f"Steer by commenting on https://github.com/{repo}/issues/{number}", flush=True)
  print(f"Notes file: {steering_file.resolve()}", flush=True)
  print(f"Polling every {interval:g}s, {len(seen)} ids already seen", flush=True)

  while True:
    url = f"{base}?per_page=50"

    if since:
      url += f"&since={since}"

    status, body, new_etag = fetch(url, token, etag)

    if status == 200:
      etag = new_etag
      failures = 0

      try:
        comments = json.loads(body)
      except json.JSONDecodeError:
        print(f"Unparseable response from {url}", flush=True)
        comments = []

      for comment in comments:
        comment_id = str(comment.get("id", ""))

        if not comment_id or comment_id in seen:
          continue

        seen.add(comment_id)
        author = str(comment.get("user", {}).get("login", "unknown"))
        created = str(comment.get("created_at", ""))

        since = max(since, created)

        if ignored(author, extra_ignored):
          continue

        text = str(comment.get("body", "")).strip()

        if not text:
          continue

        stamp = (
          f"\n<!-- gh:{comment_id} by {author} at {created} "
          f"(read {datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}) -->\n"
        )
        log_stamp = f"--- {created} [gh:{comment_id}] by {author} ---"

        append_note(steering_file, stamp, text)
        append_log(log_file, log_stamp, text)

        print(f"\nSteering from {author} [gh:{comment_id}]", flush=True)
        print(text[:2000], flush=True)
        print("-" * 60, flush=True)

        upper = text.upper()

        if "STOP:" in upper:
          print(">> STOP directive: the agent must pivot now", flush=True)

        if "PRIORITY:" in upper:
          print(">> PRIORITY directive", flush=True)
    elif status == 304:
      failures = 0
    elif status in (401, 403, 404):
      print(f"GitHub answered {status} for {url}: {body[:300]}", flush=True)

      if status in (401, 404):
        sys.exit(f"Cannot read {repo}#{number} with this token (HTTP {status})")

      time.sleep(60)
    elif status == 0:
      failures += 1
      print(f"Network error ({failures}): {body[:200]}", flush=True)
      time.sleep(min(interval * failures, 60))
    else:
      failures += 1
      print(f"GitHub answered {status}: {body[:200]}", flush=True)
      time.sleep(min(interval * failures, 60))
      continue

    time.sleep(interval)


if __name__ == "__main__":
  main()
