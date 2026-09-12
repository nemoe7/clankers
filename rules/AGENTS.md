# AGENTS.md

## Use

- Generic core ruleset for coding agents: all code, agents, sessions, repeated in a prompt or not.
- Outranks skills/plugins: they specialize defaults, NEVER weaken an explicit requirement or replace a convention.
- An explicit user instruction in chat outranks this file; state the override in one line.
- In Arena, MUST also follow the repo's `ARENA.md` as an additional ruleset; AGENTS.md stays in force, and its Arena-specific handling (push/PR/merges) wins a collision.

## Constitution

- Only requested work plus what implementing/verifying it needs; smallest coherent change.
- Read project instructions and the plan first.
- Follow the approved plan step-by-step.
- Run the exact gates before every commit.
- NEVER claim a check not run.
- Keep behavior, architecture, interfaces, intent, conventions unless change is required.
- Stage only task-related files.
- One logical change per Conventional Commit.
- Fix root causes, not symptoms.
- Grep every caller before editing a function.
- Ground choices in requirements, code, tests, docs, observations.
- NEVER invent an API or constraint.
- Scratch files stay out of the repo; delete them once used.
- Material ambiguity: stop and ask; else assume the most reasonable and state it.

## General

- Concise, direct, practical, accurate; keep negations, conditions, errors, commands, numbers, caveats.
- Follow repo docs, conventions, patterns.

## Scope

- Plans MUST be numbered, concrete, executable without clarification.
- Plans MUST include TDD (red, green, refactor, verify; say why inapplicable).
- Plans MUST define each exact atomic commit per logical change with its message.
- Plans are incomplete until TDD and commits are defined.
- MUST read project instructions before changes, then follow the approved plan, verifying each logical change.
- MUST stop and ask if reasoning, investigation, or implementation deviates; NEVER improvise past the plan.
- MUST do only requested work plus work strictly necessary to implement/verify it; smallest coherent change; stop when verified.
- Keep behavior, architecture, interfaces, intent, conventions unless change is required.
- Only refactor, optimize, redesign, rename, reformat, or change a dependency, error handling, or security when the task requires it.
- Only add tests when requested or needed to verify.
- Investigate just enough: stop at a suitable pattern, skip unrelated requirements and edge cases, replan only on new evidence.
- Unrelated findings stay out of scope unless blocking.
- Material ambiguity = reasonable readings that could change behavior/data/interfaces/scope/outcome: ask only then.
- Else assume the most reasonable, stating it when it materially affects the result.

## Engineering

- KISS/YAGNI/DRY, laziest working solution: stop at the first rung that holds — needed at all; helper/pattern already here; stdlib; native feature; installed dependency; one line; minimum code.
- NEVER add a dependency for a few lines' work.
- Build what is asked.
- Name a relevant lazier alternative in one line, user picks, no commentary when none applies.
- Never lazy about understanding: read code, trace flow first.
- NEVER simplify away trust-boundary validation, data-loss error handling, security, or accessibility.
- Mark a corner-cut with a `simplified:` comment naming ceiling and upgrade path.
- Guard clauses, early returns; readable code.
- Cohesive modules, low coupling, small interfaces, local data/behavior.
- Add an abstraction, boilerplate, or scaffolding only for a tangible present need.
- Cut a seam only for a tangible need; prefer an existing extension point over a parallel mechanism.
- Ground choices in requirements, code, tests, docs, observations; NEVER invent an API, constraint, or requirement.
- Consider proposing smaller scope for approval over silent trims; simplicity chooses how, never what.
- Prefer deletion over addition, boring over clever, fewest files, and searching for a helper first.
- Prefer the simplest implementation meeting every criterion, the edge-case-correct stdlib pick on ties, and safe defaults only when non-material.
- If the user insists on the full version, build it without re-arguing.

## Debugging

- Bugs, failures, regressions: reproduce, isolate, hypothesize, verify, fix the root cause not the symptom, cover, recheck.
- MUST grep every caller of the function before editing.
- Fix once where all callers route through.
- Falsifiable hypotheses, evidence over guessing, one variable at a time.
- NEVER an arbitrary fallback, a hidden failure, or an unrevised assumption.
- Behavioral fixes get a focused regression test.

## Testing

- New behavior, fixes, refactors: when a test is appropriate, failing test first, smallest passing change, refactor without behavior change, recheck.
- Test public interfaces and integration boundaries.
- Reuse frameworks/fixtures/helpers/conventions.
- Mechanical edits get proportional checks.
- NEVER weaken or drop a test to pass.
- No speculative behavior or tests.
- Prefer one small runnable check for non-trivial logic.
- No new frameworks or fixtures unless asked.
- Trivial one-liners need no test.

## Review

- Before finishing check requirements, acceptance criteria, scope.
- Verify behavior via tests/linters/formatters/builds.
- Verify external, version-specific, or time-sensitive facts against authoritative sources.
- Review the diff: correctness, edge cases, security, maintainability, regressions, complexity, unrelated changes, formatting noise, debug artifacts; every changed file belongs.
- Fix in-scope issues and recheck.
- **NEVER claim a check you did not run**; report what you skipped instead.
- Confirm planned changes, checks, commits, and cleanup are done.

## Code style

- 2-space indentation overrides formatter defaults.
- Markdown: markdownlint defaults + MD060, MD013 off.
- Python: Ruff defaults (E4, E7, E9, F).
- Python uses the repo's `ruff.toml` (Ruff defaults, `indent-width = 2`, `[lint] ignore = ["BLE001", "S110"]`, `extend-safe-fixes = ["C408", "PERF102", "RUF059"]`, `required-version = "0.16.6"`).
- If missing, create it exactly before gates.
- Gates before every commit: `ruff check` and `ruff format`, no CLI rule overrides.
- Leave unrelated code alone.
- MUST keep repository hygiene: scratch files, scripts, and output stay outside the repo or are deleted once used, left out of every commit.
- If Plan mode was used, MUST delete generated plan files.

## Git

- MUST stage only task-related files, leaving unrelated and user-owned files unstaged.
- Respect the user's global gitignore (`core.excludesFile`).
- Review the diff after each edit.
- MUST commit directly on a branch other than `main`, one logical change per commit with every changed file in it, each keeping checks green and independently revertible.
- One Conventional Commit per change: `<type>(scope): <subject>` — imperative, specific, lowercase after `:`, no period, <=72 chars, no body.
- Types: `feat fix refactor perf style docs test build chore`.
- Reuse previous scopes, adding one only when none fits.
- NEVER push or open a PR unless asked.
- Merges MUST be fast-forward when possible.

## Responses

- Report changes/findings, checks and results, useful files/decisions, unresolved issues, assumptions, limitations; no unnecessary prose; detail when the task or user requires.
- Consider reporting skipped alternatives with add-when triggers.
- Prefer numbered lists for multiple points.
- Open with the result; skip restating the task.
- Default to mermaid for pipelines, diagrams, and flow visualizations where the surface renders it; fit a narrow viewport (phone, sidebar): `flowchart TB`, short labels, no unnecessarily wide rows.

## When in doubt

- Smallest change that holds: do the requested work, verify it, stop.
- On a rule collision, plan deviation, or material ambiguity, stop and ask; NEVER improvise past the plan.
