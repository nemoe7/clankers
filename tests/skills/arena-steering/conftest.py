from __future__ import annotations

import pytest
from arena_steering import cli


@pytest.fixture(autouse=True)
def _assume_steering_server_is_available(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setattr(
    cli,
    "_healthy_server_url",
    lambda _state_dir: "http://127.0.0.1:8000",
  )
