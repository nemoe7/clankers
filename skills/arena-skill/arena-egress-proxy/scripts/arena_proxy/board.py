"""Private master-key board state and file store for cross-session coordination."""

import base64
import hashlib
import json
import os
import re
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

MAX_BOARD_ENTRIES = 200
MAX_BOARD_BYTES = 2 * 1024 * 1024
MAX_BOARD_FILE_BYTES = 512 * 1024
SESSION_SLUG_RE = re.compile(r"^[0-9a-f]{6,16}-([A-Za-z0-9._-]+)$", re.IGNORECASE)
WORKER_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,5}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
ISO_STAMP_RE = re.compile(
  r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?)"
)
STATUS_KEYS = (
  "polling_since",
  "waiting_for_gates",
  "checking_pr",
  "calls_since_message",
  "gate_threshold",
  "agent_seen_at",
  "turn_ended_at",
  "agent_call_ended_at",
  "remote_head",
  "origin_main_head",
)


def now_iso():
  """Return the current UTC timestamp in ISO-8601 format."""
  return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def board_session_id(raw):
  """Normalize an Arena branch or session identifier."""
  text = str(raw or "").strip()
  if text.startswith("arena/"):
    text = text[6:].strip()
  if not text or "/" in text or ".." in text or any(ch.isspace() for ch in text):
    return ""
  return text[:96]


def clean_worker_id(raw):
  """Return a validated short worker identifier, or an empty string."""
  text = str(raw or "").strip()
  if text.lower().startswith("worker-"):
    text = text[7:].strip()
  return text if WORKER_ID_RE.match(text) else ""


def clean_board_repo(raw_value, fallback_sid=""):
  """Extract a lowercase repo slug from a path or session identifier."""
  text = str(raw_value or "").strip()
  if "/" in text:
    text = text.rsplit("/", 1)[-1]
  if not text and fallback_sid:
    sid = board_session_id(fallback_sid)
    match = SESSION_SLUG_RE.match(sid)
    if match:
      text = match.group(1)
  return text.lower()


def default_worker_id(session_id, repo=""):
  """Derive a fallback worker token from a session identifier."""
  sid = board_session_id(session_id)
  clean_repo = str(repo or "").strip()
  suffix = f"-{clean_repo}"
  if clean_repo and len(sid) > len(suffix) and sid.endswith(suffix):
    sid = sid[: -len(suffix)]
  head = sid.split("-", 1)[0] if "-" in sid else sid
  token = re.sub(r"[^A-Za-z0-9]+", "", head)[:6]
  return token or "w1"


def format_board_role_id(role, repo, worker_id, multi_repo, fallback_sid):
  """Format the role label for a main or worker session."""
  clean_repo = str(repo or "").strip()
  if role == "main":
    return f"main-{clean_repo}" if multi_repo and clean_repo else "main"
  if role == "worker":
    wid = clean_worker_id(worker_id) or default_worker_id(fallback_sid, clean_repo)
    return (
      f"worker-{wid}-{clean_repo}" if multi_repo and clean_repo else f"worker-{wid}"
    )
  return str(fallback_sid or "")


def parse_stamp_ms(value):
  """Parse an ISO timestamp to epoch milliseconds, or None when invalid."""
  text = str(value or "").strip()
  if not text:
    return None
  match = ISO_STAMP_RE.match(text)
  if match:
    text = match.group(1)
  if not text.endswith("Z") and not re.search(r"[+-]\d{2}:\d{2}$", text):
    text = f"{text}Z"
  try:
    parsed = datetime.fromisoformat(text)
  except ValueError:
    return None
  return int(parsed.timestamp() * 1000)


def clip_stamp(value):
  """Return the 19-character timestamp prefix, or an empty string."""
  text = str(value or "").strip()
  return (
    text[:19] if len(text) >= 19 and text[4:5] == "-" and text[10:11] == "T" else ""
  )


def resolve_board_target(target, sessions, allowed, main_sid):
  """Resolve a session, board, or worker alias to a canonical session ID."""
  clean = board_session_id(target)
  if not clean:
    return ""
  for row in sessions or []:
    if not isinstance(row, dict):
      continue
    if row.get("session_id") == clean or row.get("board_id") == clean:
      return str(row.get("session_id") or "")
    wid = str(row.get("worker_id") or "")
    if wid and clean in (wid, f"worker-{wid}"):
      return str(row.get("session_id") or "")
  if clean == "main" or clean.startswith("main-"):
    if main_sid:
      return main_sid
    if allowed:
      return allowed[0]
  return clean


def apply_report_op_to_list(report_list, op):
  """Apply an answer or unpublish operation to a worker report list."""
  items = [dict(row) for row in (report_list or []) if isinstance(row, dict)]
  if not isinstance(op, dict):
    return items
  op_name = str(op.get("op") or op.get("operation") or "answer").strip().lower()
  target_id = str(op.get("report_id") or op.get("id") or "").strip()
  if not target_id:
    return items
  op_at = clip_stamp(op.get("at"))
  if op_name in ("unpublish", "remove", "delete"):
    kept = []
    for row in items:
      if str(row.get("id") or "") != target_id:
        kept.append(row)
        continue
      row_stamp = clip_stamp(row.get("updated_at") or row.get("published_at") or "")
      if op_at and row_stamp and op_at < row_stamp:
        kept.append(row)
    return kept
  if op_name in ("answer", "submit"):
    sub_id = str(op.get("submission_id") or op.get("note_id") or "").strip()
    sub_at = op_at or now_iso()[:19]
    out = []
    for row in items:
      if str(row.get("id") or "") != target_id:
        out.append(row)
        continue
      updated = dict(row, answered=True, needs_answer=False, latest_answer_at=sub_at)
      if sub_id:
        updated["latest_answer_id"] = sub_id
      out.append(updated)
    return out
  return items


def validate_board_file(file_obj, max_bytes=MAX_BOARD_FILE_BYTES):
  """Validate a board file descriptor and decode its bytes when content is present."""
  if not file_obj or not isinstance(file_obj, dict):
    return True, None, None, ""
  name = str(file_obj.get("name") or "").strip().replace("\\", "/")
  parts = [part for part in name.split("/") if part]
  if not name or name.startswith("/") or ".." in parts or not parts:
    return False, None, None, "invalid-file-name"
  clean_name = "/".join(parts)
  encoding = "base64" if file_obj.get("encoding") == "base64" else "utf-8"
  sha256 = str(file_obj.get("sha256") or "").strip().lower()
  if sha256 and not SHA256_RE.match(sha256):
    return False, None, None, "invalid-file-sha256"
  if "content" not in file_obj or file_obj.get("content") is None:
    size = int(file_obj.get("size") or 0)
    if size < 0 or size > max_bytes:
      return False, None, None, "file-too-large"
    meta = {
      "name": clean_name,
      "encoding": encoding,
      "size": size,
      "sha256": sha256,
      "staged": bool(file_obj.get("staged", True)),
    }
    return True, meta, None, ""
  content = str(file_obj.get("content") or "")
  try:
    raw = (
      base64.b64decode(re.sub(r"\s+", "", content), validate=False)
      if encoding == "base64"
      else content.encode("utf-8")
    )
  except Exception:
    return False, None, None, "invalid-file-encoding"
  if len(raw) > max_bytes:
    return False, None, None, "file-too-large"
  digest = hashlib.sha256(raw).hexdigest()
  if sha256 and sha256 != digest:
    return False, None, None, "file-sha256-mismatch"
  meta = {
    "name": clean_name,
    "encoding": encoding,
    "size": len(raw),
    "sha256": digest,
    "staged": True,
  }
  return True, meta, raw, ""


def normalize_board(raw):
  """Normalize board state, preserving allowlist priority and worker isolation."""
  data = raw
  if isinstance(data, str):
    try:
      data = json.loads(data)
    except ValueError:
      data = {}
  if not isinstance(data, dict):
    data = {}
  multi_repo = bool(data.get("multi_repo"))
  unique_allowed = []
  seen_allowed = set()
  for item in (
    data.get("allowed_sessions")
    if isinstance(data.get("allowed_sessions"), list)
    else []
  ):
    sid = board_session_id(item)
    if sid and sid not in seen_allowed:
      seen_allowed.add(sid)
      unique_allowed.append(sid)
  removed_list = []
  removed_set = set()
  for item in (
    data.get("removed_sessions")
    if isinstance(data.get("removed_sessions"), list)
    else []
  ):
    rem = board_session_id(item)
    if rem and rem not in seen_allowed and rem not in removed_set:
      removed_set.add(rem)
      removed_list.append(rem)
  worker_ids = {}
  raw_wids = data.get("worker_ids")
  if isinstance(raw_wids, dict):
    for key, val in raw_wids.items():
      norm_k = board_session_id(key)
      clean_v = clean_worker_id(val)
      if norm_k and norm_k not in removed_set and clean_v:
        worker_ids[norm_k] = clean_v
  raw_sessions = (
    data.get("sessions")[:64] if isinstance(data.get("sessions"), list) else []
  )
  for s_row in raw_sessions:
    if not isinstance(s_row, dict):
      continue
    s_sid = board_session_id(s_row.get("session_id") or s_row.get("branch") or "")
    if not s_sid or s_sid in removed_set:
      continue
    if s_sid.startswith("probe-") and s_sid not in seen_allowed:
      removed_set.add(s_sid)
      removed_list.append(s_sid)
      worker_ids.pop(s_sid, None)
  unique_allowed = [sid for sid in unique_allowed if sid not in removed_set]
  seen_allowed = set(unique_allowed)
  main_id = board_session_id(data.get("main_session_id") or "")
  if main_id and (main_id not in seen_allowed or main_id in removed_set):
    main_id = ""
  if main_id and main_id in worker_ids:
    main_repo = clean_board_repo("", main_id)
    replacement = ""
    for cand in unique_allowed:
      if cand not in worker_ids and clean_board_repo("", cand) == main_repo:
        replacement = cand
        break
    main_id = replacement
  if main_id:
    worker_ids.pop(main_id, None)
  sessions = []
  seen_sessions = set()
  for row in raw_sessions:
    if not isinstance(row, dict):
      continue
    row_sid = board_session_id(row.get("session_id") or row.get("branch") or "")
    if (
      not row_sid
      or row_sid in seen_sessions
      or row_sid in removed_set
      or (row_sid.startswith("probe-") and row_sid not in seen_allowed)
    ):
      continue
    seen_sessions.add(row_sid)
    if row.get("worker_id") and row_sid not in worker_ids and row_sid != main_id:
      delegated = clean_worker_id(row.get("worker_id"))
      if delegated:
        worker_ids[row_sid] = delegated
    is_poll = bool(row.get("polling") or row.get("status") == "polling")
    is_disc = bool(row.get("disconnected") or row.get("status") == "disconnected")
    row_repo = clean_board_repo(row.get("repo"), row_sid)
    updated_at = row.get("updated_at")
    row_out = {
      "session_id": row_sid,
      "board_id": "",
      "worker_id": "",
      "allowed": row_sid in seen_allowed,
      "role": "worker" if row_sid in seen_allowed else "blocked",
      "repo": row_repo,
      "branch": str(row.get("branch") or f"arena/{row_sid}"),
      "status": "disconnected" if is_disc else ("polling" if is_poll else "active"),
      "polling": is_poll,
      "disconnected": is_disc,
      "updated_at": updated_at
      if isinstance(updated_at, str) and parse_stamp_ms(updated_at) is not None
      else "",
    }
    if isinstance(row.get("survey"), dict):
      survey = dict(row["survey"])
      if row_sid not in seen_allowed and isinstance(survey.get("results"), list):
        survey["results"] = [
          {key: value for key, value in result.items() if key != "answer"}
          if isinstance(result, dict)
          else result
          for result in survey["results"]
        ]
      row_out["survey"] = survey
    for key in STATUS_KEYS:
      if row.get(key) is not None:
        row_out[key] = row[key]
    sessions.append(row_out)
  for allowed_sid in unique_allowed:
    if allowed_sid not in seen_sessions:
      seen_sessions.add(allowed_sid)
      sessions.append(
        {
          "session_id": allowed_sid,
          "board_id": "",
          "worker_id": "",
          "allowed": True,
          "role": "worker",
          "repo": clean_board_repo("", allowed_sid),
          "branch": f"arena/{allowed_sid}",
          "status": "active",
          "polling": False,
          "disconnected": False,
          "updated_at": "",
        }
      )
  repo_has_main = {}
  for s_row in sessions:
    if s_row["role"] != "blocked" and main_id and s_row["session_id"] == main_id:
      s_row["role"] = "main"
      repo_has_main[s_row["repo"]] = s_row["session_id"]
  for s_row in sessions:
    if s_row["role"] == "blocked":
      continue
    s_repo = s_row["repo"]
    if s_repo not in repo_has_main and s_row["session_id"] not in worker_ids:
      s_row["role"] = "main"
      repo_has_main[s_repo] = s_row["session_id"]
  for s_row in sessions:
    if s_row["role"] == "blocked":
      continue
    s_repo = s_row["repo"]
    if s_repo not in repo_has_main:
      s_row["role"] = "main"
      repo_has_main[s_repo] = s_row["session_id"]
    elif repo_has_main[s_repo] != s_row["session_id"]:
      s_row["role"] = "worker"
  for s_row in sessions:
    s_row["worker_id"] = (
      worker_ids.get(s_row["session_id"])
      or default_worker_id(s_row["session_id"], s_row["repo"])
      if s_row["role"] == "worker"
      else ""
    )
    s_row["board_id"] = format_board_role_id(
      s_row["role"],
      s_row["repo"],
      s_row["worker_id"],
      multi_repo,
      s_row["session_id"],
    )
  linked_repos = []
  seen_linked = set()
  for item in (
    data.get("linked_repos") if isinstance(data.get("linked_repos"), list) else []
  ):
    slug = clean_board_repo(item, "")
    if slug and slug not in seen_linked:
      seen_linked.add(slug)
      linked_repos.append(slug)
  entries = (
    [
      dict(item)
      for item in data.get("entries")[-MAX_BOARD_ENTRIES:]
      if isinstance(item, dict)
    ]
    if isinstance(data.get("entries"), list)
    else []
  )
  task_ops = (
    [
      dict(item)
      for item in data.get("task_ops")[-MAX_BOARD_ENTRIES:]
      if isinstance(item, dict)
    ]
    if isinstance(data.get("task_ops"), list)
    else []
  )
  report_ops = (
    [
      dict(item)
      for item in data.get("report_ops")[-MAX_BOARD_ENTRIES:]
      if isinstance(item, dict)
    ]
    if isinstance(data.get("report_ops"), list)
    else []
  )
  worker_tasks = {}
  if isinstance(data.get("worker_tasks"), dict):
    for key, val in data["worker_tasks"].items():
      norm_k = board_session_id(key)
      if norm_k and norm_k not in removed_set and isinstance(val, list):
        worker_tasks[norm_k] = list(val)
  worker_reports = {}
  if isinstance(data.get("worker_reports"), dict):
    for key, val in data["worker_reports"].items():
      norm_k = board_session_id(key)
      if norm_k and norm_k not in removed_set and isinstance(val, list):
        worker_reports[norm_k] = list(val)
  for op in report_ops:
    op_kind = str(op.get("op") or op.get("operation") or "").strip().lower()
    if op_kind == "entry-ack":
      continue
    op_target = resolve_board_target(
      op.get("target") or "", sessions, unique_allowed, main_id
    )
    if op_target and op_target in worker_reports:
      worker_reports[op_target] = apply_report_op_to_list(worker_reports[op_target], op)
  wakes = {}
  if isinstance(data.get("wakes"), dict):
    for key, val in data["wakes"].items():
      norm_k = board_session_id(key)
      if norm_k and norm_k not in removed_set and val:
        wakes[norm_k] = val
  return {
    "multi_repo": multi_repo,
    "linked_repos": linked_repos,
    "removed_sessions": removed_list[-MAX_BOARD_ENTRIES:],
    "worker_ids": worker_ids,
    "worker_tasks": worker_tasks,
    "task_ops": task_ops,
    "worker_reports": worker_reports,
    "report_ops": report_ops,
    "allowed_sessions": unique_allowed,
    "main_session_id": main_id,
    "sessions": sessions,
    "entries": entries,
    "wakes": wakes,
  }


def scope_board_for_target(board, session_id="", repo_hint=""):
  """Scope normalized board state for a specific session and repository."""
  normalized = normalize_board(board)
  sid = board_session_id(session_id)
  target_repo = clean_board_repo(repo_hint or "", sid)
  allowed_set = set(normalized["allowed_sessions"])
  is_allowed = bool(sid and sid in allowed_set)
  scoped_main = ""
  if target_repo:
    for row in normalized["sessions"]:
      if row["repo"] == target_repo and row["allowed"] and row["role"] == "main":
        scoped_main = row["session_id"]
        break
    if (
      not scoped_main
      and normalized["main_session_id"]
      and clean_board_repo("", normalized["main_session_id"]) == target_repo
    ):
      scoped_main = normalized["main_session_id"]
    if sid and not is_allowed and scoped_main != sid:
      same_repo_allowed = any(
        clean_board_repo("", a_sid) == target_repo
        for a_sid in normalized["allowed_sessions"]
      )
      if not same_repo_allowed:
        scoped_main = ""
  elif not sid or is_allowed:
    scoped_main = normalized["main_session_id"]
  if sid and not is_allowed:
    own_reports = {}
    if sid in normalized["worker_reports"]:
      own_reports[sid] = list(normalized["worker_reports"][sid])
    out = dict(
      normalized,
      main_session_id=scoped_main,
      entries=[],
      worker_tasks={},
      worker_reports=own_reports,
      task_ops=[],
      report_ops=[],
      wakes={},
    )
    out["removed_sessions"] = [
      rem for rem in out["removed_sessions"] if rem not in allowed_set
    ]
    return out
  out = dict(
    normalized,
    main_session_id=scoped_main,
    worker_tasks={
      k: list(v) for k, v in normalized["worker_tasks"].items() if k in allowed_set
    },
    worker_reports={
      k: list(v) for k, v in normalized["worker_reports"].items() if k in allowed_set
    },
  )
  out["removed_sessions"] = [
    rem for rem in out["removed_sessions"] if rem != sid and rem not in allowed_set
  ]
  return out


def merge_preview_board(global_board, preview_board, passive=False):
  """Merge one preview session's `/api/board` snapshot into authoritative state."""
  next_board = normalize_board(global_board)
  if not isinstance(preview_board, dict):
    return next_board
  preview_sid = board_session_id(
    preview_board.get("session_id") or preview_board.get("branch") or ""
  )
  incoming = normalize_board(preview_board)
  sync_iso = now_iso()
  is_split_brain_heal = bool(
    preview_sid
    and preview_sid == incoming["main_session_id"]
    and preview_sid not in incoming["worker_ids"]
    and (
      (
        bool(next_board["allowed_sessions"])
        and all(s in next_board["worker_ids"] for s in next_board["allowed_sessions"])
      )
      if not next_board["main_session_id"]
      else (next_board["main_session_id"] in next_board["worker_ids"])
    )
  )
  global_allowed_set = set(next_board["allowed_sessions"])
  global_removed_set = {
    rem
    for rem in next_board["removed_sessions"]
    if rem and rem not in global_allowed_set
  }
  preview_is_allowed = (
    not preview_sid
    or preview_sid in global_allowed_set
    or (
      (is_split_brain_heal or preview_sid not in global_removed_set)
      and preview_sid in incoming["allowed_sessions"]
    )
  )
  if not preview_is_allowed:
    if preview_sid in next_board["removed_sessions"]:
      return next_board
    if preview_sid in incoming["worker_reports"]:
      next_board["worker_reports"][preview_sid] = incoming["worker_reports"][
        preview_sid
      ]
    unopted_row = next(
      (
        row
        for row in incoming["sessions"]
        if board_session_id(row.get("session_id") or row.get("branch")) == preview_sid
      ),
      None,
    )
    existing_idx = next(
      (
        idx
        for idx, row in enumerate(next_board["sessions"])
        if board_session_id(row.get("session_id") or row.get("branch")) == preview_sid
      ),
      -1,
    )
    prev_unopted = next_board["sessions"][existing_idx] if existing_idx != -1 else None
    is_poll = bool(
      unopted_row
      and (unopted_row.get("polling") or unopted_row.get("status") == "polling")
    )
    prev_updated = prev_unopted.get("updated_at") if prev_unopted else ""
    built_unopted = {
      "session_id": preview_sid,
      "repo": str(
        (unopted_row and unopted_row.get("repo"))
        or (prev_unopted and prev_unopted.get("repo"))
        or preview_board.get("repo")
        or ""
      ),
      "branch": str(
        (unopted_row and unopted_row.get("branch"))
        or (prev_unopted and prev_unopted.get("branch"))
        or f"arena/{preview_sid}"
      ),
      "status": "polling" if is_poll else "active",
      "polling": is_poll,
      "disconnected": False,
      "updated_at": prev_updated if passive and prev_updated else sync_iso,
    }
    survey = (unopted_row and unopted_row.get("survey")) or (
      prev_unopted and prev_unopted.get("survey")
    )
    if isinstance(survey, dict):
      built_unopted["survey"] = survey
    if unopted_row:
      for key in STATUS_KEYS:
        if unopted_row.get(key) is not None:
          built_unopted[key] = unopted_row[key]
    if existing_idx != -1:
      next_board["sessions"][existing_idx] = built_unopted
    else:
      next_board["sessions"].append(built_unopted)
    return normalize_board(next_board)

  can_author_links = (
    not next_board["main_session_id"]
    or preview_sid == next_board["main_session_id"]
    or bool(
      preview_sid
      and preview_sid == incoming["main_session_id"]
      and next_board["main_session_id"] in next_board["worker_ids"]
      and preview_sid not in incoming["worker_ids"]
    )
  )
  if "multi_repo" in preview_board and (
    can_author_links or bool(preview_board.get("multi_repo"))
  ):
    next_board["multi_repo"] = bool(preview_board.get("multi_repo"))
  if isinstance(preview_board.get("linked_repos"), list) and (
    can_author_links or incoming["linked_repos"]
  ):
    next_board["linked_repos"] = list(incoming["linked_repos"])

  incoming_allowed_set = set(incoming["allowed_sessions"])
  protected_allowed = (
    global_allowed_set | incoming_allowed_set
    if is_split_brain_heal
    else global_allowed_set
  )
  removed_set = {
    sid
    for sid in next_board["removed_sessions"]
    if sid
    and (is_split_brain_heal or sid != preview_sid or sid in global_removed_set)
    and sid not in protected_allowed
  }
  for sid in incoming["removed_sessions"]:
    if not sid or sid == preview_sid:
      continue
    if (can_author_links and sid not in incoming_allowed_set) or (
      sid not in global_allowed_set and sid not in incoming_allowed_set
    ):
      removed_set.add(sid)
  next_board["removed_sessions"] = list(removed_set)
  next_board["allowed_sessions"] = [
    sid for sid in next_board["allowed_sessions"] if sid not in removed_set
  ]
  next_board["sessions"] = [
    row
    for row in next_board["sessions"]
    if board_session_id(row.get("session_id") or row.get("branch")) not in removed_set
  ]
  for removed_sid in removed_set:
    next_board["worker_ids"].pop(removed_sid, None)
    next_board["worker_tasks"].pop(removed_sid, None)
    next_board["worker_reports"].pop(removed_sid, None)
    next_board["wakes"].pop(removed_sid, None)
  for sid, wid in incoming["worker_ids"].items():
    if sid not in removed_set:
      next_board["worker_ids"][sid] = wid
  for sid, tasks in incoming["worker_tasks"].items():
    if sid not in removed_set and (
      sid == preview_sid or sid not in next_board["worker_tasks"]
    ):
      next_board["worker_tasks"][sid] = tasks
  for sid, reports in incoming["worker_reports"].items():
    if sid in removed_set:
      continue
    if sid == preview_sid or sid not in next_board["worker_reports"]:
      next_board["worker_reports"][sid] = reports
    elif can_author_links and isinstance(reports, list):
      inc_by_id = {
        str(r.get("id") or ""): r
        for r in reports
        if isinstance(r, dict) and r.get("id")
      }
      merged_rep_list = []
      for existing_rep in next_board["worker_reports"].get(sid) or []:
        if not isinstance(existing_rep, dict):
          continue
        rid = str(existing_rep.get("id") or "")
        inc_rep = inc_by_id.get(rid)
        if inc_rep and inc_rep.get("answered") and not existing_rep.get("answered"):
          updated_rep = dict(
            existing_rep,
            answered=True,
            needs_answer=False,
            latest_answer_at=inc_rep.get("latest_answer_at")
            or existing_rep.get("latest_answer_at"),
          )
          if inc_rep.get("latest_answer_id"):
            updated_rep["latest_answer_id"] = inc_rep["latest_answer_id"]
          merged_rep_list.append(updated_rep)
        else:
          merged_rep_list.append(existing_rep)
      next_board["worker_reports"][sid] = merged_rep_list

  seen_top = set()
  merged_tops = []
  for op in [*next_board["task_ops"], *incoming["task_ops"]]:
    if not isinstance(op, dict):
      continue
    op_id = str(op.get("id") or "")
    if op_id and op_id in seen_top:
      continue
    if op_id:
      seen_top.add(op_id)
    merged_tops.append(op)
  merged_tops.sort(key=lambda item: parse_stamp_ms(item.get("at")) or 0)
  next_board["task_ops"] = merged_tops[-MAX_BOARD_ENTRIES:]

  seen_rop = set()
  merged_rops = []
  for op in [*next_board["report_ops"], *incoming["report_ops"]]:
    if not isinstance(op, dict):
      continue
    op_id = str(op.get("id") or "")
    if op_id and op_id in seen_rop:
      continue
    if op_id:
      seen_rop.add(op_id)
    merged_rops.append(op)
  merged_rops.sort(key=lambda item: parse_stamp_ms(item.get("at")) or 0)
  rep_decisions = [op for op in merged_rops if str(op.get("op") or "") != "entry-ack"]
  entry_acks = [op for op in merged_rops if str(op.get("op") or "") == "entry-ack"]
  kept_decisions = rep_decisions[-MAX_BOARD_ENTRIES:]
  ack_budget = max(0, MAX_BOARD_ENTRIES - len(kept_decisions))
  combined_rops = [*kept_decisions, *entry_acks[-ack_budget:]]
  combined_rops.sort(key=lambda item: parse_stamp_ms(item.get("at")) or 0)
  next_board["report_ops"] = combined_rops

  if can_author_links and incoming["allowed_sessions"]:
    ordered = []
    for sid in [*incoming["allowed_sessions"], *next_board["allowed_sessions"]]:
      if sid not in removed_set and sid not in ordered:
        ordered.append(sid)
    next_board["allowed_sessions"] = ordered
  else:
    for sid in incoming["allowed_sessions"]:
      if sid not in removed_set and sid not in next_board["allowed_sessions"]:
        next_board["allowed_sessions"].append(sid)

  if (
    incoming["main_session_id"]
    and incoming["main_session_id"] not in removed_set
    and (
      not next_board["main_session_id"]
      or (
        next_board["main_session_id"] in next_board["worker_ids"]
        and incoming["main_session_id"] not in next_board["worker_ids"]
      )
    )
  ):
    next_board["main_session_id"] = incoming["main_session_id"]
  elif next_board["main_session_id"] in removed_set:
    next_board["main_session_id"] = ""

  by_sid = {}
  prev_sessions_by_sid = {}
  for row in next_board["sessions"]:
    row_sid = board_session_id(row.get("session_id") or row.get("branch"))
    if row_sid and row_sid not in removed_set:
      prev_sessions_by_sid[row_sid] = dict(row, session_id=row_sid)
      by_sid[row_sid] = dict(row, session_id=row_sid)
  for row in incoming["sessions"]:
    row_sid = board_session_id(row.get("session_id") or row.get("branch"))
    if not row_sid or row_sid in removed_set:
      continue
    prev = by_sid.get(row_sid)
    inc_ms = parse_stamp_ms(row.get("updated_at"))
    prev_ms = parse_stamp_ms(prev.get("updated_at")) if prev else None
    peer_fresher = bool(
      prev is not None and inc_ms is not None and (prev_ms is None or inc_ms > prev_ms)
    )
    if row_sid == preview_sid or prev is None or peer_fresher:
      next_poll = bool(row.get("polling") or row.get("status") == "polling")
      is_disc = (
        False
        if row_sid == preview_sid
        else bool(row.get("disconnected") or row.get("status") == "disconnected")
      )
      prev_updated = prev.get("updated_at") if prev else ""
      self_updated = prev_updated if passive and prev_updated else sync_iso
      next_row = {
        "session_id": row_sid,
        "repo": str(
          row.get("repo")
          or (prev and prev.get("repo"))
          or preview_board.get("repo")
          or ""
        ),
        "branch": str(
          row.get("branch") or (prev and prev.get("branch")) or f"arena/{row_sid}"
        ),
        "status": "polling"
        if (row_sid == preview_sid and next_poll)
        else (
          "active"
          if row_sid == preview_sid
          else ("disconnected" if is_disc else ("polling" if next_poll else "active"))
        ),
        "polling": next_poll,
        "disconnected": is_disc,
        "updated_at": self_updated
        if row_sid == preview_sid
        else str(row.get("updated_at") or prev_updated or sync_iso),
      }
      survey = (
        row.get("survey")
        if isinstance(row.get("survey"), dict)
        else (
          prev.get("survey") if prev and isinstance(prev.get("survey"), dict) else None
        )
      )
      if survey:
        next_row["survey"] = survey
      for key in STATUS_KEYS:
        if row.get(key) is not None:
          next_row[key] = row[key]
        elif row_sid != preview_sid and prev and prev.get(key) is not None:
          if key == "polling_since" and not next_poll:
            continue
          if key == "turn_ended_at":
            if next_poll:
              continue
            prev_turn_ms = parse_stamp_ms(prev.get("turn_ended_at"))
            latest_act_ms = max(
              parse_stamp_ms(row.get("agent_seen_at")) or 0,
              parse_stamp_ms(row.get("agent_call_ended_at")) or 0,
            )
            if prev_turn_ms is not None and latest_act_ms > prev_turn_ms:
              continue
          next_row[key] = prev[key]
      by_sid[row_sid] = next_row
    else:
      if isinstance(row.get("survey"), dict):
        by_sid[row_sid]["survey"] = row["survey"]
      for key in STATUS_KEYS:
        if by_sid[row_sid].get(key) is None and row.get(key) is not None:
          by_sid[row_sid][key] = row[key]
  next_board["sessions"] = list(by_sid.values())

  entry_by_id = {}
  merged_entries = []
  for item in [*next_board["entries"], *incoming["entries"]]:
    if not isinstance(item, dict):
      continue
    copy = dict(item)
    eid = str(copy.get("id") or "")
    if eid and eid in entry_by_id:
      prev = entry_by_id[eid]
      for field in (
        "seen_at",
        "acknowledged_at",
        "ack_type",
        "ack_text",
        "ack_sender",
        "ack_edited_at",
        "task_id",
      ):
        if copy.get(field) and not prev.get(field):
          prev[field] = copy[field]
      if (
        copy.get("to")
        and copy.get("to") != "*"
        and prev.get("to")
        and prev.get("to") != copy.get("to")
        and copy.get("to") in next_board["allowed_sessions"]
      ):
        prev["to"] = copy["to"]
      if (
        copy.get("ack_sender")
        and prev.get("to")
        and prev.get("to") != "*"
        and prev.get("to") != prev.get("session_id")
        and (
          copy.get("ack_sender") == prev.get("to")
          or (
            prev.get("ack_sender") == prev.get("session_id")
            and copy.get("ack_sender") != prev.get("session_id")
          )
        )
      ):
        prev["ack_sender"] = copy["ack_sender"]
      if copy.get("ack_edited_at") and (
        not prev.get("ack_edited_at")
        or str(copy.get("ack_edited_at")) > str(prev.get("ack_edited_at"))
      ):
        prev["ack_edited_at"] = copy["ack_edited_at"]
      if int(copy.get("ack_edited_seen_count") or 0) > int(
        prev.get("ack_edited_seen_count") or 0
      ):
        prev["ack_edited_seen_count"] = int(copy.get("ack_edited_seen_count") or 0)
      if isinstance(copy.get("replies"), list):
        prev_replies = (
          prev.get("replies") if isinstance(prev.get("replies"), list) else []
        )
        if len(copy["replies"]) > len(prev_replies):
          prev["replies"] = list(copy["replies"])
      if copy.get("file") and not prev.get("file"):
        prev["file"] = copy["file"]
      continue
    if eid:
      entry_by_id[eid] = copy
    merged_entries.append(copy)
  for op in next_board["report_ops"]:
    if op.get("op") != "entry-ack":
      continue
    target = entry_by_id.get(str(op.get("entry_id") or ""))
    if target and int(op.get("ack_edited_seen_count") or 0) > int(
      target.get("ack_edited_seen_count") or 0
    ):
      target["ack_edited_seen_count"] = int(op.get("ack_edited_seen_count") or 0)
  merged_entries.sort(key=lambda item: parse_stamp_ms(item.get("at")) or 0)
  next_board["entries"] = merged_entries[-MAX_BOARD_ENTRIES:]

  for wake_k, wake_v in incoming["wakes"].items():
    if wake_k != preview_sid and wake_v:
      next_board["wakes"][wake_k] = wake_v
  if preview_sid and preview_sid in next_board["wakes"]:
    raw_wakes = preview_board.get("wakes")
    if not isinstance(raw_wakes, dict) or not raw_wakes.get(preview_sid):
      next_board["wakes"].pop(preview_sid, None)
  normalized_out = normalize_board(next_board)
  for m_row in normalized_out["sessions"]:
    if not (m_row.get("allowed") and m_row.get("role") == "main"):
      continue
    prev_m = prev_sessions_by_sid.get(m_row["session_id"])
    if not prev_m:
      continue
    prev_rh = str(prev_m.get("remote_head") or "").strip().lower()
    cur_rh = str(m_row.get("remote_head") or "").strip().lower()
    prev_om = str(prev_m.get("origin_main_head") or "").strip().lower()
    cur_om = str(m_row.get("origin_main_head") or "").strip().lower()
    rh_moved = bool(
      GIT_SHA_RE.fullmatch(prev_rh)
      and GIT_SHA_RE.fullmatch(cur_rh)
      and prev_rh != cur_rh
    )
    om_moved = bool(
      GIT_SHA_RE.fullmatch(prev_om)
      and GIT_SHA_RE.fullmatch(cur_om)
      and prev_om != cur_om
    )
    if not (rh_moved or om_moved):
      continue
    moved_sha = cur_rh if rh_moved else cur_om
    wake_tok = f"main-moved:{moved_sha[:12]}"
    m_repo = m_row.get("repo") or ""
    linked_set = {
      m_repo,
      *(normalized_out["linked_repos"] if normalized_out["multi_repo"] else []),
    }
    for w_row in normalized_out["sessions"]:
      w_sid = w_row["session_id"]
      if not (w_row.get("allowed") and w_row.get("role") == "worker"):
        continue
      if w_sid == preview_sid:
        continue
      if m_repo and w_row.get("repo") and w_row.get("repo") not in linked_set:
        continue
      normalized_out["wakes"][w_sid] = wake_tok
  return normalized_out


def apply_board_action(board, action):
  """Apply an imperative board action and return `(ok, error, updated_board)`."""
  next_board = normalize_board(board)
  if not isinstance(action, dict):
    return False, "invalid-action", next_board
  action_type = str(action.get("type") or action.get("action") or "").strip()
  sid = resolve_board_target(
    action.get("session_id") or action.get("branch") or "",
    next_board["sessions"],
    next_board["allowed_sessions"],
    next_board["main_session_id"],
  )
  stamp = str(action.get("at") or now_iso())
  if action_type == "allow":
    if not sid:
      return False, "missing-session-id", next_board
    next_board["removed_sessions"] = [
      item for item in next_board["removed_sessions"] if item != sid
    ]
    raw_wid = (
      action.get("worker_id") if "worker_id" in action else action.get("identifier")
    )
    if raw_wid is not None:
      clean_wid = clean_worker_id(raw_wid)
      if not clean_wid:
        return False, "invalid-worker-id", next_board
      next_board["worker_ids"][sid] = clean_wid
    if sid not in next_board["allowed_sessions"]:
      next_board["allowed_sessions"].append(sid)
    return True, "", normalize_board(next_board)
  if action_type in ("delegate-id", "set-worker-id"):
    target_sid = resolve_board_target(
      action.get("session_id") or action.get("target") or "",
      next_board["sessions"],
      next_board["allowed_sessions"],
      next_board["main_session_id"],
    )
    if not target_sid:
      return False, "missing-session-id", next_board
    raw_id = (
      action.get("worker_id")
      if action.get("worker_id") is not None
      else (
        action.get("identifier")
        if action.get("identifier") is not None
        else action.get("id")
      )
    )
    clean_id = clean_worker_id(raw_id)
    if not clean_id:
      return False, "invalid-worker-id", next_board
    next_board["worker_ids"][target_sid] = clean_id
    return True, "", normalize_board(next_board)
  if action_type == "set-multi-repo":
    val = action["multi_repo"] if "multi_repo" in action else action.get("enabled")
    next_board["multi_repo"] = bool(val)
    return True, "", normalize_board(next_board)
  if action_type in ("worker-task", "manage-worker-tasks"):
    if next_board["main_session_id"] and sid and sid != next_board["main_session_id"]:
      return False, "only-main-session", next_board
    target_worker = resolve_board_target(
      action.get("target")
      or action.get("worker")
      or action.get("target_session_id")
      or "",
      next_board["sessions"],
      next_board["allowed_sessions"],
      next_board["main_session_id"],
    )
    if not target_worker:
      return False, "missing-worker-target", next_board
    op_name = (
      str(
        action.get("op") or action.get("operation") or action.get("subaction") or "set"
      )
      .strip()
      .lower()
    )
    op_id = str(action.get("id") or f"top-{int(time.time() * 1000)}")
    next_board["task_ops"].append(
      {
        "id": op_id,
        "target": target_worker,
        "op": op_name,
        "task_id": str(action.get("task_id") or action.get("task") or ""),
        "title": action.get("title"),
        "details": action.get("details"),
        "scope": action.get("scope"),
        "status": action.get("status"),
        "task_type": action.get("task_type") or action.get("type"),
        "order": action.get("order"),
        "order_ids": action.get("order_ids"),
        "append": bool(action.get("append")),
        "report_id": action.get("report_id"),
        "tasks": action.get("tasks"),
        "at": stamp,
      }
    )
    next_board["task_ops"] = next_board["task_ops"][-MAX_BOARD_ENTRIES:]
    if target_worker in next_board["allowed_sessions"]:
      next_board["wakes"][target_worker] = op_id
    return True, "", normalize_board(next_board)
  if action_type in ("worker-report", "manage-worker-reports"):
    from_owner = bool(action.get("from_owner"))
    if (
      not from_owner
      and next_board["main_session_id"]
      and sid
      and sid != next_board["main_session_id"]
    ):
      return False, "only-main-session", next_board
    target_worker = resolve_board_target(
      action.get("target")
      or action.get("worker")
      or action.get("target_session_id")
      or "",
      next_board["sessions"],
      next_board["allowed_sessions"],
      next_board["main_session_id"],
    )
    if not target_worker:
      return False, "missing-worker-target", next_board
    report_id = str(action.get("report_id") or action.get("report") or "").strip()
    if not report_id:
      return False, "missing-report-id", next_board
    op_name = (
      str(
        action.get("op")
        or action.get("operation")
        or action.get("subaction")
        or "answer"
      )
      .strip()
      .lower()
    )
    op_id = str(action.get("id") or f"rop-{int(time.time() * 1000)}")
    next_board["report_ops"].append(
      {
        "id": op_id,
        "target": target_worker,
        "op": op_name,
        "report_id": report_id,
        "from_owner": from_owner,
        "answers": action.get("answers")
        if isinstance(action.get("answers"), dict)
        else {},
        "submission_id": action.get("submission_id") or action.get("note_id"),
        "at": stamp,
      }
    )
    next_board["report_ops"] = next_board["report_ops"][-MAX_BOARD_ENTRIES:]
    if target_worker in next_board["allowed_sessions"]:
      next_board["wakes"][target_worker] = op_id
    return True, "", normalize_board(next_board)
  if action_type == "disconnect-session":
    if not sid:
      return False, "missing-session-id", next_board
    for row in next_board["sessions"]:
      if board_session_id(row.get("session_id") or row.get("branch")) == sid:
        row["status"] = "disconnected"
        row["disconnected"] = True
        row["polling"] = False
    return True, "", normalize_board(next_board)
  if action_type in ("revoke", "remove-session", "dismiss"):
    if not sid:
      return False, "missing-session-id", next_board
    if sid not in next_board["removed_sessions"]:
      next_board["removed_sessions"].append(sid)
    next_board["allowed_sessions"] = [
      item for item in next_board["allowed_sessions"] if item != sid
    ]
    next_board["sessions"] = [
      row
      for row in next_board["sessions"]
      if board_session_id(row.get("session_id") or row.get("branch")) != sid
    ]
    next_board["wakes"].pop(sid, None)
    next_board["worker_ids"].pop(sid, None)
    next_board["worker_tasks"].pop(sid, None)
    next_board["worker_reports"].pop(sid, None)
    if next_board["main_session_id"] == sid:
      next_board["main_session_id"] = ""
    return True, "", normalize_board(next_board)
  if action_type == "set-main":
    if not sid:
      next_board["main_session_id"] = ""
      return True, "", normalize_board(next_board)
    next_board["removed_sessions"] = [
      item for item in next_board["removed_sessions"] if item != sid
    ]
    next_board["worker_ids"].pop(sid, None)
    if sid not in next_board["allowed_sessions"]:
      next_board["allowed_sessions"].append(sid)
    next_board["main_session_id"] = sid
    return True, "", normalize_board(next_board)
  if action_type == "heartbeat":
    hb_sid = board_session_id(action.get("session_id") or action.get("branch") or "")
    if not hb_sid:
      return False, "missing-session-id", next_board
    if next_board["allowed_sessions"] and hb_sid not in next_board["allowed_sessions"]:
      return True, "", next_board
    next_board["removed_sessions"] = [
      item for item in next_board["removed_sessions"] if item != hb_sid
    ]
    found = False
    for idx, row in enumerate(next_board["sessions"]):
      if board_session_id(row.get("session_id") or row.get("branch")) == hb_sid:
        found = True
        next_board["sessions"][idx] = {
          "session_id": hb_sid,
          "repo": str(action.get("repo") or row.get("repo") or ""),
          "branch": str(action.get("branch") or row.get("branch") or f"arena/{hb_sid}"),
          "status": str(action.get("status") or row.get("status") or "active"),
          "polling": bool(action.get("polling")),
          "updated_at": stamp,
        }
    if not found:
      next_board["sessions"].append(
        {
          "session_id": hb_sid,
          "repo": str(action.get("repo") or ""),
          "branch": str(action.get("branch") or f"arena/{hb_sid}"),
          "status": str(action.get("status") or "active"),
          "polling": bool(action.get("polling")),
          "updated_at": stamp,
        }
      )
    return True, "", normalize_board(next_board)
  if action_type == "post":
    if not sid or sid not in next_board["allowed_sessions"]:
      return False, "not-allowed", next_board
    ok, checked_file, _, err = validate_board_file(action.get("file"))
    if not ok:
      return False, err, next_board
    raw_to = str(action.get("to") or "")
    resolved_to = (
      raw_to
      if raw_to in ("", "*")
      else resolve_board_target(
        raw_to,
        next_board["sessions"],
        next_board["allowed_sessions"],
        next_board["main_session_id"],
      )
    )
    next_board["entries"].append(
      {
        "id": str(action.get("id") or f"b-{int(time.time() * 1000)}"),
        "session_id": sid,
        "to": resolved_to,
        "repo": str(action.get("repo") or ""),
        "branch": str(action.get("branch") or f"arena/{sid}"),
        "at": stamp,
        "text": str(action.get("text") or ""),
        "payload": action.get("payload"),
        "file": checked_file,
      }
    )
    next_board["entries"] = next_board["entries"][-MAX_BOARD_ENTRIES:]
    return True, "", normalize_board(next_board)
  if action_type == "wake":
    if sid and sid not in next_board["allowed_sessions"]:
      return False, "not-allowed", next_board
    target = str(action.get("target") or "")
    wake_token = str(action.get("wake_id") or stamp)
    wake_iso = stamp if parse_stamp_ms(stamp) is not None else now_iso()
    if target == "all-polling":
      for row in next_board["sessions"]:
        row_id = board_session_id(row.get("session_id") or row.get("branch"))
        if row.get("polling") and row_id in next_board["allowed_sessions"]:
          next_board["wakes"][row_id] = wake_token
          row["polling"] = False
          row["status"] = "active"
          row["updated_at"] = wake_iso
    else:
      target_id = resolve_board_target(
        target,
        next_board["sessions"],
        next_board["allowed_sessions"],
        next_board["main_session_id"],
      )
      if not target_id or target_id not in next_board["allowed_sessions"]:
        return False, "target-not-allowed", next_board
      next_board["wakes"][target_id] = wake_token
      for row in next_board["sessions"]:
        if board_session_id(row.get("session_id") or row.get("branch")) == target_id:
          row["polling"] = False
          row["status"] = "active"
          row["updated_at"] = wake_iso
    return True, "", normalize_board(next_board)
  if action_type == "clear":
    next_board["entries"] = []
    return True, "", normalize_board(next_board)
  return False, "unknown-action", next_board


def material_signature(board):
  """Compute a deterministic signature ignoring heartbeat-only `updated_at` churn."""
  norm = normalize_board(board)
  sessions_sig = [
    {
      "sid": s.get("session_id") or "",
      "repo": s.get("repo") or "",
      "role": s.get("role") or "",
      "allowed": bool(s.get("allowed")),
      "wid": s.get("worker_id") or "",
      "status": s.get("status") or "",
      "polling": bool(s.get("polling")),
      "disc": bool(s.get("disconnected")),
      "ps": s.get("polling_since") or "",
      "wg": bool(s.get("waiting_for_gates")),
      "cp": bool(s.get("checking_pr")),
      "calls": int(s.get("calls_since_message") or 0),
      "seen": s.get("agent_seen_at") or "",
      "tend": s.get("turn_ended_at") or "",
      "cend": s.get("agent_call_ended_at") or "",
      "surv": str(
        (s.get("survey") or {}).get("answered_at")
        or (s.get("survey") or {}).get("answered")
        or ""
      ),
    }
    for s in sorted(
      norm["sessions"], key=lambda item: str(item.get("session_id") or "")
    )
  ]
  entries_sig = [
    {
      "id": e.get("id") or "",
      "to": e.get("to") or "",
      "seen": e.get("seen_at") or "",
      "ack": e.get("acknowledged_at") or "",
      "atp": e.get("ack_type") or "",
      "atx": e.get("ack_text") or "",
      "asd": e.get("ack_sender") or "",
      "aed": e.get("ack_edited_at") or "",
      "asc": int(e.get("ack_edited_seen_count") or 0),
      "tid": e.get("task_id") or "",
      "rlen": len(e["replies"]) if isinstance(e.get("replies"), list) else 0,
      "file": (e.get("file") or {}).get("sha256")
      or (e.get("file") or {}).get("name")
      or "",
    }
    for e in norm["entries"]
  ]
  wt_sig = [
    [
      k,
      [
        [t.get("id"), t.get("status"), t.get("order"), t.get("updated_at") or ""]
        for t in norm["worker_tasks"][k]
        if isinstance(t, dict)
      ],
    ]
    for k in sorted(norm["worker_tasks"])
  ]
  wr_sig = [
    [
      k,
      [
        [
          r.get("id"),
          r.get("updated_at") or "",
          bool(r.get("answered")),
          bool(r.get("needs_answer")),
          r.get("latest_answer_id") or "",
        ]
        for r in norm["worker_reports"][k]
        if isinstance(r, dict)
      ],
    ]
    for k in sorted(norm["worker_reports"])
  ]
  return json.dumps(
    {
      "mr": bool(norm["multi_repo"]),
      "lr": norm["linked_repos"],
      "main": norm["main_session_id"],
      "allow": norm["allowed_sessions"],
      "rem": norm["removed_sessions"],
      "wids": norm["worker_ids"],
      "wakes": norm["wakes"],
      "tops": [o.get("id") or "" for o in norm["task_ops"]],
      "rops": [o.get("id") or "" for o in norm["report_ops"]],
      "sessions": sessions_sig,
      "entries": entries_sig,
      "wt": wt_sig,
      "wr": wr_sig,
    },
    sort_keys=True,
    separators=(",", ":"),
  )


class BoardStore:
  """Persist cross-session board JSON and staged board attachments on disk."""

  def __init__(self, directory, max_file_bytes=MAX_BOARD_FILE_BYTES):
    self.directory = Path(directory)
    self.files_dir = self.directory / "files"
    self.state_file = self.directory / "board.json"
    self.max_file_bytes = max_file_bytes
    self.lock = threading.RLock()
    self.revision = 0
    self.state = normalize_board(None)
    self.material_sig = material_signature(self.state)
    self._load()

  def _load(self):
    with self.lock:
      if not self.state_file.is_file():
        return
      try:
        saved = json.loads(self.state_file.read_text(encoding="utf-8"))
      except (OSError, ValueError):
        return
      if not isinstance(saved, dict):
        return
      self.revision = max(0, int(saved.get("revision") or 0))
      self.state = normalize_board(saved.get("board"))
      self.material_sig = material_signature(self.state)

  def _persist_locked(self, next_state, passive=False):
    trimmed = normalize_board(next_state)
    while (
      len(trimmed["entries"]) > 1
      and len(json.dumps(trimmed, ensure_ascii=False).encode("utf-8")) > MAX_BOARD_BYTES
    ):
      trimmed["entries"].pop(0)
    next_sig = material_signature(trimmed)
    changed_material = next_sig != self.material_sig
    if changed_material or (not passive and trimmed != self.state):
      self.revision += 1
    self.state = trimmed
    self.material_sig = next_sig
    self.directory.mkdir(parents=True, exist_ok=True)
    tmp_path = self.directory / f"board.{os.getpid()}.{threading.get_ident()}.tmp"
    payload = json.dumps(
      {"revision": self.revision, "board": self.state},
      ensure_ascii=False,
      separators=(",", ":"),
    )
    tmp_path.write_text(payload, encoding="utf-8")
    os.replace(tmp_path, self.state_file)
    return self.revision, self.state

  def _extract_entry_files_locked(self, entries, fallback_sid=""):
    cleaned = []
    for entry in entries or []:
      if not isinstance(entry, dict):
        continue
      copy = dict(entry)
      file_obj = copy.get("file")
      if isinstance(file_obj, dict):
        from_sid = board_session_id(copy.get("session_id") or fallback_sid)
        ok, meta, raw_bytes, _ = validate_board_file(file_obj, self.max_file_bytes)
        if ok and meta:
          if raw_bytes is not None and from_sid:
            self._write_file_locked(from_sid, meta["name"], raw_bytes, meta)
          copy["file"] = meta
        else:
          copy["file"] = None
      cleaned.append(copy)
    return cleaned

  def _file_target_locked(self, session_id, name):
    sid = board_session_id(session_id)
    ok, meta, _, err = validate_board_file({"name": name}, self.max_file_bytes)
    if not sid:
      raise ValueError("missing session_id")
    if not ok or not meta:
      raise ValueError(err or "invalid-file-name")
    base = (self.files_dir / sid).resolve()
    target = (base / meta["name"]).resolve()
    if base != target and base not in target.parents:
      raise ValueError("invalid-file-name")
    return sid, meta["name"], target

  def _write_file_locked(self, session_id, name, raw_bytes, meta=None):
    _, clean_name, target = self._file_target_locked(session_id, name)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(raw_bytes)
    info = dict(
      meta
      or {
        "name": clean_name,
        "encoding": "base64",
        "size": len(raw_bytes),
        "sha256": hashlib.sha256(raw_bytes).hexdigest(),
        "staged": True,
      }
    )
    target.with_name(f"{target.name}.meta.json").write_text(
      json.dumps(info, separators=(",", ":")), encoding="utf-8"
    )
    return info

  def put_file(self, session_id, file_obj):
    """Validate and persist a board file attachment."""
    ok, meta, raw_bytes, err = validate_board_file(file_obj, self.max_file_bytes)
    if not ok or not meta or raw_bytes is None:
      raise ValueError(err or "missing-file-content")
    with self.lock:
      return self._write_file_locked(session_id, meta["name"], raw_bytes, meta)

  def get_file_by_sha256(self, sha256):
    """Read a staged board file attachment matching a 64-hex SHA-256 digest."""
    digest = str(sha256 or "").strip().lower()
    if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
      raise ValueError("invalid-sha256")
    with self.lock:
      if not self.files_dir.is_dir():
        return None
      for meta_path in self.files_dir.rglob("*.meta.json"):
        try:
          saved_meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
          continue
        if str(saved_meta.get("sha256") or "").lower() != digest:
          continue
        target = meta_path.with_name(meta_path.name[: -len(".meta.json")])
        if not target.is_file():
          continue
        raw_bytes = target.read_bytes()
        if hashlib.sha256(raw_bytes).hexdigest() != digest:
          continue
        encoding = (
          saved_meta.get("encoding")
          if saved_meta.get("encoding") in ("utf-8", "base64")
          else "base64"
        )
        if encoding == "utf-8":
          try:
            content = raw_bytes.decode("utf-8")
          except UnicodeDecodeError:
            encoding = "base64"
            content = base64.b64encode(raw_bytes).decode("ascii")
        else:
          content = base64.b64encode(raw_bytes).decode("ascii")
        return {
          "name": str(saved_meta.get("name") or target.name),
          "encoding": encoding,
          "content": content,
          "size": len(raw_bytes),
          "sha256": digest,
        }
      return None

  def get_file(self, session_id, name):
    """Read a staged board file attachment as descriptor with inline content."""
    with self.lock:
      _, clean_name, target = self._file_target_locked(session_id, name)
      if not target.is_file():
        return None
      raw_bytes = target.read_bytes()
      meta_path = target.with_name(f"{target.name}.meta.json")
      encoding = "base64"
      if meta_path.is_file():
        try:
          saved_meta = json.loads(meta_path.read_text(encoding="utf-8"))
          if saved_meta.get("encoding") in ("utf-8", "base64"):
            encoding = saved_meta["encoding"]
        except (OSError, ValueError):
          pass
      if encoding == "utf-8":
        try:
          content = raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
          encoding = "base64"
          content = base64.b64encode(raw_bytes).decode("ascii")
      else:
        content = base64.b64encode(raw_bytes).decode("ascii")
      return {
        "name": clean_name,
        "encoding": encoding,
        "content": content,
        "size": len(raw_bytes),
        "sha256": hashlib.sha256(raw_bytes).hexdigest(),
      }

  def snapshot(self, since=None, session_id="", repo=""):
    """Return full or unchanged board snapshot, plus optional target-scoped board."""
    with self.lock:
      if since is not None and since == self.revision:
        return {"ok": True, "unchanged": True, "revision": self.revision}
      out = {
        "ok": True,
        "unchanged": False,
        "revision": self.revision,
        "board": self.state,
      }
      if session_id or repo:
        out["scoped_board"] = scope_board_for_target(self.state, session_id, repo)
      return out

  def sync(self, preview_board, session_id="", repo="", passive=False):
    """Merge a preview session board payload and return global plus scoped boards."""
    with self.lock:
      incoming = dict(preview_board) if isinstance(preview_board, dict) else {}
      sid = board_session_id(
        session_id or incoming.get("session_id") or incoming.get("branch") or ""
      )
      if sid and not incoming.get("session_id"):
        incoming["session_id"] = sid
      if repo and not incoming.get("repo"):
        incoming["repo"] = repo
      if isinstance(incoming.get("entries"), list):
        incoming["entries"] = self._extract_entry_files_locked(incoming["entries"], sid)
      merged = merge_preview_board(self.state, incoming, passive=passive)
      rev, saved = self._persist_locked(merged, passive=passive)
      return {
        "ok": True,
        "revision": rev,
        "board": saved,
        "scoped_board": scope_board_for_target(
          saved, sid, repo or incoming.get("repo") or ""
        ),
      }

  def apply(self, action, session_id="", repo=""):
    """Apply an imperative board action and return global plus scoped boards."""
    with self.lock:
      act = dict(action) if isinstance(action, dict) else {}
      act_sid = board_session_id(
        act.get("session_id") or act.get("branch") or session_id or ""
      )
      if isinstance(act.get("file"), dict) and act_sid:
        ok, meta, raw_bytes, err = validate_board_file(act["file"], self.max_file_bytes)
        if not ok:
          return {
            "ok": False,
            "error": err,
            "revision": self.revision,
            "board": self.state,
          }
        if meta and raw_bytes is not None:
          self._write_file_locked(act_sid, meta["name"], raw_bytes, meta)
          act["file"] = meta
      passive = str(act.get("type") or act.get("action") or "") == "heartbeat"
      ok, err, updated = apply_board_action(self.state, act)
      if not ok:
        return {
          "ok": False,
          "error": err,
          "revision": self.revision,
          "board": self.state,
        }
      rev, saved = self._persist_locked(updated, passive=passive)
      return {
        "ok": True,
        "revision": rev,
        "board": saved,
        "scoped_board": scope_board_for_target(
          saved, act_sid or session_id, repo or act.get("repo") or ""
        ),
      }
