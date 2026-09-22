# Chromium for E2E tests

The sandbox blocks the Playwright browser CDN, the Google CDNs and `apt`. No usual Chromium install path works here. `@sparticuz/chromium` from npm does, because npm stays reachable.

## Install

```bash
npm install @sparticuz/chromium
```

The package ships four brotli archives. Inflate them with the package's own helper:

| Archive | Destination |
| --- | --- |
| binary | `/tmp/chromium` |
| libraries | `/tmp/al2023/lib` |
| fonts | `/tmp/fonts` |
| SwiftShader | `/tmp` |

## Run

The E2E suite reads `DAEDALUS_E2E_CHROMIUM`, an escape hatch that names a foreign binary rather than a Playwright-managed one. Point it at the inflated binary, and set the two variables the bundled parts need:

```bash
export DAEDALUS_E2E_CHROMIUM=/tmp/chromium
export LD_LIBRARY_PATH=/tmp/al2023/lib:/tmp
export VK_ICD_FILENAMES=/tmp/vk_swiftshader_icd.json
```

`LD_LIBRARY_PATH` must list both directories. `VK_ICD_FILENAMES` gives SwiftShader its ICD file, and the software renderer does not start without it.

## Known gap

The sandbox has no system fontconfig. One test therefore fails locally even on correct code:

`test_the_pool_column_fits_the_longest_pool_name`

That test measures a rendered column against a font the system cannot supply. Injecting a monospace TTF through `@font-face` made it pass, which proves the assertion correct and the environment short. The other 51 assertions are font-independent and pass without it.
