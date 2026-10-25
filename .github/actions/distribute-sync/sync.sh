set -euo pipefail
REPOS="${REPOS:-$REPOS_FALLBACK}"
[ -n "${REPOS// /}" ] || { echo "::error::no target repos configured"; exit 1; }
if [ -n "$RULE_SRC" ]; then
  [ -f "$GITHUB_WORKSPACE/$RULE_SRC" ] || { echo "::error::$RULE_SRC missing"; exit 1; }
  [ -n "$RULE_DEST" ] || { echo "::error::rule-dest is required with rule-src"; exit 1; }
fi
for f in $FILES; do
  [ -f "$GITHUB_WORKSPACE/$SRC_ROOT/$f" ] || { echo "::error::$SRC_ROOT/$f missing"; exit 1; }
done

# Tracked files, minus the pages that stay here and the owner-run packages under
# arena-egress-proxy/ and arena-preview-proxy/, which stay beside the published images.
skill_files() {
  local out
  out=$(git -C "$GITHUB_WORKSPACE" ls-files "$SKILL_ROOT/$1" | sed "s|^$SKILL_ROOT/$1/||" \
    | awk '$0 != "README.md" && $0 != "INSTALL.md" && $0 != "AGENTS.md" && $0 !~ /^(arena-egress-proxy|arena-preview-proxy)\//') || return
  printf '%s\n' "$out"
}
for skill in $SKILLS; do
  if [ -z "$(skill_files "$skill")" ]; then
    echo "::error::no tracked files for $skill"
    exit 1
  fi
done

if [ "${VALIDATE_ONLY:-false}" = "true" ]; then
  echo "Source payload verified."
  exit 0
fi

push_target() {
  git push --quiet "$@" 2> >(awk '
    /^remote: GitHub found [0-9]+ vulnerabilit(y|ies) on .* default branch .* To find out more, visit:[[:space:]]*$/ {
      if (notice != "") print notice
      notice = $0
      next
    }
    notice != "" && /^remote:[[:space:]]+https:\/\/github.com\/[^[:space:]]+\/security\/dependabot[[:space:]]*$/ {
      notice = ""
      next
    }
    { if (notice != "") { print notice; notice = "" }; print }
    END { if (notice != "") print notice }
  ' >&2)
}

failed=""
# shellcheck disable=SC2016  # The helper expands the token when git calls it.
git config --global credential.helper '!f() { echo username=x-access-token; echo "password=$CLANKERS_DIST_PAT"; }; f'
for repo in $REPOS; do
  set +e
  (
    set -e
    work=$(mktemp -d)
    trap 'rm -rf "$work"' EXIT
    git clone --quiet --depth 2 "https://github.com/$repo.git" "$work"
    cd "$work"
    ref=$(git symbolic-ref HEAD)
    captured=$(git rev-parse HEAD)
    if [ -n "$RULE_SRC" ]; then
      mkdir -p "$work/$(dirname "$RULE_DEST")"
      cp "$GITHUB_WORKSPACE/$RULE_SRC" "$work/$RULE_DEST"
    fi
    for legacy in $LEGACY; do
      rm -rf "$work/$SKILL_DEST_ROOT/$legacy"
    done
    for skill in $SKILLS; do
      files=$(skill_files "$skill")
      [ -n "$files" ] || continue
      # The whole directory goes, so a page that this repository keeps leaves the target repo on the same run.
      rm -rf "$work/$SKILL_DEST_ROOT/$skill"
      for f in $files; do
        mkdir -p "$work/$SKILL_DEST_ROOT/$skill/$(dirname "$f")"
        cp "$GITHUB_WORKSPACE/$SKILL_ROOT/$skill/$f" "$work/$SKILL_DEST_ROOT/$skill/$f"
      done
    done
    for f in $FILES; do
      mkdir -p "$work/$DEST_ROOT/$(dirname "$f")"
      cp "$GITHUB_WORKSPACE/$SRC_ROOT/$f" "$work/$DEST_ROOT/$f"
    done
    bot_name="github-actions[bot]"
    bot_email="41898282+github-actions[bot]@users.noreply.github.com"
    subject="chore: clankers sync"
    git config user.name "$bot_name"
    git config user.email "$bot_email"
    git add -A
    if git diff --cached --quiet; then
      :
    else
      status=$?
      [ "$status" -eq 1 ] || exit "$status"
      identity=$(git show -s --format='%an%n%ae%n%cn%n%ce%n%s' HEAD)
      wanted=$(printf '%s\n' "$bot_name" "$bot_email" "$bot_name" "$bot_email" "$subject")
      parents=$(git show -s --format=%P HEAD)
      if [ "$identity" = "$wanted" ] && [[ -n "$parents" && "$parents" != *" "* ]]; then
        git commit --quiet --amend --no-edit --reset-author
        if ! push_target "--force-with-lease=$ref:$captured" origin "HEAD:$ref"; then
          remote=$(git ls-remote --exit-code origin "$ref")
          [ "${remote%%$'\t'*}" = "$captured" ] || {
            echo "::error::$repo: remote changed; sync stopped"; exit 1;
          }
          git reset --soft "$captured"
          git commit --quiet -m "$subject"
          push_target origin "HEAD:$ref"
        fi
      else
        git commit --quiet -m "$subject"
        push_target origin "HEAD:$ref"
      fi
    fi
    expected=$(git rev-parse HEAD)
    remote=$(git ls-remote --exit-code origin "$ref")
    [ "${remote%%$'\t'*}" = "$expected" ] || {
      echo "::error::$repo: remote head differs after sync"; exit 1;
    }
    if [ -n "$RULE_SRC" ]; then
      git show "HEAD:$RULE_DEST" | cmp -s - "$GITHUB_WORKSPACE/$RULE_SRC" || {
        echo "::error::$repo: $RULE_DEST differs after sync"; exit 1;
      }
    fi
    for legacy in $LEGACY; do
      [ -z "$(git ls-tree -r --name-only HEAD -- "$SKILL_DEST_ROOT/$legacy")" ] || {
        echo "::error::$repo: retired skill $legacy remains"; exit 1;
      }
    done
    for skill in $SKILLS; do
      files=$(skill_files "$skill")
      [ -n "$files" ] || continue
      have=$(git ls-tree -r --name-only "HEAD:$SKILL_DEST_ROOT/$skill" | sort)
      # shellcheck disable=SC2086  # The word split lists one path per line.
      want=$(printf '%s\n' $files | sort)
      [ "$have" = "$want" ] || { echo "::error::$repo: $skill file-list mismatch"; exit 1; }
      for f in $files; do
        git show "HEAD:$SKILL_DEST_ROOT/$skill/$f" | cmp -s - "$GITHUB_WORKSPACE/$SKILL_ROOT/$skill/$f" || {
          echo "::error::$repo: $skill/$f differs"; exit 1;
        }
      done
    done
    for f in $FILES; do
      git show "HEAD:$DEST_ROOT/$f" | cmp -s - "$GITHUB_WORKSPACE/$SRC_ROOT/$f" || {
        echo "::error::$repo: $f differs after sync"; exit 1;
      }
    done
    echo "$repo: verified"
  )
  status=$?
  set -e
  if [ "$status" -ne 0 ]; then
    failed="$failed $repo"
  fi
done
[ -z "$failed" ] || { echo "::error::sync failed for:$failed"; exit 1; }
