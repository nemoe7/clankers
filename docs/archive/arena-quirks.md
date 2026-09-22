# Arena quirks

Behaviours of the Arena.ai hosting environment that cost work. Each entry is a platform behaviour, not a repository defect. Where a rule already carries the instruction, this file links to the rule. The rule is the authoritative copy.

Every entry traces to something that happened in a session. A command failed, a payload came back, or a file was missing. Dates are the day of the observation inside the sandbox. Where the day went unrecorded, the entry says so rather than guessing. Restores wiped the steering inbox four times, so the notes that first carried these observations are gone. [CHANGELOG.md](../../CHANGELOG.md) is the durable record.

## GitHub token expiry mid-turn

[rules/ARENA.md](../../rules/ARENA.md) carries the rule. `GH_TOKEN` can die mid-turn with no repository change. `gh auth status` calls it invalid, pushes fail, and `gh auth setup-git` does not help.

2026-09-21, `arena/01a0be68-clankers`. A push failed after a commit that changed nothing about authentication. Three consecutive `git push` attempts failed with `fatal: could not read Username for 'https://github.com': terminal prompts disabled`.

`gh auth status` reported `X github.com: authentication failed — The github.com token in GH_TOKEN is no longer valid.` The fourth attempt, roughly a minute later, pushed the commit. The agent did nothing in between but send two acknowledgements through the local preview.

That contradicts the rule's premise of "retry once, then end the turn". That premise assumes the next turn brings a fresh token. In-turn revival is real, and the failure count before it is not fixed. An earlier turn on the same branch saw the first retry fail to revive the token. The push landed only after that turn ended. Both readings stay, because they point at different guidance. Choosing between them is the owner's call.

## The question tool returns skipped at token death

2026-09-21, `arena/01a0be68-clankers`. With the token dead, a question block returned `{"answers": [], "skipped": true}`. No answers, no error, and no sign to the agent of why. The standing instruction is to attempt the tool at token death so this can be measured. Four attempts are recorded, and all four returned skipped.

No one has answered a question block while the token is dead, so the experiment stays open. The four readings do establish one fact. A skipped block is silent. It does not end the turn, it does not raise, and it does not say whether the owner saw anything.

## The token budget is not readable

No surface reports the remaining token budget to the agent. There is no counter, no warning, and no injected message. An agent that says the budget is about to run out guesses from the conversation length.

One session ended a long turn with that claim. The owner did not know the claim was possible. They expected compaction instead, because a modern agent harness condenses a long conversation rather than cut it. Compaction does occur here. This session opened with a system block that replaced the earlier conversation with a condensed memory document.

So the claim was a guess, and it cost that session a turn. The observable signal of a dead budget is different, and the section above records it. The question tool returns `skipped` when the budget dies. It returns an answer while the budget lives. That probe reports death only. Nothing exposes a number, so no probe can report a refill.

[rules/ARENA.md](../../rules/ARENA.md) now ends a turn when the agent verifies the work and stops. It bans the budget as a stated reason.

## Mid-turn sandbox restore

A restore resets the workspace to an earlier snapshot while the turn still runs. HEAD goes back to the branch base. It deletes every gitignored directory, kills background processes, and takes the preview's SQLite state. Committed and pushed work survives on the remote. Work that lived only in the tree survives as uncommitted differences against the base commit.

2026-09-21, first restore, `arena/01a0be68-clankers`. It deleted `.venv`, killed the preview server and wiped `reports/arena-preview/state.sqlite3`. That took 111 steering notes and their receipts. Recovery was `git fetch -q origin <branch>` then `git reset --mixed FETCH_HEAD`. That restored HEAD to the pushed tip and left the tree alone. The notes were not recoverable.

2026-09-21, second restore, same branch, roughly two hours later. The branch was pushed, so the code was safe. HEAD sat at the base commit `c3c11b3`. Recovery took five steps. Fetch and mixed-reset to the remote tip. Rebuild the venv with the pinned `ruff` from `ruff.toml` beside `markdown-it-py`. Restart the preview server. Rebuild the task list from what the session still held. Then write the JSON backup that `task-import` reads. That backup exists because of this restore. The feature had shipped minutes earlier with no user yet, so the loss forced a hand reconstruction.

A restore also leaves the repository dirtier in one specific way. The Python harness writes `__pycache__` inside the live skill copy. A `diff -r` parity check then reports a difference that no tracked file contains.

2026-09-21, fourth restore, minutes after a commit and its push. HEAD returned to the branch base. `.venv`, `node_modules/`, `.tiktoken-cache/` and the whole `reports/` directory were gone. So were the preview server, the state database, the published reports and the task backup. Recovery ran the five steps and added one. The task list came back from the commit history, one finished record per shipped change citing its commit. The backup shares the fate of everything under `reports/`. The published reports came back from the drafts the turn still held in context.

Two lessons repeat. The task list dies with the state directory, so its backup protects against a bad import rather than a restore. And the tooling the gates need dies too. `npx --no-install markdownlint-cli2` reported a missing package until `npm install markdownlint-cli2` restored it. That is a broken gate, not a lint failure. Read the failure before acting on it.

2026-09-21, restoring the inbox afterwards. The owner pasted the lost history back in chunks and the agent imported it. It then marked all twenty-eight restored notes acknowledged. The reasoning was that it answered them before the wipe. Five of them were not answered. The paste held the owner's unacknowledged messages, so the blanket acknowledgement reported five answers that never existed. The owner caught it and named it as an amendment.

Two rules follow. A restore must carry the acknowledgement state with the note or leave it unset. It must never assume an answer. A copy taken from the log carries only id, text and at. That omits exactly the state that decides whether a note still needs an answer. Such a copy cannot enter as though it were complete.

## A refresh can reset the sandbox, not just the visible history

2026-09-21, `arena/01a0be68-clankers`. The owner reported that a browser refresh made Arena reset the visible message history. It was unclear whether the agent still held its context. A later refresh let the same turn carry on.

The agent's working state is the sandbox filesystem plus the preview's SQLite inbox. The harness carries the reasoning the turn runs on, not the transcript on display. The agent verified rather than assumed. Local HEAD and the remote tip matched. The tree held nothing uncommitted but two untracked handoff files that stay out of Git on purpose.

The owner then fixed this entry. The refresh did cause a working sandbox state reset. It lost all uncommitted data, the message history included. So the claim above is false. A refresh can reach both the filesystem and the inbox. The two restores under the previous heading are what that looked like from inside the turn. The visible-history reset and the sandbox reset are one event seen at two altitudes. What still holds is that the harness carries the turn's reasoning. The agent kept working through a reset that deleted its files. The only defence is an early commit. That is why the branch goes out before a turn ends rather than after it.

A later message said Arena had reset the message history and instructed a repull from the branch. The agent verified instead of assuming. Local HEAD, `FETCH_HEAD` and the remote tip were all `094fc30`. The tree was clean, and `.venv` and `node` were present. The preview server still answered `/api/state` with 200. `state.sqlite3` still held all 51 notes and 32 task records. There was nothing to pull.

It then wrote a sub-entry claiming a second variant of the reset. That variant stops at the visible transcript and leaves the sandbox alone. The agent pushed it as `dad5ce1`. The owner fixed it. Arena had not reset the visible history at all. The message that read as a report of one was the owner's own earlier message arriving again. The event was a duplicate, not a reset. The variant was an inference from an ambiguous message, recorded as an observation and shipped.

What survives is the recovery. Read the durable sources rather than a memory the platform can discard. Push before a turn ends so there is something to repull. What does not survive is the claim. The retraction stays beside it rather than the entry disappearing quietly. A record that only ever grows is a record nobody checks.

The lesson is about evidence rather than about Arena. When a message is the only evidence for a platform behaviour, ask whether the message is the evidence or the event. A duplicate reads as a reset. A resend reads as a new instruction. Both are cheap to check and expensive to record incorrectly.

One detail from the same turn holds. `gh pr view` reported `mergeable=UNKNOWN mergeStateStatus=UNKNOWN` with the right head commit. The same query returned MERGEABLE earlier in the session. UNKNOWN means GitHub is still computing rather than delivering a verdict. Ask again rather than report a problem.

## The encoding host tiktoken needs is unreachable

2026-09-21, `arena/01a0be68-clankers`, after the first restore. `maintenance/check.py` could not run. Fetching its encoding from `openaipublic.blob.core.windows.net` failed with an `SSLZeroReturnError`. A retry did not help. PyPI stayed reachable, so rebuilding the venv worked while the encoding host did not. The instruction-budget gate therefore cannot run unseeded. Every CHANGELOG Checks line since says so rather than implying the gate passed. What covers the gap is `maintenance/check_measurements.py`, which measures the files without tiktoken, plus a `diff -r` across the three skill copies.

The workaround works, and it is the useful half. [maintenance/README.md](../../maintenance/README.md) carries the verified seed command. Run `gh api -H "Accept: application/vnd.github.raw" repos/niieani/gpt-tokenizer/contents/data/cl100k_base.tiktoken` and write it to `$TIKTOKEN_CACHE_DIR/<sha1 of the blob URL>`.

Verified on 2026-09-21 at 1,681,126 bytes. The validator went from unrunnable for a session to green in one step. tiktoken checks the hash itself and accepted the mirror. The raw accept header is not optional. The file sits above the 1 MB limit at which the contents API stops returning base64. Git ignores `.tiktoken-cache/`, so a restore deletes it. Re-seeding belongs in the same list as rebuilding the venv. The fourth restore proved that list right. The seed command worked again unchanged, and the budget gate passed on the first try.

## `gh pr edit --body-file` fails

2026-09, `arena/01a0be68-clankers`, day not recorded. Editing a pull request body from a file failed. Patching through the API worked instead, with `gh api -X PATCH` and the body in the request. This entry stays because the two commands look interchangeable and only one of them runs here.

## `git am` does not carry work across sessions

2026-09, `arena/01a0be68-clankers`, day not recorded. The owner tried patch files to move uncommitted work between sessions. `git am` was useless for it. A pushed branch does carry work across a session boundary. That is why the standing instruction is to try a push before ending a turn. An uncommitted handoff file is a last resort rather than a plan.

## Clipboard writes need a secure context

2026-09-21, `arena/01a0be68-clankers`. `navigator.clipboard.writeText` exists only for a page in a secure context. A copy button cannot rely on it. Over the proxied preview host, which is HTTPS, it exists. Over a plain HTTP port forward it does not. The preview therefore tries the API first. It then falls back to a hidden textarea and `document.execCommand('copy')`. It reports which path it took, or that the browser allowed neither. The owner asked that the caveat carry its context rather than sit as a bare warning.

## Arena duplicates messages, and a dupe can replace one

2026-09-21, `arena/01a0be68-clankers`. `Store.note()` looks the ID up first. It returns the stored record unchanged when the same ID arrives with the same text. It refuses when the same ID arrives with different text. A duplicate carrying the same ID therefore costs nothing. A duplicate arriving with a fresh ID is a second note. Nothing in the agent's behaviour guards against answering it twice. The guard is to look for an identical recent note in the log before answering one that reads like a repeat.

The owner then stated it from their side. Arena repeats their messages, and each repeat queues another turn. The agent observed the duplication, so it is not a hypothesis. The cost is visible. The agent answers the same ask twice unless it notices, and a repeated message can revive a turn that ended.

Note `41c6b09a` adds a second case, recorded as reported with no mechanism inferred. Arena sends dupe messages, and the dupe can replace the message the owner sends. That is worse than a repeat. A repeat leaves the original intact beside the copy, so deduping by ID or by a log read catches it. A replacement leaves one message standing in for another whose content never arrived. The agent then has nothing to compare against and no way to recover it. The only signs are indirect. An answer may refer to something the log does not contain. An instruction may not match what the owner says they sent. The only recovery is to ask. This is the case that produced the retracted entry above.

It then hit an instruction rather than a report. A message reading `continue tasks!` arrived. Thirty-four lines went into `scripts/preview.py` before the owner stopped the turn and said the message was false. The lines came out again with `git checkout` and no commit followed. The cost was a stopped turn rather than a bad commit. The agent cannot tell from inside the turn that an instruction changed. The replacement does not arrive marked as one. It arrives as an instruction, in the owner's register, asking for something plausible. What limited the damage was that the work was still uncommitted. That argues for small commits and early pushes rather than for any cleverness on the agent's part.

## The question tool answered at token death

2026-09-21, `arena/01a0be68-clankers`. This is the counter-observation to the four skipped readings. The budget was effectively spent and a real decision blocked a settled P1 bug. The agent attempted the tool again on the standing instruction. It returned `skipped: false`, with both questions answered. One came back as a chosen option and one as free text.

Nothing about this attempt ran as a control. The agent did not measure the remaining budget. The shape of the question differed, and it asked two questions rather than one. The honest statement is that the tool sometimes works at token death and sometimes does not. The sample is one against four. The behaviour stays as it already was. Ask rather than assume, because the attempt costs one call and a wrong assumption costs a turn.

Both answers were substantive. The agent fixes the P1 seen bug by giving itself one CLI command to poll. It exposes reading nowhere else. And the handoff stays out of Git, which means a restore keeps deleting it.

2026-09-22, `arena/01a0c5a8-clankers`. A retry inside the same turn does not bring a dead token back. The documented retry tells the agent that the push failed, and it does not clear the failure. The token comes back with the next turn, so the only reliable recovery is to leave the turn. Blocking with the question tool leaves it in a way that tells the owner what failed. That is why [rules/ARENA.md](../../rules/ARENA.md) now names the tool instead of a silent end.

Context exhaustion is a second failure, and it is worse. The previous session ended with `This conversation is too long for this model. Please start a new chat.` It refused to leave the turn the documented way, and it lost every commit that it had not pushed. A sandbox does not outlive the conversation that created it. An unpushed commit is therefore not a saved commit, and the agent must push after each one.

## `Something went wrong. Please try again.` arrives as a message

The owner reported on 2026-09-21 that Arena answered with `Something went wrong. Please try again.` where a turn should have been. Pasting that string back in sent it three times. It continued the turn without interrupting the agent. Both halves are the owner's report and not an inference. That is the standard this file holds itself to since the retracted entry above.

A message whose whole text is that error string is not an instruction. It is the owner nudging a stalled turn with the only text the platform handed them. It carries no content about the work. Reading it as a direction repeats the mistake of the false `continue tasks!`. That mistake cost a stopped turn and thirty-four reverted lines. The response that fits is to keep working the standing instructions. Say in the receipt that the message read as a nudge, so the owner can set that reading right if it was wrong.

The three deliveries are the duplicate behaviour arriving in a new place. Whether they land as three notes or as one is not something to assume. Read the inbox and acknowledge what is actually pending. An unacknowledged duplicate stays in the log as an unanswered message. The owner's expectation, stated in the same note, is that this is normal from here. Expect skipped question tools and a few messages of exactly this shape. So `skipped: true` is not evidence that the tool is broken. An error-string message is not evidence of a complaint. Both are the platform failing, and the owner working around it by hand.
