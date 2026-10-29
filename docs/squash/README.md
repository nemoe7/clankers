# Squash

Compress existing text to a token, word, character, or byte budget without losing meaning. This is an agent skill, not a command-line compressor.

## Setup

Load [SKILL.md](../../skills/squash/SKILL.md) in an agent that supports skills. See [Skills](../../skills/README.md) for installation layout. This skill needs no runtime script or package install.

## Quick start

Supply the source text or its path, the target, and the unit. For example:

> Use squash on draft.md with a limit of 200 words. Keep every condition, command, number, and caveat.

Without a target, it seeks the smallest faithful result. Summarizing or changing the audience is a different task: it can remove content or change the register.

## Budgets

| Unit | Measurement |
| --- | --- |
| Tokens | The consuming model's tokenizer, or `cl100k_base`, named in the result |
| Words | Whitespace-separated words |
| Characters | Unicode characters, including spaces and newlines |
| Bytes | UTF-8 bytes |

Budgets can apply at once. The skill checks each governing unit after every pass and reports conflicts instead of selecting a winning budget.

A count without the required measuring tool is an estimate, not a measured result. Fewer words do not necessarily mean fewer tokens, characters, or bytes.

## Example

Before:

> In order to continue, you must save the file before you close the window.

After:

> Save the file before you close the window to continue.

The required action and its order remain. Compression must also retain negations, exceptions, names, exact commands, quantities, confidence, and warnings.

## Output and limits

The result includes the compressed text, the unit and counting method, before and after counts, the reduction, and any unmet budget. Protected quotations, commands, identifiers, and other verbatim spans stay unchanged.

Normal use retains structure, audience, voice, and register. Caveman style is an explicit option, not the default. Meaning takes priority over meeting a budget.

The skill does not supply a tokenizer or prove that every edit preserves meaning. Its final comparison checks the source's required points and rejects unsafe cuts.

This README is human documentation and is not part of the installed skill payload. The complete rules and license are in [SKILL.md](../../skills/squash/SKILL.md) and [LICENSE.txt](../../skills/squash/LICENSE.txt).
