---
description: Bootstrap and reconcile repository documentation for downstream users and agents

# agent: code # Uncomment for Kilo
# agent: build # Uncomment for OpenCode
# other platforms can use this workflow as-is
---

# Repository Documentation

Build repository documentation for two audiences: downstream users who consume the repo, and agents that work in it. Human-only repos skip the agent layer; the workflow adapts.

The workflow MUST be portable across coding-agent platforms. The body MUST NOT depend on platform-specific tools, agent names, models, providers, UI, permissions, or interaction mechanisms.

Quadrant rules follow Diátaxis ([diataxis.fr](https://diataxis.fr/), aligned 2026-09); on conflict this file governs.

Read by task: bootstrapping an empty repo — Core Rules through Bootstrap, then the Catalog. Adding one document — the Catalog for whether it is warranted, then that document's section. Reconciling existing docs — Inspection, Audit, then Reconciliation through Verification. Full pass — straight through.

## 1. Core Rules

- The repository is the primary source of truth.
- Serve two audiences: downstream users who consume the repo, and agents that work in it.
- The client chooses what gets built: propose, let them pick, confirm before creating beyond the baseline.
- New documentation is created only for baseline documents, user-selected documents, or reconciliation of an authoritative document.
- Existing valid documentation is preserved; existing authoritative documentation is never duplicated.
- Link to the authoritative location instead of duplicating it.
- Organize by reader need on the Diátaxis map: tutorials, how-to guides, reference, explanation.
- One page serves one need; quadrants link to each other instead of absorbing each other.
- Split by need only, never merely for organization.
- Technical documentation is the default; business/product documentation needs explicit request.
- Never assert a fact without repository evidence or an explicit user statement.
- Never silently resolve material ambiguity.
- Never rewrite for style alone.
- Never remove valid user content without justification.
- Never create duplicate sources of truth.
- Never choose a license; detect and ask.
- Never commit or push unless explicitly requested.
- Do not create empty directories.

## 2. Execution Mode

Determine the execution mode before making changes.

### PLAN

PLAN mode MUST:

- inspect the repository;
- audit existing documentation;
- identify gaps, conflicts, duplication, and sources of truth;
- determine applicable documents;
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

### Unattended runs

Establish up front whether the run is interactive or unattended. Interactive runs stop and ask on material uncertainty. Unattended runs never block: record each unanswered question, proceed on the most reasonable assumption, state it, and report every assumption for review.

## 3. The client decides

The client chooses what the docs become; downstream users and agents consume the result. The agent proposes; the client disposes.

- Present the proposed document set before creating anything beyond the baseline, and let the client add, drop, or reorder.
- Re-confirm when scope emerges mid-run: a newly discovered need is a proposal, never a silent addition.
- Ask with the host agent's available user-interaction mechanism.
- Baseline documents need no per-item approval; everything else does.
- Minor editorial judgment needs no questions.

When a material uncertainty blocks progress:

1. STOP the current action.
2. Identify the specific uncertainty.
3. ASK the minimum question necessary.
4. WAIT for the answer.
5. Apply the answer.
6. RESUME from the exact blocked point.

DO NOT restart the workflow. DO NOT continue the blocked action on an assumption (interactive runs).

## 4. Bootstrap

When the repo has no usable docs, build the floor first, in this order:

1. `README.md`: identity, purpose, how to run.
2. `LICENSE`: ask which; never pick one.
3. `AGENTS.md`: only if agents will work in the repo — ask.
4. Ask what the client wants next; offer the catalog.

Do not scaffold the whole tree in one run. A thin floor that is true beats a full tree that is aspirational.

## 5. Repository Inspection

Inspect the repository before deciding what documentation is needed.

Inspect, where present:

- root structure;
- `README.md`;
- `LICENSE*`;
- `AGENTS.md` and tool-specific instruction files (`CLAUDE.md`, `.cursor/rules/`, `.github/copilot-instructions.md`, and the like) as evidence of established conventions;
- `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `SUPPORT.md`, `FUNDING.yml`;
- issue and pull request templates;
- `docs/`;
- existing requirements, design, and decision documentation;
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

## 6. Documentation Audit

Audit each relevant document before editing. For each, determine:

- whether it is applicable and appears current;
- whether it is authoritative, and where the canonical location is;
- which Diátaxis quadrant it serves, if any;
- whether equivalent information exists elsewhere;
- whether conflicting versions exist;
- whether it can safely be updated.

If authority or canonical location is unclear: STOP and ASK. Never create another source of truth to dodge the ambiguity.

Unclassifiable but valuable documents (governance notes, wiki exports, changelogs-as-docs): preserve as-is and flag for a decision; do not force them into a quadrant.

FAQs dissolve: sort each entry into the quadrant it actually serves and remove the FAQ once empty. A surviving FAQ is a sign the quadrants are incomplete.

## 7. The catalog

Every document the workflow can produce, with its audience and warrant:

| Document | Audience | Warrant |
| --- | --- | --- |
| `README.md` | users, agents | always: the repo's front door |
| `LICENSE` | users | always: ask which, never pick |
| `AGENTS.md` | agents | when agents will work in the repo |
| Community bundle: `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, templates | users | public or contributor-accepting repos |
| `docs/SRS.md` | users, agents | when the outcome must be verifiable, especially agent-built work |
| `docs/tutorials/` | users | when there is a skill to teach by doing |
| `docs/how-to/` | users, agents | when real tasks need directions |
| `docs/reference/` | users, agents | when the machinery needs exact description |
| `docs/explanation/` | users | when the why needs telling |
| `CHANGELOG.md` | users | when releases or notable changes exist |
| `ROADMAP.md` | users | when future intent is worth stating; maintained or linked, never dead |
| `docs/adr/` | users, agents | when a decision's why must survive |
| Design proposals | users, agents | per change needing review before implementation |
| `docs/SDD.md` | users | formal track: contracts, regulators, enterprise process |
| Business/product docs | users | only when explicitly requested |

Present this catalog, trimmed to what fits the repo, for selection. The baseline — `README.md`, `LICENSE`, plus `AGENTS.md` when agents are in play — needs no per-item approval; everything else is offered, never assumed, and created only when selected. Never silently expand the selected set. Reconcile existing equivalents instead of duplicating them.

Business/product documentation (Vision, Business Case, Stakeholder Register, BRD, PRD, Market Analysis, and anything else explicitly requested) is offered only when explicitly requested. Never infer it from technical docs.

## 8. Default Layout

Use the repository's existing layout when established. Otherwise:

```text
repo/
├── README.md
├── LICENSE                  # ask which; never pick
├── AGENTS.md                  # only when agents work here
├── CONTRIBUTING.md            # optional
├── CODE_OF_CONDUCT.md         # optional
├── SECURITY.md                # optional
├── CHANGELOG.md               # optional
├── ROADMAP.md                 # optional; or link the live board
└── docs/
    ├── tutorials/             # optional
    ├── how-to/                # optional
    ├── reference/             # optional
    ├── explanation/           # optional
    ├── SRS.md                 # optional; outcome contract
    ├── SDD.md                 # optional; formal track only
    ├── proposals/             # optional; per-change design docs
    └── adr/                   # only when ADRs exist
```

Never force this on a repo with an established equivalent.

## 9. README.md

`README.md` is the front door for both audiences: identity, purpose, and how to run.

Cover, as applicable: project name; purpose; scope; capabilities; prerequisites; installation; configuration; usage; development setup; testing; deployment; relevant links.

Commands MUST be verified against the repository. Never invent commands. Never turn the README into the requirements, design, or architecture specification. Link each quadrant from the README; never duplicate quadrant content into it.

## 10. AGENTS.md

`AGENTS.md` is operational context for coding agents: how to build, test, and contribute here. Only create it when agents will work in the repo.

Repo-wide rules and decisions live here; session scratch stays out.

Follow the de-facto standard's shape: plain Markdown, no required schema, operational over descriptive. Cover: scope and precedence (user instructions outrank it); build, test, lint, and format commands, exact and verified; sources of truth; architecture boundaries; repo constraints; documentation and Git rules. Repos with an established house skeleton keep it.

State the nesting rule: a nearer `AGENTS.md` outranks this one; the closest file to the work wins.

Tool-specific files may exist alongside (`CLAUDE.md`, `.cursor/rules/`, and the like). Treat them as evidence, keep shared instructions in `AGENTS.md`, and let thin tool files defer to it rather than duplicating it.

## 11. Tutorials

A tutorial is a learning-oriented lesson: the reader completes meaningful work toward a goal and acquires skill along the way.

- State the goal up front: what the reader will build or achieve, and what they will encounter.
- Make every step produce a visible result, and state what the reader should see after each one.
- Keep the path meaningful, completable, logical, and complete over the tools and concepts the lesson must cover.
- Never explain beyond what the next step needs; link how-to, reference, and explanation out instead.

## 12. How-to Guides

A how-to guide is goal-oriented directions through a real reader problem: deployment, operations, troubleshooting, development workflows.

- Write from the reader's problem, not from the machinery's motions; one guide answers one task the reader actually has.
- Give an adaptable logical sequence of actions the reader can check as they go; fork and rejoin where real problems demand it.
- Omit what the competent reader already knows; usability beats completeness.
- Link prerequisite lessons as tutorials instead of reteaching them inline.
- Never inline explanation or reference; link them out instead.

## 13. Reference

Reference is austere technical description of the machinery: APIs, contracts, configuration, components, interfaces, errors.

- Describe neutrally and completely; no instruction, no explanation, no opinion.
- Mirror the structure of the product so reader and machinery stay aligned.
- Use standard patterns and exact forms: every command, flag, option, and error verbatim.
- Illustrate with examples that do not instruct; generate from the code where the repository supports it.

## 14. Explanation

Explanation is discursive treatment that builds understanding: why things are so, context, decisions, trade-offs, alternatives.

- Open with the why-question the page answers, and bound the topic tightly; one page explores one area.
- Connect to other material freely, including outside the immediate topic, and weigh alternatives with reasons.
- Admit context, history, and opinion where they illuminate; this is the one quadrant where they belong.
- Never embed instruction or technical description; link how-to and reference out instead.

## 15. Software Requirements Specification

The SRS defines WHAT done means. It is the outcome contract — most valuable when agents build the work, because agents check conformance but cannot infer intent.

Use an ISO/IEC/IEEE 29148:2018-aligned structure when formal rigor is required; otherwise keep the shape and drop the ceremony. Never claim formal compliance unless established.

### Functional Requirements

Testable, unambiguous, traceable, with stable identifiers:

```text
FR-001
FR-002
```

Each FR MUST be verifiable by a named check or test. An untestable requirement is a wish; rewrite it or drop it.

### Quality Requirements

Stable identifiers (`NFR-001`, …). Only targets supported by evidence or explicit user statements. Never invent numeric performance, availability, scalability, security, or usability targets. Unknown material targets are questions, not guesses.

### Scope and context

Purpose, scope, references, definitions; product perspective and functions; operating environment; constraints; assumptions; dependencies; external interfaces (user, system, API, hardware as applicable); data requirements (entities, relationships, validation, persistence, retention).

### Traceability

Trace each requirement to the design element, test, or artifact that satisfies it. Open issues stay listed as open; never invent answers.

### Boundary with the quadrants

Normative statements and their IDs live here. Tutorials, how-tos, reference, and explanation teach, direct, describe, and discuss — and cite requirement IDs instead of restating them.

## 16. Design proposals

A design proposal argues for one change before it is implemented: problem, options considered, the chosen design, interfaces affected, verification plan. It is reviewed, approved, then implemented — and then it is history, not standing documentation.

Use proposals for changes big enough to get wrong: new components, interface changes, data-model changes, anything crossing a boundary the SRS or the repo's conventions set.

Keep proposals in `docs/proposals/`, one file per change, named by date or sequence. A proposal never outlives its implementation as guidance; lasting decisions graduate to ADRs, lasting facts to reference.

## 17. Architecture Decision Records

An ADR records WHY one significant decision was made, so the reasoning survives the people who made it. The SDD (when it exists) records HOW the current design works.

Do not use ADRs for routine implementation, minor configuration, every library choice, or anything the design docs already capture.

Keep them in `docs/adr/`, numbered (`0001-title.md`), preserving existing numbers. Each ADR carries: title, status, context, decision, consequences. Never duplicate a decision already recorded authoritatively.

## 18. Software Design Description

The standing SDD describes HOW the system is designed. Create it only for the formal track: contracts, regulators, or enterprise process demand it. Otherwise the design lives where it is used — interfaces in reference, rationale in ADRs and explanation, behavior in how-tos.

When created, use an IEEE 1016-2009-aligned structure: identification and scope; design context; relevant viewpoints (context, composition, logical, dependency, information, interface, interaction, state, deployment); views in Mermaid, UML, tables, or structured text; structural, behavioral, data, interface, and deployment design; constraints; significant rationale; traceability to requirements.

Views MUST represent verified architecture, never imagined architecture. Never document every function or file. Never claim active formal compliance or certification.

## 19. Community files

Offered as a bundle for public or contributor-accepting repos; private repos take only what fits.

- `LICENSE`: detect the current license. If none, ask which — never pick one for the client.
- `CODE_OF_CONDUCT.md`: use the canonical Contributor Covenant text from its published source; never reproduce it from memory.
- `CONTRIBUTING.md`: setup, workflow, and PR expectations, verified against the repo. Never copy a template nobody follows.
- `SECURITY.md`: vulnerability reporting, supported versions, disclosure process, established contacts only. Technical security architecture lives in the SDD or reference, never here. Never invent contacts or procedures.
- Templates: issue and pull request templates matching how the repo actually triages.
- `SUPPORT.md` and `FUNDING.yml`: where the repo needs them.

## 20. Time-axis documents

The changelog looks back; the roadmap looks forward. Keep both root-level and dated.

`CHANGELOG.md`: notable changes per release, newest first. Record what changed and why it matters; never reconstruct history from guesses.

`ROADMAP.md`: future intent in coarse, explicitly non-committal terms. Maintain it with dated entries, or link the live board instead of keeping a file. Reconfirm any roadmap whose dates are all past; a dead roadmap misleads agents into building canceled futures.

## 21. Reconciliation

For every selected document: locate existing equivalents; identify the apparent source of truth; determine the canonical location; compare against the selected shape; preserve valid material; add only supported missing material; correct only stale material current evidence contradicts; dedupe only when authority is clear; avoid reformatting for its own sake.

Never rewrite a document solely to match a template. Never silently merge contradictions — conflicting sources of truth with unclear authority are a question, not a judgment call.

Precedence when existing pages mix quadrants: split them only when the page is being updated anyway and authority is clear; otherwise preserve the page and flag the mix in FINDINGS. Preservation beats purity on pages nobody asked to touch.

## 22. Cross-document consistency

After creating or updating the selected documents, check consistency of: project name; scope; terminology; functional and quality requirements; architecture; components; interfaces; data models; deployment; configuration; commands; paths; links; requirement identifiers; ADR references; document status.

Never make contradictory claims. Never state draft as final, proposed as accepted, planned as implemented, unverified as verified, or intended behavior as current behavior, unless evidence supports it.

## 23. Uncertainty

Material uncertainty — unknown intent, ambiguous scope, conflicting requirements or docs, unclear authority or ownership, unknown targets, ambiguous architecture, unclear selection, anything that could materially change the result — is a question, never a guess.

Interactive runs: STOP, identify the exact uncertainty, ASK the minimum question, WAIT, apply the answer, RESUME from the blocked point. Never restart, never proceed on assumption, never hide the uncertainty, never substitute generic template content.

Unattended runs: record the question, proceed on the most reasonable stated assumption, report every assumption for review.

Before finalizing, every material statement MUST be traceable to repository evidence or an explicit user statement. Anything else is an open question. There is no third category.

## 24. Verification

In APPLY mode, verify the result: referenced commands, paths, and files exist; links resolve; names are correct; APIs, components, deployment, and diagrams match the repository; requirement identifiers are unique and stable; traceability references are valid; standards references are correctly named; repo conventions are followed.

Each quadrant page serves exactly one quadrant; quadrants link rather than duplicate.

Use repo-provided validation, linting, and link checking when available. Never run unrelated or expensive tests solely because docs changed.

## 25. Idempotency

Repeat runs MUST be safe: preserve valid docs; update stale ones on evidence; reconcile missing sections; never duplicate documents or ADRs; never renumber ADRs or requirement IDs without cause; never formatting-only rewrites; never remove valid user content without justification; never recreate what already satisfies the selection.

Destructive or materially reorganizing changes are questions first.

## 26. Worked examples

Classifying `docs/deploy.md` ("here is how our deploy pipeline works, step by step, and why we chose blue-green"): the steps are a how-to, the blue-green rationale is explanation, the pipeline's flags and environments are reference. Three pages, linked.

Classifying `docs/api.md` ("endpoints, auth flows with examples, rate-limit policy"): endpoints and rate limits are reference; the auth flows walk the reader through a task and belong in how-to, linked from reference.

Classifying `FAQ.md` ("how do I reset the db?", "what versions are supported?", "why Postgres?"): reset steps go to how-to, supported versions to reference (or `SECURITY.md`), the Postgres rationale to explanation. Delete the FAQ when empty.

## 27. PLAN Mode Output

Report: proposed baseline; proposed selected documents; existing sources of truth; conflicts and unclear authority; what would be created, updated, preserved, skipped; decisions blocking safe execution. Modify nothing.

## 28. APPLY Mode Output

Report: CREATED; UPDATED; PRESERVED (authoritative content intentionally retained, with mixes flagged); SKIPPED (with reason); STANDARDS ALIGNMENT (for example SRS: ISO/IEC/IEEE 29148:2018-aligned — never claim compliance unless established); FINDINGS (inconsistencies, gaps, observations); VERIFICATION (checks performed and results — never claim unrun checks).

## 29. Completion

End in exactly one state: PLAN completed (nothing modified), APPLY completed (selected docs reconciled and verified), or BLOCKED (state the exact decision required).

Never continue through material uncertainty. Never invent project information. Never introduce business/product docs without explicit selection. Never duplicate sources of truth. Never commit or push unless requested.
