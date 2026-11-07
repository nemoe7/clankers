---
# nonemo: STE100; nonemo: STE200; nonemo: NMP100; nonemo: NMO003
name: nuu
description: >
  Use when designing, building, refactoring, reviewing, or auditing a web page,
  component, stylesheet, layout, or client flow: icons, colour tokens, light and
  dark schemes, typography, spacing, responsive breakpoints, motion, control and
  list states, optimistic writes, docs/design.md, computed-style measurement,
  screenshot annotation, or accessibility and usability inspection.
---

# House UI and UX

One short specification for every page we ship, paired with a small command-line inspector (`scripts/nuu`). Visual clauses have pairs in `references/examples.md`. The sheet provides copyable declarations, and `references/nuu.md` describes automated and manual checks.

## Use when

- A task creates, edits, or reviews HTML, CSS, SVG, or client-side UI code.
- A page needs a design system, palette, type pairing, layout, or `docs/design.md`.
- A pull request or release needs a rendered layout, contrast, keyboard, or flow audit.

## Do not use when

- The task is backend-only, CLI-only, or data-pipeline work with no user-facing surface.
- The user supplies an explicit external brand book that conflicts with a house token; in that case, record the override in `docs/design.md` and keep the remaining clauses.
- A page exists and the task changes one of these clauses.

## Clauses

1. Every icon comes from the ordered open-source icon provider ladder: lucide first, then simple-icons for brand marks, then phosphor only when neither lucide nor simple-icons carries the glyph. Keep one 24x24 grid and a 2 px stroke (stroke-linecap="round", stroke-linejoin="round"), and use a plain text label if none of the three providers has the glyph.
2. Keep comparable surface icons one size: 16x16 px default, or 20x20 px for standalone hero icons. Icons paired with text MUST match the paired text line height.
3. Use role-named CSS variables for --bg, --surface, --surface-2, --field, --line, --text, --muted, and --accent. Include --accent-fill, --on-accent, --danger, --warn, --ok, --focus, and --scrollbar-thumb. Component rules contain no hex, RGB, or HSL literals. Give each theme's scrollbar thumb at least 3:1 track contrast. Assign colors by role and state. Make status, selection, and errors understandable without color alone, using text, shape, or another explicit cue. Check contrast against the actual adjacent background in each theme, including text over images.
4. Build both themes from one role set (`:root` + `@media (prefers-color-scheme: dark)` + `:root[data-theme]`) and offer a 3-way theme control (`System`, `Light`, `Dark`) with centered Lucide `monitor`, `sun`, and `moon` glyphs.
5. Use sizes from the nine-step type ramp (11, 12, 14, 16, 18, 22, 24, 28, and 32 px) and four weights (400, 500, 600, 700). Start with 32 px for titles, 18 px for body, and 14 px for small text. For dense dashboards, start with 24 px for titles, 16 px for body, and 12 px for small text. Apply the Clause 20 per-view limits. Keep 11 px uppercase .eyebrow labels, a tabular ID face, and offline fonts via [references/recipes/offline-fonts.md](references/recipes/offline-fonts.md) without reload jitter.
6. Use the 4 px scale (4, 8, 12, 16, 24, 32, and 48 px), or 8 px scale. Set CSS gap, row-gap, and column-gap to zero or whole multiples of the selected scale. Rows are 32 px (40 px on 8 px), icon-only buttons are 32x32 px with 24x24 px minimum, and buttons within the same group share identical width and height. Panels use concentric radii (0, 4, 6, 10, or 9999px), 6px default (10 px on 8 px), and no shadows by default. On light surfaces, restrained shadows may distinguish cards and elevated overlays. On coarse pointers, provide at least 44x44 px hit areas for rows and icon-only buttons. Group related content deliberately.
7. Layouts change at the compact breakpoint subset (68em / 1088px, 60em / 960px, and 30em / 480px width, plus 24em / 384px max-height for landscape touch viewports), written in em, with zero horizontal scroll. Verify reflow against real content and relevant input modes.
8. Every transition shares one curve (cubic-bezier(0.22, 1, 0.36, 1)) for 100-150 ms hover/press and 160-220 ms panels. ALWAYS use vendored GSAP for animations without spring overshoot. Reduced motion turns animation off. Recipes use var(--ease), and scope reduced-motion overrides to their own components.
9. Each control shows default, hover (pointer devices only), keyboard-only :focus-visible (2 px solid var(--focus) ring, 2 px offset, >= 3:1 contrast), active, disabled, and loading without changing element dimensions via [references/recipes/live-dot.md](references/recipes/live-dot.md) for rows and [references/recipes/loading-bar.md](references/recipes/loading-bar.md) for compact controls. Lists also show empty, failed, and offline. Make interactive elements recognizable, name their action, and make selected, pending, success, warning, and error states clear without relying on hover, motion, or color alone. Associate field errors with their inputs, say how to recover, preserve keyboard access, and verify named completed or failed feedback on every live action click.
10. Every write action MUST render its optimistic DOM state immediately under a held slow-network route and mocked clock. Pages MUST persist view state in URL query parameters or localStorage via [references/recipes/page-memory.md](references/recipes/page-memory.md).
11. Each repo carries its own docs/design.md (or the custom path configured at [paths].doc in nuu.toml), updated in the same change as any visual work.
12. Read padding, margin, gap, and size per element from the rendered page, compare each with the sheet, and check the house viewports (`1920x957`, `1080x2437`, `958x958`, and `411x799`, plus `855x325` landscape).
13. When a page needs a new pattern, add the entry, the Clause 12 house viewports, and screenshots in one PR.
14. Inline suppression markers (nonuu: RULE_ID) silence false-positive findings on that line and appear in lint, audit, and collect output. Approved house-style deviations use nuu-deviation: <reason> in comments or docs/design.md, and recipe links use nuurecipe: <slug> (nuu collect). Agents MUST NEVER add nuu-deviation: without explicit user approval.
15. Use outside list markers with a 2ch hanging indent slot (--indent: 2ch; padding-inline-start: 2ch; list-style-position: outside) and native disc marker size so wrapped lines align with the first line.
16. Choose line height for legibility at the actual size, measure, and script. Start with 1.1 to 1.3 times the font size for headings and 1.3 to 1.5 for body text, then verify rendered content and accessibility.
17. Keep h1-h6 letter-spacing within -0.5% to -3% (-0.005em to -0.03em). Keep non-heading letter-spacing at 0, except .eyebrow labels at 0.06em.
18. Left-align prose over 3 lines, forbid justified text, center at most 3 lines, and match alignment between headings and their body text.
19. Give multiline prose a comfortable reading measure. Use 50 to 75 characters, with 65 as a starting point, when the content and viewport permit. Do not force a minimum width on narrow or compact surfaces.
20. Use at most 2 ramp font sizes per card or dialog (3 per view), varying weight and --muted first. Keep headings larger or bolder than body text. For landing pages and content websites, use at most 6 sizes per view instead of 3 when the content needs them.
21. Match sibling gaps across axes within a group and keep inter-group gaps at least 1.5x intra-group gaps on the Clause 6 scale. Start with 2x when the layout has room.
22. Align stacked card items on one inline edge with symmetric inline padding. Use house fonts with non-italic body blocks and keep uppercase on .eyebrow.
23. Use at most one primary button per card or dialog and name the action instead of Yes/No.
24. Store and send timestamps in UTC or with numeric offsets, sort by epoch milliseconds, and localize only on display.
25. Before choosing a layout, identify the user goal, main flow, and key states. Explore the structure before visual polish when the task warrants it. Use realistic content with zero placeholder Lorem ipsum copy, and inspect representative screen sizes and input modes. Iterate on findings and keep reusable patterns consistent. Scale the work to the change and record relevant decisions in the design document.
26. In dark themes, distinguish raised surfaces from their backgrounds with surface color, and keep decorative borders and chips subdued without reducing required text or control contrast.
27. When text overlays an image, verify contrast against the rendered image and use a gradient or another local treatment when needed to preserve legibility and useful image detail.
28. Review each layout for visual balance, a clear primary action, and unnecessary complexity. Use familiar interaction patterns when they fit the task, and prototype significant flows before finalizing them.
29. Choose role colors that fit the product or brand, and use shades or transparency when needed to distinguish surfaces and states. Verify each chosen role against its actual background.
30. For text buttons, start with horizontal padding twice the vertical padding when content and the selected scale permit. Keep primary and secondary actions visually distinct and preserve the Clause 6 size and hit-area rules.
31. When a task needs a new pattern, inspect relevant real examples and choose illustrations or imagery only when they support the content or user goal.
32. Check heading letter spacing with real content and the selected typeface. Loosen it when the permitted range looks too tight.
33. On every live Nuu audit, inspect visible dialog and floating-overlay text and controls for clipping or occlusion at every edge across the five house viewports. Check tooltip and popover surfaces for missing effective backgrounds. Report selector, viewport, bounds, clipping ancestor, and computed surface color.

Component and interaction patterns live in references/recipes/:

- [offline-fonts.md](references/recipes/offline-fonts.md): bundled offline fonts without reload jitter.
- [live-dot.md](references/recipes/live-dot.md): 8x8 px pulsing dot in a fixed 16x16 px slot.
- [loading-bar.md](references/recipes/loading-bar.md): 200 ms delayed 2 px edge bar and fixed-slot control loading.
- [page-memory.md](references/recipes/page-memory.md): view cache, optimistic writes, and URL/localStorage state.
- [modal-manager.md](references/recipes/modal-manager.md): shared <dialog> manager, top-right .close-button, and delete confirmation.
- [range-sliders.md](references/recipes/range-sliders.md): <input type="range"> with step ticks, endpoint labels, and <output> bubble.
- [relative-timestamps.md](references/recipes/relative-timestamps.md): full and compact relative ages by container width.
- [scroll-edge-fade.md](references/recipes/scroll-edge-fade.md): scroll-driven CSS mask-image edge fade.
- [floating-overlay-scroll-fade.md](references/recipes/floating-overlay-scroll-fade.md): scroll fade behind floating header and composer overlays.
- [scrollbars.md](references/recipes/scrollbars.md): 9999px pill thumb in a 15 px transparent track without arrows.
- [overflow-and-clipping.md](references/recipes/overflow-and-clipping.md): unclipped rows, focus rings, sticky headers, and tooltips.
- [table-to-cards.md](references/recipes/table-to-cards.md): narrow-viewport table-to-card reflow with data-label cells.

## Workflow

1. Read docs/design.md in the target repo (or [paths].doc from nuu.toml). If none exists, create one from references/design-document.md.
2. Read `references/style.css` and copy only the declarations the page needs. Keep the custom-property names; change their values in `:root` only when `docs/design.md` records a palette or scale.
3. Read `references/examples.md` and the matching recipe in `references/recipes/` when the change touches a clause or component pattern, so the correct and incorrect dark-mode forms are both in view.
4. Build or edit the page. Run scripts/nuu audit -c <repo>/nuu.toml for static checks, and add -u <http-url> when a live server is available.
5. When reviewing screenshots in a PR or report, report open findings only. Pair each finding with a two-column Before vs After nuu board cropped (-C) and annotated (nuu annotate), adding -W when needed.

## Reference files

- AGENTS.md: mandatory agent workflow rules for sample renders, dark-mode defaults, and refs parity.
- references/nuu.toml: default paths, font preferences, viewports, board presets, and severity overrides.
- references/nuu.md: 9 subcommands, CLI flags, exit codes, and all 49 conformance rule codes.
- references/style.css: copyable role tokens, type ramp, spacing scale, and control states.
- references/examples.md: dark-mode Pass and Fail UI pairs per clause, recipe, and rule.
- references/design-document.md: six-section template and filled example for docs/design.md.

## Learn

- On `/nuu learn`, survey repo UI patterns, cite target clauses, and publish a maintainer handoff.
