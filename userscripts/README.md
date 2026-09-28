# Userscripts

Tampermonkey userscripts for Arena.ai.

| File | Purpose |
| --- | --- |
| [arena-agent-prompt.user.js](arena-agent-prompt.user.js) | Fills the `/agent` composer with `{repo} read AGENTS.md ARENA.md`. |
| [arena-agent-steering.user.js](arena-agent-steering.user.js) | Clicks the `{repo} - Steering` preview on `/agent/*`. |
| [arena-agent-hide-composer.user.js](arena-agent-hide-composer.user.js) | Hides the editor while Stop generating is present. Locks the blank 24px spacer on `/agent/*`. |

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

## Check

From the repository root:

```bash
node userscripts/arena-agent-prompt.user.js
node userscripts/arena-agent-steering.user.js
node userscripts/arena-agent-hide-composer.user.js
```

Each command prints `ok` when its checks pass.
