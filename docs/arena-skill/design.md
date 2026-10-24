# Preview design record

## Purpose and status

The preview supports messages, reports, tasks, and downloads. The survey adds a read-only results view without changing those tasks.

Status: implemented and browser-checked. Acceptance checks cover independent correctness and confidence, hidden requests, session-only results, and keyboard access.

## Users, tasks, and language

The user opens results from the connection dot. The agent receives questions through the CLI and submits ordered JSON.

Correctness and reported confidence are separate values. No participant research has run.

## Journeys and information architecture

Select the connection dot to open the shared dialog. Close or Escape returns to the page.

An empty view requests an answer from the agent. A failed read retries while the view stays open.

Bible check sends one hidden, ACK-required bible checkpoint note. Prior results stay visible until a new answer arrives.

## Screens and states

The dialog has loading, unanswered, answered, and failed states. It retains prior results during a failed refresh and shows the error.

The view refreshes while open. It sends no survey reads while closed.

The dialog keeps its accessible name, without a visible heading or session notice. Results show relative last-answer time. Unchanged results retain the button and keyboard focus.

## Design system and tokens

The existing product style remains authoritative in `skills/refs/arena-skill/assets/style.css`. It defines surfaces, text, borders, type, spacing, and themes.

Survey roles define red, amber, and green for both themes. Confidence mixes these roles from red at zero through amber at one-half to green at one.

The dialog retains its existing width and layout. The connection-dot button keeps the dot's layout size. Its centered, out-of-flow target remains at least 44 px, with a visible focus ring.

Local deviations from the `nuu` house sheet keep compact density at 1280 and 360 px. They retain warm-neutral themes, 13 to 15 px text, 12 px card radii, and 18 to 24 px card padding. Controls use 30 to 36 px heights, 22.4 by 24 px drag handles, and 6 to 18 px gaps.

## Components and contracts

`assets/app.js` extends the existing shared dialog with read-only content. `assets/index.html` retains the connection indicator inside a native button.

Correctness uses an ID, color, an icon, and an accessible label. A native progress element and percentage show reported confidence.

## Accessibility and inclusion

Checks target WCAG keyboard access, focus order, visible focus, status names, and non-color status cues. Native dialog, button, table, and progress semantics remain in use.

Chromium checks cover keyboard access, focus return, both themes, reduced motion, and 360/1280 px views. WCAG contrast checks cover ID text and endpoint bars in both themes. APCA and assistive-technology checks have not run.

## Content and assets

Interface text uses English. Question IDs remain code values, and percentages use locale-aware formatting.

The existing local Lucide check and cross icons retain `assets/lucide.LICENSE`. The page adds no external assets or fonts.

## Behavior and data

Correctness does not depend on reported confidence. The server stores results and their last-answer timestamp in RAM, outside notes, database state, and exports.

A restart clears results. An unanswered view sends one hidden, ACK-required request through the existing inbox.

## Evidence and handoff

Visual references: [Preview workflow](design-visuals/preview.md), [Shared components](design-visuals/components.md), and [Style reference](design-visuals/styles.md).

Automated client checks cover independent results, empty requests, refresh, errors, recovery, and closed-view reads. These checks are not participant studies.

Local evidence: `arena-state/survey-browser-evidence.json` and `arena-state/survey-{360,1280}-{dark,light}.png`. The captures use synthetic results, not real survey answers or verdicts.

Chromium checks passed with no page errors. Safari, Firefox, physical devices, and screen readers have not run.

Spacing evidence: `arena-state/survey-spacing-evidence.json` and `arena-state/survey-spacing-{360,1280}-{dark,light}.png`. Checks cover prior layout, touch hit area, focus, and nearby controls.

Relative-time evidence: `arena-state/survey-relative-browser-evidence.json` and `arena-state/survey-relative-{360,1280}-{dark,light}.png`. Synthetic browser checks cover relative time, the accessible dialog name, hidden request reuse, retry, unchanged-view focus, both themes, and narrow/wide layouts. Relative-time text passes WCAG contrast checks.

| Usability check | Observed result |
| --- | --- |
| Status visibility | Loading, empty, and failed states have text |
| Familiar terms | Correctness and reported confidence have separate labels |
| User control | Close and Escape return focus |
| Consistency | The view uses the shared dialog and product themes |
| Error prevention | The results view has no editable fields |
| Recognition | IDs, icons, bars, and percentages remain visible |
| Flexible use | Keyboard entry and expanded touch targets passed |
| Minimal content | Two columns separate the two measures |
| Error recovery | A failed read recovers while the dialog stays open |
| Help | Relative time shows result age |

## Decisions and history

Accepted: retain the shared dialog and product themes. Add separate correctness and confidence cues as requested.

2026-10-21: client, server, generated-runtime, and browser checks passed. Review added a colored outline at zero confidence and expanded the Close target.

2026-10-22: add relative last-answer time and Answer again. Hide the heading and session notice, and retain the dialog name.

2026-10-22: show green check, red cross, and orange question mark for correct, wrong, and wholly unknown answers. Keep Answer again and Close on one row.

2026-10-23: add `#image-modal` zoomable report image dialog, 480 px mobile wrapping rules for `#report-select` and `#log-search`, horizontally centered `#preview-note` tooltip, and GSAP 3.15.0 motion helpers.

2026-10-23: add top-right `#modal-close` exit button, `{lucide book-bookmark} Bible Check` action button, `60em`/`40em` width and `30em` max-height media-query breakpoints, and `/nuu` and `/nemoizer` composer slash commands (`#slash-menu` autocomplete and `#modal[data-wide="true"]` query view).

2026-10-24: center `.topbar-row` at `max-width: 900px` (`margin: 0 auto`) so the desktop topbar aligns with the `900` px `.notes-layout` and `.downloads-layout` columns (`NUM206`). Add a `2px` `:focus-visible` accent outline ring (`outline-offset: 2px`), demote `#downloads-tab` to a header icon control, add a sticky `.tasks-layout > .row.tight` bar, and add `#report-loading-bar` under `.topbar`.

## Message composer

Empty and one-line drafts use one row on desktop and phones. Multiline drafts grow within the view and expose an expand control at the top right. The multiline layout stays until the draft is empty.

Expansion retains the draft and selection. The panel and Send keep their existing corner shapes. Empty fields hide overflow from multiline placeholders.

Attach and Markdown preview stay left, with Send or its busy icon on the right. Controls have no idle background or border. Hover and active states show a background.

Removable file chips sit above the text. Keyboard hints, key status, and error lines sit below the panel, including during expansion. Markdown preview, storage checks, and keyboard controls remain available.

The composer uses existing product colors and local Lucide icons under `assets/lucide.LICENSE`. The `arrow-up`, `maximize-2`, and `minimize-2` paths in `assets/app.js` come from the [Lucide catalog](https://github.com/lucide-icons/lucide/tree/main/icons).
