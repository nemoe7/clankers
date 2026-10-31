"""Pre-command pipeline for the shell hook.

Each check is one small class with `applies` and `run`. A step returns `None` to
continue, a message to warn, or a verdict to stop the line. `PIPELINE` is the
registry, so adding, dropping, or reordering a check is one line here.
"""

from __future__ import annotations

import json
import re
import shlex
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol
from urllib.parse import parse_qs, urlsplit

from . import git_safety

CONTINUE = 0
END_CALL = 2
BLOCK = 130

GATE_THRESHOLD = 6
CALL_COUNT_META = "pre_call_count"
WIREFRAME_SUFFIX = "-wireframe.png"
NETWORK_WORDS = ("curl", "wget", "git clone", "git fetch", "git ls-remote")
SHELL_NAMES = {"bash", "sh", "dash", "zsh", "ksh"}
COMMAND_WRAPPERS = {"env", "command", "nice", "nohup", "stdbuf", "sudo", "time"}
ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z_0-9]*=")
SHELL_WRAPPER = re.compile(
  r"^(?:\S*/)?(?:bash|sh|dash|zsh|ksh)\s+(?:-[\w-]+\s+)*-[\w]*c\s+"
)


def command_words(words: list[str]) -> list[str]:
  """Skip assignments and ordinary shell wrappers before naming the command."""
  index = 0
  while index < len(words):
    head = Path(words[index]).name
    if ASSIGNMENT.match(words[index]):
      index += 1
    elif head in COMMAND_WRAPPERS:
      index += 1
      while index < len(words) and (
        words[index].startswith("-")
        or ASSIGNMENT.match(words[index])
        or re.fullmatch(r"\d+(?:\.\d+)?", words[index])
      ):
        index += 1
    else:
      break
  return words[index:]


def shell_line(text: str) -> str:
  """Drop the Bash launcher without losing the command it runs."""
  text = SHELL_WRAPPER.sub("", text.strip(), count=1)
  if len(text) >= 2 and text[0] == text[-1] and text[0] in ("'", '"'):
    return text[1:-1]
  return text


@dataclass
class PreContext:
  """Everything a step may read for one shell line."""

  line: str = ""
  command: str = ""
  shell: str = ""
  done: tuple[str, ...] = ()
  pending_ids: list[str] = field(default_factory=list)
  call_count: int = 0
  active_runs: tuple[str, ...] = ()
  routed: bool = False
  cwd: Path | None = None
  checkout_root: Path | None = None
  session_ids: tuple[str, ...] = ()

  def pieces(self) -> list[tuple[list[str], str]]:
    """Name simple commands and the separators that follow them."""
    lexer = shlex.shlex(
      shell_line(self.line or self.command),
      posix=True,
      punctuation_chars="|;&()\n",
    )
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    lexer.commenters = ""
    try:
      tokens = list(lexer)
    except ValueError:
      return []
    result: list[tuple[list[str], str]] = []
    current: list[str] = []
    for token in [*tokens, ";"]:
      if token in {"|", "|&", ";", "&&", "||", "&", "(", ")", "\n"}:
        if current:
          result.append((current, token))
        current = []
      else:
        current.append(token)
    return result

  def touches(self, *words: str) -> bool:
    """Report whether the command contains any of these substrings."""
    text = f"{self.command} {self.line}"
    return any(word in text for word in words)

  def is_push(self) -> bool:
    return "git push" in self.command or "git push" in self.line

  def is_inbox_recovery(self) -> bool:
    """Allow an inbox-only line to clear the gate, including a piped ACK."""
    text = shell_line(self.line or self.command)
    if "\n" in text:
      return False
    lexer = shlex.shlex(text, posix=True, punctuation_chars="|;&<>()")
    lexer.whitespace_split = True
    lexer.commenters = ""
    try:
      words = list(lexer)
    except ValueError:
      return False
    if len(words) < 2 or Path(words[0]).name != "steer":
      return False
    if words[1] not in {"read", "poll", "ack"}:
      return False
    punctuation = [
      word for word in words[2:] if word and all(c in "|;&<>()" for c in word)
    ]
    if not punctuation:
      return True
    if words[1] != "ack" or punctuation != ["|"]:
      return False
    pipe = words.index("|")
    return "git push" not in " ".join(
      words[pipe + 1 :]
    ) and not self.command.startswith("git push")

  def blocked_part(self) -> str:
    """Name the last simple command of a chained line."""
    text = self.line or self.command
    parts = [part.strip() for part in re.split(r"&&|\|\||;|\n", text)]
    parts = [part for part in parts if part]
    return parts[-1] if parts else text.strip()


def embedded_pieces(words: list[str]) -> list[tuple[list[str], str]]:
  """Read the command string passed to a shell's -c option, if present."""
  if not words or Path(words[0]).name not in SHELL_NAMES:
    return []
  for index in range(1, len(words) - 1):
    if words[index].startswith("-") and "c" in words[index][1:]:
      return PreContext(line=words[index + 1]).pieces()
  return []


@dataclass
class PreResult:
  """One step outcome: the text to print and the verdict to return."""

  messages: list[str] = field(default_factory=list)
  verdict: int = CONTINUE
  done: tuple[str, ...] = ()


class PreStep(Protocol):
  """A single pre-command check."""

  name: str

  def applies(self, ctx: PreContext) -> bool:
    """Report whether this step runs for the line."""

  def run(self, ctx: PreContext) -> PreResult:
    """Return the messages and verdict for the line."""


class InboxPipeGuard:
  """Keep inbox reads and polls from losing their output to a pipe."""

  name = "inbox-pipe"

  def applies(self, ctx: PreContext) -> bool:
    def inbox_read(words: list[str]) -> bool:
      words = command_words(words)
      return (
        len(words) >= 2
        and Path(words[0]).name in {"steer", "arena-preview"}
        and words[1] in {"read", "poll"}
      )

    for words, separator in ctx.pieces():
      words = command_words(words)
      if separator in {"|", "|&"} and inbox_read(words):
        return True
      if any(
        inbox_read(inner) and (separator in {"|", "|&"} or following in {"|", "|&"})
        for inner, following in embedded_pieces(words)
      ):
        return True
    return False

  def run(self, ctx: PreContext) -> PreResult:
    return PreResult(
      ["INBOX BLOCKED: read and poll need full output. Run without a pipe."],
      BLOCK,
    )


class PollTimeoutGuard:
  """Keep a shell timeout from cutting off a poll's own wait."""

  name = "poll-timeout"

  def applies(self, ctx: PreContext) -> bool:
    def poll(words: list[str]) -> bool:
      words = command_words(words)
      return (
        len(words) >= 2
        and Path(words[0]).name in {"steer", "arena-preview"}
        and words[1] == "poll"
      )

    for words, _ in ctx.pieces():
      words = command_words(words)
      if not words or Path(words[0]).name != "timeout":
        continue
      args = words[1:]
      while args and args[0].startswith("-"):
        option, *args = args
        if option in {"-s", "--signal", "-k", "--kill-after"} and args:
          args = args[1:]
      target = command_words(args[1:]) if args else []  # Skip the duration.
      if poll(target) or any(poll(inner) for inner, _ in embedded_pieces(target)):
        return True
    return False

  def run(self, ctx: PreContext) -> PreResult:
    return PreResult(
      [
        "TIMEOUT BANNED: do not wrap `steer poll` in shell `timeout`.",
        "Set the Bash tool timeout to 1800 seconds. Poll returns within 1799 seconds.",
      ],
      BLOCK,
    )


def _line_commands(ctx: PreContext) -> list[list[str]]:
  """Include direct commands and shell -c scripts without matching quoted prose."""
  pieces = [command_words(words) for words, _ in ctx.pieces()]
  return [
    *pieces,
    *(command_words(inner) for words in pieces for inner, _ in embedded_pieces(words)),
  ]


def _api_pr_change(args: list[str], client: str) -> bool:
  """Recognize GitHub PR-state writes, not title and body updates."""
  method, endpoint = "", ""
  fields: dict[str, object] = {}
  body = False
  value_flags = {
    "-X",
    "--method",
    "--request",
    "-d",
    "--data",
    "--data-raw",
    "--json",
    "--input",
    "--body-data",
    "--post-data",
    "-f",
    "-F",
    "--field",
    "--raw-field",
  }
  index = 0
  while index < len(args):
    word = args[index]
    option, equal, value = word.partition("=")
    if not equal and len(word) > 2 and word[:2] in {"-X", "-d", "-f", "-F"}:
      option, value, equal = word[:2], word[2:], "="
    if option in value_flags:
      if not equal:
        index += 1
        value = args[index] if index < len(args) else ""
      if option in {"-X", "--method", "--request"}:
        method = value.upper()
      else:
        body = True
        if option in {"-f", "-F", "--field", "--raw-field"}:
          key, _, field = value.partition("=")
          if option in {"-F", "--field"} and field.startswith("@") and field != "@-":
            try:
              field = Path(field[1:]).read_text(encoding="utf-8").strip()
            except (OSError, UnicodeError):
              field = ""
          fields[key] = field
        else:
          if option == "--input" and value != "-":
            try:
              value = Path(value).read_text(encoding="utf-8")
            except (OSError, UnicodeError):
              value = ""
          try:
            data = json.loads(value)
          except (ValueError, TypeError):
            data = {}
          if isinstance(data, dict):
            fields.update(data)
    elif client == "gh" and (
      word == "graphql" or word.lstrip("/").startswith("repos/")
    ):
      endpoint = word.lstrip("/").split("?", 1)[0]
    elif word.startswith(("https://", "http://")):
      url = urlsplit(word)
      if client == "gh" or url.hostname == "api.github.com":
        endpoint = url.path.lstrip("/")
        fields.update({key: values[-1] for key, values in parse_qs(url.query).items()})
    index += 1
  if endpoint == "graphql":
    query = fields.get("query", "")
    if not isinstance(query, str) or not re.search(r"\bmutation\b", query):
      return False
    if re.search(
      r"\b(?:mergePullRequest|closePullRequest|reopenPullRequest|enablePullRequestAutoMerge|"
      r"enqueuePullRequest|deleteRef|updateRef|mergeBranch)\s*\(",
      query,
    ):
      return True
    if not re.search(r"\bupdatePullRequest\s*\(", query):
      return False
    if re.search(r"\bstate\s*:\s*(?:CLOSED|OPEN)\b", query):
      return True
    variables = fields.get("variables", {})
    if isinstance(variables, str):
      try:
        variables = json.loads(variables)
      except ValueError:
        variables = {}

    def state_change(value: object) -> bool:
      return isinstance(value, dict) and any(
        (key == "state" and item in ("CLOSED", "OPEN")) or state_change(item)
        for key, item in value.items()
      )

    return bool(re.search(r"\binput\s*:\s*\$\w+", query)) and state_change(variables)
  if (method or ("POST" if body else "GET")) in {"GET", "HEAD"}:
    return False
  if re.fullmatch(r"repos/[^/]+/[^/]+/(?:pulls/\d+/merge(?:-async)?|merges)", endpoint):
    return True
  if re.fullmatch(r"repos/[^/]+/[^/]+/git/refs/heads/.+", endpoint):
    return method in {"DELETE", "PATCH"}
  return bool(
    method == "PATCH"
    and re.fullmatch(r"repos/[^/]+/[^/]+/(?:pulls|issues)/\d+", endpoint)
    and fields.get("state") in ("closed", "open")
  )


def _gh_help(args: list[str]) -> bool:
  """A help option used as comment text does not make a PR write read-only."""
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
  return any(
    word in {"--help", "-h"} and (index == 0 or args[index - 1] not in value_flags)
    for index, word in enumerate(args)
  )


class PrStateGuard:
  """Stop visible PR merges, closures, reopens, and equivalent API writes."""

  name = "pr-state"

  def applies(self, ctx: PreContext) -> bool:
    for words in _line_commands(ctx):
      if not words:
        continue
      head, args = Path(words[0]).name, words[1:]
      if (
        head == "gh"
        and args[:1] == ["pr"]
        and len(args) >= 2
        and args[1] in {"merge", "close", "reopen"}
        and not _gh_help(args[2:])
      ):
        return True
      if head == "gh" and args[:1] == ["api"] and _api_pr_change(args[1:], head):
        return True
      if head in {"curl", "wget"} and _api_pr_change(args, head):
        return True
    return False

  def run(self, ctx: PreContext) -> PreResult:
    return PreResult(
      ["PR STATE BLOCKED: visible PR-state write; use reads or metadata edits."],
      BLOCK,
    )


class DestructivePushGuard:
  """Block deletes and wholesale ref rewrites before any push executes."""

  name = "push-refs"

  def applies(self, ctx: PreContext) -> bool:
    for words in _line_commands(ctx):
      if not words or Path(words[0]).name != "git" or "push" not in words[1:]:
        continue
      args = words[words.index("push") + 1 :]
      if any(arg in {"--help", "-h", "--dry-run", "-n"} for arg in args):
        continue
      if any(arg in {"--delete", "-d", "--mirror", "--all", "--prune"} for arg in args):
        return True
      if any(arg.lstrip("+").startswith(":") for arg in args):
        return True
    return False

  def run(self, ctx: PreContext) -> PreResult:
    return PreResult(["PUSH BLOCKED: destructive ref change is not permitted."], BLOCK)


class GitSafetyGuard:
  """Inspect staged commits, managed worktrees, and fresh remote push ancestry."""

  name = "git-safe"

  def applies(self, ctx: PreContext) -> bool:
    return any(self.action(words) for words in _line_commands(ctx))

  def action(self, words: list[str]) -> str:
    if not words:
      return ""
    head, args = Path(words[0]).name, words[1:]
    if head == "git" and "commit" in args:
      return "commit"
    if head == "git" and "push" in args:
      return "push"
    if head in {"steer", "arena-preview"} and args[:2] == ["run", "start"]:
      return "gate"
    return ""

  def run(self, ctx: PreContext) -> PreResult:
    current_commands = _line_commands(PreContext(line=ctx.command or ctx.line))
    if ctx.cwd is None:
      if any(
        self.action(words) == "push"
        and not any(arg in {"--dry-run", "-n", "--help", "-h"} for arg in words)
        for words in current_commands
      ):
        return PreResult(
          ["PUSH BLOCKED: remote default comparison unavailable."], BLOCK
        )
      return PreResult()
    for words in _line_commands(ctx):
      action = self.action(words)
      if action and ctx.checkout_root is not None:
        target = (
          git_safety.target_cwd(ctx.cwd, words)
          if action in {"commit", "push"}
          else ctx.cwd
        )
        if git_safety.managed_worktree(target, ctx.checkout_root):
          return PreResult(
            [
              "WORKTREE BLOCKED: commit, push, and run start belong in the main checkout."
            ],
            BLOCK,
          )
    for current in current_commands:
      action = self.action(current)
      target = (
        git_safety.target_cwd(ctx.cwd, current)
        if action in {"commit", "push"}
        else ctx.cwd
      )
      if action == "commit":
        options = current[current.index("commit") + 1 :]
        auto_stage = any(
          word == "--all"
          or (word.startswith("-") and not word.startswith("--") and "a" in word[1:])
          for word in options
        )
        warning = git_safety.staged_warning(
          target, ctx.session_ids, include_tracked=auto_stage
        )
        if warning:
          return PreResult([warning], BLOCK)
      elif action == "push":
        warning = git_safety.push_warning(target, current)
        if warning:
          return PreResult([warning], BLOCK)
    return PreResult()


class InboxGate:
  """Refuse a line once the unacked count has waited past the call budget."""

  name = "gate"

  def applies(self, ctx: PreContext) -> bool:
    return bool(ctx.pending_ids) and not ctx.is_inbox_recovery()

  def run(self, ctx: PreContext) -> PreResult:
    if ctx.is_push():
      return PreResult(
        [
          "PUSH BLOCKED: a note or answer awaits an ack, so nothing left the sandbox.",
          "Read the inbox, then ack every item: `steer read`, then `steer ack <id> <markdown>`.",
          "Pending: " + ", ".join(ctx.pending_ids),
          f"Blocked by the part `{ctx.blocked_part()}`. Run the inbox calls alone.",
        ],
        BLOCK,
      )
    remaining = GATE_THRESHOLD - ctx.call_count
    if remaining > 0:
      return PreResult([f"bash blocked in {remaining} calls: ack the inbox."])
    return PreResult(
      [
        f"BASH BLOCKED AFTER {GATE_THRESHOLD} CALLS.",
        "Read the inbox, then ack every item: `steer read`, then `steer ack <id> <markdown>`.",
        "Pending: " + ", ".join(ctx.pending_ids),
        f"Blocked by the part `{ctx.blocked_part()}`. Run the inbox calls alone.",
      ],
      BLOCK,
    )


class WireframeGuard:
  """Block a commit that stages a wireframe capture."""

  name = "wireframe"

  def applies(self, ctx: PreContext) -> bool:
    return ctx.touches("git add", "git commit")

  def run(self, ctx: PreContext) -> PreResult:
    if WIREFRAME_SUFFIX not in ctx.line.lower():
      return PreResult()
    return PreResult(
      [f"WIREFRAME BLOCKED: never stage or commit {WIREFRAME_SUFFIX} captures."],
      BLOCK,
    )


class BarePathReminder:
  """Remind the agent to call the entry point by name."""

  name = "bare"

  def applies(self, ctx: PreContext) -> bool:
    return "/scripts/steer" in ctx.line

  def run(self, ctx: PreContext) -> PreResult:
    return PreResult(["Use bare `steer` from any directory. Drop full path."])


class EgressReminder:
  """Remind the agent about the proxy route for network commands."""

  name = "egress"

  def applies(self, ctx: PreContext) -> bool:
    return ctx.touches(*NETWORK_WORDS)

  def run(self, ctx: PreContext) -> PreResult:
    return PreResult(
      ["Use the proxy route for egress. Check the skill reference first."]
    )


SLEEP_IDLE_CAP_SECONDS = 60
SLEEP_UNIT_SECONDS = {"s": 1.0, "m": 60.0, "h": 3600.0, "d": 86400.0}
SLEEP_LOG_READERS = {"cat", "head", "tail", "grep", "rg", "sed", "less"}


def _sleep_seconds(args: list[str]) -> float:
  total = 0.0
  for arg in args:
    unit = arg[-1:].lower()
    number = arg[:-1] if unit in SLEEP_UNIT_SECONDS else arg
    try:
      value = float(number)
    except ValueError:
      continue
    if value > 0:
      total += value * SLEEP_UNIT_SECONDS.get(unit, 1.0)
  return total


class SleepGuard:
  """Block sleeps beside steering work, logs, or a live run, and long waits."""

  name = "sleep"

  def applies(self, ctx: PreContext) -> bool:
    return not ctx.routed and any(
      words and Path(words[0]).name == "sleep" for words, _ in self.commands(ctx)
    )

  def commands(self, ctx: PreContext) -> list[tuple[list[str], str]]:
    """Include shell -c commands and skip harmless wrapper words."""
    pieces = ctx.pieces()
    commands = [(command_words(words), separator) for words, separator in pieces]
    return [
      *commands,
      *(
        (command_words(inner), following)
        for words, _ in commands
        for inner, following in embedded_pieces(words)
      ),
    ]

  def run(self, ctx: PreContext) -> PreResult:
    commands = [
      (Path(words[0]).name, words[1:]) for words, _ in self.commands(ctx) if words
    ]
    if any(head in {"steer", "arena-preview", "preview.py"} for head, _ in commands):
      return PreResult(
        [
          "SLEEP BLOCKED: a sleep beside a steering call holds the turn. Run the call alone."
        ],
        BLOCK,
      )
    if any(
      head in SLEEP_LOG_READERS and any(arg.endswith(".log") for arg in args)
      for head, args in commands
    ):
      return PreResult(
        [
          "SLEEP BLOCKED: a sleep beside a .log read holds the turn. Read the run later."
        ],
        BLOCK,
      )
    if ctx.active_runs:
      names = ", ".join(ctx.active_runs)
      return PreResult(
        [
          f"SLEEP BLOCKED: background run ({names}) is live. Use a worktree or poll when it is the only blocked task."
        ],
        BLOCK,
      )
    if any(
      head == "sleep" and _sleep_seconds(args) >= SLEEP_IDLE_CAP_SECONDS
      for head, args in commands
    ):
      return PreResult(
        ["SLEEP BLOCKED: a long sleep holds the turn. Start a background run instead."],
        BLOCK,
      )
    return PreResult()


class BibleReadGuard:
  """Block a partial read of the bible instead of a full read."""

  name = "bible"

  VERBS = ("cat", "grep", "head", "tail", "rg")
  NAMES = ("ARENA.md", "AGENTS.md")
  SKILL_DIRS = ("arena-skill", "arena-steering")

  def applies(self, ctx: PreContext) -> bool:
    if not ctx.touches(*[f"{verb} " for verb in self.VERBS]):
      return False
    return self.bible_path(ctx.line) is not None

  def bible_path(self, line: str) -> str | None:
    """Name the bible file this line reads, if it reads one."""
    for token in re.split(r"[\s'\"=<>|;&()]+", line):
      name = token.rsplit("/", 1)[-1]
      if name in self.NAMES:
        return token
      parent = token.rsplit("/", 2)[-2] if token.count("/") >= 2 else ""
      if name == "SKILL.md" and parent in self.SKILL_DIRS:
        return token
    return None

  def run(self, ctx: PreContext) -> PreResult:
    found = self.bible_path(ctx.line) or "the bible"
    return PreResult(
      [
        f"BIBLE BLOCKED: `{found}` cannot be read in part.",
        "Use read_file for the full file: ARENA.md, AGENTS.md, and SKILL.md.",
      ],
      BLOCK,
    )


PIPELINE: tuple[PreStep, ...] = (
  SleepGuard(),
  InboxPipeGuard(),
  PollTimeoutGuard(),
  PrStateGuard(),
  DestructivePushGuard(),
  WireframeGuard(),
  InboxGate(),
  GitSafetyGuard(),
  BibleReadGuard(),
  BarePathReminder(),
  EgressReminder(),
)


def run_pipeline(ctx: PreContext) -> PreResult:
  """Run every step in order and stop at the first verdict."""
  messages: list[str] = []
  finished = list(ctx.done)
  for step in PIPELINE:
    if step.name in finished and not (
      (step.name == "gate" and ctx.is_push())
      or (step.name == "sleep" and ctx.active_runs)
      or step.name == "git-safe"
    ):
      continue
    if not step.applies(ctx):
      continue
    result = step.run(ctx)
    messages.extend(result.messages)
    if result.verdict == CONTINUE:
      if step.name not in finished:
        finished.append(step.name)
      continue
    return PreResult(messages, result.verdict, tuple(finished))
  return PreResult(messages, CONTINUE, tuple(finished))


def repo_root() -> Path:
  """Return the checkout root that holds the state directory."""
  checkout = Path(__file__).resolve().parents[3].parent
  return checkout.parent if checkout.name == ".agents" else checkout
