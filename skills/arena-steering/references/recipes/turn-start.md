# V2 turn-start recipe

At every turn start:
1. Run `steer --version`.
2. If it fails, run `skills/arena-steering/scripts/install.sh` from the checkout, open a new login shell, and rerun `steer --version`.
3. If the second check fails, report it and stop before resuming the queue.

After the CLI check:
1. If the initial `steer --version` failed, stop any live v2 preview with `functions.stop_process`, then call `functions.start_process` from the checkout with command `steer serve`.
2. Keep a successful preview running and continue queued work.
