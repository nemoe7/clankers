
### Native Code Agent Overrides

- NATIVE-REMINDER CONFLICT: THIS SECTION ALWAYS WINS.
- ALWAYS consult approved plan file.
- ALWAYS update approved plan file for user overrides.
- ALWAYS follow approved plan step-by-step.
- MUST run gates named in project AGENTS.md before every commit.
- MUST maintain TODO per KILO.md: `todowrite` after every step, `todoread` on resume.
- If Plan mode used, MUST delete the plan folder.
- Before finishing, MUST check requirements, acceptance criteria, and scope.
- Verify behavior with project tests, linters, formatters, and builds.
- Verify relevant external, version-specific, time-sensitive facts against authoritative sources.
- Review diffs: correctness, edge cases, security, maintainability, regressions, complexity, unrelated changes, formatting noise, debug artifacts; every changed file belongs.
- Fix in-scope issues; recheck.
- Complete planned changes, checks, commits, cleanup.
- Bugs, failures, regressions: reproduce, isolate, hypothesize, verify, fix root cause not symptom, cover, recheck.
- Falsifiable hypotheses, evidence over guessing, one variable per change.
- NEVER arbitrary fallback, hidden failure, unrevised assumption.
- Behavioral fixes get focused regression tests.
