#!/usr/bin/env python3
"""Seed sample Arena Steering data and launch a live demo server on a separate port."""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

from arena_steering.models import Attachment
from arena_steering.server import SteeringApp, create_http_server
from arena_steering.store import SqliteStore


def seed_demo_store(store: SqliteStore) -> SteeringApp:
  """Populate realistic Inbox, Tasks, and Reports records for UI inspection."""
  app = SteeringApp(store)

  if not app.messages.list_messages(unread_only=False, include_hidden=True):
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

    app.messages.send_message(
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

  if not app.reports.list_reports(stale_only=False):
    app.reports.publish_report(
      "steering-architecture",
      "Arena Steering: Architecture & UI Check",
      """# Arena Steering Architecture

Review the layout and interactive field controls below.

<!-- storage-mode -->
We should use this persistence mode
- (x) SQLite WAL mode with atomic queue updates
- ( ) In-memory ephemeral store

<!-- enabled-views -->
We should enable these steering views
- [x] Inbox messages with Markdown acknowledgements
- [x] Mutable dependency task queue
- [x] Fielded Markdown reports

Additional reviewer note: ___
""",
    )

  if not app.tasks.list_tasks(include_finished=True):
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
      "web-ui-assets",
      "Build unminified ES module web UI for Inbox, Tasks, and Reports",
      type="code",
      status="in_progress",
      scope="skills/arena-steering/assets/",
      details=[
        "Loaded dark and light Arena CSS tokens into style.css.",
        "Applied nuu recipes for modals, relative timestamps, and edge loading.",
      ],
      msg_ids=["a00002"],
      report_ids=["steering-architecture"],
      deps=["core-models-store"],
    )

  return app


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
  store = SqliteStore(state_dir / "state.sqlite3")
  app = seed_demo_store(store)
  if args.seed_only:
    store.close()
    print(f"Seeded demo state in {state_dir}")
    return 0

  httpd = create_http_server(app, host=args.host, port=args.port)
  print(f"Arena Steering demo listening on http://{args.host}:{args.port}")
  try:
    httpd.serve_forever()
  finally:
    store.close()
  return 0


if __name__ == "__main__":
  sys.exit(main())
