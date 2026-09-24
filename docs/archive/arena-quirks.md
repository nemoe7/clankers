# Arena quirks

Observed Arena.ai platform behaviours, not repository defects. Linked rules are authoritative. Each entry records an observation, its consequence and the current rule. Dates are sandbox observation dates, and unknown days stay unspecified. Restores deleted the original steering notes, so [CHANGELOG.md](../../CHANGELOG.md) is the durable record.

## GitHub token expiry mid-turn

[rules/ARENA.md](../../rules/ARENA.md) carries the rule. `GH_TOKEN` can die without a repository change: `gh auth status` calls it invalid, pushes fail with `could not read Username`, and `gh auth setup-git` does not help. Recovery can occur mid-turn after a variable failure count, so "retry once, then end the turn" does not hold.

## The question tool at token death

2026-09-21: a dead token made four question blocks return `{"answers": [], "skipped": true}`, with no answer, error or reason. A skipped block neither ends the turn nor raises an error, and it gives no evidence that the user saw it. One later block returned `skipped: false` with two answers. The question shape differed, so that sample is one success against four skips, not a trial. Ask rather than assume.

2026-09-22: an in-turn retry reported but did not clear the dead token, and the next turn restored it. [rules/ARENA.md](../../rules/ARENA.md) now requires blocking through the question tool, which exposes the failure and leaves the turn, instead of a silent end.

Context exhaustion is worse: `This conversation is too long for this model. Please start a new chat.` prevented the documented exit and lost every unpushed commit. Push after each commit.

## The token budget is not readable

No surface gives the agent a remaining-token counter, warning or injected message. A claim about impending exhaustion infers it from conversation length, and one such claim ended a turn. Compaction does occur: a system block can replace earlier conversation with condensed memory. Nothing exposes a remaining count or a refill.

[rules/ARENA.md](../../rules/ARENA.md) ends turns after it verifies and stops the work, never for a stated budget limit.

## Mid-turn sandbox restore

A reset can return HEAD to the branch base and delete ignored directories. In two observed resets on 2026-09-24, tooling, virtual environments and hooks under the home directory disappeared, and the preview server stopped. The first reset deleted preview SQLite state. The second kept it. Pushed commits survived remotely, and tree-only work appeared as uncommitted differences against the base. Notes, receipts and tasks in lost state do not survive.

Recovery runs the steering installer first, then `git fetch -q origin <branch>` and `git reset --mixed FETCH_HEAD`, then the repository toolchain and a restarted preview. Rebuild tasks from commit history only if the state is missing. The installer rewrites the home-directory files a restore deletes, including the global ignore rule that keeps the state directory out of `git status`. A task backup protects against bad imports, not every restore. Missing tooling reads as a lint failure, so distinguish a broken gate from a real one. The Python harness writes `__pycache__` inside the live skill copy, so a `diff -r` parity check reports untracked differences.

An earlier reset kept tracked worktree changes, unignored repository files and pushed commits. It deleted paths ignored by `.gitignore` or `.git/info/exclude`, and reset `.git/info/exclude`. Files outside the workspace and home-directory tools disappeared. In another reset, Git ignored one file only through `core.excludesFile`, but the file survived. That reset lost the Git setting. The cause is unknown.

2026-09-24: About one hour passed between the last check before the reset and the first check after it. Ten of 20 probe files survived: root and nested files in the untracked, hidden, globally ignored `arena-state/`, intent-to-add and staged groups. Both symlinks, both manifests, the preview SQLite inbox and its report also survived. The reset lost both files in each of five groups: repository-ignored `.tiktoken-cache/`, locally excluded, `.cache/`, `.git/info/` and outside the workspace. All surviving bytes matched the original hash. The Git index lost the staged and intent-to-add flags. The reset also lost the global ignore setting. The installer restored it. An earlier reset on the same day lost `arena-state/state.sqlite3`. The reason for this difference is unknown. Do not treat this one-hour result as a guarantee that ignored data survives. Push non-secret work that must persist. Keep private preview state out of Git.

Restore acknowledgement state with each note, or leave it unset. Never infer an answer: one import marked twenty-eight pasted notes acknowledged, and five had no answer. A log copy holding only id, text and at lacks receipt state and cannot count as complete.

## A refresh can reset the sandbox, not just the visible history

2026-09-21: a refresh resets the working sandbox and loses all uncommitted data, including history. Filesystem, inbox and visible-history resets are the same event at different levels, and harness reasoning survives while files disappear. One later recovery request repeated an earlier report, with HEAD, remote and state intact. Check whether a message describes a new event or repeats one before treating it as evidence or instruction. Keep the retraction beside the claim, and recover from durable sources. Commit and push early, before turn end.

`gh pr view` can return `mergeable=UNKNOWN mergeStateStatus=UNKNOWN` with the correct head after a MERGEABLE result. UNKNOWN means computation is pending. Query again rather than report a fault.

## The encoding host tiktoken needs is unreachable

2026-09-21: `maintenance/check.py` could not fetch its encoding from `openaipublic.blob.core.windows.net`, with `SSLZeroReturnError` unchanged on retry, while PyPI stayed reachable. The unseeded budget gate cannot run. The remaining gates still cover non-token measurements and parity.

[maintenance/README.md](../../maintenance/README.md) gives the verified seed command. The raw header is necessary, because the contents API stops base64 above 1 MB. Restores delete the ignored cache directory, so seed it again with venv recovery.

2026-09-23: the block covers more hosts than the encoding blob. `agent-plugins.org` refused a TLS handshake from `curl` and `urllib` alike. The Actions artifact host `productionresultssa19.blob.core.windows.net` ended a signed download with EOF. `api.github.com`, PyPI and the npm registry answered. A checker that fetches a canonical schema takes a local-copy override for runs here. The runner verifies an artifact's contents. A session here reports that limit instead of claiming the bytes.

## `gh pr edit --body-file` fails

2026-09, day unrecorded: editing a PR body from a file failed, and `gh api -X PATCH` with the body in the request succeeded. These apparently equivalent commands behave differently here.

## `git am` does not carry work across sessions

2026-09, day unrecorded: patches did not transfer uncommitted work with `git am`. Pushed branches do cross sessions. Try a push before turn end. An uncommitted handoff is a last resort, not a plan.

## Clipboard writes need a secure context

2026-09-21: `navigator.clipboard.writeText` exists under the HTTPS preview proxy, not a plain HTTP port forward. The preview tries it, then a hidden textarea with `document.execCommand('copy')`, and it reports the successful path or both failures.

## Arena duplicates messages, and a dupe can replace one

`Store.note()` returns the stored record for an identical ID and text pair, and it rejects changed text under that ID. A duplicate with a fresh ID is a second note. Before answering an apparent repeat, check the recent log for identical text. Without detection, repeats cause duplicate answers and can revive an ended turn.

One note reported replacement, with no mechanism established: a duplicate can replace a new message. Replacement loses the original for comparison and leaves no recovery path. Mismatched instructions, or answers that refer to absent text, are indirect signs. Ask the user. A replacement cannot be identified from plausible, unmarked instructions, so small commits and early pushes remain the safeguard.

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
