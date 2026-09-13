# DAILIES.md

## Use

- A recurring automation prompt, not a rule file: an agent reads this file at run time, executes all five sections in one pass, and writes one report.
- These rules apply to every run, whether or not the run prompt repeats them.
- They outrank skill and plugin instructions; an explicit user instruction in the run prompt outranks this file, confirmed in one line.
- Sections 1 to 4 define what may enter the report; section 5 defines the only report a run may produce.
- This file is self-contained: a run needs no other file.
- Edit this file only when asked.
- simplified: covers the 11 software items in section 1 and the `nemoe7` repositories in sections 2 and 3; monitor something else by editing that section.

## Constitution

- Current UTC+8 (Asia/Manila) datetime: `2026-09-12 17:40:00`.
- Update that embedded datetime on EVERY RUN before monitoring, using the actual current execution time.
- Update it only at execution: an edit or a view of this prompt leaves it as it is.
- Emit actionable content only: omit a section, row, or item that carries no actionable change, recommendation, issue, or required action.
- NEVER include a no-change, unchanged, informational-only, or "no actionable change" entry.
- On a change-based monitor, the first run establishes a baseline and does not report that baseline.
- Keep an ephemeral monitoring item until its purpose is complete or it is explicitly removed.
- Use the exact section names, order, table columns, and templates section 5 specifies.
- Output nothing when no section has an actionable change.

## 1. Stable software updates

Monitor the official stable release channel of each item below.

| Software | Preferred source |
| --- | --- |
| Kilo Code | GitHub Releases |
| LiteLLM | GitHub Releases |
| Tailscale | Changelog |
| zrok | GitHub Releases |
| MacroDroid | Google Play version history |
| Idle Obelisk Miner | Google Play version history |
| Bambuddy | GitHub Releases |
| Headroom | GitHub Releases |
| Open WebUI | GitHub Releases |
| Arena.ai | Product changelog |
| OpenGym | GitLab Releases |

- Report a release only when it is stable and newer than the previous check.
- Ignore commits, dev builds, nightlies, pre-releases, and tags without a stable release.
- Write the Updates table with exactly these columns: `Software | Ver. | Source`.
- Make `Source` a direct official link to the release.
- Give a meaningful feature update its own `### <Software>` heading below the table.

## 2. Wiki audit

- Inspect `nemoe7/wiki` and public GitHub repositories for genuinely useful additions, updates, and removals.
- Treat only public repositories as wiki candidates.
- Report recommendations only; NEVER modify the wiki.
- Write only `### Add` and `### Update/remove` under Wiki.
- Write the Add table with exactly these columns: `Repo | Section | Why | Docs`.

## 3. Repository audit

- Inspect every `nemoe7` GitHub repository for a pull request newly opened since the previous daily check.
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

## 5. Output

- Title the report `# Dailies — YYYY-MM-DD`, and write it only when something is actionable.
- Write the top-level sections exactly, in this order: `## 1. Updates`, `## 2. Wiki`, `## 3. Repo Audit`, `## 4. Watched`.
- Keep Updates to its compact table plus the `### <Software>` headings section 1 allows.
- Keep Wiki to `### Add` and `### Update/remove`, with the Add table `Repo | Section | Why | Docs`.
- Keep Repo Audit to its one combined table.
- Write Watched only for a material change in the LiteLLM status or a stable release, with exactly these columns: `Status | PR/Commit | Latest checked version | Evidence`.
- Output nothing when no section has an actionable change.

## When in doubt

- Smallest report that holds: include what a rule above requires, omit everything else, and stop.
- Where two sections collide, the more specific one wins; section 5 wins on report shape.
- When that does not settle it, stop and ask rather than improvise an entry.
