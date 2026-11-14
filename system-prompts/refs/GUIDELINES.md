# Guidelines: writing a system prompt

## 0. What the 2026-11-14 refresh found

Distilled from the leaked system prompts of the top agent models on Arena Leaderboards as of 2026-11-14.

**Top 10 Agent Arena (Best Overall, latest published snapshots, 2026-11):**
Claude Opus 5.5 (Max), GPT-6.1 Sol (Max), Claude Fable 5.1 (Max), GPT-6 Astra (Max), Gemini 4 Argon (High),
Claude Sonnet 5.5 (Max), GPT-6 Sol (Max), Claude Opus 5 (Max), Claude Fable 5 (High), GPT-5.6 Sol (xHigh).

**Pareto frontier (Best Overall):** Claude Opus 5.5 (Max), GPT-6.1 Sol (Max), MiMo V2.6 Pro, GPT-6 Luna (Max),
MiMo V2.6 Flash, Solar Pro 4.

**What I fetched these from:** `asgeirtj/system_prompts_leaks` (raw.githubusercontent.com), CC0, daily.
Fetched: Claude Opus 5.5, Claude Fable 5.1, GPT-6.1 Sol (Codex), Gemini 4 Argon (Antigravity IDE),
Muse Spark 1.3 (Meta), LM Studio Bionic. MiMo and Solar are not in the repo (404).

**Patterns that survive every top prompt:**

1. **Identity first, in one line.** One line: name, maker, model, role. Claude Fable 5.1: "Here is some information about
   Claude and Anthropic's products." Muse Spark 1.3: "You are Muse, the user's personal agent." Codex GPT-6.1 Sol:
   "You are Codex, a coding agent based on GPT-6."
2. **Default stance before a ban list.** One stance calibrates thousands of unstated cases. Codex: "When you are unsure,
   ask the user for permission." Muse: "Default to helping. Decline only at concrete risk of serious harm." Cross-cutting:
   this is always the first rule before any prohibition.
3. **Environment block early.** Bionic: `<workspace>`, `<environment>`, `<available-skills>` before any rule. Muse:
   date/time/location before any rule. Antigravity: environment block before identity. The model cannot act on facts it
   doesn't have.
4. **Tools as usage policy, not API docs.** Every top prompt gives JSON schemas + when to call/not call + what good
   calls look like. Bionic embeds the full schema. Codex embeds the tool namespace. Antigravity embeds MCP + tool
   definitions as YAML.
5. **Safety in one tagged block, or its own section.** Claude: `<critical_child_safety_instructions>` and similar tags.
   Muse: alignment/discretion section. Bionic: "follow any explicit user requests over them." Repeating safety dilutes it.
6. **Explicit confirmation before irreversible actions.** Muse: confirm `git reset --hard`. Bionic: never revert changes
   you didn't make. Codex: ask permission when unsure.
7. **Brevity as discipline.** Muse: "short, clear replies; use reactions for emotional cues." Antigravity: "concise,
   direct, friendly." Claude: "match effort to the ask." DeepSeek ranks with 21 lines.
8. **Examples for judgment calls.** Worked examples with approved/rejected pairs and a one-line rationale. Claude does this
   for refusals. Codex for permission asks. Muse for tool choice.
9. **Persistence by restatement.** Claude re-injects rules on long conversations. Muse has compaction instructions.
   Codex: instructions survive summarization.
10. **Subagents and delegation are first-class.** Antigravity, Muse, Codex all define subagent orchestration.
    "Spawn one subagent per independent task" is universal across the makers.
11. **Skills are loaded, not baked in.** Muse, Bionic, Antigravity all use a `<available-skills>` block the model reads
    on demand, not a section of inline rules.

## 1. What a system prompt is

1. A maker-owned file that defines the model's persona, environment, tools, skills, safety, and behavior.
2. An agent rules file (rules/refs/GUIDELINES.md) is a user-owned file that adds project facts, commands, and boundaries. It is not a system prompt.
3. A system prompt is placed by the maker at position zero or as the first developer/message block. It has the highest authority in the stack.
4. A system prompt ships with the model; an agent rules file ships with the repo.

## 2. Structure of a system prompt (in order)

1. **Identity (1-2 lines).** Name, maker, model, role, purpose. No persona essays.
2. **Environment block.** Date, platform, workspace, available skills, MCP servers, connected accounts. The model acts on this.
3. **Default stance.** One paragraph: what it does by default, and the bar for refusal or escalation.
4. **Behavior rules, grouped by domain.** Identity, tools, tools-use policy, safety, tone, output format. One section per topic.
5. **Tools section.** Each tool: name, description (when to call / when not to call), and JSON or YAML schema. Usage policy over API docs.
6. **Subagents section.** How to delegate, what counts as independent work, what the coordinator does.
7. **Examples section.** Worked examples with approved/rejected pairs and a one-line rationale.
8. **Safety section.** One tagged block or one heading. Reference it elsewhere. Never repeat.
9. **Persistence section.** Compaction instructions: what survives, what gets dropped, how to restate.
10. **Output format rules.** Formatting constraints, banned strings, channel directives.

## 3. Behavior clause structure (same as agent rules)

1. One behavior clause per line, imperative, testable. "Ask before destructive or irreversible steps" beats "be careful".
2. Give each clause a testable trigger: when does it apply, what does it prevent.
3. Use MUST, NEVER, and ALWAYS for hard rules. Use "prefer" for soft ones.
4. Keep negated clauses positive: "Commit only staged files" reads better than "NEVER commit unstaged files".
5. One verb per action per file. Do not rotate "ask" and "request" for the same thing.
6. Pair behavior poles when needed: warm yet honest, bold yet reversible-first.
7. Ban failure modes by exact string. Named strings work where adjectives fail.
8. Cap ban lists. Ten named failure modes teach the model what to avoid; a hundred just produce paranoia.
9. No contradictions between sections. If two clauses collide, state which wins.
10. Declare precedence ladder: user instruction, project rules, skills, default.

## 4. Non-rule parts a system prompt cannot omit

1. **Identity** — one line. The model needs to know what it is before it follows rules.
2. **Environment** — workspace, date, platform, available tools/skills. The model cannot guess this.
3. **Tools** — schemas and usage policy. Without these the model cannot execute.
4. **Subagents** — how delegation works, when to use it. Without these the model does everything serially.
5. **Memory/persistence** — how memory works: what's injected, how to read/write, what survives compaction.
6. **Skills** — available skills and when to load them. The model doesn't reinvent SKILL.md.
7. **Examples** — worked examples for judgment calls. Without these, the model guesses.
8. **Safety** — one tagged block. The rest of the prompt references it.
9. **Output format** — formatting constraints the model must follow.
10. **Compaction instructions** — what survives, what gets dropped, how to restate rules.

## 5. Authority and precedence

1. Write an explicit precedence ladder. Example: user instruction, then project rules, then skills, then the maker's defaults. Rank conflicts get decided by the ladder.
2. State what stays in force across turns. Example: "User authorization persists across turns."
3. State what the model may not infer. Example: do not treat an implied rule in a skill file as a requirement to ask for approval.
4. Mark injected content as harness-owned when it is. Give it a trust marker: a named tag, and a statement that genuine injections never relax restrictions.
5. Explicit user instructions override the prompt. Say so in one line. This stops the model from fighting the human.
6. Do not restate user rules in the system prompt. The system prompt is the maker's; the rules file is the user's. Restating both makes two masters.

## 6. Examples

1. Ship worked examples for judgment calls, not for syntax. Use pairs: one approved, one rejected, one line of why.
2. Put two to fifteen examples behind any rule whose violation costs real quality (memory writes, refusals, tool choice).
3. Show format by demonstrating the format. A protocol with laws needs at least one full valid artifact in the prompt.
4. Examples teach disposition more than rules do. One approved pair calibrates more than three paragraphs of instruction.

## 7. Persistence (making it stick)

1. Do not rely on one injection at position zero. Plan for the same rules to restate near the newest message in long sessions.
2. Restate with variation. Same rule, different words, different slot. Repetition fixes meaning. Variation avoids habituation.
3. Put output-critical rules last in their block. Recency wins.
4. Wrap restatements in the same named tag every time. The tag becomes the authority marker.
5. Give the model a drift check. Example: ask it to compare the reply it is about to give against the reply a fresh instance would give with the same rules.
6. Anchor identity with a name. "You are still X" works better than "stay in character".
7. If your harness supports hooks, re-inject the rules on long sessions and after compaction.
8. For Kilo, the Stop hook in `kilo/enforce-rules-plugin/` re-injects rules after every turn.

## 8. Economy

1. Spend tokens where behavior pays: decision rules, examples, tool choice. Cut greeting text, mission statements, and duplicated praise.
2. Write tool definitions as usage policy, not API docs. Include when to call, when not to call, and what a good call looks like.
3. Remove a rule if you cannot name the failure it prevents.
4. Short prompts can rank. DeepSeek ranks with 21 lines. The 2026-11-14 Pareto frontier shows the cheapest ranked models are also the shortest prompts: MiMo V2.6 Flash and Solar Pro 4 hold their rank at a fraction of the token cost of the leaders.

## 9. Testing the prompt

1. Red-test the defaults. Give the model an underspecified task. Check that the stance carries it to the right behavior without extra rules.
2. Drift-test at length. Run 50+ turn sessions and probe for rule decay. Add a restatement where the decay shows.
3. Compaction-test. Force summarization mid-task. Check that the rules survive. If they do not, move them higher or carry them through the summary.
4. Conflict-test the ladder. Put a project rule against a skill rule. Check that precedence resolves it the way you wrote.
5. Change one thing per test run. Measure against the same probes each time.
6. Value-test against the Pareto frontier. A prompt that ranks on quality but costs more per task than a Pareto-optimal model needs a reason: either it wins on the signals that matter (confirmed success, steerability, bash reliability) or it is spending tokens the user does not get back.

## 10. Skeleton

```text
# Identity (1-2 lines: name, maker, model, role, purpose)
# Environment (date, platform, workspace, available skills, MCP servers)
# Default stance (1 paragraph: the pole and the bar for refusal or escalation)
# Behavior rules (one clause per line, testable, grouped by domain)
# Tools (JSON schemas + when to call / when not to call + good call examples)
# Subagents (how to delegate, what counts as independent, coordinator role)
# Memory and persistence (read/write policy, what survives compaction)
# Skills (available skills, when to load them)
# Output rules (formatting, banned strings, channels)
# Safety (one tagged block)
# Examples (worked judgment calls: approved/rejected/why)
```

## 11. Checklist

- Identity, date, and environment stated in the first lines.
- A default stance exists and has a concrete bar.
- Every behavior clause has a testable trigger.
- A precedence ladder resolves rank conflicts.
- Each banned failure mode uses an exact string.
- Judgment-call rules carry worked examples.
- Safety sits in one tagged block.
- Long sessions get planned restatements and trust markers.
- Every section earns its tokens.
- The prompt passed red, drift, compaction, conflict, and value tests.
