# rules/refs baselines

`rules/refs/` keeps full rule baselines from `main` history, oldest commit `7841d84` through `dcea8d3`. Each clause keeps its longest historical sentence. `MUST` and `NEVER` emphasize irreversible, dangerous, and honesty rules. Others read positively (`GUIDELINES.md` 4.7). Baselines follow `GUIDELINES.md`: a one-line-rule constitution, one rule per line under domain headings, and a `When in doubt` closer. The core and `ARENA.md` open with `Use`. Overlays omit that opener. `KILO.md` also omits the closer because the core settles its doubts.

Amend here before live files. Use complete sentences and keep every negation, condition, command, number, threshold, filename, and caveat. Mirror into `rules/`, compressing only the new or affected line. On removal, attempt one squash and keep the lower budget. Refs retain the uncompressed originals, which would exceed every live budget.

## Files

- `AGENTS.md` — uncompressed core rules.
- `ARENA.md` — uncompressed Arena rules.
- `CHATGPT-CUSTOM.txt` — uncompressed ChatGPT instructions for the `Custom Instructions` field of Personalization.
- `CHATGPT-MORE.txt` — uncompressed Personalization `More about you`: precedence, response rules, and overflow work rules.
- `CLINE.md` — uncompressed Cline overlay.
- `KILO.md` — uncompressed Kilo Code overlay: two tool rules, no core repetition.
- `kilo/plan.md`, `kilo/code.md`, `kilo/debug.md` — Kilo mode overrides, paired with the live `rules/kilo/`. Each one opens with an empty line, a `### Native <mode> Agent Overrides` heading, and the clause that it wins over a native reminder.
- `COMMIT-SPEC.txt` — uncompressed commit baseline. It matched live until the 2026-09-22 compression.
- `GUIDELINES.md` — the AGENTS.md writing and baseline-audit standard. It is a verbatim reference, not a rule baseline: no live counterpart or compression. Some parts describe an unused platform: 1.2 covers Kilo loading and `<system-reminder>` wrapping, and 2.1 links `kilo/enforce-rules-plugin/`.
