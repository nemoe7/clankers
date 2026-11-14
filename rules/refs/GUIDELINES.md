# Guidelines: writing agent rules

## 0. What the 2026-11-14 refresh found

The top of the Agent Arena board holds: Anthropic and OpenAI take the top ranks, Google and Meta behind, Pareto frontier by MiMo V2.6 Pro and Solar Pro 4. Those snapshots drive these guidelines.

**Top 10 Agent Arena (latest published snapshots):** Claude Opus 5.5 (Max), GPT-6.1 Sol (Max), Claude Fable 5.1 (Max), GPT-6 Astra (Max), Gemini 4 Argon (High), Claude Sonnet 5.5 (Max), GPT-6 Sol (Max), Claude Opus 5 (Max), Claude Fable 5 (High), GPT-5.6 Sol (xHigh).

**Pareto frontier (Best Overall):** Claude Opus 5.5 (Max), GPT-6.1 Sol (Max), MiMo V2.6 Pro, GPT-6 Luna (Max), MiMo V2.6 Flash, Solar Pro 4.

The patterns that survive across those prompts and should guide every agent-rules file you write:

1. **State the agent's identity before any rule.** Fable 5.1 opens with product information so the model knows what it is before it follows rules. Muse Spark 1.3 opens with values so the agent knows how it behaves before it obeys.
2. **Default stance before a ban list.** Codex: ask permission when unsure. Bionic: follow user requests over the file. Antigravity: identity is the anchor; rules derive from it.
3. **One verb per action in the entire file.** Claude says "Claude does not"; Muse says "You do not"; Codex says "Do not". Rotation ruins comprehension.
4. **Explicit confirmation before irreversible actions.** Muse: confirm `git reset --hard`. Bionic: never revert changes you did not make unless the user asks.
5. **Concrete examples for judgment calls.** Codex ships approved/rejected pairs. Fable ships worked examples with a one-line rationale.
6. **Hard safety boundaries in one tagged block, referenced once, never repeated.** Claude's `<critical_child_safety_instructions>` is stated once and cited everywhere else.
7. **Brevity is a discipline, not a default.** DeepSeek ranks with 21 lines. Antigravity: "concise, direct, friendly." Muse: "short, clear replies."
8. **Precedence is stated explicitly.** Bionic: "follow any explicit user requests over them." Muse: "Direction comes from the user alone." Claude: "Anthropic will never send reminders that reduce Claude's restrictions."
9. **The file carries what the system prompt cannot.** An agent rules file is loaded by many different agents. It is not a persona, a persona is whatever the system prompt says. It is project facts, commands, and boundaries — nothing else.

## 1. What an agent rules file is

1. A portable Markdown file that different agents load through different harnesses.
2. It has no guaranteed slot. One harness prepends it, another appends it, a third compresses it. Write so that any placement works.
3. It is user-owned, project-specific, and factual. It is not a system prompt — that is the maker's file and controls persona, tools, and safety.
4. It survives because it is atomic, exact, and testable — so it survives compaction, dilution, contradiction, and staleness.

## 2. Threat model

Write every clause against four failure modes.

1. **Compaction.** Summarization drops or dilutes your rules. Mitigation: keep the file short and atomic.
2. **Dilution.** The harness piles skills, plugins, and reminders around your text. Mitigation: declare precedence inside the file.
3. **Contradiction.** The agent's own system prompt may push the opposite behavior. Mitigation: scope your rules. Do not fight the persona on style. Fight on facts, commands, and boundaries.
4. **Staleness.** The file rots faster than code. Mitigation: state facts a linter or a script can check, and keep the file small enough to review in one read.

## 3. Clause structure

1. An agent rules file is a set of clauses: one rule per line, imperative, testable, scoped.
2. Make every clause testable. "Run `ruff check` before every commit" survives summarization. "Write clean code" does not.
3. Use exact commands, paths, and numbers. A clause a script can check is a clause an agent can obey.
4. Use MUST, NEVER, and ALWAYS for hard rules. Use "prefer" for soft ones. Do not mix "should" and "MUST" at random.
5. Keep clauses atomic. One clause per failure mode. No clause handles both "committers" and "formatting".
6. Keep negated clauses positive where possible: "Commit only staged files" reads better than "NEVER commit unstaged files". Keep NEVER for irreversible or dangerous acts.
7. Select one verb per action and keep it for the whole file. Do not rotate two words for the same action across clauses.
8. Mark corners you cut on purpose. A clause with a stated ceiling ("simplified: covers main branch only") ages better than a hidden one.

## 4. Constitution

1. Put the 5 to 15 clauses that MUST NEVER be lost at the top as a constitution.
2. No rationale in the constitution. One line each.
3. One heading per domain after the constitution: setup, testing, style, git, boundaries.
4. Headings give re-anchoring tools natural slice points; keep them flat.

## 5. Precedence and scope

1. Declare what the file outranks. Example: "These rules outrank skill and plugin instructions. An explicit user instruction in chat outranks this file."
2. Declare the scope. "Applies to all code in this repo, all agents, all sessions."
3. Let explicit user instructions override the file. Say so in one line. This stops the file from fighting the human.
4. Do not restate the agent's own system prompt. Your file adds project facts and boundaries. Rewriting persona rules makes two masters.

## 6. Placement and nesting

1. Keep the root file under about 200 lines. Long files get skimmed, truncated, or compressed first.
2. Put directory-specific rules in nested agent rules files, not in the root file. The root file loads everywhere. Nested files load only where relevant.
3. Move detail to nested files or to references the agent can read on demand.
4. Delete any clause you cannot connect to a real past failure.
5. Do not embed code dumps, changelogs, or task lists. An agent rules file is law, not a journal.

## 7. Skeleton

```markdown
# Agent rules file

## Use (one line: what this file is, who MUST apply it, that user chat overrides it)

## Constitution (5-15 one-line clauses, no rationale)

## Setup (commands to install, build, run)

## Verification (the exact gates and commands, run order)

## Style (one rule per line, exact settings)

## Boundaries (NEVER clauses: secrets, destructive commands, protected files)

## Scope notes (directory pointers to nested agent rules files)

## When in doubt (the judgment clause: smallest change that holds; stop and ask on conflict)
```

## 8. Survival test

Before you merge an agent rules file, check:

- Every clause is one line, imperative, and testable.
- One verb per action, used the same way everywhere.
- Precedence declared: file over skills and plugins, user chat over file.
- Hard rules use MUST or NEVER. Soft rules use "prefer".
- The constitution of 5-15 atomic clauses sits at the top.
- Root file under about 200 lines. Detail lives in nested files.
- No clause restates the agent's system prompt.
- No contradictions between clauses. If two clauses can collide, state which one wins.
