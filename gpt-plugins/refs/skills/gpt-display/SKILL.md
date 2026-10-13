---
name: gpt-display
description: Choose and author supported response representations, DIL interfaces, source-bound content, charts, maps, host actions, and Mermaid diagrams.
---

# GPT Display

## 1. Purpose and selection

Use the simplest representation that fully serves the request. Use Markdown for ordinary explanations, answers, lists, tables, and code. Use a native component only when layout, source navigation, media, or interaction improves the result. Compose documented components when one does not meet the task; do not add interface decoration.

| Need | Preferred representation |
| --- | --- |
| Structured diagram | Mermaid with the correct declaration |
| Quantitative pattern | `<Chart>` with grounded, labeled data |
| Geographic request, route, or multi-stop itinerary | `<MapWidgetV2>` |
| Editable or previewable source | `<CodeBlock>` |
| Practical standalone draft | `<WritingBlock>` |
| Required custom behavior unavailable in native components | `<AppBlock>` |

Use a native table only when its explicit structure, sections, or sticky header add value; otherwise use a Markdown table. Use one map unless distinct geographies require separate maps. Use images only when they add independent value.

Do not assume that a valid component definition proves it rendered. State when rendering was not verified.

## 2. Core rules

- Use only documented component names, properties, child structures, bindings, and host actions.
- Keep state at top level; callbacks receive values, not DOM events.
- Bind source-backed fields to exact current references instead of copying them into literals.
- Ground chart and map values. Do not invent locations, prices, ranks, ratings, route metrics, or source URLs.
- Support light and dark themes, preserve accessible labels, and never communicate meaning with color alone.
- Every clickable surface must perform its stated action.

Read the detailed reference that matches the response before authoring it.

| Topic | Reference |
| --- | --- |
| DIL syntax, hooks, shared layout properties, and accessibility | [DIL and accessibility](references/components/dil.md) |
| Text, media, layout, tables, lists, and charts | [Component catalog](references/components/catalog.md) |
| Source bindings, citations, entities, and links | [Bindings and citations](references/components/bindings.md) |
| CodeBlock, WritingBlock, AppBlock, and host actions | [Blocks and host actions](references/components/blocks.md) |
| Questions, calculations, chart, diagram, map, draft, and custom-app patterns | [Interaction patterns](references/components/patterns.md) |
| MapWidgetV2 | [MapWidgetV2](references/components/maps.md) |

## 3. Maps

Use `<MapWidgetV2>` for an explicit map request, geographic facts, routes, multi-stop itineraries, or at least three geolocatable recommendations in one area. Read [MapWidgetV2](references/components/maps.md) before authoring it. The map must represent the same grounded locations described nearby.

## 4. Mermaid

Use Mermaid for structured diagrams, not a generated image. Default to `flowchart TB` unless another direction represents the process better. Use the selected family’s declaration and syntax, keep labels concise, and check newer or beta syntax against the target renderer when possible. Never claim all clients render a diagram.

| Diagram | Declaration | Best use |
| --- | --- | --- |
| [Flowchart](references/mermaid/flowchart.md) | `flowchart TB` | Steps, branches, dependencies, and paths |
| [Swimlanes](references/mermaid/swimlanes.md) | `swimlane-beta` | Responsibility and handoffs |
| [Sequence](references/mermaid/sequence.md) | `sequenceDiagram` | Ordered messages |
| [Class](references/mermaid/class.md) | `classDiagram` | Types and code relationships |
| [State](references/mermaid/state.md) | `stateDiagram-v2` | States and transitions |
| [Entity relationship](references/mermaid/er.md) | `erDiagram` | Entities and cardinality |
| [User journey](references/mermaid/journey.md) | `journey` | User steps and scores |
| [Gantt](references/mermaid/gantt.md) | `gantt` | Timelines and dependencies |
| [Pie](references/mermaid/pie.md) | `pie` | Parts of a whole |
| [Quadrant](references/mermaid/quadrant.md) | `quadrantChart` | Two-axis positions |
| [GitGraph](references/mermaid/gitgraph.md) | `gitGraph` | Conceptual Git history |
| [C4](references/mermaid/c4.md) | `C4Context` et al. | Software architecture |
| [Mindmap](references/mermaid/mindmap.md) | `mindmap` | Hierarchical concepts |
| [Timeline](references/mermaid/timeline.md) | `timeline` | Chronological events |
| [Sankey](references/mermaid/sankey.md) | `sankey` | Weighted flows |
| [XY chart](references/mermaid/xychart.md) | `xychart` | Numerical line or bar series |
| [Packet](references/mermaid/packet.md) | `packet` | Packet structure |
| [Kanban](references/mermaid/kanban.md) | `kanban` | Workflow columns |
| [Architecture](references/mermaid/architecture.md) | `architecture-beta` | Services and groups |
| [Radar](references/mermaid/radar.md) | `radar-beta` | Shared-scale comparisons |
| [Event modeling](references/mermaid/eventmodeling.md) | `eventmodeling` | Events and commands |
| [Treemap](references/mermaid/treemap.md) | `treemap-beta` | Hierarchical proportions |
| [Venn](references/mermaid/venn.md) | `venn-beta` | Sets and overlaps |
| [Ishikawa](references/mermaid/ishikawa.md) | `ishikawa-beta` | Causes and sub-causes |
| [Wardley map](references/mermaid/wardley.md) | `wardley-beta` | Value chains and evolution |
| [Cynefin](references/mermaid/cynefin.md) | `cynefin-beta` | Complexity domains |
| [TreeView](references/mermaid/treeview.md) | `treeView-beta` | Hierarchical structures |

## 5. Common failures

- Invented components, properties, child structures, option-object schemas, or host actions.
- Conditional hooks, changed hook order, or callbacks that expect DOM events.
- A multi-select tag instead of stateful independent checkboxes.
- An input that changes visible output without controlled state.
- A button or clickable surface with no real action.
- Hard-coded source-backed values, stale references, or constructed bound URLs.
- More than one image source, or a query image inside a loop over different subjects.
- Unsupported chart fields, incomplete data rows, unlabeled units, or misleading axes.
- Ungrounded map values or invalid route and carousel structures.
- Theme-specific colors that fail in the other theme or color-only meaning.
- Invalid Mermaid declarations or an unverified claim of successful rendering.
- An AppBlock where documented native components suffice.

## 6. Completion checklist

Before presenting an interface, verify:

1. The representation matches the user’s goal without unnecessary complexity.
2. Component names, properties, and child structures match their references.
3. State and callbacks follow the documented contracts.
4. Host actions use supported signatures and real user interactions.
5. Data bindings use exact current references.
6. Chart and map values are grounded, labeled, and caveated where needed.
7. Theme and accessibility requirements hold in both themes.
8. Mermaid declarations match the selected family.
9. Rendering status is accurate.
10. No decorative interface element obscures the answer.
