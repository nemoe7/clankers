# ChatGPT userscript

Tampermonkey userscript for `chatgpt.com`. See [Arena userscript](../arena/README.md) for the Arena.ai bundle.

| Bundle | Features |
| --- | --- |
| [chatgpt.user.js](../../../userscripts/chatgpt.user.js) | Hide elements, Auto Think |

## Install

1. Install Tampermonkey in the browser.
2. Open its dashboard and create a new script.
3. Paste `userscripts/chatgpt.user.js` contents and save.

To migrate, disable or remove old standalone scripts before enabling the bundle. Reload open ChatGPT tabs to stop old timers and observers. Old installations do not become bundles automatically.

The bundle has its own version and raw GitHub update URL. A saved feature setting belongs to its bundle.

## Feature switches

The ChatGPT bundle keeps its `Auto Think: ON - toggle` menu shape alongside saved target switches.

Switches apply immediately in the current tab. Other open tabs use saved settings on their next reload. Disabling stops the feature's observers, timers, and listeners.

The bundle uses `GM_getValue` and `GM_setValue` for saved settings, plus menu registration and removal, and it holds no check code. Switches never reload the page. Disabling a hiding feature restores its own DOM changes where the page has not replaced them.

## Console log

ChatGPT keeps its `[NemoUtils]` console output.

## ChatGPT hide elements

On any `chatgpt.com` path, the feature adds `hidden` to twelve managed targets:

- The div that holds the Claim offer button.
- The div that holds the Free offer button.
- The Chat and Work header toggle.
- The Codex sidebar entry.
- The Images sidebar entry.
- The Library sidebar entries, in the collapsed rail and in the open nav list.
- The Free badge.
- The prompt textarea header banner.
- The header Upgrade and Share controls.
- The sidebar Upgrade control.
- The Upgrade to Plus row, without hiding adjacent actions.

Each target has a saved, default-on menu switch. The Hide elements switch controls all targets without changing their saved preferences or Auto Think. One MutationObserver repeats the work when the page changes, and turning hiding off restores only nodes the script hid.

## ChatGPT auto think

On any `chatgpt.com` path, the feature clicks the Think pill every second while `aria-pressed` is `false`.

## Check

From the repository root:

```bash
node userscripts/chatgpt.user.js
node --test tests/userscripts/userscripts.checks.cjs
node --test tests/userscripts/userscripts.test.cjs
```

Each command prints `ok` when its checks pass. The bundle carries runtime code only: outside a browser each feature publishes its helpers through `exposeChecks`, and the feature checks run from `tests/userscripts/userscripts.checks.cjs`.
