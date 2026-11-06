<!-- nonemo: NMO100 -->

# Changelog

The format follows [Keep a Changelog](https://keepachangelog.com/), and this module uses [Semantic Versioning](https://semver.org/).

This log has no Unreleased section.

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
