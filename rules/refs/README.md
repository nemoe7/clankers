# rules/refs baselines

`rules/refs/` mirrors the agent-facing rule files in full, uncompressed wording. The text comes clause by clause from the `main` history, from the oldest rules commit `7841d84` through `dcea8d3`. Each clause keeps its longest historical sentence form. `MUST` and `NEVER` are emphasis, and they stay on the irreversible, the dangerous, and the honesty rules. Every other rule reads positively (see `GUIDELINES.md` section 4.7). The baselines follow `GUIDELINES.md`: a constitution of one-line rules, one rule per line under domain headings, and a `When in doubt` closer. The core and `ARENA.md` also open with a `Use` section. `KILO.md` drops the closer, because the core settles its doubts. The overlays drop the opener.

Amend here first, before any live file, in complete sentences that keep every negation, condition, command, number, threshold, filename, and caveat. Then mirror it into its live file in `rules/` compressed, squashing only the new or affected line. On a removal, attempt one squash and keep the lower budget. A baseline copy would exceed every live budget, so refs stay uncompressed and the original wording is never lost.

## Files

- `AGENTS.md` — uncompressed core rules.
- `ARENA.md` — uncompressed Arena rules.
- `CHATGPT-CUSTOM.txt` — uncompressed ChatGPT instructions for the `Custom Instructions` field of Personalization.
- `CHATGPT-MORE.txt` — uncompressed ChatGPT instructions for the `More about you` field of Personalization. The field holds the precedence rule, the response rules, and the work rules that the other field cannot take.
- `CLINE.md` — uncompressed Cline overlay.
- `KILO.md` — uncompressed Kilo Code overlay: the two tool rules, with nothing that the core already states.
- `kilo/plan.md`, `kilo/code.md`, `kilo/debug.md` — Kilo mode overrides, paired with the live `rules/kilo/`. Each one opens with an empty line, a `### Native <mode> Agent Overrides` heading, and the clause that it wins over a native reminder.
- `COMMIT-SPEC.txt` — equals the live file, because no compression ever applied to it.
- `GUIDELINES.md` — the standard for writing an AGENTS.md, against which an audit reads these baselines. It is a reference, not a rule baseline: no live counterpart, never compressed. It stays verbatim, so parts describe a platform this repository does not use. Section 1.2 gives Kilo loading behavior and `<system-reminder>` wrapping. Section 2.1 gives the `kilo/enforce-rules-plugin/` pointer.
