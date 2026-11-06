/bin/bash -l -c set -o pipefail
git rev-parse --verify -q 'refs/remotes/origin/{branch}' >/dev/null
code=$?
[ "$code" -eq 1 ] && exit 0
[ "$code" -ne 0 ] && exit "$code"
git reflog show --format='%H%x09%gs' 'refs/remotes/origin/{branch}' | awk -F '\t' '!found && $2 == "update by push" { print $1; found = 1 }'
