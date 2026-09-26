# Userscripts

Tampermonkey userscripts for Arena.ai.

| File | Purpose |
| --- | --- |
| [arena-agent-prompt.user.js](arena-agent-prompt.user.js) | Fills the `/agent` composer. Clicks the `{repo} - Steering` preview on `/agent/*`. |

## Install

Copy a script into Tampermonkey.

1. Install Tampermonkey in the browser.
2. Open the Tampermonkey dashboard and create a new script.
3. Paste the contents of the `.user.js` file.
4. Save the script.

## arena-agent-prompt

The script fills the composer only when the path is `/agent`. It does not fill the composer when the path has a trailing segment.

If the GitHub repo bar is not empty, the script reads `owner/repo` from `span.truncate`. The script uses the name after `/`.

The script writes `{repo} read AGENTS.md ARENA.md` into the composer. If the repo name changes, the script updates that text.

The script does not overwrite an unrelated draft.

When the path has a segment after `/agent/`, the script clicks the `{repo} - Steering` button on port 8000. The script clicks that button once per page.

## Check

From the repository root:

```bash
node userscripts/arena-agent-prompt.user.js
```

The command prints `ok` when the URL, slug, and steering-label checks pass.
