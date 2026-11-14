<!-- nonemo: NMO100 -->

# Changelog

The format follows [Keep a Changelog](https://keepachangelog.com/), and this module uses [Semantic Versioning](https://semver.org/).

This log has no Unreleased section.

## [0.2.2]

### Changed

- **Chromium lookup**: Resolve `-x`, then the Playwright default browser, then `$CHROMIUM_BIN`, and drop the PATH scan for `chromium`, `chromium-browser`, and `google-chrome`.
- **Playwright default on Windows**: Accept `.exe`, `.cmd`, and `.bat` siblings when the reported path has no extension.

## [0.2.1]

### Added

- **Stylesheet-driven design boards**: Resolve semantic colors, fonts, and radii from configured `:root` and dark-scheme stylesheet tokens for browser and bitmap output.
- **Routed design boards**: Add `orthogonal`, `scurve`, and `straight` arrows, custom canvases, responsive captures, and detailed anatomy, style-guide, and focus presets.
- **Visual examples**: Add eight dark-mode examples for design records, inline markers, goal-based flows, overlay clipping, offline fonts, and scroll behavior.

### Changed

- Remove the relative-timestamp recipe requirement for tabular numerals.

- Remove timestamp hover-title requirements and the sample title assignment, retaining relative text and boundary timers.
- **Annotation and board specs**: Require TOML inputs and preserve configurable HTML/JavaScript icon-table extraction through `[icons].file` and `table`.
- **Visual examples**: Regenerate 48 PNGs and the motion GIF with dark-mode `Pass`/`Fail` pairs. Rename rule images and correct example links.

## [0.2.0]

### Added

- **Unified Python CLI**: Consolidate `nuu` onto nine subcommands (`audit`, `walk`, `measure`, `annotate`, `board`, `lint`, `collect`, `search`, `doctor`). Use `playwright>=1.49`, Markdown output, and exit codes `0`..`3`.
- **Configuration v2**: Add `[paths]`, `[fonts]`, `[annotate]`, `[measure]`, `[board]`, `[audit]`, `[checks.severity]`, and `[[assets]]` with `<path>:<line>:<col>` parse/schema errors and unknown-key warnings.
- **Marker collector**: Scan `nonuu:`, `nuu-deviation:`, and `nuurecipe:` comments across web and Python sources, flagging unknown recipe slugs (`RCP001`).
- **Visual redline and drop-ray measurement**: Add live DevTools tints, Figma guides (`--to`), drop-rays (`-d`), and `3:1` redline contrast fallback (`#ff3366 -> #00e5ff -> #111827`).
- **Design document v2 and reference sync**: Adopt the six-section `docs/design.md` v2 template, 49-rule CLI reference, 42-verb `walk` reference, and consolidated 12-recipe index.

### Changed

- **Clause rules**: Require icon line-height match (`ICN102`), slow-network writes (`ACC207`), `[paths].doc`, `nuurecipe:`, and zero `Lorem ipsum` (`HRC203`).
- **Browser and renderer lookup**: Replace `$CHROMIUM_PATH` and `$NUU_CONFIG` with `-x` -> `$CHROMIUM_BIN` -> `PATH`, `$CHROMIUM_LIB`, `$CHROMIUM_FONTS`, and `$NUU_RENDERER` (`auto`, `chromium`, `bitmap`).
- **Severity model**: Restrict rule severities to `"error"` and `"review"` so `[checks.severity]` overrides control `lint` and `audit` exit status.

### Removed

- **Legacy Node and JSON surfaces**: Remove `browser.cjs`, `uiux.py`, `nuu extract`, legacy `NU*` rule aliases, `-T design`, and JSON CLI inputs/outputs.

## [0.1.73]

### Added

- **Completed-action feedback**: Review changed names and status text after each live-audit click. Flag missing feedback after the flow timeout.

## [0.1.72]

### Added

- **Live overlay inspection**: Check visible overlay text, controls, clipping, occlusion, and tooltip/popover backgrounds at each viewport. Replay audit flows across viewports, leaving reachable scroll content and optional page-wide overlaps separate.

## [0.1.71]

### Changed

- **Scrollbar alignment**: Match arena-steering's `15px` transparent track, `margin: 8px 0`, and `1px` transparent thumb border. Keep `9999px` pill thumbs, `var(--scrollbar-thumb)` colors, no arrows, keyboard-nav hover highlights, and global `*` Firefox fallback.
- **Scrollbar measurement**: Exempt `::-webkit-scrollbar-*` selectors from SPC001 and SPC002 checks.

## [0.1.70]

### Added

- **Dialog action visibility (`ACC203`)**: Flag action rows outside the visible dialog or viewport while allowing the dialog body to scroll.

### Fixed

- **Browser engine discovery**: Ignore unsupported private Playwright engines when choosing a public browser.

## [0.1.69]

### Added

- **Equal-size button groups (`HRC102`)**: Require buttons in the same group to share identical width and height.
- **UI/UX guideline checks**: Add `--size-32` (`32px`) and check alignment, card hierarchy, proximity, padding, italic body, and button fills.

### Changed

- **2026-10-30, study-backed guidance**: Update the principles, type defaults, examples, and checks.
- **2026-10-30, measurement policy**: Make `TYP101` and `TYP201` review findings by default, with opt-in errors.

- **Semantic rule IDs**: Reorganize rule codes into `TYP`, `SPC`, `HRC`, `ACC`, `ICN`, `DOC`, and `RUN` with `nonuu:` alias support.
- **CLI consolidation**: Consolidate `nuu` into 7 subcommands (`lint`, `audit`, `walk`, `board`, `annotate`, `search`, `doctor`) and fold static checks into `lint`.
- **Audit report workflow**: Use `## Findings` and `## Visual Judgements` headings and pair open findings with cropped 2-column `nuu board` panels.
- **Recipes**: Schedule relative timestamps at unit boundaries.
- **Proportional spacing**: Match sibling gaps across axes within a group and use Clause 6/21 clearance beside scroll fades.
- **Recipes**: Add `--scrollbar-carve` and `28px`/`36px` fade ramp.
- **Recipes**: Extend `#history` past `.card.compose` to `100%`.
- **Recipes**: Add `data-loading="done"` completion fade-out on `var(--accent)`.
