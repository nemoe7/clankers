"""Release must consume the package job's validated artifact."""

import fnmatch
import shlex
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def workflow_jobs():
  return yaml.safe_load((ROOT / ".github/workflows/artifacts.yml").read_text())["jobs"]


def test_release_depends_on_validated_package():
  release = workflow_jobs()["release-gpt-plugins"]
  needs = release["needs"]
  assert "package-gpt-plugins" in ([needs] if isinstance(needs, str) else needs)


def test_release_downloads_the_produced_archive():
  jobs = workflow_jobs()
  upload = next(
    step
    for step in jobs["package-gpt-plugins"]["steps"]
    if str(step.get("uses", "")).startswith("actions/upload-artifact@")
  )
  assert upload["with"]["archive"] is False
  name = Path(upload["with"]["path"]).name
  downloads = [
    step
    for step in jobs["release-gpt-plugins"]["steps"]
    if str(step.get("uses", "")).startswith("actions/download-artifact@")
    and (
      step.get("with", {}).get("name") == name
      or fnmatch.fnmatchcase(name, step.get("with", {}).get("pattern", ""))
    )
  ]
  assert downloads, "Release must fetch the package job's artifact from this run"
  assert all(
    step["with"].get("skip-decompress") == (not upload["with"]["archive"])
    for step in downloads
  )
  assert all("run-id" not in step.get("with", {}) for step in downloads)


def test_release_validates_download_before_publishing():
  steps = workflow_jobs()["release-gpt-plugins"]["steps"]
  download = [
    i
    for i, step in enumerate(steps)
    if str(step.get("uses", "")).startswith("actions/download-artifact@")
  ]
  verify = [
    i
    for i, step in enumerate(steps)
    if "gate_gpt_plugins.py --archive" in step.get("run", "")
  ]
  publish = [
    i for i, step in enumerate(steps) if "release upload" in step.get("run", "")
  ]
  assert download and verify and publish
  assert max(download) < min(verify) < min(publish)


def test_release_does_not_build_a_second_zip():
  for step in workflow_jobs()["release-gpt-plugins"]["steps"]:
    assert "zip" not in shlex.split(step.get("run", "")), (
      "Release must use the validated artifact, not rebuild it"
    )
