#!/usr/bin/env python3
"""Seed sample Arena Steering data and launch a live demo server on a separate port."""

from __future__ import annotations

import argparse
import json
import os
import struct
import sys
import zlib
from datetime import UTC, datetime, timedelta
from pathlib import Path

from arena_steering.models import Attachment
from arena_steering.server import SteeringApp, create_http_server
from arena_steering.store import SqliteStore


def _build_demo_board_png(width: int = 480, height: int = 140) -> bytes:
  """Build a valid multi-panel dark-mode RGB PNG image using stdlib struct and zlib."""

  def png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(chunk_type + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + chunk_type + data + struct.pack(">I", crc)

  rows: list[bytes] = []
  mid_x = width // 2
  for y in range(height):
    row = bytearray([0])  # filter type 0 (None)
    for x in range(width):
      # Outer dark canvas (#1b1a19)
      r, g, b = (27, 26, 25)
      in_left = 12 <= x <= mid_x - 8 and 10 <= y <= height - 11
      in_right = mid_x + 8 <= x <= width - 13 and 10 <= y <= height - 11
      if in_left or in_right:
        px = x - 12 if in_left else x - (mid_x + 8)
        pw = (mid_x - 20) if in_left else (width - mid_x - 21)
        py = y - 10
        ph = height - 21
        # Panel border (#413d39)
        if px in (0, pw) or py in (0, ph):
          r, g, b = (65, 61, 57)
        # Panel top header bar (#2c2b28)
        elif py < 24:
          r, g, b = (44, 43, 40)
          # Status badge pill in header
          if 10 <= px <= 54 and 7 <= py <= 16:
            r, g, b = (244, 196, 6) if in_left else (65, 190, 75)
        else:
          # Panel body (#252523)
          r, g, b = (37, 37, 35)
          # Simulated content cards inside each panel
          if 12 <= px <= pw - 12 and (
            34 <= py <= 58 or 66 <= py <= 90 or 98 <= py <= 112
          ):
            r, g, b = (44, 43, 40)
            if px <= 15:
              r, g, b = (229, 187, 139) if in_right else (103, 98, 91)
      row.extend((r, g, b))
    rows.append(bytes(row))

  ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
  idat = zlib.compress(b"".join(rows), level=6)
  return (
    b"\x89PNG\r\n\x1a\n"
    + png_chunk(b"IHDR", ihdr)
    + png_chunk(b"IDAT", idat)
    + png_chunk(b"IEND", b"")
  )


def _build_animated_gif(
  width: int = 120, height: int = 24, accent_rgb: tuple[int, int, int] = (229, 187, 139)
) -> bytes:
  """Build a valid 4-frame looping GIF89a animation using uncompressed 4-color LZW blocks."""
  bg = (27, 26, 25)
  track = (65, 60, 58)
  glow = (141, 192, 127)
  palette = bytes([*bg, *track, *accent_rgb, *glow])

  def encode_uncompressed_lzw(indices: list[int]) -> bytes:
    # Minimum LZW code size = 2 (codes 0..3 = colors, 4 = clear, 5 = end).
    # Uncompressed 3-bit codes packed LSB-first with a clear code every 4 pixels.
    bits: list[int] = []

    def push_code(code: int, width_bits: int = 3) -> None:
      for bit_idx in range(width_bits):
        bits.append((code >> bit_idx) & 1)

    push_code(4)
    for idx, pix in enumerate(indices):
      push_code(pix & 3)
      if (idx + 1) % 4 == 0:
        push_code(4)
    push_code(5)

    out_bytes = bytearray()
    for i in range(0, len(bits), 8):
      chunk = bits[i : i + 8]
      byte_val = 0
      for b_idx, bit in enumerate(chunk):
        byte_val |= bit << b_idx
      out_bytes.append(byte_val)

    sub_blocks = bytearray([2])  # LZW min code size = 2
    pos = 0
    while pos < len(out_bytes):
      part = out_bytes[pos : pos + 254]
      sub_blocks.append(len(part))
      sub_blocks.extend(part)
      pos += 254
    sub_blocks.append(0)
    return bytes(sub_blocks)

  header = b"GIF89a" + struct.pack("<HHBBB", width, height, 0xF1, 0, 0) + palette
  netscape = b"\x21\xff\x0bNETSCAPE2.0\x03\x01\x00\x00\x00"
  frames = bytearray()
  seg_w = width // 4
  for frame_idx in range(4):
    gce = struct.pack("<BBBBHBB", 0x21, 0xF9, 4, 0x04, 18, 0, 0)
    img_desc = struct.pack("<BHHHHB", 0x2C, 0, 0, width, height, 0)
    pixels: list[int] = []
    bar_start = frame_idx * seg_w
    bar_end = bar_start + seg_w + 12
    for y in range(height):
      for x in range(width):
        if 8 <= y <= height - 9 and 6 <= x <= width - 7:
          if bar_start <= x <= bar_end:
            pixels.append(3 if x >= bar_end - 4 else 2)
          else:
            pixels.append(1)
        else:
          pixels.append(0)
    frames.extend(gce + img_desc + encode_uncompressed_lzw(pixels))
  return header + netscape + bytes(frames) + b"\x3b"


TOKENS_SWATCH_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="640" height="110" viewBox="0 0 640 110">
  <rect width="640" height="110" rx="8" fill="#1b1a19" stroke="#413d39"/>
  <g font-family="monospace" font-size="11" fill="#f4f0eb">
    <rect x="16" y="16" width="112" height="54" rx="6" fill="#252523" stroke="#413d39"/>
    <text x="24" y="88">--surface-primary</text>
    <rect x="142" y="16" width="112" height="54" rx="6" fill="#413c3a" stroke="#413d39"/>
    <text x="150" y="88">--surface-raised</text>
    <rect x="268" y="16" width="112" height="54" rx="6" fill="#e5bb8b" stroke="#413d39"/>
    <text x="292" y="88">--accent</text>
    <rect x="394" y="16" width="112" height="54" rx="6" fill="#7fa7d1" stroke="#413d39"/>
    <text x="412" y="88">--dot-seen</text>
    <rect x="520" y="16" width="104" height="54" rx="6" fill="#8dc07f" stroke="#413d39"/>
    <text x="536" y="88">--dot-said</text>
  </g>
</svg>
"""

SCROLLSPY_ZONES_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="640" height="120" viewBox="0 0 640 120">
  <rect width="640" height="120" rx="8" fill="#1b1a19" stroke="#413d39"/>
  <rect x="16" y="14" width="608" height="24" rx="4" fill="#2c2b28" stroke="#e5bb8b"/>
  <text x="28" y="30" font-family="monospace" font-size="12" fill="#e5bb8b">
    Top Scrollspy Threshold (48px) + Edge Fade Mask (24px)
  </text>
  <rect x="16" y="46" width="608" height="36" rx="4" fill="#252523" stroke="#413d39"/>
  <text x="28" y="68" font-family="monospace" font-size="12" fill="#f4f0eb">
    Active Viewport Region (Click-Lock 700ms + Section Flash)
  </text>
  <rect x="16" y="90" width="608" height="18" rx="4" fill="#2c2b28" stroke="#8dc07f"/>
  <text x="28" y="103" font-family="monospace" font-size="11" fill="#8dc07f">
    Bottom Clamp Zone (8px from scrollHeight)
  </text>
</svg>
"""


def _write_demo_media_files(store: SqliteStore) -> None:
  """Write PNG, SVG, GIF, and JSON demo files into <state_dir>/reports and <state_dir>/uploads."""
  db_path = getattr(store, "db_path", "")
  if not db_path or db_path == ":memory:":
    return
  state_dir = Path(db_path).resolve().parent
  reports_dir = state_dir / "reports"
  uploads_dir = state_dir / "uploads"
  reports_dir.mkdir(parents=True, exist_ok=True)
  uploads_dir.mkdir(parents=True, exist_ok=True)

  board_png = _build_demo_board_png()
  scroll_gif = _build_animated_gif(accent_rgb=(229, 187, 139))
  loading_gif = _build_animated_gif(accent_rgb=(244, 196, 6))

  (reports_dir / "layout-board.png").write_bytes(board_png)
  (reports_dir / "scroll-fade-demo.gif").write_bytes(scroll_gif)
  (reports_dir / "loading-bar-demo.gif").write_bytes(loading_gif)
  (reports_dir / "tokens-swatch.svg").write_text(TOKENS_SWATCH_SVG, encoding="utf-8")
  (reports_dir / "scrollspy-zones.svg").write_text(
    SCROLLSPY_ZONES_SVG, encoding="utf-8"
  )

  (uploads_dir / "inbox-capture.png").write_bytes(board_png)
  (uploads_dir / "ui-motion-preview.gif").write_bytes(scroll_gif)
  (uploads_dir / "arena-tokens.json").write_text(
    json.dumps(
      {
        "surface-primary": "60 3% 14%",
        "surface-raised": "24 6% 24%",
        "accent": "#e5bb8b",
      },
      indent=2,
    ),
    encoding="utf-8",
  )
  (uploads_dir / "modulepreload-trace.txt").write_text(
    "GET /app.js 200\nGET /messages-view.js 200\nGET /reports-view.js 200\n",
    encoding="utf-8",
  )


def _set_demo_timestamps(store: SqliteStore) -> None:
  """Spread demo timestamps across recent minutes and hours."""
  now = datetime.now(UTC)

  def iso_ago(seconds: int) -> str:
    return (now - timedelta(seconds=seconds)).strftime("%Y-%m-%dT%H:%M:%SZ")

  msg_offsets = {
    "a00001": 7200,
    "a00002": 5400,
    "a00003": 3600,
    "a00004": 2400,
    "a00005": 900,
    "a00006": 420,
    "a00007": 180,
    "a00008": 120,
    "a00009": 65,
    "a00010": 35,
  }
  for idx in range(11, 36):
    msg_offsets[f"a{idx:05d}"] = 10800 + (36 - idx) * 600
  with store._lock, store._conn as conn:
    for mid, secs in msg_offsets.items():
      stamp = iso_ago(secs)
      conn.execute(
        "UPDATE messages SET modified_at = ? WHERE id = ?",
        (stamp, mid),
      )
    conn.execute(
      "UPDATE reports SET modified_at = ? WHERE id = 'steering-architecture'",
      (iso_ago(120),),
    )
    conn.execute(
      "UPDATE reports SET modified_at = ? WHERE id = 'ui-layout-audit'",
      (iso_ago(60),),
    )
    conn.execute(
      "UPDATE reports SET modified_at = ? WHERE id = 'visual-diff-gallery'",
      (iso_ago(240),),
    )
    conn.execute(
      "UPDATE reports SET modified_at = ? WHERE id = 'runtime-metrics'",
      (iso_ago(320),),
    )
    conn.execute(
      "UPDATE tasks SET modified_at = ? WHERE status = 'in_progress'",
      (iso_ago(60),),
    )


def reseed_demo_store(store: SqliteStore) -> None:
  """Clear and populate exhaustive Messages, Tasks, Reports, Survey, and media assets."""
  with store._lock, store._conn as conn:
    conn.execute("DELETE FROM messages")
    conn.execute("DELETE FROM tasks")
    conn.execute("DELETE FROM reports")
    conn.execute("DELETE FROM meta")

  _write_demo_media_files(store)

  store._seeding_demo = True  # type: ignore[attr-defined]
  try:
    app = SteeringApp(store)
  finally:
    store._seeding_demo = False  # type: ignore[attr-defined]

  # Seed historical messages (a00011..a00035) before recent messages so upward scroll paginates cleanly.
  for idx in range(11, 36):
    mid = f"a{idx:05d}"
    m_hist = app.messages.send_message(
      f"Historical steering checkpoint #{idx - 10}: verified schema migration step `{mid}`.",
      blocking=(idx % 3 != 0),
      hidden=(idx % 5 == 0),
      msg_id=mid,
    )
    app.messages.ack(
      m_hist.id,
      f"Completed checkpoint `{mid}` and updated validation fixtures (`core-models-store`).",
    )

  # 1. Messages covering sent, seen, acked (single + multi-ack), attachments (present PNG/GIF/JSON + missing),
  #    inline images/GIFs, fenced code blocks (bash, python, json, diff), GFM tables, blockquotes, and hidden notes.
  m1 = app.messages.send_message(
    "Establish the **Messages**, **Tasks**, and **Reports** contracts before implementation.",
    blocking=True,
    hidden=False,
    msg_id="a00001",
  )
  app.messages.ack(
    m1.id,
    "Locked the contracts in `steering-architecture` (`core-models-store`, `draft-architecture-spec`).",
  )

  m2 = app.messages.send_message(
    (
      "Use Arena color tokens with `Basel_Grotesk` fonts and `nuu` interaction recipes.\n\n"
      "![Arena Token Swatches](/reports/tokens-swatch.svg)"
    ),
    blocking=True,
    hidden=False,
    attachments=[
      Attachment(
        name="arena-tokens.json",
        path="uploads/arena-tokens.json",
        size_bytes=29324,
        present=True,
      ),
      Attachment(
        name="inbox-capture.png",
        path="uploads/inbox-capture.png",
        size_bytes=14280,
        present=True,
      ),
    ],
    msg_id="a00002",
  )
  app.messages.ack(
    m2.id,
    "Imported Arena dark-mode CSS custom properties into `assets/style.css` (`web-ui-assets`).",
  )
  app.messages.ack(
    m2.id,
    (
      "Bundled all 5 `Basel_Grotesk_*.woff2` font weights and verified the before/after board:\n\n"
      "![Before and After Layout Board](/reports/layout-board.png)"
    ),
  )

  m3 = app.messages.send_message(
    "Keep the server port configurable so the live demo can run alongside port 8000.",
    blocking=True,
    hidden=False,
    msg_id="a00003",
  )
  app.messages.ack(
    m3.id,
    (
      "Configured `steer serve --port` and `STEER_PORT` with default port `8100` (`hot-reload-server`):\n"
      "```bash\nsteer serve --port 8100\n```"
    ),
  )

  m4 = app.messages.send_message(
    "Internal checkpoint: verified SQLite WAL mode and foreign-key constraints.",
    blocking=False,
    hidden=True,
    msg_id="a00004",
  )
  app.messages.ack(
    m4.id,
    "Confirmed WAL journal mode and index coverage on `messages`, `tasks`, and `reports` (`configure-ci-gates`).",
  )

  m5 = app.messages.send_message(
    (
      "Ensure hot reload swaps the request handler in-process and verify the scroll-edge fade animation:\n\n"
      "![Scroll Edge Fade Animation](/reports/scroll-fade-demo.gif)"
    ),
    blocking=True,
    hidden=False,
    attachments=[
      Attachment(
        name="ui-motion-preview.gif",
        path="uploads/ui-motion-preview.gif",
        size_bytes=8192,
        present=True,
      )
    ],
    msg_id="a00005",
  )
  app.messages.ack(
    m5.id,
    (
      "Updated `watch_hot_reload` to reload `arena_steering` modules and swap "
      "`server.RequestHandlerClass` in-place (`hot-reload-server`):\n"
      "```python\n"
      "def reload_server_handler(server: ThreadingHTTPServer, app: SteeringApp) -> SteeringApp:\n"
      "    new_app = SteeringApp(new_store, assets_dir=app.assets_dir)\n"
      "    server.RequestHandlerClass = make_request_handler(new_app)\n"
      "    return new_app\n"
      "```"
    ),
  )

  m6 = app.messages.send_message(
    (
      "Check how pruned or missing upload attachments and GFM tables render in the message log:\n\n"
      "| Asset | Type | State |\n"
      "| --- | --- | --- |\n"
      "| `inbox-capture.png` | `image/png` | ==Present== |\n"
      "| `stale-heap-profile.json` | `application/json` | ~~Pruned~~ `(missing)` |"
    ),
    blocking=True,
    hidden=False,
    attachments=[
      Attachment(
        name="stale-heap-profile.json",
        path="uploads/stale-heap-profile.json",
        size_bytes=184320,
        present=False,
      )
    ],
    msg_id="a00006",
  )
  app.messages.ack(
    m6.id,
    "Verified that missing attachments render a muted `(missing)` indicator alongside the filename (`web-ui-assets`).",
  )

  # Messages in `seen` state (read by agent, awaiting acknowledgement)
  app.messages.send_message(
    (
      "Preload ES module scripts in `index.html` so sub-imports resolve cleanly (`publish-audit-report`).\n\n"
      "> All ES module sub-imports carry the document URL as `referrer`."
    ),
    blocking=True,
    hidden=False,
    attachments=[
      Attachment(
        name="modulepreload-trace.txt",
        path="uploads/modulepreload-trace.txt",
        size_bytes=4120,
        present=True,
      )
    ],
    msg_id="a00007",
  )
  app.messages.send_message(
    (
      "Also document the `STEER_PORT` and `STEER_STATE_DIR` environment "
      "variables in `SKILL.md` (`document-cli-reference`)."
    ),
    blocking=False,
    hidden=False,
    msg_id="a00008",
  )
  app.messages.read_pending(mark_seen=True)

  # Messages in `sent` state (unread by agent)
  app.messages.send_message(
    (
      "Verify that `/health` exposes `asset_version` so the browser hot-reloads assets:\n"
      "```json\n"
      '{\n  "ok": true,\n  "version": "2.0.0",\n  "repo": "clankers"\n}\n'
      "```"
    ),
    blocking=True,
    hidden=False,
    msg_id="a00009",
  )
  app.messages.send_message(
    (
      "Confirm relative timestamps floor sub-minute offsets to `0m ago` / `0 minutes ago`:\n"
      "- [x] Minute-boundary timer scheduling\n"
      "- [x] No second-level jitter"
    ),
    blocking=True,
    hidden=False,
    msg_id="a00010",
  )

  # 2. Reports covering:
  #    - `steering-architecture`: published, unseen (`seen=False`), unanswered (`needs_answer=True`)
  #    - `ui-layout-audit`: answered with 1 acked answer + 1 unacked answer (`seen=True`)
  #    - `visual-diff-gallery`: answered with all answers acked (`seen=True`)
  #    - `runtime-metrics`: published read-only report (`0` fields, `seen=False`)
  #    - `legacy-migration-draft`: dismissed report (evicted from active list with archived answer in meta)
  app.reports.publish_report(
    "steering-architecture",
    "Arena Steering: Architecture & Storage Config",
    """# Arena Steering Architecture

Review the storage, transport, and rendering fields below. Answering this report unblocks `finalize-storage-tuning`.

## Visual Overview & Token Palette

![Before and After Layout Board](/reports/layout-board.png)

![Arena Token Swatches](/reports/tokens-swatch.svg)

![Scroll Edge Fade Animation](/reports/scroll-fade-demo.gif)

## Subsystem Status

| Subsystem | Implementation | Transport / Storage | Latency Target | Status |
| --- | --- | --- | --- | --- |
| Persistence | `SqliteStore` (WAL mode) | `state.sqlite3` + WAL/SHM | `< 2.5 ms` p99 | Active |
| HTTP & RPC | `ThreadingHTTPServer` (`0.0.0.0:8100`) | REST + `/api/ws` WebSocket | `< 5.0 ms` p99 | Active |
| Markdown Cache | `markdown-it-py` + render cache | In-memory `(id, modified_at)` | `< 0.5 ms` hit | Active |
| Web UI | Unminified ES Modules + Arena CSS | Vendored PrismJS + Mermaid | `60 fps` scroll | Active |

## Request & Poll Topology

```mermaid
flowchart LR
  Browser[Browser UI] -->|WebSocket /api/ws| Router[SteeringApp Router]
  CLI[steer CLI] -->|GET /poll 1799s, POST /ack| Router
  Router --> Services[Message / Task / Report Services]
  Services --> Store[(SqliteStore WAL)]
```

### WebSocket Push & RPC Sequence

```mermaid
sequenceDiagram
  participant UI as Browser UI
  participant WS as /api/ws Handler
  participant DB as SqliteStore (WAL)
  UI->>WS: Upgrade WebSocket + rpc(state)
  WS->>DB: Query messages, tasks, reports, survey
  DB-->>WS: Snapshot payload
  WS-->>UI: rpc_result (initial render)
  Note over WS,DB: PRAGMA data_version poll (250ms)
  DB-->>WS: State mutation detected
  WS-->>UI: push {"type": "change"}
```

## Server-Side Markdown Cache

Server-side rendering caches parsed blocks in memory by `(report_id, modified_at)` and evicts dismissed entries:

```python
_REPORT_RENDER_CACHE: dict[str, tuple[str, list[dict[str, Any]], list[dict[str, str]]]] = {}

def serialize_cached_report(report: Report) -> list[dict[str, Any]]:
    cached = _REPORT_RENDER_CACHE.get(report.id)
    if cached is not None and cached[0] == report.modified_at:
        return cached[1]
    raw_blocks, _ = parse_report_markdown(report.body)
    return [render_block(block) for block in raw_blocks]
```

## Diff & GFM Extensions

Highlighted ==critical path== updates and ~~deprecated polling flags~~ with unified diff tokenization:

```diff
@@ -18,4 +18,4 @@
-steer poll --timeout 30 --interval 2
+steer poll
-Inbox: 0 pending
+Inbox 14:22:09: 0 pending
```

- [x] Indefinite server-side HTML cache keyed by `modified_at`
- [x] Vendored PrismJS syntax highlighting with GitHub Dark Dimmed tokens
- [x] Hybrid TOC scrollspy with click-lock and bottom-of-page clamp
- [ ] Optional multi-session board integration

## Storage & View Options

<!-- question {"id": "storage-mode", "label": "We should use this SQLite synchronous mode"} -->
We should use this SQLite synchronous mode
- (x) NORMAL with WAL journal mode for low-latency writes <!-- option {"label": "NORMAL with WAL"} -->
- ( ) FULL synchronous mode on every transaction <!-- option {"label": "FULL synchronous mode on every transaction"} -->
- ( ) MEMORY journal mode for ephemeral runs <!-- option {"label": "MEMORY journal mode for ephemeral runs"} -->

<!-- question {"id": "enabled-views", "label": "We should enable these live steering capabilities"} -->
We should enable these live steering capabilities
- [x] Inbox messages with Markdown acknowledgements <!-- option {"label": "Inbox acknowledgements"} -->
- [x] Agent-managed dependency task queue <!-- option {"label": "Agent-managed dependency task queue"} -->
- [x] Fielded Markdown reports with custom responses <!-- option {"label": "Fielded reports"} -->
- [ ] Experimental webhook forwarding <!-- option {"label": "Experimental webhook forwarding"} -->

## Reviewer Notes

<!-- question {"id":"additional-reviewer-note","label":"Additional reviewer note"} -->
Additional reviewer note:
""",
  )

  app.reports.publish_report(
    "ui-layout-audit",
    "UI Layout, Scrollspy & Loading Bar Audit",
    """# UI Layout, Scrollspy & Loading Bar Audit

Summary of layout, scrollspy, and edge-loading adjustments across **Messages**, **Reports**, and **Tasks**:

## Edge Loading Bar & Scrollspy Zones

![Edge Loading Bar Animation](/reports/loading-bar-demo.gif)

![Scrollspy Threshold and Clamp Zones](/reports/scrollspy-zones.svg)

## Alignment Contract

> All three tab panels share a `900px` max-width container with a `100vw` Messages scrollbar.

```css
.app-shell {
  display: flex;
  flex-direction: column;
  height: 100dvh;
  overflow: hidden;
}

.report-content pre,
.report-content .mermaid-block {
  width: 100%;
  box-sizing: border-box;
}
```

## Scrollspy & Mobile Navigation

```javascript
export function lockTocSelection(secId, durationMs = 700) {
  tocLockUntil = Date.now() + durationMs;
  setActiveTocLink(secId);
}
```

## Verification Questions

<!-- question {"id": "density-mode", "label": "Preferred spacing density across list views"} -->
Preferred spacing density across list views
- (x) Compact borderless rows with 2ch hanging indent <!-- option {"label": "Compact rows"} -->
- ( ) Padded card containers <!-- option {"label": "Padded card containers"} -->

<!-- question {"id": "verified-tabs", "label": "Tabs verified in live preview"} -->
Tabs verified in live preview
- [x] Messages tab <!-- option {"label": "Messages tab"} -->
- [x] Reports tab <!-- option {"label": "Reports tab"} -->
- [x] Tasks tab <!-- option {"label": "Tasks tab"} -->

<!-- question {"id": "layout-observation", "label": "Layout observation note"} -->
Layout observation note:
""",
  )
  ans1 = app.reports.submit_answer(
    "ui-layout-audit",
    {
      "density-mode": "Compact borderless rows with 2ch hanging indent",
      "verified-tabs": ["Messages tab", "Reports tab", "Tasks tab"],
      "layout-observation": "Desktop and mobile scrollbars align cleanly.",
    },
    answer_id="f00001",
  )
  app.reports.ack_answer(
    "ui-layout-audit",
    ans1.id,
    (
      "Applied compact borderless rows across **Reports** and **Tasks** "
      "and verified `2ch` list alignment (`web-ui-assets`)."
    ),
  )
  app.reports.submit_answer(
    "ui-layout-audit",
    {
      "density-mode": "Compact borderless rows with 2ch hanging indent",
      "verified-tabs": ["Messages tab", "Reports tab"],
      "layout-observation": "Recheck mobile TOC collapse after selecting a heading.",
    },
    answer_id="f00002",
  )

  app.reports.publish_report(
    "visual-diff-gallery",
    "Visual Diff Gallery & Media Rendering Showcase",
    """# Visual Diff Gallery & Media Rendering Showcase

This report showcases embedded PNG comparison boards, animated GIFs, vector SVGs, and Mermaid state diagrams.

## Side-by-Side Before & After Board

![Before and After Layout Board](/reports/layout-board.png)

## Animated Motion Previews

![Scroll Edge Fade Animation](/reports/scroll-fade-demo.gif)

![Edge Loading Bar Animation](/reports/loading-bar-demo.gif)

## Report Lifecycle State Machine

```mermaid
stateDiagram-v2
  [*] --> published: steer report pub
  published --> answered: POST /reports/{id}/answers
  answered --> answered: POST /ack or new answer
  published --> dismissed: steer report rm
  answered --> dismissed: steer report rm (after ack)
  dismissed --> [*]
```

## Gallery Review

<!-- question {"id": "media-rendering-check", "label": "Verified media asset rendering across formats"} -->
Verified media asset rendering across formats
- [x] PNG before/after comparison boards <!-- option {"label": "PNG before/after comparison boards"} -->
- [x] Animated looping GIF89a previews <!-- option {"label": "Animated looping GIF89a previews"} -->
- [x] Inline SVG token and scrollspy diagrams <!-- option {"label": "Inline SVG token and scrollspy diagrams"} -->
- [x] Mermaid flowchart, sequence, and state diagrams <!-- option {"label": "Mermaid diagrams"} -->
""",
  )
  ans_gallery = app.reports.submit_answer(
    "visual-diff-gallery",
    {
      "media-rendering-check": [
        "PNG before/after comparison boards",
        "Animated looping GIF89a previews",
        "Inline SVG token and scrollspy diagrams",
        "Mermaid flowchart, sequence, and state diagrams",
      ]
    },
    answer_id="f00003",
  )
  app.reports.ack_answer(
    "visual-diff-gallery",
    ans_gallery.id,
    "Confirmed all 4 visual media formats render offline without external CDN requests (`draft-architecture-spec`).",
  )

  app.reports.publish_report(
    "runtime-metrics",
    "Runtime Poll & SQLite Latency Benchmark",
    """# Runtime Poll & SQLite Latency Benchmark

Read-only benchmark report comparing SQLite WAL queries, server HTML cache hits, and long-poll wakeup latency.

## Latency Summary

| Operation | p50 Latency | p99 Latency | Throughput | Notes |
| --- | --- | --- | --- | --- |
| `POST /messages` | `0.8 ms` | `2.1 ms` | `1,150 req/s` | Atomic insert + `Condition.notify_all()` |
| `GET /poll` | `1.1 ms` | `3.4 ms` | `940 req/s` | Immediate wake on new message or report answer |
| `GET /reports/{id}` | `0.2 ms` | `0.5 ms` | `4,200 req/s` | Indefinite `_REPORT_RENDER_CACHE` hit |
| `GET /tasks?full=1` | `0.6 ms` | `1.5 ms` | `1,620 req/s` | Computed `blocked` state across dependencies |

## SQLite Schema & Indexing

```sql
CREATE TABLE IF NOT EXISTS reports (
  seq INTEGER PRIMARY KEY AUTOINCREMENT,
  id TEXT NOT NULL UNIQUE,
  title TEXT NOT NULL,
  body TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'published'
);
```

## CLI Poll Command

```bash
steer poll
```
""",
  )

  app.reports.publish_report(
    "legacy-migration-draft",
    "Legacy Preview Migration Notes",
    (
      "# Legacy Migration Notes\n"
      "\n"
      '<!-- question {"id":"we-should-archive-this-draft","label":"We should archive this draft"} -->\n'
      "We should archive this draft\n"
      '- (x) Yes <!-- option {"label":"Yes"} -->\n'
      '- ( ) No <!-- option {"label":"No"} -->\n'
    ),
  )
  ans_legacy = app.reports.submit_answer(
    "legacy-migration-draft",
    {"we-should-archive-this-draft": "Yes"},
    answer_id="f00000",
  )
  app.reports.ack_answer(
    "legacy-migration-draft",
    ans_legacy.id,
    "Archived `legacy-migration-draft` and preserved its answer in `meta`.",
  )
  app.reports.remove_report("legacy-migration-draft")

  # 3. Tasks covering `Current` (`in_progress`), `Upcoming` (`upcoming` unblocked + blocked by report + blocked by dep),
  #    and `Finished` (`finished`, 35 total so downward scroll paginates 30 + 5), across all 5 types.
  app.tasks.create_task(
    "core-models-store",
    "Build domain models, protocol ports, and SQLite store",
    type="code",
    status="finished",
    scope="skills/arena-steering/scripts/arena_steering/",
    details=[
      "Defined Message, Task, Report, ReportField, and ReportAnswer models.",
      "Implemented thread-safe SqliteStore in WAL mode.",
    ],
    msg_ids=["a00001"],
  )
  app.tasks.create_task(
    "draft-architecture-spec",
    "Publish initial Arena Steering architecture specification",
    type="report",
    status="finished",
    scope="arena-state/reports/",
    details=[
      "Published steering-architecture report with choice, checkbox, and text fields.",
    ],
    msg_ids=["a00001"],
    report_ids=["steering-architecture", "visual-diff-gallery"],
  )
  app.tasks.create_task(
    "configure-ci-gates",
    "Wire ruff, pytest, and prose lint gates for steering skill",
    type="ops",
    status="finished",
    scope="maintenance/",
    details=[
      "Configured pytest and ruff validation suites for arena_steering.",
    ],
    msg_ids=["a00004"],
  )
  app.tasks.create_task(
    "update-readme-index",
    "Register arena-steering in repository skill documentation",
    type="docs",
    status="finished",
    scope="skills/arena-steering/SKILL.md",
    details=[
      "Documented steer CLI workflow and REST API endpoints.",
    ],
  )
  task_types = ("code", "docs", "report", "ops", "misc")
  for idx in range(1, 32):
    app.tasks.create_task(
      f"finished-milestone-{idx:02d}",
      f"Complete steering verification milestone #{idx:02d}",
      type=task_types[idx % len(task_types)],
      status="finished",
      scope="skills/arena-steering/",
      details=[
        f"Verified milestone #{idx:02d} regression suite and UI state.",
      ],
    )

  app.tasks.create_task(
    "web-ui-assets",
    "Refine Inbox, Reports, and Tasks views with Arena tokens",
    type="code",
    status="in_progress",
    scope="skills/arena-steering/assets/",
    details=[
      "Loaded Arena dark-mode CSS tokens and Basel Grotesk fonts into style.css.",
      "Rendered fenced code blocks with language headers and copy buttons.",
      "Restored three-column Reports layout with TOC and scrollable report picker.",
    ],
    msg_ids=["a00002", "a00006"],
    deps=["core-models-store"],
  )
  app.tasks.create_task(
    "hot-reload-server",
    "Maintain in-process hot-reload watcher on port 8100",
    type="ops",
    status="in_progress",
    scope="skills/arena-steering/scripts/arena_steering/server.py",
    details=[
      "Swaps server.RequestHandlerClass in-process without dropping TCP connections.",
      "Includes asset_version hash in /health for browser live reload.",
    ],
    msg_ids=["a00003", "a00005"],
  )

  app.tasks.create_task(
    "publish-audit-report",
    "Publish layout and latency audit report for review",
    type="report",
    status="upcoming",
    scope="arena-state/reports/",
    details=[
      "Summarizes viewport scrollbar alignment and SQLite WAL latency.",
    ],
    msg_ids=["a00007"],
    report_ids=["ui-layout-audit"],
  )
  app.tasks.create_task(
    "finalize-storage-tuning",
    "Apply selected SQLite journal and synchronous parameters",
    type="code",
    status="upcoming",
    scope="skills/arena-steering/scripts/arena_steering/store.py",
    details=[
      "Awaiting storage-mode selection in steering-architecture report.",
    ],
    report_ids=["steering-architecture"],
    deps=["web-ui-assets"],
  )
  app.tasks.create_task(
    "document-cli-reference",
    "Document steer CLI subcommands and environment variables",
    type="docs",
    status="upcoming",
    scope="skills/arena-steering/SKILL.md",
    details=[
      "Cover STEER_PORT, STEER_STATE_DIR, and fixed 1799s poll behavior.",
    ],
    msg_ids=["a00008"],
    deps=["web-ui-assets"],
  )
  app.tasks.create_task(
    "cleanup-temp-fixtures",
    "Prune stale preview fixture directories and verify gitignore",
    type="misc",
    status="upcoming",
    scope="tests/skills/arena-steering/",
    details=[
      "Ensure temporary SQLite WAL files are cleaned up after test runs.",
    ],
  )

  # 4. Seed sample survey results so the Survey Results modal (#survey-modal) displays graded checks.
  app.messages.submit_survey(
    json.dumps(
      [
        {"id": "R3S0N", "answer": {"reasoning": True}},
        {"id": "V1S0N", "answer": {"vision": True}},
        {
          "id": "S2E5P",
          "answer": {
            "full_name": "unknown",
            "organization": "unknown",
            "role": "unknown",
          },
          "confidence": 0,
        },
        {
          "id": "A2P6R",
          "answer": {
            "command_name": "REPACK",
            "concurrency_option": "CONCURRENTLY",
          },
          "confidence": 0.95,
        },
        {
          "id": "M2A6Y",
          "answer": {
            "data_center": "unknown",
            "power_capacity_mw": {"operator": "unknown", "value": "unknown"},
            "nvidia_gpu_count": {"operator": "unknown", "value": "unknown"},
          },
          "confidence": 0,
        },
      ]
    )
  )

  _set_demo_timestamps(store)


def seed_demo_store(store: SqliteStore) -> SteeringApp:
  """Populate realistic Inbox, Tasks, and Reports records for UI inspection."""
  reseed_demo_store(store)
  store._seeding_demo = True  # type: ignore[attr-defined]
  try:
    return SteeringApp(store)
  finally:
    store._seeding_demo = False  # type: ignore[attr-defined]


def main(argv: list[str] | None = None) -> int:
  default_port = int(os.environ.get("STEER_DEMO_PORT", "8100"))
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("--host", default="0.0.0.0")
  parser.add_argument("--port", type=int, default=default_port)
  parser.add_argument(
    "--seed-only",
    action="store_true",
    help="Seed the state database and exit without starting the HTTP server.",
  )
  args = parser.parse_args(argv)

  state_dir = Path("arena-state/demo")
  state_dir.mkdir(parents=True, exist_ok=True)
  db_path = state_dir / "state.sqlite3"
  store = SqliteStore(db_path)
  app = seed_demo_store(store)

  if args.seed_only:
    print(f"Seeded Arena Steering demo database at {db_path}")
    return 0

  server = create_http_server(app, host=args.host, port=args.port)
  actual_port = server.server_address[1]
  print(
    f"Arena Steering demo listening on http://{args.host}:{actual_port} (db: {db_path})",
    flush=True,
  )
  try:
    server.serve_forever()
  except KeyboardInterrupt:
    pass
  finally:
    server.server_close()
  return 0


if __name__ == "__main__":
  sys.exit(main())
