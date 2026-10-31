# V2 state backup and clear contract

This document defines planned behavior. The v2 userscript, container backup, and clear flow are not implemented yet.

## Discovery and backup

1. The userscript discovers the active steering URL and sends it to the Docker container.
2. The container connects to steering and copies a full state snapshot with its cursor.
3. The container uses WebSocket to receive notifications and copy every state change, including deletions.
4. After reconnecting, it reconciles a full snapshot so missed changes and deletions do not leave an inconsistent copy.
5. It copies referenced static files, including images, GIFs, and report Markdown. It verifies their bytes before reporting a complete backup.

## Clear and restore

- Keep a pre-clear restore point when a backup can be made. Do not replace that point with the empty post-clear state.
- If Docker cannot confirm a complete backup, warn but still allow clear. Causes include disconnection, full storage, and failed file verification.
- Restore uses an explicitly selected backup. A backup does not automatically replace live state.

## Current limits

The current WebSocket provides change notifications, and state routes provide snapshots and incremental rows. Incremental rows do not describe deletions. The asset inventory currently lists uploads, not all referenced report files. Existing exports alone do not guarantee that referenced file bytes are present.

The implementation must define and test transport authentication, durable storage, asset discovery, and recovery. This contract does not change v1 backup behavior.
