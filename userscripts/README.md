# Userscripts

Tampermonkey userscripts for Arena.ai and chatgpt.com.

| File | Purpose |
| --- | --- |
| [arena-agent-prompt.user.js](arena-agent-prompt.user.js) | Fills the `/agent` composer with `{repo} read AGENTS.md ARENA.md`. |
| [arena-agent-steering.user.js](arena-agent-steering.user.js) | Clicks the `{repo} - Steering` preview on `/agent/*`. |
| [arena-agent-hide-composer.user.js](arena-agent-hide-composer.user.js) | Hides the editor while Stop generating is present. Locks the blank 24px spacer on `/agent/*`. |
| [chatgpt-hide-elements.user.js](chatgpt-hide-elements.user.js) | Adds `hidden` to four promo and nav elements on chatgpt.com. |
| [chatgpt-auto-think.user.js](chatgpt-auto-think.user.js) | Clicks the Think pill every second while `aria-pressed` is `false`. |

## Install

Copy each script into Tampermonkey.

1. Install Tampermonkey in the browser.
2. Open the Tampermonkey dashboard and create a new script.
3. Paste the contents of one `.user.js` file.
4. Save the script.
5. Repeat for each script.

## Arena Agent Prompt

The script fills the composer only when the path is `/agent`. It does not fill the composer when the path has a trailing segment.

If the GitHub repo bar is not empty, the script reads `owner/repo` from `span.truncate`. The script uses the name after `/`.

The script writes `{repo} read AGENTS.md ARENA.md` into the composer. If the repo name changes, the script updates that text.

The script does not overwrite an unrelated draft.

## Arena Agent Steering

The script runs only when the path has a segment after `/agent/`.

The script waits 1 second. Then the script clicks the `{repo} - Steering` button on port 8000. The script clicks that button once per page.

## Arena Agent Hide Composer

The script runs only when the path has a segment after `/agent/`.

If a button `aria-label` is `Stop generating`, the script hides `div.editor-content` with the `hidden` attribute, the `hidden` class, and `display: none !important`. It restores the editor when that button is gone.

The script keeps a blank `div.shrink-0` at 24px on `/agent/*`. It resets the height if another script changes it.

## ChatGPT Hide Elements

The script runs on any path of `chatgpt.com`.

The script adds the `hidden` attribute to four elements:

- The div that holds the Claim offer button.
- The div that holds the Free offer button.
- The div that holds the Select chat surface toggle.
- The Codex sidebar link.

A MutationObserver repeats the work when the page changes.

## ChatGPT Auto Think

The script runs on any path of `chatgpt.com`.

Every second, the script clicks the Think pill while its `aria-pressed` is `false`.

## Check

From the repository root:

```bash
node userscripts/arena-agent-prompt.user.js
node userscripts/arena-agent-steering.user.js
node userscripts/arena-agent-hide-composer.user.js
node userscripts/chatgpt-hide-elements.user.js
node userscripts/chatgpt-auto-think.user.js
```

Each command prints `ok` when its checks pass.
