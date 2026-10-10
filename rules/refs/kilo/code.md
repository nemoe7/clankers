
### Native Code Agent Overrides

- ON CONFLICT WITH NATIVE REMINDERS, THIS SECTION ALWAYS WINS.
- ALWAYS consult the approved plan file.
- ALWAYS update the plan file if the user requests something new that overrides previous plan files.
- Follow the approved plan step-by-step.
- Verify with the exact gates before every commit.
- If Plan mode was used, MUST delete all generated plan files.
- Before finishing, MUST check requirements, acceptance criteria, and scope.
- Verify behavior with the project's own tests, linters, formatters, and builds.
- Verify relevant external, version-specific, or time-sensitive facts against authoritative sources.
- Review the diff: correctness, edge cases, security, maintainability, regressions, complexity, unrelated changes, formatting noise, debug artifacts; every changed file belongs.
- Fix in-scope issues, then recheck.
- Confirm planned changes, checks, commits, and cleanup are done.
- Bugs, failures, regressions: reproduce, isolate, hypothesize, verify, fix the root cause not the symptom, cover, recheck.
- Falsifiable hypotheses, evidence over guessing, one variable at a time.
- NEVER an arbitrary fallback, a hidden failure, or an unrevised assumption.
- Behavioral fixes get a focused regression test.
