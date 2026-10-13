# Interactive Question

## Purpose

Use interactive UI to collect user input inside the conversation. Prefer structured controls over plain-text questions when they improve answer quality or make the user's response easier.

Use the DIL components and `GenUI` actions exposed by the current environment. Do not invent APIs or assume that DIL maps directly to the private native Intelligent UI component library.

## When to use

Activate this skill whenever the assistant needs user input to:

- Resolve ambiguity that materially affects the answer.
- Choose between approaches or options.
- Clarify requirements, preferences, constraints, or priorities.
- Collect several related values before completing a task.
- Confirm a decision when confirmation is necessary.
- Let the user select multiple answers or provide an answer outside the available choices.

Do not ask unnecessary questions. Use existing context first. Make a reasonable assumption when it does not create a material risk or change the requested outcome.

## Required question UI

Every question form MUST:

1. State the question clearly.
2. Present relevant preset answers when useful.
3. Always display a custom-answer text field. Do not hide this field behind an "Other" checkbox or selection.
4. Include a submit button.
5. Send the user's selected answers and custom answer to the conversation through `GenUI.issueNewTurn()`.
6. Include enough context in the submitted message to identify the question and interpret the answers.
7. Preserve the user's exact custom text, except for trimming whitespace at its boundaries.
8. Allow custom text without a preset selection unless the task genuinely requires a preset selection.
9. Avoid unrelated fields and unnecessary visual decoration.
10. Use only supported component properties, state hooks, callbacks, and host actions.

Label the free-text field **Custom answer (optional)** unless the user must provide custom text. Keep it visible regardless of the selected options.

## Choose the correct controls

### Single selection

Use `radio-group` with `radio` children when the user should select one answer from a short list.

Use `select` only when its option schema is known and appropriate for the available choices.

### Multiple selection

Use independent `checkbox` controls when the user can select several answers.

Store the selected values in state. Update the selection when a checkbox changes.

### Custom answer

Use `textarea` for longer or open-ended answers. Use `input` when the expected answer is short.

The custom-answer field MUST remain visible, whether the user selects zero, one, or several preset answers.

### Other input types

Use `date-picker`, `slider`, `segmented-control`, or other supported controls when their data types fit the question. Include the custom-answer field alongside them.

For forms that need several independent values, group the related controls in one `form` and submit the answers together.

## Recommended answer policy

Include a recommendation only when one option clearly fits the user's stated goals, constraints, or available evidence better than the alternatives.

When a recommendation is warranted:

- Mark the relevant option with **Recommended**.
- Give a brief reason when it helps the user make an informed choice.
- Do not imply that the user selected that option.
- Do not prevent the user from choosing another option.
- Do not select it automatically unless the task explicitly calls for a default.

Do not mark an option as recommended merely to make the form look helpful. For preference-neutral questions, omit the recommendation.

## Submission behavior

Use the documented DIL interaction contract:

- Declare state with supported hooks inside a top-level, unconditional `{@body ...}` block.
- Bind controlled values through the documented `value` and `onChange` properties.
- Use `checked` and `onChange` for controlled checkboxes.
- Use `form.onSubmit` to handle submission.
- Call `GenUI.issueNewTurn()` from the actual submit interaction.
- Callbacks receive new values, not DOM events.
- Do not claim that submission succeeded before the host reports success.

The submitted message MUST include:

- The original question or a clear identifier for it.
- Every selected option.
- The custom answer when the user provided one.
- Any other entered values needed to interpret the response.

Do not omit the custom answer when preset options are also selected. Do not replace the selected options with the custom answer.

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

These are reference patterns. Verify each component property against the active DIL contract before using a variation.

## Question design

- Ask one clear question per form unless several questions are needed to collect independent values for the same task.
- Use short, distinct answer labels.
- Include only options that help resolve the question.
- Use neutral wording. Do not steer the user toward an unsupported answer.
- Explain any important trade-off briefly.
- Keep custom text optional unless it is necessary.
- Do not use a form just to make an ordinary explanation interactive.
- Do not request information already available in the conversation.
- Preserve relevant prior constraints when asking a follow-up question.
- Make each form compact and usable on narrow screens.
- Use theme-safe styling and clear labels.
- Do not rely on color alone to identify a recommendation or selection.

## Final checks

Before returning a question form, verify that:

1. The controls match the allowed answer cardinality.
2. The custom-answer field is visible without any selection.
3. State and callbacks use the correct documented shapes.
4. The submit action includes every selected option and the custom text.
5. The message identifies the question being answered.
6. The submit button has a meaningful label.
7. The form does not require a preset selection when custom text alone is valid.
8. A recommendation appears only when justified.
9. The form collects only information that matters to the task.
10. No unsupported component, property, callback, or host action appears.

The purpose of this skill is to make user questions easier to answer, not to force a graphical interface into every response.