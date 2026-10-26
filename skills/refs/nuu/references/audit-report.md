# Nuu Audit: <target>

- **Status:** `<pass | action-needed>`
- **Counts:** `<N>` automated findings, `<N>` visual findings, `<N>` house-style deviations
- **Unrun Checks:** `<check>`: `<reason skipped and when to run>` (omit line when none)

## Automated Findings

### 1. `<Rule ID>` — `<Rule Statement>`

| Location | Rule ID & Statement | Width | Finding | Fix |
| --- | --- | --- | --- | --- |
| `selector` or `path:line` | `NUA301`: `<rule statement>` | `1280` / `360` | Violation description | Repair applied or needed |

![Finding 1 Before vs After](<finding-1-before-after-board.png> =720x)

## Visual Judgments

### 1. `<Component>` — `<Visual Observation>`

| Area | Observation | Disposition | Before | After | Action |
| --- | --- | --- | --- | --- | --- |
| `<component>` | Visual layout or hierarchy issue | `fix` or `keep` | Before | After | Adjustment or reason |

![Visual Judgment 1 Before vs After](<visual-1-before-after-board.png> =720x)

## Deviations

| Component, Property, or Recipe | Before | After | Reason | Marker (User-Approved Only) |
| --- | --- | --- | --- | --- |
| `<selector> (<property or recipe>)` | Before | After | Reason | `nuu-deviation: <reason>` (user approval required) |

## Captures

Omit this section unless full-viewport captures are needed.

- **Desktop maximized (`1920x957`):** dark-themed capture at the desktop maximized viewport.
- **Phone portrait (`411x799`):** dark-themed capture with `hasTouch` and `isMobile`.
