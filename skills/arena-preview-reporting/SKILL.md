---
name: arena-preview-reporting
description: Publish readable Markdown reports in Arena.ai's live preview, with a Reports tab, multiple named reports, stable updates and answerable fields written as Markdown checkboxes, choices and blanks. Use for longer reports or requested report artifacts in Arena Agent Mode; keep short reports in chat. Reuses the sibling arena-preview-steering server, never a second server or duplicated runtime.
license: MIT
compatibility: Arena.ai Agent Mode, Python 3.10+, markdown-it-py and the sibling arena-preview-steering skill.
metadata:
  origin: first-party, maintained in this repository
  version: "1.0.0"
  arena-only: "true"
---

# Arena Preview Reporting

Two procedures, one runtime: [arena-preview-steering](../arena-preview-steering/SKILL.md) owns the server and inbox. This skill publishes reports there. User instructions and repository rules win; short reports stay in chat.

## Setup

Resolve `../arena-preview-steering/scripts/preview.py` relative to this skill; never assume the consuming repository's layout. Report missing skill files; never self-install them. Reuse the session's server, state directory and port; if absent, follow the companion's setup using Arena's long-lived process tool. Never add a server per report.

`markdown-it-py` is preauthorized for this skill. Reuse an environment with it; else install in a workspace venv without asking:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install markdown-it-py
```

On Windows Command Prompt, use `.venv\Scripts\python.exe` for that venv. Never overwrite a venv; reuse it or choose another workspace venv. Restart the shared server with the venv's Python when needed. Keep skill-only packages out of app manifests and generated `requirements.txt` unless the app independently needs them. Never vendor a parser or load CDNs/remote fonts/styles. Report install failures: steering CLI commands and Markdown sources remain usable, rendering unavailable. Venvs/packages may need restoring after sandbox restarts.

## Publish and update

1. Write a UTF-8 `.md` source in an ignored, persisted workspace directory. Keep/update one source per subject; mark resolved findings. Subjects may coexist. Include changes/findings, checks actually run and their results, decisions, unresolved issues and limitations; review code and documentation critically. Follow repository report style, including Clankers' 120-character line allowance.
2. Publish with a stable ID and meaningful title:

   ```bash
   python <steering-skill>/scripts/preview.py --state-dir reports/arena-preview publish reports/review.md --id review --title "Review"
   ```

   IDs: 1–80 letters, digits, hyphens or underscores. Titles: 1–200 characters. Sources: UTF-8 `.md`, at most 2 MB; split oversized reports by subject. Publishing snapshots sources: **republish the same ID after each source update**. Another ID adds a report, never replaces the first.
3. Direct the user to the **Reports** tab and titled selector. Updating a report preserves selection; switching tabs or refreshing must not replace drafts or message history. Publishing never acknowledges steering notes. Verify the rendered endpoint; do not claim the native file viewer renders Markdown.

Raw Markdown HTML is disabled. Headings, emphasis, lists, tables, quotations, code fences and links render; remote assets are blocked. No full GFM extension set or syntax highlighter.

## Fields and answers

- ALWAYS pair each option set with a labeled custom-response field, e.g. `Custom response: ___`.

A report source may carry live inputs, written as Markdown:

| Marker | Control |
| --- | --- |
| `- ( ) option` lines, `(x)` preselects | Radio group |
| `- [ ] option` lines, `[x]` preselects | Checkbox group |
| `Label: ___`, or a bare `___` line | Text box, at most 2000 characters |

The prompt is the label, else the nearest text line above; `{#id}` ending that line fixes the field ID. Markers in fenced code stay literal. The Reports tab shows one Send answers button under the report; answers reach the steering inbox as one note headed `REPORT <id> <title>:`, read and `ACK:`-ed like any note. Use fields when a questionnaire needs prose around it, and field-only Markdown reports for a bare questionnaire. Republishing replaces documents, never delivered answers.

## Delivery and retention

Delivery is the live Reports tab. Browser download/source controls and the former standalone HTML export are gone: attachment responses returned HTTP 200 but no download appeared in the Arena sandbox preview, and the export added a second copy the file viewer did not render. Keep the Markdown source as the durable artifact; direct the user to the rendered report and verify it. Never silently restore attachment links or an export command.

Keep Markdown sources, session databases, inboxes and receipts **ignored and uncommitted; never push them**. This replaces the former local-only report commits used to expose raw Markdown in Arena's diff viewer. Channel permanence is not guaranteed: report preview failure and agree on a replacement, never silently reinstate the old workaround. See [report format and recovery](references/REFERENCE.md).

Keep production free of these skill names/paths; their own files and setup chat are exceptions.

Non-fragment Markdown links open new tabs with `noopener noreferrer`, keeping the preview in place. Browser popup policy can restrict new tabs.
