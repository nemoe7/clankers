# rules/refs baselines

`rules/refs/` mirrors the agent-facing rule files in full, uncompressed wording. The text comes clause by clause from the `main` history, from the oldest rules commit `7841d84` through `dcea8d3`. Each clause keeps its longest historical sentence form. `MUST` and `NEVER` are emphasis, and they stay on the irreversible, the dangerous, and the honesty rules. Every other rule reads positively (see `GUIDELINES.md` section 4.7). The rule baselines follow `GUIDELINES.md`. They carry a constitution of one-line rules, one per line under domain headings, and a `When in doubt` closer that `KILO.md` drops. The core settles the doubts that closer would restate. The core and `ARENA.md` open with a `Use` section. The overlays do not.

Amend here first, before any live file. Write the amendment in complete sentences, and keep every negation, condition, command, number, threshold, filename, and caveat. Then mirror the amendment into its live file in `rules/` in compressed form, and squash only the new or affected line. On a removal, attempt one squash and keep the lower budget. A copy of a baseline would exceed every live budget. Refs stay uncompressed, so the original wording is never lost.

## Files

- `AGENTS.md` — uncompressed core rules.
- `ARENA.md` — uncompressed Arena rules.
- `CHATGPT-CUSTOM.txt` — uncompressed ChatGPT instructions for the `Custom Instructions` field of Personalization.
- `CHATGPT-MORE.txt` — uncompressed ChatGPT instructions for the `More about you` field of Personalization. The field holds the precedence rule, the response rules, and the work rules that the other field cannot take.
- `CLINE.md` — uncompressed Cline overlay. It no longer carries an MCPs section, which the owner dropped, so the `tokensave` reference went with it.
- `KILO.md` — uncompressed Kilo Code overlay: the two tool rules, with nothing that the core already states.
- `kilo/plan.md`, `kilo/code.md`, `kilo/debug.md` — Kilo mode overrides, paired with the live `rules/kilo/`. Each one opens with an empty line, a `### Native <mode> Agent Overrides` heading, and the clause that it wins over a native reminder.
- `COMMIT-SPEC.txt` — equals the live file, because no compression ever applied to it.
- `GUIDELINES.md` — the standard for writing an AGENTS.md, against which an audit reads these baselines. It is a reference, not a rule baseline: no live counterpart, never compressed. The file stays verbatim, so parts of it describe a platform that this repository does not use. Section 1.2 gives Kilo loading behavior and `<system-reminder>` wrapping, and section 2.1 gives the `kilo/enforce-rules-plugin/` pointer.
