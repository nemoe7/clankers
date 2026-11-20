# KILO.md

## Tools

- ALWAYS call `kilo_memory_save` for new durable project facts: decisions, constraints, conventions, corrections.
- NEVER save environment facts (shell, venv, paths, tools, commands) that break on environment change.
- MUST manage TODO strictly per task: `todowrite` to create and update after every step, `todoread` on resume; NEVER mark done before checks pass.
- ALWAYS include commit steps with messages in the TODO list.
- MUST run shell commands in PowerShell (`pwsh`), not Bash.
- Python UTF-8 mode is enabled (`PYTHONUTF8=1`); Python child processes emit UTF-8 by default.
- NEVER use `cd`.
- Headroom elides repeated read/tool output as `[↑NL msg X: '<snippet>']`; read elided content from message X, `↑NL` counts lines, snippet names source, Grep covers pointer gaps.
- MUST trust elision fully: matching head text proves elided lines repeat the named message verbatim. NEVER re-run a command, re-read, Grep, re-derive, or work around it to see or verify content; NEVER cite a reconstruction as evidence; cite the message it repeats.
