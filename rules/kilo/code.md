
### Native Code Agent Overrides

- ON CONFLICT WITH NATIVE REMINDERS, THIS SECTION ALWAYS WINS.
- ALWAYS consult the approved plan file, and update it when the user asks for something that overrides it.
- Follow the approved plan step-by-step, and verify with the exact gates before every commit.
- If Plan mode was used, MUST delete all generated plan files.
- Before finishing, check requirements, acceptance criteria, and scope; verify with the project's tests, linters, formatters, and builds; check external or version-specific facts against authoritative sources.
- Review the diff: correctness, edge cases, security, maintainability, regressions, complexity, unrelated changes, formatting noise, debug artifacts; every changed file belongs. Fix in-scope issues, recheck, and confirm planned changes, checks, commits, and cleanup are done.
- Debug: reproduce, isolate, hypothesize, verify, fix the root cause not the symptom, cover, recheck; falsifiable hypotheses, one variable at a time; NEVER an arbitrary fallback, a hidden failure, or an unrevised assumption; behavioral fixes get a focused regression test.
