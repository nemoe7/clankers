# Design: Arena Steering (`skills/arena-steering`)

## Palette & Tokens

- Dark-only Arena surface palette (`hsl(var(--surface-primary))` `#1d1c1b`, `hsl(var(--surface-secondary))` `#252523`, `hsl(var(--surface-tertiary))` `#191817`, `hsl(var(--surface-raised))` `#2c2b28`).
- Text hierarchy tokens (`--text-primary`, `--text-secondary`, `--text-tertiary`, `--header-primary`) and border tokens (`--border-faint`, `--border-medium`, `--border-strong`).
- Status and interactive tokens (`--interactive-positive`, `--interactive-link`, `--interactive-negative`, `--interactive-cta`, `--code-bg`).
- Connection states use `--connection-ok`, `--connection-polling`, `--connection-idle`, and `--connection-down`. The initial state uses muted text color.

## Typography

- Body copy uses embedded `Basel Grotesk` (`--font-basel-grotesk`) at `14px` UI scale and `16px` inside `.message-text` and `.report`.
- Code blocks, inline code spans, ID chips, and tabular badges use embedded `Basel Grotesk Mono` (`--font-basel-grotesk-mono`) with `tabular-nums`.
- Headings use tight tracking (`-0.01em`) and `1.2` line height across report documents and modal titles.

## Spacing & Density

- Spacing follows the `4px` / `8px` / `12px` / `16px` / `20px` scale (`--space-1` through `--space-5`).
- All three tab panels (`Messages`, `Reports`, `Tasks`) share a centered `900px` max-width container (`width: min(900px, 90vw)`).
- List items use `2ch` hanging indentation (`list-style-position: outside; padding-inline-start: 2ch`) across Tasks and Markdown lists.

## Viewport Budget

- `.app-shell` locks to `100dvh` (`overflow: hidden`) with a single centered `.topbar` navigation header (`Messages`, `Reports`, `Tasks`).
- `Messages` keeps the `.log-toolbar` header and bottom `.card.compose` pinned while `#history` scrolls with a `100vw` right-edge scrollbar.
- `Reports` and `Tasks` scroll vertically inside `#view-reports` and `#view-tasks` with CSS `scroll-edge-fade` masks (`12px` edge over `192px` ramp).

## Component Inventory

- Centered equal-width `.tab-nav` (`grid-auto-columns: 1fr`) with plain-text `.tab-btn` items and `#report-pip` (`--accent: #e5bb8b`) on `Reports` when unseen or unanswered reports exist.
- `Messages` log toolbar (`#connection` status dot, `#log-search`, `#skip-poll`, `#quiet-msgs`), `.message` cards, `.code-block` copy headers, and `.card.compose`.
- `Reports` 3-column layout (`#report-toc`, `#report-main` with two-line `#report-status` under `<h1>` and `.field-card` question cards, and `#report-rail` numbered `#report-picker` with top-right unseen dot and unanswered icon plus `Copy`/`Dismiss` actions).
- `Tasks` borderless sectioned list (`Current` `18px`, `Upcoming` `18px`, `Finished` `18px`) with `16px` task rows/titles, `14px` badges/details, `.select-wrap` type filter (`#task-type-filter`), and search input.
- Shared `<dialog id="modal-shell">` confirmation modal (`createModalManager`) with equal-width `.modal-actions` buttons.

## States & Feedback

- The static connection dot is gray while connecting, green while connected, blue while polling, amber when idle, and red when disconnected.
- Text and an accessible label identify each state.
- Message status dots reflect `sent` (neutral), `seen` (`#7fa7d1`), and `acked` (`#8dc07f`) states alongside boundary-scheduled relative timestamps (`nextRelativeDelay`).
- Copy buttons (`.copy-code`, `#report-copy`) and ID chips (`code.msg-id`) swap to a green check / `data-state="good"` confirmation state on click.

## Accessibility Contract

- Semantic landmarks (`<header>`, `<nav role="tablist">`, `<main>`, `<section role="tabpanel">`, `<dialog>`) and explicit `aria-label` / `aria-selected` attributes.
- `html[data-keyboard-nav="true"]` gates keyboard focus rings (`2px solid hsl(var(--border-strong))`) without overflow clipping (`NUA307`, `NUA308`).
- Custom `<select>` controls use `appearance: none` with a non-interactive `.select-chevron` SVG and sufficient right padding (`28px`).

## Responsive Breakpoints

- `>= 75em` (`1200px`): `Reports` displays all three columns (`#report-toc` left rail, `900px` `#report-main` center, `#report-rail` right rail).
- `60em` to `74.99em`: `Reports` hides the left TOC rail and keeps `#report-main` (`70%`) plus `#report-rail` (`26%`).
- `< 60em` and `< 40em`: `Reports` stacks `#report-rail` above `#report-main`, and `Messages` and `Tasks` wrap toolbar controls cleanly without horizontal overflow.

## Visual Reference

- The repository demo runs via `maintenance/demo-arena-steer.py` on port `8100` by default.
- Verified via headless Chromium screenshots at `1372x883` desktop and `411x799` mobile viewports across `Messages`, `Reports`, and `Tasks`.

## Deviations & Suppressions

- `arena-dark-only` & `arena-tokens` (`NUM101`, `NUM201`, `NUM202`, `NUM203`, `NUL003`): Uses dark-only Arena CSS tokens, `Basel Grotesk` fonts, and keyboard-gated focus rings.
- `arena-scrollbar` (`NUM201`, `NUM203`): Matches Arena's global `scrollbar-width: thin` and `15px` `::-webkit-scrollbar` rules.
