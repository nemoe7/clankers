# CLINE.md

## Command discipline

- MUST run exactly the command the user gave.
- NEVER add an extra command or follow-up action.
- After a requested command, MUST report the output and **STOP**.
- NEVER edit, fix, refactor, or "continue the job" unless explicitly told to.
- Empty or clean output is not a mandate to act.
- **NEVER self-assign next steps, improvements, or work between turns**.
- When done, MUST stop and await instruction.
- If output shows problems worth fixing, briefly report and ask — NEVER fix them unprompted.

## Cline tools

- Use `run_commands` only for execution: tests, linters, formatters, builds, git, application commands.
- NEVER use it, shell scripts, pipes, redirection, or temporary scripts as substitutes for file tools.
- MUST edit files only with `editor` / `apply_patch`.
- If tools cannot write, report it and stay read-only; NEVER modify by other means.
- NEVER call a tool merely to satisfy these rules.
- If a required tool fails for a non-syntax reason, MUST report the failure.
- NEVER retry or work around it, except per Test Timeout.

## Test Timeout

- Run tests normally; observe the result.
- Only on test timeout (non-exit):
  - Redirect test output to `.test-output.tmp`.
  - Wait with `ping` at most 30 seconds; treat non-exit as failure.
  - Inspect output with file tools.
  - MUST delete `.test-output.tmp` on success, failure, or timeout.

## When in doubt

- MUST run the requested command, report the output, and stop; await instruction.
