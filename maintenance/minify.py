"""Build the minified browser assets of the preview skill from their refs sources.

The readable baselines live in `skills/refs/arena-preview-steering/assets/`. The two distributed
copies carry minified JavaScript, CSS and HTML, on the owner's answers to report
`minification-scope`: those three types only, a pinned third-party minifier per language, and a
size budget per file in the README table. Python and Markdown stay readable.

The minifiers come from this repository's `package.json`. Install them once with `npm install`.

Usage:
  python maintenance/minify.py            # build in memory, report drift, write nothing
  python maintenance/minify.py --update   # write the minified copies

`check.py` gates each live file's size through the README table. This script reports drift,
which the budget cannot see; run it after any change to a refs asset.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "skills/refs/arena-preview-steering/assets"
TARGETS = (
  ROOT / "skills/arena-preview-steering/assets",
  ROOT / ".agents/skills/arena-preview-steering/assets",
)
BIN = ROOT / "node_modules/.bin"

# One job per asset: the file name, the pinned minifier, and the flags that produce the build.
JOBS = (
  ("app.js", "terser", ("--compress", "--mangle")),
  ("style.css", "cleancss", ("-O2",)),
  (
    "index.html",
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


def check_javascript(text: str) -> None:
  """Refuse a build that Node cannot parse, so a broken copy never reaches a tree."""
  with tempfile.TemporaryDirectory() as directory:
    candidate = Path(directory) / "app.js"
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


def main() -> int:
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument(
    "--update",
    action="store_true",
    help="write the minified copies instead of reporting drift",
  )
  arguments = parser.parse_args()

  sources = {}

  for name, binary, flags in JOBS:
    path = SOURCE / name

    if not path.is_file():
      raise RuntimeError(f"missing source asset: {path.relative_to(ROOT)}")

    built = minify(path, binary, flags)
    sources[name] = (path.read_text(encoding="utf-8"), built)

  check_javascript(sources["app.js"][1])
  check_stylesheet(sources["style.css"][1])
  check_markup(*sources["index.html"])

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
