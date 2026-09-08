# CLINE.md

Cline-specific rules. Generic rules load from the global AGENTS.md (Cline reads it); not repeated here.

## Command discipline

- Run exactly the command the user gave; add no extra commands or follow-up actions.
- After a requested command, report the output and STOP. Do not edit, fix, refactor, or "continue the job" unless explicitly told to.
- Empty or clean output is not a mandate to act: a `git status` with nothing to commit means report "clean, nothing to do" and wait — never start changing files.
- Never self-assign next steps, improvements, or work between turns; when the task is done, stop and await instruction.
- If output surfaces a problem worth fixing, mention it briefly and ask — do not fix it unprompted.

## Cline tools

Cline built-ins (v4.1.17): `read_files`, `search_codebase`, `run_commands`, `fetch_web_content`, `editor`, `apply_patch`, `skills`, `ask_question`, `submit_and_exit`.

- Use `read_files`, `search_codebase`, `editor` to read, search, list, create, edit, and inspect files.
- Use `run_commands` only for execution: tests, linters, formatters, builds, git, application commands. Never use it, shell scripts, pipes, redirection, or temporary scripts as substitutes for file tools.
- Edit files only with `editor` / `apply_patch`. If write tools are blocked or unavailable: stay read-only, modify nothing by other means, report the limitation.
- Use `fetch_web_content` for web retrieval; `ask_question` when clarification is needed.
- Tool priority: `tokensave` and file tools for inspection and edits; `run_commands` for execution only. Pick the fitting tool; never call tools merely to satisfy these rules.
- If a required tool fails for a non-syntax reason, report the failure instead of retrying or working around it (except Test Timeout).

## MCPs

Use only if installed/configured; never invent tool names.

- `tokensave`: code search, navigation, context retrieval, callers/callees, impact analysis — when applicable.
- `context7`: dependency/library API docs — at most 3 calls per user input.
- `memory`: persistent cross-session memory — store/recall relevant facts when applicable.

## Test Timeout

Run tests normally and observe the result. Only if a test times out (does not exit), use this alternative:

- Redirect test output to `.test-output.tmp`.
- Wait with `ping` at most 30 seconds; treat non-exit as failure.
- Inspect output with file tools.
- Delete `.test-output.tmp` on success, failure, or timeout.
