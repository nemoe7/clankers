# Blocks and host actions

## CodeBlock

`<CodeBlock>` properties are `editable`, `interactive`, `language`, and `model_previewable`. Its children are raw source text. Mermaid source can preview when the client supports it. For a generic flowchart, use `A[Step]` nodes and `B{Decision?}` decisions.

Use `<CodeBlock>` when editing or preview adds value beyond a Markdown fence. Do not use it merely to display a short snippet.

## WritingBlock

`<WritingBlock>` properties are `id`, `options`, `subject`, and `variant` (`email`, `chat_message`, `social_post`, `document`, or `standard`).

- Use it for a practical standalone draft that a user is likely to copy, edit, or send.
- Use `document` for a standalone document, proposal, memo, or description; use `standard` when no other variant fits.
- `subject` is optional for `email` and omitted for every other variant.
- Use a unique five-digit `id`.
- For multiple tones, styles, or approaches, use one `options` array with the best default first.
- Children contain raw text with basic Markdown support; do not put DIL components inside them.
- Do not use it for ordinary explanations, brainstorming, stories, formulas, or code.

## AppBlock

`<AppBlock>` properties are `app_block_id`, `bind`, `bundle_version`, `entrypoint`, `icon`, `language`, `title`, and `variant`. Its children are raw HTML or JavaScript.

Use it only when native components cannot meet a required custom visualization or behavior. For ordinary responses, keep controls in DIL and use `bind={{ value, setValue }}`.

Inside AppBlock source:

- Read `globalThis.__bindings?.value` inside `globalThis.__effect?.(() => ...)` when synchronization is required.
- Call `globalThis.__bindings?.setValue?.(...)` only from direct user interaction, never from an effect.
- Optional-chain every access to `__bindings` and every call to `__effect`.
- Keep a useful static view when bindings or effects are absent.

Do not use AppBlock for a static table, supported chart, or structured diagram.

## Host actions

Only these host actions are available. Call them synchronously from a supported, real user interaction. Let the host report success or failure; do not claim either first.

| Action | Argument rules |
| --- | --- |
| `GenUI.openUrl(url)` | Pass one known string URL when navigation is intended |
| `GenUI.copy(text)` | Pass one string to copy known text |
| `GenUI.issueNewTurn(query)` | Pass one message string; do not pass payloads, metadata, attachments, or conversation/message IDs |
| `GenUI.openEntityDetail(args)` | Pass a reference object or query object (see below) |

`GenUI.openEntityDetail` accepts either a current-response reference or a query object:

```js
{ category: "product" | "business", refId: string }
{ value: string, category: string, disambig?: string, location?: string, address?: string }
```

The reference form needs an exact current-response reference. Product and business query forms require enabled capture guidance; business query forms require `location` or `address`. Strings must be nonblank and no longer than 1024 characters. `category` must be lowercase and no longer than 128 characters.
