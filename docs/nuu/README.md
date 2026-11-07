# Nemo UI/UX

The abbreviation is **nuu** (say **new**).

Build, refine, and review web interfaces. Tools cover briefs, local catalogs, design records, assets, source checks, rendered evidence, and task flows. Existing product systems take precedence over the optional house profile.

## Setup

Copy `skills/nuu` into a supported skill directory, and see [Skills](../../skills/README.md) for discovery paths. [SKILL.md](../../skills/nuu/SKILL.md) is the agent entry point. Local tools need Python 3.11+ and its standard library, while browser tools also need Node, `playwright`, and a browser binary.

The project supplies its page, running application, and browser. Tools capture pages without installing packages or browsers.

## Working flow

1. Project context starts from an existing design record or [the template](../../skills/nuu/references/design-document.md).
2. Styling follows the product's existing system, or falls back to the house [sheet](../../skills/nuu/references/style.css) and [examples](../../skills/nuu/references/examples.md).
3. Rendered checks inspect viewports across the `68em` (`1088`), `60em` (`960`), `30em` (`480`), and `24em` (`384`) breakpoints.
4. [The browser snippet](../../skills/nuu/references/measure.md) and CLI tools collect computed values, findings, and screenshots.
5. Settled design decisions and rendered evidence stay recorded in the consuming project's design document.

The skill holds the complete house constraints. Design records and screenshots belong to the consuming project rather than this repo.

## Available tools

From the repository root in Windows cmd:

```cmd
python skills\nuu\scripts\measure.py check report.json
python skills\nuu\scripts\measure.py ruler --from 120,340 --to 264,340
```

`check` reads one JSON report of computed CSS values. `ruler` measures horizontal, vertical, and straight-line distances between two page coordinates.

`check` uses sheet rules. `ruler` uses only the scale. Exit status is 0 for a pass and 1 for findings.

Defaults: the bundled sheet and a 4-pixel scale.

Global options precede the command:

```cmd
python skills\nuu\scripts\measure.py --scale 4 --sheet path\to\style.css check report.json
```

A report has this shape:

```json
{
  "width": 1280,
  "elements": [
    {"selector": ".row", "values": {"height": "40px", "gap": "16px"}}
  ]
}
```

## Full workflow tools

From the repository root in Windows cmd:

```cmd
set UI=skills\nuu\scripts\nuu.py
python %UI% doctor
python %UI% search "dashboard accessibility" --dataset ux-guidelines
python %UI% lint --project path\to\product
python %UI% extract --url https://example.com --artifacts evidence
python %UI% annotate -i evidence\1920-dark-no-preference.png -s findings.json -o annotated.png
python %UI% board -p "Desktop=annotated.png" -o board.png
python %UI% inspect --url https://example.com --artifacts evidence --output inspect.json
python %UI% flow --url https://example.com --flow flow.json
python %UI% a11y --url https://example.com --output a11y.json
python %UI% audit --project path\to\product --url https://example.com
```

```mermaid
flowchart TB
  B[Brief and authority] --> S[Search and proposal]
  S --> C[Source checks]
  C --> R[Rendered states and flows]
  R --> D[Review and design record]
```

[Tool contracts](../../skills/nuu/references/nuu.md) describe assets, live edits, eight review modes, inputs, exit codes, and missing coverage. Review modes supply evidence and task-specific checks. Visual judgment and repairs remain agent work. Search uses licensed local CSV data with source hashes, not external page content.

Read-only tools keep product files unchanged. Record creation, asset fetches, and transient live edits need their explicit command flags. Existing output files and design records are not overwritten.

## Limits

`measure.py` checks supplied pixel values. `nuu.py` adds local tools and optional browser evidence. Source checks cover selected HTML and CSS patterns. Script markup remains unverified until rendered.

Missing elements and non-pixel values do not become complete coverage checks. A passing report does not prove accessibility, usability, behavior, or visual quality. Those need rendered and interaction review.

This README is human documentation and is not part of the installed skill payload. The source credits follow.

## Sources

### Repositories

| Source | Commit | License |
| --- | --- | --- |
| [UI/UX Pro Max](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill/tree/56ea9cf174ed86786187daa9de0e6247cb0747e4) | `56ea9cf` | MIT |
| [Anthropic frontend-design](https://github.com/anthropics/skills/tree/dbd4588f9e1033efb41dad4bef2f7947c8993d44/skills/frontend-design) | `dbd4588` | Apache 2.0 |
| [Taste skill](https://github.com/Leonxlnx/taste-skill/tree/6010f91a9935f1c167dfc500fb1a475681892e6b) | `6010f91` | MIT |
| [Vercel Web Interface Guidelines](https://github.com/vercel-labs/web-interface-guidelines/tree/434b7f91364665f2f733b310ec54809bf8f37937) | `434b7f9` | MIT |
| [Impeccable](https://github.com/pbakaus/impeccable/tree/dad8dbb3aac21ad1fa236c110315ef4abece23e8) | `dad8dbb` | Apache 2.0 |

### Websites — fetched 2026-10-21

- [Jakob Nielsen: 10 Usability Heuristics](https://www.nngroup.com/articles/ten-usability-heuristics/)
- [NN/g: Good Visual Design, Explained](https://www.nngroup.com/articles/good-visual-design/)
- [GOV.UK: Design Manual](https://www.gov.uk/service-manual/design)
- [GOV.UK: Using, adapting and creating patterns](https://www.gov.uk/service-manual/design/using-adapting-and-creating-patterns)
- [W3C: WCAG 2.2 Quick Reference](https://www.w3.org/WAI/WCAG22/quickref/)
- [Atlassian Design System](https://atlassian.design/)
- [Atlassian: Design tokens](https://atlassian.design/foundations/tokens)
- [NN/g: Usability Testing 101](https://www.nngroup.com/articles/usability-testing-101/)
- [Pencil & Paper: UX Design Documentation Guide](https://www.pencilandpaper.io/articles/ux-design-documentation-guide)
- [Figma: Guide to Developer Handoff](https://www.figma.com/best-practices/guide-to-developer-handoff/)
- [Figma: Components, Styles, and Shared Libraries](https://www.figma.com/best-practices/components-styles-and-shared-libraries/)

### Credits

- `nuu` visual-reference structure and composite image-board examples: [UI Prep, The Best Way to Document UX/UI Design](https://www.uiprep.com/blog/the-best-way-to-document-ux-ui-design).
- `nuu` catalog data (`../../skills/nuu/data/vendor/ui-ux-pro-max/`): adapted under the MIT License (`../../skills/nuu/data/vendor/ui-ux-pro-max/LICENSE.txt`).
