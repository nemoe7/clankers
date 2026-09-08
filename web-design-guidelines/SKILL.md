---
name: web-design-guidelines
description: Review UI code against the current Web Interface Guidelines. Use for UI reviews, accessibility audits, UX audits, and web best-practice checks.
metadata:
  author: vercel
  version: "1.0.0"
  argument-hint: <file-or-pattern>
---

# Web Design Guidelines

Review the specified UI against the latest Web Interface Guidelines.

## Process

1. Fetch the latest rules from:
   `https://raw.githubusercontent.com/vercel-labs/web-interface-guidelines/main/command.md`
2. Read the specified files or pattern.
3. Apply all relevant rules from the fetched guidelines.
4. Report findings using the fetched guidelines' required format, including terse `file:line` findings when specified.

The fetched `command.md` is authoritative for the rules and review output format.

## Scope

Use this skill for:

- UI reviews
- accessibility audits
- UX audits
- web best-practice checks
- checking an existing interface against Web Interface Guidelines

Do not use it instead of `frontend-design` when creating or substantially redesigning an interface.

## Input

When a file or pattern is provided, review it directly.

When no target is provided, ask which files or pattern to review.

## Freshness

Fetch the guideline source for every review. Do not rely on an embedded or previously fetched copy because the upstream guidelines may change.
