
### Native Plan Agent Overrides

- ON CONFLICT WITH NATIVE REMINDERS, THIS SECTION ALWAYS WINS.
- NEVER FOLLOW the system reminder to call `open_plan` then `plan_exit`.
- In this environment, `submit_plan` replaces `open_plan`.
- ALWAYS use `submit_plan` to present the plan.
- NEVER call `plan_exit` or end the turn before approval.
- ALWAYS call `plan_exit` after approval.
- While planning, ask whether the design optimizes for SOLID reuse or YAGNI/KISS/DRY simplicity; plan for the answer.
- MUST read all project instructions and the approved plan before changing anything.
- Plans MUST be numbered, concrete, executable without clarification.
- Plans MUST carry TDD: red, green, refactor, verify. Prose-only: use existing linters and structural validators; NEVER add prose-wording tests. Keep exact-text tests for executable interface/protocol contracts.
- If a TDD step is inapplicable, state why.
- Plans MUST define exact atomic commits with messages.
- A plan is incomplete without defined TDD and commits.
- MUST stop and ask when reasoning, investigation, or implementation deviates; NEVER improvise past the plan.
- MUST stop investigation when a pattern meets stated task requirements.
- Skip unrelated requirements and edge cases.
- Replan only on new evidence.
