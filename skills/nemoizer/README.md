# Nemoizer

Find and replace AI-flavored synonyms with plain words from one rotation table. The skill also guides prose and test review. Its tools check lexical matches and measurable prose limits, not meaning.

## Setup

The tools need Python 3 and no extra packages. Use the repository paths below, or install the agent payload as described in [Skills](../README.md).

[SKILL.md](SKILL.md) holds the agent instructions. [Rule reference](references/rules.md) holds the rotations, concrete lint IDs, exclusion syntax, and prose limits.

## Quick start

From the repository root in Windows cmd:

```cmd
python skills\nemoizer\scripts\nemoizer path\to\project
python skills\nemoizer\scripts\nemoizer --ignore vendor .
python skills\nemoizer\scripts\nemoizer collect path\to\project
```

The first two commands scan without edits. The collector lists every exclusion marker: location, ID, scope, and text. Unknown markers stay visible without suppressing a known rule.

## Formatting

Formatting changes files. It is a lexical rewrite, not a code refactor, and can change identifiers, strings, comments, data, and prose.

```cmd
python skills\nemoizer\scripts\nemoizer --format path\to\project
```

The command prints each changed line before and after the rewrite. Rule-specific exceptions and the rotation table are not rewritten.

## Prose counts

```cmd
python skills\nemoizer\scripts\nemoizer prose --context instruction --paragraph-cap 4 path\to\draft.md
```

Sentence context is explicit: instruction, description, or unknown. Instruction and description caps are 20 and 25 words. Unknown skips sentence checks but still checks paragraphs.

The paragraph cap is six sentences. A project can set a stricter cap from one through six. The example uses four.

Output is JSON with review candidates and per-file coverage. Native counters omit code spans and fences, treat ordinary pipe-table cells separately, and exclude headings, lists, quotes, and tables from paragraph counts.

## Results and limits

| Mode | Result |
| --- | --- |
| Scan | Text findings, with exit 1 when findings exist and 0 otherwise |
| Format | Changed lines, with exit 0 on completion |
| Collect | Every marker, with exit 0 on completion |
| Prose | JSON candidates and coverage, with exit 1 for candidates and 0 otherwise |

Invalid command arguments return exit 2. Prose mode requires existing target paths. Directory scans omit configured dependency, build, and session-state paths.

Tools skip binary and invalid UTF-8 files. The prose parser covers ordinary Markdown shapes, not all Markdown syntax, and does not infer instruction context or prove clarity, accuracy, or meaning preservation.

Manual review still covers unsupported claims, redundant prose, test behavior, and required protocol or verbatim-data contracts. This README is human documentation and is not part of the installed skill payload.
