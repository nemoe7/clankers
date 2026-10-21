"""Count prose sentences and paragraphs.

Table parsing adapts ASD-STE100 code. The package includes its MIT license.
"""

import re

SENTENCE_CAPS = {"instruction": 20, "description": 25}
PARAGRAPH_CAP = 6
CODE_FENCE = re.compile(r"^(```|~~~)")
INLINE_CODE = re.compile(r"`[^`]*`")
CODE_SPAN_RE = INLINE_CODE
SENTENCE_END_RE = re.compile(r"(?<=[.!?])(?:\s+|$)")
LIST_OR_BLOCK_RE = re.compile(r"^(?:[-*+>|#]|\d+[.)] )")
TABLE_SEPARATOR_CELL = re.compile(r"^:?-{3,}:?$")


def _split_table_row(line):
  """Return trimmed table cells and their zero-based source columns.

  A pipe must separate at least two cells. Escaped pipes stay in their cell.
  This deliberately implements only the ordinary Markdown table shape. It is
  enough to distinguish a table from prose that happens to contain a pipe.
  """
  left = len(line) - len(line.lstrip())
  right = len(line.rstrip())
  content = line[left:right]
  if "|" not in content:
    return None
  if content.startswith("|"):
    content = content[1:]
    left += 1
  content = content.removesuffix("|")
  raw_cells = re.split(r"(?<!\\)\|", content)
  if len(raw_cells) < 2:
    return None

  cells = []
  column = left
  for raw_cell in raw_cells:
    leading = len(raw_cell) - len(raw_cell.lstrip())
    cells.append((raw_cell.strip(), column + leading))
    column += len(raw_cell) + 1
  return cells


def _markdown_table_cells(lines):
  """Map ordinary Markdown table rows to their prose cells.

  The separator row anchors detection, so pipe-containing prose is not
  treated as a table. Both leading-pipe and no-leading-pipe table styles are
  accepted when their header and body use the same number of cells.
  """
  table_cells = {}
  index = 1
  while index < len(lines):
    separator = _split_table_row(lines[index])
    header = _split_table_row(lines[index - 1])
    if (
      not separator
      or not header
      or len(separator) != len(header)
      or not all(TABLE_SEPARATOR_CELL.fullmatch(cell) for cell, _ in separator)
    ):
      index += 1
      continue

    table_cells[index - 1] = header
    table_cells[index] = []
    index += 1
    while index < len(lines):
      row = _split_table_row(lines[index])
      if not row or len(row) != len(separator):
        break
      table_cells[index] = row
      index += 1
  return table_cells


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


def sentence_lengths(line):
  """Return word counts with the existing inline-code and sentence handling."""
  cleaned = INLINE_CODE.sub("", line)
  return [len(sentence.split()) for sentence in re.split(r"(?<=[.!?])\s+", cleaned)]


def sentence_measurements(text):
  """Yield source lines, columns, and word counts outside code fences."""
  lines = text.splitlines()
  cells = _markdown_table_cells(lines)
  fenced = False
  for number, line in enumerate(lines, 1):
    if CODE_FENCE.match(line.strip()):
      fenced = not fenced
      continue
    if fenced:
      continue
    for segment, column in cells.get(number - 1, [(line, 0)]):
      for count in sentence_lengths(segment):
        yield number, column + 1, count
