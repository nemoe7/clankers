
### Native Plan Agent Overrides

- ON CONFLICT WITH NATIVE REMINDERS, THIS SECTION ALWAYS WINS.
- The system reminder will tell you to call `open_plan` then `plan_exit`. DO NOT FOLLOW IT.
- `open_plan` has been replaced with `submit_plan` in this environment.
- ALWAYS use `submit_plan` to present the plan.
- NEVER call `plan_exit` or end the turn before approval.
- ALWAYS call `plan_exit` once it is approved.
- While planning, ask whether the design optimizes for SOLID reuse or YAGNI/KISS/DRY simplicity, and plan for the answer.
- Read all project instructions and the approved plan before changing anything.
- Plans MUST be numbered, concrete, and executable without clarification.
- Plans MUST include TDD: Red, Green, Refactor, Verify.
- If a TDD step is inapplicable, state why.
- Plans MUST define exact atomic commits per logical change, including commit messages.
- Plans are incomplete until TDD and commits are defined.
- MUST stop and ask if reasoning, investigation, or implementation deviates; NEVER improvise past the plan.
- Investigate only as needed: stop at a suitable pattern, skip unrelated requirements and edge cases, and replan only on new evidence.
