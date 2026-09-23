# Portable reports

## Layout and ownership

Install `arena-preview-reporting` beside `arena-preview-steering`. The latter contains the only runtime and static assets. Reporting supplies publishing/renderer setup; neither skill assumes a Clankers checkout. Report missing companions as installation problems, not grounds for a second server.

Persist state and sources in ignored paths; verify ignoring with Git before starting. Keep one Markdown file/stable ID per subject; multiple report IDs may coexist. Re-publishing an ID updates its title, Markdown snapshot and timestamp. Source edits alone never update published snapshots.

The shared server requires `markdown-it-py`. Without it, startup fails with an install command. Steering CLI commands still work without the renderer. Always install missing `markdown-it-py` in a workspace venv without asking. Reuse a venv or create one as needed; start/restart the server with its Python. Keep skill-only dependencies out of app manifests and generated `requirements.txt` unless the app independently needs them.

## Suggested report structure

```markdown
# Review title

**Result:** one clear outcome.

## Changes

- What changed and why.

## Checks

| Check | Result |
| --- | --- |
| Actual check command | Pass, fail or not run |

## Findings and disposition

- Open: issue and impact.
- Resolved: issue and verified resolution.

## Limits

- Assumptions, unverified behavior and remaining decisions.
```

Follow the target repository's style; in Clankers reports, allow lines up to 120 characters. Never invent claims to fill the template. Short answers stay in chat. No Mermaid, remote fonts, CDN scripts or externally loaded images are needed.

## Delivery behavior

Delivery is the live Reports tab. Keep UTF-8 Markdown as the durable artifact. Raw Markdown HTML is disabled. Tables are supported, but not every GitHub Markdown extension or syntax-highlighting theme.

A report may also carry fields: `- ( ) option` for one choice, `- [ ] option` for many, and `Label: ___` or a bare `___` line for text. The steering reference documents prompts, IDs and limits. Answers arrive as one inbox note headed `REPORT <id> <title>:`.

Verify a served report's content before claiming successful rendering. File existence never proves native-viewer Markdown rendering.

If the preview becomes unreliable, report what failed and agree on a new delivery method with the user. Do not automatically resurrect former workflows.
