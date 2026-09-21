# CLINE.md

## Command discipline

- MUST run exactly the command the user gave.
- NEVER add an extra command or follow-up action.
- After a requested command, report the output and **STOP**.
- NEVER edit, fix, refactor, or "continue the job" unless explicitly told to.
- Empty or clean output is not a mandate to act.
- Example: a `git status` with nothing to commit means report "clean, nothing to do" and wait — NEVER start changing files.
- **NEVER self-assign next steps, improvements, or work between turns**.
- When the task is done, stop and await instruction.
- If output surfaces a problem worth fixing, mention it briefly and ask — NEVER fix it unprompted.

## Cline tools

- Cline built-ins (v4.1.17): `read_files`, `search_codebase`, `run_commands`, `fetch_web_content`, `editor`, `apply_patch`, `skills`, `ask_question`, `submit_and_exit`.
- Use `read_files`, `search_codebase`, `editor` to read, search, list, create, edit, and inspect files.
- Use `run_commands` only for execution: tests, linters, formatters, builds, git, application commands.
- NEVER use it, shell scripts, pipes, redirection, or temporary scripts as substitutes for file tools.
- MUST edit files only with `editor` / `apply_patch`.
- If write tools are blocked or unavailable: stay read-only, modify nothing by other means, report the limitation.
- Use `fetch_web_content` for web retrieval.
- Use `ask_question` when clarification is needed.
- Tool priority: file tools for inspection and edits; `run_commands` for execution only.
- Pick the fitting tool.
- NEVER call a tool merely to satisfy these rules.
- If a required tool fails for a non-syntax reason, report the failure.
- NEVER retry or work around it, except per Test Timeout.

## Test Timeout

- Run tests normally and observe the result.
- Only if a test times out (does not exit), use this alternative:
  - Redirect test output to `.test-output.tmp`.
  - Wait with `ping` at most 30 seconds; treat non-exit as failure.
  - Inspect output with file tools.
  - MUST delete `.test-output.tmp` on success, failure, or timeout.

## When in doubt

- Run the requested command, report the output, and stop; await instruction.
