# KILO.md

## Tools

- ALWAYS call `kilo_memory_save` for new durable project facts: decisions, constraints, conventions, corrections.
- NEVER save environment facts (shell, venv, paths, tools, commands) that break on environment change.
- MUST manage TODO strictly per task: `todowrite` to create and update after every step, `todoread` on resume; NEVER mark done before checks pass.
- ALWAYS include commit steps with messages in the TODO list.
- MUST run shell commands in PowerShell (`pwsh`), not Bash.
- Python UTF-8 mode is enabled (`PYTHONUTF8=1`); Python child processes emit UTF-8 by default.
- NEVER use `cd`.
- Headroom elides repeated read/tool output as `[↑NL msg X: '<snippet>']`; resolve mentally from the pointer alone, `↑NL` counts lines, snippet names source; Grep covers pointer gaps.
- MUST trust elision fully: matching head text proves elided lines repeat the named message verbatim. Resolve mentally from the pointer; NEVER re-run, re-read, re-open msg X, Grep, re-derive, or work around it to see or verify content; NEVER cite a reconstruction as evidence; cite the message it repeats.
- Review feedback: answer questions in chat and wait for replies, inspect points needing inspection; address every point before editing anything or resubmitting; NEVER resubmit unchanged or count an edit as addressing feedback.
- Plans MUST use `submit_plan`; NEVER write plan files or use `plan_exit` or `open_plan`.
- NEVER reshape validation output (grep, sed, awk, head, tail, cut) before reading or reporting it; read the raw output as the validation emitted it.
