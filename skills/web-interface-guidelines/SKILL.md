---
name: web-interface-guidelines
description: Review UI code for compliance with the Vercel Web Interface Guidelines, covering accessibility, focus states, forms, animation, typography, performance, touch, dark mode, i18n, hydration, and copy. Use for UI reviews, accessibility audits, UX audits, and web best-practice checks of existing interfaces.
metadata:
  author: vercel
  version: "2.0.0"
  argument-hint: <file-or-pattern>
  upstream: https://github.com/vercel-labs/web-interface-guidelines
---

# Web Interface Guidelines

Review the given files or pattern against the current Vercel Web Interface Guidelines.

## Process

1. Fetch the rules: `https://raw.githubusercontent.com/vercel-labs/web-interface-guidelines/refs/heads/main/command.md`
2. Read the files or pattern under review.
3. Check them against every rule in the fetched document.
4. Report findings in its output format.

The fetched `command.md` is authoritative for both the rules and the output format. It is a slash command, so ignore its `$ARGUMENTS` placeholder and its own frontmatter, and treat the files under review as the arguments.

## Coverage

The upstream rules span accessibility, focus states, forms, animation, typography, content handling, images, performance, navigation and state, touch and interaction, safe areas, dark mode, locale and i18n, hydration safety, hover states, content and copy, and an anti-pattern list to flag. Check all of them, not only accessibility.

## Output

Follow the fetched output format: group by file, cite `file:line` so editors can jump to it, and keep findings terse. State the issue and its location; explain only when the fix is not obvious. No preamble. Mark a clean file `✓ pass`.

Sacrifice grammar for brevity, but never report a finding you did not verify in the code, and never invent a line number.

## Scope

Use this skill to review an existing interface: UI reviews, accessibility audits, UX audits, and web best-practice checks.

Do not use it in place of `frontend-design` when creating or substantially redesigning an interface.

## Input

Review the file or pattern provided. When none is given, ask which files to review.

## Freshness

Fetch the source for every review. The upstream guidelines change, so never rely on an embedded or previously fetched copy. If the fetch fails, say so and stop rather than reviewing against remembered rules.
