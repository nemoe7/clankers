/bin/bash -l -c set -euo pipefail
BASE='{base}'
CODING_INDEX='/tmp/arena-workspace/coding.index'
TOTAL_PATCH='/tmp/arena-workspace/coding.patch'
TOTAL_DIFF='/tmp/arena-workspace/coding.diff'
TOTAL_NUMSTAT='/tmp/arena-workspace/coding-numstat.txt'
CODING_EXCLUDE='/tmp/arena-workspace/coding-exclude'
trap 'rm -f "$CODING_INDEX" "$CODING_INDEX.lock" "$CODING_EXCLUDE"' EXIT
export GIT_INDEX_FILE="$CODING_INDEX"
rm -f "$CODING_INDEX" "$CODING_INDEX.lock"
printf '%s\n' '.arena/
.cache/
.local/
.mypy_cache/
.next/
.nox/
.npm/
.nuxt/
.output/
.parcel-cache/
.playwright-cli/
.pytest_cache/
.ruff_cache/
.svelte-kit/
.tox/
.turbo/
.venv/
.vite/
__pycache__/
build/
coverage/
dist/
node_modules/
out/
target/
*.db-shm
*.db-wal
*.db-journal
.git/config
.git/credentials
.git-credentials
.netrc' > "$CODING_EXCLUDE"
git -c core.excludesFile="$CODING_EXCLUDE" read-tree HEAD
git -c core.excludesFile="$CODING_EXCLUDE" add -A
git diff --cached --binary "$BASE" -- '.' ':(exclude,glob)**/.arena/**' ':(exclude,glob)**/.cache/**' ':(exclude,glob)**/.local/**' ':(exclude,glob)**/.mypy_cache/**' ':(exclude,glob)**/.next/**' ':(exclude,glob)**/.nox/**' ':(exclude,glob)**/.npm/**' ':(exclude,glob)**/.nuxt/**' ':(exclude,glob)**/.output/**' ':(exclude,glob)**/.parcel-cache/**' ':(exclude,glob)**/.playwright-cli/**' ':(exclude,glob)**/.pytest_cache/**' ':(exclude,glob)**/.ruff_cache/**' ':(exclude,glob)**/.svelte-kit/**' ':(exclude,glob)**/.tox/**' ':(exclude,glob)**/.turbo/**' ':(exclude,glob)**/.venv/**' ':(exclude,glob)**/.vite/**' ':(exclude,glob)**/__pycache__/**' ':(exclude,glob)**/build/**' ':(exclude,glob)**/coverage/**' ':(exclude,glob)**/dist/**' ':(exclude,glob)**/node_modules/**' ':(exclude,glob)**/out/**' ':(exclude,glob)**/target/**' ':(exclude,glob)**/.git/config' ':(exclude,glob)**/.git/credentials' ':(exclude,glob)**/.git-credentials' ':(exclude,glob)**/.netrc' ':(exclude,glob)**/*.db-shm' ':(exclude,glob)**/*.db-wal' ':(exclude,glob)**/*.db-journal' > "$TOTAL_PATCH"
git diff --cached "$BASE" -- '.' ':(exclude,glob)**/.arena/**' ':(exclude,glob)**/.cache/**' ':(exclude,glob)**/.local/**' ':(exclude,glob)**/.mypy_cache/**' ':(exclude,glob)**/.next/**' ':(exclude,glob)**/.nox/**' ':(exclude,glob)**/.npm/**' ':(exclude,glob)**/.nuxt/**' ':(exclude,glob)**/.output/**' ':(exclude,glob)**/.parcel-cache/**' ':(exclude,glob)**/.playwright-cli/**' ':(exclude,glob)**/.pytest_cache/**' ':(exclude,glob)**/.ruff_cache/**' ':(exclude,glob)**/.svelte-kit/**' ':(exclude,glob)**/.tox/**' ':(exclude,glob)**/.turbo/**' ':(exclude,glob)**/.venv/**' ':(exclude,glob)**/.vite/**' ':(exclude,glob)**/__pycache__/**' ':(exclude,glob)**/build/**' ':(exclude,glob)**/coverage/**' ':(exclude,glob)**/dist/**' ':(exclude,glob)**/node_modules/**' ':(exclude,glob)**/out/**' ':(exclude,glob)**/target/**' ':(exclude,glob)**/.git/config' ':(exclude,glob)**/.git/credentials' ':(exclude,glob)**/.git-credentials' ':(exclude,glob)**/.netrc' ':(exclude,glob)**/*.db-shm' ':(exclude,glob)**/*.db-wal' ':(exclude,glob)**/*.db-journal' > "$TOTAL_DIFF"
git diff --cached --numstat "$BASE" -- '.' ':(exclude,glob)**/.arena/**' ':(exclude,glob)**/.cache/**' ':(exclude,glob)**/.local/**' ':(exclude,glob)**/.mypy_cache/**' ':(exclude,glob)**/.next/**' ':(exclude,glob)**/.nox/**' ':(exclude,glob)**/.npm/**' ':(exclude,glob)**/.nuxt/**' ':(exclude,glob)**/.output/**' ':(exclude,glob)**/.parcel-cache/**' ':(exclude,glob)**/.playwright-cli/**' ':(exclude,glob)**/.pytest_cache/**' ':(exclude,glob)**/.ruff_cache/**' ':(exclude,glob)**/.svelte-kit/**' ':(exclude,glob)**/.tox/**' ':(exclude,glob)**/.turbo/**' ':(exclude,glob)**/.venv/**' ':(exclude,glob)**/.vite/**' ':(exclude,glob)**/__pycache__/**' ':(exclude,glob)**/build/**' ':(exclude,glob)**/coverage/**' ':(exclude,glob)**/dist/**' ':(exclude,glob)**/node_modules/**' ':(exclude,glob)**/out/**' ':(exclude,glob)**/target/**' ':(exclude,glob)**/.git/config' ':(exclude,glob)**/.git/credentials' ':(exclude,glob)**/.git-credentials' ':(exclude,glob)**/.netrc' ':(exclude,glob)**/*.db-shm' ':(exclude,glob)**/*.db-wal' ':(exclude,glob)**/*.db-journal' > "$TOTAL_NUMSTAT"
unset GIT_INDEX_FILE
