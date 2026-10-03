"""Launcher for the arena-proxy backend.

Run it from this directory, or copy the whole `scripts/` folder:

  python3 server.py --generate-key
  ARENA_PROXY_KEY=<key> GITHUB_TOKEN=<token> python3 server.py --port 8787
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from arena_proxy.core import main

if __name__ == "__main__":
  raise SystemExit(main())
