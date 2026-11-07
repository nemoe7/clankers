"""The release must build and verify its own archives before publishing."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]


def test_release_builds_once_and_verifies_before_publication():
  jobs = yaml.safe_load((ROOT / ".github/workflows/artifacts.yml").read_text())["jobs"]
  assert set(jobs) == {"release-gpt-plugins", "publish-clankers-rules"}
  steps = jobs["release-gpt-plugins"]["steps"]
  positions = [
    next(index for index, step in enumerate(steps) if marker in step.get("run", ""))
    for marker in (
      "gate_gpt_plugins.py --package-dir",
      "gate_gpt_plugins.py --archive",
      "gh release upload",
    )
  ]
  assert positions == sorted(positions) and len(set(positions)) == 3
  assert not any(
    "actions/upload-artifact" in step.get("uses", "")
    or "actions/download-artifact" in step.get("uses", "")
    for step in steps
  )
