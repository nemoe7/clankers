"""nemoizer worker timeout tests."""

import subprocess
import sys

from conftest import SCRIPT, SKIPPED_MESSAGE


def test_timed_out_queued_files_do_not_block_a_full_worker_queue(tmp_path):
  notes = [tmp_path / "slow.md", tmp_path / "queued.md"]
  for note in notes:
    note.write_text("Short.\n", encoding="utf-8")
  script = """
import sys, time
sys.path.insert(0, sys.argv[1])
import nemoize
nemoize.os.cpu_count = lambda: 1
nemoize.source_prose = lambda *args: time.sleep(60)
raise SystemExit(nemoize.main(['--no-config', *sys.argv[2:]]))
"""
  result = subprocess.run(
    [sys.executable, "-c", script, str(SCRIPT.parent), *(str(note) for note in notes)],
    capture_output=True,
    text=True,
    encoding="utf-8",
    check=False,
    timeout=25,
  )
  assert result.returncode == 0, result.stderr
  assert SKIPPED_MESSAGE in result.stderr
  for note in notes:
    assert str(note) in result.stderr


def test_timed_out_worker_does_not_block_process_exit(tmp_path):
  note = tmp_path / "slow.md"
  note.write_text("Short.\n", encoding="utf-8")
  script = """
import sys, time
sys.path.insert(0, sys.argv[1])
import nemoize
nemoize.source_prose = lambda *args: time.sleep(60)
raise SystemExit(nemoize.main(['--no-config', sys.argv[2]]))
"""
  result = subprocess.run(
    [sys.executable, "-c", script, str(SCRIPT.parent), str(note)],
    capture_output=True,
    text=True,
    encoding="utf-8",
    check=False,
    timeout=15,
  )
  assert result.returncode == 0, result.stderr
  assert SKIPPED_MESSAGE in result.stderr
  assert str(note) in result.stderr
