# Preview design record

## Purpose and status

The preview supports messages, reports, tasks, and downloads. The questionnaire adds a read-only results view without changing those tasks.

Status: implemented and browser-checked. Acceptance checks cover independent correctness and confidence, hidden requests, session-only results, and keyboard access.

## Users, tasks, and language

The user opens results from the connection dot. The agent receives questions through the CLI and submits ordered JSON.

Correctness and reported confidence are separate values. No participant research has run.

## Journeys and information architecture

Select the connection dot to open the shared dialog. Close or Escape returns to the page.

An empty view requests an answer from the agent. A failed read retries while the view stays open.

Answer again sends one hidden, ACK-required request. Prior results stay visible until a new answer arrives.

## Screens and states

The dialog has loading, unanswered, answered, and failed states. It retains prior results during a failed refresh and shows the error.

The view refreshes while open. It sends no questionnaire reads while closed.

The dialog keeps its accessible name, without a visible heading or session notice. Results show relative last-answer time. Unchanged results retain the button and keyboard focus.

## Design system and tokens

The existing product style remains authoritative in `skills/refs/arena-skill/assets/style.css`. It defines surfaces, text, borders, type, spacing, and themes.

Questionnaire roles define red, amber, and green for both themes. Confidence mixes these roles from red at zero through amber at one-half to green at one.

The dialog retains its existing width and layout. The connection-dot button keeps the dot's layout size. Its centered, out-of-flow target remains at least 44 px, with a visible focus ring.

## Components and contracts

`assets/app.js` extends the existing shared dialog with read-only content. `assets/index.html` retains the connection indicator inside a native button.

Correctness uses an ID, color, an icon, and an accessible label. A native progress element and percentage show reported confidence.

## Accessibility and inclusion

Checks target WCAG keyboard access, focus order, visible focus, status names, and non-color status cues. Native dialog, button, table, and progress semantics remain in use.

Chromium checks cover keyboard access, focus return, both themes, reduced motion, and 360/1280 px views. WCAG contrast checks cover ID text and endpoint bars in both themes. APCA and assistive-technology checks have not run.

## Content and assets

Interface text uses English. Question IDs remain code values, and percentages use locale-aware formatting.

The existing local Lucide check and cross icons retain `assets/lucide.LICENSE`. No external assets or fonts are added.

## Behavior and data

Correctness does not depend on reported confidence. The server stores results and their last-answer timestamp in RAM, outside notes, database state, and exports.

A restart clears results. An unanswered view sends one hidden, ACK-required request through the existing inbox.

## Evidence and handoff

Automated client checks cover independent results, empty requests, refresh, errors, recovery, and closed-view reads. These checks are not participant studies.

Local evidence: `arena-state/questionnaire-browser-evidence.json` and `arena-state/questionnaire-{360,1280}-{dark,light}.png`. The captures use synthetic results, not real questionnaire answers or verdicts.

Chromium checks passed with no page errors. Safari, Firefox, physical devices, and screen readers have not run.

Spacing evidence: `arena-state/questionnaire-spacing-evidence.json` and `arena-state/questionnaire-spacing-{360,1280}-{dark,light}.png`. Checks cover prior layout, touch hit area, focus, and nearby controls.

Relative-time evidence: `arena-state/questionnaire-relative-browser-evidence.json` and `arena-state/questionnaire-relative-{360,1280}-{dark,light}.png`. Synthetic browser checks cover relative time, the accessible dialog name, hidden request reuse, retry, unchanged-view focus, both themes, and narrow/wide layouts. Relative-time text passes WCAG contrast checks.

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

## Message composer

Empty and one-line drafts use one row on desktop and phones. Multiline drafts grow within the view and expose an expand control at the top right. The multiline layout stays until the draft is empty.

Expansion retains the draft and selection. The panel and Send keep their existing corner shapes. Empty fields hide overflow from multiline placeholders.

Attach and Markdown preview stay left, without button backgrounds. Send or its busy icon stays right.

Removable file chips sit above the text. Markdown preview, key status, errors, storage checks, and keyboard controls remain available.

The composer uses existing product colors and local Lucide icons under `assets/lucide.LICENSE`. The `arrow-up`, `maximize-2`, and `minimize-2` paths in `assets/app.js` come from the [Lucide catalog](https://github.com/lucide-icons/lucide/tree/main/icons).
