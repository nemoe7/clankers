# DIL syntax and accessibility

## Document structure

A response can combine Markdown, JavaScript expressions, and supported components.

- `{expression}` evaluates an inline JavaScript expression.
- `{@body ...}` declares top-level state, hooks, and callbacks before markup uses them.
- `{@module ...}` declares pure, hook-free helpers.
- `{#if condition}{:else if condition}{:else}{/if}` selects markup conditionally.
- `{#each items as item, i}{/each}` repeats markup.
- `<></>` groups components without a layout container.
- `<escape>...</escape>` protects literal text that could be interpreted as markup or an expression.
- Code spans and fenced code blocks protect literal source.
- Lowercase tags are ordinary components; uppercase tags are server-resolved components.
- Close every component and directive. Use actual newlines, never HTML `<br>`.
- Use `String.raw` for LaTeX strings containing backslashes.

Ordinary DIL expressions do not provide browser APIs, network access, storage, timers, workers, dynamic imports, `eval`, `Function`, or `globalThis`.

## Hooks and state

Supported hooks are `DIL.useBreakpoint`, `DIL.useCallback`, `DIL.useEffect`, `DIL.useId`, `DIL.useMemo`, `DIL.useRef`, `DIL.useState`, and `DIL.useTheme`.

Call hooks only in an unconditional, top-level `{@body ...}` declaration. Never call a hook inside markup, a condition, a loop, or a callback. Preserve hook order. Input callbacks receive the new value, not a DOM event. Use shared state whenever an interaction changes displayed content.

## Shared layout properties

Only `<box>`, `<col>`, `<flow-item>`, `<pressable>`, `<row>`, and `<form>` accept these shared properties:

`align`, `background`, `border`, `clip`, `direction`, `disableAutoSpacing`, `flex`, `flush`, `gap`, `height`, `justify`, `key`, `maxHeight`, `maxWidth`, `minHeight`, `minWidth`, `padding`, `radius`, `role`, `scrollable`, `theme`, `width`, `wrap`.

Numeric spacing uses four points per unit. Supported literal spacing values include `px`, `rem`, `pt`, `%`, and `0`. Do not apply a shared property to another component unless its individual catalog lists it.

## Theme and accessibility

- Support light and dark themes. Prefer semantic variants and inherited foreground colors.
- Do not use literal hex, RGB, HSL, or named CSS colors for ordinary text, backgrounds, borders, or dividers.
- Use `DIL.useTheme` only when a literal color is necessary to preserve meaning. Declare it at top level and provide values for both themes.
- Maintain at least 4.5:1 contrast for body text and 3:1 for large text.
- Never rely on color alone to communicate meaning.
- Preserve labels, control semantics, and accessible names.
- Do not add decorative surfaces, icons, badges, or layout containers without a clear purpose.
