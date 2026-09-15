# Workflows

Portable agent workflows. Each workflow is a self-contained Markdown file usable as-is across coding-agent platforms.

This directory currently holds no workflows. The format below is what a new workflow must meet, so the framework stays ready without shipping an entry that has no owner.

## Format

- A workflow is one Markdown file with YAML frontmatter carrying a `description` of what it does and when to use it.
- The workflow body MUST be portable: no platform-specific tools, agent names, models, providers, UI, permissions, or interaction mechanisms. Platform-specific activation stays in commented frontmatter hints.
- No hard-wrapped prose: one line per paragraph, list item, and table row, soft-wrapped by the editor.
- Workflow files have budgets tracked in the [root README](../README.md#instruction-budgets), measured in `cl100k_base` tokens; re-measure and update the table when changing them.

## Use

Copy a workflow file into your platform's workflow location, or run it as-is where the platform accepts a file path. Portability requirements are in the [rules specification](../rules/README.md#workflows).

Installation is human maintenance, not an agent task. Agents treat installed copies as read-only, reporting missing or incompatible files rather than installing or repairing them. Requested edits to workflow source in this repository do not authorize changes to an agent's installed copies.

Workflows are independent of the rule files in [rules/](../rules/) and usable on their own.
