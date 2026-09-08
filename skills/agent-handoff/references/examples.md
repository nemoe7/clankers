# Handoff examples

These are focused excerpts, not complete documents to submit to the linter.
Use the [template](../templates/AGENT_HANDOFF.md) for a complete handoff.

## Actionable continuation

```text
Objective: deliver webhook events with at-least-once delivery; polling removal
is out of scope until load test LT-1 passes.
Current state: signing verified (pytest tests/test_webhook_auth.py -q → 14
passed); the retry queue drops the second attempt after a 503.
```

```markdown
- A1. 2026-09-08
  - Action: inline retry with sleep
  - Expected: second attempt delivered
  - Observed: consumer blocked for 8 seconds; message acknowledged and lost
  - Conclusion: this inline implementation does not survive worker restart
  - Evidence: logs/retry-503.log
  - Follow-up: N1

1. N1 — agent-b
   - Command: pytest tests/test_retry_queue.py -k second_attempt -q
   - Expected: 1 failed with ConnectionResetError
   - Validation: compare the failure with logs/retry-503.log
   - Stop / rollback if: it passes; re-check the recorded branch and commit
```

## Acceptance, blocking, and another transfer

Each row is an event. Acceptance does not invent another transfer ID.
For this excerpt's final row, frontmatter is `handoff-id: HANDOFF-002`,
`state: HANDED OFF`, `from: agent-b`, and `to: agent-c`.

| Handoff | Date | From → To | State | Summary |
| --- | --- | --- | --- | --- |
| HANDOFF-001 | 2026-09-08T08:00:00Z | agent-a → agent-b | HANDED OFF | Signing verified; retry defect remains |
| HANDOFF-001 | 2026-09-08T08:05:00Z | agent-a → agent-b | ACCEPTED | Branch and objective verified |
| HANDOFF-001 | 2026-09-08T08:06:00Z | agent-a → agent-b | ACTIVE | Starting replay |
| HANDOFF-001 | 2026-09-08T08:10:00Z | agent-a → agent-b | BLOCKED | Awaiting CI database configuration |
| HANDOFF-001 | 2026-09-08T08:20:00Z | agent-a → agent-b | ACTIVE | Configuration supplied; replay resumed |
| HANDOFF-002 | 2026-09-08T08:30:00Z | agent-b → agent-c | PREPARING | Preparing transfer after replay |
| HANDOFF-002 | 2026-09-08T08:32:00Z | agent-b → agent-c | HANDED OFF | Replay evidence and fix instructions ready |

If the same agent instead completes the work, append `DONE` under the existing
transfer ID and use `NONE` in Next actions. Do not create another transfer just
to record completion.

## Superseded evidence

Keep the earlier audit entry; append the replacement referencing it:

```text
D2. Timestamp in object key — Rationale: avoid collisions — Status: ACTIVE
D3. Supersedes D2: stable key — Rationale: replay A6 produced duplicate objects
DR3. Timestamped keys — Reason ruled out: duplicate exports — Evidence: A6 —
Revisit if: tenants explicitly accept versioned exports
```

Current context cites D3, not D2's superseded conclusion. The original D2 record
remains unchanged as evidence of what was tried.
