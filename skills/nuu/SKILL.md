---
name: nuu
description: >
  Use when designing, building, refactoring, reviewing, or auditing a web page,
  component, stylesheet, layout, or client flow: icons, colour tokens, light and
  dark schemes, typography, spacing, responsive breakpoints, motion, control and
  list states, optimistic writes, docs/design.md, computed-style measurement,
  screenshot annotation, or accessibility and usability inspection.
---

# House UI and UX

One short specification for every page we ship, paired with a small command-line inspector (`scripts/nuu`). Each clause below has a visual pair in `references/examples.md`, a copyable declaration in `references/style.css`, and an automated or manual check in `references/nuu.md`.

## Use when

- A task creates, edits, or reviews HTML, CSS, SVG, or client-side UI code.
- A page needs a design system, palette, type pairing, layout, or `docs/design.md`.
- A pull request or release needs a rendered layout, contrast, keyboard, or flow audit.

## Do not use when

- The task is backend-only, CLI-only, or data-pipeline work with no user-facing surface.
- The user supplies an explicit external brand book that conflicts with a house token; in that case, record the override in `docs/design.md` and keep the remaining clauses.
- A page exists and the task changes one of these clauses.

## Clauses

1. Every icon comes from the ordered open-source icon provider ladder: `lucide` first, then `simple-icons` for brand marks, then `phosphor` only when neither `lucide` nor `simple-icons` carries the glyph. Keep one `24x24` grid and a `2 px` stroke (`stroke-linecap="round"`, `stroke-linejoin="round"`), and use a plain text label if none of the three providers has the glyph (`ICN001`, `ICN002`).
2. Every glyph on a surface takes the single size the sheet specifies (`16x16 px` default, or `20x20 px` for standalone hero icons) (`ICN101`).
3. Use role-named CSS variables for --bg, --surface, --surface-2, --field, --line, --text, --muted, and --accent. Include --accent-fill, --on-accent, --danger, --warn, --ok, --focus, and --scrollbar-thumb. Component rules contain no hex, RGB, or HSL literals. Give each theme's scrollbar thumb at least 3:1 track contrast.
4. Build both themes from one role set (`:root` + `@media (prefers-color-scheme: dark)` + `:root[data-theme]`) and offer a 3-way theme control (`System`, `Light`, `Dark`) with centered Lucide `monitor`, `sun`, and `moon` glyphs.
5. Use the eight-step type ramp (11, 12, 14, 16, 18, 22, 28, and 32 px) and four weights (400, 500, 600, 700). Keep 11 px uppercase .eyebrow labels, a tabular ID face, and offline fonts via [references/recipes/offline-fonts.md](references/recipes/offline-fonts.md) without reload jitter.
6. Use the 4 px scale (4, 8, 12, 16, 24, 32, and 48 px), or 8 px scale. Rows are 32 px (40 px on 8 px), icon-only buttons are 32x32 px with 24x24 px minimum, and buttons within the same group share identical width and height (`HRC102`). Panels use concentric radii (0, 4, 6, 10, or 9999px), 6px default (10 px on 8 px), and no shadows. On coarse pointers, provide at least 44x44 px hit areas for rows and icon-only buttons.
7. Layouts change at the compact breakpoint subset (`68em` / `1088px`, `60em` / `960px`, and `30em` / `480px` width, plus `24em` / `384px` max-height for landscape touch viewports), written in `em`, with zero horizontal scroll (`SPC206`).
8. Every transition shares one curve (cubic-bezier(0.22, 1, 0.36, 1)) for 100-150 ms hover/press and 160-220 ms panels. ALWAYS use vendored GSAP for animations without spring overshoot. Reduced motion turns animation off. Recipes use var(--ease), and scope reduced-motion overrides to their own components.
9. Each control shows default, hover, focus (`2 px` solid `var(--focus)` ring with `2 px` offset and `>= 3:1` contrast on `:focus-visible` only, `ACC006`, `ACC202`), active, disabled, and loading without changing element dimensions (`ACC205`, `ACC204`) via [references/recipes/live-dot.md](references/recipes/live-dot.md) for the loading state of a row, and via a fixed-slot spinner or pulsing dot in [references/recipes/loading-bar.md](references/recipes/loading-bar.md) for a button or compact control awaiting a fetch. Lists also show empty, failed, and offline. Hover exists only where a pointer does, and the focus outline appears only on keyboard navigation (`ACC202`).
10. Write operations show the pending row immediately and persist view state in URL query parameters or `localStorage` via [references/recipes/page-memory.md](references/recipes/page-memory.md).
11. Each repository carries its own `docs/design.md` (or the custom path configured at `[design].path` in `nuu.toml`), updated in the same change as any visual work (`DOC001`).
12. Read padding, margin, gap, and size per element from the rendered page, compare each with the sheet, and check the house viewports (`1920x957`, `1080x2437`, `958x958`, and `411x799`, plus `855x325` landscape).
13. When a page needs a new pattern, add the entry, the house viewports (`1920x957`, `1080x2437`, `958x958`, and `411x799`, plus `855x325`), and screenshots in one PR.
14. Inline suppression markers (`nonuu: RULE_ID`) silence false-positive findings on that line and appear in `lint`, `audit`, and `collect` output. Approved house-style deviations use `nuu-deviation: <reason>` in comments or `docs/design.md` (`nuu collect --deviations`). Agents MUST NEVER add `nuu-deviation:` without explicit user approval.
15. Use outside list markers with a `2ch` hanging indent slot (`--indent: 2ch; padding-inline-start: 2ch; list-style-position: outside`) and native `disc` marker size so wrapped lines align with the first line (`TYP202`, `TYP203`).
16. Keep heading (h1 to h6) line-height within 1.1 to 1.3x font-size and non-heading line-height within 1.3 to 1.5x (TYP101).
17. Keep h1-h6 letter-spacing within -0.5% to -2% (-0.005em to -0.02em). Keep non-heading letter-spacing at 0, except .eyebrow labels at 0.06em (TYP102).
18. Left-align prose over 3 lines, forbid justified text, center at most 3 lines, and match alignment between headings and their body text (TYP103).
19. Cap multi-line prose and its container within 50 to 75ch (65ch default) (TYP201).
20. Use at most 2 ramp font sizes per card or dialog (3 per view), varying weight and --muted first. Keep headings larger or bolder than body text (HRC101).
21. Match sibling gaps across axes within a group and keep inter-group gaps at least 1.5x intra-group gaps on the Clause 6 scale (SPC101).
22. Align stacked card items on one inline edge with symmetric inline padding. Use house fonts with non-italic body blocks and keep uppercase on .eyebrow (SPC102, TYP002, TYP003).
23. Use at most one primary button per card or dialog and name the action instead of Yes/No (HRC001).
24. Store and send timestamps in UTC or with numeric offsets, sort by epoch milliseconds, and localize only on display.

Component and interaction patterns live in `references/recipes/`: [modal-manager.md](references/recipes/modal-manager.md) (top-right `.close-button` and delete confirmation), [range-sliders.md](references/recipes/range-sliders.md) (step ticks and `<output>` bubbles), [relative-timestamps.md](references/recipes/relative-timestamps.md) (relative ages, full or abbreviated by width), [loading-bar.md](references/recipes/loading-bar.md) (200 ms delayed edge bar and fixed-slot controls), [scrollbars.md](references/recipes/scrollbars.md) (`6 px` rounded thumb without arrow buttons), and [overflow-and-clipping.md](references/recipes/overflow-and-clipping.md) (unclipped focus rings, shadows, and tooltips).

## Workflow

1. Read `docs/design.md` in the target repo (or `[design].path` from `nuu.toml`). If none exists, create one from `references/design-document.md`.
2. Read `references/style.css` and copy only the declarations the page needs. Keep the custom-property names; change their values in `:root` only when `docs/design.md` records a palette or scale.
3. Read `references/examples.md` and the matching recipe in `references/recipes/` when the change touches a clause or component pattern, so the correct and incorrect dark-mode forms are both in view.
4. Build or edit the page. Run `scripts/nuu audit -p <repo>` for static and measure checks. Run `scripts/nuu audit -p <repo> -u <http-url> -f <flows.json> -r <selector>` when a live server is available.
5. When reviewing screenshots in a pull request or report, report open findings only and pair each finding or visual judgement with a side-by-side (`columns: 2`) `Before` vs `After` `nuu board` image whose panels are cropped (`--crop <x,y,w,h|auto>`) and annotated (`nuu annotate`) around the affected component; pass `-W` / `--wireframe` when structural bounding-box overlays are needed. Both commands automatically detect and embed the project's configured `@font-face` / `--font-sans` typography (`nuu.toml`, CSS, or HTML `<style>`).

## Reference files

- `AGENTS.md`: mandatory agent workflow rules for `nuu` (`--wireframe` / `-W`, `nuu walk`, `nuu board`, and `nuu.toml`).
- `references/nuu.toml`: default configuration (`Inter` / `Monaspace Neon` font stack, scale, and board defaults).
- `references/nuu.md`: CLI flags, exit codes, rule codes (`ICN001`–`ICN101`, `DOC001`, `TYP001`–`TYP203`, `SPC001`–`SPC206`, `HRC001`–`HRC202`, `ACC001`–`ACC205`, `RUN001`–`RUN102`), and recipe index.
- `references/style.css`: house tokens, type ramp, `4 px` default scale (`8 px` opt-in via `:root[data-scale="8"]`), `.close-button`, and states.
- `references/examples.md`: dark-mode correct and incorrect UI pairs per clause, recipe, and audit rule.
- `references/design-document.md`: sections and a filled example for `docs/design.md`.
- `references/recipes/offline-fonts.md`: bundled and offline font loading without reload jitter.
- `references/recipes/live-dot.md`: `8x8 px` pulsing dot in the fixed `16x16 px` glyph slot, with row text naming the state.
- `references/recipes/loading-bar.md`: subtle `2px` edge loading bar (`200ms` delay, `aria-busy="true"`, compositor-only `scaleX`, static `prefers-reduced-motion` fallback) and fixed-slot inline control loading.
- `references/recipes/page-memory.md`: content-versioned in-memory view cache, optimistic writes, and URL/`localStorage` state persistence.
- `references/recipes/modal-manager.md`: shared `<dialog>` modal manager with `showModal()`, top-right `.close-button` (`-8 px` margin, focus/hover `--text` shift), and delete confirmation.
- `references/recipes/range-sliders.md`: range slider `<input type="range">` with `step` ticks, min/max labels, and live `<output>` bubble.
- `references/recipes/relative-timestamps.md`: singular, plural, and compact relative timestamp table (`just now`, `Xmin ago`, `yesterday`, `last week`, `last month`, `last year`).
- `references/recipes/scroll-edge-fade.md`: scroll-driven CSS `mask-image` edge fade (`@supports (animation-timeline: scroll(self))`).
- `references/recipes/floating-overlay-scroll-fade.md`: full-bleed scroll container fade behind floating header and composer overlays (`backdrop-filter: blur()`, `padding-inline`, and `@supports (animation-timeline: scroll(self))`).
- `references/recipes/scrollbars.md`: thin `6px` rounded-thumb scrollbar (`var(--scrollbar-thumb)`) in a `10px` track on `var(--bg)` without arrow buttons or hover highlights unless keyboard navigation is active.
- `references/recipes/overflow-and-clipping.md`: anti-clipping and anti-overlap rules (`SPC204`, `SPC205`, `ACC203`) for flex/grid rows, focus rings, sticky headers, and viewport-clamped tooltips.

## Learn

- On `/nuu learn`, survey repo UI patterns, cite target clauses, and publish a maintainer handoff.

