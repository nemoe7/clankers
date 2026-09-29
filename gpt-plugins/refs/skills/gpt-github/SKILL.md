---
name: gpt-github
description: MUST use for every git or GitHub action.
---

# GPT GitHub

Apply these rules to every git and GitHub action, including through the GitHub connector and in scheduled tasks.

## Repository discovery

- Prefer `mcp__GitHub__fetch` to inspect repository trees, directories, and files before using `fetch_file`; do not guess file paths. Use `fetch_file` only after the path is established, and batch discovery where practical to avoid unnecessary connector calls and tool-call limits. Verify available GitHub tools before concluding an operation is unsupported.

## Pull requests and merges

- ALWAYS PR.
- ALWAYS rebase merge.
- NEVER end turn until CI is green.
- ALWAYS check `.github/workflows/` for a workflow that runs on the PR; with none, say so and skip the wait.
- No check yet is pending, not green.
- Poll checks until each has a conclusion; NEVER end early.
- After every push that changes the pull request head, record the new head SHA and locate the workflow runs for that SHA; a run for an earlier commit verifies nothing, and an absent run is a pending state.
- Treat a missing, queued, in-progress or pending check as not complete, and a failed, cancelled or timed-out check as not green; inspect the failure, repair the branch and repeat the poll from the new head SHA.
- Treat the pull request as green only when every applicable check reaches a successful conclusion; an empty status response is not success.
- NEVER end turn after a push while the new head SHA has no completed workflow run.
- NEVER litter the PR with multiple commits.

## Commits

- Atomic task-only commits.
- Print the planned final commit list, every commit you intend to land with one message per logical change, before committing.
- Review the diff after each edit.

## Commit messages

- Follow the project's commit convention when it states one; otherwise Conventional `<type>[optional scope]: description`, imperative, lowercase after ":", no period, <=72 characters, no commit body, with "!" before the colon for a breaking change.
- Types: `feat fix refactor perf style docs test build chore`; the specification mandates only `feat` and `fix`; prefer the types the project's history already uses.
- Reuse previous scopes, adding one only when none fits.
