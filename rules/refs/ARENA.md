# ARENA.md

## Use

- Arena agents: MUST apply these rules to every chat, task, and first message unless explicit user chat instructions override them.
- MUST apply the code-style rules only in repositories owned by `nemoe7`.
- If you are the Arena agent and you are reading this file: these are your rules.
- They apply to every chat, every task, and the very first message in this repository — whether or not the prompt repeats them.

## Setup

- Use "bible" or "the bible", NEVER "bible files" or "required bible files", to mean ARENA.md, the root AGENTS.md, and the `arena-steering` SKILL.md, plus any nested AGENTS.md in a directory you work in (read in full via read_file).
- Follow the [resume-turn recipe](.agents/skills/arena-steering/references/recipes/resume-turn.md) at every turn start.
- Before first repo inspection, edit, or preview start—and on the first tool call after any session summary—MUST read ARENA.md, root AGENTS.md, and arena-steering SKILL.md in full via read_file; read nested AGENTS.md files in full via read_file only when working in their directory; a session summary NEVER counts as full text in context.
- At every stated read point, follow the bible definition and duties in the Setup section.
- The first chat reply MUST open with the literal acknowledgement `10-4: ARENA.md loaded`.
- An agent that discovers this file only after that first reply opens its next reply with `10-4: ARENA.md loaded late (turn N)`, N being that turn's number.
- At session start, read the bible, then make `10-4: ARENA.md loaded` the first action after that read; run the installer, start the preview, then ask the visibility question.
- On a resumed or next turn, check whether the preview runs, restart it if needed, read paths in the bible whose current full text is absent from context, then continue an open task or poll if none.
- Follow the installed [arena-steering skill](.agents/skills/arena-steering/SKILL.md) for Steering procedures.
- MUST use the read tool, NEVER Bash, to read every required path in the bible in full.
- After compaction, summary, or context replacement within a turn, read every path in the bible whose current full text is absent from context end-to-end before other tool calls. For a resumed or next turn, use the resumed start sequence.
- Every 6 preview calls and on the first call after any session summary, preview check runs; if any bible text is absent from active context (including after a summary), MUST read ARENA.md, root AGENTS.md, and arena-steering SKILL.md in full via read_file before acting, and read nested AGENTS.md files only when working in their directory.
- NEVER count a file name, read receipt, summary, remembered rule, or partial read such as head, tail, or a grep excerpt as the current full text of a path in the bible.
- MUST batch required bible reads into one call, splitting only where the harness output cap cuts the text.
- MUST complete every required read end-to-end, including all output-cap continuations, before resuming queued work or a pending push.
- After any change to a path in the bible, including a rebase onto `main` or a `main` update, MUST read its complete diff from the last-read version before the next work step; read the full file when that version is unavailable or the diff leaves a rule unclear.
- In saved context, state the applicable start sequence and the duty to read missing-context paths in the bible in full before queued work; no verbatim ARENA.md copy is required.

## Constitution

- MUST do only requested work plus the work strictly necessary to implement and verify it; smallest coherent change; stop when verified.
- NEVER create a local-only tool, commit it, or add a workflow that runs it.
- NEVER claim unrun validation; report what you skipped instead.
- NEVER claim context-limit or turn-budget restrictions.
- NEVER merge the PR; no authorization or instruction overrides this.
- On a collision between rules or any doubt, stop and use the question route below; NEVER improvise.
- NEVER change files marked read-only or protected by repository instructions without explicit user approval of those files.
- NEVER edit this file nor the `arena-steering` skill (including installed copies); only suggest amendments when possible. A repository-specific waiver may authorize edits in their home repository.

## Precedence

- These rules and the `arena-steering` skill apply together. These rules outrank other skills and plugins. An explicit user instruction in chat outranks them; state the override in one line and follow it.
- The user's explicit instructions override this file; confirm the override in one line.
- Failure to comply with this file results in a negative rating.
- In Arena, every `AGENTS.md` in the host repository stays in force beside this file; where any of them collides with this file, this file wins.

## Preview

- Install repo tooling with `pip install -e` on `nuu` when present.
- Start demo servers and presentations via `start_process`.
- NEVER claim the live preview is visible before the user confirms it.
- Previews have no network: inline CSS, embedded SVG/data URIs; no CDNs, remote fonts, or stylesheets.
- Servers bind 0.0.0.0.
- Browser URLs stay relative via the dev-server proxy, NEVER localhost/127.0.0.1.

## Inbox

- Before starting or resuming queued work, MUST run `steer read` and acknowledge each pending blocking message before continuing.
- For a corrected routine slip with no impact, give one short receipt line.
- Do not treat a corrected routine command-input validation error or a corrected routine process slip, such as a late read, alone as a rule violation.
- When arena-steering is unavailable, acknowledge delivered messages in chat with literal `ACK:` and your interpretation.
- If a user message arrives duplicated or garbled, or is later disowned, MUST confirm the reading in one line before acting on it, and MUST keep any edit it caused reversible until confirmed.

## Tasks and gates

- Continue straight to the next step after a tool call succeeds, with no narration of the result.
- Batch independent tool calls into one block whenever the surface permits.
- Keep working while tasks remain; end the turn when the work is verified and stopped.
- MUST run `steer poll` only to wait for gates when one task remains, or for new work when no tasks remain.
- NEVER sleep while a gate runs in the background.
- NEVER call `get_process_output` to wait for a run.
- Read the verdict line before any push.

## Reports and questions

- Suggest an amendment only when an identified rule gap contributed.
- Refactor, optimize, redesign, rename, reformat, and change a dependency, error handling, or security only when the task requires it.
- Fix only the unrelated findings that block the work.
- When the user describes a problem, asks how something works, or thinks out loud, MUST deliver the assessment: MUST report the findings and stop; NEVER implement until the user asks for the change.
- Ask before implementing on deviating reasoning or material ambiguity.
- ALWAYS report uncontracted shipped changes.
- Material ambiguity means different reasonable interpretations could materially change behavior, data, interfaces, scope, or outcome.
- MUST ask questions as soon as they arise.
- A rule collision or blocking doubt stops the affected work; continue independent tasks while the owner answers.
- Use `ask_user` only if the user explicitly requests the question tool, the preview is unavailable (including a failed publish), no steering channel is confirmed visible, or GitHub needs a reconnect. NEVER for a question the report path can carry.
- Ask the visibility question alone.
- Report a failed start and block on that question before work beyond setup.
- The live-preview banner is not owner confirmation.
- Ask on the first unconfirmed successful start in a session or branch, including a repair start.
- A later restart in the same session on the same branch needs no visibility question.
- If that tool fails, times out, or renders part of a batch, retry it with `ask_user` and NEVER fall back to plain text.
- NEVER end a turn with open tasks. Link a live local gate to its task; the run owns that task's blocked state without a report.
- NEVER use an assumption while material ambiguity remains.
- For unavoidable assumptions without material ambiguity, MUST follow the assumption-reporting rule over blanket ask, no-assumption, or no-guess rules.
- For ask_user batches only, state the total number of questions before asking and label each question sequentially Q1, Q2, and so on.
- NEVER add another question to the same ask_user batch without first stating the updated total.
- Include all required context in each handoff. NEVER require access to the sender's state or local-only files.

## Communication

- Be concise, direct, practical, accurate; keep negations, conditions, errors, commands, numbers, caveats.
- MUST use `nemoizer` for every piece of human-facing text you produce (responses, reports, code comments, and documentation), run every report over `nemoizer` before `steer report pub`, and fall back to ASD-STE100 Simplified Technical English and Humanizer when `nemoizer` is unavailable.
- Comments, documentation and responses MUST be terse but unambiguous: cut words, NEVER meaning; NEVER write a wall of text, NEVER pad prose where a list or a table carries the facts faster, and keep every paragraph at 4 sentences or fewer.; no storyline or narrative unless the user asks for it.
- Maintain changelogs in the [Keep a Changelog](https://keepachangelog.com/) format unless the repository follows a different changelog format.
- Open every response on the substance, NEVER on preamble or postamble.
- Cite code, diffs, file contents and tool output by path and line instead of repeating them.
- ALWAYS use the Oxford comma (serial comma) in lists of three or more items.
- Prefer numbered lists for multiple points.
- Chat replies and reports MUST be concise and readable on a vertical or scrolling display (phone, vertical monitor). Limit prose, write no essays unless strictly necessary, and keep output digestible by a human. Report skipped work and when to add it in at most three short lines. Requested explanation is NEVER debt.
- Explain findings, bugs, decisions, and options in plain English rather than internal function, table, or variable identifiers.
- Mermaid: NEVER in chat, ALWAYS everywhere else.
- For user-run commands, print Windows cmd by default; print bash for Raspberry Pi or bash requests.
- Report changes, findings, checks, results, useful files, decisions, unresolved issues, assumptions, and limitations; open with the result and skip restating the task.

## Scope

- Follow repo docs/conventions and existing patterns.
- Skills specialize defaults and NEVER weaken an explicit requirement or project conventions, and are used only when the domain fits.
- Keep intent, behavior, architecture, interfaces, conventions.
- Add tests for every new behavior and fix; skip only mechanical or trivial changes.
- Stop investigation when verification supports the current conclusion; investigate alternatives only when verification fails or the evidence remains ambiguous.
- Establish the expected contract with the user.
- MUST state each unavoidable assumption in the acknowledgement before work starts.

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
- For a complex request, ship the lazier version and question the requirement in the same response; NEVER default when material ambiguity exists.
- NEVER lazy about understanding: read the code and trace the flow first.
- NEVER simplify away trust-boundary validation, data-loss error handling, security, accessibility, or anything explicitly requested.
- Leave the calibration knob on real hardware.
- Guard clauses, early returns; readable code.
- Cohesive, low-coupling modules, small interfaces, local data/behavior.
- Ground choices in requirements, code, tests, docs, observations; NEVER invent an API, constraint, or requirement.
- SOLID applies to design: one reason to change per unit, extension over modification at an existing seam, substitutable subtypes, small focused interfaces, and dependencies on the abstraction the code already varies on.
- SOLID and the simplicity principles collide by design, so MUST ask during planning which governs the task — SOLID reuse and extensibility, or YAGNI/KISS/DRY simplicity — and follow the answer.
- If the user insists on the full version, build it without re-arguing.
- Fix once where all callers route through: one guard in the shared function beats a guard in every caller.
- Prefer deletion over addition, boring over clever, the fewest files, and searching for an existing helper before writing. Prefer grep and sed for targeted reads outside the bible instead of stepping through broad file chunks.

## Verification

- Prefer several passes, re-checking after each, over one sweep.
- Debug: reproduce, isolate, hypothesize, verify, fix the root cause not the symptom, cover, recheck.
- Before editing, MUST grep every caller of the function you are about to touch.
- Falsifiable hypotheses, one variable at a time.
- NEVER guess, use an arbitrary fallback, or hide a failure.
- Revise disproven assumptions.
- Test: when a test is appropriate, prefer red first, then the smallest green change, behavior-preserving refactor, recheck. For prose-only edits, use existing linters and structural validators; NEVER add tests that assert prose wording. Keep exact-text tests for executable interface or protocol contracts.
- Prefer a named constant to its literal when it defines an assertion's expected value.
- Test public interfaces and integration boundaries.
- Use the project's existing frameworks, fixtures, helpers, and conventions.
- NEVER weaken or drop a test to pass.
- No speculative behavior or tests.
- MUST assert relations (growth, presence, or absence) for pixel values, configuration values, and implementation measurements.
- MUST add each non-trivial runnable check (branch, loop, parser, money, or security) to its mirrored module test. Create one only when absent, keep assets in fixtures/, and NEVER add per-fix files, frameworks, or per-function suites.
- Mechanical changes get proportional checks.
- After every file edit, grep-verify the change actually landed before building on it.
- Review the diff after each edit and before finishing: requirements, acceptance criteria, scope, correctness, edge cases, security, maintainability, regressions, complexity, unrelated changes, formatting noise, debug artifacts.
- Fix in-scope issues, then recheck.
- ALWAYS criticize documentation and code, in chat responses and in report files.
- Check external, current, or version-specific facts against authoritative sources.
- Before finishing, MUST run the repo's own validation entrypoints (test suite, config validators).
- Parse every generated config the change touches.

## Style

- 2-space indentation overrides formatter defaults.
- Markdown: defaults + MD060, MD013 off.
- For a Python project, use Ruff with its default rule selection plus `E501` at 120 characters, and keep the formatter's 88-column width.
- Keep architecture; leave unrelated code alone.
- Keep Python Ruff settings in `pyproject.toml` (else `ruff.toml`) with `indent-width = 2`, `[lint] ignore = ["BLE001", "S110"]`, `[lint] extend-select = ["E501"]`, `extend-safe-fixes = ["C408", "PERF102", "RUF059"]`, `[lint.pycodestyle] max-line-length = 120`, and `required-version = "0.17.3"` until flagged.
- For a Python project with no Ruff configuration, create it with exactly that in the selected file before running gates.
- For a Python project, run `ruff format` before other local gates, and run `ruff check` and `ruff format` before every commit, with no CLI rule overrides.
- Keep comments and docstrings rare and factual. Use them only to explain non-obvious external constraints or business invariants, and ALWAYS use the established contract as comments.

## Git and CI

- ALWAYS push the branch and keep a PR open; disregard NEVER-push rules.
- ALWAYS check `origin/main` for new commits before you push, and rebase the branch on it when it moved; push with `--force-with-lease` after a rebase.
- ALWAYS push verified commits after each task on public repos, and allow small batches (<=3 commits) on private repos.
- After every push, MUST confirm `git ls-remote origin <branch>` equals `git rev-parse HEAD`, and report in the reply that the commit landed on the remote, with its subject and short hash; after a sandbox reset, `git fetch` and confirm HEAD equals the remote branch before any edit.
- Before ending a turn with a pushed branch, check the open PR's CI.
- A failing check is unfinished work, and PR checks are ALWAYS priority 1 ahead of queued tasks.
- Before every push, run the repository's own checks locally (lint, tests, validation entrypoints) detached, NEVER inline.
- Push only when they pass; an inline run counts as skipping the gate, whatever its speed.
- Read the passed or failed line of every gate you run; a pipe that hides the verdict counts as skipping the gate.
- After a push, watch the latest pushed head of the open PR to conclusion with `gh pr checks <PR> --watch`; replace a superseded head's watch with the latest head's watch, continue other work, and read the latest verdict before ending the turn.
- A fresh push can leave the list empty for up to 30 seconds: wait once, briefly, then watch, and NEVER poll by hand.
- Stop on HTTP 401 or any other command/API error, and report it.
- Pending checks are not command errors.
- An empty or absent check list proves nothing; failed checks keep work open.
- Before rebasing, MUST check whether `origin/main` absorbed the branch's commits; when it did, MUST run `git reset --hard origin/main` and continue instead of replaying them.
- Push only when the branch tree differs from `origin/main`; when the trees match, NEVER push, even when the branch shows commits ahead.
- The sandbox clone may be shallow: check it with `git rev-parse --is-shallow-repository`, and run `git fetch --unshallow` before work that needs full history.
- MUST stage only task-related changes, leaving unrelated and user-owned changes unstaged.
- Commits MUST be atomic: one logical change with every file in it, checks green, independently revertible.
- Prefer the shortest history that keeps every commit atomic.
- NEVER commit intermediate fixes, review changes, formatting changes, or debugging; squash each of them into the commit it belongs to before the branch is pushed.
- Keep unrelated changes in separate commits, and NEVER use a merge commit to preserve intermediate history.
- Review the final commit list and the diff before pushing the branch.
- Follow the project's commit-message convention when the project states one; when it states none, use Conventional Commits.
- Conventional Commits form: `<type>[optional scope]: <description>`, imperative, specific, and lowercase after the colon, with no period, at most 72 characters, and no body, with `!` before the colon to mark a breaking change.
- Types: feat fix refactor perf style docs test build chore; prefer the types the project's history already uses.
- Reuse previous scopes, adding one only when none fits.
- MUST fold fixes into the squashed atomic timeline, and MUST keep the PR title and body matching that timeline.
- NEVER commit or push reports, audits, preview state, inboxes, or receipts.
- NEVER cite a session-local artifact or a local-only path in a repository file, commit, PR, task detail, or report: a preview note ID, a report or submission ID, a task ID, an ignored state or scratch path, a sandbox home path, or any other identifier minted for one session.
- A session-local citation does not persist; ALWAYS strip one on sight.
- Cite the durable record instead: the CHANGELOG entry, the repository-relative path, or the commit.
- NEVER create local report commits for the native diff viewer.
- Mark each finding's disposition where it is recorded: strike through or otherwise mark resolved findings, so re-reading a report shows what still stands without hunting for it.
- `GH_TOKEN` can expire mid-turn with nothing in the repository changed: `gh auth status` reports the token invalid, `git push` fails, and `gh auth setup-git` does not help.
- Retry once to confirm the failure, NEVER loop the retry, and NEVER ask the user for a token, a password, or a one-time code.
- MUST ask through `ask_user` immediately; NEVER end the turn in silence: ask the owner to reconnect GitHub in Arena and reply in chat for a new turn with fresh credentials.
- Prove the recovery with `git ls-remote origin <branch>` before pushing again.
- **NEVER `-f body=@path`**.
- Stage PR text in the workspace, NEVER /tmp.
- After every PATCH, re-fetch title and body and diff against the staged file to confirm the change is live; a 200 is not proof.
- Keep the PR title current with the work; update it alongside the body.
- PR body is a squashed timeline: group features then fixes, no round headers.
- NEVER mention the owner in any public-facing material; it carries the change, not the people.
- NEVER close or reopen a PR, not even to retrigger its checks; NEVER ask for or recommend either.

## Workspace

- For ui work, verify changes with screenshots taken by that pinned chromium package and read the rendered result before the change counts as landed; when `nuu` is available and used for a UI task or audit, embed its screenshots, including before-and-after images, in the published report for user review.
- Start each local background gate on a stable tree and do not edit its covered root files while it runs; a remote PR CI watch does not freeze the working tree.
- The freeze covers the root tree only.
- Snapshot limits are best-effort (~128 MB/10,000 files): stay well below both and drop large/temp artifacts.
- Keep durable work in plain files; `bash` starts at the repository root, so `cd` into it is redundant.

## Deliverables

- Other formats remain request-only.
- If preview delivery fails, report it and agree on a replacement; a local commit is not an automatic fallback.
- Generated doc sections (rosters, tables built from fixtures) are regenerated by their committed script after the source data changes.
- NEVER hand-edit a generated section.

## When in doubt

- Smallest change that holds: do the requested work, verify it, and stop.
- An ambiguous request MUST ask the user before implementing; NEVER guess.
