"""Check the compact build, drift handling and generated runtime without a test framework."""

import contextlib
import http.client
import importlib.util
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch

import minify


def check_preview_path():
  """Check PATH installation, reset recovery and repo-local command dispatch."""
  source_scripts = minify.SOURCE / "scripts"
  copies = ("install.sh", "arena-preview")
  for name in copies:
    source = source_scripts / name
    for target in minify.TARGETS:
      installed = target / "scripts" / name
      assert installed.read_bytes() == source.read_bytes(), installed
    assert os.access(minify.TARGETS[1] / "scripts" / name, os.X_OK), name

  with tempfile.TemporaryDirectory(prefix="arena-preview-path-") as directory:
    home = Path(directory)
    python = home / ".agents/.arena-preview-venv/bin/python"
    python.parent.mkdir(parents=True)
    python.write_text(
      '#!/usr/bin/env bash\nprintf \'%s\\n\' "$@" > "$HOME/arena-preview-args"\n',
      encoding="utf-8",
    )
    python.chmod(0o755)
    environment = os.environ.copy()
    environment["HOME"] = str(home)
    environment["XDG_CONFIG_HOME"] = str(home / ".config")
    environment.pop("BASH_ENV", None)
    environment.pop("GIT_CONFIG_GLOBAL", None)
    install = minify.TARGETS[1] / "scripts/install.sh"

    # A fresh home models a reset. Reinstallation must restore the hook once.
    for _ in range(2):
      result = subprocess.run(
        ["bash", str(install)],
        cwd=minify.ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
      )
      assert result.returncode == 0, result.stderr

    profile = (home / ".bash_profile").read_text(encoding="utf-8")
    assert profile.count("# arena-preview-hook") == 1
    assert profile.count("# arena-preview-path") == 1
    path_result = subprocess.run(
      [
        "bash",
        "--noprofile",
        "--norc",
        "-c",
        (
          'source "$HOME/.bash_profile"; source "$HOME/.bash_profile"; '
          "command -v arena-preview; printf '%s\\n' \"$PATH\"; trap - EXIT"
        ),
      ],
      cwd=minify.ROOT / "skills",
      env=environment,
      capture_output=True,
      text=True,
      check=False,
    )
    assert path_result.returncode == 0, path_result.stderr
    lines = path_result.stdout.splitlines()
    command = str(minify.TARGETS[1] / "scripts/arena-preview")
    assert lines[0] == command, path_result.stdout
    assert lines[1].split(os.pathsep).count(str(minify.TARGETS[1] / "scripts")) == 1

    command_result = subprocess.run(
      [
        "bash",
        "--noprofile",
        "--norc",
        "-c",
        'source "$HOME/.bash_profile"; arena-preview poll --max 1; trap - EXIT',
      ],
      cwd=minify.ROOT / "skills",
      env=environment,
      capture_output=True,
      text=True,
      check=False,
    )
    assert command_result.returncode == 0, command_result.stderr
    assert (home / "arena-preview-args").read_text(encoding="utf-8").splitlines() == [
      str(minify.TARGETS[1] / "scripts/preview.py"),
      "--state-dir",
      str(minify.ROOT / "arena-state"),
      "poll",
      "--max",
      "1",
    ]
  print("PASS: repo-aware PATH install, reset and dispatch")


check_preview_path()

sample = '''#!/usr/bin/env python3
"""Keep CLI help and module documentation."""
from __future__ import annotations
# This comment can go.
def public(value: int, /, *, enabled: bool = True) -> int:
  """This docstring goes."""
  assert enabled
  if __debug__:
    pass
  if False:
    raise ValueError()
  return value + 2 * 3
'''
built = minify.minify_python(sample, "example.py")
minify.check_python(sample, built, "example.py")
assert len(built) < len(sample) and "This comment can go" not in built
assert "This docstring goes" not in built
assert built.startswith("#!/usr/bin/env python3\n")
try:
  minify.check_python("x = 1", "x = 2", "changed.py")
  raise AssertionError("Changed Python tree was accepted")
except RuntimeError:
  pass
try:
  minify.check_python("x = 1", "try:\n pass\nexcept* Exception:\n pass", "new.py")
  raise AssertionError("Python 3.11-only syntax was accepted")
except SyntaxError:
  pass
with patch("minify.version", return_value="0.0.0"):
  try:
    minify.minify_python(sample, "example.py")
    raise AssertionError("Wrong minifier version was accepted")
  except RuntimeError:
    pass

sources = minify.build()
assert set(sources) == {
  "assets/app.js",
  "assets/style.css",
  "assets/index.html",
  "scripts/preview.py",
}
for relative, (source, compact) in sources.items():
  assert len(compact.encode()) < len(source.encode()), relative
  for target in minify.TARGETS:
    assert (target / relative).read_bytes() == compact.encode(), target / relative

with tempfile.TemporaryDirectory() as directory:
  root = Path(directory)
  targets = (root / "live", root / "installed")
  with (
    patch.object(minify, "ROOT", root),
    patch.object(minify, "TARGETS", targets),
    patch.object(minify, "build", return_value=sources),
    patch.object(sys, "argv", ["minify.py"]),
    contextlib.redirect_stdout(io.StringIO()),
  ):
    assert minify.main() == 1
    assert not targets[0].exists(), "A drift check wrote files"
    with patch.object(sys, "argv", ["minify.py", "--update"]):
      assert minify.main() == 0
    assert minify.main() == 0
    stale = targets[1] / "scripts/preview.py"
    stale.write_text("stale\n", encoding="utf-8")
    assert minify.main() == 1
    assert stale.read_text() == "stale\n"

  # Exact CSS/JS assertions still use readable assets. The runtime is the generated build. The
  # harness is not shipped, so it comes from the readable refs tree and drives that build.
  skill = root / "runtime"
  shutil.copytree(minify.SOURCE / "assets", skill / "assets")
  (skill / "scripts").mkdir()
  shutil.copyfile(
    minify.TARGETS[0] / "scripts/preview.py", skill / "scripts/preview.py"
  )
  shutil.copyfile(
    minify.SOURCE / "scripts/check_preview.py", skill / "scripts/check_preview.py"
  )
  subprocess.run(
    [sys.executable, "-m", "pytest", str(skill / "scripts/check_preview.py"), "-q"],
    check=True,
  )

  spec = importlib.util.spec_from_file_location(
    "compact_preview", minify.TARGETS[0] / "scripts/preview.py"
  )
  runtime = importlib.util.module_from_spec(spec)
  spec.loader.exec_module(runtime)
  # Also exercise page assembly with the actual shipped assets, not the readable test assets.
  store = runtime.Store(root / "state", create=True)
  server = runtime.ThreadingHTTPServer(("127.0.0.1", 0), runtime.handler(store))
  worker = threading.Thread(target=server.serve_forever, daemon=True)
  worker.start()
  client = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
  try:
    client.request("GET", "/", headers={"Host": "8000-sandbox.e2b.app"})
    response = client.getresponse()
    page = response.read().decode()
    assert response.status == 200
    assert "__STYLE__" not in page and "__SCRIPT__" not in page
    assert 'id="notes-panel"' in page and 'id="reports-panel"' in page
    token = re.search(r'data-token="([^"]+)"', page)[1]
    for name in ("app.js", "style.css"):
      asset = (minify.TARGETS[0] / "assets" / name).read_text()
      assert asset.replace("__TOKEN__", token).strip() in page
  finally:
    client.close()
    server.shutdown()
    worker.join()
    server.server_close()

print(
  "PASS: compact copies, Python parity and syntax floor, drift, generated runtime and shipped page"
)
