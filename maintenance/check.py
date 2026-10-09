#!/usr/bin/env python3
"""Check repository structure and maintain README measurements."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from markdown_it import MarkdownIt

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
SKILLS = ROOT / "skills"
# Vendored agent-facing skills live only under `.agents/skills/`, which this script
# deliberately never reads: they are not owner skills, so they are neither checked
# here nor listed in `skills/README.md`.
RULES = ROOT / "rules"
WORKFLOWS = ROOT / "workflows"

EXPECTED_SKILL_FIELDS = {
  "name",
  "description",
  "license",
  "compatibility",
  "metadata",
  "allowed-tools",
}

NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

EXPECTED_BUDGETS = {
  "rules/AGENTS.md": "o200k_base",
  "rules/ARENA.md": "UTF-8 file size",
  "rules/CHATGPT-CUSTOM.txt": "Unicode chars",
  "rules/CHATGPT-MORE.txt": "Unicode chars",
  "rules/CLINE.md": "o200k_base",
  "rules/KILO.md": "o200k_base",
  "rules/kilo/code.md": "o200k_base",
  "rules/kilo/debug.md": "o200k_base",
  "rules/kilo/plan.md": "o200k_base",
  "rules/COMMIT-SPEC.txt": "o200k_base",
  "system-prompts/NEMOGPT.md": "o200k_base",
  "skills/amending-violations/SKILL.md": "o200k_base",
  "skills/arena-skill/SKILL.md": "o200k_base",
  "skills/arena-skill/README.md": "o200k_base",
  "skills/arena-skill/references/REFERENCE.md": "o200k_base",
  # The table covers the arena suite: ARENA.md and every arena-skill file, one row per file,
  # except the proxies. The shipped assets and scripts keep byte budgets from
  # `maintenance/minify/minify.py`, so growth fails this check until the table is updated on
  # purpose. The `.agents/skills/` twins are byte-identical by construction, and this script
  # never reads that tree.
  "skills/arena-skill/assets/app.js": "UTF-8 file size",
  "skills/arena-skill/assets/index.html": "UTF-8 file size",
  "skills/arena-skill/assets/style.css": "UTF-8 file size",
  "skills/arena-skill/scripts/arena-preview": "UTF-8 file size",
  "skills/arena-skill/scripts/install.sh": "UTF-8 file size",
  "skills/arena-skill/scripts/preview.py": "UTF-8 file size",
  "skills/squash/SKILL.md": "o200k_base",
  "skills/web-interface-guidelines/SKILL.md": "o200k_base",
  "workflows/init-docs.md": "o200k_base",
  "gpt-plugins/skills/gpt-quirks/SKILL.md": "o200k_base",
  "gpt-plugins/skills/gpt-handoff/SKILL.md": "o200k_base",
  "gpt-plugins/skills/gpt-planning/SKILL.md": "o200k_base",
  "gpt-plugins/skills/gpt-github/SKILL.md": "o200k_base",
}

# Root `ARENA.md` is the copy `.github/workflows/distribute.yml` pushes to
# the target repositories, so it must stay byte-identical to its source.
ROOT_COPIES = ("ARENA.md",)

REFS = RULES / "refs"
LINT_CONFIG = ROOT / ".markdownlint-cli2.jsonc"

# The markdownlint scope, recomputed from LINT_CONFIG on every run.
EXPECTED_LINTED = (
  "rules/AGENTS.md",
  "rules/ARENA.md",
  "rules/CLINE.md",
  "rules/KILO.md",
  "rules/refs/AGENTS.md",
  "rules/refs/ARENA.md",
  "rules/refs/CLINE.md",
  "rules/refs/GUIDELINES.md",
  "rules/refs/KILO.md",
  "rules/refs/README.md",
  "rules/wenyan/README.md",
)

# Where the documented markdownlint file count lives, and how to find it. Root AGENTS.md
# carries the same claim in its own words and is deliberately left out of the check: it is an
# agent-facing file, and the owner's ruling keeps this script off those.
# Prose covered by the ASD-STE100 linter. Add a path only when the linter reports 0 violations
# for it. CI runs `check.py --ste` against this same list, so the local gate and CI agree.
STE_DOCS = (
  "userscripts/README.md",
  "maintenance/README.md",
  "skills/README.md",
  "README.md",
  "workflows/README.md",
  ".agents/skills/README.md",
  "docs/archive/arena-quirks.md",
  "rules/README.md",
  "rules/refs/README.md",
  "gpt-plugins/README.md",
  "CHANGELOG.md",
)
STE_LINT = ".agents/skills/asd-ste100/scripts/ste-lint.py"
# The prose lint covers the code comments and the documents outside the STE list.
PROSE_LINT = "maintenance/lint_prose.py"

# One paragraph carries at most this many sentences. A longer one splits.
PARAGRAPH_SENTENCE_CAP = 4
CODE_SPAN_RE = re.compile(r"`[^`]*`")
SENTENCE_END_RE = re.compile(r"(?<=[.!?])(?:\s+|$)")
LIST_OR_BLOCK_RE = re.compile(r"^(?:[-*+>|#]|\d+[.)] )")

LINT_COUNT_CLAIMS = ((RULES / "README.md", r"(\d+) files in all"),)

# Rule refs baselines hold full wording. Live files compress it. Compression may
# merge rule lines but never add them, so live counts stay at or below refs.
SECTIONED_PAIRS = ("AGENTS.md", "ARENA.md", "CLINE.md", "KILO.md")
PLAIN_PAIRS = ("CHATGPT-CUSTOM.txt", "CHATGPT-MORE.txt", "COMMIT-SPEC.txt")

# Kilo mode overrides live under a directory on both sides, so the check pairs them by
# name and compares them the plain way: live compresses wording, never adds rules.
KILO_PAIRS = ("plan.md", "code.md", "debug.md")

# ChatGPT's Personalization offers two instruction fields, `Custom Instructions`
# and `More about you`, each capped at 1,500 characters.
CHATGPT_FIELDS = ("CHATGPT-CUSTOM.txt", "CHATGPT-MORE.txt")

# Token counts ride the npm package gpt-tokenizer, which ships its own ranks and
# measures offline, so no cache seeding is needed.
_NODE_CWD = Path(__file__).resolve().parent.parent
_TOKEN_COUNT_SCRIPT = """
const { encode } = require("gpt-tokenizer/encoding/o200k_base");
const fs = require("fs");
const counts = {};
for (const file of JSON.parse(process.argv[1])) {
  counts[file] = encode(fs.readFileSync(file, "utf8")).length;
}
process.stdout.write(JSON.stringify(counts));
"""
_token_counts: dict[str, int] = {}


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(
    description=("Validate the repository and optionally update README measurements.")
  )
  parser.add_argument(
    "--update",
    action="store_true",
    help="Update README measurements before validation.",
  )
  parser.add_argument(
    "--ste",
    action="store_true",
    help="Run only the ASD-STE100 lint over the covered documentation.",
  )
  return parser.parse_args()


def check_ste(errors: list[str]) -> None:
  """Run the vendored STE linter over the covered prose. Any hard violation is an error."""
  result = subprocess.run(
    [sys.executable, str(ROOT / STE_LINT), *(str(ROOT / doc) for doc in STE_DOCS)],
    capture_output=True,
    text=True,
    check=False,
  )
  if result.returncode:
    output = (result.stdout + result.stderr).strip()
    errors.append(f"STE lint failed:\n{output}")


def check_prose(errors: list[str]) -> None:
  """Run the prose lint over the covered code comments and documents."""
  result = subprocess.run(
    [sys.executable, str(ROOT / PROSE_LINT)],
    capture_output=True,
    text=True,
    check=False,
  )
  if result.returncode:
    output = (result.stdout + result.stderr).strip()
    errors.append(f"Prose lint failed:\n{output}")


def sentence_count(text: str) -> int:
  """Count the sentences in one prose paragraph."""
  cleaned = CODE_SPAN_RE.sub("code", text)
  return len([part for part in SENTENCE_END_RE.split(cleaned) if part.strip()])


def prose_paragraphs(text: str) -> list[tuple[int, str]]:
  """Return each prose paragraph with the line number that opens it."""
  blocks: list[tuple[int, str]] = []
  lines: list[str] = []
  start = 0
  fenced = False

  for number, line in enumerate(text.splitlines(), start=1):
    if line.lstrip().startswith("```"):
      fenced = not fenced
      continue

    if fenced:
      continue

    if not line.strip():
      if lines:
        blocks.append((start, " ".join(lines)))
        lines = []
      continue

    if not lines:
      start = number
    lines.append(line.strip())

  if lines:
    blocks.append((start, " ".join(lines)))

  prose = []
  for number, block in blocks:
    if LIST_OR_BLOCK_RE.match(block):
      continue
    prose.append((number, block))

  return prose


def paragraph_violations(name: str, text: str) -> list[str]:
  """Name every prose paragraph that holds more sentences than the cap."""
  violations = []

  for number, block in prose_paragraphs(text):
    count = sentence_count(block)
    if count > PARAGRAPH_SENTENCE_CAP:
      violations.append(
        f"{name}:{number}: paragraph holds {count} sentences; the cap is "
        f"{PARAGRAPH_SENTENCE_CAP}"
      )

  return violations


def check_paragraph_caps(errors: list[str]) -> None:
  """Fail on a covered prose paragraph over the sentence cap."""
  for doc in STE_DOCS:
    path = ROOT / doc
    if not path.is_file():
      continue
    errors.extend(paragraph_violations(doc, path.read_text(encoding="utf-8")))


def parse_frontmatter(
  text: str,
) -> tuple[dict[str, str], list[str]]:
  errors: list[str] = []

  if not text.startswith("---\n"):
    return {}, ["missing YAML frontmatter"]

  end = text.find("\n---", 4)

  if end < 0:
    return {}, ["unterminated YAML frontmatter"]

  values: dict[str, str] = {}
  lines = text[4:end].splitlines()
  index = 0

  while index < len(lines):
    line = lines[index]

    if not line.strip():
      index += 1
      continue

    # Nested YAML content belongs to the preceding top-level key.
    if line.startswith((" ", "\t")):
      index += 1
      continue

    if ":" not in line:
      errors.append(f"invalid frontmatter line: {line}")
      index += 1
      continue

    key, raw = line.split(":", 1)
    key = key.strip()
    raw = raw.strip()

    if not key:
      errors.append(f"invalid frontmatter line: {line}")
      index += 1
      continue

    if raw in {">", "|"}:
      parts: list[str] = []
      index += 1

      while index < len(lines) and (
        lines[index].startswith((" ", "\t")) or not lines[index].strip()
      ):
        parts.append(lines[index].strip())
        index += 1

      values[key] = " ".join(part for part in parts if part)
      continue

    values[key] = raw.strip('"').strip("'")
    index += 1

  return values, errors


def workflow_description(text: str) -> str:
  """Return a workflow file's frontmatter description, ignoring comments."""
  if not text.startswith("---\n"):
    return ""

  end = text.find("\n---", 4)

  if end < 0:
    return ""

  for line in text[4:end].splitlines():
    stripped = line.strip()

    if not stripped or stripped.startswith("#"):
      continue

    # Nested YAML content belongs to the preceding top-level key.
    if line.startswith((" ", "\t")):
      continue

    if ":" not in stripped:
      continue

    key, raw = stripped.split(":", 1)

    if key.strip() == "description":
      return raw.strip().strip('"').strip("'")

  return ""


def markdown_inline_text(token: Any) -> str:
  """Reconstruct inline text while preserving text around code spans."""
  if not token.children:
    return token.content

  return "".join(
    child.content
    for child in token.children
    if child.type
    in {
      "text",
      "code_inline",
      "html_inline",
      "softbreak",
      "hardbreak",
    }
  )


def parse_budget_table(text: str) -> list[list[str]]:
  """Parse Markdown tables and return rendered cell text."""
  markdown = MarkdownIt("commonmark").enable("table")
  tokens = markdown.parse(text)

  tables: list[list[list[str]]] = []
  current_table: list[list[str]] | None = None
  current_row: list[str] | None = None

  for token in tokens:
    if token.type == "table_open":
      current_table = []
      continue

    if token.type == "tr_open":
      current_row = []
      continue

    if token.type == "inline" and current_row is not None:
      current_row.append(markdown_inline_text(token))
      continue

    if token.type == "tr_close":
      if current_table is not None and current_row is not None:
        current_table.append(current_row)
      current_row = None
      continue

    if token.type == "table_close":
      if current_table is not None:
        tables.append(current_table)
      current_table = None

  for table in tables:
    if table and table[0] == ["File", "Measure", "Current"]:
      return table

  raise RuntimeError("README budget table not found")


def read_budget_table() -> dict[str, tuple[str, str]]:
  text = README.read_text(encoding="utf-8")
  rows = parse_budget_table(text)

  result: dict[str, tuple[str, str]] = {}

  for row in rows[1:]:
    if len(row) != 3:
      continue

    relative, kind, current = row

    relative = relative.strip()

    if relative.startswith("`") and relative.endswith("`"):
      relative = relative[1:-1]

    result[relative] = (
      kind.strip(),
      current.strip(),
    )

  return result


def load_token_counts(paths: list[Path]) -> dict[str, int]:
  missing = [path for path in paths if str(path) not in _token_counts]

  if missing:
    try:
      result = subprocess.run(
        [
          "node",
          "-e",
          _TOKEN_COUNT_SCRIPT,
          json.dumps([str(path) for path in missing]),
        ],
        cwd=_NODE_CWD,
        capture_output=True,
        text=True,
        check=True,
      )
    except (OSError, subprocess.CalledProcessError) as exc:
      raise RuntimeError(
        "gpt-tokenizer is required for o200k_base measurements. Install it with: npm ci"
      ) from exc

    _token_counts.update(json.loads(result.stdout))

  return _token_counts


def measure(path: Path, kind: str) -> int:
  text = path.read_text(encoding="utf-8")

  if kind == "Unicode chars":
    return len(text)

  if kind == "UTF-8 file size":
    return len(text.encode("utf-8"))

  if kind == "o200k_base":
    return load_token_counts([path])[str(path)]

  raise ValueError(f"unsupported measurement: {kind}")


def format_unit(kind: str) -> str:
  if kind == "Unicode chars":
    return "chars"

  if kind == "UTF-8 file size":
    return "B"

  if kind == "o200k_base":
    return "tok"

  raise ValueError(f"unsupported measurement: {kind}")


def update_readme_measurements() -> bool:
  text = README.read_text(encoding="utf-8")
  lines = text.splitlines(keepends=True)
  header = "| File | Measure | Current |\n"
  if lines.count(header) != 1:
    raise RuntimeError("README must contain exactly one instruction-budget table")
  start = lines.index(header)
  end = start + 1
  while end < len(lines) and lines[end].lstrip().startswith("|"):
    end += 1

  table = [header, "| --- | --- | --- |\n"]
  for relative, kind in EXPECTED_BUDGETS.items():
    path = ROOT / relative
    if not path.is_file():
      raise RuntimeError(f"README budget path missing: {relative}")
    current = f"{measure(path, kind):,}"
    table.append(f"| `{relative}` | `{kind}` | {current} `{format_unit(kind)}` |\n")

  updated = "".join(lines[:start] + table + lines[end:])
  if updated == text:
    return False
  updated = re.sub(
    r"Latest measurements as of \d{4}-\d{2}-\d{2}\.",
    f"Latest measurements as of {datetime.now(timezone.utc).date().isoformat()}.",
    updated,
  )
  README.write_text(updated, encoding="utf-8")
  return True


def check_internal_links(
  path: Path,
  errors: list[str],
) -> None:
  text = path.read_text(encoding="utf-8")

  for target in re.findall(
    r"\[[^\]]+\]\(([^)]+)\)",
    text,
  ):
    target = target.split("#", 1)[0].strip()

    if not target:
      continue

    if re.match(
      r"^[a-z][a-z0-9+.-]*://",
      target,
      re.IGNORECASE,
    ):
      continue

    candidate = (path.parent / target).resolve()

    if not candidate.exists():
      errors.append(f"{path.relative_to(ROOT)}: broken internal link {target}")


def strip_jsonc_comments(text: str) -> str:
  return re.sub(r"^[ \t]*//.*$", "", text, flags=re.MULTILINE)


def expand_ignore_pattern(pattern: str) -> set[Path]:
  """Expand one markdownlint ignore pattern to the paths it excludes.

  ``Path.glob`` resolves a trailing ``**`` to directories only, while
  markdownlint's globby excludes everything below a matched directory, so
  this check expands directory matches recursively.
  """
  matched: set[Path] = set()

  for path in ROOT.glob(pattern):
    matched.add(path)

    if path.is_dir():
      matched.update(path.rglob("*"))

  return matched


def linted_rule_files() -> set[Path]:
  config = json.loads(strip_jsonc_comments(LINT_CONFIG.read_text(encoding="utf-8")))
  selected: set[Path] = set()

  for pattern in config.get("globs", []):
    selected.update(path for path in ROOT.glob(pattern) if path.is_file())

  ignored: set[Path] = set()

  for pattern in config.get("ignores", []):
    ignored.update(expand_ignore_pattern(pattern))

  return selected - ignored


def section_rule_counts(text: str) -> list[tuple[str, int]]:
  counts: list[tuple[str, int]] = []
  heading: str | None = None
  rules = 0

  for line in text.splitlines():
    if line.startswith("## "):
      if heading is not None:
        counts.append((heading, rules))

      heading = line[3:].strip()
      rules = 0
    elif heading is not None and line.strip():
      rules += 1

  if heading is not None:
    counts.append((heading, rules))

  return counts


def rule_line_count(path: Path) -> int:
  text = path.read_text(encoding="utf-8")

  return sum(1 for line in text.splitlines() if line.strip())


def check_lint_scope(errors: list[str]) -> None:
  if not LINT_CONFIG.is_file():
    errors.append(".markdownlint-cli2.jsonc is missing")
    return

  actual = tuple(sorted(str(path.relative_to(ROOT)) for path in linted_rule_files()))

  if actual != EXPECTED_LINTED:
    errors.append(
      f"markdownlint scope changed: expected={list(EXPECTED_LINTED)} actual={list(actual)}"
    )

  for document, pattern in LINT_COUNT_CLAIMS:
    relative = document.relative_to(ROOT)

    if not document.is_file():
      errors.append(f"{relative} is missing")
      continue

    match = re.search(pattern, document.read_text(encoding="utf-8"))

    if match is None:
      errors.append(f"{relative}: no documented markdownlint file count found")
    elif int(match.group(1)) != len(actual):
      errors.append(
        f"{relative}: documented markdownlint count {match.group(1)} != actual {len(actual)}"
      )


def check_refs_parity(errors: list[str]) -> None:
  for name in SECTIONED_PAIRS:
    reference = REFS / name
    live = RULES / name

    if not reference.is_file() or not live.is_file():
      errors.append(f"rules/{name}: refs/live pair incomplete")
      continue

    ref_counts = section_rule_counts(reference.read_text(encoding="utf-8"))
    live_counts = section_rule_counts(live.read_text(encoding="utf-8"))
    ref_headings = [heading for heading, _ in ref_counts]
    live_headings = [heading for heading, _ in live_counts]

    if ref_headings != live_headings:
      errors.append(
        f"rules/{name}: section headings diverge from rules/refs/{name}: "
        f"refs={ref_headings} live={live_headings}"
      )
      continue

    ref_map = dict(ref_counts)

    for heading, live_rules in live_counts:
      ref_rules = ref_map[heading]

      if live_rules > ref_rules:
        errors.append(
          f"rules/{name} '{heading}': {live_rules} rule lines vs {ref_rules} in "
          f"rules/refs/{name}; compression may merge lines but never add rules"
        )

  for name in KILO_PAIRS:
    reference = REFS / "kilo" / name
    live = RULES / "kilo" / name

    if not reference.is_file() or not live.is_file():
      errors.append(f"rules/kilo/{name}: refs/live pair incomplete")
      continue

    ref_rules = rule_line_count(reference)
    live_rules = rule_line_count(live)

    if live_rules > ref_rules:
      errors.append(
        f"rules/kilo/{name}: {live_rules} rule lines vs {ref_rules} in rules/refs/kilo/{name}; "
        "compression may merge lines but never add rules"
      )

  for name in PLAIN_PAIRS:
    reference = REFS / name
    live = RULES / name

    if not reference.is_file() or not live.is_file():
      errors.append(f"rules/{name}: refs/live pair incomplete")
      continue

    ref_rules = rule_line_count(reference)
    live_rules = rule_line_count(live)

    if live_rules > ref_rules:
      errors.append(
        f"rules/{name}: {live_rules} rule lines vs {ref_rules} in rules/refs/{name}; "
        "compression may merge lines but never add rules"
      )


def check_root_copies(errors: list[str]) -> None:
  for name in ROOT_COPIES:
    source = RULES / name
    copy = ROOT / name

    if not source.is_file():
      errors.append(f"rules/{name} is missing")
      continue

    if not copy.is_file():
      errors.append(f"{name}: root copy missing; run `cp rules/{name} {name}`")
      continue

    if copy.read_bytes() != source.read_bytes():
      errors.append(
        f"{name}: root copy differs from rules/{name}; run `cp rules/{name} {name}`"
      )


def validate(errors: list[str]) -> tuple[int, int]:
  skills = sorted(
    path
    for path in SKILLS.iterdir()
    if path.is_dir() and not path.name.startswith(".") and path.name != "refs"
  )

  skills_readme_path = SKILLS / "README.md"

  if not skills_readme_path.is_file():
    errors.append("skills/README.md is missing")
  else:
    skills_readme = skills_readme_path.read_text(encoding="utf-8")

    documented_skills = set(
      re.findall(
        r"\[([a-z0-9-]+)\]\([a-z0-9-]+/SKILL\.md\)",
        skills_readme,
      )
    )
    actual_skills = {path.name for path in skills}

    if documented_skills != actual_skills:
      errors.append(
        "skills/README.md list mismatch: "
        f"documented={sorted(documented_skills)} "
        f"actual={sorted(actual_skills)}"
      )

  for skill in skills:
    path = skill / "SKILL.md"

    if not path.is_file():
      errors.append(f"{skill.relative_to(ROOT)}: missing SKILL.md")
      continue

    text = path.read_text(encoding="utf-8")
    values, frontmatter_errors = parse_frontmatter(text)

    errors.extend(f"{path.relative_to(ROOT)}: {error}" for error in frontmatter_errors)

    unknown = set(values) - EXPECTED_SKILL_FIELDS

    if unknown:
      errors.append(
        f"{path.relative_to(ROOT)}: unknown frontmatter fields: {sorted(unknown)}"
      )

    adapted = re.search(
      r"^[ \t]+upstream:", text[: text.find("\n---", 4)], re.MULTILINE
    )
    license_value = str(values.get("license", ""))

    if adapted and not license_value:
      errors.append(
        f"{path.relative_to(ROOT)}: adapted skill records metadata.upstream "
        "but declares no license"
      )

    if "LICENSE.txt" in license_value and not (skill / "LICENSE.txt").is_file():
      errors.append(
        f"{path.relative_to(ROOT)}: license points at a missing LICENSE.txt"
      )

    name = values.get("name", "")
    description = values.get("description", "")

    if name != skill.name or not NAME_RE.fullmatch(name):
      errors.append(f"{path.relative_to(ROOT)}: invalid name {name!r}")

    if not 1 <= len(description) <= 1024:
      errors.append(
        f"{path.relative_to(ROOT)}: "
        f"description length is {len(description)}, "
        "expected 1..1024"
      )

    if len(text.splitlines()) > 500:
      errors.append(f"{path.relative_to(ROOT)}: SKILL.md exceeds 500 lines")

  workflows = sorted(
    path
    for path in WORKFLOWS.iterdir()
    if path.suffix == ".md" and path.name != "README.md"
  )

  workflows_readme_path = WORKFLOWS / "README.md"

  if not workflows_readme_path.is_file():
    errors.append("workflows/README.md is missing")
  else:
    workflows_readme = workflows_readme_path.read_text(encoding="utf-8")

    documented_workflows = set(
      re.findall(
        r"\[([a-z0-9-]+)\]\([a-z0-9-]+\.md\)",
        workflows_readme,
      )
    )
    actual_workflows = {path.stem for path in workflows}

    if documented_workflows != actual_workflows:
      errors.append(
        "workflows/README.md list mismatch: "
        f"documented={sorted(documented_workflows)} "
        f"actual={sorted(actual_workflows)}"
      )

  for workflow in workflows:
    if not NAME_RE.fullmatch(workflow.stem):
      errors.append(f"{workflow.relative_to(ROOT)}: invalid workflow filename")

    text = workflow.read_text(encoding="utf-8")

    if not workflow_description(text):
      errors.append(f"{workflow.relative_to(ROOT)}: missing frontmatter description")

  for path in (
    README,
    SKILLS / "README.md",
    RULES / "README.md",
    WORKFLOWS / "README.md",
  ):
    if path.is_file():
      check_internal_links(path, errors)

  budgets = read_budget_table()

  if set(budgets) != set(EXPECTED_BUDGETS):
    errors.append(
      "README budget table entries mismatch: "
      f"documented={sorted(budgets)} "
      f"expected={sorted(EXPECTED_BUDGETS)}"
    )
  else:
    for relative, expected_kind in EXPECTED_BUDGETS.items():
      recorded_kind, recorded_value = budgets[relative]

      if recorded_kind != expected_kind:
        errors.append(
          f"README budget kind mismatch for {relative}: "
          f"recorded={recorded_kind!r} "
          f"expected={expected_kind!r}"
        )
        continue

      path = ROOT / relative

      if not path.is_file():
        errors.append(f"README budget path missing: {relative}")
        continue

      try:
        actual = measure(path, expected_kind)
      except RuntimeError as exc:
        errors.append(str(exc))
        continue

      match = re.search(
        r"\d[\d,]*",
        recorded_value,
      )

      if not match:
        errors.append(
          f"README budget invalid for {relative}: recorded={recorded_value}"
        )
        continue

      recorded = int(match.group().replace(",", ""))

      if actual != recorded:
        errors.append(
          f"README budget stale for {relative}: recorded={recorded} actual={actual}"
        )

  for field in CHATGPT_FIELDS:
    chat = RULES / field

    if chat.is_file():
      characters = len(chat.read_text(encoding="utf-8"))

      if characters > 1500:
        errors.append(f"rules/{field} exceeds 1,500 Unicode chars")

  check_lint_scope(errors)
  check_refs_parity(errors)
  check_root_copies(errors)

  return len(skills), len(workflows)


def run_check(name: str, errors: list[str], check: Callable[[], Any]) -> Any:
  """Run one named check, print its verdict and span, and return what it reported.

  The count is the check's own: every check appends to one shared list, so the line
  names the check that added the problems instead of blaming the whole run.
  """
  started = time.perf_counter()
  before = len(errors)
  reported = check()
  found = len(errors) - before
  span = time.perf_counter() - started
  if found:
    print(f"FAIL {name}: {found} problem(s) in {span:.2f}s")
  else:
    print(f"ok {name} in {span:.2f}s")
  return reported


def main() -> int:
  args = parse_args()
  started = time.perf_counter()

  if args.update:
    try:
      changed = run_check("README update", [], lambda: update_readme_measurements())
    except (RuntimeError, OSError) as exc:
      print(f"README update failed: {exc}")
      return 1

    if changed:
      print("Updated README measurements.")
    else:
      print("README measurements already up to date.")

  errors: list[str] = []
  if args.ste:
    run_check("STE lint", errors, lambda: check_ste(errors))
    if errors:
      print(errors[0])
      return 1
    print(
      f"STE lint passed in {time.perf_counter() - started:.2f}s: {len(STE_DOCS)} files."
    )
    return 0
  skills, workflows = run_check("repository", errors, lambda: validate(errors))
  run_check("STE lint", errors, lambda: check_ste(errors))
  run_check("prose lint", errors, lambda: check_prose(errors))
  run_check("paragraph caps", errors, lambda: check_paragraph_caps(errors))
  span = time.perf_counter() - started

  if errors:
    print(f"Validation failed in {span:.2f}s:")

    for error in errors:
      print(f"- {error}")

    return 1

  print(
    f"Validation passed in {span:.2f}s: {skills} skills, {workflows} workflows, "
    "README measurements, the markdownlint scope, refs/live parity, the prose "
    f"lint, the {PARAGRAPH_SENTENCE_CAP}-sentence paragraph cap and the root "
    "ARENA.md copy checked."
  )

  return 0


if __name__ == "__main__":
  sys.exit(main())
