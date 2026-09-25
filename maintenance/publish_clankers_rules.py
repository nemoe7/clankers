"""Reconcile eligible rules with the secret clankers-rules Gist (GitHub Actions)."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

DESCRIPTION = "clankers-rules"
EXTENSIONS = {".md", ".txt"}
NESTED_READMES = {"README.md", "README.txt"}
INDEX_NAME = "#clankers-rules.md"
INDEX_SOURCE = "README.md"
REPO_ONLY_HEADINGS = {"Install rules", "Markdown lint scope"}
_OUTSIDE = (
  "CHANGELOG",
  "apply.py",
  "apply.bat",
  "maintenance/",
  "refs/",
  "installation",
)
_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_CODE = re.compile(r"`([^`]+)`")
_RULES_PATH = re.compile(r"\brules/([A-Za-z0-9_./-]+)")


def _sections(text: str) -> dict[str, str]:
  parts = re.split(r"(?m)^## ", text)
  sections = {}
  for part in parts[1:]:
    heading, _, body = part.partition("\n")
    title = heading.strip()
    if title not in REPO_ONLY_HEADINGS:
      sections[title] = body
  return sections


def _join_names(names: list[str]) -> str:
  shown = [f"`{name}`" for name in names]
  if len(shown) < 2:
    return shown[0] if shown else ""
  if len(shown) == 2:
    return f"{shown[0]} and {shown[1]}"
  return ", ".join(shown[:-1]) + ", and " + shown[-1]


def _children(target: str, names: set[str]) -> list[str]:
  prefix = target.rstrip("/").replace("/", "-")
  return sorted(name for name in names if name.startswith(prefix + "-"))


def _gist_name(target: str) -> str:
  return target.rstrip("/").replace("/", "-")


def _rewrite_links(text: str, names: set[str]) -> str:
  def replace(match: re.Match[str]) -> str:
    target = match.group(2)
    if target.startswith("#"):
      return ""
    if target.endswith("/"):
      return _join_names(_children(target, names))
    gist = _gist_name(target)
    return f"[{gist}]({gist})" if gist in names else ""

  return _LINK.sub(replace, text)


def _rewrite_code_paths(text: str, names: set[str]) -> str:
  def replace(match: re.Match[str]) -> str:
    raw = match.group(1)
    if not raw.startswith("rules/"):
      return match.group(0)
    gist = raw.removeprefix("rules/").replace("/", "-")
    return f"`{gist}`" if gist in names else ""

  return _CODE.sub(replace, text)


def _rewrite_plain_paths(text: str, names: set[str]) -> str:
  def replace(match: re.Match[str]) -> str:
    gist = match.group(1).replace("/", "-")
    return gist if gist in names else ""

  return _RULES_PATH.sub(replace, text)


def _tidy(text: str) -> str:
  text = re.sub(r"[ \t]{2,}", " ", text)
  text = text.replace(" in .", ".")
  text = text.replace(" .", ".")
  text = re.sub(r" +([,.;])", r"\1", text)
  return text.strip()


def _cite_only_included(text: str) -> str:
  kept = []
  for sentence in re.split(r"(?<=[.!?])\s+", text.strip()):
    if any(token in sentence for token in _OUTSIDE):
      continue
    if sentence.strip():
      kept.append(sentence.strip())
  return " ".join(kept)


def _rewrite(text: str, names: set[str]) -> str:
  return _tidy(
    _cite_only_included(
      _rewrite_plain_paths(
        _rewrite_code_paths(_rewrite_links(text, names), names), names
      )
    )
  )


def _fallback(name: str) -> str:
  # wenyan/README.md is a nested README, so the gist excludes it. Keep its boundary here.
  if name.startswith("wenyan-"):
    base = name.removeprefix("wenyan-")
    return f"Experimental Wenyan form of {base}. Not authoritative."
  if name.startswith("kilo-"):
    return "Kilo mode override"
  return "Included rule file"


def _file_rows(contents: str, names: set[str]) -> list[str]:
  """One File and Purpose row per included name; the index has no How-to-use column."""
  found: dict[str, str] = {}
  for line in contents.splitlines():
    if not line.startswith("|") or line.startswith("| ---") or " | " not in line:
      continue
    cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
    if cells[0].startswith("---") or cells[0].lower().startswith("file"):
      continue
    match = _LINK.search(cells[0])
    target = match.group(2) if match else cells[0].strip("`")
    if target.endswith("/") or _gist_name(target) not in names:
      continue
    gist = _gist_name(target)
    found[gist] = _rewrite(cells[1], names)
  for name in names:
    found.setdefault(name, _fallback(name))
  return [f"| `{name}` | {found[name]} |" for name in sorted(found)]


def _activation(contents: str, names: set[str]) -> str:
  lines = []
  seen_table = False
  for line in contents.splitlines():
    if line.startswith("|"):
      seen_table = True
      continue
    if seen_table and line.strip():
      lines.append(line.strip())
  return _rewrite(" ".join(lines), names)


def _clean_matrix(section: str, names: set[str]) -> str:
  prose: list[str] = []
  table: list[str] = []
  in_table = False
  for line in section.strip().splitlines():
    if line.startswith("|"):
      in_table = True
    if in_table:
      table.append(_rewrite_code_paths(line, names))
    else:
      prose.append(line)
  intro = _rewrite(" ".join(prose), names)
  parts = [part for part in (intro, "\n".join(table).strip()) if part]
  return "\n\n".join(parts)


def gist_index(readme: str, included: dict[str, str] | set[str]) -> str:
  """Return the gist copy of rules/README.md. It lists only included files."""
  names = set(included) - {INDEX_NAME}
  sections = _sections(readme)
  rows = _file_rows(sections.get("Contents", ""), names)
  activation = _activation(sections.get("Contents", ""), names)
  matrix = _clean_matrix(sections.get("Platform difference matrix", ""), names)
  lines = [
    "# clankers-rules",
    "",
    "These files are the rules in this gist. This file is an index, not an agent rule.",
    "",
  ]
  if rows:
    lines.extend(
      [
        "## Files",
        "",
        "| File | Purpose |",
        "| --- | --- |",
        *rows,
        "",
      ]
    )
  else:
    lines.extend(["No other rule file is included.", ""])
  if activation:
    lines.extend([activation, ""])
  if matrix:
    lines.extend(["## Platform difference matrix", "", matrix, ""])
  return "\n".join(lines).rstrip() + "\n"


def collect_sources(workspace: Path) -> tuple[dict[str, str], dict[str, list[str]]]:
  """Flatten eligible filenames; skip *every* source involved in a collision."""
  rules = workspace / "rules"
  if not rules.is_dir():
    raise FileNotFoundError(f"Rules directory missing: {rules}")
  names: dict[str, list[Path]] = {}
  for path in sorted(rules.rglob("*")):
    if path.is_symlink() or not path.is_file():
      continue
    relative = path.relative_to(rules)
    if (
      relative.parts[0] == "refs"
      or path.suffix not in EXTENSIONS
      or (len(relative.parts) > 1 and relative.name in NESTED_READMES)
    ):
      continue
    name = relative.as_posix().replace("/", "-")
    names.setdefault(name, []).append(path)
  collisions = {
    name: [path.relative_to(workspace).as_posix() for path in paths]
    for name, paths in names.items()
    if len(paths) > 1
  }
  desired = {}
  readme = None
  for name, paths in names.items():
    if name in collisions:
      continue
    content = paths[0].read_text(encoding="utf-8")
    # GitHub's Gist API rejects empty content (on PATCH it can act as a deletion). Do not
    # silently skip an eligible rule or wipe its old contents: fail before touching the Gist.
    if not content:
      raise ValueError(
        f"Gists cannot store an empty source: {paths[0].relative_to(workspace)}"
      )
    if paths[0].relative_to(rules).as_posix() == INDEX_SOURCE:
      readme = content
      continue
    desired[name] = content
  if readme is not None:
    desired[INDEX_NAME] = gist_index(readme, desired)
  return desired, collisions


def api(method: str, endpoint: str, payload: dict | None = None) -> dict | None:
  """Send one JSON body through stdin, never shell interpolation or per-line gh fields."""
  command = ["gh", "api", "--method", method, endpoint]
  if payload is not None:
    command += ["--input", "-"]
  result = subprocess.run(
    command,
    input=json.dumps(payload, ensure_ascii=False) if payload is not None else None,
    text=True,
    encoding="utf-8",
    capture_output=True,
    check=False,
  )
  if result.returncode:
    raise RuntimeError(f"gh api {method} {endpoint} failed: {result.stderr.strip()}")
  return json.loads(result.stdout) if result.stdout.strip() else None


def variable(repo: str, action: str, value: str | None = None) -> None:
  command = ["gh", "variable", action, "GIST_ID", "--repo", repo]
  if action == "set":
    command += ["--body", value or ""]
  result = subprocess.run(command, capture_output=True, text=True, check=False)
  if result.returncode:
    raise RuntimeError(f"gh variable {action} GIST_ID failed: {result.stderr.strip()}")


def reconcile(
  workspace: Path,
  gist_id: str,
  repo: str,
  *,
  call=api,
  store_id=variable,
) -> str | None:
  desired, collisions = collect_sources(workspace)
  for name, paths in sorted(collisions.items()):
    print(f"Skipping flattening collision {name}: {', '.join(paths)}")
  if not gist_id:
    if not desired:
      print("No unambiguous eligible rules; no Gist to create")
      return None
    created = call(
      "POST",
      "gists",
      {
        "description": DESCRIPTION,
        "public": False,
        "files": {name: {"content": content} for name, content in desired.items()},
      },
    )
    new_id = created.get("id") if isinstance(created, dict) else None
    if not new_id or created.get("public") is not False:
      if new_id:
        call("DELETE", f"gists/{new_id}")
      raise RuntimeError("Gist creation did not confirm a secret Gist ID")
    try:
      store_id(repo, "set", new_id)
    except Exception:
      # An unrecorded Gist would cause the next run to make another one.
      try:
        call("DELETE", f"gists/{new_id}")
      except Exception as cleanup_error:
        print(
          f"Could not remove unrecorded Gist {new_id}: {cleanup_error}", file=sys.stderr
        )
      raise
    print(f"Created secret Gist {new_id}; stored GIST_ID; {len(desired)} rules")
    return new_id

  if not re.fullmatch(r"[0-9a-fA-F]{1,80}", gist_id):
    raise ValueError("GIST_ID must be a hexadecimal Gist ID")
  existing = call("GET", f"gists/{gist_id}")
  if (
    not isinstance(existing, dict)
    or existing.get("public") is not False
    or existing.get("description") != DESCRIPTION
    or existing.get("truncated") is True
    or not isinstance(existing.get("files"), dict)
  ):
    raise ValueError(
      "GIST_ID must refer to an untruncated secret Gist described clankers-rules"
    )
  old_files = existing["files"]
  changes = {
    name: {"content": content}
    for name, content in desired.items()
    if name not in old_files
    or old_files[name].get("truncated")
    or old_files[name].get("content") != content
  }
  deleted = sorted(set(old_files) - set(desired) - set(collisions))
  changes.update({name: None for name in deleted})
  if not desired and not set(collisions).intersection(old_files):
    # GitHub rejects a Gist with zero files. The authoritative empty result is no Gist,
    # so remove it and clear the ID; a later eligible rule will create a new secret Gist.
    call("DELETE", f"gists/{gist_id}")
    store_id(repo, "delete")
    print(f"Removed empty Gist {gist_id} and GIST_ID")
    return None
  added = sorted(name for name in changes if name not in old_files)
  updated = sorted(
    name for name in changes if name in old_files and changes[name] is not None
  )
  if changes:
    call("PATCH", f"gists/{gist_id}", {"files": changes})
  verified = call("GET", f"gists/{gist_id}")
  if (
    not isinstance(verified, dict)
    or verified.get("public") is not False
    or verified.get("description") != DESCRIPTION
    or not isinstance(verified.get("files"), dict)
  ):
    raise RuntimeError("Gist verification failed: invalid Gist response")
  verified_files = verified["files"]
  expected_files = set(desired) | (set(collisions) & set(old_files))
  if set(verified_files) != expected_files:
    raise RuntimeError(
      "Gist verification failed: file set does not match desired state"
    )
  for name, content in desired.items():
    if (
      verified_files.get(name, {}).get("truncated")
      or verified_files.get(name, {}).get("content") != content
    ):
      raise RuntimeError(f"Gist verification failed: content mismatch for {name}")
  for name in set(collisions) & set(old_files):
    if verified_files.get(name, {}).get("truncated"):
      raise RuntimeError(
        f"Gist verification failed: preserved file {name} is truncated"
      )
  print(
    f"Reconciled Gist {gist_id}: {len(desired)} authoritative rules, "
    f"{len(added)} added, {len(updated)} updated, {len(deleted)} deleted, "
    f"{len(collisions)} collision names preserved; verification passed"
  )
  return gist_id


def main() -> int:
  if not os.environ.get("GH_TOKEN"):
    raise ValueError(
      "Configure the GIST_TOKEN Actions secret with Gists and Variables write access"
    )
  repo = os.environ.get("GITHUB_REPOSITORY", "")
  if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
    raise ValueError("GITHUB_REPOSITORY is required")
  workspace = Path(os.environ.get("GITHUB_WORKSPACE", ".")).resolve()
  reconcile(workspace, os.environ.get("GIST_ID", "").strip(), repo)
  return 0


if __name__ == "__main__":
  try:
    sys.exit(main())
  except (OSError, RuntimeError, ValueError) as error:
    print(f"Rule Gist sync failed: {error}", file=sys.stderr)
    sys.exit(1)
