# CLINE.md

## Command discipline

- MUST run only the user's exact command.
- NEVER add extra commands or follow-ups.
- After a requested command, MUST report the output and **STOP**.
- NEVER edit, fix, refactor, "continue the job" unless explicitly told to.
- Empty or clean output is not a mandate to act.
- **NEVER self-assign next steps, improvements, or work between turns**.
- When done, MUST stop and await instruction.
- If output shows problems worth fixing, briefly report and ask — NEVER fix them unprompted.

## Cline tools

- Use `run_commands` only for execution: tests, linters, formatters, builds, git, application commands.
- NEVER substitute it, shell scripts, pipes, redirection, or temporary scripts for file tools.
- MUST edit only with `editor` / `apply_patch`.
- If tools cannot write: stay read-only, report it; NEVER modify otherwise.
- NEVER call a tool merely to satisfy these rules.
- On a required tool's non-syntax failure, MUST report it.
- NEVER retry or work around it, except per Test Timeout.

## Test Timeout

- Run tests normally; observe the result.
- Only on test timeout (non-exit):
  - Redirect test output to `.test-output.tmp`.
  - Wait with `ping` ≤30 seconds; treat non-exit as failure.
  - Inspect output with file tools.
  - MUST delete `.test-output.tmp` on success, failure, timeout.

## When in doubt

- Run the requested command, report output, stop; await instruction.
