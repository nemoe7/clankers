"""SQLite WAL persistence, SHA-256 blob storage, and revision-cursor diff helpers."""

import hashlib
import json
import os
import re
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
BLOB_INLINE_THRESHOLD = 4096
BOARD_COLLECTION_KEYS = frozenset(
  {
    "sessions",
    "entries",
    "task_ops",
    "report_ops",
    "worker_tasks",
    "worker_reports",
    "wakes",
  }
)


def now_iso():
  """Return the current UTC timestamp in ISO-8601 format."""
  return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def canonical_json(value):
  """Serialize a JSON-compatible value with deterministic key ordering."""
  return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def state_scope_key(repo, branch=""):
  """Build a normalized scope key for a repository and optional branch."""
  clean_repo = str(repo or "").strip()
  clean_branch = str(branch or "").strip()
  if not clean_repo:
    raise ValueError("repo is required")
  return f"{clean_repo}::{clean_branch}"


def state_record_group(record):
  """Classify one core state record into reports, tasks, answers, or notes."""
  if not isinstance(record, dict):
    return "notes"
  if "markdown" in record:
    return "reports"
  if "title" in record:
    return "tasks"
  if "report_id" in record:
    return "answers"
  return "notes"


def state_record_key(record):
  """Return a stable primary key within a state record's group."""
  if not isinstance(record, dict):
    return hashlib.sha256(canonical_json(record).encode("utf-8")).hexdigest()[:16]
  rec_id = str(record.get("id") or "").strip()
  if rec_id:
    return rec_id
  if record.get("seq") is not None:
    return f"seq:{record['seq']}"
  return hashlib.sha256(canonical_json(record).encode("utf-8")).hexdigest()[:16]


def sort_state_core(records):
  """Order core records deterministically matching preview export order."""
  notes = []
  answers = []
  reports = []
  tasks = []
  for row in records or []:
    if not isinstance(row, dict) or row.get("type") == "userscript-autosave":
      continue
    group = state_record_group(row)
    if group == "notes":
      notes.append(row)
    elif group == "answers":
      answers.append(row)
    elif group == "reports":
      reports.append(row)
    else:
      tasks.append(row)
  notes.sort(
    key=lambda r: (
      int(r.get("seq") or 0),
      str(r.get("at") or ""),
      str(r.get("id") or ""),
    )
  )
  answers.sort(
    key=lambda r: (
      int(r.get("seq") or 0),
      str(r.get("at") or ""),
      str(r.get("id") or ""),
    )
  )
  reports.sort(key=lambda r: (str(r.get("published_at") or ""), str(r.get("id") or "")))
  status_rank = {"current": 0, "upcoming": 0, "finished": 1}
  tasks.sort(
    key=lambda r: (
      status_rank.get(str(r.get("status") or ""), 2),
      int(r.get("order") or 0),
      str(r.get("id") or ""),
    )
  )
  return notes + answers + reports + tasks


def core_counts(records):
  """Count notes, tasks, reports, and answers across core state records."""
  counts = {"notes": 0, "tasks": 0, "reports": 0, "answers": 0}
  for row in records or []:
    if not isinstance(row, dict) or row.get("type") == "userscript-autosave":
      continue
    group = state_record_group(row)
    counts[group] = counts.get(group, 0) + 1
  return counts


def compute_state_diff(prev_core, next_core, base_rev, next_rev):
  """Compute an incremental upsert and tombstone diff between two core lists."""
  prev_map = {}
  for row in prev_core or []:
    if isinstance(row, dict) and row.get("type") != "userscript-autosave":
      key = (state_record_group(row), state_record_key(row))
      prev_map[key] = (row, canonical_json(row))
  next_map = {}
  upserts = []
  for row in next_core or []:
    if not isinstance(row, dict) or row.get("type") == "userscript-autosave":
      continue
    key = (state_record_group(row), state_record_key(row))
    encoded = canonical_json(row)
    next_map[key] = (row, encoded)
    prev_item = prev_map.get(key)
    if prev_item is None or prev_item[1] != encoded:
      upserts.append(row)
  tombstones = [
    {"group": grp, "key": rec_key}
    for (grp, rec_key) in sorted(prev_map)
    if (grp, rec_key) not in next_map
  ]
  return {
    "base_rev": int(base_rev),
    "rev": int(next_rev),
    "upserts": upserts,
    "tombstones": tombstones,
  }


def apply_state_diff(base_core, diff_obj):
  """Apply a state diff with upserts and tombstones onto a base core list."""
  if not isinstance(diff_obj, dict):
    raise TypeError("state diff must be an object")
  upserts = diff_obj.get("upserts")
  tombstones = diff_obj.get("tombstones")
  if not isinstance(upserts, list) or not isinstance(tombstones, list):
    raise TypeError("state diff requires upserts and tombstones arrays")
  index = {}
  order = []
  for row in base_core or []:
    if not isinstance(row, dict) or row.get("type") == "userscript-autosave":
      continue
    pair = (state_record_group(row), state_record_key(row))
    if pair not in index:
      order.append(pair)
    index[pair] = dict(row)
  removed = set()
  for tomb in tombstones:
    if not isinstance(tomb, dict):
      continue
    grp = str(tomb.get("group") or "").strip()
    rec_key = str(tomb.get("key") or "").strip()
    if grp and rec_key:
      removed.add((grp, rec_key))
      index.pop((grp, rec_key), None)
  for row in upserts:
    if not isinstance(row, dict) or row.get("type") == "userscript-autosave":
      continue
    pair = (state_record_group(row), state_record_key(row))
    removed.discard(pair)
    if pair not in index:
      order.append(pair)
    index[pair] = dict(row)
  merged = [index[pair] for pair in order if pair in index and pair not in removed]
  return sort_state_core(merged)


def decompose_board_records(board):
  """Decompose a board dict into keyed records for SQLite indexing and diffs."""
  data = board if isinstance(board, dict) else {}
  records = {}
  meta = {key: val for key, val in data.items() if key not in BOARD_COLLECTION_KEYS}
  records[("meta", "scalars")] = meta
  for idx, row in enumerate(data.get("sessions") or []):
    if not isinstance(row, dict):
      continue
    br = str(row.get("branch") or row.get("session_id") or f"idx:{idx}").strip()
    if br:
      records[("session", br)] = row
  for idx, row in enumerate(data.get("entries") or []):
    if not isinstance(row, dict):
      continue
    eid = str(row.get("id") or f"idx:{idx}").strip()
    if eid:
      records[("entry", eid)] = row
  for idx, row in enumerate(data.get("task_ops") or []):
    if not isinstance(row, dict):
      continue
    oid = str(row.get("id") or f"idx:{idx}").strip()
    if oid:
      records[("task_op", oid)] = row
  for idx, row in enumerate(data.get("report_ops") or []):
    if not isinstance(row, dict):
      continue
    oid = str(row.get("id") or f"idx:{idx}").strip()
    if oid:
      records[("report_op", oid)] = row
  wt = data.get("worker_tasks")
  if isinstance(wt, dict):
    for sid, items in wt.items():
      clean_sid = str(sid or "").strip()
      if clean_sid and isinstance(items, list):
        records[("worker_tasks", clean_sid)] = items
  wr = data.get("worker_reports")
  if isinstance(wr, dict):
    for sid, items in wr.items():
      clean_sid = str(sid or "").strip()
      if clean_sid and isinstance(items, list):
        records[("worker_reports", clean_sid)] = items
  wakes = data.get("wakes")
  if isinstance(wakes, dict):
    for sid, stamp in wakes.items():
      clean_sid = str(sid or "").strip()
      if clean_sid and stamp:
        records[("wake", clean_sid)] = stamp
  return records


def recompose_board_records(records):
  """Rebuild a board dictionary from decomposed (type, key) records."""
  out = {
    "multi_repo": False,
    "linked_repos": [],
    "removed_sessions": [],
    "worker_ids": {},
    "worker_tasks": {},
    "task_ops": [],
    "worker_reports": {},
    "report_ops": [],
    "allowed_sessions": [],
    "main_session_id": "",
    "sessions": [],
    "entries": [],
    "wakes": {},
  }
  meta = records.get(("meta", "scalars"))
  if isinstance(meta, dict):
    for key, val in meta.items():
      out[key] = val
  sessions = []
  entries = []
  task_ops = []
  report_ops = []
  for (rec_type, rec_key), val in records.items():
    if rec_type == "meta":
      continue
    if rec_type == "session" and isinstance(val, dict):
      sessions.append(dict(val))
    elif rec_type == "entry" and isinstance(val, dict):
      entries.append(dict(val))
    elif rec_type == "task_op" and isinstance(val, dict):
      task_ops.append(dict(val))
    elif rec_type == "report_op" and isinstance(val, dict):
      report_ops.append(dict(val))
    elif rec_type == "worker_tasks" and isinstance(val, list):
      out["worker_tasks"][rec_key] = list(val)
    elif rec_type == "worker_reports" and isinstance(val, list):
      out["worker_reports"][rec_key] = list(val)
    elif rec_type == "wake" and val:
      out["wakes"][rec_key] = val
  entries.sort(
    key=lambda r: (
      str(r.get("created_at") or r.get("at") or ""),
      str(r.get("id") or ""),
    )
  )
  task_ops.sort(key=lambda r: (str(r.get("at") or ""), str(r.get("id") or "")))
  report_ops.sort(key=lambda r: (str(r.get("at") or ""), str(r.get("id") or "")))
  out["sessions"] = sessions
  out["entries"] = entries
  out["task_ops"] = task_ops
  out["report_ops"] = report_ops
  return out


def compute_board_diff(prev_board, next_board, base_rev, next_rev):
  """Compute an incremental record diff between two board dictionaries."""
  prev_records = decompose_board_records(prev_board)
  next_records = decompose_board_records(next_board)
  upserts = []
  for pair, val in next_records.items():
    encoded = canonical_json(val)
    if pair not in prev_records or canonical_json(prev_records[pair]) != encoded:
      upserts.append({"type": pair[0], "key": pair[1], "value": val})
  tombstones = [
    {"type": pair[0], "key": pair[1]}
    for pair in sorted(prev_records)
    if pair not in next_records
  ]
  return {
    "base_rev": int(base_rev),
    "rev": int(next_rev),
    "upserts": upserts,
    "tombstones": tombstones,
  }


def apply_board_diff(base_board, diff_obj):
  """Apply a board record diff onto a base board dictionary."""
  if not isinstance(diff_obj, dict):
    raise TypeError("board diff must be an object")
  upserts = diff_obj.get("upserts")
  tombstones = diff_obj.get("tombstones")
  if not isinstance(upserts, list) or not isinstance(tombstones, list):
    raise TypeError("board diff requires upserts and tombstones arrays")
  records = decompose_board_records(base_board)
  for tomb in tombstones:
    if not isinstance(tomb, dict):
      continue
    rec_type = str(tomb.get("type") or "").strip()
    rec_key = str(tomb.get("key") or "").strip()
    if rec_type and rec_key:
      records.pop((rec_type, rec_key), None)
  for item in upserts:
    if not isinstance(item, dict):
      continue
    rec_type = str(item.get("type") or "").strip()
    rec_key = str(item.get("key") or "").strip()
    if rec_type and rec_key and "value" in item:
      records[(rec_type, rec_key)] = item["value"]
  return recompose_board_records(records)


def render_state_ndjson(core, history=None):
  """Render core and autosave history records as trailing-newline NDJSON."""
  rows = list(core or []) + list(history or [])
  if not rows:
    return ""
  return "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n"


class ProxySqliteEngine:
  """Shared SQLite WAL database and SHA-256 content-addressed blob store."""

  def __init__(self, state_dir):
    self.root = Path(state_dir)
    self.root.mkdir(parents=True, exist_ok=True)
    self.blobs_dir = self.root / "blobs"
    self.blobs_dir.mkdir(parents=True, exist_ok=True)
    self.db_path = self.root / "proxy.sqlite3"
    self.lock = threading.RLock()
    self._closed = False
    self.conn = sqlite3.connect(
      str(self.db_path),
      check_same_thread=False,
      isolation_level=None,
    )
    self.conn.row_factory = sqlite3.Row
    with self.lock:
      self.conn.execute("PRAGMA journal_mode=WAL")
      self.conn.execute("PRAGMA synchronous=NORMAL")
      self.conn.execute("PRAGMA foreign_keys=ON")
      self._init_schema()
      self.gc_orphan_blobs(scan_disk=True)

  def _init_schema(self):
    self.conn.executescript(
      """
      CREATE TABLE IF NOT EXISTS blobs (
        sha256 TEXT PRIMARY KEY,
        size INTEGER NOT NULL,
        created_at TEXT NOT NULL
      );

      CREATE TABLE IF NOT EXISTS board_meta (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
      );

      CREATE TABLE IF NOT EXISTS board_records (
        record_type TEXT NOT NULL,
        record_key TEXT NOT NULL,
        value_json TEXT,
        blob_sha256 TEXT NOT NULL DEFAULT '',
        deleted INTEGER NOT NULL DEFAULT 0,
        rev INTEGER NOT NULL,
        updated_at TEXT NOT NULL,
        PRIMARY KEY (record_type, record_key)
      );
      CREATE INDEX IF NOT EXISTS idx_board_records_rev ON board_records(rev);

      CREATE TABLE IF NOT EXISTS board_files (
        branch TEXT NOT NULL,
        name TEXT NOT NULL,
        sha256 TEXT NOT NULL,
        encoding TEXT NOT NULL,
        size INTEGER NOT NULL,
        staged INTEGER NOT NULL DEFAULT 1,
        rev INTEGER NOT NULL,
        updated_at TEXT NOT NULL,
        PRIMARY KEY (branch, name)
      );
      CREATE INDEX IF NOT EXISTS idx_board_files_sha256 ON board_files(sha256);

      CREATE TABLE IF NOT EXISTS board_client_cursors (
        branch TEXT PRIMARY KEY,
        client_rev INTEGER NOT NULL,
        board_json TEXT,
        blob_sha256 TEXT NOT NULL DEFAULT '',
        updated_at TEXT NOT NULL
      );

      CREATE TABLE IF NOT EXISTS state_scopes (
        scope_key TEXT PRIMARY KEY,
        repo TEXT NOT NULL,
        branch TEXT NOT NULL,
        revision INTEGER NOT NULL DEFAULT 0,
        min_rev INTEGER NOT NULL DEFAULT 1,
        save_id TEXT NOT NULL DEFAULT '',
        digest TEXT NOT NULL DEFAULT '',
        stamp TEXT NOT NULL DEFAULT '',
        lastsave TEXT,
        beforelastsave TEXT,
        counts_json TEXT NOT NULL DEFAULT '{}',
        stamps_json TEXT NOT NULL DEFAULT '{}',
        history_meta_json TEXT NOT NULL DEFAULT '[]',
        updated_at TEXT NOT NULL
      );
      CREATE INDEX IF NOT EXISTS idx_state_scopes_repo
        ON state_scopes(repo, updated_at DESC);

      CREATE TABLE IF NOT EXISTS state_records (
        scope_key TEXT NOT NULL,
        record_group TEXT NOT NULL,
        record_key TEXT NOT NULL,
        value_json TEXT,
        blob_sha256 TEXT NOT NULL DEFAULT '',
        deleted INTEGER NOT NULL DEFAULT 0,
        rev INTEGER NOT NULL,
        updated_at TEXT NOT NULL,
        PRIMARY KEY (scope_key, record_group, record_key)
      );
      CREATE INDEX IF NOT EXISTS idx_state_records_scope_rev
        ON state_records(scope_key, rev);
      """
    )
    for table in ("board_files", "board_client_cursors"):
      cols = {
        row["name"]
        for row in self.conn.execute(f"PRAGMA table_info({table})").fetchall()
      }
      if "session_id" in cols and "branch" not in cols:
        self.conn.execute(f"ALTER TABLE {table} RENAME COLUMN session_id TO branch")
        self.conn.commit()

  def blob_path(self, sha256):
    digest = str(sha256 or "").strip().lower()
    if not SHA256_RE.match(digest):
      raise ValueError("invalid-sha256")
    return self.blobs_dir / digest[:2] / digest

  def put_blob_bytes(self, raw_bytes):
    """Store raw bytes by SHA-256 digest once on disk and index in SQLite."""
    if not isinstance(raw_bytes, (bytes, bytearray)):
      raise TypeError("raw_bytes must be bytes")
    data = bytes(raw_bytes)
    digest = hashlib.sha256(data).hexdigest()
    target = self.blob_path(digest)
    with self.lock:
      if not target.is_file():
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(f"{digest}.{os.getpid()}.{threading.get_ident()}.tmp")
        tmp.write_bytes(data)
        os.replace(tmp, target)
      self.conn.execute(
        "INSERT OR IGNORE INTO blobs (sha256, size, created_at) VALUES (?, ?, ?)",
        (digest, len(data), now_iso()),
      )
    return digest, len(data)

  def get_blob_bytes(self, sha256):
    """Read and verify content-addressed bytes by SHA-256 digest."""
    digest = str(sha256 or "").strip().lower()
    if not SHA256_RE.match(digest):
      raise ValueError("invalid-sha256")
    target = self.blob_path(digest)
    if not target.is_file():
      return None
    data = target.read_bytes()
    if hashlib.sha256(data).hexdigest() != digest:
      return None
    return data

  def encode_json_cell(self, value):
    """Store small JSON inline and spill larger payloads to SHA-256 blobs."""
    text = canonical_json(value)
    encoded = text.encode("utf-8")
    if len(encoded) >= BLOB_INLINE_THRESHOLD:
      digest, _ = self.put_blob_bytes(encoded)
      return None, digest
    return text, ""

  def decode_json_cell(self, value_json, blob_sha256):
    """Decode an inline JSON cell or hydrate its content-addressed blob."""
    if blob_sha256:
      raw = self.get_blob_bytes(blob_sha256)
      if raw is None:
        return None
      return json.loads(raw.decode("utf-8"))
    if value_json is None:
      return None
    return json.loads(value_json)

  def _referenced_blob_digests_locked(self):
    referenced = set()
    for query in (
      "SELECT blob_sha256 AS sha FROM board_records WHERE blob_sha256 != '' AND deleted = 0",
      "SELECT sha256 AS sha FROM board_files WHERE sha256 != ''",
      "SELECT blob_sha256 AS sha FROM board_client_cursors WHERE blob_sha256 != ''",
      "SELECT blob_sha256 AS sha FROM state_records WHERE blob_sha256 != '' AND deleted = 0",
    ):
      for row in self.conn.execute(query).fetchall():
        digest = str(row["sha"] or "").strip().lower()
        if SHA256_RE.match(digest):
          referenced.add(digest)
    for row in self.conn.execute(
      "SELECT history_meta_json FROM state_scopes"
    ).fetchall():
      try:
        items = json.loads(row["history_meta_json"] or "[]")
      except ValueError:
        items = []
      if not isinstance(items, list):
        continue
      for item in items:
        if not isinstance(item, dict):
          continue
        digest = str(item.get("core_blob_sha256") or "").strip().lower()
        if SHA256_RE.match(digest):
          referenced.add(digest)
    return referenced

  def _unlink_blob_locked(self, digest):
    try:
      target = self.blob_path(digest)
    except ValueError:
      return False
    removed = False
    try:
      if target.is_file():
        target.unlink()
        removed = True
      if target.parent.is_dir() and not any(target.parent.iterdir()):
        target.parent.rmdir()
    except OSError:
      pass
    return removed

  def gc_orphan_blobs(self, *, scan_disk=False):
    """Delete unreferenced SQLite blob index rows and content-addressed files."""
    with self.lock:
      if self._closed:
        return {"removed_rows": 0, "removed_files": 0}
      referenced = self._referenced_blob_digests_locked()
      indexed = [
        str(row["sha256"] or "").strip().lower()
        for row in self.conn.execute("SELECT sha256 FROM blobs").fetchall()
      ]
      orphan_rows = [sha for sha in indexed if sha and sha not in referenced]
      removed_files = 0
      for sha in orphan_rows:
        if self._unlink_blob_locked(sha):
          removed_files += 1
      if orphan_rows:
        placeholders = ",".join("?" for _ in orphan_rows)
        self.conn.execute(
          f"DELETE FROM blobs WHERE sha256 IN ({placeholders})",
          tuple(orphan_rows),
        )
      if scan_disk and self.blobs_dir.is_dir():
        for shard_dir in list(self.blobs_dir.iterdir()):
          if not shard_dir.is_dir():
            continue
          for entry in list(shard_dir.iterdir()):
            if not entry.is_file() or entry.name.endswith(".tmp"):
              continue
            name = entry.name.strip().lower()
            if SHA256_RE.match(name) and name not in referenced:
              try:
                entry.unlink()
                removed_files += 1
              except OSError:
                pass
          try:
            if not any(shard_dir.iterdir()):
              shard_dir.rmdir()
          except OSError:
            pass
      return {"removed_rows": len(orphan_rows), "removed_files": removed_files}

  def close(self):
    with self.lock:
      if not self._closed:
        self._closed = True
        self.conn.close()


class StateStore:
  """Master-key save-state store backed by SQLite WAL and SHA-256 blobs."""

  def __init__(self, engine):
    if not isinstance(engine, ProxySqliteEngine):
      raise TypeError("engine must be a ProxySqliteEngine")
    self.engine = engine
    self.lock = engine.lock

  def _load_scope_row_locked(self, repo, branch="", fallback_repo=False):
    clean_repo = str(repo or "").strip()
    clean_branch = str(branch or "").strip()
    if not clean_repo:
      raise ValueError("repo is required")
    exact_key = state_scope_key(clean_repo, clean_branch)
    row = self.engine.conn.execute(
      "SELECT * FROM state_scopes WHERE scope_key = ?",
      (exact_key,),
    ).fetchone()
    if row is not None or not fallback_repo:
      return row
    return self.engine.conn.execute(
      "SELECT * FROM state_scopes WHERE repo = ? ORDER BY updated_at DESC LIMIT 1",
      (clean_repo,),
    ).fetchone()

  def _load_core_locked(self, scope_key):
    rows = self.engine.conn.execute(
      "SELECT value_json, blob_sha256 FROM state_records"
      " WHERE scope_key = ? AND deleted = 0",
      (scope_key,),
    ).fetchall()
    records = []
    for row in rows:
      decoded = self.engine.decode_json_cell(row["value_json"], row["blob_sha256"])
      if isinstance(decoded, dict):
        records.append(decoded)
    return sort_state_core(records)

  def _hydrate_history_locked(self, history_meta_json, fallback_core, scope_row):
    try:
      items = json.loads(history_meta_json or "[]")
    except ValueError:
      items = []
    hydrated = []
    for item in items:
      if not isinstance(item, dict):
        continue
      entry = dict(item)
      core_sha = entry.pop("core_blob_sha256", "")
      if core_sha:
        raw = self.engine.get_blob_bytes(core_sha)
        if raw is not None:
          try:
            entry["core"] = json.loads(raw.decode("utf-8"))
          except ValueError:
            entry["core"] = fallback_core
        else:
          entry["core"] = fallback_core
      elif not isinstance(entry.get("core"), list):
        entry["core"] = fallback_core
      hydrated.append(entry)
    if not hydrated and scope_row["save_id"] and scope_row["digest"]:
      hydrated.append(
        {
          "type": "userscript-autosave",
          "version": 1,
          "save_id": scope_row["save_id"],
          "scope": {"repo": scope_row["repo"], "branch": scope_row["branch"]},
          "digest": scope_row["digest"],
          "core": fallback_core,
          "stamp": scope_row["lastsave"] or scope_row["stamp"] or None,
          "confirmed_at": scope_row["updated_at"][:19],
          "receipts": {scope_row["save_id"]: scope_row["digest"]},
        }
      )
    return hydrated

  def get_state(
    self,
    repo,
    branch="",
    *,
    fallback_repo=False,
    since=None,
    mode="full",
    include_text=False,
  ):
    """Return full, unchanged, or incremental diff state for a repo/branch scope."""
    with self.lock:
      row = self._load_scope_row_locked(repo, branch, fallback_repo=fallback_repo)
      if row is None:
        return {
          "ok": True,
          "exists": False,
          "found": False,
          "revision": 0,
          "scope": {
            "repo": str(repo or "").strip(),
            "branch": str(branch or "").strip(),
          },
        }
      rev = int(row["revision"])
      min_rev = int(row["min_rev"])
      scope = {"repo": row["repo"], "branch": row["branch"]}
      counts = json.loads(row["counts_json"] or "{}")
      stamps = json.loads(row["stamps_json"] or "{}")
      base_meta = {
        "ok": True,
        "exists": True,
        "found": True,
        "revision": rev,
        "scope": scope,
        "save_id": row["save_id"],
        "digest": row["digest"],
        "stamp": row["stamp"],
        "lastsave": row["lastsave"],
        "beforelastsave": row["beforelastsave"],
        "counts": counts,
        "stamps": stamps,
      }
      if since is not None and since == rev and not include_text:
        return {**base_meta, "unchanged": True, "mode": mode or "full"}
      if (
        mode == "diff"
        and since is not None
        and min_rev <= since < rev
        and not include_text
      ):
        changed_rows = self.engine.conn.execute(
          "SELECT record_group, record_key, value_json, blob_sha256, deleted"
          " FROM state_records WHERE scope_key = ? AND rev > ?",
          (row["scope_key"], since),
        ).fetchall()
        upserts = []
        tombstones = []
        for item in changed_rows:
          if item["deleted"]:
            tombstones.append(
              {"group": item["record_group"], "key": item["record_key"]}
            )
          else:
            decoded = self.engine.decode_json_cell(
              item["value_json"], item["blob_sha256"]
            )
            if isinstance(decoded, dict):
              upserts.append(decoded)
        return {
          **base_meta,
          "unchanged": False,
          "mode": "diff",
          "diff": {
            "base_rev": int(since),
            "rev": rev,
            "upserts": upserts,
            "tombstones": tombstones,
          },
        }
      core = self._load_core_locked(row["scope_key"])
      history = self._hydrate_history_locked(row["history_meta_json"], core, row)
      result = {
        **base_meta,
        "unchanged": False,
        "mode": "full",
        "core": core,
        "history": history,
      }
      if include_text or mode != "diff":
        result["text"] = render_state_ndjson(core, history)
      return result

  def put_state(self, payload):
    """Apply a full snapshot or revision-cursor diff to SQLite WAL state."""
    if not isinstance(payload, dict):
      raise TypeError("state payload must be an object")
    repo = str(
      payload.get("repo") or (payload.get("scope") or {}).get("repo") or ""
    ).strip()
    branch = str(
      payload.get("branch")
      if "branch" in payload
      else (payload.get("scope") or {}).get("branch") or ""
    ).strip()
    if not repo:
      raise ValueError("repo is required")
    scope_key = state_scope_key(repo, branch)
    force = bool(payload.get("force"))
    diff_obj = payload.get("diff")
    raw_core = payload.get("core")
    if diff_obj is not None and not isinstance(diff_obj, dict):
      raise TypeError("diff must be an object")
    if raw_core is not None and not isinstance(raw_core, list):
      raise TypeError("core must be an array")
    if diff_obj is None and raw_core is None:
      raise ValueError("either core or diff is required")

    with self.lock:
      existing = self.engine.conn.execute(
        "SELECT * FROM state_scopes WHERE scope_key = ?",
        (scope_key,),
      ).fetchone()
      cur_rev = int(existing["revision"]) if existing is not None else 0
      min_rev = int(existing["min_rev"]) if existing is not None else 1

      if diff_obj is not None:
        base_rev = diff_obj.get("base_rev")
        if type(base_rev) is not int:
          raise TypeError("diff.base_rev must be an integer")
        if existing is None or base_rev != cur_rev:
          return {
            "ok": False,
            "error": "stale-revision",
            "need_full": True,
            "revision": cur_rev,
          }
        prev_core = self._load_core_locked(scope_key)
        next_core = apply_state_diff(prev_core, diff_obj)
      else:
        prev_core = self._load_core_locked(scope_key) if existing is not None else []
        next_core = sort_state_core(raw_core)

      digest = str(payload.get("digest") or "").strip()
      if not digest:
        digest = hashlib.sha256(canonical_json(next_core).encode("utf-8")).hexdigest()
      save_id = str(payload.get("save_id") or "").strip()
      stamp = str(payload.get("stamp") or "").strip()
      lastsave = payload.get("lastsave")
      if lastsave is not None:
        lastsave = str(lastsave).strip() or None
      else:
        lastsave = stamp or (existing["lastsave"] if existing is not None else None)
      beforelastsave = payload.get("beforelastsave")
      if beforelastsave is not None:
        beforelastsave = str(beforelastsave).strip() or None
      elif existing is not None:
        beforelastsave = existing["lastsave"]
      counts = payload.get("counts")
      if not isinstance(counts, dict):
        counts = core_counts(next_core)
      stamps = payload.get("stamps")
      if not isinstance(stamps, dict):
        stamps = {}

      if (
        not force
        and existing is not None
        and digest == existing["digest"]
        and lastsave == existing["lastsave"]
        and beforelastsave == existing["beforelastsave"]
      ):
        return {
          "ok": True,
          "unchanged": True,
          "revision": cur_rev,
          "scope": {"repo": repo, "branch": branch},
          "digest": digest,
          "save_id": save_id or existing["save_id"],
        }

      next_rev = cur_rev + 1
      if existing is None:
        min_rev = 1
      stamp_now = now_iso()
      delta = compute_state_diff(prev_core, next_core, cur_rev, next_rev)

      core_blob_sha, _ = self.engine.put_blob_bytes(
        canonical_json(next_core).encode("utf-8")
      )
      prev_history_meta = []
      raw_history = payload.get("history")
      if isinstance(raw_history, list) and raw_history:
        for h_raw in raw_history:
          if not isinstance(h_raw, dict):
            continue
          h_copy = dict(h_raw)
          h_core = h_copy.pop("core", None)
          if isinstance(h_core, list):
            h_sha, _ = self.engine.put_blob_bytes(
              canonical_json(sort_state_core(h_core)).encode("utf-8")
            )
            h_copy["core_blob_sha256"] = h_sha
          prev_history_meta.append(h_copy)
      elif existing is not None:
        try:
          prev_history_meta = json.loads(existing["history_meta_json"] or "[]")
        except ValueError:
          prev_history_meta = []
      receipts = {}
      for h_item in prev_history_meta:
        if isinstance(h_item, dict) and isinstance(h_item.get("receipts"), dict):
          receipts.update(h_item["receipts"])
      if save_id and digest:
        receipts[save_id] = digest
      new_hist_entry = {
        "type": "userscript-autosave",
        "version": 1,
        "save_id": save_id,
        "scope": {"repo": repo, "branch": branch},
        "digest": digest,
        "core_blob_sha256": core_blob_sha,
        "stamp": lastsave or stamp or None,
        "confirmed_at": stamp_now[:19],
        "receipts": dict(receipts),
      }
      kept_history = [
        dict(item, receipts=dict(receipts))
        for item in prev_history_meta[-1:]
        if isinstance(item, dict) and item.get("save_id") != save_id
      ]
      if save_id:
        kept_history.append(new_hist_entry)

      self.engine.conn.execute("BEGIN IMMEDIATE")
      try:
        for tomb in delta["tombstones"]:
          self.engine.conn.execute(
            "INSERT INTO state_records"
            " (scope_key, record_group, record_key, value_json, blob_sha256, deleted, rev, updated_at)"
            " VALUES (?, ?, ?, NULL, '', 1, ?, ?)"
            " ON CONFLICT(scope_key, record_group, record_key) DO UPDATE SET"
            " value_json = NULL, blob_sha256 = '', deleted = 1,"
            " rev = excluded.rev, updated_at = excluded.updated_at",
            (scope_key, tomb["group"], tomb["key"], next_rev, stamp_now),
          )
        for rec in delta["upserts"]:
          grp = state_record_group(rec)
          rec_key = state_record_key(rec)
          val_json, blob_sha = self.engine.encode_json_cell(rec)
          self.engine.conn.execute(
            "INSERT INTO state_records"
            " (scope_key, record_group, record_key, value_json, blob_sha256, deleted, rev, updated_at)"
            " VALUES (?, ?, ?, ?, ?, 0, ?, ?)"
            " ON CONFLICT(scope_key, record_group, record_key) DO UPDATE SET"
            " value_json = excluded.value_json, blob_sha256 = excluded.blob_sha256,"
            " deleted = 0, rev = excluded.rev, updated_at = excluded.updated_at",
            (scope_key, grp, rec_key, val_json, blob_sha, next_rev, stamp_now),
          )
        self.engine.conn.execute(
          "INSERT INTO state_scopes ("
          " scope_key, repo, branch, revision, min_rev, save_id, digest, stamp,"
          " lastsave, beforelastsave, counts_json, stamps_json, history_meta_json, updated_at"
          ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
          " ON CONFLICT(scope_key) DO UPDATE SET"
          " revision = excluded.revision,"
          " min_rev = excluded.min_rev,"
          " save_id = excluded.save_id,"
          " digest = excluded.digest,"
          " stamp = excluded.stamp,"
          " lastsave = excluded.lastsave,"
          " beforelastsave = excluded.beforelastsave,"
          " counts_json = excluded.counts_json,"
          " stamps_json = excluded.stamps_json,"
          " history_meta_json = excluded.history_meta_json,"
          " updated_at = excluded.updated_at",
          (
            scope_key,
            repo,
            branch,
            next_rev,
            min_rev,
            save_id,
            digest,
            stamp,
            lastsave,
            beforelastsave,
            canonical_json(counts),
            canonical_json(stamps),
            canonical_json(kept_history),
            stamp_now,
          ),
        )
        self.engine.conn.execute("COMMIT")
      except Exception:
        self.engine.conn.execute("ROLLBACK")
        raise
      self.engine.gc_orphan_blobs()

      return {
        "ok": True,
        "unchanged": False,
        "revision": next_rev,
        "scope": {"repo": repo, "branch": branch},
        "save_id": save_id,
        "digest": digest,
        "lastsave": lastsave,
        "beforelastsave": beforelastsave,
        "counts": counts,
      }
