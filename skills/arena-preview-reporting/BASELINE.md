# Arena Preview Reporting — baseline

This is the full-wording source of the entry point. It stays in the source repository and is not distributed.

## Purpose

Use only in Arena.ai Agent Mode for reports that need readable rendered Markdown, multiple report documents or a portable HTML deliverable. Short reports that fit in chat stay in chat; do not start a report pipeline for them. The companion arena-preview-steering skill must be present as a sibling and owns the shared Python server and interface. This skill adds a publishing procedure, not a second server or a duplicate runtime. Report missing installed skill files to the user instead of installing them without authorization.

## Runtime and dependencies

Resolve ../arena-preview-steering/scripts/preview.py relative to this skill. Use the existing session's --state-dir and port. If the server is not running, follow the companion skill's setup and start it with Arena's long-lived process tool. Do not start a second server for another report.

Python 3.10+ is required. Reuse a Python environment containing markdown-it-py when one is already present. Otherwise, after the current task or repository policy authorizes this named rendering dependency, create a workspace virtual environment and install markdown-it-py there. Never change the application's dependency manifest for preview rendering. Restart the shared server using that environment's Python if it was started without the renderer. Do not vendor a parser or use CDNs, remote fonts or remote stylesheets. If installation fails, report the error: steering and Markdown source access still work, but do not claim rendered reports work. Cached dependencies and virtual environments do not survive every sandbox restart.

## Reports

Write each report as a UTF-8 Markdown source file under an ignored, persisted workspace directory. Keep one report per logical subject and update its source in place, marking findings resolved when appropriate. Several different subjects can coexist; do not overwrite one report to publish another. Report changes, findings, checks and actual results, decisions, unresolved issues and limitations, and criticize the code and documentation as required by repository rules. Never claim an unrun check. In the Clankers convention, allow lines up to 120 characters.

Publish with the shared runtime's publish command, giving the source path, a stable report ID and a meaningful title. The runtime stores a snapshot; editing a source file alone does not update the preview, so republish with the same ID after every source update. IDs contain 1–80 letters, digits, hyphens or underscores. Titles contain 1–200 characters. Each source must be .md, UTF-8 and at most 2 MB; split an oversized report by subject. The server renders Markdown with raw HTML disabled and displays tables, lists, quotations, code fences, links and emphasis. Images and other remote resources are not fetched by the page. The preview does not provide a full GFM extension set or syntax highlighting.

Use the clickable Reports tab and report selector. The selection stays stable when a report is updated. Notes, drafts and message history stay intact while switching views or refreshing a report. Publishing reports never acknowledges pending steering messages. Tell the user which report to select and verify its actual rendered endpoint, rather than claiming that a Markdown source in the file viewer was rendered.

## Portable delivery and retention

The Reports tab renders reports but has no browser download/source controls: attachment responses returned HTTP 200 yet silently failed for the owner, so those controls were removed by explicit choice. The exact browser restriction is unconfirmed. The shared runtime's export command writes self-contained HTML to an ignored workspace file; keep the Markdown source separately. HTML contains its own stylesheet and a dark/light toggle; recipients need only a browser, not the server, repository, Python or markdown-it-py. Links may still require their destinations; offline portability does not package linked documents. If presenting the exported artifact, open that HTML file with the file-viewer tool, and report honestly if the viewer shows source text rather than rendering it; the HTML file can be opened in a browser. Do not restore the unreliable attachment links silently.

Do not commit or push report sources, HTML exports, session databases, inboxes or receipts. Source reports and exports remain in ignored workspace files. This replaces the previous local-only report-commit workaround, which existed because Arena's native viewer exposed raw Markdown only after local commits. The historical workflow is documented in the companion's references/REFERENCE.md and the changelog. The current preview channel may change; failures require an explicit user decision, not silent fallback or a new permanent guarantee.

Explicit user instructions and repository rules outrank skill defaults. Keep production code free of references to these skills; the skill's own files and setup chat are exceptions.

Non-fragment Markdown links open in a new tab with `noopener noreferrer`, keeping the preview in place. Browser popup policy can still restrict new tabs.
