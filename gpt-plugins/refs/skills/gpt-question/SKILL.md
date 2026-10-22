---
name: gpt-question
description: Use for every question GPT asks the user. Present a supported interactive GenUI form with useful preset controls and a custom-answer option inside every choice group.
---

# GPT Question

## Use

Use a supported interactive question form only when user input is needed to resolve a material ambiguity, choose an approach, collect related values, or confirm a necessary decision.

Use existing context first. Do not ask an unnecessary question. Make a reasonable assumption when it does not create material risk or change the requested outcome.

## Form invariant

Every form MUST give each choice group a selectable `Custom answer` option with its own free-text input, use supported controls, submit selected and custom values through `GenUI.issueNewTurn()`, and allow a custom-only answer unless a preset is necessary.

Use useful preset answers when they improve the response. Show a group's input beside or immediately below the group while its custom option is selected, preserve the typed text except for boundary whitespace, and avoid unrelated fields or decoration.

## Detail

Read [references/interactive-question.md](references/interactive-question.md) before building a question form or varying its controls.
