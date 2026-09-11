# rules/refs baselines

`rules/refs/` mirrors the agent-facing rule files in full, uncompressed wording, extrapolated clause-by-clause from `main` history (oldest rules commit `7841d84` through `dcea8d3`). Each clause keeps its longest historical sentence form; MUST/NEVER hard-rule markers are emphasis and kept as-is. Deleted rules stay deleted: the handoff document, the `agent-handoff` skill line, the MUST-print line for agents, general temp-file removal (CLINE), and the dropped scope item plus write-block preference (CHATGPT). Amendments are written here first in complete sentences, then squashed into `rules/`, preserving every negation, condition, command, number, threshold, filename, and caveat. Every change amends both this baseline and the live rule, so original wording is always preserved.

## Files

- `AGENTS.md` — uncompressed core rules.
- `ARENA.md` — uncompressed Arena rules.
- `CHATGPT.txt` — uncompressed ChatGPT instructions.
- `CLINE.md` — uncompressed Cline overlay.
- `COMMIT_SPEC.txt` — equals the live file; no compression was ever applied.
