"""Progress and verdict logging shared by every stage."""

from __future__ import annotations

import logging
import shlex
import subprocess
import sys
import time
from collections.abc import Callable
from typing import Any

LOG = logging.getLogger("checks")


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


def run_logged(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess:
  rendered = shlex.join(command)
  LOG.info("$ %s", rendered)
  result = subprocess.run(command, check=False, **kwargs)
  LOG.info("exit %s: %s", result.returncode, rendered)
  return result


def run_check(name: str, errors: list[str], check: Callable[[], Any]) -> Any:
  """Run one named check, log its start and verdict, and return what it reported.

  Checks append errors to one shared list. Count only the errors this check adds.
  """
  started = time.perf_counter()
  before = len(errors)
  LOG.info("== %s ...", name)
  reported = check()
  found = len(errors) - before
  span = time.perf_counter() - started
  if found:
    LOG.error("FAIL %s: %s problem(s) in %.2fs", name, found, span)
    for error in errors[before:]:
      LOG.error("- %s", error)
  else:
    LOG.info("ok %s in %.2fs", name, span)
  return reported
