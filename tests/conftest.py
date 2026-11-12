from __future__ import annotations

import pytest


@pytest.fixture(autouse=True, scope="session")
def _isolate_global_git_config(tmp_path_factory: pytest.TempPathFactory):
  """Keep the user's global Git config and hooks out of test repos."""
  config = tmp_path_factory.mktemp("git") / "gitconfig"
  config.touch()
  with pytest.MonkeyPatch.context() as patch:
    patch.setenv("GIT_CONFIG_GLOBAL", str(config))
    yield
