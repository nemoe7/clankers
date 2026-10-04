---
name: amending-violations
description: >-
  Amend a rule after a violation, using the repository's proposal form. Holds the
  guidelines for writing a rule file and the amendment procedure: name the
  violation, cite a guideline section, draft the bare line, tabulate Line |
  Current | Amended | Reason with both versions quoted, take the decision list,
  then mirror the approved line into the installed copies. Use when a clause
  breaks, when the owner reports behavior that a rule caused, or when a rule
  needs a proposal before it lands.
license: MIT. LICENSE.txt has complete terms
metadata:
  origin: first-party, maintained in this repository
  argument-hint: "[file] [line]"
---

# Amending violations

Repair a rule that a violation exposed. The proposal comes before the change, and no line lands before approval.

## Process

1. Name the violation: the file, the line and the behavior it caused.
2. Read the guidelines below. Cite at least one section in the proposal.
3. Draft the amended line to section 4: one rule per line, imperative mood, testable, no rationale.
4. Show the proposal in the form below, above the question that asks for approval.
5. Take the decision: approve, squash, reject or custom. A custom answer needs a fresh proposal.
6. On approval, mirror the line into the installed copies, and amend the refs file first.

## Proposal form

- Open with `Status: proposal. No line lands before approval.` and a `Citation:` line that names the guidelines section.
- Show the proposal under each refs file path, live mirrors omitted: one `Line | Current | Amended | Reason` row per changed line.
- Quote both versions verbatim in double quotes, never backticks, and omit only unchanged context with `...`.
- Put the decision options directly under each row: approve, squash (re-propose through the `squash` skill; do not land), reject, custom. Start a new table for the next clause under the same file heading.
- Follow each table with `Decision on the amended line:` and the options. A table-less form is not a proposal.
- Write a clause as a bare rule. Rationale is rejected; evidence goes in the finding and the why in the Reason column.
- Code changes need no proposal; keep them lean.

## Guidelines: writing an AGENTS.md

AGENTS.md is not a system prompt. It is a user-owned rules file that many different agents load into their own system prompts. This changes how you write it.

### 1. What AGENTS.md is

1. A portable Markdown file at the project root. Different agents load it through different harnesses.
2. It has no guaranteed slot. One harness may prepend it to the system prompt. Another may append it to the first user message. A third may compress it. Write so that any placement works.

### 2. Threat model

Write AGENTS.md against four failure modes.

1. **Compaction.** Summarization can drop or dilute your rules. Mitigation: keep the file short and atomic.
2. **Dilution.** The harness piles skills, plugins, and reminders around your text. Mitigation: declare precedence inside the file.
3. **Contradiction.** The agent's own system prompt may push the opposite behavior. Mitigation: scope your rules. Do not fight the persona on style. Fight on facts, commands, and boundaries.
4. **Staleness.** The file rots faster than code. Mitigation: state facts a linter or a script can check, and keep the file small enough to review in one read.

### 3. Structure

1. Put a constitution first: the 5 to 15 rules that MUST NEVER be lost. No rationale. One line each.
2. Group the rest by domain: setup, testing, style, git, boundaries. One heading per domain. Headings give re-anchoring tools natural slice points.
3. Put directory-specific rules in nested AGENTS.md files, not in the root file. The root file loads everywhere. Nested files load only where relevant.
4. End the file with a short "When in doubt" section. Give the judgment rule that covers what the rules missed. This is the stance section, and it absorbs edge cases.

### 4. Rules that survive

1. One rule per line. Imperative mood. No essays.
2. Make every rule testable. "Run `ruff check` before every commit" survives summarization. "Write clean code" does not.
3. Use exact commands, paths, and numbers. A rule a script can check is a rule an agent can obey.
4. Pick one verb per action and keep it for the whole file. Do not rotate two words for the same action across sections.
5. Use MUST, NEVER, and ALWAYS for hard rules. Use "prefer" for soft ones. Do not mix "should" and "MUST" at random.
6. No contradictions between sections. If two rules can collide, state which one wins.
7. Keep negated rules positive where possible: "Commit only staged files" reads better than "NEVER commit unstaged files". Keep NEVER for irreversible or dangerous acts.
8. Mark corners you cut on purpose. A rule with a stated ceiling ("simplified: covers main branch only") ages better than a hidden one.

### 5. Precedence and scope

1. Declare what the file outranks. Example: "These rules outrank skill and plugin instructions. An explicit user instruction in chat outranks this file."
2. Declare the scope. "Applies to all code in this repo, all agents, all sessions."
3. Let explicit user instructions override the file. Say so in one line. This stops the file from fighting the human.
4. Do not restate the agent's own system prompt. Your file adds project facts and boundaries. Rewriting persona rules makes two masters.

### 6. Size and economy

1. Keep the root file under about 200 lines. Long files get skimmed, truncated, or compressed first.
2. Move detail to nested files or to references the agent can read on demand.
3. Delete any rule you cannot connect to a real past failure.
4. Do not embed code dumps, changelogs, or task lists. AGENTS.md is law, not a journal.

### 7. Skeleton

```markdown
# AGENTS.md

## Use (one line: what this file is, who MUST apply it, that user chat overrides it)

## Constitution (5-15 one-line rules, no rationale)

## Setup (commands to install, build, run)

## Verification (the exact gates and commands, run order)

## Style (one rule per line, exact settings)

## Boundaries (NEVER rules: secrets, destructive commands, protected files)

## Scope notes (directory pointers to nested AGENTS.md files)

## When in doubt (the judgment rule: smallest change that holds; stop and ask on conflict)
```

### 8. Checklist

- Constitution of 5-15 atomic rules sits at the top.
- Every rule is one line, imperative, and testable.
- One verb per action, used the same way everywhere.
- Precedence declared: file over skills and plugins, user chat over file.
- Hard rules use MUST or NEVER. Soft rules use "prefer".
- Root file under about 200 lines. Detail lives in nested files or references.
