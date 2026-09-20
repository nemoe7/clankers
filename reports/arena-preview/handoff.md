# Handoff — arena/01a0be68-clankers

Written 2026-09-21 for whoever picks this up next. This file is committed, against the earlier
standing instruction that a handoff does not go into git, and the owner's note `ae2f413f` is why it
came up: `reports/` is gitignored, a sandbox restore deletes gitignored directories, so an untracked
handoff is missing in exactly the session that needs it. Only this one file is un-ignored — the state
database, the task backup and the pasted history sitting beside it stay out of git, and
`git status` is the check that they still are.

Everything below is either verified in this session or cited to where it can be verified. Where the
original evidence is gone, that is said rather than papered over. Do not fill a gap by guessing; the
owner's instruction for this handoff was that the next agent must not have to.

## Where things stand

- Branch `arena/01a0be68-clankers`. Local HEAD and the remote tip were both `efebd08` at the time of writing, pushed. Verify
  with `git ls-remote origin arena/01a0be68-clankers`: this sandbox keeps no remote-tracking refs, so
  `git rev-parse origin/<branch>` fails with "Needed a single revision" and means nothing.
- Pull request #33 is open and mergeable. It has never been merged and must not be without the
  owner's explicit authorisation.
- The preview server is running on port 8000 and answering `/api/state` with 200. Its state lives in
  `reports/arena-preview/state.sqlite3`, which survives sandbox restarts. A mirror of the task list
  is at `reports/arena-preview/tasks-backup.json`, and the owner's pasted history is at
  `reports/arena-preview/history-chunks.jsonl`.
- Assets (`assets/app.js`, `index.html`, `style.css`) are read from disk per request, so editing them
  needs no restart. `scripts/preview.py` is loaded once, so editing it does. The owner's earlier
  instruction not to restart the preview until they had extracted everything is satisfied: notes
  `bcec0d77` and `017f3fd` record that the extraction happened and the restore is complete.
- Two untracked files sit in the repository root, `HANDOFF.md` and `HANDOFF-9d400e4.patch`. They are
  stale, they are not to be committed, and they are not this file.

## What happened this session, in one paragraph

Two mid-turn sandbox restores wiped the working tree and the steering inbox. The owner pasted the
lost history back in five chunks; the agent reassembled them, imported 28 notes and 25 tasks, and
then made a mistake worth carrying forward: it marked all 28 restored notes as acknowledged, when the
paste was of the owner's *unacknowledged* messages, so five notes that had never been answered were
reported as answered. The owner caught it in note `b4604c50`. Those five were un-acknowledged again
and answered for real in `b99610a`. The lesson is recorded in `docs/archive/arena-quirks.md` under
the restore heading, and the fix that would have prevented it is task 1 below.

## Task 1 — restore-behaviour-amendment (deferred; its small half already shipped)

This is the substance of the amendment the owner asked for, expressed as two changes they specified
in note `bcfab056`. Nothing here is a proposal any more; the owner named both.

**Change A: the receipt joins the JSON copy.** `assets/app.js`, in the `#copy-log` click handler,
currently emits one JSON object per line with the keys `id`, `text` and `at`. It must emit the
receipt as well: `acknowledged_at`, `ack_kind` and `ack_text`, present on every line, `null` where
absent. `scripts/preview.py`'s `import-notes` must read those three keys and, when
`acknowledged_at` is present, write the note already acknowledged, carrying the original
`acknowledged_at` verbatim rather than stamping the import time. That last point is the whole
purpose: a restored receipt must say when it was actually written.

`Store.note()` cannot do this today. It inserts `id`, `text`, `at` only, and `Store.acknowledge()`
stamps `now()` and requires an answer text. So a restore path is needed — either an optional
argument on `Store.note()` or a separate method — that writes all six fields as given. Whichever is
chosen, importing a line that carries no ack keys must produce an unacknowledged note. Never infer
answered; that inference is exactly the bug this task exists to close.

**Change B: `at` drops to seconds — SHIPPED in `094fc30`, do not redo it.** `stamp()` in
`assets/app.js` runs where the log copy is built, so a stored `2026-09-20T22:00:47.982172+00:00`
leaves the clipboard as `2026-09-20T22:00:47` while the stored record keeps full precision. That
split is deliberate: the fraction is what makes two notes arriving inside one second orderable, so
truncating at write time would let them tie. `check_client.cjs` asserts the seconds-only shape
against a fixture whose `at` is a full `toISOString()` and sweeps every copied line for a surviving
fraction or offset. The cost is in the CHANGELOG: a restore through the copy stores the truncated
value, so restored notes lose sub-second ordering and the offset. The tasks copy is untouched and
still carries a full-precision `updated_at`, which leaves the two copies inconsistent on purpose.

**Tests.** `scripts/check_client.cjs` asserts today that the log copy's lines parse with exactly the
keys id, text and at; that assertion must change to the six keys, and should gain a check that the
`at` value matches the seconds-only shape. `scripts/check_preview.py` must drive `import-notes` both
ways: a line carrying a receipt comes back acknowledged with the original `acknowledged_at`, kind and
text intact, and a line without one comes back unacknowledged.

**Process.** Edit `skills/refs/arena-preview-steering/` first, then `cp` the changed files to
`skills/arena-preview-steering/` and `.agents/skills/arena-preview-steering/`, then confirm with
`diff -r --exclude=__pycache__` that all three match. Gates, each checked on its own exit status and
never through a pipe, because a pipe reports the tail's status and hides failures: `node --check`,
`node scripts/check_client.cjs`, `python scripts/check_preview.py`,
`python maintenance/check_measurements.py`, `ruff check .`, `ruff format --check .`,
`npx markdownlint-cli2 "rules/**/*.md"`, and the `diff -r` parity. Print the planned final commit
list before committing. Conventional Commits, subject only, no body. Then push.

## The backlog — every task in it is deferred

Note `e59b3677` corrected the earlier deferral: not the large tasks only, all non-small ones. That
leaves nothing live. Everything below is deferred and written up so it can be picked up without
guessing, and the only work shipped after the correction was `at-to-seconds`, which is small and is
finished. Do not start any of these without the owner promoting one.

The authoritative order is `preview.py task-list`, mirrored at
`reports/arena-preview/tasks-backup.json`; the numbers below are the order at the time of writing and
are not the point of this section.

1. **restore-behaviour-amendment** — task 1 above, next up.
2. **upload-tab** — **deferred to the back of the queue** by note `786692e4`, which deferred every
   large task. It stays documented here because the decision and the open questions are the useful
   part, and they were settled before the deferral. A tab of its own for uploading files, not an
   attachment to a note (note `cc554e83`). The owner has decided the storage question (note
   `66c38f8e`): try disk first so the bytes never pass through the database, with the database
   holding the record of the upload and its path. Unresolved and worth asking rather than assuming:
   where on disk the bytes land, what the size ceiling is, and whether a file that is not valid
   UTF-8 is accepted.
3. **report-pip** — drop the number badge on the Reports tab; a pip on the tab means a report has not
   been read. The badge element is `#report-count`.
4. **report-seen** — mark a report seen when the owner scrolls to its end, so the agent learns it was
   read and the owner learns whether they have read it already. The notes table already carries a
   `seen_at` column; reports do not, so this needs one.
5. **check-py-host** — get `maintenance/check.py` running again. It has not run since the restore
   because tiktoken cannot reach its encoding host. The budget gate is covered in the meantime by
   `check_measurements.py` and `diff -r` parity. Do not claim this gate as green; it is not.
6. **filter-by-receipt-status** — filter the message log by receipt status (note `6ee5bf47`). The
   three states already exist as dots — gray sent, blue seen, green said — so this filters over what
   the dot already reports rather than adding a notion.

## Tasks 7 to 10 — deferred by the owner on 2026-09-21

7. **save-state-button** — a button that saves the cached state to disk, so restoring is one click
   instead of a copy and a paste (note `cae4eb3c`). The browser cannot write the sandbox filesystem,
   so the button has to post the state and the server has to write it. Depends on task 1: a backup
   that omits receipts restores the same wrong picture that caused this task's predecessor. Open
   questions the owner has not answered: what exactly is saved — the whole `/api/state` payload the
   page holds, or notes and tasks only — where the file lands, and what reads it back.
8. **refs-audit** — audit `rules/refs/` against `rules/refs/GUIDELINES.md`, which is the standard.
   Report divergences as a fielded report with a recommended answer. `rules/` is propose-before-edit:
   do not change a rule file unilaterally.
9. **cli-inventory** — report every CLI command, its parameters and its maximum accepted shape. The
   output is a fielded report, numbered by publish order, and report submissions do not go into the
   message log. The surface to inventory is `scripts/preview.py` (`serve`, `init`, `read`, `ack`,
   `publish`, `task`, `task-remove`, `task-list`, `task-import`, `import-notes`) plus the maintenance
   scripts; each has hard limits in `preview.py` worth stating exactly — a note is 4000 characters, a
   report submission is `MAX_SUBMISSION` at 150,000, a task title is 200, a task carries 40 details
   of 2000 each, a report has 1 to 50 fields of 2000.
10. **minify** — ship a minified, squashed live build. **The original notes 36 and 37 are gone.**
    They were acknowledged before the wipe, so they were not in the owner's paste of unacknowledged
    messages, and their text does not exist anywhere in this sandbox. What survives is the task title
    and the memory that notes 36 and 37 were the final word on scope. Ask the owner to restate the
    scope before starting this one. Do not invent it.

## Rules that bind, restated because they were learned the hard way

- `ARENA.md` and the preview skill's own files are protected: amendments are proposed, never applied
  unilaterally. `rules/ARENA.md` and `ARENA.md` are byte-identical and must stay so.
- Receipts are one to three lines naming the change and the commit. The owner amended agent
  behaviour in note `bcfab056` on exactly this point: unnecessary prose in agent replies. Analysis
  belongs in a report or the CHANGELOG, never in a receipt.
- Read the steering inbox at the start of a turn, at each reasoning boundary, before and after each
  tool block, and at the end of the turn. Notes arrive mid-turn, repeatedly, and several this session
  changed work already in flight.
- After any task-list mutation, immediately run
  `preview.py task-list > reports/arena-preview/tasks-backup.json`. This is self-imposed and it has
  already earned its place once.
- Questions go out as fielded reports with a recommended answer, not through the blocking question
  tool — with one exception the owner insisted on: at token death, the question tool must be
  attempted, as a resurrection experiment. It has come back `skipped: true` on every attempt so far.
- The token budget dies mid-turn. Today a fourth in-turn attempt revived it, which contradicts the
  retry-once premise in `rules/ARENA.md`. The owner's position, in note `f8724f7d`, is "better be
  safe than sorry", and Arena repeats their messages anyway so turns queue themselves. The rule text
  is unchanged and only the owner can change it.
- Arena duplicates messages. This is confirmed by the owner, not hypothesised, and recorded in
  `docs/archive/arena-quirks.md`. `Store.note()` dedupes by ID and refuses an ID reused for different
  text, which covers a same-ID repeat and nothing else. Before answering a note that reads like a
  repeat, look for an identical recent one in the log.
