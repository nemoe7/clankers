#!/usr/bin/env python3
"""Seed sample Arena Steering data and launch a live demo server on a separate port."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

from arena_steering.models import Attachment
from arena_steering.server import SteeringApp, create_http_server
from arena_steering.store import SqliteStore


def _set_demo_timestamps(store: SqliteStore) -> None:
  """Spread demo timestamps across recent seconds, minutes, and hours."""
  now = datetime.now(UTC)

  def iso_ago(seconds: int) -> str:
    return (now - timedelta(seconds=seconds)).strftime("%Y-%m-%dT%H:%M:%SZ")

  msg_offsets = {
    "a00001": 7200,
    "a00002": 5400,
    "a00003": 3600,
    "a00004": 2400,
    "a00005": 900,
    "a00006": 420,
    "a00007": 150,
    "a00008": 75,
    "a00009": 65,
    "a00010": 55,
  }
  for idx in range(11, 36):
    msg_offsets[f"a{idx:05d}"] = 10800 + (36 - idx) * 600
  with store._lock, store._conn as conn:
    for mid, secs in msg_offsets.items():
      stamp = iso_ago(secs)
      conn.execute(
        "UPDATE messages SET modified_at = ? WHERE id = ?",
        (stamp, mid),
      )
    conn.execute(
      "UPDATE reports SET modified_at = ? WHERE id = 'steering-architecture'",
      (iso_ago(120),),
    )
    conn.execute(
      "UPDATE reports SET modified_at = ? WHERE id = 'ui-layout-audit'",
      (iso_ago(60),),
    )
    conn.execute(
      "UPDATE reports SET modified_at = ? WHERE id = 'runtime-metrics'",
      (iso_ago(320),),
    )
    conn.execute(
      "UPDATE tasks SET modified_at = ? WHERE status = 'in_progress'",
      (iso_ago(60),),
    )


def reseed_demo_store(store: SqliteStore) -> None:
  """Clear and populate realistic Messages, Tasks, and Reports across all states and types."""
  with store._lock, store._conn as conn:
    conn.execute("DELETE FROM messages")
    conn.execute("DELETE FROM tasks")
    conn.execute("DELETE FROM reports")
    conn.execute("DELETE FROM meta")

  store._seeding_demo = True  # type: ignore[attr-defined]
  try:
    app = SteeringApp(store)
  finally:
    store._seeding_demo = False  # type: ignore[attr-defined]

  # Seed historical messages (a00011..a00035) before recent messages so upward scroll paginates cleanly.
  for idx in range(11, 36):
    mid = f"a{idx:05d}"
    m_hist = app.messages.send_message(
      f"Historical steering checkpoint #{idx - 10}: verified schema migration step `{mid}`.",
      blocking=(idx % 3 != 0),
      hidden=(idx % 5 == 0),
      msg_id=mid,
    )
    app.messages.ack(
      m_hist.id,
      f"Completed checkpoint `{mid}` and updated validation fixtures.",
    )

  # 1. Messages covering sent, seen, acked (single + multi-ack), attachments (present + missing),
  #    fenced code blocks (bash, python, json), tables, blockquotes, and hidden notes.
  m1 = app.messages.send_message(
    "Establish the **Messages**, **Tasks**, and **Reports** contracts before implementation.",
    blocking=True,
    hidden=False,
    msg_id="a00001",
  )
  app.messages.ack(
    m1.id,
    "Locked the contracts in `steering-architecture` (`core-models-store`).",
  )

  m2 = app.messages.send_message(
    "Use Arena color tokens with `Basel_Grotesk` fonts and `nuu` interaction recipes.",
    blocking=True,
    hidden=False,
    attachments=[
      Attachment(
        name="arena-tokens.json",
        path="uploads/arena-tokens.json",
        size_bytes=29324,
        present=True,
      )
    ],
    msg_id="a00002",
  )
  app.messages.ack(
    m2.id,
    "Imported Arena dark-mode CSS custom properties into `assets/style.css` (`web-ui-assets`).",
  )
  app.messages.ack(
    m2.id,
    "Bundled all 5 `Basel_Grotesk_*.woff2` font weights with `@font-face` rules.",
  )

  m3 = app.messages.send_message(
    "Keep the server port configurable so the live demo can run alongside port 8000.",
    blocking=True,
    hidden=False,
    msg_id="a00003",
  )
  app.messages.ack(
    m3.id,
    (
      "Configured `steer serve --port` and `STEER_PORT` with default port `8100`:\n"
      "```bash\nsteer serve --port 8100\n```"
    ),
  )

  m4 = app.messages.send_message(
    "Internal checkpoint: verified SQLite WAL mode and foreign-key constraints.",
    blocking=False,
    hidden=True,
    msg_id="a00004",
  )
  app.messages.ack(
    m4.id,
    "Confirmed WAL journal mode and index coverage on `messages`, `tasks`, and `reports`.",
  )

  m5 = app.messages.send_message(
    "Ensure hot reload swaps the request handler in-process without dropping the TCP connection.",
    blocking=True,
    hidden=False,
    msg_id="a00005",
  )
  app.messages.ack(
    m5.id,
    (
      "Updated `watch_hot_reload` to reload `arena_steering` modules and swap "
      "`server.RequestHandlerClass` in-place (`hot-reload-server`):\n"
      "```python\n"
      "def reload_server_handler(server: ThreadingHTTPServer, app: SteeringApp) -> SteeringApp:\n"
      "    new_app = SteeringApp(new_store, assets_dir=app.assets_dir)\n"
      "    server.RequestHandlerClass = make_request_handler(new_app)\n"
      "    return new_app\n"
      "```"
    ),
  )

  m6 = app.messages.send_message(
    "Check how pruned or missing upload attachments render in the message log.",
    blocking=True,
    hidden=False,
    attachments=[
      Attachment(
        name="stale-heap-profile.json",
        path="uploads/stale-heap-profile.json",
        size_bytes=184320,
        present=False,
      )
    ],
    msg_id="a00006",
  )
  app.messages.ack(
    m6.id,
    "Verified that missing attachments render a muted `(missing)` indicator alongside the filename.",
  )

  # Messages in `seen` state (read by agent, awaiting acknowledgement)
  app.messages.send_message(
    "Preload ES module scripts in `index.html` so sub-imports resolve cleanly through `arena-preview-proxy`.",
    blocking=True,
    hidden=False,
    attachments=[
      Attachment(
        name="modulepreload-trace.txt",
        path="uploads/modulepreload-trace.txt",
        size_bytes=4120,
        present=True,
      )
    ],
    msg_id="a00007",
  )
  app.messages.send_message(
    "Also document the `STEER_PORT` and `STEER_STATE_DIR` environment variables in `SKILL.md`.",
    blocking=False,
    hidden=False,
    msg_id="a00008",
  )
  app.messages.read_pending(mark_seen=True)

  # Messages in `sent` state (unread by agent)
  app.messages.send_message(
    (
      "Verify that `/health` exposes `asset_version` so the browser hot-reloads assets:\n"
      "```json\n"
      '{\n  "ok": true,\n  "version": "2.0.0",\n  "repo": "clankers"\n}\n'
      "```"
    ),
    blocking=True,
    hidden=False,
    msg_id="a00009",
  )
  app.messages.send_message(
    "Confirm relative timestamps update with second-level resolution (`Ns ago` / `N seconds ago`).",
    blocking=True,
    hidden=False,
    msg_id="a00010",
  )

  # 2. Reports covering `published` (with choice/checkbox/text fields), `answered` (with acked + unacked answers),
  #    `published` (read-only technical report with table + code fence), and `dismissed`.
  app.reports.publish_report(
    "steering-architecture",
    "Arena Steering: Architecture & Storage Config",
    """# Arena Steering Architecture

Review the storage, transport, and rendering fields below. Answering this report unblocks `finalize-storage-tuning`.

## Subsystem Status

| Subsystem | Implementation | Transport / Storage | Latency Target | Status |
| --- | --- | --- | --- | --- |
| Persistence | `SqliteStore` (WAL mode) | `state.sqlite3` + WAL/SHM | `< 2.5 ms` p99 | Active |
| HTTP & RPC | `ThreadingHTTPServer` (`0.0.0.0:8100`) | REST + `/api/ws` WebSocket | `< 5.0 ms` p99 | Active |
| Markdown Cache | `markdown-it-py` + render cache | In-memory `(id, modified_at)` | `< 0.5 ms` hit | Active |
| Web UI | Unminified ES Modules + Arena CSS | Vendored PrismJS + Mermaid | `60 fps` scroll | Active |

## Request & Poll Topology

```mermaid
flowchart LR
  Browser[Browser UI] -->|WebSocket /api/ws| Router[SteeringApp Router]
  CLI[steer CLI] -->|GET /poll 1799s, POST /ack| Router
  Router --> Services[Message / Task / Report Services]
  Services --> Store[(SqliteStore WAL)]
```

## Server-Side Markdown Cache

Server-side rendering caches parsed blocks in memory by `(report_id, modified_at)` and evicts dismissed entries:

```python
_REPORT_RENDER_CACHE: dict[str, tuple[str, list[dict[str, Any]], list[dict[str, str]]]] = {}

def serialize_cached_report(report: Report) -> list[dict[str, Any]]:
    cached = _REPORT_RENDER_CACHE.get(report.id)
    if cached is not None and cached[0] == report.modified_at:
        return cached[1]
    raw_blocks, _ = parse_report_markdown(report.body)
    return [render_block(block) for block in raw_blocks]
```

## Diff & GFM Extensions

Highlighted ==critical path== updates and ~~deprecated polling flags~~ with unified diff tokenization:

```diff
@@ -18,4 +18,4 @@
-steer poll --timeout 30 --interval 2
+steer poll
-Inbox: 0 pending
+Inbox 14:22:09: 0 pending
```

- [x] Indefinite server-side HTML cache keyed by `modified_at`
- [x] Vendored PrismJS syntax highlighting with GitHub Dark Dimmed tokens
- [x] Hybrid TOC scrollspy with click-lock and bottom-of-page clamp

## Storage & View Options

<!-- storage-mode -->
We should use this SQLite synchronous mode
- (x) NORMAL with WAL journal mode for low-latency writes
- ( ) FULL synchronous mode on every transaction
- ( ) MEMORY journal mode for ephemeral runs

<!-- enabled-views -->
We should enable these live steering capabilities
- [x] Inbox messages with Markdown acknowledgements
- [x] Agent-managed dependency task queue
- [x] Fielded Markdown reports with custom responses
- [ ] Experimental webhook forwarding

## Reviewer Notes

Additional reviewer note: ___
""",
  )

  app.reports.publish_report(
    "ui-layout-audit",
    "UI Layout & Typography Audit",
    """# UI Layout & Typography Audit

Summary of layout adjustments across the **Messages**, **Reports**, and **Tasks** tabs:

## Alignment Contract

> All three tab panels share a `900px` max-width container with a `100vw` Messages scrollbar.

```css
.app-shell {
  display: flex;
  flex-direction: column;
  height: 100dvh;
  overflow: hidden;
}

.report-content pre,
.report-content .mermaid-block {
  width: 100%;
  box-sizing: border-box;
}
```

## Scrollspy & Mobile Navigation

```javascript
export function lockTocSelection(secId, durationMs = 700) {
  tocLockUntil = Date.now() + durationMs;
  setActiveTocLink(secId);
}
```

## Verification Questions

<!-- density-mode -->
Preferred spacing density across list views
- (x) Compact borderless rows with 2ch hanging indent
- ( ) Padded card containers

<!-- verified-tabs -->
Tabs verified in live preview
- [x] Messages tab
- [x] Reports tab
- [x] Tasks tab
""",
  )
  ans1 = app.reports.submit_answer(
    "ui-layout-audit",
    {
      "density-mode": "Compact borderless rows with 2ch hanging indent",
      "verified-tabs": ["Messages tab", "Reports tab", "Tasks tab"],
    },
    answer_id="f00001",
  )
  app.reports.ack_answer(
    "ui-layout-audit",
    ans1.id,
    (
      "Applied compact borderless rows across **Reports** and **Tasks** "
      "and verified `2ch` list alignment (`web-ui-assets`)."
    ),
  )
  app.reports.submit_answer(
    "ui-layout-audit",
    {
      "density-mode": "Compact borderless rows with 2ch hanging indent",
      "verified-tabs": ["Messages tab", "Reports tab"],
    },
    answer_id="f00002",
  )

  app.reports.publish_report(
    "runtime-metrics",
    "Runtime Poll & SQLite Latency Benchmark",
    """# Runtime Poll & SQLite Latency Benchmark

Read-only benchmark report comparing SQLite WAL queries and long-poll wakeup latency.

## Latency Summary

| Operation | p50 Latency | p99 Latency | Throughput | Notes |
| --- | --- | --- | --- | --- |
| `POST /messages` | `0.8 ms` | `2.1 ms` | `1,150 req/s` | Atomic insert + `Condition.notify_all()` |
| `GET /poll` | `1.1 ms` | `3.4 ms` | `940 req/s` | Immediate wake on new message or report answer |
| `GET /tasks?full=1` | `0.6 ms` | `1.5 ms` | `1,620 req/s` | Computed `blocked` state across dependencies |

## SQLite Schema & Indexing

```sql
CREATE TABLE IF NOT EXISTS reports (
  seq INTEGER PRIMARY KEY AUTOINCREMENT,
  id TEXT NOT NULL UNIQUE,
  title TEXT NOT NULL,
  body TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'published'
);
```

## CLI Poll Command

```bash
steer poll
```
""",
  )

  app.reports.publish_report(
    "legacy-migration-draft",
    "Legacy Preview Migration Notes",
    "# Legacy Migration Notes\n\nArchived draft superseded by `steering-architecture`.",
  )
  app.reports.remove_report("legacy-migration-draft")

  # 3. Tasks covering `Current` (`in_progress`), `Upcoming` (`upcoming` unblocked + blocked by report + blocked by dep),
  #    and `Finished` (`finished`, 35 total so downward scroll paginates 30 + 5), across all 5 types.
  app.tasks.create_task(
    "core-models-store",
    "Build domain models, protocol ports, and SQLite store",
    type="code",
    status="finished",
    scope="skills/arena-steering/scripts/arena_steering/",
    details=[
      "Defined Message, Task, Report, ReportField, and ReportAnswer models.",
      "Implemented thread-safe SqliteStore in WAL mode.",
    ],
    msg_ids=["a00001"],
  )
  app.tasks.create_task(
    "draft-architecture-spec",
    "Publish initial Arena Steering architecture specification",
    type="report",
    status="finished",
    scope="arena-state/reports/",
    details=[
      "Published steering-architecture report with choice, checkbox, and text fields.",
    ],
    msg_ids=["a00001"],
    report_ids=["steering-architecture"],
  )
  app.tasks.create_task(
    "configure-ci-gates",
    "Wire ruff, pytest, and prose lint gates for steering skill",
    type="ops",
    status="finished",
    scope="maintenance/",
    details=[
      "Configured pytest and ruff validation suites for arena_steering.",
    ],
    msg_ids=["a00004"],
  )
  app.tasks.create_task(
    "update-readme-index",
    "Register arena-steering in repository skill documentation",
    type="docs",
    status="finished",
    scope="skills/arena-steering/SKILL.md",
    details=[
      "Documented steer CLI workflow and REST API endpoints.",
    ],
  )
  task_types = ("code", "docs", "report", "ops", "misc")
  for idx in range(1, 32):
    app.tasks.create_task(
      f"finished-milestone-{idx:02d}",
      f"Complete steering verification milestone #{idx:02d}",
      type=task_types[idx % len(task_types)],
      status="finished",
      scope="skills/arena-steering/",
      details=[
        f"Verified milestone #{idx:02d} regression suite and UI state.",
      ],
    )

  app.tasks.create_task(
    "web-ui-assets",
    "Refine Inbox, Reports, and Tasks views with Arena tokens",
    type="code",
    status="in_progress",
    scope="skills/arena-steering/assets/",
    details=[
      "Loaded Arena dark-mode CSS tokens and Basel Grotesk fonts into style.css.",
      "Rendered fenced code blocks with language headers and copy buttons.",
      "Restored three-column Reports layout with TOC and scrollable report picker.",
    ],
    msg_ids=["a00002", "a00006"],
    deps=["core-models-store"],
  )
  app.tasks.create_task(
    "hot-reload-server",
    "Maintain in-process hot-reload watcher on port 8100",
    type="ops",
    status="in_progress",
    scope="skills/arena-steering/scripts/arena_steering/server.py",
    details=[
      "Swaps server.RequestHandlerClass in-process without dropping TCP connections.",
      "Includes asset_version hash in /health for browser live reload.",
    ],
    msg_ids=["a00003", "a00005"],
  )

  app.tasks.create_task(
    "publish-audit-report",
    "Publish layout and latency audit report for review",
    type="report",
    status="upcoming",
    scope="arena-state/reports/",
    details=[
      "Summarizes viewport scrollbar alignment and SQLite WAL latency.",
    ],
    msg_ids=["a00007"],
    report_ids=["ui-layout-audit"],
  )
  app.tasks.create_task(
    "finalize-storage-tuning",
    "Apply selected SQLite journal and synchronous parameters",
    type="code",
    status="upcoming",
    scope="skills/arena-steering/scripts/arena_steering/store.py",
    details=[
      "Awaiting storage-mode selection in steering-architecture report.",
    ],
    report_ids=["steering-architecture"],
  )
  app.tasks.create_task(
    "document-cli-reference",
    "Document steer CLI subcommands and environment variables",
    type="docs",
    status="upcoming",
    scope="skills/arena-steering/SKILL.md",
    details=[
      "Cover STEER_PORT, STEER_STATE_DIR, and long-poll timeout flags.",
    ],
    msg_ids=["a00008"],
    deps=["web-ui-assets"],
  )
  app.tasks.create_task(
    "cleanup-temp-fixtures",
    "Prune stale preview fixture directories and verify gitignore",
    type="misc",
    status="upcoming",
    scope="tests/skills/arena-steering/",
    details=[
      "Ensure temporary SQLite WAL files are cleaned up after test runs.",
    ],
  )

  # 4. Seed sample survey results so the Survey Results modal (#survey-modal) displays graded checks.
  app.messages.submit_survey(
    json.dumps(
      [
        {"id": "R3S0N", "answer": {"reasoning": True}},
        {"id": "V1S0N", "answer": {"vision": True}},
        {
          "id": "S2E5P",
          "answer": {
            "full_name": "unknown",
            "organization": "unknown",
            "role": "unknown",
          },
          "confidence": 0,
        },
        {
          "id": "A2P6R",
          "answer": {
            "command_name": "REPACK",
            "concurrency_option": "CONCURRENTLY",
          },
          "confidence": 0.95,
        },
        {
          "id": "M2A6Y",
          "answer": {
            "data_center": "unknown",
            "power_capacity_mw": {"operator": "unknown", "value": "unknown"},
            "nvidia_gpu_count": {"operator": "unknown", "value": "unknown"},
          },
          "confidence": 0,
        },
      ]
    )
  )

  _set_demo_timestamps(store)


def seed_demo_store(store: SqliteStore) -> SteeringApp:
  """Populate realistic Inbox, Tasks, and Reports records for UI inspection."""
  reseed_demo_store(store)
  store._seeding_demo = True  # type: ignore[attr-defined]
  try:
    return SteeringApp(store)
  finally:
    store._seeding_demo = False  # type: ignore[attr-defined]


def main(argv: list[str] | None = None) -> int:
  default_port = int(os.environ.get("STEER_DEMO_PORT", "8100"))
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("--host", default="0.0.0.0")
  parser.add_argument("--port", type=int, default=default_port)
  parser.add_argument(
    "--state-dir",
    default=None,
    help="Directory for demo state.sqlite3 (default: temporary directory).",
  )
  parser.add_argument(
    "--seed-only",
    action="store_true",
    help="Seed the state database and exit without starting the HTTP server.",
  )
  args = parser.parse_args(argv)

  state_dir = (
    Path(args.state_dir)
    if args.state_dir
    else Path(tempfile.mkdtemp(prefix="arena-steering-demo-"))
  )
  state_dir.mkdir(parents=True, exist_ok=True)
  db_path = state_dir / "state.sqlite3"
  store = SqliteStore(db_path)
  app = seed_demo_store(store)

  if args.seed_only:
    print(f"Seeded Arena Steering demo database at {db_path}")
    return 0

  server = create_http_server(app, host=args.host, port=args.port)
  actual_port = server.server_address[1]
  print(
    f"Arena Steering v2 demo listening on http://{args.host}:{actual_port} (db: {db_path})",
    flush=True,
  )
  try:
    server.serve_forever()
  except KeyboardInterrupt:
    pass
  finally:
    server.server_close()
  return 0


if __name__ == "__main__":
  sys.exit(main())
