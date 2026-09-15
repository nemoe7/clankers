---
description: Initialize and reconcile repository documentation on the Diátaxis map, with user-selected templates

# agent: code # Uncomment for Kilo
# agent: build # Uncomment for OpenCode
# other platforms can use this workflow as-is
---

# Initialize Repository Documentation

Initialize or reconcile repository documentation from the repository and the user-selected templates.

The workflow MUST be portable across coding-agent platforms.

The workflow body MUST NOT depend on platform-specific tools, agent names, models, providers, UI, permissions, or interaction mechanisms.

Documentation is organized on the Diátaxis map ([diataxis.fr](https://diataxis.fr/)): tutorials, how-to guides, reference, and explanation, one page per reader need. When this workflow and that site disagree on a quadrant, the site wins.

## 1. Core Rules

- The repository is the primary source of truth.
- Existing valid documentation MUST be preserved.
- Existing authoritative documentation MUST NOT be duplicated.
- Organize documentation by reader need on the Diátaxis map: tutorials, how-to guides, reference, explanation.
- One page serves one need; quadrants link to each other instead of absorbing each other.
- Link to the authoritative location instead of duplicating it.
- Do not split documentation merely for organization.
- New documentation MUST only be created when a required baseline document, explicitly selected by the user, or necessary to reconcile an existing authoritative document.
- Technical documentation is the default.
- Business/product documentation MUST NOT be introduced unless explicitly requested.
- Do not invent facts, requirements, architecture, constraints, stakeholders, business goals, quality targets, or implementation details.
- Do not silently resolve material ambiguity.
- Do not rewrite documentation merely for style.
- Do not remove valid user content without justification.
- Do not create empty directories, including ADR directories.
- Do not unnecessarily renumber existing ADRs.
- Do not create duplicate sources of truth.
- Do not commit or push unless explicitly requested.

## 2. Execution Mode

Determine the execution mode before making changes.

### PLAN

PLAN mode MUST:

- inspect the repository;
- audit existing documentation;
- identify gaps, conflicts, duplication, and sources of truth;
- determine applicable templates;
- ask required questions;
- produce the proposed documentation set and changes.

PLAN mode MUST NOT:

- create files;
- modify files;
- delete files;
- rename files;
- commit;
- push.

### APPLY

APPLY mode MUST:

- perform the complete workflow;
- inspect the repository before editing;
- ask required questions;
- create or update the selected documentation;
- reconcile existing authoritative documentation instead of blindly replacing it;
- verify the result;
- report exactly what changed.

If the host agent has different planning/execution terminology, map these semantics to the closest equivalent.

## 3. User Interaction

When user input is required:

**ASK THE USER using the host agent's available user-interaction mechanism.**

When a material uncertainty blocks progress:

1. STOP the current action.
2. Identify the specific uncertainty.
3. ASK the minimum question necessary.
4. WAIT for the answer.
5. Apply the answer.
6. RESUME from the exact blocked point.

DO NOT restart the workflow.

DO NOT continue the blocked action using an assumption.

Minor editorial uncertainty does not require user interaction.

## 4. Repository Inspection

Inspect the repository before deciding what documentation is needed.

Inspect, where present:

- root structure;
- `README.md`;
- `AGENTS.md`;
- `CLAUDE.md`;
- `CONTEXT.md`;
- other agent instruction files;
- `docs/`;
- existing requirements and design documentation;
- existing ADRs;
- package and dependency manifests;
- build, test, lint, and format configuration;
- CI/CD configuration;
- deployment, container, and infrastructure configuration;
- API, CLI, and interface definitions;
- schemas and data models;
- configuration examples;
- relevant Git history when needed to establish intent, ownership, or decisions.

Determine only from evidence:

- repository identity;
- purpose;
- scope;
- existing capabilities;
- system boundaries;
- major components;
- interfaces;
- data and storage;
- runtime environment;
- deployment model;
- dependencies;
- constraints;
- established quality attributes;
- verification mechanisms;
- documentation conventions;
- sources of truth;
- existing architectural decisions.

DO NOT infer:

- business goals;
- product vision;
- market requirements;
- stakeholder identities;
- organizational requirements;
- unstated priorities;
- numeric quality targets;
- architectural decisions unsupported by evidence.

## 5. Documentation Audit

Audit each relevant documentation category before editing.

For each category determine:

- whether a document exists;
- whether it is applicable;
- whether it appears current;
- whether it is authoritative;
- which Diátaxis quadrant it serves, if any;
- whether equivalent information exists elsewhere;
- whether conflicting versions exist;
- whether it can safely be updated;
- where the canonical location is.

If authority or canonical location is unclear:

**STOP and ASK THE USER.**

Do not create another source of truth to avoid resolving the ambiguity.

## 6. Business/Product Gate

Business/product documentation is NOT part of the default documentation set.

ASK:

> SHOULD BUSINESS / PRODUCT DOCUMENTATION BE INCLUDED?

If **No**:

- skip all business/product documentation;
- do not create a business case;
- do not create stakeholder documentation;
- do not create a BRD;
- do not create product vision documentation.

If **Yes**, show the available templates for user selection:

- Vision;
- Business Case;
- Stakeholder Register;
- Stakeholder Analysis;
- Business Requirements Document;
- Product Requirements Document;
- Market Analysis;
- Business Process Documentation;
- Other explicitly requested business/product documentation.

Only create selected templates.

A Vision document MUST NOT be created unless business/product documentation is explicitly enabled and Vision is selected.

Do not infer business or product requirements from technical documentation.

## 7. Technical Template Selection

### Baseline

Always maintain in APPLY mode:

- `README.md`
- `AGENTS.md`

Baseline maintenance is NOT optional-template selection.

### Optional repository-level documents

- `CONTRIBUTING.md`
- `SECURITY.md`
- `CHANGELOG.md`

### Optional Diátaxis quadrants

- `docs/tutorials/` — learning-oriented lessons that teach by doing.
- `docs/how-to/` — goal-oriented guides that solve real reader problems.
- `docs/reference/` — austere technical description of the machinery.
- `docs/explanation/` — discursive treatment of why and context.

Scaffold quadrants only when the repository has content that needs them; an empty quadrant is never created.

### Optional formal specifications

- `docs/SRS.md`
- `docs/SDD.md`

Create these only when standards-aligned formal structure is explicitly required; quadrant documentation is the default, and formal specifications MUST NOT duplicate it — link instead.

### Optional ADRs

- `docs/adr/`

Show the optional templates for user selection.

Do not silently expand the selected set.

Existing equivalent documents MUST be reconciled rather than duplicated.

Architecture material splits by need: rationale, context, and decisions go to `docs/explanation/` with ADRs alongside; topology and component facts go to `docs/reference/`. No standalone architecture document unless the repository already keeps one worth preserving.

## 8. Default Layout

Use the repository's existing documentation layout when established.

Otherwise, the default structure is:

```text
repo/
├── README.md
├── AGENTS.md
├── CONTRIBUTING.md          # optional
├── SECURITY.md              # optional
├── CHANGELOG.md             # optional
└── docs/
    ├── tutorials/             # optional; only when lessons exist
    │   └── getting-started.md
    ├── how-to/                # optional
    ├── reference/             # optional
    │   └── api.md
    ├── explanation/           # optional
    ├── SRS.md                 # optional; formal track only
    ├── SDD.md                 # optional; formal track only
    └── adr/                   # optional; only when ADRs exist
        ├── 0001-title.md
        └── ...
```

Do not force this structure on a repository with an established equivalent.

Do not create empty quadrant directories.

Do not create `docs/adr/` until creating at least one ADR.

## 9. README.md

`README.md` is the primary repository orientation and usage document.

Maintain applicable information such as:

- project name;
- purpose;
- scope;
- capabilities;
- prerequisites;
- installation;
- configuration;
- usage;
- development setup;
- testing;
- deployment;
- relevant links.

Commands MUST be verified against the repository.

DO NOT invent commands.

DO NOT turn the README into the complete requirements, design, or architecture specification.

Link each quadrant from the README; DO NOT duplicate quadrant content into it.

## 10. AGENTS.md

`AGENTS.md` is the repository's agent operating guide, written to this skeleton: `Use` (scope, precedence over skills and plugins, user instructions outrank it), a constitution of one-line rules that must never be lost, one testable rule per line under domain headings with exact commands, and a `When in doubt` closer.

Maintain applicable information: repository structure; sources of truth; development, test, lint, and formatting commands; verification requirements; architecture boundaries; coding conventions; repository constraints; documentation rules; Git rules; and agent-specific operating requirements.

`AGENTS.md` MUST NOT replace `README.md`, `SRS.md`, `SDD.md`, architecture documentation, or ADRs. Keep instructions actionable and repository-specific.

## 11. Tutorials

Only create tutorials when selected.

A tutorial is a learning-oriented lesson: the reader completes meaningful work toward a goal and acquires skill along the way.

- State the goal up front: what the reader will build or achieve, and what they will encounter.
- Make every step produce a visible result, and state what the reader should see after each one.
- Keep the path meaningful, completable, logical, and complete over the tools and concepts the lesson must cover.
- Never explain beyond what the next step needs; link how-to, reference, and explanation out instead.

## 12. How-to Guides

Only create how-to guides when selected.

A how-to guide is goal-oriented directions through a real reader problem: deployment, operations, troubleshooting, development workflows.

- Write from the reader's problem, not from the machinery's motions; one guide answers one task the reader actually has.
- Give an adaptable logical sequence of actions the reader can check as they go; fork and rejoin where real problems demand it.
- Omit what the competent reader already knows; usability beats completeness.
- Never inline explanation or reference; link them out instead.

## 13. Reference

Only create reference material when selected.

Reference is austere technical description of the machinery: APIs, contracts, configuration, components, interfaces, errors.

- Describe neutrally and completely; no instruction, no explanation, no opinion.
- Mirror the structure of the product so reader and machinery stay aligned.
- Use standard patterns and exact forms: every command, flag, option, and error verbatim.
- Illustrate with examples that do not instruct; generate from the code where the repository supports it.

## 14. Explanation

Only create explanation when selected.

Explanation is discursive treatment that builds understanding: why things are so, context, decisions, trade-offs, alternatives.

- Open with the why-question the page answers, and bound the topic tightly; one page explores one area.
- Connect to other material freely, including outside the immediate topic, and weigh alternatives with reasons.
- Admit context, history, and opinion where they illuminate; this is the one quadrant where they belong.
- Never embed instruction or technical description; link how-to and reference out instead.

## 15. Software Requirements Specification

Only create or update an SRS when selected.

The SRS defines **WHAT the software must do**.

Use an **ISO/IEC/IEEE 29148:2018-aligned** structure.

Do not claim formal compliance unless explicitly established.

Include, as applicable:

### Introduction

- purpose;
- scope;
- references;
- definitions;
- acronyms and abbreviations.

### Overall Description

- product perspective;
- product functions;
- operating environment;
- constraints;
- assumptions;
- dependencies.

### External Interfaces

- user interfaces;
- external systems;
- APIs;
- hardware or infrastructure interfaces where applicable.

### Functional Requirements

Use stable identifiers:

```text
FR-001
FR-002
FR-003
```

Requirements SHOULD be specific, testable, unambiguous, and traceable.

### Quality Requirements

Use stable identifiers:

```text
NFR-001
NFR-002
NFR-003
```

Only document quality targets supported by evidence or explicitly provided by the user.

DO NOT invent numeric performance, availability, scalability, security, or usability targets.

If a material quality target is unknown:

**STOP and ASK THE USER.**

### Data Requirements

Document applicable:

- data;
- relationships;
- validation;
- persistence;
- retention.

### Constraints

Document established:

- technical constraints;
- platform constraints;
- compatibility constraints;
- regulatory or policy constraints.

### Assumptions and Dependencies

Only document established assumptions and dependencies.

### Verification

Describe how requirements can be verified.

### Requirements Traceability

Trace requirements to relevant design elements, tests, or authoritative artifacts where practical.

### Open Issues

Record unresolved requirements and decisions rather than inventing answers.

## 16. Software Design Description

Only create or update an SDD when selected.

The SDD defines **HOW the software is designed**.

Use an **IEEE 1016-2009-aligned** structure.

Do not claim active formal compliance or certification.

Include, as applicable:

### Identification and Scope

- system identity;
- design scope;
- design boundaries.

### Design Context

- external systems;
- operating context;
- relevant environmental assumptions.

### Design Viewpoints

Use only viewpoints relevant to the system, such as:

- context;
- composition;
- logical structure;
- dependencies;
- information;
- interfaces;
- interaction;
- state;
- deployment.

### Design Views

Use appropriate representations:

- Mermaid;
- UML;
- tables;
- structured text;
- diagrams.

Views MUST represent verified architecture rather than imagined architecture.

### Design Elements

Describe significant design elements and relationships.

Do not document every function or source file.

### Structural Design

Document:

- components;
- modules;
- responsibilities;
- dependencies;
- boundaries.

### Behavioral Design

Document:

- important workflows;
- state transitions;
- control flow;
- significant interactions.

### Data Design

Document:

- important entities;
- relationships;
- persistence;
- validation;
- ownership where established.

### Interface Design

Document:

- APIs;
- internal interfaces;
- external interfaces;
- protocols;
- important contracts.

### Deployment Design

Document:

- runtime components;
- hosting;
- infrastructure relationships;
- deployment boundaries.

### Design Constraints

Document established implementation constraints.

### Design Rationale

Document significant design reasoning where useful.

Do not turn routine implementation details into design rationale.

### Design Traceability

Connect important design elements to requirements or other authoritative artifacts where practical.

## 17. Architecture Decision Records

Only create ADRs when selected.

An ADR records **WHY a significant architectural or design decision was made**.

An SDD records **HOW the current design works**.

Do not use ADRs for:

- routine implementation details;
- minor configuration changes;
- every library choice;
- information already adequately captured by design documentation.

Use:

```text
docs/adr/
```

Create the directory only when creating at least one ADR.

Preserve existing numbering.

Do not unnecessarily renumber existing ADRs.

Use:

```md
# ADR-0001: Decision Title

## Status

## Context

## Decision

## Consequences
```

Do not create duplicate ADRs for decisions already documented authoritatively.

## 18. Security Documentation

Only create `SECURITY.md` when selected.

For repository-level security policy, use the repository root:

```text
SECURITY.md
```

Use it for applicable concerns such as:

- vulnerability reporting;
- supported versions;
- disclosure process;
- security-policy scope;
- established security contact information.

Technical security architecture belongs in technical documentation such as:

- `SDD.md`;
- reference or explanation material;
- other selected technical documents.

Do not invent security contacts or procedures.

Do not use `SECURITY.md` as a substitute for technical security architecture.

## 19. Template Reconciliation

For every selected template:

1. Locate existing equivalents.
2. Identify the apparent source of truth.
3. Determine the canonical location.
4. Compare existing content against the selected template.
5. Preserve valid material.
6. Identify missing material, duplication, and conflicts.
7. Update the authoritative document where appropriate.

If two plausible sources of truth conflict and authority is unclear:

**STOP and ASK THE USER.**

Do not silently merge contradictory information.

## 20. Content Reconciliation

When updating an existing document:

- preserve valid content, established terminology, stable identifiers, useful examples, working links, and repository conventions;
- add missing information only when supported;
- correct stale information when supported by current evidence;
- remove duplication only when authority is clear;
- avoid unnecessary reformatting.

Do not rewrite an entire document solely to make it resemble the selected template.

## 21. Cross-Document Consistency

After creating or updating all selected documents, check consistency across them.

Verify consistency of:

- project name;
- scope;
- terminology;
- functional requirements;
- quality requirements;
- architecture;
- components;
- interfaces;
- data models;
- deployment;
- configuration;
- commands;
- paths;
- links;
- requirement identifiers;
- ADR references;
- document status.

Documentation MUST NOT make contradictory claims.

Do not state:

- draft as final;
- proposed as accepted;
- planned as implemented;
- unverified as verified;
- intended behavior as current behavior;

unless supported by evidence.

## 22. Uncertainty Control

A material uncertainty includes:

- unknown user intent;
- ambiguous scope;
- conflicting requirements;
- conflicting documentation;
- unclear source of truth;
- unclear canonical location;
- unknown ownership;
- unknown requirements;
- unknown quality targets;
- ambiguous architecture;
- conflicting design interpretations;
- unclear template selection;
- any decision that could materially change the resulting documentation.

For any material uncertainty:

1. STOP.
2. Identify the exact uncertainty.
3. ASK the minimum necessary question.
4. WAIT.
5. Apply the answer.
6. RESUME from the exact blocked point.

DO NOT:

- guess;
- continue using a material assumption;
- hide uncertainty;
- substitute generic template content;
- restart the workflow after the answer.

## 23. Final Uncertainty Audit

Before finalizing, classify material statements as:

1. Verified directly from the repository.
2. Established elsewhere in the repository.
3. Explicitly provided by the user.
4. Clearly labeled inference.
5. A decision requiring user input.

For category 5:

**STOP and ASK THE USER.**

For category 4, if the inference materially affects the documentation:

**STOP and ASK THE USER.**

Do not leave material uncertainty disguised as fact.

## 24. Verification

In APPLY mode, verify the resulting documentation.

Verify, where applicable:

- referenced commands exist;
- referenced paths exist;
- referenced files exist;
- links resolve;
- configuration names are correct;
- APIs are correctly represented;
- components match the repository;
- deployment descriptions match the repository;
- diagrams match the documented architecture;
- requirement identifiers are unique and stable;
- traceability references are valid;
- standards references are correctly named;
- repository documentation conventions are followed;
- each page serves exactly one quadrant;
- quadrants link rather than duplicate.

Use repository-provided documentation validation, Markdown linting, link checking, or similar checks when available.

Do not run unrelated or unnecessarily expensive tests solely because documentation changed.

## 25. Idempotency

The workflow MUST be safe to run repeatedly.

On subsequent runs:

- preserve valid documentation;
- update stale documentation when supported;
- reconcile missing sections;
- do not create duplicate documents or ADRs;
- do not unnecessarily renumber ADRs;
- preserve stable requirement IDs;
- do not perform formatting-only rewrites;
- do not remove valid user content without justification;
- do not create empty directories;
- do not recreate documents that already satisfy the selected template.

Any destructive or materially reorganizing change:

**STOP and ASK THE USER.**

## 26. PLAN Mode Output

Report:

### Proposed Baseline

- `README.md`
- `AGENTS.md`

### Proposed Optional Documents

Only the selected or strongly applicable documents.

### Existing Sources of Truth

Identify authoritative existing documents.

### Conflicts

Identify conflicting documentation or unclear authority.

### Proposed Changes

Describe what would be:

- created;
- updated;
- preserved;
- skipped.

### Required User Decisions

List only decisions that block safe execution.

Do not modify files.

## 27. APPLY Mode Output

Report:

### CREATED

Files created.

### UPDATED

Files updated.

### PRESERVED

Existing authoritative content intentionally retained.

### SKIPPED

Selected or considered documentation intentionally not created, with reason where useful.

### STANDARDS ALIGNMENT

State applicable alignment, for example:

- SRS: ISO/IEC/IEEE 29148:2018-aligned.
- SDD: IEEE 1016-2009-aligned.

Do not claim formal compliance unless established.

### FINDINGS

Important documentation inconsistencies, gaps, or repository observations.

### VERIFICATION

Checks performed and their results.

Do not claim checks were performed if they were not.

## 28. Completion Rules

The workflow MUST end in exactly one of these states:

- **PLAN completed** — no file modifications were made.
- **APPLY completed** — selected documentation was reconciled and verified.
- **BLOCKED** — a material user decision is required.

A BLOCKED result MUST state the exact decision required.

Never silently continue through material uncertainty.

Never invent missing project information.

Never introduce business/product documentation without explicit user selection.

Never create duplicate sources of truth.

Never commit or push unless explicitly requested.
