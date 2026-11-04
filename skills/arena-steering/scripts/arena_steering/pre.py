"""Pre-command pipeline for the shell hook.

Each check is one small class with `applies` and `run`. A step returns `None` to
continue, a message to warn, or a verdict to stop the line. `PIPELINE` is the
registry, so adding, dropping, or reordering a check is one line here.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol
from urllib.parse import parse_qs, urlsplit

from . import git_safety
from .display_paths import home_relative

CONTINUE = 0
END_CALL = 2
BLOCK = 130

GATE_THRESHOLD = 6
CALL_COUNT_META = "pre_call_count"
WIREFRAME_SUFFIX = "-wireframe.png"
SHELL_NAMES = {"bash", "sh", "dash", "zsh", "ksh"}
COMMAND_WRAPPERS = {"env", "command", "nice", "nohup", "stdbuf", "sudo", "time"}
ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z_0-9]*=")
SHELL_WRAPPER = re.compile(
  r"^(?:\S*/)?(?:bash|sh|dash|zsh|ksh)\s+(?:-[\w-]+\s+)*-[\w]*c\s+"
)


def command_words(words: list[str], *, unwrap_timeout: bool = False) -> list[str]:
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
        if head == "command" and words[index] in {"-v", "-V"}:
          return []  # A lookup must not become the command being looked up.
        index += 1
    elif head == "timeout" and unwrap_timeout:
      index += 1
      while index < len(words):
        option = words[index]
        if option in {"-s", "--signal", "-k", "--kill-after"}:
          index += 2
        elif option.startswith("-") or re.fullmatch(r"\d+(?:\.\d+)?[smhd]?", option):
          index += 1
        else:
          break
    else:
      break
  return words[index:]


def shell_line(text: str) -> str:
  """Drop the Bash launcher without losing the command it runs."""
  text = SHELL_WRAPPER.sub("", text.strip(), count=1)
  if len(text) >= 2 and text[0] == text[-1] and text[0] in ("'", '"'):
    return text[1:-1]
  return text


ARENA_PROBE_COMMANDS = {"source ~/.profile"}
PROFILE_MKDIR_LAUNCHER = re.compile(r"/bin/bash -l -c mkdir -p '[^'\r\n]+'")
LOGIN_ACK_WRAPPER = re.compile(
  r"""PATH="\$HOME/\.local/bin:\$PATH" steer ack [0-9a-f]{6} '[^'\r\n]+'"""
)
ARENA_PORT_PROBE = (
  "(command -v ss >/dev/null 2>&1 && ss -ltnH) || netstat -ltn 2>/dev/null || true"
)
ARENA_PROCESS_PROBE_SHA256 = (
  "98cec4863048f02988a62faac41ce8c46bb987e3ec4e843769d123b67d48b665"
)
ARENA_WORKSPACE_VERBS = {"read", "edit", "write"}
STOP_PROCESS_NAME = re.compile(r"clankers-steering-[0-9a-f]{8}")
STOP_PROCESS_SCRIPT_SHA256 = (
  "34229acc3bb28de2035839b6a592ac81c7d4d01bc25f7b74bc361facbb885f39"
)
ISOLATED_READER_SHA256 = (
  "387e3514ed96d946f84178cc5b262b7740321b2638d1de359fd7fd2dac6df6b3"
)


def _isolated_reader(line: str, command: str) -> bool:
  """Match the complete isolated read-only script, varying only path and range."""
  launcher = "/bin/bash -l -c "
  if not line.startswith(launcher + "python3 -I - <<'PY'"):
    return False
  text = line.replace("\r\n", "\n").strip()
  if text.removeprefix(launcher) != command.replace("\r\n", "\n").strip():
    return False
  path_pattern = r'^path = ("(?:\\.|[^"\\])*")$'
  path_match = re.search(path_pattern, text, flags=re.MULTILINE)
  if path_match is None:
    return False
  encoded = path_match.group(1)
  try:
    path = json.loads(encoded)
  except json.JSONDecodeError:
    return False
  if (
    not isinstance(path, str)
    or not Path(path).is_absolute()
    or any(marker in path for marker in ("$(", "`", "\x00"))
    or json.dumps(path) != encoded
  ):
    return False
  text, count = re.subn(path_pattern, "path = <path>", text, flags=re.MULTILINE)
  if count != 1:
    return False
  for name in ("offset", "limit"):
    text, count = re.subn(
      rf"^{name} = ([1-9][0-9]*)$", f"{name} = <{name}>", text, flags=re.MULTILINE
    )
    if count != 1:
      return False
  return hashlib.sha256(text.encode()).hexdigest() == ISOLATED_READER_SHA256


def _checkout_directory_validator(line: str, command: str, root: Path | None) -> bool:
  """Match each checkout prefix check and reject paths escaping through symlinks."""
  launcher = "/bin/bash -l -c "
  if not line.startswith(launcher + "[ -e '"):
    return False
  checks = line.replace("\r\n", "\n").strip().removeprefix(launcher).split("\n")
  if len(checks) < 3:
    return False
  final = re.fullmatch(
    r"\[ -d '([^'\r\n]+)' \] && \{ printf 'DIR\\n'; exit 0; \}", checks[-2]
  )
  if final is None:
    return False
  target = Path(final.group(1))
  if not target.is_absolute() or any(mark in str(target) for mark in ("'", "\r", "\n")):
    return False
  try:
    checkout = (root or repo_root()).resolve()
    relative = target.relative_to(checkout)
    if len(relative.parts) < 2 or ".." in relative.parts:
      return False
    if not target.resolve().is_relative_to(checkout):
      return False
  except (OSError, RuntimeError, ValueError):
    return False
  expected = []
  for index in range(1, len(relative.parts)):
    prefix = relative.parts[:index]
    path = checkout.joinpath(*prefix)
    try:
      if not path.resolve().is_relative_to(checkout):
        return False
    except (OSError, RuntimeError):
      return False
    expected.append(
      f"[ -e '{path}' ] && [ ! -d '{path}' ] "
      f"&& {{ printf 'FILE:%s\\n' '{'/'.join(prefix)}'; exit 0; }}"
    )
  expected.extend(
    [f"[ -d '{target}' ] && {{ printf 'DIR\\n'; exit 0; }}", "printf 'OK\\n'"]
  )
  return checks == expected and command.strip() == expected[0].split(" && ", 1)[0]


def _platform_stop_process(line: str, command: str) -> bool:
  """Match the complete stop script for one eight-hex platform process name."""
  if command.strip() != "echo '===ARENA_STATUS==='":
    return False
  names = set(STOP_PROCESS_NAME.findall(line))
  if len(names) != 1:
    return False
  normalized = (
    line.replace("\r\n", "\n").strip().replace(names.pop(), "clankers-steering-{id}")
  )
  return hashlib.sha256(normalized.encode()).hexdigest() == STOP_PROCESS_SCRIPT_SHA256


def arena_maintenance_call(
  line: str, command: str, *, checkout_root: Path | None = None
) -> bool:
  """Recognize whole Arena utility calls, not user lines that merely mention them."""
  text = shell_line(line).strip()
  if _isolated_reader(line, command):
    return True
  if _checkout_directory_validator(line, command, checkout_root):
    return True
  if _platform_stop_process(line, command):
    return True
  if command.strip() == "source ~/.profile" and PROFILE_MKDIR_LAUNCHER.fullmatch(
    line.strip()
  ):
    return True
  if text == ARENA_PORT_PROBE:
    return True
  if (
    "===ARENA_ENTRY===" in text
    and "===ARENA_PORTS===" in text
    and hashlib.sha256(text.encode()).hexdigest() == ARENA_PROCESS_PROBE_SHA256
  ):
    return True
  if not text or text != shell_line(command).strip():
    return False
  if text in ARENA_PROBE_COMMANDS:
    return True
  if any(operator in text for operator in (";", "|", "&", "\n", "`", "$(")):
    return False
  try:
    words = shlex.split(text)
  except ValueError:
    return False
  direct = command_words(words)
  return (bool(direct) and Path(direct[0]).name in {"ss", "netstat"}) or (
    len(words) >= 2
    and Path(words[0]).name == "arena-workspace"
    and words[1] in ARENA_WORKSPACE_VERBS
  )


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
  renamable_ids: tuple[str, ...] = ()

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
    return any(
      remote_git_push(words)
      for source in (self.line, self.command)
      if source
      for words in _line_commands(PreContext(line=source))
    )

  def is_arena_maintenance(self) -> bool:
    return arena_maintenance_call(
      self.line, self.command, checkout_root=self.checkout_root
    )

  def is_standalone_mkdir(self) -> bool:
    if (
      self.line
      and self.command
      and shell_line(self.line).strip() != shell_line(self.command).strip()
    ):
      return False
    if any(
      mark in shell_line(self.line or self.command) for mark in ("$(", "`", "<", ">")
    ):
      return False
    pieces = self.pieces()
    if len(pieces) != 1 or pieces[0][1] != ";":
      return False
    words = command_words(pieces[0][0])
    return bool(words) and Path(words[0]).name == "mkdir"

  def is_single_push(self) -> bool:
    """Allow a checked, single push to finish without a second EXIT-trap check."""
    if not self.line or not self.command:
      return False
    text = shell_line(self.line).strip()
    if text != shell_line(self.command).strip():
      return False
    if any(mark in text for mark in (";", "|", "&", "\n", "`", "$(", "<", ">")):
      return False
    pieces = self.pieces()
    return (
      len(pieces) == 1
      and pieces[0][1] == ";"
      and remote_git_push(command_words(pieces[0][0]))
    )

  def is_inbox_recovery(self) -> bool:
    """Allow an inbox-only line to clear the gate, including a piped ACK."""
    if (
      self.line
      and self.command
      and self.line.strip() == f"/bin/bash -l -c {self.command.strip()}"
      and LOGIN_ACK_WRAPPER.fullmatch(self.command.strip())
    ):
      return True
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
    return not (self.is_push() or PreContext(line=self.command).is_push())

  def blocked_part(self) -> str:
    """Name the last simple command of a chained line."""
    text = self.line or self.command
    parts = [part.strip() for part in re.split(r"&&|\|\||;|\n", text)]
    parts = [part for part in parts if part]
    return parts[-1] if parts else text.strip()


# Count means eligible for the pending-inbox budget. Block means the six-call gate applies at its limit.
# Unconditional guards, including pending pushes, still run separately before this policy.
BASH_COMMAND_POLICY: dict[str, tuple[bool, bool]] = {
  "python3": (True, True),
  "python": (True, True),
  "standalone mkdir": (True, False),
  "inbox recovery": (False, False),
  "arena utility": (False, False),
  "routed background": (False, False),
  "*": (True, True),
}


def bash_command_policy(ctx: PreContext) -> tuple[bool, bool]:
  """Classify one Bash line without weakening the unconditional guards."""
  if ctx.routed:
    return BASH_COMMAND_POLICY["routed background"]
  if ctx.is_arena_maintenance():
    return BASH_COMMAND_POLICY["arena utility"]
  if ctx.is_inbox_recovery():
    return BASH_COMMAND_POLICY["inbox recovery"]
  if ctx.is_standalone_mkdir():
    return BASH_COMMAND_POLICY["standalone mkdir"]
  pieces = ctx.pieces()
  if len(pieces) == 1 and pieces[0][1] == ";":
    words = command_words(pieces[0][0])
    if words:
      key = Path(words[0]).name
      if key in BASH_COMMAND_POLICY:
        return BASH_COMMAND_POLICY[key]
  return BASH_COMMAND_POLICY["*"]


def embedded_pieces(words: list[str]) -> list[tuple[list[str], str]]:
  """Read the command string passed to a shell's -c option, if present."""
  if not words or Path(words[0]).name not in SHELL_NAMES:
    return []
  for index in range(1, len(words) - 1):
    if words[index].startswith("-") and "c" in words[index][1:]:
      return PreContext(line=words[index + 1]).pieces()
  return []


@dataclass(frozen=True)
class RouteRequest:
  """A shell line the CLI must handle instead of executing it again."""

  kind: str
  args: tuple[str, ...]


@dataclass
class PreResult:
  """One step outcome: the text to print, verdict, route, and blocking guard."""

  messages: list[str] = field(default_factory=list)
  verdict: int = CONTINUE
  done: tuple[str, ...] = ()
  route: RouteRequest | None = None
  blocked_by: str = ""


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
      [
        "VIOLATION: Inbox piped.",
        "Run `steer read` or `steer poll` alone to keep the full output visible.",
      ],
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
        "VIOLATION: timeout wrapped poll. Set Bash tool timeout 1800s.",
        "Poll returns within 1799s. Do not use shell `timeout`.",
      ],
      BLOCK,
    )


def _line_commands(ctx: PreContext, *, unwrap_timeout: bool = False) -> list[list[str]]:
  """Include direct commands and shell -c scripts without matching quoted prose."""
  pieces = [
    command_words(words, unwrap_timeout=unwrap_timeout) for words, _ in ctx.pieces()
  ]
  return [
    *pieces,
    *(
      command_words(inner, unwrap_timeout=unwrap_timeout)
      for words in pieces
      for inner, _ in embedded_pieces(words)
    ),
  ]


def remote_git_push(words: list[str]) -> bool:
  """Recognize Git's push subcommand, not `git stash push` or option values."""
  if not words or Path(words[0]).name != "git":
    return False
  args = words[1:]
  index = 0
  values = {
    "-C",
    "-c",
    "--git-dir",
    "--work-tree",
    "--namespace",
    "--super-prefix",
    "--config-env",
  }
  flags = {"-p", "--paginate", "-P", "--no-pager", "--no-replace-objects", "--bare"}
  prefixes = (
    "-C",
    "-c",
    "--git-dir=",
    "--work-tree=",
    "--namespace=",
    "--super-prefix=",
    "--config-env=",
  )
  while index < len(args):
    word = args[index]
    if word in {"-h", "--help", "-v", "--version"}:
      return False
    if word in values:
      index += 2
    elif word in flags or word.startswith(prefixes):
      index += 1
    elif word.startswith("-"):
      return "push" in args[index + 1 :]
    else:
      return word == "push"
  return False


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
      [
        "VIOLATION: PR mod blocked. NEVER merge, close, reopen.",
        "Use PR reads or metadata edits instead of state writes.",
      ],
      BLOCK,
    )


class DestructivePushGuard:
  """Block deletes and wholesale ref rewrites before any push executes."""

  name = "push-refs"

  def applies(self, ctx: PreContext) -> bool:
    for words in _line_commands(ctx):
      if not remote_git_push(words):
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
    return PreResult(
      [
        "VIOLATION: Push blocked. Destructive mod found.",
        "Remove destructive push flags or ref deletion, then retry safely.",
      ],
      BLOCK,
    )


class GitSafetyGuard:
  """Inspect staged commits, managed worktrees, and fresh remote push ancestry."""

  name = "git-safe"

  def applies(self, ctx: PreContext) -> bool:
    return any(self.action(words) for words in _line_commands(ctx))

  def action(self, words: list[str]) -> str:
    if not words:
      return ""
    head, args = Path(words[0]).name, words[1:]
    if remote_git_push(words):
      return "push"
    if head == "git" and "commit" in args:
      return "commit"
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
          ["Push blocked. remote default compare failed. Check remote and retry."],
          BLOCK,
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
          command = "run start" if action == "gate" else action
          return PreResult(
            [f"{command} blocked in worktree. Run in the main checkout."],
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
          target,
          ctx.session_ids,
          renamable_ids=ctx.renamable_ids,
          include_tracked=auto_stage,
        )
        if warning:
          content = warning.startswith(
            (
              "Wireframe found staged.",
              "VIOLATION: Cited session-local ID.",
            )
          )
          return PreResult(
            [warning], BLOCK, blocked_by="commit-content" if content else ""
          )
      elif action == "push":
        warning = git_safety.push_warning(target, current)
        if warning:
          return PreResult([warning], BLOCK)
    return PreResult()


class InboxGate:
  """Refuse a line once the unacked count has waited past the call budget."""

  name = "gate"

  def applies(self, ctx: PreContext) -> bool:
    if ctx.pending_ids and ctx.is_push():
      return True
    if ctx.is_arena_maintenance():
      return False
    if not ctx.pending_ids:
      return False
    return bash_command_policy(ctx)[1]

  def run(self, ctx: PreContext) -> PreResult:
    if ctx.is_push():
      return PreResult(
        [
          "VIOLATION: Push blocked. Inbox has pending. Read and ack all. Retry.",
          "Nothing left the sandbox. Use `steer read`, then `steer ack` for each item.",
          "Pending: " + ", ".join(ctx.pending_ids),
          f"Blocked by the part `{ctx.blocked_part()}`. Run the inbox calls alone.",
        ],
        BLOCK,
      )
    remaining = GATE_THRESHOLD - ctx.call_count
    if remaining > 0:
      return PreResult([f"bash block in {remaining} calls. Read and ack now."])
    return PreResult(
      [
        "VIOLATION: Bash blocked. Read and ack all NOW.",
        f"Threshold: {GATE_THRESHOLD} calls. Use `steer read`, then `steer ack` for each item.",
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
      ["Commit has wireframe. Remove and retry."],
      BLOCK,
      blocked_by="commit-content",
    )


ACK_QUOTE = re.compile(
  r'(?:^|[;&|]\s*)\s*(?:\S*/)?(?:steer|arena-preview)\s+ack\b[^;|]*?"'
)


class AckQuoteReminder:
  """Warn before an ACK's double-quoted backticks run as shell commands."""

  name = "ack-quote"

  def applies(self, ctx: PreContext) -> bool:
    text = shell_line(ctx.line or ctx.command)
    match = ACK_QUOTE.search(text)
    if match is None:
      return False
    escaped = False
    for char in text[match.end() :]:
      if char == "`" and not escaped:
        return True
      if char == '"' and not escaped:
        break
      escaped = char == "\\" and not escaped
      if char != "\\":
        escaped = False
    return False

  def run(self, ctx: PreContext) -> PreResult:
    return PreResult(
      [
        "ACK WARNING: double-quoted backticks run as shell commands. Single-quote the ACK text."
      ]
    )


class BarePathReminder:
  """Remind the agent to call the executable by name, not by script path."""

  name = "bare"

  def applies(self, ctx: PreContext) -> bool:
    installed = Path.home() / ".local/bin/steer"
    for words in _line_commands(ctx):
      if words and (
        words[0].endswith("/scripts/steer") or Path(words[0]).expanduser() == installed
      ):
        return True
      if (
        len(words) > 1
        and Path(words[0]).name.startswith("python")
        and words[1].endswith("/scripts/steer")
      ):
        return True
    return False

  def run(self, ctx: PreContext) -> PreResult:
    return PreResult(
      ["Use bare `steer` from any directory. It works without the full path."]
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
    return (
      not _platform_stop_process(ctx.line, ctx.command)
      and not ctx.routed
      and any(
        words and Path(words[0]).name == "sleep" for words, _ in self.commands(ctx)
      )
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
        ["VIOLATION: Sleep BANNED. Run alone."],
        BLOCK,
      )
    if any(
      head in SLEEP_LOG_READERS and any(arg.endswith(".log") for arg in args)
      for head, args in commands
    ):
      return PreResult(
        [
          "VIOLATION: Sleep log read BANNED. Read log later, start worktree for open task, poll if no more task."
        ],
        BLOCK,
      )
    if ctx.active_runs:
      names = ", ".join(ctx.active_runs)
      return PreResult(
        [
          "VIOLATION: Sleep run BANNED. Read log later, start worktree for open task, poll if no more task.",
          f"Live run: {names}.",
        ],
        BLOCK,
      )
    if any(
      head == "sleep" and _sleep_seconds(args) >= SLEEP_IDLE_CAP_SECONDS
      for head, args in commands
    ):
      return PreResult(
        [f"VIOLATION: Sleep BANNED over {SLEEP_IDLE_CAP_SECONDS}s. Use detached runs."],
        BLOCK,
      )
    return PreResult()


class BibleReadGuard:
  """Block a partial read of the bible instead of a full read."""

  name = "bible"

  VERBS = ("cat", "grep", "head", "tail", "rg")
  INSTALLED_SKILL = Path(".agents/skills/arena-steering/SKILL.md")

  def applies(self, ctx: PreContext) -> bool:
    return self.bible_path(ctx) is not None

  def bible_path(self, ctx: PreContext) -> str | None:
    """Name a protected read target, leaving checked-in skill source searchable."""
    root = Path(os.path.abspath(ctx.checkout_root or repo_root()))
    cwd = Path(os.path.abspath(ctx.cwd or root))
    protected = {root / "AGENTS.md", root / "ARENA.md", root / self.INSTALLED_SKILL}
    for words in _line_commands(ctx):
      if not words or Path(words[0]).name not in self.VERBS:
        continue
      if Path(words[0]).name == "rg" and "--files" in words[1:]:
        continue  # File discovery does not read file contents.
      for token in words[1:]:
        path = Path(token)
        if path.name not in {"AGENTS.md", "ARENA.md", "SKILL.md"}:
          continue
        target = Path(os.path.abspath(path if path.is_absolute() else cwd / path))
        if target in protected:
          return home_relative(target)
    return None

  def run(self, ctx: PreContext) -> PreResult:
    found = self.bible_path(ctx) or "the bible"
    return PreResult(
      [
        f"VIOLATION: Partial read blocked: `{found}`. Use `read_file` only if absent from context.",
        "Read protected bible files in full, never through Bash.",
      ],
      BLOCK,
    )


TEST_RUNNERS = {"pytest", "py.test", "tox", "nox"}
TEST_COMMANDS = (
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
GITHUB_LOG = re.compile(r"/?repos/[^/]+/[^/]+/actions/(jobs|runs)/(\d+)/logs/?$")
GITHUB_PR = re.compile(r"/?repos/[^/]+/[^/]+/pulls/(\d+)/?$")


def _test_route(words: list[str]) -> RouteRequest | None:
  if not words:
    return None
  head, args = Path(words[0]).name, words[1:]
  if any(flag in args for flag in ("--help", "-h", "--version", "-V")):
    return None
  if head in TEST_RUNNERS:
    return RouteRequest("run", ("pytest" if head == "py.test" else head,))
  if head.startswith("python") and args[:2] == ["-m", "pytest"]:
    return RouteRequest("run", ("pytest",))
  if head == "node" and args[:1] == ["--test"]:
    return RouteRequest("run", ("node-tests",))
  if head == "gh" and args[:2] in (["pr", "checks"], ["run", "watch"]):
    return RouteRequest("run", ("pr-checks" if args[0] == "pr" else "run-watch",))
  for command, name in TEST_COMMANDS:
    if head != command[0]:
      continue
    selected = args[: len(command) - 1]
    if len(selected) == len(command) - 1 and all(
      value.startswith(expected[:-1]) if expected.endswith("*") else value == expected
      for value, expected in zip(selected, command[1:])
    ):
      return RouteRequest("run", (name,))
  return None


def _pr_patch_fields(args: list[str]) -> tuple[str, str]:
  title, body_file = "", ""
  for index, word in enumerate(args):
    value = ""
    if word in {"-f", "-F", "--field", "--raw-field"} and index + 1 < len(args):
      value = args[index + 1]
    elif word.startswith(("--field=", "--raw-field=")):
      value = word.split("=", 1)[1]
    elif word.startswith(("-f", "-F")) and len(word) > 2:
      value = word[2:]
    key, sep, field = value.partition("=")
    if sep and key == "title":
      title = field
    elif sep and key == "body" and field.startswith("@"):
      body_file = field[1:]
  return title, body_file


def _github_route(words: list[str]) -> RouteRequest | None:
  if not words:
    return None
  head, args = Path(words[0]).name, words[1:]
  if head not in {"gh", "curl"} or (head == "gh" and args[:1] != ["api"]):
    return None
  if any(flag in args for flag in ("--help", "-h", "--version", "-V")):
    return None
  for arg in args:
    url = urlsplit(arg)
    if url.scheme:
      if url.hostname != "api.github.com":
        continue
      path = url.path
    elif head == "gh":
      path = arg.split("?", 1)[0]
    else:
      continue
    if match := GITHUB_LOG.fullmatch(path):
      log_type, number = match.groups()
      return RouteRequest("job-log", (log_type, number))
    if match := GITHUB_PR.fullmatch(path):
      method = ""
      for index, flag in enumerate(args):
        if flag in {"-X", "--method", "--request"} and index + 1 < len(args):
          method = args[index + 1].upper()
        elif flag.startswith(("-X", "--method=", "--request=")):
          method = flag.split("=", 1)[-1].upper() if "=" in flag else flag[2:].upper()
      if method == "PATCH":
        title, body_file = _pr_patch_fields(args)
        if title and body_file:
          return RouteRequest("pr-update", (match.group(1), title, body_file))
        if head == "curl":
          return RouteRequest("pr-update-manual", (match.group(1),))
        return RouteRequest("pr-update-possible", (match.group(1),))
  return None


def post_push_watch(line: str) -> bool:
  """A successful line needs a check watch only after a real push or PR creation."""
  for words in _line_commands(PreContext(line=line), unwrap_timeout=True):
    if not words:
      continue
    head, args = Path(words[0]).name, words[1:]
    if any(flag in args for flag in ("--help", "-h", "--version", "-V")):
      continue
    if head == "gh" and args[:2] == ["pr", "create"]:
      return True
    if remote_git_push(words):
      options = args[args.index("push") + 1 :]
      if not any(flag in options for flag in ("-n", "--dry-run")):
        return True
  return False


class RouteGuard:
  """Route single test, check-wait, PR-update, and job-log lines safely."""

  name = "route"

  def applies(self, ctx: PreContext) -> bool:
    return not ctx.routed and any(
      _test_route(words) or _github_route(words)
      for words in _line_commands(ctx, unwrap_timeout=True)
    )

  def run(self, ctx: PreContext) -> PreResult:
    pieces = ctx.pieces()
    if (
      len(pieces) != 1
      or pieces[0][1] != ";"
      or (ctx.command and shell_line(ctx.line) != shell_line(ctx.command))
    ):
      return PreResult(
        [
          (
            "VIOLATION: Mixed shell blocked for auto detach. "
            "Use separate calls or explicit `steer run start`."
          ),
          "For a detached command, use `steer run start <name> -- <remaining command>`.",
          "For a GitHub call, use its helper.",
        ],
        BLOCK,
      )
    route = next(
      request
      for words in _line_commands(ctx, unwrap_timeout=True)
      if (request := _test_route(words) or _github_route(words)) is not None
    )
    if route.kind == "pr-update-possible":
      return PreResult()  # Ordinary single-field metadata PATCHes remain allowed.
    if route.kind == "pr-update-manual":
      return PreResult(
        [
          (
            f"PR PATCH routed. Use `steer pr-update -n {route.args[0]} "
            "-t <title> -f <workspace-file>` instead of direct curl PATCH."
          )
        ],
        BLOCK,
      )
    return PreResult(verdict=END_CALL, route=route)


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
  RouteGuard(),
  AckQuoteReminder(),
  BarePathReminder(),
)


def run_pipeline(ctx: PreContext) -> PreResult:
  """Run every step in order and stop at the first verdict."""
  messages: list[str] = []
  finished = list(ctx.done)
  for step in PIPELINE:
    if step.name in finished and not (
      (step.name == "gate" and ctx.is_push())
      or (step.name == "sleep" and ctx.active_runs)
      or step.name in {"git-safe", "route", "ack-quote"}
    ):
      continue
    if not step.applies(ctx):
      if step.name == "gate" and ctx.is_arena_maintenance():
        # An exact utility shell still runs profile cleanup before EXIT.
        finished.append(step.name)
      continue
    result = step.run(ctx)
    messages.extend(result.messages)
    if result.verdict == CONTINUE:
      if step.name not in finished:
        finished.append(step.name)
      continue
    return PreResult(
      messages,
      result.verdict,
      tuple(finished),
      result.route,
      (result.blocked_by or step.name) if result.verdict == BLOCK else "",
    )
  return PreResult(messages, CONTINUE, tuple(finished))


def repo_root() -> Path:
  """Return the checkout root that holds the state directory."""
  checkout = Path(__file__).resolve().parents[3].parent
  return checkout.parent if checkout.name == ".agents" else checkout
