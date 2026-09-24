# WENYAN CHATGPT EXPERIMENT

Experimental only; not authoritative or validated.

## Purpose

Test whether hybrid Wenyan can preserve the complete ChatGPT instruction meaning in fewer Unicode characters than the current live English fields.

## Sources

- `rules/CHATGPT-CUSTOM.txt` and `rules/CHATGPT-MORE.txt` are the production character-count baselines.
- `rules/refs/CHATGPT-CUSTOM.txt` and `rules/refs/CHATGPT-MORE.txt` are the complete semantic baselines.

## Method

- Optimize Unicode character count only; ChatGPT's field limit is 1,500 characters.
- Preserve actors, actions, conditions, exceptions, negations, ordering, precedence, thresholds, paths, commands, identifiers, and verification requirements.
- Keep technical identifiers and hard constraints in English when that reduces interpretation risk.
- Wenyan-style Chinese is used only where its meaning remains explicit from context.
- Compare the candidate with both production fields and full refs; do not treat character savings as proof of semantic equivalence.

## Boundary

- Nothing here is authoritative.
- Do not mirror these files into `rules/`.
- Do not add them to `maintenance/check.py`.
- Do not replace the production ChatGPT fields unless a later decision explicitly adopts the experiment.
