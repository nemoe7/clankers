# Userscripts

Tampermonkey userscripts for Arena.ai.

| File | Purpose |
| --- | --- |
| [arena-agent-prompt.user.js](arena-agent-prompt.user.js) | Fills the `/agent` composer with `{repo} read AGENTS.md ARENA.md`. |
| [arena-agent-steering.user.js](arena-agent-steering.user.js) | Clicks the `{repo} - Steering` preview on `/agent/*`. |
| [arena-agent-hide-composer.user.js](arena-agent-hide-composer.user.js) | Hides the composer shell on `/agent/*` while Stop generating is present. |

## Install

Copy each script into Tampermonkey.

1. Install Tampermonkey in the browser.
2. Open the Tampermonkey dashboard and create a new script.
3. Paste the contents of one `.user.js` file.
4. Save the script.
5. Repeat for each script.

## arena-agent-prompt

The script fills the composer only when the path is `/agent`. It does not fill the composer when the path has a trailing segment.

If the GitHub repo bar is not empty, the script reads `owner/repo` from `span.truncate`. The script uses the name after `/`.

The script writes `{repo} read AGENTS.md ARENA.md` into the composer. If the repo name changes, the script updates that text.

The script does not overwrite an unrelated draft.

## arena-agent-steering

The script runs only when the path has a segment after `/agent/`.

The script waits 1 second. Then the script clicks the `{repo} - Steering` button on port 8000. The script clicks that button once per page.

## arena-agent-hide-composer

The script runs only when the path has a segment after `/agent/`.

If a button `aria-label` is `Stop generating`, the script hides the outermost `div.flex.w-full.flex-col.items-start.justify-center.p-2` that holds the editor. It sets the `hidden` attribute, the `hidden` class, and `display: none !important`, because Tailwind `flex` overrides the `hidden` attribute. The script restores the shell when that button is gone.

## Check

From the repository root:

```bash
node userscripts/arena-agent-prompt.user.js
node userscripts/arena-agent-steering.user.js
node userscripts/arena-agent-hide-composer.user.js
```

Each command prints `ok` when its checks pass.
