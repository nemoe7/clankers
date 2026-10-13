---
name: gpt-question
description: Use when user input is needed to resolve a material ambiguity, choose an approach, collect related values, or confirm a necessary decision. Present a supported interactive GenUI form with useful preset controls and an always-visible custom-answer field.
---

# GPT Question

## Use

Use a supported interactive question form only when user input is needed to resolve a material ambiguity, choose an approach, collect related values, or confirm a necessary decision.

Use existing context first. Do not ask an unnecessary question. Make a reasonable assumption when it does not create material risk or change the requested outcome.

## Form invariant

Every form MUST show a visible custom-answer field, use supported controls, submit selected and custom values through `GenUI.issueNewTurn()`, and allow custom text alone unless a preset is necessary.

Use useful preset answers when they improve the response. Keep the custom field visible, preserve its text except for boundary whitespace, and avoid unrelated fields or decoration.

## Detail

Read [references/interactive-question.md](references/interactive-question.md) before building a question form or varying its controls.
