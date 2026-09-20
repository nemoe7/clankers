# Portable reports

## Layout and ownership

Install `arena-preview-reporting` beside `arena-preview-steering`. The latter contains the only runtime and static assets. The reporting entry point supplies publishing instructions and the renderer setup; neither skill assumes a Clankers checkout. A missing companion is an installation problem to report, not a reason to create a second server.

Use a persisted, ignored state directory and source files. Verify ignoring with Git before starting. Keep one Markdown file and stable ID for each logical subject; several report IDs can exist simultaneously. Re-publishing an ID updates its title, Markdown snapshot and timestamp. Source edits alone do not change a published snapshot.

The server starts without `markdown-it-py` for steering. Rendering is optional and reports a clear dependency error when unavailable. With authorization for that named dependency, install it in a workspace venv and start/restart the existing server with that Python. Never add it to a consuming application's manifest solely for reports.

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

Follow the target repository's style; in Clankers reports, allow lines up to 120 characters. Never add a claim merely to fill the template. Short answers stay in chat. No Mermaid, remote fonts, CDN scripts or externally loaded images are needed.

## Delivery behavior

Delivery is the live Reports tab. The standalone HTML export was removed on 2026-09-20: it did not work in the Arena sandbox preview — attachment routes returned 200 with no visible download, and the exported file added a second copy that the native viewer showed as source. Keep the UTF-8 Markdown source as the durable artifact. Raw Markdown HTML is disabled. Tables are supported, but not every GitHub Markdown extension or syntax-highlighting theme.

A report may also carry fields: `- ( ) option` for one choice, `- [ ] option` for many, and `Label: ___` or a bare `___` line for text. The steering reference documents prompts, IDs and limits. Answers arrive as one inbox note headed `REPORT <id> <title>:`.

Open a served report and verify its content before claiming rendering succeeded. Do not claim the native file viewer renders Markdown because a file exists on disk.

## Previous workflow and future changes

The local-only `chore(reports): hold the local records` commit was formerly used to make raw Markdown visible in Arena's diff viewer. The current preview replaces that workaround: reports, messages and receipts remain ignored and uncommitted. This is an explicit 2026-09-20 owner decision, not a claim that the preview will always be available.

The former ntfy steering path and report-commit procedure are recorded in the companion's [migration reference](../../arena-preview-steering/references/REFERENCE.md) and in Git history. If the preview becomes unreliable, report what failed and agree on a new delivery method. Do not automatically resurrect either former workflow.
