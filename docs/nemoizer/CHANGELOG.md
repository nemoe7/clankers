<!-- nonemo: NMO100 -->

# Changelog

The format follows [Keep a Changelog](https://keepachangelog.com/), and this module uses [Semantic Versioning](https://semver.org/).

This log has no Unreleased section.

## [0.1.13]

### Added

- `scripts/prose.py` (`_iter_js_masked_templates`, `js_ui_prose_spans`) and `scripts/nemoize.py` (`_source_prose`): Extract visible HTML template-literal prose from `.js` and `.mjs` files and flag prose dashes (`HMN905`) in JavaScript UI strings.

### Changed

- `SKILL.md`: Require comments and docstrings to use the established contract when complexity requires them.

## [0.1.12]

### Added

- `scripts/nemoize.py` (`_match_glob`, `skipped`): Support `/**/` zero-or-more directory globs and `!pattern` negation rules in `exclude`, `extend-exclude`, and `--ignore`.
