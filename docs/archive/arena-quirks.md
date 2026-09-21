# Arena quirks

Behaviours of the Arena.ai hosting environment that cost work. This file records what the agent
observed inside the sandbox, not what anyone documents upstream. Each entry is a platform behaviour,
not a repository defect. Where a rule already carries the operational instruction, this file links to
the rule instead of repeating it. The rule is the authoritative copy.

Each entry holds dated observations, newest last, in the form `### YYYY-MM-DD branch`. A date is the
day the agent made the observation inside the sandbox. Where the day was not recorded at the time,
the entry says so rather than guessing. Every entry traces to something that happened in a session: a
command that failed, a payload that came back, a file that was missing. Nothing here comes from one
reading presented as a pattern.

Restores wiped the steering inbox four times, so the notes that first carried these observations are
gone. The durable record of the response lives in [CHANGELOG.md](../../CHANGELOG.md), whose Origins
lines name the notes by ID.

## GitHub token expiry mid-turn

[rules/ARENA.md](../../rules/ARENA.md) carries the rule: `GH_TOKEN` can die mid-turn with no
repository change, `gh auth status` calls it invalid, pushes fail, and `gh auth setup-git` does not
help.

### 2026-09-21 arena/01a0be68-clankers

A push failed after a commit that changed nothing about authentication. Three consecutive `git push`
attempts returned `fatal: could not read Username for 'https://github.com': terminal prompts
disabled`, and `gh auth status` reported `X github.com: authentication failed — The github.com token
in GH_TOKEN is no longer valid.` The fourth attempt, roughly a minute later, pushed the commit. The
agent did nothing in between but send two acknowledgements through the local preview.

That result contradicts the premise behind the rule's "retry once, then end the turn". The premise
assumes the next turn brings a fresh token. In-turn revival is real, and the number of failures
before it is not fixed. Earlier observations on this branch include a turn where the first retry did
not revive the token and the push landed only after the turn ended. This file records both readings
because they point at different guidance. Choosing between them is the owner's call, and an amendment
to `rules/ARENA.md` is not something this file can make.

## The question tool returns skipped at token death

### 2026-09-21 arena/01a0be68-clankers

With the token dead, a question block sent to the owner returned `{"answers": [], "skipped": true}`:
no answers, no error, and no visible sign to the agent of why. The owner's standing instruction is to
attempt the question tool at token death precisely so this behaviour can be measured. This is the
fourth attempt recorded, and every attempt returned skipped.

No one has yet answered a question block while the token is dead, so the experiment stays open. The
four readings do establish one fact: a skipped block is silent. It does not end the turn, it does not
raise, and it does not tell the agent whether the owner saw anything.

## Mid-turn sandbox restore

A restore resets the workspace to an earlier snapshot while the turn is still running. HEAD goes back
to the branch base. The restore deletes every gitignored directory, kills background processes, and
takes the preview's SQLite state with it. File content that the snapshot holds survives, so work that was
committed and pushed survives intact on the remote. Work that was only in the working tree survives
as uncommitted differences against the base commit.

### 2026-09-21 arena/01a0be68-clankers — first restore

The reset deleted `.venv`, killed the preview server and wiped `reports/arena-preview/state.sqlite3`,
which took 111 steering notes and their receipts with it. Recovery was `git fetch -q origin <branch>`
followed by `git reset --mixed FETCH_HEAD`, which restored HEAD to the pushed tip and left the
working tree alone. The notes were not recoverable. The CHANGELOG Origins lines are the only
surviving record of them.

### 2026-09-21 arena/01a0be68-clankers — second restore

The same shape, roughly two hours later, with the branch pushed and therefore the code safe. HEAD sat
at the base commit `c3c11b3`. `.venv` and the state directory were gone, the server was dead, and the
steering inbox held nothing. Recovery took five steps. The agent fetched and mixed-reset to the remote tip. It rebuilt the venv
and installed the pinned `ruff` from `ruff.toml` beside `markdown-it-py`. It restarted the preview
server. It rebuilt the whole task list from what the session still held. Then it wrote the JSON
backup that `task-import` reads. The second restore is the reason that backup exists. The feature had
shipped minutes earlier and no one was using it yet, so the first loss of the task list forced a
hand reconstruction.

A restore also leaves the repository dirtier than it found it in one specific way. The Python harness
writes `__pycache__` inside the live skill copy, which makes a `diff -r` parity check report a
difference that no tracked file contains.

### 2026-09-21 arena/01a0be68-clankers — fourth restore

The fourth restore arrived mid-turn, minutes after a commit and its push. HEAD returned to the branch
base, and `.venv`, `node_modules/`, `.tiktoken-cache/` and the whole `reports/` directory were gone,
along with the preview server, the state database, the published reports and the task backup.
Recovery ran the five steps above and added one. The task list came back from the commit history, one
finished record per shipped change citing its commit, because the backup shares the fate of
everything else under `reports/`. The published reports came back from the drafts the turn still held
in context.

Two lessons repeat here. The task list dies with the state directory, so its backup protects against
a bad import rather than against a restore. And the tooling the gates need dies too: `npx
--no-install markdownlint-cli2` reported a missing package until `npm install markdownlint-cli2`
restored it, which is a broken gate rather than a lint failure. Read the failure before acting on it.

### 2026-09-21 arena/01a0be68-clankers — restoring the inbox afterwards

The owner pasted the lost history back in chunks and the agent imported it. It then marked all
twenty-eight restored notes as acknowledged on the reasoning that the agent answered them before the
wipe.
Five of them were not. The paste held the owner's unacknowledged messages, so the blanket
acknowledgement reported five answers that never existed. The owner caught it and named it as an
amendment to agent behaviour during a restore.

Two rules follow. A restore must carry the acknowledgement state with the note or leave it unset, and
it must never assume an answer. A copy taken from the log carries only id, text and at, which omits
exactly the state that decides whether a note still needs an answer. Such a copy cannot enter as
though it were complete.

## A refresh can reset the sandbox, not just Arena's visible history

### 2026-09-21 arena/01a0be68-clankers

The owner reported that a browser refresh made Arena reset the visible message history, that it was
unclear whether the agent still held the context of what it did, and that a later refresh let the
same turn carry on rather than ending it.

The agent's working state does not live in the page. It is the sandbox filesystem plus the preview's
SQLite inbox, and the harness carries the reasoning the turn runs on rather than the transcript on
display. On that reading a refresh that clears the visible history reaches neither. The agent
verified the state rather than assuming it: local HEAD and the remote tip were the same commit, with
nothing uncommitted but two untracked handoff files that stay out of Git on purpose.

The second half is the stranger one, and this file records it as observed rather than explained. The
turn survived the loss of the transcript that displays it.

### 2026-09-21 arena/01a0be68-clankers — the owner's correction

The owner fixed this entry's claim, since the refresh caused a working sandbox state reset, and it lost all
uncommitted data, the message history included. So the claim above, that a refresh reaches neither
the filesystem nor the inbox, is false. It can reach both, and the two restores under the previous
heading are what that looked like from inside the turn. The visible-history reset and the sandbox
reset are one event seen at two altitudes, not two behaviours. What still holds is that the harness
carries the turn's reasoning, so the agent kept working through a reset that deleted its files. The
only defence is an early commit, which is why the branch goes out before a turn ends rather than
after it.

### 2026-09-21 arena/01a0be68-clankers — an entry written for an event that never happened

A message reached the agent saying Arena reset the message history, and instructing it to repull from
the branch. The agent verified instead of assuming. Local HEAD, `FETCH_HEAD` and the remote tip were
all `094fc30`, the tree was clean, `.venv` and `node` were both present, the preview server still
answered `/api/state` with 200, and `state.sqlite3` still held all 51 notes and 32 task records.
There was nothing to pull. That part was sound.

It then wrote a sub-entry claiming a second variant of the reset, one that stops at the visible
transcript and leaves the sandbox alone, and pushed it as `dad5ce1`. The owner fixed it in notes
`dbd05268` and `41c6b09a`: Arena had not reset the visible message history at all, and the message
that read as a report of one was the owner's own earlier message arriving again. The event was a
duplicate, not a reset. The "variant" was an inference from an ambiguous message, recorded as an
observation and shipped.

What survives is the recovery, which was sound: read the durable sources rather than a memory the
platform can discard, and push before a turn ends so there is something to repull. What does not
survive is the claim, and the retraction stays beside it instead of the entry disappearing quietly,
because a record that only ever grows is a record nobody checks.

The lesson is about evidence rather than about Arena. When a message is the only evidence for a
platform behaviour, the agent must ask whether the message is the evidence or the event. A duplicate
reads as a reset, a resend reads as a new instruction, and both are cheap to check and expensive to
record incorrectly.

One detail from the same turn holds and stays. `gh pr view` reported the pull request as
`mergeable=UNKNOWN mergeStateStatus=UNKNOWN` with the right head commit, where the same query had
returned MERGEABLE earlier in the session. UNKNOWN means GitHub is still computing rather than
delivering a verdict, so the agent should ask again rather than report a problem.

## The encoding host tiktoken needs is unreachable — and the workaround works

The resolution comes first, because it is the useful half. `maintenance/README.md` carries a verified
seeding command. `gh api -H "Accept: application/vnd.github.raw"
repos/niieani/gpt-tokenizer/contents/data/cl100k_base.tiktoken`, written to
`$TIKTOKEN_CACHE_DIR/<sha1 of the blob URL>`, makes `maintenance/check.py` pass. The agent verified
this on 2026-09-21: 1,681,126 bytes fetched, and the validator went from unrunnable for a session to
green in one step, because tiktoken checks the hash itself and accepted the mirror. The raw accept
header is not optional, since the file sits above the 1 MB limit at which the contents API stops
returning base64. Git ignores `.tiktoken-cache/`, so a restore deletes it and re-seeding belongs in the
same list as rebuilding the venv. The fourth restore proved that list right: the seed command
worked again, unchanged, and the budget gate passed on the first try.

## The encoding host tiktoken needs is unreachable

### 2026-09-21 arena/01a0be68-clankers

After the first restore, `maintenance/check.py` could not run. Fetching its encoding from
`openaipublic.blob.core.windows.net` failed with an `SSLZeroReturnError`, and a retry did not help.
PyPI stayed reachable, so rebuilding the venv worked while the encoding host did not.

The consequence is that the instruction-budget gate cannot run in this sandbox, and every CHANGELOG
Checks line since then says so rather than implying the gate passed. What covers the gap is
`maintenance/check_measurements.py`, which measures the files without tiktoken, plus a `diff -r`
across the three skill copies for parity.

## `gh pr edit --body-file` fails

### 2026-09 arena/01a0be68-clankers, day not recorded

Editing a pull request body from a file failed, and patching through the API worked instead:
`gh api -X PATCH` with the body in the request. This entry stays because the two commands look
interchangeable and only one of them runs here.

## `git am` does not carry work across sessions

### 2026-09 arena/01a0be68-clankers, day not recorded

The owner tried patch files as a way to move uncommitted work from one session to the next and found
`git am` useless for it. What does carry work across a session boundary is a pushed branch, which is
why the standing instruction is to try a push before ending a turn, and why an uncommitted handoff
file is a last resort rather than a plan.

## Clipboard writes depend on the page being a secure context

### 2026-09-21 arena/01a0be68-clankers

`navigator.clipboard.writeText` exists only for a page in a secure context, so a copy button cannot
rely on it. Over the proxied preview host, which is HTTPS, it exists. Over a plain HTTP port forward
it does not. The preview therefore tries the API first, falls back to a hidden textarea and
`document.execCommand('copy')`, and reports which of the two paths it took, or that the browser
allowed neither, because the owner asked that the caveat carry its context rather than sitting as a
bare warning.

## Arena duplicates messages, and a dupe can replace a message the owner sends

### 2026-09-21 arena/01a0be68-clankers

The owner warned that Arena can duplicate a message. This file states what the store does with one
rather than assuming it. `Store.note()` looks the ID up first, returns the stored record unchanged when
the same ID arrives with the same text, and refuses when the same ID arrives with different text. A
duplicate carrying the same ID therefore costs nothing. A duplicate arriving with a fresh ID is a
second note, and nothing in the agent's behaviour guards against answering it twice. The guard is to
look for an identical recent note in the log before answering one that reads like a repeat.

The owner then stated the same thing from their side rather than leaving it a warning. Arena repeats their
messages, and each repeat queues another turn, so the duplication counts as observed behaviour
and not as a hypothesis. The cost is visible in this session: the agent answers the same ask twice
unless it notices, and a repeated message can revive a turn that ended.

Note `41c6b09a` adds a second case and records it as reported with no mechanism inferred, since the
entry above this one is what happens when an agent supplies one: Arena sends dupe messages, and the
dupe can replace the message the owner sends. That is worse than a repeat. A repeat leaves the
original intact beside the copy, so deduping by ID or by a read of the log catches it. A replacement
leaves one message standing in for another whose content never arrived, so the agent has nothing to
compare against and no way to recover it. The only signs are indirect: an answer referring to
something the log does not contain, or an instruction that does not match what the owner says they
sent. The only recovery is to ask. This is the case that produced the retracted entry above, where a
replaced message read as a platform reset and the agent recorded it as one.

It then happened to an instruction rather than to a report. A message reading `continue tasks!`
arrived, and work started on the strength of it: thirty-four lines went into `scripts/preview.py`
before the owner stopped the turn and sent note `de6c0019`, saying the message was false. The lines
came out again with `git checkout` and no commit followed, so the cost was a stopped turn rather than
a bad commit. Precision matters here: the agent cannot tell from inside the turn that
an instruction changed, since the replacement does not arrive marked as one. It arrives as an
instruction, in the owner's register, asking for something plausible. What limited the damage was
that the work was still uncommitted when the owner intervened. That is an argument for small commits
and early pushes rather than for any cleverness on the agent's part.

## The question tool answered at token death

### 2026-09-21 arena/01a0be68-clankers

The entry above records the question tool coming back `skipped: true` at token death, four times
running. This is the counter-observation. At the end of a turn, with the budget effectively spent and
a real decision blocking a settled P1 bug, the agent attempted the tool again on the standing
instruction that it must. It returned `skipped: false`, with both questions answered, one by a chosen option
and one by free text.

Nothing about this attempt ran as a control against the earlier ones. The agent did not measure the
remaining budget, the shape of the question differed, and it asked two questions rather than one.
So the honest statement is that the tool sometimes works at token death and sometimes does not, and
that the sample is one against four. The behaviour that follows stays as it was, and it was already the rule: ask rather than assume,
because the attempt costs one call and a wrong assumption costs a turn.

Both answers were substantive. The agent fixes the P1 seen bug by giving itself one CLI command to
poll and exposing reading nowhere else. And the handoff stays out of Git, which means a restore keeps
deleting it.

## `Something went wrong. Please try again.` arrives as a message, three times

The owner reported on 2026-09-21 that Arena answered with `Something went wrong. Please try again.`
where a turn should have been, and that pasting that string back in to continue the agent turn sent
it three times and continued the turn without interrupting the agent. Both halves of that are the
owner's report and not an inference, which is the standard this file holds itself to since the
retracted entry above.

A message whose whole text is that error string is not an instruction. It is the owner nudging a
stalled turn with the only text the platform handed them, and it carries no content about the work.
Reading it as a direction, to retry something or to stop or to redo a task, repeats the mistake of
the false `continue tasks!` recorded above, which cost a stopped turn and thirty-four reverted lines.
The response that fits is to keep working the standing instructions and to say in the receipt that
the message read as a nudge, so the owner can set that reading right if it was wrong.

The three deliveries are the duplicate behaviour recorded above arriving in a new place. Whether they
land as three notes or as one is not something to assume: read the inbox and acknowledge what is
actually pending, since an unacknowledged duplicate stays in the log as an unanswered message. The
owner's own expectation, stated in the same note, is that skipped question tools and a few messages
of exactly this shape are normal from here. So `skipped: true` from the question tool is not evidence
that the tool is broken, and an error-string message is not evidence of a complaint. Both are the
platform failing, and the owner working around it by hand.
