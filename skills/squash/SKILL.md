---
name: squash
description: >
  Compress existing text against a size budget, measured in tokens, words,
  characters, or bytes, while preserving its full meaning. Iterative passes
  remove words, never content: every claim, negation, condition, number, name,
  command, and caveat survives. Use when the user supplies or points to text and
  asks to squash it, compress it, fit it into a budget, context window, prompt
  field, or character limit, or get it under a stated token, word, character, or
  byte count. The request must be about the size of specific text. Ignore the
  bare words "shorten", "trim", "condense", or "tighten" when they describe
  writing something new, cutting scope, shortening a process, or reducing an
  unrelated quantity. Do NOT use to summarize, abridge, outline, paraphrase, or
  rewrite for a new audience, since those discard content by design.
license: MIT. LICENSE.txt has complete terms
metadata:
  origin: first-party, maintained in this repository
  argument-hint: "[tokens|words|chars|bytes] [target]"
---

# Squash

Compress text against a stated budget without losing anything it says.

Squashing is editorial, not lossy: it removes words, never content.

## Criterion

Pick the unit first, measure it before and after, and keep every pass that lowers it. Use whatever unit measures the real limit:

| Unit | Use when | How to count |
| --- | --- | --- |
| tokens | context windows, model budgets, prompt cost | the consuming model's tokenizer, `cl100k_base` when absent, and say which |
| words | drafts, human review, no tooling | whitespace-separated words |
| characters (`chars`) | form fields, hard input limits | Unicode characters, including whitespace and newlines |
| bytes | file size, upload limits | UTF-8 bytes |

Resolve the unit in this order, stopping at the first that applies:

1. the unit the user names
2. the unit that carries any stated limit
3. tokens, when a model consumes the text
4. characters, when a human or an input field consumes it
5. tokens, and say that you chose it

Never substitute a proxy silently: say which unit governs, and label any count you could not measure directly an estimate.

Set the target first: an explicit budget, a percentage, or "as small as still faithful". Without a target, stop when a pass yields nothing safe.

### Mixed units

Text often satisfies several limits at once, such as a character cap on a field whose contents also cost tokens. Accept every budget given and treat them as simultaneous constraints, not alternatives.

Units do not move together: contractions and symbols can cut characters while adding tokens, and fewer words can leave bytes unchanged. Measure every governing unit after each pass. Keep a pass only when no budget regresses, and let whichever unit is still over drive the next pass. Report all of them.

When budgets conflict, so satisfying one pushes another over, stop and report the conflict with both counts rather than picking a winner.

## What must survive

Never drop:

- claims, instructions, conclusions
- negations and exceptions: never, no, except, unless, only
- conditions and triggers: if, when, before, after, until
- numbers, units, thresholds, limits, dates, versions
- names, paths, filenames, commands, flags, identifiers, links
- caveats, warnings, stated uncertainty
- ordering and precedence when they carry meaning

Removing one of these edits the content, not the wording. Do it only when asked, and report it.

## What to cut

- filler: preambles, transitions, throat-clearing, restated topic sentences
- redundant qualifiers: very, quite, really, actually, simply, just, in order to
- clauses restating a neighbor
- the longer of two equivalent phrasings
- metadiscourse: "it is worth noting that", "as mentioned above"
- context the reader already has

Merge items sharing a subject into one sentence or bullet.

## Method

1. Measure the input in every governing unit and record the numbers.
2. Read for meaning. List the load-bearing points to check later.
3. Pass over the text making only safe reductions.
4. Re-measure. Keep the pass when nothing was lost and no budget regressed. Otherwise discard it.
5. Repeat, targeting whichever unit is still over, until every target is met or a pass yields nothing.
6. Check against the step 2 list, then report before, after, and percentage.

Keep each pass small enough to review.

## Constraints

Keep the structure: headings, section order, list versus prose, tables, code blocks. Squashing shortens and never reorganizes. Reorganizing is a separate request.

Keep the register and audience. Do not turn prose into telegraphic notes, invent abbreviations, or drop articles until the text reads as a different document. Terse, but unambiguous: cryptic is a failed pass.

Keep verbatim spans verbatim: quotations, code, commands, error strings, identifiers, anything the reader must copy exactly.

Preserve voice, person, and tense. A rule saying "never push" must not become "avoid pushing".

## Adding to squashed text

New content may push the text over budget. Compress the rest in the same change so the result lands at or below the previous measurement in every governing unit. Report the addition and the recovery.

## Reporting

State each governing unit and how you counted it, before and after counts, percentage saved, and pass count. Name anything you could not compress without risking meaning, anything removed with the user's approval, and any budget left unmet. Add a fixtures table when one change covers several files: before, after and percentage saved per file, plus the average.

Never claim a measurement you did not take.
