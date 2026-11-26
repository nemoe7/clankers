# KILO.md

## Tools

- ALWAYS call `kilo_memory_save` on new durable facts about the project: decisions, constraints, conventions, corrections.
- NEVER save environment facts (shell, venv, paths, tools, commands) that break when the environment changes.
- MUST manage the TODO list strictly for every implementation task: create it with `todowrite` before starting, update status with `todowrite` after every step, and refresh with `todoread` when resuming; NEVER mark a task complete before its checks pass.
- ALWAYS include commit steps in the TODO list, each with its commit message.
- The shell is PowerShell (`pwsh`), not Bash. MUST use PowerShell syntax for shell commands.
- Python UTF-8 mode is enabled in this shell (`PYTHONUTF8=1`); every Python process emits UTF-8 by default.
- NEVER use `cd`.

- When a plan review returns feedback, address every point in chat before editing the plan or any file: answer every question it asks and wait for the reply, inspect every point that needs inspection before resubmitting, and NEVER resubmit unchanged or count an edit itself as addressing feedback.
- Plans MUST be submitted through the `submit_plan` tool; NEVER write a plan file to disk or use `plan_exit` or `open_plan`.
- When checking, using, or reporting a validation run, read its raw output as the validation emitted it; NEVER pass validation output through text-munging tools (grep, sed, awk, head, tail, cut) to filter, summarize, or reshape it before reading, using, or reporting it.
- MUST judge a validation run by its full printed output; NEVER treat the exit code alone as proof it passed, and NEVER suppress or truncate the output.
- Before running pytest, MUST read the active addopts from pytest config and avoid options it already sets, above all a second `-q` (double `-q` removes the summary line).
- MUST commit each verified change before stopping; NEVER leave verified work uncommitted. This never overrides CORE's `NEVER commit on default branch` — commit on a branch.
