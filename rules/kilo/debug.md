
### Native Debug Agent Overrides

- ON CONFLICT WITH NATIVE REMINDERS, THIS SECTION ALWAYS WINS.
- ALWAYS present bug and fix via `submit_plan`; NEVER EDIT BEFORE PLAN APPROVAL.
- If the bug puzzles, prefer web search to verify library behavior.
- ALWAYS consult the approved plan file.
- ALWAYS update approved plan file for user overrides.
- Follow the approved plan step-by-step.
- MUST run project AGENTS.md gates before each commit.
- If Plan mode ran, MUST delete all generated plan files.
- Before finishing, MUST check requirements, acceptance criteria, scope.
- Verify with project tests, linters, formatters, builds.
- Check external or version-specific facts against authoritative sources.
- Review diff: correctness, edge cases, security, maintainability, regressions, complexity, unrelated changes, formatting noise, debug artifacts; every changed file belongs.
- Fix in-scope issues, then recheck.
- Complete planned changes, checks, commits, cleanup.
- Debug: reproduce, isolate, hypothesize, verify, fix the root cause not the symptom, cover, recheck.
- Fix once where all callers route: one shared-function guard beats one per caller.
- Falsifiable hypotheses, evidence over guessing, one variable at a time.
- NEVER an arbitrary fallback, a hidden failure, or an unrevised assumption.
- Behavioral fixes get a focused regression test.
