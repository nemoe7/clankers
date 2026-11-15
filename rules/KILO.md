# KILO.md

## Tools

- ALWAYS call `kilo_memory_save` on new context.
- MUST manage TODO strictly per task: `todowrite` to create and update after every step, `todoread` on resume; NEVER mark done before checks pass.
- ALWAYS include commit steps with messages in the TODO list.
- MUST run shell commands in PowerShell (`pwsh`), not Bash.
- NEVER use `cd`.
- Headroom elides repeated read/tool output as `[↑NL msg X: '<snippet>']`; read elided content from message X, `↑NL` counts lines, snippet names source, Grep covers pointer gaps.
