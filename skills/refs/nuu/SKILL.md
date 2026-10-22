---
name: nuu
description: Build and revise web pages in a settled house style. Use when a task adds or changes a page, dialog, table, form, theme, empty or error state, or any UI that needs icons, colour roles, light and dark schemes, type, spacing, breakpoints, motion, states, optimistic writes, a design document, or measured values at 1280 and 360 px.
license: MIT
---

# Nemo UI/UX (nuu)

## Shared workflow

- Classify the task as build, refine, audit, critique, harden, extract, or live inspection before choosing tools.
- Preserve an existing product design system unless the user authorizes its redesign.
- Apply the bundled house clauses, sheet, and work order only when no product design system exists or the user selects the house profile.
- Record the audience, primary task, factual content, constraints, and acceptance checks before building a new interface.
- Choose a visual direction from the brief without inventing claims, assets, or proof.
- Search the local rule catalog for the task outcome and detected stack, and verify each recommendation against the project.
- Identify fallback search results and missing evidence instead of presenting them as exact matches.
- Generate design-system proposals without replacing existing tokens or design records until the change is approved.
- Record each asset's source, license, attribution, and local path before using it.
- Preserve applicable upstream licenses and notices when adapting source text, code, or data.
- Run source checks with stable finding IDs, locations, severity, and evidence before browser verification.
- Inspect rendered pages at project widths plus 1280 and 360 px with available browser tools.
- Test the changed task flow, including keyboard operation, focus movement, validation, loading, failure, retry, and recovery where applicable.
- Check supported themes, reduced motion, long content, and empty, sparse, dense, error, and offline states where applicable.
- Keep viewport screenshots, computed measurements, browser errors, and flow results with the verification report.
- Separate automated findings, visual judgments, synthesized input, and real-device evidence in every audit.
- Name checks that did not run, missing dependencies, and unsupported browser or device coverage without claiming a pass.
- Report audit and critique findings without changing files unless repair is requested.
- Keep live inspection read-only until the user authorizes a specific edit, and retain its before-and-after evidence.
- Extract reusable tokens and component patterns without introducing a competing source of truth.
- Repair only the requested scope, then rerun affected source, browser, and task-flow checks.
- Keep credentials and private page content out of external searches, asset requests, and shared artifacts.
- Use existing design records, or docs/design.md when none exist, as the design authority.
- Update the authoritative design record in the same change as a settled design decision.
- Evaluate changed flows against the ten usability heuristics, citing observed behavior for each finding.
- Check alignment, hierarchy, color roles, typography, and useful imagery against the task and active design system.
- Create a new interaction pattern only when existing patterns cannot meet the documented user need.
- Map accessibility findings to applicable WCAG criteria with the test method, evidence, and verification status.
- Label automated task-flow checks separately from usability sessions with real participants.
- Mark implementation readiness and link behavior, states, assets, and component sources in each handoff.
- Create component forks only when existing variants cannot meet the task and the exception is recorded.

## House profile

Apply this skill to a page, a component, or an interface change. The sheet is the reference for values, and the design document records the calls that a repository already made.

## When to use

- A task adds or changes a page, dialog, table, form, theme, or state.
- A review asks whether the interface matches the house style.
- A new pattern needs a decision that later pages must repeat.
- A page exists and the task changes one of these clauses.

## Clauses

1. Take the glyph a control needs from the icon set, keep its licence beside it, and inline that same path. A name with no glyph shows its word.

2. Every glyph on a surface takes the single size the sheet names.

3. A component asks the sheet for a role. Nobody writes a colour literal into a component.

4. The roles resolve in light and in dark. The theme control names System, Light, and Dark, so the page can follow the machine.

5. Four sizes from the sheet, three weights, one eyebrow size, and a tabular face for IDs.

6. Every gap lands on the 8 px scale. Rows are 40 px, panels take a 10 px radius and no shadow, and a touch target is at least 44 px.

7. The sheet names 1200, 900, and 640. A width outside the list gets no behaviour of its own.

8. Every transition shares one curve over 160 to 220 ms. Reduced motion turns animation off.

9. Each control shows default, hover, focus, active, disabled, and loading. Lists also show empty, failed, and offline. Hover exists only where a pointer does.

10. The pending row appears before the reply. A failure retries once with the same ID, so the list holds one row.

11. Record settled calls in the authoritative design record.

12. Read padding, margin, gap, and size per element from the rendered page, compare each with the sheet, and check 1280 and 360.

13. When a page needs a pattern the sheet lacks, the change adds the entry, both widths, and the screenshots, in one pull request.

## Order of work

1. Read the authoritative design record, or create docs/design.md from references/design-document.md if none exists.
2. Copy the declarations the page needs from `references/style.css`. Keep the role names, and change only the values that the repository settles.
3. Read `references/examples.md` when the change touches a clause, so the correct and incorrect forms are both in view.
4. Make only authorized page changes, then measure both widths and fix every value the check names.
5. Update the authoritative design record in the same change as a settled design decision.

## Measuring

`scripts/measure.py check` reads a JSON report of computed values and names every value that leaves the sheet. A value passes when it sits on the scale, when a type property takes a size from the ramp, or when the sheet names that size for that property, such as the 10 px radius.

`scripts/measure.py ruler` reads a gap between two guides on the page, the way a screen ruler does, and answers whether each axis sits on the scale.

```bash
python scripts/measure.py check report.json
python scripts/measure.py ruler --from 120,340 --to 264,340
```

`references/measure.md` holds the browser snippet that writes the report, and the list of what to keep.

## Files

- `references/style.css`: the sheet as code. Roles, type, space, states, and motion.
- `references/design-document.md`: the eleven sections of `docs/design.md`, with a filled example.
- `references/examples.md`: one correct and incorrect pair per clause, drawn from the sheet.
- `references/measure.md`: the report shape, the snippet, and the ruler.
- `scripts/measure.py`: the check and the ruler.

- `scripts/uiux.py`: briefs, catalog search, system proposals, design records, assets, source checks, extraction, and evidence-based task modes.
- `scripts/browser.cjs`: optional Playwright captures, declared flows, and authorized transient live edits.
- `data/vendor/`: licensed catalog data and source hashes.
- `references/tools.md`: command contracts, report fields, and coverage limits.
