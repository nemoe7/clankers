"""Shared preview runtime. Steering uses only Python's standard library."""

import argparse
import base64
import hashlib
import html
import json
import os
import re
import secrets
import shlex
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from contextlib import closing, contextmanager, nullcontext
from datetime import datetime, timedelta, timezone
from fnmatch import fnmatchcase
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

# markdown-it-py loads on first use: serve needs it, and a gate tick that never renders
# Markdown must not pay for the import. None until the first check.
HAS_RENDERER = None

# sqlite3 loads on first use too: only the store needs it, and a gate tick never opens
# one. None until `sqlite_api` runs.
sqlite3 = None


def __getattr__(name):
  """Serve the http.server classes on first use, so a gate tick skips that import.

  A serve needs both names, and the checks build a server straight from this module.
  Name them here, and a line that only reads the gate pays nothing for the server.
  """
  if name in ("BaseHTTPRequestHandler", "ThreadingHTTPServer"):
    from http import server

    return getattr(server, name)
  raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


ASSETS = Path(__file__).resolve().parents[1] / "assets"
IDENTIFIER = re.compile(r"[a-zA-Z0-9_-]{1,80}\Z")
REPLY_REFERENCE = re.compile(r"^RE:\s*([a-zA-Z0-9_-]{1,80})(?:\s|$)", re.IGNORECASE)
MAX_REPORT = 2_000_000
WS_TICK_SECONDS = 0.25
WS_HEARTBEAT_SECONDS = 10
WS_IDLE_SECONDS = 35
WS_MAX_MESSAGE = MAX_REPORT + 4096
# Documented snapshot cap, not a measured limit.
SNAPSHOT_CAP_BYTES = 128_000_000
# A data URI lands inside a Markdown message row, so the cap keeps one pasted image sane.
IMAGE_DATA_URI_MAX_BYTES = 2 * 1024 * 1024
WORKSPACE_SKIP = {
  ".arena",
  ".cache",
  ".git",
  ".local",
  ".mypy_cache",
  ".next",
  ".nox",
  ".npm",
  ".nuxt",
  ".output",
  ".parcel-cache",
  ".pytest_cache",
  ".ruff_cache",
  ".svelte-kit",
  ".tox",
  ".turbo",
  ".venv",
  ".vite",
  "__pycache__",
  "build",
  "coverage",
  "dist",
  "node_modules",
  "out",
  "target",
}
FETCH_LEASE = timedelta(minutes=5)
# File bytes live beside the database, never inside it. Stored names are relative to state.
UPLOAD_DIR = "uploads"
FETCH_DIR = "downloads"


def workspace_usage(root=None):
  """Bytes and files under root, skipping snapshot-excluded directories."""
  root = Path(root or Path.cwd())
  total = 0
  count = 0
  for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
    dirnames[:] = [name for name in dirnames if name not in WORKSPACE_SKIP]
    for name in filenames:
      try:
        total += (Path(dirpath) / name).stat().st_size
      except OSError:
        continue
      count += 1
  return {
    "bytes": total,
    "files": count,
    "documented_cap_bytes": SNAPSHOT_CAP_BYTES,
    "download_cap_bytes": None,
  }


FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
CHOICE = re.compile(r"^\s*[-*]\s+\(([ xX]?)\)\s+(\S.*?)\s*$")
CHECKBOX = re.compile(r"^\s*[-*]\s+\[([ xX]?)\]\s+(\S.*?)\s*$")
BLANK = re.compile(r"^(?:(.*?)[\s:])?_{3,}\s*$")
ANCHOR = re.compile(r"\s*\{#([a-zA-Z0-9_-]{1,80})\}\s*$")
# A wrapped option label may run past its marker line. A block start ends the option instead.
BLOCK_START = re.compile(
  r"^ {0,3}(?:"
  r"#{1,6}(?:\s|$)|"
  r">|"
  r"[-*+](?:\s|$)|"
  r"\d+[.)](?:\s|$)|"
  r"(?:[-*_]\s*){3,}$|"
  r"`{3,}|~{3,}"
  r")"
)
# One repeated tail reads as noise, so the reminder rotates through rules an agent most often
# drops. The cursor lives in meta, so a cycle covers every string before one repeats.
TASK_REMINDER = "{remaining} tasks left."


def fill_reminder(tail, remaining):
  """Fill the task-count reminder. One task reads in the singular.

  That entry hides itself with no unfinished task, so its fill is None.
  """
  if "{remaining}" in tail and remaining == 0:
    return None
  count = f"{remaining} task" if remaining == 1 else f"{remaining} tasks"
  return tail.replace("{remaining} tasks", count)


def reminder_tail(cursor, remaining, stale=0):
  """Return the rotating tail at the cursor. A hidden entry yields the next one."""
  for step in range(len(REMINDERS)):
    tail = fill_reminder(REMINDERS[(cursor + step) % len(REMINDERS)], remaining)
    if tail:
      if tail == "Unpublish stale reports." and stale:
        return f"Unpublish {stale} stale report{'s' if stale != 1 else ''}."
      return tail
  return REMINDERS[cursor % len(REMINDERS)]


REMINDERS = (
  (
    "Context check: MUST read ARENA.md, root/nested AGENTS.md, and arena-skill "
    "SKILL.md fully before other tools if current full text is absent from context, "
    "including session start and post-compaction/summary/context replacement; MUST "
    "reread all after a rule violation or reread request."
  ),
  "`task-list` at turn start. Update it as work changes.",
  "Take the smallest open task next.",
  "Always push.",
  "`ask_user` on GH_TOKEN failure.",
  "Keep docs terse but clear.",
  "Ask questions ASAP in reports.",
  "Publish your reports.",
  "Never end a turn with unblocked tasks.",
  "Unpublish stale reports.",
  "End the turn with `poll`.",
  "Grep-verify each edit.",
  TASK_REMINDER,
  "Rebase `origin/main` before pushing; empty checks mean it moved.",
  "Check the PR's CI before ending a pushed turn; read the run's verdict on a later call, never a loop in the call.",
  "Run `arena-preview`, not the full path.",
)
REMINDER_CURSOR = "reminder_cursor"
POLLS_SINCE_MESSAGE = "polls_since_message"
GATE_THRESHOLD = 6
# At this many published reports, the reminder names the stale ones to unpublish.
STALE_REPORT_THRESHOLD = 10
# The port the skill names. A serve on another one hides the owner's page from the
# address they expect, so the gate names the difference.
DEFAULT_PORT = 8000
# The key the userscript holds. The page records it, so the Downloads tab can show it.
AGENT_KEY_META = "agent_key"
# The userscript replaces the record inside its 15-minute rotation window, so an older
# record means no key post arrived and the agent's key is dead until a new one lands.
AGENT_KEY_EXPIRY_SECONDS = 1200
AGENT_KEY_EXPIRY_META = "agent_key_expired_at"
AGENT_SEEN_META = "agent_seen_at"
AGENT_INTERRUPT_META = "agent_interrupt"
AGENT_CALL_ENDED_META = "agent_call_ended_at"
# A poll that returns with nothing to read ends the turn. The header reads this mark, so the
# silence after a turn never reads as a running bash call. The agent's next call clears it.
TURN_ENDED_META = "turn_ended_at"
# Removing rows can move group stamps back. The state stamp also reads this mark.
# The save stamp trigger rewrites a file that still has a removed report.
REMOVED_META = "state_removed_at"
# Agent report changes wait this long after a recorded owner view.
REPORT_CHANGE_VIEW_SECONDS = 60
AGENT_KEY_RE = re.compile(r"[A-Za-z0-9_-]{20,64}\Z")
# The proxy host, one HTTPS origin with no path, as the userscript saves it.
AGENT_HOST_RE = re.compile(r"https://[A-Za-z0-9.-]+\Z")


def now():
  return datetime.now(timezone.utc).isoformat()


TIMEZONE_META = "display_tz"
DISPLAY_ZONE = None


def zone_exists(name):
  """True when the system tzdata knows an IANA zone name."""
  try:
    ZoneInfo(name)
    return True
  except (KeyError, ValueError, OSError):
    return False


def resolve_display_zone(store):
  """The zone CLI stamps print in: the TZ env first, then the zone init stored."""
  name = os.environ.get("TZ") or (store.meta_value(TIMEZONE_META) if store else None)
  if not name or not zone_exists(name):
    return None
  return ZoneInfo(name)


def local_stamp(value):
  """Print one stored UTC stamp in the set zone. Storage and exports keep UTC."""
  if not value or DISPLAY_ZONE is None:
    return value
  try:
    parsed = datetime.fromisoformat(value)
  except ValueError:
    return value
  if parsed.tzinfo is None:
    parsed = parsed.replace(tzinfo=timezone.utc)
  return parsed.astimezone(DISPLAY_ZONE).isoformat()


def workspace_branch(root=None):
  """The checked-out branch of a git checkout, or an empty string.

  A state file name carries the branch beside the repository, so the pick control asks
  the checkout the preview serves rather than the browser.
  """
  try:
    head = (
      (Path(root or Path.cwd()) / ".git" / "HEAD").read_text(encoding="utf-8").strip()
    )
  except OSError:
    return ""
  prefix = "ref: refs/heads/"
  return head[len(prefix) :] if head.startswith(prefix) else ""


def clear_skip_poll(db):
  """Drop an armed Skip poll press when the owner writes.

  The owner presses Skip poll and then writes a note or a report answer. The press would end
  the next wait on an item that just arrived, so the arriving item clears the flag and the
  wait delivers it instead.
  """
  db.execute("DELETE FROM meta WHERE key = ?", (SKIP_POLL_META,))


def reset_poll_count(db):
  """Zero the hook-poll tally only when an item starts a fresh backlog.

  The hook line reports calls since the owner's first still-unread message, so an item
  landing on an unacked pile keeps the tally running instead of zeroing the backlog's age.
  The arriving item is already written when this runs, so a fresh backlog counts one.
  """
  if gate_pending_count(db) == 1:
    db.execute("INSERT OR REPLACE INTO meta VALUES (?, '0')", (POLLS_SINCE_MESSAGE,))


def meta_number(db, key):
  """Read one meta value as a non-negative integer, or 0 when it is absent or not a number."""
  row = db.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
  value = str(row[0]) if row else ""
  return int(value) if value.isdigit() else 0


def gate_pending_count(db):
  """The unacknowledged items that hold a non-inbox Bash call."""
  return db.execute(
    "SELECT (SELECT count(*) FROM notes WHERE acknowledged_at IS NULL AND blocking = 1)"
    " + (SELECT count(*) FROM submissions WHERE acknowledged_at IS NULL)"
  ).fetchone()[0]


def pr_state_warning(line):
  """Reject recognized PR-state writes without executing the command or payload."""

  def payload(text):
    if text.startswith("@"):
      try:
        text = Path(text[1:]).read_text(encoding="utf-8")
      except (OSError, UnicodeError):
        return {}
    try:
      value = json.loads(text)
      return value if isinstance(value, dict) else {}
    except (ValueError, TypeError):
      return {}

  def api_write(words, client):
    method, endpoint, data = "", "", {}
    has_body = False
    index = 0
    while index < len(words):
      word = words[index]
      option, equal, value = word.partition("=")
      if option in (
        {
          "-X",
          "--method",
          "--request",
          "-d",
          "--data",
          "--data-raw",
          "--data-binary",
          "--json",
          "--post-data",
          "--body-data",
          "--input",
          "--post-file",
          "--body-file",
        }
        | ({"-f", "-F", "--field", "--raw-field"} if client == "gh" else set())
      ):
        if not equal:
          index += 1
          value = words[index] if index < len(words) else ""
        has_body = has_body or option not in {"-X", "--method", "--request"}
        if option in {"-X", "--method", "--request"}:
          method = value.upper()
        elif option in {"-f", "-F", "--field", "--raw-field"}:
          key, separator, field = value.partition("=")
          if separator:
            if option in {"-F", "--field"} and field.startswith("@") and field != "@-":
              try:
                field = Path(field[1:]).read_text(encoding="utf-8")
              except (OSError, UnicodeError):
                field = ""
            keys = [key for key in re.split(r"\[|\]", key) if key]
            target = data
            for key in keys[:-1]:
              target = target.setdefault(key, {})
              if not isinstance(target, dict):
                break
            if keys and isinstance(target, dict):
              try:
                target[keys[-1]] = json.loads(field)
              except ValueError:
                target[keys[-1]] = field
        elif option in {"--input", "--post-file", "--body-file"}:
          if value != "-":
            data.update(payload("@" + value))
        else:
          data.update(payload(value))
      elif len(word) > 2 and word[:2] in (
        {"-X", "-d"} | ({"-f", "-F"} if client == "gh" else set())
      ):
        words = [word[:2], word[2:], *words[index + 1 :]]
        index = 0
        continue
      elif word.startswith(("https://", "http://")):
        url = urlsplit(word)
        if client == "gh" or url.hostname == "api.github.com":
          endpoint = url.path.strip("/")
          data.update({key: values[-1] for key, values in parse_qs(url.query).items()})
      elif client == "gh" and (
        word == "graphql" or word.lstrip("/").startswith("repos/")
      ):
        endpoint = word.strip("/").split("?", 1)[0]
      index += 1
    endpoint = unquote(endpoint)
    method = method or ("POST" if has_body else "GET")
    if endpoint == "graphql":
      query = data.get("query", "")
      if not isinstance(query, str):
        return False
      # Quoted titles and bodies are data, not mutation fields.
      query = re.sub(r'"""[\s\S]*?"""|"(?:\\.|[^"\\])*"', '""', query)
      query = re.sub(r"#[^\n]*", "", query)
      if re.search(
        (
          "\\b(?:closePullRequest|reopenPullRequest|mergePullRequest|enablePullRequestAutoMe"
          "rge|enqueuePullRequest|deleteRef|updateRef|mergeBranch|createCommitOnBranch)\\s*\\"
          "("
        ),
        query,
      ):
        return True
      if re.search(r"\bupdatePullRequest\s*\(", query):
        if re.search(r"\bstate\s*:\s*(?:CLOSED|OPEN)\b", query):
          return True
        variables = data.get("variables", {})
        if isinstance(variables, str):
          variables = payload(variables)

        def state_input(value):
          return isinstance(value, dict) and any(
            (key == "state" and item in ("CLOSED", "OPEN")) or state_input(item)
            for key, item in value.items()
          )

        if isinstance(variables, dict) and any(
          state_input(variables.get(name))
          for name in re.findall(r"\binput\s*:\s*\$(\w+)", query)
        ):
          return True
        if isinstance(variables, dict):
          return any(
            variables.get(name) in ("CLOSED", "OPEN")
            for name in re.findall(r"\bstate\s*:\s*\$(\w+)", query)
          )
      return False
    if method == "GET" or method == "HEAD":
      return False
    if re.fullmatch(r"repos/[^/]+/[^/]+/pulls/\d+/merge(?:-async)?", endpoint):
      return True
    if re.fullmatch(r"repos/[^/]+/[^/]+/merges", endpoint):
      return True
    if re.match(r"repos/[^/]+/[^/]+/git/refs/heads/", endpoint):
      return method in {"DELETE", "PATCH"}
    return bool(
      method == "PATCH"
      and re.fullmatch(r"repos/[^/]+/[^/]+/(?:pulls|issues)/\d+", endpoint)
      and data.get("state") in ("closed", "open")
    )

  def blocked(words):
    while words:
      executable = Path(words[0]).name
      if "=" in words[0] and not words[0].startswith("-"):
        words = words[1:]
      elif executable in {"command", "builtin", "exec", "env", "sudo"}:
        if executable == "command" and any(word in {"-v", "-V"} for word in words[1:]):
          return False
        words = words[1:]
        while words and words[0].startswith("-"):
          option = words.pop(0)
          if option in {"-u", "--unset", "--user", "-g", "--group"} and words:
            words.pop(0)
      else:
        break
    if not words:
      return False
    executable, arguments = Path(words[0]).name, words[1:]
    if executable in {"bash", "sh", "dash", "zsh", "ksh"}:
      for index, word in enumerate(arguments[:-1]):
        if word.startswith("-") and "c" in word:
          return script_write(arguments[index + 1])
      return False
    if executable == "git":
      if "push" not in arguments:
        return False
      position = arguments.index("push")
      prefix, remaining = arguments[:position], arguments[position + 1 :]
      targets, destructive, read_only, remote_option, tags_only = (
        [],
        False,
        False,
        False,
        False,
      )
      index = 0
      while index < len(remaining):
        word = remaining[index]
        option, equal, _ = word.partition("=")
        if option in {"-o", "--push-option", "--receive-pack", "--exec", "--repo"}:
          remote_option = remote_option or option == "--repo"
          if not equal:
            index += 1
        elif word in {"--help", "-h", "--dry-run", "-n"}:
          read_only = True
        elif option in {"--delete", "-d", "--mirror", "--all", "--prune"}:
          destructive = True
        elif word == "--tags":
          tags_only = True
        elif not word.startswith("-"):
          targets.append(word)
        index += 1
      if read_only:
        return False
      if destructive:
        return True
      refs = targets if remote_option else targets[1:]
      if refs:
        return any(
          word.lstrip("+").startswith(":")
          or word.rsplit(":", 1)[-1].removeprefix("refs/heads/").lstrip("+") == "main"
          for word in refs
        )
      if tags_only:
        return False
      try:
        branch = subprocess.run(
          ["git", *prefix, "symbolic-ref", "--quiet", "--short", "HEAD"],
          capture_output=True,
          text=True,
          check=False,
        )
        return branch.returncode == 0 and branch.stdout.strip() == "main"
      except OSError:
        return False
    if executable == "gh":
      while arguments and arguments[0].startswith("-"):
        option = arguments.pop(0)
        if option in {"--help", "-h", "--version"}:
          return False
        if option in {"-R", "--repo", "--hostname"} and arguments:
          arguments.pop(0)
      if len(arguments) >= 2 and arguments[0] == "pr":
        if arguments[1] not in {"close", "reopen", "merge"}:
          return False
        value_flags = {
          "--comment",
          "--body",
          "--subject",
          "--match-head-commit",
          "--author-email",
          "--repo",
          "-R",
          "-b",
        }
        return not any(
          word in {"--help", "-h"}
          and (index == 0 or arguments[index - 1] not in value_flags)
          for index, word in enumerate(arguments)
        )
      return bool(
        arguments and arguments[0] == "api" and api_write(arguments[1:], "gh")
      )
    return executable in {"curl", "wget"} and api_write(arguments, executable)

  def script_write(text):
    start, quote, escaped = 0, "", False
    for index, char in enumerate(text):
      if escaped:
        escaped = False
      elif char == "\\" and quote != "'":
        escaped = True
      elif quote:
        if char == quote:
          quote = ""
      elif char in "\"'":
        quote = char
      elif char in ";&|\n":
        if blocked(shlex.split(text[start:index])):
          return True
        start = index + 1
    return blocked(shlex.split(text[start:]))

  try:
    if blocked(shlex.split(line)):
      return "PR STATE BLOCKED: visible PR-state write; use reads or metadata edits."
  except ValueError:
    return None
  return None


def main_identical(root="."):
  """True when origin/main holds the tree at HEAD, so a push carries no change.

  A rewritten main leaves the old branch commits ahead by ancestry while the content
  matches, and that push leaves the pull request without a diff.
  """

  def git(*arguments):
    return subprocess.run(
      ["git", *arguments], cwd=root, capture_output=True, text=True, check=False
    )

  try:
    for ref in ("origin/main", "HEAD"):
      if git("rev-parse", "--verify", "--quiet", ref).returncode:
        return False
    return git("diff", "--quiet", "origin/main", "HEAD", "--").returncode == 0
  except OSError:
    return False


def main_drift_warning(root=".", fresh=True):
  """Read origin tips without moving HEAD, the index, or working files.

  A fresh read fetches the remote tips first, which the push checkpoint pays for.
  The commit checkpoint passes fresh False and reads the local refs alone.
  """

  def git(*arguments):
    return subprocess.run(
      ["git", *arguments],
      cwd=root,
      capture_output=True,
      text=True,
      check=False,
      timeout=30,
      env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
    )

  def unavailable(reason):
    return f"Remote branch check unavailable: {reason}; behind count is unknown."

  try:
    if git("rev-parse", "--git-dir").returncode:
      return ""
    remote = git("remote", "get-url", "origin")
    if fresh and remote.returncode == 0:
      branch = git("symbolic-ref", "--quiet", "--short", "HEAD").stdout.strip()
      if not branch:
        return unavailable("detached HEAD")
      shallow = git("rev-parse", "--is-shallow-repository").stdout.strip() == "true"
      main_ref = "refs/remotes/origin/main"
      branch_ref = f"refs/remotes/origin/{branch}"
      refs = list(
        dict.fromkeys(
          [
            f"+refs/heads/main:{main_ref}",
            f"+refs/heads/{branch}:{branch_ref}",
          ]
        )
      )
      arguments = ["fetch", "--quiet", "--no-tags"]
      if shallow:
        arguments.append("--unshallow")
      fetched = git(*arguments, "origin", *refs)
      if fetched.returncode:
        return unavailable(f"origin fetch failed (exit {fetched.returncode})")
      if git("rev-parse", "--is-shallow-repository").stdout.strip() != "false":
        return unavailable("history is still shallow")
      if git("merge-base", main_ref, branch_ref).returncode:
        return unavailable("main and branch have no shared history")
      counts = git("rev-list", "--left-right", "--count", f"{main_ref}...{branch_ref}")
      if counts.returncode:
        return unavailable("cannot compare remote tips")
      behind, _ahead = map(int, counts.stdout.split())
      if git("diff", "--quiet", main_ref, branch_ref, "--").returncode == 0:
        if behind:
          return (
            f"Remote branch {branch} and origin/main have identical trees; "
            "do not replay those commits. Start new work from main."
          )
      elif behind:
        return (
          f"Remote branch {branch} is {behind} commit(s) behind origin/main. "
          "Check whether main absorbed its commits before rebasing."
        )
    # Preserve the local checkpoint for unpublished repositories and local drift.
    if main_identical(root):
      return ""
    if git("rev-parse", "--is-shallow-repository").stdout.strip() == "true":
      visible = git("rev-list", "--count", "origin/main").stdout.strip()
      if visible in {"", "0", "1"}:
        return ""
    count = git("rev-list", "--count", "HEAD..origin/main")
    if count.returncode == 0 and int(count.stdout.strip()) > 0:
      return (
        f"Local check: origin/main carries {count.stdout.strip()} commit(s) "
        "this branch lacks. Replay your commits over main: run git fetch "
        "origin and git rebase origin/main, then push."
      )
    return ""
  except subprocess.TimeoutExpired:
    return unavailable("Git timed out")
  except (OSError, ValueError):
    return unavailable("cannot read Git state")


def main_ancestor_warning(root="."):
  """The push-blocking message when origin/main is not an ancestor of HEAD, else an empty string.

  The read refreshes origin/main alone, so a branch with no remote counterpart still
  yields a verdict. A fetch fault, a missing origin remote or an unreadable repository
  yields no verdict, and the push checkpoint stays open.
  """

  def git(*arguments):
    return subprocess.run(
      ["git", *arguments],
      cwd=root,
      capture_output=True,
      text=True,
      check=False,
      timeout=30,
      env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
    )

  try:
    if git("rev-parse", "--git-dir").returncode:
      return ""
    if git("remote", "get-url", "origin").returncode:
      return ""
    main_ref = "refs/remotes/origin/main"
    arguments = ["fetch", "--quiet", "--no-tags"]
    if git("rev-parse", "--is-shallow-repository").stdout.strip() == "true":
      arguments.append("--unshallow")
    if git(*arguments, "origin", f"+refs/heads/main:{main_ref}").returncode:
      return ""
    if git("rev-parse", "--verify", "--quiet", main_ref).returncode:
      return ""
    # Exit 0 holds the ancestry and exit 1 denies it. Any other code names a tip the
    # repository cannot compare, so only the denial blocks the push.
    if git("merge-base", "--is-ancestor", main_ref, "HEAD").returncode != 1:
      return ""
    return (
      "PUSH BLOCKED: `origin/main` is not an ancestor of HEAD, so the push replays"
      " onto a stale base. Run `git fetch origin` and `git rebase origin/main`,"
      " then push again."
    )
  except subprocess.TimeoutExpired:
    return ""
  except (OSError, ValueError):
    return ""


def repo_slug(root="."):
  """The owner/name of the origin remote, or an empty string when it will not parse."""
  try:
    url = subprocess.run(
      ["git", "config", "--get", "remote.origin.url"],
      cwd=root,
      capture_output=True,
      text=True,
      check=False,
    ).stdout.strip()
  except OSError:
    return ""
  match = re.search(r"[:/]([^/:]+/[^/]+?)(?:\.git)?$", url)
  return match.group(1) if match else ""


FAILED_CONCLUSIONS = ("failure", "cancelled", "timed_out")
PR_CHECK_POLL_SECONDS = 10


def pr_failed_check(root="."):
  """The failed check names on the branch pull request, joined, or an empty string.

  The poll runs this off its wait path, so a gh read never delays a note. A missing
  branch or pull request reads as an empty string. A gh fault reads as None, so the
  monitor reads again instead of reporting a false all-clear. Only the newest run
  of each job name counts, so a passed re-run clears an older failure.
  """
  branch = workspace_branch(root)
  slug = repo_slug(root)
  if not branch or not slug:
    return ""
  try:
    listed = subprocess.run(
      [
        "gh",
        "pr",
        "list",
        "--head",
        branch,
        "--json",
        "headRefOid",
        "--jq",
        ".[0].headRefOid",
      ],
      cwd=root,
      capture_output=True,
      text=True,
      check=False,
    )
    if listed.returncode:
      return None
    head = listed.stdout.strip()
    if not head:
      return ""
    rows = subprocess.run(
      [
        "gh",
        "api",
        f"repos/{slug}/commits/{head}/check-runs",
        "--paginate",
        "--jq",
        ".check_runs[] | [.name, .started_at, .conclusion] | @tsv",
      ],
      cwd=root,
      capture_output=True,
      text=True,
      check=False,
    )
    if rows.returncode:
      return None
    # The API lists every run of a re-run job, so the newest start per name decides.
    newest = {}
    for row in rows.stdout.splitlines():
      name, _, rest = row.partition("\t")
      stamp, _, conclusion = rest.partition("\t")
      if name and (name not in newest or stamp.rstrip("Z") > newest[name][0]):
        newest[name] = (stamp.rstrip("Z"), conclusion)
    failed = [
      name
      for name, (_, conclusion) in newest.items()
      if conclusion in FAILED_CONCLUSIONS
    ]
    return ", ".join(failed)
  except OSError:
    return None


def pr_check_once(result, root):
  """Append the branch pull request's failed check names, when any check failed.

  The poll calls this from its background monitor, so the gh read never delays
  a note. A gh fault reads as unknown and records nothing.
  """
  failed = pr_failed_check(root)
  if failed:
    result.append(failed)


def pr_check_watch(result, root, stopped):
  while not stopped.is_set():
    pr_check_once(result, root)
    if result:
      return
    stopped.wait(PR_CHECK_POLL_SECONDS)


# A check wait runs in two phases, because the installed gh exits on an empty check list
# instead of waiting for the first check to appear.
PR_CHECK_DISCOVERY_SECONDS = 30
PR_CHECK_DISCOVERY_STEP = 5


def pr_head_sha(root, branch, slug):
  """Read the branch PR head, an empty string for no PR, or None on a fault."""
  try:
    listed = subprocess.run(
      [
        "gh",
        "pr",
        "list",
        "--head",
        branch,
        "--json",
        "headRefOid",
        "--jq",
        ".[0].headRefOid",
      ],
      cwd=root,
      capture_output=True,
      text=True,
      check=False,
      timeout=PR_CHECK_DISCOVERY_STEP,
    )
  except (OSError, subprocess.TimeoutExpired):
    return None
  if listed.returncode:
    return None
  return listed.stdout.strip()


def gh_check_json(root, arguments):
  """Read GitHub check data, or return None on a command, timeout, or JSON fault."""
  try:
    result = subprocess.run(
      ["gh", *arguments],
      cwd=root,
      capture_output=True,
      text=True,
      check=False,
      timeout=PR_CHECK_DISCOVERY_STEP,
    )
    if result.returncode:
      return None
    return [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
  except (OSError, subprocess.TimeoutExpired, ValueError):
    return None


def pr_check_rollup(root, slug, sha):
  """Read all pages and select the latest checks, as gh pr checks does."""
  owner, name = slug.split("/", 1)
  query = (
    "query($owner:String!,$name:String!,$sha:String!,$endCursor:String){"
    "repository(owner:$owner,name:$name){object(expression:$sha){... on Commit{"
    "statusCheckRollup{contexts(first:100,after:$endCursor){"
    "pageInfo{hasNextPage endCursor} nodes{__typename "
    "... on CheckRun{name status conclusion startedAt "
    "checkSuite{workflowRun{workflow{name}}}} "
    "... on StatusContext{context state createdAt}}}}}}}}"
  )
  projection = (
    ".data.repository.object.statusCheckRollup.contexts.nodes[]? | "
    'if .__typename == "CheckRun" then '
    '{kind:"check",name,workflow:(.checkSuite.workflowRun.workflow.name // ""),'
    'state:(if .status == "COMPLETED" then .conclusion else .status end),at:.startedAt} '
    'else {kind:"status",name:.context,workflow:"",state,at:.createdAt} end | @json'
  )
  data = gh_check_json(
    root,
    [
      "api",
      "graphql",
      "--paginate",
      "-f",
      f"query={query}",
      "-f",
      f"owner={owner}",
      "-f",
      f"name={name}",
      "-f",
      f"sha={sha}",
      "--jq",
      projection,
    ],
  )
  if not isinstance(data, list):
    return None
  latest = {}
  for node in data:
    if not isinstance(node, dict) or not all(
      isinstance(node.get(field), str)
      for field in ("kind", "name", "workflow", "state", "at")
    ):
      return None
    if node["kind"] not in ("check", "status") or not node["name"]:
      return None
    try:
      stamp = datetime.fromisoformat(node["at"].replace("Z", "+00:00"))
    except ValueError:
      return None
    if stamp.tzinfo is None:
      return None
    key = (node["kind"], node["name"], node["workflow"])
    if key not in latest or stamp > latest[key][0]:
      latest[key] = stamp, node["state"]
  states = {state for _, state in latest.values()}
  if states & {"ERROR", "FAILURE", "CANCELLED", "TIMED_OUT", "ACTION_REQUIRED"}:
    return "FAILURE", len(latest)
  if not states or states - {"SUCCESS", "SKIPPED", "NEUTRAL"}:
    return "PENDING", len(latest)
  return "SUCCESS", len(latest)


def pr_checks_discovery(
  root=".",
  seconds=PR_CHECK_DISCOVERY_SECONDS,
  step=PR_CHECK_DISCOVERY_STEP,
  sleep=None,
):
  """Observe visible checks for the full window before the requested CLI watch.

  Reset the window on a new head. Fail on a read fault, empty rollup, or non-green deadline state.
  Success is best effort: checks can still appear after this window.
  """
  pause = sleep or time.sleep
  branch = workspace_branch(root)
  slug = repo_slug(root)
  if not branch or not slug:
    return "no branch pull request to watch"
  pinned = pr_head_sha(root, branch, slug)
  if pinned is None:
    return "gh did not read the pull request head"
  if not pinned:
    return "no branch pull request to watch"
  started = time.monotonic()
  polls = (seconds + step - 1) // step + 1
  poll = 0
  while True:
    if poll:
      head = pr_head_sha(root, branch, slug)
      if head is None:
        return "gh did not read the pull request head"
      if not head:
        return "no branch pull request to watch"
      if head != pinned:
        pinned = head
        started = time.monotonic()
        poll = 0
    rollup = pr_check_rollup(root, slug, pinned)
    if rollup is None:
      return "gh did not read the check rollup"
    remaining = seconds - (time.monotonic() - started)
    if remaining <= 0 or poll + 1 == polls:
      head = pr_head_sha(root, branch, slug)
      if head is None:
        return "gh did not read the pull request head"
      if not head:
        return "no branch pull request to watch"
      if head != pinned:
        pinned = head
        started = time.monotonic()
        poll = 0
        continue
      state, count = rollup
      if not count:
        return f"no visible checks appeared on {pinned[:7]} within {seconds} seconds"
      if state != "SUCCESS":
        return (
          f"visible checks are {state.lower()} on {pinned[:7]} after {seconds} seconds"
        )
      return None
    pause(min(step, remaining))
    poll += 1


# The record kinds whose IDs are session-local: minted here, unresolvable elsewhere.
SESSION_ID_TABLES = (
  ("notes", "note"),
  ("submissions", "answer"),
  ("reports", "report"),
  ("tasks", "task"),
)
# A row minted before the six-character change cites its seven-character head in old prose.
HEX7_RE = re.compile(r"[0-9a-f]{7}")
# A minted ID that clashes with a stored row re-mints. Six characters hold 16.7 million
# values, so a handful of tries clears every realistic clash, and the last one refuses.
MINT_ATTEMPTS = 16
DIFF_FILE_RE = re.compile(r"^\+\+\+ b/(.+)$")
DIFF_HUNK_RE = re.compile(r"^@@ -\S+ \+(\d+)")


def session_id_tokens(store):
  """Every literal the commit trap matches, mapped to the record it names.

  The list comes from the state database and never from a pattern, so a git SHA
  that is not a session ID cannot match. A citation is the first six characters, which
  is the whole ID of a row minted now, and an older dashed ID also matches on its
  seven-character head, the form older prose cites.
  """
  tokens = {}
  with closing(store.connect()) as db:
    for table, label in SESSION_ID_TABLES:
      for row in db.execute(f"SELECT id FROM {table}").fetchall():
        ident = row["id"]
        tokens.setdefault(ident, (label, ident))
        # Only a minted ID takes a citation token: a written ID such as a task name
        # keeps its whole form, whatever its first characters spell.
        if NOTE_ID.fullmatch(ident):
          tokens.setdefault(ident[:6], (label, ident))
        head = ident.split("-", 1)[0]
        if HEX7_RE.fullmatch(head):
          tokens.setdefault(head, (label, ident))
  return tokens


def staged_session_id_hits(store, root="."):
  """Each staged line that cites a session-local ID.

  Only added lines count, so a citation this commit removes does not block it.
  A token matches on a word boundary, which keeps a 7-character window inside a
  longer SHA out while a standalone short SHA still fires.
  """
  tokens = session_id_tokens(store)

  if not tokens:
    return []

  try:
    diff = subprocess.run(
      ["git", "diff", "--cached", "-U0", "--no-color"],
      cwd=root,
      capture_output=True,
      text=True,
      check=False,
    )
  except OSError:
    return []

  if diff.returncode:
    return []

  patterns = {
    token: re.compile(rf"(?<![0-9A-Za-z]){re.escape(token)}(?![0-9A-Za-z])")
    for token in tokens
  }
  hits = []
  path = None
  number = 0

  for line in diff.stdout.splitlines():
    named = DIFF_FILE_RE.match(line)

    if named:
      path = named.group(1)
      continue

    hunk = DIFF_HUNK_RE.match(line)

    if hunk:
      number = int(hunk.group(1)) - 1
      continue

    if not line.startswith("+") or line.startswith("+++"):
      continue

    number += 1

    for token, pattern in patterns.items():
      if pattern.search(line):
        kind, ident = tokens[token]
        hits.append((path, number, token, kind, ident))

  return hits


def commit_id_report(hits):
  """The block message for a commit whose staged lines cite session-local IDs."""
  if not hits:
    return None

  lines = [
    (
      "COMMIT BLOCKED: the staged change cites a session-local ID. That ID exists"
      " only in this session, so a reader of the repository cannot resolve it."
    )
  ]

  for path, number, token, kind, ident in hits:
    named = ident if token == ident else f"{token} of {ident}"
    lines.append(f"  {path}:{number}: {kind} {named}")

  lines.append("Strip the citation, then commit again.")
  renames = {ident for _, _, _, kind, ident in hits if kind in {"task", "report"}}
  if renames:
    lines.append(
      "If this is a name collision, rename the preview record, not repository content:"
    )
    lines.extend(
      f"  arena-preview rename {shlex.quote(ident)} NEW-ID" for ident in sorted(renames)
    )
    lines.append("Replace NEW-ID with an unused preview ID.")
  return "\n".join(lines)


def new_id():
  """One identifier in the shape the log shows: six characters, whole.

  Six characters name a note in prose and in a task marker, so the mint carries no tail
  to cut. A row minted before this change keeps its longer ID and cites its head.
  """
  return uuid.uuid4().hex[:6]


def seconds_since(value):
  """Seconds between one stored stamp and now, or None when it will not parse."""
  if not value:
    return None
  try:
    return (datetime.now(timezone.utc) - datetime.fromisoformat(value)).total_seconds()
  except ValueError:
    return None


def clip_stamp(value):
  "Cut an ISO stamp to seconds. A restore needs no milliseconds or offset."
  return value[:19] if value else value


def at_or_after(value, other):
  "True when a stored stamp is at or after another. Equal seconds count."
  if not value or not other:
    return False
  return clip_stamp(value) >= clip_stamp(other)


def import_stamp(value):
  """Return a stamp for comparison, in UTC, or None when the text will not parse.

  A save file may carry a naive stamp (the server writes UTC) or one with an
  offset, so both sides become aware datetimes before they compare.
  """
  if not value:
    return None
  try:
    parsed = datetime.fromisoformat(str(value))
  except ValueError:
    return None
  if parsed.tzinfo is None:
    parsed = parsed.replace(tzinfo=timezone.utc)
  return parsed


def identifier(value):
  if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
    raise ValueError("ID must contain 1–80 letters, digits, underscores or hyphens")
  return value


def owner_text(text):
  if not isinstance(text, str) or not text.strip():
    raise ValueError("Enter a nonblank note")
  return text


def note_text(text):
  if not isinstance(text, str) or not text.strip():
    raise ValueError("Enter a nonblank note")
  return text


def when(value):
  """Return a timestamp a restore carried exactly as it arrived, once it parses."""
  try:
    datetime.fromisoformat(str(value))
  except ValueError as error:
    raise ValueError(f"Not a timestamp: {value!r}") from error
  return str(value)


def restore_receipt(acknowledged_at, ack_kind, ack_text, ack_edited_at=None):
  """Check a restored receipt. Require all receipt fields or none. Reject a partial receipt so a note never
  returns as answered."""
  carried = (acknowledged_at, ack_kind, ack_text)
  if all(value is None for value in carried):
    if ack_edited_at is not None:
      raise ValueError("An edited receipt needs an acknowledgement")
    return (None, None, None, None)
  if any(value is None for value in carried):
    raise ValueError(
      "A restored receipt carries its stamp, kind and text, or none of them"
    )
  if ack_kind not in {"note", "reply"}:
    raise ValueError("Every acknowledgement is a note or a reply, with its text")
  return (
    when(acknowledged_at),
    ack_kind,
    note_text(ack_text),
    when(ack_edited_at) if ack_edited_at is not None else None,
  )


def restore_replies(replies, acknowledged):
  """Check replies from later acknowledgements. Require kind, text, and a stamp for each reply. Reject replies
  on an unanswered record. Store the list as JSON text."""
  if not replies:
    return None
  if not acknowledged:
    raise ValueError("Appended replies need an acknowledgement")
  if not isinstance(replies, list):
    raise TypeError("Appended replies are a list")
  checked = []
  for item in replies:
    if not isinstance(item, dict) or item.get("kind") not in {"note", "reply"}:
      raise ValueError(
        "Every appended reply is a note or a reply, with its text and stamp"
      )
    checked.append(
      {
        "kind": item["kind"],
        "text": note_text(item.get("text")),
        "at": when(item.get("at")),
      }
    )
  return json.dumps(checked, ensure_ascii=False)


def replies_list(value):
  """The list shape the state surface and the save file carry for a stored replies column."""
  return json.loads(value) if value else []


def message_row(row):
  """One note or answer row as a record, its replies parsed.

  The record carries no seq: the arrival stamp orders and identifies a note, and a
  surfaced sequence number only invites citing it instead of the ID.
  """
  record = dict(row)
  record.pop("seq", None)
  if "replies" in record:
    record["replies"] = replies_list(record["replies"])
  return record


def reply_reference(text):
  """Return the first-line RE target, or None for an ordinary note."""
  match = REPLY_REFERENCE.match(text or "")
  return match.group(1) if match else None


def reply_thread(record, notes):
  """Return parent records from oldest to newest, without repeated IDs."""
  thread, seen = [], {record["id"]}
  target = reply_reference(record.get("text"))
  while target:
    parent = notes.get(target)
    if parent is None:
      matches = [note for note_id, note in notes.items() if note_id.startswith(target)]
      if len(matches) != 1:
        break
      parent = matches[0]
    parent_id = parent["id"]
    if parent_id in seen:
      break
    thread.append(parent)
    seen.add(parent_id)
    target = reply_reference(parent.get("text"))
  return list(reversed(thread))


def restore_reply_seen_count(value, replies):
  "Check the saved count of viewed appended replies."
  if value is None:
    return 0
  if type(value) is not int or value < 0:
    raise ValueError("A saved viewed-reply count is a nonnegative integer")
  if value > len(replies_list(replies)):
    raise ValueError("A saved viewed-reply count exceeds the stored replies")
  return value


def submission_text(text):
  "Check flattened owner answers."
  if not isinstance(text, str) or not text.strip():
    raise ValueError("A report submission carries at least one answer")
  return text


def slug(text, used):
  base = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60] or "field"
  candidate, suffix = base, 2
  while candidate in used:
    candidate = f"{base}-{suffix}"
    suffix += 1
  used.add(candidate)
  return candidate


def prompt_text(line):
  text = re.sub(r"^\s*(?:[-*+]\s+|#+\s+|>\s+|\d+[.)]\s+)", "", line).strip()
  return text.strip("*_` ").rstrip(":").strip()


def custom_label(option):
  """The label of a free-text option, or None for a plain one.

  `Label: ___` means free text whether it is a whole field or one option in a group, so the same BLANK pattern
  decides both. A bare `___` option falls back to the label `Other`."""
  found = BLANK.match(option)
  return None if not found else prompt_text(found.group(1) or "") or "Other"


def custom_answer(field, value):
  "Return true when a free-text option in this field receives typed text."
  if not isinstance(value, str):
    return False
  for option in field["options"]:
    label = custom_label(option)
    if label is None or not value.startswith(f"{label}: "):
      continue
    typed = value[len(label) + 2 :]
    if typed.strip():
      return True
  return False


def option_continuation(line):
  """True when a line wraps the option above it instead of starting a new block."""
  if not line.strip() or BLOCK_START.match(line):
    return False
  return not BLANK.match(line) and not ANCHOR.match(line)


def parse_fields(markdown):
  """Split Markdown into prose blocks and answer fields written as list markers."""
  lines = markdown.splitlines()
  blocks, chunk, questions, used = [], [], [], set()
  fence, prompt, anchor, index, position = None, "", None, 0, 0
  while position < len(lines):
    line = lines[position]
    if fence is not None:
      chunk.append(line)
      if line.strip().startswith(fence):
        fence = None
      position += 1
      continue
    opening = FENCE.match(line)
    if opening:
      fence = opening.group(1)
      chunk.append(line)
      position += 1
      continue
    kind = (
      "choice" if CHOICE.match(line) else "checkbox" if CHECKBOX.match(line) else None
    )
    blank = None if kind else BLANK.match(line)
    if not kind and not blank:
      chunk.append(line)
      if line.strip():
        prompt, anchor = prompt_text(ANCHOR.sub("", line)), None
        found = ANCHOR.search(line)
        if found:
          anchor = found.group(1)
          chunk[-1] = ANCHOR.sub("", line)
      position += 1
      continue
    index += 1
    if kind:
      pattern = CHOICE if kind == "choice" else CHECKBOX
      options, default = [], []
      while position < len(lines):
        item = pattern.match(lines[position])
        if not item:
          break
        preselected = item.group(1).lower() == "x"
        options.append(item.group(2))
        if preselected:
          default.append(item.group(2))
        position += 1
        while position < len(lines) and option_continuation(lines[position]):
          options[-1] = f"{options[-1]} {lines[position].strip()}"
          if preselected:
            default[-1] = options[-1]
          position += 1
      if len(set(options)) != len(options):
        raise ValueError(
          f"Field '{prompt or index}' repeats an option; make each unique"
        )
      question = {"type": kind, "options": options, "default": default}
    else:
      label = (blank.group(1) or "").strip()
      question = {"type": "text", "default": []}
      if label:
        prompt, anchor = prompt_text(ANCHOR.sub("", label)), None
        found = ANCHOR.search(label)
        if found:
          anchor = found.group(1)
      position += 1
    question["prompt"] = prompt or f"Field {index}"
    question["id"] = (
      anchor if anchor and anchor not in used else slug(question["prompt"], used)
    )
    used.add(question["id"])
    anchor = None
    blocks.append(("markdown", "\n".join(chunk)))
    blocks.append(("field", question))
    chunk = []
    questions.append(question)
  blocks.append(("markdown", "\n".join(chunk)))
  if questions:
    Store.validate_fields(questions)
  return blocks, questions


def field_html(question):
  prompt = html.escape(question["prompt"], quote=True)
  name = html.escape(question["id"], quote=True)
  body = f'<div class="question" data-field="{name}"'
  body += f' data-type="{question["type"]}">'
  body += f'<small class="question-id">Question ID: <code>{name}</code></small>'
  if question["type"] == "text":
    return (
      f'{body}<textarea class="answer-text" rows="2" '
      f'placeholder="Answer" aria-label="{prompt}"></textarea></div>'
    )
  control = "radio" if question["type"] == "choice" else "checkbox"
  group = f'<div class="options" role="group" aria-label="{prompt}">'
  for option in question["options"]:
    value = html.escape(option, quote=True)
    checked = " checked" if option in question["default"] else ""
    label = custom_label(option)
    if label is None:
      group += (
        f'<label class="option"><input type="{control}" name="{name}" '
        f'value="{value}"{checked}> {html.escape(option)}</label>'
      )
      continue
    named = html.escape(label, quote=True)
    group += (
      f'<label class="option"><input type="{control}" name="{name}" '
      f'value="{value}"{checked} data-label="{named}" aria-label="{named}">'
      f'<textarea class="custom-text" rows="1" data-custom="{named}" '
      f'placeholder="{named}:" aria-label="{named}, your own answer"></textarea></label>'
    )
  return f"{body}{group}</div></div>"


TASK_STATUSES = ("upcoming", "finished")
# One primary type per task, by deliverable. Stored legacy values stay unchanged.
TASK_UNSPECIFIED = "unspecified"
TASK_MISC = "misc"
TASK_TYPES = ("report", "code", "docs", "ops", "misc")
TASK_LEGACY_TYPES = ("operations", TASK_UNSPECIFIED)
TASK_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
# A note ID is six hex characters, alone or followed by a hyphen and the rest for a row minted
# before the six-character change, and the shape check above accepts it as a task name without this.
NOTE_ID = re.compile(r"^[0-9a-f]{6,7}(?:-[0-9a-f]+)?$")
MAX_TASK_TITLE = 200
MAX_TASK_DETAIL = 2000
MAX_TASK_DETAILS = 40
# A task detail is one step: a longer line is a wall of text, and the tool refuses it.
TASK_STEP_MAX = 120
TASK_ORDER_OWNED_META = "task_order_owned"
TASK_ORDER_PENDING_META = "task_order_notice_pending"
TASK_ORDER_NOTICE = (
  "Task order changed in the preview; preserve its upcoming task order."
)
ECHO_DETAIL = 200
TASK_COLUMNS = (
  "id, title, details, status, position, updated_at, completed_at, blocked, report_id,"
  " type"
)
TASK_ORDER = (
  "status DESC, CASE WHEN status = 'finished' THEN completed_at END DESC,"
  " CASE WHEN status = 'finished' THEN id END DESC, (blocked = 0 OR report_id IS NULL), position, id"
)
# Each kind has its own table and ID columns. No foreign keys or cascades change these rows.
# A rename repoints them by hand.
RENAME_TARGETS = {
  "note": ("notes", (("uploads", "note_id"),)),
  "answer": ("submissions", ()),
  "report": ("reports", (("submissions", "report_id"), ("tasks", "report_id"))),
  "task": ("tasks", (("notes", "task_id"), ("submissions", "task_id"))),
}
RENAME_TABLES = ("notes", "submissions", "reports", "tasks")

# The importer carries note, task, and answer lines through one schema.
# Name keys here so the writer and reader stay aligned. The default save path stays inside the ignored state directory.
CLI_DESCRIPTION = (
  "Notes, reports, tasks and the preview server for Arena steering. The platform's"
  " hooks call the -tick commands, `gate`, `inbox-line` and `route-run`; the rest are"
  " the agent's."
)
SAVED_STATE = "saved-state.ndjson"
NOTE_LINE_KEYS = (
  "id",
  "text",
  "at",
  "acknowledged_at",
  "ack_kind",
  "ack_text",
  "ack_edited_at",
  "replies",
  "ack_edited_seen_count",
  "seen_at",
  "task_id",
)
TASK_LINE_KEYS = (
  "id",
  "title",
  "details",
  "status",
  "completed_at",
  "order",
  "report_id",
  "type",
)
SUBMISSION_LINE_KEYS = (
  "id",
  "report_id",
  "text",
  "at",
  "acknowledged_at",
  "ack_kind",
  "ack_text",
  "ack_edited_at",
  "replies",
  "ack_edited_seen_count",
  "seen_at",
  "task_id",
)
REPORT_LINE_KEYS = ("id", "title", "markdown", "published_at", "seen_at")


def task_row(row):
  """Shape one stored task for the state payload, keeping its details a list.

  A task carries its report link only while it waits on that report, so an unlinked
  task keeps the shape it had before the link existed.
  """
  shaped = {
    "id": row[0],
    "title": row[1],
    "details": json.loads(row[2]),
    "status": row[3],
    "order": row[4],
    "updated_at": row[5],
    "completed_at": row[6] if len(row) > 6 else None,
    "blocked": bool(row[7]) if len(row) > 7 else False,
  }
  if len(row) > 8 and row[8]:
    shaped["report_id"] = row[8]
  shaped["type"] = row[9] if len(row) > 9 and row[9] else TASK_MISC
  return shaped


def link_task_answers(db, records):
  """Attach each task's linked answers, one entry per submission ID.

  The page block and the CLI list share this read: every answer of the task's report
  plus any answer that names the task. A task with no link keeps its record unchanged.
  """
  links = db.execute(
    "SELECT id, report_id, task_id, text, at FROM submissions ORDER BY at, seq"
  ).fetchall()
  answers = [
    {
      "id": link["id"],
      "at": clip_stamp(link["at"]),
      "text": link["text"],
      "report_id": link["report_id"],
      "task_id": link["task_id"],
    }
    for link in links
  ]
  for item in records:
    linked = [
      {
        "id": answer["id"],
        "at": answer["at"],
        "text": answer["text"],
        "report_id": answer["report_id"],
      }
      for answer in answers
      if answer["task_id"] == item["id"]
      or (answer["report_id"] and answer["report_id"] == item.get("report_id"))
    ]
    if linked:
      item["answers"] = linked
  return records


def saved_note_line(record):
  """Return the keys a saved note line carries, and nothing else."""
  if not isinstance(record, dict):
    raise TypeError("Every saved note is an object")
  return {key: record.get(key) for key in NOTE_LINE_KEYS}


def saved_answer_line(record):
  """Return the keys a saved report answer line carries, so a restore keeps the answer."""
  if not isinstance(record, dict):
    raise TypeError("Every saved answer is an object")
  return {key: record.get(key) for key in SUBMISSION_LINE_KEYS}


def saved_report_line(record):
  """Return source and the owner's first-read stamp for one report save line."""
  if not isinstance(record, dict):
    raise TypeError("Every saved report is an object")
  return {key: record.get(key) for key in REPORT_LINE_KEYS}


def state_ndjson(lines):
  """Return one JSON line per record, with one trailing newline: the save-file text."""
  return "".join(json.dumps(line, ensure_ascii=False) + "\n" for line in lines)


def saved_task_line(record):
  """Return the keys a saved task line carries. Details keep their list shape.

  The report link rides only when a task has one, so a task line stays disjoint from an answer line, which is
  the only other line that carries a `report_id`."""
  if not isinstance(record, dict):
    raise TypeError("Every saved task is an object")
  line = {key: record.get(key) for key in TASK_LINE_KEYS}
  line["details"] = [str(item) for item in record.get("details") or []]
  line["type"] = record.get("type") or TASK_MISC
  if not line.get("report_id"):
    line.pop("report_id", None)
  return line


def upload_name(name):
  "Return the supplied file name for labels and the download header."
  cleaned = Path(str(name or "")).name.strip()
  if not cleaned:
    raise ValueError("An upload needs a file name")
  if any(ord(char) < 32 or ord(char) == 127 for char in cleaned):
    raise ValueError("A file name must not contain control characters")
  return cleaned


def header_filename(name):
  """A download file name with the characters that split a response header replaced."""
  return str(name).replace("\n", "_").replace("\r", "_").replace('"', "_")


def fetch_url(value, *, agent=True):
  "Accept one HTTPS URL without credentials or control characters. The server never fetches it."
  if not isinstance(value, str) or not value.strip() or (agent and len(value) > 2048):
    raise ValueError("Enter one HTTPS URL of at most 2048 characters")
  value = value.strip()
  if any(ord(char) < 33 or ord(char) == 127 for char in value):
    raise ValueError("A download URL must not contain spaces or control characters")
  try:
    parsed = urlsplit(value)
    if parsed.scheme.lower() != "https" or not parsed.hostname or parsed.port == 0:
      raise ValueError("Only HTTPS download URLs are allowed")
    if parsed.username is not None or parsed.password is not None:
      raise ValueError("Do not put credentials in a download URL")
  except ValueError as error:
    raise ValueError(f"Invalid HTTPS download URL: {error}") from error
  return urlunsplit(parsed._replace(fragment=""))


def fetch_row(row, directory):
  """Expose metadata and disk presence, but never the claim secret used by a browser worker."""
  item = dict(row)
  item.pop("claim", None)
  item["allow_proxy"] = bool(item["allow_proxy"])
  file = item["file"]
  path = directory / FETCH_DIR / file if file else None
  item["path"] = str(path) if path else None
  item["present"] = bool(path and path.is_file())
  return item


def upload_type(content_type):
  "Return the browser content type or a neutral type. Do not use it to read bytes."
  cleaned = str(content_type or "").split(";")[0].strip()[:120]
  return cleaned or "application/octet-stream"


class FileBody:
  def __init__(self, stream):
    self.stream = stream
    self.path = None
    self.size = 0
    self.hash = hashlib.sha256()

  def __len__(self):
    return self.size

  def write(self, chunk):
    self.stream.write(chunk)
    self.size += len(chunk)
    self.hash.update(chunk)

  def digest(self):
    return self.hash.hexdigest()

  def save(self, target):
    source = self.path.open("rb") if self.path else self.stream
    with closing(source) if self.path else nullcontext(source):
      source.seek(0)
      with target.open("wb") as output:
        shutil.copyfileobj(source, output, 65536)


def body_digest(data):
  return (
    data.digest() if isinstance(data, FileBody) else hashlib.sha256(data).hexdigest()
  )


def save_body(target, data):
  # Replace a file only when complete, including after a restore.
  with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as staged:
    temporary = Path(staged.name)
  try:
    if isinstance(data, FileBody):
      data.save(temporary)
    else:
      temporary.write_bytes(data)
    temporary.chmod(0o600)
    os.replace(temporary, target)
  finally:
    temporary.unlink(missing_ok=True)


class RequestBody:
  def __init__(self, stream, length):
    self.stream = stream
    self.remaining = length
    self.buffer = b""

  def fill(self):
    if self.remaining == 0:
      return False
    chunk = self.stream.read(min(65536, self.remaining))
    if not chunk:
      raise ValueError("Incomplete request body")
    self.remaining -= len(chunk)
    self.buffer += chunk
    return True

  def take(self, size):
    while len(self.buffer) < size:
      if not self.fill():
        raise ValueError("Incomplete multipart body")
    result, self.buffer = self.buffer[:size], self.buffer[size:]
    return result

  def until(self, marker, write, boundary=False):
    while True:
      index = self.buffer.find(marker)
      if index >= 0:
        end = index + len(marker)
        if boundary:
          while len(self.buffer) < end + 2 and self.fill():
            pass
          if self.buffer[end : end + 2] not in {b"\r\n", b"--"}:
            write(self.buffer[: index + 1])
            self.buffer = self.buffer[index + 1 :]
            continue
        write(self.buffer[:index])
        self.buffer = self.buffer[end:]
        return
      keep = len(marker) - 1
      if len(self.buffer) > keep:
        write(self.buffer[:-keep])
        self.buffer = self.buffer[-keep:]
      if not self.fill():
        raise ValueError("Incomplete multipart body")


@contextmanager
def stream_note_attachments(content_type, stream, length):
  from email import policy
  from email.parser import BytesParser

  if any(char in content_type for char in "\r\n"):
    raise ValueError("Invalid multipart boundary")
  header = BytesParser(policy=policy.default).parsebytes(
    b"Content-Type: " + content_type.encode("ascii") + b"\r\n\r\n"
  )
  boundary = header.get_boundary()
  if (
    not boundary
    or not re.fullmatch(r"[0-9A-Za-z'()+_,./:=? -]{1,70}", boundary)
    or boundary.endswith(" ")
  ):
    raise ValueError("Invalid multipart boundary")
  reader = RequestBody(stream, length)
  delimiter = b"--" + boundary.encode("ascii")
  if reader.take(len(delimiter) + 2) != delimiter + b"\r\n":
    raise ValueError("Invalid multipart opening")
  with tempfile.TemporaryDirectory() as staging:
    fields, files = {}, []
    while True:
      headers = bytearray()
      reader.until(b"\r\n\r\n", headers.extend)
      part = BytesParser(policy=policy.default).parsebytes(bytes(headers) + b"\r\n\r\n")
      for key in ("Content-Disposition", "Content-Type", "Content-Transfer-Encoding"):
        if len(part.get_all(key, [])) > 1:
          raise ValueError("Duplicate attachment header")
      encoding = str(part.get("Content-Transfer-Encoding", "binary")).strip().lower()
      if encoding not in {"binary", "8bit"}:
        raise ValueError("Unsupported attachment transfer encoding")
      name = part.get_param("name", header="content-disposition")
      if (
        part.defects
        or part.is_multipart()
        or part.get_content_disposition() != "form-data"
        or name not in {"id", "text", "file"}
      ):
        raise ValueError("Unexpected note attachment field")
      if name != "file" and (name in fields or part.get_filename() is not None):
        raise ValueError("Duplicate or invalid note attachment field")
      if name == "file":
        path = Path(staging) / str(len(files))
        stream = path.open("wb")
        body = FileBody(stream)
        body.path = path

        def write(chunk, body=body):
          body.write(chunk)

        with stream:
          reader.until(b"\r\n" + delimiter, write, boundary=True)
        if not body:
          raise ValueError("An upload must not be empty")
        files.append((part.get_filename(), part.get_content_type(), body))
      else:
        value = bytearray()
        reader.until(b"\r\n" + delimiter, value.extend, boundary=True)
        fields[name] = value.decode("utf-8")
      ending = reader.take(2)
      if ending == b"--":
        if (reader.buffer or reader.remaining) and reader.take(2) != b"\r\n":
          raise ValueError("Invalid closing multipart delimiter")
        # Consume the remainder to detect a short body, even after a closing delimiter.
        while reader.fill():
          reader.buffer = b""
        break
      if ending != b"\r\n":
        raise ValueError("Invalid multipart delimiter")
    if set(fields) != {"id", "text"} or not files:
      raise ValueError("Send one note ID, text and at least one file")
    yield fields["id"], fields["text"], files


def upload_row(row, directory):
  """A stored upload, plus the two things the row cannot say: where the bytes are and whether they are there."""
  path = directory / UPLOAD_DIR / row["file"]
  record = dict(row) | {"path": str(path), "present": path.exists()}
  record.pop("seq", None)
  return record


def add_note_attachments(note, records):
  "Expose all file paths to the agent and names to the receipt. Keep first-file compatibility."
  if records:
    note["attachment_name"] = records[0]["name"]
    note["attachment_path"] = records[0]["path"]
    note["attachments"] = records
  return note


def bare_id(token):
  "Return one ID token. Accept a token wrapped in backticks. Reject blank values."
  return str(token or "").strip().strip("`").strip()


def format_size(size):
  """A byte count in B, KB or MB, whichever keeps the read line short."""
  if size < 1024:
    return f"{size} B"
  if size < 1024**2:
    return f"{short_number(size / 1024)} KB"
  return f"{short_number(size / 1024**2)} MB"


def short_number(value):
  """One decimal, dropped when the value is whole: 1.5, 2, 47.7."""
  text = f"{value:.1f}"
  return text.removesuffix(".0")


def attachment_line(record):
  """One attachment as name and path, with the size of the bytes that are there."""
  line = f"{record.get('name', '')}: {record.get('path', '')}"
  if not record.get("present"):
    return line + " (missing)"
  size = record.get("size")
  return line + (f" ({format_size(size)})" if isinstance(size, int) else "")


def format_pending_record(item):
  """Format one pending record without its reply thread."""
  kind = item.get("kind") or "note"
  display_kind = "answer" if kind == "report" else kind
  # A short ID names the record, and a short ID acks it, so the full ID costs nothing here.
  # The ticks hold the citation together across any renderer between this line and its reader.
  header = "`" + str(item.get("id", ""))[:6] + "`"
  if display_kind != "note":
    header += f" {display_kind}"
  if item.get("quiet") and not item.get("blocking"):
    header += " quiet (no ack required)"
  if item.get("report_id"):
    header += f" report {item['report_id']}"
  lines = [header]
  text = item.get("text") or ""
  if text:
    lines.append(text)
  # A note's own text never names its uploads, so the read carries each file's name, saved
  # path and size.
  attachments = item.get("attachments") or []
  if attachments:
    names = ", ".join(attachment_line(record) for record in attachments)
    lines.append(f"attachments: {names}")
  return "\n".join(lines)


def format_pending_item(item):
  if not reply_reference(item.get("text")):
    return format_pending_record(item)
  context = ""
  for parent in item.get("thread") or []:
    body = REPLY_REFERENCE.sub("", parent.get("text") or "", count=1).lstrip("\r\n")
    body = format_pending_record(parent | {"text": body}).partition("\n")[2]
    if context:
      body = context + "\n\n" + body
    context = "\n".join("> " + line for line in body.split("\n"))
  body = REPLY_REFERENCE.sub("", item.get("text") or "", count=1).lstrip("\r\n")
  context = context or "Referenced message unavailable."
  return format_pending_record(item | {"text": context + "\n\n" + body})


def format_read(listing):
  checked_at = listing.get("checked_at")
  pending = listing.get("pending") or []
  count = len(pending)
  if checked_at:
    first = f"Inbox {local_stamp(checked_at)}: {count} pending"
  else:
    first = f"Inbox: {count} pending"
  if count == 0:
    return first
  # No blank line between items: the short ID opens each one, so the split stays visible.
  return "\n".join([first, *(format_pending_item(item) for item in pending)])


def current_task(tasks):
  """The first upcoming task no blocked mark holds, or None when every one waits.

  A task that waits on a report sorts first in its group, so the head alone would hand the
  current seat to work the agent cannot start. Both the CLI listing and the page read this.
  """
  for task in tasks:
    if task.get("status") == "upcoming" and not task.get("blocked"):
      return task
  return None


def format_task_list(tasks, full=False):
  """The working queue by default. `full` prints every task, finished included.

  The first unblocked upcoming task reads `current`, the same one the page gives a div of its own, so what the
  agent can start next is visible without reading down a list."""
  shown = tasks if full else [t for t in tasks if t.get("status") == "upcoming"]
  lines = [f"Tasks {len(shown)}" if full else f"Tasks {len(shown)} upcoming"]
  if any(t.get("blocked") for t in shown):
    lines.append("* = blocked on a report answer or linked run")
  head = None if full else current_task(shown)
  for task in shown:
    order = task.get("order")
    status = task.get("status")
    if head is not None and task.get("id") == head.get("id"):
      status = "current"
    id_ = task.get("id")
    blocked = task.get("blocked")
    report_id = task.get("report_id")
    blocked_mark = "*" if blocked else ""
    line = f"{order}{blocked_mark}  {status} {id_}"
    if report_id:
      line += f" | waits on {report_id}"
    if task.get("runs"):
      line += f" | runs {', '.join(task['runs'])}"
    if task.get("type") and task.get("type") != TASK_UNSPECIFIED:
      line += f" | type {task.get('type')}"
    lines.append(line)
    for detail in task.get("details", []):
      lines.append(f"    {detail}")
    for answer in task.get("answers", []):
      lines.append(f"    answer {answer['id']}, at {answer['at']}")
      lines.append(f"    {answer['text']}")
  return "\n".join(lines)


def format_task(record, full=False):
  id_ = record.get("id")
  order = record.get("order")
  status = record.get("status")
  report_id = record.get("report_id")
  blocked = record.get("blocked")
  title = record.get("title") or ""
  details = record.get("details") or []
  cut = (
    details
    if full
    else [
      detail[:ECHO_DETAIL] + ("\u2026" if len(detail) > ECHO_DETAIL else "")
      for detail in details
    ]
  )
  first = f"task {id_}, order {order}, status {status}"
  task_type = record.get("type")
  if task_type and task_type != TASK_UNSPECIFIED:
    first += f", type {task_type}"
  if report_id:
    first += f", report {report_id}"
  if record.get("runs"):
    first += f", runs {', '.join(record['runs'])}"
  if blocked:
    first += ", blocked"
  lines = [first, title] + [f"- {d}" for d in cut]
  if full:
    for answer in record.get("answers", []):
      lines.extend([f"answer {answer['id']}, at {answer['at']}", answer["text"]])
  return "\n".join(lines)


def format_key(record):
  lines = []
  if record.get("key"):
    lines.append(f"key {record['key']}")
  if record.get("host"):
    lines.append(f"host {record['host']}")
    # The sandbox egress filter blocks the proxy host, so a shell call cannot carry the key.
    # Naming the tool here stops a session from retrying the read through bash.
    lines.append(f"use fetch_page on {record['host']}/v1/<route>?key=<key>, never bash")
  if record.get("at"):
    lines.append(f"at {local_stamp(record['at'])}")
  return "\n".join(lines) if lines else ""


def format_fetch_job(job):
  """Render one download request: what waits in the queue and the owner's next click."""
  id_ = job.get("id")
  url = job.get("url")
  allow_proxy = job.get("allow_proxy")
  approval = job.get("approval")
  status = job.get("status")
  line = f"Queued {id_} {url}"
  if allow_proxy is not None:
    line += f" (proxy {'on' if allow_proxy else 'off'})"
  if approval:
    line += f", approval {approval}"
  if status:
    line += f", status {status}"
  parts = [line]
  if approval == "pending":
    parts.append("Ask the owner to Approve it on the Preview page.")
  return "\n".join(parts)


def format_import_receipt(receipt, merged=False):
  notes = receipt.get("notes", 0)
  answers = receipt.get("answers", 0)
  reports = receipt.get("reports", 0)
  tasks = receipt.get("tasks", 0)
  fate = "merged by ID" if merged else "the live state was replaced"
  return (
    f"Imported notes {notes}, answers {answers}, reports {reports}, tasks {tasks};"
    f" {fate}"
  )


def format_clear_state(counts):
  parts = [f"{k} {v}" for k, v in counts.items()]
  return "Cleared " + ", ".join(parts) if parts else "Cleared"


def require_server(store):
  """Break a guarded call while the preview server is not up, so the agent starts it.

  `serve` records its bound port in the state, so a call can tell a quiet
  inbox from a dead server: the port is the evidence, and a refused connect
  means the owner's page is gone with it. A state that never served has no
  live preview either, so it breaks the same way. The error names the
  restart command as the script the installer puts on PATH, with the
  recorded port when one exists.
  """
  port = store.meta_value("port")
  if not port:
    raise ValueError("preview server is not up. Start it with arena-preview serve")
  with closing(socket.socket()) as probe:
    probe.settimeout(1)
    if probe.connect_ex(("127.0.0.1", int(port))) == 0:
      return
  raise ValueError(
    f"preview server is down; start it before polling: arena-preview serve --port {port}"
  )


def print_read(store):
  """Print pending entries, then mark delivered IDs as seen. A failed print leaves each entry pending.
  Seen nonquiet entries still need acknowledgement."""
  listing = store.read()
  print(format_read(listing), flush=True)
  if listing["pending"]:
    store.mark_seen([item["id"] for item in listing["pending"]])
    store.mark_reports_agent_seen(
      [item.get("report_id") for item in listing["pending"]]
    )


POLL_INTERVAL = 1

POLL_MAX_LOOPS = 1800
POLL_WAIT_SECONDS = 1799
POLLING_META = "polling_at"
# Stamp the wait start once.
# The page then shows the agent wait length.
POLL_SINCE_META = "polling_since"
# The page shows its polling dot while a poll heartbeat is no older than this.
POLLING_FRESH_SECONDS = 5.0
# The latest wall-clock slot that created the hidden, agent-blocking read-set note.
READ_SET_SLOT_META = "read_set_slot"
READ_SET_INTERVAL_MINUTES = 20
# The owner's Skip poll press is a one-shot request: the waiting poll ends at once, and no
# note lands in the message log for a later turn to misread.
SKIP_POLL_META = "skip_poll_at"


def read_set_slot(moment=None):
  """The current 00, 20, or 40 wall-clock slot, including its UTC offset."""
  moment = moment or datetime.now(DISPLAY_ZONE or timezone.utc)
  if moment.tzinfo is None:
    moment = moment.replace(tzinfo=timezone.utc)
  minute = (moment.minute // READ_SET_INTERVAL_MINUTES) * READ_SET_INTERVAL_MINUTES
  return moment.replace(minute=minute, second=0, microsecond=0).isoformat()


def read_set_paths(root=None):
  """Existing files in the required read set, in stable reading order."""
  root = Path(root or resolve_repo_root()).resolve()
  agents = []
  for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
    dirnames[:] = sorted(name for name in dirnames if name not in WORKSPACE_SKIP)
    if "AGENTS.md" in filenames:
      agents.append(Path(dirpath) / "AGENTS.md")
  skill = root / ".agents" / "skills" / "arena-skill" / "SKILL.md"
  return [
    path for path in [root / "ARENA.md", *sorted(agents), skill] if path.is_file()
  ]


INERT_COMMANDS = (
  "cd",
  "export",
  "set",
  "unset",
  "true",
  ":",
  "source",
  ".",
  "trap",
  "shopt",
  "umask",
)


def unquote_commands(line):
  """Return the command line with quoted text dropped.

  Quoted text is an argument, never a command, so a reply may span lines. A
  substitution inside quotes still runs, so it leaves a marker behind.
  """
  kept = []
  quote = ""
  index = 0
  text = str(line or "").replace("\r", "\n")
  while index < len(text):
    char = text[index]
    if quote:
      if char == "\\" and quote == '"':
        index += 2
        continue
      # Only double quotes substitute: backticks and $() inside single quotes stay text.
      if quote == '"' and (text.startswith("$(", index) or char == "`"):
        kept.append(" $(")
      if char == quote:
        quote = ""
      index += 1
      continue
    if char in ("'", '"'):
      quote = char
      index += 1
      continue
    if char == "\\" and index + 1 < len(text):
      kept.append(text[index + 1])
      index += 2
      continue
    kept.append(char)
    index += 1
  return "".join(kept)


# An inline ack text in double quotes, which is the shape the shell substitutes.
INLINE_ACK_RE = re.compile(r'(?:arena-preview|preview\.py)\s+ack(?:\s+[\w.-]+)*\s+"')


def bare_backtick(text):
  """True when text holds a backtick the shell substitutes. An odd backslash run escapes none."""
  index = 0
  while True:
    index = text.find("`", index)
    if index < 0:
      return False
    slashes = 0
    while index - slashes - 1 >= 0 and text[index - slashes - 1] == "\\":
      slashes += 1
    if slashes % 2 == 0:
      return True
    index += 1


def tick_warning(line):
  """A warning when an inline ack text carries an unescaped backtick inside double quotes.

  The shell runs a backtick in double quotes as a command and substitutes its output, so the
  ticks vanish before the tool sees the text. The gate reads the command line before that
  expansion, so this is the one place the loss can be named before it happens.
  """
  found = INLINE_ACK_RE.search(line or "")
  if not found or not bare_backtick(line[found.end() :]):
    return None
  return (
    "arena-preview gate: that ack text sits in double quotes, so the shell runs each"
    " unescaped backtick as a command and the ticks vanish. Single-quote the text."
  )


SERVE_PORT_RE = re.compile(
  r"(?:arena-preview|preview\.py)\s+serve\b[^\n]*?(?:--port|-p)(?:=|\s*)(\d+)"
)


def serve_warning(line):
  """Warn when `serve` uses a nondefault port. The poll and page use the recorded port, so another port hides both.
  Inspect the line before it runs."""
  found = SERVE_PORT_RE.search(line or "")
  if not found or int(found.group(1)) == DEFAULT_PORT:
    return None
  return (
    f"arena-preview gate: that serve names port {found.group(1)}, not the standard"
    f" {DEFAULT_PORT}. The page the owner has open follows the standard address, and"
    f" the poll follows the recorded port. Name another only when {DEFAULT_PORT} is"
    " taken, and say so."
  )


# Sandbox hosts come from arena-quirks.md: "Sandbox egress allowlist, GitHub session" (2026-10-03).
# Other hosts resolve and accept TCP, then fail TLS with SSL_ERROR_SYSCALL. Callers retry this transient fault.
EGRESS_ALLOWLIST = frozenset(
  (
    "github.com",
    "api.github.com",
    "codeload.github.com",
    "registry.npmjs.org",
    "pypi.org",
    "files.pythonhosted.org",
    "dns.google",
  )
)

# The commands that open a network connection to a URL named on the line. A URL inside
# any other command is text, so it must not raise the warning.
FETCH_COMMAND_RE = re.compile(
  r"(?:^|[\s;&|(])(?:curl|wget|git\s+(?:clone|fetch|ls-remote|pull|push))\b"
)
URL_HOST_RE = re.compile(r"(?:https?|ftp)://([^/\s\"'@?]+)")
# The preview server listens on the loopback address, so a read of it never leaves the sandbox.
LOOPBACK_HOSTS = frozenset(("127.0.0.1", "localhost", "::1"))


def url_host(authority):
  """Return the host of a URL authority, with the IPv6 brackets and any port removed."""
  if authority.startswith("["):
    return authority.split("]", 1)[0].lstrip("[").lower()
  return authority.split(":", 1)[0].lower()


def egress_warning(line):
  """Warn before a command reaches a host that the sandbox filter blocks. Suggest `fetch_page`, which runs outside
  the sandbox."""
  text = line or ""
  if not FETCH_COMMAND_RE.search(text):
    return None
  hosts = []
  for found in URL_HOST_RE.finditer(text):
    host = url_host(found.group(1))
    if (
      host
      and host not in EGRESS_ALLOWLIST
      and host not in LOOPBACK_HOSTS
      and host not in hosts
    ):
      hosts.append(host)
  if not hosts:
    return None
  names = ", ".join(hosts)
  return (
    f"arena-preview gate: {names} sits outside this sandbox's egress allowlist. The"
    " TLS handshake fails with SSL_ERROR_SYSCALL, which reads as a transient fault"
    " and never clears on a retry. Read it through the fetch_page tool instead."
  )


def first_blocking_piece(line):
  """Return the first command that ends the inbox-only exemption. Return None only when the line contains an inbox
  call and inert prefixes. A redirect ends the exemption because it hides the reminder. Ignore debug traps that
  silence output."""
  text = unquote_commands(line)
  for separator in ("&&", "||", ";", "|", "\n"):
    text = text.replace(separator, "\x00")
  for piece in text.split("\x00"):
    tokens = [token for token in piece.split() if token]
    if not tokens:
      continue
    # Strip leading assignments like VAR=value and bash invocation.
    idx = 0
    while idx < len(tokens) and "=" in tokens[idx] and not tokens[idx].startswith("-"):
      idx += 1
    if idx >= len(tokens):
      continue
    # Bash itself and its flags are inert for the purpose of the full cmdline.
    if tokens[idx] == "bash":
      idx += 1
      while idx < len(tokens) and tokens[idx].startswith("-"):
        idx += 1
        # -c takes a following arg that is the script. Skip it if present
        # but keep checking remaining pieces via outer split.
        if idx < len(tokens) and tokens[idx - 1] == "-c":
          # Split the script by newline and stop here.
          break
      if idx >= len(tokens):
        continue
    head = tokens[idx].rsplit("/", 1)[-1]
    if head in INERT_COMMANDS:
      continue
    if head in ("arena-preview", "preview.py"):
      rest = tokens[idx + 1 :]
      # A substitution runs work beside the read. Ignore a plain redirect for debug traps.
      if any(token.startswith("$(") or "`" in token for token in rest):
        return piece.strip()
      continue
    return piece.strip()
  return None


# A shell keyword runs the command that follows it, so a piece may start with one.
SHELL_KEYWORDS = ("do", "then", "else", "elif", "if", "for", "until", "while", "time")


def command_pieces(line):
  """Split a shell line at its separators, so each piece stands on its own."""
  text = unquote_commands(line)
  for separator in ("&&", "||", ";", "|", "\n"):
    text = text.replace(separator, "\x00")
  return [piece.strip() for piece in text.split("\x00") if piece.strip()]


def piece_head(piece):
  """Name the command a piece runs, past assignments, shell keywords and a bash word."""
  tokens = [token for token in piece.split() if token]
  index = 0
  while (
    index < len(tokens) and "=" in tokens[index] and not tokens[index].startswith("-")
  ):
    index += 1
  while index < len(tokens) and tokens[index].strip("\"'") in SHELL_KEYWORDS:
    index += 1
  if index < len(tokens) and tokens[index] == "bash":
    index += 1
    while index < len(tokens) and tokens[index].startswith("-"):
      index += 1
  if index >= len(tokens):
    return ""
  return tokens[index].rsplit("/", 1)[-1].strip("\"'")


def idle_wait(line):
  """Name a sleep that waits beside a preview call, so the gate stops it before it runs.

  A sleep on its own runs, because the line holds nothing else. The gate reads the
  shell's own command line, so the login wrapper comes off first.
  """
  heads = [head for head in map(piece_head, command_pieces(agent_line(line))) if head]
  if "sleep" not in heads or not any(
    head in ("arena-preview", "preview.py") for head in heads
  ):
    return None
  return (
    "WAIT BLOCKED: a sleep beside a preview call holds the turn. Take the next queued"
    " task, or read the run on a later call. A routed run keeps its verdict, and"
    " `arena-preview poll` waits when the queue is empty."
  )


def quiet_inbox_line(line):
  """True when a command line that names an inbox call runs nothing else."""
  return first_blocking_piece(line) is None


def read_set_actions(line):
  """Preview subcommands on an otherwise inert line, or None when the line does work."""
  actions = []
  for piece in command_pieces(agent_line(line)):
    tokens = [token for token in unquote_commands(piece).split() if token]
    index = 0
    while (
      index < len(tokens) and "=" in tokens[index] and not tokens[index].startswith("-")
    ):
      index += 1
    while index < len(tokens) and tokens[index].strip("\"'") in SHELL_KEYWORDS:
      index += 1
    if index >= len(tokens):
      continue
    head = tokens[index].rsplit("/", 1)[-1].strip("\"'")
    if head in INERT_COMMANDS:
      continue
    if (
      head.startswith("python")
      and index + 1 < len(tokens)
      and tokens[index + 1].rsplit("/", 1)[-1].strip("\"'") == "preview.py"
    ):
      index += 1
      head = "preview.py"
    if head not in ("arena-preview", "preview.py") or index + 1 >= len(tokens):
      return None
    actions.append(tokens[index + 1].strip("\"'"))
  return tuple(actions)


def read_set_tick(store, line, moment=None, root=None):
  """Create a due checkpoint and block work until the agent acknowledges it."""
  actions = read_set_actions(line)
  if (actions and set(actions) == {"poll"}) or poll_timeout_line(line):
    return None
  pending = store.pending_read_set_note()
  if pending is None:
    if store.polling():
      return None
    pending = store.schedule_read_set_note(moment=moment, root=root)
  if pending is None or (actions is not None and set(actions) <= {"read", "ack"}):
    return None
  return (
    f"READ SET BLOCKED: checkpoint {pending['id']} is pending. Run"
    " `arena-preview read`, read every listed path in full with the read tool, then"
    f" `arena-preview ack {pending['id']} <markdown>`."
  )


# Commands around an inbox call end its quiet-line exemption and appear in the block hint.
# A cd prefix may stay on a line but still counts against the call threshold.
GATE_NOISE = ("tail", "grep", "head")


RUN_NAME = re.compile(r"[A-Za-z0-9._-]{1,64}")
RUN_TAIL_LINES = 40
# The gh watch loop prints its own advice and reprints every check each frame.
RUN_FOOTER_RE = re.compile(
  r"^Refreshing checks status every \d+ seconds\. Press Ctrl\+C to quit\.$"
)


def clean_run_tail(lines):
  """Drop the watch footer, then keep one copy of a repeated line in its last place."""
  kept = []
  for line in lines:
    if RUN_FOOTER_RE.match(line):
      continue
    if line in kept:
      kept.remove(line)
    kept.append(line)
  return kept


def run_record_path(state_dir, name):
  return Path(state_dir) / "runs" / f"{name}.json"


def read_marker_path(state_dir, name):
  return Path(state_dir) / "runs" / f"{name}.read"


def run_read_stamp(state_dir, name):
  """Return the start stamp of the run an earlier read named, or None."""
  try:
    return read_marker_path(state_dir, name).read_text(encoding="utf-8").strip()
  except OSError:
    return None


def mark_run_read(state_dir, name, record):
  """Record one read of a live run, so the next read waits for its verdict.

  The marker holds the run's start stamp. A fresh run under the same name carries
  another stamp, so its first read stands, and the run record stays untouched.
  """
  marker = read_marker_path(state_dir, name)
  try:
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(str(record.get("started_at") or ""), encoding="utf-8")
  except OSError:
    pass


ROUTE_START_FAILED = "routed child failed to start; rerun the gate"
ROUTE_CHILD_EXITED = "routed child exited without recording a verdict; rerun the gate"


def write_run_record(path, record):
  """Atomically replace one routed-run record."""
  path = Path(path)
  path.parent.mkdir(parents=True, exist_ok=True)
  descriptor, temporary = tempfile.mkstemp(
    prefix=f".{path.name}.", dir=path.parent, text=True
  )
  try:
    with os.fdopen(descriptor, "w", encoding="utf-8") as file:
      file.write(json.dumps(record, ensure_ascii=False, indent=1) + "\n")
      file.flush()
      os.fsync(file.fileno())
    os.replace(temporary, path)
  except OSError:
    try:
      Path(temporary).unlink()
    except OSError:
      pass
    raise


def process_start_identity(pid):
  """Return Linux's stable process-start tick for a live process, or None."""
  if isinstance(pid, bool) or not isinstance(pid, int) or pid < 1:
    return None
  try:
    stat = (Path("/proc") / str(pid) / "stat").read_text(encoding="utf-8")
  except OSError:
    return None
  close = stat.rfind(")")
  fields = stat[close + 2 :].split() if close >= 0 else []
  return fields[19] if len(fields) > 19 else None


def routed_child_matches(record):
  """True when a pending record still names its original child process."""
  pid = record.get("pid")
  started = record.get("pid_started_at")
  return (
    isinstance(pid, int)
    and not isinstance(pid, bool)
    and isinstance(started, str)
    and bool(started)
    and process_start_identity(pid) == started
  )


def terminal_route_failure(path, record, verdict):
  """Write a terminal routed failure without replaying its command."""
  failed = dict(record)
  elapsed = detached_seconds(failed.get("started_at"))
  failed.update(
    {
      "exit": 1,
      "seconds": elapsed if elapsed is not None else 0,
      "finished_at": now(),
      "verdict": verdict,
      "tail": [verdict],
      "announced": False,
    }
  )
  write_run_record(path, failed)
  return failed


def reconcile_routed_record(path, record):
  """Turn a vanished routed child into a terminal failure record."""
  if (
    record.get("detached")
    and record.get("exit") is None
    and not routed_child_matches(record)
  ):
    return terminal_route_failure(path, record, ROUTE_CHILD_EXITED)
  return record


WORKTREE_DIR = "worktrees"
WORKTREE_ACTIONS = {"gate": "a gate", "commit": "a commit", "push": "a push"}


def worktree_record_path(state_dir, name):
  return Path(state_dir) / WORKTREE_DIR / f"{name}.json"


def json_record(path):
  try:
    record = json.loads(Path(path).read_text(encoding="utf-8"))
  except (OSError, ValueError):
    return None
  return record if isinstance(record, dict) else None


def routed_record(state_dir, name):
  if not RUN_NAME.fullmatch(name or ""):
    raise ValueError(
      "Gate names take 1 to 64 letters, digits, dots, dashes or underscores."
    )
  path = run_record_path(state_dir, name)
  record = json_record(path)
  if record is None:
    raise ValueError(f"No routed run named {name}.")
  return reconcile_routed_record(path, record)


def git_worktree(cwd, *args, input=None, allowed=(0,)):
  """Run Git for a detached-worktree record and return its text output."""
  try:
    result = subprocess.run(
      ["git", *args],
      cwd=str(cwd),
      input=input,
      capture_output=True,
      text=True,
      check=False,
    )
  except OSError as error:
    raise ValueError(f"Cannot run Git: {error}") from None
  if result.returncode not in allowed:
    detail = (result.stderr or result.stdout).strip()
    raise ValueError(detail or f"Git {' '.join(args)} failed")
  return result.stdout


def git_worktree_root(cwd=None):
  """The Git worktree root at cwd."""
  root = git_worktree(cwd or Path.cwd(), "rev-parse", "--show-toplevel").strip()
  return Path(root).resolve()


def under_path(path, parent):
  try:
    Path(path).resolve().relative_to(Path(parent).resolve())
  except ValueError:
    return False
  return True


def stored_worktree(state_dir, name):
  name = checked_worktree_name(name)
  record = json_record(worktree_record_path(state_dir, name))
  if record is None:
    raise ValueError(f"No worktree named {name}.")
  return record


def worktree_at(state_dir, cwd=None):
  current = Path(cwd or Path.cwd()).resolve()
  directory = Path(state_dir) / WORKTREE_DIR
  if not directory.is_dir():
    return None
  for path in sorted(directory.glob("*.json")):
    record = json_record(path)
    target = record.get("worktree") if record else None
    if isinstance(target, str) and under_path(current, target):
      return record
  return None


def worktree_warning(state_dir, action, cwd=None):
  """Name a registered detached worktree that must not run an action."""
  record = worktree_at(state_dir, cwd)
  if record is None:
    return None
  label = WORKTREE_ACTIONS.get(action, action)
  return (
    f"WORKTREE BLOCKED: {record.get('name')} is detached. Do not run {label} here."
    f" Run it from {record.get('root')}."
  )


def checked_worktree_name(name):
  if not RUN_NAME.fullmatch(name or ""):
    raise ValueError(
      "Worktree names take 1 to 64 letters, digits, dots, dashes or underscores."
    )
  return name


def start_worktree(state_dir, name, destination, gate, allowed, cwd=None):
  """Create one detached task worktree while a routed root gate runs."""
  name = checked_worktree_name(name)
  if not allowed or any(not pattern for pattern in allowed):
    raise ValueError("Give at least one --allow path glob.")
  current = Path(cwd or Path.cwd()).resolve()
  registered = worktree_at(state_dir, current)
  if registered is not None:
    raise ValueError(
      f"Start a worktree from the registered root: {registered.get('root')}."
    )
  root = git_worktree_root(current)
  if current != root:
    raise ValueError("Start a worktree from the repository root.")
  destination = Path(destination).expanduser().resolve()
  if destination.exists():
    raise ValueError(f"Worktree path already exists: {destination}")
  if under_path(destination, root):
    raise ValueError("Put the detached worktree outside the repository root.")
  record_path = worktree_record_path(state_dir, name)
  if record_path.exists():
    raise ValueError(f"A worktree named {name} is already recorded.")
  running = routed_record(state_dir, gate)
  if not running.get("detached") or running.get("exit") is not None:
    raise ValueError(f"Gate {gate} is not running.")
  base = git_worktree(root, "rev-parse", "HEAD").strip()
  destination.parent.mkdir(parents=True, exist_ok=True)
  git_worktree(root, "worktree", "add", "--detach", str(destination), base)
  record = {
    "name": name,
    "root": str(root),
    "worktree": str(destination),
    "base": base,
    "gate": gate,
    "allow": list(allowed),
    "created_at": now(),
  }
  try:
    record_path.parent.mkdir(parents=True, exist_ok=True)
    record_path.write_text(
      json.dumps(record, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
  except OSError as error:
    subprocess.run(
      ["git", "worktree", "remove", "--force", str(destination)],
      cwd=str(root),
      capture_output=True,
      check=False,
    )
    raise ValueError(f"Cannot record worktree {name}: {error}") from None
  return record


def worktree_paths(worktree):
  """The tracked and untracked paths that a detached worktree changed."""
  tracked = git_worktree(worktree, "diff", "--name-only", "-z", "HEAD")
  untracked = git_worktree(worktree, "ls-files", "--others", "--exclude-standard", "-z")
  return sorted({path for path in (tracked + untracked).split("\0") if path})


def collect_worktree(state_dir, name, cwd=None):
  """Return an allowed detached-worktree patch after its root gate passes."""
  record = stored_worktree(state_dir, name)
  root = Path(record.get("root", "")).resolve()
  if Path(cwd or Path.cwd()).resolve() != root:
    raise ValueError(f"Collect worktree {name} from its root: {root}")
  worktree = Path(record.get("worktree", "")).resolve()
  if git_worktree_root(worktree) != worktree:
    raise ValueError(f"Worktree path is not a Git root: {worktree}")
  if git_worktree(worktree, "rev-parse", "HEAD").strip() != record.get("base"):
    raise ValueError(f"Worktree {name} has a commit. Keep task changes uncommitted.")
  gate = routed_record(state_dir, record.get("gate"))
  if gate.get("exit") is None:
    raise ValueError(f"Gate {record.get('gate')} is still running.")
  if gate.get("exit") != 0:
    raise ValueError(f"Gate {record.get('gate')} did not pass.")
  allowed = record.get("allow")
  if not isinstance(allowed, list) or not all(
    isinstance(pattern, str) for pattern in allowed
  ):
    raise ValueError(f"Worktree {name} has no valid allowed paths.")
  paths = worktree_paths(worktree)
  if not paths:
    raise ValueError(f"Worktree {name} has no changes.")
  outside = [
    path for path in paths if not any(fnmatchcase(path, pattern) for pattern in allowed)
  ]
  if outside:
    raise ValueError("Worktree changes outside allowed paths: " + ", ".join(outside))
  patch = git_worktree(worktree, "diff", "--binary", "--no-ext-diff", "HEAD")
  for path in git_worktree(
    worktree, "ls-files", "--others", "--exclude-standard", "-z"
  ).split("\0"):
    if not path:
      continue
    patch += git_worktree(
      worktree,
      "diff",
      "--no-index",
      "--binary",
      "--",
      "/dev/null",
      path,
      allowed=(0, 1),
    )
  return patch


def run_command(state_dir, name, argv):
  """Run one command in this process, then record its exit for a later call.

  This is the child side of `route`: the detached child calls it as `route-run`, and a
  test calls it directly. It prints the output tail and the verdict line for whoever
  reads this process, and the record carries both either way.
  """
  if not RUN_NAME.fullmatch(name or ""):
    print(
      "arena-preview route: the name takes 1 to 64 letters, digits, dot, dash or"
      " underscore.",
      flush=True,
    )
    return 2
  if argv[:1] == ["--"]:
    argv = argv[1:]
  if not argv:
    print(
      "arena-preview route: name a command after --, for example: route gates -- make"
      " check",
      flush=True,
    )
    return 2
  started = time.monotonic()
  # Observe the full window before watching. A discovery failure never starts the watch.
  check_watch = pr_checks_command(argv)
  discovery = pr_checks_discovery(resolve_repo_root()) if check_watch else None
  if discovery:
    completed = subprocess.CompletedProcess(
      argv, 1, f"pr-checks wait failed: {discovery}\n", ""
    )
  else:
    completed = subprocess.run(argv, capture_output=True, text=True, check=False)
    if check_watch and completed.returncode == 0:
      completed.stdout += (
        "\nBest effort: all visible checks passed; later checks can still appear.\n"
      )
  seconds = round(time.monotonic() - started, 1)
  output = (completed.stdout + completed.stderr).splitlines()
  tail = clean_run_tail(output[-RUN_TAIL_LINES:])
  verdict = tail[-1] if tail else "(no output)"
  path = run_record_path(state_dir, name)
  existing = json_record(path) or {}
  record = {
    **existing,
    "name": name,
    "argv": argv,
    "exit": completed.returncode,
    "seconds": seconds,
    "finished_at": now(),
    "verdict": verdict,
    "tail": tail,
    "announced": False,
  }
  write_run_record(path, record)
  for line in tail:
    print(line, flush=True)
  # One stream: the agent reads both, so a duplicate line only costs tokens.
  print(
    f"run {name} done: exit {completed.returncode} {seconds}s {verdict}", flush=True
  )
  return completed.returncode


def live_runs(state_dir):
  """Names of detached waits that have not finished, in run-name order.

  The Skip poll press reads this list: a live run still has a verdict to deliver, so the
  press waits for it instead of ending the turn early.
  """
  names = []
  runs = Path(state_dir) / "runs"
  if not runs.is_dir():
    return names
  for path in sorted(runs.glob("*.json")):
    record = json_record(path)
    if record is None:
      continue
    record = reconcile_routed_record(path, record)
    if record.get("detached") and record.get("exit") is None:
      names.append(record.get("name") or path.stem)
  return names


def live_task_runs(state_dir):
  """Map each task ID to its live routed-run names.

  Run files own this state. Reading the map reconciles a vanished child first, so an
  orphan releases its task through the same terminal record as a passed or failed run.
  """
  linked = {}
  runs = Path(state_dir) / "runs"
  if not runs.is_dir():
    return linked
  for path in sorted(runs.glob("*.json")):
    record = json_record(path)
    if record is None:
      continue
    record = reconcile_routed_record(path, record)
    task_id = record.get("task_id")
    if (
      record.get("detached")
      and record.get("exit") is None
      and isinstance(task_id, str)
      and task_id
    ):
      linked.setdefault(task_id, []).append(record.get("name") or path.stem)
  return linked


def link_task_runs(records, state_dir):
  """Overlay run-owned blocking on task records without changing stored task rows."""
  linked = live_task_runs(state_dir)
  for record in records:
    names = linked.get(record.get("id"))
    if names:
      record["runs"] = names
      record["blocked"] = True
    else:
      record.pop("runs", None)
  return records


def guard_task_runs(state_dir, task_id=None, action="change"):
  """Refuse a destructive task change while one of its linked runs is live."""
  linked = live_task_runs(state_dir)
  selected = linked if task_id is None else {task_id: linked.get(task_id, [])}
  held = [(identifier, names) for identifier, names in selected.items() if names]
  if not held:
    return
  labels = "; ".join(
    f"{identifier}: {', '.join(names)}" for identifier, names in sorted(held)
  )
  raise ValueError(f"Cannot {action}; live task run(s): {labels}")


def skip_poll_ready(store):
  "Return true when the owner requests a skip and no detached run is live."
  return store.skip_poll_requested() and not live_runs(store.path.parent)


def run_notices(state_dir, show_running=False):
  """Print one useful routed-run notice per call.

  A finished verdict wins over a live status. Each finished record prints once, while a
  live detached record can report its age on a later call. The return value lets a poll
  stop when a verdict arrives.
  """
  runs = Path(state_dir) / "runs"
  if not runs.is_dir():
    return 0
  records = []
  for path in sorted(runs.glob("*.json")):
    record = json_record(path)
    if record is not None:
      records.append((path, reconcile_routed_record(path, record)))
  for path, record in records:
    if record.get("exit") is None or record.get("announced"):
      continue
    print(
      f"run {record.get('name')} done: exit {record.get('exit')} {record.get('seconds')}s"
      f" {record.get('verdict')}",
      flush=True,
    )
    record["announced"] = True
    write_run_record(path, record)
    return 1
  if not show_running:
    return 0
  for _, record in records:
    if record.get("exit") is not None or not record.get("detached"):
      continue
    elapsed = detached_seconds(record.get("started_at"))
    if elapsed is None or elapsed > DETACHED_STATUS_SECONDS:
      continue
    print(f"run {record.get('name')} running {elapsed}s", file=sys.stderr, flush=True)
    return 1
  return 0


SHELL_WRAPPER = re.compile(r"^(?:\S*/)?(?:ba|z|da)?sh\s+(?:-\w+\s+)*-c\s+")


def shell_command_text(text):
  """Return the command a shell wrapper runs, so a block names the command, not its launcher."""
  stripped = SHELL_WRAPPER.sub("", text.strip(), count=1)
  if len(stripped) >= 2 and stripped[0] == stripped[-1] and stripped[0] in "'\"":
    stripped = stripped[1:-1]
  return stripped


def gate_line_hint(line):
  """Name the extra commands on a blocked call, so the next read keeps the exemption."""
  words = {token for token in re.split(r"[^A-Za-z0-9_.-]+", line or "")}
  found = [name for name in GATE_NOISE if name in words]
  if not found:
    return None
  named = ", ".join(f"`{name}`" for name in found)
  return f"This call runs {named}. Omit them: only a bare `arena-preview read` passes."


def poll_timeout_line(line):
  """True when the shell `timeout` command wraps an arena-preview poll.

  The poll has a 1799-second deadline, so a `timeout` wrapper can kill the
  wait before it returns its listing. Give the Bash tool 1800 seconds instead. The check reads
  command pieces, so a line that merely mentions both words, like a script that
  documents the ban, stays fine.
  """
  text = unquote_commands(line or "")
  for separator in ("&&", "||", ";", "|", "\n"):
    text = text.replace(separator, "\x00")
  for piece in text.split("\x00"):
    tokens = [token for token in piece.split() if token]
    if not tokens or tokens[0].rsplit("/", 1)[-1] != "timeout":
      continue
    words = tokens[1:]
    for index, word in enumerate(words):
      if (
        word in ("arena-preview", "preview.py")
        and index + 1 < len(words)
        and words[index + 1] == "poll"
      ):
        return True
  return False


# A wrapper in front of the head token changes only that token, so the scan steps past
# one and the flags, assignments or seconds that follow it.
PR_CHECK_WRAPPERS = (
  "env",
  "command",
  "timeout",
  "xargs",
  "nice",
  "nohup",
  "stdbuf",
  "sudo",
)
PR_CHECK_NAMES = (("pr", "checks", "pr-checks"), ("run", "watch", "run-watch"))
# Long test runs can outlive their shell call. The trap detaches them as it detaches check waits.
# The heads carry no repository knowledge, so the same set serves every repo the installer touched.
LONG_RUN_HEADS = {"pytest": "pytest", "py.test": "pytest", "tox": "tox", "nox": "nox"}
# Each rule stores command words and a run name. A final `*` matches a prefix, so `npm run test:unit` counts.
# Test commands match alone. Build commands (`npm install`, `make build`, `go build`) stay legal.
LONG_RUN_WORDS = (
  (("npm", "test"), "npm-tests"),
  (("npm", "run", "test*"), "npm-tests"),
  (("yarn", "test"), "yarn-tests"),
  (("pnpm", "test"), "pnpm-tests"),
  (("make", "test"), "make-tests"),
  (("npx", "jest"), "npx-tests"),
  (("npx", "vitest"), "npx-tests"),
  (("npx", "mocha"), "npx-tests"),
  (("npx", "ava"), "npx-tests"),
  (("go", "test"), "go-tests"),
  (("cargo", "test"), "cargo-tests"),
  (("dotnet", "test"), "dotnet-tests"),
  (("mvn", "test"), "mvn-tests"),
  (("mvnw", "test"), "mvn-tests"),
  (("gradle", "test"), "gradle-tests"),
  (("gradlew", "test"), "gradle-tests"),
)
WORKTREE_STEP = (
  "NEXT: work queued file task in worktree while this runs: `arena-preview "
  "worktree start --gate <gate-name> [--allow <glob>] <name> <destination>`."
)
DETACHED_NOTICE = (
  "RUN DETACHED: `{name}` runs in background, call ends clean. Verdict on "
  "later call. " + WORKTREE_STEP
)
DETACHED_BLOCK = (
  "RUN BLOCKED: background start failed, wait not started. Use `arena-preview "
  "route {name} -- <the same line>` instead."
)
# A detached record older than this stops printing its status line, so a killed child
# leaves no forever-running line.
DETACHED_STATUS_SECONDS = 7200
# Tests set this so a classifier probe writes the record without starting a real wait.
DETACH_DRY_RUN = "ARENA_PREVIEW_DETACH_DRY"


def long_run_words(tokens, index, head):
  """Return the matching runner name at this head position. The caller removes paths and quotes first. Skip flags
  between the head and runner words."""
  rest = [token for token in tokens[index + 1 :] if not token.startswith("-")]
  for words, name in LONG_RUN_WORDS:
    if head != words[0]:
      continue
    span = rest[: len(words) - 1]
    if len(span) != len(words) - 1:
      continue
    if all(
      token.startswith(word[:-1]) if word.endswith("*") else token == word
      for token, word in zip(span, words[1:])
    ):
      return name
  return None


def long_run_name(line):
  """Return a detached-run name or None. Recognize check waits and test runs after wrappers, flags, substitutions,
  or chains. Ignore a line that only prints those words. Let `bash` use its own gate."""
  text = unquote_commands(line or "")
  for separator in ("&&", "||", ";", "|", "\n", "$(", "`"):
    text = text.replace(separator, "\x00")
  for piece in text.split("\x00"):
    tokens = [token for token in piece.split() if token]
    index = 0
    while (
      index < len(tokens) and "=" in tokens[index] and not tokens[index].startswith("-")
    ):
      index += 1
    while index < len(tokens):
      head = tokens[index].lstrip("({\"'").rsplit("/", 1)[-1]
      if head not in PR_CHECK_WRAPPERS:
        break
      index += 1
      while index < len(tokens) and (
        tokens[index].startswith("-")
        or "=" in tokens[index]
        or tokens[index].rstrip("smhd").isdigit()
      ):
        if head == "command" and re.fullmatch(r"-[pVv]*[Vv][pVv]*", tokens[index]):
          index = len(tokens)
          break
        index += 1
    if index >= len(tokens):
      continue
    head = tokens[index].lstrip("({\"'").rsplit("/", 1)[-1]
    if head in INERT_COMMANDS or head == "bash":
      continue
    if head in LONG_RUN_HEADS:
      return LONG_RUN_HEADS[head]
    runner = long_run_words(tokens, index, head)
    if runner:
      return runner
    if head.startswith("python") and tuple(tokens[index + 1 : index + 3]) == (
      "-m",
      "pytest",
    ):
      return "pytest"
    if head == "node" and tokens[index + 1 : index + 2] == ["--test"]:
      return "node-tests"
    if head != "gh":
      continue
    for position, word in enumerate(tokens[index + 1 : -1]):
      for first, second, name in PR_CHECK_NAMES:
        if word == first and tokens[index + 2 + position] == second:
          return name
  return None


def pr_check_line(line):
  """True when a command piece runs a long run the gate detaches."""
  return long_run_name(line) is not None


def pr_checks_command(argv):
  """True when this argv waits on a pull request's checks, so the discovery runs first."""
  line = argv[-1] if len(argv) > 2 and argv[0] in SHELL_BASENAMES else " ".join(argv)
  return long_run_name(line) == "pr-checks"


def detached_seconds(started_at):
  """Whole seconds since a detached run started, or None when the stamp will not parse."""
  try:
    started = datetime.fromisoformat(str(started_at))
    if started.tzinfo is None:
      started = started.replace(tzinfo=timezone.utc)
    return max(0, int((datetime.now(timezone.utc) - started).total_seconds()))
  except (TypeError, ValueError):
    return None


def write_detached_placeholder(
  state_dir, name, argv, pid=None, pid_started_at=None, task_id=None
):
  """Write the record a detached run carries while it runs, and return its path."""
  path = run_record_path(state_dir, name)
  record = {
    "name": name,
    "argv": list(argv),
    "exit": None,
    "seconds": None,
    "started_at": now(),
    "finished_at": None,
    "verdict": None,
    "tail": [],
    "detached": True,
    "announced": False,
  }
  if task_id:
    record["task_id"] = task_id
  if isinstance(pid, int) and not isinstance(pid, bool) and pid > 0:
    record["pid"] = pid
  if isinstance(pid_started_at, str) and pid_started_at:
    record["pid_started_at"] = pid_started_at
  write_run_record(path, record)
  return path


# The three answers the PR-check tick gives its hook.
# The hook allows lines that only mention wait words. A started wait ends the call clean. A failed start keeps refusal.
PR_CHECK_OTHER = 0
PR_CHECK_RUNS = 1
PR_CHECK_REFUSED = 2


# The harness wraps an agent line in `bash -l -c`.
# Remove only that login-shell wrapper before replay. Keep an agent-written `bash -c` command intact.
SHELL_BASENAMES = ("bash", "sh", "dash", "ksh", "zsh")


def agent_line(line):
  """The agent's own line, without the login-shell wrapper the harness puts in front."""
  words = (line or "").split(" ")
  head = words[0].rsplit("/", 1)[-1] if words else ""
  if head not in SHELL_BASENAMES or len(words) < 2:
    return line or ""
  first = words[1]
  if not first.startswith("-") or "l" not in first:
    return line or ""
  if "c" in first:
    rest = words[2:]
  elif words[2:3] == ["-c"]:
    rest = words[3:]
  else:
    return line or ""
  return " ".join(rest).strip() or (line or "")


def pr_check_wait(state_dir, line, command=None):
  """Detach the wait one line names, and say how the call must end.

  A wait that started returns `PR_CHECK_RUNS`: the hook ends its shell clean, because
  the work the line asked for already runs in the background. A failed start returns
  `PR_CHECK_REFUSED`, so the hook keeps the refusal. Any other line returns
  `PR_CHECK_OTHER` and runs untouched. Each message rides stderr.
  """
  line = agent_line(line)
  warning = worktree_warning(state_dir, "gate")
  if warning:
    print(warning, file=sys.stderr, flush=True)
    return PR_CHECK_REFUSED
  name = long_run_name(line)
  if not name:
    return PR_CHECK_OTHER
  if command is not None and line.strip() != command.strip():
    print(
      "RUN BLOCKED: automatic routing would replay a mixed shell line."
      f" Use `arena-preview route {name} -- <remaining command>`;"
      " do not repeat completed commands.",
      file=sys.stderr,
      flush=True,
    )
    return PR_CHECK_REFUSED
  if not detach_run(state_dir, name, ["bash", "-c", line]):
    print(DETACHED_BLOCK.format(name=name), file=sys.stderr, flush=True)
    return PR_CHECK_REFUSED
  print(DETACHED_NOTICE.format(name=name), file=sys.stderr, flush=True)
  return PR_CHECK_RUNS


def run_task_id(state_dir, selected=None):
  """Resolve an explicit task, or choose the current task for an automatic route."""
  try:
    store = Store(state_dir)
  except FileNotFoundError:
    if selected:
      raise ValueError(f"No task is stored under {selected}") from None
    return None
  if selected:
    try:
      task_id = store.resolve_id(selected)
    except ValueError as error:
      raise ValueError(f"Cannot link routed run: {error}") from None
    record = store.task_record(task_id)
    if record is None:
      raise ValueError(f"No task is stored under {selected}")
    if record.get("status") != "upcoming":
      raise ValueError(f"Task {task_id} is finished; a run needs an upcoming task")
    return task_id
  record = current_task(store.list_tasks())
  return record.get("id") if record else None


def detach_run(state_dir, name, argv, task_id=None):
  """Start one command detached under `name`, and say whether the spawn left.

  A detached child outlives the shell call that started it, so the run keeps going
  while the agent works on. The child executes the command through `route-run` and
  writes the finished record itself, so the verdict replays on a later call like any
  routed run. One live wait per name: a second line for the same family keeps the run
  and task link that already stand. An omitted task selects the current unblocked task.
  Tests set `ARENA_PREVIEW_DETACH_DRY` to write the record and skip the spawn.
  """
  path = run_record_path(state_dir, name)
  standing = json_record(path)
  if standing is not None:
    standing = reconcile_routed_record(path, standing)
    if standing.get("exit") is None:
      return True
  task_id = run_task_id(state_dir, task_id)
  if os.environ.get(DETACH_DRY_RUN):
    pid = os.getpid()
    write_detached_placeholder(
      state_dir, name, argv, pid, process_start_identity(pid), task_id
    )
    return True
  path = write_detached_placeholder(state_dir, name, argv, task_id=task_id)
  # A plain `bash -c` reads no login profile, so a child never meets the gate that started it.
  # The marker covers a shell that sources the gate anyway, and BASH_ENV leaves with it.
  child_env = {
    key: value
    for key, value in os.environ.items()
    if key not in ("BASH_ENV", DETACH_DRY_RUN, "ARENA_PREVIEW_ROUTE")
  }
  child_env["ARENA_PREVIEW_ROUTE"] = "1"
  try:
    child = subprocess.Popen(
      [
        sys.executable,
        str(Path(__file__).resolve()),
        "route-run",
        name,
        "--",
        *argv,
      ],
      stdin=subprocess.DEVNULL,
      stdout=subprocess.DEVNULL,
      stderr=subprocess.DEVNULL,
      env=child_env,
      start_new_session=True,
      close_fds=True,
    )
  except OSError:
    terminal_route_failure(path, json_record(path) or {}, ROUTE_START_FAILED)
    return False
  record = json_record(path)
  if record is not None and record.get("exit") is None:
    record["pid"] = child.pid
    started = process_start_identity(child.pid)
    if started:
      record["pid_started_at"] = started
    write_run_record(path, record)
  return True


def route_command(state_dir, name, argv, task_id=None):
  """Start a command detached under `name`, and return at once.

  This is the helper the trap uses for a long run it detects, and the call a line names
  when the trap could not start one. The verdict arrives on a later call, and `poll`
  ends when the run finishes.
  """
  if not RUN_NAME.fullmatch(name or ""):
    print(
      "arena-preview route: the name takes 1 to 64 letters, digits, dot, dash or"
      " underscore.",
      flush=True,
    )
    return 2
  if argv[:1] == ["--"]:
    argv = argv[1:]
  if not argv:
    print(
      "arena-preview route: name a command after --, for example: route gates -- make"
      " check",
      flush=True,
    )
    return 2
  if not detach_run(state_dir, name, argv, task_id=task_id):
    print(f"arena-preview route: the start of `{name}` failed.", flush=True)
    return 1
  print(
    f"routed {name}: background run. Verdict on later call. {WORKTREE_STEP}",
    file=sys.stderr,
    flush=True,
  )
  return 0


def run_log_report(state_dir, name):
  """Print one routed run's recorded status and its output tail.

  A second read of a run that has no verdict yet is a wait, not work, so the gate stops
  it: one read per verdict is what the gate allows, and the verdict keeps.
  """
  record = routed_record(state_dir, name)
  if record.get("exit") is None:
    stamp = str(record.get("started_at") or "")
    if run_read_stamp(state_dir, name) == stamp:
      print(
        f"WAIT BLOCKED: run {name} has no verdict yet. Take the next queued task, or"
        " read it on a later call. The verdict keeps, and `arena-preview poll` waits"
        " when the queue is empty.",
        file=sys.stderr,
        flush=True,
      )
      return 130
    mark_run_read(state_dir, name, record)
    elapsed = detached_seconds(record.get("started_at"))
    age = f" {elapsed}s" if elapsed is not None else ""
    print(f"run {name} running{age}")
    print(WORKTREE_STEP)
    return 0
  print(f"run {name} done: exit {record['exit']} {record.get('seconds')}s")
  for line in clean_run_tail(record.get("tail") or []):
    print(line)
  return 0


def poll_inbox(store, sleeper=None):
  if sleeper is None:
    sleeper = time.sleep
  deadline = time.monotonic() + POLL_WAIT_SECONDS
  listing = {"checked_at": None, "pending": []}
  # A full wait ends for messages, tasks, or failed branch checks. A heartbeat lights the page dot.
  print(
    f"poll waits up to {POLL_WAIT_SECONDS} s. Set the bash tool timeout to 1800 s.",
    file=sys.stderr,
    flush=True,
  )
  store.start_poll()
  # The monitor rechecks until a failure or the poll ends. It never holds the inbox path.
  failures = []
  stop_checks = threading.Event()
  threading.Thread(
    target=pr_check_watch,
    args=(failures, resolve_repo_root(), stop_checks),
    daemon=True,
  ).start()
  try:
    for index in range(POLL_MAX_LOOPS):
      if time.monotonic() >= deadline:
        break
      notice = store.take_interrupt()
      if notice:
        print(notice, flush=True)
        return 0
      listing = store.read(include_quiet=False)
      if listing["pending"]:
        full = store.read()
        print(format_read(full), flush=True)
        store.mark_seen([item["id"] for item in full["pending"]])
        store.mark_reports_agent_seen(
          [item.get("report_id") for item in full["pending"]]
        )
        return 0
      # A finished gate run ends this poll, so a separate closing poll still ends the turn.
      if run_notices(store.path.parent):
        print("DO NOT END TURN. POLL AGAIN.", flush=True)
        return 0
      # A failed check on the branch pull request ends the wait, so the turn fixes it now.
      if failures:
        print(
          f"PR CHECKS FAILED: {failures[0]}. Fix the failed check before the next push.",
          flush=True,
        )
        return 0
      open_tasks = [
        item
        for item in store.list_tasks()
        if item["status"] == "upcoming" and not item["blocked"]
      ]
      if open_tasks:
        listing["tasks"] = open_tasks
        names = ", ".join(item["id"] for item in open_tasks)
        # The early return continues the task. Process the still-up list before the next poll.
        # The line rides stderr and stdout both, so a turn that reads only stdout still meets the warning.
        continue_line = (
          f"CONTINUE: unblocked task {names}. Work it or block it; do not end the turn."
        )
        print(continue_line, flush=True)
        print(format_task_list(listing.get("tasks", [])), flush=True)
        return 0
      # A message, unblocked task, or live detached run outranks a skip so its verdict arrives first.
      # The skip stays armed until the run ends. It ends the turn only then.
      if skip_poll_ready(store):
        store.take_skip_poll()
        # The skip ends the turn here, so the header learns the turn is over.
        store.mark_turn_ended()
        # A one-shot skip prints on stdout, never as a repeated note.
        # On stderr it merged with gate hints and made agents poll again.
        print(
          "SKIP: owner pressed Skip poll. End the turn, no second poll.",
          flush=True,
        )
        print(format_read(listing), flush=True)
        return 0
      if index + 1 < POLL_MAX_LOOPS:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
          break
        sleeper(min(POLL_INTERVAL, remaining))
        store.stamp_polling()
  finally:
    stop_checks.set()
    store.clear_polling()
  # The wait ran its whole span with nothing to read: the turn ends here.
  store.mark_turn_ended()
  print("Poll returned with no new messages. End the turn.", flush=True)
  return 1


def parse_state_import(text):
  try:
    value = json.loads(text)
  except json.JSONDecodeError:
    value = [json.loads(line) for line in text.splitlines() if line.strip()]
  if isinstance(value, dict) and "notes" in value:
    notes = value["notes"]
    tasks = value.get("tasks", {})
    if tasks is None:
      tasks = {}
    answers = value.get("submissions", [])
    if isinstance(tasks, dict):
      tasks = tasks.get("upcoming", []) + tasks.get("finished", [])
    if not all(isinstance(items, list) for items in (notes, tasks, answers)):
      raise ValueError("State collections must be arrays")
    value = notes + tasks + answers
  elif isinstance(value, dict):
    value = [value]
  if not isinstance(value, list) or not all(isinstance(r, dict) for r in value):
    raise ValueError("Import JSON records or copied state")
  if not value:
    raise ValueError("Nothing to import")
  return value


AUTOSAVE_HISTORY = "userscript-autosave-history"
AUTOSAVE_RECEIPTS = "userscript-autosave-receipts"


def autosave_core_and_stamp(records):
  if not isinstance(records, list) or not all(isinstance(row, dict) for row in records):
    raise TypeError("Autosave core must be an array of records")
  if any(row.get("kind") == "userscript-autosave" for row in records):
    raise ValueError("Autosave core cannot contain history")
  with tempfile.TemporaryDirectory() as directory:
    checked = Store(directory, create=True)
    if records:
      checked.import_state(json.dumps(records))
    core, _ = checked.state_lines(checked.state()["notes"], checked.tasks() or {})
    stamp = checked.newest_stamp()
  # Renumber emitted tasks so a second canonical pass keeps every position and the digest.
  order = dict.fromkeys(TASK_STATUSES, 0)
  for row in core:
    status = row.get("status")
    if status in order and "title" in row and "markdown" not in row:
      order[status] += 1
      row["order"] = order[status]
  return core, stamp


def autosave_core(records):
  return autosave_core_and_stamp(records)[0]


def autosave_digest(core):
  encoded = json.dumps(core, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
  return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def autosave_scope_key(scope):
  if not isinstance(scope, dict) or set(scope) != {"repo", "branch"}:
    raise TypeError("Autosave scope needs repository and branch")
  if not all(isinstance(value, str) for value in scope.values()) or not scope["repo"]:
    raise ValueError("Invalid autosave scope")
  return json.dumps(scope, sort_keys=True)


def autosave_record(record):
  if (
    record.get("kind") != "userscript-autosave"
    or type(record.get("version")) is not int
    or record["version"] != 1
  ):
    raise ValueError("Unsupported autosave history version")
  if not isinstance(record.get("save_id"), str):
    raise TypeError("Autosave save ID must be a UUID string")
  if set(record) - {
    "kind",
    "version",
    "save_id",
    "scope",
    "digest",
    "core",
    "stamp",
    "confirmed_at",
    "receipts",
  }:
    raise ValueError("Unsupported autosave history fields")
  uuid.UUID(record["save_id"])
  autosave_scope_key(record["scope"])
  core = autosave_core(record["core"])
  if autosave_digest(core) != record.get("digest"):
    raise ValueError("Autosave history digest does not match")
  if record.get("stamp") is not None and import_stamp(record["stamp"]) is None:
    raise ValueError("Autosave history stamp is invalid")
  if import_stamp(record.get("confirmed_at")) is None:
    raise ValueError("Autosave history needs a confirmation time")
  receipts = record.get("receipts", {})
  if not isinstance(receipts, dict):
    raise TypeError("Autosave receipts must be an object")
  for save_id, digest in receipts.items():
    uuid.UUID(save_id)
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
      raise ValueError("Invalid autosave receipt digest")
  if record["save_id"] in receipts and receipts[record["save_id"]] != record["digest"]:
    raise ValueError("Autosave receipt conflicts with its saved state")
  return {**record, "core": core}


def verify_publication(store, report_id, revision, count):
  from http.client import HTTPConnection, HTTPException

  failure = "Publication verification failed. Check the preview before retrying."
  try:
    with closing(
      HTTPConnection("127.0.0.1", int(store.meta_value("port")), timeout=15)
    ) as client:
      documents = []
      for path in ("/api/state", f"/api/reports/{report_id}/html"):
        client.request("GET", path)
        response = client.getresponse()
        if response.status != 200:
          raise ValueError(f"Publication verification failed: HTTP {response.status}.")
        documents.append(json.loads(response.read()))
  except (OSError, HTTPException, UnicodeError, json.JSONDecodeError):
    raise ValueError(failure) from None
  state, rendered = documents
  if not isinstance(state, dict) or not isinstance(state.get("reports"), list):
    raise TypeError(failure)
  matches = [
    row
    for row in state["reports"]
    if isinstance(row, dict) and row.get("id") == report_id
  ]
  if (
    len(matches) != 1
    or matches[0].get("updated_at") != clip_stamp(revision)
    or not isinstance(rendered, dict)
    or rendered.get("revision") != revision
    or type(rendered.get("fields")) is not int
    or rendered["fields"] != count
    or not isinstance(rendered.get("html"), str)
  ):
    raise ValueError(failure)


def task_steps(details):
  """One step per line: a line break inside one argument becomes a break between steps."""
  steps = []
  for item in details or ():
    steps.extend(part.strip() for part in str(item).splitlines())
  return [step for step in steps if step]


def check_task_steps(details):
  """Refuse a wall of text: each detail is one step on one short line."""
  for step in details or ():
    if len(step) > TASK_STEP_MAX:
      raise ValueError(
        "A task detail is one step per line,"
        f" {TASK_STEP_MAX} characters or fewer; this line runs {len(step)}."
        " Split it and repeat --details"
      )


def check_task(task_id, title, details):
  "Check task fields before a write."
  if not TASK_ID.match(task_id or ""):
    raise ValueError(
      "A task ID is 1-64 characters of lowercase letters, digits and hyphens,"
      " and starts with a letter or digit"
    )
  # A note ID passes the shape check, so it needs its own refusal: a task named after the note it
  # answers puts one ID on two things, and the agent that reaches for the note ID reads the fix here.
  if NOTE_ID.match(task_id or ""):
    raise ValueError(
      "That ID is a note ID. A task ID names the job: give the task a proper name,"
      " like fix-the-widget"
    )
  if title is not None and len(title) > MAX_TASK_TITLE:
    raise ValueError(f"A task title must be {MAX_TASK_TITLE} characters or fewer")
  if len(details or ()) > MAX_TASK_DETAILS:
    raise ValueError(f"A task carries at most {MAX_TASK_DETAILS} details")
  for detail in details or ():
    if len(detail) > MAX_TASK_DETAIL:
      raise ValueError(f"A task detail must be {MAX_TASK_DETAIL} characters or fewer")


# An image the agent sized: `![alt](src =320x200)`, or `=320x` for a scaled height.
SIZED_IMAGE = re.compile(r"!\[([^\]\n]*)\]\((\S+?)\s+=(\d+)x(\d*)\)")


def hold_out(markdown, pattern, build, slug):
  """Replace each match with a placeholder and return the text and stored HTML.

  Preserve allowlisted list markup and sized images during rendering, then restore their HTML.
  `build` returns HTML for a match, or None to leave it unchanged."""
  held = []

  def hold(match):
    built = build(match)
    if built is None:
      return match.group(0)
    held.append(built)
    return f" preview{slug}{len(held) - 1}x "

  return re.sub(pattern, hold, markdown), held


def put_back(rendered, held, slug):
  """Swap each placeholder for the HTML it stood in for."""
  return re.sub(
    rf"preview{slug}(\d+)x", lambda match: held[int(match.group(1))], rendered
  )


def render_report_block(markdown):
  """Render a markdown chunk, letting allowlisted list markup through the renderer.

  Bare ul, ol and li tags pass anywhere when they form one contiguous block of tags and padding. The text around
  and between them renders as markdown (a `<li>`'s text renders inline, so **bold** survives). A tag with an
  attribute, or any other tag, keeps escaping like every other HTML."""
  # A maximal run of list tags and optional whitespace is one holdout.
  # Keep it inline in table cells. Surrounding spaces let Markdown end adjacent paragraphs.
  tagged, held = hold_out(
    markdown,
    r"(?:\s*(?:</?(?:ul|ol|li)>)\s*){2,}",
    lambda match: match.group(0).strip().lower(),
    "listtag",
  )
  out = put_back(render(tagged), held, "listtag")
  # Block tags kept inline sit in the paragraph their text formed: break the paragraph
  # at each block boundary so the list renders as a list, and drop the empty pairs.
  out = re.sub(r"<p>(<(?:ul|ol)>)", r"\1", out)
  out = re.sub(r"(</(?:ul|ol)>)</p>", r"\1", out)
  return out


def render_report(markdown):
  blocks, questions = parse_fields(markdown)
  parts = []
  for kind, item in blocks:
    if kind == "markdown":
      if item.strip():
        parts.append(render_report_block(item))
    else:
      parts.append(field_html(item))
  return "".join(parts), questions


class ReportChanged(ValueError):
  pass


class FetchChanged(ValueError):
  pass


# A report change can conflict with a new answer, its unseen acknowledgement, or a fresh view.
class ReportHeld(ValueError):
  pass


def format_report_state(rows):
  """Render report-state rows: publication, owner view stamp, answer visibility."""
  lines = []
  for row in rows:
    lines.append(f"{row['id']} {row['title']}")
    lines.append(f"  published: {local_stamp(row['published_at']) or 'never'}")
    lines.append(f"  updated: {local_stamp(row['updated_at'])}")
    lines.append(f"  stale: {'yes' if row['stale'] else 'no'}")
    lines.append(f"  viewed: {local_stamp(row['viewed_at']) or 'never'}")
    if not row["answers"]:
      lines.append("  answers: none")
    for answer in row["answers"]:
      lines.append(
        f"  answers: {answer['id']} acknowledged"
        f" {'yes' if answer['acknowledged'] else 'no'},"
        f" agent-seen {'yes' if answer['seen'] else 'no'}"
      )
  return "\n".join(lines) + ("\n" if lines else "")


def sqlite_api():
  """Import sqlite3 on first use and return it.

  A gate tick reads the command line and never opens the store, so the driver waits for
  the first state call. Every sqlite3 reference goes through here, so an error path keeps
  working whichever command raised it.
  """
  global sqlite3
  if sqlite3 is None:
    import sqlite3

  return sqlite3


class Store:
  def __init__(self, directory, create=False, save_path=None):
    directory = Path(directory).resolve()
    self.path = directory / "state.sqlite3"
    # The save file is not the database, and it lands beside it by default: one directory the installer ignores
    # through core.excludesFile carries both, and a sandbox restore keeps a path the repository does not ignore.
    self.save_path = Path(save_path) if save_path else self.path.parent / SAVED_STATE
    existed = self.path.is_file()
    if not create and not existed:
      raise FileNotFoundError(
        f"Inbox missing: {self.path}. The sandbox may have been reset, so follow the restore "
        f"routine: run scripts/install.sh from the repository root, start `arena-preview serve --port 8000` "
        f"with the start_process tool, then `arena-preview read`."
      )
    if create and not existed:
      directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    with closing(self.connect()) as db, db:
      db.executescript("""
        CREATE TABLE IF NOT EXISTS notes (
          seq INTEGER PRIMARY KEY, id TEXT UNIQUE NOT NULL,
          text TEXT NOT NULL, at TEXT NOT NULL, acknowledged_at TEXT,
          ack_kind TEXT, ack_text TEXT, seen_at TEXT, replies TEXT,
          ack_edited_seen_count INTEGER NOT NULL DEFAULT 0,
          quiet INTEGER NOT NULL DEFAULT 0,
          blocking INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS reports (
          id TEXT PRIMARY KEY, title TEXT NOT NULL,
          markdown TEXT NOT NULL, updated_at TEXT NOT NULL, published_at TEXT,
          seq INTEGER, seen_at TEXT,
          ever_seen INTEGER NOT NULL DEFAULT 0, agent_seen_at TEXT,
          ack_seen_at TEXT, viewed_at TEXT
        );
        CREATE TABLE IF NOT EXISTS submissions (
          seq INTEGER PRIMARY KEY, id TEXT UNIQUE NOT NULL,
          report_id TEXT NOT NULL, text TEXT NOT NULL, at TEXT NOT NULL,
          acknowledged_at TEXT, ack_kind TEXT, ack_text TEXT, seen_at TEXT, replies TEXT,
          ack_edited_seen_count INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS uploads (
          seq INTEGER PRIMARY KEY, id TEXT UNIQUE NOT NULL, note_id TEXT,
          name TEXT NOT NULL, type TEXT NOT NULL, size INTEGER NOT NULL,
          sha256 TEXT NOT NULL, file TEXT NOT NULL, at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS fetch_jobs (
          seq INTEGER PRIMARY KEY, id TEXT UNIQUE NOT NULL,
          url TEXT NOT NULL, allow_proxy INTEGER NOT NULL CHECK (allow_proxy IN (0, 1)),
          status TEXT NOT NULL CHECK (status IN ('queued', 'fetching', 'saved', 'failed')),
          approval TEXT NOT NULL DEFAULT 'approved'
            CHECK (approval IN ('pending', 'approved', 'denied')),
          claim TEXT, lease_until TEXT, error TEXT, source TEXT,
          name TEXT, type TEXT, size INTEGER, sha256 TEXT, file TEXT,
          at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS tasks (
          id TEXT PRIMARY KEY,
          title TEXT NOT NULL,
          details TEXT NOT NULL DEFAULT '[]',
          status TEXT NOT NULL DEFAULT 'upcoming'
            CHECK (status IN ('upcoming', 'finished')),
          position INTEGER NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          completed_at TEXT,
          blocked INTEGER NOT NULL DEFAULT 0,
          type TEXT NOT NULL DEFAULT 'misc'
        );
      """)
      columns = {row["name"] for row in db.execute("PRAGMA table_info(notes)")}
      for column in (
        "ack_kind",
        "ack_text",
        "ack_edited_at",
        "seen_at",
        "task_id",
        "replies",
      ):
        if column not in columns:
          db.execute(f"ALTER TABLE notes ADD COLUMN {column} TEXT")
      if "ack_edited_seen_count" not in columns:
        db.execute(
          "ALTER TABLE notes ADD COLUMN ack_edited_seen_count INTEGER NOT NULL DEFAULT 0"
        )
      if "quiet" not in columns:
        # A quiet note carries information the agent needs when it looks, and it
        # never wakes a poll. The userscript posts the key this way.
        db.execute("ALTER TABLE notes ADD COLUMN quiet INTEGER NOT NULL DEFAULT 0")
      if "blocking" not in columns:
        db.execute("ALTER TABLE notes ADD COLUMN blocking INTEGER NOT NULL DEFAULT 1")
        # Every pre-feature quiet row is informational. Hidden read-set checkpoints
        # are the first quiet rows that can block, so no legacy row belongs to that class.
        db.execute("UPDATE notes SET blocking = CASE WHEN quiet = 1 THEN 0 ELSE 1 END")
      if "origin" in columns:
        # The author tag is gone from the note schema. Drop a column a restore might
        # still carry so SELECT * never resurfaces it on the state surface.
        db.execute("ALTER TABLE notes DROP COLUMN origin")
        columns.discard("origin")
      if "seen_at" not in columns:
        db.execute(
          "UPDATE notes SET seen_at = acknowledged_at"
          " WHERE seen_at IS NULL AND acknowledged_at IS NOT NULL"
        )
      columns = {row["name"] for row in db.execute("PRAGMA table_info(tasks)")}
      if "blocked" not in columns:
        db.execute("ALTER TABLE tasks ADD COLUMN blocked INTEGER NOT NULL DEFAULT 0")
      if "report_id" not in columns:
        db.execute("ALTER TABLE tasks ADD COLUMN report_id TEXT")
      if "completed_at" not in columns:
        db.execute("ALTER TABLE tasks ADD COLUMN completed_at TEXT")
      if "type" not in columns:
        db.execute("ALTER TABLE tasks ADD COLUMN type TEXT NOT NULL DEFAULT 'misc'")
      db.execute(
        "UPDATE tasks SET completed_at = updated_at"
        " WHERE status = 'finished' AND completed_at IS NULL"
      )
      columns = {row["name"] for row in db.execute("PRAGMA table_info(submissions)")}
      if "ack_edited_at" not in columns:
        db.execute("ALTER TABLE submissions ADD COLUMN ack_edited_at TEXT")
      if "seen_at" not in columns:
        db.execute("ALTER TABLE submissions ADD COLUMN seen_at TEXT")
      if "task_id" not in columns:
        db.execute("ALTER TABLE submissions ADD COLUMN task_id TEXT")
      if "replies" not in columns:
        db.execute("ALTER TABLE submissions ADD COLUMN replies TEXT")
      if "ack_edited_seen_count" not in columns:
        db.execute(
          "ALTER TABLE submissions ADD COLUMN ack_edited_seen_count INTEGER NOT NULL DEFAULT 0"
        )
      columns = {row["name"] for row in db.execute("PRAGMA table_info(reports)")}
      if "seen_at" not in columns:
        db.execute("ALTER TABLE reports ADD COLUMN seen_at TEXT")
        db.execute(
          "UPDATE submissions SET seen_at = acknowledged_at"
          " WHERE seen_at IS NULL AND acknowledged_at IS NOT NULL"
        )
      columns = {row["name"] for row in db.execute("PRAGMA table_info(reports)")}
      if "seq" not in columns:
        db.execute("ALTER TABLE reports ADD COLUMN seq INTEGER")
        db.execute("UPDATE reports SET seq = rowid WHERE seq IS NULL")
      if "ever_seen" not in columns:
        db.execute(
          "ALTER TABLE reports ADD COLUMN ever_seen INTEGER NOT NULL DEFAULT 0"
        )
        db.execute("UPDATE reports SET ever_seen = 1 WHERE seen_at IS NOT NULL")
      if "agent_seen_at" not in columns:
        db.execute("ALTER TABLE reports ADD COLUMN agent_seen_at TEXT")
      if "ack_seen_at" not in columns:
        # The ack mark is about the answer, not the report text: the owner clears it by
        # opening the report, so its stamp moves where seen_at keeps the first read.
        db.execute("ALTER TABLE reports ADD COLUMN ack_seen_at TEXT")
      if "viewed_at" not in columns:
        # The view stamp moves on every look, because the unpublish guard reads how
        # fresh the last one is rather than when the report was first read.
        db.execute("ALTER TABLE reports ADD COLUMN viewed_at TEXT")
      columns = {row["name"] for row in db.execute("PRAGMA table_info(reports)")}
      if "published_at" not in columns:
        # A store from before this column keeps no first-publish stamp, so the date the
        # owner sees starts at the row it already had: updated_at of the last republish.
        db.execute("ALTER TABLE reports ADD COLUMN published_at TEXT")
        db.execute(
          "UPDATE reports SET published_at = updated_at WHERE published_at IS NULL"
        )
      columns = {row["name"] for row in db.execute("PRAGMA table_info(uploads)")}
      if "note_id" not in columns:
        db.execute("ALTER TABLE uploads ADD COLUMN note_id TEXT")
        # Older uploads posted one notification note with the upload's ID. Keep those links.
        db.execute("UPDATE uploads SET note_id = id WHERE note_id IS NULL")
      db.execute("CREATE INDEX IF NOT EXISTS uploads_note_id ON uploads(note_id)")
      # Keep older owner-entered jobs claimable after this migration.
      columns = {row["name"] for row in db.execute("PRAGMA table_info(fetch_jobs)")}
      if "approval" not in columns:
        db.execute(
          "ALTER TABLE fetch_jobs ADD COLUMN approval TEXT NOT NULL DEFAULT 'approved'"
          " CHECK (approval IN ('pending', 'approved', 'denied'))"
        )
      if "origin" not in columns:
        db.execute(
          "ALTER TABLE fetch_jobs ADD COLUMN origin TEXT NOT NULL DEFAULT 'agent'"
        )
    if not existed:
      self.path.chmod(0o600)

  def id_matches(self, token):
    """Every record whose ID equals the token or starts with it, across all four kinds.

    The token arrives bare or wrapped in the ticks `read` prints, and both reach one record.
    """
    token = bare_id(token)
    like = f"{token}%"
    found = []
    with closing(self.connect()) as db:
      for table, label in (
        ("notes", "note"),
        ("submissions", "answer"),
        ("reports", "report"),
        ("tasks", "task"),
      ):
        rows = db.execute(
          f"SELECT * FROM {table} WHERE id = ? OR id LIKE ?", (token, like)
        ).fetchall()
        found.extend((label, dict(row)) for row in rows)
    return found

  def resolve_id(self, token):
    """One full ID for a full ID or a prefix.

    A prefix that names two records is a named conflict, and the error lists every match
    with its kind and title, so the caller can see which full ID to give instead.
    """
    token = bare_id(token)
    matches = self.id_matches(token)
    exact = [item for item in matches if item[1]["id"] == token]
    if len(exact) == 1:
      return token
    if len(matches) == 1:
      return matches[0][1]["id"]
    if not matches:
      raise ValueError(f"No note, answer, report or task holds the ID {token}")
    listed = "; ".join(
      f"{kind} {record['id']}"
      f" {(record.get('title') or record.get('text') or '')[:40]!r}"
      for kind, record in matches
    )
    raise ValueError(
      f"{token} matches {len(matches)} records: {listed}. Give the full ID of one"
    )

  def list_note_ids(self, page, page_size):
    """List stored note IDs without note text or receipt changes."""
    if page < 1 or not 1 <= page_size <= 100:
      raise ValueError("Page must be at least 1; page size must be 1 to 100")
    with closing(self.connect()) as db:
      db.execute("BEGIN")
      total = db.execute("SELECT count(*) FROM notes").fetchone()[0]
      offset = (page - 1) * page_size
      ids = []
      if offset < total:
        ids = [
          row[0]
          for row in db.execute(
            "SELECT id FROM notes ORDER BY at DESC, seq DESC LIMIT ? OFFSET ?",
            (page_size, offset),
          )
        ]
    return ids, total

  def notes_matching(self, token):
    """The reread takes the short or the full ID, and a short ID that matches
    several notes prints every match, newest first, so a saved note is never
    out of reach after its ack.
    """
    with closing(self.connect()) as db:
      return [
        message_row(row)
        for row in db.execute(
          "SELECT * FROM notes WHERE id = ? OR id LIKE ? ORDER BY at DESC",
          (token, f"{token}%"),
        ).fetchall()
      ]

  def connect(self):
    db = sqlite_api().connect(self.path, timeout=5)
    db.row_factory = sqlite_api().Row
    return db

  def note(
    self,
    note_id,
    text,
    at=None,
    acknowledged_at=None,
    ack_kind=None,
    ack_text=None,
    seen_at=None,
    task_id=None,
    ack_edited_at=None,
    autosave=True,
    shared=None,
    replies=None,
    ack_edited_seen_count=None,
    quiet=False,
    blocking=None,
  ):
    """Store a message with its supplied receipt and read state. Never replace a restored receipt stamp. Leave
    existing IDs unchanged so imports stay idempotent."""
    identifier(note_id)
    owner_text(text)
    receipt = restore_receipt(acknowledged_at, ack_kind, ack_text, ack_edited_at)
    more = restore_replies(replies, receipt[0])
    seen_reply_count = restore_reply_seen_count(ack_edited_seen_count, more)
    seen = when(seen_at) if seen_at is not None else None
    blocking = not quiet if blocking is None else bool(blocking)
    with self.transaction(shared, autosave=autosave) as db:
      if shared is None:
        db.execute("BEGIN IMMEDIATE")
      existing = db.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
      if existing:
        if existing["text"] != text:
          raise ValueError("This message ID already belongs to different text")
        return message_row(existing)
      db.execute(
        "INSERT INTO notes"
        " (id, text, at, acknowledged_at, ack_kind, ack_text, ack_edited_at, seen_at, task_id,"
        " replies, ack_edited_seen_count, quiet, blocking)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
          note_id,
          text,
          at or now(),
          *receipt,
          seen,
          task_id,
          more,
          seen_reply_count,
          1 if quiet else 0,
          1 if blocking else 0,
        ),
      )
      if not quiet:
        reset_poll_count(db)
      clear_skip_poll(db)
      return message_row(
        db.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
      )

  def pending_read_set_note(self):
    """Return the one outstanding hidden read-set checkpoint, if any."""
    with closing(self.connect()) as db:
      row = db.execute(
        "SELECT * FROM notes"
        " WHERE quiet = 1 AND blocking = 1 AND acknowledged_at IS NULL"
        " ORDER BY at, seq LIMIT 1"
      ).fetchone()
    return message_row(row) if row else None

  def schedule_read_set_note(self, moment=None, root=None):
    """Atomically create at most one checkpoint for the current 20-minute slot."""
    slot = read_set_slot(moment)
    paths = read_set_paths(root)
    with closing(self.connect()) as db, db:
      db.execute("BEGIN IMMEDIATE")
      heartbeat = db.execute(
        "SELECT value FROM meta WHERE key = ?", (POLLING_META,)
      ).fetchone()
      age = seconds_since(heartbeat["value"] if heartbeat else None)
      if age is not None and 0 <= age < POLLING_FRESH_SECONDS:
        return None
      row = db.execute(
        "SELECT * FROM notes"
        " WHERE quiet = 1 AND blocking = 1 AND acknowledged_at IS NULL"
        " ORDER BY at, seq LIMIT 1"
      ).fetchone()
      if row:
        return message_row(row)
      recorded = db.execute(
        "SELECT value FROM meta WHERE key = ?", (READ_SET_SLOT_META,)
      ).fetchone()
      if recorded and recorded["value"] == slot:
        return None
      for _ in range(MINT_ATTEMPTS):
        note_id = new_id()
        if not any(
          db.execute(f"SELECT 1 FROM {table} WHERE id = ?", (note_id,)).fetchone()
          for table in ("notes", "submissions", "uploads", "reports", "tasks")
        ):
          break
      else:
        raise RuntimeError(
          "The state holds no free six-character ID for a read-set note"
        )
      listed = "\n".join(f"- `{path}`" for path in paths)
      text = (
        f"Read-set checkpoint for local slot {slot}. Read every listed path in full"
        " with the read tool, then acknowledge this note.\n"
        f"{listed}"
      )
      record = self.note(
        note_id,
        text,
        shared=db,
        autosave=False,
        quiet=True,
        blocking=True,
      )
      db.execute(
        "INSERT INTO meta(key, value) VALUES (?, ?)"
        " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (READ_SET_SLOT_META, slot),
      )
    self.autosave()
    return record

  def submission(
    self,
    submission_id,
    report_id,
    text,
    at=None,
    acknowledged_at=None,
    ack_kind=None,
    ack_text=None,
    seen_at=None,
    task_id=None,
    ack_edited_at=None,
    shared=None,
    autosave=True,
    replies=None,
    ack_edited_seen_count=None,
  ):
    """Store report answers separately from messages. Restore receipts and read state without new stamps. Leave
    existing IDs unchanged."""
    identifier(submission_id)
    identifier(report_id)
    submission_text(text)
    receipt = restore_receipt(acknowledged_at, ack_kind, ack_text, ack_edited_at)
    more = restore_replies(replies, receipt[0])
    seen_reply_count = restore_reply_seen_count(ack_edited_seen_count, more)
    with self.transaction(shared, autosave=autosave) as db:
      if shared is None:
        db.execute("BEGIN IMMEDIATE")
      existing = db.execute(
        "SELECT * FROM submissions WHERE id = ?", (submission_id,)
      ).fetchone()
      if existing:
        if existing["text"] != text:
          raise ValueError("This message ID already belongs to different text")
        self.release_report_tasks(db, report_id)
        return message_row(existing)
      db.execute(
        "INSERT INTO submissions"
        " (id, report_id, text, at, acknowledged_at, ack_kind, ack_text, ack_edited_at, seen_at,"
        " task_id, replies, ack_edited_seen_count) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
          submission_id,
          report_id,
          text,
          at or now(),
          *receipt,
          when(seen_at) if seen_at is not None else None,
          task_id,
          more,
          seen_reply_count,
        ),
      )
      self.release_report_tasks(db, report_id)
      reset_poll_count(db)
      clear_skip_poll(db)
      return message_row(
        db.execute(
          "SELECT * FROM submissions WHERE id = ?", (submission_id,)
        ).fetchone()
      )

  def submissions(self):
    with closing(self.connect()) as db:
      return [
        message_row(row)
        for row in db.execute("SELECT * FROM submissions ORDER BY at, seq")
      ]

  def report_sources(self):
    """Every report source, oldest first, for the save file."""
    with closing(self.connect()) as db:
      return [
        dict(row)
        for row in db.execute(
          "SELECT id, title, markdown, published_at, seen_at FROM reports ORDER BY seq, id"
        )
      ]

  def state(self):
    """Return page state with second-precision stamps. The save file and shift-click copy restore this shape. Keep
    full stamps in the database."""
    tasks = self.tasks()
    with closing(self.connect()) as db:
      meta = dict(db.execute("SELECT key, value FROM meta"))
      notes = [
        message_row(row) for row in db.execute("SELECT * FROM notes ORDER BY at, seq")
      ]
      reports = [
        dict(row)
        for row in db.execute(
          "SELECT id, title, updated_at, published_at, seq, seen_at, ever_seen,"
          " agent_seen_at, ack_seen_at, markdown, EXISTS("
          "SELECT 1 FROM submissions WHERE report_id = reports.id) AS answered "
          "FROM reports ORDER BY seq, id"
        )
      ]
      latest_answers = {
        row["report_id"]: row
        for row in db.execute("SELECT * FROM submissions ORDER BY seq")
      }
      for report in reports:
        answered = report.pop("answered")
        latest = latest_answers.get(report["id"])
        report["acknowledgements"] = [
          message_row(row)
          for row in db.execute(
            "SELECT * FROM submissions WHERE report_id = ? AND acknowledged_at IS NOT NULL ORDER BY seq",
            (report["id"],),
          )
        ]
        for ack in report["acknowledgements"]:
          ack.pop("text", None)
        report["latest_answer_id"] = latest["id"] if latest else None
        report["latest_answer_at"] = clip_stamp(latest["at"]) if latest else None
        report["latest_answer_acknowledged_at"] = (
          clip_stamp(latest["acknowledged_at"]) if latest else None
        )
        agent_seen = report.pop("agent_seen_at", None)
        report["agent_seen_at"] = (
          clip_stamp(agent_seen)
          if latest is not None and at_or_after(agent_seen, latest["at"])
          else None
        )
        try:
          report["needs_answer"] = (
            bool(parse_fields(report.pop("markdown"))[1]) and not answered
          )
        except ValueError as error:
          report["needs_answer"] = True
          report["field_error"] = str(error)
      uploads = self.uploads()
      by_note = {}
      for item in uploads:
        by_note.setdefault(item["note_id"], []).append(item)
      for note in notes:
        add_note_attachments(note, by_note.get(note["id"], []))
      fetch_jobs = self.fetch_jobs()
      for item in notes + reports + uploads + fetch_jobs:
        for key in (
          "at",
          "acknowledged_at",
          "ack_edited_at",
          "seen_at",
          "ack_seen_at",
          "updated_at",
          "published_at",
        ):
          if key in item:
            item[key] = clip_stamp(item[key])
        for reply in item.get("replies") or []:
          reply["at"] = clip_stamp(reply["at"])
      if tasks is not None:
        for item in tasks["finished"] + tasks["upcoming"]:
          item["updated_at"] = clip_stamp(item["updated_at"])
        tasks["updated_at"] = clip_stamp(tasks["updated_at"])
      polling = self.polling()
      return {
        "notes": notes,
        "reports": reports,
        "tasks": tasks,
        "uploads": uploads,
        "fetch_jobs": fetch_jobs,
        "workspace": workspace_usage(),
        "last_check": clip_stamp(meta.get("last_check")),
        "polling": polling,
        "waiting_for_gates": polling and bool(live_runs(self.path.parent)),
        # The wait start rides the heartbeat, so a stale stamp never shows.
        "polling_since": (clip_stamp(meta.get(POLL_SINCE_META)) if polling else None),
        # The page paints its Skip poll button from this stamp until a poll consumes it.
        "skip_poll": clip_stamp(meta.get(SKIP_POLL_META)),
        "agent_interrupt_pending": bool(meta.get(AGENT_INTERRUPT_META)),
        # The message log header names the bash calls since the owner's last message.
        "calls_since_message": meta_number(db, POLLS_SINCE_MESSAGE),
        # The Downloads tab shows the key the userscript holds.
        "agent_key": self.agent_key(),
        # The header turns amber when this stamp ages, so a stale preview shows itself.
        "agent_seen_at": clip_stamp(meta.get(AGENT_SEEN_META)),
        # The header suppresses the long call text after this mark and turns amber past the
        # quiet window, since silence after a returned poll is not a running call.
        "turn_ended_at": clip_stamp(meta.get(TURN_ENDED_META)),
        # The hook stamps this after every bash call. The long call text holds only while
        # the last seen stamp is newer, so a finished call never reads as running.
        "agent_call_ended_at": clip_stamp(meta.get(AGENT_CALL_ENDED_META)),
      }

  def tasks(self):
    """Return ordered task records for both page divs. Return None when no task exists.

    Each task carries its linked answers for the page's read-only block: every answer of its
    report plus any answer that names the task, one entry per submission ID. A task with no
    link keeps the shape it had before the block existed."""
    with closing(self.connect()) as db:
      rows = db.execute(
        f"SELECT {TASK_COLUMNS} FROM tasks ORDER BY {TASK_ORDER}"
      ).fetchall()
      records = [task_row(row) for row in rows]
      if not records:
        return None
      link_task_answers(db, records)
    link_task_runs(records, self.path.parent)
    return {
      "finished": [item for item in records if item["status"] == "finished"],
      "upcoming": [item for item in records if item["status"] == "upcoming"],
      "updated_at": max(item["updated_at"] for item in records),
    }

  def list_tasks(self):
    """Every task with report answers and derived live-run state."""
    with closing(self.connect()) as db:
      rows = db.execute(
        f"SELECT {TASK_COLUMNS} FROM tasks ORDER BY {TASK_ORDER}"
      ).fetchall()
      records = link_task_answers(db, [task_row(row) for row in rows])
    return link_task_runs(records, self.path.parent)

  def task_record(self, task_id):
    """Read one task with derived live-run state, or None when no row holds its ID."""
    with closing(self.connect()) as db:
      row = db.execute(
        f"SELECT {TASK_COLUMNS} FROM tasks WHERE id = ?", (task_id,)
      ).fetchone()
    if row is None:
      return None
    return link_task_runs([task_row(row)], self.path.parent)[0]

  def free_id(self):
    """A six-character ID no stored row holds, so a server mint never lands on a record.

    Six characters name a note whole, and the mint shares that space with every stored row. A clash re-mints. A
    state that fills the space refuses instead of looping."""
    tables = ("notes", "submissions", "uploads", "reports", "tasks")
    with closing(self.connect()) as db:
      for _ in range(MINT_ATTEMPTS):
        candidate = new_id()
        if not any(
          db.execute(f"SELECT 1 FROM {table} WHERE id = ?", (candidate,)).fetchone()
          for table in tables
        ):
          return candidate
    raise RuntimeError("The state holds no free six-character ID for a new record")

  @contextmanager
  def transaction(self, db=None, autosave=True):
    """Use one transaction for the work. Reuse a supplied transaction so imports can remove and write atomically.
    Refresh the save file after an outer commit unless autosave is false."""
    if db is not None:
      yield db
      return
    with closing(self.connect()) as own, own:
      yield own
    if autosave:
      self.autosave()

  def write_task(
    self,
    task_id,
    title=None,
    details=None,
    status=None,
    order=None,
    blocked=None,
    report_id=None,
    completed_at=None,
    task_type=None,
    shared=None,
    append_details=False,
    restoring=False,
  ):
    """Insert or update a task and return it. Keep omitted title and detail values. Use a supplied transaction so
    imports remain atomic."""
    details = [str(item) for item in details if str(item).strip()] if details else None
    if append_details and not details:
      raise ValueError("Appending requires at least one task detail")
    check_task(task_id, title, details)
    if status is not None and status not in TASK_STATUSES:
      raise ValueError(f"A task is either {' or '.join(TASK_STATUSES)}")
    allowed_types = TASK_TYPES + TASK_LEGACY_TYPES if restoring else TASK_TYPES
    if task_type is not None and task_type not in allowed_types:
      raise ValueError(f"A task type is one of {', '.join(allowed_types)}")
    stamp = now()
    with self.transaction(shared) as db:
      if append_details and not db.in_transaction:
        db.execute("BEGIN IMMEDIATE")
      row = db.execute(
        f"SELECT {TASK_COLUMNS} FROM tasks WHERE id = ?", (task_id,)
      ).fetchone()
      stored = task_row(row) if row else None
      if stored is None and title is None:
        raise ValueError("A new task needs a title")
      if stored is None:
        self.refuse_shared_id(db, "tasks", "reports", task_id)
      title = title if title is not None else stored["title"]
      if append_details:
        details = (stored["details"] if stored else []) + details
        check_task(task_id, title, details)
      elif details is None:
        details = stored["details"] if stored else []
      if not details:
        # A task with no detail is a title alone, and the queue works from its steps.
        raise ValueError("A task needs at least one detail")
      status = status or (stored["status"] if stored else "upcoming")
      if status == "finished":
        if stored and stored["status"] == "finished":
          completed_at = stored["completed_at"]
        elif completed_at is None:
          completed_at = stamp
      else:
        completed_at = None
      if blocked is None:
        blocked = stored["blocked"] if stored else False
      report_wait = report_id is not None
      if report_id is None:
        report_id = stored.get("report_id") if stored else None
      if task_type is None:
        if stored is None and not restoring:
          raise ValueError("A new task needs an explicit type")
        task_type = (stored.get("type") if stored else None) or TASK_MISC
      if report_id:
        identifier(report_id)
      if (
        report_wait and report_id and blocked and self.report_has_answers(db, report_id)
      ):
        # The wait is over before it starts when the report already has its answer.
        blocked = False
      if (
        report_id
        and blocked
        and (
          not stored or not stored["blocked"] or stored.get("report_id") != report_id
        )
      ):
        report = db.execute(
          "SELECT markdown FROM reports WHERE id = ?", (report_id,)
        ).fetchone()
        if report is not None and not parse_fields(report["markdown"])[1]:
          raise ValueError("A blocked task needs a report with answer fields")
      if status == "finished":
        guard_task_runs(self.path.parent, task_id, "finish task")
      if status == "finished" and blocked:
        raise ValueError(
          f"Task {task_id} is blocked; clear the report wait with --unblocked first"
        )
      siblings = [
        task_row(item)
        for item in db.execute(
          f"SELECT {TASK_COLUMNS} FROM tasks WHERE status = ? AND id != ?"
          " ORDER BY position, id",
          (status, task_id),
        ).fetchall()
      ]
      record = {
        "id": task_id,
        "title": title,
        "details": details,
        "status": status,
        "order": len(siblings) + 1,
        "updated_at": stamp,
        "completed_at": completed_at,
        "blocked": bool(blocked),
        "report_id": report_id,
        "type": task_type,
      }
      if order is not None:
        index = max(0, min(order - 1, len(siblings)))
      elif stored and stored["status"] == status:
        index = max(0, min(stored["order"] - 1, len(siblings)))
      else:
        index = len(siblings)
      if (
        not restoring
        and stored
        and stored["status"] == status == "upcoming"
        and order is not None
        and index + 1 != stored["order"]
        and meta_number(db, TASK_ORDER_OWNED_META)
      ):
        raise ValueError(
          "Task order belongs to the preview; omit --order for this update"
        )
      siblings.insert(index, record)
      record["order"] = index + 1
      db.execute(
        "INSERT INTO tasks (id, title, details, status, position, created_at, updated_at,"
        " completed_at, blocked, report_id, type) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        " ON CONFLICT(id) DO UPDATE SET title = excluded.title,"
        " details = excluded.details, status = excluded.status,"
        " position = excluded.position, updated_at = excluded.updated_at,"
        " completed_at = excluded.completed_at, blocked = excluded.blocked,"
        " report_id = excluded.report_id, type = excluded.type",
        (
          task_id,
          title,
          json.dumps(details, ensure_ascii=False),
          status,
          index + 1,
          stamp,
          stamp,
          completed_at,
          1 if blocked else 0,
          report_id,
          task_type,
        ),
      )
      # Write positions from the computed list.
      # A tie could reorder siblings by ID.
      for position, item in enumerate(siblings, 1):
        db.execute("UPDATE tasks SET position = ? WHERE id = ?", (position, item["id"]))
      self.renumber(db)
    return link_task_runs([record], self.path.parent)[0]

  def reorder_tasks(self, ids):
    """Move the named upcoming tasks into the drawn order and return the page payload.

    The page sends the rows it shows, so a filter or a search can leave tasks out: an unlisted
    task keeps its slot, and the drawn names refill the slots they came from."""
    if (
      not isinstance(ids, list)
      or not ids
      or not all(isinstance(item, str) for item in ids)
    ):
      raise ValueError("ids must be a list of one or more task IDs")
    if len(set(ids)) != len(ids):
      raise ValueError("Each task ID appears once in ids")
    with self.transaction() as db:
      rows = db.execute(
        "SELECT id FROM tasks WHERE status = ? ORDER BY position, id", ("upcoming",)
      ).fetchall()
      stored = [row["id"] for row in rows]
      for task_id in ids:
        if task_id not in stored:
          raise ValueError(f"No upcoming task holds {task_id}")
      db.executemany(
        "INSERT OR REPLACE INTO meta VALUES (?, ?)",
        [(TASK_ORDER_OWNED_META, "1"), (TASK_ORDER_PENDING_META, "1")],
      )
      drawn = iter(ids)
      wanted = set(ids)
      sequence = [next(drawn) if task_id in wanted else task_id for task_id in stored]
      for position, task_id in enumerate(sequence, 1):
        db.execute("UPDATE tasks SET position = ? WHERE id = ?", (position, task_id))
      db.execute(
        f"UPDATE tasks SET updated_at = ? WHERE id IN ({', '.join('?' for _ in ids)})",
        (now(), *ids),
      )
    return self.tasks()

  @staticmethod
  def report_has_answers(db, report_id):
    """Whether this report already holds an answer, so no task waits on it."""
    return bool(
      db.execute(
        "SELECT 1 FROM submissions WHERE report_id = ? LIMIT 1", (report_id,)
      ).fetchone()
    )

  @staticmethod
  def release_report_tasks(db, report_id):
    """Clear the blocked mark on every task waiting on this report.

    A task blocked on a report waits for one thing, the owner's answer, so the answer
    releases it. The task stays upcoming, and the next poll then
    returns it as work instead of as a wait.
    """
    db.execute(
      "UPDATE tasks SET blocked = 0, updated_at = ?"
      " WHERE report_id = ? AND blocked = 1",
      (now(), report_id),
    )

  def remove_task(self, task_id):
    "Remove one task and return its stored record for the output."
    guard_task_runs(self.path.parent, task_id, "remove task")
    with self.transaction() as db:
      row = db.execute(
        f"SELECT {TASK_COLUMNS} FROM tasks WHERE id = ?", (task_id,)
      ).fetchone()
      if row is None:
        raise ValueError(f"No task is stored under {task_id}")
      db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
      self.renumber(db)
    return task_row(row)

  @staticmethod
  def refuse_shared_id(db, table, other, identity):
    """Fail when `identity` already names a row in `other`: the log links one ID to one panel."""
    if db.execute(f"SELECT 1 FROM {other} WHERE id = ?", (identity,)).fetchone():
      raise ValueError(
        f"{identity} already names a {other[:-1]}; a {table[:-1]} needs another ID,"
        f" for example {identity}-{table[:-1]}"
      )

  def rename_entity(self, prev_id, new_id):
    """Move one record to a new ID and repoint every row that names the old one.

    A git SHA can share its letters with a session ID, and the commit trap then
    has no way to tell them apart. Renaming the session record clears the collision
    without touching the SHA. One transaction covers the record and its dependents,
    so a rename never lands half.
    """
    identifier(new_id)
    exact = [item for item in self.id_matches(prev_id) if item[1]["id"] == prev_id]

    if len(exact) != 1:
      raise ValueError(f"No note, answer, report or task holds the ID {prev_id}")

    kind = exact[0][0]
    table, dependents = RENAME_TARGETS[kind]

    if kind == "task":
      guard_task_runs(self.path.parent, prev_id, "rename task")
      check_task(new_id, None, None)

    with self.transaction() as db:
      for other in RENAME_TABLES:
        if db.execute(f"SELECT 1 FROM {other} WHERE id = ?", (new_id,)).fetchone():
          raise ValueError(f"{new_id} already names a row in {other}")

      db.execute(f"UPDATE {table} SET id = ? WHERE id = ?", (new_id, prev_id))

      if table == "tasks":
        db.execute("UPDATE tasks SET updated_at = ? WHERE id = ?", (now(), new_id))

      for other, column in dependents:
        db.execute(
          f"UPDATE {other} SET {column} = ? WHERE {column} = ?", (new_id, prev_id)
        )

    return kind

  def amend_task(self, prev_id, task_id):
    """Move a stored task to a new ID and keep the rest, so a typo costs no removal."""
    check_task(task_id, None, None)
    stamp = now()
    with self.transaction() as db:
      row = db.execute(
        "SELECT id, title, details, status, position, created_at, completed_at, blocked, report_id"
        " FROM tasks WHERE id = ?",
        (prev_id,),
      ).fetchone()
      if row is None:
        raise ValueError(f"No task is stored under {prev_id}")
      guard_task_runs(self.path.parent, prev_id, "rename task")
      if db.execute("SELECT 1 FROM tasks WHERE id = ?", (task_id,)).fetchone():
        raise ValueError(f"A task is already stored under {task_id}")
      self.refuse_shared_id(db, "tasks", "reports", task_id)
      db.execute("DELETE FROM tasks WHERE id = ?", (prev_id,))
      db.execute(
        "INSERT INTO tasks (id, title, details, status, position, created_at, updated_at,"
        " completed_at, blocked, report_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
          task_id,
          row[1],
          row[2],
          row[3],
          row[4],
          row[5],
          stamp,
          row[6],
          row[7],
          row[8],
        ),
      )
      self.renumber(db)

  def userscript_history(self, shared=None):
    with self.transaction(shared, autosave=False) as db:
      row = db.execute(
        "SELECT value FROM meta WHERE key = ?", (AUTOSAVE_HISTORY,)
      ).fetchone()
      return json.loads(row[0]) if row else []

  def userscript_scope(self):
    root = self.path.parent.parent
    return {"repo": root.name, "branch": workspace_branch(root) or ""}

  def userscript_snapshot(self):
    core, counts = self.state_lines(self.state()["notes"], self.tasks() or {})
    core, stamp = autosave_core_and_stamp(core)
    scope = self.userscript_scope()
    history = self.userscript_history()
    stamps = self.newest_stamps()
    rows = [row for row in history if row["scope"] == scope and row.get("stamp")]
    return {
      "save_id": str(uuid.uuid4()),
      "scope": scope,
      "core": core,
      "digest": autosave_digest(core),
      "history": rows,
      "lastsave": rows[-1]["stamp"] if rows else None,
      "beforelastsave": rows[-2]["stamp"] if len(rows) > 1 else None,
      "text": state_ndjson(core + history),
      "counts": counts,
      "stamp": stamp,
      "stamps": stamps,
    }

  def confirm_userscript_save(self, payload):
    save_id, scope = payload.get("save_id"), payload.get("scope")
    if not isinstance(save_id, str):
      raise TypeError("Autosave save ID must be a UUID string")
    uuid.UUID(save_id)
    key = autosave_scope_key(scope)
    if scope != self.userscript_scope():
      raise ValueError("Autosave confirmation is outside this repository and branch")
    core = autosave_core(payload.get("core"))
    stamp = payload.get("stamp", payload.get("lastsave"))
    if stamp is not None and import_stamp(stamp) is None:
      raise ValueError("Autosave confirmation stamp is invalid")
    digest = autosave_digest(core)
    if digest != payload.get("digest"):
      raise ValueError("Autosave confirmation digest does not match")
    with self.transaction() as db:
      db.execute("BEGIN IMMEDIATE")
      row = db.execute(
        "SELECT value FROM meta WHERE key = ?", (AUTOSAVE_RECEIPTS,)
      ).fetchone()
      receipts = json.loads(row[0]) if row else {}
      scope_receipts = receipts.setdefault(key, {})
      if save_id in scope_receipts:
        if scope_receipts[save_id] != digest:
          raise ValueError("Autosave save ID already confirms another state")
      else:
        scope_receipts[save_id] = digest
        history = self.userscript_history(db)
        record = {
          "kind": "userscript-autosave",
          "version": 1,
          "save_id": save_id,
          "scope": scope,
          "digest": digest,
          "core": core,
          "stamp": stamp,
          "confirmed_at": now(),
        }
        previous = [item for item in history if item["scope"] == scope]
        kept = previous[-1:] + [record]
        for item in kept:
          item["receipts"] = scope_receipts.copy()
        history = [item for item in history if item["scope"] != scope] + kept
        db.execute(
          "INSERT OR REPLACE INTO meta VALUES (?, ?)",
          (AUTOSAVE_HISTORY, json.dumps(history)),
        )
        db.execute(
          "INSERT OR REPLACE INTO meta VALUES (?, ?)",
          (AUTOSAVE_RECEIPTS, json.dumps(receipts)),
        )
    return {"confirmed": True, "save_id": save_id, "digest": digest}

  def compare_userscript_save(self, payload):
    candidate, candidate_stamp = autosave_core_and_stamp(payload.get("core"))
    baseline = payload.get("baseline")
    result = {
      "candidate_stamp": candidate_stamp,
      "counts": {"candidate": len(candidate)},
    }
    if not isinstance(baseline, dict):
      return {**result, "result": "unknown-baseline"}
    if (
      payload.get("scope") != baseline.get("scope")
      or payload.get("scope") != self.userscript_scope()
    ):
      return {**result, "result": "scope-mismatch"}
    rows = [
      row
      for row in self.userscript_history()
      if row["scope"] == baseline["scope"] and row.get("stamp") is not None
    ]
    lastsave = rows[-1]["stamp"] if rows else None
    beforelastsave = rows[-2]["stamp"] if len(rows) > 1 else None
    slots = {"lastsave": lastsave, "beforelastsave": beforelastsave}
    result = {**result, **slots}
    if (
      baseline.get("lastsave") != lastsave
      or baseline.get("beforelastsave") != beforelastsave
      or not rows
    ):
      return {**result, "result": "unknown-baseline"}
    saved = rows[-1]
    supplied = baseline.get("core")
    if supplied is not None and autosave_core(supplied) != autosave_core(saved["core"]):
      return {**result, "result": "unknown-baseline"}
    core = autosave_core(saved["core"])
    before = saved["stamp"]

    def identity(row):
      kind = (
        "report"
        if "markdown" in row
        else "task"
        if "title" in row
        else "answer"
        if "report_id" in row
        else "note"
      )
      return kind, row["id"]

    missing = len(
      {identity(row) for row in core} - {identity(row) for row in candidate}
    )
    status = (
      "equal"
      if candidate_stamp == before
      else "candidate-missing-records"
      if missing
      else "different"
    )
    return {
      **result,
      "result": status,
      "baseline_stamp": before,
      "counts": {
        "baseline": len(core),
        "candidate": len(candidate),
        "missing": missing,
      },
    }

  def autosave(self):
    """Refresh the save file from the database after a committed mutation.

    State mutations route through `transaction`. Construction, `set_meta` and `reminder` do
    not. A failed refresh warns on stderr and the committed mutation stands.
    """
    try:
      self.save_state({"notes": self.state()["notes"], "tasks": self.tasks()})
    except Exception as error:
      print(f"preview: autosave failed: {error}", file=sys.stderr)

  def state_lines(self, notes, tasks):
    """Build save-file lines and counts for one state snapshot. Include note receipts, read stamps, task markers,
    task order, answers, and report Markdown. Omit quiet notes. Keep an answer a task still
    references, even after its report row is gone."""
    if not isinstance(notes, list) or not isinstance(tasks, dict):
      raise TypeError("Save a state object with notes and tasks")
    saved_notes = [record for record in notes if not record.get("quiet")]
    lines = [saved_note_line(record) for record in saved_notes]
    for status in TASK_STATUSES:
      for record in tasks.get(status) or []:
        lines.append(saved_task_line(record))
    sources = self.report_sources()
    live = {record["id"] for record in sources}
    task_ids = set()
    task_reports = set()
    for status in TASK_STATUSES:
      for record in (tasks.get(status) if tasks is not None else None) or []:
        task_ids.add(record.get("id"))
        if record.get("report_id"):
          task_reports.add(record["report_id"])
    answers = [
      saved_answer_line(record)
      for record in self.submissions()
      if record.get("report_id") in live
      or record.get("task_id") in task_ids
      or record.get("report_id") in task_reports
    ]
    lines.extend(answers)
    reports = [saved_report_line(record) for record in sources]
    lines.extend(reports)
    return lines, {
      "notes": len(saved_notes),
      "tasks": len(lines) - len(saved_notes) - len(answers) - len(reports),
      "answers": len(answers),
      "reports": len(reports),
    }

  def newest_stamps(self):
    """Return the newest durable change time per group in UTC."""
    groups = (
      ("note", "notes", ("at", "acknowledged_at", "ack_edited_at", "seen_at")),
      ("answer", "submissions", ("at", "acknowledged_at", "seen_at")),
      ("report", "reports", ("updated_at", "published_at", "seen_at", "agent_seen_at")),
      ("upload", "uploads", ("at",)),
      ("task", "tasks", ("updated_at",)),
    )
    stamps = {}
    with closing(self.connect()) as db:
      for group, table, names in groups:
        exprs = ", ".join(f"MAX({name})" for name in names)
        newest = None
        for value in db.execute(f"SELECT {exprs} FROM {table}").fetchone():
          stamp = import_stamp(value)
          if stamp and (newest is None or stamp > newest):
            newest = stamp
        stamps[group] = newest.isoformat() if newest else None
      # A removal can move a group maximum back. Its removal mark carries the newest stamp forward.
      # The save stamp trigger rewrites a file that still contains the removed report.
      removed = db.execute(
        "SELECT value FROM meta WHERE key = ?", (REMOVED_META,)
      ).fetchone()
      mark = import_stamp(removed[0]) if removed else None
      stamps["removed"] = mark.isoformat() if mark else None
    return stamps

  def newest_stamp(self, stamps=None):
    """Return the latest state stamp in UTC. Use it in a download name so the name follows state rather than
    browser time. Exclude the poll heartbeat. Accept already-read group stamps."""
    stamps = stamps or self.newest_stamps()
    values = [import_stamp(value) for value in stamps.values()]
    values = [value for value in values if value]
    return max(values).isoformat() if values else None

  def save_state(self, payload):
    """Write the current state to the save file, in the shape the importer reads.

    Autosave calls this after every committed mutation, so the file follows the database with no button press.
    The page copies the same text from `/api/copy-state`. It posts nothing.

    The file lands inside the state directory unless a path overrides it, so one globally ignored directory
    carries the database and its export together."""
    if not isinstance(payload, dict):
      raise TypeError("Save a state object")
    notes = payload.get("notes")
    tasks = payload.get("tasks")
    if tasks is None:
      tasks = {}
    lines, counts = self.state_lines(notes, tasks)
    path = self.save_path
    if path.parent != Path("."):
      path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(state_ndjson(lines + self.userscript_history()), encoding="utf-8")
    return {"path": str(path), **counts}

  def uploads(self):
    """Every upload, newest last, with `present` saying whether its bytes are still on disk."""
    with closing(self.connect()) as db:
      rows = db.execute("SELECT * FROM uploads ORDER BY seq").fetchall()
    return [upload_row(row, self.path.parent) for row in rows]

  def save_upload(
    self,
    name,
    content_type,
    data,
    upload_id=None,
    shared=None,
    note_id=None,
    position=None,
  ):
    """Keep raw bytes beside SQLite, with a stable note link and distinct file record."""
    if not isinstance(data, (bytes, bytearray, FileBody)):
      raise TypeError("An upload is bytes")
    if not data:
      raise ValueError("An upload must not be empty")
    cleaned = upload_name(name)
    kind = upload_type(content_type)
    digest = body_digest(data)
    upload_id = identifier(upload_id) if upload_id is not None else self.free_id()
    note_id = identifier(note_id) if note_id is not None else upload_id
    if position is not None and (not isinstance(position, int) or position < 1):
      raise ValueError("Invalid attachment position")
    directory = self.path.parent / UPLOAD_DIR
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    with self.transaction(shared) as db:
      if shared is None:
        db.execute("BEGIN IMMEDIATE")
      existing = db.execute(
        "SELECT * FROM uploads WHERE id = ?", (upload_id,)
      ).fetchone()
      if existing:
        if (
          existing["note_id"],
          existing["name"],
          existing["type"],
          existing["size"],
          existing["sha256"],
        ) != (note_id, cleaned, kind, len(data), digest):
          raise ValueError("This note ID already belongs to a different file")
        target = directory / existing["file"]
        if (
          not target.is_file()
          or hashlib.sha256(target.read_bytes()).hexdigest() != digest
        ):
          save_body(target, data)
          target.chmod(0o600)
        return upload_row(existing, self.path.parent)
      duplicate_count = db.execute(
        "SELECT COUNT(*) FROM uploads WHERE note_id = ? AND replace(name, ' ', '-') = ?",
        (note_id, cleaned.replace(" ", "-")),
      ).fetchone()[0]
      number = duplicate_count + 1
      timestamp = int(time.time())
      extension = Path(cleaned).suffix[:16].replace(" ", "-")
      filename_stem = Path(cleaned).stem.replace(" ", "-")
      while True:
        duplicate = f"-{number}" if number > 1 else ""
        stem = f"{note_id[:6]}-{timestamp}{duplicate}-{filename_stem}"
        target = directory / f"{stem}{extension}"
        if len(os.fsencode(target.name)) > 255:
          target = directory / f"{upload_id}{duplicate}{extension}"
        collision = db.execute(
          "SELECT 1 FROM uploads WHERE file = ?", (target.name,)
        ).fetchone()
        if not collision and not target.exists():
          break
        number += 1
      save_body(target, data)
      target.chmod(0o600)
      db.execute(
        "INSERT INTO uploads (id, note_id, name, type, size, sha256, file, at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (upload_id, note_id, cleaned, kind, len(data), digest, target.name, now()),
      )
      row = db.execute("SELECT * FROM uploads WHERE id = ?", (upload_id,)).fetchone()
    return upload_row(row, self.path.parent)

  def note_with_uploads(self, note_id, text, files):
    "Store several linked files and one note in one transaction. Identical retries are safe."
    identifier(note_id)
    owner_text(text)
    if not isinstance(files, (list, tuple)) or len(files) < 1:
      raise ValueError("Attach at least one file to a note")
    prepared = []
    for file in files:
      if not isinstance(file, (list, tuple)) or len(file) != 3:
        raise ValueError("Each attachment needs a name, type and bytes")
      name, content_type, data = file
      if not isinstance(data, (bytes, bytearray, FileBody)):
        raise TypeError("An upload is bytes")
      if not data:
        raise ValueError("An upload must not be empty")
      prepared.append(
        (
          upload_name(name),
          upload_type(content_type),
          data if isinstance(data, FileBody) else bytes(data),
        )
      )
    created = []
    try:
      with self.transaction(autosave=False) as db:
        db.execute("BEGIN IMMEDIATE")
        existing = db.execute(
          "SELECT text FROM notes WHERE id = ?", (note_id,)
        ).fetchone()
        rows = db.execute(
          "SELECT * FROM uploads WHERE note_id = ? ORDER BY seq", (note_id,)
        ).fetchall()
        if existing and existing["text"] != text:
          raise ValueError("This message ID already belongs to different text")
        if rows:
          if len(rows) != len(prepared) or any(
            (row["name"], row["type"], row["size"], row["sha256"])
            != (name, kind, len(data), body_digest(data))
            for row, (name, kind, data) in zip(rows, prepared)
          ):
            raise ValueError("This note ID already belongs to different files")
          # A restore can keep SQLite records but lose bytes. Repeating exactly the same request
          # restores missing bytes, not the note's acknowledgement or its attachment order.
          for row, (_, _, data) in zip(rows, prepared):
            target = self.path.parent / UPLOAD_DIR / row["file"]
            if (
              not target.is_file()
              or hashlib.sha256(target.read_bytes()).hexdigest() != row["sha256"]
            ):
              target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
              save_body(target, data)
              target.chmod(0o600)
          records = [upload_row(row, self.path.parent) for row in rows]
        else:
          if existing:
            raise ValueError("This note ID was already sent without a file")
          records = []
          for index, (name, kind, data) in enumerate(prepared, 1):
            record = self.save_upload(
              name,
              kind,
              data,
              upload_id=note_id if index == 1 else new_id(),
              note_id=note_id,
              position=index if len(prepared) > 1 else None,
              shared=db,
            )
            records.append(record)
            created.append(Path(record["path"]))
        note = self.note(note_id, text, shared=db)
        result = add_note_attachments(note, records)
    except Exception:
      for path in created:
        path.unlink(missing_ok=True)
      raise
    self.autosave()
    return result

  def fetch_jobs(self):
    "Queue status and saved file locations. A claim token never reaches the state poll."
    with closing(self.connect()) as db:
      rows = db.execute("SELECT * FROM fetch_jobs ORDER BY seq DESC").fetchall()
    return [fetch_row(row, self.path.parent) for row in rows]

  def enqueue_fetch(self, url, allow_proxy, *, pending=False):
    url = fetch_url(url, agent=pending)
    if not isinstance(allow_proxy, bool):
      raise TypeError("Proxy fallback must be true or false for this URL")
    if not isinstance(pending, bool):
      raise TypeError("Pending approval must be true or false")
    job_id, stamp = new_id(), now()
    with self.transaction(autosave=False) as db:
      db.execute(
        "INSERT INTO fetch_jobs (id, url, allow_proxy, status, approval, at, updated_at, origin)"
        " VALUES (?, ?, ?, 'queued', ?, ?, ?, ?)",
        (
          job_id,
          url,
          int(allow_proxy),
          "pending" if pending else "approved",
          stamp,
          stamp,
          "agent" if pending else "owner",
        ),
      )
      row = db.execute("SELECT * FROM fetch_jobs WHERE id = ?", (job_id,)).fetchone()
    return fetch_row(row, self.path.parent)

  def decide_fetch(self, job_id, decision):
    """A preview Approve/Deny click decides one pending request exactly once."""
    identifier(job_id)
    if decision not in {"approved", "denied"}:
      raise ValueError("Choose Approve or Deny for the download")
    with self.transaction(autosave=False) as db:
      # The conditional UPDATE acquires SQLite's write lock before reading a job, so simultaneous
      # tabs cannot decide the same request differently. Denied jobs cannot be retried or claimed.
      changed = db.execute(
        "UPDATE fetch_jobs SET approval = ?, status = CASE WHEN ? = 'denied'"
        " THEN 'failed' ELSE status END, error = CASE WHEN ? = 'denied'"
        " THEN 'Denied in the preview' ELSE NULL END, updated_at = ?"
        " WHERE id = ? AND approval = 'pending' AND status = 'queued'",
        (decision, decision, decision, now(), job_id),
      )
      if changed.rowcount != 1:
        if (
          db.execute("SELECT 1 FROM fetch_jobs WHERE id = ?", (job_id,)).fetchone()
          is None
        ):
          raise FileNotFoundError("No queued download with that ID")
        raise FetchChanged(
          "This download request was already decided; refresh Downloads"
        )
      row = db.execute("SELECT * FROM fetch_jobs WHERE id = ?", (job_id,)).fetchone()
    return fetch_row(row, self.path.parent)

  def claim_fetch(self):
    "Atomically take the oldest queued URL. Abandoned claims return after five minutes."
    stamp = now()
    with self.transaction(autosave=False) as db:
      # `UPDATE` takes SQLite's write lock before `SELECT`, so two browser tabs cannot take the
      # same row. Active clients renew their lease while reading or sending a large file.
      db.execute(
        "UPDATE fetch_jobs SET status = 'queued', claim = NULL, lease_until = NULL,"
        " error = 'Browser stopped; queued again', updated_at = ?"
        " WHERE status = 'fetching' AND approval = 'approved' AND lease_until <= ?",
        (stamp, stamp),
      )
      row = db.execute(
        "SELECT id FROM fetch_jobs WHERE status = 'queued' AND approval = 'approved'"
        " ORDER BY seq LIMIT 1"
      ).fetchone()
      if row is None:
        return None
      job_id = row["id"]
      claim = secrets.token_urlsafe(24)
      lease = (datetime.now(timezone.utc) + FETCH_LEASE).isoformat()
      db.execute(
        "UPDATE fetch_jobs SET status = 'fetching', claim = ?, lease_until = ?,"
        " error = NULL, updated_at = ? WHERE id = ?",
        (claim, lease, stamp, job_id),
      )
      row = db.execute("SELECT * FROM fetch_jobs WHERE id = ?", (job_id,)).fetchone()
    return fetch_row(row, self.path.parent) | {"claim": claim}

  def claimed_fetch(self, db, job_id, claim):
    identifier(job_id)
    row = db.execute("SELECT * FROM fetch_jobs WHERE id = ?", (job_id,)).fetchone()
    if row is None:
      raise FileNotFoundError("No queued download with that ID")
    if (
      row["status"] != "fetching"
      or row["approval"] != "approved"
      or not isinstance(claim, str)
      or not secrets.compare_digest(row["claim"] or "", claim)
      or not row["lease_until"]
      or row["lease_until"] <= now()
    ):
      raise FetchChanged("Download claim expired; refresh the queue and try again")
    return row

  def renew_fetch(self, job_id, claim):
    with self.transaction(autosave=False) as db:
      self.claimed_fetch(db, job_id, claim)
      lease = (datetime.now(timezone.utc) + FETCH_LEASE).isoformat()
      db.execute("UPDATE fetch_jobs SET lease_until = ? WHERE id = ?", (lease, job_id))
      row = db.execute("SELECT * FROM fetch_jobs WHERE id = ?", (job_id,)).fetchone()
    return fetch_row(row, self.path.parent)

  def fail_fetch(self, job_id, claim, error):
    message = str(error).strip()[:1000] or "The browser could not fetch this URL"
    with self.transaction(autosave=False) as db:
      self.claimed_fetch(db, job_id, claim)
      db.execute(
        "UPDATE fetch_jobs SET status = 'failed', error = ?, claim = NULL,"
        " lease_until = NULL, updated_at = ? WHERE id = ?",
        (message, now(), job_id),
      )
      row = db.execute("SELECT * FROM fetch_jobs WHERE id = ?", (job_id,)).fetchone()
    return fetch_row(row, self.path.parent)

  def drop_fetch(self, job_id):
    """Remove one download record and its staged bytes, on the owner's click."""
    identifier(job_id)
    with self.transaction(autosave=False) as db:
      row = db.execute("SELECT * FROM fetch_jobs WHERE id = ?", (job_id,)).fetchone()
      if row is None:
        raise FileNotFoundError("No download with that ID")
      if row["status"] in {"queued", "fetching"} and row["claim"]:
        raise FetchChanged("This download is active in a browser")
      db.execute("DELETE FROM fetch_jobs WHERE id = ?", (job_id,))
      if row["file"]:
        target = self.path.parent / "downloads" / row["file"]
        try:
          target.unlink()
        except FileNotFoundError:
          pass
    return {"dropped": job_id}

  def retry_fetch(self, job_id):
    identifier(job_id)
    with self.transaction(autosave=False) as db:
      row = db.execute("SELECT * FROM fetch_jobs WHERE id = ?", (job_id,)).fetchone()
      if row is None:
        raise FileNotFoundError("No queued download with that ID")
      if row["approval"] != "approved":
        raise FetchChanged("Only approved downloads can be retried")
      if row["status"] not in {"queued", "failed"}:
        raise FetchChanged("Only a failed download can be queued again")
      db.execute(
        "UPDATE fetch_jobs SET status = 'queued', error = NULL, updated_at = ?"
        " WHERE id = ?",
        (now(), job_id),
      )
      row = db.execute("SELECT * FROM fetch_jobs WHERE id = ?", (job_id,)).fetchone()
    return fetch_row(row, self.path.parent)

  def complete_fetch(self, job_id, claim, name, content_type, source, data):
    if not data:
      raise ValueError("A download must not be empty")
    if source not in {"direct", "allorigins", "codetabs"}:
      raise ValueError("Unknown download source")
    cleaned = upload_name(name)
    file_type = upload_type(content_type)
    target = None
    try:
      with self.transaction(autosave=False) as db:
        row = self.claimed_fetch(db, job_id, claim)
        if source != "direct" and not row["allow_proxy"]:
          raise ValueError("Proxy fallback was not enabled for this URL")
        directory = self.path.parent / FETCH_DIR
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        target = directory / f"{job_id}{Path(cleaned).suffix[:16]}"
        save_body(target, data)
        target.chmod(0o600)
        stamp = now()
        db.execute(
          "UPDATE fetch_jobs SET status = 'saved', source = ?, name = ?, type = ?,"
          " size = ?, sha256 = ?, file = ?, error = NULL, claim = NULL,"
          " lease_until = NULL, updated_at = ? WHERE id = ?",
          (
            source,
            cleaned,
            file_type,
            len(data),
            body_digest(data),
            target.name,
            stamp,
            job_id,
          ),
        )
        message = (
          f"Download: {cleaned} ({len(data)} B, {file_type}) from "
          f"{urlsplit(row['url']).hostname} via {source} saved to {target}"
        )
        db.execute(
          "INSERT INTO notes (id, text, at) VALUES (?, ?, ?)",
          (job_id, message, stamp),
        )
        result = db.execute(
          "SELECT * FROM fetch_jobs WHERE id = ?", (job_id,)
        ).fetchone()
    except Exception:
      if target is not None:
        target.unlink(missing_ok=True)
      raise
    self.autosave()  # the completion wrote an inbox note. Unfinished queue rows stay only in SQLite
    return fetch_row(result, self.path.parent)

  def import_state(self, text, replace_tasks=False, merge=False):
    "Import a backup. Replace live entries unless the caller requests merge."
    records = parse_state_import(text)
    history = [
      autosave_record(row)
      for row in records
      if row.get("kind") == "userscript-autosave"
    ]
    records = [row for row in records if row.get("kind") != "userscript-autosave"]
    groups = {}
    imported_receipts = {}
    for row in history:
      key = autosave_scope_key(row["scope"])
      groups.setdefault(key, []).append(row)
      receipts = imported_receipts.setdefault(key, {})
      for save_id, digest in {
        **row.get("receipts", {}),
        row["save_id"]: row["digest"],
      }.items():
        if save_id in receipts and receipts[save_id] != digest:
          raise ValueError("Conflicting autosave receipt digests")
        receipts[save_id] = digest
      if len(groups[key]) > 2 or len({item["save_id"] for item in groups[key]}) != len(
        groups[key]
      ):
        raise ValueError("Autosave history holds at most two distinct saves per scope")
    reports = [r for r in records if "markdown" in r and "text" not in r]
    tasks = [
      r for r in records if "markdown" not in r and "title" in r and "text" not in r
    ]
    messages = [
      r for r in records if "markdown" not in r and ("title" not in r or "text" in r)
    ]
    if not merge:
      guard_task_runs(self.path.parent, action="replace state")
    with self.transaction(autosave=False) as db:
      db.execute("BEGIN IMMEDIATE")
      if history and (not merge or not self.userscript_history(db)):
        receipts = {}
        for row in history:
          key = autosave_scope_key(row["scope"])
          receipts.setdefault(key, {}).update(row.get("receipts", {}))
          receipts[key][row["save_id"]] = row["digest"]
        db.execute(
          "INSERT OR REPLACE INTO meta VALUES (?, ?)",
          (AUTOSAVE_HISTORY, json.dumps(history)),
        )
        db.execute(
          "INSERT OR REPLACE INTO meta VALUES (?, ?)",
          (AUTOSAVE_RECEIPTS, json.dumps(receipts)),
        )
      if not merge:
        for table in ("notes", "reports", "submissions", "tasks"):
          db.execute(f"DELETE FROM {table}")
      self.import_reports(reports, shared=db)
      self.import_tasks(tasks, replace_tasks, autosave=False, shared=db)
      for record in messages:
        if "text" not in record or "title" in record:
          raise ValueError("Each record must be a note, task or report answer")
        options = {
          key: record.get(key)
          for key in (
            "acknowledged_at",
            "ack_kind",
            "ack_text",
            "ack_edited_at",
            "seen_at",
            "task_id",
            "replies",
            "ack_edited_seen_count",
          )
        }
        args = [record["id"]]
        writer = self.note
        if "report_id" in record:
          writer = self.submission
          args.append(record["report_id"])
        writer(
          *args, record["text"], record.get("at"), shared=db, autosave=False, **options
        )
    receipt = {
      "notes": sum("report_id" not in r for r in messages),
      "answers": sum("report_id" in r for r in messages),
      "reports": len(reports),
      "tasks": len(tasks),
    }
    return receipt

  def import_reports(self, records, shared=None):
    """Restore reports and published state from the save file. Use saved Markdown to rebuild report pages. Check
    every record before writing."""
    if not isinstance(records, list):
      raise TypeError("Import a list of report objects")
    prepared = []
    for record in records:
      if not isinstance(record, dict):
        raise TypeError("Import a list of report objects")
      report_id = record.get("id")
      identifier(report_id)
      title = record.get("title")
      if not isinstance(title, str) or not title.strip() or len(title) > 200:
        raise ValueError("Report title must contain 1–200 characters")
      markdown = record.get("markdown")
      if not isinstance(markdown, str) or not markdown.strip():
        raise ValueError("A saved report needs its markdown")
      if len(markdown.encode("utf-8")) > MAX_REPORT:
        raise ValueError("Report exceeds the 2 MB limit; split it into reports")
      published_at = record.get("published_at")
      if published_at is not None and not isinstance(published_at, str):
        raise ValueError("A saved publish stamp is text")
      seen_at = record.get("seen_at")
      if seen_at is not None and not isinstance(seen_at, str):
        raise ValueError("A saved seen stamp is text")
      if seen_at is not None:
        when(seen_at)
      prepared.append(
        (report_id, title, markdown, published_at, seen_at, seen_at is not None)
      )
    with self.transaction(shared) as db:
      for report_id, title, markdown, published_at, seen_at, ever_seen in prepared:
        highest = db.execute("SELECT COALESCE(MAX(seq), 0) FROM reports").fetchone()[0]
        db.execute(
          """INSERT INTO reports
             (id, title, markdown, updated_at, published_at, seq, seen_at, ever_seen)
             VALUES (?, ?, ?, ?, ?, ?, ?, ?)
             ON CONFLICT(id) DO UPDATE SET title = excluded.title,
               markdown = excluded.markdown, updated_at = excluded.updated_at,
               published_at = COALESCE(reports.published_at, excluded.published_at),
               seen_at = COALESCE(reports.seen_at, excluded.seen_at),
               ever_seen = MAX(reports.ever_seen, excluded.ever_seen)""",
          (
            report_id,
            title,
            markdown,
            now(),
            published_at,
            highest + 1,
            seen_at,
            ever_seen,
          ),
        )
    return len(prepared)

  def import_tasks(self, records, replace=False, autosave=True, shared=None):
    """Restore tasks from saved JSON. Check every record before writes, then use one transaction. Reject an
    invalid replacement before it removes stored tasks."""
    if not isinstance(records, list):
      # The importer also calls this directly, so reject malformed records here.
      raise TypeError("Import a list of task objects")
    prepared = []
    for index, record in enumerate(records, 1):
      if not isinstance(record, dict):
        raise TypeError("Import a list of task objects")
      details = [str(item) for item in record.get("details") or [] if str(item).strip()]
      status = record.get("status")
      completed_at = record.get("completed_at")
      # The checks write_task applies, run over every record up front: an import that can
      # only fail on its fortieth record should fail before it touches the first.
      check_task(record.get("id"), record.get("title"), details)
      if status is not None and status not in TASK_STATUSES:
        raise ValueError(f"A task is either {' or '.join(TASK_STATUSES)}")
      task_type = record.get("type")
      if task_type is not None and task_type not in TASK_TYPES + TASK_LEGACY_TYPES:
        raise ValueError(
          f"A task type is one of {', '.join(TASK_TYPES + TASK_LEGACY_TYPES)}"
        )
      if completed_at is not None:
        if not isinstance(completed_at, str):
          raise ValueError("A saved completion stamp is text")
        when(completed_at)
      prepared.append(
        (
          record.get("id"),
          record.get("title"),
          details,
          status,
          record.get("order") or index,
          record.get("blocked"),
          record.get("report_id"),
          completed_at,
          task_type,
        )
      )
    if replace:
      guard_task_runs(self.path.parent, action="replace tasks")
    with self.transaction(shared, autosave=autosave) as db:
      if replace:
        # Replacement records cannot inherit a title. Reject before removal to name the offending record.
        # A later error rolls back before an empty transaction appears saved.
        for task_id, title, *_ in prepared:
          stored = db.execute("SELECT 1 FROM tasks WHERE id = ?", (task_id,)).fetchone()
          if title is None and not stored:
            raise ValueError(f"A new task needs a title: {task_id}")
        db.execute("DELETE FROM tasks")
      written = [self.write_task(*item, shared=db, restoring=True) for item in prepared]
    return written

  def renumber(self, db):
    """Keep positions dense inside each div after a move, an insert or a removal."""
    for status in TASK_STATUSES:
      rows = db.execute(
        "SELECT id FROM tasks WHERE status = ? ORDER BY position, id", (status,)
      ).fetchall()
      for position, row in enumerate(rows, 1):
        db.execute("UPDATE tasks SET position = ? WHERE id = ?", (position, row[0]))

  def meta_value(self, key):
    """Read one meta value, or None when it is absent."""
    with closing(self.connect()) as db:
      row = db.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
      return row[0] if row else None

  def stamp_polling(self):
    """Record that an agent poll runs now.

    The poll stamps once a second and clears the stamp when it stops. A killed poll
    leaves the stamp behind, and the freshness window expires it.
    """
    with closing(self.connect()) as db, db:
      db.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", (POLLING_META, now()))

  def start_poll(self):
    """Record the heartbeat and the wait start, so the page can time the wait."""
    with closing(self.connect()) as db, db:
      stamp = now()
      db.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", (POLLING_META, stamp))
      db.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", (POLL_SINCE_META, stamp))

  def clear_polling(self):
    """Drop the poll heartbeat and the wait start, so the page returns to its connected dot."""
    with closing(self.connect()) as db, db:
      db.execute(
        "DELETE FROM meta WHERE key IN (?, ?)", (POLLING_META, POLL_SINCE_META)
      )

  def polling(self):
    """True while a poll heartbeat sits inside the freshness window."""
    age = seconds_since(self.meta_value(POLLING_META))
    return age is not None and 0 <= age < POLLING_FRESH_SECONDS

  def request_interrupt(self, tab, report_id=None, armed=True):
    if not armed:
      self.take_interrupt()
      return {"agent_interrupt_pending": False}
    if not isinstance(tab, str) or tab not in {
      "notes",
      "reports",
      "tasks",
      "downloads",
    }:
      raise ValueError("tab must name a preview tab")
    header = "VIOLATION"
    if tab == "reports" and report_id is not None:
      try:
        self.report(report_id)
      except FileNotFoundError:
        pass
      else:
        header = f"VIOLATION: report {report_id}"
    elif tab == "tasks":
      task = current_task((self.tasks() or {}).get("upcoming", []))
      if task:
        header = f"VIOLATION: task {task['id']}"
    notice = (
      f"{header}\nThis Bash call was blocked. Read ARENA.md, root AGENTS.md, "
      "every nested AGENTS.md, and arena-skill SKILL.md in full again, then fix "
      "the violation before continuing."
    )
    self.set_meta(AGENT_INTERRUPT_META, notice)
    return {"agent_interrupt_pending": True}

  def take_interrupt(self):
    with closing(self.connect()) as db, db:
      db.execute("BEGIN IMMEDIATE")
      row = db.execute(
        "SELECT value FROM meta WHERE key = ?", (AGENT_INTERRUPT_META,)
      ).fetchone()
      db.execute("DELETE FROM meta WHERE key = ?", (AGENT_INTERRUPT_META,))
      return row["value"] if row else None

  def request_skip_poll(self, armed=True):
    "Arm or clear the owner's Skip poll press. The next poll consumes an armed flag once."
    if not armed:
      self.take_skip_poll()
      return {"skip_poll": None}
    self.set_meta(SKIP_POLL_META, now())
    return {"skip_poll": clip_stamp(self.meta_value(SKIP_POLL_META))}

  def skip_poll_requested(self):
    """True while the owner's Skip poll press waits for a poll to end."""
    return self.meta_value(SKIP_POLL_META) is not None

  def take_skip_poll(self):
    """Drop the Skip poll request and return its stamp, or None when none waits."""
    stamp = self.meta_value(SKIP_POLL_META)
    if stamp is None:
      return None
    with closing(self.connect()) as db, db:
      db.execute("DELETE FROM meta WHERE key = ?", (SKIP_POLL_META,))
    return clip_stamp(stamp)

  def set_meta(self, key, value):
    """Record one meta value, replacing any previous one."""
    with closing(self.connect()) as db, db:
      db.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", (key, str(value)))

  def touch_agent(self):
    """Stamp the agent's own call: the liveness signal the preview header reads.

    The call also clears the turn-end mark: a working agent never reads as gone.
    """
    self.set_meta(AGENT_SEEN_META, now())
    self.clear_turn_ended()

  def mark_turn_ended(self):
    "Record that the turn ended here. The header reads the mark."
    self.set_meta(TURN_ENDED_META, now())

  def clear_turn_ended(self):
    """Drop the turn-end mark, so the next turn starts clean."""
    with closing(self.connect()) as db, db:
      db.execute("DELETE FROM meta WHERE key = ?", (TURN_ENDED_META,))

  def set_agent_key(self, key, host=None):
    """Record the key the userscript holds and the proxy host, with the stamp."""
    self.set_meta(
      AGENT_KEY_META,
      json.dumps({"key": key, "host": host, "at": now()}, ensure_ascii=False),
    )

  def notice_expired_key(self):
    """Tell the agent once per record when the recorded key outlives the rotation window.

    A new key overwrites the record by itself, so nothing here removes one. The note
    names no key: `arena-preview key` prints the live one, and the record is already
    stored. One note per record stamp, so a later read never repeats it.
    """
    record = self.agent_key()
    if not record:
      return None
    # Read the stored stamp as UTC because it has no offset.
    stamp = import_stamp(record["at"])
    if stamp is None:
      return None
    if (datetime.now(timezone.utc) - stamp).total_seconds() < AGENT_KEY_EXPIRY_SECONDS:
      return None
    if self.meta_value(AGENT_KEY_EXPIRY_META) == record["at"]:
      return None
    self.set_meta(AGENT_KEY_EXPIRY_META, record["at"])
    return self.note(
      self.free_id(),
      f"The recorded agent key expired (set {record['at']}). Run `arena-preview key`"
      " for the live key; a new post overwrites this record by itself.",
      quiet=True,
    )

  def agent_key(self):
    """The recorded key, host and stamp, or None while none stands or the record is broken."""
    value = self.meta_value(AGENT_KEY_META)
    if not value:
      return None
    try:
      record = json.loads(value)
    except json.JSONDecodeError:
      return None
    if not isinstance(record, dict):
      return None
    key = record.get("key")
    if not isinstance(key, str) or not AGENT_KEY_RE.fullmatch(key):
      return None
    host = record.get("host")
    if not isinstance(host, str) or not AGENT_HOST_RE.fullmatch(host):
      host = None
    return {"key": key, "host": host, "at": clip_stamp(record.get("at"))}

  def stale_report_rows(self, db):
    """Published reports that are stale: no fields, or fields answered and acked."""
    stale = []
    rows = db.execute(
      "SELECT id, markdown FROM reports WHERE published_at IS NOT NULL ORDER BY seq, id"
    )
    for row in rows:
      try:
        fields = len(parse_fields(row["markdown"])[1])
      except ValueError:
        continue
      if fields == 0:
        stale.append({"id": row["id"], "reason": "no fields"})
        continue
      pending = db.execute(
        "SELECT count(*) FROM submissions"
        " WHERE report_id = ? AND acknowledged_at IS NULL",
        (row["id"],),
      ).fetchone()[0]
      answered = db.execute(
        "SELECT count(*) FROM submissions WHERE report_id = ?", (row["id"],)
      ).fetchone()[0]
      if answered and not pending:
        stale.append({"id": row["id"], "reason": "all submissions acknowledged"})
    return stale

  def stale_report_ids(self, db):
    """The stale report IDs for the reminder line."""
    return [record["id"] for record in self.stale_report_rows(db)]

  def stale_reports(self):
    """List stale published report IDs and reasons without changing state."""
    with closing(self.connect()) as db:
      return self.stale_report_rows(db)

  def report_state(self, report_id=None):
    """Row per report: publication, owner view stamp and answer visibility. No changes."""
    with closing(self.connect()) as db:
      rows = db.execute(
        "SELECT id, title, published_at, updated_at, viewed_at FROM reports"
        + (" WHERE id = ?" if report_id else "")
        + " ORDER BY updated_at DESC",
        (report_id,) if report_id else (),
      ).fetchall()
      stale = {row["id"] for row in self.stale_report_rows(db)}
      out = []
      for row in rows:
        answers = db.execute(
          "SELECT id, acknowledged_at, seen_at FROM submissions"
          " WHERE report_id = ? ORDER BY seq",
          (row["id"],),
        ).fetchall()
        out.append(
          {
            "id": row["id"],
            "title": row["title"],
            "published_at": row["published_at"],
            "updated_at": row["updated_at"],
            "viewed_at": row["viewed_at"],
            "stale": row["id"] in stale,
            "answers": [
              {
                "id": answer["id"],
                "acknowledged": answer["acknowledged_at"] is not None,
                "seen": answer["seen_at"] is not None,
              }
              for answer in answers
            ],
          }
        )
      return out

  def reminder(self, advance=False, routine=True):
    """Count pending kinds without marking any message seen. Any count asks for an ack.

    The tail rotates through REMINDERS only with routine guidance.
    `advance` counts one hook poll, and that
    count prints only beside a pending count, so an idle line carries the tail alone. A poll that finds nothing
    pending clears the count, so the printed number reports the bash calls since the owner's first still-unread
    message. Only `--reminder` advances it. A new note or form answer resets it only when it starts a fresh
    backlog, and `read` does not."""
    order_notice = False
    with closing(self.connect()) as db, db:
      if advance and meta_number(db, TASK_ORDER_PENDING_META):
        order_notice = True
        db.execute("DELETE FROM meta WHERE key = ?", (TASK_ORDER_PENDING_META,))
      uploads = db.execute(
        "SELECT count(*) FROM notes JOIN uploads USING (id)"
        " WHERE acknowledged_at IS NULL AND blocking = 1"
      ).fetchone()[0]
      notes = (
        db.execute(
          "SELECT count(*) FROM notes WHERE acknowledged_at IS NULL AND blocking = 1"
        ).fetchone()[0]
        - uploads
      )
      reports = db.execute(
        "SELECT count(*) FROM submissions WHERE acknowledged_at IS NULL"
      ).fetchone()[0]
      # Unfinished tasks feed the rotation's task-count line.
      remaining = db.execute(
        "SELECT count(*) FROM tasks WHERE status <> 'finished'"
      ).fetchone()[0]
      published = db.execute(
        "SELECT count(*) FROM reports WHERE published_at IS NOT NULL"
      ).fetchone()[0]
      stale = self.stale_report_ids(db) if published >= STALE_REPORT_THRESHOLD else []
      cursor = meta_number(db, REMINDER_CURSOR)
      # A new user item resets the count. An idle poll clears it. Reading does not.
      polls = (
        0
        if advance and not (notes + reports + uploads)
        else meta_number(db, POLLS_SINCE_MESSAGE) + (1 if advance else 0)
      )
      blocked = bool(gate_pending_count(db)) and polls >= GATE_THRESHOLD
      if routine:
        db.execute(
          "INSERT OR REPLACE INTO meta VALUES (?, ?)",
          (REMINDER_CURSOR, str(cursor + 1)),
        )
      if advance:
        db.execute(
          "INSERT OR REPLACE INTO meta VALUES (?, ?)", (POLLS_SINCE_MESSAGE, str(polls))
        )
    counts = [
      f"{count} {kind}{'s' if count != 1 else ''}"
      for count, kind in ((notes, "note"), (reports, "answer"), (uploads, "upload"))
      if count
    ]
    # The label keeps the pending tally apart from the call count, so a reader never takes
    # "8. 1 note" for eight notes.
    unacked = [f"unacked {', '.join(counts)}"] if counts else []
    head = ["blocked"] if blocked else [f"calls {polls}"] if polls and counts else []
    tail = reminder_tail(cursor, remaining, len(stale)) if routine else ""
    parts = [" ".join([*head, *unacked]).strip()]
    if order_notice:
      parts.append(TASK_ORDER_NOTICE)
    parts.append(tail)
    return " | ".join(parts).strip(" |")

  def calls_since_message(self):
    """The current debug-call count for a blocked-call message."""
    with closing(self.connect()) as db:
      return meta_number(db, POLLS_SINCE_MESSAGE)

  def gate(self, threshold=GATE_THRESHOLD, pending_only=False):
    """Return False when bash calls must block.

    The count gate holds mid-work commands until the tally passes the threshold.
    `pending_only` drops the tally: a checkpoint like a push waits for any
    unacknowledged item, whatever the count.
    """
    with closing(self.connect()) as db, db:
      pending = gate_pending_count(db)
      polls = meta_number(db, POLLS_SINCE_MESSAGE)
    if pending_only:
      return not pending
    return not (pending and polls >= threshold)

  def read(self, include_quiet=True):
    """Unacknowledged work and unseen quiet notes. Polls exclude quiet notes."""
    quiet_filter = (
      " AND (quiet = 0 OR blocking = 1 OR seen_at IS NULL)"
      if include_quiet
      else " AND quiet = 0"
    )
    with self.transaction(autosave=False) as db:
      pending = [
        message_row(row) | {"kind": "note"}
        for row in db.execute(
          "SELECT * FROM notes WHERE acknowledged_at IS NULL"
          f"{quiet_filter} ORDER BY at, seq"
        )
      ]
      pending += [
        message_row(row) | {"kind": "report"}
        for row in db.execute(
          "SELECT * FROM submissions WHERE acknowledged_at IS NULL ORDER BY at, seq"
        )
      ]
      notes = {}
      for table in ("notes", "submissions"):
        for row in db.execute(f"SELECT * FROM {table} ORDER BY at, seq"):
          record = message_row(row)
          notes[record["id"]] = record
      for row in db.execute("SELECT id, markdown FROM reports"):
        notes[row["id"]] = {"id": row["id"], "text": row["markdown"]}
      for row in db.execute(f"SELECT {TASK_COLUMNS} FROM tasks"):
        task = task_row(row)
        notes[task["id"]] = {
          "id": task["id"],
          "text": "\n".join([task["title"], *task["details"]]),
        }
      attachments = {}
      for row in db.execute("SELECT * FROM uploads ORDER BY seq"):
        record = upload_row(row, self.path.parent)
        attachments.setdefault(record["note_id"], []).append(record)
      for record in notes.values():
        add_note_attachments(record, attachments.get(record["id"], []))
      for item in pending:
        if item["kind"] == "note":
          add_note_attachments(item, attachments.get(item["id"], []))
          thread = reply_thread(item, notes)
          if thread:
            item["thread"] = thread
        for key in ("at", "acknowledged_at", "ack_edited_at", "seen_at"):
          item[key] = clip_stamp(item[key])
      pending.sort(key=lambda item: item["at"])
      checked = now()
      db.execute("INSERT OR REPLACE INTO meta VALUES ('last_check', ?)", (checked,))
      # An armed Skip poll press rides every listing. A read reports it, and the poll that
      # consumes it prints the same stamp.
      waiting = db.execute(
        "SELECT value FROM meta WHERE key = ?", (SKIP_POLL_META,)
      ).fetchone()
      return {
        "checked_at": clip_stamp(checked),
        "pending": pending,
        "skip_poll": clip_stamp(waiting[0]) if waiting else None,
      }

  def mark_seen(self, ids):
    """Receipt the IDs a delivered read printed or an explicit call named."""
    stamp = now()
    with self.transaction() as db:
      for record_id in ids:
        identifier(record_id)
        for table in ("notes", "submissions"):
          cursor = db.execute(
            f"UPDATE {table} SET seen_at = COALESCE(seen_at, ?) WHERE id = ?",
            (stamp, record_id),
          )
          if cursor.rowcount:
            break
        else:
          raise ValueError(f"Unknown note: {record_id}; no Seen receipts written")

  def mark_reports_agent_seen(self, report_ids):
    """Stamp the parent report when a read or an ack delivers its answer.

    The receipt sits beside the owner's seen_at, so the unread star keeps its
    meaning, and the latest read wins so the line describes the current answer.
    """
    stamp = now()
    with self.transaction() as db:
      for report_id in report_ids or []:
        if not report_id:
          continue
        identifier(report_id)
        db.execute(
          "UPDATE reports SET agent_seen_at = ? WHERE id = ?", (stamp, report_id)
        )

  def mark_replies_seen(self, record_id, count):
    "Persist the number of appended replies shown as viewed."
    identifier(record_id)
    if type(count) is not int or count < 0:
      raise ValueError("A viewed-reply count is a nonnegative integer")
    with self.transaction() as db:
      for table in ("notes", "submissions"):
        row = db.execute(
          f"SELECT replies, ack_edited_seen_count FROM {table} WHERE id = ?",
          (record_id,),
        ).fetchone()
        if row is None:
          continue
        reply_count = len(replies_list(row["replies"]))
        if count > reply_count:
          raise ValueError("The viewed-reply count exceeds the current replies")
        seen_count = max(int(row["ack_edited_seen_count"] or 0), count)
        db.execute(
          f"UPDATE {table} SET ack_edited_seen_count = ? WHERE id = ?",
          (seen_count, record_id),
        )
        return {"id": record_id, "ack_edited_seen_count": seen_count}
    raise FileNotFoundError("Message not found")

  def mark_task(self, record_id, task_id, shared=None):
    """Mark the message task and append new attachment paths. Return the updated task when paths change.
    Raise on unknown IDs inside the caller transaction."""
    identifier(record_id)
    identifier(task_id)
    with self.transaction(shared) as db:
      for table in ("notes", "submissions"):
        cursor = db.execute(
          f"UPDATE {table} SET task_id = ? WHERE id = ?", (task_id, record_id)
        )
        if cursor.rowcount:
          if table == "notes":
            uploads = db.execute(
              "SELECT * FROM uploads WHERE note_id = ? ORDER BY seq", (record_id,)
            ).fetchall()
            if uploads:
              stored = db.execute(
                "SELECT details FROM tasks WHERE id = ?", (task_id,)
              ).fetchone()
              details = json.loads(stored["details"]) if stored else []
              paths = [
                f"Attachment: {upload_row(row, self.path.parent)['path']}"
                for row in uploads
              ]
              added = [path for path in paths if path not in details]
              if added:
                return self.write_task(
                  task_id, details=added, append_details=True, shared=db
                )
          return
    raise ValueError(f"Unknown note: {record_id}; no task marker written")

  def pending_ack(self):
    """The one unanswered note or answer a bare `ack` answers.

    Two or more pending items stay ambiguous, so the refusal names them and the ID stays
    the way to answer either one.
    """
    with self.connect() as db:
      rows = db.execute(
        "SELECT id, at FROM notes WHERE acknowledged_at IS NULL AND blocking = 1"
        " UNION ALL SELECT id, at FROM submissions WHERE acknowledged_at IS NULL"
        " ORDER BY at"
      ).fetchall()
    if not rows:
      raise ValueError("No pending note or answer to acknowledge")
    if len(rows) > 1:
      listed = ", ".join(row["id"] for row in rows)
      raise ValueError(
        f"{len(rows)} items are pending: {listed}. Name the ID to answer one"
      )
    return rows[0]["id"]

  def acknowledge(self, ids, text, shared=None):
    """Store the first acknowledgement as a receipt. Append each later reply without replacing earlier text. Use
    `ack_edited_at` for the latest reply stamp."""
    text = note_text(text)
    stamp = now()
    with self.transaction(shared) as db:
      for record_id in ids:
        identifier(record_id)
        for table in ("notes", "submissions"):
          row = db.execute(
            f"SELECT acknowledged_at, replies FROM {table} WHERE id = ?", (record_id,)
          ).fetchone()
          if row is None:
            continue
          if row["acknowledged_at"] is None:
            db.execute(
              f"UPDATE {table} SET acknowledged_at = ?, ack_kind = ?, ack_text = ?,"
              " seen_at = COALESCE(seen_at, ?) WHERE id = ?",
              (stamp, "reply", text, stamp, record_id),
            )
          else:
            more = replies_list(row["replies"]) + [
              {"kind": "reply", "text": text, "at": stamp}
            ]
            db.execute(
              f"UPDATE {table} SET replies = ?, ack_edited_at = ? WHERE id = ?",
              (json.dumps(more, ensure_ascii=False), stamp, record_id),
            )
          if table == "submissions":
            db.execute(
              "UPDATE reports SET agent_seen_at = ?"
              " WHERE id = (SELECT report_id FROM submissions WHERE id = ?)",
              (stamp, record_id),
            )
          break
        else:
          raise ValueError(f"Unknown note: {record_id}; no receipts written")
      # The header labels one stamp as the last read or ack, so an ack writes it too.
      db.execute("INSERT OR REPLACE INTO meta VALUES ('last_check', ?)", (stamp,))
      # An emptied inbox resets the tally now, not at the next hook poll.
      if not gate_pending_count(db):
        db.execute(
          "INSERT OR REPLACE INTO meta VALUES (?, '0')", (POLLS_SINCE_MESSAGE,)
        )

  def guard_report_change(self, db, report_id, report, hold_view=True):
    """Hold an agent change while an answer, acknowledgement, or fresh view is unread.

    The view hold applies to an answered report only: a report nobody answered has nothing to
    disturb, so a look at it never blocks a change. An unpublish passes `hold_view=False`: the
    page keeps the open report on screen, so a removal never empties a reader's view.
    """
    unread = db.execute(
      "SELECT 1 FROM submissions WHERE report_id = ? AND acknowledged_at IS NULL LIMIT 1",
      (report_id,),
    ).fetchone()
    if unread is not None:
      raise ReportHeld("The report has an unacknowledged answer.")
    acknowledged = db.execute(
      "SELECT MAX(acknowledged_at) FROM submissions WHERE report_id = ?",
      (report_id,),
    ).fetchone()[0]
    if acknowledged and not at_or_after(report["ack_seen_at"], acknowledged):
      raise ReportHeld(
        "The report waits for the owner: its answer acknowledgement is unseen."
      )
    if not hold_view:
      return
    answered = db.execute(
      "SELECT 1 FROM submissions WHERE report_id = ? LIMIT 1", (report_id,)
    ).fetchone()
    age = seconds_since(report["viewed_at"])
    if (
      answered is not None and age is not None and 0 <= age < REPORT_CHANGE_VIEW_SECONDS
    ):
      remaining = max(1, int(REPORT_CHANGE_VIEW_SECONDS - age))
      raise ReportHeld(
        f"The owner is reading this report: retry after {remaining} s without a view."
      )

  def publish(self, report_id, title, source):
    identifier(report_id)
    if not isinstance(title, str) or not title.strip() or len(title) > 200:
      raise ValueError("Report title must contain 1–200 characters")
    source = Path(source)
    if source.suffix.lower() != ".md":
      raise ValueError("Publish a UTF-8 .md source file")
    with source.open("rb") as stream:
      data = stream.read(MAX_REPORT + 1)
    if len(data) > MAX_REPORT:
      raise ValueError("Report exceeds the 2 MB limit; split it into reports")
    text = data.decode("utf-8")
    # Embedding runs here, at publication, so the stored text carries every local
    # image and the renderer later reads no file.
    text = embed_report_images(text, source.resolve().parent)
    # Reject invalid fields before publication so the error names the field and preserves the report and connection.
    fields = parse_fields(text)[1]
    with self.transaction() as db:
      report = db.execute(
        "SELECT ack_seen_at, viewed_at FROM reports WHERE id = ?", (report_id,)
      ).fetchone()
      if report is not None:
        self.guard_report_change(db, report_id, report)
      else:
        # Answers survive an unpublish, so their old ID cannot name a new report.
        answered = db.execute(
          "SELECT 1 FROM submissions WHERE report_id = ? LIMIT 1", (report_id,)
        ).fetchone()
        if answered is not None:
          raise ValueError(
            f"Report {report_id} has submitted answers; publish the update under a new ID"
          )
      self.refuse_shared_id(db, "reports", "tasks", report_id)
      highest = db.execute("SELECT COALESCE(MAX(seq), 0) FROM reports").fetchone()[0]
      db.execute(
        """INSERT INTO reports (id, title, markdown, updated_at, published_at, seq)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(id) DO UPDATE SET title = excluded.title,
             markdown = excluded.markdown, updated_at = excluded.updated_at,
             seq = COALESCE(reports.seq, excluded.seq), seen_at = NULL""",
        (report_id, title, text, now(), now(), highest + 1),
      )
    return len(fields)

  def unpublish(self, report_id, dismissed_by_owner=False, *, stale_only=False):
    """Remove only the report tab row. Keep answers and the Markdown source."""
    identifier(report_id)
    with self.transaction() as db:
      if stale_only:
        db.execute("BEGIN IMMEDIATE")
      row = db.execute(
        "SELECT title, ack_seen_at, viewed_at FROM reports WHERE id = ?",
        (report_id,),
      ).fetchone()
      if row is None:
        if stale_only:
          return False
        raise FileNotFoundError("Report not found")
      if stale_only and report_id not in self.stale_report_ids(db):
        return False
      if not dismissed_by_owner:
        # The page holds the open report, so the owner's view never blocks this removal.
        self.guard_report_change(db, report_id, row, hold_view=False)
      db.execute("DELETE FROM reports WHERE id = ?", (report_id,))
      self.release_report_tasks(db, report_id)
      # The state stamp reads this mark, so the save's own stamp trigger rewrites a file that
      # still carries the removed report.
      db.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", (REMOVED_META, now()))
      if dismissed_by_owner:
        # A dismissal informs the agent without waking a poll: the agent looks, it is not
        # roused for a report the owner already read.
        db.execute(
          "INSERT INTO notes (id, text, at, quiet, blocking) VALUES (?, ?, ?, 1, 0)",
          (
            new_id(),
            f"The owner dismissed the report {report_id} ({row['title']}).",
            now(),
          ),
        )

    if stale_only:
      return True

  def clear_state(self):
    """Empty every state table in one transaction and return the row counts.

    Keep the server running and the schema. Autosave updates the save file to match the empty state.
    Copy the state first to keep a backup.

    Keep the agent key record that the page posts on load.
    Keep the recorded server port for the next command's live-server check."""
    guard_task_runs(self.path.parent, action="clear state")
    counts = {}
    with self.transaction() as db:
      for table in (
        "notes",
        "reports",
        "submissions",
        "tasks",
        "uploads",
        "fetch_jobs",
      ):
        counts[table] = db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        db.execute(f"DELETE FROM {table}")
      kept = db.execute(
        "SELECT key, value FROM meta WHERE key IN (?, ?)", (AGENT_KEY_META, "port")
      ).fetchall()
      db.execute("DELETE FROM meta")
      for key, value in kept:
        db.execute("INSERT INTO meta VALUES (?, ?)", (key, value))
    return counts

  def mark_report_seen(self, report_id):
    """Store the first completed report view. Keep that stamp when another browser opens the report. Clear it on
    republish. Keep `ever_seen` so the tab dot waits for a first view."""
    identifier(report_id)
    with self.transaction() as db:
      row = db.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
      if row is None:
        raise FileNotFoundError("Report not found")
      db.execute(
        "UPDATE reports SET seen_at = COALESCE(seen_at, ?), ever_seen = 1 WHERE id = ?",
        (now(), report_id),
      )
      return dict(
        db.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
      )

  def mark_report_ack_seen(self, report_id):
    """Stamp the moment the owner opened a report whose answer carries an agent ack.

    The answer reaches the page as a star and the tab dot, and the open is what clears them.
    The read stamp keeps its own once-only rule, so this one moves on every call: an ack the
    owner has already looked at leaves no mark on a later open.
    """
    identifier(report_id)
    with self.transaction() as db:
      row = db.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
      if row is None:
        raise FileNotFoundError("Report not found")
      db.execute("UPDATE reports SET ack_seen_at = ? WHERE id = ?", (now(), report_id))
      return dict(
        db.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
      )

  def mark_report_viewed(self, report_id, active=True):
    """Stamp the moment the owner's page shows a report, for the unpublish guard.

    The stamp moves on every look, because the guard reads how fresh the last one is rather
    than when the report was first read. A page that hides the report, or a browser that hides
    the page, clears the stamp, so a background look never holds an agent change. The write
    skips the autosave: a view is not saved state, so it neither changes the save file nor the
    state stamp.
    """
    identifier(report_id)
    with closing(self.connect()) as db, db:
      row = db.execute("SELECT 1 FROM reports WHERE id = ?", (report_id,)).fetchone()
      if row is None:
        raise FileNotFoundError("Report not found")
      stamp = now() if active else None
      db.execute("UPDATE reports SET viewed_at = ? WHERE id = ?", (stamp, report_id))
    return {"id": report_id, "viewed_at": clip_stamp(stamp)}

  def report(self, report_id, shared=None):
    identifier(report_id)
    with self.transaction(shared) as db:
      row = db.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
      if row is None:
        raise FileNotFoundError("Report not found")
      return dict(row)

  @staticmethod
  def validate_fields(fields):
    if not 1 <= len(fields) <= 50:
      raise ValueError("A report holds 1–50 fields")
    seen = set()
    for field in fields:
      field_id = field["id"]
      identifier(field_id)
      if field_id in seen:
        raise ValueError(f"Duplicate field ID: {field_id}")
      seen.add(field_id)
      prompt = field["prompt"]
      if not prompt.strip() or len(prompt) > 500:
        raise ValueError("Each prompt is 1–500 characters")
      if field["type"] == "text":
        continue
      options = field["options"]
      if (
        not 1 <= len(options) <= 20
        or len(set(options)) != len(options)
        or any(not option.strip() or len(option) > 200 for option in options)
      ):
        raise ValueError(
          f"{field['type']} fields take 1–20 unique options of 1–200 characters"
        )
      labels = [custom_label(option) for option in options]
      labels = [label for label in labels if label is not None]
      if len(set(labels)) != len(labels):
        raise ValueError(
          f"{field['type']} fields give each free-text option its own label"
        )

  def submit_report(self, report_id, note_id, answers, revision=None):
    if not isinstance(revision, str) or not revision:
      raise ValueError(
        "Report revision required; copy your entries and reload the preview"
      )
    with self.transaction() as db:
      db.execute("BEGIN IMMEDIATE")
      report = self.report(report_id, shared=db)
      if revision != report["updated_at"]:
        raise ReportChanged(
          "Report changed. Your entries are kept; copy them before refreshing, reviewing and resending"
        )
      fields = parse_fields(report["markdown"])[1]
      if not fields:
        raise ValueError("This report has no fields to answer")
      return self.submit(
        report_id, report["title"], fields, note_id, answers, shared=db
      )

  def submit(self, report_id, title, fields, note_id, answers, shared=None):
    if not isinstance(answers, dict):
      raise TypeError("Answers is a JSON object keyed by field ID")
    known = {field["id"] for field in fields}
    unknown = set(answers) - known
    if unknown:
      raise ValueError(f"Unknown field IDs: {', '.join(sorted(unknown))}")
    lines = [f"REPORT {report_id} {title}:"]
    for field in fields:
      field_id = field["id"]
      value = answers.get(field_id)
      if field["type"] == "text":
        if value is None:
          rendered = "(skipped)"
        elif not isinstance(value, str):
          raise ValueError(f"{field_id}: text answers must be strings")
        else:
          rendered = value if value.strip() else "(skipped)"
      elif value is None:
        rendered = "(skipped)"
      elif field["type"] == "choice":
        if value not in field["options"] and not custom_answer(field, value):
          raise ValueError(f"{field_id}: choose one of " + ", ".join(field["options"]))
        rendered = value
      else:
        if (
          not isinstance(value, list)
          or len({item for item in value if isinstance(item, str)}) != len(value)
          or any(
            item not in field["options"] and not custom_answer(field, item)
            for item in value
          )
        ):
          raise ValueError(
            f"{field_id}: pick options only: " + ", ".join(field["options"])
          )
        rendered = ", ".join(value) if value else "(skipped)"
      lines.append(f"  {field['prompt']} ({field_id}): {rendered}")
    return self.submission(note_id, report_id, "\n".join(lines), shared=shared)


def open_link(renderer, tokens, index, options, env):
  token = tokens[index]
  href = token.attrGet("href") or ""
  if href and not href.startswith("#"):
    token.attrSet("target", "_blank")
    token.attrSet("rel", "noopener noreferrer")
  return renderer.renderToken(tokens, index, options, env)


def render_image(renderer, tokens, index, options, env):
  """Retain image alt text before the default renderer runs."""
  pending = list(tokens[index].children or [])
  while pending:
    token = pending.pop()
    if token.type in {"text_special", "code_inline"}:
      token.type = "text"
    elif token.type == "hardbreak":
      token.type = "softbreak"
    pending.extend(token.children or [])
  return renderer.image(tokens, index, options, env)


def has_renderer():
  """Import markdown-it-py on first use. Return whether this interpreter holds it."""
  global HAS_RENDERER
  if HAS_RENDERER is None:
    try:
      import markdown_it  # noqa: F401
    except ImportError:
      HAS_RENDERER = False
    else:
      HAS_RENDERER = True
  return HAS_RENDERER


def require_renderer():
  if not has_renderer():
    raise SystemExit(
      "serve needs markdown-it-py: install it in the preview venv with "
      "`python -m pip install markdown-it-py`, then start the server with that "
      "venv's Python. read, ack and publish work without it."
    )


CODE_BLOCK = re.compile(r"<pre>(.*?)</pre>", re.DOTALL)
CODE_TAG = re.compile(r"<[^>]+>")


# The page's icons are Lucide geometry, vendored inline (ISC. Copyright (c) 2026 Lucide Icons
# and Contributors). A rendered code block carries the copy shape, the twin of the page's own.
ICON_COPY = (
  '<svg class="lucide lucide-copy" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"'
  ' stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"'
  ' focusable="false"><rect width="14" height="14" x="8" y="8" rx="2" ry="2"></rect>'
  '<path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"></path></svg>'
)


def add_copy_buttons(rendered):
  """Add a copy button to each code block. Store code in `data-code` because `innerHTML` cannot hold listeners.
  Encode newlines as `&#10;` for attribute parsing."""

  def replace(match):
    inner = match.group(1)
    code = html.unescape(CODE_TAG.sub("", inner))
    payload = html.escape(code, quote=True).replace("\n", "&#10;")
    button = (
      f'<button type="button" class="copy-code" aria-label="Copy code" title="Copy code" '
      f'data-code="{payload}">{ICON_COPY}</button>'
    )
    return f'<div class="code-block">{button}<pre>{inner}</pre></div>'

  return CODE_BLOCK.sub(replace, rendered)


ESCAPED_FENCE = re.compile(
  r"^(?P<indent>[ \t]*)\\(?P<fence>(?:`{3,}|~{3,}))", re.MULTILINE
)


def unescape_fences(source):
  """Restore a line-leading fence that a backslash hides. Markdown treats that fence as literal text instead of a
  code block. Accept backticks and tildes. Leave other escapes unchanged."""
  return ESCAPED_FENCE.sub(
    lambda match: match.group("indent") + match.group("fence"), source
  )


PARAGRAPH = re.compile(r"<p>.*?</p>", re.DOTALL)
# Only the tag goes: the newline beside it stays, so a pre-wrap paragraph keeps its line break
PARAGRAPH_BREAK = re.compile(r"<br\s*/?>")


def drop_paragraph_breaks(rendered):
  """Remove `<br>` tags from paragraphs and keep source newlines.

  The message log uses `white-space: pre-wrap`, so source newlines already create line breaks.
  Keep `<br>` tags in other elements, including list items."""
  return PARAGRAPH.sub(lambda match: PARAGRAPH_BREAK.sub("", match.group(0)), rendered)


def sized_image(match, validate):
  """Build an escaped `<img>` for a sized image. CommonMark has no size syntax, so this function handles
  `![alt](src =320x200)`. Return None when the renderer rejects it."""
  alt, source, width, height = match.groups()
  if not validate(source):
    return None
  size = f' width="{width}"' + (f' height="{height}"' if height else "")
  return (
    f'<img src="{html.escape(source, quote=True)}"'
    f' alt="{html.escape(alt, quote=True)}"{size} />'
  )


def highlight_markdown(parser):
  """Add markdown-it-mark delimiters (MIT). See assets/markdown-it.LICENSE."""
  from markdown_it.rules_inline.state_inline import Delimiter

  def tokenize(state, silent):
    if silent or state.src[state.pos] != "=":
      return False
    scanned = state.scanDelims(state.pos, True)
    length = scanned.length
    if length < 2:
      return False
    if length % 2:
      state.push("text", "", 0).content = "="
      length -= 1
    for _ in range(0, length, 2):
      state.push("text", "", 0).content = "=="
      if scanned.can_open or scanned.can_close:
        state.delimiters.append(
          Delimiter(
            marker=ord("="),
            length=0,
            token=len(state.tokens) - 1,
            end=-1,
            open=scanned.can_open,
            close=scanned.can_close,
          )
        )
    state.pos += scanned.length
    return True

  def post_process(state):
    groups = [state.delimiters] + [
      meta["delimiters"] for meta in state.tokens_meta if meta and "delimiters" in meta
    ]
    for delimiters in groups:
      lone = []
      for start in delimiters:
        if start.marker != ord("=") or start.end == -1:
          continue
        end = delimiters[start.end]
        for index, nesting in ((start.token, 1), (end.token, -1)):
          token = state.tokens[index]
          token.type = "mark_open" if nesting == 1 else "mark_close"
          token.tag, token.nesting = "mark", nesting
          token.markup, token.content = "==", ""
        previous = state.tokens[end.token - 1]
        if previous.type == "text" and previous.content == "=":
          lone.append(end.token - 1)
      while lone:
        index = lone.pop()
        end = index + 1
        while end < len(state.tokens) and state.tokens[end].type == "mark_close":
          end += 1
        end -= 1
        if index != end:
          state.tokens[index], state.tokens[end] = (
            state.tokens[end],
            state.tokens[index],
          )

  parser.inline.ruler.before("emphasis", "mark", tokenize)
  parser.inline.ruler2.before("emphasis", "mark", post_process)


def render(markdown, breaks=False):
  try:
    from markdown_it import MarkdownIt
    from markdown_it.common.normalize_url import validateLink
  except ImportError as error:
    raise RuntimeError(
      "Markdown rendering needs markdown-it-py. Install it in the preview's venv "
      "and restart the server with that venv's Python; steering still works."
    ) from error
  parser = MarkdownIt("commonmark", {"html": False, "breaks": breaks}).enable(
    ["table", "strikethrough"]
  )
  highlight_markdown(parser)
  parser.add_render_rule("link_open", open_link)
  parser.add_render_rule("image", render_image)
  tagged, images = hold_out(
    markdown, SIZED_IMAGE, lambda match: sized_image(match, validateLink), "image"
  )
  rendered = drop_paragraph_breaks(parser.render(unescape_fences(tagged)))
  return add_copy_buttons(put_back(rendered, images, "image"))


def handler(store):
  from http.server import BaseHTTPRequestHandler

  class Handler(BaseHTTPRequestHandler):
    def setup(self):
      super().setup()
      self.connection.settimeout(15)

    def reply(
      self, status, body, content_type="application/json; charset=utf-8", filename=None
    ):
      # An upload answers with the bytes it stored, so this takes bytes as well as text.
      data = body if isinstance(body, (bytes, bytearray)) else body.encode("utf-8")
      if getattr(self, "ws_request_id", None) is not None:
        self.ws_send(
          1,
          json.dumps(
            {
              "type": "response",
              "id": self.ws_request_id,
              "status": status,
              "body": data.decode("utf-8"),
              "contentType": content_type,
            }
          ).encode(),
        )
        return
      self.send_response(status)
      self.send_header("Content-Type", content_type)
      self.send_header("Content-Length", str(len(data)))
      self.send_header("Cache-Control", "no-store")
      self.send_header("X-Content-Type-Options", "nosniff")
      self.send_header(
        "Content-Security-Policy",
        "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
        # Without this, default-src none blocks every image a report carries.
        "img-src 'self' data: https:; "
        "connect-src 'self' https: ws: wss:; base-uri 'none'; form-action 'self'",
      )
      if filename:
        # A CR or LF here splits the response header. A quote ends the value early.
        safe = header_filename(filename)
        self.send_header("Content-Disposition", f'attachment; filename="{safe}"')
      self.end_headers()
      self.wfile.write(data)

    def problem(self, status, error):
      self.reply(status, json.dumps({"error": str(error)}))

    def ws_send(self, opcode, data):
      size = len(data)
      length = (
        bytes([size])
        if size < 126
        else (
          b"\x7e" + size.to_bytes(2, "big")
          if size < 65536
          else b"\x7f" + size.to_bytes(8, "big")
        )
      )
      self.connection.sendall(bytes([0x80 | opcode]) + length + data)

    def ws_dispatch(self, value):
      import io
      from email.message import Message

      if not isinstance(value, dict):
        raise TypeError("Expected an object")
      if value.get("type") == "pong":
        return
      request_id = value.get("id")
      method, path = value.get("method", "GET"), value.get("path", "")
      body, headers = value.get("body", ""), value.get("headers", {})
      if (
        type(request_id) not in (str, int)
        or len(str(request_id)) > 80
        or method not in ("GET", "POST")
        or not isinstance(path, str)
        or not path.startswith("/api/")
        or urlsplit(path).path == "/api/ws"
        or not isinstance(body, str)
        or not isinstance(headers, dict)
      ):
        raise ValueError("Invalid WebSocket request")
      fields = Message()
      for name in ("Content-Type", "X-Fetch-Claim", "X-Fetch-Source"):
        item = headers.get(name)
        if item is not None:
          if not isinstance(item, str) or "\r" in item or "\n" in item:
            raise ValueError("Invalid request header")
          fields[name] = item
      data = body.encode("utf-8")
      fields["Content-Length"] = str(len(data))
      original = self.path, self.rfile, self.headers
      self.path, self.rfile, self.headers = path, io.BytesIO(data), fields
      self.ws_request_id = request_id
      try:
        (self.do_GET if method == "GET" else self.do_POST)()
      finally:
        self.path, self.rfile, self.headers = original
        del self.ws_request_id

    def websocket(self):
      try:
        origin = urlsplit(self.headers.get("Origin", ""))
      except ValueError:
        self.problem(403, "Invalid WebSocket origin")
        return
      if (
        origin.scheme not in ("http", "https")
        or origin.netloc.lower() != self.headers.get("Host", "").lower()
      ):
        self.problem(403, "WebSocket origin must match the preview")
        return
      if (
        self.headers.get("Upgrade", "").lower() != "websocket"
        or "upgrade"
        not in {
          part.strip() for part in self.headers.get("Connection", "").lower().split(",")
        }
        or self.headers.get("Sec-WebSocket-Version") != "13"
      ):
        self.problem(400, "Expected a version 13 WebSocket upgrade")
        return
      key = self.headers.get("Sec-WebSocket-Key", "")
      try:
        if len(base64.b64decode(key, validate=True)) != 16:
          raise ValueError("Invalid WebSocket key")
      except ValueError as error:
        self.problem(400, error)
        return
      self.protocol_version = "HTTP/1.1"
      self.send_response(101)
      self.send_header("Upgrade", "websocket")
      self.send_header("Connection", "Upgrade")
      self.send_header(
        "Sec-WebSocket-Accept",
        base64.b64encode(
          hashlib.sha1(
            (key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode(),
            usedforsecurity=False,
          ).digest()
        ).decode(),
      )
      self.end_headers()
      self.close_connection = True
      self.connection.settimeout(WS_TICK_SECONDS)
      buffer, message = bytearray(), bytearray()
      fragmented = False
      last_seen = last_heartbeat = time.monotonic()
      try:
        with closing(store.connect()) as db:
          version = db.execute("PRAGMA data_version").fetchone()[0]
          self.ws_send(1, b'{"type":"change"}')
          while True:
            try:
              chunk = self.connection.recv(65536)
              if not chunk:
                return
              buffer.extend(chunk)
              last_seen = time.monotonic()
            except TimeoutError:
              pass
            while len(buffer) >= 2:
              first, second = buffer[:2]
              opcode, final = first & 15, bool(first & 128)
              if first & 112 or not second & 128 or opcode not in (0, 1, 2, 8, 9, 10):
                raise ValueError("Invalid frame")
              size, offset = second & 127, 2
              if size in (126, 127):
                width = 2 if size == 126 else 8
                if len(buffer) < 2 + width:
                  break
                size = int.from_bytes(buffer[2 : 2 + width], "big")
                offset += width
                if size < (126 if width == 2 else 65536) or size >= 2**63:
                  raise ValueError("Invalid frame length")
              if opcode >= 8 and (not final or size > 125):
                raise ValueError("Invalid control frame")
              if size + (len(message) if opcode < 8 else 0) > WS_MAX_MESSAGE:
                self.ws_send(8, (1009).to_bytes(2, "big"))
                return
              if len(buffer) < offset + 4 + size:
                break
              mask = buffer[offset : offset + 4]
              data = bytes(
                v ^ mask[i % 4]
                for i, v in enumerate(buffer[offset + 4 : offset + 4 + size])
              )
              del buffer[: offset + 4 + size]
              if opcode == 8:
                if len(data) == 1:
                  raise ValueError("Invalid close frame")
                if data:
                  code = int.from_bytes(data[:2], "big")
                  if (
                    code
                    not in (
                      1000,
                      1001,
                      1002,
                      1003,
                      1007,
                      1008,
                      1009,
                      1010,
                      1011,
                      1012,
                      1013,
                      1014,
                    )
                    and not 3000 <= code < 5000
                  ):
                    raise ValueError("Invalid close code")
                  data[2:].decode("utf-8")
                self.ws_send(8, data)
                return
              if opcode == 9:
                self.ws_send(10, data)
                continue
              if opcode == 10:
                continue
              if opcode == 2:
                self.ws_send(8, (1003).to_bytes(2, "big"))
                return
              if (opcode == 0) != fragmented:
                raise ValueError("Invalid continuation")
              message.extend(data)
              fragmented = not final
              if final:
                self.ws_dispatch(json.loads(message.decode("utf-8")))
                message.clear()
            current = db.execute("PRAGMA data_version").fetchone()[0]
            if current != version:
              version = current
              self.ws_send(1, b'{"type":"change"}')
            now = time.monotonic()
            if now - last_seen > WS_IDLE_SECONDS:
              self.ws_send(8, (1001).to_bytes(2, "big"))
              return
            if now - last_heartbeat >= WS_HEARTBEAT_SECONDS:
              self.ws_send(1, b'{"type":"heartbeat"}')
              last_heartbeat = now
      except (ValueError, TypeError) as error:
        code = 1007 if isinstance(error, UnicodeDecodeError) else 1002
        try:
          self.ws_send(8, code.to_bytes(2, "big"))
        except OSError:
          pass
      except (OSError, sqlite_api().Error):
        return

    def do_GET(self):
      path = urlsplit(self.path).path
      try:
        if path == "/api/ws":
          self.websocket()
          return
        if path == "/":
          page = (ASSETS / "index.html").read_text(encoding="utf-8")
          page = page.replace(
            "__STYLE__", (ASSETS / "style.css").read_text(encoding="utf-8")
          )
          page = page.replace(
            "__MARKDOWN_SCRIPT__",
            (ASSETS / "markdown-it.min.js").read_text(encoding="utf-8"),
          )
          page = page.replace(
            "__SCRIPT__",
            (ASSETS / "message-markdown.js").read_text(encoding="utf-8")
            + "\n"
            + (ASSETS / "app.js").read_text(encoding="utf-8"),
          )
          self.reply(200, page, "text/html; charset=utf-8")
          return
        if path == "/api/userscript-autosave":
          self.reply(200, json.dumps(store.userscript_snapshot(), ensure_ascii=False))
          return
        if path == "/api/state":
          state = store.state()
          try:
            for item in state["notes"] + [
              ack for report in state["reports"] for ack in report["acknowledgements"]
            ]:
              # No `breaks`: the log sets `white-space: pre-wrap`, so the newline the source carries is the line break.
              # A `<br>` would add a second break beside each source newline.
              if "text" in item:
                item["html"] = render(item["text"])
              if item.get("ack_kind") == "reply" and item.get("ack_text"):
                item["ack_html"] = render(item["ack_text"].replace("\\n", "\n"))
              for reply in item.get("replies") or []:
                if reply["kind"] == "reply":
                  reply["html"] = render(reply["text"].replace("\\n", "\n"))
          except RuntimeError as error:
            state["rendering_error"] = str(error)
          self.reply(200, json.dumps(state, ensure_ascii=False))
          return
        if path == "/api/submissions":
          # The clipboard copy asks for the answer lines on click, scoped to the reports still in
          # the tab. A removed report's answers stay in the database and out of this copy.
          live = {report["id"] for report in store.state()["reports"]}
          self.reply(
            200,
            json.dumps(
              [
                saved_answer_line(record)
                for record in store.submissions()
                if record["report_id"] in live
              ],
              ensure_ascii=False,
            ),
            "application/json; charset=utf-8",
          )
          return
        if path == "/api/copy-state":
          # The copy button requests the server state export in one call.
          # The server stamp names the downloaded state file.
          notes = store.state()["notes"]
          lines, counts = store.state_lines(notes, store.tasks() or {})
          stamps = store.newest_stamps()
          self.reply(
            200,
            json.dumps(
              {
                "text": state_ndjson(lines),
                "counts": counts,
                "stamp": store.newest_stamp(stamps),
                "stamps": {"note": stamps["note"], "task": stamps["task"]},
                # The preview checkout names the repository and its branch, so a saved
                # file carries both, as the userscript's own downloads do.
                "repo": store.path.parent.parent.name,
                "branch": workspace_branch(store.path.parent.parent),
              },
              ensure_ascii=False,
            ),
            "application/json; charset=utf-8",
          )
          return
        if path == "/api/report-sources":
          # The copy button asks for the report lines too, so the clipboard carries the same
          # fields as the save file and a restore rebuilds the report pages from either one.
          self.reply(
            200,
            json.dumps(
              [saved_report_line(record) for record in store.report_sources()],
              ensure_ascii=False,
            ),
            "application/json; charset=utf-8",
          )
          return
        match = re.fullmatch(r"/api/reports/([a-zA-Z0-9_-]{1,80})/(html|source)", path)
        if match:
          report_id, kind = match.groups()
          report = store.report(report_id)
          if kind == "html":
            try:
              body, questions = render_report(report["markdown"])
            except ValueError as error:
              # A report saved before field validation can still fail to render. Do_GET returns its ValueError.
              # Otherwise the connection closes without a response and the tab cannot explain the fetch failure.
              self.problem(500, f"This report cannot be rendered: {error}")
              return
            self.reply(
              200,
              json.dumps(
                {
                  "html": body,
                  "fields": len(questions),
                  "revision": report["updated_at"],
                  "published": report["published_at"] or report["updated_at"],
                  "edited": report["updated_at"],
                },
                ensure_ascii=False,
              ),
            )
            return
          self.reply(
            200, report["markdown"], "text/plain; charset=utf-8", f"{report_id}.md"
          )
          return
        self.problem(404, "Not found")
      except FileNotFoundError as error:
        self.problem(404, error)
      except (OSError, sqlite_api().Error, RuntimeError) as error:
        self.problem(503, error)

    def do_POST(self):
      path = urlsplit(self.path).path
      autosave_post = path in {
        "/api/userscript-autosave",
        "/api/userscript-autosave/compare",
      }
      report_submit = re.fullmatch(r"/api/reports/([a-zA-Z0-9_-]{1,80})/submit", path)
      report_seen = re.fullmatch(r"/api/reports/([a-zA-Z0-9_-]{1,80})/seen", path)
      report_ack_seen = re.fullmatch(
        r"/api/reports/([a-zA-Z0-9_-]{1,80})/ack-seen", path
      )
      report_view = re.fullmatch(r"/api/reports/([a-zA-Z0-9_-]{1,80})/view", path)
      message_replies_seen = re.fullmatch(
        r"/api/messages/([a-zA-Z0-9_-]{1,80})/replies/seen", path
      )
      report_unpublish = re.fullmatch(
        r"/api/reports/([a-zA-Z0-9_-]{1,80})/unpublish", path
      )
      fetch_post = re.fullmatch(
        r"/api/fetch-jobs/([a-zA-Z0-9_-]{1,80})/(renew|result|fail|retry|approve|deny|drop)",
        path,
      )
      note_upload = path == "/api/notes/with-file"
      agent_key_post = path == "/api/key"
      skip_poll_post = path == "/api/skip-poll"
      interrupt_post = path == "/api/agent-interrupt"
      task_order_post = path == "/api/tasks/order"
      fetch_result = bool(fetch_post and fetch_post.group(2) == "result")
      if (
        path
        not in {
          "/api/notes",
          "/api/markdown",
          "/api/fetch-jobs",
          "/api/fetch-jobs/claim",
        }
        and not report_submit
        and not report_seen
        and not report_ack_seen
        and not report_view
        and not message_replies_seen
        and not report_unpublish
        and not note_upload
        and not fetch_post
        and not agent_key_post
        and not skip_poll_post
        and not interrupt_post
        and not task_order_post
        and not autosave_post
      ):
        self.problem(404, "Not found")
        return
      # A composed note carries its files and text in one multipart request.
      content_type = self.headers.get("Content-Type", "")
      if note_upload:
        if not content_type.lower().startswith("multipart/form-data;"):
          self.problem(415, "Expected multipart/form-data")
          return
      elif content_type != "application/json" and not fetch_result:
        self.problem(415, "Expected application/json")
        return
      try:
        if (
          self.headers.get("Transfer-Encoding")
          or len(self.headers.get_all("Content-Length", [])) != 1
        ):
          raise ValueError("Send one Content-Length and no Transfer-Encoding")
        length = int(self.headers.get("Content-Length", "0"))
        if fetch_result:
          with closing(store.connect()) as db:
            store.claimed_fetch(
              db, fetch_post.group(1), self.headers.get("X-Fetch-Claim", "")
            )
        if length <= 0:
          subject = (
            "Upload" if note_upload else "Download" if fetch_result else "Request body"
          )
          self.problem(413, f"{subject} has an invalid length")
          return
        if note_upload:
          with stream_note_attachments(content_type, self.rfile, length) as parsed:
            note = store.note_with_uploads(*parsed)
          for key in ("at", "acknowledged_at", "ack_edited_at", "seen_at"):
            note[key] = clip_stamp(note[key])
          self.reply(201, json.dumps(note, ensure_ascii=False))
          return
        if fetch_result:
          with tempfile.TemporaryFile() as stream:
            data = FileBody(stream)
            remaining = length
            while remaining:
              chunk = self.rfile.read(min(65536, remaining))
              if not chunk:
                raise ValueError("Incomplete request body")
              data.write(chunk)
              remaining -= len(chunk)
            name = parse_qs(urlsplit(self.path).query).get("name", [""])[0]
            record = store.complete_fetch(
              fetch_post.group(1),
              self.headers.get("X-Fetch-Claim", ""),
              name,
              self.headers.get("Content-Type", ""),
              self.headers.get("X-Fetch-Source", ""),
              data,
            )
          for key in ("at", "updated_at"):
            record[key] = clip_stamp(record[key])
          self.reply(201, json.dumps(record, ensure_ascii=False))
          return
        data = self.rfile.read(length)
        if len(data) != length:
          self.problem(400, "Incomplete request body; retry the upload or request")
          return
        payload = json.loads(data)
        if not isinstance(payload, dict):
          self.problem(400, "Expected a JSON object")
          return
        if autosave_post:
          result = (
            store.compare_userscript_save(payload)
            if path.endswith("/compare")
            else store.confirm_userscript_save(payload)
          )
          self.reply(200, json.dumps(result, ensure_ascii=False))
          return
        if agent_key_post:
          candidate = payload.get("key")
          if not isinstance(candidate, str) or not AGENT_KEY_RE.fullmatch(candidate):
            raise ValueError(
              "key must be 20 to 64 letters, digits, dashes or underscores"
            )
          host = payload.get("host")
          if host is not None and (
            not isinstance(host, str) or not AGENT_HOST_RE.fullmatch(host)
          ):
            raise ValueError("host must be one https origin, with no path")
          store.set_agent_key(candidate, host)
          self.reply(200, json.dumps(store.agent_key(), ensure_ascii=False))
          return
        if interrupt_post:
          armed = payload.get("armed", True)
          if not isinstance(armed, bool):
            raise ValueError("armed must be true or false")
          self.reply(
            200,
            json.dumps(
              store.request_interrupt(
                payload.get("tab"), payload.get("report_id"), armed
              ),
              ensure_ascii=False,
            ),
          )
          return
        if skip_poll_post:
          armed = payload.get("skip", True)
          if not isinstance(armed, bool):
            raise ValueError("skip must be true or false")
          self.reply(
            200, json.dumps(store.request_skip_poll(armed), ensure_ascii=False)
          )
          return
        if task_order_post:
          # The page sends the drawn rows alone, so one drop writes the queue order.
          self.reply(
            200, json.dumps(store.reorder_tasks(payload.get("ids")), ensure_ascii=False)
          )
          return
        if path == "/api/fetch-jobs":
          record = store.enqueue_fetch(
            payload.get("url"), payload.get("allow_proxy", False)
          )
          self.reply(201, json.dumps(record, ensure_ascii=False))
          return
        if path == "/api/fetch-jobs/claim":
          self.reply(200, json.dumps({"job": store.claim_fetch()}, ensure_ascii=False))
          return
        if fetch_post:
          job_id, action = fetch_post.groups()
          if action == "renew":
            record = store.renew_fetch(job_id, self.headers.get("X-Fetch-Claim", ""))
          elif action == "fail":
            record = store.fail_fetch(
              job_id, self.headers.get("X-Fetch-Claim", ""), payload.get("error", "")
            )
          elif action in {"approve", "deny"}:
            record = store.decide_fetch(
              job_id, "approved" if action == "approve" else "denied"
            )
          elif action == "drop":
            record = store.drop_fetch(job_id)
          else:
            record = store.retry_fetch(job_id)
          self.reply(200, json.dumps(record, ensure_ascii=False))
          return
        if path == "/api/markdown":
          self.reply(
            200,
            render(owner_text(payload.get("text")), breaks=True),
            "text/html; charset=utf-8",
          )
          return
        if report_seen:
          report = store.mark_report_seen(report_seen.group(1))
          for key in ("updated_at", "seen_at"):
            report[key] = clip_stamp(report[key])
          self.reply(200, json.dumps(report, ensure_ascii=False))
          return
        if report_view:
          # The page stamps a look while it shows a report, and clears on leaving, so the
          # unpublish guard reads a fresh view rather than a first read.
          self.reply(
            200,
            json.dumps(
              store.mark_report_viewed(
                report_view.group(1), payload.get("active", True)
              ),
              ensure_ascii=False,
            ),
          )
          return
        if report_ack_seen:
          report = store.mark_report_ack_seen(report_ack_seen.group(1))
          for key in ("updated_at", "seen_at", "ack_seen_at"):
            report[key] = clip_stamp(report[key])
          self.reply(200, json.dumps(report, ensure_ascii=False))
          return
        if message_replies_seen:
          seen = store.mark_replies_seen(
            message_replies_seen.group(1), payload.get("count")
          )
          self.reply(200, json.dumps(seen, ensure_ascii=False))
          return
        if report_unpublish:
          # The page removes a report only on the owner's two clicks, so the removal
          # writes the inbox note that names it.
          store.unpublish(report_unpublish.group(1), dismissed_by_owner=True)
          self.reply(200, json.dumps({"unpublished": report_unpublish.group(1)}))
          return
        if report_submit:
          note = store.submit_report(
            report_submit.group(1),
            payload.get("id"),
            payload.get("answers"),
            payload.get("revision"),
          )
          for key in ("at", "acknowledged_at", "ack_edited_at", "seen_at"):
            note[key] = clip_stamp(note[key])
          self.reply(201, json.dumps(note, ensure_ascii=False))
          return
        note = store.note(
          payload.get("id"), payload.get("text"), quiet=bool(payload.get("quiet"))
        )
        for key in ("at", "acknowledged_at", "ack_edited_at", "seen_at"):
          note[key] = clip_stamp(note[key])
        self.reply(201, json.dumps(note, ensure_ascii=False))
      except (ReportChanged, FetchChanged, ReportHeld) as error:
        # A held removal is a conflict with the owner's live state, not bad input.
        self.problem(409, error)
      except FileNotFoundError as error:
        self.problem(404, error)
      except (ValueError, TypeError, UnicodeDecodeError) as error:
        self.problem(400, error)
      except (OSError, sqlite_api().Error, RuntimeError) as error:
        self.problem(503, error)

  return Handler


def resolve_repo_root():
  """The first ancestor of this file that holds .git, or the working directory."""
  for parent in Path(__file__).resolve().parents:
    if (parent / ".git").exists():
      return str(parent)
  return str(Path.cwd())


def print_skills():
  try:
    import yaml
  except ImportError as error:
    raise RuntimeError("PyYAML is required; rerun the preview installer") from error
  root = Path(resolve_repo_root())
  skills = {}
  for kind, directory in (
    ("installed", root / ".agents" / "skills"),
    ("repository", root / "skills"),
  ):
    for path in sorted(directory.glob("*/SKILL.md")):
      if kind == "repository" and path.parent.name == "refs":
        continue
      lines = path.read_text(encoding="utf-8-sig").splitlines()
      try:
        if not lines or lines[0].strip() != "---":
          raise ValueError("missing YAML frontmatter")
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
        metadata = yaml.safe_load("\n".join(lines[1:end]))
        if not isinstance(metadata, dict) or not all(
          isinstance(metadata.get(key), str) and metadata[key].strip()
          for key in ("name", "description")
        ):
          raise ValueError("name and description must be nonempty text")
      except (ValueError, StopIteration, yaml.YAMLError) as error:
        raise ValueError(f"Invalid skill metadata in {path}: {error}") from error
      name = metadata["name"]
      skills.setdefault(name.casefold(), (name, kind, path, metadata["description"]))
  for name, kind, path, description in skills.values():
    print(f"{name} [{kind}] {path}\n{description}\n")


def resolve_state_dir():
  "ARENA_PREVIEW_STATE_DIR wins. Otherwise the repository arena-state."
  configured = os.environ.get("ARENA_PREVIEW_STATE_DIR")
  if configured:
    return configured
  for parent in Path(__file__).resolve().parents:
    if (parent / ".git").exists():
      return str(parent / "arena-state")
  return "arena-state"


def ensure_installed():
  """Run the installer once when the shim is absent from PATH.

  Restore the shim and hooks before continuing the preview command.
  Skip installation in a guarded run or a checkout without the live skill."""
  if os.environ.get("ARENA_PREVIEW_NO_BOOTSTRAP") or shutil.which("arena-preview"):
    return
  for ancestor in Path(__file__).resolve().parents:
    installer = (
      ancestor / ".agents" / "skills" / "arena-skill" / "scripts" / "install.sh"
    )
    if installer.is_file():
      try:
        subprocess.run(["bash", str(installer)], cwd=str(ancestor), check=False)
      except OSError:
        pass
      return


def image_payload(path: Path) -> tuple:
  """Check one local image and return its MIME type and Base64 bytes.

  Publication and the CLI helper share these checks, so a pasted or published
  image meets the same type rules and the same 2 MiB cap.
  """
  if not path.is_file():
    raise ValueError(f"{path} is not a file")
  size = path.stat().st_size
  if size > IMAGE_DATA_URI_MAX_BYTES:
    raise ValueError(
      f"{path} is {size} bytes; the data URI cap is {IMAGE_DATA_URI_MAX_BYTES} bytes"
    )
  try:
    with path.open("rb") as image:
      data = image.read(IMAGE_DATA_URI_MAX_BYTES + 1)
  except OSError as error:
    raise ValueError(f"Cannot read {path}: {error.strerror or error}") from None
  if len(data) > IMAGE_DATA_URI_MAX_BYTES:
    raise ValueError(
      f"{path} exceeds the data URI cap of {IMAGE_DATA_URI_MAX_BYTES} bytes"
    )
  if data.startswith(b"\x89PNG\r\n\x1a\n"):
    mime = "image/png"
  elif data.startswith(b"\xff\xd8\xff"):
    mime = "image/jpeg"
  elif data.startswith((b"GIF87a", b"GIF89a")):
    mime = "image/gif"
  elif data.startswith(b"RIFF") and data[8:12] == b"WEBP":
    mime = "image/webp"
  else:
    raise ValueError(
      f"{path} is not a supported image; the allowed types are PNG, JPEG, GIF and WebP"
    )
  encoded = base64.b64encode(data).decode("ascii")
  return mime, encoded


def image_data_uri(path: Path) -> str:
  """Read one image file and return Markdown text that carries it as a data URI."""
  mime, encoded = image_payload(path)
  alt = path.stem.replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]")
  return f"![{alt}](data:{mime};base64,{encoded})"


# An inline image destination, with the optional title or ` =WxH` suffix that follows it.
IMAGE_IN_MARKDOWN = re.compile(r"!\[([^\]\n]*)\]\(\s*(<[^>]+>|[^)\s]+)([^)\n]*)\)")


def embed_report_images(markdown, report_dir):
  """Rewrite report images for publication: local bytes become data URIs.

  The owner boundary allows any readable local image, including absolute paths
  and parent directories. A remote source becomes a hint, because publication
  fetches nothing. Publication skips a local file that fails the shared checks.
  Plain links and data URIs keep their original text, and the renderer reads no
  file: the stored text already carries the bytes.
  """

  def swap(match):
    alt, destination, suffix = match.groups()
    source = destination[1:-1] if destination.startswith("<") else destination
    if source.startswith("data:"):
      return match.group(0)
    if source.startswith("//") or re.match(r"[a-zA-Z][a-zA-Z0-9+.-]*:", source):
      return (
        f"Publication skips remote image {source}. Fetch it locally, then embed"
        " it with arena-preview image-data-uri."
      )
    path = Path(source)
    if not path.is_absolute():
      path = report_dir / path
    try:
      mime, encoded = image_payload(path)
    except ValueError as error:
      return (
        f"Publication skips local image {source}: {error}. Run"
        " arena-preview image-data-uri for the helper."
      )
    return f"![{alt}](data:{mime};base64,{encoded}{suffix})"

  return IMAGE_IN_MARKDOWN.sub(swap, markdown)


class PreviewArgumentParser(argparse.ArgumentParser):
  def print_usage(self, file=None):
    pass

  def exit(self, status=0, message=None):
    super().exit(
      status, message.removeprefix("arena-preview: ") if message else message
    )


def main():
  parser = PreviewArgumentParser(description=CLI_DESCRIPTION, prog="arena-preview")
  parser.add_argument(
    "-r",
    "--reminder",
    action="store_true",
    help="Print the unacked-count reminder line and exit",
  )
  commands = parser.add_subparsers(dest="command", required=False)
  serve = commands.add_parser("serve", help="Serve the preview page; -p names the port")
  serve.add_argument(
    "-p",
    "--port",
    type=int,
    default=DEFAULT_PORT,
    help=f"Port to bind (default: {DEFAULT_PORT})",
  )
  init = commands.add_parser("init", help="Create the state directory and its database")
  init.add_argument("--tz", help="An IANA zone for CLI stamps. The TZ env still wins")
  commands.add_parser("read", help="Print every pending note, answer and upload")
  commands.add_parser(
    "interrupt-tick", help="Read the header request without blocking Bash"
  )
  commands.add_parser(
    "skills",
    help="List skill names, full descriptions, and paths without loading skills",
  )
  note_list = commands.add_parser(
    "note-list",
    help="List stored note IDs by page, newest first, including acknowledged notes",
  )
  note_list.add_argument("--page", type=int, default=1, help="Page number (default: 1)")
  note_list.add_argument(
    "--page-size", type=int, default=20, help="IDs per page, 1 to 100 (default: 20)"
  )
  note_reread = commands.add_parser(
    "note",
    help="Reread a stored note by its short or full ID",
  )
  note_reread.add_argument("id", help="Six or all characters of a note ID")
  image_uri = commands.add_parser(
    "image-data-uri",
    help="Print Markdown text that carries one local image as a data URI",
  )
  image_uri.add_argument(
    "path", type=Path, help="One local PNG, JPEG, GIF or WebP file up to 2 MiB"
  )
  commands.add_parser("key", help="Print the recorded agent key, host and use line")
  pr_state = commands.add_parser("pr-state-tick", help="Reject visible PR-state writes")
  pr_state.add_argument("line", help="The command as the DEBUG hook read it")
  inbox_line = commands.add_parser(
    "inbox-line",
    help="Report whether a command line that names an inbox call runs nothing else",
  )
  inbox_line.add_argument("line", help="The command line, as the hook read it")
  read_set_tick_parser = commands.add_parser(
    "read-set-tick", help="Schedule a hidden read-set checkpoint before agent work"
  )
  read_set_tick_parser.add_argument(
    "line", help="The command line, as the hook read it"
  )
  read_set_tick_parser.add_argument("--repo", default=".")
  route = commands.add_parser(
    "route",
    help=(
      "Start a command detached, keep its output tail, and show the exit on a later"
      " call"
    ),
  )
  route.add_argument(
    "--task",
    dest="task_id",
    metavar="TASK-ID",
    help="Link this run to an upcoming task instead of the current task",
  )
  route.add_argument("name", help="A short name for the run, for example gates")
  route.add_argument(
    "command_args", nargs=argparse.REMAINDER, help="The command, after --"
  )
  # The child side of `route`. The gate and the CLI both spawn it, so one place runs
  # the command and writes the finished record.
  route_run = commands.add_parser(
    "route-run",
    help="Run one command here and record its exit for a later call",
  )
  route_run.add_argument("name", help="The run name the caller already recorded")
  route_run.add_argument(
    "command_args", nargs=argparse.REMAINDER, help="The command, after --"
  )
  logs = commands.add_parser(
    "logs", help="Print a routed run's status and its recorded output tail"
  )
  logs.add_argument("name", help="The run name to read")
  worktree = commands.add_parser(
    "worktree", help="Create or collect a detached task worktree beside a root gate"
  )
  worktree_action = worktree.add_subparsers(dest="worktree_action", required=True)
  worktree_start = worktree_action.add_parser(
    "start", help="Create a detached worktree while a named root gate runs"
  )
  worktree_start.add_argument("name", help="A short worktree name")
  worktree_start.add_argument(
    "destination", type=Path, help="A new path outside the root"
  )
  worktree_start.add_argument(
    "--gate", required=True, help="The running root gate name"
  )
  worktree_start.add_argument(
    "--allow", action="append", default=[], help="A path glob task work may change"
  )
  worktree_collect = worktree_action.add_parser(
    "collect", help="Print the allowed detached-worktree patch after a green root gate"
  )
  worktree_collect.add_argument("name", help="The worktree name to collect")
  worktree_tick = commands.add_parser(
    "worktree-tick", help="Block a gate, commit or push from a detached task worktree"
  )
  worktree_tick.add_argument("action", choices=sorted(WORKTREE_ACTIONS))
  ack_tick = commands.add_parser(
    "ack-tick",
    help="Warn when an inline ack text holds a backtick the shell will substitute",
  )
  ack_tick.add_argument("line", help="The command line, as the hook read it")
  idle_tick = commands.add_parser(
    "idle-tick", help="Refuse a line that sleeps beside a preview call"
  )
  idle_tick.add_argument("line", help="The command line, as the hook read it")
  serve_tick = commands.add_parser(
    "serve-tick",
    help="Warn when a serve names a port other than the default",
  )
  serve_tick.add_argument("line", help="The command line, as the hook read it")
  pr_check_tick = commands.add_parser(
    "pr-check-tick",
    help="Refuse a bash line that runs a PR-check wait the background tool must take",
  )
  pr_check_tick.add_argument("line", help="The command line, as the hook read it")
  pr_check_tick.add_argument(
    "--command", dest="current_command", help="The command the DEBUG trap reached"
  )
  main_drift_tick = commands.add_parser(
    "main-drift-tick", help="Check remote branch drift at commit and push checkpoints"
  )
  main_drift_tick.add_argument("--repo", default=".")
  main_drift_tick.add_argument(
    "--local",
    dest="local_read",
    action="store_true",
    help="Read the local refs alone, with no fetch",
  )
  egress_tick = commands.add_parser(
    "egress-tick",
    help="Warn when a line fetches a host the sandbox egress filter blocks",
  )
  egress_tick.add_argument("line", help="The command line, as the hook read it")
  rename = commands.add_parser(
    "rename",
    help="Move a note, answer, report or task to a new ID",
  )
  rename.add_argument("old_id", help="The stored ID, or a prefix that names one record")
  rename.add_argument("new_id", help="The ID to move the record to")
  commit_tick = commands.add_parser(
    "commit-tick",
    help="Block a commit whose staged lines cite a session-local ID",
  )
  commit_tick.add_argument(
    "--repo", default=".", help="The repository to read the staged diff from"
  )
  gate = commands.add_parser(
    "gate",
    help="Read the inbox gate; -p blocks on any unacked note, -l names the blocked line",
  )
  gate.add_argument(
    "-p",
    "--push",
    action="store_true",
    help="Block while any note or answer awaits an ack, whatever the call count",
  )
  gate.add_argument(
    "-l",
    "--line",
    default="",
    help="The command line, as the hook read it; a blocked call then names the commands to drop",
  )
  commands.add_parser(
    "poll", help="Block until the owner answers or a gate run finishes"
  )
  download = commands.add_parser(
    "download-request",
    help=(
      "Request an HTTPS browser download, pending a preview Approve click;"
      " -a allows the proxy fallback"
    ),
  )
  download.add_argument("url", help="One HTTPS URL without embedded credentials")
  download.add_argument(
    "-a",
    "--allow-proxy",
    action="store_true",
    help="Let the owner opt in to AllOrigins and CodeTabs fallback for this request",
  )
  ack = commands.add_parser(
    "ack",
    help="Answer notes with inline Markdown; omit IDs for one pending item",
  )
  ack.add_argument("ids", nargs="*")
  ack.add_argument("markdown", help="Literal inline Markdown answer")
  ack.add_argument("--task-id")
  ack.add_argument("--task-title")
  ack.add_argument("--task-type", choices=TASK_TYPES)
  ack.add_argument("--task-detail", action="append")
  publish = commands.add_parser(
    "publish", help="Publish a report; -i names the ID, -t the title"
  )
  publish.add_argument("source", type=Path)
  publish.add_argument("-i", "--id", required=True)
  publish.add_argument("-t", "--title", required=True)
  report = commands.add_parser("report", help="Report batch actions")
  report_actions = report.add_subparsers(dest="report_action", required=True)
  report_unpublish = report_actions.add_parser(
    "unpublish", help="Remove stale reports through existing guards"
  )
  report_unpublish.add_argument("--stale", action="store_true", required=True)
  unpublish = commands.add_parser(
    "unpublish", help="Withdraw a published report by its ID"
  )
  unpublish.add_argument("report_id")
  commands.add_parser(
    "stale-reports",
    help="List stale published report IDs and reasons without changing state",
  )
  report_state = commands.add_parser(
    "report-state",
    help="Print publication, owner view stamp and answer visibility for one report or all",
  )
  report_state.add_argument("report_id", nargs="?")
  task = commands.add_parser(
    "task",
    help=(
      "Write or update a task; TASK-ID alone prints the stored row; -s status,"
      " -o order, -d details, -A append, -m message, -r report, -u unblocked,"
      " -a amend, --task-type type"
    ),
  )
  task.add_argument("id_arg", nargs="?", metavar="TASK-ID")
  task.add_argument("title_arg", nargs="?", metavar="TASK-TITLE")
  task.add_argument("detail_arg", nargs="*", metavar="TASK-DETAIL")
  task.add_argument(
    "-d",
    "--details",
    "--task-details",
    dest="task_details",
    action="append",
    help="One step per line, 120 characters or fewer, repeatable",
  )
  task.add_argument(
    "-A",
    "--append",
    dest="append_details",
    action="store_true",
    help="Append provided details instead of replacing stored details",
  )
  task.add_argument(
    "-u",
    "--unblocked",
    dest="blocked",
    action="store_false",
    default=None,
    help="Clear a report wait or legacy blocked mark",
  )
  task.add_argument(
    "-m",
    "--msg-id",
    help="Message this task answers; marks that message as having a task",
  )
  task.add_argument(
    "-r",
    "--report",
    metavar="REPORT-ID",
    help="Report this task waits on; its answer clears the blocked mark",
  )
  task.add_argument(
    "-a",
    "--amend",
    metavar="PREV-ID",
    help="Rename the task stored under this ID to the one given",
  )
  task.add_argument("-s", "--status", choices=TASK_STATUSES, default=None)
  task.add_argument(
    "--task-type",
    dest="task_type",
    choices=TASK_TYPES,
    default=None,
    help="Primary deliverable type; an omitted flag keeps a stored type",
  )
  task.add_argument(
    "-o",
    "--order",
    type=int,
    default=None,
    help="1-based place in its div, not the end",
  )
  task_remove = commands.add_parser("task-remove", help="Delete a task by its ID")
  task_remove.add_argument("task_id")
  task_list = commands.add_parser(
    "task-list", help="List the tasks; -f includes the finished ones"
  )
  task_list.add_argument(
    "-f", "--full", action="store_true", help="print every task, finished included"
  )
  state_import = commands.add_parser(
    "import-state",
    help="Import an NDJSON backup; replaces the live state unless --merge",
  )
  state_import.add_argument("source", nargs="?", type=Path)
  state_import.add_argument("-r", "--replace-tasks", action="store_true")
  state_import.add_argument(
    "--merge",
    action="store_true",
    help="keep the live notes, answers, reports and tasks, and merge the import by ID",
  )
  commands.add_parser(
    "clear-state",
    help="Empty every state table in place; the agent key record survives",
  )
  args = parser.parse_args()
  state_dir = resolve_state_dir()
  # Read before the store opens: creating the database is what this call reports.
  fresh_state = not (Path(state_dir).resolve() / "state.sqlite3").is_file()
  try:
    if args.reminder:
      store = Store(state_dir, create=False)
      require_server(store)
      reminder = store.reminder(advance=True)
      # The hook runs this after every bash call, so the stamp marks the call's end: the
      # page keeps the long call text only while a call started after the last recorded end.
      store.set_meta(AGENT_CALL_ENDED_META, now())
      # A pending inbox item outranks a routed status. Otherwise one routed status or one
      # reminder line is enough for the agent to act.
      if (
        "unacked " in reminder
        or TASK_ORDER_NOTICE in reminder
        or not run_notices(state_dir, show_running=True)
      ):
        print(reminder, file=sys.stderr, flush=True)
      return 0
    if not args.command:
      parser.error(
        "a command is required; run arena-preview --help for the command list"
      )
    if args.command == "read-set-tick":
      if fresh_state:
        return 0
      tick_store = Store(state_dir)
      warning = read_set_tick(
        tick_store,
        args.line,
        moment=datetime.now(resolve_display_zone(tick_store)),
        root=args.repo,
      )
      if warning:
        print(warning, file=sys.stderr)
        return 1
      return 0
    if args.command == "interrupt-tick":
      if fresh_state:
        return 0
      notice = Store(state_dir, create=False).take_interrupt()
      if notice:
        print(notice, file=sys.stderr)
        return 1
      return 0
    if args.command == "skills":
      print_skills()
      return 0
    if args.command == "pr-state-tick":
      warning = pr_state_warning(args.line)
      if warning:
        print(warning, file=sys.stderr)
        return 1
      return 0
    if args.command == "inbox-line":
      return 0 if quiet_inbox_line(args.line) else 1
    if args.command == "image-data-uri":
      try:
        print(image_data_uri(args.path))
      except ValueError as error:
        print(error, file=sys.stderr)
        return 1
      return 0
    if args.command == "worktree-tick":
      warning = worktree_warning(state_dir, args.action)
      if warning:
        print(warning, file=sys.stderr)
        return 1
      return 0
    if args.command == "worktree":
      if args.worktree_action == "start":
        record = start_worktree(
          state_dir, args.name, args.destination, args.gate, args.allow
        )
        print(f"Worktree {record['name']} at {record['worktree']}")
        return 0
      print(collect_worktree(state_dir, args.name), end="")
      return 0
    if args.command == "route":
      warning = worktree_warning(state_dir, "gate")
      if warning:
        print(warning, file=sys.stderr)
        return 1
      return route_command(
        state_dir, args.name, args.command_args, task_id=args.task_id
      )
    if args.command == "route-run":
      warning = worktree_warning(state_dir, "gate")
      if warning:
        print(warning, file=sys.stderr)
        return 1
      return run_command(state_dir, args.name, args.command_args)
    if args.command == "logs":
      return run_log_report(state_dir, args.name)
    if args.command == "ack-tick":
      warning = tick_warning(args.line)
      if warning:
        print(warning, file=sys.stderr)
      return 0
    if args.command == "idle-tick":
      warning = idle_wait(args.line)
      if warning:
        print(warning, file=sys.stderr)
        return 1
      return 0
    if args.command == "serve-tick":
      warning = serve_warning(args.line)
      if warning:
        print(warning, file=sys.stderr)
      return 0
    if args.command == "main-drift-tick":
      warning = main_drift_warning(args.repo, fresh=not args.local_read)
      if warning:
        print(warning, file=sys.stderr)
      return 0
    if args.command == "egress-tick":
      warning = egress_warning(args.line)
      if warning:
        print(warning, file=sys.stderr)
      return 0
    if args.command == "pr-check-tick":
      return pr_check_wait(state_dir, args.line, args.current_command)
    if args.command == "rename":
      require_server(Store(state_dir))
      try:
        old_id = Store(state_dir).resolve_id(args.old_id)
      except FileNotFoundError:
        print(
          f"No note, answer, report or task holds the ID {args.old_id}", file=sys.stderr
        )
        return 1
      except ValueError as error:
        print(error, file=sys.stderr)
        return 1
      try:
        kind = Store(state_dir).rename_entity(old_id, args.new_id)
      except ValueError as error:
        print(error, file=sys.stderr)
        return 1
      print(f"ok {kind} {old_id} -> {args.new_id}")
      return 0
    if args.command == "commit-tick":
      warning = worktree_warning(state_dir, "commit", cwd=args.repo)
      if warning:
        print(warning, file=sys.stderr)
        return 1
      try:
        store = Store(state_dir)
      except FileNotFoundError:
        return 0
      report = commit_id_report(staged_session_id_hits(store, args.repo))
      if report:
        print(report, file=sys.stderr)
        return 1
      return 0
    if args.command == "gate":
      # Finished runs announce here. The running heartbeat rides the reminder alone, so a
      # call prints one status line, not one per gated command plus one at exit.
      run_notices(state_dir)
      if poll_timeout_line(args.line):
        print(
          "TIMEOUT BANNED: never wrap `arena-preview poll` in shell `timeout`."
          " Set the Bash tool timeout to 1800 seconds; the poll returns within"
          " its 1799-second wait.",
          flush=True,
        )
        return 1
      try:
        gate_store = Store(state_dir)
        allowed = gate_store.gate(pending_only=args.push)
        blocked_calls = (
          gate_store.calls_since_message() if not allowed and not args.push else None
        )
      except FileNotFoundError:
        allowed = True
        blocked_calls = None
      except Exception:
        return 2
      if not allowed:
        if blocked_calls is not None:
          print(f"BASH BLOCKED AFTER {blocked_calls} CALLS.", flush=True)
        if args.push:
          # Name the pending item and the steps that allow the push.
          print(
            "PUSH BLOCKED: a note or answer awaits an ack, so nothing left the"
            " sandbox. Read the inbox, ack every item, push again.",
            flush=True,
          )
        print(
          "READ INBOX NOW. Only a bare `arena-preview read` passes. Then ack"
          " every note: `arena-preview ack <id> <markdown>`.",
          flush=True,
        )
        hint = gate_line_hint(args.line)
        if hint:
          print(hint, flush=True)
        blocker = first_blocking_piece(args.line)
        if blocker:
          blocker = shell_command_text(blocker)
          print(
            f"Blocked by the part `{blocker}`. Run the inbox calls alone, or drop this part.",
            flush=True,
          )
        return 1
      # A push whose content equals origin/main leaves the pull request without a diff,
      # and GitHub then closes it. The checkpoint holds before any such push.
      if args.push and main_identical():
        print(
          "HEAD equals `origin/main`, so the push carries nothing."
          " Start new work from `origin/main`.",
          flush=True,
        )
        return 1
      # A branch that lacks the commits origin/main carries replays onto a stale base,
      # and the pull request then shows the main diff. The checkpoint holds that push.
      stale = main_ancestor_warning() if args.push else ""
      if stale:
        print(stale, flush=True)
        return 1
      return 0
    store = Store(
      state_dir,
      create=args.command in {"serve", "init", "import-state"},
    )
    global DISPLAY_ZONE
    DISPLAY_ZONE = resolve_display_zone(store)
    # Every state command breaks while no preview answers. Only the setup pair
    # stays open so the recovery command itself always runs.
    if args.command not in {"serve", "init"}:
      require_server(store)
    read_only = args.command in {"stale-reports", "note-list", "report-state"}
    if not read_only:
      routine = (
        os.environ.get("ARENA_PREVIEW_SHELL_HOOK") != "1"
        or os.environ.get("ARENA_PREVIEW_ROUTE") == "1"
      )
      reminder = store.reminder(routine=routine)
      if reminder:
        print(reminder, file=sys.stderr, flush=True)
    if args.command != "serve" and not read_only:
      # Store the agent CLI call as a durable debug-trap signal.
      # A preview left open after a turn then reports no agent activity.
      store.touch_agent()
    if args.command == "serve":
      from http.server import ThreadingHTTPServer

      require_renderer()
      with ThreadingHTTPServer(("0.0.0.0", args.port), handler(store)) as server:
        store.set_meta("port", str(server.server_port))
        print(
          f"Preview on 0.0.0.0:{server.server_port}; state: {store.path}",
          flush=True,
        )
        server.serve_forever()
    elif args.command == "read":
      require_server(store)
      store.notice_expired_key()
      print_read(store)
    elif args.command == "note-list":
      ids, total = store.list_note_ids(args.page, args.page_size)
      pages = max(1, (total + args.page_size - 1) // args.page_size)
      if args.page > pages:
        print(f"Page {args.page} is past the last page ({pages}).", file=sys.stderr)
        return 1
      print(f"Notes page {args.page}/{pages} ({total} total; newest first)")
      for note_id in ids:
        print(note_id)
    elif args.command == "note":
      # The read lists the pending notes. This one reaches the acked history, so
      # a note stays open to the agent after its answer lands.
      rows = store.notes_matching(args.id)
      if not rows:
        print(f"No note matches {args.id}.", file=sys.stderr)
        return 1
      for row in rows:
        head = f"note {row['id']} at {local_stamp(row['at'])}"
        head += (
          f" acked {local_stamp(row['acknowledged_at'])}"
          if row["acknowledged_at"]
          else " unacked"
        )
        print(head)
        print(row["text"])
        print()
    elif args.command == "key":
      # The key note is quiet and it ages out of the pending list after an ack, so a later
      # session reads the recorded key here instead of waiting for a new note.
      record = store.agent_key()
      if not record:
        print("No agent key recorded.", file=sys.stderr)
        return 1
      print(format_key(record))
    elif args.command == "poll":
      require_server(store)
      store.notice_expired_key()
      return poll_inbox(store)
    elif args.command == "download-request":
      # The agent path is pending. The browser form keeps its existing immediate queue path.
      print(
        format_fetch_job(store.enqueue_fetch(args.url, args.allow_proxy, pending=True))
      )
    elif args.command == "ack":
      if args.markdown == "-":
        raise ValueError(
          "Pass literal inline Markdown; acknowledgement stdin is not supported"
        )
      text = args.markdown
      ids = (
        [store.resolve_id(token) for token in args.ids]
        if args.ids
        else [store.pending_ack()]
      )
      task_options = (args.task_id, args.task_title, args.task_type, args.task_detail)
      if any(value is not None for value in task_options):
        if len(args.ids) != 1 or not all(task_options):
          raise ValueError(
            "A combined acknowledgement needs one explicit message ID and all four task options"
          )
        details = task_steps(args.task_detail)
        check_task_steps(details)
        with store.transaction() as shared:
          store.write_task(
            args.task_id,
            args.task_title,
            details,
            task_type=args.task_type,
            shared=shared,
          )
          store.acknowledge(ids, text, shared=shared)
          store.mark_task(ids[0], args.task_id, shared=shared)
      else:
        store.acknowledge(ids, text)
      short = [i[:6] for i in ids]
      print("ok " + " ".join(short))
      untracked = [
        record_id
        for record_id in ids
        if not any(
          record.get("task_id")
          for _, record in store.id_matches(record_id)
          if record["id"] == record_id
        )
      ]
      if untracked:
        print(
          "link it with: "
          + "; ".join(f'arena-preview task <id> "<title>" -m {i}' for i in untracked)
        )
    elif args.command == "publish":
      count = store.publish(args.id, args.title, args.source)
      revision = store.report(args.id)["updated_at"]
      verify_publication(store, args.id, revision, count)
      plural = "" if count == 1 else "s"
      print(f"Published {args.id}, {count} field{plural}. Verification passed.")
      if not count and "{#" in Path(args.source).read_text("utf-8"):
        # A `{#id}` marker on its own parses as prose. The owner then sees no answer form.
        print(
          "Warning: 0 fields parsed. A `{#id}` marker ends a prompt line, then"
          " the `- ( ) option` lines follow.",
          file=sys.stderr,
        )
    elif args.command == "report":
      held = False
      for record in store.stale_reports():
        report_id = record["id"]
        try:
          removed = store.unpublish(report_id, stale_only=True)
        except ReportHeld as error:
          print(f"Skipped {report_id}: {error}", file=sys.stderr)
          held = True
          continue
        if removed:
          print(f"Unpublished {report_id}. Answers and source file remain.")
        else:
          print(f"Skipped {report_id}: no longer stale or published.")
      return 1 if held else 0
    elif args.command == "unpublish":
      report_id = store.resolve_id(args.report_id)
      store.unpublish(report_id)
      print(f"Unpublished {report_id}. Answers and source file remain.")
    elif args.command == "stale-reports":
      reports = store.stale_reports()
      print(f"Stale reports {len(reports)}")
      for report in reports:
        print(f"{report['id']}\t{report['reason']}")
    elif args.command == "report-state":
      rows = store.report_state(args.report_id)
      if args.report_id and not rows:
        print(f"No report {args.report_id}", file=sys.stderr)
        raise SystemExit(1)
      print(format_report_state(rows), end="")
    elif args.command == "task":
      task_id = args.id_arg
      if not task_id:
        raise ValueError(
          'A task needs an ID: arena-preview task <id> "<title>" -m <msg-id>'
        )
      if (
        args.title_arg is None
        and not args.detail_arg
        and args.task_details is None
        and not args.append_details
        and args.status is None
        and args.order is None
        and args.blocked is None
        and args.report is None
        and args.msg_id is None
        and args.amend is None
        and args.task_type is None
      ):
        # A bare ID reads the stored row without writing. An ID that names nothing at
        # all reads as a task miss here, since this is the task command.
        if not store.id_matches(task_id):
          raise ValueError(f"No task is stored under {task_id}.")
        resolved = store.resolve_id(task_id)
        tasks = store.tasks() or {}
        record = next(
          (
            item
            for status in TASK_STATUSES
            for item in tasks.get(status, [])
            if item["id"] == resolved
          ),
          None,
        )
        if record is None:
          raise ValueError(f"No task is stored under {resolved}.")
        print(format_task(record, full=True))
        return 0
      details = args.task_details
      if details is None and args.detail_arg:
        details = args.detail_arg
      if details is not None:
        details = task_steps(details)
        check_task_steps(details)
      if args.amend:
        store.amend_task(store.resolve_id(args.amend), task_id)
      if args.report:
        try:
          store.report(args.report)
        except FileNotFoundError:
          raise ValueError(f"No report is stored under {args.report}") from None
        if args.blocked is None:
          args.blocked = True
      if args.msg_id:
        # One transaction: a message ID that matches nothing takes the task with it, rather than
        # leaving a task whose marker never landed.
        with store.transaction() as shared:
          record = store.write_task(
            task_id,
            args.title_arg,
            details,
            args.status,
            args.order,
            args.blocked,
            args.report,
            task_type=args.task_type,
            shared=shared,
            append_details=args.append_details,
          )
          record = store.mark_task(args.msg_id, task_id, shared=shared) or record
      else:
        record = store.write_task(
          task_id,
          args.title_arg,
          details,
          args.status,
          args.order,
          args.blocked,
          args.report,
          task_type=args.task_type,
          append_details=args.append_details,
        )
      print(format_task(record))
    elif args.command == "task-remove":
      print(format_task(store.remove_task(store.resolve_id(args.task_id))))
    elif args.command == "task-list":
      print(format_task_list(store.list_tasks(), args.full))
    elif args.command == "import-state":
      if args.source:
        try:
          text = args.source.read_text(encoding="utf-8")
        except OSError as error:
          raise ValueError(
            f"No such state file: {error.filename or args.source}"
          ) from None
      else:
        text = sys.stdin.read()
      print(
        format_import_receipt(
          store.import_state(text, args.replace_tasks, args.merge), args.merge
        )
      )
    elif args.command == "clear-state":
      print(format_clear_state(store.clear_state()))
    elif args.command == "init":
      if args.tz:
        if not zone_exists(args.tz):
          print(f"Unknown zone {args.tz}.", file=sys.stderr)
          return 1
        store.set_meta(TIMEZONE_META, args.tz)
        DISPLAY_ZONE = resolve_display_zone(store)
      # The command reports what it did, so a reader can tell a fresh state from a
      # re-used one without looking at the directory.
      print(f"state {store.path} {'created' if fresh_state else 'present'}")

  except (
    OSError,
    ValueError,
    TypeError,
    KeyError,
    sqlite_api().Error,
    RuntimeError,
  ) as error:
    print(f"Preview error: {error}", file=sys.stderr)
    return 1
  return 0


if __name__ == "__main__":
  ensure_installed()
  raise SystemExit(main())
