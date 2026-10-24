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
import tempfile
import urllib.request
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import check

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "gpt-plugins"
MANIFEST = PLUGIN / "plugin.json"
ASSETS = PLUGIN / "assets"
# The collection README documents the layout for a human reader, so the tree allows it
# and shipped_paths() leaves it out of the archive.
README = PLUGIN / "README.md"
REFS = PLUGIN / "refs" / "skills"
SHIPPED = PLUGIN / "skills"
PLUGIN_NAME = "gpt-plugins"
ICON_ARCHIVE_PATH = "assets/icon.svg"
ICON_MANIFEST_REF = "./assets/icon.svg"
LOCAL_SKILLS = (
  "gpt-quirks",
  "gpt-handoff",
  "gpt-planning",
  "gpt-github",
  "gpt-display",
  "gpt-question",
)
MOUNTED_SKILLS = {
  "nemoizer": (ROOT / "skills" / "refs" / "nemoizer", ROOT / "skills" / "nemoizer"),
}
EXPECTED_SKILLS = (*LOCAL_SKILLS, *MOUNTED_SKILLS)
SCHEMA_URL = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
FENCED_CODE_BLOCK = re.compile(
  r"(?ms)^(?: {0,3})(?:(?P<ticks>`{3,})(?!`)|(?P<tildes>~{3,})(?!~))[^\n]*\n"
  r".*?^(?: {0,3})(?:(?P=ticks)`*|(?P=tildes)~*)[ \t]*$"
)


DEPENDENCY_NOTES = {
  "gpt-handoff": "References gpt-planning and Ponytail. Neither dependency is included.",
  "gpt-planning": "References gpt-handoff. That skill is not included.",
  "gpt-github": "Uses GitHub tools from the host. No GitHub tools are included.",
  "gpt-display": "Uses rendering and file features from the host. No host features are included.",
  "gpt-question": "Uses interactive form features from the host. No host features are included.",
  "gpt-quirks": "Uses file references from the host. No host tools are included.",
  "nemoizer": "Includes Python prose and test linter scripts under scripts/.",
}

SKILL_INTERFACES = {
  "gpt-quirks": {
    "displayName": "GPT Quirks",
    "shortDescription": "Verified GPT tool quirks",
    "brandColor": "#D97706",
  },
  "gpt-handoff": {
    "displayName": "GPT Handoff",
    "shortDescription": "New-work handoffs and audits",
    "brandColor": "#2563EB",
  },
  "gpt-planning": {
    "displayName": "GPT Planning",
    "shortDescription": "Requirements and completion",
    "brandColor": "#059669",
  },
  "gpt-github": {
    "displayName": "GPT GitHub",
    "shortDescription": "Git and GitHub workflow rules",
    "brandColor": "#7C3AED",
  },
  "gpt-display": {
    "displayName": "GPT Display",
    "shortDescription": "Supported response formats",
    "brandColor": "#0284C7",
  },
  "gpt-question": {
    "displayName": "GPT Question",
    "shortDescription": "Interactive question forms",
    "brandColor": "#DB2777",
  },
  "nemoizer": {
    "displayName": "Nemoizer",  # nonemo: NMO100
    "shortDescription": "STE prose and test linter",
    "brandColor": "#4F46E5",
  },
}
HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


def skill_openai_yaml(name: str) -> bytes:
  """Build the skills/<name>/agents/openai.yaml metadata for ChatGPT."""
  info = SKILL_INTERFACES[name]
  lines = (
    "interface:",
    f'  display_name: "{info["displayName"]}"',
    f'  short_description: "{info["shortDescription"]}"',
    f'  icon_small: "{ICON_MANIFEST_REF}"',
    f'  icon_large: "{ICON_MANIFEST_REF}"',
    f'  brand_color: "{info["brandColor"]}"',
  )
  return ("\n".join(lines) + "\n").encode("utf-8")


def skill_roots(name: str) -> tuple[Path, Path]:
  """Return the (refs, shipped) directories for a collection skill."""
  return MOUNTED_SKILLS.get(name, (REFS / name, SHIPPED / name))


def shipped_paths() -> list[Path]:
  """Return the collection files the archive carries, in a stable order."""
  return list(archive_members().values())


def archive_members() -> dict[str, Path]:
  """Return archive-root paths and their source files."""
  members: dict[str, Path] = {
    "plugin.json": MANIFEST,
    ICON_ARCHIVE_PATH: ASSETS / f"{PLUGIN_NAME}.svg",
  }

  for name in EXPECTED_SKILLS:
    _, ship_dir = skill_roots(name)
    members[f"skills/{name}/SKILL.md"] = ship_dir / "SKILL.md"
    members[f"skills/{name}/{ICON_ARCHIVE_PATH}"] = ASSETS / f"{name}.svg"

    # A skill may split detail into references/ or scripts/ so a reader loads only the file it needs.
    for sub in ("references", "scripts"):
      folder = ship_dir / sub
      if not folder.is_dir():
        continue
      for item in sorted(folder.rglob("*")):
        if (
          item.is_file()
          and "__pycache__" not in item.parts
          and not item.name.startswith("test_")
        ):
          rel = item.relative_to(ship_dir).as_posix()
          members[f"skills/{name}/{rel}"] = item

  return members


def archive_contents(skill: str | None = None) -> dict[str, bytes]:
  """Return complete archive payloads without changing the shipped skill files."""
  if skill is None:
    contents = {name: source.read_bytes() for name, source in archive_members().items()}
    for name in EXPECTED_SKILLS:
      contents[f"skills/{name}/agents/openai.yaml"] = skill_openai_yaml(name)
    return contents
  if skill not in EXPECTED_SKILLS:
    raise ValueError(f"Unknown skill: {skill}")
  manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
  _, ship_dir = skill_roots(skill)
  metadata, _ = check.parse_frontmatter(
    (ship_dir / "SKILL.md").read_text(encoding="utf-8")
  )
  info = SKILL_INTERFACES[skill]
  manifest.update(name=skill, description=metadata["description"])
  manifest["extensions"]["com.openai"]["interface"].update(
    displayName=info["displayName"],
    shortDescription=info["shortDescription"],
    longDescription=metadata["description"],
    brandColor=info["brandColor"],
  )
  contents = {
    name: source.read_bytes()
    for name, source in archive_members().items()
    if name.startswith(f"skills/{skill}/")
  }
  contents[f"skills/{skill}/agents/openai.yaml"] = skill_openai_yaml(skill)
  contents[ICON_ARCHIVE_PATH] = (ASSETS / f"{skill}.svg").read_bytes()
  contents["plugin.json"] = (json.dumps(manifest, indent=2) + "\n").encode()
  notes = (
    f"# {skill}\n\nVersion: {manifest['version']}.\n\n"
    f"{DEPENDENCY_NOTES[skill]}\n\n"
    "The host supplies tools and interface features. This ZIP does not install them. "
    "Archive checks do not prove ChatGPT import support.\n"
  )
  contents["README.md"] = notes.encode()
  return contents


def package_archives(directory: Path) -> dict[str, Path]:
  """Build the collection and each single-skill plugin once."""
  directory.mkdir(parents=True, exist_ok=True)
  archives = {}
  for skill in (None, *EXPECTED_SKILLS):
    name = skill or PLUGIN_NAME
    archive = directory / f"{name}.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as opened:
      for member, contents in archive_contents(skill).items():
        opened.writestr(member, contents)
    archives[name] = archive
  return archives


def check_archives(directory: Path, errors: list[str]) -> None:
  """Check all release assets, including their names and complete payloads."""
  expected = {f"{name}.zip" for name in (PLUGIN_NAME, *EXPECTED_SKILLS)}
  found = {
    path.name
    for path in directory.glob("*.zip")
    if path.name in expected or path.name.startswith("gpt-")
  }
  if found != expected:
    errors.append(
      f"{directory}: archive set differs: missing={sorted(expected - found)} extra={sorted(found - expected)}"
    )
  for skill in (None, *EXPECTED_SKILLS):
    check_archive(directory / f"{skill or PLUGIN_NAME}.zip", errors, skill=skill)


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


def check_openai_interface(label: str, manifest: dict, errors: list[str]) -> None:
  """Check the OpenAI client extension interface fields required for ChatGPT."""
  ext = manifest.get("extensions")
  openai_ext = ext.get("com.openai") if isinstance(ext, dict) else None
  interface = openai_ext.get("interface") if isinstance(openai_ext, dict) else None
  if not isinstance(interface, dict):
    errors.append(f"{label}: missing extensions.com.openai.interface object")
    return
  limits = (
    ("displayName", 1, 30),
    ("shortDescription", 1, 30),
    ("longDescription", 1, 4000),
    ("developerName", 1, 80),
    ("category", 1, 80),
  )
  for field, low, high in limits:
    value = interface.get(field)
    if not isinstance(value, str) or not (low <= len(value.strip()) <= high):
      errors.append(f"{label}: interface.{field} must be {low}..{high} characters")
  brand = interface.get("brandColor")
  if not isinstance(brand, str) or not HEX_COLOR_RE.fullmatch(brand):
    errors.append(f"{label}: interface.brandColor must match #RRGGBB")
  for icon_key in ("logo", "composerIcon"):
    if interface.get(icon_key) != ICON_MANIFEST_REF:
      errors.append(f"{label}: interface.{icon_key} must equal {ICON_MANIFEST_REF!r}")


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

  check_openai_interface("gpt-plugins/plugin.json", manifest, errors)

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

  # A skill can include a references folder.
  # Shipped_paths() and check_references() account for its files. This check needs no entry list.


def check_collections(errors: list[str]) -> None:
  """Check both trees hold exactly the expected skills, and that they agree."""
  for root in (REFS, SHIPPED):
    label = root.relative_to(ROOT)

    if not root.is_dir():
      errors.append(f"{label}: missing directory")
      continue

    found = sorted(item.name for item in root.iterdir())

    if found != sorted(LOCAL_SKILLS):
      errors.append(f"{label}: skills are {found}, expected {sorted(LOCAL_SKILLS)}")

  for name in EXPECTED_SKILLS:
    ref_dir, ship_dir = skill_roots(name)
    check_skill(ref_dir.parent, name, errors)
    check_skill(ship_dir.parent, name, errors)

    source = ref_dir / "SKILL.md"
    copy = ship_dir / "SKILL.md"

    if not source.is_file() or not copy.is_file():
      continue

    ref_text = source.read_text(encoding="utf-8")
    live_text = copy.read_text(encoding="utf-8")
    if not matching_structure(
      ref_text, live_text, require_headings=name not in MOUNTED_SKILLS
    ):
      errors.append(
        f"{copy.relative_to(ROOT)}: headings differ or compressed copy exceeds refs size"
      )


def matching_structure(
  reference: str, live: str, *, require_headings: bool = True
) -> bool:
  headings_match = not require_headings or (
    re.findall(r"^#+ .+$", reference, re.MULTILINE)
    == re.findall(r"^#+ .+$", live, re.MULTILINE)
  )
  return headings_match and len(live.encode()) <= len(reference.encode())


def fenced_code_blocks(text: str) -> list[str]:
  """Return complete Markdown code fences in their source order."""
  return [match.group(0) for match in FENCED_CODE_BLOCK.finditer(text)]


def matching_reference(reference: str, live: str) -> bool:
  """True when a prose squash leaves every fenced code block unchanged."""
  return fenced_code_blocks(reference) == fenced_code_blocks(live)


def reference_files(root: Path, name: str) -> list[Path]:
  """Return the skill's references files, relative to its directory."""
  return sorted(
    item.relative_to(root / name)
    for item in (root / name / "references").rglob("*")
    if item.is_file()
  )


def check_references(errors: list[str]) -> None:
  """Require matching reference paths and unchanged fenced Markdown code blocks."""
  for name in EXPECTED_SKILLS:
    ref_dir, ship_dir = skill_roots(name)
    source = ref_dir / "references"
    copy = ship_dir / "references"

    if not source.is_dir() and not copy.is_dir():
      continue

    if source.is_dir() != copy.is_dir():
      present = source if source.is_dir() else copy
      errors.append(f"{present.relative_to(ROOT)}: only one tree has references/")
      continue

    ref_files = reference_files(ref_dir.parent, name)
    copy_files = reference_files(ship_dir.parent, name)

    if ref_files != copy_files:
      errors.append(f"{name}: references files differ between the two trees")
      continue

    for item in ref_files:
      source_path = ref_dir / item
      copy_path = ship_dir / item
      left = source_path.read_bytes()
      right = copy_path.read_bytes()
      same = (
        matching_reference(left.decode("utf-8"), right.decode("utf-8"))
        if item.suffix == ".md"
        else left == right
      )

      if not same:
        reason = (
          "fenced code blocks differ from refs"
          if item.suffix == ".md"
          else "differs from refs"
        )
        errors.append(f"{copy_path.relative_to(ROOT)}: {reason}")


def check_tree(errors: list[str]) -> None:
  """Reject any collection file the manifest, refs and shipped skills do not account for."""
  if not PLUGIN.is_dir():
    errors.append("gpt-plugins/ is missing")
    return

  allowed = (MANIFEST, README, ASSETS, REFS, SHIPPED)
  stray = []

  for path in sorted(PLUGIN.rglob("*")):
    if path.is_dir():
      continue

    if not any(path == item or item in path.parents for item in allowed):
      stray.append(str(path.relative_to(ROOT)))

  if stray:
    errors.append(f"gpt-plugins/: unexpected files: {stray}")

  expected_icons = sorted(f"{name}.svg" for name in (PLUGIN_NAME, *EXPECTED_SKILLS))
  found_icons = (
    sorted(p.name for p in ASSETS.iterdir() if p.is_file()) if ASSETS.is_dir() else []
  )
  if found_icons != expected_icons:
    errors.append(
      f"gpt-plugins/assets: icons are {found_icons}, expected {expected_icons}"
    )
  for icon_name in expected_icons:
    icon_path = ASSETS / icon_name
    if not icon_path.is_file():
      continue
    svg_text = icon_path.read_text(encoding="utf-8")
    if (
      'width="64"' not in svg_text
      or 'height="64"' not in svg_text
      or 'viewBox="0 0 64 64"' not in svg_text
    ):
      errors.append(f"gpt-plugins/assets/{icon_name}: expected square 64x64 SVG")


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
  assert matching_structure(
    "# Skill\n## Details\nFull wording",
    "# Skill\nShort",
    require_headings=False,
  )
  assert not matching_structure("# Skill\nShort", "# Skill\nLonger wording")
  collection_errors: list[str] = []
  check_collections(collection_errors)
  check_references(collection_errors)
  check_tree(collection_errors)
  check_manifest(None, collection_errors)
  for skill in EXPECTED_SKILLS:
    check_openai_interface(
      f"{skill}/plugin.json",
      json.loads(archive_contents(skill)["plugin.json"]),
      collection_errors,
    )
  assert not collection_errors, collection_errors
  fenced = "```jsx\nconst answer = 1;\n```"
  long_fence = "````jsx\nconst answer = 1;\n`````"
  assert fenced_code_blocks(fenced) == [fenced]
  assert fenced_code_blocks(long_fence) == [long_fence]
  assert not fenced_code_blocks("````jsx\nconst answer = 1;\n```")
  assert matching_reference(f"Full prose\n{fenced}", f"Short prose\n{fenced}")
  assert not matching_reference(fenced, "```jsx\nconst answer = 2;\n```")
  expected = archive_members()
  assert "plugin.json" in expected
  assert any(name.startswith("skills/") for name in expected)
  assert not any(name.startswith("gpt-plugins/") for name in expected)
  payloads = archive_contents()
  with tempfile.TemporaryDirectory() as directory:
    archive = Path(directory) / "gpt-plugins.zip"
    with zipfile.ZipFile(archive, "w") as opened:
      for name, data in payloads.items():
        opened.writestr(name, data)
    errors: list[str] = []
    check_archive(archive, errors)
    assert not errors, errors
    legacy = Path(directory) / "legacy-gpt-plugins.zip"
    with zipfile.ZipFile(legacy, "w") as opened:
      for name, data in payloads.items():
        opened.writestr(f"gpt-plugins/{name}", data)
    legacy_errors: list[str] = []
    check_archive(legacy, legacy_errors)
    assert legacy_errors, "a nested gpt-plugins archive passed"
  print("ok version, compression-structure, fenced-code and archive-layout checks")


def check_archive(
  archive: Path, errors: list[str], *, skill: str | None = None
) -> None:
  """Check exact payloads for the collection or a complete single-skill plugin."""
  if not archive.is_file():
    errors.append(f"{archive}: missing archive")
    return

  expected = archive_contents(skill)

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
      if opened.read(name) != expected[name]:
        errors.append(f"{archive.name}: {name} differs from its expected payload")


def main() -> int:
  parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
  parser.add_argument(
    "--schema",
    default=SCHEMA_URL,
    help="Canonical schema URL, or a local copy for offline runs",
  )
  parser.add_argument("--archive", help="Packaged zip to verify against the collection")
  parser.add_argument(
    "--skill", choices=EXPECTED_SKILLS, help="Single skill in --archive"
  )
  parser.add_argument(
    "--package-dir", type=Path, help="Build and check all plugin archives here"
  )
  parser.add_argument(
    "--archives-dir", type=Path, help="Check all downloaded plugin archives here"
  )
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
  if arguments.skill and not arguments.archive:
    parser.error("--skill requires --archive")

  if arguments.self_check:
    run_self_check()
    return 0

  errors: list[str] = []

  check_tree(errors)
  check_collections(errors)
  check_references(errors)
  schema = load_schema(arguments.schema, errors)
  check_manifest(schema, errors)
  if schema is not None and not errors:
    import jsonschema

    validator = jsonschema.Draft202012Validator(schema)
    for skill in EXPECTED_SKILLS:
      manifest = json.loads(archive_contents(skill)["plugin.json"])
      check_openai_interface(f"{skill}/plugin.json", manifest, errors)
      for problem in validator.iter_errors(manifest):
        errors.append(f"{skill}/plugin.json: schema violation: {problem.message}")

  if arguments.base_manifest:
    check_version_bump(Path(arguments.base_manifest), errors)

  if arguments.archive:
    check_archive(Path(arguments.archive), errors, skill=arguments.skill)

  if arguments.package_dir and not errors:
    package_archives(arguments.package_dir)
    check_archives(arguments.package_dir, errors)

  if arguments.archives_dir:
    check_archives(arguments.archives_dir, errors)

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

  if arguments.package_dir or arguments.archives_dir:
    scope += ", plus all collection and single-skill archives"

  print(f"gpt-plugins validation passed: {scope}.")
  return 0


if __name__ == "__main__":
  sys.exit(main())
