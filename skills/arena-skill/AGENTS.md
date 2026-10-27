# arena-skill Agent Rules

- Keep source scripts in `skills/refs/arena-skill/` and build minified copies via `python3 maintenance/minify/minify.py --update`.
- Mirror `skills/refs/arena-skill/arena-egress-proxy/` edits directly to `skills/arena-skill/arena-egress-proxy/` because `minify.py` only syncs `scripts/` and `assets/`.
- Keep `arena-egress-proxy` `/v1/board` and `/v1/state` in shared SQLite (`WAL` mode) with SHA-256 blobs, `X-Master-Key` auth, and revision-cursor diff sync.

