---
name: gpt-display
description: Exhaustive reference for supported response representations, DIL components, data shapes, citations, media, charts, maps, interactions, and Mermaid diagrams. Use when choosing or constructing a structured or visual response.
---

# GPT Display

## 1. Purpose and limits

Select the simplest representation that fully serves the information need. Use Markdown by default. Use a specialized component when it improves comprehension, comparison, source traceability, geographic context, navigation, or interaction.

This skill inventories the documented response contract available to the assistant and the diagram families listed in the official Mermaid syntax reference. It is exhaustive against those published inventories, not against unknown future components, arbitrary HTML, every external chart library, or every possible visual design. The active runtime can support fewer features than the published Mermaid release.

Never invent component names, properties, callbacks, data fields, references, URLs, coordinates, metrics, or host actions. A valid source example does not prove that the target client rendered it successfully.

## 2. Choose the representation

| Need | Preferred method | Use it when |
|---|---|---|
| Explanation, summary, result, or caveat | Markdown prose | Text communicates the result clearly. |
| Ordered steps or a simple collection | Markdown list or `<list>` | The reader follows a sequence or scans items. |
| Exact row-and-column comparison | Markdown table or `<table>` | Readers must compare named fields. |
| Inline emphasis, status, or equation | Markdown or text components | A local formatting change helps interpretation. |
| Related content in a composed layout | `<box>`, `<row>`, `<col>`, `<grid>`, `<card>` | Hierarchy or placement improves scanning. |
| A navigable set of options | `<carousel>` | Items are alternatives or media cards. |
| A process or decision path | Mermaid flowchart | Branches, paths, or dependencies matter. |
| Work divided by owners | Mermaid swimlanes | Cross-team ownership and handoffs matter. |
| Messages among participants over time | Mermaid sequence | Order of messages matters. |
| Code structure | Mermaid class diagram | Types and their relationships matter. |
| Lifecycle and transitions | Mermaid state diagram | Legal states and transitions matter. |
| Database entities | Mermaid ER diagram | Entities, attributes, and cardinalities matter. |
| Software architecture | Mermaid C4, architecture, block, or flowchart | Choose the level and semantics that match the question. |
| Quantitative trend or category comparison | `<Chart>` | Numerical patterns matter more than exact row lookup. |
| Weighted movement between categories | Mermaid Sankey | Flow magnitude matters. |
| Numerical data as line or bar | Mermaid XY chart, or `<Chart>` | Use native charts when their schema and rendering are suitable. |
| Part-to-whole composition | `<Chart>` pie, Mermaid pie, or treemap | Use pie for few parts and treemap for hierarchical parts. |
| Geographic locations and routes | `<MapWidgetV2>` | Real places or ordered travel stops matter. |
| A photograph, media collection, or video | `<AsyncImage>`, `<AsyncImageGroup>`, `<AsyncVideo>` | Visual evidence or context adds value. |
| Named entity or source navigation | `<Entity>`, `<Link>`, or citation components | The entity or source should be linked or cited. |
| User-adjustable answer | Input components plus state | Input changes displayed values or causes a real action. |
| Editable or previewable code | `<CodeBlock>` | Its editor or preview adds value over a Markdown fence. |
| Copyable standalone writing | `<WritingBlock>` | The user needs a complete draft to reuse. |
| Bespoke interactive visualization | `<AppBlock>` | No standard component can meet the requirement. |

Do not add cards, badges, icons, diagrams, charts, maps, images, or controls only for decoration. Do not use a chart when exact data values are the main requirement. Do not use an image to replace required structured, editable, or executable content.

## 3. Markdown, DIL syntax, and expressions

### 3.1 Markdown

Supported Markdown includes headings, paragraphs, bold, italic, underline, strikethrough, links, tables, ordered and unordered lists, checklists, code, and math. Prefer Markdown for ordinary prose. Do not switch to a component when Markdown is clearer and equivalent.

### 3.2 Component syntax

Components use tag syntax. Lowercase names identify ordinary components. Uppercase names identify server-resolved components. Close every component and directive.

- Use only documented component names and properties.
- Put expressions inside `{...}`. Use quoted strings for text-valued props.
- Use `<></>` to group elements without an extra layout container.
- Use `<escape>...</escape>` only for literal text that could otherwise be parsed as DIL syntax. If the content needs an internal `</escape>`, use the documented `char="\\"` escape form.
- Use `{@body ...}` for top-level state and hook declarations.
- Use `{#if ...}{:else if ...}{:else}{/if}` for conditional rendering and `{#each items as item, i}{/each}` for repeated rendering.
- Preserve source text inside `<CodeBlock>`, `<AppBlock>`, and `<WritingBlock>` according to each component's raw-content rules.
- Use `String.raw` for LaTeX strings that contain backslash commands.
- One spacing unit equals four points. Where supported, spacing values accept a number, `px`, `rem`, `pt`, `%`, or `0`.

### 3.3 Supported DIL hooks

Call only these documented hooks, and only through a top-level, unconditional `{@body ...}` declaration: `DIL.useBreakpoint`, `DIL.useCallback`, `DIL.useEffect`, `DIL.useId`, `DIL.useMemo`, `DIL.useRef`, `DIL.useState`, `DIL.useTheme`.

Do not call hooks in markup loops, conditions, or callbacks. Keep hook order stable. A callback receives the new value from a supported input, not a DOM event.

### 3.4 Shared layout properties

These properties apply only to `<box>`, `<col>`, `<flow-item>`, `<pressable>`, `<row>`, and `<form>`: `align`, `background`, `border`, `clip`, `direction`, `disableAutoSpacing`, `flex`, `flush`, `gap`, `height`, `justify`, `key`, `maxHeight`, `maxWidth`, `minHeight`, `minWidth`, `padding`, `radius`, `role`, `scrollable`, `theme`, `width`, `wrap`.

Do not assume a property belongs to a component unless the component reference lists it.

### 3.5 Theme-safe colors

The host renders one output in a light theme and in a dark theme. The reader chooses the theme, and the output cannot know the choice. Write every color so both themes read correctly.

- Prefer the `theme` property and the `variant` values a component documents. A semantic value follows the active theme; a literal value does not.
- Never write a literal hex, `rgb()`, `hsl()`, or named CSS color for text, a background, a border, or a divider. A literal that reads on white disappears on black, and the reverse.
- Omit `color` to take the inherited foreground. Inherited text is correct in both themes by construction.
- Use `DIL.useTheme` only when a literal color is the only way to carry the meaning. Read the theme once in a top-level `{@body ...}` declaration, and supply one value per theme. Never call `DIL.useTheme` inside a loop, a condition, or a callback.
- Keep a contrast ratio of at least 4.5 to 1 for body text and 3 to 1 for large text, in both themes. Check the pair you ship, not the theme you previewed.
- Carry state with more than color. A status that only a color names is unreadable to a color-blind reader and invisible in a low-contrast theme.
- Do not tint a surface to signal emphasis. Use `variant`, `weight`, `size`, or a `<divider>`.
- For a chart, take the palette the chart component supplies. Declare an explicit series color only when the series must match a color used elsewhere in the same output, and then declare one value per theme.
- For a Mermaid diagram, keep the default theme. A `%%{init: {'theme': ...}}%%` override pins one theme and breaks the other.
- Do not set `background` on a container to fake a surface. A card or a box variant follows the theme; a literal background does not.

When a design needs a color the theme cannot supply, state the constraint in the output and ship the nearest theme-safe value. Never ship a literal that only one theme renders correctly.

## 4. Text and inline components

| Component | Supported properties | Use |
|---|---|---|
| `<title>` | `color`, `italic`, `maxLines`, `size`, `strong`, `tabularNums`, `textAlign`, `truncate`, `weight`, `width` | Heading or prominent value. |
| `<text>` | `color`, `highlight`, `inline`, `italic`, `lineThrough`, `maxLines`, `minLines`, `preserveWhitespace`, `size`, `strong`, `tabularNums`, `textAlign`, `truncate`, `underline`, `weight`, `width` | General text. |
| `<caption>` | `color`, `maxLines`, `textAlign`, `truncate`, `weight` | Secondary context. |
| `<label>` | `color`, `htmlFor`, `size`, `textAlign`, `truncate`, `weight`, `width` | Input or field label. |
| `<badge>` | `color`, `label`, `maxWidth`, `onHover`, `padding`, `pill`, `size`, `variant`, `weight` | One compact status or category. |
| `<bold>` | `weight` | Local emphasis. |
| `<italic>` | None listed | Italic text. |
| `<underline>` | None listed | Underlined text. |
| `<strikethrough>` | None listed | Struck-through text. |
| `<code>` | None listed | Inline code. |
| `<blockquote>` | None listed | Quoted or indented content. Accepts generic children. |
| `<math>` | `block`, `value` | Mathematical expression. |

Use restrained emphasis. Do not use a badge as a heading, an ordinary field label, or a repeated decoration. Do not use color alone to communicate a status.

## 5. Layout components

### 5.1 Component and property catalog

| Component | Additional properties | Use |
|---|---|---|
| `<box>` | `aspectRatio`, `columnGap`, `maxSize`, `minSize`, `rowGap`, `size` plus shared layout properties | General container. |
| `<col>` | `aspectRatio`, `columnGap`, `maxSize`, `minSize`, `size` plus shared layout properties | Vertical layout. |
| `<row>` | `aspectRatio`, `maxSize`, `minSize`, `rowGap`, `size` plus shared layout properties | Horizontal layout. |
| `<card>` | `background`, `disableAutoSpacing`, `gap`, `height`, `justify`, `padding`, `shadow`, `size`, `theme`, `variant`, `width` | Group related content. |
| `<grid>` | `columnGap`, `columns`, `gap`, `minChildWidth`, `rowGap`, `rows` | Grid of items. Direct children use `<grid-item>`. |
| `<grid-item>` | `rowSpan`, `span` | Grid child. |
| `<flow>` | `columns`, `gap`, `layout`, `rows` | Adaptive arrangement. Direct children use `<flow-item>`. |
| `<flow-item>` | Shared layout properties plus `aspectMode`, `aspectRatio`, `rowSpan`, `span` | Flow child. |
| `<divider>` | `color`, `flush`, `size`, `spacing` | Separate sections. |
| `<spacer>` | `minSize` | Intentional empty space. |
| `<pressable>` | Shared layout properties plus `aspectRatio`, `disabled`, `inline`, `maxSize`, `minSize`, `onClick`, `size`, `tooltip` | Clickable surface. |
| `<carousel>` | `activeIndex`, `flush`, `gap`, `onChange`, `showArrows`, `snap`, `snapAlign`, `visibleItems` | Navigable sequence. Children must be carousel items. |
| `<carousel-item>` | `aspectRatio`, `background`, `border`, `gap`, `height`, `key`, `maxHeight`, `maxWidth`, `minHeight`, `minWidth`, `padding`, `radius`, `variant`, `width` | Text or general carousel item. |
| `<carousel-media-item>` | `aspectRatio`, `background`, `border`, `gap`, `height`, `key`, `maxHeight`, `maxWidth`, `minHeight`, `minWidth`, `padding`, `radius`, `size`, `variant`, `width`, `media` | Media carousel item. |
| `<popover>` | `hoverOpenDelay`, `open`, `showOnHover` | Detail panel. Contains trigger and content. |
| `<popover-trigger>` | `block`, `onClick` | Opens the popover. |
| `<popover-content>` | `align`, `showCloseButton`, `side`, `sideOffset` | Popover content. |

### 5.2 Example

Use `<grid>` with `<grid-item>` children, and hold each compared value in a `<card>`. `<carousel>` children must be carousel items; `activeIndex` and `onChange` control its state. `<popover>` holds one `<popover-trigger>` and one `<popover-content>`. `<pressable>` takes `onClick` and an optional `tooltip`.

Do not add `onClick` to an unsupported component. Every clickable element must perform its stated action.

### 5.3 Carousel, popover, and pressable examples

`<carousel showArrows={true} visibleItems={2} gap={2}>` holds `<carousel-item>` entries. `<pressable onClick={() => GenUI.copy("Selected text")} tooltip="Copy text">` copies on a real press. Copy text stays verbatim inside the callback.

## 6. Tables and lists

### 6.1 Native table components

| Component | Supported properties |
|---|---|
| `<table>` | `columnSizing`, `dividers`, `emptyLabel`, `stickyHeader` |
| `<table-section>` | `header`, `rowDivider` |
| `<table-row>` | `header`, `label`, `labelColSpan` |
| `<table-cell>` | `align`, `colSpan`, `header`, `padding`, `rowSpan`, `vAlign`, `width` |

Use only the named child structure in `<table>`: `<table-section>` holds `<table-row>`, which holds `<table-cell>`. Do not insert arbitrary layout components directly inside it. Exact accepted values for `columnSizing` and `dividers` must come from the active component schema.

Use a Markdown table for normal comparisons. Use the native table when explicit row and cell components, table sections, or sticky headers add value.

### 6.2 Lists

`<list>` properties: `connector`, `gap`, `marker`, `maxMarkerSize`, `start`. `<list-item>` properties: `description`, `disabled`, `label`, `marker`, `markerSize`.

Use a list for steps or short collections. Use a table when readers need to compare multiple fields for each item.

## 7. Charts

### 7.1 Chart component shape

`<Chart>` accepts exactly one JSON-compatible object through `content`. Do not pass JSON text. Do not assume that the component accepts the Recharts API.

For `line`, `bar`, and `scatter`, the object carries `chartType` (`"bar"`, `"line"`, or `"scatter"`), `xKey` (the horizontal or category field name), `series`, and `data`. Each `series` entry carries `dataKey` (the numeric measure field name) and optional `label`, `valueFormat`, and `valuePrefix`. Each `data` record must include the `xKey` field and every series `dataKey` field. Optional top-level fields: `xAxisLabel`, `axisLabel`, `valueSuffix`, `yAxisMin`, `yAxisMax`, `xAxisScale`, `layout`.

For `pie`, use `nameKey` and `valueKey` instead of `xKey`, with `series: [{dataKey: <the value field>}]`.

### 7.2 Selection rules

- Use a line chart for change over an ordered or continuous dimension.
- Use a bar chart for categorical comparison.
- Use a scatter chart for relationships between numerical variables, if the target renderer supports the expected data shape.
- Use a pie chart for a small number of parts of a whole.
- Use a table when exact values are more important than visual patterns.
- Use a Mermaid Sankey for weighted flows, Mermaid XY chart for a Mermaid-native line or bar diagram, or a treemap for hierarchical proportions when the renderer supports that diagram type.

Use `xAxisScale: "linear"` only for a numeric line chart. Use `layout: "vertical"` only for a bar chart. Set axis bounds only when they preserve the meaning of the data. Prefer a tick step of `(yAxisMax - yAxisMin) / 4` for bounded integer axes when that choice does not distort or exclude values.

Do not invent data. Keep units, labels, data grain, sources, and caveats visible. Never use visual design to exaggerate a difference.

## 8. Images, video, icons, and SVG

### 8.1 Images

`<AsyncImage>` properties: `alt`, `aspectRatio`, `fallback`, `fit`, `frame`, `group`, `height`, `maxHeight`, `maxWidth`, `minHeight`, `minWidth`, `query`, `radius`, `ref`, `src`, `width`.

`<AsyncImage>` requires exactly one source:

- `query`: ask for a suitable image.
- `ref`: use an exact matching image, product, or business reference returned by a tool.
- `src`: use an unchanged HTTP(S) URL supplied by an authorized model-data binding. Do not construct or modify it.

Do not combine `query`, `ref`, and `src`. For repeated images of different items, write a separate occurrence for each subject. Do not put one query-based `<AsyncImage>` inside a loop over different items.

`<AsyncImageGroup>` properties: `aspectRatio`, `fallback`, `layout`, `numPerQuery`, `query`, `ref`, `refs`, `size`. Use an image group only when several images add independent value. Avoid image groups for exact specifications, one-number answers, or long catalogs.

`<AsyncVideo>` accepts `ref`. Use only an exact video reference returned by an available tool. Do not guess IDs.

### 8.2 Icons and favicons

`<icon>` properties: `color`, `inline`, `name`, `size`. Use an exact supported Lucide icon name in kebab case, such as `check-circle`. `<favicon>` properties: `alt`, `frame`, `inline`, `size`, `url`.

Use icons to improve recognition. Never rely on color alone. Do not use an icon as a substitute for a clear label when the meaning may be unclear.

### 8.3 SVG

`<svg>` properties: `color`, `fill`, `height`, `preserveAspectRatio`, `size`, `stroke`, `strokeLinecap`, `strokeLinejoin`, `strokeWidth`, `viewBox`, `width`, `xmlns`. Children must be native SVG elements. Do not put event handlers on native SVG elements.

Use SVG for a small, precise vector graphic. Use Mermaid for a structured diagram, `<Chart>` for supported quantitative charts, and `<MapWidgetV2>` for maps. Do not use a decorative image when an editable structured format is required.

## 9. Maps and routes

Use `<MapWidgetV2>` for explicit map requests, geographic facts, recommendations involving at least three geolocatable places in one area, routes, and itineraries with multiple practical stops. The map must represent the same locations described in the response.

The property list, points schema, group and route rules, carousel schema, and icon rules
live in [references/components/maps.md](references/components/maps.md). Read that file
before writing a map block.

## 10. Entities, links, citations, and data bindings

Use exact references returned by the relevant source or tool. Do not reuse historical refs unless they are declared in the current response. A citation component does not make an unsupported claim true. Put each citation close to the claim it supports.

### 10.1 Link and entity components

- `<Link>` properties: `ref`, `title`, `url`.
- `<Entity>` properties: `address`, `category`, `disambig`, `location`, `query`, `ref`, `value`.
- `<Cite>` properties: `params`, `ref`, `refs`. The `params` schema is provider-specific and must not be guessed.
- `<FileCite>` properties: `line_range_end`, `line_range_start`, `ref`.
- `<CodeCite>` properties: `citation_id`, `line_range_end`, `line_range_start`, `tool`.
- `<FileNavList>` property: `items`.
- `<FollowUp>` properties: `query`, `source`, `value`.
- `<MemoryCite>` has no props.

All `turnN...` values are placeholders. Replace them with exact references from the active response. Use the smallest supported file line range that proves the claim. Use `<FileNavList>` when the user asks to locate files or resources; each item needs a valid file reference and a short description.

For every `<Entity category="brand">`, provide a non-empty `disambig` that identifies the brand's industry or product type. Reuse matching product or business refs for entities and images when available.

### 10.2 Data binding rules

When a tool declares data bindings, render from those fields instead of copying values into literals. Supported refs are `ProductRef`, `BusinessRef`, and `WebRef` with declared fields. Follow the schema for the active tool result.

- Product: bind title, displayed price, merchant, and product URL to the declared fields. Use the same product ref for `<Entity>` and `<AsyncImage>`.
- Business: bind name and address to the business fields. Use the same business ref for `<Entity>` and `<AsyncImage>`.
- Web search: bind titles and URLs to the returned web reference. Use ordinary cited prose for a search ref; do not present it as a product or business card.
- News: use the exact news ref and bind headline and article URL to its fields. Keep the image lightbox separate from the article-opening action.
- Do not construct or modify source URLs. Bind unchanged HTTP(S) URLs only where the contract allows it.

Reference names in examples are placeholders. Do not copy them as if they were current evidence.

## 11. Code blocks, writing blocks, and app blocks

### 11.1 CodeBlock

`<CodeBlock>` properties: `editable`, `interactive`, `language`, `model_previewable`. Its children are raw source text.

Use a Markdown fenced block for ordinary code. Use `<CodeBlock>` when editing or previewing code is helpful. Mermaid code fences can preview supported diagrams. For flowcharts, use `flowchart TB` by default.

### 11.2 WritingBlock

`<WritingBlock>` properties: `id`, `options`, `subject`, `variant`. Use it for a standalone, copyable draft.

- `id`: unique five-digit identifier.
- `variant`: `email`, `chat_message`, `social_post`, `document`, or `standard`.
- `subject`: optional for `email`; omit it for other variants.
- `options`: use when the user requests multiple tones, styles, or approaches. Put the best default first.
- Children are raw text with basic Markdown support. Do not include DIL components inside the block.

Do not use `WritingBlock` for an ordinary explanation, brainstorming, code, a formula, or a story.

### 11.3 AppBlock

`<AppBlock>` properties: `app_block_id`, `bind`, `bundle_version`, `entrypoint`, `icon`, `language`, `title`, `variant`. Its children are raw HTML or JavaScript.

Use it only when the user needs a custom app visualization or interaction that standard components cannot support. For ordinary responses, keep controls in DIL and use `bind={{value, setValue}}` to pass state to the visualization.

Inside AppBlock source:

- Read `globalThis.__bindings?.value` inside `globalThis.__effect?.(() => ...)` when synchronization is required.
- Call `globalThis.__bindings?.setValue?.(...)` only from direct user interaction within the visualization, never from an effect.
- Optional-chain every access to `__bindings` and every call to `__effect`.
- Keep a useful static view when bindings or effects are absent.

Do not use an AppBlock for a static table, chart, or diagram that an existing component can render.

## 12. Interactive controls and host actions

### 12.1 Control property reference

| Component | Supported properties |
|---|---|
| `<button>` | `block`, `color`, `disabled`, `label`, `loading`, `onClick`, `pill`, `size`, `submit`, `uniform`, `variant` |
| `<checkbox>` | `checked`, `defaultChecked`, `disabled`, `label`, `lineThrough`, `name`, `onChange`, `required`, `shape`, `value` |
| `<date-picker>` | `align`, `block`, `clearable`, `defaultValue`, `disabled`, `max`, `min`, `onChange`, `pill`, `placeholder`, `required`, `side`, `size`, `value`, `variant` |
| `<form>` | Shared layout properties plus `aspectRatio`, `maxSize`, `minSize`, `onSubmit`, `size` |
| `<input>` | `autoSelect`, `defaultValue`, `disabled`, `fontSize`, `inputType`, `invalid`, `mask`, `name`, `onChange`, `pill`, `placeholder`, `required`, `size`, `value`, `variant` |
| `<radio-group>` | `defaultValue`, `direction`, `disabled`, `label`, `name`, `onChange`, `required`, `value` |
| `<radio>` | `disabled`, `id`, `required`, `value` |
| `<segmented-control>` | `defaultValue`, `disabled`, `label`, `onChange`, `options`, `pill`, `size`, `value`, `variant` |
| `<select>` | `align`, `block`, `clearable`, `defaultValue`, `disabled`, `icon`, `name`, `onChange`, `options`, `pill`, `placeholder`, `required`, `side`, `size`, `value`, `variant` |
| `<slider>` | `defaultValue`, `disabled`, `marks`, `max`, `min`, `name`, `onChange`, `required`, `sliderStyle`, `step`, `value` |
| `<textarea>` | `autoResize`, `autoSelect`, `defaultValue`, `disabled`, `invalid`, `maxRows`, `name`, `onChange`, `placeholder`, `required`, `rows`, `size`, `value`, `variant` |

`<radio-group>` must contain `<radio>` children. Keep forms small. The exact object schema for the `options` property of `<select>` and `<segmented-control>` is not specified here. Verify it in the active environment instead of guessing.

### 12.2 State example

Declare state in one top-level `{@body ...}` block with `DIL.useState`, then bind it below. Use `value` plus `onChange` for controlled values. Use `checked` plus `onChange` for controlled checkboxes. Use `defaultValue` or `defaultChecked` for uncontrolled initial values. Change callbacks receive the new value, not an event.

### 12.3 Supported host actions

Use an action only from a real user interaction. Available actions are:

- `GenUI.openUrl(url: string)`: open a URL.
- `GenUI.copy(text: string)`: copy text.
- `GenUI.issueNewTurn(query: string)`: submit a new user message.
- `GenUI.openEntityDetail(args)`: open a product or business detail.

`GenUI.openEntityDetail` accepts exactly one of the supported shapes: a ref shape `{category: "product", refId: "turn0product0"}`, or a query shape `{value: "Example product", category: "product", disambig: "wireless headphones"}`.

The ref must exist in the active response. Product or business query shapes require enabled capture guidance. Business queries must include `location` or `address`. Do not invent host action names, action arguments, or success messages.

## 13. Mermaid: core rules

Mermaid is a text-based diagram language. Use Mermaid when the target renders it. Prefer the supported structured format over an image of a diagram source.

Default to `flowchart TB` unless another layout better represents the information. This skill covers the diagram families in the official Mermaid syntax catalog. Mermaid's official documentation identified version 12.1.0 during the source check for this skill. Check the active renderer before using newer or beta features.

### 13.1 General syntax

Most Mermaid diagrams start with a diagram declaration followed by content. Frontmatter is an exception because it can appear before the declaration. Comments use `%%` for the rest of a line where the diagram grammar allows comments. Unknown keywords can break a diagram. Misspelled configuration values can be silently ignored.

Every Mermaid example MUST begin with the correct diagram declaration, except when the official syntax explicitly permits another structure, such as frontmatter before the declaration.

- Use the exact declaration documented for the selected diagram type.
- Include the declaration in every standalone example. Never omit it because the surrounding heading names the diagram type.
- Use the correct version-specific or beta declaration.
- Keep the declaration inside the Mermaid source block.
- Do not confuse content indentation with a diagram declaration.
- Do not assume that syntax from one diagram type works in another.
- Verify each example against the official documentation for its diagram type.
- Test rendering when the target renderer is available.
- When rendering fails, identify and correct the syntax error. Do not report success without verification.

### 13.2 Directions

Flowchart-like diagrams commonly support `TB` (top to bottom, the default), `TD` (top down, same as `TB`), `BT` (bottom to top), `LR` (left to right), and `RL` (right to left).

Check the individual diagram reference. Not every diagram type supports the same directions.

### 13.3 Flowchart nodes and edges

Common node syntax: `A[Text]` rectangle, `A(Text)` rounded rectangle, `A([Text])` stadium, `A{Text}` decision, `A((Text))` circle, `A{{Text}}` hexagon. Newer Mermaid versions support expanded node shapes through `A@{ shape: rect, label: "Text" }` and related shape names. Check the official shape catalog for valid shape IDs.

Common edges: `A --> B` directed arrow, `A --- B` undirected line, `A -->|Yes| B` labeled edge, `A -.-> B` dotted arrow, `A ==> B` thick arrow.

Use stable IDs, short labels, and explicit decision outcomes. Avoid bare lowercase `end` as a flowchart node label; it can break parsing. Quote ambiguous labels. A connection beginning with `o` or `x` after certain edge symbols can create special edge shapes; add a separating space or capitalize the node ID when needed.

### 13.4 Styling, accessibility, and layout

Mermaid supports per-diagram syntax for classes, styles, configuration, themes, layout, look, and accessibility. Support and default values vary by diagram type and Mermaid version.

Use frontmatter only when the target supports it. Configuration keys are case-sensitive. Do not add style configuration unless it improves meaning or readability. Prefer default rendering over theme overrides when custom colors add no information.

Add accessibility titles and descriptions where supported, using the syntax documented for that diagram type. Keep node labels readable, use concise identifiers, and split dense diagrams rather than shrinking labels.

## 14. Mermaid diagram catalog

Keywords and beta status can change. Follow each official documentation link for the full grammar and current options.

| Diagram | Declaration | Best use | Official syntax |
|---|---|---|---|
| [Flowchart](references/mermaid/flowchart.md) | `flowchart TB` or `graph TB` | Steps, branches, dependencies, and paths | [Flowchart](https://mermaid.js.org/syntax/flowchart.html) |
| [Swimlanes](references/mermaid/swimlanes.md) | `swimlane-beta` | Processes divided by responsibility and cross-lane handoffs | [Swimlanes](https://mermaid.js.org/syntax/swimlanes.html) |
| [Sequence](references/mermaid/sequence.md) | `sequenceDiagram` | Ordered messages between actors or services | [Sequence](https://mermaid.js.org/syntax/sequenceDiagram.html) |
| [Class](references/mermaid/class.md) | `classDiagram` | Types, attributes, methods, and code relationships | [Class](https://mermaid.js.org/syntax/classDiagram.html) |
| [State](references/mermaid/state.md) | `stateDiagram-v2` | States, transitions, and lifecycle constraints | [State](https://mermaid.js.org/syntax/stateDiagram.html) |
| [Entity relationship](references/mermaid/er.md) | `erDiagram` | Entities, attributes, and cardinality | [ER](https://mermaid.js.org/syntax/entityRelationshipDiagram.html) |
| [User journey](references/mermaid/journey.md) | `journey` | User steps with experience scores | [Journey](https://mermaid.js.org/syntax/userJourney.html) |
| [Gantt](references/mermaid/gantt.md) | `gantt` | Task timelines, duration, dependencies, and milestones | [Gantt](https://mermaid.js.org/syntax/gantt.html) |
| [Pie](references/mermaid/pie.md) | `pie` | A small number of parts of a whole | [Pie](https://mermaid.js.org/syntax/pie.html) |
| [Quadrant](references/mermaid/quadrant.md) | `quadrantChart` | Position items on two labeled axes | [Quadrant](https://mermaid.js.org/syntax/quadrantChart.html) |
| [GitGraph](references/mermaid/gitgraph.md) | `gitGraph` | Conceptual Git branches, commits, and merges | [GitGraph](https://mermaid.js.org/syntax/gitgraph.html) |
| [C4](references/mermaid/c4.md) | `C4Context`, `C4Container`, `C4Component`, `C4Dynamic`, `C4Deployment` | Software architecture at different levels | [C4](https://mermaid.js.org/syntax/c4.html) |
| [Mindmap](references/mermaid/mindmap.md) | `mindmap` | Hierarchical concepts and brainstorming | [Mindmap](https://mermaid.js.org/syntax/mindmap.html) |
| [Timeline](references/mermaid/timeline.md) | `timeline` | Chronological events or periods | [Timeline](https://mermaid.js.org/syntax/timeline.html) |
| [Sankey](references/mermaid/sankey.md) | `sankey` | Weighted flows between source and target categories | [Sankey](https://mermaid.js.org/syntax/sankey.html) |
| [XY chart](references/mermaid/xychart.md) | `xychart` | Numerical line and bar series | [XY chart](https://mermaid.js.org/syntax/xyChart.html) |
| [Packet](references/mermaid/packet.md) | `packet` | Bit fields and packet structure | [Packet](https://mermaid.js.org/syntax/packet.html) |
| [Kanban](references/mermaid/kanban.md) | `kanban` | Tasks arranged in workflow columns | [Kanban](https://mermaid.js.org/syntax/kanban.html) |
| [Architecture](references/mermaid/architecture.md) | `architecture-beta` | Services, groups, and directional connections | [Architecture](https://mermaid.js.org/syntax/architecture.html) |
| [Radar](references/mermaid/radar.md) | `radar-beta` | Compare entities across dimensions using a common scale | [Radar](https://mermaid.js.org/syntax/radar.html) |
| [Event modeling](references/mermaid/eventmodeling.md) | `eventmodeling` | Events, commands, UI, and time-frame relationships | [Event modeling](https://mermaid.js.org/syntax/eventmodeling.html) |
| [Treemap](references/mermaid/treemap.md) | `treemap-beta` | Hierarchical proportions | [Treemap](https://mermaid.js.org/syntax/treemap.html) |
| [Venn](references/mermaid/venn.md) | `venn-beta` | Sets and overlaps | [Venn](https://mermaid.js.org/syntax/venn.html) |
| [Ishikawa](references/mermaid/ishikawa.md) | `ishikawa-beta` | Causes and sub-causes of a problem | [Ishikawa](https://mermaid.js.org/syntax/ishikawa.html) |
| [Wardley map](references/mermaid/wardley.md) | `wardley-beta` | Value-chain dependency and evolution mapping | [Wardley](https://mermaid.js.org/syntax/wardley.html) |
| [Cynefin](references/mermaid/cynefin.md) | `cynefin-beta` | Classify situations by domain of complexity | [Cynefin](https://mermaid.js.org/syntax/cynefin.html) |
| [TreeView](references/mermaid/treeview.md) | `treeView-beta` or documented box-drawing input | Directory and hierarchical structures | [TreeView](https://mermaid.js.org/syntax/treeView.html) |

Each catalog family has its own file under `references/mermaid/`, linked from its row above
and carrying a worked example. Read that one file before writing a diagram in a family you
have not used in this answer. Do not read the whole folder.

## 15. Media, diagram, and custom-format decision rules

Use this escalation order:

1. Markdown prose, lists, tables, and code fences.
2. Existing DIL primitives for local styling, layout, source linking, or interaction.
3. Mermaid for structured diagrams.
4. `<Chart>` for the supported chart types, or `<MapWidgetV2>` for geographic data.
5. `<AsyncImage>` or `<AsyncImageGroup>` for real visual material.
6. `<CodeBlock>` or `<WritingBlock>` when editing, preview, or copyable artifact support matters.
7. `<AppBlock>` only for a custom visualization or behavior that the existing methods cannot express.

Do not substitute image generation for a user-required editable diagram, data table, or working interactive control. When a static illustration is explicitly requested and no structured format is required, image generation may be appropriate. Retrieved images cannot be treated as editable source diagrams.

## 16. Common failures

- Invented component or property names.
- Incorrect child structure, such as arbitrary children inside `<table>` or unsupported direct children inside `<grid>`.
- More than one source for `<AsyncImage>`.
- An image query inside a loop over different subjects, causing repeated identical images.
- A `<Chart>` content value passed as a JSON string instead of an object.
- A chart with missing fields, mixed units, unsupported axis options, or misleading axis ranges.
- An ungrounded map point, invented route time, or unverified opening status.
- A citation with a fabricated or stale reference.
- Hard-coded source-backed values when the active result declares a supported binding.
- A clickable element with no real action.
- Hooks called conditionally, inside a loop, or from a callback.
- A guessed `select` or `segmented-control` option schema.
- Invalid Mermaid declaration, misspelled configuration, malformed nesting, or unsupported beta syntax.
- A Mermaid example that lacks its required diagram declaration.
- A diagram declaration that does not match the selected diagram type.
- An example that uses syntax from a different diagram type or Mermaid version.
- An example with invalid indentation, nesting, identifiers, fields, or relationships.
- An example that was not checked against the official syntax reference.
- A claim of rendering success without an actual rendering check.
- A dense diagram with long labels, crossing lines, or unreadable scale.
- Styling that adds visual weight without adding information.
- A statement that a component rendered correctly when rendering was not checked.

## 17. Completion checklist

Before presenting the answer, verify:

1. The representation serves the user's goal and does not add unnecessary complexity.
2. Every component name, property, callback, and child shape is documented.
3. Chart and map data use grounded values and correct units.
4. Every source reference and model-data binding is real and current.
5. Interactions modify visible state or perform their stated action.
6. Mermaid uses the correct diagram declaration and current syntax for the target version.
7. Beta or experimental features have a fallback when the target renderer may not support them.
8. Labels, units, titles, accessibility descriptions, and caveats are clear where relevant.
9. The result preserves the source facts and does not overstate certainty.
10. The response uses Markdown instead of a component wherever both communicate equally well.

Before finalizing Mermaid documentation or examples:

1. Confirm that every diagram family in the catalog has an example.
2. Confirm that every example includes its required declaration.
3. Verify every declaration and example against the official diagram reference.
4. Check version requirements for beta and recently added diagram types.
5. Render each example in the target environment when possible.
6. Correct failures before declaring the gallery complete.
7. If a renderer is unavailable, state that rendering remains unverified.

A syntactically plausible example is not proof of successful rendering.

## 18. Official Mermaid references

Use these references to verify a specific grammar or version. The index lists diagram families, configuration, theming, accessibility, layouts, deployment, and the Mermaid CLI.

- [Mermaid syntax reference](https://mermaid.js.org/intro/syntax-reference.html)
- [Mermaid examples](https://mermaid.js.org/syntax/examples.html)
- [Mermaid Live Editor](https://mermaid.live/)
- [Mermaid configuration](https://mermaid.js.org/config/setup/mermaid/interfaces/MermaidConfig.html)

The response component catalog is specific to the current response environment. If a runtime adds or removes components, update this skill from the authoritative component contract rather than inferring availability from an example.
