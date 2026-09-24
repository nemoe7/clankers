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
    desired[name] = content
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
  if changes:
    call("PATCH", f"gists/{gist_id}", {"files": changes})
  print(
    f"Reconciled Gist {gist_id}: {len(desired)} authoritative rules, "
    f"{len(deleted)} stale files removed, {len(collisions)} collision names preserved"
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
