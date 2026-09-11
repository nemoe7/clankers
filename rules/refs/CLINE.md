# CLINE.md

Cline-specific rules. Generic rules load from the global AGENTS.md (Cline reads it); not repeated here.

## Command discipline

- MUST run exactly the command the user gave; NEVER add an extra command or follow-up action.
- After running a requested command, report the output and **STOP**. NEVER edit, fix, refactor, or otherwise "continue the job" unless explicitly told to.
- Empty or clean output is not a mandate to act. Example: a `git status` with nothing to commit means report "clean, nothing to do" and wait — NEVER start changing files.
- **NEVER self-assign next steps, improvements, or work between turns**. When the requested task is done, stop and await the next instruction.
- If output surfaces a problem worth fixing, mention it briefly and ask — NEVER fix it unprompted.

## Cline tools

Cline built-ins (v4.1.17): `read_files`, `search_codebase`, `run_commands`, `fetch_web_content`, `editor`, `apply_patch`, `skills`, `ask_question`, `submit_and_exit`.

- Use `read_files`, `search_codebase`, `editor` for reading, searching, listing, creating, editing, and inspecting files.
- Use `run_commands` only for actual execution: tests, linters, formatters, builds, git, and application commands.
- NEVER use `run_commands`, shell scripts, pipes, redirection, or temporary scripts as substitutes for file tools.
- MUST edit files only with `editor` / `apply_patch`. If write tools are blocked or unavailable: stay read-only, modify nothing by any other means, and report the limitation.
- Use `fetch_web_content` for web retrieval; `ask_question` when clarification is needed.
- Tool priority: `tokensave` and file tools (`read_files`/`search_codebase`/`editor`) for inspection and edits; `run_commands` for execution only.
- Use the most appropriate tool for the operation; NEVER call a tool merely to satisfy these rules.
- If a required tool fails for a non-syntax reason, report the failure; NEVER retry or work around it (except Test Timeout).

## MCPs

Use only if installed/configured; NEVER invent tool names.

- `tokensave`: code search, navigation, context retrieval, callers/callees, impact analysis — when applicable.
- `context7`: dependency/library API docs — at most 3 calls per user input.
- `memory`: persistent cross-session memory — store/recall relevant facts when applicable.

## Test Timeout

Run tests normally and observe the result. Only if a test does time out (does not exit), use the protocol below as an alternative:

- Redirect test output to `.test-output.tmp`.
- Wait with `ping` at most 30 seconds; treat non-exit as failure.
- Inspect output with file tools.
- MUST delete `.test-output.tmp` on success, failure, or timeout.
