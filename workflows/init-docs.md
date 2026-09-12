---
description: Initialize and reconcile repository documentation with user-selected templates

# agent: code # Uncomment for Kilo
# agent: build # Uncomment for OpenCode
# other platforms can use this workflow as-is
---

# Initialize Repository Documentation

Initialize or reconcile repository documentation from the repository and the user-selected templates.

The workflow MUST be portable across coding-agent platforms.

The workflow body MUST NOT depend on platform-specific tools, agent names, models, providers, UI, permissions, or interaction mechanisms.

## 1. Core Rules

- The repository is the primary source of truth.
- Existing valid documentation MUST be preserved.
- Existing authoritative documentation MUST NOT be duplicated.
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

### Optional technical documents

- `docs/SRS.md`
- `docs/SDD.md`
- `docs/architecture.md`
- `docs/api.md`
- `docs/configuration.md`
- `docs/development.md`
- `docs/deployment.md`
- `docs/operations.md`
- `docs/troubleshooting.md`

### Optional ADRs

- `docs/adr/`

Show the optional technical templates for user selection.

Do not silently expand the selected set.

Existing equivalent documents MUST be reconciled rather than duplicated.

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
    ├── SRS.md               # optional
    ├── SDD.md               # optional
    ├── architecture.md      # optional
    ├── api.md               # optional
    ├── configuration.md     # optional
    ├── development.md       # optional
    ├── deployment.md        # optional
    ├── operations.md        # optional
    ├── troubleshooting.md   # optional
    └── adr/                 # optional; only when ADRs exist
        ├── 0001-title.md
        └── ...
```

Do not force this structure on a repository with an established equivalent.

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

## 10. AGENTS.md

`AGENTS.md` is the repository's agent operating guide, written to this skeleton: `Use` (scope, precedence over skills and plugins, user instructions outrank it), a constitution of one-line rules that must never be lost, one testable rule per line under domain headings with exact commands, and a `When in doubt` closer.

Maintain applicable information: repository structure; sources of truth; development, test, lint, and formatting commands; verification requirements; architecture boundaries; coding conventions; repository constraints; documentation rules; Git rules; and agent-specific operating requirements.

`AGENTS.md` MUST NOT replace `README.md`, `SRS.md`, `SDD.md`, architecture documentation, or ADRs. Keep instructions actionable and repository-specific.

## 11. Software Requirements Specification

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

### Traceability

Trace requirements to relevant design elements, tests, or authoritative artifacts where practical.

### Open Issues

Record unresolved requirements and decisions rather than inventing answers.

## 12. Software Design Description

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

### Traceability

Connect important design elements to requirements or other authoritative artifacts where practical.

## 13. Architecture Documentation

Only create `docs/architecture.md` when selected.

Architecture documentation provides the high-level architectural view.

When both architecture documentation and an SDD exist:

- `architecture.md` = high-level architectural overview;
- `SDD.md` = detailed software design.

Avoid duplicating entire sections.

Focus on:

- system boundaries;
- major components;
- important dependencies;
- major interfaces;
- runtime/deployment topology;
- architectural constraints;
- significant architectural decisions.

## 14. Architecture Decision Records

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

## 15. Security Documentation

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
- `architecture.md`;
- other selected technical documents.

Do not invent security contacts or procedures.

Do not use `SECURITY.md` as a substitute for technical security architecture.

## 16. Supporting Technical Documentation

Only create supporting documents when selected and each has a clear purpose.

### `docs/api.md`

Document applicable APIs, interfaces, contracts, authentication, errors, and examples.

### `docs/configuration.md`

Document supported configuration, defaults, environment variables, files, and behavior.

### `docs/development.md`

Document development setup, workflows, commands, and repository-specific practices.

### `docs/deployment.md`

Document build, packaging, deployment, runtime requirements, configuration, and rollback considerations where established.

### `docs/operations.md`

Document applicable operational procedures, monitoring, maintenance, backups, recovery, and administration.

### `docs/troubleshooting.md`

Document verified symptoms, causes, diagnostics, and resolutions.

Do not split documentation merely for organization.

If information already has an authoritative location, link to it instead of duplicating it.

## 17. Template Reconciliation

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

## 18. Content Reconciliation

When updating an existing document:

- preserve valid content, established terminology, stable identifiers, useful examples, working links, and repository conventions;
- add missing information only when supported;
- correct stale information when supported by current evidence;
- remove duplication only when authority is clear;
- avoid unnecessary reformatting.

Do not rewrite an entire document solely to make it resemble the selected template.

## 19. Cross-Document Consistency

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

## 20. Uncertainty Control

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

## 21. Final Uncertainty Audit

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

## 22. Verification

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
- repository documentation conventions are followed.

Use repository-provided documentation validation, Markdown linting, link checking, or similar checks when available.

Do not run unrelated or unnecessarily expensive tests solely because documentation changed.

## 23. Idempotency

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

## 24. PLAN Mode Output

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

## 25. APPLY Mode Output

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

## 26. Completion Rules

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
