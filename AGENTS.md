# AGENTS.md

## Use

- MUST apply these repository rules to every task and session here.
- A bare imperative is a hard rule. MUST, NEVER, and ALWAYS restate the hardest ones; prefer marks a soft rule.

## Constitution

- For each dependency advisory, check whether a later dependency version fixes it; report it only when a fix is available, and otherwise ignore it.
- Compression removes words, NEVER rules.
- Squash only the new or amended line; on a deletion, attempt one full squash and keep whichever budget is lower.
- Stage only task-related files; leave unrelated files unstaged.
- Keep one dated entry per date in `docs/CHANGELOG.md` for `rules/`, `automations/`, `system-prompts/`, and `maintenance/`, extending it while the date holds.
- Use dates as versions in `docs/CHANGELOG.md` (`## YYYY-MM-DD`, with no bracket, no repeated date, and no version numbers in entries), following `docs/archive/CHANGELOG.md`, and use SemVer headings without dates (`## [X.Y.Z]`) in every module changelog, anywhere it lives.
- Group changes by [Keep a Changelog](https://keepachangelog.com/) type and then domain.
- Omit Unreleased.

## Precedence

- They outrank skill and plugin instructions.
- An explicit user instruction in chat outranks this file, confirmed in one line.

## Setup

- ARENA.md's NEVER-edit-this-file clause is waived in this repository, the home of that file (refs, live and root copies) and the preview skill.
- Mirror task-related source changes into installed copies in this repository without separate user authorization.
- Follow the clause-proposal and approval scope in [Reports and approval](#reports-and-approval).

## Glossary

- arena = [ARENA.md](ARENA.md)
- house = this repository; house rules = root AGENTS.md
- arena suite = ARENA.md and arena-steering files

- [README.md](README.md) — budgets, compression procedure, layout
- [docs/CHANGELOG.md](docs/CHANGELOG.md) — rule, prompt, automation, and maintenance history
- [rules/README.md](rules/README.md) — rule structure, installation, maintenance
- [rules/refs/GUIDELINES.md](rules/refs/GUIDELINES.md) — the standard for writing an AGENTS.md; audit rule files against it
- [skills/README.md](skills/README.md) — skill format, upstream sources, install notes
- [maintenance/README.md](maintenance/README.md) — validation and measurement tooling

## Verification

1. `npx --yes markdownlint-cli2` from the repository root, with no extra globs.
2. `ruff format .`, then `ruff check .` and `ruff format --diff .` at the version `pyproject.toml` pins.
3. `python3 maintenance/check.py` after changing skills, rules, workflows, or README budgets; add `--update` to refresh README measurements.
4. Run only the tests and validators that cover the changed files instead of a repository-wide validation.

## Rules

- Agent-facing rule files live in `rules/`: the generic core `CORE.md` and the platform overlays `KILO.md`, `ARENA.md`, `CHATGPT-CUSTOM.txt`, `CHATGPT-MORE.txt`.
- Baseline skill trees live in `skills/refs/`: keep prose files only unless nested `AGENTS.md` exempts minification. Amend refs first, then squash only live `SKILL.md`, and never install or distribute refs.
- Mode-specific Kilo overrides live in `rules/refs/kilo/`: `plan.md`, `code.md`, `debug.md`.
  - Keep compressed live copies in `rules/kilo/`, each with a blank first line, a `### Native <mode> Agent Overrides` heading, and the clause that it wins over a native reminder.

- Amend rules/refs/ first, then use [squash](skills/squash/SKILL.md) for the new or affected live line. Apply the result to rules/ and, for ChatGPT fields, rules/wenyan/.
  - Keep refs uncompressed as the baseline.
- No size diffs or budget changes in `docs/CHANGELOG.md` or `docs/**/CHANGELOG.md`.
- Before suggesting any amendment, read [rules/refs/GUIDELINES.md](rules/refs/GUIDELINES.md), cite at least one of its sections in the proposal, and draft the line to its section 4 (one rule per line, imperative, testable); write every rule file to that standard.

## Reports and approval

- Amend this file when a rule or decision proves durable and repo-wide; otherwise edit only when asked.
- MUST include ARENA and CHATGPT amendment proposals in the same report as each CORE amendment proposal.
- MUST name the failure each proposed amendment prevents.
- Apply this section's AGENTS.md proposal and approval requirements to all agent-facing files.
- Any agent-facing material MUST NEVER contain rationale, narrative, or facts that drive a clause.
- Before editing any clause, use [Kilo amendment template](maintenance/amendment-template.md) on Kilo or other harnesses, or [Arena amendment template](maintenance/amendment-template-arena.md) on Arena.
  - Keep the existing code-change exception.
  - For prose-only changes, structural validators and Markdown lint replace red/green executable tests.
  - Kilo/Plannotator uses annotations and approval; Arena uses Steering fielded reports.
  - Code changes need no proposal; keep them lean.
- Proposals come before any other task or queued work: in a turn that holds both, show every proposal first, then start tasks.
- Ledger prose: neutral wording — actions, files, numbers; one terse entry per event; no narrative, rationale or story.
- Chat text and reports: at most 3 sentences per block; concise on phone and vertical monitors; no essays unless strictly necessary; digestible.
- No clause in a rule, skill, workflow or system-prompt file is added, amended, or deleted until the user approves the report; hold the work and say so in one line.
- Edits that change no clause — a squash that removes no rule, a typo or link fix, formatting, a re-measure — need no report.
- For skills, restrict this section's clause-proposal and approval requirements to first-party agent-facing text; unchanged third-party copies are exempt.
- Propose every clause from refs, including owner text.
- A custom answer on a clause takes a fresh proposal of the new wording; the line lands only after that proposal is approved.
- Report at the level the user approves from — the clause change and why, not a full implementation patch; the fenced `diff` block describes only the proposed clause.
- Multiple reports may coexist; reports, inboxes and receipts stay uncommitted and are NEVER pushed.

## Budgets

- Keep root `AGENTS.md` outside the instruction measurement table.
- NEVER use instruction measurements as fixed size ceilings.
- Target a smaller size than the previous version for every amended instruction file.
- Accept unavoidable size growth.
- Rule files, `SKILL.md` entry points, and workflow files have budgets tracked in [README.md](README.md#instruction-budgets).
- Re-measure and update the table when changing them.

## Skills

- ChatGPT-related skills ALWAYS go to gpt-plugins.
- ALWAYS bump each changed module's version one step above main per PR.
- Skills in `skills/` follow the [Agent Skills specification](https://agentskills.io/specification).
- Every `SKILL.md` needs YAML frontmatter using only `name`, `description`, `license`, `compatibility`, `metadata`, `allowed-tools`.
- `name` matches its directory.
- Record `metadata.upstream` for adapted skills.
- The file stays under 500 lines.
- A skill holds only what an agent needs to use it; design decisions, background, rationale, and history go to `docs/<skill>/CHANGELOG.md` or [docs/arena-quirks.md](docs/arena-quirks.md).

## Style

- 2-space indentation, overriding formatter defaults.
- No hard-wrapped prose: one line per paragraph, list item, and table row, soft-wrapped by the editor.
- Markdownlint: **MD060 enabled**, **MD013 disabled**.
- Python: Ruff, configured by `pyproject.toml`, which owns the selection and the pinned version.
- Prose style: write and edit chat reports and the documentation prose of this repository (`docs/` and every `README.md`) with `nemoizer` (`skills/nemoizer/scripts/nemoizer`), falling back to ASD-STE100 and Humanizer when `nemoizer` is unavailable; both linters MUST pass on changed text.
  - Rules, skills and agent-facing files such as this one stay outside the linter's scope.
  - A copy of a third-party file stays outside it too, because the copy belongs to its upstream: no rewrite of a vendored file, and no path into the gate for one.

- Squash every `README.md` and every file in `docs/` against the [compression procedure](README.md#compression); prose is not exempt.

## Git

- One Conventional Commit subject per change: `<type>(scope): <subject>` — imperative, specific, lowercase after `:`, no period, at most 72 chars, no body.
- Types: `feat fix refactor perf style docs test build chore`.
- Merges MUST be rebase merges: rebase onto the target, then merge; no merge commit.

## Boundaries

- Add no further CI workflows, dependency manifests, test scaffolding, or tooling installs unless explicitly requested.
- Treat installed rule copies as read-only.
- Review changes directly in the diff; every changed file belongs to the task.
- Keep scratch files, scripts, and generated plan files out of every commit.
