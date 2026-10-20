"""Extract code comments and docstrings as JSON groups keyed by file."""

import argparse
import ast
import io
import json
import subprocess
import tokenize
from functools import lru_cache
from pathlib import Path

USERSCRIPT_SUFFIX = ".user.js"
USERSCRIPT_HEADER_START = "==UserScript=="
USERSCRIPT_HEADER_END = "==/UserScript=="
METADATA_PROSE_KEYS = {"name", "description"}
COMMENT_SUFFIXES = {
  ".bat",
  ".cjs",
  ".css",
  ".html",
  ".ini",
  ".js",
  ".jsonc",
  ".py",
  ".sh",
  ".svg",
  ".toml",
  ".yml",
}
JAVASCRIPT_SUFFIXES = {".cjs", ".js"}
SLASH_SUFFIXES = {".css", ".jsonc"}
HTML_SUFFIXES = {".html", ".svg"}
HASH_SUFFIXES = {".ini", ".sh", ".toml", ".yml"}
SPECIAL_CODE_NAMES = {"Dockerfile", "arena-preview"}
AGENT_SKILLS = Path(".agents/skills")
FIRST_PARTY_AGENT_SKILL = AGENT_SKILLS / "arena-skill"
VENDORED_PARTS = (
  Path(".agents/skills/asd-ste100"),
  Path("skills/refs/arena-skill/assets/markdown-it.min.js"),
  Path("skills/arena-skill/assets/markdown-it.min.js"),
  Path(".agents/skills/arena-skill/assets/markdown-it.min.js"),
)


def python_comments(source: str) -> list[tuple[str, int, int]]:
  """Collect Python comments with their source line spans."""
  comments: list[tuple[str, int, int]] = []
  for token in tokenize.generate_tokens(io.StringIO(source).readline):
    if token.type == tokenize.COMMENT:
      comments.append(
        (token.string.lstrip("# ").strip(), token.start[0], token.start[0])
      )
  return comments


def python_sections(source: str) -> list[str]:
  """Collect each Python comment and docstring as one prose section."""
  sections: list[str] = []
  for node in ast.walk(ast.parse(source)):
    if isinstance(
      node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
    ):
      body = node.body
      first = body[0] if body else None
      if (
        isinstance(first, ast.Expr)
        and isinstance(first.value, ast.Constant)
        and isinstance(first.value.value, str)
      ):
        text = first.value.value.strip()
        if text:
          sections.append(text)
  sections.extend(text for text, _, _ in python_comments(source) if text)
  return sections


@lru_cache(maxsize=128)
def javascript_comments(
  source: str, skip_metadata: bool = False
) -> tuple[tuple[str, int, int], ...]:
  """Collect JavaScript comments and their source lines with the parser."""
  result = subprocess.run(
    ["node", str(Path(__file__).with_name("javascript-comments.cjs"))],
    input=source,
    capture_output=True,
    text=True,
    check=True,
  )
  comments = []
  in_metadata = False
  for text, first, last in json.loads(result.stdout):
    clean = "\n".join(
      line.strip().lstrip("*").strip() for line in text.splitlines()
    ).strip()
    if skip_metadata and clean == USERSCRIPT_HEADER_START:
      in_metadata = True
    elif skip_metadata and clean == USERSCRIPT_HEADER_END:
      in_metadata = False
    elif not in_metadata:
      comments.append((clean, first, last))
  return tuple(comments)


def clean_comment(text: str) -> str:
  """Strip line decoration and outer whitespace from one comment block."""
  return "\n".join(
    line.strip().lstrip("*").strip() for line in text.splitlines()
  ).strip()


def slash_comments(source: str) -> list[tuple[str, int, int]]:
  """Collect slash and block comments with their source line spans."""
  comments: list[tuple[str, int, int]] = []
  state = "code"
  quote = ""
  buffer = ""
  line = 1
  start_line = 1
  index = 0

  while index < len(source):
    char = source[index]
    next_char = source[index + 1] if index + 1 < len(source) else ""
    consumed = 1
    if state == "string":
      if char == "\\":
        consumed = 2
      elif char == quote:
        state = "code"
    elif state == "line-comment":
      if char == "\n":
        comments.append((clean_comment(buffer), start_line, line))
        buffer = ""
        state = "code"
      else:
        buffer += char
    elif state == "block-comment":
      if char == "*" and next_char == "/":
        comments.append((clean_comment(buffer), start_line, line))
        buffer = ""
        state = "code"
        consumed = 2
      else:
        buffer += char
    elif char in "'\"`":
      state = "string"
      quote = char
    elif char == "/" and next_char == "/":
      state = "line-comment"
      start_line = line
      buffer = ""
      consumed = 2
    elif char == "/" and next_char == "*":
      state = "block-comment"
      start_line = line
      buffer = ""
      consumed = 2
    line += source[index : index + consumed].count("\n")
    index += consumed

  if state == "line-comment":
    comments.append((clean_comment(buffer), start_line, line))
  return comments


def hash_comments(
  source: str, suffix: str, skip_shebang: bool = False
) -> list[tuple[str, int, int]]:
  """Collect hash and INI semicolon comments with their source line spans."""
  comments: list[tuple[str, int, int]] = []
  for number, line in enumerate(source.splitlines(), start=1):
    if skip_shebang and line.startswith("#!"):
      continue
    quote = ""
    escaped = False
    for index, char in enumerate(line):
      if quote:
        if escaped:
          escaped = False
        elif char == "\\":
          escaped = True
        elif char == quote:
          quote = ""
        continue
      if char in "'\"":
        quote = char
        continue
      starts_comment = char == "#" and (
        suffix == ".toml" or index == 0 or line[index - 1].isspace()
      )
      starts_comment = starts_comment or (
        suffix == ".ini" and char == ";" and (index == 0 or line[index - 1].isspace())
      )
      if starts_comment:
        comments.append((line[index + 1 :].strip(), number, number))
        break
  return comments


def html_comments(source: str) -> list[tuple[str, int, int]]:
  """Collect HTML and XML comment blocks with their source line spans."""
  comments: list[tuple[str, int, int]] = []
  cursor = 0
  while True:
    start = source.find("<!--", cursor)
    if start < 0:
      break
    end = source.find("-->", start + 4)
    if end < 0:
      break
    first = source.count("\n", 0, start) + 1
    last = source.count("\n", 0, end) + 1
    comments.append((source[start + 4 : end].strip(), first, last))
    cursor = end + 3
  return comments


def batch_comments(source: str) -> list[tuple[str, int, int]]:
  """Collect batch REM and double-colon comments with their source line spans."""
  comments: list[tuple[str, int, int]] = []
  for number, line in enumerate(source.splitlines(), start=1):
    stripped = line.lstrip()
    if stripped.startswith("@"):
      stripped = stripped[1:].lstrip()
    upper = stripped.upper()
    if upper == "REM" or upper.startswith("REM "):
      comments.append((stripped[3:].lstrip(), number, number))
    elif stripped.startswith("::"):
      comments.append((stripped[2:].strip(), number, number))
  return comments


def span_comments(
  path: Path, source: str, skip_shebang: bool = False
) -> list[tuple[str, int, int]] | None:
  """Return the comment spans for one code path, or None when no scanner covers it."""
  if path.suffix in JAVASCRIPT_SUFFIXES:
    return list(javascript_comments(source, path.name.endswith(USERSCRIPT_SUFFIX)))
  if path.suffix in SLASH_SUFFIXES:
    return slash_comments(source)
  if path.suffix in HTML_SUFFIXES:
    return html_comments(source)
  if path.suffix in HASH_SUFFIXES or path.name in SPECIAL_CODE_NAMES:
    return hash_comments(source, path.suffix, skip_shebang)
  if path.suffix == ".bat":
    return batch_comments(source)
  return None


def userscript_metadata_sections(source: str) -> list[str]:
  """Collect prose values from required userscript metadata."""
  sections: list[str] = []
  in_metadata = False
  for line in source.splitlines():
    stripped = line.lstrip()
    if not stripped.startswith("//"):
      continue
    comment = stripped[2:].strip()
    if comment == USERSCRIPT_HEADER_START:
      in_metadata = True
      continue
    if comment == USERSCRIPT_HEADER_END:
      break
    if not in_metadata or not comment.startswith("@"):
      continue
    key, _, value = comment[1:].partition(" ")
    if key in METADATA_PROSE_KEYS and value.strip():
      sections.append(value.strip())
  return sections


def source_sections(path: Path, source: str) -> list[str]:
  """Collect ordinary comments and docstrings from one tracked code file."""
  if path.suffix == ".py":
    return python_sections(source)
  spans = span_comments(path, source)
  return [text for text, _, _ in spans if text] if spans is not None else []


def python_comment_lines(source: str) -> set[int]:
  """Collect Python comment lines beside their spans, never a shebang."""
  lines = source.splitlines()
  return {
    first
    for _, first, _ in python_comments(source)
    if not lines[first - 1].startswith("#!")
  }


def comment_lines(path: Path, source: str) -> set[int]:
  """Collect physical lines that hold ordinary code comments."""
  if path.suffix == ".py":
    return python_comment_lines(source)
  spans = span_comments(path, source, skip_shebang=True)
  return (
    {line for _, first, last in spans for line in range(first, last + 1)}
    if spans is not None
    else set()
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
