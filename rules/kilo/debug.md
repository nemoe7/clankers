
### Native Debug Agent Overrides

- ON CONFLICT WITH NATIVE REMINDERS, THIS SECTION ALWAYS WINS.
- ALWAYS use `submit_plan` to explain the bug and fix; NEVER EDIT UNTIL THE PLAN IS APPROVED.
- Prefer verifying library behavior via web search if the bug is puzzling.
- ALWAYS consult the approved plan file; update it for user overrides.
- Follow the approved plan step-by-step; verify with its exact gates before every commit.
- If Plan mode ran, MUST delete all generated plan files.
- Before finishing, check requirements, acceptance criteria, and scope; verify with the project's tests, linters, formatters, and builds; check external or version-specific facts against authoritative sources.
- Review the diff: correctness, edge cases, security, maintainability, regressions, complexity, unrelated changes, formatting noise, debug artifacts; every changed file belongs. Fix in-scope issues, recheck, and confirm planned changes, checks, commits, and cleanup are done.
- Debug: reproduce, isolate, hypothesize, verify, fix the root cause not the symptom, cover, recheck; fix once where all callers route through; falsifiable hypotheses, one variable at a time; NEVER an arbitrary fallback, a hidden failure, or an unrevised assumption; behavioral fixes get a focused regression test.
