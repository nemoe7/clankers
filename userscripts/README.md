# Userscripts

Tampermonkey userscripts for Arena.ai and chatgpt.com.

| Bundle | Feature switches |
| --- | --- |
| [arena.user.js](arena.user.js) | Prompt fill, Open Steering, Hide composer, Transcript auto-scroll, Transcript trim, Preview state download, Tab title |
| [chatgpt.user.js](chatgpt.user.js) | Hide elements, Auto Think |

## Install

1. Install Tampermonkey in the browser.
2. Open its dashboard and create a new script.
3. Paste one bundle's `.user.js` contents and save.
4. Repeat for the other domain if needed.

To migrate, disable or remove the five old scripts before enabling the bundles. Reload open Arena and ChatGPT tabs to stop old timers and observers. Old installations do not become bundles automatically.

Each bundle has its own version and raw GitHub update URL. A saved feature setting belongs to its bundle.

## Feature switches

Eight features default to On. Transcript trim ships OFF because it removes transcript content from the page. On a matching page, open the Tampermonkey menu and select a command such as `Auto Think: ON — toggle`. The label shows the saved setting.

Switches apply immediately in the current tab. Other open tabs use saved settings on their next reload. Disabling stops the feature’s observers, timers and listeners.

The bundles use `GM_getValue` and `GM_setValue` for saved settings, plus menu registration and removal, and they hold no check code. Switches never reload the page. Disabling a hiding feature restores its own DOM changes where the page has not replaced them. Earlier automatic clicks and inserted prompt text remain.

## Console log

Both bundles log under one tag, `[clankers]`. The devtools console filter shows the page's story: feature switches on load and on toggle, the prompt fill write, and each state save. A log line never carries a loop, so a busy page stays quiet. No key or message text ever reaches the log.

## Arena Prompt Fill

The feature fills the composer on `/agent` and on `/agent/`, not on paths with a trailing segment.

If the GitHub repo bar is not empty, it reads `owner/repo` from `span.truncate` and uses the name after `/`. The name leads the message, then `read ARENA.md AGENTS.md in full before your first edit, and follow both.` The rest is the initial message. It asks for a full read of the task and the touched files, and for reuse before new code. It asks for a failing check before new behavior, and a root-cause fix for a bug. It asks for stated assumptions, no claim of an unrun check, the steering channel for corrections, and a closing report. The text updates when the repo name changes, and an unrelated draft stays. A return to the composer after a session route is a new chat, and the fill writes it again. The full stop keeps the editor from linking `AGENTS.md` as a bare domain.

The message names the rules files, and the fill appends `rules/ARENA.md` fetched once from the fixed raw URL of this repository: `https://raw.githubusercontent.com/nemoe7/clankers/refs/heads/main/rules/ARENA.md`. The fill waits for that fetch and writes the composer one time per page, the file under a `here is ARENA.md:` line after the initial message. A failed fetch writes the plain message. A second write would put a line break after the name. The editor reads that break as the end of a domain.

### Arena proxy settings and key rotation

The prompt fill stays free of the proxy. The preview carries the proxy host and the key to the agent. Two menu entries save the settings, `Arena proxy host — set` and `Arena proxy master key — set`, and a third, `Arena proxy rotate now — run`, rotates at once. A fourth, `Arena proxy post key now — run`, posts the key the script holds to the preview. It rotates nothing, and a missing key fetches the live one.

- The host is one HTTPS origin with no path. The script trims a trailing `/v1`.
- With both settings saved, the script asks `/v1/key` for the live agent key. The composer holds the rules line only.
- Every 15 minutes the script asks `/v1/rotate` with `min=900`, and each call lands at a random moment inside a 15-second band after the beat. When the backend reports a rotation, the script takes the new key and posts one note to the steering preview. The agent then picks the key up at its next inbox read.
- The script saves the due time, so a reload resumes the countdown. The backend holds the minimum age. An early second tab learns the key's age and waits.
- The note post uses `GM_xmlhttpRequest`, because the Arena page and the preview are different origins. The preview URL comes from the `App preview on port 8000` iframe the page carries.
- The script posts the key and the host it holds to the preview, so the Downloads tab shows both. One quiet note carries the host and a new key to the agent. A saved key keeps a reload or a second tab from repeating the note.
- Every minute the script asks `/v1/key` again, with the same scatter. A new key makes the script adopt it, post it to the preview and send one quiet note. A container restart therefore reaches the agent inside a minute, not at the next rotation.
- `@connect arena.site` names the preview host, the only target of `GM_xmlhttpRequest`. The proxy calls use plain `fetch`, which the proxy's wildcard origin allows, so the owner's proxy host never enters the file.

## Arena Open Steering

After `/agent/`, the feature waits 1 second, then clicks the port 8000 row whose label mentions `steering` or `preview`, once per page. A running row wins over the `Start …` cards that earlier turns leave behind, and those cards are never clicked, because a click on one opens nothing. A row naming the repository outranks a renamed row, and the newest row breaks a tie. Matching ignores letter case.

## Arena Hide Composer

On paths with a segment after `/agent/`, a button with `aria-label="Stop generating"` causes the feature to hide `div.editor-content` with the `hidden` attribute, the `hidden` class and `display: none !important`. It restores the editor when that button is gone.

The feature keeps a blank `div.shrink-0` at 24px on `/agent/*` and resets its height if another script changes it.

## Arena Transcript Auto-scroll

On `/agent/*`, ON keeps the transcript at the bottom while the Stop generating button exists. This includes upward scrolling, new messages, resized tool output and session changes. Without that button the composer is visible and the transcript does not follow until the button returns. A toggle button sits in the action row next to Stop generating: pressed while follow is ON, unpressed when OFF. OFF disables follow. The saved menu setting and the button apply immediately.

The feature uses the transcript message marker and its scrollable `role="log"` ancestor.

## Arena Transcript Trim

This switch ships OFF, and OFF stops the trim: a reload redraws the transcript from Arena, so removed rows return. On `/agent/*`, ON keeps the newest `50` row nodes across all message roots and removes older rows first. It also removes the sibling action container, `div.mt-3.flex.flex-col.gap-3`, from each message that loses rows or holds no row node. It keeps each message root because Arena crashes if a `#chat-message-*` root leaves its tree. The row limit cannot fall below `20`.

The menu command reads `Transcript trim: 50 rows — set`. After a trim it adds the running row count, such as `Transcript trim: 50 rows (12 removed) — set`, so a plan above the transcript size reads as no change. The command takes one row limit. It converts a saved two-value plan to its row limit. An empty or too small answer keeps the old plan.

The trim waits for the page to settle. It touches nothing while a turn streams, a live icon pulses, or a question widget waits for an answer. It waits for a quiet window after the last change. A root the document dropped, and a root whose row nodes sit detached during a redraw, stay untouched.

A row is a child of the outermost `div.flex.flex-col.gap-2` block. It can hold text, a tool call, a thinking line or a status line. Only attached rows count, and the oldest rows leave first.

The page holds fewer nodes, so the tab uses less memory. The Arena client may keep its own copy until you remove the message there.

## Arena Preview State Download

The feature saves the preview state to one file, without a click. It asks the preview once a minute, and the request lands at a random moment inside a 15-second band after the beat. It writes nothing unless the state's newest stamp moved, so an idle preview costs one small request a minute.

The first save asks for the file through the browser's own picker. After that the script fills the same file on every change, with no second question. A browser without the picker downloads a stamped file on a manual save press. With no file set, an automatic save writes nothing. The picker needs the press itself, and a save that waited on the network has none. Press `Arena preview state — choose the file` to pick one.

The name leads with the repository and the branch, and a stamped save adds the stamp and the record counts, such as `clankers-main-20261006T061233-n12-t4.ndjson`. The repository and the branch come from the GitHub bar, so two repositories never collide in one folder.

The feature keys the stamp memory and the chosen file by repository and branch. Two tabs of two sessions never share one file or one stamp chain. A remembered file is reused only when its name carries the current scope, so a file from another repository or branch is never written. The same repository and branch keeps one file, and the picker asks once per repository and branch.

A stamp older than the last write never overwrites the file. The script says so once, quietly, and keeps the older file. A state with no stamp writes nothing.

The script also remembers the newest note stamp and the newest task stamp of the state it wrote. A rollback leaves older records behind while one new record moves the state stamp forward. The script refuses that write and keeps the newer file. A lone note deletion moves one stamp back and leaves the state stamp still, so the script keeps the file and logs no refusal. A state that carries no pair keeps the single-stamp rule.

Three menu entries sit with the feature: `Arena preview state — choose the file`, `Arena preview state — save now`, and `Arena preview state — force save`. The force entry writes the state whatever its stamp says and moves the reference to the saved one. The chosen handle lives in IndexedDB, so a reload keeps the file. The import stays the owner's own command. The feature only writes the file.

## Arena Tab Title

On `/agent/*`, ON reads the repository name from the GitHub link in the session header. It sets the tab title to `Arena | <repository>`. While the agent works, the title adds an emoji for the live action, such as `Arena | clankers 🖥️`. The action text is the shimmering status label, which a thinking row carries without a pulsing icon. The map is running 🖥️, read 📖, edit ✏️, search 🔍, think 💭, wait 💤, and ⚙️ for anything else. Reading covers `Read` and `Explored`, and editing covers `Edit`, `Editing files` and `Write`. `Bash` and `command` count as running, so `using Bash` and `Ran commands` show 🖥️. A row whose command runs the preview poll shows 💤, because the agent waits on you. The command counts when it names the script plus the `poll` word, bare, as a full path or as `preview.py`. A separate `polling` or `polls` word does not count. A waiting line carries a 16px spinner canvas beside rotating monospace text. It shows ⏳ while the model works with no named action and no streamed words. The words rotate per run, so that case anchors on the canvas together with the text block beside it. An action row carries the same canvas as its own icon, so a bare canvas never counts as a waiting line. The emoji holds for five seconds after the live row leaves, so a gap between calls does not flash the title. It clears at the turn end, and the repository name stays in the title. A read or edit group shows no pulse and no shimmer, so while the turn runs the newest group label supplies the emoji. The label is the row's `text-text-secondary` span. That span sits beside the toggle, not inside it. The feature holds the title against every Arena rewrite. It re-asserts the title each second and keeps the last repository name while the page stays put, so a header re-render never drops it. Switching the feature off restores the earlier title.

## Arena Security Check Hold

While the Arena security check shows, the tab title carries the shield emoji and the automatic posts wait.
The held work is the prompt fill, the Open Steering click and the proxy key posts. Each tab reads its own page, so a background tab keeps its own work. The held work resumes when the check clears.

## Arena Userscript Pause

One entry, `Arena userscript — pause all`, stops every feature where it stands: the observers, the timers, the automatic posts and the tab title. The press applies at once, with no reload, and the entry then reads `Arena userscript — resume all`. The resume brings back every feature whose own switch is ON and leaves the others off.

The script saves the pause, so a reload keeps it: a paused page starts with nothing running and still offers the resume. Each feature switch stays in the menu while paused, and a flip is saved for the resume. The security check hold is independent of the pause.

## ChatGPT Hide Elements

On any `chatgpt.com` path, the feature adds `hidden` to eight elements:

- The div that holds the Claim offer button.
- The div that holds the Free offer button.
- The div that holds the Select chat surface toggle.
- The Codex sidebar link.
- The Images sidebar link.
- The Library sidebar link.
- The Free badge.
- The prompt textarea header banner.

A MutationObserver repeats the work when the page changes.

## ChatGPT Auto Think

On any `chatgpt.com` path, the feature clicks the Think pill every second while `aria-pressed` is `false`.

## Check

From the repository root:

```bash
node userscripts/arena.user.js
node userscripts/chatgpt.user.js
node --test maintenance/userscripts.checks.cjs
node --test maintenance/userscripts.test.cjs
```

Each command prints `ok` when its checks pass. The bundles carry runtime code only: outside a browser each feature publishes its helpers through `exposeChecks`, and the feature checks run from `maintenance/userscripts.checks.cjs`. The integration check covers saved switches, reloads, disabled startup, storage errors, transcript growth, forced follow, live cleanup and navigation.
