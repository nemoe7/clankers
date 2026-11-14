# Guidelines: writing a system prompt

Distilled from the system prompts of the top agent models on Arena Leaderboards on 2026-09-11, refreshed against the
top 10 Agent Arena models and the Pareto frontier on 2026-11-14.

## 0. What the 2026-11-14 refresh found

The top of the Agent Arena board has not changed its shape since September: Anthropic and OpenAI still hold the top
ranks, Google and Meta sit just behind, and the Pareto frontier is defined by a handful of value leaders. What changed
is the density of the prompts and the spread of the patterns.

**Top 10 Agent Arena (Best Overall, latest published snapshots, 2026-11):**
Claude Opus 5.5 (Max), GPT-6.1 Sol (Max), Claude Fable 5.1 (Max), GPT-6 Astra (Max), Gemini 4 Argon (High),
Claude Sonnet 5.5 (Max), GPT-6 Sol (Max), Claude Opus 5 (Max), Claude Fable 5 (High), GPT-5.6 Sol (xHigh).

**Pareto frontier (Best Overall):** Claude Opus 5.5 (Max), GPT-6.1 Sol (Max), MiMo V2.6 Pro, GPT-6 Luna (Max),
MiMo V2.6 Flash, Solar Pro 4.

**Patterns that survived the refresh and now sit in this file:**

1. **Identity first, one line.** Every top prompt opens with name, maker, and role before any rule. Claude Opus 5.5,
   Codex GPT-6.1 Sol, Muse, and Antigravity all do this. The identity line is the anchor the rest hangs on.
2. **A default stance before a ban list.** Claude Opus 5.5: "Default to helping. Decline only at concrete risk of
   serious harm." Codex: effort-setting table. Muse: truth, beauty, respect, fun, connection, curiosity, due
   diligence. One stance calibrates thousands of cases the prompt never lists.
3. **Safety in one tagged block, referenced, never repeated.** Claude keeps child safety, weapons, and IP in
   `<critical_child_safety_instructions>` and similar named tags. Antigravity and Muse keep boundaries in their own
   sections. Repeating safety text dilutes it.
4. **Explicit confirmation before irreversible actions.** Muse Code: confirm `git reset --hard`. Antigravity CLI:
   confirm destructive git commands. LM Studio Bionic: request read/write access before touching external paths.
   This is the single most common "ask vs act" rule across all five makers.
5. **Tool definitions as usage policy, not API docs.** Every top prompt lists when to call and when not to call.
   Muse Code and Antigravity both spell out "never poll long-running processes" and "use background task management".
6. **Brevity as a discipline, not a default.** Muse: "short, clear replies; use reactions for emotional cues."
   Antigravity: "concise, direct, friendly." Claude: "match effort to the ask." DeepSeek still ranks with 21 lines.
   Short prompts can rank.
7. **Examples for judgment calls, not syntax.** Claude ships worked examples with approved/rejected pairs and a
   one-line rationale. Muse and Antigravity do the same for tool choice and formatting.
8. **Persistence by restatement, not by length.** Claude re-injects rules on long sessions and after compaction.
   Muse manages conversation state across turns. The rule that survives is the one restated near the newest message.
9. **Subagents and delegation are first-class.** Antigravity, Muse Code, and Muse agent all define subagent
   orchestration as a core capability, not an add-on.
10. **No AGENTS.md-specific language in a system prompt.** A system prompt is maker-owned and persona-driven. An
    agent rules file is user-owned and fact-driven. They share structure; they do not share voice. See
    [rules/refs/GUIDELINES.md](../rules/refs/GUIDELINES.md) for the rules file standard.

## 1. Reader and harness

1. Write for one reader: the model. It cannot ask you what you meant. Remove every ambiguous word.
2. Know where the harness puts your text. System prompt, developer message, tool definition, and user
   message have different authority. Put each rule in the slot with the authority it needs.
3. List the environment early. State the date, the platform, the tools, and the knowledge cutoff.
   The model cannot act on facts it does not have.

## 2. Structure

1. Start with identity in one line: name, maker, role. ("You are Codex, an agent based on GPT-6.")
2. Order sections from general to specific: identity, product facts, policy, tone, behavior, tools,
   output format.
3. Use one section per topic. Name every section with a heading or a tag. The model cites structure
   when it resolves conflicts.
4. Use XML-style tags for blocks with special authority (safety, reminders). Use Markdown headings
   for the rest. Do not mix more than two marking systems.
5. Keep safety in one tagged block. Reference it elsewhere. Do not repeat it.

## 3. Authority and precedence

1. Write an explicit precedence ladder. Example: user instruction, then project rules, then skills,
   then defaults. Rank conflicts get decided by the ladder.
2. State what stays in force across turns. Example: "User authorization persists across turns."
3. State what the model may not infer. Example: do not treat an implied rule in a skill file as a
   requirement to ask for approval.
4. Mark injected content as harness-owned when it is. Give it a trust marker: a named tag, and a
   statement that genuine injections never relax restrictions.

## 4. Behavior rules

1. Set a default stance first. "Default to helping. Decline only at concrete risk of serious harm."
   One stance calibrates thousands of cases you did not list.
2. Give each rule a testable trigger. "Search when a fact may have changed" beats "be current".
   "Ask only before destructive or irreversible steps" beats "be careful".
3. Write rules as pairs of poles when the target behavior is a balance: warm yet honest, bold yet
   reversible-first. One pole alone collapses to an extreme.
4. Ban failure modes by exact string. List the phrases the model may not write, the framings it may
   not use, the moves it may not make. Named strings work where adjectives fail.
5. Cap the ban lists. Select the failures you actually see. A long ban list teaches the model to
   sound like the ban list.

## 5. Examples

1. Ship worked examples for judgment calls, not for syntax. Use pairs: one approved, one rejected,
   one line of why.
2. Put two to fifteen examples behind any rule whose violation costs real quality (memory writes,
   refusals, tool choice).
3. Show format by demonstrating the format. A protocol with laws needs at least one full valid
   artifact in the prompt.

## 6. Persistence (making it stick)

1. Do not rely on one injection at position zero. Plan for the same rules to restate near the newest
   message in long sessions.
2. Restate with variation. Same rule, different words, different slot. Repetition fixes meaning.
   Variation avoids habituation to one string.
3. Put output-critical rules last in their block. Recency wins.
4. Wrap restatements in the same named tag every time. The tag becomes the authority marker.
5. Give the model a drift check. Example: ask it to compare the reply it is about to give against
   the reply a fresh instance would give with the same rules.
6. Anchor identity with a name. "You are still X" works better than "stay in character".
7. If your harness supports hooks, re-inject the rules on long sessions and after compaction.
   (For Kilo, see `kilo/enforce-rules-plugin/`.)

## 7. Economy

1. Spend tokens where behavior pays: decision rules, examples, tool choice. Cut greeting text,
   mission statements, and duplicated praise.
2. Write tool definitions as usage policy, not API docs. Include when to call, when not to call,
   and what a good call looks like.
3. Remove a rule if you cannot name the failure it prevents.
4. Short prompts can rank. DeepSeek ranks with 21 lines. Add a section only when the defaults fail
   you in testing. The 2026-11-14 Pareto frontier shows the cheapest ranked models are also the shortest
   prompts: MiMo V2.6 Flash and Solar Pro 4 hold their rank at a fraction of the token cost of the leaders.

## 8. Testing the prompt

1. Red-test the defaults. Give the model an underspecified task. Check that the stance carries it to the
   right behavior without extra rules.
2. Drift-test at length. Run 50+ turn sessions and probe for rule decay. Add a restatement where the
   decay shows.
3. Compaction-test. Force summarization mid-task. Check that the rules survive. If they do not,
   move them higher or carry them through the summary.
4. Conflict-test the ladder. Put a project rule against a skill rule. Check that precedence resolves
   it the way you wrote.
5. Change one thing per test run. Measure against the same probes each time.
6. Value-test against the Pareto frontier. A prompt that ranks on quality but costs more per task than
   a Pareto-optimal model needs a reason: either it wins on the signals that matter (confirmed success,
   steerability, bash reliability) or it is spending tokens the user does not get back.

## 9. Skeleton

```text
# Identity (1-2 lines: name, maker, role, date, environment)
# Default stance (1 paragraph: the pole and the bar for refusal or escalation)
# Behavior rules (each with a testable trigger, grouped by domain)
# Tools and add-ons (usage policy, precedence ladder, batching rules)
# Output rules (format, channels, banned strings)
# Safety (one tagged block)
# Examples (worked judgment calls)
# Persistence contract (what persists, trust markers for reinjection)
```

## 10. Checklist

- Identity, date, and environment stated in the first lines.
- A default stance exists and has a concrete bar.
- Every behavior rule has a testable trigger.
- A precedence ladder resolves rank conflicts.
- Each banned failure mode uses an exact string.
- Judgment-call rules carry worked examples.
- Safety sits in one tagged block.
- Long sessions get planned restatements and trust markers.
- Every section earns its tokens.
- The prompt passed red, drift, compaction, and conflict tests.
