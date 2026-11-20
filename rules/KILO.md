# KILO.md

## Tools

- ALWAYS call `kilo_memory_save` on new durable facts about the project: decisions, constraints, conventions, corrections.
- NEVER save environment facts (shell, venv, paths, tools, commands) that break when the environment changes.
- MUST manage TODO strictly per task: `todowrite` to create and update after every step, `todoread` on resume; NEVER mark done before checks pass.
- ALWAYS include commit steps with messages in the TODO list.
- MUST run shell commands in PowerShell (`pwsh`), not Bash.
- Python UTF-8 mode is enabled (`PYTHONUTF8=1`); Python child processes emit UTF-8 by default.
- NEVER use `cd`.
- Headroom elides repeated read/tool output as `[↑NL msg X: '<snippet>']`; read elided content from message X, `↑NL` counts lines, snippet names source, Grep covers pointer gaps.
- MUST trust the elision: matching head text proves the lines repeat the named message, so NEVER re-run a command or read to see elided content.
