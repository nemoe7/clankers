# V2 resume-turn recipe

If bible text is absent from active context, read all required paths in full via read_file before acting. Then answer steer survey. Otherwise, acknowledge the loaded bible and skip the survey.

At every turn start:
1. Run steer task to show the current task.
2. If it fails, run skills/arena-steering/scripts/install.sh from the checkout and rerun steer task.
3. If the second check fails, report it and stop before resuming the queue.

After the CLI check:
Name every Steering preview {repo} - Steering, where {repo} is the checkout directory name.
1. If the initial steer task failed, call functions.start_process from the checkout with command steer serve.
2. Keep a successful preview running and continue queued work.
