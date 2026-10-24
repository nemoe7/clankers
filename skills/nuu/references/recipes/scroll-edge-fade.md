# Recipe: Scroll-edge fade

Fade scrollable containers and scrollable inputs (`12px`–`36px` edge height over a `192px` scroll ramp) with CSS scroll-driven animations while keeping non-scrollable containers and single-line inputs unmasked.

## Floating header and composer over a full-bleed scroller

When a thread sits between a top search/status bar and a bottom composer card:

- Keep the header bar and composer card on top (`position: relative; z-index: 2;`).
- Let the scroll wrapper bleed to the viewport edges (`width: 100vw; margin: -12px calc(50% - 50vw) -36px;`) so the scrollbar sits at the right viewport edge while `padding-inline: max(5vw, calc((100% - 900px) / 2))` centers the column.
- Extend the scroller vertically behind both the header (`margin-top: -12px; padding-top: 24px`) and the composer (`margin-bottom: -36px; padding-bottom: 40px`) so the `mask-image` fade dissolves scrolling messages behind the header and composer while the final message still rests above the composer at the bottom of the scroll range.

```css
:root { --edge-fade: 36px; --edge-ramp: 192px; }
@property --edge-start { syntax: "<length>"; inherits: false; initial-value: 0px; }
@property --edge-end { syntax: "<length>"; inherits: false; initial-value: 0px; }

.thread-header,
.composer-card {
  position: relative;
  z-index: 2;
}

.thread-scroll-wrap {
  position: relative;
  display: flex;
  flex-direction: column;
  flex: 1 1 auto;
  min-height: 0;
  width: 100vw;
  margin: -12px calc(50% - 50vw) -36px;
}

.thread-scroller {
  flex: 1 1 auto;
  min-height: 0;
  margin: 0;
  padding: 24px max(5vw, calc((100% - 900px) / 2)) 40px;
  overflow-y: auto;
  scrollbar-gutter: stable;
}

@media (prefers-reduced-motion: no-preference) {
  @supports (animation-timeline: scroll(self)) {
    .thread-scroller, .scroll-panel, textarea {
      mask-image: linear-gradient(to bottom, transparent, black var(--edge-start), black calc(100% - var(--edge-end)), transparent);
      animation: edge-start linear both, edge-end linear both;
      animation-timeline: scroll(self), scroll(self);
      animation-range: 0px var(--edge-ramp), calc(100% - var(--edge-ramp)) 100%;
    }
    @keyframes edge-start { from { --edge-start: 0px; } to { --edge-start: var(--edge-fade); } }
    @keyframes edge-end { from { --edge-end: var(--edge-fade); } to { --edge-end: 0px; } }
  }
}
```
