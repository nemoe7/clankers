# V2 turn-start recipe

At every turn start:
1. Run `steer --version`.
2. If it fails, run `skills/arena-steering/scripts/install.sh` from the checkout, open a new login shell, and rerun `steer --version`.
3. If the second check fails, report it and stop before resuming the queue.

After the CLI check:
1. Check whether the current v2 preview serves `/`.
2. If it does not, call `functions.start_process` from the checkout with command `steer serve` and keep that process running.
3. If startup fails, report the failure and do not start another copy on the same port.
4. Otherwise reuse the live preview and continue queued work.
