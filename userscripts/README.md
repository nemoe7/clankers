# Userscripts

Tampermonkey userscripts for Arena.ai and chatgpt.com.

| Bundle | Feature switches |
| --- | --- |
| [arena.user.js](arena.user.js) | Prompt fill, Open Steering, Hide composer, Transcript auto-scroll |
| [chatgpt.user.js](chatgpt.user.js) | Hide elements, Auto Think |

## Install

1. Install Tampermonkey in the browser.
2. Open its dashboard and create a new script.
3. Paste one bundle's `.user.js` contents and save.
4. Repeat for the other domain if needed.

To migrate, disable or remove the five old scripts before enabling the bundles. Reload open Arena and ChatGPT tabs to stop old timers and observers. Old installations do not become bundles automatically.

Each bundle has its own version and raw GitHub update URL. A saved feature setting belongs to its bundle.

## Feature switches

All six features default to On. On a matching page, open the Tampermonkey menu and select a command such as `Auto Think: ON — toggle; reload to apply`. The label shows the saved setting, not the active page state.

Reload manually to apply a change. Other open tabs use saved settings on their next reload. A disabled feature starts no observer or timer.

The bundles use `GM_getValue` and `GM_setValue` for saved settings, plus menu registration and removal. A switch change does not reload the page or reset the DOM.

## Arena Prompt Fill

The feature fills the composer only on exact `/agent`, not paths with a trailing segment.

If the GitHub repo bar is not empty, it reads `owner/repo` from `span.truncate` and uses the name after `/`. It writes `{repo} read AGENTS.md ARENA.md` and updates that text when the repo name changes. It does not overwrite an unrelated draft.

## Arena Open Steering

On paths with a segment after `/agent/`, the feature waits 1 second, then clicks `{repo} - Steering` on port 8000 once per page. Label and repository-name matching ignore letter case.

## Arena Hide Composer

On paths with a segment after `/agent/`, a button with `aria-label="Stop generating"` causes the feature to hide `div.editor-content` with the `hidden` attribute, the `hidden` class and `display: none !important`. It restores the editor when that button is gone.

The feature keeps a blank `div.shrink-0` at 24px on `/agent/*` and resets its height if another script changes it.

## Arena Transcript Auto-scroll

On `/agent/*`, the transcript follows new messages and resized tool output when it is within 80px of the bottom. Scrolling up pauses follow. Scrolling down to within 80px resumes it.

The feature uses the transcript message marker and its scrollable `role="log"` ancestor. It preserves a reading position when the transcript or session changes. Adjust `BOTTOM_GAP` in the script if needed.

## ChatGPT Hide Elements

On any `chatgpt.com` path, the feature adds `hidden` to five elements:

- The div that holds the Claim offer button.
- The div that holds the Free offer button.
- The div that holds the Select chat surface toggle.
- The Codex sidebar link.
- The prompt textarea header banner.

A MutationObserver repeats the work when the page changes.

## ChatGPT Auto Think

On any `chatgpt.com` path, the feature clicks the Think pill every second while `aria-pressed` is `false`.

## Check

From the repository root:

```bash
node userscripts/arena.user.js
node userscripts/chatgpt.user.js
node maintenance/check_userscripts.cjs
```

Each command prints `ok` when its checks pass. The bundles retain the five feature checks. The integration check covers saved switches, reloads, disabled startup, storage errors, transcript growth, pause/resume and navigation.
