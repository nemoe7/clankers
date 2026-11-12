"""Size measurers, one per README budget type."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple

# gpt-tokenizer ships its ranks and measures offline, and needs no cache seeding.
# Node resolves it from the real root, fixed when a test points `Repo` at a temporary tree.
NODE_CWD = Path(__file__).resolve().parents[2]
_TOKEN_COUNT_SCRIPT = """
const { encode } = require("gpt-tokenizer/encoding/o200k_base");
const fs = require("fs");
process.stdout.write(String(encode(fs.readFileSync(process.argv[1], "utf8")).length));
"""
# A file whose size or time changed between two measurements is measured again.
_token_cache: dict[tuple[str, int, int], int] = {}


def token_count(path: Path) -> int:
  stat = path.stat()
  key = (str(path), stat.st_mtime_ns, stat.st_size)

  if key not in _token_cache:
    try:
      result = subprocess.run(
        ["node", "-e", _TOKEN_COUNT_SCRIPT, str(path)],
        cwd=NODE_CWD,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
      )
    except (OSError, subprocess.CalledProcessError) as exc:
      raise RuntimeError(
        "gpt-tokenizer is required for o200k_base measurements. Install it with: npm ci"
      ) from exc

    _token_cache[key] = int(result.stdout)

  return _token_cache[key]


class Measurer(NamedTuple):
  count: Callable[[Path, str], int]
  unit: str


# Each README budget type maps to its measurer and the unit the table prints.
MEASURERS = {
  "Unicode chars": Measurer(lambda path, text: len(text), "chars"),
  "o200k_base": Measurer(lambda path, text: token_count(path), "tok"),
}
MEASURE_DEFAULT = "o200k_base"


def measurer(measure_type: str) -> Measurer:
  try:
    return MEASURERS[measure_type]
  except KeyError:
    raise ValueError(f"unsupported measurement: {measure_type}") from None


def measure(path: Path, measure_type: str) -> int:
  return measurer(measure_type).count(path, path.read_text(encoding="utf-8"))


def format_unit(measure_type: str) -> str:
  return measurer(measure_type).unit
