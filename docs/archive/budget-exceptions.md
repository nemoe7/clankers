# Budget exceptions

Budget growth, oldest first, with dates, numbers and reasons. [README.md](../../README.md#instruction-budgets) gives current measurements and the compression procedure. Per item 6, add a paragraph for each over-budget change. Strike or mark entries superseded when later compression funds them. 

2026-09-13: Accepted without funding. `rules/AGENTS.md` +87 `tok` (1,731 → 1,818). `rules/ARENA.md` +636 `B` (9,205 → 9,841). Seven-rung ladder and three MUST upgrades accepted as baselines, not deferred debt. Both files later sit below these levels, funded by amendments. Item 5 applies at the recorded measurements. 

2026-09-17: after the resquash, `rules/AGENTS.md` lands 1,785 → 1,549 `tok`. `skills/arena-live-steering/SKILL.md` 13,419 → 8,132 `B`. `rules/ARENA.md` settles 10,129 → 10,307 `B`. the residual 178 `B` funds requested new rules (SOLID pair, tool-call batching, fix-once-where-callers-route-through). The unfunded visible-activation clause raises the residual to 299 `B`. 2026-09-18 compressions reduce it to 287 `B`. The two-read-path amendment lands 2 `B` below its prior 10,416 `B`, narrowing it to 285 `B`. Item 5 applies once funded. 

2026-09-17: Funded in the same change. The steering `SKILL.md` note (+341 `B`, 8,473 vs 8,132 `B`) is paid by moving full wording to `BASELINE.md`: 8,022 `B`, 110 `B` below prior. No exception remains. 

2026-09-18: Accepted without funding. Steering ingest-script rule: live bullet +91 `B` (10,414 → 10,505 `B`). `rules/refs/ARENA.md` 18,620 → 18,899 `B`, unbudgeted. Ten compressed clauses elsewhere recovered 275 `B`, already spent on the two-read-path rule. Residual against the 10,129 `B` baseline: 376 `B`. Item 5 applies once funded. 

2026-09-18: Accepted without funding. `skills/arena-live-steering/SKILL.md` +1,141 `B` (7,961 → 9,102 `B`) for three rules: pull cadence on batched-tool-call surfaces, duty to report a mangled channel, disk-observable activation. `BASELINE.md` 10,429 → 12,211 `B`. `references/REFERENCE.md` 16,903 → 18,725 `B`, both unbudgeted. No squash pass ran. Remaining wording is mechanics. Item 5 applies once funded. 

2026-09-19: Accepted without funding. `rules/ARENA.md` +573 `B` (11,003 → 11,576 `B`). `rules/AGENTS.md` +41 `tok` (1,549 → 1,590 `tok`). Four rules: pull cadence with exceptions, literal activation line, literal note-acknowledgement prefix, recommended answer on every question. `skills/arena-live-steering/SKILL.md` +1,207 `B` (10,265 → 11,472 `B`) at 1.10.0: read fetch bodies not status. channel move on `SignatureDoesNotMatch`, turn pause on topic repeat, `ACK:` prefix, `BASELINE.md` home note. Unbudgeted: `rules/refs/ARENA.md` 19,908 → 21,084 `B`, `rules/refs/AGENTS.md` → 10,100 `B`, `BASELINE.md` 14,124 → 16,223 `B`, `references/REFERENCE.md`, root `AGENTS.md` 10,091 → 11,203 `B`. New lines written compressed, not copied. No squash pass ran. Item 5 applies once funded. 

2026-09-20: literal `fast-forward/rebase` wording. `rules/ARENA.md` +7 `B` (11,576 → 11,583 `B`) for `/rebase`. Unfunded. 

2026-09-20: preview migration. `rules/ARENA.md` +62 `B` (11,583 → 11,645 `B`) after compression from 11,777 `B`: inbox receipts, rendered-report pipeline, portable HTML, former workflows stay historical. `arena-preview-steering` replaces the 11,472 `B` entry at 6,089 `B`. new `arena-preview-reporting` baseline 4,987 `B`. together 396 `B` below the old entry. 

2026-09-20: external-channel option (preview invisible on Arena mobile). `skills/arena-preview-steering/SKILL.md` +1,578 `B` (6,089 → 7,667 `B`): user-selected ntfy activation, topic naming `<repo>-<branch>-<8-char secret>`, JSON polling with `since=`, empty-or-500-quiet contract, fallback ladder, `SignatureDoesNotMatch` handling, no automatic fallback. Unfunded. 

2026-09-20: form-submission feature. `skills/arena-preview-steering/SKILL.md` +830 `B` (7,667 → 8,497 `B`). `references/REFERENCE.md` +1,117 `B` (7,536 → 8,653 `B`), unbudgeted. Unfunded. 

2026-09-20: Report answerable-field contract (+1,058 `B`), less Forms removal (−743 `B`), plus pre-filled answers and sent receipt (+195 `B`). The steering skill rose from 8,497 to 9,007 `B`, a net +510 `B`. The reporting skill rose +495 `B` (4,987 → 5,482 `B`). A compression pass covered the refs. No further removal was available. Unfunded. 

2026-09-20, second round: ack answers moved into the message log, report answers out, fielded reports as question surface. `skills/arena-preview-steering/SKILL.md` +549 `B` (9,007 → 9,556 `B`). `rules/ARENA.md` +448 `B` (11,625 → 12,073 `B`) after one pass recovered 29 `B`. Refs amended first, mirrored compressed. Renderer startup check added 216 `B` later that day, to 9,772 `B`. Unfunded. 

2026-09-21: mid-turn `GH_TOKEN` expiry documentation. `rules/ARENA.md` +316 `B` (12,073 → 12,389 `B`). written compressed from a 756 `B` refs amendment: literal failure strings, `gh auth setup-git` dead end, single-retry limit, `git ls-remote` proof. No funding pass available. Unfunded. 

2026-09-21: acknowledgement amendment with squash. `rules/ARENA.md` +272 `B` (12,389 → 12,661 `B`): receipt leaves in the same tool block as the read. work that outlives the block goes out as in progress. receipt is one to three lines naming change and commit, analysis goes to a report or `CHANGELOG.md`. Compressed from a 428 `B` refs amendment. Unfunded. 

2026-09-21: smallest-open-task standing order. `rules/ARENA.md` +192 `B` (12,661 → 12,853 `B`), compressed from a 294 `B` refs amendment. reason: a large task never blocks a small one. Funding review retained the General section. Unfunded. 

2026-09-21: note-ID citation, refined to first seven characters. `skills/arena-preview-steering/SKILL.md` +308 `B` (9,772 → 10,080 `B`). refs and `.agents` mirror take the same bytes. Funding review retained the bullet. Unfunded. 

2026-09-21: turn-rule amendment. `rules/ARENA.md` +173 `B` (12,853 → 13,026 `B`). `rules/refs/ARENA.md` 22,439 → 22,719 `B`, unbudgeted. Turn keeps working while budget and tasks remain. ends only for exhausted budget or strict need for user attention, stating which. Funding review retained the General section. Unfunded. 

2026-09-21: PowerShell (`pwsh`) over Bash in Kilo. `rules/KILO.md` 185 → 199 `tok`. two passes reduced the new line from 20 to 14 `tok`. Accepted without funding. 

2026-09-21: queue-update and message-link clauses. Two passes reduced them from 714 to 672 bytes. `skills/arena-preview-steering/SKILL.md` 10,689 → 11,361 bytes. Accepted without funding. 

2026-09-21: terse-but-unambiguous register bar. `skills/squash/SKILL.md` +2 `tok` (1,263 → 1,265 `tok`). unbudgeted refs take the amendment. No restatement available to fund it. Unfunded. 

2026-09-22: question-tool block on turn end after a dead token lost four approved commits. `rules/ARENA.md` +48 `B` (13,026 → 13,074 `B`). `rules/CHATGPT-CUSTOM.txt` +10 `chars` (1,484 → 1,494 `chars`) for the think-longer clause. the dropped lazier-alternative line pays for most, within the 1,500 limit. `rules/ARENA.md` +124 `B` more (13,074 → 13,198 `B`) for the ban on session-local note IDs in repository files. Unfunded. 

2026-09-22: `rules/CHATGPT-MORE.txt` +20 `chars` (1,475 → 1,495), accepted without funding. A resquash restored `phone-sized`, `existing helper first`, and the no-turn-while-a-test-fails rule. The pass freed 33 `chars`, spent more than it recovered. 5 `chars` headroom. Unfunded. 

2026-09-22: first-start visibility amendment. `rules/ARENA.md` +283 `B` (13,493 → 13,776 `B`): visibility question before non-setup work, first successful start enters the block, live-preview banner is not proof. `rules/refs/ARENA.md` 23,611 → 23,968 `B`, unbudgeted. Unfunded. 

2026-09-22: turn-await rule via form `platform-reasons`. `rules/ARENA.md` +107 `B` (13,776 → 13,883 `B`). `rules/refs/ARENA.md` 23,968 → 24,075 `B`, unbudgeted. Also drops one sentence from `rules/refs/README.md` naming a removed Cline section. Unfunded. 

2026-09-22: file-upload notification. `skills/arena-preview-steering/SKILL.md` +166 `B` (11,399 → 11,565 `B`) for `## Uploads`. `references/REFERENCE.md` +433 `B` (50,063 → 50,496 `B`), unbudgeted. Unfunded. 

2026-09-22: pending amendments except the core merge clause and the incorrect install path. `rules/ARENA.md` 13,863 → 14,081 `B` for the CI check and chat-versus-document mermaid rules. `skills/arena-preview-steering/SKILL.md` 11,565 → 12,061 `B` for final read, restart notice, report rendering limit, CLI reminder contract. Unfunded. 

2026-09-22: Chromium rule. `rules/ARENA.md` 14,081 → 14,225 `B`: use the npm package and its extracted runtime, not a Playwright-managed browser. Unfunded. 

2026-09-22: mandatory custom responses for option sets. `skills/arena-preview-steering/SKILL.md` 11,802 → 11,900 `B`. `skills/arena-preview-reporting/SKILL.md` 5,482 → 5,580 `B`. Unfunded. 

2026-09-22: stale-guidance correction 5,580 → 5,589 `B`, funded by a compression pass to 5,452 `B`. No exception remains. 

2026-09-23: auto-seen reads. Build sizes: `scripts/preview.py` 54,009 → 54,509 `B`. `scripts/check_preview.py` 51,841 → 53,449 `B`. `skills/arena-preview-steering/SKILL.md` 11,626 → 11,757 `B`. A read stamps Seen for the IDs it printed once its write succeeds. 

2026-09-23: end-of-bash-call poll. `rules/ARENA.md` 13,903 → 13,908 `B`. `skills/arena-preview-steering/SKILL.md` shrinks 11,757 → 11,722 `B`. 

2026-09-22 to 2026-09-23: successive preview runtime and harness changes added explicit Seen receipts, composer line-break handling, shift-hover copy feedback, and multiple uploads. They also added edited-reply timestamps and jump links, shared report/reply border colour, mandatory custom responses, and report-refresh isolation. Compact reminders, unread-or-unanswered report markers, and audit items M5/M6/H3 followed. Auto-seen reads, answer survival across republish, minified-build harness asserts, end-of-bash-call poll, and automatic polling hook with installer and server-down message followed. Per-file deltas are in Git history and the CHANGELOG. Unfunded.

2026-09-23: save-state notification. `scripts/preview.py` grows 55,826 → 55,978 `B`. `scripts/check_preview.py` grows 53,947 → 54,203 `B`. The save route writes an inbox note, so the next `read` delivers it. The harness covers the note text and its unacknowledged state. Unfunded.

2026-09-23: save-state clause, read-now timing and the squash fixtures table. `rules/ARENA.md` grows 13,908 → 13,984 → 14,100 `B`, and the root copy matches it. The first step is the read-now clause. The second is the turn-end, violation and all-reports clauses approved in `house-rule-amendments`. `skills/arena-preview-steering/SKILL.md` lands under its 11,099 `B` baseline at 10,777 `B` after the clause-audit omissions, so it needs no exception. `skills/squash/SKILL.md` grows 1,265 → 1,289 `tok`. One squash pass covered each new line, and no further removal was available. Unfunded.
2026-09-23: ack-asap reminder. `scripts/preview.py` grows 56,113 → 56,179 `B`. `skills/arena-preview-steering/SKILL.md` +35 `B` (10,777 → 10,812 `B`) for the clause `ACK ASAP.` after any pending count. The refs harness takes the matching assertions. One pass over the new line found no removal that keeps the rule. Unfunded.
2026-09-23: republish guard. `scripts/preview.py` grows 56,179 → 56,401 `B`. `skills/arena-preview-steering/SKILL.md` +24 `B` (10,812 → 10,836 `B`) and `skills/arena-preview-reporting/SKILL.md` +182 `B` (5,803 → 5,985 `B`) for the refused-republish clauses, after one squash pass. The steering `references/REFERENCE.md` copies and the refs harness take matching changes. Unfunded.
2026-09-23: reminder emphasis. `scripts/preview.py` grows 56,401 → 56,416 `B`. `skills/arena-preview-steering/SKILL.md` +15 `B` (10,836 → 10,851 `B`) for the clause `DO NOT IGNORE.` before `ACK ASAP.` The refs harness grows 77,016 → 77,124 `B` with matching assertions. Unfunded.
2026-09-23: steering prose audit. `skills/arena-preview-steering/SKILL.md` shrinks 10,851 → 8,959 `B` (the approved cuts, net of the external-channel pointer). The three `references/REFERENCE.md` copies grow 13,654 → 15,043 `B` for the relocated ntfy procedure. References stay unbudgeted. Unfunded.
2026-09-23: reporting merge. `skills/arena-preview-reporting/SKILL.md` leaves the table with the retired skill. `skills/arena-preview-steering/SKILL.md` grows 8,959 → 10,435 `B` for the publishing section, still 6,401 `B` below the two former entry points combined. The three `references/REFERENCE.md` copies grow 15,043 → 15,551 `B` with the report structure. Unfunded.

2026-09-23: session-local artifact ban. `rules/ARENA.md` grows 14,096 → 14,100 `B`, and the root copy matches it. One squash pass on the affected line funds all but 4 `B`. Unfunded.

2026-09-23: rotating reminder and poll count. `scripts/preview.py` grows 56,416 → 57,564 `B` for the `REMINDERS` tuple, the cursor and the counter. `skills/arena-preview-steering/SKILL.md` grows 10,435 → 10,559 `B` for the reminder contract. The refs harness grows 77,124 → 79,039 `B` with the matching asserts. One squash pass on each new line found no further removal. Unfunded.

2026-09-23: task-link requirement. `skills/arena-preview-steering/SKILL.md` grows 10,559 → 10,580 `B` for the `--msg-id` clause, after one squash pass on the new line. Unfunded.

2026-09-23: poll count beside pending only. `scripts/preview.py` grows 57,564 → 57,639 `B`. `skills/arena-preview-steering/SKILL.md` grows 10,580 → 10,600 `B` for the clause. The refs harness grows 79,039 → 79,373 `B` with the rewritten rotation block. Unfunded.
