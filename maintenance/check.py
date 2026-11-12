#!/usr/bin/env python3
"""Check repo structure and maintain README measurements. See the `checks` package."""

import sys

from checks.cli import main

if __name__ == "__main__":
  sys.exit(main())
