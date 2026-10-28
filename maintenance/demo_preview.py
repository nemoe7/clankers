"""Start an isolated demo arena-skill server for UI prototyping."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
  from collections.abc import Sequence

ROOT = Path(__file__).resolve().parent.parent
PREVIEW_SCRIPT = ROOT / "skills" / "refs" / "arena-skill" / "scripts" / "preview.py"


def load_preview_module():
  scripts_dir = str(PREVIEW_SCRIPT.parent)
  if scripts_dir not in sys.path:
    sys.path.insert(0, scripts_dir)
  spec = importlib.util.spec_from_file_location("arena_preview_demo", PREVIEW_SCRIPT)
  if spec is None or spec.loader is None:
    raise RuntimeError(f"Unable to load preview module from {PREVIEW_SCRIPT}")
  module = importlib.util.module_from_spec(spec)
  spec.loader.exec_module(module)
  return module


def seed_demo_store(state_dir: Path):
  preview = load_preview_module()
  state_dir.mkdir(parents=True, exist_ok=True)
  store = preview.Store(state_dir, create=True)

  store.note(
    "d1a001",
    "Review worker changes and reports before asking for approval.",
  )
  store.acknowledge(
    ["d1a001"],
    "I will review worker changes and reports before requesting approval.",
  )
  store.note("d1a002", "Check the mobile report toolbar layout on portrait.")

  report_one_md = state_dir / "ui-audit-demo.md"
  report_one_md.write_text(
    "## Automated Findings\n\n"
    "| Rule | Diff | Verdict | Reason |\n"
    "| --- | --- | --- | --- |\n"
    "| `NUM201`: 4 px scale | ~~`gap: 10px`~~ ==`gap: 12px`== | `fix` | Aligns toolbar gap to 4 px scale |\n\n"
    "<!-- field: decision -->\n"
    "Shall we ship the updated report toolbar spacing?\n\n"
    "- (x) Ship 12 px toolbar gap\n"
    "- ( ) Keep 8 px toolbar gap\n"
    "- ( ) custom: ___\n",
    encoding="utf-8",
  )
  store.publish("ui-audit-demo", "UI Audit · Demo Report", report_one_md)

  report_two_md = state_dir / "architecture-demo.md"
  report_two_md.write_text(
    "## Multi-Session Flow\n\n"
    "```mermaid\n"
    "flowchart LR\n"
    "  Main[main] --> Board[/api/board]\n"
    "  Worker[worker-ui] --> Board\n"
    "```\n",
    encoding="utf-8",
  )
  store.publish("architecture-demo", "Architecture · Demo Flow", report_two_md)

  store.write_task(
    "prototype-messages-board",
    "Prototype interleaved board feed in Messages",
    ["Render board posts inline in #history and remove Wake buttons."],
    status="upcoming",
    task_type="code",
    scope="skills/refs/arena-skill/assets/",
  )
  store.write_task(
    "publish-ui-audit-demo",
    "Publish demo UI audit report",
    ["Published sample report with inline diff and decision field."],
    status="finished",
    task_type="report",
    scope="arena-state/ui-audit-demo.md",
  )

  branch = store.board_state()["branch"] or "arena/demo0001-clankers"
  store.board_action({"action": "allow", "branch": branch})
  store.board_action(
    {
      "action": "post",
      "branch": branch,
      "to": "*",
      "tag": "audit",
      "text": "Completed spacing audit on `#reports-panel` and verified mobile portrait.",
    }
  )
  store.board_action(
    {
      "action": "post",
      "branch": branch,
      "to": "*",
      "tag": "review",
      "text": "Verified the diff locally; all preview tests pass.",
    }
  )
  return preview, store


def build_parser() -> argparse.ArgumentParser:
  parser = argparse.ArgumentParser(
    prog="demo_preview.py",
    description="Launch an isolated demo arena-skill server with seeded data.",
  )
  parser.add_argument(
    "-d",
    "--dir",
    type=Path,
    default=None,
    help="Directory for demo state (defaults to a temporary directory).",
  )
  parser.add_argument(
    "-H",
    "--host",
    default="127.0.0.1",
    help="Bind address for the demo server (default: 127.0.0.1).",
  )
  parser.add_argument(
    "-p",
    "--port",
    type=int,
    default=8090,
    help="TCP port for the demo server (default: 8090).",
  )
  parser.add_argument(
    "-S",
    "--seed-only",
    action="store_true",
    help="Seed the demo state directory and print summary JSON without serving.",
  )
  return parser


def main(argv: Sequence[str] | None = None) -> int:
  args = build_parser().parse_args(argv)
  temp_ctx = (
    tempfile.TemporaryDirectory(prefix="arena-demo-") if args.dir is None else None
  )
  try:
    target_dir = (
      Path(temp_ctx.name) if temp_ctx is not None else Path(args.dir).resolve()
    )
    preview, store = seed_demo_store(target_dir)
    state = store.state()
    board = state.get("board") or {}
    summary = {
      "state_dir": str(target_dir),
      "url": f"http://{args.host}:{args.port}",
      "notes": len(state.get("notes") or []),
      "reports": len(state.get("reports") or []),
      "tasks": len(state.get("tasks") or []),
      "board_entries": len(board.get("entries") or []),
    }
    print(json.dumps(summary, indent=2), flush=True)
    if args.seed_only:
      return 0
    server = preview.ThreadingHTTPServer((args.host, args.port), preview.handler(store))
    try:
      server.serve_forever()
    except KeyboardInterrupt:
      return 0
    finally:
      server.server_close()
  finally:
    if temp_ctx is not None:
      temp_ctx.cleanup()
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
