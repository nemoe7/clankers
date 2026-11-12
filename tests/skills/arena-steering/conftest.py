from __future__ import annotations

import importlib.util
import os
from http.server import ThreadingHTTPServer

import pytest

pytest.importorskip("fcntl", reason="arena-steering needs POSIX fcntl")

from arena_steering import cli


@pytest.fixture(autouse=True)
def _require_browser_when_requested() -> None:
  """Turn a missing browser into a failure when CI_REQUIRE_BROWSER is set."""
  if os.environ.get("CI_REQUIRE_BROWSER") != "1":
    return
  if importlib.util.find_spec("playwright.sync_api") is None:
    pytest.fail("CI_REQUIRE_BROWSER=1 but playwright is not installed")


@pytest.fixture(autouse=True)
def _assume_steering_server_is_available(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setattr(
    cli,
    "_healthy_server_url",
    lambda _state_dir: "http://127.0.0.1:8000",
  )


@pytest.fixture(autouse=True)
def _join_browser_request_threads(
  request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> None:
  if request.node.path.name.endswith(("_ui.py", "_views.py")):
    monkeypatch.setattr(ThreadingHTTPServer, "daemon_threads", False)
