# Amendment Proposal Template: Kilo

Before editing an agent-facing clause, submit its proposal in Plannotator. Approval covers all clauses in the submission. Use annotations for corrections or rejections. Resubmit only unresolved clauses.

For other harnesses, present the same clause layout and request approve, reject, or custom per clause using their native controls.

Use one section per clause. List exact guideline citations and the failure prevented. In each `diff`, prefix changed old lines with `-` and changed new lines with `+`. Keep unchanged context verbatim, omit only unchanged context, and never replace changed text with `...`.

Do not invent hunk line numbers. Additions have no `-` line. Deletions have no `+` line and leave the final clause empty. Keep quoted or explicitly verbatim wording unchanged.

Never wrap clause text in backticks in proposals, acks, or reports. Pair CORE proposals with ARENA and CHATGPT proposals in the same submission.

````markdown
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
````
