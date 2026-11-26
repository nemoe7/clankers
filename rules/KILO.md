# KILO.md

## Tools

- ALWAYS call `kilo_memory_save` for new durable project facts: decisions, constraints, conventions, corrections.
- NEVER save environment facts (shell, venv, paths, tools, commands) that break on environment change.
- MUST manage TODO strictly per task: `todowrite` to create and update after every step, `todoread` on resume; NEVER mark done before checks pass.
- ALWAYS include commit steps with messages in the TODO list.
- MUST run shell commands in PowerShell (`pwsh`), not Bash.
- Python UTF-8 mode is enabled (`PYTHONUTF8=1`); Python child processes emit UTF-8 by default.
- NEVER use `cd`.
- MUST use `git switch` to change branches; NEVER `git checkout` or other syntax.
- MUST run global `ruff`; NEVER use a venv-local ruff.

- Review feedback: answer questions in chat and wait for replies, inspect points needing inspection; address every point before editing anything or resubmitting; NEVER resubmit unchanged or count an edit as addressing feedback.
- Plans MUST use `submit_plan`, which writes the plan file; NEVER write a separate one or use `plan_exit`/`open_plan`. Generated plan files in the plan folder, suffixed `approved`/`annotations`/`denied`, join the deletion flow.
- Read validation output raw as emitted; NEVER pass it through text-munging tools (grep, sed, awk, head, tail, cut) before reading, using, or reporting it.
- MUST judge validation by its full printed output; NEVER treat the exit code alone as proof it passed, and NEVER suppress or truncate the output.
- MUST read pytest addopts before running; avoid a second `-q` (double `-q` removes the summary line).
- MUST commit each verified change before stopping; NEVER leave verified work uncommitted. CORE's `NEVER commit on default branch` still holds — commit on a branch.
