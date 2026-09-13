# DAILIES.md

## Use

- A recurring automation prompt, not a rule file: an agent reads this file at run time, executes all five sections in one pass, and writes one report.
- The runtime is a ChatGPT scheduled monitoring task: it runs unattended, at most once a day, and also whenever the user asks for it. Web search, the GitHub connector (linked to the account this repository lives on), and the automation metadata are the tools; a terminal and local files exist only when the task decides it needs them, so never depend on them. The state between runs is the embedded datetime in this prompt, whose update lands on some runs and not others, and the automation metadata, which can itself be unreliable.
- These rules apply to every run, whether or not the run prompt repeats them.
- They outrank skill and plugin instructions, and on report shape they outrank the account's custom instructions and any saved memory; an explicit user instruction in the run prompt outranks this file, confirmed in one line.
- Sections 1 to 4 define what may enter the report; section 5 defines the only report a run may produce.
- This file is self-contained: a run needs no other file.
- Edit this file only when asked.
- simplified: covers the 11 software items in section 1 and the `nemoe7` repositories in sections 2 and 3; monitor something else by editing that section.

## Constitution

- Last completed run started (UTC+8, Asia/Manila): `2026-09-12 17:40:00`.
- Update that embedded datetime on EVERY RUN after the report is written, using this run's actual start time.
- Update it only at execution: an edit or a view of this prompt leaves it as it is.
- Keep the embedded datetime as the start time of the last run that completed, because the automation metadata can be unreliable.
- When the embedded datetime and `last_run` disagree, take the later as the window start and name the disagreement in Coverage.
- Emit actionable content only: omit a section, row, or item that carries no actionable change, recommendation, issue, or required action.
- NEVER include a no-change, unchanged, informational-only, or "no actionable change" entry; the Coverage section is the one exception.
- NEVER state a version, tag, date, or commit SHA that is not in content you fetched this run, and NEVER claim a check you did not run.
- On a change-based monitor, the first run establishes a baseline and does not report that baseline.
- Keep an ephemeral monitoring item until its purpose is complete or it is explicitly removed.
- Use the exact section names, order, table columns, and templates section 5 specifies.
- Output nothing when no section has an actionable change.

## Run state and evidence

- Read the automation metadata before monitoring: `last_run`, `next_run`, `updated`, `timezone`, `schedule`, `enabled`, `paused_count`, `completed_count`.
- The comparison window runs from the later of the embedded datetime and `last_run` to the current run time; report a change whose published, opened, or merged timestamp falls inside it.
- Derive the report date and every date you print from the metadata timestamps and `timezone` where they are available, converted to UTC+8 (Asia/Manila); NEVER infer the current date from memory.
- Treat a missing `last_run`, or a first run, as a baseline: record what you saw and report nothing from it.
- Treat a `last_run` older than `schedule`, or a risen `paused_count`, as missed windows: widen the window to `last_run` and name the gap in Coverage.
- When the metadata is not visible in the run, say so in Coverage and take the window start from the embedded datetime alone.
- Attempt the embedded-datetime update on every run; when the edit does not land, say so in Coverage and treat `last_run` as that run's record.
- A window re-covered because an update did not land may repeat an item already reported: report it again, since a missed release costs more than a duplicate.
- Route `nemoe7` repositories, private ones included, through the GitHub connector; route everything else through web search and the URLs in section 1.
- Cite in the Source or Evidence cell the URL or identifier you actually fetched for every version, tag, date, and SHA you report.
- Omit an item whose source you could not fetch, and name it in Coverage.
- Work the sections in the order 1, 4, 2, 3, so the expensive repository audit runs last; the report keeps the order section 5 specifies.
- When a section cannot be completed, output the sections you completed and name the gap in Coverage; NEVER fill a gap with inferred content.

## 1. Stable software updates

Monitor the official stable release channel of each item below, preferring its GitHub or GitLab releases page and falling back to the official channel.

| Software | Preferred source |
| --- | --- |
| Kilo Code | `https://github.com/Kilo-Org/kilocode/releases` |
| LiteLLM | `https://github.com/BerriAI/litellm/releases` |
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
- A Google Play listing pinned to `&hl=en` may corroborate a release date for either app; NEVER put a listing or a third-party tracker in the Source cell.

### Tracking a new item

- Add the item as one row in the table above, holding its name and the source URL you fetched to verify it exists.
- Prefer a GitHub or GitLab releases page; use the official changelog, patch-notes page, or vendor release feed when the project publishes none, and treat a store listing as date corroboration, never as a version source.
- Fetch the URL before adding it, and record the version or date it showed so the first run has a baseline rather than a gap.
- Say in the row what counts as a stable release for that item when its channel mixes stable releases with pre-releases.
- Mark a temporary item ephemeral in its row, so it is removed when its purpose is complete.
- Add a repository to section 3's scope only when it is a `nemoe7` repository; everything else stays in this table.
- Keep the item count in the `simplified:` line in `## Use` equal to the rows in the table.
- Remove a row only on an explicit instruction, and state in one line that the item is no longer tracked.

## 2. Wiki audit

- Inspect `nemoe7/wiki` and the public `nemoe7` repositories, not GitHub at large, for genuinely useful additions, updates, and removals.
- Treat only public repositories as wiki candidates.
- Report at most five recommendations per run, highest value first.
- Report recommendations only; NEVER modify the wiki.
- Write only `### Add` and `### Update/remove` under Wiki.
- Write the Add table with exactly these columns: `Repo | Section | Why | Docs`.

## 3. Repository audit

- Inspect every `nemoe7` GitHub repository for a pull request newly opened inside the comparison window.
- Treat a repository as active when it is not archived and shows meaningful activity in the last 90 days.
- Audit active repositories for actionable maintenance and quality issues.
- Audit private repositories too, for health and public-release readiness.
- For a private active repository with a meaningful implementation, a usable documented path, relevant docs, and no blocking CI, config, or security issue: recommend making it public and adding it to the wiki; NEVER make it public.
- For a public active repository, assess release and tag readiness.

### Release baseline

- MUST start by enumerating and reviewing the commit history from the release baseline to the current default branch HEAD.
- Use the latest release or tag that is an ancestor of the current default branch HEAD as that baseline.
- Take individual commits, diffs, and files as the primary basis.
- Use an aggregate diff, file list, changelog, or CI result only to verify or refine that basis.
- NEVER base release notes primarily on aggregate file counts or a generic final-tree summary.
- Account for every meaningful commit, grouping related commits that represent the same user-visible change.
- Where the connector cannot prove ancestry, CI state, or pull-request state, say so in the Evidence cell instead of inferring it.

### Release recommendation

- For every release or tag-ready recommendation, consult the repository documentation and its current state to choose a stable release or a pre-release.
- Recommend stable only when the project is sufficiently production-ready.
- Recommend pre-release when the project is usable but not yet production-ready.
- Recommend an initial release only when the project is sufficiently complete and usable.
- Write the release body on this exact template: `## Summary` holding 1 to 2 sentences, then the optional `## Features`, `## Improvements`, `## Bug Fixes`, `## Breaking Changes`, and `## Other`.
- Omit an empty body section.
- Put only verified baseline-to-HEAD changes and their supporting evidence in the body.
- Prefer user-visible changes over internals, and state a breaking change or migration explicitly.
- Reuse the body verbatim in the prefilled release-form URL and in the Repo Audit finding.

### Findings table

- Write exactly one combined Repo Audit table with these columns: `Repo | Priority | Finding | Evidence`.
- Express priority with circle emojis only.
- Rate a public release candidate Medium normally, and an optional or minor one Low.
- Rate an initial-release candidate Medium.
- Consolidate the findings of one repository into a single row whenever practical.
- Keep the public-release and branch findings inside that one table: no separate subsection for either.

### Branch audit

- Report a stale branch only after verifying it is fully merged or carries no unique changes.
- Report a branch ahead without an open pull request when it holds meaningful unique work or warrants review.
- Verify ancestry, the default branch, and pull-request state before reporting either.

## 4. LiteLLM tracked PR

- Track merged LiteLLM pull request #39157 by its final PR head commit `9e7cfee8d7cba55dbf11b61d2d2fdce94c70037e`.
- The tracked change is the router fallback fix: resolve fallbacks against the pre-routing tier selected by complexity or auto routing, select a fresh tier at each fallback hop, and handle an Anthropic safeguard-refusal fallback.
- Notify only when those final changes ship in an official stable LiteLLM release.
- A dev or pre-release inclusion does not count.
- Reference merge commit `59da6e75a50024dcca1af5efa90e4eec340b89b` when useful; it is not the tracked identifier.
- A material change is a new stable release containing the tracked commit, a revert of it, or an official statement that it will not ship.
- Once that change is reported, the item is complete: stop checking it and state in one line that it needs removal from this prompt.

## 5. Output

- Title the report `# Dailies — YYYY-MM-DD`, and write it only when something is actionable.
- Write the top-level sections exactly, in this order: `## 1. Updates`, `## 2. Wiki`, `## 3. Repo Audit`, `## 4. Watched`.
- Keep Updates to its compact table plus the `### <Software>` headings section 1 allows.
- Keep Wiki to `### Add` and `### Update/remove`, with the Add table `Repo | Section | Why | Docs`.
- Keep Repo Audit to its one combined table.
- Write Watched only for a material change in the LiteLLM status or a stable release, with exactly these columns: `Status | PR/Commit | Latest checked version | Evidence`.
- End every report with `## Coverage`, appended after `## 4. Watched` as the only permitted addition to that list: the sources and repositories you reached, the ones you did not with the reason, the sections you did not complete, and any question you could not ask with the assumption you proceeded on.
- Output nothing when no section has an actionable change; on a surface that cannot send an empty message, output exactly `# Dailies — YYYY-MM-DD — no actionable change` followed by `## Coverage`, and never let that line replace an empty output on a surface that can send one.

### Columns and legend

- `Ver.` is the release tag exactly as published, for example `v0.0.0`.
- `Source`, `Evidence`, and `Docs` are URLs or identifiers you fetched this run: a release URL, a compare URL, a commit SHA, a pull-request number.
- `Section` is the wiki section a recommendation targets, and `Why` is one sentence.
- `Latest checked version` is the newest stable LiteLLM release you inspected this run.
- `Status` names the change: `In pre-release`, `Shipped in stable`, or `Closed without shipping`.
- Priority takes a circle emoji only: 🔴 High for a finding that blocks use or exposes a secret, 🟠 Medium, 🟡 Low.
- The example rows below are shape only, and their values are placeholders to never report:
  - Updates: `| <Software> | v0.0.0 | https://example.invalid/releases/tag/v0.0.0 |`
  - Wiki Add: `| nemoe7/<repo> | <wiki section> | <one-sentence why> | https://example.invalid/<doc> |`
  - Repo Audit: `| nemoe7/<repo> | 🟠 | <finding and its baseline> | https://example.invalid/compare/v0.0.0...main |`
  - Watched: `| <status> | <tracked sha> | <version> | https://example.invalid/releases/tag/v0.0.0 |`

## When in doubt

- Smallest report that holds: include what a rule above requires, omit everything else, and stop.
- Where two sections collide, the more specific one wins; section 5 wins on report shape.
- When a fact is not in fetched content, leave the item out and name the gap in Coverage rather than improvise an entry.
- When that does not settle it, NEVER block the run on a question: record it in Coverage, proceed on the most reasonable assumption, and state it rather than improvise an entry.
