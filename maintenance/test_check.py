"""Tests for the paragraph cap gate."""

from __future__ import annotations

import check

FIVE_SENTENCES = "One. Two. Three. Four. Five."
FOUR_SENTENCES = "One. Two. Three. Four."


def test_sentence_count_splits_on_terminators():
  assert check.sentence_count(FIVE_SENTENCES) == 5
  assert check.sentence_count(FOUR_SENTENCES) == 4


def test_sentence_count_ignores_code_spans_and_decimals():
  assert check.sentence_count("Run `check.py --update` after 1.2 s. Then stop.") == 2


def test_prose_paragraphs_skips_lists_tables_headings_and_fences():
  text = """# Heading

Prose that stays. Two sentences.

- a list item with five sentences. Two. Three. Four. Five.

| a | b |
| --- | --- |
| 1 | 2 |

```text
Code with five sentences. Two. Three. Four. Five.
```

> a quote with five sentences. Two. Three. Four. Five.
"""
  assert check.prose_paragraphs(text) == [(3, "Prose that stays. Two sentences.")]


def test_paragraph_violations_names_line_and_count():
  text = f"{FOUR_SENTENCES}\n\n{FIVE_SENTENCES}\n"
  assert check.paragraph_violations("docs/x.md", text) == [
    "docs/x.md:3: paragraph holds 5 sentences; the cap is 4"
  ]


def test_clean_text_reports_nothing():
  assert check.paragraph_violations("docs/x.md", f"{FOUR_SENTENCES}\n") == []
