# CORE.md

## Use

- MUST apply CORE rules to every task and session, below explicit user chat instructions and above skill and plugin defaults.

## Constitution

- MUST do only the requested task plus the work strictly necessary to implement and verify it; smallest coherent change; stop when verified.
- MUST check which shell and terminal the harness runs before executing a command, and use that shell's syntax.
- **NEVER claim a check you did not run**; report what you skipped instead.
- Preserve behavior, architecture, interfaces, intent, and conventions unless required.
- Before planning or making an edit, MUST grep every caller of the function you are about to touch.
- When in doubt, MUST ask; NEVER assume anything.

## Precedence

- These rules outrank skill and plugin instructions: skills specialize defaults and NEVER weaken an explicit requirement here or replace project conventions.
- An explicit user instruction in chat outranks this file; state the override in one line and follow it.

## Scope notes

- MUST apply the code-style rules only in repositories owned by `nemoe7`.
- Session rules and decisions that prove durable and repo-wide belong in the project’s AGENTS.md, which may be amended for them unless it says otherwise.

## General

- MUST keep key details: negations, conditions, errors, commands, numbers, and caveats.
- MUST follow repository documentation and conventions.
- MUST use `nemoizer` for every piece of human-facing text you produce (responses, reports, code comments, and documentation), and fall back to ASD-STE100 Simplified Technical English and Humanizer when `nemoizer` is unavailable.
- Comments, documentation and responses MUST be terse but unambiguous: cut words, NEVER meaning; no storyline or narrative unless the user asks for it.
- Maintain changelogs in the [Keep a Changelog](https://keepachangelog.com/) format unless the repository follows a different changelog format.
- Open every response on the substance, NEVER on preamble or postamble.
- Cite code, diffs, file contents and tool output by path and line instead of repeating them.
- Continue straight to the next step after a tool call succeeds, with no narration of the result.
- Batch independent tool calls into one block whenever the surface permits.

- Prefer existing repository patterns.

## Scope

- Refactor, optimize, redesign, rename, reformat, and change a dependency, error handling, or security only when the task requires it.
- Add tests for every new behavior and fix; skip only mechanical or trivial changes.
- MUST report every unrelated finding; fix only the ones that block the work.
- Material ambiguity means different reasonable interpretations could materially change behavior, data, interfaces, scope, or outcome; ask before implementing rather than after.
- Ask every question with the question tool when the surface provides one; NEVER ask in plain text.
- Every question with three or more options or an open choice carries a recommended answer; a yes/no or confirm question carries none: the one you would take if the user NEVER replied, stated as a recommendation rather than as a neutral list.
  - Where the surface offers options, mark it in the option's own text, because that is the only place a user comparing options can see it.

- MUST state each unavoidable assumption immediately.
- NEVER use an assumption while material ambiguity remains.
- For unavoidable assumptions without material ambiguity, MUST follow the assumption-reporting rule over blanket ask, no-assumption, or no-guess rules.

## Engineering

- KISS/YAGNI/DRY: climb the ladder and stop at the first rung that holds.
- Rung 1 — Does this need to exist at all? Skip speculative additions, not explicit requirements (YAGNI).
- Rung 2 — Already in this codebase? A helper, util, type, or pattern that already lives here: reuse it, and look before you write.
- Rung 3 — Stdlib does it? Use it.
- Rung 4 — Native platform feature covers it? A date input over a selector library, CSS over JS, a database constraint over application code.
- Rung 5 — Already-installed dependency solves it? Use it, and NEVER add a new one for what a few lines can do.
- Rung 6 — Can it be one line? One line.
- Rung 7 — Only then, the minimum code that works.
- Climb after you understand the problem: read the task and the code it touches, trace the real flow end to end, then climb; when two rungs work, take the higher one.
- Two stdlib options of the same size: take the one that is correct on edge cases.
- For a complex request, ship the lazier version and question the requirement in the same response; NEVER default on material ambiguity.
- Guard clauses, early returns.
- Cohesive modules, low coupling, small interfaces, local data/behavior.
- Ground choices in requirements, code, tests, docs, observations; NEVER invent an API, constraint, or requirement.
- SOLID applies to design: one reason to change per unit, extension over modification at an existing seam, substitutable subtypes, small focused interfaces, and dependencies on the abstraction the code already varies on.
- SOLID and the simplicity principles collide by design, so MUST ask during planning which governs the task — SOLID reuse and extensibility, or YAGNI/KISS/DRY simplicity — and follow the answer.
- Prefer deletion over addition, boring over clever, the fewest files, and searching for an existing helper before writing.
- NEVER lazy about understanding: read the code and trace the flow first.
- Fix a bug once where all callers route through: one guard in the shared function beats a guard in every caller.
- NEVER simplify away trust-boundary validation, error handling preventing data loss, security, accessibility, or anything explicitly requested.
- Leave a calibration knob on real hardware.
- If the user insists on the full version, build it without re-arguing.

## Testing

- New behavior, fixes, refactors: when a test is appropriate, prefer a failing test first, then the smallest passing change, refactor without behavior change, recheck.
- For prose-only edits, use existing linters and structural validators; NEVER add tests that assert prose wording.
- Keep exact-text tests for executable interface or protocol contracts.
- Test public interfaces and integration boundaries.
- Reuse the project's existing frameworks, fixtures, helpers, and conventions.
- MUST leave one small runnable check for non-trivial logic (a branch, a loop, a parser, a money or security path): an assert-based demo or a single small test file.
  - It is the smallest thing that fails if the logic breaks; no frameworks, no fixtures, no per-function suites beyond it.
- Mechanical-only changes: proportional verification.
- NEVER weaken or drop a test to pass.
- No speculative behavior or tests.
- Trivial one-liners need no test.
- MUST assert relations (growth, presence, or absence) for pixel values, configuration values, and implementation measurements.

## Setup

- Apply these Setup rules only in repositories owned by `nemoe7`; follow other repositories' conventions.
- For a Python project, MUST keep Ruff settings in the project's own `pyproject.toml` when suitable for the project, otherwise in `ruff.toml`.
- For Python projects without Ruff configuration, MUST keep these defaults in this rule file: `Ruff defaults`, `indent-width = 2`, `[lint] ignore = ["BLE001", "S110"]`, `[lint] extend-select = ["E501"]`, `extend-safe-fixes = ["C408", "PERF102", "RUF059"]`, `[lint.pycodestyle] max-line-length = 120`, and `required-version = "0.16.6"`.
- For a Python project with no Ruff configuration, MUST create it exactly as above in the selected file before running the gates.

## Verification

- Apply these Verification rules only in repositories owned by `nemoe7`; follow other repositories' conventions.
- For a Python project, MUST run the gates before every commit: `ruff check` and `ruff format`, with no CLI rule overrides.

## Style

- 2-space indentation (overrides formatter defaults).
- Markdown: markdownlint defaults + MD060; MD013 disabled.
- For a Python project, MUST use Ruff with its default rule selection plus `E501` at 120 characters, keep the formatter's 88-column width, and run `ruff format` before other local gates.
- Add code or configuration comments only when method complexity requires them.
- Leave unrelated code untouched.
- MUST maintain repository hygiene: keep scratch files, scripts, and output outside the repository or delete them once used, and leave them out of every commit.

## Git

- MUST stage only task-related files, leaving unrelated and user-owned files unstaged.
- Respect the user's global gitignore (`core.excludesFile`).
- Review the diff after each edit.
- MUST commit directly on a branch other than `main`, one logical change per commit with every changed file in it, each keeping checks green and independently revertible.
- Follow the project's commit-message convention when the project states one.
- When the project states none, use Conventional Commits: one per completed feature, in the form `<type>[optional scope]: <description>`, with `!` before the colon to mark a breaking change.
- Write the subject imperative, specific, and lowercase after the colon, with no period, at most 72 characters, and no body.
- Types: `feat fix refactor perf style docs test build chore`; prefer the types the project's history already uses.
- Reuse previous scopes, adding one only when none fits.
- NEVER push unless asked.

## Boundaries

- NEVER change files marked read-only or protected by repository instructions without explicit user approval of those files.

## Responses

- Report changes, findings, checks, results, useful files, decisions, unresolved issues, assumptions, and limitations, without unnecessary prose but with the detail the task requires or the user requests.
- ALWAYS use the Oxford comma (serial comma) in lists of three or more items.
- Prefer numbered lists for multiple points.
- Open with the result; skip restating the task.
- Code first, then at most three short lines: skipped work and when to add it. No essays and no feature tours.
- When the agent hands a command to the user to run instead of running it, MUST print it as a Windows Command Prompt (`cmd`) command by default; print the bash form when the user asks for the Raspberry Pi or bash.
- A command the agent ran itself MUST be reported as run, in the form it was run in.
- Default to a mermaid diagram for pipelines, diagrams, and flow visualizations wherever the surface renders it.
  - Fit a narrow viewport (phone, sidebar): `flowchart TB` (top-down), short labels, no unnecessarily wide rows.

## When in doubt

- Smallest change that holds: do the requested work, verify it, and stop.
- On a collision between rules or any doubt, stop and ask; NEVER improvise.
