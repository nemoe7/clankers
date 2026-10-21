# Interactive Question

## Purpose

Collect user input in the conversation. Prefer structured controls to plain-text questions when they improve answer quality or make a response easier.

Use DIL components and `GenUI` actions exposed by the current environment. Do not invent APIs or assume DIL maps directly to the private native Intelligent UI component library.

## When to use

Activate when user input must:

- Resolve ambiguity that materially affects the answer.
- Choose between approaches or options.
- Clarify requirements, preferences, constraints, or priorities.
- Collect related values before completing a task.
- Confirm a necessary decision.
- Select multiple answers or answer outside available choices.

Use existing context first. Do not ask unnecessary questions. Make a reasonable assumption when it creates no material risk or change to the requested outcome.

## Required question UI

Every form MUST:

1. State the question clearly.
2. Present relevant presets when useful.
3. Give every choice group a selectable `Custom answer` option with its own input, shown beside or below the group while selected, never as a form-level block.
4. Include a submit button.
5. Send selected and custom answers through `GenUI.issueNewTurn()`.
6. Submit enough context to identify the question and interpret answers.
7. Preserve exact custom text except for boundary whitespace.
8. Allow custom-only answers when the question's rules permit, and count a selected custom option toward its selection limit.
9. Avoid unrelated fields and unnecessary decoration.
10. Use only supported component properties, state hooks, callbacks, and host actions.

Label each group's option **Custom answer** and its input **Custom answer (optional)** unless required. Each question owns its custom option, input, state and validation.

## Choose the correct controls

### Single selection

Use `radio-group` with `radio` children for one answer from a short list, and add the group's `Custom answer` radio beside the presets. Use `select` only when its option schema is known and fits the choices.

### Multiple selection

Use independent `checkbox` controls for several answers, and add the group's `Custom answer` checkbox beside the presets. Store selected values in state and update them when a checkbox changes.

### Custom answer

Use `textarea` for longer or open-ended answers; use `input` for a short expected answer. The input appears with its group while the custom option is selected and leaves on deselect. Deselect keeps the text in state yet excludes it from submission. A selected custom option counts toward its question's limit, and custom-only answers submit when the rules allow.

### Other input types

Use `date-selector`, `slider`, `segmented-control`, or another supported control when its data type fits. Give their choice groups the same custom option and input.

For several independent values, group related controls in one `form` and submit answers together.

## Recommended answer policy

Recommend an option only when it clearly fits stated goals, constraints, or evidence better than alternatives. When recommending:

- Mark it **Recommended**.
- Give a brief reason when it helps an informed choice.
- Do not imply selection.
- Do not prevent another selection.
- Do not select it automatically unless the task explicitly calls for a default.

Do not recommend an option only to make a form look helpful. Omit recommendations for preference-neutral questions.

## Submission behavior

Use the documented DIL interaction contract:

- Declare state with supported hooks in a top-level, unconditional `{@body ...}` block.
- Bind controlled values through documented `value` and `onChange` properties.
- Use `checked` and `onChange` for controlled checkboxes.
- Use `form.onSubmit` for submission.
- Call `GenUI.issueNewTurn()` from the actual submit interaction.
- Callbacks receive new values, not DOM events.
- Do not claim submission succeeded before the host reports success.

The submitted message MUST include:

- The original question or a clear identifier.
- Every selected option.
- The custom answer when provided.
- Other entered values needed for interpretation.

Do not omit custom text with selected presets. Do not replace selected options with custom text. Exclude a group's custom text while its custom option is deselected.

## Reference pattern: single selection plus custom answer

Adapt this pattern to the actual question and options.

```jsx
{@body
const [choice, setChoice] = DIL.useState("");
const [customAnswer, setCustomAnswer] = DIL.useState("");
const options = [
  "Explain a concept",
  "Compare options",
  "Create a plan"
];
const customChosen = choice === "Custom answer";
const canSubmit = Boolean(choice) && (!customChosen || Boolean(customAnswer.trim()));
}
<form
  gap={3}
  onSubmit={() => GenUI.issueNewTurn([
    "Question: What would you like help with?",
    `Selected option: ${choice || "(none)"}`,
    ...(customChosen ? [`Custom answer: ${customAnswer.trim()}`] : [])
  ].join("\n"))}
>
  <radio-group
    value={choice}
    onChange={setChoice}
    label="Choose one"
  >
    {#each options as option}
      <radio value={option}>{option}</radio>
    {/each}
    <radio value="Custom answer">Custom answer</radio>
  </radio-group>
  {#if customChosen}
    <textarea
      value={customAnswer}
      onChange={setCustomAnswer}
      placeholder="Custom answer"
      rows={3}
    />
  {/if}
  <button
    block
    submit={true}
    disabled={!canSubmit}
    label="Submit answer"
  />
</form>
```

## Reference pattern: multiple selections plus custom answer

Use this pattern when the user can select several options.

```jsx
{@body
const [selected, setSelected] = DIL.useState([]);
const [customAnswer, setCustomAnswer] = DIL.useState("");
const options = [
  "Explain a concept",
  "Compare options",
  "Create a plan",
  "Troubleshoot a problem"
];
const customChosen = selected.includes("Custom answer");
const toggleOption = (option, checked) => {
  setSelected(
    checked
      ? [...selected, option]
      : selected.filter(item => item !== option)
  );
};
const canSubmit = selected.length > 0 && (!customChosen || Boolean(customAnswer.trim()));
}
<form
  gap={3}
  onSubmit={() => GenUI.issueNewTurn([
    "Question: What would you like help with?",
    "Selected options:",
    ...(selected.length
      ? selected.map(option => `- ${option}`)
      : ["- None selected"]),
    ...(customChosen ? [`Custom answer: ${customAnswer.trim()}`] : [])
  ].join("\n"))}
>
  {#each options as option}
    <checkbox
      checked={selected.includes(option)}
      onChange={checked => toggleOption(option, checked)}
    >
      {option}
    </checkbox>
  {/each}
  <checkbox
    checked={customChosen}
    onChange={checked => toggleOption("Custom answer", checked)}
  >
    Custom answer
  </checkbox>
  {#if customChosen}
    <textarea
      value={customAnswer}
      onChange={setCustomAnswer}
      placeholder="Custom answer"
      rows={3}
    />
  {/if}
  <button
    block
    submit={true}
    disabled={!canSubmit}
    label="Submit answers"
  />
</form>
```

## Reference pattern: mixed selection limits in one form

Use this pattern when one form carries questions with different selection counts. Each question keeps its own state, custom option, custom text and validation, and the submit button waits for every question.

```jsx
{@body
const [select, setPick] = DIL.useState("");
const [selectCustom, setPickCustom] = DIL.useState("");
const [pair, setPair] = DIL.useState([]);
const [pairCustom, setPairCustom] = DIL.useState("");
const [any, setAny] = DIL.useState([]);
const [anyCustom, setAnyCustom] = DIL.useState("");
const selectOptions = ["Speed", "Cost"];
const pairOptions = ["Retry", "Alert"];
const anyOptions = ["Logs", "Metrics"];
const selectCustomChosen = select === "Custom answer";
const pairCustomChosen = pair.includes("Custom answer");
const anyCustomChosen = any.includes("Custom answer");
const toggle = (list, setList) => (option, checked) => {
  setList(
    checked
      ? [...list, option]
      : list.filter(item => item !== option)
  );
};
const togglePair = toggle(pair, setPair);
const toggleAny = toggle(any, setAny);
const selectValid = Boolean(select) && (!selectCustomChosen || Boolean(selectCustom.trim()));
const pairValid = pair.length === 2 && (!pairCustomChosen || Boolean(pairCustom.trim()));
const anyValid = any.length >= 1 && (!anyCustomChosen || Boolean(anyCustom.trim()));
const canSubmit = selectValid && pairValid && anyValid;
}
<form
  gap={3}
  onSubmit={() => GenUI.issueNewTurn([
    "Question 1, exactly one: Which goal leads?",
    `Selected option: ${select || "(none)"}`,
    ...(selectCustomChosen ? [`Custom answer: ${selectCustom.trim()}`] : []),
    "Question 2, exactly two: Which safeguards run?",
    "Selected options:",
    ...pair.map(option => `- ${option}`),
    ...(pairCustomChosen ? [`Custom answer: ${pairCustom.trim()}`] : []),
    "Question 3, one or more: Which signals stay on?",
    "Selected options:",
    ...any.map(option => `- ${option}`),
    ...(anyCustomChosen ? [`Custom answer: ${anyCustom.trim()}`] : [])
  ].join("\n"))}
>
  <radio-group
    value={select}
    onChange={setPick}
    label="Choose exactly one"
  >
    {#each selectOptions as option}
      <radio value={option}>{option}</radio>
    {/each}
    <radio value="Custom answer">Custom answer</radio>
  </radio-group>
  {#if selectCustomChosen}
    <textarea
      value={selectCustom}
      onChange={setPickCustom}
      placeholder="Custom answer"
      rows={2}
    />
  {/if}
  {#each pairOptions as option}
    <checkbox
      checked={pair.includes(option)}
      onChange={checked => togglePair(option, checked)}
    >
      {option}
    </checkbox>
  {/each}
  <checkbox
    checked={pairCustomChosen}
    onChange={checked => togglePair("Custom answer", checked)}
  >
    Custom answer
  </checkbox>
  {#if pairCustomChosen}
    <textarea
      value={pairCustom}
      onChange={setPairCustom}
      placeholder="Custom answer"
      rows={2}
    />
  {/if}
  {#each anyOptions as option}
    <checkbox
      checked={any.includes(option)}
      onChange={checked => toggleAny(option, checked)}
    >
      {option}
    </checkbox>
  {/each}
  <checkbox
    checked={anyCustomChosen}
    onChange={checked => toggleAny("Custom answer", checked)}
  >
    Custom answer
  </checkbox>
  {#if anyCustomChosen}
    <textarea
      value={anyCustom}
      onChange={setAnyCustom}
      placeholder="Custom answer"
      rows={2}
    />
  {/if}
  <button
    block
    submit={true}
    disabled={!canSubmit}
    label="Submit answers"
  />
</form>
```

These are reference patterns. Verify each component property against the active DIL contract before varying one.

## Question design

- Ask one clear question per form unless several questions collect independent values for one task.
- Use short, distinct answer labels.
- Include only options that resolve the question.
- Use neutral wording; do not steer toward an unsupported answer.
- Explain an important trade-off briefly.
- Keep custom text optional unless necessary.
- Do not use a form only to make an ordinary explanation interactive.
- Do not request information already available in the conversation.
- Preserve relevant prior constraints in a follow-up.
- Keep each form compact and usable on narrow screens.
- Use theme-safe styling and clear labels.
- Do not rely on color alone for a recommendation or selection.

## Final checks

Before returning a question form, verify that:

1. Controls match allowed answer cardinality.
2. Every choice group carries its own custom option, and inputs appear only while selected.
3. State and callbacks use documented shapes.
4. Submit includes every selected option and custom text.
5. The message identifies the answered question.
6. The submit button has a meaningful label.
7. The form does not require a preset when custom text alone is valid.
8. A recommendation appears only when justified.
9. The form collects only task-relevant information.
10. No unsupported component, property, callback, or host action appears.
11. Each question validates alone, and submit stays disabled until all are valid.
12. A deselected custom option contributes no stale text.

The skill makes questions easier to answer. It does not force a graphical interface into every response.
