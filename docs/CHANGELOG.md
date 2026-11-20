<!-- nonemo: NMO100 -->

# Changelog

The format follows [Keep a Changelog](https://keepachangelog.com/). This log uses `YYYY-MM-DD` dates as versions instead of [Semantic Versioning](https://semver.org/).

Keep one entry per date and extend the open date. This log has no Unreleased section.

## 2026-11-20

### Added

#### rules

- Add a Kilo rule stating Python UTF-8 mode is enabled (`PYTHONUTF8=1`), so Python child processes emit UTF-8 by default.

### Changed

#### rules

- Require full trust of headroom elision.
- Ban re-running, re-reading, Grep, re-derivation, and every other workaround that seeks to see or verify elided content.
- Ban citing any reconstruction as evidence.
- Scope `kilo_memory_save` to durable project facts (decisions, constraints, conventions, corrections) and explicitly exclude environment facts that break when the environment changes.
- Delete the plan folder instead of the plan files after Plan mode.
- Squash live clause files whose clauses still matched refs word-for-word. Every clause, keyword count, and line count survives, and each touched budget shrinks.

#### checks

- Print one `{step}: {result} {time}` verdict line per stage and a `check: pass` or `check: fail` summary, replacing the stage header and problem-count lines.
- Group parity warnings per file instead of one line per clause. Each file lists sections and line numbers, `*` marks a reworded clause.
- Drop the nemoize command echo and print the prose linter's own output instead.

#### system prompts

- Squash the live prompt and its wenyan copy where clauses still matched refs, including worked examples. Meaning, quoted strings, and line pairing stay intact.

## 2026-11-15

### Added

#### checks

- Add a hard-rule keyword parity stage: flag `ALWAYS`, `MUST`, `NEVER`, and `Prefer` dropped from live or added against refs. Compare clause lines only when line counts pair, skip headers and code, replace soft `do not` with `NEVER`.
- Require equal refs and live line counts for system prompts and skill files, so compression keeps every clause instead of merging or dropping lines.
- Warn when a live clause matches its refs clause exactly or rewords at the same token count. Missed compression and non-shrinking rewrites then surface without failing the check.

#### rules

- Add a Kilo rule stating headroom elides repeated read and tool output into pointer lines, with recovery via the cited message and Grep.
- Add a Kilo rule trusting the elision: matching head text proves repetition, so agents never re-run a command or read to see elided content.

### Fixed

#### checks

- Align hard-rule keywords between refs baselines and live copies across rules, system prompts, and skills. Replace soft `do not` negation with `NEVER` in clause lines, and re-measure the README table.
- Restore the `checks` logger's prior level after parity warning capture, so shared-logger tests pass regardless of test order or worker scheduling.

### Changed

#### checks

- Fold the parity stage into one `check_parity` entry point over a shared line comparer. Rename the skill-refs check to skills, match prompt sections by heading, swap the byte cap for per-clause tokens, keep the wenyan keyword skip.

#### docs

- Restructure root AGENTS.md to agents.md format, dropping environment-specific facts, redundant config redefinitions, and rot-prone specifics. Split Rules, System Prompts, GPT Plugins, Userscripts, Skills into own overview sections.

#### rules

- Drop `plan_exit` from kilo plan agent. Use `submit_plan` only.
- Add global pre-commit validation rule to CORE.md: run all repo gates before every commit.
- Extend ARENA.md pre-commit validation to commit time. Add paired ChatGPT clause.
- Strengthen TODO discipline: KILO.md, plan/code/debug overrides require `todowrite`/`todoread` per step. Completion forbidden before checks pass.
- Mirror wenyan CHATGPT-MORE.txt with compressed commit clause.

## 2026-11-14

### Changed

#### rules

- Delete the plan files instead of the plan folder after Plan mode.
- Require setting the TODO list after plan approval.
- Require switching off `main` before editing and committing on that branch.
- Require updating the TODO list after each task in the code and debug overrides.
- Create a branch only when on the default branch.
- Rewrite the agent-rules writing standard as rules an agent can follow. Keep dated research in section 0.
- Rewrite the system-prompt writing standard with the same rule structure. Add the parts only system prompts need: identity, environment, tools, subagents, memory, skills, safety, examples.
- Restore the constitution requirements in the agent-rules standard and restate section 0 as a dated model reference.
- Retarget the agent-rules standard to harness-installed rules. Drop project-fact sections from the skeleton and keep behavioral contracts.
- Fold precedence into `Use` in the agent-rules skeleton and drop the one-line requirement on it.
- Overlays inherit skeleton from base. AGENTS.md points to guidelines instead of repeating it.

#### maintenance

- Bump ruff to 0.17.5 and reformat config lists (pyproject.toml, requirements.txt).

## 2026-11-12

### Changed

#### rules

- Route amendments to platform-specific templates.
- Split amendment templates by review surface.
- Use Kilo/Plannotator annotations and approval, and use Arena Steering fielded reports.
- Place runnable checks in focused test files under directories that mirror source directories, and split mixed test files when touched.

#### maintenance

- Exclude amendment proposal templates from Markdown lint (the Markdownlint config).
- Split the checker into the checks package (the validation tooling). It uses an injected `Repo`, one module per concern, and stdlib logging with the same output text.
- Re-measure a token budget file after it changes inside one run (the measurement tooling).
- Discover clause files by glob instead of a hand-listed budget map (the validation tooling and READMEs). Measure `o200k_base` tokens by default and count characters only for the two ChatGPT fields.
- Rename the Nemoize stage in the checker and its summary, replacing the "domains" wording, and rename the Nemoize module key.
- Reword maintenance comments, docstrings, and READMEs after a nemoizer advisory review, with no behavior change.
- Register focused Nemoizer test files in the changed-paths workflow.

### Removed

#### maintenance

- Remove the Markdown lint scope test (the structural checks tests).

### Added

#### maintenance

- Introduce Kilo/Plannotator amendment proposal template.
- Introduce Arena Steering amendment proposal template with the final clause verbatim as the approval option label.

### Fixed

#### maintenance

- Reject Git and gate output that is not UTF-8 on Windows as well (the PR gate tooling).
- Keep the global Git config and hooks out of test repos (the test fixtures).
- Compare test paths with `/`, and skip tests that need POSIX `bash`, `sh`, or `fcntl` on Windows.

## 2026-11-11

### Changed

#### rules

- Read and acknowledge blocking inbox messages before starting or resuming queued work (the Arena rules).
- Restrict `steer poll` gate waits to a sole task and empty-queue work waits to no remaining tasks (the Arena rules).

#### arena-steering

- Require a report phase first for approved report work affecting features or documentation (the arena-steering skill).

## 2026-11-09

### Changed

#### rules

- Keep comments and docstrings rare and factual, limited to non-obvious external constraints and business invariants.
- Move Steering procedures from Arena into the skill and keep both in force together.
- Require the squash skill for refs-to-live rule amendments.
- Group Arena clauses by domain and place the bible definition before its first reference.
- Keep each nemoizer rewrite example faithful to its input contract.
- Move the resumed-work and worktree gate clause from Arena into the skill.

### Removed

#### rules

- Remove the retired ntfy restoration rule and both retired question-tool channel cases.
- Remove the Steering installer, lifecycle, survey, inbox, task, gate, report, and preview procedures that the skill now carries.
- Remove invented port, claim, and threshold details from the nemoizer rewrite examples.

### Fixed

#### maintenance

- Retain the local CI preparation-action reference until the released syntax validator supports self-repository references.
- Match the release-impact prompt to Semantic Versioning 2.0.0 section 7.
- Align the baseline Steering CLI reference with the shipped poll warning.
- Place the DAILIES item-count rule in the section it names.
- Restore focus after filling the Arena composer with a wake-up or no-poll draft.

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

- Rewrite the rules READMEs for human readers.
- Specify the stale-report reminder command (the Arena rules).
- Remove the code-scanning requirement (the Arena rules).

#### system-prompts

- Rewrite the system-prompts READMEs in human-facing prose.

#### maintenance

- Parse README budgets without `markdown-it-py`, drop retired group budgets and the retired JavaScript comments utility, and refresh the maintenance README.
- Rewrite the maintenance README for human maintainers and replace retired `arena-preview` hook tables with `steer pre`.
- Archive the retired minification workflow check and its tests under the archive.
- Exclude minified, archived, and vendored material from the root Nemoizer scan.
- Filter CodeQL language scans conservatively and restrict dependency reviews to dependency and workflow changes.
- Group plugin release and rules publication into separate credential-isolated jobs.
- Validate and sync distribution targets in one job, preserving remote reconciliation.
- Group read-only CI checks into one job, including PR plugin validation, and reuse successful input digests.
- Guard the archived Arena proxy tests against returning to the active test matrix.
- Refresh Ponytail and its audit skill from upstream `96608e0`, keeping only those two skills.
- Add pass-ledger collection and recording primitives for CI surfaces (the changed-paths workflow).
- Run workflow lint, security audit, and contract checks in one job (the workflow security checks).
- Ignore seven reviewed historical test-fixture findings in Gitleaks (the Gitleaks ignore list).
- Replace the root Arena symlink with a byte-identical regular copy (the root Arena file and the validation tooling).
- Expand Markdownlint coverage and remove the fixed scope guard (the Markdownlint config and the validation tooling).

### Fixed

#### maintenance

- Decode child-process text pipes as strict UTF-8, reconfigure CLI streams for Windows consoles, and pass explicit `encoding="utf-8"` across test suites.
- Update the seeded `S2E5P` survey payload in the demo script to use `first_name` and `last_name`.

## 2026-11-06

### Changed

#### maintenance

- Route Preview checks to consolidated Steering test modules (the changed-paths workflow).
- Route test checks to mirrored modules and split userscript suites (the changed-paths workflow).
- Time skills, links, budgets, parity, and paths validation as separate stages (the validation tooling).
- Run one Nemoizer stage using the root configuration instead of a separate Markdown allowlist (the validation tooling and root config).

#### rules

- Place non-trivial checks in mirrored module tests (the CORE, Arena, and ChatGPT rules).
- Distinguish stderr read reminders from other action reminders (the Arena rules).
- Limit inbox reads to stderr-reported unacknowledged messages (the Arena rules).
- Forbid Mermaid in chat and require it everywhere else (the Arena rules).
- Protect running Steering previews and require recommended report options (the Arena rules).
- Require self-contained handoffs (the Arena rules).
- Remove the deliverable-open requirement and publish handoffs as unfielded Steering reports (the Arena rules).
- Set the final poll Bash timeout to 1800 seconds and prohibit shell timeouts (the Arena rules).
- Remove the violation-notice trigger for full bible reads (the Arena rules).
- Route turn start, task ordering, Steering procedures, and job-log lookup through the installed skill. Use v2 `steer` commands (the Arena rules).
- Split the contract rules and keep the no-commit rule free of storage-location details (the Arena rules).
- After one diagnosis, resume unblocked work, use a worktree for frozen files, and recheck logs only after meaningful progress (the Arena rules).

## 2026-11-05

### Changed

#### rules

- Replace v1 steering references with v2, require six-call bible rechecks, and use v2 for all reports (the Arena rules and the house rules).

#### maintenance

- Log Nemoize child commands and exit codes during repo validation (the validation tooling).
- Add optional per-file scan and worker progress logging to Nemoizer (the Nemoizer).

## 2026-11-04

### Changed

#### rules

- Require substantive answers to delivered messages in their own acknowledgement before chat (the Arena rules).
- Remove the short-report-to-chat exception (the house rules).

### Fixed

#### maintenance

- Assign blocked-Bash dismissal and task-priority regressions to the Preview test group (the changed-paths workflow).

## 2026-11-03

### Changed

#### maintenance

- Print each failed check's findings under its FAIL line. Rename the STE lint check to Nemoize and its constants (the validation tooling).
- Decode every checker subprocess as UTF-8. Compare the markdownlint scope on POSIX separators so the check holds on Windows (the validation tooling).
- Nemoizer scans files in parallel with a 10 second per-file cap, reports skipped files, and prints progress dots (the Nemoizer).
- Feed Node subprocesses UTF-8 and cap each call at 10 seconds (the Nemoizer).
- Match nemoizer exclusion patterns against the config root so a subdirectory target keeps them (the Nemoizer).
- Exclude the retired arena-skill trees, its tests, prompt-fill text, archive changelog, and markdown outside READMEs under automations, system-prompts, and gpt-plugins (the project config).
- Remove the `--ste` flag from the checker. Nemoize runs as part of normal validation (the validation and extraction tooling).
- Drop the vendored asd-ste100 skill from vendored prose extraction targets (the extraction tooling).
- Remove the obsolete `--ste` CI step because repo validation checks covered docs (the CI workflow).
- Use fenced clause diff blocks instead of proposal tables.

#### skills

- Remove vendored `asd-ste100` skill (the vendored asd-ste100 skill).
- Remove vendored `humanizer` skill (the vendored humanizer skill).
- Remove `asd-ste100` row from vendored skills table (the vendored skills README).
- Remove ASD-STE100 and Humanizer rule references from nemoizer description (the gpt-plugins README).

#### system-prompts

- Reword nemoizer-only writing style line. Drop ASD-STE100-style controlled English (the NEMOGPT system prompt).

#### automations

- Drop the ASD-STE100 report language line (the Dailies automation).

## 2026-11-01

### Changed

#### maintenance

- Seed finished steering demo tasks as historical rows while live task creation requires phase completion checks (the demo script).
- Route steering source changes and the task-chain regression through Preview CI tests (the changed-paths workflow).

## 2026-10-31

### Changed

#### maintenance

- Reset the running demo to sample data without restarting its server. Preserve survey results and the reset action across reloads (the demo script).
- Route demo changes, reset tests, and connection tests to the Preview test group (the changed-paths workflow).
- Assign the composer parity browser test to the Preview test group (the changed-paths workflow).
- Assign the message retry browser test to the Preview test group (the changed-paths workflow).
- Assign the browser violation regression to the Preview test group (the changed-paths workflow).
- Ignore `.agents/` during Gitleaks scans while retaining the default rules (the Gitleaks ignore list).
- Move the configurable steering demo out of the shipped skill (the demo script).

## 2026-10-30

### Changed

#### maintenance

- Assign the message scroll-fade tests to the Preview test group (the changed-paths workflow).
- Exclude vendored arena-steering assets bundles and licenses from repo prose extraction (the validation and extraction tooling).

#### rules

- Require code and configuration comments to use the established contract (the Arena rules).
- Require reporting uncontracted shipped changes (the Arena rules).

## 2026-10-29

### Changed

#### maintenance

- Route the `Preview` test group to the arena-steering tests and remove legacy arena-skill test references (the changed-paths workflow and the README).
