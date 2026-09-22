# Workflows

Each workflow is a self-contained Markdown file usable as-is across coding-agent platforms.

Contents:

- [init-docs](init-docs.md) — bootstrap and reconcile repository documentation for downstream users and agents.

## Format

- One Markdown file with YAML frontmatter: `description` states its action and when to use it.
- The body MUST stay portable: no platform-specific tools, agent names, models, providers, UI, permissions, or interaction mechanisms. Platform-specific activation stays in commented frontmatter hints.
- No hard-wrapped prose: one line per paragraph, list item, and table row, soft-wrapped by the editor.
- The [root README](../README.md#instruction-budgets) tracks workflow budgets in `cl100k_base` tokens. Re-measure and update it after every change.

## Use

Copy a workflow file into your platform's workflow location, or run it as-is where the platform accepts a file path. Portability requirements are in the [rules specification](../rules/README.md#workflows).

Installation is human maintenance. Agents treat installed copies as read-only and report missing or incompatible files, never install or repair them. Source edits here do not authorize installed-copy changes.

Workflows stand alone, independent of the rule files in [rules/](../rules/).
