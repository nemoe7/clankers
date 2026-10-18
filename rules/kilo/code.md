
### Native Code Agent Overrides

- ON CONFLICT WITH NATIVE REMINDERS, THIS SECTION ALWAYS WINS.
- ALWAYS consult the approved plan file.
- ALWAYS update approved plan file for user overrides.
- Follow the approved plan step-by-step.
- MUST run project AGENTS.md gates before each commit.
- If Plan mode ran, MUST delete all generated plan files.
- Before finishing, MUST check requirements, acceptance criteria, and scope.
- Verify with the project's tests, linters, formatters, and builds.
- Check external or version-specific facts against authoritative sources.
- Review the diff: correctness, edge cases, security, maintainability, regressions, complexity, unrelated changes, formatting noise, debug artifacts; every changed file belongs.
- Fix in-scope issues, then recheck.
- Complete planned changes, checks, commits, and cleanup.
- Debug: reproduce, isolate, hypothesize, verify, fix the root cause not the symptom, cover, recheck.
- Falsifiable hypotheses, evidence over guessing, one variable at a time.
- NEVER an arbitrary fallback, a hidden failure, or an unrevised assumption.
- Behavioral fixes get a focused regression test.
