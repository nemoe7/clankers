<!-- nonemo: NMO100 -->

# Changelog

The format follows [Keep a Changelog](https://keepachangelog.com/). This log uses `YYYY-MM-DD` dates as versions instead of [Semantic Versioning](https://semver.org/).

Keep one entry per date and extend the open date. This log has no Unreleased section.

## 2026-10-30

### Changed

#### maintenance

- Exclude vendored `skills/arena-steering/assets/` bundles and licenses from repository prose extraction (`check.py`, `extract_prose.py`).

#### rules

- Require code and configuration comments to use the established contract (`CORE.md`, `ARENA.md`, `CHATGPT-MORE.txt`).

## 2026-10-29

### Changed

#### maintenance

- Route the `Preview` test group to `tests/skills/arena-steering/` and remove legacy `tests/skills/arena-skill/` test references (`workflows/changed_paths.py`, `README.md`).
