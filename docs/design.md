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

## Screens and states

The dialog has loading, unanswered, answered, and failed states. It retains prior results during a failed refresh and shows the error.

The view refreshes while open. It sends no questionnaire reads while closed.

## Design system and tokens

The existing product style remains authoritative in `skills/refs/arena-skill/assets/style.css`. It defines surfaces, text, borders, type, spacing, and themes.

Questionnaire roles define red, amber, and green for both themes. Confidence mixes these roles from red at zero through amber at one-half to green at one.

The dialog retains its existing width and layout. The connection-dot button has an expanded touch target and a visible focus ring.

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

Correctness does not depend on reported confidence. The server stores results in RAM, outside notes, database state, and exports.

A restart clears results. An unanswered view sends one hidden, ACK-required request through the existing inbox.

## Evidence and handoff

Automated client checks cover independent results, empty requests, refresh, errors, recovery, and closed-view reads. These checks are not participant studies.

Local evidence: `arena-state/questionnaire-browser-evidence.json` and `arena-state/questionnaire-{360,1280}-{dark,light}.png`. The captures use synthetic results, not real questionnaire answers or verdicts.

Chromium checks passed with no page errors. Safari, Firefox, physical devices, and screen readers have not run.

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
| Help | The dialog states that a restart clears results |

## Decisions and history

Accepted: retain the shared dialog and product themes. Add separate correctness and confidence cues as requested.

2026-10-21: client, server, generated-runtime, and browser checks passed. Review added a colored outline at zero confidence and expanded the Close target.
