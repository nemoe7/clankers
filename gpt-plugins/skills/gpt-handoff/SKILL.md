---
name: gpt-handoff
description: "Independently audit agent work or draft a new-work handoff. Use Ponytail or SOLID when relevant."
---

Create a compact, actionable handoff for the next agent.

Make the output easy to copy and paste as an agent prompt. Use plain text and Markdown. Avoid conversational framing, unnecessary explanation, and formatting that does not copy cleanly.

Do not repeat rules the agent already has.

## Mode

Use `audit` when the user asks for an independent review of existing or proposed work.

Use `handoff` when the user asks for implementation direction or a plan.

Use the user's requested outcome over repository state.

## Work type

Infer from the requested outcome:

- `new`: add behavior
- `change`: modify behavior
- `bugfix`: correct behavior
- `refactor`: preserve behavior while changing implementation
- `docs`, `test`, `config`: primary deliverable
- `mixed`: multiple primary types

The requested outcome takes priority over file-based inference.

## Review

Independently verify enough context to assess requirements, implementation, project patterns, tests, scope, and complexity.

For existing work, identify defects, missed requirements, unnecessary complexity, missing verification, and scope issues.

For new work, define required behavior, affected areas, the simplest viable design, minimum checks, and material open questions.

Do not invent requirements.

## Design

Use **Ponytail** for unnecessary complexity, abstraction, indirection, duplication, dependencies, or speculative flexibility.

Use **SOLID** when necessary structure improves responsibility, coupling, or changeability.

Do not apply either mechanically.

Prefer existing patterns and the simpler design when requirements permit.

## Evidence

Support material findings and decisions with the smallest useful evidence.

Use requirements, code, project patterns, tests, command results, configuration, or documented behavior.

Do not treat agent claims as evidence.

Verify behavior with tests or direct checks when practical. State limits when verification is not practical.

## Findings

Use when applicable:

`delete:` `stdlib:` `native:` `yagni:` `shrink:` `bug:` `docs:` `test:` `scope:`

Rank by impact.

## Checks

List the minimum required checks.

These are a baseline, not a limit.

- Add more tests if necessary.

Never claim a check passed without verification.

## Output

Produce only the actionable handoff.

For `audit`, include only:

- findings
- required changes
- required checks
- unresolved questions, only when material
- `audit-by`

For `handoff`, include only:

- required behavior
- design direction
- minimum checks
- material evidence
- unresolved questions
- next actions
- `handoff-by`

Do not repeat:

- the user's task
- repository or branch
- audit scope
- exclusions
- existing agent rules
- instructions already known to the next agent

Do not create a task prompt or audit setup. The next agent already has the original task context.

Do not output a standalone review, audit report, explanation, or meta-commentary around the handoff.

When another skill supplies findings, analysis, or a format, use its analysis as input. The GPT Handoff format owns the final output format. Do not reproduce the other skill's standalone report or setup.

Keep findings directly actionable. Prefer the applicable finding labels:

`delete:` `stdlib:` `native:` `yagni:` `shrink:` `bug:` `docs:` `test:` `scope:`

Omit anything that does not apply.

Do not produce a separate summary.

Do not modify files.

For audits, end with:

`audit-by: <actual model identifier>`

For new-work handoffs, end with:

`handoff-by: <actual model identifier>`
