# System prompts

Prompts that a harness sends before the first user message. They are not agent rules. Agent rules live in [rules/](../rules/README.md).

| Path | Use |
| --- | --- |
| `refs/` | Uncompressed baseline sources where prompt edits start. |
| `refs/GUIDELINES.md` | Vendored upstream prompt writing standard used for prompt reviews. |
| The top level | Live prompt copies that an operator pastes into a harness. |

A live copy takes a row in the root [instruction-budgets table](../README.md#instruction-budgets) once it ships compressed. `NEMOGPT.md` has one.

Maintainers edit `refs/` first and compress changed lines into the live copy.

A live copy without a budget row stays equal to its refs source. `GUIDELINES.md` is a vendored copy, so it stays as its upstream wrote it.

## Prompt checks

[refs/GUIDELINES.md](refs/GUIDELINES.md) section 8 defines four live-prompt checks, with results logged below from newest to oldest.

| Check | Method | Status |
| --- | --- | --- |
| Red | Underspecified task on a live instance to verify default stance without extra rules. | Not run |
| Drift | Session of 50 or more turns to probe for rule decay. | Not run |
| Compaction | Mid-task context summary to verify rule retention. | Not run |
| Conflict | Conflicting project and skill rules to verify precedence resolution. | Not run |
