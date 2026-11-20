"""Progress and verdict logging shared by every stage."""

from __future__ import annotations

import logging
import sys
import time
from collections.abc import Callable
from typing import Any

LOG = logging.getLogger("checks")

EXACT_COPY = "live clause matches refs exactly; compression or review may be missing"
EQUAL_TOKENS_REWORDED = (
  "live clause reworded at the same token count as refs; compression did not shrink it"
)


class _StdoutHandler(logging.StreamHandler):
  """Write to whatever `sys.stdout` is now, so captured and reconfigured streams both work."""

  @property
  def stream(self):
    return sys.stdout

  @stream.setter
  def stream(self, value) -> None:
    pass


if not LOG.handlers:
  _handler = _StdoutHandler()
  _handler.setFormatter(logging.Formatter("%(message)s"))
  LOG.addHandler(_handler)
  LOG.setLevel(logging.INFO)
  LOG.propagate = False


class Notes:
  """Collect per-line parity findings, flush one grouped warning per file."""

  def __init__(self) -> None:
    self._groups: dict[tuple[str, str | None, str], list[int]] = {}

  def add(self, file: str, section: str | None, lineno: int, kind: str) -> None:
    self._groups.setdefault((file, section, kind), []).append(lineno)

  @property
  def count(self) -> int:
    return sum(len(linenos) for linenos in self._groups.values())

  def flush(self) -> None:
    """Log one warning per file, then reset. A second flush logs nothing."""
    by_file: dict[str, list[tuple[str | None, str, list[int]]]] = {}
    for (file, section, kind), linenos in self._groups.items():
      by_file.setdefault(file, []).append((section, kind, linenos))
    for file, groups in by_file.items():
      parts = [
        f"{section} {', '.join(self._marker(n, kind) for n in linenos)}"
        if section
        else ", ".join(self._marker(n, kind) for n in linenos)
        for section, kind, linenos in groups
      ]
      LOG.warning("- %s - %s", file, ". ".join(parts))
    self._groups.clear()

  @staticmethod
  def _marker(lineno: int, kind: str) -> str:
    return f"{lineno}*" if kind == EQUAL_TOKENS_REWORDED else str(lineno)


def run_check(
  name: str, errors: list[str], check: Callable[[], Any], warnings: int = 0
) -> Any:
  """Run one named check and log its verdict as `{step}: {result} {time}`.

  Checks append errors to one shared list. Count only the errors this check adds.
  A positive `warnings` count reports a `warn` verdict instead of `ok`.
  """
  started = time.perf_counter()
  before = len(errors)
  reported = check()
  found = len(errors) - before
  span = time.perf_counter() - started
  if found:
    LOG.error("%s: FAIL %.2fs", name, span)
    for error in errors[before:]:
      LOG.error("- %s", error)
  elif warnings:
    LOG.warning("%s: warn %.2fs", name, span)
  else:
    LOG.info("%s: ok %.2fs", name, span)
  return reported
