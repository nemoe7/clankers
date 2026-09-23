---
name: arena-preview-reporting
description: Publish readable Markdown reports in Arena.ai's live preview with a Reports tab, multiple named reports and answerable fields. Use for longer reports or requested report artifacts; keep short reports in chat. Reuses the arena-preview-steering runtime, never a second server. NEVER USE THIS SKILL OUTSIDE OF ARENA.AI.
license: MIT
compatibility: Arena.ai Agent Mode, Python 3.10+, the sibling arena-preview-steering skill, markdown-it-py in a workspace venv.
metadata:
  origin: first-party, maintained in this repository
  arena-only: "true"
---

# Arena Preview Reporting

## Purpose

Use only in Arena.ai Agent Mode for reports that need readable rendered Markdown, multiple report documents or answerable fields inside a report. Short reports that fit in chat stay in chat; do not start a report pipeline for them. The companion arena-preview-steering skill must be present as a sibling and owns the shared Python server and interface. This skill adds a publishing procedure, not a second server or a duplicate runtime. Report missing installed skill files to the user instead of installing them without authorization.

## Runtime and dependencies

Resolve ../arena-preview-steering/scripts/preview.py relative to this skill. Use the existing session's --state-dir and port. If the server is not running, follow the companion skill's setup and start it with Arena's long-lived process tool. Do not start a second server for another report.

Python 3.10+ is required. Installing markdown-it-py for this skill is preauthorized. Reuse a Python environment containing markdown-it-py when one is already present. If it is missing, always install markdown-it-py in a workspace virtual environment without asking for approval. Reuse an existing virtual environment or create one when needed. Keep skill-only dependencies out of application manifests and generated requirements.txt files unless the application independently needs them. Start or restart the shared server using that environment's Python. Do not vendor a parser or use CDNs, remote fonts or remote stylesheets. If installation fails, report the error: steering CLI commands and Markdown source access still work, but do not claim rendered reports work. Cached dependencies and virtual environments do not survive every sandbox restart.

## Reports

Write each report as a UTF-8 Markdown source file under an ignored, persisted workspace directory. Keep one report per logical subject and update its source in place, marking findings resolved when appropriate. Several different subjects can coexist; do not overwrite one report to publish another. Report changes, findings, checks and actual results, decisions, unresolved issues and limitations, and criticize the code and documentation as required by repository rules. Never claim an unrun check. In the Clankers convention, allow lines up to 120 characters.

Publish with the shared runtime's publish command, giving the source path, a stable report ID and a meaningful title. The runtime stores a snapshot; editing a source file alone does not update the preview, so republish with the same ID after every source update. IDs contain 1–80 letters, digits, hyphens or underscores. Titles contain 1–200 characters. Each source must be .md, UTF-8 and at most 2 MB; split an oversized report by subject. The server renders Markdown with raw HTML disabled and displays tables, lists, quotations, code fences, links and emphasis. Images and other remote resources are not fetched by the page. The preview does not provide a full GFM extension set or syntax highlighting.

Delivery is the live Reports tab. Keep the Markdown source as the durable artifact and direct the user to the rendered report. Tell the user which report to select and verify its actual rendered endpoint, rather than claiming that a Markdown source in the file viewer was rendered. Publishing reports never acknowledges pending steering messages. Mermaid is never rendered; do not use it in reports.

## Fields and answers

- ALWAYS include a labeled custom-response text field with each option set so the user can answer outside the listed options. Use `Custom response: ___` in Markdown reports.

A report source may contain form fields written as Markdown: a `- ( ) option` list becomes a radio group, a `- [ ] option` list becomes a checkbox group, and `Label: ___` or a bare `___` line becomes a text box. `(x)` and `[x]` preselect an option. The prompt is the label, else the nearest text line above the field, and `{#id}` at the end of that line fixes the field ID. Markers inside fenced code blocks stay literal. The Reports tab renders one Send answers button under the whole report, and the answers arrive in the steering inbox as one note headed `REPORT <id> <title>:`, which the agent reads and acknowledges like any note. Use this when a questionnaire needs explanation around it; use field-only Markdown reports for a bare questionnaire. Keep one report per subject: republishing replaces the rendered document, not the answers already delivered.

## Delivery and retention

Do not commit or push report sources, session databases, inboxes or receipts. Report sources remain in ignored workspace files. The current preview channel may change; failures require an explicit user decision, not silent fallback or a new permanent guarantee.

Explicit user instructions and repository rules outrank skill defaults. Keep production code free of references to these skills; the skill's own files and setup chat are exceptions.

Non-fragment Markdown links open in a new tab with `noopener noreferrer`, keeping the preview in place. Browser popup policy can still restrict new tabs. See [portable reports](references/REFERENCE.md) for structure and delivery detail.
