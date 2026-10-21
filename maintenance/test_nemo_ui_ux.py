"""Tests for the nemo-ui-ux measure helper."""

from __future__ import annotations

import importlib.util
from pathlib import Path

MEASURE = (
  Path(__file__).resolve().parents[1]
  / "skills"
  / "nemo-ui-ux"
  / "scripts"
  / "measure.py"
)

SHEET = {
  "size-12": "12px",
  "size-14": "14px",
  "eyebrow": "11px",
  "space-2": "16px",
  "row": "40px",
  "radius": "10px",
  "touch": "44px",
}


def load_measure():
  spec = importlib.util.spec_from_file_location("nemo_measure", MEASURE)
  assert spec is not None and spec.loader is not None
  module = importlib.util.module_from_spec(spec)
  spec.loader.exec_module(module)
  return module


def test_sheet_reads_tokens_and_their_values():
  measure = load_measure()
  sheet = measure.parse_sheet(
    """
    :root {
      --text: #17171a;
      --space-2: 16px;
      --ease: cubic-bezier(.22, 1, .36, 1);
    }
    """
  )
  assert sheet["text"] == "#17171a"
  assert sheet["space-2"] == "16px"
  assert sheet["ease"] == "cubic-bezier(.22, 1, .36, 1)"


def test_a_value_off_the_scale_is_a_finding():
  measure = load_measure()
  report = {
    "width": 1280,
    "elements": [
      {"selector": ".row", "values": {"height": "40px", "padding-left": "13px"}},
    ],
  }
  findings = measure.check(report, SHEET, 8)
  assert any("padding-left" in finding and "13px" in finding for finding in findings)
  assert not any("height" in finding for finding in findings)


def test_a_spacing_value_never_borrows_a_type_size():
  measure = load_measure()
  report = {
    "width": 1280,
    "elements": [
      {"selector": ".card", "values": {"padding-left": "13px", "gap": "16px"}}
    ],
  }
  findings = measure.check(report, SHEET, 8)
  assert any("padding-left" in finding for finding in findings)
  assert not any("gap" in finding for finding in findings)


def test_a_named_size_outside_the_scale_passes_on_its_own_property():
  measure = load_measure()
  report = {
    "width": 360,
    "elements": [
      {
        "selector": ".title",
        "values": {"font-size": "14px", "border-radius": "10px"},
      }
    ],
  }
  assert measure.check(report, SHEET, 8) == []


def test_an_unnamed_type_size_is_a_finding():
  measure = load_measure()
  report = {
    "width": 360,
    "elements": [{"selector": ".title", "values": {"font-size": "22px"}}],
  }
  findings = measure.check(report, SHEET, 8)
  assert any("font-size" in finding and "22px" in finding for finding in findings)


def test_zero_and_non_px_values_pass():
  measure = load_measure()
  report = {
    "width": 640,
    "elements": [
      {"selector": ".row", "values": {"margin": "0px", "gap": "auto", "color": "#fff"}}
    ],
  }
  assert measure.check(report, SHEET, 8) == []


def test_the_ruler_reports_the_gap_and_the_scale_fit():
  measure = load_measure()
  gap = measure.ruler((120, 340), (264, 340), scale=8)
  assert gap["dx"] == 144
  assert gap["dy"] == 0
  assert gap["on_scale"] is True
  odd = measure.ruler((120, 340), (265, 341), scale=8)
  assert odd["on_scale"] is False


def test_the_ruler_names_each_axis():
  measure = load_measure()
  gap = measure.ruler((0, 0), (16, 24), scale=8)
  assert gap["axes"] == {"x": True, "y": True}
  gap = measure.ruler((0, 0), (16, 25), scale=8)
  assert gap["axes"] == {"x": True, "y": False}
