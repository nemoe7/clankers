"""Pre-command pipeline for the shell hook.

Each check is one small class with `applies` and `run`. A step returns `None` to
continue, a message to warn, or a verdict to stop the line. `PIPELINE` is the
registry, so adding, dropping, or reordering a check is one line here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

CONTINUE = 0
END_CALL = 2
BLOCK = 130

GATE_THRESHOLD = 6
CALL_COUNT_META = "pre_call_count"
WIREFRAME_SUFFIX = "-wireframe.png"
NETWORK_WORDS = ("curl", "wget", "git clone", "git fetch", "git ls-remote")


@dataclass
class PreContext:
  """Everything a step may read for one shell line."""

  line: str = ""
  command: str = ""
  shell: str = ""
  done: tuple[str, ...] = ()
  pending_ids: list[str] = field(default_factory=list)
  call_count: int = 0

  def touches(self, *words: str) -> bool:
    """Report whether the command contains any of these substrings."""
    text = f"{self.command} {self.line}"
    return any(word in text for word in words)

  def is_push(self) -> bool:
    return "git push" in self.command or "git push" in self.line

  def blocked_part(self) -> str:
    """Name the last simple command of a chained line."""
    text = self.line or self.command
    parts = [part.strip() for part in re.split(r"&&|\|\||;|\n", text)]
    parts = [part for part in parts if part]
    return parts[-1] if parts else text.strip()


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


class InboxGate:
  """Refuse a line once the unacked count has waited past the call budget."""

  name = "gate"

  def applies(self, ctx: PreContext) -> bool:
    return bool(ctx.pending_ids)

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
    return "/scripts/steer" in ctx.line or "/scripts/demo.py" in ctx.line

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


class SleepGuard:
  """Block a sleep that holds a steering call open."""

  name = "sleep"

  def applies(self, ctx: PreContext) -> bool:
    return "sleep" in ctx.line and (
      "steer " in ctx.line or "arena-preview " in ctx.line
    )

  def run(self, ctx: PreContext) -> PreResult:
    return PreResult(
      ["SLEEP BLOCKED: never sleep beside a steering call. Run the call alone."],
      BLOCK,
    )


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
  WireframeGuard(),
  InboxGate(),
  BibleReadGuard(),
  BarePathReminder(),
  EgressReminder(),
)


def run_pipeline(ctx: PreContext) -> PreResult:
  """Run every step in order and stop at the first verdict."""
  messages: list[str] = []
  finished = list(ctx.done)
  for step in PIPELINE:
    if step.name in finished or not step.applies(ctx):
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
  return Path(__file__).resolve().parents[3]
