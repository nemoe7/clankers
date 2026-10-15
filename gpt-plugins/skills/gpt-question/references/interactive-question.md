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

Use `date-picker`, `slider`, `segmented-control`, or another supported control when its data type fits. Give their choice groups the same custom option and input.

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
const canSubmit = Boolean(choice || customAnswer.trim());
}
<form
  gap={3}
  onSubmit={() => GenUI.issueNewTurn([
    "Question: What would you like help with?",
    `Selected option: ${choice || "(none)"}`,
    `Custom answer: ${customAnswer.trim() || "(not provided)"}`
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
  </radio-group>
  <textarea
    value={customAnswer}
    onChange={setCustomAnswer}
    placeholder="Custom answer (optional)"
    rows={3}
  />
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
const toggleOption = (option, checked) => {
  setSelected(
    checked
      ? [...selected, option]
      : selected.filter(item => item !== option)
  );
};
const canSubmit = selected.length > 0 || Boolean(customAnswer.trim());
}
<form
  gap={3}
  onSubmit={() => GenUI.issueNewTurn([
    "Question: What would you like help with?",
    "Selected options:",
    ...(selected.length
      ? selected.map(option => `- ${option}`)
      : ["- None selected"]),
    `Custom answer: ${customAnswer.trim() || "(not provided)"}`
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
  <textarea
    value={customAnswer}
    onChange={setCustomAnswer}
    placeholder="Custom answer (optional)"
    rows={3}
  />
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
