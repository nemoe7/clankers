# arena.md — research: downloading Chromium for Playwright

Task: find a way to download Chromium for Playwright testing (suggested route: npm).
Date: 2026-09-19. Verified live in-sandbox (node v22.22.3, npm 10.9.8, Playwright 1.63.0).

## Answer

The npm route works. The npm package only ships the driver; the Chromium binary is a
separate ~170 MB download from Microsoft's CDN, not from the npm registry.

Two npm-based routes:

1. **Auto-download during `npm install`** (pure npm, the suggested route):

   ```bash
   npm i -D @playwright/browser-chromium
   ```

   `@playwright/browser-chromium` is the only Playwright package with an npm `install`
   script, so the browser downloads as part of the package install.
   Siblings: `@playwright/browser-firefox`, `@playwright/browser-webkit`.

2. **Driver via npm, browser via CLI** (standard route):

   ```bash
   npm i -D playwright        # or: @playwright/test
   npx playwright install chromium
   ```

   On Linux add `--with-deps` so OS libraries are apt-installed too:

   ```bash
   npx playwright install --with-deps chromium
   ```

## Verified behavior (this sandbox, 2026-09-19)

- `npm i @playwright/browser-chromium` fetched `@playwright/browser-chromium@1.63.0` +
  `playwright-core@1.63.0` from registry.npmjs.org normally.
- Its postinstall hook (`node install.js`) then downloaded the binary:

  ```text
  Downloading Chrome for Testing 153.0.8010.12 (playwright chromium v1243) from
  https://cdn.playwright.dev/builds/cft/153.0.8010.12/linux64/chrome-linux64.zip
  ```

  The binary is a Chrome-for-Testing build, fetched from `cdn.playwright.dev` — a
  different egress path than the npm registry.
- This sandbox only permits egress to the npm registry, so the download failed
  (ECONNRESET during TLS) and **npm rolled back the entire install**: no
  `node_modules` left behind, exit code 1, only an empty `~/.cache/ms-playwright/.links`
  remained.
  Consequence: in a firewalled environment the CDN (or a mirror) is the path to allow,
  and a failure there fails the whole `npm install`, not just a postinstall warning.
- Confirmed via `npm view <pkg>@1.63.0 scripts`: only the `@playwright/browser-*` helper
  packages carry an install script. `playwright`, `playwright-core`, and `@playwright/test`
  have none — `npm i playwright` alone never downloads a browser.

## Where the binary lands

One directory per build under the OS cache root:

| OS      | Default path |
| ------- | ------------------------------------------------- |
| Linux   | `~/.cache/ms-playwright` |
| macOS   | `~/Library/Caches/ms-playwright` |
| Windows | `%USERPROFILE%\AppData\Local\ms-playwright` |

- Sizes (official figures): chromium ~281 MB, firefox ~187 MB, webkit ~180 MB.
- `PLAYWRIGHT_BROWSERS_PATH=<dir>` → custom location; `=0` → hermetic install into
  `node_modules/playwright-core/.local-browsers` (also the search path at run time).
- Playwright garbage-collects old builds once no client needs them; opt out with
  `PLAYWRIGHT_SKIP_BROWSER_GC=1` or `npx playwright install --no-remove`.
- Inspect/remove: `npx playwright install --list`, `npx playwright uninstall [--all]`.
- Browser builds are pinned to the Playwright version (1.63.0 → CFT 153.0.8010.12,
  chromium build v1243 here). After upgrading Playwright, re-run `npx playwright install`.

## Knobs for restricted or mirrored networks

| Variable | Effect |
| ------------------------------------ | ------------------------------------------------ |
| `PLAYWRIGHT_DOWNLOAD_HOST` | Download host (internal artifact repo mirror) |
| `PLAYWRIGHT_CHROMIUM_DOWNLOAD_HOST` | Per-browser host; wins over the general one |
| `HTTPS_PROXY` | Download through a proxy |
| `NODE_EXTRA_CA_CERTS` | Custom root CA for intercepting proxies |
| `PLAYWRIGHT_DOWNLOAD_CONNECTION_TIMEOUT` | Connection timeout in ms for slow CDNs |
| `PLAYWRIGHT_BROWSERS_PATH` | Install/search location; `0` = project-local |
| `PLAYWRIGHT_SKIP_BROWSER_GC` | `1` = never auto-delete old builds |

Useful install flags: `--only-shell` (headless shell only; skip full Chromium),
`--no-shell` (full Chromium only, for `channel: 'chromium'` new-headless mode),
`--with-deps` (OS libraries via the system package manager, Linux).
Note: default headless runs the separate `chromium-headless-shell` build, so a headless
CI can use `--only-shell` to halve the download.

## CI / no general egress

- Docker image with browsers preinstalled: `mcr.microsoft.com/playwright:v1.63.0-noble`
  (tag matches the Playwright version) — the standard way to avoid CDN downloads in CI.
- GitHub Actions recipe (official): `npm ci` → `npx playwright install --with-deps`
  → `npx playwright test`.

## Sources

- playwright.dev/docs/browsers — install, proxies, mirror hosts, binary management; read 2026-09-19
- playwright.dev/docs/ci — Docker image, GitHub Actions recipe; read 2026-09-19
- playwright.dev/docs/library — `@playwright/browser-*` helper packages
- Live run in-sandbox: `npm i @playwright/browser-chromium@1.63.0`; npm debug log
  `/home/user/.npm/_logs/2026-09-19T16_34_05_745Z-debug-0.log`
