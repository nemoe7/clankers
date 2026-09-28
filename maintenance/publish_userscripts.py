"""Reconcile the userscripts directory with a secret Gist (GitHub Actions)."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

DESCRIPTION = "clankers-userscripts"
GIST_ID_VARIABLE = "USERSCRIPTS_GIST_ID"


def collect_sources(workspace: Path) -> dict[str, str]:
  """Read top-level userscript files by their original names."""
  directory = workspace / "userscripts"
  if not directory.is_dir():
    raise FileNotFoundError(f"Userscripts directory missing: {directory}")
  desired = {}
  for path in sorted(directory.iterdir()):
    if path.is_symlink() or not path.is_file() or not path.name.endswith(".user.js"):
      continue
    content = path.read_text(encoding="utf-8")
    if not content:
      raise ValueError(
        f"Gists cannot store an empty source: {path.relative_to(workspace)}"
      )
    desired[path.name] = content
  return desired


def api(method: str, endpoint: str, payload: dict | None = None) -> dict | None:
  """Send JSON on stdin without shell interpolation."""
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
  command = ["gh", "variable", action, GIST_ID_VARIABLE, "--repo", repo]
  if action == "set":
    command += ["--body", value or ""]
  result = subprocess.run(command, capture_output=True, text=True, check=False)
  if result.returncode:
    raise RuntimeError(
      f"gh variable {action} {GIST_ID_VARIABLE} failed: {result.stderr.strip()}"
    )


def reconcile(
  workspace: Path,
  gist_id: str,
  repo: str,
  *,
  call=api,
  store_id=variable,
) -> str | None:
  desired = collect_sources(workspace)
  if not gist_id:
    if not desired:
      print("No userscripts to publish; no Gist to create")
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
      try:
        call("DELETE", f"gists/{new_id}")
      except Exception as cleanup_error:
        print(
          f"Could not remove unrecorded Gist {new_id}: {cleanup_error}", file=sys.stderr
        )
      raise
    print(f"Created secret Gist {new_id} with {len(desired)} userscripts")
    return new_id

  if not re.fullmatch(r"[0-9a-fA-F]{1,80}", gist_id):
    raise ValueError(f"{GIST_ID_VARIABLE} must be a hexadecimal Gist ID")
  existing = call("GET", f"gists/{gist_id}")
  if (
    not isinstance(existing, dict)
    or existing.get("public") is not False
    or existing.get("description") != DESCRIPTION
    or existing.get("truncated") is True
    or not isinstance(existing.get("files"), dict)
  ):
    raise ValueError(
      f"{GIST_ID_VARIABLE} must refer to an untruncated secret Gist described {DESCRIPTION}"
    )
  old_files = existing["files"]
  if not desired:
    call("DELETE", f"gists/{gist_id}")
    store_id(repo, "delete")
    print(f"Removed empty Gist {gist_id} and {GIST_ID_VARIABLE}")
    return None
  changes = {
    name: {"content": content}
    for name, content in desired.items()
    if name not in old_files
    or old_files[name].get("truncated")
    or old_files[name].get("content") != content
  }
  deleted = sorted(set(old_files) - set(desired))
  changes.update({name: None for name in deleted})
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
  if set(verified_files) != set(desired):
    raise RuntimeError("Gist verification failed: file set does not match userscripts")
  for name, content in desired.items():
    if (
      verified_files.get(name, {}).get("truncated")
      or verified_files.get(name, {}).get("content") != content
    ):
      raise RuntimeError(f"Gist verification failed: content mismatch for {name}")
  print(
    f"Reconciled Gist {gist_id}: {len(added)} added, {len(updated)} updated, "
    f"{len(deleted)} deleted; verification passed"
  )
  return gist_id


def main() -> int:
  if not os.environ.get("GH_TOKEN"):
    raise ValueError(
      "Configure GIST_TOKEN with Gists and repository Variables write access"
    )
  repo = os.environ.get("GITHUB_REPOSITORY", "")
  if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
    raise ValueError("GITHUB_REPOSITORY is required")
  workspace = Path(os.environ.get("GITHUB_WORKSPACE", ".")).resolve()
  reconcile(workspace, os.environ.get(GIST_ID_VARIABLE, "").strip(), repo)
  return 0


if __name__ == "__main__":
  try:
    sys.exit(main())
  except (OSError, RuntimeError, ValueError) as error:
    print(f"Userscripts Gist sync failed: {error}", file=sys.stderr)
    sys.exit(1)
