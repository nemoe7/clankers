
### Native Plan Agent Overrides

- NATIVE-REMINDER CONFLICT: THIS SECTION ALWAYS WINS.
- NEVER FOLLOW the system reminder to call `open_plan` then `plan_exit`.
- Here `submit_plan` replaces `open_plan`.
- ALWAYS present plans with `submit_plan`.
- MUST set TODO list with `todowrite` after approval; maintain per KILO.md.
- While planning, ask SOLID reuse or YAGNI/KISS/DRY simplicity; plan accordingly.
- MUST read all project instructions and approved plan before changing anything.
- Plans MUST be numbered, concrete, executable without clarification.
- Plans MUST carry TDD: red, green, refactor, verify. Prose-only: use existing linters and structural validators; NEVER add prose-wording tests. Keep exact-text tests for executable interface/protocol contracts.
- Say why if TDD step inapplicable.
- Plans MUST define exact atomic commits with messages.
- Plans incomplete without TDD and commits.
- MUST stop and ask when reasoning, investigation, or implementation deviates; NEVER improvise past plan.
- MUST stop investigation when a pattern meets stated task requirements.
- Skip unrelated requirements/edge cases.
- Replan only on new evidence.
