# The design document

Every repository that installs this skill keeps one `docs/design.md`. The file records the calls that repository already made. A reader opens it before changing a page, and the change edits it in the same commit.

## Sections

Keep these eleven sections, in this order. Short sections stay one line.

1. **Renders**: the pages and panels that exist, each with one line on what it shows.
2. **Product shape**: the objects the pages speak about, and the words the pages use for them.
3. **Settings**: the stored preferences and their defaults.
4. **Colour**: the role names in use, the values for light and dark, and the contrast check.
5. **Type**: the family, the weights, the sizes in use, and the mono face.
6. **Icons**: the icon set, the vendored glyphs, the licence, and the size per surface.
7. **Layout**: the column, the gutters, the grid, and the breakpoints with what each one changes.
8. **Components**: one entry per pattern, with its parts and its states.
9. **Theme and motion**: the theme control, the curve, the durations, and the reduced-motion rule.
10. **States**: the empty, loading, failed, disabled, and offline states per page.
11. **Change log**: one line per settled call, newest first.

## Filled example

```markdown
# Design

## Renders

- Inbox: filters, list, inspector.
- Settings: preferences and the theme control.

## Product shape

- Request: one item a person sent. Identifier `req_<number>`.
- Owner: the person who answers it.

## Settings

- Theme: System by default; Light and Dark are explicit choices.
- Page size: 20 rows.

## Colour

- Roles: bg, surface, surface-2, field, line, text, muted, accent, accent-fill, on-accent, danger, warn, ok.
- Light and dark resolve the same names. Body text passes 4.5:1 in both.

## Type

- Inter at 400, 600, 800. Sizes 11, 12, 13, 14, 15, 20, 28 px.
- IDs use the mono face with tabular figures.

## Icons

- Lucide, vendored one glyph at a time, ISC licence beside each file.
- 18 px on every surface.

## Layout

- One 1280 px column with 32 px gutters.
- 1200 px: inspector takes 320 px. 900 px: the opened item fills the page. 640 px: tables stack.

## Components

- `row`: height 40 px, padding 0 16 px, border-bottom 1 px line. States: default, hover, selected.
- `pill`: dot and word, 24 px high, radius 10 px.

## Theme and motion

- Theme control: System, Light, Dark.
- One curve `cubic-bezier(0.22, 1, 0.36, 1)`, 160 to 220 ms. Reduced motion stops it.

## States

- Inbox empty: says no request matches, and offers Clear filters.
- Inbox failed: names the failed load and offers Retry.
- Offline: a banner above the list, and the write keeps its draft.

## Change log

- 2026-03-04: inspector width at 1200 px set to 320 px.
```

## Rules for an entry

- An entry names a settled call, not an option.
- A screenshot belongs beside the entry when the pattern is new.
- Delete an entry only with the code it describes.
