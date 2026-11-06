"""Check complete collection and single-skill release archives."""

import importlib.util
import json
import zipfile
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
  "gpt_assets",
  Path(__file__).resolve().parents[3] / "maintenance/gpt_plugins/gate_gpt_plugins.py",
)
gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate)


def test_package_collection_and_each_complete_skill(tmp_path):
  archives = gate.package_archives(tmp_path)
  assert set(archives) == {gate.PLUGIN_NAME, *gate.EXPECTED_SKILLS}
  shared = json.loads(gate.MANIFEST.read_text())
  names = set()
  for name, path in archives.items():
    with zipfile.ZipFile(path) as opened:
      manifest = json.loads(opened.read("plugin.json"))
      assert manifest["name"] == name
      assert manifest["name"] not in names
      names.add(manifest["name"])
      assert manifest["version"] == shared["version"]
      assert manifest["$schema"] == shared["$schema"]
      selected = gate.EXPECTED_SKILLS if name == gate.PLUGIN_NAME else (name,)
      expected = {
        member: source.read_bytes()
        for member, source in gate.archive_members().items()
        if member not in {"plugin.json", gate.ICON_ARCHIVE_PATH}
        and any(member.startswith(f"skills/{skill}/") for skill in selected)
      }
      for skill in selected:
        assert (
          gate.archive_members()[f"skills/{skill}/assets/icon.svg"]
          == gate.ASSETS / f"{skill}.svg"
        )
        expected[f"skills/{skill}/agents/openai.yaml"] = gate.skill_openai_yaml(skill)
      expected[gate.ICON_ARCHIVE_PATH] = (gate.ASSETS / f"{name}.svg").read_bytes()
      interface = manifest["extensions"]["com.openai"]["interface"]
      assert interface["logo"] == gate.ICON_MANIFEST_REF
      assert interface["composerIcon"] == gate.ICON_MANIFEST_REF
      assert 1 <= len(interface["displayName"]) <= 30
      assert 1 <= len(interface["shortDescription"]) <= 30
      assert 1 <= len(interface["longDescription"]) <= 4000
      assert interface["developerName"] == "nemoe7"
      assert interface["category"] == "Developer Tools"
      assert interface["brandColor"].startswith("#")
      files = {p for p in opened.namelist() if not p.endswith("/")}
      notes = set() if name == gate.PLUGIN_NAME else {"README.md"}
      assert files == {"plugin.json", *expected, *notes}
      for member, contents in expected.items():
        assert opened.read(member) == contents
      if notes:
        assert name in opened.read("README.md").decode()
    errors = []
    gate.check_archive(path, errors, skill=None if name == gate.PLUGIN_NAME else name)
    assert not errors, errors


@pytest.mark.parametrize(
  "mutation", ["missing-reference", "changed-skill", "extra-skill"]
)
def test_single_skill_archive_rejects_incomplete_or_changed_files(tmp_path, mutation):
  archives = gate.package_archives(tmp_path)
  skill = next(
    name for name in gate.EXPECTED_SKILLS if gate.reference_files(gate.SHIPPED, name)
  )
  with zipfile.ZipFile(archives[skill]) as opened:
    contents = {name: opened.read(name) for name in opened.namelist()}
  if mutation == "missing-reference":
    del contents[next(name for name in contents if "/references/" in name)]
  elif mutation == "changed-skill":
    contents[f"skills/{skill}/SKILL.md"] += b"changed"
  else:
    other = next(name for name in gate.EXPECTED_SKILLS if name != skill)
    contents[f"skills/{other}/SKILL.md"] = (
      gate.SHIPPED / other / "SKILL.md"
    ).read_bytes()
  damaged = tmp_path / "damaged.zip"
  with zipfile.ZipFile(damaged, "w") as opened:
    for name, data in contents.items():
      opened.writestr(name, data)
  errors = []
  gate.check_archive(damaged, errors, skill=skill)
  assert errors


def test_release_downloads_every_direct_package_artifact():
  import fnmatch

  import yaml

  jobs = yaml.safe_load((gate.ROOT / ".github/workflows/artifacts.yml").read_text())[
    "jobs"
  ]
  uploads = [
    step["with"]
    for step in jobs["package-gpt-plugins"]["steps"]
    if str(step.get("uses", "")).startswith("actions/upload-artifact@")
  ]
  expected = {f"{name}.zip" for name in (gate.PLUGIN_NAME, *gate.EXPECTED_SKILLS)}
  assert {Path(step["path"]).name for step in uploads} == expected
  assert all(step.get("archive") is False for step in uploads)
  downloads = [
    step["with"]
    for step in jobs["release-gpt-plugins"]["steps"]
    if str(step.get("uses", "")).startswith("actions/download-artifact@")
  ]
  for filename in expected:
    matching = [
      step
      for step in downloads
      if step.get("name") == filename
      or fnmatch.fnmatchcase(filename, step.get("pattern", ""))
    ]
    assert matching
    assert all(step.get("skip-decompress") is True for step in matching)
    assert all("run-id" not in step for step in matching)
