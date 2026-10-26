# Worker Session Rules

- In a board worker session, this file is part of the bible and wins over ARENA.md.
- NEVER commit, push, or open or update a PR in a worker session.
- Attach a git diff patch file and hand off verified findings to the main session through POST /api/board.
- The main session manages worker tasks and reports, reviews worker changes, and asks the user before landing.
- Mark a worker task finished after its local gates pass and you post its board handoff.
