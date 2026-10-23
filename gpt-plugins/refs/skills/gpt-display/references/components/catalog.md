# Component catalog

Use Markdown for ordinary prose. Use a component only when its documented behavior improves the result.

## Text and inline components

| Component | Properties |
| --- | --- |
| `<badge>` | `color`, `label`, `maxWidth`, `onHover`, `padding`, `pill`, `size`, `variant`, `weight` |
| `<bold>` | `weight` |
| `<caption>` | `color`, `maxLines`, `textAlign`, `truncate`, `weight` |
| `<label>` | `color`, `htmlFor`, `size`, `textAlign`, `truncate`, `weight`, `width` |
| `<math>` | `block`, `value` |
| `<text>` | `color`, `highlight`, `inline`, `italic`, `lineThrough`, `maxLines`, `minLines`, `preserveWhitespace`, `size`, `strong`, `tabularNums`, `textAlign`, `truncate`, `underline`, `weight`, `width` |
| `<title>` | `color`, `italic`, `maxLines`, `size`, `strong`, `tabularNums`, `textAlign`, `truncate`, `weight`, `width` |

`<code>`, `<italic>`, `<strikethrough>`, and `<underline>` take no extra properties. Use inline components only when they improve meaning or readability. Do not use badges as headings, ordinary field labels, or repeated decoration.

## Media components

| Component | Properties |
| --- | --- |
| `<AsyncImage>` | `alt`, `aspectRatio`, `fallback`, `fit`, `frame`, `group`, `height`, `maxHeight`, `maxWidth`, `minHeight`, `minWidth`, `query`, `radius`, `ref`, `src`, `width` |
| `<AsyncImageGroup>` | `aspectRatio`, `fallback`, `layout`, `numPerQuery`, `query`, `ref`, `refs`, `size` |
| `<AsyncVideo>` | `ref` |
| `<favicon>` | `alt`, `frame`, `inline`, `size`, `url` |
| `<icon>` | `color`, `inline`, `name`, `size` |
| `<svg>` | `color`, `fill`, `height`, `preserveAspectRatio`, `size`, `stroke`, `strokeLinecap`, `strokeLinejoin`, `strokeWidth`, `viewBox`, `width`, `xmlns` |

`<AsyncImage>` requires exactly one source: `query`, `ref`, or `src`. Use an exact returned reference when it matches the requested subject. Use `src` only for an unchanged HTTP(S) URL from an authorized model-data binding; never construct or modify that URL. Do not combine image sources.

For different subjects, author a separate image component for each subject. Do not put one query-based image inside a loop over different subjects. Do not attach event handlers to `<AsyncImage>` or native SVG elements. Use exact supported Lucide icon names in lowercase kebab case. Use SVG for precise vector artwork and Mermaid for structured diagrams.

## Layout components

Shared layout properties appear in [DIL and accessibility](dil.md).

| Component | Additional properties |
| --- | --- |
| `<box>`, `<row>` | `aspectRatio`, `columnGap` (`<box>` only), `maxSize`, `minSize`, `rowGap`, `size` |
| `<col>` | `aspectRatio`, `columnGap`, `maxSize`, `minSize`, `size` |
| `<card>` | `background`, `disableAutoSpacing`, `gap`, `height`, `justify`, `padding`, `shadow`, `size`, `theme`, `variant`, `width` |
| `<grid>` | `columnGap`, `columns`, `gap`, `minChildWidth`, `rowGap`, `rows` |
| `<grid-item>` | `rowSpan`, `span` |
| `<flow>` | `columns`, `gap`, `layout`, `rows` |
| `<flow-item>` | `aspectMode`, `aspectRatio`, `rowSpan`, `span`, plus shared layout properties |
| `<divider>` | `color`, `flush`, `size`, `spacing` |
| `<spacer>` | `minSize` |
| `<pressable>` | `aspectRatio`, `disabled`, `inline`, `maxSize`, `minSize`, `onClick`, `size`, `tooltip`, plus shared layout properties |
| `<carousel>` | `activeIndex`, `flush`, `gap`, `onChange`, `showArrows`, `snap`, `snapAlign`, `visibleItems` |
| `<carousel-item>` | `aspectRatio`, `background`, `border`, `gap`, `height`, `key`, `maxHeight`, `maxWidth`, `minHeight`, `minWidth`, `padding`, `radius`, `variant`, `width` |
| `<carousel-media-item>` | `<carousel-item>` properties plus `media`, `size` |
| `<popover>` | `hoverOpenDelay`, `open`, `showOnHover` |
| `<popover-trigger>` | `block`, `onClick` |
| `<popover-content>` | `align`, `showCloseButton`, `side`, `sideOffset` |

`<grid>` contains `<grid-item>` children. `<carousel>` contains `<carousel-item>` or `<carousel-media-item>` children. `<popover>` contains `<popover-trigger>` and `<popover-content>`. Every clickable surface must perform its stated action. Keep multi-column layouts readable on narrow screens.

## Tables and lists

| Component | Properties |
| --- | --- |
| `<table>` | `columnSizing`, `dividers`, `emptyLabel`, `stickyHeader` |
| `<table-section>` | `header`, `rowDivider` |
| `<table-row>` | `header`, `label`, `labelColSpan` |
| `<table-cell>` | `align`, `colSpan`, `header`, `padding`, `rowSpan`, `vAlign`, `width` |
| `<list>` | `connector`, `gap`, `marker`, `maxMarkerSize`, `start` |
| `<list-item>` | `description`, `disabled`, `label`, `marker`, `markerSize` |

A table uses its documented nesting: `<table>`, `<table-section>`, `<table-row>`, then `<table-cell>`. Do not insert arbitrary components into that structure or invent values for `columnSizing` or `dividers`. Use Markdown tables for ordinary comparisons; use native tables when sections, explicit cells, or a sticky header add value.

## Input and interaction components

| Component | Properties |
| --- | --- |
| `<button>` | `block`, `color`, `disabled`, `label`, `loading`, `onClick`, `pill`, `size`, `submit`, `uniform`, `variant` |
| `<checkbox>` | `checked`, `defaultChecked`, `disabled`, `label`, `lineThrough`, `name`, `onChange`, `required`, `shape`, `value` |
| `<date-picker>` | `align`, `block`, `clearable`, `defaultValue`, `disabled`, `max`, `min`, `onChange`, `pill`, `placeholder`, `required`, `side`, `size`, `value`, `variant` |
| `<form>` | `aspectRatio`, `maxSize`, `minSize`, `onSubmit`, `size`, plus shared layout properties |
| `<input>` | `autoSelect`, `defaultValue`, `disabled`, `fontSize`, `inputType`, `invalid`, `mask`, `name`, `onChange`, `pill`, `placeholder`, `required`, `size`, `value`, `variant` |
| `<radio-group>` | `defaultValue`, `direction`, `disabled`, `label`, `name`, `onChange`, `required`, `value` |
| `<radio>` | `disabled`, `id`, `required`, `value` |
| `<segmented-control>` | `defaultValue`, `disabled`, `label`, `onChange`, `options`, `pill`, `size`, `value`, `variant` |
| `<select>` | `align`, `block`, `clearable`, `defaultValue`, `disabled`, `icon`, `name`, `onChange`, `options`, `pill`, `placeholder`, `required`, `side`, `size`, `value`, `variant` |
| `<slider>` | `defaultValue`, `disabled`, `marks`, `max`, `min`, `name`, `onChange`, `required`, `sliderStyle`, `step`, `value` |
| `<textarea>` | `autoResize`, `autoSelect`, `defaultValue`, `disabled`, `invalid`, `maxRows`, `name`, `onChange`, `placeholder`, `required`, `rows`, `size`, `value`, `variant` |

`<radio-group>` contains `<radio>` children. Controlled inputs use `value` and `onChange`; controlled checkboxes use `checked` and `onChange`. Uncontrolled inputs can use `defaultValue` or `defaultChecked`. Use `DIL.useState` whenever input changes affect displayed content. Keep forms small and wire every submit or action control to a real action.

The option-object schema for `select.options` and `segmented-control.options` is not defined here. Do not invent it or write guessed option-object examples. There is no `<multi-select>` component: use independent `<checkbox>` controls with shared state.

## Chart

`<Chart>` accepts one JSON-compatible object through `content`; do not pass a JSON string or a Recharts API object.

- For `bar`, `line`, and `scatter`: provide `chartType`, `xKey`, `series` (`{dataKey, label?, valueFormat?, valuePrefix?}`), and `data` (each row includes `xKey` and every `dataKey`). Optional top-level fields: `xAxisLabel`, `axisLabel`, `valueSuffix`, `yAxisMin`, `yAxisMax`, `xAxisScale` (`"linear"` only for numeric line charts), and `layout` (`"vertical"` only for bar charts).
- For `pie`: provide `chartType: "pie"`, `nameKey`, `valueKey`, `series: [{dataKey: "..."}]`, and `data`.

Use line charts for ordered trends, bars for category comparisons, scatter charts for numerical relationships when supported, and pie charts for few parts of a whole. Use tables when exact values matter more than patterns. Preserve units, labels, data grain, sources, and caveats. Never invent data or use misleading axes. Prefer the supplied palette; override a series color only for a grounded cross-theme match.

### Cartesian (`line`, `bar`, `scatter`)

```jsx
<Chart
  content={{
    chartType: "line",
    xKey: "month",
    series: [{dataKey: "revenue", label: "Revenue", valuePrefix: "$"}],
    data: [
      {month: "Jan", revenue: 12},
      {month: "Feb", revenue: 18},
      {month: "Mar", revenue: 16}
    ],
    xAxisLabel: "Month",
    axisLabel: "Revenue (USD)"
  }}
/>
```

### Pie

```jsx
<Chart
  content={{
    chartType: "pie",
    nameKey: "segment",
    valueKey: "share",
    series: [{dataKey: "share"}],
    data: [
      {segment: "A", share: 45},
      {segment: "B", share: 35},
      {segment: "C", share: 20}
    ],
    valueSuffix: "%"
  }}
/>
```
