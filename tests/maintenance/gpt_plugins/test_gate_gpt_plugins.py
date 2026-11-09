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
  shared = json.loads(gate.MANIFEST.read_text(encoding="utf-8"))
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


def test_release_builds_verifies_and_publishes_every_package():
  import fnmatch

  import yaml

  jobs = yaml.safe_load(
    (gate.ROOT / ".github/workflows/artifacts.yml").read_text(encoding="utf-8")
  )["jobs"]
  steps = jobs["release-gpt-plugins"]["steps"]
  scripts = [step.get("run", "") for step in steps]
  build = next(i for i, script in enumerate(scripts) if "--package-dir ." in script)
  verify = next(i for i, script in enumerate(scripts) if "--archives-dir ." in script)
  publish = next(i for i, script in enumerate(scripts) if "gh release upload" in script)
  assert build < verify < publish
  assert "gh release create" in scripts[publish]
  assert "gpt-*.zip nemoizer.zip" in scripts[publish]
  for filename in (f"{name}.zip" for name in (gate.PLUGIN_NAME, *gate.EXPECTED_SKILLS)):
    assert fnmatch.fnmatchcase(filename, "gpt-*.zip") or filename == "nemoizer.zip"


@pytest.mark.parametrize(
  ("current", "accepted"),
  [
    ("1.10.31", False),
    ("1.10.30", False),
    ("1.10.32", True),
    ("1.11.0", True),
    ("2.0.0", True),
    ("1.10.33", False),
    ("1.12.0", False),
    ("3.0.0", False),
  ],
)
def test_plugin_version_requires_exactly_one_bump(
  tmp_path, monkeypatch, current, accepted
):
  baseline = tmp_path / "default-plugin.json"
  baseline.write_text(json.dumps({"version": "1.10.31"}), encoding="utf-8")
  manifest = tmp_path / "plugin.json"
  manifest.write_text(json.dumps({"version": current}), encoding="utf-8")
  monkeypatch.setattr(gate, "MANIFEST", manifest)
  errors = []
  gate.check_version_bump(baseline, errors)
  assert (not errors) is accepted
