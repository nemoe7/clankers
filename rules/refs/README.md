# rules/refs baselines

`rules/refs/` mirrors the agent-facing rule files in full, uncompressed wording, extrapolated clause-by-clause from `main` history (oldest rules commit `7841d84` through `dcea8d3`). Each clause keeps its longest historical sentence form. MUST/NEVER markers are emphasis and stay on irreversible, dangerous, and honesty rules; other rules read positively (see `GUIDELINES.md` section 4.7). The rule baselines follow `GUIDELINES.md`: a `Use` section, a constitution of one-line rules, one rule per line under domain headings, and a `When in doubt` closer. Amend here first, before touching any live file: write the amendment in complete sentences, preserving every negation, condition, command, number, threshold, filename, and caveat. Then mirror the amendment into its corresponding live file in `rules/` in compressed form, and squash only the new or affected line; on a deletion, attempt one squash and keep the lower budget; copying a baseline verbatim would exceed every live budget. Refs stay unsquashed, so the original wording is never lost.

## Files

- `AGENTS.md` — uncompressed core rules.
- `ARENA.md` — uncompressed Arena rules.
- `CHATGPT-CUSTOM.txt` — uncompressed ChatGPT instructions for Personalization's `Custom Instructions` field.
- `CHATGPT-MORE.txt` — uncompressed ChatGPT instructions for Personalization's `More about you` field: the precedence rule, the response rules, and the work rules the other field cannot fit.
- `CLINE.md` — uncompressed Cline overlay; it no longer carries an MCPs section, dropped on request, so the `tokensave` reference went with it.
- `KILO.md` — uncompressed Kilo Code overlay: the two tool rules and the pointer to the mode overrides, with nothing the core already states.
- `kilo/plan.md`, `kilo/code.md`, `kilo/debug.md` — Kilo mode overrides, paired with the live `rules/kilo/`: each opens with an empty line, a `### Native <mode> Agent Overrides` heading, and the clause that it wins over a native reminder.
- `COMMIT-SPEC.txt` — equals the live file; no compression was ever applied.
- `GUIDELINES.md` — the standard for writing an AGENTS.md, which these baselines are audited against. A reference, not a rule baseline: no live counterpart, never squashed. Kept verbatim, so parts of it describe a platform this repository does not use: section 1.2's Kilo loading behavior and `<system-reminder>` wrapping, and section 2.1's `kilo/enforce-rules-plugin/` pointer.
