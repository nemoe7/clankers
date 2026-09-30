# Userscripts

Tampermonkey userscripts for Arena.ai and chatgpt.com.

| Bundle | Feature switches |
| --- | --- |
| [arena.user.js](arena.user.js) | Prompt fill, Open Steering, Hide composer, Transcript auto-scroll, Transcript trim, Tab title |
| [chatgpt.user.js](chatgpt.user.js) | Hide elements, Auto Think |

## Install

1. Install Tampermonkey in the browser.
2. Open its dashboard and create a new script.
3. Paste one bundle's `.user.js` contents and save.
4. Repeat for the other domain if needed.

To migrate, disable or remove the five old scripts before enabling the bundles. Reload open Arena and ChatGPT tabs to stop old timers and observers. Old installations do not become bundles automatically.

Each bundle has its own version and raw GitHub update URL. A saved feature setting belongs to its bundle.

## Feature switches

Seven features default to On. Transcript trim ships OFF, because it removes messages from the page. On a matching page, open the Tampermonkey menu and select a command such as `Auto Think: ON — toggle`. The label shows the saved setting.

Switches apply immediately in the current tab. Other open tabs use saved settings on their next reload. Disabling stops the feature’s observers, timers and listeners.

The bundles use `GM_getValue` and `GM_setValue` for saved settings, plus menu registration and removal, and they hold no check code. Switches never reload the page. Disabling a hiding feature restores its own DOM changes where the page has not replaced them. Earlier automatic clicks and inserted prompt text remain.

## Arena Prompt Fill

The feature fills the composer only on exact `/agent`, not paths with a trailing segment.

If the GitHub repo bar is not empty, it reads `owner/repo` from `span.truncate` and uses the name after `/`. It writes `{repo} read AGENTS.md ARENA.md` and updates that text when the repo name changes. It does not overwrite an unrelated draft.

## Arena Open Steering

After `/agent/`, the feature waits 1 second, then clicks the port 8000 row whose label mentions `steering` or `preview`, once per page. A running row wins over the `Start …` cards that earlier turns leave behind, and those cards are never clicked, because a click on one opens nothing. A row naming the repository outranks a renamed row, and the newest row breaks a tie. Matching ignores letter case.

## Arena Hide Composer

On paths with a segment after `/agent/`, a button with `aria-label="Stop generating"` causes the feature to hide `div.editor-content` with the `hidden` attribute, the `hidden` class and `display: none !important`. It restores the editor when that button is gone.

The feature keeps a blank `div.shrink-0` at 24px on `/agent/*` and resets its height if another script changes it.

## Arena Transcript Auto-scroll

On `/agent/*`, ON keeps the transcript at the bottom while the Stop generating button exists. This includes upward scrolling, new messages, resized tool output and session changes. Without that button the composer is visible and the transcript does not follow until the button returns. A toggle button sits in the action row next to Stop generating: pressed while follow is ON, unpressed when OFF. OFF disables follow. The saved menu setting and the button apply immediately.

The feature uses the transcript message marker and its scrollable `role="log"` ancestor.

## Arena Transcript Trim

This switch ships OFF, and OFF stops the trim: a reload redraws the transcript from Arena, so removed rows come back. On `/agent/*`, ON removes the oldest transcript rows. It keeps the newest `1` message whole and cuts it to its last `50` rows. Older messages empty out, and every message root stays on the page. The row count never drops below `20`.

The menu command reads `Transcript trim: 1 message, 50 rows — set`. After a trim it adds the running row count, such as `Transcript trim: 1 message, 50 rows (12 removed) — set`, so a plan above the transcript size reads as no change. The command takes a new plan as `<messages>,<rows>`; one number sets the rows alone. An empty or too small answer keeps the old plan.

The trim waits for the page to settle. It touches nothing while a turn streams or a live icon pulses, and it waits for a quiet window after the last change. A row is a part inside a message: text, a tool call, a thinking line or a status line. Only rows still on the page count, and the oldest attached row leaves first. The page holds fewer nodes, so the tab uses less memory. The Arena client may keep its own copy until you delete the message there.

The message root itself never leaves. Arena complains when a `#chat-message-*` element disappears, and this switch runs inside its tree.

## Arena Tab Title

On `/agent/*`, ON reads the repository name from the GitHub link in the session header and sets the tab title to `Arena | <repository>`. While the agent works, the title adds an emoji for the live action, such as `Arena | clankers 🖥️`. The action text is the shimmering status label, which a thinking row carries without a pulsing icon. The map is running 🖥️, read 📖, edit ✏️, search 🔍, think 💭, wait 💤, and ⚙️ for anything else. Reading covers `Read` and `Explored`, and editing covers `Edit`, `Editing files` and `Write`. `Bash` and `command` count as running, so `using Bash` and `Ran commands` show 🖥️. A row whose command is any form of the preview poll, bare, full path or `preview.py`, shows 💤, because the agent waits on you. The emoji holds for five seconds after the live row leaves, so a gap between calls does not flash the title, and it clears once the turn ends. The feature holds the title against every Arena rewrite. It re-asserts the title each second and keeps the last repository name while the page stays put, so a header re-render never drops it. Switching the feature off restores the earlier title.

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
