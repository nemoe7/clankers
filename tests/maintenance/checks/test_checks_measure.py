"""Tests for the size measurers."""

from __future__ import annotations

from pathlib import Path

import pytest
from checks import measure


def test_default_measure_is_tokens():
  assert measure.MEASURE_DEFAULT == "o200k_base"
  assert measure.format_unit("o200k_base") == "tok"
  assert measure.format_unit("Unicode chars") == "chars"


def test_unicode_chars_count_characters_not_bytes(tmp_path: Path):
  text = "é\n"
  path = tmp_path / "field.txt"
  path.write_text(text, encoding="utf-8")
  assert measure.measure(path, "Unicode chars") == len(text)
  assert len(text.encode("utf-8")) > len(text)


def test_tokens_come_from_the_o200k_encoder(tmp_path: Path):
  text = "hello world, hello world"
  path = tmp_path / "tok.md"
  path.write_text(text, encoding="utf-8")
  assert 0 < measure.measure(path, "o200k_base") < len(text)


def test_tokens_are_measured_again_after_the_file_changes(tmp_path: Path):
  path = tmp_path / "tok.md"
  path.write_text("hello", encoding="utf-8")
  before = measure.measure(path, "o200k_base")
  path.write_text("hello world and many more words", encoding="utf-8")
  assert measure.measure(path, "o200k_base") > before


def test_unsupported_measures_are_rejected():
  with pytest.raises(ValueError, match="unsupported measurement"):
    measure.measurer("UTF-8 file size")
