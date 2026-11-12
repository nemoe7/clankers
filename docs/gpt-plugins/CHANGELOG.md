<!-- nonemo: NMO100 -->

# Changelog

The format follows [Keep a Changelog](https://keepachangelog.com/), and this module uses [Semantic Versioning](https://semver.org/).

This log has no Unreleased section.

## [1.10.34]

### Changed

- `skills/nemoizer/scripts/`: Split `nemoize.py` into single-purpose modules with the same command line.

### Fixed

- `skills/nemoizer/scripts/`: Keep CRLF line endings in `--format` output and in JavaScript parsing on Windows.
- `skills/nemoizer/scripts/nemoize.py`: Load the discovered config in `prose` and `review-tests`.

## [1.10.33]

### Removed

- `skills/nemoizer/scripts/nemoize.py`: Retire the pick-to-select rotation.

## [1.10.32]

### Changed

- Split the repository-discovery bullet and the cost-comparison bullet into one action each.
- Rewrite `docs/gpt-plugins/README.md` in human-facing prose and drop the stale turn receipt.

### Removed

- Remove unshipped imperative `README.md` stubs under `gpt-plugins/skills/gpt-*/`.

### Fixed

- Align bundled nemoizer rotation guidance with the current implementation.
- Remove self-maintenance instructions from the bundled nemoizer skill.

## [1.10.31]

### Added

- `skills/nemoizer/scripts/nemoize.py`: Add `-v` and `--verbose` logging for file scans and worker start or completion.

## [1.10.30]

### Fixed

- `skills/nemoizer/scripts/`: Bound source scans and subprocesses, force UTF-8 output, and honor repository-root exclusions.

## [1.10.29]

### Added

- `skills/nemoizer/scripts/prose.py` (`_iter_js_masked_templates`, `js_ui_prose_spans`) and `skills/nemoizer/scripts/nemoize.py` (`_source_prose`): Extract visible HTML template-literal prose from `.js` and `.mjs` files and flag prose dashes (`HMN905`) in JavaScript UI strings.

### Changed

- `skills/nemoizer/SKILL.md`: Require comments and docstrings to use the established contract when complexity requires them.

## [1.10.28]

### Added

- `skills/nemoizer/scripts/nemoize.py` (`_match_glob`, `skipped`): Support `/**/` zero-or-more directory globs and `!pattern` negation rules in `exclude`, `extend-exclude`, and `--ignore`.
