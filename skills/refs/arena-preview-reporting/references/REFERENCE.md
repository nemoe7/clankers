# Portable reports

## Layout and ownership

Install `arena-preview-reporting` beside `arena-preview-steering`. The latter contains the only runtime and static assets. The reporting entry point supplies publishing instructions and the renderer setup; neither skill assumes a Clankers checkout. A missing companion is an installation problem to report, not a reason to create a second server.

Use a persisted, ignored state directory and source files. Verify ignoring with Git before starting. Keep one Markdown file and stable ID for each logical subject; several report IDs can exist simultaneously. Re-publishing an ID updates its title, Markdown snapshot and timestamp. Source edits alone do not change a published snapshot.

The server starts without `markdown-it-py` for steering. Rendering is optional and reports a clear dependency error when unavailable. With authorization for that named dependency, install it in a workspace venv and start/restart the existing server with that Python. Never add it to a consuming application's manifest solely for reports. A portable HTML export needs no Python environment to read.

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

## Export behavior

The agent's `export` subcommand writes a standalone HTML document with inline CSS and a dark/light toggle to a workspace path. Keep the UTF-8 Markdown source separately. Browser attachment routes returned 200 during the experiment but produced no visible download for the owner; the exact browser restriction is unconfirmed. The owner chose removal of browser download/source controls, not another fallback delivery mechanism. The document has no runtime API requests; linked destinations are not included. Raw Markdown HTML is disabled. Tables are supported, but not every GitHub Markdown extension or syntax-highlighting theme.

Open a served report and verify its content before claiming rendering succeeded. When using the native file viewer, verify whether it renders the exported HTML; if it shows source, say so and distinguish the working live rendering from reading the portable file in a browser. Do not claim the viewer can render Markdown based on a file existing on disk.

## Previous workflow and future changes

The local-only `chore(reports): hold the local records` commit was formerly used to make raw Markdown visible in Arena's diff viewer. The current preview replaces that workaround: reports, exports, messages and receipts remain ignored and uncommitted. This is an explicit 2026-09-20 owner decision, not a claim that the preview will always be available.

The former ntfy steering path and report-commit procedure are recorded in the companion's [migration reference](../../arena-preview-steering/references/REFERENCE.md) and in Git history. If the preview becomes unreliable, report what failed and agree on a new delivery method. Do not automatically resurrect either former workflow.
