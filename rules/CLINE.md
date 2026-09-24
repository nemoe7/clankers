# CLINE.md

## Command discipline

- MUST run exactly the user's command.
- NEVER add commands or follow-up actions.
- After running it, report output and **STOP**.
- NEVER edit, fix, refactor, or continue unless explicitly told.
- Empty or clean output is not a mandate to act.
- Example: `git status` with nothing to commit means report "clean, nothing to do" and wait — NEVER start changing files.
- **NEVER self-assign next steps, improvements, or work between turns**.
- When done, stop and await instruction.
- If output shows a problem worth fixing, briefly report it and ask — NEVER fix it unprompted.

## Cline tools

- Cline built-ins (v4.1.17): `read_files`, `search_codebase`, `run_commands`, `fetch_web_content`, `editor`, `apply_patch`, `skills`, `ask_question`, `submit_and_exit`.
- Use `read_files`, `search_codebase`, `editor` to read, search, list, create, edit, and inspect files.
- Use `run_commands` only for execution: tests, linters, formatters, builds, git, and app commands.
- NEVER use it, shell scripts, pipes, redirection, or temporary scripts as file-tool substitutes.
- MUST edit files only with `editor` / `apply_patch`.
- If write tools are blocked/unavailable, report it and stay read-only; NEVER modify by other means.
- Use `fetch_web_content` for web retrieval.
- Use `ask_question` for clarification.
- Tool priority: file tools for inspection/editing; `run_commands` for execution.
- Pick the fitting tool.
- NEVER call a tool merely to satisfy these rules.
- If a required tool fails for a non-syntax reason, report it.
- NEVER retry or work around it, except per Test Timeout.

## Test Timeout

- Run tests normally; observe the result.
- Only on test timeout (non-exit):
  - Redirect test output to `.test-output.tmp`.
  - Wait with `ping` at most 30 seconds; treat non-exit as failure.
  - Inspect output with file tools.
  - MUST delete `.test-output.tmp` on success, failure, or timeout.

## When in doubt

- Run the requested command, report output, and stop; await instruction.