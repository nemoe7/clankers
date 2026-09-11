import argparse
import difflib
import os
import shutil
from pathlib import Path

RULES = Path(__file__).parent
BASE = Path(os.environ.get("APPLY_RULES_BASE") or Path.home())

MAPPINGS = [
  (RULES / "AGENTS.md", BASE / ".agents" / "AGENTS.md"),
  (RULES / "CLINE.md", BASE / "Documents" / "Cline" / "Rules" / "CLINE.md"),
]

parser = argparse.ArgumentParser(description="Install agent rule files.")
parser.add_argument("--yes", "-y", action="store_true", help="Apply without prompting.")
parser.add_argument(
  "--dry-run", action="store_true", help="Preview diffs without changing anything."
)
args = parser.parse_args()

missing = [src for src, _ in MAPPINGS if not src.is_file()]

if missing:
  print(f"Missing rule sources: {', '.join(str(path) for path in missing)}")
  raise SystemExit(1)

changes = []
diffs = []
for src, dst in MAPPINGS:
  current = (
    dst.read_text(encoding="utf-8").splitlines(keepends=True) if dst.exists() else []
  )
  proposed = src.read_text(encoding="utf-8").splitlines(keepends=True)
  diff = list(
    difflib.unified_diff(
      current,
      proposed,
      fromfile=f"{dst} (current)",
      tofile=f"{dst} (proposed)",
    )
  )
  if diff:
    changes.append((src, dst))
    diffs.extend(diff)

if not diffs:
  print("Rules are already up to date.")
  raise SystemExit(0)

print("".join(diffs), end="")

if args.dry_run:
  raise SystemExit(0)

if not args.yes:
  try:
    confirmed = input("Apply these changes? [y/N] ")
  except EOFError:
    confirmed = ""

  if confirmed.lower() not in {"y", "yes"}:
    print("Aborted.")
    raise SystemExit(0)

for src, dst in changes:
  dst.parent.mkdir(parents=True, exist_ok=True)
  shutil.copy2(src, dst)
  print(f"Copied {src} -> {dst}")
