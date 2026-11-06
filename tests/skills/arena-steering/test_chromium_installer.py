"""Checks for the on-demand Chromium runtime installer."""

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "skills/arena-steering/scripts/chromium.sh"


def test_installer_reports_runtime_paths_and_reuses_package(tmp_path: Path) -> None:
  fake_bin = tmp_path / "bin"
  fake_bin.mkdir()
  npm = fake_bin / "npm"
  npm.write_text(
    "#!/bin/sh\n"
    "set -eu\n"
    "prefix=$2\n"
    "pkg=$prefix/node_modules/@sparticuz/chromium\n"
    'mkdir -p "$pkg/bin" "$pkg/build"\n'
    'printf \'%s\' \'{"version":"153.0.0","type":"module"}\' > "$pkg/package.json"\n'
    "cat > \"$pkg/build/index.js\" <<'EOF'\n"
    "import { mkdirSync, writeFileSync } from 'node:fs';\n"
    "import { join } from 'node:path';\n"
    "const root = process.env.TMPDIR;\n"
    "export async function inflate(path) {\n"
    "  const name = path.includes('al2023') ? 'al2023/lib' : 'fonts';\n"
    "  mkdirSync(join(root, name), {recursive:true});\n"
    "}\n"
    "export function setupLambdaEnvironment() {}\n"
    "export default { async executablePath() {\n"
    "  const path = join(root, 'chromium'); writeFileSync(path, 'browser', {mode:0o700}); return path;\n"
    "} };\n"
    "EOF\n"
    'echo invoked >> "$prefix/npm-calls"\n',
    encoding="utf-8",
  )
  npm.chmod(0o755)
  cache = tmp_path / "runtime cache"
  env = {
    **os.environ,
    "PATH": f"{fake_bin}:{os.environ['PATH']}",
    "STEER_CHROMIUM_DIR": str(cache),
  }
  for _ in range(2):
    result = subprocess.run(
      [str(SCRIPT)], env=env, capture_output=True, text=True, check=True
    )
    paths = dict(line.split("=", 1) for line in result.stdout.strip().splitlines())
    assert Path(paths["CHROMIUM_BIN"]).is_file()
    assert Path(paths["CHROMIUM_LIB"]).is_dir()
    assert Path(paths["CHROMIUM_FONTS"]).is_dir()
  assert (cache / "npm-calls").read_text().splitlines() == ["invoked"]
