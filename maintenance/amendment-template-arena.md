# Amendment Proposal Template: Arena Steering

Publish proposals as Steering fielded reports, not chat. Use one section and one unique field ID per clause. List exact guideline citations and the failure prevented.

In each `diff`, prefix changed old lines with `-` and changed new lines with `+`. Keep unchanged context verbatim, omit only unchanged context, and never replace changed text with `...`. Do not invent hunk line numbers.

Additions have no `-` line. Deletions have no `+` line and leave the final clause empty. Keep quoted or explicitly verbatim wording unchanged. Never wrap clause text in backticks in proposals, acks, or reports.

Pair CORE proposals with ARENA and CHATGPT proposals in the same report. Keep each field directly below its clause. Use the built-in "Something else..." input for custom wording. Submit a new proposal for custom wording before editing.

## <filename.ext> - <clause-name>

Citations:
- <rules/GUIDELINES.md or system-prompts/GUIDELINES.md>, Section <N> <Title>: "<exact guideline rule text>"

Failure: <one sentence stating the failure this amendment prevents.>

```diff
-<exact old clause; omit for addition>
+<exact new clause; omit for deletion>
```

Reason: <one sentence stating what changes.>

Final clause:
<exact resulting clause (empty on deletion)>

<!-- question {"id":"<unique-clause-id>","label":"<specific clause outcome>"} -->
Should this clause change be applied?
- (x) <exact final clause> <!-- option {"label":"<exact final clause>"} -->
- ( ) Keep <current behavior> <!-- option {"label":"Keep <current behavior>"} -->
