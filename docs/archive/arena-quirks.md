# Arena quirks

Behaviours of the Arena.ai hosting environment that cost work, recorded as observed rather than as
documented anywhere upstream. Each entry is a platform behaviour and not a repository defect. Where
a rule already carries the operational instruction, this file links to the rule instead of repeating
it, because the rule is the authoritative copy.

Each entry holds dated observations, newest last, in the form `### YYYY-MM-DD branch`. A date is the
day the observation was made inside the sandbox; where the day was not recorded at the time, the
entry says so rather than guessing. Everything here is traceable to something that happened in a
session: a command that failed, a payload that came back, a file that was missing. Nothing is
inferred from a single reading and presented as a pattern.

The steering inbox that these observations were reported through has itself been wiped twice, so the
notes that first carried them are gone. The durable record of what was changed in response lives in
[CHANGELOG.md](../../CHANGELOG.md), whose Origins lines name the notes by ID.

## GitHub token expiry mid-turn

[rules/ARENA.md](../../rules/ARENA.md) carries the rule: `GH_TOKEN` can die mid-turn with nothing in
the repository changed, `gh auth status` calls it invalid, pushes fail, and `gh auth setup-git` does
not help.

### 2026-09-21 arena/01a0be68-clankers

A push failed after a commit that had changed nothing about authentication. Three consecutive
`git push` attempts returned `fatal: could not read Username for 'https://github.com': terminal
prompts disabled`, and `gh auth status` reported `X github.com: authentication failed — The
github.com token in GH_TOKEN is no longer valid.` The fourth attempt, roughly a minute later and
with nothing done in between but send two acknowledgements through the local preview, succeeded and
pushed the commit.

That contradicts the premise behind the rule's "retry once, then end the turn", which assumes the
next turn is what brings a fresh token. In-turn revival is real, and the number of failures before
it is not fixed: earlier observations on this branch include a turn where the first retry did not
revive it and the push only landed after the turn ended. Both readings are recorded here because
they point at different guidance, and choosing between them is the owner's call rather than mine —
amending `rules/ARENA.md` is not something this file may do.

## The question tool returns skipped at token death

### 2026-09-21 arena/01a0be68-clankers

With the token dead, a question block sent to the owner returned `{"answers": [], "skipped": true}`:
no answers, no error, and no visible sign to the agent of why. The owner's standing instruction is
to attempt the question tool at token death precisely so this could be measured, and this is the
fourth attempt recorded. Every one has come back skipped.

A question block that is actually answered while the token is dead therefore remains untested, and
the experiment stays open. What the four readings do establish is that a skipped block is silent: it
does not end the turn, does not raise, and does not tell the agent whether the owner saw anything.

## Mid-turn sandbox restore

A restore resets the workspace to an earlier snapshot while the turn is still running. The branch
HEAD goes back to the branch base, every gitignored directory is deleted, background processes are
killed, and the preview's SQLite state is removed. File content that the snapshot holds is
preserved, so work that was committed and pushed survives intact on the remote; work that was only
in the working tree survives as uncommitted differences against the base commit.

### 2026-09-21 arena/01a0be68-clankers — first restore

The reset deleted `.venv`, killed the preview server and wiped `reports/arena-preview/state.sqlite3`,
taking 111 steering notes and their receipts with it. Recovery was `git fetch -q origin <branch>`
followed by `git reset --mixed FETCH_HEAD`, which restored HEAD to the pushed tip and left the
working tree alone. The notes were not recoverable, and the CHANGELOG Origins lines are the only
surviving record of them.

### 2026-09-21 arena/01a0be68-clankers — second restore

The same shape, roughly two hours later, with the branch pushed and therefore the code safe: HEAD
was at the base commit `c3c11b3`, `.venv` and the state directory were gone, the server was dead,
and the steering inbox held nothing. Recovery took five steps — fetch and mixed reset to the remote
tip, rebuild the venv and install the pinned `ruff` from `ruff.toml` alongside `markdown-it-py`,
restart the preview server, rebuild the whole task list from what the session still held, and write
the JSON backup that `task-import` reads. The second restore is the reason that backup exists: the
feature had shipped minutes earlier and had not yet been used, so the first wipe of the task list
had to be reconstructed by hand.

A restore also leaves the repository dirtier than it found it in one specific way: running the
Python harness creates `__pycache__` inside the live skill copy, which makes a `diff -r` parity
check report a difference that is not a difference in any tracked file.

### 2026-09-21 arena/01a0be68-clankers — restoring the inbox afterwards

The owner pasted the lost history back in chunks and the agent imported it, then marked all
twenty-eight restored notes as acknowledged on the reasoning that they had been answered before the
wipe. Five of them had not: the paste was of the owner's unacknowledged messages, so the blanket
acknowledgement reported five answers that never existed. The owner caught it and named it as an
amendment to agent behaviour during a restore. What follows from it: a restore has to carry the
acknowledgement state with the note, or leave it unset, and must never assume answered. A copy taken
from the log carries only id, text and at, which omits exactly the state that decides whether a note
still needs an answer, so such a copy cannot be imported as though it were complete.

## A refresh can reset the sandbox, not just Arena's visible history

### 2026-09-21 arena/01a0be68-clankers

The owner reported that a browser refresh made Arena reset the visible message history, that it was
unclear whether the agent still held the context of what had been done, and that a later refresh let
the same turn carry on rather than ending it.

The agent's working state does not live in the page. It is the sandbox filesystem plus the preview's
SQLite inbox, and the reasoning the turn runs on is carried by the harness rather than by the
transcript on display, so a refresh that clears the visible history reaches neither. What was
verified at the time rather than assumed: local HEAD and the remote tip were the same commit, with
nothing uncommitted but two untracked handoff files that are deliberately not committed.

The second half is the stranger one and it is recorded as observed, not explained: the turn survived
the loss of the transcript that displays it.

### 2026-09-21 arena/01a0be68-clankers — the owner's correction

The owner corrected this entry: the refresh was what caused a working sandbox state reset, and it
lost all uncommitted data including the message history. So the claim above, that a refresh reaches
neither the filesystem nor the inbox, is false. It can reach both, and the two restores recorded
under the previous heading are what that looked like from inside the turn. The visible-history reset
and the sandbox reset are one event seen at two altitudes rather than two behaviours. What still
holds is that the turn's reasoning is carried by the harness, so the agent kept working through a
reset that had removed its files, and the only defence is committing early, which is why the branch
gets pushed before a turn ends rather than after it.

### 2026-09-21 arena/01a0be68-clankers — an entry written for an event that never happened

A message reached the agent saying Arena had reset the message history, and instructing it to repull
from the branch. The agent verified instead of assuming: local HEAD, `FETCH_HEAD` and the remote tip
were all `094fc30`, the tree was clean, `.venv` and `node` were both present, the preview server still
answered `/api/state` with 200, and `state.sqlite3` still held all 51 notes and 32 task records. There
was nothing to pull. That part was sound.

It then wrote a sub-entry claiming a second variant of the reset — one that stops at the visible
transcript and leaves the sandbox alone — and pushed it as `dad5ce1`. The owner corrected it in notes
`dbd05268` and `41c6b09a`: Arena had not reset the visible message history at all, and the message
that read as a report of one was their own earlier message arriving again. The event was a duplicate,
not a reset. The "variant" was an inference from an ambiguous message, recorded as an observation and
shipped.

What survives is the recovery, which was correct: read the durable sources rather than a memory the
platform may have discarded, and push before a turn ends so there is something to repull. What does
not survive is the claim, and the retraction stays beside it instead of the entry being quietly
deleted, because a record that only ever grows is a record nobody checks.

The lesson is about evidence rather than about Arena. When the only evidence for a platform behaviour
is a message, the message has to be asked whether it is the evidence or the event. A duplicate reads
as a reset, a resend reads as a new instruction, and both are cheap to confirm and expensive to write
down wrong.

One detail from the same turn that is verified and stays: `gh pr view` reported the pull request as
`mergeable=UNKNOWN mergeStateStatus=UNKNOWN` with the correct head commit, where the same query had
returned MERGEABLE earlier in the session. UNKNOWN is GitHub still computing rather than a verdict,
so it should be re-asked rather than reported as a problem.

## The encoding host tiktoken needs is unreachable — and the workaround works

The resolution is recorded first because it is the useful half: `maintenance/README.md` carries a
verified seeding command. `gh api -H "Accept: application/vnd.github.raw"
repos/niieani/gpt-tokenizer/contents/data/cl100k_base.tiktoken`, written to
`$TIKTOKEN_CACHE_DIR/<sha1 of the blob URL>`, makes `maintenance/check.py` pass. Verified on
2026-09-21: 1,681,126 bytes fetched, and the validator went from unrunnable-for-a-session to green in
one step, because tiktoken checks the hash itself and accepted the mirror. The raw accept header is
not optional — the file is over the 1 MB limit at which the contents API stops returning base64.
`.tiktoken-cache/` is gitignored, so a restore deletes it and re-seeding belongs in the same list as
rebuilding the venv.

## The encoding host tiktoken needs is unreachable

### 2026-09-21 arena/01a0be68-clankers

After the first restore, `maintenance/check.py` could not run: fetching its encoding from
`openaipublic.blob.core.windows.net` failed with an `SSLZeroReturnError`, and retrying did not help.
PyPI stayed reachable, so rebuilding the venv worked while the encoding host did not.

The consequence is that the instruction-budget gate cannot be run in this sandbox, and every
CHANGELOG Checks line since says so rather than implying the gate passed. What covers the gap is
`maintenance/check_measurements.py`, which measures the files without tiktoken, plus a `diff -r`
across the three skill copies for parity.

## `gh pr edit --body-file` fails

### 2026-09 arena/01a0be68-clankers, day not recorded

Editing a pull request body from a file failed, and patching through the API worked instead:
`gh api -X PATCH` with the body in the request. Recorded because the two commands look
interchangeable and only one of them runs here.

## `git am` does not carry work across sessions

### 2026-09 arena/01a0be68-clankers, day not recorded

The owner tried patch files as a way to move uncommitted work from one session to the next and found
`git am` useless for it. What does carry work across a session boundary is a pushed branch, which is
why the standing instruction is to try a push before ending a turn, and why an uncommitted handoff
file is treated as a last resort rather than a plan.

## Clipboard writes depend on the page being a secure context

### 2026-09-21 arena/01a0be68-clankers

`navigator.clipboard.writeText` is only available to a page in a secure context, so a copy button
cannot rely on it: over the proxied preview host, which is HTTPS, it is available, and over a plain
HTTP port forward it is not. The preview therefore tries the API first, falls back to a hidden
textarea and `document.execCommand('copy')`, and reports which of the two paths it used — or that
the browser allowed neither — because the owner asked that the caveat carry its context rather than
sitting as a bare warning.

## Arena duplicates messages, and a dupe can replace what was sent

### 2026-09-21 arena/01a0be68-clankers

The owner warned that Arena might duplicate a message. What the store does with one is verified here
rather than assumed: `Store.note()` looks the ID up first, returns the stored record unchanged when
the same ID arrives with the same text, and refuses when the same ID arrives with different text. A
duplicate carrying the same ID therefore costs nothing. A duplicate arriving with a fresh ID is a
second note, and nothing in the agent's behaviour guards against answering it twice, so the guard is
to look for an identical recent note in the log before answering one that reads like a repeat.

The owner then confirmed it from their side rather than leaving it a warning: Arena likes to repeat
their messages, and each repeat queues another turn, so the duplication is observed behaviour and not
a hypothesis. What it costs is visible in this session — the same ask arriving twice is answered
twice unless the agent notices, and a repeated message can revive a turn that had ended.

Note `41c6b09a` adds a second case, recorded as reported with no mechanism inferred, since the entry
above this one is what happens when an agent supplies one: Arena sends dupe messages, and what would
have been sent can be replaced by the dupe. That is worse than a repeat. A repeat leaves the original
intact beside the copy, so deduping by ID or by reading the log catches it. A replacement leaves one
message standing in for another whose content never arrived, so there is nothing to compare against
and no way to recover it from the agent's side. The only signs are indirect: an answer referring to
something the log does not contain, or an instruction that does not match what the owner says they
sent. The only recovery is to ask. This is the case that produced the retracted entry above, where a
replaced message was read as a platform reset and written down as one.

It has now happened to an instruction rather than to a report. A message reading `continue tasks!`
arrived, and work started on the strength of it: thirty-four lines went into `scripts/preview.py`
before the owner stopped the turn and sent note `de6c0019`, saying the message was false. The lines
were reverted with `git checkout` and nothing was committed, so the cost was a stopped turn rather
than a bad commit. Worth being precise about why: there is no way to tell from inside the turn that
an instruction was replaced, since it does not arrive marked as replaced — it arrives as an
instruction, in the owner's register, asking for something plausible. What limited the damage was
that the work was still uncommitted when the owner intervened, which is an argument for small commits
and for pushing early rather than for any cleverness on the agent's part.

## The question tool answered at token death

### 2026-09-21 arena/01a0be68-clankers

The entry above records the question tool coming back `skipped: true` at token death, four times
running. This is the counter-observation. At the end of a turn, with the budget effectively spent and
a real decision blocking a confirmed P1 bug, the tool was attempted again on the standing instruction
that it must be — and it returned `skipped: false`, with both questions answered, one by a chosen
option and one by free text.

Nothing about this attempt was controlled against the earlier ones. The remaining budget was not
measured, the shape of the question differed, and two questions were asked rather than one. So the
honest statement is that the tool sometimes works at token death and sometimes does not, and that the
sample is one against four. What follows for behaviour is unchanged and was already the rule: ask
rather than assume, because the attempt costs one call and a wrong assumption costs a turn.

Both answers were substantive. The P1 seen bug is to be fixed by giving the agent one CLI command to
poll and exposing reading nowhere else. And the handoff stays out of git, which means a restore will
keep deleting it.

## `Something went wrong. Please try again.` arrives as a message, three times

The owner reported on 2026-09-21 that Arena answered with `Something went wrong. Please try again.`
where a turn should have been, and that pasting that string back in to continue the agent turn sent it
three times and continued the turn without interrupting the agent. Both halves of that are the owner's
report and not an inference, which is the standard this file holds itself to since the retracted entry
above.

A message whose whole text is that error string is not an instruction. It is the owner nudging a
stalled turn with the only text the platform handed them, and it carries no content about the work.
Reading it as a direction — to retry something, to stop, to redo a task — is the same mistake as the
false `continue tasks!` recorded above, which cost a stopped turn and thirty-four reverted lines. The
response that fits is to keep working the standing instructions and to say in the receipt that the
message was read as a nudge, so the owner can correct that reading if it was wrong.

The three deliveries are the duplicate behaviour recorded above arriving in a new place. Whether they
land as three notes or one is not something to assume: read the inbox and ack what is actually
pending, since an unacked duplicate stays in the log as an unanswered message. The owner's own
expectation, stated in the same note, is that skipped question tools and a few messages of exactly
this shape are normal from here. So `skipped: true` from the question tool is not evidence the tool is
broken, and an error-string message is not evidence of a complaint; both are the platform failing and
the owner working around it by hand.
