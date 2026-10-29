"""Command-line interface (`steer`) for Arena Steering."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import TextIO

from . import __version__
from .models import MESSAGE_ID_RE, Message, Report, ReportAnswer, Task
from .server import SteeringApp, create_http_server
from .services import MessageService, ReportService, TaskService
from .store import SqliteStore


def resolve_state_dir(explicit: str | None = None) -> Path:
  """Return the configured state directory path."""
  raw = explicit or os.environ.get("ARENA_STATE_DIR") or "arena-state"
  path = Path(raw)
  path.mkdir(parents=True, exist_ok=True)
  return path


def open_services(
  state_dir: Path,
) -> tuple[SqliteStore, MessageService, TaskService, ReportService]:
  """Open SqliteStore and domain services for a state directory."""
  store = SqliteStore(state_dir / "state.sqlite3")
  messages = MessageService(store, store, store)
  tasks = TaskService(store, store)
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
  parser.add_argument(
    "--state-dir",
    default=None,
    help="State directory holding state.sqlite3 (default: arena-state).",
  )
  sub = parser.add_subparsers(dest="command")

  default_port = int(os.environ.get("STEER_PORT", "8100"))
  serve_p = sub.add_parser("serve", help="Start the local steering HTTP server.")
  serve_p.add_argument("--host", default="0.0.0.0")
  serve_p.add_argument("--port", type=int, default=default_port)

  sub.add_parser("read", help="Read pending messages and report answers.")

  poll_p = sub.add_parser("poll", help="Wait for pending messages or skip_poll.")
  poll_p.add_argument("-t", "--timeout", type=float, default=1799.0)

  ack_p = sub.add_parser("ack", help="Acknowledge a message or report answer.")
  ack_p.add_argument("parts", nargs="+", help="[<id>] <markdown>")
  ack_p.add_argument("-i", "--id", dest="task_id", default=None)
  ack_p.add_argument("-t", "--title", dest="task_title", default=None)
  ack_p.add_argument("-T", "--type", dest="task_type", default="code")
  ack_p.add_argument("-S", "--scope", dest="task_scope", default="")
  ack_p.add_argument("-d", "--detail", dest="task_details", action="append", default=[])

  msg_p = sub.add_parser("msg", help="List or inspect stored messages.")
  msg_sub = msg_p.add_subparsers(dest="msg_cmd")
  msg_list_p = msg_sub.add_parser("list", help="List messages newest-first.")
  msg_list_p.add_argument("-p", "--page", type=int, default=1)
  msg_list_p.add_argument("-s", "--size", type=int, default=20)
  msg_show_p = msg_sub.add_parser("show", help="Show one message by ID.")
  msg_show_p.add_argument("id")

  tasks_p = sub.add_parser("tasks", help="List tasks in queue order.")
  tasks_p.add_argument("-f", "--full", action="store_true")

  sub.add_parser("task", help="Show, create, remove, or modify a task.")

  reports_p = sub.add_parser("reports", help="List active or stale reports.")
  reports_p.add_argument("-s", "--stale", action="store_true")

  sub.add_parser("report", help="Show, publish, or remove a report.")

  survey_p = sub.add_parser("survey", help="Inspect or submit bible survey answers.")
  survey_p.add_argument("entries", nargs="*", help="[<key=value> ...]")
  survey_p.add_argument("--interrupt", action="store_true", help="Trigger bible check.")

  state_dir, remaining = _extract_global_state_dir(args_list)
  if not remaining:
    parser.print_help(file=stdout)
    return 0

  cmd = remaining[0]
  cmd_args = remaining[1:]

  store, messages, tasks, reports = open_services(resolve_state_dir(state_dir))
  try:
    if cmd == "serve":
      parsed = serve_p.parse_args(cmd_args)
      app = SteeringApp(store)
      httpd = create_http_server(app, host=parsed.host, port=parsed.port)
      print(
        f"Steering server listening on http://{parsed.host}:{parsed.port}",
        file=stdout,
      )
      httpd.serve_forever()
      return 0
    if cmd == "read":
      delivered = messages.read_pending(mark_seen=True)
      _print_delivered(delivered, stdout)
      return 0
    if cmd == "poll":
      parsed = poll_p.parse_args(cmd_args)
      delivered = messages.poll(timeout_seconds=parsed.timeout)
      _print_delivered(delivered, stdout)
      return 0
    if cmd == "ack":
      parsed = ack_p.parse_args(cmd_args)
      return _run_ack(parsed, messages, tasks, stdout)
    if cmd == "msg":
      return _run_msg(cmd_args, msg_list_p, msg_show_p, messages, stdout)
    if cmd == "tasks":
      parsed = tasks_p.parse_args(cmd_args)
      _print_task_list(tasks.list_tasks(include_finished=parsed.full), stdout)
      return 0
    if cmd == "task":
      return _run_task(cmd_args, tasks, stdout)
    if cmd == "reports":
      parsed = reports_p.parse_args(cmd_args)
      _print_reports_list(reports.list_reports(stale_only=parsed.stale), stdout)
      return 0
    if cmd == "report":
      return _run_report(cmd_args, reports, stdout)
    if cmd == "survey":
      parsed = survey_p.parse_args(cmd_args)
      return _run_survey(parsed, messages, stdout)

    parsed_root = parser.parse_args(remaining)
    if not parsed_root.command:
      parser.print_help(file=stdout)
    return 0
  except (KeyError, ValueError, IndexError, OSError) as exc:
    msg = exc.args[0] if isinstance(exc, KeyError) and exc.args else str(exc)
    print(f"Steer error: {msg}", file=stderr)
    return 1
  finally:
    store.close()


def _extract_global_state_dir(argv: list[str]) -> tuple[str | None, list[str]]:
  state_dir: str | None = None
  remaining: list[str] = []
  idx = 0
  while idx < len(argv):
    token = argv[idx]
    if token == "--state-dir" and idx + 1 < len(argv):
      state_dir = argv[idx + 1]
      idx += 2
      continue
    if token.startswith("--state-dir="):
      state_dir = token.split("=", 1)[1]
      idx += 1
      continue
    remaining.append(token)
    idx += 1
  return state_dir, remaining


def _run_ack(
  parsed: argparse.Namespace,
  messages: MessageService,
  tasks: TaskService,
  out: TextIO,
) -> int:
  parts: list[str] = parsed.parts
  if len(parts) == 1:
    target_id = None
    markdown = parts[0]
  elif len(parts) == 2 and MESSAGE_ID_RE.fullmatch(parts[0]):
    target_id = parts[0]
    markdown = parts[1]
  else:
    raise ValueError("Usage: steer ack [<6-char-hex-id>] '<markdown>'")

  _, acked = messages.ack(target_id, markdown)
  print(f"ok {acked.id}", file=out)
  if parsed.task_id:
    if not parsed.task_title:
      raise ValueError("Task creation on ack requires -t/--title")
    created = tasks.create_task(
      parsed.task_id,
      parsed.task_title,
      type=parsed.task_type,
      scope=parsed.task_scope,
      details=parsed.task_details,
      msg_ids=[acked.id],
    )
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
    items = messages.list_messages(
      unread_only=False,
      include_hidden=True,
      newest_first=True,
      page=parsed.page,
      page_size=parsed.size,
    )
    if not items:
      print("No messages.", file=out)
      return 0
    for item in items:
      _print_message(item, out)
    return 0
  if args[0] == "show":
    parsed = show_parser.parse_args(args[1:])
    item = messages.get_message(parsed.id)
    _print_message(item, out)
    return 0
  raise ValueError(f"Unknown msg subcommand: {args[0]!r}")


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
        raise ValueError("Usage: steer task mod <id> links rm <msg|report|task> <id>")
      updated = tasks.mod_links_rm(task_id, rest[1], rest[2])
    elif len(rest) == 2 and rest[0].lower() in {"msg", "report", "task", "dep"}:
      updated = tasks.mod_links_add(task_id, rest[1], link_type=rest[0])
    else:
      if len(rest) != 1:
        raise ValueError("Usage: steer task mod <id> links [msg|report|task] <link-id>")
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


def _run_report(args: list[str], reports: ReportService, out: TextIO) -> int:
  if not args:
    raise ValueError("Usage: steer report <id|pub|rm> ...")
  subcmd = args[0]
  if subcmd == "pub":
    pub_p = argparse.ArgumentParser(prog="steer report pub")
    pub_p.add_argument("source")
    pub_p.add_argument("-i", "--id", required=True)
    pub_p.add_argument("-t", "--title", required=True)
    parsed = pub_p.parse_args(args[1:])
    source_path = Path(parsed.source)
    if not source_path.is_file():
      raise ValueError(f"Report source file does not exist: {source_path}")
    body = source_path.read_text(encoding="utf-8")
    report = reports.publish_report(parsed.id, parsed.title, body)
    print(
      f"Published {report.id}, {len(report.fields)} fields.",
      file=out,
    )
    return 0

  if subcmd == "rm":
    if len(args) != 2:
      raise ValueError("Usage: steer report rm <id|--stale>")
    removed = reports.remove_report(args[1])
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


def _print_delivered(delivered: dict[str, list], out: TextIO) -> None:
  msgs: list[Message] = delivered["messages"]
  ans_pairs: list[tuple[Report, ReportAnswer]] = delivered["report_answers"]
  total = len(msgs) + len(ans_pairs)
  if total == 0:
    print("Inbox: 0 pending", file=out)
    return
  print(f"Inbox: {total} pending", file=out)
  for msg in msgs:
    _print_message(msg, out)
  for report, ans in ans_pairs:
    print(f"`{ans.id}` answer report {report.id} ({report.title})", file=out)
    for key, val in ans.values.items():
      print(f"  {key}: {val}", file=out)


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


def _run_survey(
  parsed: argparse.Namespace, messages: MessageService, out: TextIO
) -> int:
  if parsed.interrupt:
    survey = messages.trigger_bible_check(active=True)
    print(f"Survey bible check pending={survey['pending']}", file=out)
    return 0
  entries: list[str] = list(parsed.entries or [])
  if entries:
    values: dict[str, str] = {}
    for entry in entries:
      if "=" not in entry:
        raise ValueError(f"Expected <key=value> survey entry, got {entry!r}")
      key, _, val = entry.partition("=")
      values[key.strip()] = val.strip()
    survey = messages.submit_survey(values)
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
  return 0
