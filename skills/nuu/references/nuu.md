# `nuu` CLI Reference

`scripts/nuu` (`scripts/uiux.py`) runs UI/UX audits, proposals, records, measurements, and annotations.

| Subcommand | Purpose | Arguments and Shorthands |
| --- | --- | --- |
| `search` | Search vendored catalogs | `<query>`, `-d, --dataset <name>`, `-s, --stack <name>`, `-n, --limit <n>`, `-j, --json` |
| `system` | Generate a five-part system proposal | `<query>`, `-p, --project <name>`, `-s, --stack <name>`, `-w, --write [path]`, `-f, --force`, `-j, --json` |
| `record` | Initialize or check `docs/design.md` | `<init\|check>`, `-r, --root <path>`, `-p, --path <rel>`, `-t, --title <text>`, `-s, --status <state>`, `-f, --force`, `-j, --json` |
| `asset` | Fetch, verify, or record licensed assets | `<fetch\|verify\|record>`, `-r, --root <path>`, `-u, --url <https-url>`, `-o, --output <rel>`, `-s, --sha256 <hex>`, `-l, --license <spdx>`, `-a, --attribution <text>`, `-p, --purpose <text>`, `-d, --design-doc <rel>`, `-f, --force`, `-j, --json` |
| `extract` | Extract candidate tokens | `-r, --root <path>`, `-m, --measure <path>`, `-o, --output <rel>`, `-f, --force`, `-j, --json` |
| `check` | Check measure JSON against the sheet | `<report>`, `-s, --sheet <path>`, `-g, --scale <px>`, `-j, --json` |
| `ruler` | Measure pixel gap between two `x,y` guides | `-f, --from <x,y>`, `-t, --to <x,y>`, `-g, --scale <px>`, `-j, --json` |
| `annotate` | Render overlays on a PNG screenshot | `-i, --input <png>`, `-o, --output <png>`, `-b, --box <spec>`, `-l, --label <spec>`, `-a, --arrow <spec>`, `-c, --callout <spec>`, `-s, --spec <json>`, `-j, --json` |
| `audit` | Run source, measure, flow, and a11y checks | `-r, --root <path>`, `-u, --url <url>`, `-s, --sheet <path>`, `-m, --measure <path>`, `-f, --flows <json>`, `-c, --change <spec>`, `-A, --allow-live-edits`, `-R, --ready <selector>`, `-o, --out <dir>`, `-j, --json` |
