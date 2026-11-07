# Wenyan ChatGPT experiment

Experimental only. It is not authoritative or validated.

## Purpose

Test whether hybrid Wenyan can preserve the complete ChatGPT instruction meaning in fewer Unicode characters than the current live English fields.

## Sources

- `rules/CHATGPT-CUSTOM.txt` and `rules/CHATGPT-MORE.txt` are the production character-count baselines.
- `rules/refs/CHATGPT.txt` is the merged complete semantic baseline.

## Method

- Candidates target ChatGPT's 1,500-character ceiling per field.
- Candidates aim to retain actors, actions, conditions, exceptions, negations, ordering, precedence, thresholds, paths, commands, identifiers, and checks.
- Technical identifiers and hard constraints stay in English where translation adds ambiguity.
- Wenyan-style phrasing appears only where context keeps its meaning explicit.
- Character savings alone do not establish semantic equivalence with production fields or `rules/refs/CHATGPT.txt`.

## Boundary

- Files in this directory are non-authoritative experiments.
- Top-level `rules/` and `maintenance/check.py` omit them.
- Production ChatGPT fields remain in `rules/CHATGPT-CUSTOM.txt` and `rules/CHATGPT-MORE.txt`.
