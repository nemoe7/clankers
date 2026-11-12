# Rules specification

Human reference for rule structure, platform differences, and local installation. See [maintenance/README.md](../maintenance/README.md) for repo maintenance procedures. This document is human documentation, not a deployed rule file.

Commands and code-span paths are repository-root-relative unless stated otherwise.

The installer uses only the Python standard library.

## Contents

| File or directory | Purpose |
| --- | --- |
| [rules/CORE.md](CORE.md) | Generic core rules |
| [rules/KILO.md](KILO.md) | Kilo Code overlay |
| [rules/ARENA.md](ARENA.md) | Self-contained Arena rules, optimized for file size |
| [rules/CHATGPT-CUSTOM.txt](CHATGPT-CUSTOM.txt) | ChatGPT Personalization: `Custom Instructions` |
| [rules/CHATGPT-MORE.txt](CHATGPT-MORE.txt) | ChatGPT Personalization: `More about you` |
| [rules/COMMIT-SPEC.txt](COMMIT-SPEC.txt) | Short commit-message reference |
| [rules/refs/](refs/README.md) | Uncompressed rule originals and the AGENTS.md writing guidelines |

Active rule loading depends on the installed agent host rather than filenames alone. Verify that CORE.md remains active in your host configuration after upgrades.

CORE.md provides the shared base rules, and platform overlays add host-specific rules beside it.

- ARENA.md bundles a compressed standalone copy of the core rules for Arena sessions.
- Cline and Kilo load the project AGENTS.md alongside their configured platform overlays.

## Core rules summary

- Human-facing prose follows ASD-STE100 and plain-word rules.
- Responses and docs stay terse and unambiguous.
- Material ambiguity triggers clarifying questions before implementation.
- Engineering choices follow YAGNI, KISS, and DRY.
- Behavior changes include tests without weakening existing assertions.
- Workstation agents branch from `main` and push only on request.

## Platform difference matrix

Platform constraints shape three distinct rule surfaces, and each row summarizes where their rules diverge.

<!-- markdownlint-disable MD033 -->

| Domain | Agents | Arena | ChatGPT |
| --- | --- | --- | --- |
| Git/Hub | <ul><li>Pushes only when asked. </li><li>Branches from main. </li></ul> | <ul><li>Pushes commits and keeps a PR open. </li><li>Uses rebase merges without merging PRs itself. </li><li>Lists planned files before committing. </li><li>Requests GitHub reconnect after one auth retry. </li><li>Watches PR checks and reports CI before turn end. </li></ul> | <ul><li>Opens a PR and uses rebase merges. </li><li>Polls checks to completion before turn end. </li><li>Uses one atomic commit with a planned file list. </li></ul> |
| Questions | Uses the host question tool instead of plain text. | Uses fielded Steering reports instead of plain text. | — |
| Changelogs | Follows Keep a Changelog unless the repo defines another format. | Follows Keep a Changelog unless the repo defines another format. | — |
| Mermaid Diagrams | Uses phone-sized Mermaid where rendered. | Restricts Mermaid to docs, omitting it in chat. | Uses Mermaid for pipelines and flows where rendered instead of ASCII. |
| Recommendation | Marks a recommended choice when offering three or more options. | Marks a recommended choice when offering three or more options. | — |
| Platform Specific | <ul><li>Checks the active shell first. </li></ul> | <ul><li>Opens the first reply with a 10-4 confirmation. </li><li>Runs the Steering preview server, task queue, and fielded reports. </li><li>Works smallest unblocked tasks first until the queue clears. </li><li>Protects rule and Steering files unless waived. </li></ul> | <ul><li>Uses extended thinking by default. </li></ul> |

<!-- markdownlint-enable MD033 -->

## Markdown lint scope

Run `npx --yes markdownlint-cli2` from the repo root. `.markdownlint-cli2.jsonc` defines the scope.
