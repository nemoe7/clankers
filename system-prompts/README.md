# System prompts

Prompts that a harness sends before the first user message. They are not agent rules. Agent rules live in [rules/](../rules/README.md).

| Path | Use |
| --- | --- |
| `refs/` | The uncompressed baseline. Amend a prompt here first. |
| `refs/GUIDELINES.md` | The standard for a prompt. Audit each prompt against it. |
| The top level | The live copies. An operator pastes one into a harness. |

A live copy takes a row in the root [instruction-budgets table](../README.md#instruction-budgets) once it ships compressed. `NEMOGPT.md` has one. Amend `refs/` first, then compress the changed line into the live copy. A live copy without a budget row stays equal to its refs source. `GUIDELINES.md` is a vendored copy, so it stays as its upstream wrote it.
