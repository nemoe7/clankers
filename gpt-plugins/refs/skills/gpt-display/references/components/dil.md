# DIL syntax and accessibility

## Document structure

- `{expression}` evaluates an inline JavaScript expression; `{@body ...}` declares top-level state, hooks, and callbacks; `{@module ...}` declares pure, hook-free helpers.
- `{#if condition}{:else if condition}{:else}{/if}` and `{#each items as item, i}{/each}` control conditional and repeated markup.
- `<></>` groups components without a container; `<escape>...</escape>`, code spans, and fenced code blocks protect literal source.
- Lowercase tags are ordinary components; uppercase tags are server-resolved components. Close every tag and directive.
- Use actual newlines, never HTML `<br>`. Use `String.raw` for LaTeX strings containing backslashes.
- Ordinary DIL expressions lack browser APIs, network access, storage, timers, workers, dynamic imports, `eval`, `Function`, and `globalThis`.

## Hooks and state

Supported hooks: `DIL.useBreakpoint`, `DIL.useCallback`, `DIL.useEffect`, `DIL.useId`, `DIL.useMemo`, `DIL.useRef`, `DIL.useState`, and `DIL.useTheme`.

Call hooks only in an unconditional, top-level `{@body ...}` declaration, never inside markup, conditions, loops, or callbacks. Preserve hook order. Input callbacks receive the new value, not a DOM event. Use shared state whenever an interaction changes displayed content.

## Shared layout properties

Only `<box>`, `<col>`, `<flow-item>`, `<pressable>`, `<row>`, and `<form>` accept: `align`, `background`, `border`, `clip`, `direction`, `disableAutoSpacing`, `flex`, `flush`, `gap`, `height`, `justify`, `key`, `maxHeight`, `maxWidth`, `minHeight`, `minWidth`, `padding`, `radius`, `role`, `scrollable`, `theme`, `width`, `wrap`.

Numeric spacing uses four points per unit; literal values support `px`, `rem`, `pt`, `%`, and `0`. Do not apply shared properties to other components unless listed in their catalog.

## Theme and accessibility

- Support light and dark themes. Prefer semantic variants and inherited foreground colors.
- Do not use literal hex, RGB, HSL, or named CSS colors for ordinary text, backgrounds, borders, or dividers.
- Use `DIL.useTheme` only when a literal color is necessary to preserve meaning. Declare it at top level and provide values for both themes.
- Maintain at least 4.5:1 contrast for body text and 3:1 for large text.
- Never rely on color alone to communicate meaning.
- Preserve labels, control semantics, and accessible names.
- Do not add decorative surfaces, icons, badges, or layout containers without a clear purpose.
