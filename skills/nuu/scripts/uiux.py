"""Compatibility shim re-exporting nuu."""

import sys

import nuu as _nuu
from nuu import *
from nuu import main

__all__ = [name for name in dir(_nuu) if not name.startswith("_")]

if __name__ == "__main__":
  for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
      stream.reconfigure(encoding="utf-8", errors="replace")
  raise SystemExit(main())
