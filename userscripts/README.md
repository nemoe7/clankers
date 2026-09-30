# Userscripts

Tampermonkey userscripts for Arena.ai and chatgpt.com.

| Bundle | Feature switches |
| --- | --- |
| [arena.user.js](arena.user.js) | Prompt fill, Open Steering, Hide composer, Transcript auto-scroll, Tab title |
| [chatgpt.user.js](chatgpt.user.js) | Hide elements, Auto Think |

## Install

1. Install Tampermonkey in the browser.
2. Open its dashboard and create a new script.
3. Paste one bundle's `.user.js` contents and save.
4. Repeat for the other domain if needed.

To migrate, disable or remove the five old scripts before enabling the bundles. Reload open Arena and ChatGPT tabs to stop old timers and observers. Old installations do not become bundles automatically.

Each bundle has its own version and raw GitHub update URL. A saved feature setting belongs to its bundle.

## Feature switches

All seven features default to On. On a matching page, open the Tampermonkey menu and select a command such as `Auto Think: ON — toggle`. The label shows the saved setting.

Switches apply immediately in the current tab. Other open tabs use saved settings on their next reload. Disabling stops the feature’s observers, timers and listeners.

The bundles use `GM_getValue` and `GM_setValue` for saved settings, plus menu registration and removal. Switches never reload the page. Disabling a hiding feature restores its own DOM changes where the page has not replaced them. Earlier automatic clicks and inserted prompt text remain.

## Arena Prompt Fill

The feature fills the composer only on exact `/agent`, not paths with a trailing segment.

If the GitHub repo bar is not empty, it reads `owner/repo` from `span.truncate` and uses the name after `/`. It writes `{repo} read AGENTS.md ARENA.md` and updates that text when the repo name changes. It does not overwrite an unrelated draft.

## Arena Open Steering

On paths with a segment after `/agent/`, the feature waits 1 second, then clicks `{repo} - Steering` on port 8000 once per page. Label and repository-name matching ignore letter case.

## Arena Hide Composer

On paths with a segment after `/agent/`, a button with `aria-label="Stop generating"` causes the feature to hide `div.editor-content` with the `hidden` attribute, the `hidden` class and `display: none !important`. It restores the editor when that button is gone.

The feature keeps a blank `div.shrink-0` at 24px on `/agent/*` and resets its height if another script changes it.

## Arena Transcript Auto-scroll

On `/agent/*`, ON keeps the transcript at the bottom while the Stop generating button exists. This includes upward scrolling, new messages, resized tool output and session changes. Without that button the composer is visible and the transcript does not follow until the button returns. A toggle button sits in the action row next to Stop generating: pressed while follow is ON, unpressed when OFF. OFF disables follow. The saved menu setting and the button apply immediately.

The feature uses the transcript message marker and its scrollable `role="log"` ancestor.

## Arena Tab Title

On `/agent/*`, ON reads the repository name from the GitHub link in the session header and sets the tab title to `Arena | <repository>`. While the agent works, the title adds an emoji for the live action from the last agent message, such as `Arena | clankers 🖥️`. The map is running 🖥️, read 📖, edit ✏️, search 🔍, think 💭, wait 💤, and ⚙️ for anything else. A row whose command is any form of the preview poll, bare, full path or `preview.py`, shows 💤, because the agent waits on you. The emoji clears when the turn ends. The feature holds the title against the rewrites that Arena makes on navigation, and it restores the earlier title when the link leaves the page.

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
node --test maintenance/userscripts.test.cjs
```

Each command prints `ok` when its checks pass. The bundles retain the five feature checks. The integration check covers saved switches, reloads, disabled startup, storage errors, transcript growth, forced follow, live cleanup and navigation.
