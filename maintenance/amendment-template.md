# Amendment Proposal Template

Use a short filename in the heading, such as `ARENA.md` or `nuu/SKILL.md`. Always edit baseline `refs` files first, then squash approved lines into live copies. Render `approve`, `reject`, and `custom` with native option controls when the harness supports them.

```markdown
## <filename.ext> - <clause-name>

Citations:
- <rules/GUIDELINES.md or system-prompts/GUIDELINES.md>, Section <N> <Title>: "<guideline rule text>"

Failure: <one sentence stating the failure this amendment prevents.>

| Line | Diff | Reason |
| --- | --- | --- |
| <N> | <unchanged text ~~removed~~ <mark>inserted</mark>> | <one sentence stating what changes.> |

Final clause:
<exact final clause without diff markup or backticks>

- approve
- reject
- custom
```
