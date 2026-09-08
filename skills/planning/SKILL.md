---
name: planning
description: Structured planning for substantial or materially underspecified software, technical, research, and operational work. Use when requirements, scope, design, dependencies, sequencing, or acceptance criteria need clarification.
---

# Planning

Create the smallest useful plan that makes substantial work clear, executable, and verifiable.

## When to Use

Use for:

- substantial or materially underspecified work
- unclear requirements, scope, design, dependencies, sequencing, or acceptance criteria
- work requiring phases, tasks, risks, constraints, or significant decisions
- creating or maintaining planning artifacts

Do not add planning overhead to routine, sufficiently specified work.

## Principles

- Existing requirements, documentation, decisions, constraints, and project conventions are authoritative.
- Inspect relevant artifacts before planning.
- Resolve only ambiguity that can materially affect the result.
- Do not guess about material requirements or decisions.
- Keep authoritative information in one place; reference rather than duplicate it.
- Make important scope, exclusions, dependencies, assumptions, risks, decisions, and acceptance criteria explicit.
- Use proportional traceability.
- Do not claim standards compliance without verifying the applicable standard and edition.

## Workflow

### 1. Understand

Inspect relevant requirements, specifications, architecture, design, code, tests, existing plans, and project conventions.

Identify:

- objective and desired outcome
- scope and exclusions
- requirements and constraints
- dependencies and interfaces
- acceptance criteria
- risks and assumptions

### 2. Clarify

Ask only questions whose answers can materially affect the work.

For each material ambiguity:

1. identify the issue
2. provide relevant context
3. give a recommendation when evidence supports one
4. record the confirmed decision

For non-material ambiguity, use a clearly stated assumption when safe.

When artifacts conflict, identify the conflict and determine the authoritative source.

### 3. Plan

Create the smallest coherent plan needed.

Include, as applicable:

- objective and success criteria
- scope and exclusions
- requirements and acceptance criteria
- implementation tasks and sequence
- dependencies
- risks and assumptions
- verification points
- significant decisions

Each significant task should trace to a requirement, objective, constraint, risk, or decision when useful.

### 4. Validate

Check the plan for:

- completeness and consistency
- alignment with requirements and constraints
- feasible sequencing and dependencies
- clear acceptance criteria
- addressed material risks
- unnecessary work or artifacts

Do not claim validation or approval without evidence.

### 5. Handoff

When planning precedes implementation:

- treat validated requirements and decisions as the implementation baseline
- preserve established constraints
- record unresolved assumptions explicitly
- make the plan concrete enough that implementation does not require re-deriving the investigation
- return to planning when implementation reveals a material requirement or planning conflict

If the agent is not running on Arena.ai and supports a plan mode that writes to a file, include an explicit "Update the canonical handoff" step in that plan file, following the `agent-handoff` skill. Place it after verification and before pause, transfer, or completion; update an existing handoff to reflect completion rather than leaving it active.

Planning owns **understanding, requirements, decomposition, and execution planning**.

Implementation owns **carrying out the technical work**.

### 6. Maintain

When information changes:

- update affected planning artifacts
- reassess scope, requirements, dependencies, risks, and sequencing
- record significant changes and decisions
- preserve useful traceability
- do not silently change committed requirements or scope

## Standards

Use recognized standards only when relevant.

Common references include:

- ISO/IEC/IEEE 29148 — requirements engineering
- ISO/IEC/IEEE 12207 — system life-cycle processes
- ISO/IEC/IEEE 15288 — system life-cycle processes
- ISO/IEC/IEEE 29119 — software testing

Verify the applicable edition and status before making compliance claims.

Standards guide planning; they do not justify unnecessary bureaucracy.

## Failure Behavior

- **Missing information:** determine whether it is material.
- **Material ambiguity:** ask or explicitly record the unresolved issue.
- **Non-material ambiguity:** use a clearly stated assumption when safe.
- **Conflicting artifacts:** identify the conflict and determine the authoritative source.
- **Unverified standards:** do not claim compliance.
- **Unsupported claims:** do not claim validation, approval, agreement, or completion without evidence.
