# userscripts Agent Rules

- Record newly discovered userscript bugs, DOM selector hazards, and dead ends in `userscripts/AGENTS.md` whenever a fix lands so other agents NEVER repeat them.
- Bump `@version` and the version suffix in `@name` on every edit to `userscripts/*.user.js`.
- Add controls in `openSettingsModal()` (`#clankers-settings-modal`) for every new feature, toggle, and configurable parameter.
- Keep the 26 Tampermonkey menu command labels (`GM_registerMenuCommand`) unchanged unless explicitly instructed to change them.
- Make every `MutationObserver` callback strictly idempotent: compare current `textContent`, attributes, and style value/priority before mutating the DOM, and NEVER write unconditionally inside an observed subtree.
- Exclude transcript children (`[role="log"]`, `[data-perf-target="transcript"]`, `.max-w-3xl`) when selecting outer layout or composer wrappers (`div.flex.min-h-0.flex-1.flex-col > div.shrink-0`).
- Detect open preview drawers by preview-specific controls (`button[aria-label="Close preview"]`, `iframe[title^="App preview"]`), NEVER by `button[aria-label="Collapse workspace sidebar"]` alone (`256px` `Workspace card views` sidebar keeps that button when the preview is closed).
- Lock width on both the outer (`div.absolute.bottom-0.end-0.top-0.z-10.overflow-clip`) and inner (`> div`) preview drawer containers.
- NEVER fall back to timestamped downloads when a quiet state save fails; show `#clankers-state-panel` specifying the error and offering `Choose file`.
- Keep `storeKey` in `fetchStateFile` aligned with `stateScope(document)` instead of overwriting it with `body.scope.branch`, and fall back to `lastScope` handles.
- Initialize `BOARD_KEY`, `onPreviewMessage`, `notifyPreviewReady`, and `syncPreviewBoard` above `runFeature` calls and keep `syncPreviewBoard` independent of `stateBusy`.
- NEVER put en-dashes (`\u2013`) or em-dashes (`\u2014`) in `userscripts/*.user.js` or `userscripts/README.md`.
- Run both `node --test maintenance/workflows/userscripts.test.cjs` and `node --test maintenance/workflows/userscripts.checks.cjs` via `arena-preview run start` before pushing `userscripts/` changes.
