"""Separate SQLite counters for browser fallback polling."""

from __future__ import annotations

import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path

FALLBACK_SECONDS = 3


class FallbackAnalytics:
  """Store cumulative client ticks without changing the steering state version."""

  def __init__(self, state_dir: str | Path | None) -> None:
    path = ":memory:"
    if state_dir is not None:
      path = str(Path(state_dir) / "fallback-analytics.sqlite3")
      Path(state_dir).mkdir(parents=True, exist_ok=True)
    self._lock = threading.RLock()
    self._conn = sqlite3.connect(path, check_same_thread=False, timeout=5)
    with self._lock, self._conn:
      self._conn.execute(
        "CREATE TABLE IF NOT EXISTS summary ("
        "singleton INTEGER PRIMARY KEY CHECK (singleton = 1), "
        "started_at TEXT NOT NULL, fallback_ticks INTEGER NOT NULL)"
      )
      self._conn.execute(
        "CREATE TABLE IF NOT EXISTS clients ("
        "client_id TEXT PRIMARY KEY, last_total INTEGER NOT NULL)"
      )
      self._conn.execute(
        "INSERT OR IGNORE INTO summary VALUES (1, ?, 0)",
        (datetime.now(UTC).isoformat(),),
      )

  def record(self, client_id: str, total: int) -> int:
    """Apply only new ticks from a client, including across retried writes."""
    with self._lock, self._conn:
      # Lock the side database before reading so concurrent server instances cannot double-count.
      self._conn.execute("BEGIN IMMEDIATE")
      row = self._conn.execute(
        "SELECT last_total FROM clients WHERE client_id = ?", (client_id,)
      ).fetchone()
      previous = int(row[0]) if row is not None else 0
      if total > previous:
        self._conn.execute(
          "INSERT INTO clients VALUES (?, ?) "
          "ON CONFLICT(client_id) DO UPDATE SET last_total = excluded.last_total",
          (client_id, total),
        )
        self._conn.execute(
          "UPDATE summary SET fallback_ticks = fallback_ticks + ? WHERE singleton = 1",
          (total - previous,),
        )
      return int(
        self._conn.execute(
          "SELECT fallback_ticks FROM summary WHERE singleton = 1"
        ).fetchone()[0]
      )

  def close(self) -> None:
    with self._lock:
      self._conn.close()

  def snapshot(
    self, now: datetime | None = None
  ) -> dict[str, str | int | float | None]:
    with self._lock:
      row = self._conn.execute(
        "SELECT started_at, fallback_ticks FROM summary WHERE singleton = 1"
      ).fetchone()
    started_at = str(row[0])
    count = int(row[1])
    elapsed = max(
      0.0,
      ((now or datetime.now(UTC)) - datetime.fromisoformat(started_at)).total_seconds(),
    )
    return {
      "started_at": started_at,
      "fallback_ticks": count,
      "elapsed_seconds": elapsed,
      "percent": 100 * count * FALLBACK_SECONDS / elapsed if elapsed else None,
    }
