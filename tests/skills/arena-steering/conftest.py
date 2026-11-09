from __future__ import annotations

from http.server import ThreadingHTTPServer

import pytest
from arena_steering import cli


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
