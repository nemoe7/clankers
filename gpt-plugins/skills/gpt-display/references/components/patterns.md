# Interaction and response patterns
Use these patterns only with documented APIs and task-grounded labels and values.
## Multi-select question with a custom answer
Use independent controlled checkboxes and shared state to support zero or more selections without inventing a multi-select component.

```jsx
{@body
const [selected, setSelected] = DIL.useState([]);
const [custom, setCustom] = DIL.useState("");

const toggle = (value, checked) => {
  setSelected(current =>
    checked
      ? [...current, value]
      : current.filter(item => item !== value)
  );
};

const submit = () => {
  GenUI.issueNewTurn(
    `Selected: ${selected.join(", ") || "None"}. Custom answer: ${custom.trim() || "None"}.`
  );
};
}
<col gap={2}>
  <text>Which options apply?</text>
  <checkbox
    label="Option A"
    checked={selected.includes("Option A")}
    onChange={checked => toggle("Option A", checked)}
  />
  <checkbox
    label="Option B"
    checked={selected.includes("Option B")}
    onChange={checked => toggle("Option B", checked)}
  />
  <label>Other answer</label>
  <input
    value={custom}
    onChange={setCustom}
    placeholder="Enter another answer"
  />
  <button onClick={submit}>Submit answers</button>
</col>
```

Include a recommended answer only when context supports it. Do not guess a `select.options` or `segmented-control.options` object schema.
## Single-choice question
Use a controlled `<radio-group>` with `<radio>` children. Do not invent a separate radio-label property.

```jsx
{@body
const [choice, setChoice] = DIL.useState("");
const [custom, setCustom] = DIL.useState("");

const submit = () => {
  const answer = choice === "Other" ? custom.trim() : choice;
  GenUI.issueNewTurn(`Selected: ${answer || "None"}.`);
};
}
<col gap={2}>
  <radio-group label="Choose one" value={choice} onChange={setChoice}>
    <radio value="Option A" />
    <radio value="Option B" />
    <radio value="Other" />
  </radio-group>
  {#if choice === "Other"}
    <label>Other answer</label>
    <input
      value={custom}
      onChange={setCustom}
      placeholder="Enter another answer"
    />
  {/if}
  <button onClick={submit}>Submit answer</button>
</col>
```
## Adjustable calculation
Keep local calculations local. Derive the result from shared state without submitting a new turn.

```jsx
{@body
const [quantity, setQuantity] = DIL.useState(2);
const unitPrice = 12;
const total = quantity * unitPrice;
}
<col gap={2}>
  <label>Quantity</label>
  <slider value={quantity} onChange={setQuantity} min={1} max={10} step={1} />
  <text>Total: {total}</text>
</col>
```
## Diagram
Make Mermaid source editable in `<CodeBlock>` only when the user needs to edit it; see [Mermaid](../../SKILL.md#3-mermaid).

```jsx
<CodeBlock editable={true} interactive={true} language="mermaid" model_previewable={true}>
flowchart TB
  A[Step] --> B{Decision?}
  B -->|Yes| C[Continue]
  B -->|No| D[Stop]
</CodeBlock>
```
## Standalone draft
```jsx
<WritingBlock id="12345" variant="email" subject="Project update">
Hello team,

Here is the completed update and the next step.

Best,
Name
</WritingBlock>
```
## Custom application
Use `<AppBlock>` only when native components cannot meet the requirement. Keep a useful static view if bindings or effects are unavailable.

```jsx
{@body
const [value, setValue] = DIL.useState("Ready");
}
<AppBlock
  app_block_id="status-view"
  bind={{ value, setValue }}
  language="html"
  title="Status"
>
<p id="status">Ready</p>
<script>
const output = document.querySelector("#status");

globalThis.__effect?.(() => {
  const value = globalThis.__bindings?.value;
  if (value && output) output.textContent = value;
});

output?.addEventListener("click", () => {
  globalThis.__bindings?.setValue?.("Updated");
});
</script>
</AppBlock>
```
