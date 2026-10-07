# Changelog

The format follows [Keep a Changelog](https://keepachangelog.com/). This repository uses `YYYY-MM-DD` dates as versions instead of [Semantic Versioning](https://semver.org/).

Keep one entry per date and extend the open date. This log has no Unreleased section.

## 2026-10-07

### Changed

#### arena

- **NemoGPT working rules**: The prompt now treats a failed tool call as a signal to change approach. It reaches for a tool instead of memory, names what a newer instruction replaces, and reads harness memory files.
- **NemoGPT memory rule**: Documentation and version answers now require a source the model read. Memory alone no longer counts, and an unreachable source means an unverified answer.
- **Turn-start reads**: The turn-start reread now covers the arena-preview-steering skill with its reference and the arena-proxy skill.
- **Assessment for a described problem**: A described problem or a how-question yields the findings, and the fix waits for a request.
- **stderr count**: A pending count on the Bash-call stderr line now brings the inbox read before the next work step.
- **Close and reopen scope**: The Git clause now also bans asking for or recommending a close or reopen.
- **Push cadence boundary**: The Constitution now pushes verified commits to origin after each task completion, and it never holds verified batches across tasks.
- **One arena skill**: `arena-preview-steering` and `arena-proxy` merge into `arena`. The proxy pages join its SKILL.md, the proxy code moves to `skills/arena/proxy/`, and the turn-read, install, report, gate and workflow pointers name the one skill. Target repositories receive the skill without its proxy directory, so the docker files stay in this repository beside the published image.
- **Read cadence**: The read bullet and the skill reference now say a read never waits for the Bash gate to block. A read that comes only after a blocked call is late.
- **Tooling installs**: The Workspace rules now install dependencies and virtual environments with the background process tool, so an install runs while the turn continues. The arena installer never runs that way.
- **Rule text re-squash**: The live files carry the squash and the refs trees keep the full wording. ARENA.md drops 49 bytes and the arena skill 318. The README measurements follow the smaller files.

### Added

#### userscripts

- **Log texts**: The no-file hint reads `no file selected; launching dialog`, and that path alerts with the card. Its blocked line is gone, a closed picker reads `no file selected;`, and a stale state reads `history does not match`. Arena 1.8.9.
- **Failure lines**: A refused copy read now reads `GET <status> <copy-state url>`, and the missing frame line reads `no preview detected`. The write-failure line keeps its words, and no other line is cut. Arena 1.9.0.
- **Fill and title lines**: The fill lines read `no repo detected`, `no composer detected for <repo>` and `filled composer for <repo>`. The unchanged title line is gone, and a title change still writes its line. Arena 1.8.9.
- **Console log shape**: Both bundles log under the `[NemoUtils]` tag, and the state lines carry short stamp hashes now. The userscripts README lists the new write, quiet tick and force save lines in place of the long stamps and the route words. Arena 1.8.8, ChatGPT 1.3.4.
- **Agent message emoji**: An agent chat message that lands with no turn open now holds the tab title with 💬. A chat switch stays quiet, and the streaming mark keeps its own bubble. Arena 1.9.3.
- **Fetching row emoji**: A Fetching action row now shows the search emoji 🔍, in place of the gear. Arena 1.9.2.
- **Question card emoji**: The tab title shows ❓ while an ask_user card waits for an answer, and the security check still outranks it. Arena 1.9.1.
- **Writing row emoji**: The title emoji now shows the pencil for a Writing action row. The earlier table held only `write`, so `Writing` fell to the gear emoji. Arena 1.8.7.
- **Save cards**: A card in the page corner warns when the page has no save file, with a Choose file button. A force save reports the file it wrote. Arena 1.8.6.
- **Menu press logs**: Every menu press writes its own line under the `menu` module before the command runs. Arena 1.8.1.
- **State comparison logs**: Every comparison in the auto save writes its own line, from the stamp verdict to each pair check. Arena 1.8.1.

#### preview

- **Merge audit**: The merged skill reference and the AGENTS.md pointer name the skill again after the rename (note 27019a6).
- **Gate clause**: The read cadence clause names only the banned readers, `tail`, `head` and `grep`, and it drops `cd` (note bf26910).
- **Skill name**: The merged skill is `arena-skill`, because `arena` collided with ARENA.md. The trees, the installer and the dispatch list carry the new name, and `arena` joins the retired names (note 946a387).
- **Report ID after a send**: The report status line keeps its ID chip after an answer lands. The loaded line and the sent line now agree (note f1630e1).
- **Poll wording**: The unblocked-task poll line now names the still-up task list. It says to continue the task or mark it blocked before the next poll. A turn cannot read it as permission to end (note 12c5a66).
- **Gate hints**: A blocked call names the `tail`, `grep` or `head` commands it ran. A `cd` prefix stays fine, and the count gate still holds a `cd` line. The hook names the bare `arena-preview` form, the proxy route for code-scanning alerts, and the clearing ack for a blocked push.
- **Missing stderr reminder**: A Bash call with no reminder line now reads as a possible sandbox reset. The session runs the reset steps before other work (note 9ba7cfb).
- **Task report links**: A blocked task now names the report it waits on with `--report`. The owner's answer clears the blocked mark, and the link rides the save file.
- **Report form example**: The steering reference now shows a worked form with two groups: a radio group and a checkbox group. Each group carries its own anchored prompt and a custom answer.

### Changed

#### system-prompts

- **NemoGPT answer rule**: The prompt now requires the answer in the reply itself. It restates what a tool result established, and it bans raw tool output or a pointer as the answer.
- **NemoGPT prompt**: The prompt gains autonomy and persistence, a directive-or-inquiry split, harness trust markers, and a sharper permission ladder. Output bans now cover setup phrases and labeled closings. The Core rules and Task routing sections fold into the surviving ones.

#### userscripts

- **Menu modules**: Every Arena menu entry leads with its module, such as `Proxy — host` or `State — save now`. A switch names its state in parentheses, and no entry carries a role word. Arena 1.8.5.
- **State file names**: The auto save names the file after the repository and the branch. A stamped save keeps the stamp and the counts after the branch part. Arena 1.8.1.

#### maintenance

- **Reference parity**: `check_minify.py` no longer requires the shipped references to match the refs copies. The refs tree is the full wording, and the lives carry the squash.

### Removed

#### preview

- **Save control**: The message toolbar drops its save-state button (owner note ffa0cbd). The userscript owns the file path, and the page keeps the copy route.

### Fixed

#### preview

- **Quoted reply text**: The gate read a backtick or `$()` beside a read as work, but single quotes keep both literal in bash. Only double quotes now mark a substitution, so a reply with formatting passes the quiet-line test.
- **Main drift notice**: The gate prints one stderr line when origin/main carries commits the branch lacks. The line lands on a commit or push line, once per shell, and names the replay: fetch origin, rebase over main, then push.
- **Turn end in the header**: A returned poll marks the turn end, and the agent's next call clears the mark. The header drops the long call text at that mark. After three quiet minutes it names the agent gone, instead of counting a call that no longer runs.

#### userscripts

- **State file scope**: The script reuses a remembered file only when its name belongs to the current repository and branch. It refuses a handle outside that scope, and the owner picks the file again. Arena 1.8.2.
- **Blocked save without a file**: With no file set, the automatic save writes nothing. A manual save press keeps the download only where the browser cannot offer a picker. Arena 1.8.3.
- **Deferred picker**: A save that waited on the network never opens the picker, which needs the press itself. It points to the choose entry instead, and the write-failure path does the same. Arena 1.8.4.

## 2026-10-06

### Added

#### userscripts

- **Forced state save**: A third menu entry, `Arena preview state — force save`, writes the state whatever its stamp says and moves the reference to the saved one. Arena 1.8.0.
- **Rules file in the fill**: The fill fetches `rules/ARENA.md` once from the fixed raw URL of this repository. It appends the file under a `here is ARENA.md:` line after the initial message, and a failed fetch writes the plain message. Arena 1.7.0.
- **Global pause**: One entry, `Arena userscript — pause all`, stops every feature where it stands and flips to `Arena userscript — resume all`. The script saves the pause, so a reload keeps it, and the resume restores the features whose switch is ON. Arena 1.6.20.
- **Scattered HTTP timers**: The key watch, the key rotation and the state watch land each call at a random moment in a 15-second band. The DOM ticks keep their steady interval. Arena 1.6.20.
- **Captcha hold**: The prompt fill, the Open Steering click and the proxy key posts wait while the Arena security check shows.
  The tab title keeps the shield, each tab reads its own page, and the held work resumes when the check clears. Arena 1.6.17.
- **Preview state download**: The userscript saves the preview state to one owner-chosen file, checked once a minute.
  It writes only when the newest stamp moves, and an older stamp never overwrites the file.
  The name carries the repo, the branch, the stamp and the record counts. Version 1.4.0.

#### preview

- **Skip poll control**: The Message log toolbar carries a Skip poll button beside the refresh and composer controls.
  A press arms one flag and writes no note. A second press clears the flag, so the owner can take the skip back.
  The agent's poll consumes an armed flag and the wait ends at once. No stale line waits in the log for a later turn to misread.

#### arena

- **PR close and reopen**: The Git section bans closing or reopening a PR, not even to retrigger its checks.
  It lands on the approved proposal in report `proposal-arena-md-conduct-bans`.
- **Local-only tools**: The Constitution bans creating a local-only tool, committing it, or adding a workflow that runs it.
  It lands on the approved proposal in report `proposal-arena-md-conduct-bans-2`.
- **Owner mentions**: The Git section bans mentioning the owner in any public-facing material. The material carries the change, not the people.
  It lands on the approved proposal in report `proposal-arena-md-conduct-bans-2`.

### Changed

#### arena

- **Merge ban**: The Constitution bans the merge outright. No authorization or instruction overrides it.
- **Push cadence**: The Constitution pushes each verified commit or batch at once and never holds green commits.
- **Poll call wording**: The Verification clause now reads "Run every arena-preview poll as 1 Bash call with tool timeout 1800 s and no pipe. A shorter tool timeout is a failed wait, and NEVER a result."
  It lands on the approved proposal in report `proposal-arena-md-conduct-bans-2`.
- **Skill pointer**: ARENA.md names the two Arena skills: `arena-preview-steering` for the inbox, the reports and the gate, and `arena-proxy` for a source the sandbox cannot reach.
  The refs copy carries the full line, and the live and root copies the compressed form. It lands on the approved proposal in report `arena-skill-names-2`.
- **Quoted report ID**: A ctrl-click on a report ID quotes it, whole, into the Messages composer, the tab the box lives in.
  The quote regrows the box and leaves the Markdown preview, so the ID and the text stay complete.
- **Long call header**: While no call reports for three minutes, the header counts the call instead of naming the agent gone.
  Past the 32-minute call cap it names the agent gone, as before.
- **Note ID scope**: The note-ID rule now covers prose, task details, reports and notes by the first seven characters.
  Two notes that share a prefix extend it, and the ack length stays with the skill.

#### house

- **Verbatim trigger**: The house clause names when a copy is verbatim: the user's word, the user's phrase `as is`, or a double-quoted passage.
  A Markdown quote stays context.

#### preview

- **Preview pick control**: The message toolbar carries a save button that picks one file and writes the state into it. The click is the gesture the picker needs, and the name carries the repo, the branch, the stamp and the record counts.
- **State stamp scope**: The state stamp takes the newest change the state carries, receipts included, so a download follows every change. The poll heartbeat stays out.
- **Skip poll on a message**: A note or a report answer clears an armed Skip poll flag, so the wait delivers it. An item that arrived before the press still outranks the skip.
- **Paste line rule**: The composer stages a pasted text file when the paste holds more than 25 lines, counted in lines rather than characters.
- **Poll ceiling**: The poll wait spans 1800 seconds, the bash tool's own maximum.
- **Bash call tally**: The header names the bash calls alone, without the phrase since your last message.
- **Skill cuts**: The preview skill drops the client-side copy-state fallback, the dead `stamp()` helper, the commented write-token lines and the test-only upload wrappers. The minified copies follow, with the assets falling from 49,083 B to 47,757 B and the script from 96,176 B to 95,943 B.

#### gpt-plugins

- **Handoff trigger**: An explicit handoff request activates `handoff` mode, and the trigger holds for ordinary writing.
  Plugin version 1.5.3.

#### system-prompts

- **NEMOGPT refusal scope**: The safety block names the subjects a refusal must not block, and the decline list becomes three narrow guardrails.
  The minors and copyright limits, the wellbeing lines and every tool and formatting line stay.

#### maintenance

- **Plugin frontmatter**: `check_gpt_plugins.py` imports `parse_frontmatter`, `NAME_RE` and `EXPECTED_SKILL_FIELDS` from `check.py` instead of carrying drifted copies of all three.
- **Skill and workflow counts**: `check.py` prints the counts its own validation pass returns instead of walking both trees a second time.
- **Bullet walk**: `check_pr.py` keeps one heading-slice helper, and `_check_none_or_bullets` drops its extra failure line for a section that holds no bullet at all.

#### workflows

- **Release arithmetic**: `baseline` reads a target alone and `version_tag` reads a version alone, so the `tag` and `previous` parameters that only tests exercised go. The tests keep the surviving baseline, tag and version paths.

#### userscripts

- **Rollback guard on the state save**: The auto save remembers the newest note stamp and the newest task stamp of the state it wrote. When one of the two moves backward while the state stamp moves forward, the save refuses the write and keeps the newer file. Arena 1.6.18.
- **Shared page helpers**: The transcript bar, the slug key, the arena URL readers and the label reader live once for every feature. The file falls from 74,024 B to 72,488 B. Arena 1.6.16.
- **Comment trim**: The userscript keeps one comment per feature and drops the rest. The file falls from 87,133 B to 74,024 B. Arena 1.6.15.
- **URL and menu helpers**: Each feature carries one URL test instead of a parser and a wrapper, and the menu entries share one guard. No behavior changes. Arena 1.6.14.
- **Script names**: The two bundles take new manager names: Arena.ai | NemoUtils and ChatGPT.com | NemoUtils. Both scripts add a favicon icon: arena.ai for Arena and chatgpt.com for ChatGPT. Arena 1.6.13, ChatGPT 1.3.3.
- **State tick stamps**: The state tick line carries the server stamp and the last written stamp beside the file name. Arena 1.6.12.
- **Module log tags**: Every `[clankers]` line carries the module in a second bracket, so one filter shows one module. New lines cover each state tick and its route, each title decision with its anchors, the fill failures, and the link download route. Arena 1.6.10, ChatGPT 1.3.1.
- **Title log lines**: Each tab-title change prints one `[clankers]` line: the signal that won, the label behind it and the emoji the title takes. Version 1.6.6.
- **State download route**: The stamped save goes through the manager's own download, which the page download policy cannot block. The page link stays as the fallback. Version 1.6.5.
- **State file name**: The saved name keeps the repository from the saved slug when the header leaves the page. The stamp drops its timezone offset. Version 1.6.4.
- **Security check mark**: The tab title shows a shield while the Arena security check holds the page. The mark outranks the poll row, the speech bubble and the waiting line. Version 1.6.3.
- **Tagged console log**: Both bundles log under one `[clankers]` tag. Feature switches, the prompt fill and the state save land in the devtools console filter. Arena 1.6.0, ChatGPT 1.3.0.
- **Initial message fill**: The composer fill writes the initial-message block under the repo name. It drops the ARENA.md fetch and the `here is ARENA.md:` copy, because the agent reads the rules file from the repository. Version 1.5.0.
- **Waiting line in the title**: A waiting line shows a 16px spinner canvas beside rotating monospace text. The tab title shows ⏳ for that state.
  The words rotate, so the selector anchors on the canvas and the animated ellipsis. Version 1.3.0.

### Fixed

#### userscripts

- **New-chat refill**: The fill memory survived a route away from the composer, so a return to `/agent` after a session route wrote nothing. The memory now leaves with the route, and the same repo fills its new chat. Arena 1.7.1.
- **State scope per repo**: The auto save kept one memory and one file per browser, so two tabs of two sessions wrote one file. The script now scopes the memory, the chosen file and the handle cache by repo and branch. Arena 1.6.21.
- **Waiting-line anchor**: The hourglass needs the spinner canvas and the text block beside it. An action row carries the same canvas as its icon, so a bare canvas no longer reads as a waiting line. Version 1.6.19.
- **State without a picker**: A pick needs a click for the browser gesture. The automatic path writes the stamped download, so the state lands. Version 1.6.9.
- **Quiet state notices**: Every state-file notice is a console line under the `[clankers]` tag, and no popup interrupts the preview. Version 1.6.9.
- **State file names**: The save line names the file the write reached, from the chosen handle. The repo name falls back to the tab title when the bar is gone. Version 1.6.11.
- **Parked security node**: The page keeps the reCAPTCHA node after the widget closes, so the shield stuck. The mark now needs a rendered node, not a present one. Version 1.6.8.
- **Closed security dialog**: Radix keeps the closed dialog in the page, so the shield stuck. The mark now needs an open dialog ancestor. Version 1.6.7.
- **State picker call**: The picker ran in the userscript sandbox, which refuses the call with a TypeError. The call now runs on the page window. Version 1.6.2.

#### skills

- **Kilo path**: The `amending-violations` skill drops the directory path in the persistence item. The rule stays: re-inject the rules on long sessions and after compaction.

#### userscripts

- **State log lines**: The state download logs each silent path. A missing frame, a bad copy-state status, the plan, the missing handle, a closed picker and the stamped download each print a line. Version 1.6.1.
- **Fill loop**: The prompt fill rewrote the composer on every DOM mutation when the editor changed the text, which made the page unresponsive. It writes once per repo per page now.

#### preview

- **Gateway error line**: A non-JSON error body keeps the connection line short. An HTML page becomes its HTTP status, and plain text folds to 120 characters.
- **Message table spacing**: A table inside a message takes tight rows, so a three-column table no longer eats the Messages tab.
- **Dropped upload**: A note upload the network drops replays once under the same note ID, so a lost response does not lose the send.
  The staged chips now carry each file's size, and the failure line names the combined upload.


## 2026-10-04

### Changed

#### arena

- **One GitHub route**: The proxy replaces `/v1/github` and `/v1/logs` with `/v1/gh`.
  The path parameter carries the real `api.github.com` path and its own query, and a run-log path answers the text tail.
- **Push rule**: The push bullet measures the branch by tree, not commit count. A branch whose tree matches `origin/main` never pushes, even when it shows commits ahead.

### Changed

#### workflows

- **Diff evidence**: The Gemini release runner keeps one diff per commit. One base-to-target diff cuts the input tokens by 14% to 54%, and the owner keeps the per-commit diffs for attribution.
- **Gemini token packing**: The runner puts a commit message and its diff in one evidence item. It counts every payload with the Count Tokens API, and an oversized list halves until every part fits the 230,000-token ceiling. A model that answers or spends its tokens cools down for 60 seconds plus 5 seconds of safety.
  The next request starts at the highest ready rung.

#### skills

- **Amendment skill trimmed**: `amending-violations` drops the five-step process and the five-point format. It keeps the system-prompt guidelines and the output table, with one row per changed line.
- **Amendment skill frame**: The output format also names the status line, the citation and the decision list. The model answers in the proposal form.
- **Process tool line**: The steering skill gives the long-lived process tool one job. That tool MUST host `serve` alone, and every other command runs as a one-shot shell call.
- **Key command line**: The steering skill names `arena-preview key` for a call that needs the recorded key. The command prints the key, the host and the stamp.
- **Copy receipt**: The copy-state receipt reads `Copied state as NDJSON.` and drops the record counts.
- **Downloads fallback**: A download tries direct access, then AllOrigins, then CodeTabs with no opt-in. The per-URL proxy toggle leaves the page.
- **Key line in the composer**: The agent key and host leave the Downloads tab for the composer footer. The line prints the first seven key characters in monospace.

### Changed

#### house

- **Prose gate**: `maintenance/check.py` runs `maintenance/lint_prose.py`. The gate covers the code comments under `maintenance` and `rules` and the covered documents. The changelog bullet cap stays at three sentences.
- **Runner prep**: One composite action holds the Python setup, the pip cache and the Node setup. The three `ci.yml` jobs call it, so the block lives in one file.
- **Clause gate**: The clause gate names system prompts beside rules, skills and workflows. The verbatim pass stays.
- **Waiver limit**: The waiver bullet names its limit: it never covers a clause change. Every clause change waits for the approved report.

### Added

#### preview
- **Report ID on show**: The Reports tab prints the loaded report's ID beside the status line.
  A click copies it, and a ctrl-click quotes it to the composer.

- **Key expiry notice**: A recorded key older than the rotation window posts one quiet note.
  The note points at `arena-preview key` and names no key. A new post overwrites the record by itself.
- **Quiet dismissal**: The report-dismissal note posts quiet. It informs a read without waking a poll.
- **Terse status lines**: The downloads, reports, tasks and composer lines lose their extra prose.
  The files cap line opens with the size, and the key line joins the Enter to send row with only the key characters in monospace.
- **Download removal**: The Downloads tab carries a ✕ that removes a row and the bytes it staged. The first click arms it for eight seconds, and the confirmation names the URL.
- **Dead surfaces removed**: The preview drops `/api/probe`, the legacy `/api/uploads` pair, `parse_note_attachments` and the CLI `--pretty` flag. Nothing called them. Attachments ride the note route.
- **Copy state carries reports**: The copy button fetches `/api/report-sources`, so the clipboard carries the report sources with the notes, tasks and answers. A restore rebuilds the report pages from either the copy or the save file.

#### skills

- **Push guard**: The push checkpoint refuses a push whose HEAD tree equals `origin/main`. Such a push leaves the pull request without a diff, and GitHub closes it.
- **Poll return**: A poll that returns for an unblocked task names the task on stderr, so the turn continues it.
- **Key command**: `arena-preview key` prints the recorded agent key, host and stamp. A later session recovers the key after the key note leaves the pending list.
- **Route pointer in the note**: The key note names `/v1/ping` as the route list. It names `skills/arena-proxy` as the map, so a session without the skill guesses no route. Version 1.2.8.
- **Key recovery line**: The 401 line in the proxy skill names `arena-preview key` beside the inbox read, and the preview reference table carries the row.
- **Post key now**: A fourth proxy menu command posts the key the script holds to the preview. It rotates nothing, and a missing key fetches the live one. Version 1.2.7.
- **Rotate log**: The rotation line prints the new agent key, as the start line does. The owner reads the key from the container log when no preview is at hand.
- **Gate threshold**: The read gate blocks after ten calls while notes wait. The owner raised the number from three.
- **Read exemption**: The gate exempts a command line only when every command on it is an inbox call or an inert prefix. A read beside work no longer exempts the work, so the work meets the gate. Quoted text is an argument, so a reply may span lines.
- **Ack line in the gate message**: The blocked line names a bare `arena-preview ack <id>` call with its `--reply` and `--note` flags. Earlier the line named only the read.
  A redirect that sends the read to `/dev/null` ends the exemption too. `preview.py inbox-line` answers the question and `maintenance/test_preview_gate.py` covers it.
- **Report sources in the save file**: `saved-state.ndjson` carries each report's markdown, and `import-state` rebuilds the report pages from it.
- **Copy state from one route**: `/api/copy-state` returns the save-file text and its counts. The copy button copies that text in one fetch. The cached assembly stays as the fallback.
- **Dismissal note**: A report the owner unpublishes from the page writes one inbox note that names it. The CLI form stays silent.
- **Wall-of-text ban**: The terse line bans the wall of text and padded prose. It points at the list and the table as the shorter form.
- **No working directory needed**: A CLI call finds the repository from the wrapper's own path. It runs from any directory and needs no `cd`.
- **Gate message names the bare call**: The blocked gate prints that the only call that passes is a bare `arena-preview read`. Work beside the read ends the exemption.
- **Stale import guard**: `import-state` reads the newest message stamp in the payload and in the database. It refuses the import when the database is fresher, and names both stamps. `--force` overrides the guard and the receipt says `forced`.
- **Gate mark rule**: The steering reference bans the `_arena_preview_platform` mark. NEVER set or export it. NEVER bypass a blocked gate.
  The owner approved the line.
- **Amendment skill**: `skills/amending-violations` amends the NEMOGPT prompt after a violation. The skill file holds the system-prompt guidelines and the model's five-point amendment format, and the prompt points at the skill by name.

#### arena

- **Skill reads**: A skill's first use in a session needs a full read of its SKILL.md and every Markdown reference it names. A partial read does not count.
- **Full reads**: The reread bullet names full reads: a partial read, such as head, tail or a grep excerpt, does not count. The line also names the skill reference as the home of the gate and read cadence mechanics.
- **Idle dot**: Every CLI call stamps `agent_seen_at`. The header turns amber with `No agent since <time>` after three quiet minutes, so a preview left open after a turn shows no agent instead of a live connection.
- **Fetch page limits**: `docs/archive/arena-quirks.md` records the measured 8,000-character chunk, the two-chunk split above it, the 63-chunk RFC read and the 100-call lower bound.
- **Note IDs in prose**: ARENA.md names the first seven characters of a note ID as the prose reference, never the sequence number. The steering skill already carries the rule.
- **Proposal skeleton**: The amendment clause in the root `AGENTS.md` fixes the proposal opening lines, names the `Citation:` line, and puts the decision list under each table. This clause landed on the owner's approval.
- **Tool claim sources**: The NEMOGPT prompt holds a second verification line. Search official documentation before a claim about a tool or an interface, and mark the advice unverified when verification is impossible. This line landed on the owner's approval.
  The owner rejected the first long-answer line, so a compact answer shape is a separate proposal.
- **Re-read on rebase**: A rebase onto `main`, or a new `main` change to a rule or skill file, forces a full re-read.
  Every affected file comes before the next work step.

### Fixed

#### preview
- **Quiet notes out of the log**: A quiet note stays in the cached state and the copy file.
  The log and its tally show the owner-facing messages only.

- **Poll header**: A live poll heartbeat keeps the wait text in the header. Only an aged stamp with no poll reads as `No agent since <time>`.
- **Report drafts**: An edit in a report form writes the answers at once, so a reload keeps the chosen options. A submit still replaces the record with the server's stamp.
- **Report custom slot**: The field rule puts the custom slot inside its option group, in `REFERENCE.md` and `SKILL.md`.
  A standalone `Answer: ___` line stays a question of its own.

#### userscripts

- **Key posts keep the preview fresh**: The userscript posts the held key when the preview frame appears and once a minute after that.
  A refresh and a preview enabled later both land, and the preview stamp keeps moving. Version 1.2.9.
- **Tab title turn end**: The title reverted to the Arena default when a turn ended. The title now keeps the repository name, and only the emoji clears. Version 1.2.6.

#### workflows

- **Classifier prompt**: The version request uses the version prompt. The release phase stamp overrode the caller, so every classification answered with release notes.
- **Chunk plan**: A packed round lists each chunk and its token count before the requests run.
- **Classification retry**: An invalid classification answer retries on the next rung, one try per rung, and stops when the rungs run out.
- **Single reduction**: The proposal run summarizes the evidence once. The version request and the release body read the same summaries, so a big release skips the second chunk pass.
- **Summary hand-off**: A ready summary item keeps its text. Unpacking it like a pair sent the literal keys to the version request, so the classifier answered review.
- **Step log**: Every Count Tokens call prints, and a split names the two commits it falls between. The packing steps stay visible during a long round.
- **Uncapped combine**: The final summarization request carries no output cap, because its payload is already compact. The chunk rounds keep the 8,192-token cap.

## 2026-10-03

### Added

#### arena

- **Sandbox reach**: `docs/archive/arena-quirks.md` records the reachable hosts, the readable endpoints and the refused security endpoints of a GitHub session.
- **Token limit**: A user personal access token cannot reach the sandbox, because the egress proxy replaces the Authorization header.
- **Preview fetch proxy**: The preview can fetch a blocked public URL through the owner's browser, and the archive entry lists its limits.
- **Fetch tool reach**: `fetch_page` reads public text on hosts that the sandbox egress filter blocks. It cannot carry a token, and it cannot read binary bytes.
- **Turn-start reads**: ARENA.md now requires a turn-start reread of itself and every AGENTS.md in the repository, and again after a compaction or summary. This clause landed on the owner's approval. The refs copy carries the full line, and the live and root copies carry the compressed form.
- **Proxy pointer**: The ARENA.md Use section now points to the `arena-proxy` skill for a task that needs a source the sandbox cannot reach. The refs copy carries the full line and the live and root copies the compressed form.
- **Skill content**: Every skill now holds only what an agent needs to use it. Design decisions, background, rationale and history go to this changelog or the archive, as the root AGENTS.md and the skills guide both state.
- **Skill audit**: The `arena-proxy` and `squash` skills drop the owner setup steps and the rationale clauses an agent cannot act on. The vendored `web-interface-guidelines` skill stays verbatim.
- **Interface verification**: The NemoGPT search rule now names a menu path and a setting beside the API and platform cases. The live copy keeps the same line, and the budget row follows.

#### skills

- **Arena proxy**: A new first-party skill pairs the `fetch_page` tool with an owner-run backend that holds a provider credential. The backend answers `/v1/ping`, `/v1/github`, and `/v1/logs`, checks a generated agent key, and removes the query string from its log lines. `maintenance/test_arena_proxy.py` covers auth, forwarding, the log tail, and key redaction.
- **Module split**: The backend becomes an `arena_proxy` package of five modules with a thin `server.py` launcher. `/v1/health` answers without a key. `/v1/fetch` returns text, base64, base85 or gzip, and stages large bytes for chunked reads.
  `/v1/llm` queues an OpenAI-compatible job and returns its result on a poll. Staged bytes and jobs expire after one hour. The backend accepts loopback HTTP for a local service.
- **Container**: `skills/arena-proxy/Dockerfile` builds a `python:3.12-alpine` image with no build step, runs as a non-root user, and keeps secrets in the environment.
- **Exposure**: The skill records Cloudflare Tunnel and Tailscale Funnel as the HTTPS options, with the agent key as the only gate. The shipped scripts stay readable, not minified, because the owner hosts and debugs them.
- **Fetch guard**: The fetch route refuses private and link-local addresses, the cloud metadata address, single-label names, and internal suffixes. Public HTTPS and the owner's loopback stay open. `maintenance/test_arena_proxy.py` covers the blocked and allowed shapes.
- **Rename**: The skill, its Python package and its budget row become `arena-proxy`, and the environment prefix becomes `ARENA_PROXY_`.
- **Plugin release**: `release-gpt-plugins.yml` publishes `gpt-plugins.zip` as a GitHub Release on the tag `gpt-plugins-v<version>` from `plugin.json`, and the workflow contract gains that file.
- **CodeQL scope**: `.github/codeql/codeql-config.yml` excludes `py/full-ssrf`, whose reports describe the fetch design. The `allowed_url` guard and its tests carry the control. An inline `# codeql[py/full-ssrf]` comment came first, and the check ignored it.
- **Core rules in the prompt**: The NemoGPT prompt gains a Core rules section with the operative repository rules. It covers controlled English, terseness, ambiguity, YAGNI, verification, and unasked pushes, on owner direction.
- **Proxy key rotation**: the server makes a new random key on every start and prints it once. It never reads the key from the environment, on owner direction.
- **Image publish**: `publish-arena-proxy-image.yml` builds `skills/arena-proxy/Dockerfile` for amd64 and arm64, and pushes `ghcr.io/nemoe7/arena-proxy` under the one mutable tag `latest`. The skill ships a compose file with a Tailscale sidecar and the funnel serve config.
- **Install cadence**: ARENA.md now requires the preview installer from the repository root before activation, never a manual copy. It holds in every session, the ntfy and no-steering cases included. It lands in `rules/refs/ARENA.md`, `rules/ARENA.md` and the root copy, on the approved proposal in report `install-cadence-proposal`.
  The duplicate-message check found the rule already present at refs line 112, so no second clause landed.
- **Agent key panel**: The preview serves `POST /api/key`, which stores the key and the proxy host the userscript holds. The Downloads tab shows both with the arrival time, and `/api/state` carries them.

### Changed

#### skills

- **Key recovery**: The proxy skill states one inbox read after a 401, then a retry with the newest key note.

#### userscripts

- **Rotation countdown and quiet notes**: The bundle saves the rotation due time. A reload therefore resumes the countdown instead of waiting a fresh 15 minutes. A second tab that asks early reads the key's age and waits.
  The key note is quiet, so it wakes no poll and stops no command. The script posts the key it holds to the preview. Version 1.2.1.
- **Key watch**: The bundle asks the key route every minute. A container restart therefore reaches the agent inside a minute, not at the next rotation. A changed key swaps the composer line, posts one quiet note, and shows in the Downloads panel.
  Version 1.2.2.
- **Connect tag**: The bundle carries `@connect arena.site`, so the userscript manager stops asking the owner about each new preview host. The rotation call moves to `fetch`, which keeps the owner's proxy host out of the file. Version 1.2.5.
- **Preview carries the proxy**: The composer keeps the rules line only. The script posts the proxy host with the key, and the quiet note names both.

#### system-prompts

- **NemoGPT prompt revision**: The operator's tighter draft replaces the long prompt in `system-prompts/refs/NEMOGPT.md` and its live copy. The audit against `GUIDELINES.md` added the date line, a concrete refusal bar, exact banned openers, a restatement clause, and two worked examples. Confidentiality gives way to prompt transparency, per the draft.
- **Live squash**: The live `system-prompts/NEMOGPT.md` copy compresses from its refs source to 12,578 characters and 2,428 `cl100k_base` tokens, with every section and rule kept.
- **Prompt budget**: The root instruction-budgets table and `maintenance/check.py` now measure the live prompt, so its size is a recorded budget. `system-prompts/README.md` states the compressed-live convention.
- **Search verification**: The NemoGPT prompt requires a check of the current official documentation before advice on a specific API, tool, or platform behavior. When no source is reachable, the answer states the assumption and marks the advice unverified. Both copies carry the line.

#### house

- **Guidelines citation**: The amendment clause in the root `AGENTS.md` now requires the proposal to cite at least one section of `rules/refs/GUIDELINES.md`. The required read therefore leaves a trace. Owner direction.

## 2026-10-02

### Added

#### workflows

- **Security workflows**: `codeql.yml` analyzes Python, JavaScript and the workflow YAML. `dependency-review.yml` fails a high or critical advisory. `secret-scan.yml` scans the pushed commits and the full history on a schedule.
- **Workflow lint**: `workflow-security.yml` runs actionlint, zizmor and the workflow set gate on every workflow change, with a weekly run.
- **Pull request gate**: `pr-check.yml` checks each commit and the pull request title against the Conventional Commit rules that `maintenance/check_pr.py` inlines from `rules/COMMIT-SPEC.txt`. It checks the body heading order and runs the vendored Simplified Technical English linter on it.
- **Validators**: `maintenance/check_pr.py`, `maintenance/check_workflows.py` and their test modules hold the pull request contract and the workflow set contract. A pull request records its rules in `.github/pull_request_template.md`.

#### preview

- **Task steps**: The `task` command refuses a detail line over 120 characters. A passed block splits on its line breaks, so details are the steps taken, one per line.
- **Report dates**: The report status line shows one date stamp. A report never republished shows its publish time, and the first republish swaps the same place to the edit time. The store keeps the first `published_at` for each id.
- **Message log call count**: The message log header names the bash calls since the owner's last message, beside the saved message count. The server state payload carries the counter the gate already keeps.

#### userscripts

- **Chat speech bubble**: The tab title shows a speech bubble while the agent speaks in regular chat. Streaming `data-agent-word` spans under an open turn raise the bubble, and a settled message drops it after the hold. Version 1.1.34.

#### arena

- **Code scanning read**: A Verification line orders the agent to read the open code scanning alerts before every push and address each. It lands in `rules/refs/ARENA.md`, `rules/ARENA.md` and the byte-identical root copy, on the approved proposal in report `arena-codeql-rule-2`.

### Changed

#### arena

- **Verdict line**: The push-check rule now requires reading the passed or failed line of every gate. A pipe that hides the verdict counts as skipping the gate, after one local sweep let a hard STE violation ride to CI. The rule lands in `rules/refs/ARENA.md`, `rules/ARENA.md` and the byte-identical root copy.
- **Commit history**: Four rules hold the pull request history small. Minimize it and keep commits intentional. Never commit intermediate fixes or debugging.
  Keep unrelated changes separate, with no merge commits. Review the final list and diff before pushing. The rules land in `rules/refs/ARENA.md`, `rules/ARENA.md` and the root copy.

#### gpt-plugins

- **Handoff verification**: The `gpt-handoff` output tells the receiving agent to check material claims before applying them. The collection version steps to `1.5.1`.
- **Handoff disclaimer scope**: The output disclaimer now names both output forms, handoff and audit. Independent verification of material claims stays a condition before the receiving agent applies either output. The output also carries every source and reference the verification needs: relative paths inside the repository, direct links outside it, and nothing else.
  The plugin version is `1.5.2`.

#### house

- **Changelog headings**: The house rule states the date heading form `## YYYY-MM-DD`. The bracket and the repeated date go, and the 24 headings follow.

#### maintenance

- **Commit scope areas**: The pull request gate no longer binds a commit scope to a path list, and the `SCOPE_AREAS` map goes. One house commit carries a rule file, its ledger entry and its measurement row, so a bound scope rejected a compliant commit.
- **Changelog scope**: `changelog` leaves the allowed scope list. Its area was one file, so it could never carry a ledger entry beside the change.
- **Scope list**: The gate takes any scope in a commit subject and a pull request title, and the frozen 39-name list goes.
- **Body headings**: The `Breaking Changes` and `Related` headings may stay out of a pull request body when neither holds content. `Summary`, `Changes` and `Validation` stay required and in order.
- **Placeholder rule**: Angle brackets inside a fenced code block pass the pull request body gate. Every other line keeps the ban, on the owner answer to the `pr-constraints` report.
- **Body heading order**: A kept `Related` section no longer needs an empty `Breaking Changes` heading in front of it. Either of the last two headings may stay out on its own, and the kept ones follow the locked order.
- **Breaking cross-check**: A commit that carries the breaking marker now needs a `Breaking Changes` section that lists something. The reverse direction stays unchecked, on the owner answer to the `pr-constraints` report.
- **Empty optional sections**: A `Breaking Changes` or `Related` section that holds exactly `None` fails the body gate and names the fix: omit the heading. The pull request template no longer pre-fills the two sections, on owner note `a892211`.

#### workflows

- **CI split**: `validate.yml` becomes `ci.yml`, named CI, with independent `quality`, `tests` and `preview-tests` jobs. It runs on pull requests and after every push to `main`.
- **Artifacts merge**: `package-gpt-plugins.yml` and `publish-clankers-rules.yml` become `artifacts.yml`, named Artifacts. A `changes` job detects the affected path group, and two jobs keep the packaging and publishing behavior.
- **Distribution triggers**: `distribute.yml` runs on a relevant `main` change, on a daily schedule at 03:17 UTC, and on manual dispatch. The two jobs and the two override inputs stay.

#### preview

- **Gate threshold**: The debug gate's call tally now blocks at 20 bash calls since the owner's last message while the inbox stays pending. The count drops from 50 on owner note `9c5b08b`.
- **Poll span**: The poll wait always runs its 900 second span. Only a new message or an unblocked task breaks it, and a task that appears mid-wait breaks it too, printing the task list. Owner notes `04ca4e0` and `359c909`.
- **Poll restart command**: The poll error names the script on PATH and the recorded port, so the agent restarts the server as written.
- **PR check reminder**: A rotating tail line covers a pull request whose checks never ran: rebase onto `main` first.
- **Push gate**: A `git push` blocks while a note or answer awaits an ack, whatever the call count. The count threshold still holds every other command.
- **Gate trap message**: The blocked command gate prints ``READ INBOX NOW WITH `arena-preview read`, THEN ACK EVERY NOTE WITH `arena-preview ack <id>``. The old line named read only, while a read but unacked note gates commands too.
- **Path reminder**: The rotating tails gain one entry: don't use the full script path, run `arena-preview` instead. The installer puts that command on PATH.
- **PATH block**: The installer PATH entry resolved the repo root when the profile sourced, so a shell outside the checkout missed the command. The block pins the root at install time through a placeholder the installer substitutes, in all three install.sh copies.

#### userscripts

- **Prompt fill screenshot line**: The filled prompt states `Expect screenshots to be sent via the steering channel.` after the read line, so a vision session knows where the images arrive. The Arena bundle moves to `1.1.36`.

### Fixed

#### workflows

- **Preview tests**: The `preview-tests` job installs `pytest`, which `maintenance/check_minify.py` runs on the minified runtime. The workflow contract check now refuses a job that runs the script without the install.
- **Shell lint**: actionlint reports shellcheck findings. The plugin validation step takes its base commit through the environment. Four scripts in `distribute.yml` carry a scoped disable directive.
  No command changes.

#### maintenance

- **Subject wording rule**: The rule read an imperative verb that ends in `d` or `s` as an inflection, so it rejected `add` and `hold`. The rule and its exception list go.
- **Comment end tag**: The body rule matched `-->` only, so `--!>` passed. The pattern takes both forms, and a test holds the second one.

#### preview

- **PR checks reminder**: A rotating tail line names the `gh pr checks` command for pull request checks.
- **Gate chain**: The count gate leaves a shell quiet when its command line holds an inbox read. A chain that starts with `cd` reaches the read, and the push rule still runs for every push. The installer carries the same guard into the source, live and installed copies.
- **Report answer seen dot**: The submission dot compared clipped stamps with a strict greater check. An answer the agent read inside the answer's own second kept the sent dot. The dot now takes an equal stamp as seen.
  The refs app.js and both minified copies change.
- **Dead list regexes**: `REPORT_LIST_TAG` and `REPORT_LIST_TAGS` had no callers, and the nested quantifier of the second tripped a redos alert. Both go with their two stale comments.
- **Content-Disposition file name**: `reply()` put the raw file name into the header, and a CR or LF in a name splits the response. It now replaces CR, LF and double quote with `_` before the header goes out.
- **Selector equality**: Two field-label lookups built attribute selectors with only quotes escaped. One `byDataAttr` helper now compares attribute values, and the incomplete-sanitization findings go.

#### userscripts

- **Tab title edit row**: The live anchor matched `svg.animate-pulse` only. A collapsed edit row pulses its label span, so the title never read as editing. The anchor takes any pulsing element.
  The label reader falls back to the pulsing element text. A class-aware checks case guards both tag forms. Version 1.1.31.
- **Prompt fill single write**: The fill wrote the plain line first and the file second. The second write put a line break after `AGENTS.md`. The editor reads that break as the end of a bare domain and links the name.
  The fill now waits for the one fetch of `rules/ARENA.md` to settle and writes the composer once per page. A failed fetch writes the plain prompt. Version 1.1.35.
- **Prompt fill trailing space**: The read line ends with a space after `AGENTS.md`, on owner direction. Without a character between the name and the line break, the editor links the name. Version 1.1.37.
- **Prompt fill full stop**: The trailing space did not hold, and the editor still linked the name. A full stop after `AGENTS.md` stops the link, on the owner's live test. Version 1.1.38.
- **Tab title group bound**: The read and edit group fallback waited on a button whose aria-label reads exactly Stop generating. One label drift therefore silenced every read and write in the title. The fallback now bounds to the newest transcript message, which a new user message clears without any button.
  Version 1.1.32.
- **Tab title turn end**: The group fallback lost the stop bound at 1.1.32. A finished group label then kept the title alive after the turn ended. The fallback now bounds by a loose stop word match on the button aria-label.
  The whole title reverts when no row, no held emoji and no stop control remain. Version 1.1.33.

#### userscripts

- **Poll detection**: The tab title matches a poll call as the script name followed by `poll`. A `polling` or `polls` word in another command no longer shows the waiting emoji. The Arena bundle moves to `1.1.30`.

## 2026-10-01

### Added

#### system-prompts

- **New directory**: `system-prompts/` holds a refs baseline and a live copy. It opens with the NemoGPT prompt and the vendored writing guidelines.

#### git

- **Commit types**: The specification adds `ci` and `revert`. The installer reads the allowed types from `rules/COMMIT-SPEC.txt`.

### Changed

#### system-prompts

- **Live squash**: The live NemoGPT copy compresses from the refs, 34,952 to 28,380 bytes, with every section and rule kept. The squash also removes a duplicated tail fragment that the fourteen additions left behind.

#### rules

- **First read cadence**: ARENA.md orders the first inbox read after the visibility answer. The live and root mirrors follow, and the exceptions file records the growth.
- **Installed mirror updates**: `AGENTS.md` allows task-related source changes in this repository's installed copies without separate user approval.
- **Question batches**: `ARENA.md` applies question labels and totals only to `ask_user` batches.
- **Changelog convention**: The shared AGENTS and ARENA rules use Keep a Changelog unless the repository uses another format. This log uses dates as versions, with change types and domain groups, and no Unreleased section.
- **Repository type**: `AGENTS.md` identifies the rules/skills/workflows repository and its maintenance build tooling and tests.
- **Empty rebase push**: The push clause says NEVER push after a rebase that leaves no commits ahead of `main`. The live and root copies follow.

#### workflows

- **Gemini release sections**: The proposal removes optional sections with no text. The approval check rejects empty sections. The Summary section stays required.
- **Gemini release reference**: The draft receives previous published release notes as style-only context. The prompt forbids their use as evidence. Version classification does not receive them.
- **Gemini retry diagnostics**: The workflow reports model HTTP status and sanitized API errors, with immediate console flush. A draft that fails template validation receives one same-model correction attempt.

#### git

- **Commit-message hook**: The preview installer replaces the local hook with a validator for `rules/COMMIT-SPEC.txt`. It checks the subject format, rejects a body, and adds no co-author trailer.

#### userscripts

- **Transcript trim**: The menu takes one global row limit. The trim removes oldest rows and action containers from trimmed or empty roots while keeping message roots. The Arena bundle moves to `1.1.23`.
- **Transcript trim settle**: The settle check also rejects a pending question widget, so the trim waits for the answer. The Arena bundle moves to `1.1.24`.
- **Prompt fill URL**: The composer match strips trailing slashes, so `/agent/` fills like `/agent`. The Arena bundle moves to `1.1.25`.
- **Tab title read groups**: The newest group label supplies the emoji while a turn runs, because a read or edit group never pulses. The bundle moves to `1.1.26`.
- **Prompt fill ARENA.md**: The fill appends `rules/ARENA.md` fetched from the fixed raw URL of this repository. The Arena bundle moves to `1.1.28`.

#### preview

- **Gate prompt**: The blocked bash gate prints `READ INBOX NOW WITH arena-preview read`. The gate test asserts the line and the exit code.
- **Trap reminders**: The debug trap prints one task-list reminder per shell on `git commit`, `git push`, and `gh pr checks`. The copy check asserts the count.
- **Composer paste**: A text paste over 2,000 characters stages one attachment named `<lines>-pasted-lines-<epoch>.txt` and leaves the composer text alone. The client test covers both paths.
- **Missing inbox error**: The error names the installer, the `start_process` tool with the serve command, and the read command. It also names a possible sandbox reset. A test asserts the five fragments.
- **Blocked tasks**: A task carries a `blocked` mark that `--blocked` and `--unblocked` set. A poll returns at once with the task list while an upcoming task stays unblocked.
- **Reference parity**: A minify check compares the shipped `REFERENCE.md` against the refs baseline. The two copies must stay byte-identical.
- **Blocked finish**: A task that carries the blocked mark refuses `--status finished`. The error names `--unblocked`.
- **Blocked color**: A blocked task title reads in `var(--muted)`, so the queue shows what the agent can act on. Both themes share the one variable.
- **Sized report images**: A report image takes a size the agent sets, as `![alt](src =320x200)`. A refused source stays text, and a wide image shrinks to the panel.
- **Setup step 4**: The skill orders the first read after the visibility answer, in step with the ARENA.md line.

#### maintenance

- **CSS minifier**: The build uses `clean-css@5.3.3` through a Node runner instead of `clean-css-cli`. The lockfile removes `glob` and `inflight`. Level-2 optimization, relative URLs, warning rejection and shipped CSS bytes stay unchanged.

### Removed

#### preview

- **State directory**: The CLI drops `--state-dir`. It reads `ARENA_PREVIEW_STATE_DIR` when the environment names it, and the repository `arena-state` otherwise. The tests set the variable.
- **Two cuts**: The CLI drops the unused save-path flag. One holdout helper now serves both the list markup and the sized images.
- **Task flags**: The CLI drops the task-id and task-title flags. The two positional arguments do the same work.

### Fixed

#### git

- **Portable hook**: The hook carries its own type list and 72-character limit, so a checkout without `rules/` still checks the message. A test pins both to `rules/COMMIT-SPEC.txt`.

#### userscripts

- **Tab title labels**: The group selector drops its button parent. The label falls back to the row's action span, so `Edit`, `Write` and `Explored` map. The bundle moves to `1.1.27`.
- **Transcript trim redraw**: The trim skips a root the document dropped, and a root whose row nodes sit detached. The redraw after a Stop generating click then keeps the transcript. The Arena bundle moves to `1.1.29`.

#### preview

- **Profile blocks**: The installer rewrites all four `~/.bash_profile` blocks on every run. A stale block from an older release no longer survives. A minify check proves it.
- **Agent call gate**: The gate blocks only a shell that runs a command string, so a launcher-script shell keeps the process it hosts. The earlier command-text guard missed a command that preceded the server start in the same shell.
- **Platform probe shells**: The gate marks Arena's own probe and bookkeeping shells from their command line and skips them. An exit 130 in one reads as a dead preview or sandbox, while the server stays up.
- **Image policy**: The page policy adds an image directive. The policy starts at none, so it blocked every report image before this.

#### maintenance

- **Prose lint**: Comments in `maintenance/check_minify.py` use periods instead of semicolons. `userscripts/README.md` splits a long sentence. The full prose check passes.

## 2026-09-30

### Added

#### preview

- **Task-count reminder**: The rotation adds the tail `You have {remaining} tasks remaining.` That entry fills in the unfinished task count, with `1 task` in the singular. With no unfinished task the entry hides itself, and the line shows the next reminder.

#### userscripts

- **Action label forms**: The tab-title emoji map adds `Write` to the edit mark and `Explored` to the read mark. Every label in the owner's editing and reading groups maps. The version moves to `1.1.22`.
- **Arena tab title**: The Arena bundle gains a Tab title switch. It sets the tab title from the repository link in the session header and clears the emoji when the turn ends. The title adds an emoji for the live action, such as `Arena | clankers 🖥️`, or 💤 while the agent waits on a poll.
- **Transcript trim**: The Arena bundle gains a Transcript trim switch, off by default. It removes the oldest transcript messages and keeps a count set from the menu, from 20 up. The version moves to `1.1.14`.

### Changed

#### rules

- **Serial comma**: The ChatGPT custom-instructions field carries the line `ALWAYS Oxford comma.`
- **CI watch**: ARENA.md watches the PR checks with `gh pr checks <PR> --watch` on a Bash call with timeout 1800s. The sleep ladder leaves the refs and live lines.
- **Ledger prose**: AGENTS.md bans narrative, rationale and story in the ledger. The budget exceptions file drops reasons from its fill rule and every entry.
- **Custom answers**: AGENTS.md requires a fresh proposal of the new wording after a custom answer. The line lands only after approval of that proposal.
- **Clause proposals**: AGENTS.md requires a proposal on the initial refs wording of every clause change. Owner-supplied text is no exception, and the live mirrors follow the approved line.
- **ChatGPT long-text fences**: The `More about you` field scans for the longest inner backtick run and sets the outer fence to `max(4, run + 1)`. The fence stays strictly longer than every inner run and holds at least 4 backticks.

#### preview

- **Context reminder**: The rotation leads with `Refresh context with ARENA.md, SKILL.md, and REFERENCE.md.`, so a resumed session refreshes its rules and skill references first.
- **Preview reminders**: The rotation names the `task-list` timing and bans an open-task turn end. It adds the edit grep check, the pre-push rebase and the pushed-turn CI check.
- **Report receipt dot**: The Reports tab matches the log: submission ID, the state dot, then the latest stamp time.
- **CLI short form**: The skill guide calls the CLI as `arena-preview`, never the full script path.
- **Report agent receipt**: A read or a poll that delivers an answer stamps the parent report read by the agent. The report line shows the receipt beside Sent and Acked, an ack implies the read, and the owner's unread star keeps its own field.
- **Polling dot**: A running `poll` stamps a heartbeat once a second, and the state payload carries `polling`. The page shows its connection dot blue while the agent waits, with no extra text beyond the dot. The freshness window expires the flag five seconds after a killed poll.

#### gpt-plugins

- **Handoff output contract**: `gpt-handoff` emits the handoff as one Markdown fenced block with no prose around it. Evidence carries a direct link beside each claim, and `audit` takes the same single-block rule. The plugin version is `1.5.0`.

#### userscripts

- **Trim granularity**: The menu takes `<messages>,<rows>` and shows the live removed count. It keeps the newest messages whole, cuts older messages to the row limit, and keeps each `#chat-message-*` root because Arena complains if one leaves. It waits for a settled page and moves to `1.1.21`.
- **ChatGPT hide wiring**: The Images link, Library link and Free badge finders join the sync pass, so all eight elements hide. The self-check drives `syncDocument`, and the version moves to `1.2.1`.
- **Steering row words**: Open Steering finds the row by the words `steering` or `preview`, case-insensitive, and prefers the row that names the repository. The version moves to `1.1.7`.
- **Tab title hold**: The title re-asserts each second and holds the last repository name on the page. A turn end no longer drops it. The version moves to `1.1.8`.
- **Thinking row**: The tab title takes the live row from any message with a pulse. It reads the label even when that row is not a button, so a `Thinking…` row shows 💭. The version moves to `1.1.9`.
- **Live label anchor**: The action text comes from the shimmering status label, so a thinking row with no pulsing icon still shows 💭. The version moves to `1.1.10`.
- **Bash label forms**: The emoji map covers `Bash` and `command`, so `using Bash`, `used Bash`, `Running commands` and `Ran commands` show 🖥️. The version moves to `1.1.11`.
- **Newest steering row**: Open Steering takes the newest matching row, so a stale card from an earlier turn no longer shadows the live preview. The version moves to `1.1.12`.
- **Steering row ranks**: Open Steering ranks a running row above a `Start …` history card. The newest row wins inside a rank, so the click lands on the live preview. The version moves to `1.1.13`.
- **Emoji hold**: The title holds the last action emoji for five seconds after the live row leaves. A gap between calls no longer flashes the title. The version moves to `1.1.13`.
- **Bundle checks**: The bundles carry runtime code only. Outside a browser each feature publishes its helpers, and `maintenance/userscripts.checks.cjs` runs the feature checks. Arena moves to `1.1.15`, ChatGPT to `1.2.2`.
- **No Start click**: Open Steering never clicks a `Start …` transcript card, because a click on one opens nothing. With no running row it clicks nothing. The version moves to `1.1.16`.

#### workflows

- **Action caches**: The preview-tests job caches pip downloads, like the other Python jobs. The `lint-validate-budget` job caches the `cl100k_base` file that `tiktoken` fetches, so a cold run downloads it once instead of on every push. Every other workflow installs nothing and keeps no cache.
- **Action versions**: Every workflow pins the latest stable action majors: `actions/checkout@v7`, `actions/setup-python@v7`, `actions/setup-node@v7`, `actions/cache@v6`, `actions/upload-artifact@v7` and `DavidAnson/markdownlint-cli2-action@v24`. The shipped `github/workflows/gemini-release.yml` carries the same pins.
- **Gemini prompt rules**: The release prompt bans a Summary that repeats another section, internal identifiers, and repository tooling under Features or Fixes. Its Upgrade notes rule names the edits or the words `No action required`.

#### automations

- **DAILIES coverage gate**: A report carries `## Coverage` only when it has at least one finding. A run with no finding sends nothing and omits Coverage, and the title line drops the Coverage-gap case.

#### maintenance

- **Rename follow-up**: The `validate.yml` skip list, `maintenance/README.md`, `maintenance/check.py` and the preview skill README name `.github/workflows/distribute.yml`, the owner's renamed file.
- **Lint cleanup**: Both prose gates report zero violations. The passive and semicolon findings leave `maintenance/check.py`, `maintenance/check_gpt_plugins.py`, and `skills/squash/SKILL.md`. The CHANGELOG bullets cap at three sentences, and the preview skill README drops the synonym rotation.

#### docs

- **CHANGELOG domains**: Every date groups its changes under domain headings. The headings are rules, preview, gpt-plugins, userscripts, workflows, automations, maintenance and docs. AGENTS.md requires the shape.

## 2026-09-29

### Added

#### preview

- **Autoscroll toggle button**: Add a toggle to the transcript action row next to Stop generating. The button shows pressed while follow is ON and unpressed when OFF, and it stays in sync with the menu toggle. Drop the Shift pause.
- **Arena transcript auto-scroll**: The Arena bundle adds an independent saved switch. It follows new messages and resized output near the bottom, pauses on upward scroll and keeps reading positions across session changes. Node checks cover follow, pause, resume and cleanup, and steering label and repository matching now ignore letter case.

#### gpt-plugins

- **GitHub repository discovery**: `gpt-github` adds the owner's clause on tree discovery before file reads, known paths, batched calls and tool checks. Source and shipped copies match. Plugin version is `1.3.0`.

#### workflows

- **Gemini release drafts**: Add reusable GitHub Actions sources under `github/workflows`. Generate draft notes from complete release history with Gemini 3.5 Flash-Lite, a release template and split-and-combine summaries. Keep activation separate from the source library.

### Changed

#### rules

- **ChatGPT diagrams rule**: All diagrams use Mermaid, `flowchart TB` by default, no ASCII. The rule no longer limits itself to pipelines and flows.
- **ChatGPT outer fences**: Long fenced text uses at least four outer backticks, with a longer fence when the content requires one. Inner fences and language tags stay unchanged. The English More field uses approved lossless compression of existing lines.
- **ChatGPT Mermaid requirement**: Pipelines and flows must use Mermaid unless the target explicitly cannot render it. ASCII diagrams stay prohibited, and the top-down, short-label and phone-sized rules stay. Refs, live, wenyan and the platform table match the approved replacement.

#### preview

- **Owner-verbatim scope**: AGENTS.md grants the approval exemption only for the owner's complete clause text. Any other owner directive takes the report route first.
- **CI poll output**: ARENA.md polls the plain `gh pr checks` output. An empty or absent check list stays unverified, never a conclusion.
- **ChatGPT hide elements**: The ChatGPT userscript hides the Images sidebar link, the Library sidebar link and the Free badge. The bundle version is `1.2.0`.
- **Push after a rebase**: ARENA.md pushes only when the branch has commits ahead of `origin/main`. A rebase that leaves nothing to push skips the push.
- **Re-ack block gap**: Later ack blocks in the Messages tab use 8px around the hairline and drop the first paragraph top margin.
- **Autoscroll button hover**: Arena bundle 1.1.5 gives each toggle state its own hover fill: surface raised when off, CTA active when on. The on state stays visible under the pointer.
- **Publish feedback**: `publish` prints the parsed field count and warns when a `{#id}` marker parsed as prose. A shared-ID refusal suggests `<id>-report` or `<id>-task`.
- **Rules audit**: AGENTS.md, ARENA.md, CLINE.md, the preview SKILL.md and REFERENCE.md lose rationale tails, duplicates and untestable lines. ARENA.md now names every host `AGENTS.md` and wins collisions. The same edits apply to the ChatGPT files and COMMIT-SPEC.txt.
- **Tab pip alignment**: Tab buttons centre their label and unread pip with flex and a 6px gap. The pip sits on the text midline. Tabs are 116px wide (98px narrow), so the pip does not widen the row.
- **Report ack block gap**: Later reply blocks in the report ack history use 8px above and below the hairline and no paragraph top margin.
- **No shared report and task IDs**: `publish` refuses a report ID that a task holds. A new or amended task refuses an ID that a report holds. The ack log links one ID to one panel.
- **Local checks before push**: ARENA.md requires the repository checks to pass locally before every push, then the PR CI poll.
- **Link colour**: Preview anchors use a muted blue, `#6ea3d6`, in both themes instead of the accent colour.
- **Task ID shape**: Task IDs are short kebab-case titles, and acks put task IDs in backticks so the log links them.
- **Autoscroll only while generating**: Arena bundle 1.1.4 follows the transcript only while the Stop generating button exists, the same condition that hides the composer. With the composer shown, the transcript stays where the user put it.
- **Report ack top gap**: The report ack history sits 10px below the toolbar rule instead of touching it.
- **No init before serve or restore**: `preview.py gate` passes when the state database does not exist, and `import-state` creates a missing database. `init` stays for a manual create.
- **Task status values**: `SKILL.md` names the two `--status` values, `upcoming` and `finished`.
- **Report ack spacing**: Remove the top line and the extra space above the first reply in the report ack history. Zero the container and paragraph top spacing there. Keep the line between later replies.
- **Shift pause**: Arena bundle 1.1.2 pauses transcript follow while you hold Shift. Release Shift to resume while ON. Clear the held-key state on window blur without changing the saved switch.
- **Report footer status**: Repeat the submission status below the report form. Keep agent replies at the top and only the top status as a live announcement.
- **Report reply position**: Move report acknowledgement history and submission status above the report form. Keep reply history and links unchanged.
- **Clipboard images**: Paste images into the composer as staged attachments with epoch-time filenames. Keep image bytes, native text paste, removable files, the per-file limit and the normal send/retry path.
- **Turn-end task status**: State in chat that no open tasks remain before the final inbox poll. Keep the final poll and task-list check requirements.
- **Unified state import**: Replace import-notes and task-import with import-state for copied notes, tasks and report answers. Accept a file or stdin, preserve receipts and backups, and roll back the whole import on invalid records. Task replacement requires --replace-tasks.
- **Authoritative steering inbox**: Use the preview inbox for steering instructions, receipts and work status when Arena chat delivery is unreliable. Retain duplicate-message and reversible-edit safeguards.
- **Note references**: Require seven-character note IDs in prose, never sequence numbers or list positions. Check references against inbox IDs and keep full IDs in CLI calls.
- **Acknowledgement reference links**: Require exact report and task IDs in inline code in Markdown acknowledgements instead of generic labels. Retain short prose IDs for other references.
- **Report acknowledgement history**: Show agent replies in the report header with the Messages acknowledgement style. Preserve replies across submissions and repeated acknowledgements, including reference links.
- **Live userscript switches**: Apply all Arena and ChatGPT menu switches without page reload. Stop disabled observers, timers and listeners. Restore script-owned hiding changes without undoing earlier clicks or prompt insertion.
- **Messages tab**: Rename the visible Notes tab to Messages. Keep its data and routes unchanged.
- **Always-follow transcript switch**: Arena bundle 1.1.1 keeps the transcript at the bottom while enabled. Remove the near-bottom gate and upward-scroll pause. Disable the saved switch to stop follow immediately.
- **PR check polling**: Use exponential delays from 1 to 64 seconds after the initial check, then 64-second intervals. Stop and report command or API errors, including HTTP 401. Pending checks remain distinct from errors.
- **Finished tasks**: Show the last finished task first. Keep upcoming and saved task order unchanged.

#### gpt-plugins

- **gpt-github CI gates**: Poll the runs for the new head SHA after every push, since an older run verifies nothing. A missing, queued, in-progress or pending check is not complete, and a failed, cancelled or timed-out check is not green. The turn stays open after a push while the new head SHA has no completed run, and the plugin version is `1.4.0`.
- **Rebase rule**: ARENA.md requires a check of `origin/main` before each push and a rebase when main moved. After a push or a sandbox reset, HEAD must equal the remote branch.
- **GPT plugin compression**: Keep full refs and compress shipped skill wording without rule changes. Remove the destructive copy command, check matching structure and retain exact archive validation. Raise the plugin version to 1.3.1.
- **GPT plugin versions**: Require a version increase in `gpt-plugins/plugin.json` for every update under `gpt-plugins/`, including sources and documentation.
- **ChatGPT skill location**: Root `AGENTS.md` requires ChatGPT-related skills to go in `gpt-plugins`.

#### userscripts

- **Userscript domain bundles**: `arena.user.js` and `chatgpt.user.js` replace the five standalone scripts and keep their feature checks. Each feature has a saved, default-on Tampermonkey menu switch that applies after manual reload. Node integration checks cover switches, persistence, disabled startup and storage errors.

#### workflows

- **Workflows README**: The Gemini release page keeps the install steps, the proposal and approval run, and four operating facts. The intermediate mechanics and the dispatch note leave, and the page drops from 670 to 194 words by the linter count.
- **Distribution secret**: The dispatch workflow reads `CLANKERS_DIST_PAT` in both jobs, and the workflows README names the same secret.
- **Distribute consolidation**: One dispatch workflow holds two jobs, `Distribute Arena` and `Distribute Gemini Release`, each with its own target list and its own override input. `REPOS_ARENA` keeps the four repositories and `REPOS_GEMINI` keeps `nemoe7/daedalus`.
- **Release tags**: Proposed tags always start with `v`, so an initial release is `v0.1.0`.
- **Gemini prompts**: The four release prompts follow GUIDELINES.md section 4. Each has a task line, shared boundary lines, one imperative rule per bullet, and a final return rule.
- **Release notes sections**: Gemini omits template sections without evidence and always keeps Summary. An initial release shows Summary and Features only, with no commit comparison.
- **STE lint in the gate**: `check.py` runs the ASD-STE100 linter over the covered documents (`STE_DOCS`), and CI calls `check.py --ste` with the same list.
- **One pytest**: Test files are `test_*.py` and `*.test.cjs`. The `check_*` names stay for gates. A root `pytest.ini` runs the preview and Gemini release tests in one call, and CI now runs the Gemini tests.
- **Gemini model ladder**: The release workflow `models` input is a comma-separated ladder. Each request moves to the next model on an HTTP error or blocked output. Default: gemini-3.8-flash to gemini-3.1-flash-lite.
- **Distribute Gemini release**: `distribute-gemini-release.yml` copies `gemini-release.yml` and `gemini_release.py` to target repositories on dispatch, `nemoe7/daedalus` by default, on the pattern of `distribute-arena.yml`.
- **Gemini release in two files**: The prompts and the release template move into `gemini_release.py` as constants. A target repository installs the YAML and the Python file only.
- **Gemini evidence input**: The release workflow has an `evidence` choice. `commits-and-diffs` is the default and `commits` sends commit messages only.
- **Gemini HTTP error detail**: A Gemini HTTP failure now shows the status and message from the response body after the HTTP code. The detail stops at 500 characters and the script redacts secrets.
- **Gemini release input**: Send only commit messages and text diffs to Gemini. Binary files add one marker line and no patch data.
- **Gemini release path**: Run the Gemini release scripts from `.github/workflows` instead of `github/workflows`.
- **Gemini release proposals**: Classify SemVer impact from complete commit history. Write a version and notes proposal first. Only a separate approved run can create a tag and draft.
- **Release command errors**: Include the failed command and stderr in Gemini release errors. Explain the existing-tag requirement when tag resolution fails. Redact configured GitHub and Gemini secrets, and check missing-tag diagnostics offline.
- **DAILIES monitoring**: Use a rolling 24-hour event window without checkpoint writes. Show incomplete coverage, rotate deep audits through three active repositories per day, keep monitoring read-only and separate release drafts from findings. Repository and scheduler copies remain separate.

### Removed

#### preview

- **Seen subcommand removed**: `read` and `poll` stamp delivered IDs Seen, so `preview.py seen` goes from the code, the tests and `REFERENCE.md`.
- **Poll flags removed**: `preview.py poll` takes no `--interval` or `--max`. The wait stays 900 × 1 s in refs, live and installed copies. The test covers the fixed wait and rejects the old flags.
- **PR-only validation**: Stop repeat validation after main updates and remove the main-only README measurement commit. Keep PR checks, plugin packaging and rules publishing.
- **Owner input limits**: Remove note, answer, submission and total request caps. Keep the 50 MB per-file upload cap and current timeouts. Stream multipart files and download results to temporary storage while agent replies, reports, tasks and agent-requested downloads retain their limits.

#### maintenance

- **Userscripts Gist retired**: `.github/workflows/publish-userscripts.yml`, `maintenance/publish_userscripts.py` and `maintenance/check_publish_userscripts.py` leave the repository. The rules Gist publisher and its check stay, and `validate.yml` runs only that check. The five userscripts point `@updateURL` and `@downloadURL` at this repository's raw files.

## 2026-09-28

### Added

#### preview

- **Preview CLI PATH command**: `install.sh` adds `.agents/skills/arena-preview-steering/scripts` to PATH for new Bash shells. `arena-preview <command>` uses the repo's script, venv and state. Tests cover PATH recovery and forwarding, so rerun the installer after a sandbox reset.

#### userscripts

- **ChatGPT userscripts**: `userscripts/chatgpt-hide-elements.user.js` adds `hidden` to the Claim offer, Free offer, chat surface toggle, Codex sidebar link and prompt-textarea header elements. `userscripts/chatgpt-auto-think.user.js` clicks the Think pill every second while `aria-pressed` is `false`. Node checks print `ok`.

### Changed

#### preview

- **Final task-list check**: Require `task-list` before the final reply, then continue any unblocked upcoming task.
- **Steering prose cleanup**: Use `arena-preview` for ARENA inbox reads and the end-turn wait. Drop duplicate rules and report text plus the primary-skill `--state-dir` line. Keep the raw Python fallback.
- **ARENA compaction retention**: Request verbatim preservation in context summaries. Reread if a summary omits or changes it. Arena host reinjection is the only guarantee, so the request is best-effort.

## 2026-09-27

### Changed

#### preview

- **Turn-end poll**: `preview.py poll` waits for a pending inbox item. Refs, live and root drop the sleep-10 / 100-loop wait. The default wait is 1 second, 300 times (5 min).
- **Poll wait 15 min**: `preview.py poll` waits 900 × 1 s (15 min), from 300 × 1 s (5 min), in refs and live copies.
- **Reminder rotation**: The GH_TOKEN line now reads ask_user on GH_TOKEN failure. The entry adds "Remove stale reports with unpublish." and "End the turn with `poll` to wait for more work."
- **Inbox cadence hardened**: REFERENCE line 32 now reads: ALWAYS run `poll` on the bash call that ends the turn, chained or not. A second line reads: between two reads, NEVER run a fourth bash call. A read MUST come before it, mirrored in refs and live.
- **Skill prose trimmed**: Twelve approved rows leave `SKILL.md` and `references/REFERENCE.md`: ceilings, browser-page facts, proxy names, the tab X detail, filename receipts and the venv-install line. Live, refs and `.agents` copies stay byte-identical where mirrored.

#### userscripts

- **Steering click delay**: `userscripts/arena-agent-steering.user.js` waits 1 second, then clicks `{repo} - Steering` once per page.
- **Hide editor-content**: `userscripts/arena-agent-hide-composer.user.js` hides `div.editor-content` while Stop generating is present, not the outer composer shell.

### Removed

#### preview

- **Report 120 line dropped**: The line "Reports MUST allow lines up to 120 characters (MD013 at 120)." leaves refs, live and root `ARENA.md`. One squash attempt on the live Style gates line keeps "gates: `ruff check`, `ruff format`, no CLI overrides."
- **Edited report dot dropped**: The Reports tab pip hides a report the owner already opened. The select star still marks changed text. `reports.ever_seen` carries the open across a republish, with a migration backfill, in refs and both live copies.
- **Five-file cap dropped**: The composer stage, the multipart note route and the skill docs lose the five-file count. The 50MB per-file ceiling and the multipart body bound stay (`MAX_NOTE_UPLOAD` 250,000,000 + `MAX_BODY`). Six-file HTTP and chip tests added.

## 2026-09-26

### Added

#### preview

- **Answers ride the copy**: The copy button's NDJSON gains the answers of every report still in the tab. A new `GET /api/submissions` endpoint serves them filtered to live reports, and the copy click merges them in. The receipt reads Copied N messages, A answers and T tasks as NDJSON, and `import-notes` restores them as before.

#### userscripts

- **Hide composer while generating**: On `/agent/*`, `userscripts/arena-agent-hide-composer.user.js` adds `hidden` to the outermost composer shell when a button `aria-label` is `Stop generating`. It removes the hidden state when that button is gone.

### Changed

#### rules

- **Setup gate**: The `Use` section of refs, live and root `ARENA.md` requires the 10-4 line, the preview start and the visibility question. It applies before the first tool call that is not a read of a rule or skill file.
- **Re-read clause**: The `Use` section of refs, live and root `ARENA.md` tells the agent to read the file end-to-end at each turn start. It applies when the full text is not in context, summary or truncation included. The re-read comes before the first tool call.
- **Gist index links**: The Files table in `#clankers-rules.md` links each file to its anchor on the gist page, for example `[AGENTS.md](#file-agents-md)`. `publish_clankers_rules.py` gains `gist_anchor`, and the contract check asserts the linked rows.

#### gpt-plugins

- **gpt-plugins package split**: `.github/workflows/package-gpt-plugins.yml` runs on pull requests only. A PR that changes shipped plugin files must raise the `plugin.json` version above the base. Package and artifact upload stay on `main`, and `maintenance/check_gpt_plugins.py` gains `--base-manifest` and `--self-check`.

#### userscripts

- **Composer hide vs flex**: `userscripts/arena-agent-hide-composer.user.js` sets the `hidden` class and inline `display: none !important` so Tailwind `flex` cannot keep the composer open.
- **Userscripts split**: The steering click moves to `userscripts/arena-agent-steering.user.js`. `userscripts/arena-agent-prompt.user.js` fills the `/agent` composer only.
- **Steering preview auto-click**: On `/agent/*`, `userscripts/arena-agent-prompt.user.js` clicks the `{repo} - Steering` button on port 8000 once per page. Composer fill stays on exact `/agent`.
- **userscripts README**: Root README lists `userscripts/`. `userscripts/README.md` covers Tampermonkey install, `/agent` fill behavior and the node check. No budget-table row.
- **Arena agent prompt userscript**: `userscripts/arena-agent-prompt.user.js` fills the `/agent` composer with `{repo} read AGENTS.md ARENA.md` when the GitHub repo bar is present. It updates the text when the repo slug changes.

### Removed

#### rules

- **Force-with-lease clause dropped**: The line "Rewrite remotes with `--force-with-lease`, NEVER plain `--force`." leaves refs, live and root `ARENA.md`. The matrix Git/Hub Arena cell drops "`--force-with-lease` only."

#### preview

- **Form-wait inbox poll**: Drop `ask_user` while a report form awaits answers. Loop `sleep 10` and inbox `read`. Break on a new message or after 100 loops.

## 2026-09-25

### Added

#### rules

- **Owner-verbatim clauses**: Root `AGENTS.md` says a clause the owner amends or adds verbatim does not need to pass thru approval.

#### preview

- **Ambiguity guards**: The assumption and lazy-default clauses gain NEVER guards against material ambiguity in refs and live. The root `AGENTS.md` copy matches.
- **Report deletion**: A ✕ button in the `Reports` toolbar and `unpublish <id>` remove a stale report, and the tab asks for a second click. Sent answers and the source file survive, so a new ID republishes.
- **CI poll backoff**: `ARENA.md` and refs gain the CI poll rule. After a push, poll PR checks at once, then 10s, 20s, 30s, and every 30s to a conclusion. The Git/Hub Arena cell gains "Backoff polls for PR checks."
- **Re-ack appends**: A second `ack` on the same ID adds a reply block under the first answer. The block keeps its own kind and stamp, so the earlier answer stays. The database, save file, shift-click copy and restore all carry the blocks, and the log shows "Replied again" with a "New reply" pip.

#### gpt-plugins

- **PR checks**: The `gpt-github` skill gains three lines after the CI line. ALWAYS check `.github/workflows/` for a workflow that runs on the PR and, with none, say so and skip the wait. No check yet is pending, not green: poll until each check concludes and NEVER end early.

### Changed

#### rules

- **Platform Specific squashed**: Every item caps at five words. Merge authorization joins the Git/Hub Arena cell as "NEVER merge unauthorized." The investigation stop drops.
- **Core rules refinement**: The list drops the platform-specific and redundant lines, keeping seven. The Questions and Recommendation rows stay in the matrix. The remaining compress to Ask if ambiguous, YAGNI/KISS/DRY, Always add tests, NEVER weaken one.
- **Core rules section**: A dash list of the core clauses before the matrix, ten words a line, hard words kept. The matrix's Rule area column becomes Domain and Core becomes Agents. Rows rename to Git/Hub, Questions, Mermaid Diagrams, Recommendation, Platform Specific.
- **Contents table**: The heading loses "and activation". The "How to use" column leaves the table. The purpose cells stay as they were.
- **Platform specific de-git**: Merge, commit list, force push, and GitHub auth leave the Arena cell. The Git and GitHub row carries them. Merge authorization stays put, since its NEVER has no other home.
- **Git and GitHub as lists**: The row takes each platform's git duties as bulleted lists, with CI included and five words an item. Platform specific keeps the non-git items.
- **Matrix squashed**: The remaining cells cap at five words each, keeping the keyword. Smaller scope, Tests and Dependency approval drop. ChatGPT and core carry the same clause after the alignment, and the ladder rung took the dependency one.
- **Report lines and allowlist**: The report head, footnote and send receipt use the log's receipt grammar: object, then state, then time, joined by dots. The `Reports` tab says Acked where the log says Said. Report prose allows `ul`, `ol` and `li` alone on their lines while other HTML keeps escaping, and the matrix row renders its bullets.
- **Matrix intro and Terseness row**: The intro is one sentence on why the surfaces differ, and the Terseness row leaves the matrix. The refs share T1 to T3 on core and Arena.
- **Matrix rows**: Docs narrative and SOLID governs leave the matrix. Their summary was the same on all three platforms, and the intro now says such rules are not listed.
- **ChatGPT Tests and turn end**: The Tests line takes the core wording that starts "Add tests for every new behavior and fix". The lines "NEVER end turn until tests are green." and the simplicity tail of the WORK line leave `CHATGPT-MORE.txt`. The `gpt-github` skill carries the CI rule for every git task, and refs, wenyan and matrix follow.
- **Two Arena cuts**: "NEVER ASCII art" leaves the mermaid line, and "no skill or linter" leaves the short chat reports line. Live, refs and the matrix cells follow.
- **Two owner cuts**: "and NEVER go cryptic" leaves the T2 terseness line in core and Arena, refs and live, and the two matrix cells. The ChatGPT unattended sentence leaves `CHATGPT-CUSTOM.txt` and the Ask on ambiguity cell.
- **Terseness T1 live line**: `rules/AGENTS.md` and `rules/ARENA.md` share one ASD-STE100 line: MUST use ASD-STE100 for all human-facing text: responses, comments, docs. The refs already share T1 to T3, and T4 short chat reports stays Arena-only by decision.
- **Core ASD-STE100 in the matrix**: The core already carries the ASD-STE100 MUST on `rules/AGENTS.md` L22, and the Terseness Core cell now shows it. Six more cells gain the NEVER or MUST of their rule area: Smaller scope, Terseness Arena, Tests, Smallest task, Open tasks and the `gpt-github` bullet. The ChatGPT Mermaid cell says "NEVER ASCII art" like its source.
- **ChatGPT ambiguity clause**: `CHATGPT-CUSTOM.txt` L5 takes material-ambiguity wording: readings that change behavior, data, interfaces, scope or outcome, with an ask before implementing. The assume-nothing sentence leaves refs, live and wenyan while the Unattended sentence stays. Refs `CHATGPT-MORE.txt` L4 gains "detail when asked", which the live line already had.
- **Core push rule**: `rules/AGENTS.md` and its refs say "NEVER push unless asked." Pull requests belong to Arena and the `gpt-github` skill only. The matrix Core cell and the publisher check follow.
- **Matrix collapse**: The 17 rows that one platform alone carries fold into one Platform specific row, skill cells not counted. 13 rows remain. Each cell of that row is an inline bulleted list, one clause per bullet.
- **Steering bullet split**: The 2,701-char constitution bullet in refs `ARENA.md` becomes one constitution line plus eight one-rule General bullets, wording kept. The block mechanics of the read cadence move to the steering skill reference, section Read cadence, in refs, live and `.agents`.
- **Question channel split**: The one question-channel bullet in refs and live `ARENA.md` becomes five one-rule bullets, wording unchanged (Guidelines 4.1).
- **Plain adverbs**: "NEVER came up" becomes "did not start" in refs and live `ARENA.md`. Refs "if the user NEVER replied" becomes "on silence" as in the core. NEVER now marks only rules.
- **GitHub reconnect**: A dead `GH_TOKEN` now ends in an `ask_user` reconnect question, not a fielded report, and the `ask_user` exception list names that case. Refs, live and root `ARENA.md` take it, and the matrix cells follow.
- **Matrix keywords**: Matrix summaries keep MUST, NEVER and ALWAYS where the source rule carries them, 19 rows. Plain-case cells mean the source has no hard keyword, and the ChatGPT Smaller scope cell follows `CHATGPT-MORE.txt` L12.
- **Keyword case**: Every standalone never, always and must under `rules/` is uppercase, 73 words in 10 files. The root `ARENA.md` mirrors.
- **Matrix summaries**: The `rules/README.md` platform matrix gives the behavior each rule instills instead of the quoted clause, 29 rows in short sentences. The intro sentence follows.
- **Arena storyline ban**: `rules/refs/ARENA.md` takes the core refs sentence, and `rules/ARENA.md` plus the root copy take the core live line. It reads: Documentation, no storyline or narrative unless asked, after the terse clause. The matrix Arena cell follows.
- **ChatGPT refill**: The space the git block freed takes four core clauses. Refs `CHATGPT-CUSTOM.txt` gains the full core sentences, and the live and wenyan files gain the SCOPE, CODE and FORMAT lines plus a new DOCS label. The unrelated-findings line stayed out for the SOLID line, and the `rules/README.md` matrix gains the Docs narrative and SOLID governs rows.
- **Investigation stop**: `rules/refs/ARENA.md` replaces the investigate-just-enough clause with the owner sentence. Live `rules/ARENA.md` and the root copy take that sentence in place of the compressed fragment.
- **Platform matrix**: `rules/README.md` aligns the stale cells and adds the missing platform diffs, and periods replace semicolons. The tests purpose word and its synonym exception stay in code spans because the STE synonym gate would reject them in prose. The contents line uses `fix` so the tests row can quote that verb.
- **Gist index**: The publisher no longer copies `rules/README.md` into `#clankers-rules.md`. The gist file lists only the files that publish, including the wenyan files, and keeps the platform matrix. The installer, refs, lint scope and changelog pointer stay out, and the CI job runs the publisher contract.
- **Visibility block**: The preview carried its own visibility question, so a hidden preview hid the question too. ARENA's `ask_user` ban covered an unconfirmed preview, so ARENA and `SKILL.md` now ask through `ask_user` with Yes, No, ntfy and Continue without steering. Work stays blocked until the owner answers the question, and `ask_user` is also allowed when no steering channel is visible.
- **Recommended answers**: Core and ARENA require a recommended answer only for questions with three or more options or an open choice. Yes/no and approval questions carry none.
- **Approval format**: House proposals group rows under each refs file, and each ID takes approve, squash, reject or custom. Code changes need no proposal. Proposals come before tasks.
- **Visibility question alone**: ARENA asks the visibility question alone, and after Yes all other questions go by fielded report. A house `squash` decision now means re-propose a line squashed with the `squash` skill, not land it.
- **ChatGPT alignment**: ChatGPT takes the core wording on asking, big briefs and user-run commands, and it gains the core testing details and formatting rules. It drops the unrequested-abstraction pair and the no-preamble line, which the terse clause covers. The house cascade adds `rules/wenyan/`, and the wenyan fields follow.
- **Per-clause options**: House proposals put each clause's options directly under its row, with a new table per clause under the file heading.

#### preview

- **Negative-rating clause**: "Failure to ack immediately earns a negative rating." joins the ack cadence paragraph in all three `SKILL.md` copies.
- **Rationale ban**: The clause "NEVER contain rationale, narrative, or facts that drive a clause" lands in root `AGENTS.md` first. The measured rules files do not change.
- **Narrative audit applied**: The owner's picks drop rationale tails, two history parentheticals and one slogan from refs `ARENA.md`, with the live mirrors in step. The refs backoff line becomes a plain bullet, and the merge bullet reads: ALWAYS merge rebase. The snapshot-cap derivation leaves both `SKILL.md` and `REFERENCE.md` copies while the size and "cap is not measured" caveat stay.
- **First-unread counter**: The hook's call count resets only on a fresh backlog's first item. A message on an unacked pile leaves the count running.
- **Toolbar parity**: The unpublish button joins the 44px rule. The report select draws the log filter's chevron instead of the native arrow.
- **Downloads prose**: The agent-request line reads "agent requests need approval below".
- **Audit F4 splits and F5b drop**: Six long bullets split at sentence boundaries in refs and live `ARENA.md`, one rule per line, wording kept. The HTML export story leaves both files, and the root copy matches.
- **Re-ack clause**: `SKILL.md` and the reference now say a second `ack` appends a reply block. The earlier sentence said it replaces. The rule and code agree since 01220f0.
- **Arena trims**: The six web-path bullets leave refs and live `ARENA.md`. They served web research, not the steering skill. The self-loading sentence leaves the Use section, since an agent that reads the line has already loaded the file.
- **Double quotes**: Root `AGENTS.md` says to quote clauses in double quotes, never backticks, in proposals, acks and reports, because backticks break the front-end rendering.
- **Re-ack clause**: Both steering `SKILL.md` copies and the refs baseline say a second ack replaces the earlier answer.
- **Preview prose trim**: The Downloads tab keeps the 102,400,000-byte ceiling, the keep-page-open line and the Approve line. The cap rationale, the 512 MB anecdote and the CORS, proxy, SQLite and restore sentences go. The Reports tab answers note and report-loaded status each keep one sentence, and `check_preview.py` asserts the new page line.
- **Preview checks**: `check_preview.py` is 26 pytest tests, and `check_client.cjs` is 45 ordered `node:test` checks. `validate.yml` names its two jobs, and the test job skips when preview paths did not change. `check_minify.py` runs pytest on the generated runtime with `pytest==9.1.1` installed in that job only.
- **Downloads**: The `download-request` skill names the flow, the owner approves or denies the pending job, and `--allow-proxy` stays a per-URL opt-in. The download ceiling is 102,400,000 bytes, 80% of the documented 128,000,000-byte snapshot cap, while uploads stay at 50,000,000 bytes. The page says the cap is not measured, and one session reported 512 MB.
- **Ack reminders**: `ack` prints a `task ... --msg-id` reminder, and `SKILL.md` says to queue each work note. An ack that empties the inbox resets the call count at once.
- **Pending-form block**: With a report form awaiting answers and no unblocked work left, ARENA blocks with `ask_user` naming that report. It reads the inbox instead of ending the turn, and the `ask_user` exceptions list this case.

#### gpt-plugins

- **Platform specific trims**: The `gpt-github` rebase-merge bullet leaves the ChatGPT cell. The Git and GitHub row already carries those three clauses.
- **Matrix git row**: Push and PR and Turn-end tests merge into one Git and GitHub row. The matrix intro drops the CHANGELOG pointer and the gpt-github cell names. The previous commit dropped the Terseness row.
- **gpt-planning keywords**: The two completion-gate lines start with NEVER instead of "Do not".
- **Matrix skill cells**: Empty ChatGPT cells that the `gpt-github` skill covers name it: Push and PR, Merge, Commit list. Turn-end tests adds the PR-check poll.
- **gpt-github**: The ChatGPT `GITHUB:` block leaves the three CHATGPT files and becomes the `gpt-plugins` skill `gpt-github`. The description reads MUST use for every git or GitHub action. The body keeps five refs lines, two owner lines and three core Git lines, and `plugin.json` moves to 1.2.0.
- Gates green.

### Removed

#### rules

- **Arena dependency approval drop**: The per-case sentence leaves live and refs. The shared NEVER sentence stays. Ask on ambiguity leaves the matrix, identical on all three.
- **Dependency sentence drops**: The line "NEVER add a dependency for a few lines' work" leaves live and refs on all three platforms. The ladder rung already carries it, so Arena keeps the per-case approval sentence and the matrix cell follows the rung.
- **No ID column**: House proposal rows drop the ID, and each clause takes its own options.

#### preview

- **Write-token check dropped**: The preview server no longer refuses writes without the token. The check stays commented out in refs `preview.py` with the original reload clause as its comment, and minify strips both from the compact copies. The reload lines leave `SKILL.md` and `REFERENCE.md`, so page and API writes pass without the header.
- **Reports tail send flash dropped**: The green Sent receipt line leaves the `Reports` tab, and the footnote under the report carries the same facts.

### Fixed

#### rules

- **Matrix order fix**: The Questions-row restore had left the Recommendation row twice, and one copy goes. The row order matches the list: Git/Hub, Questions, Mermaid Diagrams, Recommendation, Platform Specific.

#### preview

- **Gist index fix**: `publish_clankers_rules.py` reads the Contents section and emits File and Purpose only, so the gist's Files table shows real purposes again.
- **Audit fixes**: The Arena Git/Hub cell gains "Planned list before commits." and "GitHub reconnect after one retry". Both are live Arena clauses that earlier squashes lost.

## 2026-09-24

### Added

#### preview

- **Preview download queue**: Add a SQLite-backed browser queue for HTTPS files with direct access first and per-job opt-in AllOrigins and CodeTabs fallback. Fetched files and manual uploads cap at 50,000,000 bytes, and claims expire after five minutes without renewal. Successful jobs save the bytes plus inbox path notes, and the change updates both shipped copies with the trust warning kept.

### Changed

#### preview

- **Preview task reminder**: Rotate the reminder text that warns against ending a turn while tasks stay open. Add a source test and rebuild both runtime copies.
- **Preview operator docs**: The shipped `SKILL.md` and bundled reference shrink while keeping operating steps, current attachments and owner-entered Downloads. Implementation notes move to the source-only `skills/arena-preview-steering/README.md`, excluded from both dispatch file lists. General preview trust warnings go, and readable and installed copies stay aligned.

#### gpt-plugins

- **Direct plugin artifact**: `.github/workflows/package-gpt-plugins.yml` keeps the collection and ZIP checks, then uses `actions/upload-artifact@v7` with `archive: false` to publish `gpt-plugins.zip` directly. The workflow-definition check pins the direct mode and the effective file name, and the plugin and maintenance READMEs name the new download.
- **GPT Handoff audits**: Activate audit mode for reviews of agent-produced work: code, human-facing docs, agent-created branches, PRs, commits, implementations and follow-up audits. Always route code and docs audits through Ponytail, then produce only the GPT Handoff format. Keep SOLID conditional on need, exclude audit setup and methodology, check the actual-model marker, and skip the skill for a normal non-agent task.
- Gates green.

## 2026-09-23

### Added

#### preview

- **Report path**: The same three files gain `ALL reports MUST go through the preview skill`. It went into `ARENA.md` and not `AGENTS.md` L76, which keeps its fits-in-chat line and loses to `ARENA.md` where the two disagree.
- **Save-state clause**: The refs `SKILL.md` gains a Save state section, and both `REFERENCE.md` copies record that `POST /api/save-state` also writes an inbox note. The live SKILL.md stays unchanged by request. Both steering `SKILL.md` copies gain the clause Markup needs `--reply`.
- **Auto-poll hook**: Install an idempotent hook: one installer creates the venv, writes `~/.arena-preview-hook.sh` and adds the EXIT trap to `~/.bash_profile`. The hook polls after every Arena bash call, prints the unacked counts to stderr and marks nothing seen. `--reminder` is its CLI interface, `require_server` names a down server, `serve` records its port, and the change removes the manual cadence.
- **Practice-only rule**: Root `AGENTS.md` Skills section gains the preview skill's practice-only rule, and the first pass applies it. The state-directory clause keeps its prohibition and drops the restore rationale, and the renderer sentence drops its justification. Refs and both live twins carry it file by file.

#### gpt-plugins

- **gpt-plugins collection**: Add the gpt-plugins Agent Plugins 1.0.0 collection with `plugin.json` against the canonical schema, `gpt-quirks` and `gpt-handoff` shipped byte-identical, and a non-shipping README. `.github/workflows/package-gpt-plugins.yml` packages `gpt-plugins.zip` from `plugin.json` and `skills/` only, and uploads it on pushes to main, on pull requests and on demand. `check_gpt_plugins.py` gains `--update`, `--schema` and `--archive`, and local runs use `--schema` with a downloaded copy since the sandbox cannot reach agent-plugins.org.

### Changed

#### rules

- **Exceptions ledger**: Every date, budgeted file, delta, reason and funding status stays, and the 2026-09-17 residual chronicle collapses to its final entry. The header drops Per item 6, and the save-state row drops a session-local report ID.
- **Install prose**: `skills/README.md` drops the vendor-and-version explanation from the discovery notes and keeps the constraint: check each path and its precedence against the installed release. The maintainer lead-in and the Antigravity scope note tighten to the same meaning. Every constraint survives: read-only installed copies, whole-folder copies, one active copy, no shell-execution syntax, and the post-setup check.
- **Compression procedure**: `README.md` drops the six generic squash steps the `squash` skill already carries. The Clankers rules stay as bullets: refs first, the clause budgets, restructuring as an amendment, remove words never rules, and the bookkeeping. The `README.md#compression` anchor that root `AGENTS.md` L124 cites still resolves.
- **Session artifact citation**: `rules/README.md` L94 drops a report ID that does not persist between sessions. It keeps the approval: the pinned minifier manifest is the one exception on the approved answers.
- **Arena activation narrative**: `rules/README.md` L103 drops the dated verifications and narrative observations. The contract stays: exploration does not gate activation, activation is a human step, and delivery is not activation. The workflow distributes while `rules/apply.py` does not install, and the exact line goes in the first message and the custom-instructions field.
- **Session-local artifacts**: `rules/refs/ARENA.md` L141 broadens the citation ban to every session-local artifact: note, report, submission or task IDs, or any identifier minted for one session. Live `rules/ARENA.md` L83 takes the compressed form (note, report, submission, task ID), and the root copy matches.
- **Per-date ledger**: 109 dated sections merge into 15 per-date entries: one heading per date, bodies in file order, and eight repeated Date lines drop. Session-local citations leave: 20 preview-report IDs, 18 old-format note IDs and one note sequence reference, each becoming a neutral phrase that keeps the fact.
- **Turn end**: `rules/refs/ARENA.md`, `rules/ARENA.md` and the root copy replace the awaiting-owner condition with the approved wording: never end a turn while tasks are open. A blocked task receives a published fielded report and then waits for input. The old line said when a turn may end awaiting the owner and never said a turn may not end while work remained.
- **Read cadence**: `rules/refs/ARENA.md`, `rules/ARENA.md` and the root copy state that a count moving inside a block means read now, not at the next boundary. The steering skill carries the same rule on its polling bullet. The reminder prints only a count, so a rising count meant notes sat unread until the next block.
- **Squash fixtures table**: `skills/squash/SKILL.md` requires a fixtures table when one change covers several files. The table carries before, after and percentage saved per file plus the average.
- **Ledger neutrality**: 136 lines in the pre-2026-09-23 entries now name actions, files and numbers instead of an actor. No line names the owner or the agent, and every fact, date and command stays. `workflows/init-docs.md` L260 drops the phrase along the way for gains skill.
- **Compression cut**: Strip storytelling, narrative and per-event framing from ledger and archive prose: every entry now states actions, files and numbers only. The pass removes no facts, dates, sizes or commands.
- **Editorial pass on 2026-09-12**: 52 bullets become 51 as cut lists keep counts and lose enumerations. The positive-phrasing rewrite keeps which seven clauses changed, the constitution keeps its count instead of its eight rules, and ruff.toml settings go back to `ruff.toml`. Every audit finding stays.

#### preview

- **Composer limit**: The composer caps a note at 15,000 characters, up from 4,000, end to end. `scripts/preview.py` carries the cap in a new `MAX_NOTE` constant that the validator and its error message read, and the composer textarea takes maxlength=15000. The request-body limit rises to 96,000 bytes because a fully escaped 15,000-character note can reach 90,000 bytes.
- **Idle reminder**: `Store.reminder()` prints the call-since-read segment only beside a pending count. An idle line carries the rotating tail alone while the counter still advances on every hook poll. `SKILL.md` L35 moves the call count behind the pending counts in all three copies.
- **Task-link requirement**: `SKILL.md` L49 turns the `--msg-id` guidance into a requirement: every task born from a note or report carries `--msg-id <full-message-id>`. An unlinked task is a violation, and refs keeps the full wording. The live copy squashes it to the short form.
- **Rotating reminder**: `Store.reminder()` draws its tail from a module-level `REMINDERS` tuple via a cursor in `meta`, so every string appears once per cycle. It prints the hook polls since the last `read` as the first segment. Only `--reminder`, the hook's interface, advances the count, and `read` clears it beside the `last_check` stamp.
- **Ack nudge**: `scripts/preview.py` appends `ACK ASAP.` to the stderr reminder whenever messages, form answers or uploads await action, and `skills/arena-preview-steering/SKILL.md` states the same contract.
- **Reminder emphasis**: The stderr reminder prefixes `DO NOT IGNORE.` before `ACK ASAP.` whenever anything is pending, and both SKILL.md copies state it.
- **Steering prose audit**: The audit answers apply every steering row. The read clause drops the stale `filters` claim since `read` takes no arguments, and the ntfy transport spec moves behind a pointer into `references/REFERENCE.md`. Setup item 5, the duplicate and owner-side sentences go, and the stale `check_preview.py` pointer now names the refs tree that ships the harness.
- **Reporting merge**: The same audit answers merge `arena-preview-reporting` into `arena-preview-steering` 3.0.0. One entry point now covers steering and reports, and a Publishing reports section absorbs the reporting skill's unique procedure and content rules. The three reporting trees go, the rule files drop the reporting pointers, and dispatch retires the installed reporting skill.
- **Republish guard**: `publish` refuses a report ID with submitted answers, so an update goes out under a new ID against changed fields. The refusal covers the CLI and every caller of the same method, exits 1 and names the report. The marker harness covers the refusal, the fresh-ID publish and the CLI error, and both SKILL.md copies and the references state the new contract.
- **Violation receipts**: The same three files pin the suggested amendment to the reply that reports the violation. The old line required a suggestion without saying when, so it could land after the turn it amends.
- **Identifier shape**: Uploads and save-state notes take the shape the log shows: seven characters, a hyphen and the rest. Both used a raw uuid4.
- **Unread marks**: The report star and the Reports tab pip track unread only. `needs_answer` moves neither, so an unanswered form carries no marker.
- **Approval gate**: Narrow the root `AGENTS.md` edit gate from every file to clause changes: no rule-file clause changes until the owner approves its report. Edits that change no clause, like a squash that removes no rule, a typo or a re-measure, need no report. `scripts` stays outside the gate.
- **Hook paths**: Bake the absolute repository root into `~/.arena-preview-hook.sh` at install time so the poll reminder runs from any working directory. The previous hook resolved paths against the caller's cwd, and the setup verifies from `/` and `/tmp` in a login shell.
- **Save-state note**: The `/api/save-state` route writes an inbox note naming the file and its note, task and answer counts, so the next `read` delivers it. The file landed untracked at the repository root and nothing else signalled a save-state press.
- **AGENTS.md amendment**: Two report clauses land in root `AGENTS.md`: neutral wording with no who-did-what narrative, one terse entry per event. Refs gains documentation stays terse but unambiguous, no storyline unless asked, and live takes the compressed form.
- **Read order**: Change the first steering read from optional before discovery and startup to required after startup. Before the first `serve` there is no inbox, and a missing state file then is no failed read. The Arena refs baseline, live Arena rules, root `ARENA.md`, steering skill refs baseline, compressed live skill and installed mirror all update.
- **Auto-seen**: Make a CLI `read` stamp Seen for exactly the IDs it printed once its output write succeeds. A failed write stays unseen, and pending stays the acknowledgement queue, so a stamped note prints again until answered. Update the refs runtime and harness, rebuild both distributed copies, and reword the steering contract and reference.
- **Answers survive republish**: Compute a report's `needs_answer` from the existence of any form answer instead of one newer than the last publish. An agent republish never asks the owner the same form twice, and the republish still clears the read stamp so changed text shows unread.
- **Poll cadence**: Amend the steering cadence: end every bash call with a poll, replacing always include a poll in bash calls. Update the Arena refs baseline, live Arena rules, root `ARENA.md`, steering skill refs baseline, compressed live skill and installed mirror.
- **Steering state location**: Move the steering state out of `reports/arena-preview` into `arena-state/` and exclude it only through `core.excludesFile`. The save file defaults beside the database, and a sandbox restore removes every path the repository ignores plus every home-directory file. A `.gitignore` rule destroyed the state on five restores while a globally ignored path survives as untracked and unmatched.
- **Ack contract**: Amend the steering skill and its reference: one answer per call, and never the same text to two messages. The rule came from three notes acked with one copied sentence.
- **Reminder tally**: Change the reminder tally to count only while something is pending: an idle inbox showed "111 call/s since read" beside a message. An empty `--reminder` poll clears the tally, and the segment reads N call/s waiting. The number counts the bash calls the pending items waited, and both SKILL.md clauses follow.
- **Task-list rule**: Amend the steering task-list clause: ack and queue in one call, and a work note receives its task immediately. A verified item moves to finished in the call that verifies it. The rule came from a work note acked and done without a task record, which left the queue behind reality.
- **Live steering sync**: Sync the live steering docs with refs and close a drift no gate watches. `minify.py` distributes JavaScript, CSS, HTML and Python only, so four refs amendments never reached the shipped `SKILL.md` or `REFERENCE.md`. The first sync loop compared a tree with itself, and refs and live markdown parity for skills stays unchecked.
- **State autosave**: Every committed mutation rewrites `saved-state.ndjson` beside the database, where the export once waited on a browser button. Nine mutators route through `transaction`, which refreshes the file after the commit, while construction, `set_meta`, `reminder` and both imports do not. A poll cursor is not state, a fresh database must not overwrite an older export, and a restore reads the file twice.
- **Unreachable-host quirk**: Two more hosts join the quirk: `agent-plugins.org` refuses a TLS handshake, and the Actions artifact blob host ends a signed download with EOF. `api.github.com`, PyPI and npm still answer. A schema-loading checker needs a local-copy override here, and an uploaded artifact verifies on the runner instead of downloading.
- **Markdown parity declined**: Skip the markdown parity gate: the workflow handles the live twins, so copying them by hand stays optional. `distribute-arena.yml` rewrites the `.agents/skills/arena-preview-steering/` copy in every target repository on dispatch, and `maintenance/README.md` records why the gate stays out.
- **Task-detail replacement**: A `task` call that passes one `--task-details` line replaces the whole stored list, since `repeatable` reads as append. Two finished tasks lost their details to that behavior. `references/REFERENCE.md` now states that passed detail lines replace the stored list, in refs and both live twins.
- **Copy state replaces Save state**: Turn the page's Save state button into Copy state and drop `/api/save-state`, since autosave rewrites `saved-state.ndjson` after every mutation. One click copies the cached notes and tasks as NDJSON, one JSON line per record, so a paste lands in `import-notes` and `task-import`. Report answers stay out, and the route's inbox note and shift-click glyph machinery go with it.
- **Editorial pass on 2026-09-21**: 304 fragmented bullets become 60, and the four-line summary shape merges into single bullets with bold leads kept. Raw asks go since they restate the entry above and some carried session-local note IDs, along with repeated boilerplate copies. The rewrites keep each change, its reason, its limits and its history, and only this section differs from its pre-pass state.
- **Editorial pass on 2026-09-13**: 61 bullets become 56 as correction chains and repeated recovery detail collapse into single bullets. Each keeps the change with its evidence, its questions or its reason. Every rule change and its reason stay.
- **Editorial pass on 2026-09-16**: 40 bullets become 38 as discoveries merge with what they surfaced, and gate lists collapse to four gates plus `compileall`. The token chain keeps its deltas, the seeding command returns to `maintenance/README.md`, and the retired `assets/steer.html` entry keeps what the page proved. The egress map, live-run defects, recorded hazards and eighteen-check demo scope stay.
- **Editorial pass on 2026-09-20**: 60 bullets become 20 as four-line entries merge into one bullet each and three divider titles become bold leads. Three asks keep facts only they hold: the fielded-report ask, the AMEND export-reference instruction and the markdown-it-py approval. Counting bullets caught a merge that swallowed the neighbouring PR entry, and it split back.

#### workflows

- **Init-docs consolidation**: `workflows/init-docs.md` gives each repeated guardrail one home. Uncertainty keeps the stop-and-ask procedure and interactive-versus-unattended behaviour, while Execution Mode keeps only the instruction to establish the mode up front. PLAN and APPLY obligations become prose, Core Rules keeps the cross-cutting nevers, and the catalog drops rules the sections already carry.

#### maintenance

- **Unshipped harness**: `check_preview.py` and `check_client.cjs` leave the distributed copies since nothing loads them at runtime. `check_minify.py` now runs the harness from the readable refs tree against the generated runtime. `minify.py` builds four files instead of six.
- **Minify strips docstrings**: `maintenance/minify.py` sets `remove_literal_statements=True`, and its Python parity check drops bare string statements from both trees before comparing them. The only runtime consumer was argparse's `description=__doc__`, so the help text moves to a `CLI_DESCRIPTION` constant that survives the build in both distributed copies.

#### docs

- **Restore survival, measured**: Restores and two probe sets settle what survives: tracked content as diffs against the base, unignored in-repo files and pushed commits. `/tmp`, `/var/tmp`, `/dev/shm`, `/usr/local/share` and the whole home directory reset, and `.git/info/exclude` returns to its default content. `docs/archive/arena-quirks.md` carries the rule: no sandbox path is restore-proof, so autosave cannot replace a push.
- **Restore removal list**: A probe experiment settles what a mid-turn restore removes, and a second probe tests `.git/info/exclude`. A file ignored only through `core.excludesFile` survived, as did an untracked file no ignore matched, while a file under a `.gitignore` path did not. The restore also removes `~/.gitconfig` and the global excludes file, and `docs/archive/arena-quirks.md` records the rule: survive a restore by staying pushed or untracked and unmatched.
- **CHANGELOG format**: Every entry becomes one bullet with its bold lead, and the 13 measurement tables become single Measurements bullets. Check-command bullets, standalone verification sentences, harness internals, restore mechanics, measurement chains and redundant parentheticals leave, since Git history carries them. Each date keeps one Gates green line as its verification result, and the file ends with 15 date entries and 833 bullets intact.
- **Exceptions ledger, second pass**: `docs/archive/budget-exceptions.md` keeps only the accounting facts: date, budgeted file, delta, reason and funding status. Rows that gave a delta beside before-and-after pairs now give the delta alone, chains collapse to endpoints, and unbudgeted deltas leave since no budget applies. The header states the row contract, and all 44 rows survive with their funding statuses unchanged.
- **Quirks archive, second pass**: `docs/archive/arena-quirks.md` drops the experiment and recovery detail that survived the first cut. The two token-death entries merge into one section with the observation, the sample and the rule. The restore, refresh and duplicate-message entries keep their durable rules, and the token-budget and tiktoken entries drop their probes and numbers.
- **Quirks archive**: `docs/archive/arena-quirks.md` reduces each incident to its durable observation, consequence and current rule. The restore chronology collapses to one entry, the refresh and token-budget sections keep their rules, and the Chromium procedure keeps its steps. Session-local branch names and one note ID leave the file under the artifact ban.
- **CHANGELOG neutrality pass**: The audit answers order C1-C6, the same pass on the remaining flagged lines, and the extension to owner and session mentions. The six C rows land as tabled, and lines 141, 505, 529, 537, 540, 601 and 605 take the same treatment. Narrative owner and session mentions on 23 further lines turn into actions and facts, and three first-person remnants turn neutral.
- **Note-ID sweep**: Nine session-local note-ID mentions leave the changelog: one violation parenthetical, three clause parentheticals and five receipt-format examples, each becoming a neutral placeholder. The twelve other short hex tokens stay since each resolves as a commit. `ARENA.md` bans citing session-local note IDs in repository files because they do not persist between sessions.
- Gates green.

### Removed

#### rules

- **Commit-discipline table**: `rules/README.md` drops the Commit disciplines section: rows restating the commit, list and merge rules each rule file already carries. It made a second source of truth, and no link pointed at its anchor.

#### preview

- **Clause audit**: Both steering `SKILL.md` copies drop three clauses. One stamps Seen after the write succeeds, one requires a note-ID citation, and one points at `scripts/check_preview.py`. The live copy falls under its baseline, so no exception covers it.

### Fixed

#### docs

- **Docs audit fixes**: The audit answers approve all eight rows. `rules/README.md` L103 drops the actor narrative and the exploration metaphor while keeping both verification dates. `arena-quirks.md` turns the recovery steps into proper sentences and drops the stray period, the actor narrative and one aphorism.

## 2026-09-22

### Changed

#### rules

- **Rule and preview compression**: A full live pass preserves refs baselines, constraints, code spans, numbers, links and headings, with no governing budget growing. Supporting references shrink, and the ChatGPT, Kilo overlay and Wenyan text stay unchanged where no safe cut exists.
- **Matrix and report**: The second correction round lands as dispositions 7 to 10, and disposition 6 records the house-rule resolution. `rules/README.md` gains the scope line: automations are prompts, not rules.
- **Rule change**: `rules/refs/ARENA.md` first, then `rules/ARENA.md` and its byte-identical root copy: merge by rebase only, rebase onto the target then merge, with no merge commit. The core joins after the row-2 correction: `rules/refs/AGENTS.md` first, then `rules/AGENTS.md` with merge by rebase only, and the question-tool clauses name `ask_user`. `rules/README.md` takes the matching commit-disciplines row, the Arena-file sentence and a new 13-row Platform difference matrix.
- **Resquash**: The token-budgeted live files show no further safe pass. The wenyan experiment files restore the dropped refs clauses: rung-1 explicit requirements, the final commit list, skip-restating-task, the Mermaid naming and the failing-check minimum. Both wenyan files stay under the 1,500-character field and beat the live English fields.
- **Rule change**: `rules/refs/ARENA.md` first, then squashed `rules/ARENA.md` and its byte-identical root copy. End a turn awaiting the owner only after publishing its fielded report and queueing the blocked task. `rules/refs/README.md` loses the sentence that named the dropped Cline section.
- **Ignored reports**: The parity audit, the platform matrix and the text-field form live under `reports/` as ignored sources, republished with dispositions.
- **Rule change**: Before suggesting any amendment, read `rules/refs/GUIDELINES.md` and draft the line to its section 4, one rule per line, imperative and testable. The prior one-liner only required writing rule files to the standard.
- **Visibility-question origin**: A session started the steering server and continued without the visibility question after mistaking the process tool's LIVE PREVIEW banner for confirmation. A steering note recorded that the preview only became visible at turn end.
- **Rule change**: `rules/refs/ARENA.md` first, then squashed `rules/ARENA.md` and its byte-identical root copy. A preview that never came up blocks with one visibility question before any work beyond setup. The first successful start enters the block: name the preview in chat, then ask, since the banner is not confirmation.
- **Rule change**: `rules/refs/ARENA.md` first, then squashed `rules/ARENA.md` and its byte-identical root copy. When `GH_TOKEN` dies mid-turn, block with the question tool instead of ending the turn in silence. The question asks how to proceed, never for a credential, and a new turn carries a fresh token for the next push.
- **Rule change**: The same three files take a second rule: NEVER cite a session-local note ID in a repository file. Each session mints its own IDs, so citations go to the durable record: the CHANGELOG entry, the report source or the commit. The rule sits in the Git section, root `AGENTS.md` drops the amendment-origin rule that put note IDs here, and this file stays the only ledger.
- **ChatGPT change**: `rules/refs/CHATGPT-CUSTOM.txt` takes the think-longer clause in full wording, and the squashed live file takes its compressed form.
- **Resquash**: The compression procedure runs across `rules/` with a waiver of its line-scoped rule. `COMMIT-SPEC.txt` gives back nothing since its refs baseline exempts it from compression, and `CLINE.md` and `ARENA.md` sit near their floors. The wenyan experiment keeps its lead under the live fields, and the pass restores four lost clauses, among them the think-longer rule.

#### preview

- **Cadence update**: Change the steering check cadence from appending a read to the last shell command to always including a poll in bash calls. Update the steering skill refs baseline, live skill, installed mirror, Arena refs and live rules and root `ARENA.md`.
- **Task status**: Remove the extra explanation after the updated timestamp. The client regression failed before the change and passed after it.
- **Composer preview**: Preserve paragraph newlines with scoped `white-space: pre-wrap`, without adding double-spaced `<br>` tags. Both the Python regression and real Chromium check failed before the CSS change, then passed. npm `@sparticuz/chromium` 153.0.0 supplied the binary and runtime.
- **Shift copy icon**: Show the copy icon while Shift covers Save state. Key release, pointer leave and window blur restore the save icon, and copy feedback keeps its timer before it uses the current modifier state. Red and green client checks cover the transitions and timers.
- **Multiple uploads**: Allow multi-file selection, and check the whole selection before requests. Send each file through the existing API, block duplicate batches, and report completed files on partial failure. Preserve the single-file receipt and per-file limit, with client checks covering all paths.
- **Report read time**: Reduce the short-report dwell from five seconds to one. Keep end-of-scroll marking and cancellation on tab exit. The timing regression failed before the change and passed after it.
- **Edited replies**: Preserve the first receipt time and stamp changed answers with `ack_edited_at`, while identical retries and first answers stay unedited. Show a local-time Edited label, a Notes dot and a New edit jump link without moving messages, and keep viewed-edit state browser-local across reloads. Save and import carry the edit stamps, with regressions covering changes, retries, restores, filtering and same-second edits.
- **Left borders**: Match report questions and report blockquotes to the reply border color `rgb(199, 194, 188)`, with widths and spacing unchanged. A scan finds no other unmatched left border.
- **Custom answers**: Require a labeled custom-response field with every option set in both preview skills. Refs carry full wording and the live and installed copies carry the compressed clause.
- **Reminders**: Omit zero counts, the total, and the read and ack sentence. Print only nonzero kinds as requested, followed by Manage the task list. Empty, message-only, form-only and mixed-upload cases pass without Seen changes.
- **Unanswered forms**: Keep the report star and tab dot until the owner submits the form, even after reading, and let optional blanks count. Server state preserves markers across devices, and republishing requires a fresh answer. Plain reports stay read-only, and invalid legacy fields remain visible as errors without breaking the state endpoint.
- **Documentation compression**: Two reviewed passes reduce nine maintained README and docs files by 14.6%, with code spans, numeric values and link targets intact. No third-party prose changes, and historical observations stay with their retractions.
- **Reporting dependencies**: Preauthorize `markdown-it-py` installation for the reporting skill in a workspace venv, with no separate approval. Keep skill-only packages out of application manifests and generated `requirements.txt` unless the application independently needs them. Ref, live and installed instructions agree.
- **Audit L8**: Update CI coverage in the rules README and house instructions: main-branch pushes and PRs targeting any branch, subject to ignored-path exclusions. Only qualifying main pushes commit refreshed README measurements.
- **Inbox-poll lapse**: A turn ended without an inbox poll, so 13 items, two violation call-outs and eleven directives, never arrived mid-turn. The rule changes went into a fielded report with one queue task per blocked item.
- **Rule change**: Root `AGENTS.md` Git says merges MUST be rebase merges: rebase onto the target, then merge, with no merge commit. GitHub restricts the repo to rebase merge only, and the line matches the core and Arena copies.
- **Pending amendments**: A fielded report proposes A1 to A9 with answers Q1 to Q9. The list covers turn-end read hardening, the restart notice, the Arena turn-end PR CI check, the Arena mermaid split and preview no-mermaid. It also carries the core merge-authorization clause, the terse line, the row-7 cell mapping and the CLI inbox reminder per subcommand.
- **Upload notice origin**: A lost-upload incident caused the change: the uploads list renders only in the browser, so no signal showed that bytes arrived.
- **Upload notes**: `preview.py` writes an inbox note after every successful `Store.save_upload`, naming the file, size, content type and stored path under the upload's ID. Only a token-authenticated upload creates the note, while a refused one creates neither record nor note, and the harness pins its ID and text.
- **Uploads docs**: A new Uploads section in the steering SKILL.md records the read-then-ack contract, and `references/REFERENCE.md` takes the Uploads-tab paragraph.
- **Rule change**: Preview confirmation is session-scoped: every session's first successful start blocks, and only a same-session restart after its own confirmation needs no ask. Refs take the full wording first, then live, then the byte-identical root copy.
- **Amendment-drafting rule**: The house rejected a too-specific draft, so the house rule now requires `GUIDELINES.md` before any amendment suggestion. The record also fixes why root `AGENTS.md` differs from the core, why `.agents/skills` needs no squash mirror and why `web-interface-guidelines` has no refs baseline.
- **Origin-task note**: Some preview times ignored the user timezone, and `origin` leaves the preview skills' JSON schema entirely while `SKILL.md` `metadata.origin` stays.
- **Skill change**: The preview process takes one standard name, `{repo} - Steering`, so every session labels the same preview the same way.
- **Note IDs**: `assets/app.js` mints a note ID as seven hex characters, a hyphen, then the remaining 25. A cited prefix is now a whole visible segment.

#### docs

- **Chromium**: Move the standalone guide into `docs/archive/arena-quirks.md` with its environment variable and font limit labeled, and remove `docs/chromium-e2e.md`. Add the approved npm and extracted-runtime rule to the Arena refs, live and root copies. Only the new rule line compresses, and the owner approved the growth.
- **Evidence**: `docs/archive/arena-quirks.md` takes two observations: a same-turn retry does not bring a dead token back, and the token returns with the next turn. Context exhaustion loses every unpushed commit, which is why this branch pushes after each commit.
- **Rule amendments**: The core takes two rules: no unnecessary code or config comment, and terse but unambiguous comments, docs and responses. `ARENA.md` makes the smallest-task-first rule unconditional and ends a turn when the work passes verification and stops, since no surface reports the remaining budget. Root `AGENTS.md` defines house as this repository and requires every `README.md` and `docs/` file to be squashed, with the refs baselines exempt.
- Gates green.

### Removed

#### rules

- **Approved follow-up**: Remove merge policy from the generic core while Arena and ChatGPT keep platform-specific merge rules, and omit the proposed loading-path matrix cell. Add the final inbox-read requirement, preview-restart notice and no-mermaid rule for preview reports, while Arena keeps its PR CI check before turn end. Steering 2.1.0 prints unacknowledged counts and the task-list duty on stderr, and the runtime harness covers the reminder, JSON compatibility and count behavior.

#### preview

- **Origin removed from notes**: The note schema loses `origin` end to end: `Store.note()` drops the author, `NOTE_LINE_KEYS` drops the key and the CREATE statement drops the column. A migration removes a leftover `origin` on reopen, and the client stops rendering the uppercase agent tag so receipts read ID, state, time and task. `import-notes` ignores the key an older save carries, and the references record the removal in both directions.

### Fixed

#### preview

- **Seen fix**: Reproduce a failed inbox-output write that still stamped Seen, then make `read` non-marking with atomic per-ID `seen` receipts after full delivery. Counts and browser polls stay read-only, and acknowledgements still imply Seen. Cover failed delivery, rollback, late arrivals, report answers, repeat receipts and CLI dispatch, and update the skill contract.
- **Report refresh**: Reproduce a render of the selected report when a different one changes, and reload only on its ID or version change. Retain its content while a real update loads. Client checks cover unrelated publication, CLI reads, current-report updates and explicit refresh.
- **Documentation corrections**: Align renderer startup requirements, Markdown report delivery, field-only questionnaires, assert-based checks, platform-specific merge rules and the one-second read-delay comment with current code. Apply the approved corrections to refs, live files and installed mirrors.
- **Audit M5**: Reject incomplete HTTP bodies before parsing or saving them. Half-closed uploads with partial or empty bodies receive HTTP 400 and create no file, upload record or inbox note. Exact-size uploads remain covered.
- **Audit M6**: Save notes before the first task exists. Normalize absent or null task lists to empty groups in the server save path while rejecting malformed values. The client now permits notes-only saves, with coverage for persistence, malformed-task rejection and the save button.
- **Audit H3**: Require the full revision from rendered report responses on form submissions, then check it and save the answer in one write transaction. Reject stale forms with HTTP 409 and missing revisions with HTTP 400, while keeping unsent entries during automatic updates. An explicit refresh loads the new form for review, with coverage for revisions, retries, transaction boundaries, payload binding and retained entries.
- **Preview fix**: The `#send-status` save line formats the server stamp through the client's `time()` helper, which pins a seconds-only ISO stamp to UTC. The status line then reads the viewer's timezone instead of the server's wall clock.
- **Correction origin**: The round applies form corrections for rows 2, 5 and 7 plus a steering note on the `.state-dot` margin. This entry reconstructs the ignored reports lost with sandbox state, with the corrections applied.
- **Preview fix**: The Upcoming list no longer re-renders the head task, which already has its own Current div. The client refs take `upcoming.slice(1)`, the harness pin flips to a two-task fixture, and minify rebuilds both distributed copies.
- **Timezone fix**: The state surface cuts stamps to seconds and drops the UTC offset, so `Date` read those digits as local time outside UTC. `time()` pins a seconds-only ISO stamp to UTC before the local formatter sees it, so receipts, last-check, tasks and uploads convert into the viewer's timezone. The header clock needed no change, since it formats through `toISOString()`.
- **Null-tasks copy fix**: `Store.tasks()` returns `None` before any task exists, so `/api/state` sends `"tasks": null` while a session holds notes only. The page cached that value and the shift-click guard blocked the copy, so `restoreCopy` defaults the queue to two empty divs. The client harness mocked the empty queue and crashed on the empty clipboard, which was the red gate on the parent branch.

## 2026-09-21

### Added

#### rules

- **PowerShell rule for Kilo**: `rules/refs/KILO.md` gains the shell rule under Tools and `rules/KILO.md` carries it compressed: run shell commands in PowerShell (`pwsh`), not Bash. No mode override or installed rule changes. The live rule grows, and the README measurement and the ledger record the accepted growth.
- **Turn rule**: `rules/ARENA.md` gains one General rule: keep working while budget remains, and end the turn only on budget exhaustion or strict attention. The turn says in one line which it was, and `rules/refs/ARENA.md` carries the full wording with the waiting-report and queued-task reasons. The root copy follows byte-identical.
- **Summary**: `rules/ARENA.md` gains one General rule: with several tasks open, do the smallest first, a user-stated priority outranks size, and re-sort whenever a task arrives. `rules/refs/ARENA.md` carries the full wording, which adds that a large task never blocks a small one. The root copy follows byte-identical, as `.github/workflows/distribute-arena.yml` expects.
- **Summary**: The steering bullet in `rules/ARENA.md` gains two clauses beside the ack contract: the receipt leaves in the read's own tool block. The receipt covers work that outlives the block as in progress, runs one to three lines and names the change and its commit. `rules/refs/ARENA.md` takes both in full wording, and the root copy follows byte-identical.
- **Summary**: `rules/ARENA.md` gains one Git rule: `GH_TOKEN` can expire inside a turn, `gh auth status` calls it invalid and pushes fail. Retry once, never loop and never ask for credentials, then end the turn, because the next turn carries a fresh token. Prove recovery with `git ls-remote origin <branch>` before pushing again, while `rules/refs/ARENA.md` carries the full wording and the root copy follows byte-identical.

#### preview

- **Receipt dot and task marker**: The receipt line gains the requested ASCII dot after the ID, so it reads `<id> · ● · Sep 21, 18:51`. A message that became a task says ` · Task added` with the task ID in the marker's title, and `task` takes `--msg-id <message id>`. Task and marker land in one transaction, so an unmatched message ID never creates a task.
- **Summary**: The steering skill's ack contract gains one rule: name a note by its ID's first seven characters, never by its sequence number. `ack` takes the full ID that `read` prints, and `references/REFERENCE.md` records the convention with one exception: reports keep their earlier title numbering. Seven characters of a UUID collide only after some 16 million notes, and the full ID stays the key in `ack` and storage.

### Changed

#### rules

- **Loader-rule dedup and the preview state copy**: `rules/CLINE.md` loses its `Use` section, `rules/AGENTS.md` its description line, and `rules/KILO.md` keeps `Tools`, since loaders restate those sections. The refs baselines mirror the wording, and `skills/squash/SKILL.md` takes the register line Terse but unambiguous. The preview reply gains a coloured left bar and seconds-only stamps, and the shift-click copy matches the save file's keys.
- `rules/README.md` is rewritten in ASD-STE100 and joins the CI gate, which then names eight clean files, with every command, path and number surviving. The root `AGENTS.md` gains a second answer: a third-party copy stays outside the linter's scope, so the vendored README is never rewritten. The chain-linking rule on word pairs forced one wording change: the file points at `.github/workflows/` as a directory rather than naming its file.
- Fifteen bullets over 220 characters, five in `rules/refs/AGENTS.md` and ten in root `AGENTS.md`, now lead with their rule and carry the rest as sub-bullets. The approval declined section renames and ceiling markers, so only the wrapping changed: no rule gained, lost or moved meaning. The compressed live mirror `rules/AGENTS.md` takes no change, so refs and live parity holds.
- The house copies `danyuchn/asd-ste100-skill` at `7d4a135` into `.agents/skills/asd-ste100/` under its MIT licence, recorded as a third-party audit tool. `ruff.toml` excludes the directory, because the house copies vendored code verbatim and never reformats it, and markdownlint's scope already stops at `rules/**/*.md`. The linter runs report-only per the approved scope, and its first run flags a 46-word sentence in root `AGENTS.md` alone.

#### preview

- Small preview interface changes, each verified by the client or runtime harness. They cover receipts, state dots, theme and focus borders, composer growth, log spacing, filters, report scroll, copy buttons, task-list presentation, uploads, chips and edited-reply markers. Git history carries the per-change costs.
- **Steering reference compressed**: The distributed reference drops 83% and keeps invocation and state, read and ack, task commands, links, report publishing and recovery. `--msg-id` verifies against the CLI and `Store.mark_task`: task and link writes share a transaction, and an unknown ID fails both. Both delivered copies match, and the guide no longer asks agents to run the string-pinning check against minified assets, which stays in refs and CI.
- **Queue-rule amendment**: Two bullets land after instruction precedence in the steering entry point: read `task-list` at turn start and record approved work before implementing. Update the queue on scope or status change, finish with `--status finished` and route inbox work through `--msg-id <full-message-id>`. Queued stays neither acknowledged nor complete, so `ack` remains required, and the comparison shows only the two approved clauses landed.
- **Copy buttons consolidated**: The log copy button and the tasks copy button go away, and the save button carries the copy instead. A shift-click puts the page's cached state on the clipboard as minified JSON, and the reports tab keeps its own export copy. Neither path nor file leaves the page, and the harness pins the minified JSON, the empty-cache message and a copy that restores the button name.
- **Two restores in one turn**: The pasted log imported as 51 notes and the task list came back to 54 records, one per ask. One ask never landed: a turn-rule amendment never reached `ARENA.md`, and a fielded report carries the wording for approval. An upload through the new tab verified byte for byte, and a save-state press produced `saved-state.ndjson` that imported into a fresh state directory.
- **One poll path**: Notes read and answered while their dot stayed gray, since ad-hoc paths counted pending without marking seen. The settled design gives one CLI command charge: it is the only poll and the only path that stamps `seen_at`. `REFERENCE.md` gains the same fact, and the limit is that an instruction is not enforcement: nothing stops the next agent from calling `state()` directly.
- **A retraction kept beside its claim**: An entry shipped as `dad5ce1` claimed a reset variant Arena never performed, and a duplicate arrived again. The sub-entry becomes a record of the mis-inference instead of a deletion, keeping the verified parts: the identical-HEAD checks, the durable-source recovery and `mergeable=UNKNOWN`. The added rule is about evidence: when a message is the only evidence for a behaviour, ask whether it is the evidence or the event.
- **Five restored notes answered**: Three are layout: `#history-title` stands alone with `#connection` and `#last-check` stacked to its right, so the header drops to two rows. The composer's first and last rows lose their margin, and the requested `:nth-child` selectors landed as `:first-child` and `:last-child`. A fourth note amended the archive around refresh-caused sandbox resets, and a fifth warned that Arena may duplicate a message.
- **Summary**: The tasks copy drops pretty-printed JSON for minified JSON, because the agent parses it and whitespace costs tokens. The log copy needed nothing, since it was already one minified object per line in the shape `import-notes` reads, and the reports tab copies Markdown. `REFERENCE.md` now records the choice beside the button descriptions, and an older pretty-printed backup still restores.
- **Summary**: The live agent task list arrives as its own tab with two divs, finished and upcoming, beside Notes and Reports. `preview.py tasks <source.md>` replaces both sections from one Markdown file whose `## Finished` and `## Upcoming` headings are both required in either order. Each section renders at write time into the `meta` table, and `/api/state` carries the pair so the tab refreshes on the three-second poll.
- **Summary**: The accent bar and muted colour return from `.message` to `.answer.reply`, and the message block keeps its original padding and radius. The reply carries the bar it had plus the colour from the plain-note class, and every acknowledgement is a reply since the answer classes collapsed. Plain text still goes into a `<p>`, an unanswered message carries no bar, and nothing pins the visual result beyond the rule text.
- **Summary**: Two follow-ups to the log styling. Inline code takes a new `--chip` colour, one step off every surface, and the receipt ID opts out by class. The two answer styles collapse into one: `.answer.note` goes away, every acknowledgement renders as answer reply, and plain text goes into a `<p>`.
- **Summary**: The left bar and muted colour moved onto `.message` itself, so every `li.message` reads the same whether it carries a report, a note or nothing. `.answer.reply` loses its own bar, because keeping it would draw a second bar inside every answered message. A rendered reply inside a message turns muted too, and a message with a question shows two bars at different indents.
- **Summary**: The workflow installed `tiktoken` and `markdown-it-py` from scratch on every run, and an `actions/cache@v4` step now sits between `setup-python` and the first install. It caches `~/.cache/pip` under a key hashed on the workflow file, which covers the ruff install too, and the run stays whole-repo and speeds up. The cache waits for its first Actions run, so the first evidence it works is the next push's timing.
- **Summary**: A note suggested that `--port` default to 8000 so `preview.py serve` can be called bare. It already did: the argument carries `default=8000` and `serve --help` lists the flag as optional. Documentation wrote the command as `serve --port 8000` everywhere, so the command table now reads `serve` with the port defaulting to 8000.
- **Summary**: Once a note saves, `#send-status` reads Saved 3:14:17 AM · awaiting acknowledgement, which describes the agent's obligations rather than what the user just did. It now reads Saved 3:14:17 AM · Message sent, matching the receipt's Sent, and the retried-send branch keeps its wording. The Reports panel still says awaiting acknowledgement after an answer goes out, which no request asked about and which stays as it was.
- **Summary**: Two owner complaints about the same page. The selected tab kept `border-color` `var(--accent)` even under focus, so tabs rest on a new `--tab-border` and `nav button:focus-visible` restores `var(--focus)` at a winning specificity. In the Reports panel the rule under the toolbar hugged the form, so it now has 12px above and `margin-top: 24px` on `#report-form` below.
- **Summary**: Seen now means the agent read the message, while `read` stamps a new `seen_at` column on every unacknowledged note it returns. `/api/state` carries the column, and the browser reads Sent until `seen_at` lands, Seen after, and Said once an acknowledgement lands. The browser's own poll deliberately stamps nothing, or every note would read Seen whether an agent looked or not.
- **Summary**: The receipt's state word was `Delivered` while a message waited and `Seen` once acknowledged. It now reads `Sent` while no ack exists, `Seen` for a plain-line acknowledgement and `Said` for a rendered reply. One expression over `acknowledged_at` and `ack_kind` picks the word, so the log separates an agent that read a note from one that answered it.
- **Summary**: The previous entry printed the entire ID in every receipt, and a bug report arrived within the hour. The receipt is back to `item.id.slice(0, 7)` and the whole ID moves into that element's `title`, so a full ID is one hover away. `boundedId()` comes out entirely, and the harness now drives a real UUID through the log to pin the truncated text and the tooltip.
- **Summary**: The Copy button works in the real preview, the first browser evidence on it, and the owner asked for an icon. The word is now `⧉` at rest, `✓` on success and `✗` when both clipboard paths fail, with the words in `aria-label` and `title`. The button is a 26px square like the other icon buttons, and a code block's right padding drops from 62px to 40px.
- **Summary**: A hand-quoted citation came out at eight characters, so the receipt renders the first seven, a hyphen and the remainder through `boundedId()`. The rule's boundary shows in the render, the whole ID is there to copy, and short IDs come back unbroken.
- **Summary**: The growing textarea shipped with two faults reported as P1. The `.notes-layout` move to `min-height: 100%` unbounded the layout, so the bound is back and growth pushes the log upward. The border-box trap goes too: `scrollHeight` excludes the 1px border, so growth now adds the 2px back and textareas hide their overflow.
- **Summary**: Three later requests took the simpler line over the previous explicit `h3`-to-`h6` sizes: every heading keeps the browser default. The four new rules are out, and `h1`'s clamp and `h2`'s 19px went with them, so the scale descends and clears the 0.28px collision. `h1` keeps its `-.035em` letter-spacing and `h2` its margins, and a comment in the stylesheet records the defaults and the collision they replaced.
- **Summary**: `h2` carried an explicit 19px and `h3` carried nothing, so the two levels read as one size 0.28px apart. `h4` to `h6` fell back the same way, to 16px, 13.28px and 10.72px, which put `h4` at body text. All four now carry explicit sizes descending from `h2`: `h3` 17px, `h4` 16px, `h5` 15px, `h6` 14px, with a comment naming the fallback they replace.
- **Summary**: A fielded report answered through the slot itself, and the 200-character cap cut that answer off mid-word, which settled four changes at once. Typing in a slot now checks its radio or checkbox, blanking the text lets go again, and the label moves into the textarea's placeholder. The typed cap rises from 200 to 2000 characters, matching a whole text field.
- **Summary**: The composer's textarea loses its resize handle and grows with the draft: `grow()` sets its height from `scrollHeight` on every input. Nothing caps it now, since `.compose` loses its 48% ceiling and its own scrollbar, and the notes panel scrolls as a page instead. `.log-card` keeps a 200px floor so the log cannot be squeezed out of existence, and `#history` still scrolls in place inside that floor.
- **Summary**: An option written `Label: ___`, or a bare `___`, is now a free-text slot instead of a fixed choice. `custom_label()` reads the label through the `BLANK` pattern and `prompt_text()`'s colon stripping, and `field_html()` renders the control beside a 200-character input carrying `data-label` and `data-custom`. `custom_answer()` checks that form server-side, and `validate_fields` refuses two slots sharing one label in a group.
- **Summary**: Every fenced code block now has a Copy button in its top-right corner, and `add_copy_buttons()` holds its text in `data-code`. One delegated click handler reads that attribute, tries `navigator.clipboard.writeText` and falls back to `execCommand`, flashing Copied or Select and copy for 1.5 seconds. The block becomes the positioning context and its `pre` keeps 62px of right padding so code does not run under the button.
- **Summary**: Inside `li.message` the second and third children swap roles on approval: the answer sits under the user's note, receipt last. Two assignments in `assets/app.js` carry the change, and spacing follows: `.answer` takes 8px above instead of 10px, `.receipt` gains 8px. A hidden answer still holds its place in the DOM, so the receipt's gap never collapses against the message text.
- **Summary**: The chip rule loses its `.report` scope, so raw messages, field options and the composer's draft preview chip like a published report. The message-log receipt IDs are the one exclusion: `.receipt code` keeps its monospace face and drops the background and padding, and it needs no `!important`. Code inside a `pre` still takes no chip of its own, the block carrying the background.
- **Summary**: `p#report-status` moves inside `div.report-toolbar` on its own row with the muted 13px face, so it can no longer pass as the report's first line. It also carries the submitted state: Answers sent `<time>` with a stored answer record, and Report loaded with N fields before one exists. The post-submit message shares that wording and the single `time()` formatter, replacing a `toLocaleTimeString()` call that printed seconds and a 12-hour clock.
- **Summary**: `#preview-note` inverts its states on approval: dim with the draft preview shut, lit while it opens, and a lit button means the preview shows. The pencil keeps the opposite mapping, grayed while the composer is hidden, because a hidden composer is the state worth marking there. `aria-pressed` and the `MD 👁` label stay the same, so the state stays available to a screen reader.
- **Summary**: Inline code in reports and rendered log messages now chips with the bubble background, 1px by 5px of padding and a 4px radius. That also fixes the reported bug: a fence closed on its opening line becomes an inline code span that never reaches the `pre` background. Code inside a `pre` keeps no background of its own, and the receipt's monospaced ID sits outside any `.report` element, so it takes no chip.
- **Summary**: Rendered Markdown keeps one heading rhythm: all levels take 10px above and 6px below, with the report's first child flush to the top. `.report pre` padding drops from 16px to 10px. One margin for every level means a deep ladder no longer reads as stepped by spacing, only by font size.
- **Summary**: The message-log receipt rewrites on approval: the 7-character ID leads, monospaced in a `code` element, then one state word and the delivery time. A waiting note reads `<id> · Delivered` and an acknowledged one `<id> · Seen`, while the ACK-ed pair and separate ack timestamp are gone. The last-check line reads Last checked `<time>` or Not checked yet, without naming the agent, and Seen carries the delivery time.

#### maintenance

- **Script minification**: `minify.py` builds all three scripts and the assets with pinned minifiers, and the approval covers the installed mirror. Terser handles CommonJS, and Python minification removes ordinary comments and excess whitespace with every AST transform off, so names, annotations, docstrings, assertions and shebangs survive. A Python 3.10 grammar check, parsed-tree equality and compilation gate the outputs before any write, and CI pins Python 3.11 while keeping Ruff on refs.
- **Asset minification**: The approved scope is JavaScript, CSS and HTML only, with a pinned minifier per language and a size budget per file. `minify.py` builds the three assets from readable refs baselines into both distributed directories, and the build refuses JavaScript that Node cannot parse. The client harness passes against the shipped minified build, and markup that loses an id or a visible word never lands.
- The Simplified Technical English clause binds new and edited text now, and each covered file joins the CI gate once a pass clears it. `maintenance/README.md` led the path from 10 violations to 0, and the workflow grows its file list one clean file at a time. The remaining five stayed report-only until their own pass, with first-run counts of 13, 7, 56, 11 and 68.
- The documented markdownlint file count had two carriers, and `LINT_COUNT_CLAIMS` cross-checked both against the files markdownlint actually covers. The root entry is gone, which keeps `check.py` off agent-facing files, and the gate still fails when the scope itself moves. What goes is the second copy of the claim, so the "— 10 files," wording in root `AGENTS.md` is now wording nothing checks.
- **A runnable `check.py`**: The gate stayed unrunnable since the first restore, and `maintenance/README.md` held the seed path: the `cl100k_base` cache comes from a byte-identical mirror. Seeding from `niieani/gpt-tokenizer` through the GitHub API with the raw accept header fetched 1,681,126 bytes, and the validator passed on the first attempt. The repo keeps `.tiktoken-cache/` out of history, and the mirror stays neither vendored nor pinned: an upstream change fails the hash and stops the gate.
- **Summary**: `--focus` in the dark theme becomes `#524d47`, replacing `#f4ca93`, so `:focus-visible` changes a resting `#56504a` border into a nearly equal value. The light theme keeps `#8f5b13`, which the request did not name. The page carries no focus outline, so this border is the only focus cue it offers.

#### docs

- Editorial passes bring every covered file to zero ASD-STE100 violations, and the CI gate grows as each file lands. The covered files are `docs/archive/arena-quirks.md`, `.agents/skills/README.md`, `rules/README.md`, `rules/refs/README.md` and the budget-exceptions and workflow READMEs. Dates, commands, numbers and filenames survive each pass, and the vendored `.agents/skills/asd-ste100/README.md` stays outside the gate.
- `rules/refs/README.md` is the ninth file in the CI gate and the last covered file the agent can clean. Every `README.md` and everything under `docs/` now reports zero violations except the vendored `.agents/skills/asd-ste100/README.md`, which an approved answer exempted. The refs index loses three semicolons and two sentences over the cap, and it keeps every filename, commit, section number and platform note.
- Root `AGENTS.md` names the vendored ASD-STE100 linter and its scope, on an approved answer: `docs/` and every `README.md`, and nothing else. The clause binds text written or edited in those files from here, and older prose keeps its wording until someone touches it. Rules, skills and agent-facing files stay outside the linter's scope, which leaves the 46-word sentence in this file out of it as well.
- The house copies `DietrichGebert/ponytail` at `e3ba2aa` (MIT) verbatim into `.agents/skills/ponytail/`, six skills and licence included. It lives under `.agents/skills/` only, because it audits this repository rather than belonging to it, and takes no part in the parity gates. The audit tool is `.agents/skills/ponytail/skills/ponytail-audit/SKILL.md`.
- **Summary**: The approved docs restructure is in: `docs/archive/` now holds `budget-exceptions.md`, moved with `git mv` so its history follows, and `arena-quirks.md` with eight hosting behaviours. `README.md` and `AGENTS.md` name the exceptions file by its new path, every relative link under `docs/` resolves, and undated observations say so. No budget covers these two, and the quirks file stays a record rather than a control, with no archive index saying what belongs there.

### Removed

#### maintenance

- **Summary**: The house removes `check_skill_refs_parity` from `maintenance/check.py` on approval, together with its call in `validate()`, so nothing compares `skills/refs/<skill>/` against `skills/<skill>/` byte for byte. `skills/README.md` amends its wording to the new contract: supporting files keep their refs form and compress or minify to live. Rule refs and live parity and the root `ARENA.md` byte identity take no change, and `maintenance/README.md` needed no change.

### Fixed

#### preview

- **Four preview fixes together**: `/api/state` hands the page its write token, so the save button lands after a sandbox reset with no browser refresh. The retry's page reader accepts either quote style because the build ships minified, and the token rides the page as an HTML attribute. The log filter drops the native dropdown chrome, a code block carries its background wherever markdown renders, and a paragraph carries no `<br>`.

## 2026-09-20

### Added

#### rules

- **ntfy transport by selection**: The visibility question gains an external-channel option. On selection the retired ntfy transport runs with topic `<repo>-<branch>-<8-char unguessable secret>`, posts notes and polls `https://ntfy.sh/<topic>/json?poll=1&since=<marker>` at every read. The first poll uses `since=all`.
- **Wenyan experiment**: `rules/wenyan/` gains hybrid-Wenyan ChatGPT candidates built from live English as the character-count baseline and full refs as the semantic baseline. The experiment stays unvalidated and non-authoritative with no production rules, refs or validator changes. It measures Unicode characters only.

### Changed

#### rules

- **ASD-STE100 becomes MUST**: The rules require it everywhere they define it — `rules/CHATGPT-MORE.txt`, `AGENTS.md`, `ARENA.md`, `rules/AGENTS.md`, `rules/ARENA.md`, both refs originals and `rules/wenyan/CHATGPT-MORE.txt`. `ARENA.md`'s Git bullet loses the "offer portable HTML" clause.
- **Export**: Export wording leaves `ARENA.md`, `rules/ARENA.md`, `rules/refs/ARENA.md` and `AGENTS.md`.
- **Root AGENTS compressed to lines**: Three multi-sentence lines compress per `rules/refs/GUIDELINES.md`. L61 drops both rationales, L67 moves to its own line with the file's `NEVER` cap and L95 loses its `so` and `because` clauses.
- Every rule, negation and fact survives, and `rules/` and its refs stay untouched.
- **PR, rebase merge, green tests**: ChatGPT custom rules require a PR, a rebase merge and green tests before any turn ends. They replace the conditional PR rule that contradicted them.
- **Origin**: The 2026-09-20 chat asked for `NEVER end turn until tests are green`, `ALWAYS PR` and `ALWAYS rebase merge`.
- Project history runs newest first, one entry per pull request with the open entry extended until merge. Each entry opens with at most three summary bullets — change and deferred. Entries below 2026-09-12 keep their older form.
- [README.md](README.md#instruction-budgets) carries current measurements.
- **Merge wording**: The approved Arena merge wording becomes `fast-forward/rebase`, with merge authorization and rebase-first-on-divergence unchanged.
- `ARENA.md` refs, live and root plus root `AGENTS.md` adopt the preview inbox and report pipeline with work-boundary reads and literal `ACK:`. Setup starts the server, blocks on the visibility question, then reads the answer, and a visible preview reuses without asking. Failed reads error instead of reading empty, acknowledgement records only visible-chat IDs, and the experiment's 21 saved notes import without ID changes.

#### preview

- **Chat surface**: The page drops its `h1` and eyebrow. Tabs, the theme button and the collapse toggle move to a viewport-pinned top bar. The log sits above the composer.
- **Log behaviour**: The log fills the height between bar and composer, scrolls oldest-first in place and pins to the newest message unless scrolled up. It re-pins when the composer reopens, and a second toggle hides the composer.
- **Toggles**: Both toggles persist per browser with the theme.
- **Renderer probe at startup**: `serve` probes `markdown-it-py` and exits with the install command plus a venv reminder instead of serving raw text. `read`, `ack` and `publish` need no renderer.
- **Probe history**: A prior banner-and-disable design came and went at request. A renderer that breaks after boot still falls back to raw text with no re-check while the server runs.
- **Acknowledgements join the message log**: `ack` requires an answer. `--reply <markdown>` renders as a log message, `--note <text>` prints one line under the receipt, and a bare `ack <ids>` fails.
- **Stored receipts**: Notes store `ack_kind`/`ack_text`, `/api/state` serves `ack_html`, and a repeat keeps its first timestamp. Report answers leave the log for a `submissions` table. `read` merges them as `kind: report`, `ack` accepts either table's IDs, and `/api/state` serves notes only.
- **Report questions**: The Reports tab shows a `✓ Sent` receipt. Questions go to fielded reports, and every shell block ends with a read.
- **Sent report answers stay on screen**: The client stores `{answers, at}` under `answers:<report id>` and pre-fills that report. It shows `✓ Sent <time>` beside Send answers, and `.report h1` margins tighten to 8/12.
- **Forms fold into Reports**: The JSON path leaves — `publish-form`, the `forms` table, form routes, the Forms tab, the `FORM` note header and the 2–20-option floor. A questionnaire is now a fielded report whose answers arrive as `REPORT` notes.
- **Folding details**: `Store.validate_form` becomes `Store.validate_fields`, `submit` drops its label, the note textarea keeps its own placeholder, and the page retitles to Notes & reports.
- **Fields in report sources**: `parse_fields` splits prose and fields: `- ()` radio, `- [ ]` checkbox, `Label: ___` text, `(x)`/`[x]` preselect. The prompt comes from the line above or an explicit `{#id}`, and fenced code stays literal.
- **Routes**: `GET /api/reports/<id>/html` returns JSON (`html`, `fields`). A token-protected `POST /api/reports/<id>/submit` writes one `REPORT` note, and the tab renders one Send answers button.
- **Export subcommand leaves**: The standalone HTML export subcommand, route, builder and docs leave because sandbox attachment downloads never showed a file.
- **JSON forms, first cut**: `publish-form <form.json>` checks 1–50 questions of `text`/`choice`/`checkbox`, prompt ≤500 chars, 2–20 options ≤200 chars and file ≤256 KB.
- **Form answers**: The Forms tab posts token-protected answers (text ≤2000, one choice, checkbox subset) as one `FORM` note with `(skipped)` gaps. Bad answers return 400 and keep input.
- `check_preview.py` and `node scripts/check_client.cjs` stay green.
- **Quiet cases**: Quiet cases, the signature-error ladder (retry once, fresh topic, turn pause) and the JSON-to-HTML fallback restore from commit a50d3c5. The preview server and inbox stay up, and the choice is that session's approval.
- **Preview-steering 2.0**: `arena-live-steering` becomes `arena-preview-steering` 2.0.0 beside new `arena-preview-reporting` 1.0.0. One server exposes Notes and Reports tabs, persistent messages with receipts, duplicate-safe retries, Enter-to-send with Shift+Enter/IME and a default-dark theme. Named reports ship with standalone HTML export.
- The visible proposal authorized `markdown-it-py`, installed-copy migration, report-commit removal and historical documentation.
- Both remain history in the migration reference and Git, neither a fallback nor a ban. Reports, exports, inboxes and receipts now stay ignored and uncommitted.
- The runtime uses stdlib HTTP and SQLite. Only `markdown-it-py` renders Markdown, installed in a workspace venv and never in the app manifest. An owner-approved Write / Preview toggle reuses it for unsaved drafts with the last-message placeholder and Send confirmation intact.
- Raw HTML stays off, report paths register explicitly, submissions bound, retries dedupe, and no secrets belong in the inbox.
- The tracked `.agents/skills` mirrors migrate with approval and match their sources without baselines. The dispatch workflow distributes both siblings and removes the retired directory. Input repo names pass through an environment variable rather than shell interpolation, with no external repository changes.
- Markdown links open with `target="_blank"` and `rel="noopener noreferrer"`, and the log renders Markdown with stored text unchanged plus a raw-text warning when the renderer is absent. Browser attachment downloads returned 200 with no visible file, so a diagnostic question removed the browser download and source controls while agent-side export stayed. The browser restriction stays unconfirmed, and forms stay a named follow-up with no implementation.
- The budget generator rebuilds its table from `EXPECTED_BUDGETS`, handling added and retired skills without hand-edited rows. CI also runs the stdlib preview integration check and the dependency-free simulated-DOM client check.
- Page-fetch reads the owner's CSS paths where sandbox curl fails at TLS. Only the supplied palette loads, not Arena's stylesheet or fonts. The two-path verification rule survives, and the image path stays untested.

### Removed

#### preview

- The ntfy transport with page-fetch polling and local ingestion logs retires. So does the report pipeline's force-added local `chore(reports): hold the local records` commit that never pushed and undid itself next turn.

## 2026-09-19

### Added

#### rules

- **NEVER-edit clauses**: `rules/ARENA.md` Constitution gains NEVER edit this file or the live steering skill, only suggest amendments, and on a violation ALWAYS suggest an amendment. Root `AGENTS.md` Glossary maps core = all, arena = ARENA.md. `rules/kilo/plan.md` replaces `open_plan` with `submit_plan`, and root `AGENTS.md` waives the NEVER-edit clause across refs, live, root and the skill.

#### preview

- Root `AGENTS.md` gains visible-proposal-before-question and amendment-origin-in-CHANGELOG rules. `distribute-arena.yml` excludes `BASELINE.md` through `$SKILL_EXCLUDE`, so the pre-run clear removes stray baselines.
- **Later same-PR adds**: Chat-omitted reports, short chat replies under ASD-STE100, first-read before the link, topic `<repo>-<pr>-<random>` (1.7.0) and local reports commits via `git add -f reports && git commit --no-verify`, never pushed.

### Changed

#### rules

- **ARENA pull cadence**: The Constitution states pulls per tool-call block. A block without a pull violates, except the first block's topic link and a block whose only call blocks.
- Every question carries a recommended answer marked among the options. `validate.yml` narrows its push trigger to `[main]`.
- Another session found an unreproducible route, so it withdraws. Nothing gates `.agents/skills/` against its source, and `validate.yml` keeps `pull_request: branches: ['**']`. The recommended-answer clause mirrors into `rules/ARENA.md` because ARENA stands alone in an Arena session, and reverting takes one line.
- House order: `rules/refs/ARENA.md` first, compressed mirror into `rules/ARENA.md`, `cp` to the root copy. `BASELINE.md` first, squashed into `SKILL.md`, mechanics in `references/REFERENCE.md`, then `cp` to `.agents/skills/arena-live-steering` for every distributed file, which no longer includes the baseline.
- **Deferred**: the portable `skills/squash` line still says to compress the rest of the text and house `AGENTS.md` outranks it. Live ARENA still omits nine full-wording refs items, from `since=all` scope to the never-edit coverage.
- House order: `rules/refs/ARENA.md` first with full wording, compressed mirror into `rules/ARENA.md`, then `cp` to root `ARENA.md`. The waiver sits in root `AGENTS.md` beside the ARENA pointer so the Arena-handling-wins line cannot void it.
- New-line squash on the live ARENA bullets drops `Upon` to `On`. Gates green.

#### preview

- **Activation line**: The activation line becomes literal `10-4: ARENA.md loaded`, and the ack literal `ACK:` in both ARENA files, `SKILL.md`, `BASELINE.md` and `references/REFERENCE.md`.
- **Topic retry**: On the first `SignatureDoesNotMatch` the skill posts a fresh topic in one line, resets `STEERING_NTFY_TOPIC` and polls `since=all`. It stops only if the fresh topic repeats the error.
- **Deferred**: the Playwright/Chromium finding stays out of rules — npm opens, every Chromium host dies after Client Hello, `PLAYWRIGHT_DOWNLOAD_HOST` 404s and `@sparticuz/chromium` misses `libnspr4.so`/`libnss3.so`/`libnssutil3.so`.
- Origins: the cadence came from the chat task, the activation literal from a steering note and body-over-status from three notes escalated by a fourth.
- The visible-proposal gate came from a violation report. The ack prefix came from two notes renamed by a third. Origin, baseline-exclusion, recommended-answer, push-trigger and exceptions-file rules came from steering notes, and two further notes sharpen the prefix rule's "and nothing else".
- **Live steering 1.8/1.9**: Production docs never name the skill, its directory, `SKILL.md` or its scripts. Exceptions are the skill's own files, the topic link and `10-4:` acks, which replace `STEER RECEIVED:`.
- 1.9.0 sets topic form `<branch>-<secret>` and requires the ack line to interpret rather than restate. It also records that the JSON renderer removes `<>`, so a full check walks `since=` and reads the HTML topic page.
- **Mirrors**: `BASELINE.md` takes full wording, `SKILL.md` the squash, `REFERENCE.md` the mechanics, and the tracked `.agents` copy stays byte-identical.
- The production clause governs product docs, not this repository's CHANGELOG, skill files and rule files, which still name the skill.
- Topic form sanitizes the branch to `[A-Za-z0-9_-]` then appends a random token. A truncated JSON body is a malformed pull: tell the user, then fall back to HTML instead of ingesting it.

#### maintenance

- Budget exceptions leave the front page for `BUDGET-EXCEPTIONS.md`, which item 6 of the compression procedure and root `AGENTS.md` point at.
- The exclude line ran against `git ls-files` (five files, baseline absent), both workflow files parse as YAML, and `maintenance/check.py` stays green after the exceptions moved.
- **Funding changes**: A new clause squashes only on the new line, an amended clause only on the affected line. A deletion tries one squash and keeps the lower budget.

### Removed

#### rules

- Compression item 5 in the README, the constitution, maintenance item 10 and both Baselines paragraphs drop the rest-of-file squash wording. Historical exception notes that name the old item 5 stand as the record.

## 2026-09-18

### Added

#### rules

- **ARENA two-read-path rule, live 1.5.0**: `rules/ARENA.md` adds a Verification rule querying websites with both read paths. Page-fetch renders JS and reaches hosts the sandbox closes to curl.

### Changed

#### rules

- **Mirrors**: `BASELINE.md` and `rules/refs/ARENA.md` take full wording first, and mirrors plus the tracked `.agents` copy stay byte-identical.
- **Deferred**: The `routify-file-proxy-sg.oss-ap-southeast-1.aliyuncs.com` `SignatureDoesNotMatch` stays a session-level tooling fault with no repository fallback. The GitHub PR-comment fallback tested (comment 5735924529 posted, read back with ETag, 304 verified) stays outside skill scope on instruction. Generic `rules/AGENTS.md` waits until other harnesses need the rule.
- **Amendment A**: Where calls batch into one block, the pull joins the block as a parallel call and reads again once the block returns. Batching never lowers the pull rate. Full wording sits at `BASELINE.md` line 61, the compressed mirror at `SKILL.md` line 57.
- **Amendment D**: `rules/refs/ARENA.md` line 17 names `scripts/ntfy_steering.py` and its log/anchor generation. `rules/ARENA.md` line 15 adds `pass each body to the skill's ingest script and anchor the next pull on the log's last id`.
- `rules/refs/ARENA.md` line 17 takes the amendment in full wording, `rules/ARENA.md` line 15 the mirror, root refreshed by `cp`. The read path states the live negation once, and `curl` stays named in refs and the skill.

#### preview

- Curl reports status, headers, TLS SAN and RDAP, and either failure or 404 stands until the other checks it. The same rule names `scripts/ntfy_steering.py` and its anchor as operational.
- **Live 1.5.0**: `skills/arena-live-steering` goes 1.5.0 with four areas. Co-issue the pull inside every batched block, inform the chat when the channel comes back mangled, stamp every check into `STEERING_LOG.md` even on empty bodies. Activation becomes observable through that log line.
- Steering cadence lapsed for four causes. The live bullet never named the ingest script, and "before and after every tool call" cannot run on a batching surface. Consecutive fetch failures decayed silently, and empty runs left no disk anchor.
- **Amendment B**: Quiet channels stay silent, but a mangled return — fetch error, `SignatureDoesNotMatch`, unparseable body — earns one chat line naming the error. The error passes to ingest as `STEERING_NTFY_ERROR` so the log's check line records it. Owner instruction later replaced the wording.
- **Amendment C**: The empty-body path of `scripts/ntfy_steering.py` appends `--- <UTC> [ntfy <topic> checked, 0 delivered] ---` to `LOG_FILE`, creating it if absent and carrying `STEERING_NTFY_ERROR` or `(no messages in the body)`. It stamps no `id=`, so `pull_url()` forges no anchor and keeps printing `since=all` until real messages arrive.
- **Amendment E**: `SKILL.md`, `BASELINE.md` and `REFERENCE.md` make activation observable on disk: the first reply posts the topic and the first block stamps a `STEERING_LOG.md` check line. A session without the log never ran the skill.
- `metadata.version` 1.4.0 → 1.5.0 in `SKILL.md`, `BASELINE.md` and the tracked `.agents/skills/arena-live-steering` mirror, with `diff -r` byte-identical parity.
- The owner's steer replaced wording and arithmetic: T5 went over T3, W3 (credential finding) and W6 (proxy-CA caveat). The dropped clauses stay in refs, where W3 is bullet 3 and W6 is bullet 5, and refs keep six bullets per `GUIDELINES.md` 4.1.
- Measured 2026-09-18: `ntfy.sh` fails in-sandbox curl with `SSL_ERROR_SYSCALL` on 443 and empty reply on 80 while page-fetch reads it. TCP connects to `159.203.148.75:443` and the Client Hello leaves.
- `openssl s_client` writes 320 bytes, reads 0 and sees no peer certificate, so the kill is a TLS filter. `rdap.verisign.com` behaves the same on both ports, so the audit blob's plain-HTTP re-pull does not reproduce here.
- The two paths carry different identities: `api.github.com/repos/nemoe7/clankers` answers curl `HTTP/2 200` with `"private": true` and page-fetch `404` in the same minute while `octocat/Hello-World` fetches clean, so the 404 is auth. A keyless `api.github.com/user` answers curl `403 Resource not accessible by integration` with `x-ratelimit-limit: 5400` and `allows_permissionless_access=true`, so the blob's 401-versus-402 claim belongs to a credentialed path that only header-reading shows.
- The proxy intercepts TLS: `api.github.com` presents `subject=O = E2B, CN = api.github.com` and `issuer=O = E2B, CN = E2B Proxy CA`, and the trust store holds that CA under `vTrus Root CA`. An in-sandbox certificate proves the proxy, a filtered host presents none, and refs bullet 5 reads certificates only where the handshake survives.
- The renderer escapes JSON into a markdown code block with quotes and brackets backslashed — RDAP's status and `client-delete-prohibited` fields arrive mangled. Exact-string matching fails on its output, and that is how the blob read catalog fields.
- `curl -D-` alone exposes `etag`, `cache-control`, `x-ratelimit-*`, `x-github-request-id` and `strict-transport-security`. Page-fetch exposes no headers.
- The ten funding cuts remove restated wording only, each kept in full by refs: the explanation-is-debt rationale, `before finishing`, `not after` and `just enough`. Plus the Angular commitlint provenance.
- Also cut: the `since` joiner, `so check rather than ask`, the pushing-is-safe rationale and `committing unlisted is a violation`. The `Simplified Technical English` expansion and `assume` for `take` leave too.
- No negation, condition, command, number, threshold, filename or caveat dropped, and no rule cut.
- Finding F9's turn could not read the steering channel: the empty topic returned the documented HTTP 500 twice. Then `SignatureDoesNotMatch` XML came from `routify-file-proxy-sg.oss-ap-southeast-1.aliyuncs.com`, naming an `OSSAccessKeyId` and a `StringToSign`. It records as a failed check, and nothing reached `reports/STEERING.md` because the ingest script needs a body it never got.
- The report rule broke and fixed inside one turn: the local reports commit landed before the rule commit. The first push carried it with `reports/PROPOSAL-fetch-path-rule.md` in the tree.
- The commit rebuilt from its tree with `git rm --cached -r reports`, `git write-tree` and `git commit-tree` onto `dfb19fe`, pushed with `--force-with-lease` pinned to the bad tip. The remote now holds one commit over five rule files with `reports/` absent, and the local reports commit runs last, on top.
- The artifact `bd7f2c0 chore(reports): record the two-read-path proposal` staged `-f` from the ignored `reports/`, never pushed, amended each turn end and undone next turn. The rule behind it is ARENA.md's, and the miss records here because the report rule holds the diff viewer honest.
- The edit script asserted each of the ten cuts matched exactly once. Live Verification holds no more bullets than refs (8 against 35). Documentation carries no logic, so no runnable check follows.
- The pull also lands before anything expensive or hard to undo. It replaces the same-day batched-call trigger that shipped without its own entry, and this entry folds it in on instruction.
- A check that reads only `STEERING.md` is not a check, and an empty last read skips nothing. The pull URL becomes `<topic>/json?poll=1&since=<lastmessage>` anchored on the log's newest id, with `since=all` only first or after log loss. `scripts/ntfy_steering.py` prints the next URL, so the log is the state.
- The ack clause pins to a medium: the chat reply the user reads is where a delivered note counts. Never in a reasoning block, a tool call or the notes file. Only a delivered note earns the line, so an empty pull goes unreported.
- Cuts in the same change pay: the curl negation repeated, the `GET-only` and `TLS-killed` rationales and the duplicated `STEERING_NTFY_BASELINE` bullet.
- Also cut: the web UI and phone app restated, the `check_steering` snippet `references/REFERENCE.md` already carries and the compressed page-fetch lead-in and pointer. The live visible-activation rationale stays in refs.
- **Deferred**: `since=<lastmessage>` comes from ntfy docs and server source, not an end-to-end measure. The `GET`-only path cannot publish a second message for a two-read sequence. A live anchored read lands the next session whose channel carries a note.
- ntfy docs state that a poll without `since=` re-reads the whole topic cache and replay caps at the newest messages fitting 10 MB with `X-Messages-Truncated: 1`. Replayed bytes bill the daily budget, and a repeat poller passes `since=<last message ID>`.
- The stale-anchor rule came from `message/cache_sqlite.go` on `main` read over `api.github.com`: `id > COALESCE((SELECT id FROM messages WHERE mid = ?), 0) AND published = 1`. An aged-out anchor resolves to cache start, the whole cache returns and message-id dedup absorbs it. Losing the log costs one full read and never a note, so no `since=` state file exists.
- `scripts/ntfy_steering.py` turns `load_seen` into `log_ids` (delivery-order ids serving dedup and anchor). `pull_url` walks backwards to the newest id, printing `Next pull: <url>` on empty and delivery paths alike, including after a `current` hold. A message without an ntfy id stamps `digest-...`, which the server cannot resolve, so it never anchors and the anchor stays put.
- `BASELINE.md` carries the unsquashed wording first per house order — step-3 URL, log dual role, unconditional cadence, script bullet, Limits entry, `Next pull:` example, ack bullet. `SKILL.md` mirrors squashed. `REFERENCE.md` gains anchor mechanics, the docs citation, the source clause, the moved-log note, the `since=all` escape and the anchored-empty-read note.
- The ack clause names the medium: `SKILL.md` opens "Acknowledge every note in chat" and lists reasoning, tool calls and `STEERING.md` as non-places. `BASELINE.md` says nothing the user cannot see counts. `references/REFERENCE.md` argues a silent agent is indistinguishable from a dropped channel, and only a delivered note earns `STEER RECEIVED:`.
- `metadata.version` 1.2.0 → 1.3.0 with the anchor change and → 1.4.0 with the ack clause, both inside one pull request. `.agents/skills/arena-live-steering` follows byte for byte, and gates stay green.

#### automations

- **Validation paths-ignore**: `.github/workflows/validate.yml` skips `push` and `pull_request` runs for `.github/workflows/distribute-arena.yml`, `.gitignore`, `apply.bat`, `automations/**`, `CHANGELOG.md` and `maintenance/README.md`. Project history, scheduler prompts, launcher wrappers, exclusions, manual dispatch workflows and tooling docs triggered runs without touching checked assets. No budgets move, and `YAML parse`, `maintenance/check.py`, `markdownlint`, `ruff check` and `ruff format` stay green.

### Removed

#### preview

- **Pull always**: `skills/arena-live-steering` drops call-shape sampling. It pulls at turn start, every reasoning block, before and after every tool call, and before the turn ends.

## 2026-09-17

### Added

#### rules

- Root `AGENTS.md` gains `Reports and approval` — a `Current`/`Amended`/`Reason` table with line numbers, truncate but never omit, edit nothing before approval. `maintenance/check.py` gains `rules/KILO.md` in budget and lint tables while `.markdownlint-cli2.jsonc` ignores the mode overrides.

### Changed

#### rules

- `rules/ARENA.md` (refs, live, root) requires the first reply to open with the one-line ruleset confirmation plus the channel link. `rules/README.md` records the counter-example that exploration is a bet, and root `AGENTS.md` gains the matching first-action rule.
- `skills/arena-live-steering/BASELINE.md` is new: the `SKILL.md` copied verbatim with Agent Skills frontmatter and the `metadata.baseline` marker, the amend-first baseline that mirrors `rules/refs/` and `skills/squash/BASELINE.md`. The squash makes ten cuts of restated wording and adds the Files-manifest row, keeping every command, code block, filename, number, negation and caveat.
- `references/REFERENCE.md` states that the chat carries the channel before the first read and that a fresh topic's first 500 is no fault. `skills/README.md` notes the second skill carrying a `BASELINE.md`. `metadata.version` 1.1.0 → 1.2.0, and the `.agents` copy follows byte for byte including the new baseline.
- The activation clause lands in house order — `rules/refs/ARENA.md` line 7 full wording, `rules/ARENA.md` line 6 mirror, root `ARENA.md` by `cp`. Root `AGENTS.md` line 8 opens with read end-to-end before any edit, folding the Arena read of `ARENA.md` into that first read.
- The 2026-09-17 counter-example records a session that explored the skill subtree and pushed twice before reading the rulesets. Exploration is a bet, not a gate. The custom-instructions field, not the first message, is the only injection path that survives a forgotten bootstrap line.
- **Kilo live counterparts**: `rules/kilo/{plan,code,debug}.md` mirror their `rules/refs/kilo/` baselines and join the budget table. A new `KILO_PAIRS` gate in `maintenance/check.py` fails when a live override states more rules than its refs baseline. The shell-check rule leaves `rules/ARENA.md` for the core because Arena sessions do not choose a terminal, and ARENA squashes again to absorb both changes.
- Lint scope stays 10 files with `rules/kilo/**` ignored beside `rules/refs/kilo/**` for MD001 and MD041.
- `rules/README.md` and `rules/refs/README.md` stop calling the overrides refs-only and name both ignored directories. The live Kilo overrides keep their required shape — empty first line, `### Native <mode> Agent Overrides`, then the conflict clause.
- **Core slimming, skill ntfy-only**: Planning and execution clauses move to `rules/refs/kilo/{plan,code,debug}.md`. Each opens with a blank line, the `###` heading and a clause that beats a native reminder. `rules/refs/KILO.md` plus live `rules/KILO.md` carry the Kilo-only tool rules.
- The Lazy Ladder returns inline at full intensity with no skill artifact, intensity switch or marker after a first pass removed every trace. The questionnaire that would re-add the rest defers.
- markdownlint scope moves 8 → 10 files with `rules/refs/kilo/**` excluded for MD001 and MD041.
- **Deferred**: a session answered the ponytail questionnaire on 2026-09-17 — every unomitted item inline, recorded in `reports/PONYTAIL-REINCORPORATION-QUESTIONNAIRE.md` — and P12's fix-once half restored with it. Still open: the ARENA resquash, the `rules/ARENA.md` MD013 contradiction, and the dropped `.doc/.ppt` line.
- SOLID joins Engineering in both cores: SOLID pulls against YAGNI/KISS/DRY, so planning MUST ask which governs — reusable and extensible, or simple. The collision stays stated, and Kilo's plan override asks where drafting happens.
- `rules/refs/AGENTS.md` loses its generic preamble, plan and execution clauses and three ambiguity rules. It gains the shell check, tool-call batching, minimum-comment, single `nemoe7` scope, question-tool-only ask, and a test clause rewritten to match TDD. `rules/refs/ARENA.md` keeps its plan and execution clauses because it ships alone to four repositories and gains the collision clause as the core's mirror.
- `rules/refs/KILO.md` and `rules/KILO.md` hold `kilo_memory_save`, `todowrite`/`todoread` and the commit step in every TODO list, never repeating the core. `rules/refs/kilo/plan.md` requires `submit_plan`, forbids `plan_exit` or turn end before approval. `code.md` and `debug.md` consult and update the approved plan, and `debug.md` adds the bug explanation, no-edit-before-approval and a web search when the bug is puzzling.

#### preview

- **Link-first activation, live 1.2.0**: `skills/arena-live-steering` step 1 requires the ntfy link as the first line of the reply. The fetch fails until the user posts, because the agent cannot publish (`GET`-only fetch, TLS-killed POSTs).
- An empty topic reads as HTTP 500, so expect that first failure. The full wording copies to a new `BASELINE.md`, and the live entry point squashes back in the same change.
- The channel carried its first message during the change — "no report needed just amend and merge". The ingester delivered it 1/1, checking channel and ingest path live.

### Removed

#### preview

- `skills/arena-live-steering` removes `scripts/dns_steering.py`, `scripts/ntfy_relay.py` and the `dns-txt` metadata. It checks at every reasoning block, every three tool calls and the turn end, and never reads immediately before a blocking call.
- The DNS relay leaves as measured and removed rather than dropped: the page-fetch path reads the topic directly at the new cadence. A relay needs an unreliable preview tab that fails silently. `check_steering.py` defaults `STEERING_FILE` to `reports/STEERING.md` instead of a hardcoded `/home/user` path.

## 2026-09-16

### Changed

#### rules

- The blocked set's first half: `ntfy.sh`, `ntfy.envs.net`, `ntfy.tilde.team`, `cl1p.net`, `kvdb.io`, `paste.rs`, `0x0.st`, `api.telegram.org`, `discord.com`, `matrix.org`, `script.google.com`, `docs.google.com`. Second half: `googleapis.com`, `webhook.site`, `jsonblob.com`, `textdb.online`, `hastebin.com`, `dpaste.org`, `ix.io`, `api.pushover.net`, `api.pushbullet.com`, `hooks.slack.com`, `e2b.app`, `arena.ai`. Four peers stay reachable: `github.com`, `api.github.com`, `pypi.org` and `registry.npmjs.org`.
- A half-applied amendment exposed a gate that cannot see it: the turn-ending steering check existed in `rules/refs/ARENA.md` but not the live file. The parity rule accepts that by construction, since a refs-only addition satisfies it. Mirrored now in both places, with the root byte-identical copy refreshed.

#### preview

- **Registration, house voice, one channel**: `skills/arena-live-steering/` landed unregistered, so `maintenance/check.py` failed its `skills/README.md` coverage gate and both Ruff gates failed on the scripts. This change registers the skill and turns all three gates green. It rewrites the `ALWAYS USE` / `DO NOT USE` activation wording into house voice on request, keeping every trigger.
- The channel rebuilt from measurement: `ntfy.sh` and 25 other HTTP hosts are TLS-closed in an Arena sandbox. A GitHub transport built and verified live, then declined, and DNS proved unfiltered. `scripts/dns_steering.py` reads one TXT record over UDP/53 into notes with no service, repository or HTTP.
- On instruction the failed and declined transports are gone. The skill ships one channel, `scripts/steering_notes.py` holds the shared note writer, and root `AGENTS.md` records the `tiktoken` cache route and egress map.
- **Deferred**: the surviving ntfy route keeps two defects the new ones avoided. It overwrites `STEERING.md` instead of appending, and anyone who learns the topic can read and steer. DNS checks pass only against sandbox-readable records, not a zone the user edits, so the human end waits on a real name.
- Moving detail into `references/` was the plan, and removing the channels did it instead.
- The coverage gate now sees a purpose row and a selection row. The upstream-sources paragraph says plainly that `squash` marks `metadata.origin` while `arena-live-steering` does not yet. Root `README.md`'s `skills/` bullet names the third subject beside UI reviews and text compression.
- All four scripts went mode `100755`, and `ruff format` re-indents them plus the fenced Python in `SKILL.md` and `REFERENCE.md` to the pinned `indent-width = 2`.
- The activation wording keeps its triggers and loses its shout: `description` and `compatibility` still carry Arena-only scope, mid-turn correction, cross-device steering and an unreliable client. `metadata` drops `always-use` and `priority: always` as duplicates and keeps `arena-only` and `use-when` as facts.
- The egress map decided every channel: 26 hosts close TLS from an Arena sandbox (curl exit 35, HTTP 000) or fail to resolve.
- TCP to `ntfy.sh:443` connects and the handshake is then cut, so the filter is deliberate and no proxy variable takes effect. An egress allowlist is a security control, not an obstacle to route around.
- DNS is the opening the shipped channel uses: a hand-rolled TXT query over UDP/53 with stdlib `socket` and `struct` returns `_dmarc.gmail.com` correctly at about 1 ms. Only the resolver in `/etc/resolv.conf` answers. 8.8.8.8 works while 1.1.1.1, 8.8.4.4, 9.9.9.9 and a zone's own authorities time out, which is what makes the channel one-way.
- `scripts/dns_steering.py` therefore reads that file, with `DNS_RESOLVER` as override and 8.8.8.8 as fallback.
- `scripts/dns_steering.py` watches one TXT record with no account or service: the value is every record on the name sorted and joined by newlines. Order cannot churn the digest. `STEERING_NTFY_BASELINE=current` holds the startup value while `empty` ingests the first found, and a change delivers the lines after the longest prefix already seen.
- Labels check against the 63-octet limit, a failed query prints one line and retries, and nothing exits silently.
- Three hazards are inherent: a TXT record is public, so the name is a capability and a secret never belongs in a note. TTL sets latency (60s record, 180s zone SOA minimum), and two edits inside one TTL collapse. DNS carries no author, so notes attribute to the record name, and one character-string is 255 octets that providers split and the poller rejoins.
- The channel ran live: the user created a `dns.army` zone on `dynv6.com`, and `STEERING TEST` became a note within one interval. A second edit arrived 30 seconds later. A 370-character value kept its blank lines and multiple strings with three instructions this entry obeys.
- `dns.army` itself is NXDOMAIN at apex while `steering.vlht-mrsv.dns.army` resolves under `SOA ns1.dynv6.net`, so `REFERENCE.md` now says how to check a candidate name first.
- Live use found the defect: 40 queries returned the current value 22 times and the previous 18 times six minutes after an edit. The resolver serves disagreeing caches, and the poller delivered twelve duplicates before the real note.
- Digest dedup now persists to the log and recovers on restart — re-setting an old value does nothing until one character changes. Verification: 25 polls delivered one note, and a warm restart delivered none.
- Two more live-run defects: transient NXDOMAIN made the startup banner claim no note could ever arrive. `probe_startup` retries three times and says when the resolver changed its mind (four checks pin it). `query_txt` returned `""` for both no-record and no-answer, so one failure moved the baseline and replayed everything.
- `None` now means no answer, baselines survive it, and a baseline can establish late.
- The note path consolidated into `scripts/steering_notes.py`: `digest`, `added_lines`, `deliver`, `DIRECTIVES`, header, append, tail cap and log write. Running it exposed what reading did not. `NOTES_HEADER`'s trailing newline survived `split("## Current Notes:")[1]`, and blank lines accumulated above the first note, nine after seven comments.
- The remainder now strips on append, and the assert pins the head gap at one. The log stamp carries one timestamp with the body on its own line.
- It ran on pull request 13 (description edit to note in 12s) and 148 real comments on `octocat/Hello-World#1`. Permissions outlive it: installation tokens read issues but receive 403 creating them, read and write PR descriptions, and write contents. Both gist hosts are TLS-closed, and `api.github.com/gists` answers 403 for `GET`, `POST` and `PATCH` alike.
- `assets/steer.html` gave the user a page: a textarea autosaving 1.2s after typing stops and a sync light driven by DNS-over-HTTPS rather than the provider API. The light samples Google and Cloudflare resolvers, goes amber when they disagree, tells NXDOMAIN apart from no-TXT and falls back to a copyable `curl`.
- The token stays in browser `localStorage`, and TXT parsing is unit-tested against eleven payload shapes including a 255-octet split and `\DDD` escapes. This sandbox never exercised it, and the section removes it later.
- The channel took itself down: after 500 queries of one name in 25 minutes, every name under the zone answered NOERROR with no records. Apex and SOA included, while control zones still resolved, and the user removed nothing.
- `POLL_INTERVAL` defaults to 30s instead of 10s. `REFERENCE.md` carries the measurement with the rule to check the provider panel or DoH before blaming the poller.
- Retraction: ten queries of one record returned its value five times and no-data five times, each within two milliseconds. `_dmarc.google.com`, the apex and `example.com` came back right every time. The resolver path blinks on about half of queries, and the earlier sweep sampled a run of blinks.
- The zone did serve no data for about fifty minutes while the panel showed the record, then recovered intact. `dns_steering.py` now queries a control name before saying anything about the steering name, so an observer's blink cannot publish as a fact about somebody's zone.
- Two write-offs overturned by one distinction: the egress allowlist binds sandbox processes, not the agent's page-fetch path. A public gist's raw content, `dns.google` DoH and an `ntfy.sh` topic page all load through it. The reliable record read is now `https://dns.google/resolve?name=<record>&type=TXT` at a turn boundary with the procedure in `REFERENCE.md`.
- Ntfy's JSON form stays reachable-but-unproven after its empty-topic 500. That fetch surfaced two directives — a `STEER RECEIVED` clause and a ban on agreeing with everything — now clauses in `SKILL.md`.
- The distribution workflow now carries the skill: `distribute-arena.yml` mirrors tracked `skills/arena-live-steering` files into each target's `.agents/skills` and clears the destination first. It lists files from `git ls-files` and verifies list and bytes after each push.
- The rules it already delivered said to activate a skill no target had. Tested against a seeded local target: stale file removed, seven files identical, second run committed nothing.
- `scripts/ntfy_relay.py` gave ntfy continuous capture without sandbox contact: the preview page subscribes to the topic stream and forwards messages to the server with id dedup. It falls back to 10s polling when CORS refuses the stream, and a closed tab costs nothing because ntfy holds 12 hours under `since=all`. Tested live: a POST delivered, a repeat id skipped, an NDJSON keepalive plus titled message delivered one note intact.
- `skills/arena-live-steering/SKILL.md` measures in bytes rather than `cl100k_base` tokens on instruction: bytes need no tokenizer and survive an unseedable `tiktoken` cache. Tokens are what a model pays — roughly four to one for English prose, so the other rows keep the dependency.
- The closing-check rule joins the cadence on instruction. The acknowledgment clause cannot fire on a note nobody read, and a mid-turn note would deliver a turn late.
- Ntfy became default and DNS the fallback on the user's measurement: same-minute publish versus edit, instant note versus 60-second TTL. The path serves no data half the time. Seven messages read in one poll, a second ingest delivered nothing, and `expires` puts retention at 12.0 hours.
- The cadence follows read cost: a network round trip, so turn boundaries and pre-blockers rather than every tool call.
- `assets/steer.html` goes: 597 lines whose sending half could not work. The provider answers CORS preflight with an empty `Access-Control-Allow-Origin`, and its `GET` update endpoint is dyndns2 with `ipv4`/`ipv6` only.
- Its checking half went redundant the moment ntfy's own UI checked posts. The DNS route keeps the provider panel and one-line API call in `REFERENCE.md`.
- Session reports reached the remote and then left it: five `docs(reports)` commits shipped as ancestors of later pushes, so `git filter-branch --prune-empty` stripped `reports/` from every branch commit. The force-push left a byte-identical tree with the pull request open on 15 non-report files. The rewrite took tracked working-tree copies with it, restored from the pre-rewrite commit, and the review report quoted the notes publicly for the interval.
- `reports/` is never `git add -f`'d again.
- `SKILL.md` grew past carrying measurements, so they moved to `REFERENCE.md` read on demand. A route-block reorder first truncated the file to 45 lines, and `check.py --update` re-baselined the wreck without complaint, which is the argument for asserting structure before writing.
- The portable route is an `ntfy.sh` topic published from a browser, the phone app or `curl -d`: `scripts/ntfy_steering.py` ingests poll bodies into the shared notes and log. It dedupes by ntfy message id, keeps titles, skips `open` and `keepalive`, strips the markdown fence and digests id-less messages. `STEERING_NTFY_BASELINE=current` holds history and the hold writes to the log, because a one-shot script that forgets its baseline delivers the history it was told to bury.
- The first run did exactly that.
- Three measured limits: the agent cannot publish to ntfy (sockets TLS-closed, page-fetch `GET`-only, secrets 403, topic equals password). The first message must come from the user. HTTP 500 on the JSON poll form is the empty-topic read path, since the same tool 500s a 200-with-empty-body.
- `/atom` and `/feed.xml` are 404 while the poll form stops instead of streaming. The sending page's DoH failures no longer win the light: it reports `cannot reach the resolvers` with reasons. Any throw surfaces in a banner.
- The sending page's DoH failures no longer win the light: it reports `cannot reach the resolvers` with reasons. Any throw surfaces in a banner. A preview-framed page cannot touch `localStorage` and died on the first keystroke.
- Two live-session questions settled by measurement: gists are unreachable three ways — `gist.github.com` and `gist.githubusercontent.com` TLS-closed, `api.github.com/gists` 403 under the injected installation identity. The browser cannot send to dynv6 at all. The blockers: empty preflight header, dyndns2 `GET` carries no TXT.
- `assets/steer.html` leads with a live-rendered terminal command and trusts the DoH light. The rendered command round-trips apostrophes, newlines, quotes, backslashes, `$VAR`, backticks and non-ASCII byte-exact through `python3 -c 'json.dumps(sys.argv[1])'` because the note travels as `argv`.
- Stdin would append a newline, and the nsupdate zone comes from the provider, not the last three labels.
- Verification ran the skill rather than reading it: four repository gates plus `compileall`, and the `validate` workflow on every pushed commit. The DNS transport carries an 18-check assert over read path, change and failure semantics, round trip, digest recovery and the startup probe. Only the provider's write API stays unexercised, documented from its specification rather than a call this sandbox could make.

#### maintenance

- No other measured file changes, and `maintenance/check.py` gains the matching `EXPECTED_BUDGETS` key.
- Root `AGENTS.md` records the venv install under PEP 668 and the `TIKTOKEN_CACHE_DIR` seeding route through `niieani/gpt-tokenizer`, with `maintenance/README.md` carrying the command.

### Removed

#### preview

- A GitHub transport arrived, verified live, then removed on instruction: it watched an issue or pull request through `api.github.com` by default via description edit. Opt-in comment mode joined `If-None-Match` polling against the 5,400-request hourly limit and a prefix diff shared with the DNS poller.
- The dropped skill's ntfy channel left with it. `REFERENCE.md` keeps a table of every channel measured and not shipped with the evidence. It records that `pypi.org` and `registry.npmjs.org` would work as carriers but lost on one publish per steer.
- The dailies automation drops LiteLLM per its own section 4: the tracked-PR section, its section-1 row, the `Watched` columns and example leave. The prose count falls to ten, sections renumber 5 → 4, and the work order becomes `1, 2, 3` with the expensive audit last.

## 2026-09-15

### Added

#### rules

- `rules/refs/CHATGPT-MORE.txt` gains `NEVER ASCII art for diagrams` on the mermaid line, mirrored as `; NEVER ASCII art`. `nemoe7/wiki` joins `REPOS` in `distribute-arena.yml`. The `ARENA_DIST_PAT` PAT needs Contents read/write there before the next dispatch, and access arrived since.
- `rules/refs/ARENA.md` Verification gains the file-tools-over-shell rule with the batching rationale, mirrored live. ARENA.md records the harness limits measured 2026-09-11: 100 cheap calls per block, the ceiling is result tokens not count, and verification runs next message. Hard caps: 10 speech clips and image-search `count <= 5`.
- Refs and live Use gain the delegation rule: durable session rules go in the project's `AGENTS.md`, amendable unless it says otherwise.
- `skills/README.md`'s install example copies `squash` instead of `planning`, and its Format section gains a bullet defining `BASELINE.md` and the amend-then-squash order.

### Changed

#### rules

- **Deferred resquash lands**: The Python-project scoping and project-first commit convention mirrors from `rules/refs/` into `rules/AGENTS.md` and `rules/ARENA.md`. That covers spec-aligned `<type>[optional scope]: <description>`, the `!` marker and history-preferred types. The FORMAT line moves into `rules/CHATGPT-CUSTOM.txt`.
- A follow-up hardens the ChatGPT diagram rule with `NEVER ASCII art` and routes the report-turn closer through the question tool. The removed `workflows/init-docs.md` returns fully rewritten, and `rules/ARENA.md` prefers read/write tools over shell for file work.
- Every addition funds in-change: four core lines and five ARENA lines of constitution/body redundancy and a micro-trim pass. The `-f body=@path` war story cuts to its mechanism. The narrowed ask amendment rides along, closer through the question tool with plain text as fallback, amended in refs first and mirrored compressed.
- **Deferred**: the `GITHUB` commit-format line in `rules/CHATGPT-CUSTOM.txt` keeps its wording.
- The parity gate failed on `main`: live `Debugging` held 6 rule lines against refs' 5 (a `MUST grep every caller` repeat). Live `When in doubt` held 2 against 1. The round removes both repeats, and each rule survives once.
- The core's Code style now scopes all three Ruff lines to Python projects, prefers the project's own `ruff.toml` and drops the E4/E7/E9/F codes. Its Git section leads with the project's convention, fixes the Conventional form and prefers history's types with the spec-mandated `feat`/`fix` provenance kept. ARENA's Style and Git take the same mirror with the provenance trimmed to a parenthetical.
- Full findings sit in refs, with two compressed lines live.
- Root `AGENTS.md` takes the durable-amend rule (amend when durable and repo-wide) and the nesting rule (a nearer file wins). It stays out of `rules/refs/AGENTS.md` by decision, so the core keeps its wording and its precedence gap stays open.
- Two skills leave, and `workflows/` keeps its framework and README without shipping an ownerless workflow. `skills/squash/BASELINE.md` is new, the unsquashed original of that skill with Agent Skills frontmatter, documented in `skills/README.md` as the skill-side counterpart of `rules/refs/`.
- The four refs baselines amend so Python tooling rules apply to Python projects. The commit convention defers to the project's own before defaulting to Conventional, and the E4/E7/E9/F codes drop as already covered by Ruff defaults.
- Every amendment lands in `rules/refs/` only — the live mirrors keep pre-amendment wording on request until a later resquash. Refs and live disagree there by design, and the parity check cannot see it, since it compares headings and rule counts.
- `rules/COMMIT-SPEC.txt` is the exception: documented equal to its baseline and never compressed. The round rewrote both copies together. Its README row stays stale until the `validate` workflow's `--update` refreshes it, because the sandbox cannot reach `openaipublic.blob.core.windows.net` for the `cl100k_base` BPE file.
- **Deferred**: the four live mirrors still carry the old Python and commit wording — resquashing them is the next pass. The redundancy review recommends its findings without applying them: constitution-versus-body duplicates in the three rule files and root's restatement of the installed global core.
- The open precedence gap stays: no rule yet says a nearer project `AGENTS.md` outranks the global core, although agents.md states closest-wins. A check of `rules/ARENA.md` found no branch-other-than-`main` rule to omit per the Arena carve-out, and it carries none.
- A redundancy review measured the corpus first: 698 rule lines across 11 files, compared on stopword-stripped token sets at 0.60 Jaccard. It yielded three tiers: deliberate mirrors, 62 pairs between the two refs baselines that make one change cost four edits, and an unmanaged cluster. There constitution lines repeat body lines, sometimes weaker.
- The Python amendments split one rule into four in `rules/refs/AGENTS.md` — Ruff selection, `ruff.toml` conventions, create-if-missing, pre-commit gates — each opening `For a Python project`. `rules/refs/ARENA.md` scopes its four Ruff lines, and `rules/refs/CHATGPT-CUSTOM.txt` restates FORMAT as `Python projects: use Ruff with its default rule selection`. The project's own config counts as such when present, so an existing `ruff.toml` stays untouched.
- Testing rules take the same treatment: check with the project's own tests, linters, formatters and builds, and reuse the project's frameworks and fixtures. The discipline stays global while its target is project-scoped. The commit amendment adds one rule ahead of the format: follow the project's convention when it states one.
- The round fixes the format itself against <https://www.conventionalcommits.org/en/v1.0.0/> — `<type>[optional scope]: <description>`, scope in parentheses, `!` before the colon — replacing the `<type>(scope): <subject>` form these files carried. The type list stays with provenance: the spec mandates only `feat` and `fix`, the rest arrive via Angular through `@commitlint/config-conventional`, so the project's history wins.
- `skills/squash/BASELINE.md` restates the whole skill in complete sentences: unit table, five-step resolution, no silent proxy units and simultaneous budgets with conflicts reported. Also: seven survivors, six safe cuts, six-step method, four structural constraints, funded-in-change and reporting contract. It closes with a `When in doubt` section like the rules baselines.

#### preview

- Testing and verification lines now name the project's frameworks, fixtures, helpers and conventions in both cores. The new ARENA report-turn rule sits last in Response: refs full two sentences with the plain-text fallback, live one line: `End report turns with an open question via question tool; never mid-task or tool-only.`

#### workflows

- The two parity failures that broke validation leave: a live `Debugging` line and a live `When in doubt` line each duplicating a Constitution rule. `.github/workflows/distribute-arena.yml` targets `nemoe7/wiki` beside the three existing repos.
- `workflows/init-docs.md` rewrites as the universal docs starting point: a tiered catalog — baseline, community bundle, SRS outcome contract, time-axis pair, ADRs and design proposals.
- Also: Diátaxis quadrants, formal SDD and gated business docs, a no-docs bootstrap, client choice beyond baseline, worked classifications and FAQ dissolution. Plus an unattended-run policy, no third category beyond evidence and open questions, and `llms.txt` kept out as proposal not standard. Its section 10 states the home rule: repo-wide rules live in the project's `AGENTS.md`, session scratch stays out.
- The harness findings compress to one summary line each in refs and live: 2 CPU workers cap shell parallelism. File work stays on read/write tools. Nesting moves outward — root drops its line for this flat repo and `workflows/init-docs.md` section 10 teaches bootstrapped repos instead.
- It reverts the unfundable GITHUB line.
- Not mirrored for size, with refs still holding them: the spec URL in both cores and the `@commitlint/config-conventional` citation in ARENA.
- `workflows/README.md` loses both tables and states in prose that the directory holds no workflows. Its Format section still defines what a new workflow must meet. Root `AGENTS.md` keeps its Workflows section and read-first link.

### Removed

#### rules

- The removed skill and workflow take their validator entries with them.

#### workflows

- **Planning and init-docs retired, squash baseline born**: `skills/planning/` and `workflows/init-docs.md` are gone on request.

## 2026-09-13

### Added

#### rules

- `rules/ARENA.md` and its ref gain the activation rule in Use, refs first: no platform loads the file. An agent without it in context MUST open it at the repository root before its first edit and say so in one line. The live file compresses to `No platform loads this file: if it is not in your context, MUST open it at the repo root before your first edit and confirm in one line.`
- The Constitution gains two rules from the critique: metadata beats the embedded datetime when both exist. The second: NEVER state a version, tag, date or SHA absent from content fetched this run or claim a check you did not run. The embedded-datetime rules stay verbatim since a run cannot edit its own prompt, and the precedence line resolves the collision instead of removing either.
- The rule files gain the voted ask discipline, refs first and mirrored compressed: Arena's Verification prefers the question tool globally instead of fallback-only. Both cores' Scope require the ask before implementing. The generic core plus `rules/CHATGPT-CUSTOM.txt` carry the carve-out that unattended runs record the question, assume and proceed.

#### preview

- Section 4 gains its completion path: a stable release containing the tracked commit, a revert, or an official not-shipping statement. After that the item stops the check and asks in one line for removal.
- Section 3 gains the honesty valve: where the connector cannot prove ancestry, CI or PR state, the `Evidence` cell says so instead of inferring. Section 2 scopes to `nemoe7`'s public repositories capped at five recommendations per run.
- The `### Tracking a new item` section adds eight embedded rules for onboarding. One: a row with a proven URL, releases preferred over store or feed, the shown version or date as first-run baseline. Two: a stable-channel definition, `ephemeral` marking, `nemoe7` scope, the `simplified:` count matched to the table and removal only on instruction.
- Skipped/add-when reporting returns soft as `Consider` in both Responses.

### Changed

#### rules

- The prompt leaves run-on prose for rules without losing one: a `## Use` preamble, a nine-rule `## Constitution`, five numbered sections and a closing `## When in doubt`. The `## Use` preamble says what it is, applies every run and outranks skills and plugins. An explicit run-prompt instruction outranks it, and sections 1–4 feed section 5's shapes.
- The Constitution carries the embedded `2026-09-12 17:40:00` UTC+8 datetime beside its two rules: update on EVERY RUN before monitoring, leave it when merely edited. Then: actionable-only output, the NEVER on no-change entries, first-run baselines unreported, ephemeral items until purpose-complete, the exact section-5 contract and output-nothing when nothing is actionable.
- A `simplified:` marker in `## Use` caps scope at the 11 software items and `nemoe7` repositories, and the file is self-contained on request. It keeps the guidelines' shape — Use, Constitution, numbered domains, When in doubt — with no cross-reference or dependency, without them at run time.
- The rise funds in-change by two passes that remove words never rules, and root `ARENA.md` re-copies byte-identical.
- `maintenance/check.py` gates that identity with `ROOT_COPIES`, comparing root `ARENA.md` bytes to `rules/ARENA.md` and printing the fixing `cp` on drift. Root `AGENTS.md` folds verification step 4 into step 3, `maintenance/README.md` describes it, and `rules/README.md` retires its "rather than gating the identity" corner cut.
- `rules/README.md` fixes the premise: not `Arena loads ARENA.md on its own`. The recorded observation: an injected context carries sandbox, branch and tool details only, and the agent reaches the file by opening it.
- That also ends the clash with `never assume a filename alone enables loading`. The contents row and Arena section carry the exact bootstrap line for a first message or custom-instructions field and state that delivery is not activation. They split into three paragraphs: condensing, activation and the root copy.
- Root `AGENTS.md` aligns its Arena pointer — `also follow` becomes `MUST also read and follow... before your first edit`. It leaves both bold clauses untouched.
- `.github/workflows/distribute-arena.yml` verifies its own work: resolve the source once, fail before the loop when `rules/ARENA.md` is missing. Each push compares `git show HEAD:$DEST` with the source into the existing `sync failed for:` list. The header records dispatch-only scope and that delivery is not activation.
- Coverage becomes the one sanctioned exception to actionable-only: appended after `## 4. Watched`, it carries sources and repos reached, misses with reasons and incomplete sections.
- Unreachable sources are actionable and must not be suppressed. The stop rule works sections 1, 4, 2, 3 so the expensive audit runs last, outputting what completed rather than inferring gaps.
- The carve-out is absent from `rules/ARENA.md` by design: the core carries it under Arena's always-loaded `AGENTS.md`, and Arena has no unattended surface.
- The record rejected the broader alternative: stop-and-ask before every edit, command and commit would contradict the materiality threshold and assume-and-state branch. It would deadlock unattended runs, turn one-line fixes into two-turn exchanges and wear the signal out. The observed failure — improvising past material ambiguity — is what the timing clause addresses.
- The automation then obeyed its own carve-out: `## When in doubt` no longer ends with `stop and ask rather than improvise`. It instead records the question in `## Coverage`, proceeds on the most reasonable assumption and states it. Section 5's closed enum gains `any question you could not ask with the assumption you proceeded on`.
- The tool preference generalized on request: `rules/AGENTS.md` and its ref prefer the question tool whenever the surface provides one, conditional on purpose. Arena keeps its own copy since its activation rule exists because `AGENTS.md` may not load there. `rules/CLINE.md` inherits while naming `ask_question` with zero headroom, and `rules/CHATGPT-CUSTOM.txt` stays untouched because ChatGPT offers no such tool.
- A correction fixed the ChatGPT field mapping: Personalization now offers `Custom Instructions`, `Nickname`, `Occupation` and `More about you`, first and last capped 1,500 chars. `rules/CHATGPT-CUSTOM.txt` maps to the first, and `rules/CHATGPT-MORE.txt` to the last. The existing 1,500 gate in `maintenance/check.py` was right, and only naming in `rules/README.md` and a validator comment was wrong.
- `rules/refs/` copies stay uncompressed, never pasted. `Nickname` and `Occupation` stay unversioned profile lines.
- Experiment settled whether `More about you` binds rules, after a leaked 2024 wrapper told the model profile content is irrelevant to 99% of requests. Two canaries across three fresh chats showed an unconditional marker rule firing everywhere while a conditional flag fired only on the related request. A third canary showed a conditional work rule firing on coding.
- So the field binds unconditional instructions across topics, deweights judgment triggers when unrelated and carries work rules where needed.
- That result paid the 2026-09-13 ponytail entry's deferred debt: the seven-rung ladder replaces field one's four-step ladder in `Custom Instructions`. The three MUST upgrades plus the reflex caveat join a `WORK:` label in `More about you`. They are: propose smaller scope, leave one runnable check, grep every caller.
- The caveat names the field the rungs live in rather than saying above, because the halves paste into different boxes. Both refs baselines take full wording first.
- A request renamed the two ChatGPT files to name their fields: `rules/CHATGPT.txt` → `rules/CHATGPT-CUSTOM.txt`, `rules/CHATGPT_RESPONSE.txt` → `rules/CHATGPT-MORE.txt`, refs baselines with them. Eight references followed across `maintenance/check.py`, `README.md`, root `AGENTS.md`, `rules/README.md` and `rules/refs/README.md`. Older entries here keep the names they were accurate under.
- Ten more core rules then moved into `rules/CHATGPT-MORE.txt` once canaries proved the field binds: chat-outranks precedence, open with the result and the full debug cycle. Then: never lazy about understanding, build full when insisted, follow repo docs, prefer deletion and boring, check requirements before finishing. Report skipped alternatives with add-when triggers and `simplified:` corner-cut comments.
- The precedence rule sits above both blocks, response rules join `RESPONSE:` and work rules join `WORK:`. Poor-value-per-character candidates stay out — plan MUSTs, `ruff.toml` specifics, review-the-diff, cohesive modules, merge and scope-reuse.
- Three nits closed: `rules/AGENTS.md` capitalizes `NEVER block an unattended run` to match refs and its caps-for-irreversible rules convention at zero token cost. Root `AGENTS.md` gains `## Automations` beside Rules, Skills and Workflows, stating that prompts are scheduler-owned self-contained text running on web search and the GitHub connector.
- `distribute-arena.yml` stays dispatch-only by decision, because a cron would ship a broken `rules/ARENA.md` to every target and compare-before-push gives idempotency not correctness.
- No rule followed, because pushes, branches and PRs are already gated by `rules/CHATGPT-CUSTOM.txt` on every request. Only documentation changed, reports stay in the chat response, and `automations/` stays ungated and unbudgeted. A gate would watch the repo copy, not the live paste, and its editor edits only itself.
- `rules/CHATGPT-MORE.txt` now says `Mermaid diagrams` rather than the bare name — `Default to Mermaid diagrams for pipelines/flows`. Refs carries the explanation (a fenced `mermaid` block a supporting surface renders as a picture), and the core's line still reads `Default to mermaid for pipelines, diagrams, and flows` per the amendment's scope.
- `rules/COMMIT_SPEC.txt` became `rules/COMMIT-SPEC.txt` with its baseline in lockstep — the hyphen being the repository's other multiword separator. Seven referencing places across five files followed: `EXPECTED_BUDGETS`, `PLAIN_PAIRS`, the README table, three `rules/README.md` spots and `rules/refs/README.md`.
- Every rule file producing human-facing text now prefers ASD-STE100 Simplified Technical English as one line with no linter behind it. `rules/AGENTS.md` takes it as a `General` line, `rules/ARENA.md` folds it into its style line, `rules/CHATGPT-MORE.txt` as a second global line and `automations/DAILIES.md` as a report rule.
- Handled-off commands print in two forms on request: bash plus Windows PowerShell by default or cmd for one line. They serve commands the agent hands the user, always for setup, install and multi-step runs, with the Raspberry-Pi bash reason living in refs.
- The corner-cut rule survives in AGENTS, ARENA and all refs, but ChatGPT no longer carries it.
- Both new checks ran red before green: drifted root copy, missing root copy and diverged distribution target in a scratch repository. The workflow YAML parses.
- The full seven-rung ladder lands for the first time. `rules/ARENA.md` gains a client-unreliability clause.
- **Deferred**: `rules/CHATGPT.txt` stays untouched — no ultra content to remove.
- Per-part decisions land in `rules/refs/` first, then mirror compressed: scope-challenge returns as a MUST with the how-never-what guardrail. Shaping and decision heuristics return whole as `Prefer` lines. Grep-callers returns as the hard rule with `Fix once where all callers route through` and its Constitution echo.
- Rung 4's example stays prose because MD033 forbids inline HTML under the markdownlint defaults covering `rules/`.
- `rules/ARENA.md` and its ref gain the client-unreliability clause beside the garbled-message rule: the client resends, truncates and drops, and empties tools that ran. A repeat is a resend: answer what is pending, restate completed work in one line, never treat it as authorization to redo or widen.
- Root `ARENA.md` re-copies byte-identical. `rules/CHATGPT.txt` and its ref stay unchanged, greps for the ten ultra terms finding zero matches.
- Removals: `skills/ponytail/` and `skills/frontend-design/` leave with their references: three `skills/README.md` tables and the root README line. `web-interface-guidelines`' pointer now reads "in place of design work".
- Historical CHANGELOG mentions stay as the record of incorporation, when and at what cost.

#### preview

- Section 1's 11 items bind to one source each in a two-column table: `MacroDroid` and `Idle Obelisk Miner` to developer channels, `Tailscale` to its changelog, `Arena.ai` to its product changelog. `OpenGym` binds to GitLab releases, the rest to GitHub releases. No URL embeds, because the report's `Source` cell must carry the direct official link found at run time.
- Section 3's 30 rules keep their order under four `###` groups: Release baseline, Release recommendation, Findings table, Branch audit. The report's 1-to-5 numbering holds.
- Commit-history-first stays a MUST, commits and diffs stay primary with aggregates only checking, and aggregate file counts stay NEVER. The private-repo rule keeps public-plus-wiki recommendation with NEVER-public.
- Section 4 keeps two LiteLLM identifiers distinct: merged PR #39157 tracks by head commit `9e7cfee8d7cba55dbf11b61d2d2fdce94c70037e`. The merge commit `59da6e75a50024dcca1af5efa90e4eec340b89b` stays referenceable but untracked, and notification waits on an official stable release.
- Section 1's eleven URLs were each verified before writing: five GitHub releases pages through the API, `https://tailscale.com/changelog` and both Play listings fetched live. `https://arena.ai/company/product-changelog` came from its page, and the GitLab path for OpenGym builds from release-mirror reports since `gitlab.com` is unreachable — the one unfetched URL here. Headroom stays `unresolved:` with three candidate repos inline, because guessing would put a fabricated source in a monitoring prompt.
- The two Play rows then became the official version channels the evidence showed exist: MacroDroid's listing shows `Updated on Sep 8, 2026` with no version. Idle Obelisk Miner's carries `v2.2.15` in What's new, so the store reports per-app differ and full history lives off-store.
- `https://idleobeliskminer.com/patchnotes` publishes release by release (v2.2.21/v2.2.20 in September 2026, v2.2.15/v2.2.14 on 31 August). MacroDroid's forum board `macrodroid-news-and-announcements.3` is the developer's stable `[UPDATE] 5.x` channel, so `version history` wording is gone rather than reworded.
- Section 5 now defines what it left to the model: empty-run output on a surface that cannot send nothing. Also: a 🔴 High legend for blocking or secret-exposing findings with 🟠 and 🟡 as assigned.
- One-line meanings for `Ver.`, `Source`, `Evidence`, `Docs`, `Section`, `Why` and `Latest checked version`, plus a closed `Status` enum. Its four example rows use `example.invalid` and `v0.0.0` on purpose. A file a model copies must hold no value it could mistake for a finding.
- A request amended the stamp timing: `before monitoring` becomes `after the report is written, using this run's actual start time`. A dying run then leaves the previous stamp, and the next re-covers the window instead of swallowing it. The prompt states that a re-covered window may repeat an item, because repeating costs less than missing a release.
- Section 1's sources now resolve — `headroomlabs-ai/headroom`, `maziggy/bambuddy`, `DuarteSantos8/opengym`. The `unresolved:` row and skip rule are gone, and all eleven items carry one fetched-or-mirrored URL.
- Two traps encode with the swap: MacroDroid's `Beta Releases` board exists because Play review times are long. The announcements board is the only stable source named. Play's `Updated on` shifted `Sep 11, 2026` at `?hl=en` against `31 Aug 2026` at `?hl=en-SG`, so a listing pinned `&hl=en` may corroborate but never sources a version.
- A correction fixed the runtime facts on account, superseding what `DAILIES.md` and root `AGENTS.md` claimed: the task runs at most daily plus on request. The GitHub connector reads and writes this account's repository, and a terminal with local files exists when the task chooses it. The old `no shell and no git` was wrong, and `no repo access` too absolute.
- The ladder is new to the rule files: both refs carry all seven rungs in full upstream wording. The rungs: needed at all, already here, stdlib, native feature, installed dependency, one line, minimum code, plus the reflex-not-a-research caveat and the two-rungs-take-the-higher tie-break. Live compresses to one enumerated list and one caveat.

#### automations

- **Automations and Arena enforcement**: A new top-level `automations/` holds `DAILIES.md`, the combined daily monitoring prompt. It rewrites to `rules/refs/GUIDELINES.md` as a self-contained file, then refits for the ChatGPT scheduled task that runs it.
- The same pull request closes the gap that left `ARENA.md` unenforced: an in-file rule requires an Arena agent to open it before its first edit. A validator gate covers the root copy. The fixed loading premise carries a recorded bootstrap line, and post-sync verification joins the distribution workflow.
- `automations/DAILIES.md` stays untracked by request, with its size history in Git.
- **Deferred**: no `automations/` README, no `check.py` validation of `DAILIES.md`, no root read-first link or Automations section. Distribution stays dispatch-only, so a repository between dispatches receives `ARENA.md` only when added to `REPOS`. The ask-discipline set is the voted one: prefer the question tool, ask before implementing, never block an unattended run.
- The embedded-datetime MUST stays by design with its timing amended on request, and every other opened item closes inside this entry.
- A critique pass against the real runtime preceded the refit: the prompt targeted a file-based coding agent. It demanded state a scheduled task lacks, tools it does not have and two sources that publish otherwise.
- Findings 1, 6–9, 11 and 12 amend here. Findings 4 and 5 answered with facts. Findings 13 and 14 rejected: the file stays self-contained and one combined run.
- Finding 2 stays as written, and 3 stands disputed with evidence below.
- State anchors to automation metadata instead of memory: `## Run state and evidence` reads `last_run`, `next_run`, `updated`, `timezone`, `schedule`, `enabled`, `paused_count`, `completed_count`, and sections 1 and 3 say `inside the comparison window`.
- Evidence then reversed part of the refit: runs sometimes edit the prompt, stamp landings vary, metadata itself errs. The embedded datetime is the running record.
- The window starts at the later of it and `last_run` and widens on lag or paused growth. A metadata-less run falls back to the embedded stamp alone. Disagreements name themselves in Coverage.
- It carries no repo-edit reach. `automations/DAILIES.md` relabels its stamp `Last completed run started (UTC+8, Asia/Manila)` so no editor rewrites it to now and destroys the coverage window.
- Two items defer by choice: `automations/README.md`, worth writing once a second automation exists, and the narrow `DAILIES.md` validator. Its scope: `simplified:` count against section-1 rows, section-5 names, one URL per row, parseable stamp. Later cost and rationale dropped it.

#### maintenance

- `maintenance/check.py`'s parity gate caught a placement error in this round: the unattended-run rule sat live in Constitution while refs has it in Scope. The rule moved to Scope, because a live file may merge lines but never add rules.

### Removed

#### rules

- `rules/AGENTS.md` dropped a Constitution-duplicate keep-behavior line and merged two Ruff-restating lines. `rules/ARENA.md` takes nine word-level trims and `rules/CHATGPT-MORE.txt` four telegraphic trims, while `rules/CLINE.md` and `rules/COMMIT_SPEC.txt` deliberately decline.
- **Adapted skills removed, ponytail rules restored**: Both adapted skills are gone with every reference. The rules keep the 2026-09-09 ponytail-lite set and regain all six 2026-09-11 parts at the voted intensity.

## 2026-09-12

### Added

#### rules

- `rules/AGENTS.md` gains the Arena clause (MUST also read and follow the repo's `ARENA.md`, supplements, NEVER replaces) plus the generally applicable amendments. These: strict-necessary scope, the test gate, material-ambiguity definition, relevance-conditioned lazier alternative, Mermaid where the surface renders it and `no unnecessary prose; detail when the task or user requires`.
- `rules/ARENA.md` mirrors those amendments and adds two Arena-only clauses: Verification requires stating a question batch's total with Q1/Q2 labels. NEVER add one without restating the total.
- The round adds the missing skeleton sections: ARENA and its ref gain an 11-line `## Constitution` and `## When in doubt`. CLINE and its ref gain `## Use` stating it loads beside the global core with scope, precedence and user-override for both, plus a one-line closer. CLINE deliberately has no constitution to avoid duplicating the core, recorded in `rules/README.md` Formatting.
- `rules/ARENA.md` gains the two Arena-only session-failure rules under Verification: question tool failing or partial falls back to plain text with same labels and totals. Duplicated or disowned messages receive a one-line confirmation before acting, amended in refs first. ARENA emphasis moves to the rule that failed: `Report honestly...` keeps its `NEVER` and loses bold, while `NEVER use the -f body=@<path> form; pass --arg-built JSON on stdin` gains it, with the inventory following.

#### maintenance

- It gains `## Repository type`, `## Style`, `## Boundaries` and `## When in doubt`, keeping every repository-specific fact from read-first list to the two bold clauses. Its markdownlint claim matches the configured globs.
- `maintenance/check.py` gains two gates, each proven by breaking the invariant. First: markdownlint scope recomputed from `.markdownlint-cli2.jsonc` (globs minus ignores, `/**` patterns expanded recursively since `Path.glob` resolves trailing `**` to directories only) against the recorded list and documented counts.

### Changed

#### rules

- **September amendments land**: Every September amendment now lands, including 4 and 7 once ChatGPT opened its second custom-instruction field. The instruction set aligned to `rules/refs/GUIDELINES.md` behind a full audit, two CI gates and a validator pass.
- `rules/CHATGPT.txt` takes amendments 1, 2, 3, 5, 6 and 8 inside its 1,500-char limit: RESPONSE avoids unnecessary prose while allowing detail when required. Mermaid becomes the default for pipelines/diagrams/flow with `flowchart TB`, short labels and no wide rows. SCOPE covers requested work plus strictly necessary implementation with `NEVER add tests unless requested/needed to verify`.
- CODE names a lazier alternative only when relevant, and GITHUB prints the planned final commit list.
- Amendments 4 and 7 define material ambiguity covers readings that could change behavior, data, interfaces, scope or outcome. Non-material resolves by the most reasonable assumption, stated when material. They defer from ChatGPT, which keeps `Ask only on material ambiguity.` while `rules/AGENTS.md`, `rules/ARENA.md` and all refs take them in full.
- Add them when ChatGPT spare frees up.
- Root `ARENA.md` re-copies byte-identical, matching what `distribute-arena.yml` pushes. The round amended `rules/refs/` first per Baselines: `refs/AGENTS.md`, `refs/ARENA.md` and `refs/CHATGPT.txt` hold full uncompressed wording, including `before committing` and `no unnecessarily wide rows` where live compresses. Refs/CHATGPT omits 4 and 7 so its baseline mirrors its live file.
- `rules/README.md` renames the printed list in the Emphasis note and commit-disciplines table so the spec stays truthful about amendment 6. `rules/CLINE.md`, `rules/COMMIT_SPEC.txt` and root `AGENTS.md` stay untouched: the overlay is platform-specific and the spec carries no list rule. The Arena clause belongs to the distributed core by decision.
- Every cut removes illustration only with rules kept whole in refs.
- `rules/refs/GUIDELINES.md` is new: the user's `Guidelines: writing an AGENTS.md` saved verbatim as the audit standard, no provenance header per direction, in eight sections. They cover what AGENTS.md is, the threat model, structure, rules that survive, precedence and scope, size and economy, skeleton and checklist. It stays a reference, never a baseline: indexed in `rules/refs/README.md`, `rules/README.md`, root `README.md` and root `AGENTS.md`'s read-first list, with markdownlint at 8 files and 0 issues.
- The round clarifies the refs workflow where it contradicted itself. Amend `rules/refs/` first, mirror the amendment compressed into the live file, then squash that live file under budget. Refs stay unsquashed as baseline.
- That replaces `amend refs and the live rule together` in maintenance item 10 and Baselines, stated in `rules/refs/README.md`, root `AGENTS.md` and root `README.md`.
- `rules/refs/AGENTS.md` audited to the skeleton: a leading `## Use` (what it is, covers all code agents and sessions, outranks skills and plugins, explicit chat instruction outranks it). Its Arena clause names `ARENA.md` as collision winner for push and PR. It gains a 9-rule `## Constitution` restating existing rules one per line with none invented, and a closing `## When in doubt`.
- Skills-precedence and Arena clauses move from `## General` into `## Use`: 63 → 97 lines, inside the ~200-line ceiling.
- Guideline 4.1 reflows `Debugging`, `Testing` and `Code style` from paragraphs to bullets in refs and live with live `Review` following. It fixes the stray blank line splitting `Engineering`. Guideline 4.7 rewrites seven non-dangerous negations positively while NEVER stays on irreversible, dangerous and honesty rules.
- The NEVER list: dependency for a few lines, trust-boundary validation, data-loss handling, security, accessibility, inventing an API and arbitrary fallback. Then hidden failure, unrevised assumption, weakened test, unrun-check claims and unasked push or PR. `rules/README.md`'s Emphasis note and `rules/refs/README.md` record the split.
- The hold on `rules/refs/ARENA.md` and `rules/refs/CLINE.md` lifts on request and both take the skeleton. `rules/CHATGPT.txt` still cannot hold `Use`, Constitution or `When in doubt` headings inside 1,500 chars, so it carries one rule per plain line. A ceiling, not an oversight.
- The full guideline audit found and fixed the violations. Guideline 4.1 ranked largest: refs ARENA held one 1,790-char line in a 12-line file, refs AGENTS a 544-char line, refs CHATGPT five long lines.
- So all files are one rule per line: refs move 56 → 167 lines (ARENA), 97 → 135 (AGENTS) and 9 → 30 (CHATGPT). Live mirrors compressed.
- Lines that stay long each carry one rule with its parameters or exact command, which 4.1 and the skeleton's `exact settings` allow.
- Guideline 4.4 makes `rerun checks` and `re-verify` become `recheck` with ARENA's Ruff wording aligned to the core. Guideline 4.7 extends to ARENA and ChatGPT for the same six clauses. Refs AGENTS bolds the honesty rule, with every file staying at or under two bold clauses.
- New merge amendment on request: fast-forward when possible, and on divergence rebase onto the target first, then fast-forward. Full wording sits in refs, with live compression `on divergence, rebase onto the target first, then fast-forward` and ARENA constitution `Merges MUST be fast-forward; on divergence, rebase first`.
- It agrees with ARENA's existing `--force-with-lease` rule and lands in AGENTS, ARENA, root copies and root `AGENTS.md`. It skips `rules/CHATGPT.txt` per direction while CLINE inherits and COMMIT_SPEC stays a format reference. `rules/README.md` records it in the Arena note and commit-disciplines table.
- Full audit against `rules/refs/GUIDELINES.md` and this repository's specification, every finding grepped or measured rather than recalled. It also caught the constitution inversion this pull request introduced. Refs AGENTS held 11 compound lines where live carried 14 atomic rules.
- The round fixes refs workflow wording in six places. The phrase `copy the amended baseline onto its live counterpart, then squash` becomes `mirror the amendment into its live counterpart in compressed form, then squash that file` across `rules/README.md`, `rules/refs/README.md`, root `AGENTS.md` and root `README.md`.
- README Compression item 4 rescripts to the squash step: keep `the section headings and order the refs baseline already has`. Restructuring is an amendment made in refs first. The old wording contradicted it against this round's own renames (`Repo type`, `Markdown`, `Lightweight repo`) and new sections.
- The same pass disambiguates the `squash` skill as an extraction of the compression rules, not of the guidelines.
- Emphasis cap scoped and inventory fixed in `rules/README.md`: two bold clauses apply to deployed rule files and refs baselines, not spec, skills or workflows. The inventory names what is actually bold: honesty rule, planned final commit list, `STOP` and self-assignment ban, two markdownlint settings. The redundant MD007 pin leaves `.markdownlint-cli2.jsonc` with its bolded clause, markdownlint staying clean over all 8 files.
- MD060 sits at default `any`, MD007 at default indent 2.
- `rules/refs/README.md` names the guidelines parts describing a platform this repository does not use — section 1.2's Kilo loading and `<system-reminder>` wrapping, section 2.1's `kilo/enforce-rules-plugin/` pointer. The guidelines text stays verbatim per direction.
- The lint scope went stale by hand twice, and the parity gate reproduces the inversion that prompted it. A third gate — root ARENA byte identity — came and went on direction, since `cp rules/ARENA.md ARENA.md` needs no validator.
- Validation lives in root `AGENTS.md`, `maintenance/README.md` and a `rules/README.md` note. No rule-file budget changed, the only content edit being the unbudgeted refs constitution split.
- Two audit findings resolve on direction so they stay closed: ARENA.md must keep duplicating the core because Arena loads it without `AGENTS.md`. It stands alone rather than overlaying. Root `ARENA.md` stays a plain copy refreshed by `cp` after every amendment for `distribute-arena.yml` to push.
- Full wording sits in refs, compressed live and root. `rules/ARENA.md` gains it with constitution 11 → 8 rules kept for irreversible, honesty-bearing or historically violated duty.
- The three dropped headlines stay in body sections, and all 11 remain in refs. A lossless squash funds the rest: Use tail, one open-prompt example, the ladder's `helper/pattern already here`, the Ruff frame, `is a violation, not an oversight` and the PR-body fold. Then the `@/tmp/pr_body.md` example, the PATCH re-fetch, `always commit locally` and the merge rule's redundant tail.
- `workflows/init-docs.md` section 10 rewrites to this repository's skeleton so it no longer ships a template failing its own standard. The standard: Use with scope and precedence, a constitution, one testable rule per line, exact commands, a closer, plain requirements instead of mixed modals. A request reverted its funding squash.
- Templates keep their readable form. README Compression marks the file an accepted baseline rather than deferred debt.
- Remaining audit findings record as recommendations: ChatGPT amendments 4 and 7, the missing `skills/web-interface-guidelines` license and persona-style rules marked deliberate. ARENA emphasis lands on the one violated rule. Also a three-line CHANGELOG summary convention and the two session-failure rules that belong in ARENA alone as Arena-client behaviors.
- ChatGPT then uses both fields: the RESPONSE block moves to `rules/CHATGPT_RESPONSE.txt`. Refs carry each field uncompressed and `maintenance/check.py` measures, parity-checks and enforces the 1,500-char limit on both.
- This round records persona rules as deliberate, not rewritten: `Concise, direct, practical, accurate`, `Write clear, readable code`, `Never lazy about understanding`, `Criticize all` state voice. Per guidelines 2.3 and 4.8. `rules/README.md` gains a Persona rules subsection so audits read them as marked corner cuts.
- This changelog adopts the summary convention recorded in its header, and entries below 2026-09-12 predate it and keep their form.

#### preview

- Verification also ends blocks with an open prompt. Response requires reporting changes in the final reply at a high level after the task, not during execution.
- Git's bold clause reads `print the planned final commit list`. Mermaid stays banned because Arena cannot render it.
- The three — `Stage only task-related files; ...`, `Fix root causes, not symptoms; ...` and `Ground every choice ...` — each split in two per guideline 4.1.
- New ARENA rule on request: report and audit artifacts mark each finding's disposition where recorded, striking through resolved findings. A re-read then shows what stands.

#### workflows

- `.github/workflows/validate.yml` installs Ruff at the version `ruff.toml` pins, parsed from that file, and runs `ruff check.` then `ruff format --diff.` after the README maintenance commit. The rules mandated both gates while CI enforced neither. A style regression once merged green, and this round explicitly authorized adding CI.

#### maintenance

- Style specs reorder on request across AGENTS, ARENA, root and both refs. The `ruff.toml` spec reads Ruff defaults first, then indent, lint ignores and safe-fix extensions with `required-version` last. Markdownlint stays `defaults + MD060, MD013 off` after naming MD007 proved redundant against its default indent of 2.
- `ruff.toml` and `.markdownlint-cli2.jsonc` stay unchanged.
- CI plans no STE linter, and the gates stay markdownlint plus `maintenance/check.py`.
- Second: refs/live parity requires identical sections in order with each live section at or below its refs rule lines. The same relation holds for CHATGPT and COMMIT_SPEC.
- `skills/web-interface-guidelines` bundles its upstream license — `LICENSE.txt`, MIT, Copyright (c) 2025 Vercel Labs, fetched upstream, declared in frontmatter. `maintenance/check.py` fails any skill recording `metadata.upstream` without `license` or with a missing file, verified by deletion. `skills/README.md` loses its now-false no-bundled-license claim.
- Deferred: nothing.

### Removed

#### rules

- A request removes the guidelines' `Lint and test` section: the STE CI linter, read-as-the-agent-sees-it check and compaction probes go. `Skeleton` and `Checklist` renumber 8/9 → 7/8, and their two orphaned checklist items go with them. The file lands 81 lines from 90.
- Root `AGENTS.md` takes the same skeleton and ends its contradiction with `rules/ARENA.md`: the `Never push or open a pull request unless asked` clause drops on request. `## Use` states Arena's handling — including push and PR — wins there. It gains an 8-line `## Constitution` and a `## Verification` listing the four gates in run order plus what `validate.yml` runs.
- `rules/CLINE.md` and its ref drop `## MCPs` on request — `tokensave`, `context7`, `memory` — taking the orphaned `tokensave` mention and the `Use only if installed/configured; NEVER invent tool names` lead. `rules/README.md` Formatting loses its stale markdownlint claim, since the globs lint 8 files including all five in `rules/refs/`.

## 2026-09-11

### Added

#### rules

- `rules/ARENA.md` gains criticism duties (`Criticize everything: docs may be stale; code may be wrong`) and the local-only report workflow with `NEVER push` and next-turn undo. It compresses in two squash passes: preamble, punctuation, Engineering, Verification, Style, Git, Deliverables and pass-2 trims.
- ARENA adds `clean timeline`, `one message per logical change` and `updated in place`. CHATGPT regains `yet clear` and `detail on request`.
- Incorporated ponytail ultra-as-suggested per vote: five parts soft via consider/prefer — scope-challenge with how-never-what, skipped/add-when, shaping heuristics, decision heuristics, one-check minimalism reconciled with reuse-existing. Plus the hard MUST grep every caller and fix once where callers route through, ARENA mirroring all six condensed.

#### preview

- Added `ruff.toml` with exactly the amended conventions

### Changed

#### rules

- `rules/ARENA.md` replaces Use with the Arena-agent preamble (every chat, task, first message, explicit-override `confirm`) and appends Engineering per-case dependency approval. Verification gains `grep-verify` with scripted splice and repo validation entrypoints. Style takes `ruff.toml` conventions plus Ruff gates.
- `rules/ARENA.md` fixes the REST PATCH snippet (`--arg title <title>`, `repos/<owner>/<repo>` prefix), sets criticism venue to chat and reports, and caps reports at MD013 120. `rules/AGENTS.md` drops the squashed commit list (generic agents commit directly) and gains the Ruff style rules.
- `rules/CHATGPT.txt` strengthens inside 1,500 chars: NEVER mermaid unless asked, NEVER filler or essays, spelled-out Conventional `<type>(scope): subject`. `maintenance/check.py --update` manages the README date (UTC) with timezone-aware DTZ011 fixed. `rules/apply.py` gains `--yes`/`--dry-run` and a missing-source guard, and `apply.bat` forwards args.
- `rules/README.md` moves install and selection detail into `skills/README.md` and `workflows/README.md`, crisps Rule maintenance to ten one-line items with subsections. It documents the MD007 pin that `.markdownlint-cli2.jsonc` now sets explicitly. New `ref/` baseline: tracking copies of the five agent-facing rule files snapshotted from `main` `dcea8d3` (2026-09-10) for agents measuring without history, refreshed on intentional rebaselines.
- `rules/ARENA.md` pins `required-version = "0.16.6"` in its `ruff.toml` spec and keeps a single updated-in-place report file. It drops the `rosters` example and restated `atomic` while keeping the `-f` war story. `ruff.toml` sets the pin so gates run pinned defaults, `rules/AGENTS.md` records it, and `maintenance/README.md` documents the `TIKTOKEN_CACHE_DIR` offline path.
- `ref/` moved to `rules/refs/` via `git mv` with references relinked, and baselines rebuilt clause-by-clause from `main` history (`7841d84`–`dcea8d3`) so each keeps its longest historical sentence form. Restored squash victims: `without exception`, `one message per logical change`, `step-by-step`, `not the symptom`, plan/TDD/commit bullets, while removals stay removed and MUST/NEVER markers stay.
- COMMIT_SPEC equals live, never compressed.
- Squash audit verdicts: no silent meaning loss. Nine weak wordings turn explicit: AGENTS regains `replace a convention`, exact per-logical-change plans, `not the symptom`, `no speculative behavior or tests` and `deleted once used`.
- Rule maintenance now requires dual amendment: every change amends `rules/refs/` full and the live file compressed together so originals are never lost. Item 10, Baselines and `refs/README.md` agree. Compressing the incorporated ponytail text against refs: AGENTS takes six cuts.
- ARENA restores the search object (`searching for a helper`) after weak-grade inference drew a flag, and refs diffs recheck as OK-class.
- ChatGPT stays untouched for ceiling room, the skill itself unchanged at canonical lite/full/ultra.
- Compression Pass 1 against refs: AGENTS six cuts (bare-plural universal, order-encoded `then`, articles, possessive, strict reuse-entails-existing, parallel ellipsis). ARENA six cuts (ones-ellipsis plus five rationale drops kept in refs). Pass 2 found no safe cuts with CHATGPT/CLINE/COMMIT_SPEC at floor.

#### preview

- Git takes local-only report commits with REST PR updates and squashed-timeline bodies, and Deliverables regenerates doc sections.
- Pass 3 found no safe cuts. `.gitignore` gains `reports/` so artifacts live in an ignored dir, force-added to a local-only end-of-turn commit for the diff viewer.

### Removed

#### rules

- `rules/COMMIT_SPEC.txt` drops its MUST-print clause, and ChatGPT keeps its list.
- `rules/refs/README.md` drops the `deleted-rules` audit-trail sentence per direction with baselines unchanged.

### Fixed

#### rules

- Fixed `rules/refs/AGENTS.md`: dropped the MUST-print bullet the rebuild resurrected. Generic agents are exempt, the deletion stands, and the baseline matches its own methodology note.

## 2026-09-10

### Added

#### rules

- Added a disabled `distribute-arena` workflow template (`.github/workflows/distribute-arena.yml.disabled`): manual dispatch pushes `rules/ARENA.md` to each listed repo over HTTPS with a short-expiry `ARENA_DIST_PAT`. It amends the prior sync commit when HEAD is one and commits only on change. The default list holds `nemoe7/clankers`, a dispatch input overrides it, and renaming to `.yml` enables it.

### Changed

#### rules

- The squash trims `replace a convention` to `convention`, `behavior or tests` to `tests`, `corrected` to `fixed`, `per completed feature` to `per change`, `root cause not the symptom` to `root cause` and dropping `step-by-step`. `rules/ARENA.md` condenses the same rule as `Commits MUST be atomic: one logical change with every file in it, checks green, independently revertible`, gaining the completeness half the core had.
- Squashed `workflows/init-docs.md` over four passes, merging same-subject bullets and cutting filler with headings, order, lists and code blocks. Every rule, condition and identifier stays preserved. `rules/ARENA.md` gains a handoff clause in Workspace: MUST maintain a handoff document (goal, done, next, key files/decisions) updated as work lands.
- Scratched the handoff document: `rules/ARENA.md` now always pushes the branch and keeps a PR open so work survives limits. It folds fixes into the squashed atomic timeline, matches the PR body to it and rewrites remotes with `--force-with-lease` never plain `--force`. The rules spec records the intentional push/PR divergence from the core.
- `rules/ARENA.md` now disregards never-push rules (Arena controlled edits make pushing safe, judged safe for now) and NEVER merges the PR until authorized.
- Gates stay green.

#### preview

- The handoff clause pins its lifecycle (NEVER commit or gitignore: untracked, local, downloadable). Scope's ask rule becomes MUST stop and ask on deviating reasoning or material ambiguity only.
- The document then names its contents (goal, requirements fulfilled, done, next, decisions, key files) and must resume work without re-asking.

#### maintenance

- The `workflows/` directory integrates: a new `workflows/README.md` index describes the portable single-file format. Root README gains a layout bullet, root `AGENTS.md` a read-first link. The Workflows section gains updated validator notes, the rules spec gains a contents row with a selection table, and `maintenance/README.md` describes the new checks.
- `maintenance/check.py` checks the workflows listing against `workflows/README.md`, requires a `description` frontmatter field per workflow, checks internal links in the index, and budgets `workflows/init-docs.md` in `cl100k_base` tokens. The lightweight-repo rule now prohibits further CI workflows, since the old wording read as banning the new directory. No budgeted file changed.

## 2026-09-09

### Added

#### rules

- ChatGPT gains ponytail at `lite lite`: ladder compressed to `reuse what's here > stdlib/native > installed dep > minimal code`, no dependency for a few lines' work and no unrequested abstraction. It adds build then name the lazier alternative and the never-simplify list, costing the `Prefer write-block for full markdown` UI note and the `Corrections: error and fix` line. SCOPE's dependency clause folds into CODE's.

### Changed

#### rules

- `rules/AGENTS.md` Engineering carries ponytail at `lite` intensity inline: the ladder (needed at all, existing helper/pattern, stdlib, native feature, installed dependency, one line, minimum code). Build-what-is-asked follows with the lazier alternative named in one line. Also: the never-lazy caveat, the never-simplify list (trust-boundary validation, data-loss error handling, security, accessibility), a `simplified:` corner-cut comment and no-unrequested-abstraction rules.
- No rule file loads or names the skill: the marker is `simplified:` not `ponytail:`. The spec's skill table records that the rules no longer load it. The skill stays in `skills/ponytail/` for `full` or `ultra`.
- No rule file now requires loading any skill.
- Root `AGENTS.md` is a repository guide only, independent of any skill or personal rule set. It covers what the repo is, verification, skill specification, rule-file locations, budgets, Markdown and Python style, commit format and lightweight constraint. It carries no skill loading order and requires following this changelog's entry rule.
- `skills/planning` triggers in plan mode, its description saying to use it whenever you are in plan mode.
- `rules/ARENA.md` tracks the core again: ponytail-lite ladder, never-simplify list and `simplified:` comment. It gains an Arena rule to work in passes and ask for feedback with the question tool. It asks before another round and ends with an open question.
- The squash merges General, Scope and Verification lists into paragraphs.
- Every rule file marks hard rules with `MUST`/`NEVER` and rations bold to exactly two clauses: the honesty rule and the squashed commit list. In CLINE the two are stopping after a requested command and never self-assigning. `rules/AGENTS.md` is the core the others mirror, and the spec records maintenance rule 5: emphasize the rules most often violated.
- A third bold clause requires a demotion.
- ChatGPT's mermaid clause tightens to `Mermaid ONLY when structure/flow beats prose, NEVER for lists or decoration`, keeping shape constraints, plus the squashed commit list and unrun-check ban.
- The squashed commit list becomes unmissable after practice ignored it: `rules/ARENA.md` opens its Git section with it bold as a standalone paragraph. `rules/AGENTS.md` leads its Git list with a MUST bullet. Both state that committing without printing it is a violation, not an oversight.
- An unlisted commit requires printing the fixed timeline before the next one. Compression guidance runs to exhaustion: README step 1 repeats passes until one yields nothing, matching the `squash` skill's loop.
- Staging now respects the user's global gitignore (`core.excludesFile`), `AGENT_HANDOFF.md` is never committed overriding the skill's requirement, and a minimal root `AGENTS.md` points to README and changelog.
- The clauses rose `rules/AGENTS.md` over budget with compression declined (+41).
- AGENTS.md makes committing mandatory (atomic, Conventional, off `main`) by folding the push/PR allowance into the commit clause. It removes the only-when-required permission, scoped to AGENTS.md only. It squashes with the `squash` skill (`belonging to it` → `in it`, `characters` → `chars`).

### Removed

#### rules

- Removed the `agent-handoff` skill and every reference: the directory, `skills/README.md` and `maintenance/check.py` entries, the spec's Handoff sections and the handoff clauses in `rules/AGENTS.md`. No mandatory load, no read before changes, no plan updates, no commit exclusion. Planning's own plan-to-implementation `Handoff` phase stays, unrelated.

#### maintenance

- The workflow stops hardcoding lint globs, leaving `.markdownlint-cli2.jsonc` the single lint-scope definition, and drops the dead `templates/` exclusion.

### Fixed

#### rules

- Fixed stale documentation: `maintenance/` is not dependency-free: root README, spec and `maintenance/README.md` state `check.py` needs `markdown-it-py` and `tiktoken` with an install command. The installer is `rules/apply.py` not `apply_rules.py`. With `.github/workflows/validate.yml` existing, the no-CI claims go and the lightweight rule reads `no further workflows`.

## 2026-09-08

### Added

#### preview

- Added the `squash` skill: iterative text compression against an explicit unit — tokens, words, characters or bytes. It preserves every claim, negation, condition, number, name and caveat. It resolves units by precedence and accepts several budgets as simultaneous constraints with conflicts reported rather than resolved.
- Added `skills/README.md` listing every skill and purpose so the spec links an index instead of a bare directory. Refreshed frontend-design and ponytail from upstream, re-applying the local `Precedence` section that keeps explicit requirements and project conventions ahead of each skill's preferences. Adapted skills now record `metadata.upstream`, first-party skills `metadata.origin`, with `skills/README.md` documenting the requirements and every upstream.

### Changed

#### rules

- Squashed this changelog and `rules/README.md` with that skill: wording only, every claim, number and table preserved. Rule and skill files are no longer hard-wrapped: each paragraph and list item is one line, with licenses keeping their original wrapping.
- The rule installer previews unified diffs and asks once before changing either destination.

#### preview

- Its description triggers on sizing specific text, not bare `shorten` or `trim`, and it depends on nothing in this repository.
- Planning and agent-handoff include MIT license files, planning also declaring its license in metadata. Response rules prefer numbered lists for multiple points. Agents may commit without separate authorization when commits are atomic, conventional, task-only and off `main`.
- ChatGPT still requires it because its integration writes directly to `main`.
- Arena keeps open-PR history reviewable by folding iterative fixes when safe and using lease-protected rewrites. Generic rules always load `agent-handoff` and select other skills when domains fit. Arena and Cline hold no handoff-specific policy, and skills carry no platform exemptions or cross-skill planning requirements.
- Agent-handoff references call it a skill using `SKILL.md` only as its filename.
- The root README tracks all agent rule and skill entry files, using deployment-specific measures for Arena and ChatGPT and tokens for the rest. Arena no longer loads or applies agent-handoff. Plan-file steps and commit checkpoints exempt it explicitly across shared rules, Arena rules, skill discovery, protocol, planning integration and specification.
- Arena still commits atomically on request, and other agents keep the workflow.
- Optimized `ARENA.md` preserving core intent and removing platform-managed branch/push/PR boilerplate. The spec makes file size its maintenance target. `AGENTS.md` forbids committing to `main` without requiring a fresh branch, and the change removes the redundant ChatGPT GitHub-header parenthetical.
- Moved `implementation_plan.md` conventions from the generic planning skill to Cline. Generic file-backed plans still require a handoff-update step. Task work and handoff checkpoints require atomic commits with separate identities and explicit reporting of blocked commits.
- Moved installation guidance to the human-facing rules specification. Agents report missing or incompatible skills instead of changing installed copies, and the count lists only changed instruction files.
- Tracking covers only agent-facing rule files and `SKILL.md` entry points: documentation, references, templates, scripts, configs and licenses stay out. Counts exclude files a skill loads on demand.

#### gpt-plugins

- Ponytail bundles the MIT license it declares, attributed upstream. All six skills conform to the Agent Skills specification, with `argument-hint` moved under `metadata` where web-design-guidelines already kept it.
- Upstream renamed `web-design-guidelines` to `web-interface-guidelines`, and the skill rewrote against the current command: full rule coverage named, terse `file:line` output, the fetched slash command's `$ARGUMENTS` explained. No reviewing from memory when the fetch fails.

#### maintenance

- The root README documents the compression procedure beside the budgets it maintains. Iterate and re-measure, never drop a constraint, keep headings, and compress the rest of a file when a new rule exceeds its budget. Generic rules require repository hygiene: scratch files, scripts and command output stay outside the repo or die once used.

#### docs

- Pull requests open only when the user requires it. Commits still follow atomic Conventional rules, and Arena also outputs a squashed commit list before committing. Local commits and fixes fold into a clean timeline, updated as work lands.
- Generic rules call for a mermaid diagram when structure or flow beats prose and the surface renders it. Shape it for a narrow viewport: top-down, short labels, no wide rows. ARENA.md excludes mermaid because Arena cannot render it, and CHATGPT.txt keeps its guidance in the same wording.

### Removed

#### maintenance

- `CLINE.md` drops its duplicate, Arena relies on workspace-size rules and ChatGPT stays out of scope.

#### docs

- CHATGPT.txt mirrors AGENTS.md structure with a SCOPE section inside its 1,500-character limit, and ARENA.md drops the platform-precedence restatement because Arena applies platform instructions regardless.
