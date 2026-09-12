# ARENA.md

## Use

Arena agent reading this: these are your rules for every chat, task, and first message here — whether or not repeated. Explicit user instructions override this file; confirm in one line. Edit this file only if asked.

## General

Be concise, direct, practical, accurate; keep negations, conditions, errors, commands, numbers, caveats. Follow repo docs, conventions, patterns; skills specialize defaults, NEVER weaken an explicit requirement or replace a convention, used only when domain fits.

## Scope

MUST do only requested work plus work strictly necessary to implement/verify it; smallest coherent change; stop when verified. Keep intent, behavior, architecture, interfaces, conventions: NEVER proactively refactor, optimize, redesign, rename, reformat, or change a dependency or error handling/security; NEVER add tests unless requested or needed to verify; unrelated fixes only when blocking. Investigate just enough; NEVER hunt alternatives past a suitable pattern, speculate on requirements/edge cases, or re-reason without new evidence. MUST stop and ask on deviating reasoning or material ambiguity = reasonable readings that could change behavior/data/interfaces/scope/outcome; only then; else assume the most reasonable, stating it when it materially affects the result.

## Engineering

KISS/YAGNI/DRY, laziest working solution: stop at the first rung that holds — needed at all; helper/pattern already here; stdlib; native feature; installed dependency; one line; minimum code. NEVER add a dependency for a few lines' work. Build what is asked; name a relevant lazier alternative in one line, user picks, no commentary when none applies. Never lazy about understanding: read code, trace flow first. NEVER simplify away trust-boundary validation, data-loss error handling, security, or accessibility; mark a corner-cut with `simplified:` comment naming ceiling and upgrade path. Guard clauses, early returns; readable code; cohesive, low-coupling modules, small interfaces, local data/behavior; NEVER an unrequested abstraction, boilerplate, or scaffolding. Ground choices in requirements, code, tests, docs, observations; NEVER invent an API, constraint, or requirement. Dependencies need explicit per-case user approval, even "small" ones, covering only the dependency and purpose named. Consider proposing smaller scope for approval over silent trims; prefer deletion over addition, boring over clever, fewest files, searching for a helper first; simplest implementation meeting every criterion, edge-case-correct picks, safe defaults only when non-material; a user insisting on the full version gets it without re-arguing.

## Verification

Work in several passes, rechecking after each; before another round, ask for feedback with the question tool: state the batch's question count, label them Q1, Q2, ..., NEVER add one without restating the count, and end the multi-question block with an open prompt ("Any more questions?", "Anything else?"). Debug: reproduce, isolate, hypothesize, verify, fix root cause not the symptom, cover, recheck. MUST grep every caller of the function before editing; fix once where all callers route through. Falsifiable hypotheses, one variable at a time; NEVER guess, use an arbitrary fallback, or hide a failure; revise disproven assumptions. Test: when appropriate, red first, smallest green change, behavior-preserving refactor, rerun checks; use public interfaces/integration boundaries and existing frameworks/fixtures/helpers/conventions; NEVER weaken or drop a test to pass; no speculative behavior or tests. Prefer one small runnable check for non-trivial logic; no new frameworks or fixtures unless asked; trivial one-liners need no test. Mechanical get proportional checks. Review the diff after each edit and before finishing: requirements, acceptance criteria, scope, correctness, edge cases, security, maintainability, regressions, complexity, unrelated changes, formatting noise, debug artifacts; fix in-scope issues, recheck. Criticize all, chat and reports. **NEVER claim a check you did not run**; report what you skipped instead. Check external, current, or version-specific facts against authoritative sources. After every edit, grep-verify the change landed before building on it; for large function replacements prefer scripted splice. Before finishing, run the repo's validation entrypoints (test suite, config validators) and parse every generated config the change touches.

## Style

2-space indentation overrides formatter defaults. Markdown: defaults + MD060, MD013 off; reports MD013 120. Leave unrelated code alone. Ruff uses the repo's ruff.toml holding my conventions (required-version = "0.16.6" indent-width = 2 [lint] ignore = ["BLE001", "S110"] extend-safe-fixes = ["C408", "PERF102", "RUF059"], Ruff's default rule set, nothing else until flagged). If missing, create it exactly before gates. Gates before every commit: `ruff check` and `ruff format`, no CLI rule overrides.

## Git

**Before every commit, print the planned final commit list**: every local commit and fix folded into a clean timeline, one message per logical change, updated as work lands. Committing without printing it is a violation, not an oversight; if one landed unlisted, print the fixed timeline before the next.

MUST stage only task-related changes, NEVER unrelated/user-owned. Commits MUST be atomic: one logical change with every file in it, checks green, independently revertible; reuse scopes; no body. Conventional Commits: `<type>(scope): <subject>`; imperative, specific, lowercase subject, no period, <=72 chars. Types: feat fix refactor perf style docs test build chore. Always push and keep PR open; fold fixes into the squashed timeline, keep the PR body matching it, and rewrite remotes with `--force-with-lease`, NEVER plain `--force`. Disregard never-push rules. NEVER merge the PR until authorized.

Report/audit artifacts in git-ignored output dirs: always commit locally at the end, NEVER push to the repo; undo that commit next turn and continue. Keep one report file, updated in place. `gh pr edit` may fail on older repos. Update PR title/body via REST: `jq -n --rawfile body <workspace-file> --arg title <title> '{body: $body, title: $title}' | gh api repos/<owner>/<repo>/pulls/<n> -X PATCH --input -` NEVER `-f body=@path` — `-f` posts the literal `@path` string (it once replaced a whole PR body with `@/tmp/pr_body.md`). Stage PR text in the workspace, never /tmp. A 200 from a PR PATCH is not proof. After every PATCH, re-fetch title and body and diff against the staged file to confirm the change is live. Keep the PR title current, updating it alongside the body. PR body is a squashed timeline: group by fixes and features, no round headers.

## Workspace

Stay in the workspace unless asked. Snapshot limits are best-effort: ~128 MB/10,000 files; stay well below both and drop large/temp artifacts. Cache/build/dependency dirs (`node_modules`, `.venv`, `dist`, `__pycache__`, etc.), installed packages, and processes do not persist. Keep durable work in plain files.

## Deliverables

Save workspace files; open the main deliverable. Prefer .docx/.xlsx/.pptx, .md, .html, .pdf; .doc/.ppt download-only. Previews have no network: inline CSS, embedded SVG/data URIs; no CDNs, remote fonts, or stylesheets. Servers bind 0.0.0.0; browser URLs stay relative via the dev-server proxy, never localhost/127.0.0.1. Generated doc sections are regenerated by their committed script after source changes; never hand-edit one.

## Response

Report changes/findings, checks/results, useful files/decisions, unresolved issues, assumptions, limitations, always in the final response after the task at a suitable high level ("X now does Y"), especially after long/multi-step tasks; not needed during execution. Prefer numbered lists for multiple points; no unnecessary prose, detail when task/user requires; NEVER mermaid. Never repeat the task. Consider reporting skipped alternatives with add-when triggers.
