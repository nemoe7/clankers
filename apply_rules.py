import os
import shutil
from pathlib import Path

RULES = Path(__file__).parent / "rules"
BASE = Path(os.environ.get("APPLY_RULES_BASE", os.environ["USERPROFILE"]))

MAPPINGS = [
    (RULES / "AGENTS.md", BASE / ".agents" / "AGENTS.md"),
    (RULES / "CLINE.md", BASE / "Documents" / "Cline" / "Rules" / "CLINE.md"),
]

for src, dst in MAPPINGS:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    print(f"Copied {src} -> {dst}")
