#!/usr/bin/env python3
"""Helper for agents to check steering file"""

import os
import pathlib

STEERING_FILE = os.environ.get("STEERING_FILE", "reports/STEERING.md")


def check_steering():
  p = pathlib.Path(STEERING_FILE)
  if not p.exists():
    return ""
  try:
    content = p.read_text(encoding="utf-8")
    # Extract after Current Notes
    if "## Current Notes:" in content:
      notes = content.split("## Current Notes:")[-1].strip()
    else:
      notes = content.strip()
    return notes
  except Exception as e:
    print(f"Check failed: {e}")
    return ""


if __name__ == "__main__":
  notes = check_steering()
  print("=== STEERING ===")
  print(notes[-2000:])
  print("=== END ===")
  up = notes.upper()
  if "STOP:" in up:
    print("🚨 STOP detected")
  if "PRIORITY:" in up:
    print("⭐ PRIORITY detected")
