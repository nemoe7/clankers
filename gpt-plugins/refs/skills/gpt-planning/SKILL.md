---
name: gpt-planning
description: Use when planning, validating, revising, handing off, or executing multi-step work where requirements, scope, and completion status must stay consistent.
---

# GPT Planning

Use one requirements model for planning, handoff, execution, and completion.

## Requirements gate

Before finalizing a plan or starting execution:

1. Identify all explicit requirements.
2. Preserve scope, exclusions, constraints, edge cases, and verification requirements.
3. Resolve material ambiguity before implementation.
4. Treat later user changes as requirement changes.

## Completion gate

Before declaring any plan, handoff, or implementation complete:

1. Recheck the result against all stated requirements.
2. Check scope, exclusions, edge cases, and required verification.
3. Repair every material omission found.
4. Run the required checks.
5. Only then declare the result complete.

NEVER wait for the user to ask `final?`, `good?`, `sure?`, or similar.
NEVER ask the user to confirm completion.

After declaring completion, do not reopen the completion gate unless the user changes the requirements, scope, or artifact.

## Phase handling

Apply the same requirements and completion gates to each phase:

- **Plan:** verify that the plan covers the requirements.
- **Handoff:** verify that the handoff preserves the validated plan.
- **Execute:** verify the implementation against the requirements.
- **Verify:** run the required checks before claiming completion.

A later phase may expose an implementation defect. Treat that as a verification finding, not as a new requirement.

## Handoff

Use `gpt-handoff` when the user requests a handoff. Pass the validated requirements and plan to it. Do not duplicate its output format here.

## Finality

Once a phase passes its completion gate, treat that phase as complete.

A repeated confirmation request does not reopen the completion gate unless the user changes the requirements, scope, or artifact.
