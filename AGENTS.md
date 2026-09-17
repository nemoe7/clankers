# AGENTS.md

## Use

- Guide for agents working in this repository: these rules apply to every task and session here, whether or not a prompt repeats them.
- They outrank skill and plugin instructions.
- An explicit user instruction in chat outranks this file, confirmed in one line.
- In Arena, MUST also read and follow [ARENA.md](ARENA.md) as an additional ruleset before your first edit; it wins on Arena-specific handling, including pushing, pull requests, and merges.
- Amend this file when a rule or decision proves durable and repo-wide; otherwise edit only when asked.

Read these first:

- [README.md](README.md) — budgets, compression procedure, layout
- [CHANGELOG.md](CHANGELOG.md) — rule history and token changes
- [rules/README.md](rules/README.md) — rule structure, installation, maintenance
- [rules/refs/GUIDELINES.md](rules/refs/GUIDELINES.md) — the standard for writing an AGENTS.md; audit rule files against it
- [skills/README.md](skills/README.md) — skill format, upstream sources, install notes
- [workflows/README.md](workflows/README.md) — workflow format, portability, usage
- [maintenance/README.md](maintenance/README.md) — validation and measurement tooling

## Constitution

- Run `python3 maintenance/check.py` after changing skills, rules, workflows, or README budgets.
- NEVER claim a check you did not run.
- Compression removes words, never rules.
- A new rule may exceed a budget only if the same change compresses the rest of the file.
- Use a Conventional Commit subject, no body.
- Stage only task-related files.
- Keep one CHANGELOG entry per pull request, extending the open entry while that pull request is unmerged.

## Repository type

- A rules/skills/workflows repository, not a software project: no build system, package manifest, or test suite.
- `maintenance/check.py` needs `markdown-it-py` and `tiktoken`.
- It validates skill metadata, workflow frontmatter, README measurements, internal links, both ChatGPT character limits, skill licensing for adapted skills, the markdownlint scope, refs/live rule parity, and the root `ARENA.md` copy.
- `.github/workflows/validate.yml` runs `python maintenance/check.py --update` on every push and pull request.
- On pushes it commits refreshed README measurements; it also runs Ruff at the version `ruff.toml` pins, compiles the maintenance script, and lints Markdown with markdownlint-cli2.

## Verification

1. `npx --yes markdownlint-cli2` from the repository root, with no extra globs.
2. `ruff check .` and `ruff format --diff .` at the version `ruff.toml` pins.
3. `python3 maintenance/check.py` (`python` on Windows); add `--update` to refresh README measurements. It gates the root copy: `ARENA.md` stays byte-identical to `rules/ARENA.md`, which `.github/workflows/distribute-arena.yml` pushes to the target repositories.
4. Arena sandbox only: install the two dependencies into a venv, since system `pip` refuses under PEP 668, and seed the `tiktoken` cache by hand, since `openaipublic.blob.core.windows.net` and `raw.githubusercontent.com` are unreachable there while `api.github.com` answers. Fetch `niieani/gpt-tokenizer` `data/cl100k_base.tiktoken` with `gh api -H "Accept: application/vnd.github.raw" repos/niieani/gpt-tokenizer/git/blobs/<sha>` and save it as `$TIKTOKEN_CACHE_DIR/<first 40 hex of sha1 of the cl100k_base blob URL>`; use `~/.cache/tiktoken`, which snapshots exclude, and run `check.py` with `TIKTOKEN_CACHE_DIR` set. [maintenance/README.md](maintenance/README.md) has the general procedure. The same allowlist blocks `ntfy.sh`, every public ntfy instance, and 23 other notification, paste, chat, webhook, and Google hosts for processes in the sandbox, which is not the whole story: the agent's own page-fetch path is not behind it, and it read `ntfy.sh`, `dns.google`, and public gist content on 2026-09-16, all three closed to these sockets. So `skills/arena-live-steering` carries notes over an ntfy topic, which needs no account and publishes instantly, and reads it only through the agent's page-fetch path, never through curl or another in-sandbox HTTP client, because the egress proxy answers an in-sandbox GET with a fake empty 200 even while the topic holds messages.

## Rules

- Agent-facing rule files live in `rules/`: the generic core `AGENTS.md` and the platform overlays `CLINE.md`, `KILO.md`, `ARENA.md`, `CHATGPT-CUSTOM.txt`, `CHATGPT-MORE.txt`.
- Mode-specific Kilo overrides live in `rules/refs/kilo/`: `plan.md`, `code.md`, `debug.md`. They are refs-only, and each opens with a blank line, a `### Native <mode> Agent Overrides` heading, and the clause that it wins over a native reminder.
- Installing them via `rules/apply.py` or `apply.bat` is human maintenance, not an agent task.
- Amend `rules/refs/` first, mirror the amendment into its live counterpart in `rules/` in compressed form, then squash that file back under its budget; refs stay uncompressed as the baseline, and copying one verbatim would exceed every budget.
- Write every rule file to [rules/refs/GUIDELINES.md](rules/refs/GUIDELINES.md).

## Reports and approval

- Propose before editing: report the intended change as a table with `Current`, `Amended`, and `Reason` columns, one row per changed line, citing its line number; truncate a long line but never omit it.
- No rule, skill, script, or workflow file is edited until the user approves the report; hold the work and say so in one line.
- Report at the level the user approves from — the change and why, not a patch; a report is not a diff.
- Keep one report file per change in a git-ignored output dir, updated in place across turns, committed locally only and never pushed.

## Budgets

- Rule files, `SKILL.md` entry points, and workflow files have budgets tracked in [README.md](README.md#instruction-budgets).
- Re-measure and update the table when changing them.

## Skills

- Skills in `skills/` follow the [Agent Skills specification](https://agentskills.io/specification).
- Every `SKILL.md` needs YAML frontmatter using only `name`, `description`, `license`, `compatibility`, `metadata`, `allowed-tools`.
- `name` matches its directory.
- Adapted skills record `metadata.upstream`; first-party ones record `metadata.origin`.
- The file stays under 500 lines.

## Workflows

- Workflows in `workflows/` are portable across coding-agent platforms: the workflow body depends on no platform-specific tool, name, or mechanism.
- Each workflow is a self-contained Markdown file with a `description` frontmatter field.

## Automations

- Automation prompts live in `automations/`: self-contained text pasted into an external scheduler, not rules an agent loads.
- [automations/DAILIES.md](automations/DAILIES.md) is the daily monitoring prompt for a ChatGPT scheduled task, which runs unattended at most once a day and also on request: web search and the GitHub connector are its tools, with a terminal and local files only when the task itself decides it needs them, so a prompt must not depend on them. The connector can read and write in this repository, and the prompts repeat no git rule, because pushes, branches, and pull requests are already gated by the git rules in [rules/CHATGPT-CUSTOM.txt](rules/CHATGPT-CUSTOM.txt), which that account loads on every request including a scheduled one. Reports go to the chat response and nothing is persisted.
- Prompts carry no budget row and no validator gate, both declined on request rather than deferred, because the scheduler owns its own copy and edits the embedded datetime between runs; CI must not depend on their contents.
- Amend one here, then re-paste it into the task: an edit in the repo never reaches a running automation.

## Style

- 2-space indentation, overriding formatter defaults.
- No hard-wrapped prose: one line per paragraph, list item, and table row, soft-wrapped by the editor.
- markdownlint covers `rules/**/*.md` — 10 files, `rules/refs/` included — and excludes root-level `*.md`, `skills/**`, the ChatGPT text files, `rules/README.md`, and `rules/refs/kilo/**`; **MD060 enabled**, **MD013 disabled**.
- Python: Ruff default selection (E4, E7, E9, F), configured by `ruff.toml`, which pins `required-version = "0.16.6"`.

## Git

- Commit on a branch other than `main`, one logical change per commit with every changed file in it.
- One Conventional Commit subject per change: `<type>(scope): <subject>` — imperative, specific, lowercase after `:`, no period, at most 72 chars, no body.
- Types: `feat fix refactor perf style docs test build chore`.
- Merges MUST be fast-forward when possible; if the branch has diverged from the target, rebase onto the target first, then fast-forward.

## Boundaries

- Add no further CI workflows, dependency manifests, test scaffolding, or tooling installs unless explicitly requested.
- Treat installed rule copies as read-only; installing them is human maintenance.
- Review changes directly in the diff; every changed file belongs to the task.
- Keep scratch files, scripts, and generated plan files out of every commit.

## When in doubt

- Smallest change that holds: make the requested change, run the gates above, and stop.
- Where this file, `rules/`, and `ARENA.md` disagree, the more specific file wins.
- When that does not settle it, stop and ask rather than improvise.
