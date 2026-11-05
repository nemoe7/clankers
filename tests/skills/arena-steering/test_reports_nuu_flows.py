"""Run safe Reports Nuu flows against isolated empty and populated preview states."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
from pathlib import Path

import pytest
from arena_steering.server import SteeringApp, create_http_server
from arena_steering.store import SqliteStore

ROOT = Path(__file__).resolve().parents[3]
FLOWS = ROOT / "skills" / "arena-steering" / "references" / "nuu"
VIEWPORTS = {411: 799, 855: 325, 1372: 883}
FLOWS_BY_STATE = {
  "empty": ("reports-empty.json",),
  "populated": ("reports-top.json", "reports-scrolled.json"),
}


@pytest.mark.parametrize(
  "state,flow_name",
  (
    ("empty", "reports-empty.json"),
    ("top", "reports-top.json"),
    ("scrolled", "reports-scrolled.json"),
  ),
)
def test_reports_nuu_flow_is_safe(state: str, flow_name: str) -> None:
  flow_file = FLOWS / flow_name
  assert flow_file.is_file(), flow_file
  steps = json.loads(flow_file.read_text(encoding="utf-8"))
  assert steps[0] == {"action": "click", "selector": "#tab-reports"}
  # Only open Reports, inspect the existing state, and focus an answer field.
  # Exclude writes, answer edits, navigation, and absent-element waits.
  assert {step["action"] for step in steps} <= {
    "click",
    "visible",
    "text",
    "attribute",
    "focus",
    "focused",
  }
  assert all(
    step["selector"] == "#tab-reports" for step in steps if step["action"] == "click"
  )
  if state == "top":
    assert steps[-1] == {
      "action": "attribute",
      "selector": "#report-scroll-top",
      "name": "hidden",
      "expected": "",
    }
  if state == "scrolled":
    assert steps[-2:] == [
      {"action": "focus", "selector": "#report .field-text-input"},
      {"action": "focused", "selector": "#report .field-text-input"},
    ]


@pytest.mark.skipif(
  not os.environ.get("CHROMIUM_BIN") or not shutil.which("nuu"),
  reason="Set CHROMIUM_BIN and install Nuu for rendered flow audits",
)
@pytest.mark.parametrize("state", tuple(FLOWS_BY_STATE))
def test_reports_nuu_flows_capture_real_states(tmp_path: Path, state: str) -> None:
  store = SqliteStore(tmp_path / "state.sqlite3")
  app = SteeringApp(store)
  if state == "populated":
    body = (
      "# Report audit\n\n"
      + (
        "A report with enough prose to move its answer field below the fold. " * 10
        + "\n\n"
      )
      * 25
      + '<!-- question {"id":"note","label":"Note"} -->\nNote: ___\n'
    )
    app.reports.publish_report("audit", "Report audit", body)
  server = create_http_server(app, host="0.0.0.0", port=0)
  thread = threading.Thread(target=server.serve_forever, daemon=True)
  thread.start()
  captures_by_flow = {}
  try:
    for flow_name in FLOWS_BY_STATE[state]:
      stem = Path(flow_name).stem
      output = tmp_path / f"{stem}.json"
      artifacts = tmp_path / f"{stem}-captures"
      command = [
        "nuu",
        "audit",
        "-u",
        f"http://127.0.0.1:{server.server_port}/?transport=poll",
        "-o",
        str(output),
        "-d",
        str(artifacts),
        "-w",
        "1372",
        "855",
        "411",
        "-s",
        "#view-reports",
        "-r",
        "#tab-reports",
        "-f",
        str(FLOWS / flow_name),
        "-e",
        "chromium",
        "-x",
        os.environ["CHROMIUM_BIN"],
        "-O",
      ]
      result = subprocess.run(
        command, capture_output=True, text=True, timeout=180, check=False
      )
      assert result.returncode in (0, 1), (result.returncode, result.stderr[-1500:])
      assert output.exists(), (result.returncode, result.stderr[-1500:])
      report = json.loads(output.read_text(encoding="utf-8"))
      captures = report["rendered"]["captures"]
      captures_by_flow[stem] = {
        (capture["width"], capture["scheme"], capture["motion"]): capture
        for capture in captures
      }
      assert set(captures_by_flow[stem]) == {
        (width, scheme, motion)
        for width in VIEWPORTS
        for scheme in ("light", "dark")
        for motion in ("no-preference", "reduce")
      }, (result.returncode, report["rendered"])
      for capture in captures:
        assert capture["status"] == "captured", capture
        assert capture["height"] == VIEWPORTS[capture["width"]], capture
        assert capture["flow"]["status"] == "passed", capture["flow"]
        assert capture["flow"]["assertions"] >= 1, capture["flow"]
        assert Path(capture["screenshot"]).is_file(), capture
        assert capture["overlaps"]["status"] == "checked", capture
      # Nuu exits 1 on known source candidates or target-size notices.
      # The assertions above still reject flow and capture failures.
      assert not any(
        row["rule"] in {"RUN101", "RUN102", "SPC206"} for row in report["findings"]
      ), report["findings"]
    if state == "populated":
      for key, top in captures_by_flow["reports-top"].items():
        scrolled = captures_by_flow["reports-scrolled"][key]
        assert (
          Path(top["screenshot"]).read_bytes()
          != Path(scrolled["screenshot"]).read_bytes()
        ), key
  finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)
    store.close()
