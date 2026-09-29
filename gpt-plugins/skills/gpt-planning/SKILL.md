---
name: gpt-planning
description: Use when planning, validating, revising, handing off, or executing multi-step work where requirements, scope, and completion status must stay consistent.
---

# GPT Planning

Use one requirements model for planning, handoff, execution, and completion.

## Requirements gate

Before finalizing plans or starting execution:

1. Identify all explicit requirements.
2. Preserve scope, exclusions, constraints, edge cases, and verification requirements.
3. Resolve material ambiguity before implementation.
4. Treat later user changes as requirement changes.

## Completion gate

Before declaring any plan, handoff, or implementation complete:

1. Recheck all stated requirements against the result.
2. Check scope, exclusions, edge cases, and required verification.
3. Repair every material omission found.
4. Run the required checks.
5. Only then declare the result complete.

NEVER wait for the user to ask `final?`, `good?`, `sure?`, or similar.
NEVER ask the user to confirm completion.

After completion, reopen the gate only if the user changes requirements, scope or artifact.

## Phase handling

Apply both gates to each phase:

- **Plan:** verify that the plan covers the requirements.
- **Handoff:** verify that the handoff preserves the validated plan.
- **Execute:** verify the implementation against the requirements.
- **Verify:** run the required checks before claiming completion.

Treat implementation defects exposed in later phases as verification findings, not new requirements.

## Handoff

For requested handoffs, pass validated requirements and plan to `gpt-handoff`; do not duplicate its output format here.

## Finality

Once a phase passes its completion gate, treat that phase as complete.

Repeated confirmation requests reopen the completion gate only if the user changes requirements, scope or artifact.
