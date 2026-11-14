# Guidelines: writing agent rules

## 0. Preamble

Date: 2026-11-14

Models:
- Claude Opus 5.5 (Max)
- GPT-6.1 Sol (Max)
- Claude Fable 5.1 (Max)
- GPT-6 Astra (Max)
- Gemini 4 Argon (High)
- Claude Sonnet 5.5 (Max)
- GPT-6 Sol (Max)
- Claude Opus 5 (Max)
- Claude Fable 5 (High)
- GPT-5.6 Sol (xHigh)

Why those models were selected:
These models represent the current state-of-the-art in agent systems and the Pareto-optimal value-performance tradeoff. The refresh informs the agent-rules guidelines to ensure they reflect the most capable and efficient models available.

## 1. What an agent rules file is

1. A user-owned Markdown file installed once in the harness's config. The harness loads it for every project and every session.
2. It has no guaranteed slot. One harness may prepend it to the system prompt. Another may append it to the first user message. A third may compress it. Write so that any placement works.
3. It carries behavioral contracts: precedence, invariants, boundaries, git and style discipline. It carries no project facts. Commands, venv paths, ports, configs, and gate lists belong in that repo's own file or README. A project fact placed here is wrong somewhere else, because the file applies everywhere.
4. It is not a system prompt — that is the maker's file and controls persona, tools, and safety.
5. It survives because it is atomic, exact, and testable — so it survives compaction, dilution, contradiction, and staleness.

## 2. Threat model

Write an agent rules file against four failure modes.

1. **Compaction.** Summarization can drop or dilute your rules. Mitigation: keep the file short and atomic.
2. **Dilution.** The harness piles skills, plugins, and reminders around your text. Mitigation: declare precedence inside the file.
3. **Contradiction.** The agent's own system prompt may push the opposite behavior. Mitigation: scope your rules. Do not fight the persona on style. Fight on behavioral contracts and boundaries.
4. **Staleness.** The file rots faster than code. Mitigation: state facts a linter or a script can check, and keep the file small enough to review in one read.

## 3. Clause structure

1. An agent rules file is a set of clauses: one rule per line, imperative, testable, scoped.
2. Make every clause testable. "Run `ruff check` before every commit" survives summarization. "Write clean code" does not.
3. Use exact commands, paths, and numbers. A rule a script can check is a rule an agent can obey.
4. Use MUST, NEVER, and ALWAYS for hard rules. Use "prefer" for soft ones. Do not mix "should" and "MUST" at random.
5. Keep clauses atomic. One clause per failure mode. No clause handles both "committers" and "formatting".
6. Keep negated clauses positive where possible: "Commit only staged files" reads better than "NEVER commit unstaged files". Keep NEVER for irreversible or dangerous acts.
7. Select one verb per action and keep it for the whole file. Do not rotate two words for the same action across sections.
8. Mark corners you cut on purpose. A rule with a stated ceiling ("simplified: covers main branch only") ages better than a hidden one.

## 4. Constitution

1. Put the 5 to 15 rules that MUST NEVER be lost at the top of the file as a constitution.
2. No rationale in the constitution. One line per rule.
3. One heading per domain after the constitution: git, style, testing, boundaries. Use carries precedence before the constitution.
4. Headings give re-anchoring tools natural slice points; keep them flat.

## 5. Precedence and scope

Place this content in the `Use` section of the produced file, not in a heading of its own.

1. Declare what the file outranks. Example: "These rules outrank skill and plugin instructions. An explicit user instruction in chat outranks this file."
2. Declare the scope. "Applies to every project, every agent, every session, wherever this harness runs."
3. State the chat override in `Use`. This stops the file from fighting the human.
4. Do not restate the agent's own system prompt. Your file adds behavioral contracts. Rewriting persona rules makes two masters.

## 6. Installation and economy

1. Keep the file under about 200 lines. Long files get skimmed, truncated, or compressed first.
2. Detailed workflows or steps belong in a skill, not the rules file.
3. Delete any rule you cannot connect to a real past failure.
4. Do not embed code dumps, changelogs, task lists, or project facts. An agent rules file is law, not a journal.

## 7. Skeleton

```markdown
# <NAME> rules (for example, CORE, KILO)

## Use
- What this file outranks, what outranks it.
- User chat overrides this file.

## Constitution (5-15 one-line rules, no rationale)

## Boundaries (NEVER rules: secrets, destructive commands, protected files)

## When in doubt (the judgment rule: smallest change that holds; stop and ask on conflict)
```

## 8. Checklist

- Constitution of 5-15 atomic rules sits at the top.
- Every rule is one line, imperative, and testable.
- One verb per action, used the same way everywhere.
- Precedence declared in Use: file over skills and plugins, user chat over file.
- Hard rules use MUST or NEVER. Soft rules use "prefer".
- The file under about 200 lines. Detail lives in a references file the agent can open on demand.