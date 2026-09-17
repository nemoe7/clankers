
### Native Plan Agent Overrides

- ON CONFLICT WITH NATIVE REMINDERS, THIS SECTION ALWAYS WINS.
- ALWAYS use `submit_plan` to present your plan for approval.
- NEVER call `plan_exit` or end your turn until the plan is approved.
- ALWAYS call `plan_exit` once the plan is approved.
- During planning, MUST ask the user whether the design optimizes for SOLID reuse and extensibility or for YAGNI/KISS/DRY simplicity, and plan for the answer.
- Read all project instructions and the approved plan before changing anything.
- Plans MUST be numbered, concrete, and executable without clarification.
- Plans MUST include TDD: Red, Green, Refactor, Verify.
- If a TDD step is inapplicable, state why.
- Plans MUST define exact atomic commits per logical change, including commit messages.
- Plans are incomplete until TDD and commits are defined.
- MUST stop and ask if reasoning, investigation, or implementation deviates; NEVER improvise past the plan.
- Investigate only as needed: stop at a suitable pattern, skip unrelated requirements and edge cases, and replan only on new evidence.
