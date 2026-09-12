# rules/refs baselines

`rules/refs/` mirrors the agent-facing rule files in full, uncompressed wording, extrapolated clause-by-clause from `main` history (oldest rules commit `7841d84` through `dcea8d3`). Each clause keeps its longest historical sentence form. MUST/NEVER markers are emphasis and stay on irreversible, dangerous, and honesty rules; other rules read positively (see `GUIDELINES.md` section 4.7). The rule baselines follow `GUIDELINES.md`: a `Use` section, a constitution of one-line rules, one rule per line under domain headings, and a `When in doubt` closer. Amend here first, before touching any live file: write the amendment in complete sentences, preserving every negation, condition, command, number, threshold, filename, and caveat. Then copy the amended baseline onto its corresponding live file in `rules/`, and squash that live copy back under its budget. Refs stay unsquashed, so the original wording is never lost.

## Files

- `AGENTS.md` — uncompressed core rules.
- `ARENA.md` — uncompressed Arena rules.
- `CHATGPT.txt` — uncompressed ChatGPT instructions.
- `CLINE.md` — uncompressed Cline overlay; it no longer carries an MCPs section, dropped on request, so the `tokensave` reference went with it.
- `COMMIT_SPEC.txt` — equals the live file; no compression was ever applied.
- `GUIDELINES.md` — the standard for writing an AGENTS.md, which these baselines are audited against. A reference, not a rule baseline: no live counterpart, never squashed.
