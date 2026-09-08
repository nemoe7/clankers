# CLINE.md

Cline-specific rules. Generic rules load from the global AGENTS.md (Cline reads it); not repeated here.

## Command discipline

- Run exactly the command the user gave; do not add extra commands or follow-up actions.
- After running a requested command, report the output and STOP. Do not edit, fix, refactor, or otherwise "continue the job" unless explicitly told to.
- Empty or clean output is not a mandate to act. Example: a `git status` with nothing to commit means report "clean, nothing to do" and wait — never start changing files.
- Never self-assign next steps, improvements, or work between turns. When the requested task is done, stop and await the next instruction.
- If output surfaces a problem worth fixing, mention it briefly and ask — do not fix it unprompted.

## Implementation plan

When appropriate, use `implementation_plan.md` as a **local-only** planning artifact unless project conventions specify otherwise.

Keep it concrete enough for another coding agent to execute without re-deriving context.

Use:

```md
### 1. <task>

<implementation details>

STATUS: 🔴
```

On completion:

```md
~~### 1. <task>~~

~~<implementation details>~~

STATUS: 🟢 - `<commit hash>`: <commit message>
```

Update the plan as implementation reveals new information. Do not commit it unless explicitly required by project conventions.

## Cline tools

Cline built-ins (v4.1.17): `read_files`, `search_codebase`, `run_commands`, `fetch_web_content`, `editor`, `apply_patch`, `skills`, `ask_question`, `submit_and_exit`.

- Use `read_files`, `search_codebase`, `editor` for reading, searching, listing, creating, editing, and inspecting files.
- Use `run_commands` only for actual execution: tests, linters, formatters, builds, git, and application commands.
- Never use `run_commands`, shell scripts, pipes, redirection, or temporary scripts as substitutes for file tools.
- Edit files only with `editor` / `apply_patch`. If write tools are blocked or unavailable: stay read-only, modify nothing by any other means, and report the limitation.
- Use `fetch_web_content` for web retrieval; `ask_question` when clarification is needed.
- Tool priority: `tokensave` and file tools (`read_files`/`search_codebase`/`editor`) for inspection and edits; `run_commands` for execution only.
- Use the most appropriate tool for the operation; do not call tools merely to satisfy these rules.
- If a required tool fails for a non-syntax reason, report the failure instead of retrying or working around it (except Test Timeout).
- Remove temporary files when no longer needed.

## MCPs

Use only if installed/configured; never invent tool names.

- `tokensave`: code search, navigation, context retrieval, callers/callees, impact analysis — when applicable.
- `context7`: dependency/library API docs — at most 3 calls per user input.
- `memory`: persistent cross-session memory — store/recall relevant facts when applicable.

## Test Timeout

- Run tests normally and observe the result.
- Only if a test does time out (does not exit) use the protocol below as an alternative.
- Redirect test output to `.test-output.tmp`.
- Wait with `ping` at most 30 seconds; treat non-exit as failure.
- Inspect output with file tools.
- Delete `.test-output.tmp` on success, failure, or timeout.
