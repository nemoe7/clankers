---
name: squash
description: >
  Compress existing text against a size budget, measured in tokens, words,
  characters, or bytes, while preserving its full meaning. Iterative passes
  remove words, never content: every claim, negation, condition, number, name,
  command, and caveat survives. Use when the user supplies or points to text and
  asks to squash it, compress it, fit it into a budget, context window, prompt
  field, or character limit, or get it under a stated token, word, character, or
  byte count. The request must be about the size of specific text; ignore the
  bare words "shorten", "trim", "condense", or "tighten" when they describe
  writing something new, cutting scope, shortening a process, or reducing an
  unrelated quantity. Do NOT use to summarize, abridge, outline, paraphrase, or
  rewrite for a new audience, since those discard content by design.
license: MIT. LICENSE.txt has complete terms
metadata:
  origin: first-party, maintained in this repository
  argument-hint: "[tokens|words|chars|bytes] [target]"
  baseline: >-
    Unsquashed original of `SKILL.md` in this directory. Amend this file first,
    then squash it into `SKILL.md` and re-measure that file against its budget
    in the repository README. This file carries no budget of its own.
---

# Squash

Compress text against a stated budget without losing anything the text says.

Squashing is editorial, not lossy: it removes words, never content. If a reader learns less from the output than from the input, the pass failed.

## Use

- This file is the unsquashed baseline of the `squash` skill. It holds the full wording that `SKILL.md` is compressed from, and it carries no budget of its own.
- Amend this file first. Then squash it into `SKILL.md` in the same directory and re-measure that file against the budget recorded for it in the repository README.
- `SKILL.md` is the entry point an agent loads when it performs compression. This file is the record of everything the compressed form must still say, so a rule that survives here and vanishes in `SKILL.md` is a compression failure, not an amendment.
- These instructions specialize how compression is done. They NEVER override an explicit user instruction about what the text must say, and they NEVER replace a project convention.

## Criterion

Pick the unit first. Measure the text in that unit before the first pass and after every pass, and keep only the passes that lower it. Use whatever unit the real limit is measured in.

| Unit | Use when | How to count |
| --- | --- | --- |
| tokens | context windows, model budgets, prompt cost | the consuming model's tokenizer; absent one, `cl100k_base`, and say so |
| words | drafts, human review, no tooling | whitespace-separated words |
| characters (`chars`) | form fields, hard input limits | Unicode characters, including whitespace and newlines |
| bytes | file size, upload limits | UTF-8 bytes |

Resolve the unit in this order, stopping at the first step that applies:

1. the unit the user names;
2. the unit any stated limit is written in;
3. tokens, when a model consumes the text;
4. characters, when a human or an input field consumes the text;
5. tokens, and say that you chose it.

Never substitute a proxy silently. Say which unit governs, and label any count you could not measure directly an estimate rather than presenting it as measured.

Set the target before the first pass. A target is an explicit budget, a percentage, or "as small as still faithful". With no target, stop when a pass yields nothing safe to remove.

### Mixed units

Text often satisfies several limits at once, such as a character cap on a field whose contents also cost tokens. Accept every budget given, and treat them as simultaneous constraints rather than alternatives.

Units do not move together. Contractions and symbols can cut characters while adding tokens, and fewer words can leave bytes unchanged. Measure every governing unit after each pass, keep a pass only when no budget regresses, and let whichever unit is still over drive the next pass. Report all of them.

When budgets conflict, so that satisfying one pushes another over, stop and report the conflict with both counts rather than picking a winner on the user's behalf.

## What must survive

Never drop any of the following. Removing one of these edits the content rather than the wording, so do it only when asked, and report it:

- claims, instructions, conclusions;
- negations and exceptions: never, no, except, unless, only;
- conditions and triggers: if, when, before, after, until;
- numbers, units, thresholds, limits, dates, versions;
- names, paths, filenames, commands, flags, identifiers, links;
- caveats, warnings, stated uncertainty;
- ordering and precedence, where they carry meaning.

## What to cut

- filler: preambles, transitions, throat-clearing, restated topic sentences;
- redundant qualifiers: very, quite, really, actually, simply, just, in order to;
- clauses that restate a neighbour;
- the longer of two equivalent phrasings;
- metadiscourse such as "it is worth noting that" and "as mentioned above";
- context the reader already has.

Merge items that share a subject into one sentence or one bullet.

## Method

1. Measure the input in every governing unit and record the numbers.
2. Read for meaning, and list the load-bearing points to check against later.
3. Pass over the text making only safe reductions.
4. Re-measure. Keep the pass when nothing was lost and no budget regressed; otherwise discard it.
5. Repeat, targeting whichever unit is still over, until every target is met or a pass yields nothing safe.
6. Verify the result against the list from step 2, then report before, after, and the percentage saved.

Keep each pass small enough to review. Several modest passes beat one aggressive rewrite, because a lost constraint is easier to spot in a short diff than in a rewritten document.

## Constraints

Keep the structure: headings, section order, list versus prose, tables, and code blocks. Squashing shortens; it never reorganizes. Reorganizing is a separate request.

Keep the register and the audience. Do not turn prose into telegraphic notes, invent abbreviations, or drop articles until the text reads as a different document. Terse, but unambiguous, is the passing result; cryptic is a failed pass.

Keep verbatim spans verbatim: quotations, code, commands, error strings, identifiers, and anything else the reader must copy exactly.

Preserve voice, person, and tense. A rule that says "never push" must not come out of a pass as "avoid pushing".

## Adding to squashed text

New content may push the text over its budget. Compress the rest of the text in the same change, so that the result lands at or below the previous measurement in every governing unit. Report both the addition and the recovery that paid for it.

## Reporting

State each governing unit and how it was counted, the before and after counts, the percentage saved, and the number of passes. Name anything you could not compress without risking meaning, anything you removed with the user's approval, and any budget left unmet.

Never claim a measurement you did not take.

## When in doubt

- Preserve meaning over length: a text that is over budget and complete beats one that fits and lost a constraint.
- Stop and report rather than guessing which unit governs, which budget wins, or whether a cut is safe.
