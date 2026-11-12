"""nemoizer file walking and skip-rule tests."""

from pathlib import PureWindowsPath

import files
from conftest import run


def test_generated_pytest_cache_is_not_scanned(tmp_path):
  cache = tmp_path / ".pytest_cache" / "v" / "cache"
  cache.mkdir(parents=True)
  (cache / "nodeids").write_text("names the fixture\n", encoding="utf-8")
  (tmp_path / "prose.md").write_text("names the wording\n", encoding="utf-8")
  result = run(cwd=tmp_path)
  assert result.returncode == 0
  assert "prose.md:1: [NMO901]" in result.stdout  # nonemo: NMT100
  assert ".pytest_cache" not in result.stdout


def test_ignore_prefixes_accept_windows_paths():
  class WindowsPath(PureWindowsPath):
    def resolve(self):
      return self

  root = WindowsPath("C:/repo")
  assert files.skipped(root / "vendor" / "file.txt", root, ["vendor"])
  assert files.skipped(root / ".agents" / "skills" / "tool" / "SKILL.md", root, [])
  assert files.skipped(root / "node_modules" / "lib" / "file.js", root, [])
  assert not files.skipped(root / "app" / "code.py", root, ["vendor"])
