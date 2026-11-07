# nuu Agent Rules

- Render samples before changing `nuu`: show before-and-after renders for every addition or change, and render a range of options for any value change.
- Render example images, sample boards (`nuu board`), and browser walks (`nuu walk`) in dark mode (`color-scheme: dark`, `data-theme="dark"`) by default.
- Pass `-c <nuu.toml>`, run scripted walks via `nuu walk <walk.py>` with `w.view("<name>")`, add `-W` when wireframe overlays are needed, and resolve Chromium via `-x` or `$CHROMIUM_BIN`.
- Keep `skills/refs/nuu/` and `skills/nuu/` in sync, and bump `pyproject.toml` in both directories one step above `main` per PR.
