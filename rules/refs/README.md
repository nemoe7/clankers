# rules/refs baselines

`rules/refs/` keeps full rule baselines from `main` history, oldest commit `7841d84` through `dcea8d3`. The baselines follow `GUIDELINES.md`:

- a one-line-rule constitution, one rule per line under domain headings, and a `When in doubt` closer.
- `MUST` and `NEVER` on the irreversible, the dangerous and the honesty rules, with every other rule positive (`GUIDELINES.md` 4.7).
- a `Use` opener in the core and `ARENA.md`, which the overlays omit.
- no closer in `KILO.md`, because the core settles its doubts.

See [maintenance/README.md](../../maintenance/README.md) for the refs-first maintenance procedure.

## Files

- `AGENTS.md` — uncompressed core rules.
- `ARENA.md` — uncompressed Arena rules.
- `CHATGPT-CUSTOM.txt` — uncompressed ChatGPT instructions for the `Custom Instructions` field of Personalization.
- `CHATGPT-MORE.txt` — uncompressed Personalization `More about you`: precedence, response rules, and overflow work rules.
- `CLINE.md` — uncompressed Cline overlay.
- `KILO.md` — uncompressed Kilo Code overlay: two tool rules, no core repetition.
- `kilo/plan.md`, `kilo/code.md`, `kilo/debug.md` — Kilo mode overrides, paired with the live `rules/kilo/`. Each one opens with an empty line, a `### Native <mode> Agent Overrides` heading, and the clause that it wins over a native reminder.
- `COMMIT-SPEC.txt` — uncompressed commit baseline. It matched live until the 2026-09-22 compression.
- `GUIDELINES.md` — the AGENTS.md writing and baseline-audit standard. It is a verbatim reference, not a rule baseline: no live counterpart or compression.
