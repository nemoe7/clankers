# Source bindings, citations, entities, and links

When a tool declares a supported binding, render source-backed fields from that binding instead of copying them into literals. Keep repeated values bound in text, tables, labels, image components, and action arguments. Only `ProductRef`, `BusinessRef`, and `WebRef` support field bindings. Historical references do not authorize bindings unless the current response declares them.

## ProductRef

Supported fields:

- `title?: string`
- `brand?: string`
- `description?: string`
- `displayed_price?: string | integer | number`
- `rating?: integer | number`
- `review_count?: integer`
- `merchant?: string`
- `product_page?: Uri`

Bind a product name to `.title`, displayed price to `.displayed_price`, merchant to `.merchant`, and product URL to `.product_page.uri`. Reuse the exact same product reference for `Entity.ref`, `AsyncImage.ref`, and field bindings. Do not substitute an image query for a matching returned product reference.

```jsx
<AsyncImage ref="turn0product0" />
<Entity
  ref="turn0product0"
  category="product"
  value={turn0product0.title}
/>
<text>{turn0product0.displayed_price}</text>
<Link
  url={turn0product0.product_page.uri}
  title="View product"
/>
```

Use this pattern only when the active response declares the reference.

## BusinessRef

Supported fields:

- `name?: string`
- `address?: string`
- `rating?: RatingData`
- `price_str?: string`
- `is_open?: boolean`
- `phone?: string`
- `categories?: string[]`

Bind `Entity.value` to `.name` and displayed addresses to `.address`. Reuse the exact business reference for `Entity.ref`, `AsyncImage.ref`, and bound fields. `RatingData` is opaque: pass it unchanged only to the documented `Rating.data` consumer when that component is available in the active contract. Do not unpack or infer its structure.

## WebRef

Supported fields:

- `title?: string`
- `snippet?: string`
- `timestamp?: integer | number`
- `domain?: string`
- `url?: Uri`

`Uri` has `uri: string`, optional `$type: "uri"`, and optional `media_type: string`. Bind displayed fields and destinations to the declared reference. For news, bind the headline to `title` and the opening action to `url.uri`. Format a Unix timestamp with `new Date(ref.timestamp * 1000)` when appropriate.

## Citation, entity, and link components

| Component | Properties |
| --- | --- |
| `<Cite>` | `params`, `ref`, `refs` |
| `<CodeCite>` | `citation_id`, `line_range_end`, `line_range_start`, `tool` |
| `<Entity>` | `address`, `category`, `disambig`, `location`, `query`, `ref`, `value` |
| `<FileCite>` | `line_range_end`, `line_range_start`, `ref` |
| `<FileNavList>` | `items` |
| `<FollowUp>` | `query`, `source`, `value` |
| `<Link>` | `ref`, `title`, `url` |
| `<MemoryCite>` | None listed |

Use exact references returned by the current source or tool; never invent one or reuse a historical reference without authorization. Keep citations next to the claims they support. Use `<FileNavList>` when the user asks to locate resources. Every `<Entity category="brand">` needs a non-empty `disambig` identifying the brand’s industry or product type. Do not guess provider-specific schemas for `Cite.params`. Keep links bound to returned URLs when a binding is available.
