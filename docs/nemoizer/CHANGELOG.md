<!-- nonemo: NMO100 -->

# Changelog

The format follows [Keep a Changelog](https://keepachangelog.com/), and this module uses [Semantic Versioning](https://semver.org/).

This log has no Unreleased section.

## [0.1.18]

### Changed

- Split `scripts/nemoize.py` into single-purpose modules, and keep the command line in `nemoize.py`.
- Build the rule ID tables, rule descriptions, advisory status, and line scope from one rule registry.

### Fixed

- Keep the line endings of each file that `--format` rewrites.
- Count CRLF as one line break in JavaScript comment and test parsing on Windows.
- Load the discovered config in `prose` and `review-tests`, so their exclusions apply.

### Removed

- Remove the inlined `markers.py` copy from `nemoize.py`.

## [0.1.17]

### Changed

- Name the default scan "prose and test candidates" in the command-line help.

### Removed

- Retire the pick-to-select rotation.

## [0.1.16]

### Added

- Detect local prose expectations and alias chains in Python test functions and JavaScript test callbacks. Exclude supplied inputs, dynamic values, and production constants.

- Add advisory NMT400 for direct numeric copies of statically resolved Python production settings, with source citations and conservative mutation exclusions.

- Add advisory NMT300 for test sleeps, excluding bounded polling, fake timers, and Playwright timeout helpers.

### Changed

- Document measurement property, static-key, and pixel-string coverage, with explicit-input exemptions.

- Document NMT200's zero-value exemption and add explicit coverage.
- Require explicit user authorization for every new suppression, and reuse production output values in assertion guidance.

### Fixed

- Detect pixel strings, static measurement lookups, chained reads, and JavaScript `toBe` and `toHaveCSS` assertions.
- Exempt measurements explicitly set to the asserted value in the same test.
- Reconfigure `markers.py` CLI output streams to UTF-8 on Windows consoles.
- Align rotation guidance with explicit forms and current mappings.

### Removed

- Remove self-maintenance instructions from the usage skill.

## [0.1.15]

### Added

- Add `-v` and `--verbose` logging for file scans and worker start or completion (`scripts/nemoize.py`).

### Fixed

- Preserve rotation inflections and protect fenced code, URLs, and code tokens.
- Scan table prose and wrapped pull requests, and expand verb name contexts.
- Reject missing targets before scanning or formatting.
- Let timed-out workers exit without blocking the process.
- Cover `naming` and restricted `named` verb forms in `NMO901`.

## [0.1.14]

### Fixed

- Scan files in parallel with a 10 second per-file cap, report skipped files, and print pytest-style progress dots (`scripts/nemoize.py`).
- Feed Node subprocesses UTF-8 and cap each call at 10 seconds (`scripts/prose.py`).
- Match exclusion patterns against the config root so a subdirectory target keeps them (`scripts/nemoize.py`).

## [0.1.13]

### Added

- `scripts/prose.py` (`_iter_js_masked_templates`, `js_ui_prose_spans`) and `scripts/nemoize.py` (`_source_prose`): Extract visible HTML template-literal prose from `.js` and `.mjs` files and flag prose dashes (`HMN905`) in JavaScript UI strings.

### Changed

- `SKILL.md`: Require comments and docstrings to use the established contract when complexity requires them.

## [0.1.12]

### Added

- `scripts/nemoize.py` (`_match_glob`, `skipped`): Support `/**/` zero-or-more directory globs and `!pattern` negation rules in `exclude`, `extend-exclude`, and `--ignore`.
