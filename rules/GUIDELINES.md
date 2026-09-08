# GUIDELINES.md

Specification for the agent-rule system. Source of truth for structure,
constraints, and maintenance. Not a rule file — do not place in any agent's
Rules folder.

## Rule files and constraints

| File | Applies to | Constraint | Format |
| --- | --- | --- | --- |
| AGENTS.md | any agent/chat (generic) | markdownlint (MD013 off) + token count | linted |
| CLINE.md | Cline (VS Code v4.1.17) | markdownlint (MD013 off) + token count | linted |
| ARENA.md | Arena.ai Agent Mode | optimize file size | compact |
| CHATGPT.md | ChatGPT | optimize character count (no more than 1,500) | mirrors instructions field |

- **Linted** (AGENTS.md, CLINE.md): must pass markdownlint configured by
  `.markdownlint.json` in the workspace root, which disables the max line-length
  rule (MD013) so bullets stay on one line and token count stays low.
- **Compact** (ARENA.md): exempt from markdownlint.
- **Mirrors instructions field** (CHATGPT.md): plain run-on text — inline
  `SECTION:` labels only; no `#` headings, no `-` bullets, no `**`, no
  linting.

## Structure

- Header is a bare `# FILENAME.md` anchor ("shebang") so rules stay attributable
  when combined. No subtitles or descriptions (exceptions: ARENA.md's activation
  preamble; CLINE.md's one-line AGENTS.md pointer; CHATGPT.md has no header).
- Files are independent with one deliberate exception: CLINE.md assumes Cline
  loads the global AGENTS.md (no embedded core, so it is not standalone on its
  own).
- AGENTS.md is the generic core. CLINE.md is Cline-specific only — it holds no
  copy of the core because Cline loads the global AGENTS.md (per current Cline
  behavior); the two files are layered, not duplicates. ARENA.md embeds the
  core (minus Tools) plus its activation preamble. CHATGPT.md carries a
  distinct content set, not the core.
- Edit core rules in AGENTS.md once; ARENA.md embeds a copy that must be
  synced to it. CLINE.md needs no core sync — it inherits AGENTS.md via Cline's
  global read.

## Shared core content (AGENTS / ARENA-embedded copy)

- **Scope:** only the requested task; nothing beyond what's required, needed to
  verify, or necessary. Smallest coherent change; stop when implemented and
  verified. Preserve behavior, architecture, interfaces, intent, conventions
  unless change is required. No proactive refactor/optimize/redesign/rename/
  reformat/dependency/error-handling/security/extra-test-coverage. Investigate
  only as needed; no alternative-hunting after a suitable pattern; no
  speculation; unrelated findings out of scope unless blocking; ask only when
  ambiguity materially affects safe scope or behavior; task-focused reasoning.
- **Engineering:** KISS/YAGNI/DRY; guard clauses and early returns; cohesive
  modules, low coupling, small interfaces; abstractions/seams only for tangible
  requirements; no parallel mechanism where an extension point fits;
  evidence-based decisions; clear human-readable code; preserve APIs/behavior
  unless intentionally changed.
- **Debugging:** Reproduce → Hypothesize → Verify → Fix → Cover → Verify.
  Isolate first; falsifiable hypotheses; evidence over guessing; one variable at
  a time. Root cause, not symptom; no arbitrary fallbacks; never conceal
  failures; update assumptions when disproven. Focused regression test for
  meaningful behavioral fixes; re-run checks.
- **Testing:** Red → Green → Refactor → Verify. Failing test first when
  practical; smallest passing change; refactor without behavior change; run
  tests and checks. Test public interfaces and meaningful integration
  boundaries; reuse existing frameworks/fixtures/helpers/conventions.
  Mechanical-only changes: proportional verification. Never weaken/remove tests
  to pass; no speculative behavior or tests beyond the task.
- **Review:** before finishing, check requirements/acceptance criteria/scope and
  verify behavior via tests/linters/formatters/builds; verify external/
  version-specific/time-sensitive facts against authoritative sources; review
  diff for correctness/edge cases/security/maintainability/regressions/
  complexity/unrelated edits/formatting noise/debug artifacts; every changed
  file belongs to the change; never claim verification not performed.
- **Code style:** 2-space indentation (overrides formatter defaults); simple,
  readable code; Markdown per markdownlint defaults with no line-length limit, enforce ;
  Python per Ruff default selection (E4, E7, E9, F); preserve architecture;
  leave unrelated code untouched.
- **Git:** stage only task-related files (never unrelated or user-owned);
  review the diff after each edit; atomic commits (one logical change per
  commit) — commits are allowed without asking, but always on a dedicated new
  branch, never directly on main (branch first if on the default branch);
  reuse commit scopes from previous commits, add a new scope only when none
  fits; no commit body; no push or PR unless asked. Otherwise propose one
  Conventional Commit message `<type>(scope): <subject>` — imperative,
  specific, lowercase after `:`, no period, no more than 72 characters. Types:
  feat, fix, refactor, perf, style, docs, test, build, chore. One message per
  completed feature.

## CLINE.md specifics

- **Layering:** CLINE.md is Cline-specific only — no embedded generic core,
  because Cline reads the global AGENTS.md. Deploy CLINE.md in Cline's global
  Rules folder and AGENTS.md at `~/.agents/AGENTS.md` so both load; if Cline
  ever stops loading AGENTS.md globally, re-embed the core.
- **Command discipline (own section after Scope):** run exactly the command
  given; after any requested command report the output and STOP — no follow-up
  edits/fixes unless explicitly told to; empty or clean output (e.g., `git
  status` clean) is not a mandate to act; never self-assign next steps between
  turns; if output surfaces a fixable problem, mention and ask, don't fix
  unprompted.
- **Built-in tools (verified against v4.1.17 source):** `read_files`,
  `search_codebase`, `run_commands`, `fetch_web_content`, `editor`,
  `apply_patch`, `skills`, `ask_question`, `submit_and_exit`. `run_commands` is
  execution-only — never a substitute for file tools. Edits go through
  `editor`/`apply_patch` only; if write tools are blocked, stay read-only and
  report.
- **MCPs** (only if installed; never invent tool names): `tokensave` (code
  search/navigation/context/callers/callees/impact analysis); `context7`
  (dependency/library docs, no more than 3 calls per input); `memory`
  (persistent cross-session memory).
- **Skills** (only these installed SKILL.md skills; may combine): `planning`
  (non-trivial tasks), `frontend-design` (creating/redesigning an interface),
  `web-design-guidelines` (reviewing/auditing a web interface).
- **Test Timeout (alternative only):** run tests normally first. Only if a test
  does time out (does not exit) use the alternative protocol — redirect output
  to `.test-output.tmp`; wait with `ping` at most 30 s; treat non-exit as
  failure; inspect with file tools; delete `.test-output.tmp` on success,
  failure, or timeout.

## ARENA.md specifics

- **Activation preamble (`## How to read this file`, first section):** Arena has
  no documented auto-loaded rules mechanism, so ARENA.md is uploaded manually per
  session. The preamble tells the reading agent it is Arena Agent Mode, that the
  file is its binding operating rules for the session (not reference material),
  to apply them unless the user explicitly overrides, to confirm in one line that
  it loaded them, and not to edit the file. Deploy by uploading ARENA.md with an
  explicit instruction to follow it; verify with a probe ("summarize your
  rules").
- **Omitted sections:** ARENA.md has no `## Tools` section (per owner decision).
  `## Git` was restored when Arena gained GitHub access, so the core sections
  present are General, Scope, Engineering, Debugging, Testing, Review, Code
  style, Git, then the platform sections below, then Responses.
- **Workspace limits (enforce):** work inside the workspace root only; never
  access external drives, other projects, or system files unless asked.
  Snapshots are best-effort capped at ~128 MB or no more than 10,000 files —
  stay well under both; remove large/temporary artifacts as you go.
  Cache/build/dependency directories do not persist between turns
  (`node_modules`, `.cache`, `.venv`, `dist`, `build`, `out`, `target`,
  `__pycache__`, etc.); neither do installed packages or running processes —
  keep anything that must survive in ordinary files.
- **Deliverables/previews:** deliver results as workspace files; open the main
  deliverable in the viewer; prefer modern formats (.docx/.xlsx/.pptx, .md,
  .html, .pdf) — legacy (.doc/.ppt) only download. The preview iframe is
  sandboxed with no network access — use inline styles, embedded SVG, and data
  URIs; external CDNs/fonts/stylesheets will not load in-app. Servers: bind to
  0.0.0.0; browser code uses relative URLs via the dev-server proxy — never
  call localhost/127.0.0.1 from browser code.

## CHATGPT.md specifics

- **Budget/content:** no more than 1,500 characters, kept as-deployed in the
  ChatGPT custom-instructions field. Plain section labels (RESPONSE, CODE,
  FORMAT, GITHUB) with bullets; no `#` headings, no linting.
- **Response:** most concise response only; structured output preferred; no
  filler (preambles, postambles, transitions, acknowledgments, disclaimers,
  commentary); clarity > brevity; add detail when asked; state what
  changed/was found incl. unresolved issues, assumptions, limitations; accurate
  facts first; verify current/external/version/time-sensitive info when
  relevant; state uncertainty; use mermaid diagrams optimized for mobile.
- **Code:** YAGNI — only what's currently needed, smallest coherent change that
  satisfies the requirement; KISS — simplest correct solution; DRY — reuse
  meaningful logic without forced abstractions; human-readable over clever; repo
  docs/conventions are truth; preserve intent, behavior, architecture,
  interfaces, features, patterns unless change is required; root causes, not
  symptoms; evidence over guessing; check relevant edge cases, no speculative
  over-engineering; preserve original meaning/intent/requirements/structure
  unless asked otherwise; for important corrections identify the error and the
  meaningful fix or tradeoff; use relevant plugins when they materially improve
  accuracy or efficiency.
- **Format:** 2-space indentation; Python per Ruff default (E4, E7, E9, F);
  Markdown per markdownlint defaults; prefer write-block for fully markdown
  responses.
- **GitHub (ChatGPT can push — guard it):** push/commit only on explicit
  authorization; Conventional Commit format; no commit body; write the diff to
  the plugin body on commit. (No atomic/new-branch/scope-reuse rules — git flow
  is owner-controlled.)

## Design decisions (rationale)

- Single verbose file → validated → deduplicated and split into a generic file
  (AGENTS.md) plus platform files; later made self-contained and independent.
  CLINE.md duplication was then removed when Cline began loading the global
  AGENTS.md — CLINE.md is now Cline-specific only. ARENA.md still embeds a copy
  of the core; keep it synced from AGENTS.md.
- Whitespace minification is counterproductive for tokenizers: stripping spaces
  raises token counts, so readable clause-per-line is the practical floor. Size
  wins come from prose compression, not removing whitespace.
- Headers are bare filenames; descriptive subtitles were fluff.
- Tool references remapped to real Cline v4.1.17 names; `web_search` is not a
  Cline tool; `memory` is an MCP; `headroom` and `rtk` removed.
- markdownlint line-length (MD013) is disabled via `.markdownlint.json` so
  rule bullets stay single-line (fewer newlines = fewer tokens). All other
  default rules still enforced on AGENTS.md and CLINE.md.
- The `≤` character is avoided in favor of "no more than" — models handle it
  more reliably.
- Commit policy: atomic commits are allowed without asking, but always on a
  dedicated new branch (never directly on main; branch first if on the default
  branch) — the branch rule is the enforcement, not per-commit permission;
  scopes reused from prior commits unless a new one is warranted; no commit
  body. Push/PR still requires asking.
- ARENA.md omits only the Tools section (Git was restored when Arena gained
  GitHub access); it is a size-optimized target and carries an activation
  preamble for manual per-session upload.
- CHATGPT.md mirrors the deployed ChatGPT instructions field (plain section
  labels + bullets) inside its hard character limit; git flow there is
  owner-controlled (no atomic/new-branch/scope rules).

## Verification

- Lint (AGENTS, CLINE): `markdownlint-cli2 --config .markdownlint.json
  AGENTS.md CLINE.md` → 0 issues.
- Tokens: `tiktoken` cl100k_base.
- Core sync: compare shared sections (General, Scope, Engineering, Debugging,
  Testing, Review, Code style, Git, Responses) byte-for-byte between AGENTS.md
  and ARENA.md — must match. CLINE.md is exempt (no embedded core).

## Current baseline

| File | chars | tokens |
| --- | --- | --- |
| AGENTS.md | ~4,242 | ~860 |
| CLINE.md | ~3,059 | ~697 |
| ARENA.md | ~5,678 | ~1,198 |
| CHATGPT.md | ~1,497 | ~309 |
