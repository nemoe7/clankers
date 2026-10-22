# AGENTS.md

## Use

- MUST apply these repository rules to every task and session here unless explicit user chat instructions override them.
- A bare imperative is a hard rule. MUST, NEVER, and ALWAYS restate the hardest ones; prefer marks a soft rule.

## Arena-specific instructions

- ARENA.md wins on Arena-specific handling, including pushing, pull requests, and merges.
- Read maintenance/README.md for the general procedure, the token-measurement note and the steering history.
- Only Arena agents MUST publish a proposal through the `arena-skill` skill in an ignored workspace file; its approval question is a fielded report field, and blind approval approves nothing.
- Keep one ignored Markdown report per logical change, update it in place and publish its stable ID through the shared preview.

## Constitution

- Run `python3 maintenance/check.py` after changing skills, rules, workflows, or README budgets.
- NEVER claim a check you did not run.
- For each dependency advisory, check whether a later dependency version fixes it; report it only when a fix is available, and otherwise ignore it.
- Compression removes words, NEVER rules.
- New clause: squash only that new line.
- Amended clause: squash only the affected line.
- Deleted clause: attempt one squash and keep whichever budget is lower.
- Use a Conventional Commit subject, no body.
- Stage only task-related files; leave unrelated and user-owned files unstaged.
- Keep one CHANGELOG entry per date, extending it while the date holds.
- Use dates as versions: a date heading reads `## YYYY-MM-DD`, with no bracket and no repeated date.
- Group changes by [Keep a Changelog](https://keepachangelog.com/) type and then domain.
- Omit Unreleased.
- Omit version numbers from CHANGELOG entries.

## Precedence

- Guide for agents working in this repository: these rules apply to every task and session here, whether or not a prompt repeats them.
- They outrank skill and plugin instructions.
- An explicit user instruction in chat outranks this file, confirmed in one line.

## Setup

- Your first action in a new session is to read this file end-to-end.
- ARENA.md's NEVER-edit-this-file clause is waived in this repository, the home of that file (refs, live and root copies) and the preview skill.
  - Mirror task-related source changes into installed copies in this repository without separate user authorization.
  - Follow the clause-proposal and approval scope in [Reports and approval](#reports-and-approval).

## Glossary

- arena = [ARENA.md](ARENA.md)
- house = this repository; house rules = root AGENTS.md
- arena suite = ARENA.md and arena-skill files

Read these first:

- [README.md](README.md) — budgets, compression procedure, layout
- [CHANGELOG.md](CHANGELOG.md) — rule history
- [rules/README.md](rules/README.md) — rule structure, installation, maintenance
- [rules/refs/GUIDELINES.md](rules/refs/GUIDELINES.md) — the standard for writing an AGENTS.md; audit rule files against it
- [skills/README.md](skills/README.md) — skill format, upstream sources, install notes
- [maintenance/README.md](maintenance/README.md) — validation and measurement tooling

## Repository type

- Treat this as a rules/skills/workflows repository with maintenance build tooling and tests.
- `maintenance/check.py` needs `markdown-it-py` and the npm package `gpt-tokenizer`.
- It validates live skill metadata, baseline/live skill parity, workflow frontmatter, README measurements, internal links, both ChatGPT character limits, and skill licensing for adapted skills.
  - It also checks the markdownlint scope, refs/live rule parity, and the root `ARENA.md` copy.
- `.github/workflows/ci.yml` runs `python maintenance/check.py --update` on PRs targeting any branch, except changes limited to its `paths-ignore` list, and after every push to `main`.
- It runs Ruff at the version `ruff.toml` pins, compiles the maintenance script, and lints Markdown with markdownlint-cli2.

## Verification

1. `npx --yes markdownlint-cli2` from the repository root, with no extra globs.
2. `ruff check .` and `ruff format --diff .` at the version `ruff.toml` pins.
3. `python3 maintenance/check.py` (`python` on Windows); add `--update` to refresh README measurements. It gates the root copy: `ARENA.md` stays byte-identical to `rules/ARENA.md`, which `.github/workflows/distribute.yml` pushes to the target repositories.

## Rules

- Agent-facing rule files live in `rules/`: the generic core `CORE.md` and the platform overlays `CLINE.md`, `KILO.md`, `ARENA.md`, `CHATGPT-CUSTOM.txt`, `CHATGPT-MORE.txt`.
- Baseline skill trees live in `skills/refs/`: amend them first, keep supporting files mirrored, then squash only the live `SKILL.md`; refs are not installed or distributed.
- Mode-specific Kilo overrides live in `rules/refs/kilo/`: `plan.md`, `code.md`, `debug.md`.
  - Keep compressed live copies in `rules/kilo/`, each with a blank first line, a `### Native <mode> Agent Overrides` heading, and the clause that it wins over a native reminder.
- Installing them via `rules/apply.py` or `apply.bat` is human maintenance, not an agent task.
- Amend `rules/refs/` first, mirror the amendment into its live counterpart in `rules/` in compressed form, and for the ChatGPT fields also into `rules/wenyan/`, then squash only the new or affected line.
  - On a deletion, attempt one squash and keep the lower budget; refs stay uncompressed as the baseline, and copying one verbatim would exceed every budget.
- The CHANGELOG is the only ledger, with no separate amendment file.
- No size diffs or budget changes in CHANGELOG.md.
- Before suggesting any amendment, read [rules/refs/GUIDELINES.md](rules/refs/GUIDELINES.md), cite at least one of its sections in the proposal, and draft the line to its section 4 (one rule per line, imperative, testable); write every rule file to that standard.

## Reports and approval

- Amend this file when a rule or decision proves durable and repo-wide; otherwise edit only when asked.
- MUST include ARENA and CHATGPT amendment proposals in the same report as each CORE amendment proposal.
- MUST name the failure and the check that verifies each proposed amendment.
- Apply this section's AGENTS.md proposal and approval requirements only to `rules/**/CORE.md`; other AGENTS.md files are exempt.
- Any agent-facing material MUST NEVER contain rationale, narrative, or facts that drive a clause.
- Before editing a clause, show the proposal under each refs file path, live mirrors omitted: one `Line | Diff | Reason` row per changed line.
  - Quote the exact final clause verbatim below its table, without diff markup or deleted text; treat text as verbatim when the user says "verbatim" or "as is" or quotes it with double quotes, NEVER a Markdown `>` quote.
  - In Diff, keep unchanged wording verbatim, strike only removed text with ~~...~~, highlight only inserted text with ==...==, and omit change labels.
  - Omit only unchanged context with `...`.
  - Quote clauses in double quotes, NEVER backticks, in proposals, acks, and reports.
  - Each clause takes approve, squash (re-propose squashed via the `squash` skill; do not land), reject, or custom.
  - Put its options directly under its row, and start a new table for the next clause under the same file heading.
  - Put it above form fields; a form without it is not a proposal.
  - Open the report with `Status: proposal. No line lands before approval.` and a `Citation:` line naming the GUIDELINES section.
  - Follow each table with `Decision on the amended line:` and the approve, squash, reject and custom options.
  - Code changes need no proposal; keep them lean.
- Proposals come before any task: in a turn that holds both, show every proposal first, then start tasks.
- Run an amendment proposal task first, before any other queued work.
- NEVER commit or push report artifacts.
- A report that fits in chat stays in chat; omit its Markdown artifact and reporting pipeline.
- Ledger prose: neutral wording — actions, files, numbers; no narrative, rationale or story.
- Every entry terse: one entry per event, no story between facts.
- Short chat reports: concise on phone and vertical monitors; limit prose; no essays unless strictly necessary; digestible; MUST ASD-STE100; no skill or linter.
- Chat text and reports: at most 3 sentences per block; keep terse.
- No clause in a rule, skill, workflow or system-prompt file is added, amended, or deleted until the user approves the report; hold the work and say so in one line.
- Edits that change no clause — a squash that removes no rule, a typo or link fix, formatting, a re-measure — need no report.
- For skills, restrict this section's clause-proposal and approval requirements to first-party agent-facing text; unchanged third-party copies are exempt.
- Every clause change takes a proposal on its initial refs wording, owner-supplied text included; the compressed live mirrors and platform copies follow the approved line.
- A custom answer on a clause takes a fresh proposal of the new wording; the line lands only after that proposal is approved.
- Report at the level the user approves from — the change and why, not a patch; a report is not a diff.
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
- ALWAYS bump a module's respective version numbers after edits.
- Skills in `skills/` follow the [Agent Skills specification](https://agentskills.io/specification).
- Every `SKILL.md` needs YAML frontmatter using only `name`, `description`, `license`, `compatibility`, `metadata`, `allowed-tools`.
- `name` matches its directory.
- Record `metadata.upstream` for adapted skills.
- The file stays under 500 lines.
- A skill holds only what an agent needs to use it. NEVER add a design decision, background, rationale or history; those go to [CHANGELOG.md](CHANGELOG.md) or [docs/archive/arena-quirks.md](docs/archive/arena-quirks.md).

## Automations

- Automation prompts live in `automations/`: self-contained text pasted into an external scheduler, not rules an agent loads.
- [automations/DAILIES.md](automations/DAILIES.md) is the daily monitoring prompt for a ChatGPT scheduled task, which runs unattended at most once a day and also on request.
  - Web search and the GitHub connector are its tools, with a terminal and local files only when the task itself decides it needs them; a prompt MUST not depend on them.
  - The connector can read and write in this repository; the prompts repeat no git rule.
  - The [gpt-github](gpt-plugins/skills/gpt-github/SKILL.md) skill manages ChatGPT's behavior when using GitHub.
  - Reports go to the chat response and nothing is persisted.
- Prompts carry no budget row and no validator gate, both declined on request rather than deferred.
  - The scheduler owns its own copy and edits the embedded datetime between runs; CI MUST not depend on their contents.
- Amend one here, then re-paste it into the task: an edit in the repo NEVER reaches a running automation.

## Style

- 2-space indentation, overriding formatter defaults.
- No hard-wrapped prose: one line per paragraph, list item, and table row, soft-wrapped by the editor.
- markdownlint covers `rules/**/*.md` — 11 files, `rules/refs/` included — and excludes root-level `*.md`, `skills/**`, the ChatGPT text files, `rules/README.md`, and `rules/refs/kilo/**`.
  - **MD060 enabled**, **MD013 disabled**.
- Python: Ruff, configured by `ruff.toml`, which owns the selection and the pinned version.
- Simplified Technical English: write and edit the documentation prose of this repository in ASD-STE100.
  - The covered files are `docs/`, every `README.md`, and `CHANGELOG.md`.
  - The vendored linter at `.agents/skills/asd-ste100/scripts/ste-lint.py` reports violations, and MUST pass on the text you add or change in those files.
  - Rules, skills and agent-facing files such as this one stay outside the linter's scope.
  - A copy of a third-party file stays outside it too, because the copy belongs to its upstream: no rewrite of a vendored file, and no path into the gate for one.

- Squash every `README.md` and every file in `docs/` against the [compression procedure](README.md#compression); prose is not exempt.

## Git

- Commit on a branch other than `main`, one logical change per commit with every changed file in it.
- One Conventional Commit subject per change: `<type>(scope): <subject>` — imperative, specific, lowercase after `:`, no period, at most 72 chars, no body.
- Types: `feat fix refactor perf style docs test build chore`.
- Merges MUST be rebase merges: rebase onto the target, then merge; no merge commit.
- A commit call NEVER shares a shell line with the gates that judge it.

## Boundaries

- Add no further CI workflows, dependency manifests, test scaffolding, or tooling installs unless explicitly requested.
- Treat installed rule copies as read-only; installing them is human maintenance.
- Review changes directly in the diff; every changed file belongs to the task.
- Keep scratch files, scripts, and generated plan files out of every commit.

## When in doubt

- Smallest change that holds: make the requested change, run the gates above, and stop.
- When that does not settle it, stop and ask rather than improvise.
