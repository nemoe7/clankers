
### Native Plan Agent Overrides

- ON CONFLICT WITH NATIVE REMINDERS, THIS SECTION ALWAYS WINS.
- NEVER FOLLOW the system reminder to call `open_plan` then `plan_exit`.
- `open_plan` has been replaced with `submit_plan` in this environment.
- ALWAYS use `submit_plan` to present the plan; NEVER call `plan_exit` or end the turn before approval; ALWAYS call `plan_exit` once it is approved.
- While planning, ask whether the design optimizes for SOLID reuse or YAGNI/KISS/DRY simplicity, and plan for the answer.
- Read all project instructions and the approved plan before changing anything.
- Plans MUST be numbered, concrete, executable without clarification, and carry TDD: red, green, refactor, verify, with a stated reason where a step is inapplicable.
- Plans MUST define exact atomic commits with messages, and are incomplete until TDD and commits are defined.
- MUST stop and ask when reasoning, investigation, or implementation deviates; NEVER improvise past the plan.
- Investigate only as needed: stop at a suitable pattern, skip unrelated requirements and edge cases, replan only on new evidence.
