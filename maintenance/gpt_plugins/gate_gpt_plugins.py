#!/usr/bin/env python3
"""Check the gpt-plugins collection and, with --archive, its packaged zip.

The collection ships one Agent Plugins manifest and the skills listed in
EXPECTED_SKILLS. `gpt-plugins/refs/skills/` holds the readable sources and
`gpt-plugins/skills/` holds manually compressed copies. Structure checks do not
prove semantic parity. Review every clause against refs.
Packaging rewrites nothing, so `--archive` compares the zip members with the
committed bytes and rejects anything the collection does not ship, including
`refs/`. The check compares the manifest against the canonical schema fetched from
agent-plugins.org, never a vendored copy.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
import zipfile
from pathlib import Path

import check

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "gpt-plugins"
MANIFEST = PLUGIN / "plugin.json"
# The collection README documents the layout for a human reader, so the tree allows it
# and shipped_paths() leaves it out of the archive.
README = PLUGIN / "README.md"
REFS = PLUGIN / "refs" / "skills"
SHIPPED = PLUGIN / "skills"
PLUGIN_NAME = "gpt-plugins"
EXPECTED_SKILLS = ("gpt-quirks", "gpt-handoff", "gpt-planning", "gpt-github")
SCHEMA_URL = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"


def shipped_paths() -> list[Path]:
  """Return the collection files the archive carries, in a stable order."""
  paths = [MANIFEST]

  for name in EXPECTED_SKILLS:
    paths.append(SHIPPED / name / "SKILL.md")

  return paths


def load_schema(source: str, errors: list[str]) -> dict | None:
  """Return the canonical manifest schema from a URL or a local path."""
  try:
    if source.startswith(("http://", "https://")):
      request = urllib.request.Request(
        source, headers={"User-Agent": "clankers-maintenance"}
      )

      with urllib.request.urlopen(request, timeout=30) as response:
        raw = response.read()
    else:
      raw = Path(source).read_bytes()

    schema = json.loads(raw)
  except Exception as error:
    errors.append(f"{source}: cannot load the canonical schema: {error}")
    return None

  try:
    import jsonschema
  except ModuleNotFoundError:
    errors.append("jsonschema is missing: python3 -m pip install jsonschema")
    return None

  try:
    jsonschema.Draft202012Validator.check_schema(schema)
  except Exception as error:
    errors.append(f"{source}: the downloaded schema is invalid: {error}")
    return None

  if schema.get("$id") != SCHEMA_URL:
    errors.append(
      f"{source}: schema $id is {schema.get('$id')!r}, expected {SCHEMA_URL!r}"
    )

  return schema


def check_manifest(schema: dict | None, errors: list[str]) -> None:
  """Check the manifest identity, then compare it with the schema."""
  if not MANIFEST.is_file():
    errors.append("gpt-plugins/plugin.json is missing")
    return

  try:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
  except json.JSONDecodeError as error:
    errors.append(f"gpt-plugins/plugin.json: invalid JSON: {error}")
    return

  if not isinstance(manifest, dict):
    errors.append("gpt-plugins/plugin.json: the manifest is not a JSON object")
    return

  if manifest.get("name") != PLUGIN_NAME:
    errors.append(
      f"gpt-plugins/plugin.json: name is {manifest.get('name')!r}, expected {PLUGIN_NAME!r}"
    )

  if manifest.get("$schema") != SCHEMA_URL:
    errors.append(
      f"gpt-plugins/plugin.json: $schema is {manifest.get('$schema')!r}, expected {SCHEMA_URL!r}"
    )

  if schema is None:
    return

  import jsonschema

  validator = jsonschema.Draft202012Validator(schema)

  for problem in sorted(
    validator.iter_errors(manifest), key=lambda item: list(item.path)
  ):
    location = "/".join(str(part) for part in problem.path) or "the manifest root"
    errors.append(
      f"gpt-plugins/plugin.json: schema violation at {location}: {problem.message}"
    )


def check_skill(root: Path, name: str, errors: list[str]) -> None:
  """Check one SKILL.md against the Agent Skills limits this repository enforces."""
  directory = root / name
  path = directory / "SKILL.md"
  label = path.relative_to(ROOT)

  if not path.is_file():
    errors.append(f"{label}: missing SKILL.md")
    return

  text = path.read_text(encoding="utf-8")
  values, frontmatter_errors = check.parse_frontmatter(text)

  errors.extend(f"{label}: {error}" for error in frontmatter_errors)

  unknown = set(values) - check.EXPECTED_SKILL_FIELDS

  if unknown:
    errors.append(f"{label}: unknown frontmatter fields: {sorted(unknown)}")

  if values.get("name") != name or not check.NAME_RE.fullmatch(values.get("name", "")):
    errors.append(f"{label}: invalid name {values.get('name')!r}, expected {name!r}")

  description = values.get("description", "")

  if not 1 <= len(description) <= 1024:
    errors.append(
      f"{label}: description length is {len(description)}, expected 1..1024"
    )

  if len(text.splitlines()) > 500:
    errors.append(f"{label}: SKILL.md exceeds 500 lines")

  stray = sorted(item.name for item in directory.iterdir() if item.name != "SKILL.md")

  if stray:
    errors.append(f"{label.parent}: unexpected extra entries: {stray}")


def check_collections(errors: list[str]) -> None:
  """Check both trees hold exactly the expected skills, and that they agree."""
  for root in (REFS, SHIPPED):
    label = root.relative_to(ROOT)

    if not root.is_dir():
      errors.append(f"{label}: missing directory")
      continue

    found = sorted(item.name for item in root.iterdir())

    if found != sorted(EXPECTED_SKILLS):
      errors.append(f"{label}: skills are {found}, expected {sorted(EXPECTED_SKILLS)}")

    for name in EXPECTED_SKILLS:
      check_skill(root, name, errors)

  for name in EXPECTED_SKILLS:
    source = REFS / name / "SKILL.md"
    copy = SHIPPED / name / "SKILL.md"

    if not source.is_file() or not copy.is_file():
      continue

    ref_text = source.read_text(encoding="utf-8")
    live_text = copy.read_text(encoding="utf-8")
    if not matching_structure(ref_text, live_text):
      errors.append(
        f"{copy.relative_to(ROOT)}: headings differ or compressed copy exceeds refs size"
      )


def matching_structure(reference: str, live: str) -> bool:
  return re.findall(r"^#+ .+$", reference, re.MULTILINE) == re.findall(
    r"^#+ .+$", live, re.MULTILINE
  ) and len(live.encode()) <= len(reference.encode())


def check_tree(errors: list[str]) -> None:
  """Reject any collection file the manifest, refs and shipped skills do not account for."""
  if not PLUGIN.is_dir():
    errors.append("gpt-plugins/ is missing")
    return

  allowed = (MANIFEST, README, REFS, SHIPPED)
  stray = []

  for path in sorted(PLUGIN.rglob("*")):
    if path.is_dir():
      continue

    if not any(path == item or item in path.parents for item in allowed):
      stray.append(str(path.relative_to(ROOT)))

  if stray:
    errors.append(f"gpt-plugins/: unexpected files: {stray}")


def parse_plugin_version(value: object) -> tuple[int, ...] | None:
  """Return dotted integer parts, or None when the value is not a version."""
  if not isinstance(value, str) or not value:
    return None

  parts = value.split(".")

  if not parts or any(not part.isdigit() for part in parts):
    return None

  return tuple(int(part) for part in parts)


def check_version_bump(base_path: Path, errors: list[str]) -> None:
  """Require gpt-plugins/plugin.json version to be greater than the base manifest."""
  if not base_path.is_file():
    errors.append(f"{base_path}: missing base manifest")
    return

  try:
    base = json.loads(base_path.read_text(encoding="utf-8"))
  except json.JSONDecodeError as error:
    errors.append(f"{base_path}: invalid JSON: {error}")
    return

  if not isinstance(base, dict):
    errors.append(f"{base_path}: the manifest is not a JSON object")
    return

  if not MANIFEST.is_file():
    return

  try:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
  except json.JSONDecodeError:
    return

  if not isinstance(manifest, dict):
    return

  new_raw = manifest.get("version")
  base_raw = base.get("version")
  new = parse_plugin_version(new_raw)
  old = parse_plugin_version(base_raw)

  if new is None:
    errors.append(
      f"gpt-plugins/plugin.json: version {new_raw!r} is not dotted integers"
    )
    return

  if old is None:
    errors.append(f"{base_path}: version {base_raw!r} is not dotted integers")
    return

  if new <= old:
    errors.append(
      f"gpt-plugins/plugin.json: version {new_raw} must be greater than base {base_raw}"
    )


def run_self_check() -> None:
  """Assert version comparison for dotted integer plugin versions."""
  assert parse_plugin_version("1.2.0") == (1, 2, 0)
  assert parse_plugin_version("1.2.1") > parse_plugin_version("1.2.0")
  assert parse_plugin_version("2.0.0") > parse_plugin_version("1.9.9")
  assert parse_plugin_version("1.10.0") > parse_plugin_version("1.9.0")
  assert parse_plugin_version("") is None
  assert parse_plugin_version("1.2.a") is None
  assert parse_plugin_version(None) is None
  assert matching_structure("# Skill\nFull wording", "# Skill\nShort")
  assert not matching_structure("# Skill\nFull wording", "# Other\nShort")
  assert not matching_structure("# Skill\nShort", "# Skill\nLonger wording")
  print("ok version and compression-structure checks")


def check_archive(archive: Path, errors: list[str]) -> None:
  """Check the zip carries exactly the shipped bytes, and no refs."""
  if not archive.is_file():
    errors.append(f"{archive}: missing archive")
    return

  expected = {
    f"gpt-plugins/{path.relative_to(PLUGIN).as_posix()}": path
    for path in shipped_paths()
  }

  with zipfile.ZipFile(archive) as opened:
    members = [name for name in opened.namelist() if not name.endswith("/")]
    listed = set(members)

    if listed != set(expected):
      missing = sorted(set(expected) - listed)
      extra = sorted(listed - set(expected))
      errors.append(
        f"{archive.name}: entries differ from the collection: missing={missing} extra={extra}"
      )

    for name in sorted(listed & set(expected)):
      if opened.read(name) != expected[name].read_bytes():
        errors.append(
          f"{archive.name}: {name} differs from {expected[name].relative_to(ROOT)}"
        )


def main() -> int:
  parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
  parser.add_argument(
    "--schema",
    default=SCHEMA_URL,
    help="Canonical schema URL, or a local copy for offline runs",
  )
  parser.add_argument("--archive", help="Packaged zip to verify against the collection")
  parser.add_argument(
    "--base-manifest",
    help="Require plugin.json version greater than this base manifest",
  )
  parser.add_argument(
    "--self-check",
    action="store_true",
    help="Run version-parser assertions and exit",
  )
  arguments = parser.parse_args()

  if arguments.self_check:
    run_self_check()
    return 0

  errors: list[str] = []

  check_tree(errors)
  check_collections(errors)
  check_manifest(load_schema(arguments.schema, errors), errors)

  if arguments.base_manifest:
    check_version_bump(Path(arguments.base_manifest), errors)

  if arguments.archive:
    check_archive(Path(arguments.archive), errors)

  if errors:
    for error in errors:
      print(error, file=sys.stderr)

    print(f"gpt-plugins validation failed: {len(errors)} problems", file=sys.stderr)
    return 1

  scope = f"manifest against the canonical schema, refs structure, and all {len(EXPECTED_SKILLS)} skills"

  if arguments.base_manifest:
    scope += ", plus a version bump against the base manifest"

  if arguments.archive:
    scope += f", plus the {Path(arguments.archive).name} listing"

  print(f"gpt-plugins validation passed: {scope}.")
  return 0


if __name__ == "__main__":
  sys.exit(main())
