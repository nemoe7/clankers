---
name: gpt-question
description: Use when user input is needed to resolve a material ambiguity, choose an approach, collect related values, or confirm a necessary decision. Present a supported interactive GenUI form with useful preset controls and an always-visible custom-answer field.
---

# GPT Question

## Use

Use a supported interactive form only for needed input. Use context first; avoid unnecessary questions and make safe assumptions.

## Form invariant

Every form MUST show custom input, use supported controls, submit selected and custom values with `GenUI.issueNewTurn()`, and allow custom-only answers unless a preset is necessary.

## Detail

Read [references/interactive-question.md](references/interactive-question.md) before building or varying a form.
