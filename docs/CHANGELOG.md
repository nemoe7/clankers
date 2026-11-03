<!-- nonemo: NMO100 -->

# Changelog

The format follows [Keep a Changelog](https://keepachangelog.com/). This log uses `YYYY-MM-DD` dates as versions instead of [Semantic Versioning](https://semver.org/).

Keep one entry per date and extend the open date. This log has no Unreleased section.

## 2026-11-03

### Changed

#### maintenance

- Print each failed check's findings under its FAIL line. Rename the STE lint check to Nemoize and its constants (`maintenance/check.py`).
- Decode every `check.py` subprocess as UTF-8. Compare the markdownlint scope on POSIX separators so the check holds on Windows (`maintenance/check.py`).
- Nemoizer scans files in parallel with a 10 second per-file cap, reports skipped files, and prints progress dots (`skills/nemoizer/scripts/nemoize.py`, `skills/nemoizer/scripts/prose.py`).
- Feed Node subprocesses UTF-8 and cap each call at 10 seconds (`skills/nemoizer/scripts/prose.py`).
- Match nemoizer exclusion patterns against the config root so a subdirectory target keeps them (`skills/nemoizer/scripts/nemoize.py`).
- Exclude the retired arena-skill trees, its tests, prompt-fill text, archive changelog, and markdown outside READMEs under automations, system-prompts, and gpt-plugins (`pyproject.toml`).
- Remove the `--ste` flag from `check.py`. Nemoize runs as part of normal validation (`maintenance/check.py`, `maintenance/extract_prose.py`).
- Drop `.agents/skills/asd-ste100` from vendored prose extraction targets (`maintenance/extract_prose.py`).

#### skills

- Remove vendored `asd-ste100` skill (`.agents/skills/asd-ste100/`).
- Remove vendored `humanizer` skill (`.agents/skills/humanizer/`).
- Remove `asd-ste100` row from vendored skills table (`.agents/skills/README.md`).
- Remove ASD-STE100 and Humanizer rule references from nemoizer description (`docs/gpt-plugins/README.md`).

#### system-prompts

- Reword nemoizer-only writing style line. Drop ASD-STE100-style controlled English (`system-prompts/NEMOGPT.md`, `system-prompts/refs/NEMOGPT.md`, `system-prompts/wenyan/NEMOGPT.md`).

#### automations

- Drop the ASD-STE100 report language line (`automations/DAILIES.md`).

## 2026-11-01

### Changed

#### maintenance

- Seed finished steering demo tasks as historical rows while live task creation requires phase completion checks (`demo-arena-steer.py`).
- Route steering source changes and the task-chain regression through Preview CI tests (`workflows/changed_paths.py`).

## 2026-10-31

### Changed

#### maintenance

- Reset the running demo to sample data without restarting its server. Preserve survey results and the reset action across reloads (`demo-arena-steer.py`).
- Route demo changes, reset tests, and connection tests to the Preview test group (`workflows/changed_paths.py`).
- Assign the composer parity browser test to the Preview test group (`workflows/changed_paths.py`).
- Assign the message retry browser test to the Preview test group (`workflows/changed_paths.py`).
- Assign the browser violation regression to the Preview test group (`workflows/changed_paths.py`).
- Ignore `.agents/` during Gitleaks scans while retaining the default rules (`.gitleaks.toml`).
- Move the configurable steering demo out of the shipped skill (`demo-arena-steer.py`).

## 2026-10-30

### Changed

#### maintenance

- Assign the message scroll-fade tests to the Preview test group (`workflows/changed_paths.py`).
- Exclude vendored `skills/arena-steering/assets/` bundles and licenses from repository prose extraction (`check.py`, `extract_prose.py`).

#### rules

- Require code and configuration comments to use the established contract (`CORE.md`, `ARENA.md`, `CHATGPT-MORE.txt`).
- Require reporting uncontracted shipped changes (`ARENA.md`).

## 2026-10-29

### Changed

#### maintenance

- Route the `Preview` test group to `tests/skills/arena-steering/` and remove legacy `tests/skills/arena-skill/` test references (`workflows/changed_paths.py`, `README.md`).
