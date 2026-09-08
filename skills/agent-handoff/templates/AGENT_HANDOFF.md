---
workstream-id: <slug>
handoff-id: HANDOFF-<NNN>
state: <ACTIVE | PREPARING | HANDED OFF | ACCEPTED | BLOCKED | DONE>
from: <sender>
to: <receiver or UNKNOWN>
created: <ISO 8601 timestamp with timezone>
---

# Agent handoff

## 1. Handoff metadata

Transfer identity and state are in frontmatter; the newest history event must match them.

## 2. Objective

`<Stand-alone outcome, constraints, and what is done versus remaining>`

## 3. Current state

- Working: `<verified behavior and command that verified it>`
- Not working: `<observed failure and exact symptom, or NONE>`
- Recent changes: `<outcomes and paths since the last handoff>`
- Environment: `<OS, runtime, tool versions>`
- Branch / work commit: `<branch and exact task-work commit before the handoff-only commit>`
- Config / flags: `<relevant variable names and flags, never secret values>`

## 4. Context

- Binding user requirements: `<requirements>`
- Decisions in force: `<D IDs; do not repeat superseded conclusions>`
- Critical findings: `<findings>`
- Constraints: `<constraints>`
- Assumptions still in force: `<assumptions>`
- Open questions: `<questions the receiver must resolve>`

## 5. Resources

| Resource | Reference | Why it matters |
| --- | --- | --- |
| Repository | `<repository path or URL>` | `<purpose>` |

Reference files, issues, specifications, logs, and artifacts by location; do not embed their contents.

## 6. Completed work

- `<outcome>` — evidence: `<test, commit, or observation>`

## 7. Decisions (append only)

- D1. `<date>` — `<decision>` — Rationale: `<brief justification>` — Status: ACTIVE

## 8. Attempts (append only)

- A1. `<date>`
  - Action: `<command or change>`
  - Expected: `<observable result>`
  - Observed: `<actual result or exact error>`
  - Conclusion: `<what the result supports or rules out>`
  - Evidence: `<log, trace, commit, or link>`
  - Follow-up: `<action ID or NONE>`

## 9. Do not repeat (append only)

- DR1. Approach: `<approach>` — Reason ruled out: `<reason>` — Evidence: `<attempt ID or resource>` — Revisit if: `<condition>`

## 10. Unknowns, blockers, risks, decision triggers

- Unknowns: `<unknowns or NONE>`
- Blockers: `<blockers and resumption conditions, or NONE>`
- Risks: `<risks or NONE>`
- Decision triggers: `<observation and resulting action>`

## 11. Next actions

<!-- When DONE, replace this section's entire body with NONE. -->

1. N1 — `<owner>`
   - Command: `<exact command>`
   - Expected: `<observable result>`
   - Validation: `<how to confirm>`
   - Stop / rollback if: `<condition>`

## 12. Definition of Done

- `<observable, checkable completion condition>`

## 13. Validation

| Area | Check | Command | Status |
| --- | --- | --- | --- |
| Tests | `<relevant behavior>` | `<exact command>` | not run |

Record applicable functional, failure-path, performance, security, and operational checks.
Use N/A with a reason for inapplicable checks; never invent a passing result.

## 14. Rollback / recovery

- Trigger: `<condition>`
- Steps: `<exact recovery steps>`
- Verification: `<how to confirm recovery>`
- Escalation: `<owner or route, or NONE with reason>`

## 15. Handoff history (append only)

| Handoff | Date | From → To | State | Summary |
| --- | --- | --- | --- | --- |
| `HANDOFF-<NNN>` | `<event timestamp>` | `<sender>` → `<receiver>` | `<state>` | `<outcome>` |
