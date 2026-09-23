"""Build compact preview assets and scripts from their readable refs sources.

The readable sources live in `skills/refs/arena-preview-steering/`. Both distributed
copies carry minified JavaScript, CSS, HTML and Python, each budgeted in README.md.
Markdown compression is editorial, never part of this build.

Install the pinned npm tools with `npm ci` and the build-only Python dependency with
`python -m pip install python-minifier==3.3.0`. CI builds with Python 3.11; generated
Python must retain its parsed tree and parse as Python 3.10 before any output is written.

Usage:
  python maintenance/minify.py            # build in memory, report drift, write nothing
  python maintenance/minify.py --update   # write the minified copies

`check.py` gates each live file's size through the README table. This script reports drift,
which the budget cannot see; run it after any change to a refs asset or script.
"""

from __future__ import annotations

import argparse
import ast
import re
import subprocess
import sys
import tempfile
from importlib.metadata import version
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "skills/refs/arena-preview-steering"
TARGETS = (
  ROOT / "skills/arena-preview-steering",
  ROOT / ".agents/skills/arena-preview-steering",
)
BIN = ROOT / "node_modules/.bin"
PYTHON_MINIFIER_VERSION = "3.3.0"
PYTHON_SCRIPTS = ("scripts/preview.py",)

# One job per npm build: the file name, the pinned minifier, and the flags that produce the build.
JOBS = (
  ("assets/app.js", "terser", ("--compress", "--mangle")),
  ("assets/style.css", "cleancss", ("-O2",)),
  (
    "assets/index.html",
    "html-minifier-terser",
    ("--collapse-whitespace", "--remove-comments", "--conservative-collapse"),
  ),
)


def minify(source: Path, binary: str, flags: tuple[str, ...]) -> str:
  """Return the minified text of one asset, or raise with the minifier's own error."""
  executable = BIN / binary

  if not executable.exists():
    raise RuntimeError(f"{binary} is missing; run `npm install`")

  result = subprocess.run(
    # The file precedes the flags: terser reads its first positional as the input.
    [str(executable), str(source), *flags],
    capture_output=True,
    text=True,
    check=False,
  )

  if result.returncode or result.stderr.strip():
    # A warning is a failure here. clean-css reported an unterminated string once by dropping every
    # rule it swallowed, which a size budget cannot see and a browser may hide (commit 99b126e).
    raise RuntimeError(
      f"{binary} on {source.name}:\n{result.stderr.strip() or 'failed'}"
    )

  return result.stdout.rstrip("\n") + "\n"


def strip_string_statements(tree):
  """Drop every bare string statement, which is what the minifier removes."""
  for node in list(ast.walk(tree)):
    body = getattr(node, "body", None)
    if not isinstance(body, list):
      continue
    node.body = [
      item
      for item in body
      if not (
        isinstance(item, ast.Expr)
        and isinstance(item.value, ast.Constant)
        and isinstance(item.value.value, str)
      )
    ]
  return tree


def check_python(source: str, built: str, filename: str) -> None:
  """Keep the Python 3.10 syntax floor, every parsed statement, name and annotation.

  Bare string statements are compared away, because the build removes them.
  """
  before = ast.parse(source, filename, feature_version=(3, 10), type_comments=True)
  after = ast.parse(built, filename, feature_version=(3, 10), type_comments=True)
  if ast.dump(strip_string_statements(before)) != ast.dump(
    strip_string_statements(after)
  ):
    raise RuntimeError(f"minified Python changed the parsed tree: {filename}")
  compile(built, filename, "exec")


def minify_python(source: str, filename: str) -> str:
  """Remove comments, docstrings and excess whitespace, not behavior."""
  if version("python-minifier") != PYTHON_MINIFIER_VERSION:
    raise RuntimeError(f"install python-minifier=={PYTHON_MINIFIER_VERSION}")
  import python_minifier

  built = (
    python_minifier.minify(
      source,
      filename=filename,
      remove_annotations=False,
      remove_pass=False,
      remove_literal_statements=True,
      combine_imports=False,
      hoist_literals=False,
      rename_locals=False,
      rename_globals=False,
      remove_object_base=False,
      convert_posargs_to_args=False,
      preserve_shebang=True,
      remove_asserts=False,
      remove_debug=False,
      remove_explicit_return_none=False,
      remove_builtin_exception_brackets=False,
      constant_folding=False,
      remove_dead_branches=False,
    )
    + "\n"
  )
  check_python(source, built, filename)
  return built


def check_javascript(text: str, suffix: str = ".js") -> None:
  """Refuse a build that Node cannot parse, so a broken copy never reaches a tree."""
  with tempfile.TemporaryDirectory() as directory:
    candidate = Path(directory) / f"candidate{suffix}"
    candidate.write_text(text, encoding="utf-8")
    result = subprocess.run(
      ["node", "--check", str(candidate)],
      capture_output=True,
      text=True,
      check=False,
    )

    if result.returncode:
      raise RuntimeError(
        f"minified JavaScript does not parse:\n{result.stderr.strip()}"
      )


def check_markup(source: str, built: str) -> None:
  """Every id in the readable template must survive, because the client reaches each by id."""
  before = set(re.findall(r'id="([^"]+)"', source))
  after = set(re.findall(r'id="([^"]+)"', built))
  missing = sorted(before - after)

  if missing:
    raise RuntimeError(f"minified HTML lost these ids: {missing}")

  if "__STYLE__" not in built or "__SCRIPT__" not in built:
    raise RuntimeError(
      "minified HTML lost a placeholder; the server inlines both assets"
    )

  def words(markup: str) -> list[str]:
    return re.sub(r"<[^>]+>", " ", markup).split()

  if words(source) != words(built):
    raise RuntimeError(
      "minified HTML changed the visible words; whitespace carries meaning"
    )


def check_stylesheet(built: str) -> None:
  """A stylesheet that lost a brace would break the page silently, so refuse it here."""
  if built.count("{") != built.count("}"):
    raise RuntimeError("minified CSS has unbalanced braces")

  if not built.strip():
    raise RuntimeError("minified CSS is empty")


def build() -> dict[str, tuple[str, str]]:
  """Build and validate all outputs before the first write."""
  sources = {}

  for name, binary, flags in JOBS:
    path = SOURCE / name

    if not path.is_file():
      raise RuntimeError(f"missing source file: {path.relative_to(ROOT)}")

    built = minify(path, binary, flags)
    sources[name] = (path.read_text(encoding="utf-8"), built)

  for name in PYTHON_SCRIPTS:
    path = SOURCE / name
    source = path.read_text(encoding="utf-8")
    sources[name] = (source, minify_python(source, name))

  check_javascript(sources["assets/app.js"][1])
  check_stylesheet(sources["assets/style.css"][1])
  check_markup(*sources["assets/index.html"])
  return sources


def main() -> int:
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument(
    "--update",
    action="store_true",
    help="write the minified copies instead of reporting drift",
  )
  arguments = parser.parse_args()

  sources = build()

  drift = []

  for name, (source, built) in sources.items():
    saved = len(source.encode()) - len(built.encode())
    share = saved / len(source.encode()) * 100
    print(
      f"{name}: {len(source.encode()):,} -> {len(built.encode()):,} B ({share:.0f}% smaller)"
    )

  for target in TARGETS:
    for name, (_, built) in sources.items():
      path = target / name
      current = path.read_text(encoding="utf-8") if path.is_file() else None

      if current == built:
        continue

      relative = path.relative_to(ROOT)

      if arguments.update:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(built, encoding="utf-8")
        print(f"wrote {relative}")
      else:
        drift.append(str(relative))

  if drift:
    print("\nDrift from the refs sources:")
    for relative in drift:
      print(f"- {relative}")
    print(
      "\nRun `python maintenance/minify.py --update` and refresh the README measurements."
    )
    return 1

  if not arguments.update:
    print("\nBoth distributed copies match the refs sources.")

  return 0


if __name__ == "__main__":
  sys.exit(main())
