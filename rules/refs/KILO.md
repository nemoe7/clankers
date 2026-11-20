# KILO.md

## Tools

- ALWAYS call `kilo_memory_save` on new durable facts about the project: decisions, constraints, conventions, corrections.
- NEVER save environment facts (shell, venv, paths, tools, commands) that break when the environment changes.
- MUST manage the TODO list strictly for every implementation task: create it with `todowrite` before starting, update status with `todowrite` after every step, and refresh with `todoread` when resuming; NEVER mark a task complete before its checks pass.
- ALWAYS include commit steps in the TODO list, each with its commit message.
- The shell is PowerShell (`pwsh`), not Bash. MUST use PowerShell syntax for shell commands.
- Python UTF-8 mode is enabled in this shell (`PYTHONUTF8=1`); every Python process emits UTF-8 by default.
- NEVER use `cd`.
- Headroom elides repeated read and tool output into pointer lines like `[↑NL same as msg X: '<snippet>']`; read the elided content from message X, where `↑NL` counts the elided lines, the snippet names the source, and Grep covers content the pointer does not.
- MUST trust the elision fully: when a read or tool output line starts with the same head text, the elided lines repeat the named message verbatim. NEVER re-run a command, re-read a file, Grep, re-derive, or use any other workaround to see or verify elided content, and NEVER cite any such reconstruction as new or confirmatory evidence; cite elided content by the message it repeats.
