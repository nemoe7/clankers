# Arena quirks

Observed Arena.ai platform behaviours, not repository defects. Linked rules are authoritative. Each entry records an observation, its consequence and the current rule. Dates are sandbox observation dates, and unknown days stay unspecified. Four restores deleted the original steering notes, so [CHANGELOG.md](../../CHANGELOG.md) is the durable record. 

## GitHub token expiry mid-turn

[rules/ARENA.md](../../rules/ARENA.md) carries the rule. `GH_TOKEN` can die without a repository change: `gh auth status` calls it invalid, pushes fail with `could not read Username`, and `gh auth setup-git` does not help. 

2026-09-21: three consecutive pushes failed after a commit unrelated to authentication, and the fourth succeeded roughly a minute later. Recovery can occur mid-turn after a variable failure count, so "retry once, then end the turn" does not hold. 

## The question tool returns skipped at token death

2026-09-21: four question blocks with a dead token returned `{"answers": [], "skipped": true}`, with no answer, error or reason. A skipped block neither ends the turn nor raises an error, and it gives no evidence that the user saw it. 

## The token budget is not readable

No surface gives the agent a remaining-token counter, warning or injected message. A claim about impending exhaustion infers it from conversation length, and one such claim ended a turn. Compaction does occur: a system block can replace earlier conversation with condensed memory. 

A probe distinguishes a dead budget, which returns `skipped`, from a live one, which returns an answer. Nothing exposes a remaining count or a refill. 

[rules/ARENA.md](../../rules/ARENA.md) ends turns after it verifies and stops the work, never for a stated budget limit. 

## Mid-turn sandbox restore

A restore returns HEAD to the branch base, deletes every gitignored directory, kills processes, and deletes preview SQLite state while the turn continues. Pushed commits survive remotely. Tree-only work survives as uncommitted differences against the base. 

2026-09-21: four restores on one branch deleted `.venv`, `node_modules/`, `.tiktoken-cache/`, the preview server and the `reports/` data, including 111 notes and receipts. Recovery is `git fetch -q origin <branch>` then `git reset --mixed FETCH_HEAD`, then a rebuilt venv, a restarted preview and tasks reconstructed from commit history. The notes were unrecoverable. 

The Python harness writes `__pycache__` inside the live skill copy, so a `diff -r` parity check then reports untracked differences. 

A task backup protects against bad imports, not restores. Tooling disappears too: `npx --no-install markdownlint-cli2` reported a missing package until an install restored it. Distinguish a broken gate from a lint failure. 

One import that day marked all twenty-eight pasted notes acknowledged, and five had no answer. Restore acknowledgement state with each note, or leave it unset. Never infer an answer. A log copy holding only id, text and at lacks receipt state and cannot count as complete. 

## A refresh can reset the sandbox, not just the visible history

2026-09-21: a refresh resets the working sandbox and loses all uncommitted data, including history. Filesystem, inbox and visible-history resets are the same event at different levels. Harness reasoning survives while files disappear. Commit and push early, before turn end. 

A later message asked for another history-reset recovery. Local HEAD, `FETCH_HEAD` and remote all matched, the tree was clean, `/api/state` returned 200, and the state file held 51 notes and 32 tasks. Nothing needed pulling. Check whether a message describes a new event or repeats one before treating it as evidence or instruction. Keep the retraction beside the claim, and recover from durable sources, not discardable memory. 

One observation remains: `gh pr view` returned `mergeable=UNKNOWN mergeStateStatus=UNKNOWN` with the correct head after an earlier MERGEABLE result. UNKNOWN means computation is pending. Query again rather than report a fault. 

## The encoding host tiktoken needs is unreachable

2026-09-21: `maintenance/check.py` could not fetch its encoding from `openaipublic.blob.core.windows.net`, with `SSLZeroReturnError` unchanged on retry, while PyPI stayed reachable. The unseeded budget gate cannot run. `maintenance/check_measurements.py` and three-copy `diff -r` checks cover non-token measurements and parity. 

[maintenance/README.md](../../maintenance/README.md) gives the verified seed command. The raw header is necessary, because the contents API stops base64 above 1 MB. A seeded cache is 1,681,126 bytes and passes the tiktoken hash check. Restores delete the ignored cache directory, so seed it again with venv recovery. 

## `gh pr edit --body-file` fails

2026-09, day unrecorded: editing a PR body from a file failed, and `gh api -X PATCH` with the body in the request succeeded. These apparently equivalent commands behave differently here. 

## `git am` does not carry work across sessions

2026-09, day unrecorded: patches did not transfer uncommitted work with `git am`. Pushed branches do cross sessions. Try a push before turn end. An uncommitted handoff is a last resort, not a plan. 

## Clipboard writes need a secure context

2026-09-21: `navigator.clipboard.writeText` exists under the HTTPS preview proxy, not a plain HTTP port forward. The preview tries it, then a hidden textarea with `document.execCommand('copy')`, and it reports the successful path or both failures. 

## Arena duplicates messages, and a dupe can replace one

`Store.note()` returns the stored record for an identical ID and text pair, and it rejects changed text under that ID. A duplicate with a fresh ID is a second note. Before answering an apparent repeat, check the recent log for identical text. Without detection, repeats cause duplicate answers and can revive an ended turn. 

One historical note reports replacement, with no mechanism established: a duplicate can replace a new message. Ordinary repeats retain the original for comparison, and replacement loses that evidence with no recovery path. Mismatched instructions, or answers that refer to absent text, are indirect signs. Ask the user. 

A false `continue tasks!` once triggered thirty-four new lines in `scripts/preview.py`, and `git checkout` deleted them before any commit. Replacements cannot be identified from plausible, unmarked instructions. Small commits and early pushes remain the practical safeguard. 

## The question tool answered at token death

2026-09-21: against four skipped attempts, one question tool returned `skipped: false` with two answers when a settled P1 bug required a decision. This was not a controlled trial: the question shape differed, and there were two questions. The sample is one success against four skips. Ask rather than assume. 

2026-09-22: an in-turn retry reported but did not clear the dead token, and the next turn restored it. Blocking through the question tool exposes the failure and leaves the turn, so [rules/ARENA.md](../../rules/ARENA.md) now requires that instead of a silent end. 

Context exhaustion is worse: `This conversation is too long for this model. Please start a new chat.` prevented the documented exit and lost every unpushed commit. Push after each commit. 

## `Something went wrong. Please try again.` arrives as a message

2026-09-21: Arena returned `Something went wrong. Please try again.` instead of a turn. Pasting it sent three messages and continued the turn without interrupting the agent. Both facts are reports, not inferred mechanisms. 

Treat a message holding only that error as a nudge to resume standing work, not a new instruction or complaint. Say so in the receipt, so the user can correct that reading. Read and acknowledge the actual pending messages, and do not assume three deliveries became three notes or one. `skipped: true` alone does not establish a broken tool. 

## Chromium for E2E tests

The sandbox blocks the normal Chromium installation paths: the Playwright browser CDN, Google CDNs and `apt`. Use `@sparticuz/chromium` from reachable npm. Observation date unrecorded. 

### Install

```bash
npm install @sparticuz/chromium
```

Extract the four brotli archives in the package with its helper: 

| Archive | Destination |
| --- | --- |
| binary | `/tmp/chromium` |
| libraries | `/tmp/al2023/lib` |
| fonts | `/tmp/fonts` |
| SwiftShader | `/tmp` |

### Run

The source project's E2E suite accepts a non-Playwright binary through `DAEDALUS_E2E_CHROMIUM`. Set it and the required runtime variables: 

```bash
export DAEDALUS_E2E_CHROMIUM=/tmp/chromium
export LD_LIBRARY_PATH=/tmp/al2023/lib:/tmp
export VK_ICD_FILENAMES=/tmp/vk_swiftshader_icd.json
```

`LD_LIBRARY_PATH` needs both directories. SwiftShader cannot start without the ICD file in `VK_ICD_FILENAMES`. 

### Known gap

The sandbox lacks system fontconfig. One source-project test measures a column against a missing font, so it fails locally with no code defect: `test_the_pool_column_fits_the_longest_pool_name`. A monospace TTF through `@font-face` made it pass, which proves an environment defect. The other 51 assertions pass without that font. 
