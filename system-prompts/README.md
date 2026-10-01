# System prompts

Prompts that a harness sends before the first user message. They are not agent rules. Agent rules live in [rules/](../rules/README.md).

| Path | Use |
| --- | --- |
| `refs/` | The uncompressed baseline. Amend a prompt here first. |
| `refs/GUIDELINES.md` | The standard for a prompt. Audit each prompt against it. |
| The top level | The live copies. An operator pastes one into a harness. |

A prompt carries no instruction budget. Keep a live copy equal to its refs source until a budget exists. `GUIDELINES.md` is a vendored copy, so it stays as its upstream wrote it.
