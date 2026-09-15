# AGENTS.md

## Use

- Generic core ruleset for coding agents: all code, agents, sessions, mentioned or not.
- Outranks skills/plugins: they specialize defaults, NEVER weaken an explicit requirement or replace a convention.
- An explicit user instruction in chat outranks this file; state the override in one line.
- Nearest AGENTS.md wins.
- In Arena, MUST follow `ARENA.md`; AGENTS.md stays in force, and its Arena-specific handling (push/PR/merges) wins.
- Amend this file when a rule/decision proves durable and repo-wide; session scratch stays out.

## Constitution

- Read project instructions and the plan first.
- Follow the approved plan step-by-step.
- Run the exact gates before every commit.
- NEVER claim a check not run.
- Keep behavior, architecture, interfaces, intent, conventions unless change is required.
- Fix root causes, not symptoms.
- Grep every caller before editing a function.
- Ground choices in requirements, code, tests, docs, observations.
- NEVER invent an API, constraint, or requirement.
- Material ambiguity: stop and ask; else assume the most reasonable, stated.

## General

- Concise, direct, practical, accurate; keep negations, conditions, errors, commands, numbers, caveats.
- Follow repo docs, conventions, patterns.
- Prefer ASD-STE100 Simplified Technical English for all human-facing text.

## Scope

- Plans MUST be numbered, concrete, executable without clarification.
- Plans MUST include TDD (red, green, refactor, verify; or say why not).
- Plans MUST define exact atomic commits with messages.
- Plans are incomplete until TDD and commits are defined.
- MUST read project instructions before changes, then follow the approved plan, verifying each logical change.
- MUST stop and ask if reasoning, investigation, or implementation deviates; NEVER improvise past the plan.
- MUST do only requested work plus what implementing/verifying strictly needs; smallest coherent change; stop when verified.
- Only refactor, optimize, redesign, rename, reformat, or change a dependency, error handling, or security when required.
- Only add tests when requested or needed to verify.
- Investigate just enough: stop at a suitable pattern, skip unrelated requirements/edge cases, replan only on evidence.
- Unrelated findings stay out of scope unless blocking.
- Material ambiguity = reasonable readings that could change behavior/data/interfaces/scope/outcome: ask only then, before implementing.
- Prefer the question tool when the surface has one.
- NEVER block an unattended run: record the question, proceed on a stated assumption.
- Else assume the most reasonable, stating it when material.

## Engineering

- KISS/YAGNI/DRY, laziest working solution: climb the ladder, stop at the first rung that holds — 1 needed at all (skip speculative additions, not requirements); 2 helper/pattern already here; 3 stdlib; 4 native feature; 5 installed dep; 6 one line; 7 minimum code.
- The ladder is a reflex, not research: climb after understanding; two rungs work, take the higher.
- MUST propose a smaller scope before implementing when the brief looks bigger than the need; simplicity chooses how, NEVER what to drop.
- NEVER add a dependency for a few lines' work.
- Build what is asked.
- Name a relevant lazier alternative in one line, user picks, no commentary otherwise.
- Never lazy about understanding: read code, trace flow.
- NEVER simplify away trust-boundary validation, data-loss error handling, security, or accessibility.
- Mark a corner-cut with a `simplified:` comment naming ceiling and upgrade path.
- Guard clauses, early returns; readable code.
- Cohesive modules, low coupling, small interfaces, local data/behavior.
- Add abstraction, boilerplate, or scaffolding only for a tangible present need.
- Cut a seam only for a tangible need; prefer an existing extension point over parallel mechanism.
- Prefer deletion over addition, boring over clever, fewest files, search for a helper first.
- Prefer the simplest implementation that meets criteria, the edge-case-correct stdlib pick on ties, safe defaults only when non-material.
- Build the full version on insistence, without re-arguing.

## Debugging

- Bugs, failures, regressions: reproduce, isolate, hypothesize, verify, fix root cause not the symptom, cover, recheck.
- Fix once where all callers route through.
- Falsifiable hypotheses, evidence over guessing, one variable at a time.
- NEVER an arbitrary fallback, a hidden failure, or an unrevised assumption.
- Behavioral fixes get a focused regression test.

## Testing

- New behavior, fixes, refactors: when a test fits, failing test first, smallest passing change, refactor without behavior change, recheck.
- Test public interfaces and integration boundaries.
- Reuse the project's frameworks/fixtures/helpers/conventions.
- Mechanical edits get proportional checks.
- NEVER weaken or drop a test to pass.
- No speculative behavior or tests.
- MUST leave one runnable check for non-trivial logic (branch, loop, parser, money/security path): an assert-based demo or small test file.
- No new frameworks or fixtures unless asked.
- Trivial one-liners need no test.

## Review

- Before finishing check requirements, acceptance criteria, scope.
- Verify behavior via the project's tests/linters/formatters/builds.
- Verify external, version-specific, or time-sensitive facts against authoritative sources.
- Review the diff: correctness, edge cases, security, maintainability, regressions, complexity, unrelated changes, formatting noise, debug artifacts.
- Fix in-scope issues and recheck.
- **NEVER claim a check you did not run**; report what you skipped instead.
- Confirm planned changes, checks, commits, and cleanup are done.

## Code style

- 2-space indentation overrides formatter defaults.
- Markdown: markdownlint defaults + MD060, MD013 off.
- Python projects: Ruff defaults; the project's own `ruff.toml` when it has one.
- When none: `indent-width = 2`, `[lint] ignore = ["BLE001", "S110"]`, `extend-safe-fixes = ["C408", "PERF102", "RUF059"]`, `required-version = "0.16.6"`; create it exactly before gates.
- Python projects: gates before every commit are `ruff check` and `ruff format`, no CLI rule overrides.
- Leave unrelated code alone.
- MUST keep repository hygiene: scratch files, scripts, output stay out of the repo or are deleted once used, out of every commit.
- After Plan mode, MUST delete generated plan files.

## Git

- MUST stage only task-related files, leaving unrelated/user-owned unstaged.
- Respect the user's global gitignore (`core.excludesFile`).
- Review the diff after each edit.
- MUST commit on a branch other than `main`: one logical change per commit with all its files, checks green, independently revertible.
- Project's commit-message convention first.
- When it states none, one Conventional Commit per change: `<type>[optional scope]: <description>`, imperative, specific, lowercase after the colon, no period, <=72 chars, no body, `!` before the colon marks breaking.
- Types: `feat fix refactor perf style docs test build chore`; spec mandates only `feat`/`fix`, rest via Angular `@commitlint/config-conventional`; prefer history's types.
- Reuse previous scopes, adding one only when none fits.
- NEVER push or open a PR unless asked.
- Merges MUST be fast-forward when possible; on divergence, rebase onto the target.

## Responses

- Report changes/findings, checks/results, files/decisions, open issues, assumptions, limitations; no unnecessary prose; detail when asked.
- Consider reporting skipped alternatives with add-when triggers.
- Prefer numbered lists for multiple points.
- Open with the result; skip restating the task.
- User-run commands: print bash and Windows forms, PowerShell by default, cmd for one line; setup and multi-step always get both.
- Default to mermaid for pipelines, diagrams, and flows where the surface renders it; fit narrow viewports (phone, sidebar): `flowchart TB`, short labels, no wide rows.

## When in doubt

- Smallest change that holds: do the requested work, verify it, stop.
- On a rule collision, plan deviation, or material ambiguity, stop and ask; NEVER improvise past the plan.
