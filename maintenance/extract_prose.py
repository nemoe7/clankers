"""Extract repository code prose through nemoizer's shared parser."""

import argparse
import importlib.util
import json
import subprocess
from pathlib import Path

_ENGINE = Path(__file__).resolve().parents[1] / "skills/nemoizer/scripts/prose.py"
_SPEC = importlib.util.spec_from_file_location("nemoizer_prose", _ENGINE)
_PROSE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_PROSE)

COMMENT_SUFFIXES = _PROSE.COMMENT_SUFFIXES
SPECIAL_CODE_NAMES = _PROSE.SPECIAL_CODE_NAMES
USERSCRIPT_SUFFIX = _PROSE.USERSCRIPT_SUFFIX
python_comments = _PROSE.python_comments
python_sections = _PROSE.python_sections
javascript_comments = _PROSE.javascript_comments
clean_comment = _PROSE.clean_comment
slash_comments = _PROSE.slash_comments
hash_comments = _PROSE.hash_comments
html_comments = _PROSE.html_comments
batch_comments = _PROSE.batch_comments
span_comments = _PROSE.span_comments
userscript_metadata_sections = _PROSE.userscript_metadata_sections
source_sections = _PROSE.source_sections
python_comment_lines = _PROSE.python_comment_lines
comment_lines = _PROSE.comment_lines

AGENT_SKILLS = Path(".agents/skills")
FIRST_PARTY_AGENT_SKILL = AGENT_SKILLS / "arena-skill"
VENDORED_PARTS = (
  Path(".agents/skills/asd-ste100"),
  Path("skills/refs/arena-skill/assets/markdown-it.min.js"),
  Path("skills/arena-skill/assets/markdown-it.min.js"),
  Path(".agents/skills/arena-skill/assets/markdown-it.min.js"),
)


def is_vendored(path: Path) -> bool:
  """Return whether a tracked code path belongs to vendored content."""
  if any(path.is_relative_to(part) for part in VENDORED_PARTS):
    return True
  if path.is_relative_to(AGENT_SKILLS):
    return not path.is_relative_to(FIRST_PARTY_AGENT_SKILL)
  return False


def code_targets() -> list[Path]:
  """Collect tracked files that can hold comments or docstrings."""
  result = subprocess.run(
    ["git", "ls-files"], capture_output=True, text=True, check=True
  )
  paths = [Path(item) for item in result.stdout.splitlines()]
  return [
    path
    for path in paths
    if (path.suffix in COMMENT_SUFFIXES or path.name in SPECIAL_CODE_NAMES)
    and not is_vendored(path)
  ]


def extract_files(paths=None):
  """Group extracted prose by file. Without paths, use tracked first-party code."""
  paths = code_targets() if paths is None else [Path(path) for path in paths]
  grouped = {}
  for path in paths:
    if path.suffix not in COMMENT_SUFFIXES and path.name not in SPECIAL_CODE_NAMES:
      raise ValueError(f"Unsupported code file: {path}")
    source = path.read_text(encoding="utf-8")
    sections = source_sections(path, source)
    if path.name.endswith(USERSCRIPT_SUFFIX):
      sections = userscript_metadata_sections(source) + sections
    grouped[str(path)] = sections
  return grouped


def main(argv=None):
  """Print per-file prose without executing the supplied source."""
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument(
    "paths", nargs="*", type=Path, help="Code files (default: tracked first-party code)"
  )
  args = parser.parse_args(argv)
  try:
    grouped = extract_files(args.paths or None)
  except (
    OSError,
    UnicodeError,
    SyntaxError,
    ValueError,
    subprocess.CalledProcessError,
  ) as error:
    parser.error(str(error))
  print(json.dumps(grouped, ensure_ascii=False, indent=2))
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
