---
name: gpt-question
description: Use for every question GPT asks the user. Present a supported interactive GenUI form with useful preset controls and a custom-answer option in every choice group.
---

# GPT Question

## Use

Use a supported interactive form only for needed input. Use context first; avoid unnecessary questions and make safe assumptions.

## Form invariant

Every form MUST give each choice group a selectable `Custom answer` option with its own input, use supported controls, submit selected and custom values with `GenUI.issueNewTurn()`, and allow custom-only answers unless a preset is necessary.

Use "Something else..." for each custom-answer input placeholder.

## Detail

Read [references/interactive-question.md](references/interactive-question.md) before building or varying a form.
