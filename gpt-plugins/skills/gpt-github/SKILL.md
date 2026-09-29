---
name: gpt-github
description: MUST use for every git or GitHub action.
---

# GPT GitHub

Apply to every git/GitHub action, including GitHub connector and scheduled tasks.

## Repository discovery

- Prefer `mcp__GitHub__fetch` for repository trees, directories and files before `fetch_file`; NEVER guess paths. Use `fetch_file` only for established paths. Batch discovery where practical to avoid unnecessary connector calls and tool-call limits. Verify available GitHub tools before concluding an operation is unsupported.

## Pull requests and merges

- ALWAYS PR.
- ALWAYS rebase merge.
- NEVER end turn until CI is green.
- ALWAYS check `.github/workflows/` for a workflow that runs on the PR; with none, say so and skip the wait.
- No check yet is pending, not green.
- Poll checks until each has a conclusion; NEVER end early.
- NEVER litter the PR with multiple commits.

## Commits

- Atomic task-only commits.
- Before committing, print the final planned commit list: every intended commit, one message per logical change.
- Review the diff after each edit.

## Commit messages

- Follow the project's stated commit convention; otherwise Conventional `<type>[optional scope]: description`, imperative, lowercase after ":", no period, <=72 characters, no commit body, with "!" before the colon for a breaking change.
- Types: `feat fix refactor perf style docs test build chore`; the specification mandates only `feat` and `fix`; prefer the project's historical types.
- Reuse previous scopes, adding one only when none fits.
