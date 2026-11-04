# Arena Steering notice inventory

This reference lists current v2 violations, neutral blocks, reminders, and runtime advisories. Its numbered rows keep the original audit's identifiers, including removed and superseded entries. The v2 release remains pending.

**V** = violation. Each V appends this separate string: `If full bible missing, use read_file for {paths}`. The paths are the full root `AGENTS.md`, root `ARENA.md`, and installed steering `SKILL.md`. Read them only when their full text is absent from active context. **N** = warning, block, or reminder without a violation flag. N never appends BIBLE_READ. The classification markers are not user-facing notice text.

## Full numbered inventory

| # | Class and source | Trigger | Current user-facing notice and recovery |
| --- | --- | --- | --- |
| 01 | V. `cli._run_pre` hidden cadence flag. | Pending inbox, Bash threshold reached. | VIOLATION: Bash blocked after {GATE_THRESHOLD} calls. `steer read` and `steer ack` now. Plus BIBLE_READ. |
| 02 | V. `cli._run_pre` hidden pipe flag. | Piped `steer read` or `steer poll`. | `VIOLATION: Inbox piped.` Plus BIBLE_READ. Immediate 08 also gives the run-alone recovery. |
| 03 | V. `cli._run_pre` hidden sleep flag. | Blocked sleep guard. | `VIOLATION: Sleep blocked. Use worktree if more task open, else poll.` Plus BIBLE_READ. |
| 04 | Replaced. `cli._run_pre`. | Staged session-ID citation formerly created a hidden flag. | No duplicate hidden flag. The immediate violation is 15. Staged wireframes remain warning-only. |
| 05 | V. `services.MessageService.flag_dirty_finish`. | Task finish with dirty Git tree. | `VIOLATION: Finish task with dirty tree. Clean tree then retry.` Plus BIBLE_READ. |
| 06 | V. `services.MessageService.flag_repeat_poll`. | Fast repeated poll within 45 seconds. | `VIOLATION: Repeat poll. Use worktree if more task open.` Plus BIBLE_READ. |
| 07 | V. `server.SteeringApp._handle_flag_violation`. | Owner flags a Messages, Reports, or Tasks violation. | `VIOLATION: {reason}. Ack with file:ln: clause then fix cause.` Keeps cited note, report source, or task context. Plus BIBLE_READ. |
| 08 | V. `pre.InboxPipeGuard`. | Piped steering inbox read or poll. | `VIOLATION: Inbox piped.` Run `steer read` or `steer poll` alone. Plus BIBLE_READ. |
| 09 | V. `pre.PollTimeoutGuard`. | Shell `timeout` wraps `steer poll`. | `VIOLATION: timeout wrapped poll. Set Bash tool timeout 1800s.` Poll returns within 1799s. Plus BIBLE_READ. |
| 10 | V. `pre.PrStateGuard`. | PR merge, close, reopen, or API state mutation. | `VIOLATION: PR mod blocked. NEVER merge, close, reopen.` Use reads or metadata edits. Plus BIBLE_READ. |
| 11 | V. `pre.DestructivePushGuard`. | Delete, mirror, prune, or destructive ref push. | `VIOLATION: Push blocked. Destructive mod found.` Remove destructive flags or ref deletion. Plus BIBLE_READ. |
| 12 | N. `pre.GitSafetyGuard`. | Push preflight has no working directory. | `Push blocked. remote default compare failed. Check remote and retry.` No BIBLE_READ. |
| 13 | N. `pre.GitSafetyGuard`. | Commit, push, or run start in managed worktree. | `{command} blocked in worktree. Run in the main checkout.` No BIBLE_READ. |
| 14 | N. `pre.WireframeGuard`. | Stage or commit line mentions a `-wireframe.png` capture. | `Commit has wireframe. Remove and retry.` No BIBLE_READ or hidden flag. |
| 15 | V. `git_safety.staged_warning` through `cli._run_pre`. | Added staged line cites a session-local ID. | `VIOLATION: Cited session-local ID. {path}:{line}: {id}. Remove the citation and retry.` Genuine task/report name clashes add `steer ren OLD_ID NEW_ID`. Plus BIBLE_READ immediately. No hidden duplicate. |
| 16 | N. `git_safety.staged_warning`. | Git diff cannot inspect staged changes. | `Git changes failed detect. Retry after recover.` No BIBLE_READ. |
| 17 | V. `git_safety.push_warning` through `cli._run_pre`. | Push would update remote default. | `VIOLATION: Push blocked. Only push {current}. Forbidden target: {remote}/{default}.` Plus BIBLE_READ. |
| 18 | N. `git_safety.push_warning`. | Remote default is not an ancestor of HEAD. | `Push blocked. Rebase default and retry. {remote}/{default} is not an ancestor of HEAD.` No BIBLE_READ. |
| 19 | N. `git_safety.push_warning`. | Remote lookup, fetch, or comparison failed. | `Push blocked. remote default compare failed. Check remote and retry.` No BIBLE_READ. |
| 20 | V. `pre.InboxGate`. | Push with pending inbox. | `VIOLATION: Push blocked. Inbox has pending. Read and ack all. Retry.` Prints pending IDs and blocked command. Plus BIBLE_READ. |
| 21 | N. `pre.InboxGate`. | Pending inbox but Bash threshold not reached. | `bash block in {remaining} calls. Read and ack now.` No BIBLE_READ. |
| 22 | V. `pre.InboxGate`. | Bash threshold reached. | `VIOLATION: Bash blocked. Read and ack all NOW.` Prints threshold and blocked part. Plus BIBLE_READ. |
| 23 | N. `git_safety.staged_warning`. | Commit includes staged wireframe captures. | `Wireframe found staged. Remove before commit. Captures: {names}` No BIBLE_READ or hidden flag. |
| 24 | V. `pre.SleepGuard`. | Sleep combined with steering call. | `VIOLATION: Sleep BANNED. Run alone.` Plus BIBLE_READ. |
| 25 | V. `pre.SleepGuard`. | Sleep combined with `.log` read. | `VIOLATION: Sleep log read BANNED. Read log later, start worktree for open task, poll if no more task.` Plus BIBLE_READ. |
| 26 | V. `pre.SleepGuard`. | Sleep while background run is live. | `VIOLATION: Sleep run BANNED. Read log later, start worktree for open task, poll if no more task.` Names live run. Plus BIBLE_READ. |
| 27 | V. `pre.SleepGuard`. | Sleep at or above `{SLEEP_IDLE_CAP_SECONDS}` seconds. | `VIOLATION: Sleep BANNED over {SLEEP_IDLE_CAP_SECONDS}s. Use detached runs.` Plus BIBLE_READ. |
| 28 | V. `pre.BibleReadGuard`. | Partial Bash read of protected bible path. | VIOLATION: Partial read blocked: {found}. Use `read_file` only if absent from context. Plus BIBLE_READ. |
| 29 | V. `pre.RouteGuard`. | Auto-detach would replay mixed shell line. | VIOLATION: Mixed shell blocked for auto detach. Use separate calls or explicit `steer run start`. Gives the detached command and GitHub-helper recovery. Plus BIBLE_READ. |
| 30 | N. `pre.RouteGuard`. | Direct PR PATCH needs helper. | PR PATCH routed. Use `steer pr-update -n {number} -t <title> -f <workspace-file>` instead of direct curl PATCH. No BIBLE_READ. |
| 31 | N. `cli._pre_state_unavailable`. | Push when steering state unavailable. | `PUSH BLOCKED: steering state unavailable ({reason}).` Policy change to allow such pushes remains deferred. No BIBLE_READ. |
| 32 | N. `cli._run_pre_route`. | Detached helper or PR helper failed. | `Run failed: {error}. Original did not run. Fix and retry safely.` No BIBLE_READ. |
| 33–34 | Removed. `cli` standalone `steer gate` command. | No current v2 production caller. | Approved removal of obsolete parser, handler, docs, and tests. Installed `steer pre` inbox guards remain. |
| 35 | V. `cli._run_pr_update`. | PR title/body cites session-local ID. | VIOLATION: Cited session-local ID in PR data. If name clash `steer ren OLD_ID NEW_ID` and retry. Prints title/body line locations. Plus BIBLE_READ. |

## Other user-visible steering reminders and status

| Class and source | Trigger | Text, action, and limits |
| --- | --- | --- |
| N. `cli._schedule_instruction_check`. | 15 minutes since last instruction check, not on `poll`. | Hidden `15min bible check`. Full `read_file` only if absent from context. Survey only when required text was absent before the check. Not a violation. |
| N. `pre.AckQuoteReminder`. | Double-quoted backticks in an ACK command. | `ACK WARNING:` single-quote the ACK text. Does not block. |
| N. `pre.BarePathReminder`. | Call installed `steer` by absolute path. | Use bare `steer` from any directory. It works without the full path. Does not block. |
| N. `cli._pre_state_unavailable`. | Non-push steering state unavailable. | `STATE UNAVAILABLE: pre-command gate skipped ({reason}).` Work continues. |
| N. `cli._audit_blocked_bash` and shell fallback. | Blocked-Bash audit write fails. | `BLOCK AUDIT FAILED: {reason}`. The guarded command stays blocked. |
| N. `install.sh` profile fallback. | CLI gate exits unexpectedly. | `STEER WARNING: gate exited {status}; work may continue.` A push gets `PUSH BLOCKED: steering gate failed.` No BIBLE_READ. |
| N. `cli._run_pre` or `_run_pre_route`. | Violation flag or detached route. | `Violation flag: {id}` or `routed {name}: background run. Verdict on later call.` Status only. |
| N. `cli._run_post_exit`. | Successful push/PR creation or failed check-watch startup. | `routed pr-checks: background watch after push. Verdict on later call.` Failure prints `PR checks watch could not start: {error}`. |
| N. `cli._slow_call_hint`. | Bash call takes at least 10 seconds. | Bash call took {elapsed}s (>= 10s). Use `steer run start -t <task-id> <name> -- <cmd>` for slow commands. |
| N. `cli._exit_state_reminders`. | Unacked work or at least ten reports with stale items. | Prints `unacked {counts}` and `Unpublish {count} stale reports.` These do not imply a violation by themselves. |
| N. `cli._exit_state_reminders`. | Local unpushed commits. | Private repo: `push small batches (<=3)`. Otherwise: `ALWAYS push. NEVER delay for batch.` Existing reminders, unchanged. |
| N. `server.watch_hot_reload`. | Python hot reload fails. | Logs `Hot-reload skipped: {error}`. This is not evidence that the old preview code is current. |
| N. `assets/reports-view.js`. | Reports Copy Markdown attempt. | On `execCommand("copy")` true, `Copied through the selection fallback`. Otherwise `Copy failed. Browser did not copy report Markdown.` Code-block Copy remains separate and unchanged. |
