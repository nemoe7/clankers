<!-- nonemo: NMO100 -->

# Changelog

The format follows [Keep a Changelog](https://keepachangelog.com/). This log uses `YYYY-MM-DD` dates as versions instead of [Semantic Versioning](https://semver.org/).

Keep one entry per date and extend the open date. This log has no Unreleased section.

## 2026-11-09

### Changed

#### rules

- Keep comments and docstrings rare and factual, limited to non-obvious external constraints and business invariants.
- Require the squash skill for refs-to-live rule amendments.
- Group Arena clauses by domain and place the bible definition before its first reference.

### Removed

#### rules

- Remove the retired ntfy restoration rule and both retired question-tool channel cases.

### Fixed

#### maintenance

- Retain the local CI preparation-action reference until the released syntax validator supports self-repository references.

- Register split Steering browser suites with the CI module selector so ownership checks and Preview test selection include them.

- Check PR versions against the repo default branch, retaining exactly one version bump and the original PR commit range.

## 2026-11-07

### Removed

#### maintenance

- Remove the Gitleaks workflow and configuration.

### Changed

#### arena-steering

- Preserve typed message metadata on retry-token saves.
- Mark dead detached runs as failed so their task gates can recover.
- Preserve staged uploads when verifying published reports.
- Delay initial hover tooltips, with immediate keyboard focus and a brief rapid-switch window.

#### rules

- Rewrite `rules/README.md` and `rules/wenyan/README.md` for human readers.
- Specify the stale-report reminder command (`rules/refs/ARENA.md`, `rules/ARENA.md`, `ARENA.md`).
- Remove the code-scanning requirement (`rules/refs/ARENA.md`, `rules/ARENA.md`, `ARENA.md`).

#### system-prompts

- Rewrite `system-prompts/README.md` and `system-prompts/wenyan/README.md` in human-facing prose.

#### maintenance

- Parse README budgets without `markdown-it-py`, drop retired group budgets and `maintenance/javascript-comments.cjs`, and refresh `maintenance/README.md`.
- Rewrite `maintenance/README.md` for human maintainers and replace retired `arena-preview` hook tables with `steer pre`.
- Archive the retired minification workflow check and its tests under `docs/archive/arena-skill/`.
- Exclude minified, archived, and vendored material from the root Nemoizer scan.
- Filter CodeQL language scans conservatively and restrict dependency reviews to dependency and workflow changes.
- Group plugin release and rules publication into separate credential-isolated jobs.
- Validate and sync distribution targets in one job, preserving remote reconciliation.
- Group read-only CI checks into one job, including PR plugin validation, and reuse successful input digests.
- Guard the archived Arena proxy tests against returning to the active test matrix.
- Refresh Ponytail and its audit skill from upstream `96608e0`, keeping only those two skills.
- Add pass-ledger collection and recording primitives for CI surfaces (`maintenance/workflows/changed_paths.py`).
- Run workflow lint, security audit, and contract checks in one job (`.github/workflows/workflow-security.yml`).
- Ignore seven reviewed historical test-fixture findings in Gitleaks (`.gitleaksignore`).
- Replace the root Arena symlink with a byte-identical regular copy (`ARENA.md`, `maintenance/check.py`).
- Expand Markdownlint coverage and remove the fixed scope guard (`.markdownlint-cli2.jsonc`, `maintenance/check.py`).

### Fixed

#### maintenance

- Decode child-process text pipes as strict UTF-8, reconfigure CLI streams for Windows consoles, and pass explicit `encoding="utf-8"` across test suites.
- Update the seeded `S2E5P` survey payload in `maintenance/demo-arena-steer.py` to use `first_name` and `last_name`.

## 2026-11-06

### Changed

#### maintenance

- Route Preview checks to consolidated Steering test modules (`maintenance/workflows/changed_paths.py`).
- Route test checks to mirrored modules and split userscript suites (`maintenance/workflows/changed_paths.py`).
- Time skills, links, budgets, parity, and paths validation as separate stages (`maintenance/check.py`).
- Run one Nemoizer stage using the root configuration instead of a separate Markdown allowlist (`maintenance/check.py`, `nemoizer.toml`).

#### rules

- Place non-trivial checks in mirrored module tests (`rules/refs/CORE.md`, `rules/refs/ARENA.md`, `rules/refs/CHATGPT.txt`, `rules/CORE.md`, `rules/ARENA.md`, `rules/CHATGPT-MORE.txt`, `rules/wenyan/CHATGPT-MORE.txt`).
- Distinguish stderr read reminders from other action reminders (`rules/refs/ARENA.md`, `rules/ARENA.md`).
- Limit inbox reads to stderr-reported unacknowledged messages (`rules/refs/ARENA.md`, `rules/ARENA.md`, `ARENA.md`).
- Forbid Mermaid in chat and require it everywhere else (`rules/refs/ARENA.md`, `rules/ARENA.md`).
- Protect running Steering previews and require recommended report options (`rules/refs/ARENA.md`, `rules/ARENA.md`).
- Require self-contained handoffs (`rules/refs/ARENA.md`, `rules/ARENA.md`).
- Remove the deliverable-open requirement and publish handoffs as unfielded Steering reports (`rules/refs/ARENA.md`, `rules/ARENA.md`).
- Set the final poll Bash timeout to 1800 seconds and prohibit shell timeouts (`rules/refs/ARENA.md`, `rules/ARENA.md`).
- Remove the violation-notice trigger for full bible reads (`rules/refs/ARENA.md`, `rules/ARENA.md`).
- Route turn start, task ordering, Steering procedures, and job-log lookup through the installed skill. Use v2 `steer` commands (`rules/refs/ARENA.md`, `rules/ARENA.md`, `ARENA.md`).
- Split the contract rules and keep the no-commit rule free of storage-location details (`rules/refs/ARENA.md`, `rules/ARENA.md`, `ARENA.md`).
- After one diagnosis, resume unblocked work, use a worktree for frozen files, and recheck logs only after meaningful progress (`rules/refs/ARENA.md`, `rules/ARENA.md`, `ARENA.md`).

## 2026-11-05

### Changed

#### rules

- Replace v1 steering references with v2, require six-call bible rechecks, and use v2 for all reports (`rules/refs/ARENA.md`, `rules/ARENA.md`, `ARENA.md`, `AGENTS.md`).

#### maintenance

- Log Nemoize child commands and exit codes during repo validation (`maintenance/check.py`).
- Add optional per-file scan and worker progress logging to Nemoizer (`skills/nemoizer/scripts/nemoize.py`).

## 2026-11-04

### Changed

#### rules

- Require substantive answers to delivered messages in their own acknowledgement before chat (`rules/refs/ARENA.md`, `rules/ARENA.md`, `ARENA.md`).
- Remove the short-report-to-chat exception (`AGENTS.md`).

### Fixed

#### maintenance

- Assign blocked-Bash dismissal and task-priority regressions to the Preview test group (`workflows/changed_paths.py`).

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
- Remove the obsolete `--ste` CI step because repo validation checks covered docs (`.github/workflows/ci.yml`).
- Use fenced clause diff blocks instead of proposal tables (`maintenance/amendment-template.md`, `AGENTS.md`).

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
