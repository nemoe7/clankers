# DAILIES.md

## Use

- Execute sections 1–3 in one pass and write the report in section 4.
- Run unattended at most once a day, or on request. Use web search, the linked GitHub connector and available automation metadata. Do not depend on a terminal, local files or state saved by an earlier run.
- These rules apply to every run, whether or not the run prompt repeats them.
- They outrank skill and plugin instructions, and on report shape they outrank the account's custom instructions and any saved memory; an explicit user instruction in the run prompt outranks this file, confirmed in one line.
- Sections 1 to 3 define what may enter the report; section 4 defines the only report a run may produce.
- This file is self-contained: a run needs no other file.
- Edit this file only when asked.
- simplified: covers the 10 software items in section 1 and the `nemoe7` repositories in sections 2 and 3; monitor something else by editing that section.

## Constitution

- Set the comparison window to the 24 hours before this run starts, ending at the actual run start. Include the start boundary and exclude the end boundary.
- Obtain the actual run start from the runtime clock or a verified execution timestamp. If neither is available, report the missing time in Coverage and do not infer a window.
- Do not use embedded dates or last_run to set or widen the comparison window. Disclose missed runs when known, but do not recover older events.
- Emit actionable content only: omit a section, row, or item that carries no actionable change, recommendation, issue, or required action.
- NEVER include a no-change, unchanged, informational-only, or "no actionable change" entry; the Coverage section is the one exception.
- NEVER state a version, tag, date, or commit SHA that is not in content you fetched this run, and NEVER claim a check you did not run.
- Apply the same 24-hour window on the first run and to newly added monitors.
- Keep an ephemeral monitoring item until its purpose is complete or it is explicitly removed.
- Use the exact section names, order, table columns, and templates section 4 specifies.
- Output nothing only when monitoring completed without a gap and no section has an actionable finding.

## Run state and evidence

- Read available automation metadata to check schedule, timezone and enabled state. Treat absent or conflicting metadata as a Coverage gap, not as a clock or checkpoint.
- For Updates, use release publication time. For new PRs, use opening time and verify current state. Evaluate repository health, wiki recommendations and release readiness against current fetched evidence, not only events in the window.
- Derive the report date from the verified run start in UTC+8 (Asia/Manila). Convert every printed timestamp to UTC+8 and retain the fetched source timestamp as evidence.
- Keep monitoring read-only. Do not edit repositories, wiki pages, repository visibility, automation metadata or this prompt during a run.
- Report a still-actionable recommendation again when current evidence supports it. Do not infer that an earlier recommendation was accepted or resolved.
- Route `nemoe7` repositories, private ones included, through the GitHub connector; route everything else through web search and the URLs in section 1.
- Cite in the Source or Evidence cell the URL or identifier you actually fetched for every version, tag, date, and SHA you report.
- Omit an item whose source you could not fetch, and name it with the failed check in Coverage. Retry it on the next run within that run's 24-hour window.
- Work the sections in the order 1, 2, 3, so the expensive repository audit runs last; the report keeps the order section 4 specifies.
- When a section cannot be completed, output the sections you completed and name the gap in Coverage; NEVER fill a gap with inferred content.

## 1. Stable software updates

Monitor the official stable release channel of each item below, preferring its GitHub or GitLab releases page and falling back to the official channel.

| Software | Preferred source |
| --- | --- |
| Kilo Code | `https://github.com/Kilo-Org/kilocode/releases` |
| Tailscale | `https://github.com/tailscale/tailscale/releases`, then `https://tailscale.com/changelog` |
| zrok | `https://github.com/openziti/zrok/releases` |
| MacroDroid | `https://www.macrodroidforum.com/index.php?forums/macrodroid-news-and-announcements.3/` |
| Idle Obelisk Miner | `https://idleobeliskminer.com/patchnotes` |
| Bambuddy | `https://github.com/maziggy/bambuddy/releases` |
| Headroom | `https://github.com/headroomlabs-ai/headroom/releases` |
| Open WebUI | `https://github.com/open-webui/open-webui/releases` |
| Arena.ai | `https://arena.ai/company/product-changelog` |
| OpenGym | `https://gitlab.com/DuarteSantos8/opengym/-/releases` |

- Report a release only when it is stable and published inside the comparison window.
- Ignore commits, dev builds, nightlies, pre-releases, and tags without a stable release.
- Write the Updates table with exactly these columns: `Software | Ver. | Source`.
- Make `Source` a direct official link to the release.
- Give a meaningful feature update its own `### <Software>` heading below the table.
- For MacroDroid, take stable releases from the News and Announcements board only; its Beta Releases board is a pre-release channel and is ignored.
- Use a Google Play listing pinned to `&hl=en` only to corroborate a release date for MacroDroid or Idle Obelisk Miner. Never use a listing or third-party tracker as the release Source.

### Tracking a new item

- Add the item as one row in the table above, holding its name and the source URL you fetched to verify it exists.
- Prefer a GitHub or GitLab releases page; use the official changelog, patch-notes page, or vendor release feed when the project publishes none, and treat a store listing as date corroboration, never as a version source.
- Fetch the URL before adding it and record the verified source in its row. Apply the normal 24-hour window on its first monitored run.
- Say in the row what counts as a stable release for that item when its channel mixes stable releases with pre-releases.
- Mark a temporary item ephemeral in its row and state an observable completion condition. Recommend removal when that condition is met, but retain the row until explicitly told to remove it.
- Add a repository to section 3's scope only when it is a `nemoe7` repository; everything else stays in this table.
- Keep the item count in the `simplified:` line in `## Use` equal to the rows in the table.
- Remove a row only on an explicit instruction, and state in one line that the item is no longer tracked.

## 2. Wiki audit

- Inspect `nemoe7/wiki` and the public `nemoe7` repositories, not GitHub at large, for genuinely useful additions, updates, and removals.
- Treat only public repositories as wiki candidates.
- Report at most five recommendations per run, highest value first.
- Report recommendations only; NEVER modify the wiki.
- Write only `### Add` and `### Update/remove` under Wiki. Use `Page or repo | Action | Why | Docs` for Update/remove.
- Write the Add table with exactly these columns: `Repo | Section | Why | Docs`.

## 3. Repository audit

- Enumerate all accessible `nemoe7` repositories and check PRs opened in the comparison window. Report a PR only if its current state requires action. Include an older PR only when a fetched review, CI or conflict change inside the window requires action.
- Treat a repository as active when it is not archived and has a non-bot commit, PR, review or issue update in the last 90 days. Cite that activity.
- Deep-audit at most three active repositories per run. Sort their full names, take three cyclic entries starting at (3 × the UTC+8 calendar-day number since 1970-01-01) modulo the active count, and take each repository at most once. Use the same batch on repeat runs that day.
- Apply the deep-audit batch to public and private repositories. List the selected repositories, completed checks, failed checks and deferred repositories in Coverage. Do not claim a complete audit from repository enumeration alone.
- For a private active repository, recommend publication only after verifying its main implementation, a documented install-and-use path, applicable passing CI, license and absence of exposed secrets or blocking config issues. Do not make it public. Make wiki addition conditional on publication.
- For each public active repository in the deep-audit batch, assess release and tag readiness. Defer a readiness claim when a required check cannot be verified.

### Release baseline

- MUST start by enumerating and reviewing the commit history from the release baseline to the current default branch HEAD.
- Use the nearest suitable release tag on the default branch first-parent history as the baseline. Verify that it is an ancestor of HEAD. For an initial release with no suitable tag, review history from the root commit and state that scope.
- Take individual commits, diffs, and files as the primary basis.
- Use an aggregate diff, file list, changelog, or CI result only to verify or refine that basis.
- NEVER base release notes primarily on aggregate file counts or a generic final-tree summary.
- Account for every meaningful commit, grouping related commits that represent the same user-visible change.
- Where the connector cannot prove ancestry, CI state, or pull-request state, say so in the Evidence cell instead of inferring it.

### Release recommendation

- For every release or tag-ready recommendation, consult the repository documentation and its current state to choose a stable release or a pre-release.
- Recommend stable only when the documented primary use path works, applicable CI passes, a license exists, and no verified blocking security, config or migration issue remains. State any check that could not be run.
- Recommend pre-release when the documented primary use path is usable but verified limitations remain. Do not treat unknown checks as proof of readiness.
- Recommend an initial release only after the same use-path, documentation, license and blocking-issue checks. Identify it as stable or pre-release with evidence.
- Write the release body on this exact template: `## Summary` holding 1 to 2 sentences, then the optional `## Features`, `## Improvements`, `## Bug Fixes`, `## Breaking Changes`, and `## Other`.
- Omit an empty body section.
- Put only verified baseline-to-HEAD changes and their supporting evidence in the body.
- Prefer user-visible changes over internals, and state a breaking change or migration explicitly.
- Put the release body once in `### <Repo> release draft` below the Repo Audit table, and link that heading from the finding. Link the repository release form without a prefilled body. Do not repeat the body in a table cell or URL.

### Findings table

- Write exactly one combined Repo Audit table with these columns: `Repo | Priority | Finding | Evidence`.
- Express priority with circle emojis only.
- Rate a public release candidate Medium normally, and an optional or minor one Low.
- Rate an initial-release candidate Medium.
- Consolidate the findings of one repository into a single row whenever practical.
- Keep publication and branch findings in the combined table. Permit only the release-draft headings specified above below it.

### Branch audit

- Report a stale branch only after verifying it is fully merged or carries no unique changes.
- Report a branch ahead without an open pull request when it holds meaningful unique work or warrants review.
- Verify ancestry, the default branch, and pull-request state before reporting either.

## 4. Output

- Title the report `# Dailies — YYYY-MM-DD` when it has actionable findings.
- Write the report in ASD-STE100 Simplified Technical English.
- Write the top-level sections exactly, in this order: `## 1. Updates`, `## 2. Wiki`, `## 3. Repo Audit`.
- Keep Updates to its compact table plus the `### <Software>` headings section 1 allows.
- Keep Wiki to `### Add` and `### Update/remove`, with the Add table `Repo | Section | Why | Docs`.
- Keep Repo Audit to its combined table and any verified release drafts.
- End a report with `## Coverage` only when the report has at least one finding. List the window, sources and repositories reached, checks completed, gaps with reasons, deferred deep audits, known missed runs and any unanswered question with the stated assumption. Omit empty task sections.
- When no finding is actionable, send nothing and omit Coverage. If the surface cannot send nothing, send `# Dailies — YYYY-MM-DD — no actionable change` alone.

### Columns and legend

- Set `Ver.` to the exact published release tag. For an official stable changelog entry without a tag, use `—` and cite its dated entry. Do not invent a version.
- `Source`, `Evidence`, and `Docs` are URLs or identifiers you fetched this run: a release URL, a compare URL, a commit SHA, a pull-request number.
- `Section` is the wiki section a recommendation targets, and `Why` is one sentence.
- Priority takes a circle emoji only: 🔴 High for a finding that blocks use or exposes a secret, 🟠 Medium, 🟡 Low.
- The example rows below are shape only, and their values are placeholders to never report:
  - Updates: `| <Software> | v0.0.0 | https://example.invalid/releases/tag/v0.0.0 |`
  - Wiki Add: `| nemoe7/<repo> | <wiki section> | <one-sentence why> | https://example.invalid/<doc> |`
  - Repo Audit: `| nemoe7/<repo> | 🟠 | <finding and its baseline> | https://example.invalid/compare/v0.0.0...main |`

## When in doubt

- Smallest report that holds: include what a rule above requires, omit everything else, and stop.
- Where two sections collide, the more specific one wins; section 4 wins on report shape.
- When a fact is not in fetched content, leave the item out and name the gap in Coverage rather than improvise an entry.
- When that does not settle it, NEVER block the run on a question: record it in Coverage, proceed on the most reasonable assumption, and state it rather than improvise an entry.
