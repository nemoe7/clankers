"""Command-line interface (`steer`) for Arena Steering."""

from __future__ import annotations

import argparse
import json
import re
import shlex
import sqlite3
import subprocess
import sys
import urllib.error
import urllib.request
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import TextIO

from . import __version__
from . import pre as pre_mod
from .gates import FileGateStatus
from .models import MESSAGE_ID_RE, Message, Report, ReportAnswer, Task
from .server import SteeringApp, create_http_server
from .services import MessageService, ReportService, TaskService
from .store import SqliteStore

BIND_HOST = "0.0.0.0"
SERVE_PORT = 8000
HISTORICAL_PAGE_SIZE = 10
MESSAGE_PAGE_MIN = 5
MESSAGE_PAGE_MAX = 50


def _snippet_words(text: str, max_words: int = 6) -> str:
  words = str(text or "").split()
  if not words:
    return ""
  if len(words) <= max_words:
    return " ".join(words)
  return " ".join(words[:max_words]) + "..."


def resolve_state_dir() -> Path:
  """Return the fixed state directory for this working directory."""
  path = Path("arena-state")
  path.mkdir(parents=True, exist_ok=True)
  return path


def open_services(
  state_dir: Path,
) -> tuple[SqliteStore, MessageService, TaskService, ReportService]:
  """Open SqliteStore and domain services for a state directory."""
  # Restore state.sqlite3 after v1 is retired and its database no longer collides.
  store = SqliteStore(state_dir / "steering-v2.sqlite3")
  messages = MessageService(store, store, store)
  tasks = TaskService(store, store, gates=FileGateStatus(state_dir))
  reports = ReportService(store, store, on_answer_callback=messages.notify_new_work)
  return store, messages, tasks, reports


def main(
  argv: list[str] | None = None,
  *,
  out: TextIO | None = None,
  err: TextIO | None = None,
) -> int:
  """Run a `steer` CLI command and return its exit code."""
  stdout = out if out is not None else sys.stdout
  stderr = err if err is not None else sys.stderr
  args_list = list(sys.argv[1:] if argv is None else argv)

  if args_list in (["--version"], ["-V"]):
    print(f"steer {__version__}", file=stdout)
    return 0

  parser = argparse.ArgumentParser(
    prog="steer",
    description="Steer an Arena agent through inbox messages, tasks, and reports.",
  )
  parser.add_argument(
    "-V",
    "--version",
    action="version",
    version=f"steer {__version__}",
  )
  sub = parser.add_subparsers(dest="command")

  serve_p = sub.add_parser("serve", help="Start the local steering HTTP server.")

  read_p = sub.add_parser("read", help="Read pending messages and report answers.")

  poll_p = sub.add_parser("poll", help="Wait for pending messages or skip_poll.")

  ack_p = sub.add_parser("ack", help="Acknowledge a message or report answer.")
  ack_p.add_argument("parts", nargs="+", help="[<id> ...] <markdown>")
  ack_p.add_argument("-i", "--id", dest="task_id", default=None)
  ack_p.add_argument("-t", "--title", dest="task_title", default=None)
  ack_p.add_argument("-T", "--type", dest="task_type", default="code")
  ack_p.add_argument("-S", "--scope", dest="task_scope", default="")
  ack_p.add_argument("-d", "--detail", dest="task_details", action="append", default=[])

  msg_p = sub.add_parser("msg", help="List or inspect stored messages.")
  msg_p.add_argument("id", nargs="?", help="Message ID, or list for history.")
  msg_list_p = argparse.ArgumentParser(
    prog="steer msg list", description="List messages newest-first."
  )
  msg_list_p.add_argument("-p", "--page", type=int, default=1)
  msg_list_p.add_argument("-s", "--page-size", type=int, default=MESSAGE_PAGE_MIN)
  msg_show_p = argparse.ArgumentParser(
    prog="steer msg", description="Show one message by ID."
  )
  msg_show_p.add_argument("id")

  tasks_p = sub.add_parser("tasks", help="List upcoming tasks (or finished with -f).")
  tasks_p.add_argument(
    "-f", "--finished", "--full", dest="finished", action="store_true"
  )
  tasks_p.add_argument("-p", "--page", type=int, default=1)

  task_p = sub.add_parser(
    "task",
    help="Show, create, remove, or modify a task.",
    usage="%(prog)s <id|new|rm|mod|unlink> ...",
    formatter_class=argparse.RawDescriptionHelpFormatter,
    epilog=(
      "Commands:\n"
      "  ID                                  Show a task.\n"
      "  new ID TITLE -d DETAIL [options]    Create a task.\n"
      "  rm ID                               Remove a task.\n"
      "  mod ID FIELD [rm] VALUE             Update a task.\n"
      "  unlink ID [TYPE] LINK               Remove a task link."
    ),
  )

  reports_p = sub.add_parser("reports", help="List active or stale reports (10/page).")
  reports_p.add_argument("-s", "--stale", action="store_true")
  reports_p.add_argument("-p", "--page", type=int, default=1)

  report_p = sub.add_parser(
    "report",
    help="Show, publish, or remove a report.",
    usage="%(prog)s <id|pub|pin|unpin|rm> ...",
    formatter_class=argparse.RawDescriptionHelpFormatter,
    epilog=(
      "Commands:\n"
      "  ID                          Show a report.\n"
      "  pub FILE -i ID -t TITLE     Publish a report.\n"
      "  pin ID                      Pin a report.\n"
      "  unpin ID                    Unpin a report.\n"
      "  rm ID [ID ...] | --stale    Remove reports."
    ),
  )

  survey_p = sub.add_parser("survey", help="Inspect or submit bible survey answers.")
  survey_p.add_argument("entries", nargs="*", help="[<json-array> | <key=value> ...]")
  survey_p.add_argument(
    "-i",
    "--smallest-image",
    action="store_true",
    help="Print path to smallest image in workspace for V1S0N check.",
  )
  survey_p.add_argument(
    "-f",
    "--file",
    default=None,
    help="Read survey JSON array submission from file.",
  )
  survey_p.add_argument(
    "--template",
    action="store_true",
    help="Print the unfilled JSON array template.",
  )

  ren_p = sub.add_parser("ren", help="Move a task or report to a new ID.")
  ren_p.add_argument("old_id")
  ren_p.add_argument("new_id")

  pr_update_p = sub.add_parser(
    "pr-update", help="Update a pull request title and body via gh and verify parity."
  )
  pr_update_p.add_argument("-n", "--number", type=int, required=True)
  pr_update_p.add_argument("-t", "--title", required=True)
  pr_update_p.add_argument("-f", "--body-file", required=True)

  job_log_p = sub.add_parser("job-log", help="Print a GitHub Actions log via gh.")
  job_log_p.add_argument("-j", "--job", dest="job_id", default=None)
  job_log_p.add_argument("-r", "--run", dest="run_id", default=None)

  gate_p = sub.add_parser(
    "gate", help="Refuse a shell command while the inbox has pending items."
  )
  gate_p.add_argument(
    "-p", "--push", action="store_true", help="Gate a push instead of a command."
  )
  gate_p.add_argument(
    "-l", "--line", default="", help="Command line passed by the shell hook."
  )

  pre_p = sub.add_parser("pre", help="Run the pre-command pipeline for a shell line.")
  pre_p.add_argument("-l", "--line", default="", help="Whole shell line.")
  pre_p.add_argument(
    "-c", "--command", dest="command_text", default="", help="Command the trap reached."
  )
  pre_p.add_argument("-s", "--shell", default="", help="Shell name, such as bash.")
  pre_p.add_argument(
    "-d", "--done", default="", help="Steps this shell already finished."
  )

  skills_p = sub.add_parser("skills", help="List skill names, descriptions, and paths.")

  worktree_p = sub.add_parser(
    "worktree",
    help="Manage native git worktrees under .worktrees/.",
    usage="%(prog)s <add|list|remove|prune|collect> ...",
    formatter_class=argparse.RawDescriptionHelpFormatter,
    epilog=(
      "Commands:\n"
      "  add NAME [-b BRANCH]    Add a worktree.\n"
      "  list                    List worktrees.\n"
      "  remove NAME             Remove a worktree.\n"
      "  prune                   Prune worktree records.\n"
      "  collect NAME            Print a worktree patch."
    ),
  )
  run_p = sub.add_parser(
    "run",
    help="Start detached runs and read their logs.",
    usage="%(prog)s <start|logs|pr-checks> ...",
    formatter_class=argparse.RawDescriptionHelpFormatter,
    epilog=(
      "Commands:\n"
      "  start [-t TASK] [-a RUN] NAME -- COMMAND    Start a detached run.\n"
      "  logs NAME [-n LINES]                        Read run status and logs.\n"
      "  pr-checks [-n NUMBER]                       Watch PR checks."
    ),
  )

  remaining = args_list
  if not remaining:
    parser.print_help(file=stdout)
    return 0

  cmd = remaining[0]
  cmd_args = remaining[1:]
  group_parsers = {
    "task": task_p,
    "report": report_p,
    "worktree": worktree_p,
    "run": run_p,
  }
  if cmd in group_parsers and cmd_args in (["-h"], ["--help"]):
    group_parsers[cmd].print_help(file=stdout)
    return 0

  resolved_state_dir = resolve_state_dir()
  store, messages, tasks, reports = open_services(resolved_state_dir)
  try:
    if cmd == "serve":
      serve_p.parse_args(cmd_args)
      app = SteeringApp(store)
      httpd = create_http_server(app, host=BIND_HOST, port=SERVE_PORT)
      port = int(httpd.server_address[1])
      server_file = resolved_state_dir / "server.json"
      server_file.write_text(
        json.dumps({"host": BIND_HOST, "port": port}, indent=2),
        encoding="utf-8",
      )
      print(f"Steering server listening on http://{BIND_HOST}:{port}", file=stdout)
      try:
        httpd.serve_forever()
      finally:
        server_file.unlink(missing_ok=True)
        httpd.server_close()
      return 0
    if cmd == "gate":
      parsed = gate_p.parse_args(cmd_args)
      return _run_gate(messages, parsed, stdout)
    if cmd == "pre":
      parsed = pre_p.parse_args(cmd_args)
      return _run_pre(parsed, messages, store, stdout)
    if cmd == "skills":
      skills_p.parse_args(cmd_args)
      return _run_skills(stdout)
    if cmd == "read":
      read_p.parse_args(cmd_args)
      _print_restore_notice(store, stdout)
      delivered = messages.read_pending(mark_seen=True)
      _print_delivered(delivered, stdout)
      _reset_call_count(store)
      return 0
    if cmd == "poll":
      poll_p.parse_args(cmd_args)
      _print_restore_notice(store, stdout)
      delivered = messages.poll(timeout_seconds=1799.0)
      _print_delivered(delivered, stdout)
      _reset_call_count(store)
      return 0
    if cmd == "ack":
      parsed = ack_p.parse_args(cmd_args)
      return _run_ack(parsed, messages, tasks, store, stdout)
    if cmd == "msg":
      return _run_msg(cmd_args, msg_list_p, msg_show_p, messages, stdout)
    if cmd == "tasks":
      parsed = tasks_p.parse_args(cmd_args)
      all_items = tasks.list_tasks(include_finished=parsed.finished)
      if parsed.finished:
        finished_only = [(t, b) for t, b in all_items if t.status == "finished"]
        page = max(1, int(parsed.page))
        start = (page - 1) * HISTORICAL_PAGE_SIZE
        paged = finished_only[start : start + HISTORICAL_PAGE_SIZE]
        _print_task_list(paged, stdout)
      else:
        _print_task_list(all_items, stdout)
      return 0
    if cmd == "task":
      return _run_task(cmd_args, tasks, stdout)
    if cmd == "reports":
      parsed = reports_p.parse_args(cmd_args)
      all_reports = reports.list_reports(stale_only=parsed.stale)
      page = max(1, int(parsed.page))
      start = (page - 1) * HISTORICAL_PAGE_SIZE
      _print_reports_list(all_reports[start : start + HISTORICAL_PAGE_SIZE], stdout)
      return 0
    if cmd == "report":
      return _run_report(cmd_args, reports, store, stdout)
    if cmd == "survey":
      parsed = survey_p.parse_args(cmd_args)
      return _run_survey(parsed, messages, stdout, resolved_state_dir)
    if cmd == "ren":
      parsed = ren_p.parse_args(cmd_args)
      return _run_rename(parsed, tasks, reports, stdout)
    if cmd == "pr-update":
      parsed = pr_update_p.parse_args(cmd_args)
      return _run_pr_update(parsed, stdout)
    if cmd == "job-log":
      parsed = job_log_p.parse_args(cmd_args)
      return _run_job_log(parsed, stdout)
    if cmd == "worktree":
      return _run_worktree(cmd_args, stdout)
    if cmd == "run":
      return _run_run(cmd_args, resolved_state_dir, stdout, tasks, store)
    if cmd == "init":
      raise ValueError(
        "steer has no init --tz; the browser sets timezone with POST /api/timezone"
      )

    parsed_root = parser.parse_args(remaining)
    if not parsed_root.command:
      parser.print_help(file=stdout)
    return 0
  except (KeyError, ValueError, IndexError, OSError, RuntimeError) as exc:
    msg = exc.args[0] if isinstance(exc, KeyError) and exc.args else str(exc)
    print(f"Steer error: {msg}", file=stderr)
    return 1
  finally:
    store.close()


def _run_ack(
  parsed: argparse.Namespace,
  messages: MessageService,
  tasks: TaskService,
  store: SqliteStore,
  out: TextIO,
) -> int:
  parts: list[str] = parsed.parts
  target_ids: list[str | None] = list(parts[:-1]) or [None]
  markdown = parts[-1]
  if any(
    target is not None and not MESSAGE_ID_RE.fullmatch(target) for target in target_ids
  ):
    raise ValueError("Usage: steer ack [<6-char-hex-id> ...] '<markdown>'")

  created = None
  with store.transaction():
    if parsed.task_id:
      if len(target_ids) != 1:
        raise ValueError("Task creation on ack requires one target")
      if not parsed.task_title:
        raise ValueError("Task creation on ack requires -t/--title")
      target_type, target = messages.resolve_ack_target(target_ids[0])
      created = tasks.create_task(
        parsed.task_id,
        parsed.task_title,
        type=parsed.task_type,
        scope=parsed.task_scope,
        details=parsed.task_details,
        msg_ids=[target.id] if target_type == "message" else [],
        report_ids=[target.report_id] if target_type == "report_answer" else [],
      )
      target_ids = [target.id]
    acked_ids = [messages.ack(target, markdown)[1].id for target in target_ids]
  print(f"ok {' '.join(acked_ids)}", file=out)
  if created:
    _, blocked = tasks.get_task(created.id)
    _print_single_task(created, blocked, out)
  return 0


def _run_msg(
  args: list[str],
  list_parser: argparse.ArgumentParser,
  show_parser: argparse.ArgumentParser,
  messages: MessageService,
  out: TextIO,
) -> int:
  if not args or args[0] == "list":
    parsed = list_parser.parse_args(args[1:] if args else [])
    if not MESSAGE_PAGE_MIN <= parsed.page_size <= MESSAGE_PAGE_MAX:
      raise ValueError("Message page size must be between 5 and 50")
    items = messages.list_messages(
      unread_only=False,
      include_hidden=True,
      newest_first=True,
      page=parsed.page,
      page_size=parsed.page_size,
    )
    if not items:
      print("No messages.", file=out)
      return 0
    for item in items:
      snippet = _snippet_words(item.body, max_words=6)
      print(f"{item.id} {snippet}".rstrip(), file=out)
    return 0
  parsed = show_parser.parse_args(args)
  item = messages.get_message(parsed.id)
  _print_message(item, out)
  return 0


def _run_task(args: list[str], tasks: TaskService, out: TextIO) -> int:
  if not args:
    raise ValueError("Usage: steer task <id|new|rm|mod> ...")
  subcmd = args[0]
  if subcmd == "new":
    new_p = argparse.ArgumentParser(prog="steer task new")
    new_p.add_argument("id")
    new_p.add_argument("title")
    new_p.add_argument("-T", "--type", default="code")
    new_p.add_argument("-s", "--status", default="upcoming")
    new_p.add_argument("-S", "--scope", default="")
    new_p.add_argument("-d", "--detail", action="append", default=[])
    new_p.add_argument("-m", "--msg", action="append", default=[])
    new_p.add_argument("-r", "--report", action="append", default=[])
    new_p.add_argument("-g", "--gate", action="append", default=[])
    new_p.add_argument(
      "-k", "--task", "--dep", dest="task_ids", action="append", default=[]
    )
    parsed = new_p.parse_args(args[1:])
    task = tasks.create_task(
      parsed.id,
      parsed.title,
      type=parsed.type,
      status=parsed.status,
      scope=parsed.scope,
      details=parsed.detail,
      links={
        "msg_ids": parsed.msg,
        "report_ids": parsed.report,
        "task_ids": parsed.task_ids,
        "gate_names": parsed.gate,
      },
    )
    _, blocked = tasks.get_task(task.id)
    _print_single_task(task, blocked, out)
    return 0

  if subcmd == "rm":
    if len(args) != 2:
      raise ValueError("Usage: steer task rm <id>")
    removed = tasks.remove_task(args[1])
    if not removed:
      raise KeyError(f"Unknown task ID: {args[1]}")
    print(f"Removed task {args[1]}", file=out)
    return 0

  if subcmd == "mod":
    return _run_task_mod(args[1:], tasks, out)

  if subcmd == "unlink":
    if len(args) == 3:
      updated = tasks.unlink_task(args[1], args[2])
    elif len(args) == 4:
      updated = tasks.unlink_task(args[1], args[3], link_type=args[2])
    else:
      raise ValueError(
        "Usage: steer task unlink <id> [<msg|report|task|gate>] <link-id>"
      )
    _, blocked = tasks.get_task(updated.id)
    _print_single_task(updated, blocked, out)
    return 0

  if len(args) == 1:
    task, blocked = tasks.get_task(subcmd)
    _print_single_task(task, blocked, out)
    return 0

  raise ValueError(f"Unrecognized task arguments: {args}")


def _run_task_mod(args: list[str], tasks: TaskService, out: TextIO) -> int:
  if len(args) < 3:
    raise ValueError("Usage: steer task mod <id> <field> [rm] <value>")
  task_id, field = args[0], args[1].lower()
  rest = args[2:]

  if field == "deets":
    if rest[0] == "rm":
      if len(rest) != 2:
        raise ValueError("Usage: steer task mod <id> deets rm <number>")
      updated = tasks.mod_deets_rm(task_id, int(rest[1]))
    else:
      updated = tasks.mod_deets(task_id, " ".join(rest))
  elif field == "links":
    if rest[0] == "rm":
      if len(rest) != 3:
        raise ValueError(
          "Usage: steer task mod <id> links rm <msg|report|task|gate> <id>"
        )
      updated = tasks.mod_links_rm(task_id, rest[1], rest[2])
    elif len(rest) == 2 and rest[0].lower() in {"msg", "report", "task", "dep", "gate"}:
      updated = tasks.mod_links_add(task_id, rest[1], link_type=rest[0])
    else:
      if len(rest) != 1:
        raise ValueError(
          "Usage: steer task mod <id> links [msg|report|task|gate] <link-id>"
        )
      updated = tasks.mod_links_add(task_id, rest[0])
  elif field == "deps":
    if rest[0] == "rm":
      if len(rest) != 2:
        raise ValueError("Usage: steer task mod <id> deps rm <task-id>")
      updated = tasks.mod_deps_rm(task_id, rest[1])
    else:
      if len(rest) != 1:
        raise ValueError("Usage: steer task mod <id> deps <task-id>")
      updated = tasks.mod_deps_add(task_id, rest[0])
  elif field in {"status", "title", "type", "scope"}:
    updated = tasks.mod_scalar(task_id, field, " ".join(rest))
  else:
    raise ValueError(
      f"Unknown task mod field {field!r}; expected deets, links, deps, status, title, type, or scope"
    )

  _, blocked = tasks.get_task(updated.id)
  _print_single_task(updated, blocked, out)
  return 0


def _run_rename(
  parsed: argparse.Namespace,
  tasks: TaskService,
  reports: ReportService,
  out: TextIO,
) -> int:
  try:
    renamed = tasks.rename_task(parsed.old_id, parsed.new_id)
  except KeyError:
    renamed_report = reports.rename_report(parsed.old_id, parsed.new_id)
    print(f"Renamed report {parsed.old_id} -> {renamed_report.id}", file=out)
    return 0
  print(f"Renamed task {parsed.old_id} -> {renamed.id}", file=out)
  _, blocked = tasks.get_task(renamed.id)
  _print_single_task(renamed, blocked, out)
  return 0


def _run_gh(args: list[str]) -> str:
  result = subprocess.run(
    args,
    check=False,
    capture_output=True,
    text=True,
  )
  if result.returncode != 0:
    detail = (result.stderr or result.stdout or "").strip()
    raise ValueError(f"{' '.join(args)} failed: {detail}")
  return result.stdout


def _run_pr_update(parsed: argparse.Namespace, out: TextIO) -> int:
  body_path = Path(parsed.body_file)
  if not body_path.is_file():
    raise ValueError(f"PR body file does not exist: {body_path}")
  expected_body = body_path.read_text(encoding="utf-8")
  _run_gh(
    [
      "gh",
      "pr",
      "edit",
      str(parsed.number),
      "--title",
      parsed.title,
      "--body-file",
      str(body_path),
    ]
  )
  raw = _run_gh(
    [
      "gh",
      "pr",
      "view",
      str(parsed.number),
      "--json",
      "title,body",
    ]
  )
  current = json.loads(raw)
  if current.get("title") != parsed.title or current.get("body") != expected_body:
    raise ValueError(f"PR #{parsed.number} title/body did not verify after update")
  print(f"Updated PR #{parsed.number}: {parsed.title}", file=out)
  return 0


def _gh_url(args: list[str]) -> tuple[str, str]:
  """Return a log URL and the reason it is missing, when it is."""
  try:
    result = subprocess.run(args, check=False, capture_output=True, text=True)
  except OSError as exc:
    return "", f"gh could not start: {exc}"
  if result.returncode != 0:
    detail = (result.stderr or result.stdout or "").strip().splitlines()
    return "", f"gh exited {result.returncode}: {detail[0] if detail else 'no detail'}"
  url = result.stdout.strip()
  if not url:
    return "", "gh printed an empty URL"
  return url, ""


def _run_job_log(parsed: argparse.Namespace, out: TextIO) -> int:
  """Print one log URL for the agent to fetch, else the log text and the reason."""
  if bool(parsed.job_id) == bool(parsed.run_id):
    raise ValueError("Usage: steer job-log -j <job-id> or -r <run-id>")
  if parsed.run_id:
    url_args = [
      "gh",
      "run",
      "view",
      str(parsed.run_id),
      "--json",
      "url",
      "--jq",
      ".url",
    ]
    log_args = ["gh", "run", "view", str(parsed.run_id), "--log"]
    target = f"run {parsed.run_id}"
  else:
    url_args = [
      "gh",
      "api",
      f"repos/{{owner}}/{{repo}}/actions/jobs/{parsed.job_id}",
      "--jq",
      ".html_url",
    ]
    log_args = ["gh", "run", "view", "--job", str(parsed.job_id), "--log"]
    target = f"job {parsed.job_id}"
  url, reason = _gh_url(url_args)
  if url:
    print(url, file=out)
    return 0
  try:
    log_text = _run_gh(log_args)
  except (ValueError, OSError) as exc:
    print(f"job-log: no URL for {target} ({reason}); log text failed: {exc}", file=out)
    return 1
  print(log_text, end="" if log_text.endswith("\n") else "\n", file=out)
  print(f"job-log: no URL for {target} ({reason})", file=out)
  return 0


def _run_git(args: list[str]) -> str:
  result = subprocess.run(
    args,
    check=False,
    capture_output=True,
    text=True,
  )
  if result.returncode != 0:
    detail = (result.stderr or result.stdout or "").strip()
    raise ValueError(f"{' '.join(args)} failed: {detail}")
  return result.stdout


def _safe_local_name(name: str) -> str:
  cleaned = str(name or "").strip()
  if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", cleaned):
    raise ValueError(f"Invalid name: {name!r}")
  return cleaned


def _call_count(store: SqliteStore) -> int:
  """Read how many shell lines ran since the inbox was last read."""
  raw = store.get_meta(pre_mod.CALL_COUNT_META, "0") or "0"
  try:
    return int(raw)
  except ValueError:
    return 0


def _bump_call_count(store: SqliteStore) -> int:
  """Record one more shell line and return the new count."""
  count = _call_count(store) + 1
  store.set_meta(pre_mod.CALL_COUNT_META, str(count))
  return count


def _reset_call_count(store: SqliteStore) -> None:
  """Restart the countdown after the agent works the inbox."""
  store.set_meta(pre_mod.CALL_COUNT_META, "0")


def _run_pre(
  parsed: argparse.Namespace,
  messages: MessageService,
  store: SqliteStore,
  out: TextIO,
) -> int:
  """Run the pre-command pipeline and return its verdict."""
  pending_ids = messages.pending_ids()
  count = _call_count(store) if pending_ids else 0
  ctx = pre_mod.PreContext(
    line=str(parsed.line or ""),
    command=str(parsed.command_text or ""),
    shell=str(parsed.shell or ""),
    done=tuple(str(parsed.done or "").split()),
    pending_ids=pending_ids,
    call_count=count,
  )
  result = pre_mod.run_pipeline(ctx)
  for message in result.messages:
    print(message, file=out)
  if parsed.shell and set(result.done) - set(ctx.done):
    # The shell evals this line, so a later command in the same shell skips
    # the steps that already ran.
    print(f'_arena_preview_done="{" ".join(result.done)}"', file=out)
  if pending_ids and parsed.shell:
    _bump_call_count(store)
  return result.verdict


def _run_gate(messages: MessageService, parsed: argparse.Namespace, out: TextIO) -> int:
  """Refuse a command while a message or report answer waits for an acknowledgement."""
  waiting = messages.pending_ids()
  if not waiting:
    return 0
  if parsed.push:
    print(
      "PUSH BLOCKED: a note or answer awaits an ack, so nothing left the sandbox.",
      file=out,
    )
  else:
    print("BASH BLOCKED: a note or answer awaits an ack.", file=out)
  print(
    "Read the inbox, then ack every item: `steer read`, then `steer ack <id> <markdown>`.",
    file=out,
  )
  print("Pending: " + ", ".join(waiting), file=out)
  blocker = parsed.line.strip()
  if blocker:
    print(
      f"Blocked by the part `{blocker}`. Run the inbox calls alone, or drop this part.",
      file=out,
    )
  return 1


def _skill_description(skill_md: Path) -> str:
  """Read the frontmatter description without loading the skill body."""
  lines = skill_md.read_text(encoding="utf-8", errors="replace").splitlines()
  if not lines or lines[0].strip() != "---":
    return ""
  for line in lines[1:]:
    if line.strip() == "---":
      break
    if line.startswith("description:"):
      return line.split(":", 1)[1].strip()
  return ""


def _run_skills(out: TextIO) -> int:
  """List repository and installed skills, preferring the installed copy of a name."""
  root = _repo_root()
  found: dict[str, dict[str, str]] = {}
  for source, base in (
    ("repo", root / "skills"),
    ("installed", root / ".agents" / "skills"),
  ):
    if not base.is_dir():
      continue
    for skill_md in sorted(base.glob("*/SKILL.md")):
      name = skill_md.parent.name
      if name in found and source == "repo":
        continue
      found[name] = {
        "name": name,
        "source": source,
        "path": str(skill_md),
        "description": _skill_description(skill_md),
      }
  entries = [found[name] for name in sorted(found)]
  if not entries:
    print("No skills found.", file=out)
    return 0
  for entry in entries:
    print(f"{entry['name']} [{entry['source']}] {entry['path']}", file=out)
    if entry["description"]:
      print(f"  {entry['description']}", file=out)
  return 0


def _repo_root() -> Path:
  top = _run_git(["git", "rev-parse", "--show-toplevel"]).strip()
  return Path(top) if top else Path.cwd()


def _run_worktree(args: list[str], out: TextIO) -> int:
  if not args:
    raise ValueError("Usage: steer worktree <add|list|remove|prune|collect> ...")
  subcmd = args[0]
  if subcmd == "list":
    print(_run_git(["git", "worktree", "list", "--porcelain"]), end="", file=out)
    return 0
  if subcmd == "prune":
    _run_git(["git", "worktree", "prune"])
    print("Pruned worktree records", file=out)
    return 0
  if subcmd == "add":
    add_p = argparse.ArgumentParser(prog="steer worktree add")
    add_p.add_argument("name")
    add_p.add_argument("-b", "--branch", default=None)
    parsed = add_p.parse_args(args[1:])
    name = _safe_local_name(parsed.name)
    target = _repo_root() / ".worktrees" / name
    git_args = ["git", "worktree", "add"]
    if parsed.branch:
      git_args += ["-b", parsed.branch]
    git_args.append(str(target))
    _run_git(git_args)
    print(f"Added worktree {name} at {target}", file=out)
    return 0
  if subcmd == "collect":
    if len(args) != 2:
      raise ValueError("Usage: steer worktree collect <name>")
    name = _safe_local_name(args[1])
    target = _repo_root() / ".worktrees" / name
    if not target.is_dir():
      raise ValueError(f"No worktree at {target}")
    head = _run_git(["git", "-C", str(target), "rev-parse", "HEAD"]).strip()
    base = _run_git(["git", "merge-base", head, "HEAD"]).strip()
    if not base:
      raise ValueError(
        f"No shared base between {name} and HEAD; refuse to guess a diff"
      )
    patch = _run_git(["git", "-C", str(target), "diff", base])
    print(patch, end="", file=out)
    untracked = _run_git(
      ["git", "-C", str(target), "ls-files", "--others", "--exclude-standard"]
    ).strip()
    if untracked:
      print("Untracked files, not in the patch:", file=out)
      print(untracked, file=out)
    return 0
  if subcmd == "remove":
    if len(args) != 2:
      raise ValueError("Usage: steer worktree remove <name>")
    name = _safe_local_name(args[1])
    target = _repo_root() / ".worktrees" / name
    _run_git(["git", "worktree", "remove", str(target)])
    _run_git(["git", "worktree", "prune"])
    print(f"Removed worktree {name}", file=out)
    return 0
  raise ValueError(f"Unknown worktree subcommand: {subcmd!r}")


def _runs_dir(state_dir: Path) -> Path:
  runs = state_dir / "runs"
  runs.mkdir(parents=True, exist_ok=True)
  return runs


def _start_detached_run(
  state_dir: Path,
  name: str,
  command: list[str],
  *,
  after: str | None = None,
  out: TextIO,
) -> int:
  runs = _runs_dir(state_dir).resolve()
  with sqlite3.connect(runs / ".launch.sqlite3") as lock:
    lock.execute("BEGIN IMMEDIATE")
    return _start_locked_run(runs, name, command, after=after, out=out)


def _start_locked_run(
  runs: Path,
  name: str,
  command: list[str],
  *,
  after: str | None,
  out: TextIO,
) -> int:
  record_path = runs / f"{name}.json"
  if record_path.exists():
    previous = json.loads(record_path.read_text(encoding="utf-8"))
    if not Path(previous["exit_path"]).is_file():
      raise ValueError(f"Run {name} is already active")
  dependency = None
  if after:
    dep_record_path = runs / f"{after}.json"
    if not dep_record_path.is_file():
      raise ValueError(f"Unknown dependency: {after}")
    dependency = json.loads(dep_record_path.read_text(encoding="utf-8"))
  run_id = uuid.uuid4().hex
  log_path = runs / f"{name}-{run_id}.log"
  exit_path = runs / f"{name}-{run_id}.exit"
  exit_file = shlex.quote(str(exit_path))
  temp_exit_file = shlex.quote(str(exit_path) + ".tmp")
  write_exit = (
    f'printf "%s\\n" "$status" > {temp_exit_file} && mv {temp_exit_file} {exit_file}'
  )
  script_lines: list[str] = []
  if dependency:
    dep_exit = shlex.quote(dependency["exit_path"])
    script_lines.append(f"while [ ! -f {dep_exit} ]; do sleep 0.2; done")
    script_lines.append(
      f'if [ "$(cat {dep_exit})" != "0" ]; then '
      f'echo "dependency {after} did not pass"; '
      f"status=125; {write_exit}; exit 125; fi"
    )
  script_lines.append(f"( {shlex.join(command)} )")
  script_lines.append(f"status=$?; {write_exit}")
  log_handle = log_path.open("ab")
  try:
    proc = subprocess.Popen(
      ["/bin/sh", "-c", "\n".join(script_lines)],
      stdout=log_handle,
      stderr=subprocess.STDOUT,
      stdin=subprocess.DEVNULL,
      start_new_session=True,
    )
  finally:
    log_handle.close()
  temp_record = runs / f".{name}-{run_id}.json"
  try:
    temp_record.write_text(
      json.dumps(
        {
          "name": name,
          "pid": proc.pid,
          "command": command,
          "after": after,
          "log_path": str(log_path),
          "exit_path": str(exit_path),
        }
      ),
      encoding="utf-8",
    )
    temp_record.replace(record_path)
  except OSError:
    proc.terminate()
    raise
  print(f"Started run {name} (pid {proc.pid})", file=out)
  return 0


def _run_run(
  args: list[str], state_dir: Path, out: TextIO, tasks: TaskService, store: SqliteStore
) -> int:
  if not args:
    raise ValueError("Usage: steer run <start|logs|pr-checks> ...")
  subcmd = args[0]
  if subcmd == "start":
    raw_args = args[1:]
    if "--" in raw_args:
      split_at = raw_args.index("--")
      option_args = raw_args[:split_at]
      command = raw_args[split_at + 1 :]
    else:
      option_args = raw_args
      command = []
    start_p = argparse.ArgumentParser(prog="steer run start")
    start_p.add_argument("name")
    start_p.add_argument("-a", "--after", default=None)
    start_p.add_argument("-t", "--task", default=None)
    parsed = start_p.parse_args(option_args)
    if not command:
      raise ValueError("Usage: steer run start <name> [--after <run>] -- <command...>")
    name = _safe_local_name(parsed.name)
    after = _safe_local_name(parsed.after) if parsed.after else None
    if parsed.task:
      with store.transaction():
        tasks.get_task(parsed.task)
        tasks.mod_links_add(parsed.task, name, link_type="gate")
        return _start_detached_run(state_dir, name, command, after=after, out=out)
    return _start_detached_run(state_dir, name, command, after=after, out=out)

  if subcmd == "logs":
    logs_p = argparse.ArgumentParser(prog="steer run logs")
    logs_p.add_argument("name")
    logs_p.add_argument("-n", "--lines", type=int, default=50)
    parsed = logs_p.parse_args(args[1:])
    name = _safe_local_name(parsed.name)
    runs = _runs_dir(state_dir)
    if not (runs / f"{name}.json").is_file():
      raise KeyError(f"Unknown run: {name}")
    record = json.loads((runs / f"{name}.json").read_text(encoding="utf-8"))
    exit_path = Path(record["exit_path"])
    if exit_path.is_file():
      status = f"exit {exit_path.read_text(encoding='utf-8').strip()}"
    else:
      status = "running"
    print(f"run {name} {status}", file=out)
    log_path = Path(record["log_path"])
    if log_path.is_file():
      lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
      for line in lines[-parsed.lines :]:
        print(line, file=out)
    return 0
  if subcmd == "pr-checks":
    checks_p = argparse.ArgumentParser(prog="steer run pr-checks")
    checks_p.add_argument("-n", "--number", type=int, default=None)
    parsed = checks_p.parse_args(args[1:])
    command = ["gh", "pr", "checks"]
    if parsed.number is not None:
      command.append(str(parsed.number))
    command.append("--watch")
    return _start_detached_run(state_dir, "pr-checks", command, out=out)
  raise ValueError(f"Unknown run subcommand: {subcmd!r}")


def _run_report(
  args: list[str], reports: ReportService, store: SqliteStore, out: TextIO
) -> int:
  if not args:
    raise ValueError("Usage: steer report <id|pub|pin|unpin|rm> ...")
  subcmd = args[0]
  if subcmd == "pub":
    pub_p = argparse.ArgumentParser(prog="steer report pub")
    pub_p.add_argument("source")
    pub_p.add_argument("-i", "--id", required=True)
    pub_p.add_argument("-t", "--title", required=True)
    pub_p.add_argument("-u", "--allow-unparsed-markers", action="store_true")
    parsed = pub_p.parse_args(args[1:])
    source_path = Path(parsed.source)
    if not source_path.is_file():
      raise ValueError(f"Report source file does not exist: {source_path}")
    body = source_path.read_text(encoding="utf-8")
    report = reports.publish_report(
      parsed.id,
      parsed.title,
      body,
      allow_unparsed_markers=parsed.allow_unparsed_markers,
    )
    SteeringApp(store).verify_published_report(report)
    print(
      f"Published {report.id}, {len(report.fields)} fields. Verified.",
      file=out,
    )
    return 0

  if subcmd in {"pin", "unpin"}:
    if len(args) != 2:
      raise ValueError(f"Usage: steer report {subcmd} <id>")
    reports.pin_report(args[1], subcmd == "pin")
    print(f"{'Pinned' if subcmd == 'pin' else 'Unpinned'} {args[1]}.", file=out)
    return 0

  if subcmd == "rm":
    targets = args[1:]
    if not targets or ("--stale" in targets and len(targets) != 1):
      raise ValueError("Usage: steer report rm <id> [<id> ...] | --stale")
    removed: list[str] = []
    with store.transaction():
      for target in dict.fromkeys(targets):
        removed.extend(reports.remove_report(target))
    print(
      f"Dismissed reports: {', '.join(removed) if removed else 'none'}",
      file=out,
    )
    return 0

  if len(args) == 1:
    report = reports.get_report(subcmd)
    _print_single_report(report, out)
    return 0

  raise ValueError(f"Unrecognized report arguments: {args}")


def _print_restore_notice(store: SqliteStore, out: TextIO) -> None:
  """Print and clear the one-line notice left by a state merge."""
  raw = store.get_meta("state_restore_notice", "")
  if not raw:
    return
  store.set_meta("state_restore_notice", "")
  try:
    notice = json.loads(raw)
  except json.JSONDecodeError:
    return
  source = str(notice.get("source") or "a container")
  added = int(notice.get("added") or 0)
  updated = int(notice.get("updated") or 0)
  print(f"State restored from {source}: {added} added, {updated} updated.", file=out)


def _print_delivered(delivered: dict[str, list], out: TextIO) -> None:
  msgs: list[Message] = delivered["messages"]
  ans_pairs: list[tuple[Report, ReportAnswer]] = delivered["report_answers"]
  total = len(msgs) + len(ans_pairs)
  stamp = datetime.now(UTC).strftime("%H:%M:%S")
  if total == 0:
    print(f"Inbox {stamp}: 0 pending", file=out)
    return
  print(f"Inbox {stamp}: {total} pending", file=out)
  for msg in msgs:
    _print_message(msg, out)
  for report, ans in ans_pairs:
    print(f"`{ans.id}` answer report {report.id} ({report.title})", file=out)
    for key, val in ans.values.items():
      label = ans.field_labels.get(key, key)
      formatted = (
        ", ".join(str(item) for item in val) if isinstance(val, list) else str(val)
      )
      print(f"  {label}: {formatted}", file=out)


def _print_message(msg: Message, out: TextIO) -> None:
  flags: list[str] = [msg.status]
  if msg.hidden:
    flags.append("hidden")
  if not msg.blocking:
    flags.append("non-blocking")
  print(f"`{msg.id}` ({', '.join(flags)}) [{msg.modified_at}]", file=out)
  if msg.body:
    print(msg.body, file=out)
  for att in msg.attachments:
    print(f"attachment: {att.name} -> {att.path} ({att.size_bytes} B)", file=out)
  for ack_text in msg.acks:
    print(f"ack: {ack_text}", file=out)


def _print_task_list(items: list[tuple[Task, bool]], out: TextIO) -> None:
  if not items:
    print("Tasks: 0", file=out)
    return
  print(f"Tasks: {len(items)}", file=out)
  for idx, (task, blocked) in enumerate(items, 1):
    state_str = f"{task.status}, blocked" if blocked else task.status
    print(f"{idx}  {task.id} [{state_str}] ({task.type}) - {task.title}", file=out)
    if task.scope:
      print(f"   Scope: {task.scope}", file=out)
    if task.deps:
      print(f"   Deps: {', '.join(task.deps)}", file=out)
    if task.report_ids:
      print(f"   Reports: {', '.join(task.report_ids)}", file=out)
    if task.gate_names:
      print(f"   Gates: {', '.join(task.gate_names)}", file=out)
    for detail_idx, line in enumerate(task.details, 1):
      print(f"   {detail_idx}. {line}", file=out)


def _print_single_task(task: Task, blocked: bool, out: TextIO) -> None:
  state_str = f"{task.status}, blocked" if blocked else task.status
  print(f"task {task.id}, status {state_str}, type {task.type}", file=out)
  print(task.title, file=out)
  if task.scope:
    print(f"- Scope: {task.scope}", file=out)
  if task.deps:
    print(f"- Deps: {', '.join(task.deps)}", file=out)
  if task.report_ids:
    print(f"- Reports: {', '.join(task.report_ids)}", file=out)
  if task.msg_ids:
    print(f"- Messages: {', '.join(task.msg_ids)}", file=out)
  if task.gate_names:
    print(f"- Gates: {', '.join(task.gate_names)}", file=out)
  for idx, line in enumerate(task.details, 1):
    print(f"- [{idx}] {line}", file=out)


def _print_reports_list(items: list[Report], out: TextIO) -> None:
  if not items:
    print("Reports: 0", file=out)
    return
  print(f"Reports: {len(items)}", file=out)
  for rep in items:
    print(
      f"- {rep.id} [{rep.status}] ({len(rep.fields)} fields, {len(rep.answers)} answers): {rep.title}",
      file=out,
    )


def _print_single_report(rep: Report, out: TextIO) -> None:
  print(
    f"report {rep.id} [{rep.status}] - {rep.title} (modified {rep.modified_at})",
    file=out,
  )
  for field in rep.fields:
    print(f"  field {field.id} ({field.type}): {field.label}", file=out)
  for ans in rep.answers:
    print(f"  answer {ans.id} [{ans.status}]: {ans.values}", file=out)


def _survey_server_url(state_dir: Path) -> str | None:
  """Return the running server base URL recorded in the state directory."""
  server_file = state_dir / "server.json"
  if not server_file.is_file():
    return None
  try:
    data = json.loads(server_file.read_text(encoding="utf-8"))
    host = str(data.get("host") or "127.0.0.1")
    port = int(data.get("port") or 0)
  except (OSError, ValueError, TypeError):
    return None
  if not port:
    return None
  return f"http://{'127.0.0.1' if host in ('0.0.0.0', '::') else host}:{port}"


def _post_survey(url: str, payload: str) -> dict | None:
  """Submit survey answers to the running server so its memory holds them."""
  # The HTTP layer takes objects only, so array submissions travel under "answers".
  try:
    decoded = json.loads(payload)
  except json.JSONDecodeError:
    decoded = payload
  body = json.dumps({"answers": decoded}).encode("utf-8")
  request = urllib.request.Request(
    f"{url}/survey",
    data=body,
    headers={"Content-Type": "application/json"},
    method="POST",
  )
  opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
  try:
    with opener.open(request, timeout=5) as response:
      body = json.loads(response.read().decode("utf-8"))
  except (urllib.error.URLError, OSError, ValueError):
    return None
  survey = body.get("survey") if isinstance(body, dict) else None
  return survey if isinstance(survey, dict) else None


def _submit_survey(
  payload: str,
  messages: MessageService,
  state_dir: Path,
  out: TextIO,
) -> dict:
  """Send answers to the live server, or grade them locally when none runs."""
  url = _survey_server_url(state_dir)
  survey = _post_survey(url, payload) if url else None
  if survey is not None:
    print("survey-source=server", file=out)
    return survey
  if url:
    print("survey-source=local", file=out)
  return messages.submit_survey(payload)


def _run_survey(
  parsed: argparse.Namespace,
  messages: MessageService,
  out: TextIO,
  state_dir: Path | None = None,
) -> int:
  import json

  from . import survey as survey_mod

  if getattr(parsed, "smallest_image", False):
    print(survey_mod.smallest_image(), file=out)
    return 0
  if getattr(parsed, "template", False):
    print(json.dumps(survey_mod.template(), indent=2), file=out)
    return 0
  state_dir = state_dir or resolve_state_dir()
  if getattr(parsed, "file", None):
    payload = Path(parsed.file).read_text(encoding="utf-8")
    survey = _submit_survey(payload, messages, state_dir, out)
    print(
      f"Submitted {len(survey['results'])} survey answer(s) at {survey['checked_at']}",
      file=out,
    )
    return 0
  entries: list[str] = list(parsed.entries or [])
  if entries:
    if len(entries) == 1 and entries[0].lstrip().startswith("["):
      survey = _submit_survey(entries[0], messages, state_dir, out)
      print(
        f"Submitted {len(survey['results'])} survey answer(s) at {survey['checked_at']}",
        file=out,
      )
      return 0
    values: dict[str, str] = {}
    for entry in entries:
      if "=" not in entry:
        raise ValueError(
          f"Expected JSON array or <key=value> survey entry, got {entry!r}"
        )
      key, _, val = entry.partition("=")
      values[key.strip()] = val.strip()
    survey = _submit_survey(json.dumps(values), messages, state_dir, out)
    print(
      f"Submitted {len(values)} survey answer(s) at {survey['checked_at']}",
      file=out,
    )
    return 0
  survey = messages.get_survey()
  print(
    f"Survey: pending={survey['pending']} checked_at={survey['checked_at'] or 'never'}",
    file=out,
  )
  for q in survey["questions"]:
    qid = q["id"]
    ans = survey["answers"].get(qid, "(unanswered)")
    print(f"- {qid}: {q['prompt']} -> {ans}", file=out)
  print("\nSubmission template:", file=out)
  print(json.dumps(survey_mod.template(), indent=2), file=out)
  return 0
