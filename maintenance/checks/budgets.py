"""The README instruction-budget table: discovery, rebuild, and staleness checks."""

from __future__ import annotations

import re
from datetime import UTC, datetime

from .measure import MEASURE_DEFAULT, format_unit, measure
from .repo import Repo

BUDGET_HEADER = "| File | Measure | Current |\n"
BUDGET_LINK_RE = re.compile(r"^\[([^\]]+)\]\([^)]+\)$")
NUMBER_RE = re.compile(r"\d[\d,]*")
UPDATED_RE = re.compile(r"Latest measurements as of \d{4}-\d{2}-\d{2}\.")

# ChatGPT's Personalization offers two instruction fields, `Custom Instructions`
# and `More about you`, each capped at 1,500 characters.
CHATGPT_FIELDS = ("CHATGPT-CUSTOM.txt", "CHATGPT-MORE.txt")
# The cap covers production fields and Wenyan experimentals.
CHATGPT_CHAR_CAP = 1500

# Every clause file measures in tokens. Only the ChatGPT fields count characters,
# because ChatGPT caps its fields in characters.
MEASURE_OVERRIDES = {f"rules/{field}": "Unicode chars" for field in CHATGPT_FIELDS}
# Clause files live under these globs. READMEs are documentation, not clauses.
BUDGET_GLOBS = (
  "rules/*.md",
  "rules/*.txt",
  "rules/kilo/*.md",
  "system-prompts/*.md",
  "system-prompts/wenyan/*.md",
  "userscripts/*.txt",
  "skills/*/SKILL.md",
  "gpt-plugins/skills/*/SKILL.md",
)


def measure_type(relative: str) -> str:
  return MEASURE_OVERRIDES.get(relative, MEASURE_DEFAULT)


def budget_items(repo: Repo) -> list[tuple[str, str]]:
  """Return canonical sorted `(relative_path, measure_type)` budget entries."""
  found = {
    repo.relative(path)
    for pattern in BUDGET_GLOBS
    for path in repo.root.glob(pattern)
    if path.is_file() and path.name != "README.md"
  }
  return [
    (relative, measure_type(relative)) for relative in sorted(found, key=str.casefold)
  ]


def budget_value(repo: Repo, relative: str, kind: str) -> int:
  """Measure one instruction-budget file."""
  path = repo.root / relative
  if not path.is_file():
    raise RuntimeError(f"README budget path missing: {relative}")
  return measure(path, kind)


def _clean_cell(cell: str) -> str:
  cleaned = cell.strip()
  linked = BUDGET_LINK_RE.fullmatch(cleaned)
  if linked:
    cleaned = linked.group(1).strip()
  return cleaned.replace("`", "").strip()


def parse_budget_table(text: str) -> list[list[str]]:
  """Parse the README File / Measure / Current pipe table."""
  lines = text.splitlines(keepends=True)
  if BUDGET_HEADER not in lines:
    raise RuntimeError("README budget table not found")

  rows: list[list[str]] = [["File", "Measure", "Current"]]

  for line in lines[lines.index(BUDGET_HEADER) + 1 :]:
    stripped = line.strip()
    if not stripped.startswith("|"):
      break
    cells = [part.strip() for part in stripped.strip("|").split("|")]
    if len(cells) == 3 and all(cell and set(cell) <= {"-", ":"} for cell in cells):
      continue
    rows.append([_clean_cell(cell) for cell in cells])

  return rows


def read_budget_table(repo: Repo) -> dict[str, tuple[str, str]]:
  rows = parse_budget_table(repo.readme.read_text(encoding="utf-8"))[1:]
  return {row[0]: (row[1], row[2]) for row in rows if len(row) == 3}


def format_budget_row(repo: Repo, relative: str, kind: str) -> str:
  current = f"{budget_value(repo, relative, kind):,}"
  return (
    f"| [`{relative}`]({relative}) | `{kind}` | {current} `{format_unit(kind)}` |\n"
  )


def update_readme_measurements(repo: Repo) -> bool:
  text = repo.readme.read_text(encoding="utf-8")
  lines = text.splitlines(keepends=True)
  if lines.count(BUDGET_HEADER) != 1:
    raise RuntimeError("README must contain exactly one instruction-budget table")
  start = lines.index(BUDGET_HEADER)
  end = start + 1
  while end < len(lines) and lines[end].lstrip().startswith("|"):
    end += 1

  table = [
    BUDGET_HEADER,
    "| --- | --- | --- |\n",
    *(format_budget_row(repo, relative, kind) for relative, kind in budget_items(repo)),
  ]

  updated = "".join(lines[:start] + table + lines[end:])
  if updated == text:
    return False
  today = datetime.now(UTC).date().isoformat()
  updated = UPDATED_RE.sub(f"Latest measurements as of {today}.", updated)
  repo.readme.write_text(updated, encoding="utf-8")
  return True


def _check_recorded(
  repo: Repo, relative: str, kind: str, recorded: tuple[str, str], errors: list[str]
) -> None:
  recorded_type, recorded_value = recorded

  if recorded_type != kind:
    errors.append(
      f"README budget type mismatch for {relative}: recorded={recorded_type!r} expected={kind!r}"
    )
    return

  try:
    actual = budget_value(repo, relative, kind)
  except RuntimeError as exc:
    errors.append(str(exc))
    return

  match = NUMBER_RE.search(recorded_value)
  if not match:
    errors.append(f"README budget invalid for {relative}: recorded={recorded_value}")
    return

  stored = int(match.group().replace(",", ""))
  if actual != stored:
    errors.append(
      f"README budget stale for {relative}: recorded={stored} actual={actual}"
    )


def _check_char_caps(repo: Repo, errors: list[str]) -> None:
  capped = [
    *(repo.rules / field for field in CHATGPT_FIELDS),
    *sorted((repo.rules / "wenyan").glob("CHATGPT-*.txt")),
  ]
  for path in capped:
    if path.is_file() and len(path.read_text(encoding="utf-8")) > CHATGPT_CHAR_CAP:
      errors.append(f"{repo.relative(path)} exceeds {CHATGPT_CHAR_CAP:,} Unicode chars")


def check_budgets(repo: Repo, errors: list[str]) -> None:
  budgets = read_budget_table(repo)
  items = budget_items(repo)
  expected = {relative for relative, _ in items}

  if set(budgets) != expected:
    errors.append(
      f"README budget table entries mismatch: documented={sorted(budgets)} expected={sorted(expected)}"
    )
  else:
    for relative, kind in items:
      _check_recorded(repo, relative, kind, budgets[relative], errors)

  _check_char_caps(repo, errors)
