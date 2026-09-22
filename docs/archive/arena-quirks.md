# Arena quirks

Observed Arena.ai platform behaviours, not repository defects. Linked rules are authoritative. Entries record failed commands, returned payloads, missing files, or owner reports. Dates are sandbox observation dates. Unknown days stay unspecified. Four restores deleted the original steering notes. [CHANGELOG.md](../../CHANGELOG.md) is the durable record.

## GitHub token expiry mid-turn

[rules/ARENA.md](../../rules/ARENA.md) carries the rule. `GH_TOKEN` can die without a repository change. `gh auth status` calls it invalid, pushes fail, and `gh auth setup-git` does not help.

2026-09-21, `arena/01a0be68-clankers`. After a commit unrelated to authentication, three consecutive `git push` attempts failed: `fatal: could not read Username for 'https://github.com': terminal prompts disabled`.

`gh auth status` reported `X github.com: authentication failed — The github.com token in GH_TOKEN is no longer valid.` The fourth push succeeded roughly a minute later. Between attempts, the agent only sent two local-preview acknowledgements.

This contradicts the premise of "retry once, then end the turn": recovery can occur mid-turn after a variable failure count. An earlier turn on this branch recovered only after the first retry failed and the turn ended. Both observations remain. The owner decides the guidance.

## The question tool returns skipped at token death

2026-09-21, `arena/01a0be68-clankers`. Four question blocks with a dead token returned `{"answers": [], "skipped": true}`. They gave no answer, error, or reason. The standing instruction requires attempts at token death to measure this.

At that point, no dead-token attempt received an answer. The experiment stayed open. A skipped block neither ends the turn nor raises an error, and gives no evidence that the owner saw it.

## The token budget is not readable

No surface gives the agent a remaining-token counter, warning, or injected message. Claims about impending exhaustion infer it from conversation length.

One such claim ended a turn. The owner expected compaction, not a cutoff, and did not know the agent could make that claim. Compaction does occur: this session opened with a system block that replaced earlier conversation with condensed memory.

The unsupported claim cost a turn. The recorded probe distinguishes a dead budget (`skipped`) from a live one (an answer), not a number or a refill. Nothing exposes a remaining count.

[rules/ARENA.md](../../rules/ARENA.md) ends turns when work is verified and stopped, never for a stated budget limit.

## Mid-turn sandbox restore

A restore returns HEAD to the branch base, deletes every gitignored directory, kills processes, and deletes preview SQLite state while the turn continues. Pushed commits survive remotely. Tree-only work survives as uncommitted differences against the base.

2026-09-21, first restore, `arena/01a0be68-clankers`: `.venv`, the preview server, and `reports/arena-preview/state.sqlite3` disappeared, including 111 notes and receipts. Recovery used `git fetch -q origin <branch>` then `git reset --mixed FETCH_HEAD` to restore HEAD without changing the tree. The notes were unrecoverable.

The second restore, roughly two hours later on the same branch, left HEAD at `c3c11b3`. The earlier push protected the code. Recovery took five steps. Fetch and mixed-reset. Rebuild the venv with pinned `ruff` from `ruff.toml` and `markdown-it-py`. Restart the preview. Reconstruct tasks from context. Write the JSON backup for `task-import`. That feature shipped minutes earlier without a user. The loss forced manual reconstruction.

The Python harness also writes `__pycache__` inside the live skill copy. A `diff -r` parity check then reports untracked differences.

The fourth restore occurred minutes after a commit and push on 2026-09-21. HEAD returned to base. `.venv`, `node_modules/`, `.tiktoken-cache/`, and all `reports/` data disappeared, including the server, database, reports, and task backup. Recovery repeated the five steps and rebuilt finished tasks from commit history, one record per shipped change with its commit. Report drafts survived in context and restored the publications.

A task backup protects against bad imports, not restores. Tooling also disappears: `npx --no-install markdownlint-cli2` reported a missing package until `npm install markdownlint-cli2` restored it. Distinguish a broken gate from a lint failure.

During inbox restoration that day, the owner pasted history in chunks. The agent imported and acknowledged all twenty-eight notes, assuming earlier answers. Five had no answer. The owner identified the false receipts as an amendment.

Restore acknowledgement state with each note or leave it unset. Never infer an answer. A log copy containing only id, text, and at lacks receipt state and cannot count as complete.

## A refresh can reset the sandbox, not just the visible history

2026-09-21, `arena/01a0be68-clankers`. The owner reported that refresh reset visible history. Agent-context retention was unclear. A later refresh let the same turn continue.

The agent initially distinguished filesystem and preview state from the harness reasoning and displayed transcript. It checked matching local and remote tips. Only two intentionally untracked handoff files remained.

The owner corrected that account: refresh reset the working sandbox and lost all uncommitted data, including history. The earlier distinction was false. Filesystem, inbox, and visible-history resets were the same event at different levels, as the preceding two restores indicated. Harness reasoning did survive while files disappeared. Commit and push early, before turn end.

A later message requested another history-reset recovery. Local HEAD, `FETCH_HEAD`, and remote all remained `094fc30`. The tree was clean, `.venv` and `node` existed, `/api/state` returned 200, and `state.sqlite3` retained 51 notes and 32 tasks. Nothing needed pulling.

The agent nevertheless recorded a transcript-only reset variant and pushed `dad5ce1`. The owner corrected it: the message was a duplicate of an earlier report, not another reset. The agent inferred and shipped an observation from ambiguous text.

Keep the retraction beside the claim. Recover from durable sources, not discardable memory, and push before turn end. Check whether a message describes a new event or repeats one before treating it as evidence or instruction.

One observation remains: `gh pr view` returned `mergeable=UNKNOWN mergeStateStatus=UNKNOWN` with the correct head after an earlier MERGEABLE result. UNKNOWN means computation is pending. Query again rather than report a fault.

## The encoding host tiktoken needs is unreachable

2026-09-21, `arena/01a0be68-clankers`, after the first restore. `maintenance/check.py` could not fetch its encoding from `openaipublic.blob.core.windows.net`: `SSLZeroReturnError`, unchanged on retry. PyPI remained reachable for venv recovery. The unseeded budget gate could not run. CHANGELOG Checks lines stated the gap. `maintenance/check_measurements.py` and three-copy `diff -r` checks covered non-token measurements and parity.

[maintenance/README.md](../../maintenance/README.md) gives the verified seed command: `gh api -H "Accept: application/vnd.github.raw" repos/niieani/gpt-tokenizer/contents/data/cl100k_base.tiktoken`. Write the result to `$TIKTOKEN_CACHE_DIR/<sha1 of the blob URL>`.

Verified on 2026-09-21: 1,681,126 bytes, accepted by tiktoken's hash check. The validator then passed. The raw header is required because the contents API stops base64 above 1 MB. Restores delete ignored `.tiktoken-cache/`, so seed again with venv recovery. The unchanged command passed on the first attempt after the fourth restore.

## `gh pr edit --body-file` fails

2026-09, `arena/01a0be68-clankers`, day unrecorded. Editing a PR body from a file failed. `gh api -X PATCH` with the body in the request succeeded. These apparently equivalent commands behave differently here.

## `git am` does not carry work across sessions

2026-09, `arena/01a0be68-clankers`, day unrecorded. The owner's patches did not transfer uncommitted work with `git am`. Pushed branches do cross sessions. Try a push before turn end. An uncommitted handoff is a last resort, not a plan.

## Clipboard writes need a secure context

2026-09-21, `arena/01a0be68-clankers`. `navigator.clipboard.writeText` exists under the HTTPS preview proxy, not a plain HTTP port forward. The preview tries it, then a hidden textarea with `document.execCommand('copy')`. It reports the successful path or both failures. The owner requested this context with the warning.

## Arena duplicates messages, and a dupe can replace one

2026-09-21, `arena/01a0be68-clankers`. `Store.note()` returns the stored record for an identical ID/text pair and rejects changed text under that ID. A duplicate with a fresh ID is a second note. Before answering an apparent repeat, check the recent log for identical text. Nothing otherwise prevents a second answer.

The owner reported repeats that each queue another turn. The agent also observed them. Without detection, repeats cause duplicate answers and can revive an ended turn.

Historical note `41c6b09a` reports replacement, with no mechanism established: a duplicate can replace a new message. Ordinary repeats retain the original for comparison. Replacement loses that evidence and leaves no recovery path. Mismatched instructions or answers referring to absent text are indirect signs. Ask the owner. This caused the retracted entry above.

A false `continue tasks!` then triggered thirty-four new lines in `scripts/preview.py`. The owner stopped the turn and disowned it. `git checkout` deleted the lines before any commit. The agent cannot identify replacements from plausible, unmarked instructions. Uncommitted work limited this incident to a stopped turn. Small commits and early pushes remain the practical safeguard.

## The question tool answered at token death

2026-09-21, `arena/01a0be68-clankers`. Against four skipped attempts, a question tool returned `skipped: false` with two answers when a settled P1 bug required a decision. One answer selected an option, the other supplied text. The budget was effectively spent, but no remaining count was measured.

This was not a controlled trial: the question shape differed and there were two questions, not one. The sample is one success against four skips. Ask rather than assume. One call costs less than a wrong turn.

The answers required one CLI polling command, with no other exposed read path, for the P1 Seen bug. They also kept the handoff out of Git, where restores delete it.

2026-09-22, `arena/01a0c5a8-clankers`. An in-turn retry reported but did not clear the dead token. The next turn restored it. Blocking through the question tool exposes the failure and leaves the turn, so [rules/ARENA.md](../../rules/ARENA.md) now requires that instead of a silent end.

Context exhaustion was worse: `This conversation is too long for this model. Please start a new chat.` prevented the documented exit and lost every unpushed commit. The sandbox did not outlive its conversation. Push after each commit.

## `Something went wrong. Please try again.` arrives as a message

The owner reported on 2026-09-21 that Arena returned `Something went wrong. Please try again.` instead of a turn. Pasting it sent three messages and continued the turn without interrupting the agent. Both facts are owner reports, not inferred mechanisms.

Treat a message containing only that error as a nudge to resume standing work, not a new instruction or complaint. Say so in the receipt so the owner can correct that reading. This avoids repeating the false `continue tasks!` incident that cost a turn and thirty-four reverted lines.

Read and acknowledge the actual pending messages. Do not assume three deliveries became three notes or one. Unacknowledged duplicates remain unanswered in the log. The owner expects these error-string messages and skipped question tools as normal workarounds for platform failures. `skipped: true` alone does not establish a broken tool.

## Chromium for E2E tests

The sandbox blocks normal Chromium installation paths: the Playwright browser CDN, Google CDNs and `apt`. Use `@sparticuz/chromium` from reachable npm. Observation date and branch unrecorded.

### Install

```bash
npm install @sparticuz/chromium
```

Extract the package’s four brotli archives with its helper:

| Archive | Destination |
| --- | --- |
| binary | `/tmp/chromium` |
| libraries | `/tmp/al2023/lib` |
| fonts | `/tmp/fonts` |
| SwiftShader | `/tmp` |

### Run

The source project’s E2E suite accepts a non-Playwright binary through `DAEDALUS_E2E_CHROMIUM`. Set it and the required runtime variables:

```bash
export DAEDALUS_E2E_CHROMIUM=/tmp/chromium
export LD_LIBRARY_PATH=/tmp/al2023/lib:/tmp
export VK_ICD_FILENAMES=/tmp/vk_swiftshader_icd.json
```

`LD_LIBRARY_PATH` needs both directories. SwiftShader cannot start without the ICD file in `VK_ICD_FILENAMES`.

### Known gap

The sandbox lacks system fontconfig. This source-project test fails locally even without a code defect:

`test_the_pool_column_fits_the_longest_pool_name`

It measures a column against a missing font. A monospace TTF through `@font-face` made it pass, proving an environment defect, not an assertion defect. The other 51 assertions pass without that font.
