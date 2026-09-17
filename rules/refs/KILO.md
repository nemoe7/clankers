# KILO.md

## Use

- Kilo Code rules only, specific to this platform: they never repeat the core `AGENTS.md`, which stays in force beside them.
- They apply to every Kilo Code session, whatever the mode.
- Where a mode's native reminders collide with the mode override files in `kilo/`, the override wins.

## Tools

- ALWAYS call `kilo_memory_save` when you gain additional context.
- ALWAYS manage the TODO list with `todowrite` and `todoread`.
- ALWAYS include commit steps in the TODO list, each with its commit message.

## Modes

- Mode-specific overrides live in `kilo/`, one file per mode: `kilo/plan.md`, `kilo/code.md`, `kilo/debug.md`.
- Read the override file for the mode you are in, and follow it where it collides with a native reminder.

## When in doubt

- The core `AGENTS.md` settles it; where the core is silent, ask rather than improvise.
