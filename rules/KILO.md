# KILO.md

## Use

- Kilo Code only: these rules never repeat the core `AGENTS.md`, which stays in force beside them.
- They apply in every Kilo Code session, whatever the mode; where a native reminder collides with a mode override file, the override wins.

## Tools

- ALWAYS call `kilo_memory_save` when you gain additional context.
- ALWAYS manage the TODO list with `todowrite` and `todoread`.
- ALWAYS include commit steps in the TODO list, each with its commit message.
- Run shell commands in PowerShell (`pwsh`), not Bash.

## Modes

- Mode overrides live in `kilo/`, one per mode: `plan.md`, `code.md`, `debug.md`; read the one for your mode and follow it over any native reminder.

## When in doubt

- The core `AGENTS.md` settles it; where it is silent, ask rather than improvise.
