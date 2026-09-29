---
name: gpt-handoff
description: "MUST use for audits or reviews of agent-produced work (including code and human-facing docs), agent-created branches, agent-created PRs, agent-created commits, agent implementations, and follow-up audits of previously reviewed agent work. Draft new-work handoffs on request. For code audits, always use Ponytail; use SOLID only when necessary. For human-facing docs audits, always use Ponytail."
---

Create a compact, actionable handoff for the next agent.

Use easily copied plain text and Markdown as an agent prompt. Avoid conversational framing, unnecessary explanation and formatting that copies poorly.

Do not repeat rules the agent already has.

- Use `gpt-planning` for requirements and completion validation.

## Mode

Use `audit` for requested independent reviews of existing or proposed work.

MUST activate `audit` for reviews of agent-produced work (including code and human-facing docs), agent-created branches, agent-created PRs, agent-created commits, agent implementations, and follow-up audits of previously reviewed agent work.

For code audits, MUST follow: GPT Handoff audit → Ponytail code audit/review → GPT Handoff final output.

For human-facing docs audits, MUST follow: GPT Handoff audit → Ponytail docs audit/review → GPT Handoff final output.

Use `handoff` for requested implementation direction or plans.

Use the user's requested outcome over repository state.

Do not activate GPT Handoff for ordinary non-agent tasks without an audit, review, or handoff request.

## Work type

Infer from the requested outcome:

- `new`: add behavior
- `change`: modify behavior
- `bugfix`: correct behavior
- `refactor`: preserve behavior while changing implementation
- `docs`, `test`, `config`: primary deliverable
- `mixed`: multiple primary types

Requested outcomes outrank file-based inference.

## Review

Independently verify context sufficient to assess requirements, implementation, project patterns, tests, scope and complexity.

For existing work, identify defects, missed requirements, excess complexity, missing verification and scope issues.

For human-facing docs audits, use `docs:` for actionable findings.

For new work, define required behavior, affected areas, the simplest viable design, minimum checks, and material open questions.

Do not invent requirements.

## Design

MUST use **Ponytail** for code audits and human-facing docs audits, including work in agent-created branches, PRs, commits, and implementations, to assess unnecessary complexity, abstraction, indirection, duplication, dependencies, and speculative flexibility.

Use **SOLID** when needed structure improves responsibility, coupling or changeability.

Do not apply Ponytail findings or SOLID recommendations mechanically.

Prefer existing patterns and the simpler design when requirements permit.

## Evidence

Support material findings/decisions with the smallest useful evidence.

Use requirements, code, project patterns, tests, command results, configuration, or documented behavior.

Do not treat agent claims as evidence.

Verify behavior with tests or direct checks where practical; otherwise state verification limits.

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

NEVER include audit setup, scope, exclusions, methodology, task restatement, repository summaries, standalone audit prose, or task prompts. The next agent already has the original task context.

Do not output a standalone review, audit report, explanation, or meta-commentary around the handoff.

Use another skill's findings and analysis as input only.

When active, MUST use only GPT Handoff's final output format.

NEVER replace that format or append another skill's report format, setup, or sections.

Keep findings directly actionable. Prefer the applicable finding labels:

`delete:` `stdlib:` `native:` `yagni:` `shrink:` `bug:` `docs:` `test:` `scope:`

Omit anything that does not apply.

Do not produce a separate summary.

Before responding, retain only the active mode's permitted sections, no banned audit text or other skill format; end with `audit-by:` or `handoff-by:` and the actual model identifier, never the placeholder.

Do not modify files.

For audits, end with:

`audit-by: <actual model identifier>`

For new-work handoffs, end with:

`handoff-by: <actual model identifier>`
