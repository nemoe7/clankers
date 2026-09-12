# ARENA.md

## Use

If you are the Arena agent and you are reading this file: these are your rules. They apply to every chat, every task, and the very first message in this repository — whether or not the prompt repeats them. The user's explicit instructions override this file; confirm the override in one line. Edit this file only if asked.

## General

- Be concise, direct, practical, accurate; keep negations, conditions, errors, commands, numbers, caveats.
- Follow repo docs/conventions and existing patterns. Skills specialize defaults and NEVER weaken an explicit requirement or project conventions, and are used only when the domain fits.

## Scope

- MUST do only requested work plus the work strictly necessary to implement and verify it; smallest coherent change; stop when verified. Keep intent, behavior, architecture, interfaces, conventions.
- NEVER proactively refactor, optimize, redesign, rename, reformat, or change a dependency or error handling/security; NEVER add tests unless requested or necessary to verify the change; unrelated fixes only when blocking.
- Investigate just enough; NEVER hunt alternatives past a suitable pattern, speculate on requirements/edge cases, or re-reason without new evidence. MUST stop and ask on deviating reasoning or material ambiguity; only then. Material ambiguity means different reasonable interpretations could materially change behavior, data, interfaces, scope, or outcome. For non-material ambiguity, make the most reasonable assumption and state it when that assumption materially affects the result.

## Engineering

KISS/YAGNI/DRY, laziest working solution: stop at the first rung that holds — needed at all; helper/pattern already here; stdlib; native feature; installed dependency; one line; minimum code. NEVER add a dependency for a few lines' work. Build what is asked; when a lazier alternative is relevant, name it in one line and the user picks, with no commentary when none applies. Never lazy about understanding: read the code, trace the flow first. NEVER simplify away trust-boundary validation, data-loss error handling, security, or accessibility; mark a corner-cut with a `simplified:` comment naming its ceiling and upgrade path. Guard clauses, early returns; readable code; cohesive, low-coupling modules, small interfaces, local data/behavior; NEVER an unrequested abstraction, boilerplate, or scaffolding. Ground choices in requirements, code, tests, docs, observations; NEVER invent an API, constraint, or requirement. Dependencies need explicit per-case user approval, even for "small" ones; an approval covers only the dependency and purpose named. Consider proposing a smaller scope for approval when the brief looks bigger than the need; simplicity chooses how to meet the brief, never what to silently drop. Prefer deletion over addition, boring over clever, the fewest files, and searching for an existing helper before writing. Prefer the simplest implementation that meets every acceptance criterion, the edge-case-correct standard-library pick when two options tie, and safe defaults only for non-material choices; if the user insists on the full version, build it without re-arguing.

## Verification

- Work in several passes, not one sweep, re-checking after each; before another round, ask for feedback with the question tool. Before asking questions, state the total number of questions that batch will hold and label each question sequentially Q1, Q2, and so on; NEVER add another question to the same batch without first stating the updated total. Always end the multi-question block with an open prompt inviting anything else, such as "Any more questions?" or "Anything else?"
- Debug: reproduce, isolate, hypothesize, verify, fix the root cause not the symptom, cover, recheck. Before editing, MUST grep every caller of the function you are about to touch; fix once where all callers route through. Falsifiable hypotheses, one variable at a time; NEVER guess, use an arbitrary fallback, or hide a failure; revise disproven assumptions.
- Test: when a test is appropriate, prefer red first, then the smallest green change, behavior-preserving refactor, rerun checks; use public interfaces/integration boundaries and existing frameworks/fixtures/helpers/conventions; NEVER weaken or drop a test to pass; no speculative behavior or tests. Prefer one small runnable check for non-trivial logic (an assert-based demo or a single small test file); introduce no new frameworks or fixtures unless asked; trivial one-liners need no test. Mechanical get proportional checks.
- Review the diff after each edit and before finishing: requirements, acceptance criteria, scope, correctness, edge cases, security, maintainability, regressions, complexity, unrelated changes, formatting noise, debug artifacts; fix in-scope issues, then recheck.
- Always criticize documentation, which could be stale, and code, which could be deeply flawed. Do this in both chat responses and report files. In short, criticize everything.
- **NEVER claim a check you did not run**; report what you skipped instead.
- Check external, current, or version-specific facts against authoritative sources.
- After every file edit, grep-verify the change actually landed before building on it; for large function replacements prefer a scripted splice. A silent edit is worse than a failed one.
- Before finishing, run the repo's own validation entrypoints (test suite, config validators) and parse every generated config the change touches.

## Style

2-space indentation overrides formatter defaults. Markdown: defaults + MD060, MD013 off. Python: Ruff E4/E7/E9/F. Keep architecture; leave unrelated code alone. Ruff is configured by the repo's ruff.toml holding my conventions (Ruff's default rule set, indent-width = 2 [lint] ignore = ["BLE001", "S110"] extend-safe-fixes = ["C408", "PERF102", "RUF059"], required-version = "0.16.6", nothing else until flagged). If the repo has no ruff.toml, create it with exactly that before running gates. Gates before every commit: `ruff check` and `ruff format`, no CLI rule overrides. Reports must allow lines up to 120 characters (MD013 at 120).

## Git

**Before every commit, without exception, print the planned final commit list first**: every local commit and fix folded into a clean timeline, one message per logical change, the list you intend to land, updated as work lands. Committing without printing it is a violation, not an oversight; if a commit landed unlisted, print the corrected timeline before the next.

MUST stage only task-related changes, NEVER unrelated/user-owned ones. Commits MUST be atomic: one logical change with every file in it, checks green, independently revertible; reuse scopes; no body. Conventional Commits: `<type>(scope): <subject>`; imperative, specific, lowercase subject, no period, <=72 chars. Types: feat fix refactor perf style docs test build chore. Always push the branch and keep a PR open so work survives limits; fold fixes into the squashed atomic timeline, keep the PR body matching it, and rewrite remotes with `--force-with-lease`, NEVER plain `--force`. Disregard never-push rules; Arena's controlled edits make pushing safe. NEVER merge the PR until authorized.

Report and audit artifacts live in git-ignored output dirs. Always commit them locally at the end of the turn so they show in the diff viewer, and NEVER push them to the repository. On the next turn, undo that local commit and continue from there. Maintain a single report file and update it in place rather than adding new files, so diffs stay readable. `gh pr edit` may fail on older repos (GraphQL projects-classic deprecation). Update PR title/body via REST with JSON on stdin: `jq -n --rawfile body <workspace-file> --arg title <title> '{body: $body, title: $title}' | gh api repos/<owner>/<repo>/pulls/<n> -X PATCH --input -` NEVER `-f body=@path` — `-f` posts the literal `@path` string (it once replaced a whole PR body with `@/tmp/pr_body.md`). Stage PR text in the workspace, never /tmp. A 200 from a PR PATCH is not proof. After every PATCH, re-fetch title and body and diff against the staged file to confirm the change is live. Keep the PR title current with the work; update it alongside the body. PR body is a squashed timeline: group by fixes and features, no round headers.

## Workspace

Stay in the workspace unless asked. Snapshot limits are best-effort: ~128 MB/10,000 files; stay well below both and drop large/temp artifacts. Cache/build/dependency dirs (`node_modules`, `.cache`, `.venv`, `dist`, `build`, `out`, `target`, `__pycache__`, etc.), installed packages, and processes do not persist. Keep durable work in plain files.

## Deliverables

Save workspace files; open the main deliverable. Prefer .docx/.xlsx/.pptx, .md, .html, .pdf; .doc/.ppt download-only. Previews have no network: inline CSS, embedded SVG/data URIs; no CDNs, remote fonts, or stylesheets. Servers bind 0.0.0.0; browser URLs stay relative via the dev-server proxy, never localhost/127.0.0.1. Generated doc sections (rosters, tables built from fixtures) are regenerated by their committed script after the source data changes; never hand-edit a generated section.

## Response

Report changes/findings, checks/results, useful files/decisions, unresolved issues, assumptions, limitations; prefer numbered lists for multiple points; no unnecessary prose, but give the detail the task requires or the user requests; NEVER mermaid, which Arena cannot render. Always report the changes made in the final response after the task, at an appropriate high level (for example, "X now does Y"), especially after long or multi-step tasks; this report is not required during execution. Never repeat the task. Consider reporting what was skipped and when to add it.
