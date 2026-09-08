---
name: frontend-design
description: "Distinctive, intentional visual design for new or substantially redesigned interfaces. Use when typography, visual hierarchy, layout, motion, interface copy, or visual direction require deliberate design decisions."
license: Complete terms in LICENSE.txt
---

# Frontend Design

Design the interface as a deliberate visual system, not a generic template.

## Ground the Design

Base visual decisions on:

- product or subject matter
- target audience
- primary user goal
- intended visual character

When the visual direction is undefined, propose a concrete direction based on the subject, audience, and primary job.

For prominent pages, make the hero the most characteristic element: use the form most appropriate to the product rather than defaulting to a large headline, stats, and decorative accent.

## Design Principles

### Visual Identity

Make deliberate choices about:

- color
- typography
- spacing
- layout
- hierarchy
- imagery
- shape and surface treatment

Every major visual element should have a purpose.

### Typography

- Prefer one or two intentional typefaces.
- Define clear type roles, scale, weight, and spacing.
- Keep normal text lines roughly under 80 characters.
- Give serif body text slightly more line-height when appropriate.
- Treat display typography as part of the visual identity.

Avoid generated-page tells:

- emphasizing one headline word with a different color, weight, or style without a clear reason
- unnecessary all-caps labels
- decorative labels or eyebrows above content

### Structure

Treat visual structure as information.

Use borders, dividers, numbering, labels, outlines, and similar devices only when they communicate meaningful structure.

Do not add numbered markers unless the content is actually sequential.

### Motion

- Use motion deliberately and sparingly.
- Prefer motion that communicates state or responds to user action.
- A single orchestrated entrance or reveal is usually better than scattered effects.
- Avoid applying the same fade, slide, or hover effect everywhere.
- Respect reduced-motion preferences.

## Avoid Generic Defaults

Common patterns are not forbidden, but they must be justified by the brief.

Avoid defaulting to familiar generated combinations such as:

- cream + serif + terracotta
- near-black + bright acid accent
- broadsheet/newspaper styling
- identical rounded SaaS cards with soft shadows
- decorative gradients
- repetitive all-caps eyebrows
- monospace metadata everywhere
- decorative arrows appended to actions

When the brief explicitly requests such a style, follow the brief.

## Two-Pass Process

### Pass 1 — Design System

Before implementation, define:

**Color**

- 4–6 core colors
- named roles
- concrete values when useful

**Typography**

- families
- roles
- scale
- weights

**Layout**

- overall composition
- alignment
- spacing
- responsive behavior
- important regions

Use a simple wireframe when comparing materially different layouts.

**Principles**

- what makes the interface appropriate to the product
- what should be visually memorable
- what should remain quiet

### Pass 2 — Critique

Review the proposed direction against the brief before coding:

1. Does it fit the subject and audience?
2. Are the major choices specific to this brief?
3. Does anything look like a generic template?
4. Is the hierarchy clear?
5. Is there a useful memorable element?
6. Can decoration be removed without weakening the design?

Revise generic or unjustified choices before implementation.

## Restraint

Spend visual boldness selectively.

Prefer:

- one memorable focal point
- disciplined supporting elements
- meaningful contrast
- intentional whitespace
- removal of decoration that adds no value

Distinctive does not mean visually busy.

## Interface Copy

Treat text as part of the interface design.

- Write from the user's perspective.
- Use plain language and active voice.
- Name things by what users understand, not by implementation details.
- Name actions consistently throughout the interface.
- Make buttons describe what they actually do.
- Keep terminology consistent across actions, confirmations, and notifications.
- Make errors explain what happened and what the user can do next.
- Make empty states provide useful direction.
- Avoid filler, vagueness, and unnecessary marketing language.

## Quality Floor

Every implementation should account for:

- responsive behavior, including mobile
- readable typography
- sufficient contrast
- visible keyboard focus
- accessible interaction targets
- loading states
- error states
- empty states
- reduced-motion preferences

Do not treat these as optional polish.

## Implementation

- Use predictable CSS selectors and avoid specificity conflicts.
- Prefer reusable design tokens for repeated visual values.
- Do not introduce abstractions solely to eliminate small amounts of repetition.
- Preserve existing project conventions unless the design requires a justified change.
- Review the rendered result, preferably with screenshots, when the environment supports it.

## Final Critique

Before considering the UI complete:

1. Does the visual language fit the product and audience?
2. Is the interface recognizably intentional rather than templated?
3. Is hierarchy obvious?
4. Is the memorable element useful?
5. Is unnecessary decoration removed?
6. Are usability and accessibility intact?
