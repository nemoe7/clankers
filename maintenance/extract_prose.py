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


def prose(path: Path) -> str:
  """Collect Python comments and docstrings from one file."""
  return python_prose(path.read_text(encoding="utf-8"))


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
  for token in tokenize.generate_tokens(io.StringIO(source).readline):
    if token.type == tokenize.COMMENT:
      text = token.string.lstrip("# ").strip()
      if text:
        sections.append(text)
  return sections


def joined_comments(comments: list[str]) -> str:
  """Join nonempty comment lines for callers that need one text value."""
  return "\n".join(
    line.strip()
    for comment in comments
    for line in comment.splitlines()
    if line.strip()
  )


def python_prose(source: str) -> str:
  """Collect Python comments and docstrings from source text."""
  return joined_comments(python_sections(source))


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


def slash_sections(source: str, skip_metadata: bool = False) -> list[str]:
  """Collect slash and block comments without string contents."""
  comments: list[str] = []
  in_metadata = False
  state = "code"
  quote = ""
  buffer = ""
  index = 0

  def add_comment(text: str) -> None:
    nonlocal in_metadata
    clean = "\n".join(
      line.strip().lstrip("*").strip() for line in text.splitlines()
    ).strip()
    if skip_metadata and clean == USERSCRIPT_HEADER_START:
      in_metadata = True
      return
    if skip_metadata and clean == USERSCRIPT_HEADER_END:
      in_metadata = False
      return
    if clean and not in_metadata:
      comments.append(clean)

  while index < len(source):
    char = source[index]
    next_char = source[index + 1] if index + 1 < len(source) else ""
    if state == "string":
      if char == "\\":
        index += 2
        continue
      if char == quote:
        state = "code"
      index += 1
      continue
    if state == "line-comment":
      if char == "\n":
        add_comment(buffer)
        buffer = ""
        state = "code"
      else:
        buffer += char
      index += 1
      continue
    if state == "block-comment":
      if char == "*" and next_char == "/":
        add_comment(buffer)
        buffer = ""
        state = "code"
        index += 2
        continue
      buffer += char
      index += 1
      continue
    if char in "'\"`":
      state = "string"
      quote = char
      index += 1
      continue
    if char == "/" and next_char == "/":
      state = "line-comment"
      index += 2
      continue
    if char == "/" and next_char == "*":
      state = "block-comment"
      index += 2
      continue
    index += 1
  if state == "line-comment":
    add_comment(buffer)
  return comments


def slash_prose(source: str, skip_metadata: bool = False) -> str:
  """Collect slash and block comments as one text value."""
  return joined_comments(slash_sections(source, skip_metadata))


def hash_sections(source: str, suffix: str) -> list[str]:
  """Collect hash and INI semicolon comments outside quoted strings."""
  comments: list[str] = []
  for line in source.splitlines():
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
        text = line[index + 1 :].strip()
        if text:
          comments.append(text)
        break
  return comments


def hash_prose(source: str, suffix: str) -> str:
  """Collect hash and INI semicolon comments as one text value."""
  return joined_comments(hash_sections(source, suffix))


def html_sections(source: str) -> list[str]:
  """Collect HTML and XML comment blocks."""
  comments: list[str] = []
  start = 0
  while True:
    start = source.find("<!--", start)
    if start < 0:
      break
    end = source.find("-->", start + 4)
    if end < 0:
      break
    text = source[start + 4 : end].strip()
    if text:
      comments.append(text)
    start = end + 3
  return comments


def html_prose(source: str) -> str:
  """Collect HTML and XML comment blocks as one text value."""
  return joined_comments(html_sections(source))


def batch_sections(source: str) -> list[str]:
  """Collect batch REM and double-colon comments."""
  comments: list[str] = []
  for line in source.splitlines():
    stripped = line.lstrip()
    if stripped.startswith("@"):
      stripped = stripped[1:].lstrip()
    upper = stripped.upper()
    if upper == "REM" or upper.startswith("REM "):
      text = stripped[3:].lstrip()
      if text:
        comments.append(text)
    elif stripped.startswith("::"):
      text = stripped[2:].strip()
      if text:
        comments.append(text)
  return comments


def batch_prose(source: str) -> str:
  """Collect batch REM and double-colon comments as one text value."""
  return joined_comments(batch_sections(source))


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
  if path.suffix in JAVASCRIPT_SUFFIXES:
    return [
      text
      for text, _, _ in javascript_comments(
        source, path.name.endswith(USERSCRIPT_SUFFIX)
      )
      if text
    ]
  if path.suffix in SLASH_SUFFIXES:
    return slash_sections(source)
  if path.suffix in HTML_SUFFIXES:
    return html_sections(source)
  if path.suffix in HASH_SUFFIXES or path.name in SPECIAL_CODE_NAMES:
    return hash_sections(source, path.suffix)
  if path.suffix == ".bat":
    return batch_sections(source)
  return []


def source_prose(path: Path, source: str) -> str:
  """Collect ordinary comments and docstrings as one text value."""
  return joined_comments(source_sections(path, source))


def userscript_prose(source: str) -> str:
  """Collect non-metadata comments from one userscript source."""
  return joined_comments(
    [text for text, _, _ in javascript_comments(source, True) if text]
  )


def slash_comment_lines(source: str, skip_metadata: bool = False) -> set[int]:
  """Collect physical lines that hold slash or block comments."""
  lines: set[int] = set()
  in_metadata = False
  state = "code"
  quote = ""
  buffer = ""
  line = 1
  start_line = 1
  index = 0

  while index < len(source):
    char = source[index]
    next_char = source[index + 1] if index + 1 < len(source) else ""
    if state == "string":
      if char == "\\":
        index += 2
        continue
      if char == quote:
        state = "code"
      if char == "\n":
        line += 1
      index += 1
      continue
    if state == "line-comment":
      if char == "\n":
        text = buffer.strip()
        if skip_metadata and text == USERSCRIPT_HEADER_START:
          in_metadata = True
        elif skip_metadata and text == USERSCRIPT_HEADER_END:
          in_metadata = False
        elif not in_metadata:
          lines.add(start_line)
        buffer = ""
        state = "code"
        line += 1
      else:
        buffer += char
      index += 1
      continue
    if state == "block-comment":
      lines.add(line)
      if char == "*" and next_char == "/":
        state = "code"
        index += 2
        continue
      if char == "\n":
        line += 1
      index += 1
      continue
    if char in "'\"`":
      state = "string"
      quote = char
    elif char == "/" and next_char == "/":
      state = "line-comment"
      start_line = line
      buffer = ""
      index += 1
    elif char == "/" and next_char == "*":
      state = "block-comment"
      lines.add(line)
      index += 1
    elif char == "\n":
      line += 1
    index += 1

  if state == "line-comment":
    text = buffer.strip()
    if (
      not (skip_metadata and text in {USERSCRIPT_HEADER_START, USERSCRIPT_HEADER_END})
      and not in_metadata
    ):
      lines.add(start_line)
  return lines


def hash_comment_lines(source: str, suffix: str) -> set[int]:
  """Collect physical lines that hold hash or INI comments."""
  comments: set[int] = set()
  for number, line in enumerate(source.splitlines(), start=1):
    if line.startswith("#!"):
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
      starts_hash = char == "#" and (
        suffix == ".toml" or index == 0 or line[index - 1].isspace()
      )
      starts_ini = (
        suffix == ".ini" and char == ";" and (index == 0 or line[index - 1].isspace())
      )
      if starts_hash or starts_ini:
        comments.add(number)
        break
  return comments


def html_comment_lines(source: str) -> set[int]:
  """Collect physical lines that hold HTML or XML comments."""
  lines: set[int] = set()
  start = 0
  while True:
    start = source.find("<!--", start)
    if start < 0:
      return lines
    end = source.find("-->", start + 4)
    if end < 0:
      return lines
    first = source.count("\n", 0, start) + 1
    last = source.count("\n", 0, end) + 1
    lines.update(range(first, last + 1))
    start = end + 3


def batch_comment_lines(source: str) -> set[int]:
  """Collect physical lines that hold batch comments."""
  comments: set[int] = set()
  for number, line in enumerate(source.splitlines(), start=1):
    stripped = line.lstrip()
    if stripped.startswith("@"):
      stripped = stripped[1:].lstrip()
    upper = stripped.upper()
    if upper == "REM" or upper.startswith("REM ") or stripped.startswith("::"):
      comments.add(number)
  return comments


def comment_lines(path: Path, source: str) -> set[int]:
  """Collect physical lines that hold ordinary code comments."""
  if path.suffix == ".py":
    return {
      token.start[0]
      for token in tokenize.generate_tokens(io.StringIO(source).readline)
      if token.type == tokenize.COMMENT and not token.string.startswith("#!")
    }
  if path.suffix in JAVASCRIPT_SUFFIXES:
    return {
      line
      for _, first, last in javascript_comments(
        source, path.name.endswith(USERSCRIPT_SUFFIX)
      )
      for line in range(first, last + 1)
    }
  if path.suffix in SLASH_SUFFIXES:
    return slash_comment_lines(source)
  if path.suffix in HTML_SUFFIXES:
    return html_comment_lines(source)
  if path.suffix in HASH_SUFFIXES or path.name in SPECIAL_CODE_NAMES:
    return hash_comment_lines(source, path.suffix)
  if path.suffix == ".bat":
    return batch_comment_lines(source)
  return set()


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
