"""Checks for the lightweight Mermaid block validator."""

import pytest
from mermaid_check import check_mermaid_markdown, format_mermaid_warnings

VALID_DIAGRAMS = [
  "flowchart TD\n  A-->B",
  "graph LR\n  A---B",
  "sequenceDiagram\n  Alice->>Bob: Hi",
  "stateDiagram\n  [*] --> Ready",
  "stateDiagram-v2\n  [*] --> Ready",
  "classDiagram\n  Animal <|-- Dog",
  "erDiagram\n  CUSTOMER ||--o{ ORDER : places",
  "gantt\n  title Plan\n  section Build\n  Task :a1, 2026-01-01, 1d",
  'pie title Pets\n  "Dogs" : 10',
  "gitGraph\n  commit",
  "journey\n  title Trip\n  section Go\n  Drive: 5: Me",
  "mindmap\n  root((Plan))\n    Child",
  "mindmap\n  root\n    id2)Cloud(",
  "flowchart TD\n  A>Flag] --> B[Done]",
  "timeline\n  title History\n  2026 : Launch",
  "quadrantChart\n  title Reach\n  x-axis Low --> High",
]


def wrap(body: str) -> str:
  return f"```mermaid\n{body}\n```\n"


@pytest.mark.parametrize("body", VALID_DIAGRAMS)
def test_valid_diagram_headers_pass(body):
  assert check_mermaid_markdown(wrap(body)) == []


def test_ignores_comment_lines_and_non_mermaid_code():
  markdown = (
    "Text with `graph TD A-->` inline.\n\n"
    "```python\ngraph TD\n  A-->\n```\n\n"
    "```mermaid\n%%{init: {'theme': 'dark'}}%%\n%% Comment.\n"
    "flowchart TD\n  A-->B\n```\n"
  )
  assert check_mermaid_markdown(markdown) == []


def test_empty_and_unknown_header_blocks_fail():
  assert check_mermaid_markdown(wrap("%% Only a comment.")) == [
    (1, "empty mermaid block")
  ]
  assert check_mermaid_markdown(wrap("foobar TD\n  A-->B")) == [
    (2, "unknown diagram header 'foobar'")
  ]


@pytest.mark.parametrize(
  "body",
  [
    "flowchart TD\n  subgraph Group\n    A-->B",
    "sequenceDiagram\n  rect rgb(10, 20, 30)\n    Alice->>Bob: Hi",
    "sequenceDiagram\n  alt Ready\n    Alice->>Bob: Hi",
    "sequenceDiagram\n  loop Retry\n    Alice->>Bob: Hi",
    "sequenceDiagram\n  opt Ready\n    Alice->>Bob: Hi",
    "sequenceDiagram\n  par Sync\n    Alice->>Bob: Hi",
  ],
)
def test_unclosed_group_blocks_fail(body):
  keyword = body.splitlines()[1].strip().split()[0]
  assert check_mermaid_markdown(wrap(body)) == [(3, f"unclosed '{keyword}' block")]


def test_closed_group_blocks_pass():
  body = "flowchart TD\n  subgraph Group\n    A-->B\n  end"
  assert check_mermaid_markdown(wrap(body)) == []


def test_quote_bracket_and_arrow_issues_report_source_lines():
  markdown = (
    "# Report\n\n"
    "```mermaid\n"
    "flowchart TD\n"
    '  A["Label]\n'
    "```\n\n"
    "```mermaid\n"
    "flowchart TD\n"
    "  A[Label --> B\n"
    "  B -->\n"
    "```\n"
  )
  assert check_mermaid_markdown(markdown) == [
    (5, "unclosed quote"),
    (10, "unclosed '[' bracket"),
    (11, "dangling arrow operator"),
  ]


def test_format_mermaid_warnings():
  issues = [(4, "empty mermaid block"), (9, "dangling arrow operator")]
  assert format_mermaid_warnings("report.md", issues) == [
    "Mermaid warning (report.md:4): empty mermaid block",
    "Mermaid warning (report.md:9): dangling arrow operator",
  ]
