#!/usr/bin/env bash
set -eu

SCRIPTS_DIR="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
VENV="$HOME/.agents/.steer-venv"
PYTHON="$VENV/bin/python"
BIN_DIR="$HOME/.local/bin"
COMMAND="$BIN_DIR/steer"
PROFILE="$HOME/.bash_profile"
COMMAND_MARKER="# arena-steering-installed"
PATH_MARKER="# arena-steering-path"

fail() { echo "steer installer: $*" >&2; exit 1; }

[ -f "$SCRIPTS_DIR/steer" ] || fail "missing $SCRIPTS_DIR/steer"
if [ -L "$COMMAND" ]; then
  fail "$COMMAND already exists"
fi
if [ -e "$COMMAND" ]; then
  [ -f "$COMMAND" ] && grep -qxF "$COMMAND_MARKER" "$COMMAND" || fail "$COMMAND already exists"
fi

if [ ! -x "$PYTHON" ]; then
  python3 -m venv "$VENV" || fail "cannot create $VENV"
fi
"$PYTHON" -c 'import sys; assert sys.version_info >= (3, 11)' || fail "Python 3.11 or later is required"
if ! env -u PYTHONPATH "$PYTHON" -c 'import markdown_it' >/dev/null 2>&1; then
  "$PYTHON" -m pip install --quiet 'markdown-it-py==4.2.0' || fail "cannot install markdown-it-py"
fi

mkdir -p "$BIN_DIR"
printf -v python_quoted '%q' "$PYTHON"
printf -v entry_quoted '%q' "$SCRIPTS_DIR/steer"
printf '#!/usr/bin/env bash\n%s\nexec %s %s "$@"\n' "$COMMAND_MARKER" "$python_quoted" "$entry_quoted" > "$COMMAND"
chmod 755 "$COMMAND"
touch "$PROFILE"
if ! grep -qxF "$PATH_MARKER" "$PROFILE"; then
  cat >> "$PROFILE" <<'EOF'

# arena-steering-path
case ":$PATH:" in
  *":$HOME/.local/bin:"*) ;;
  *) export PATH="$HOME/.local/bin:$PATH" ;;
esac
EOF
fi
GATE_MARKER="# arena-steering-gate"
if ! grep -qxF "$GATE_MARKER" "$PROFILE"; then
  cat >> "$PROFILE" <<'EOF'

# arena-steering-gate
_steer_gate() {
  if [ "${_steer_gate_running:-}" = 1 ]; then return 0; fi
  _steer_gate_running=1
  local command=$BASH_COMMAND reply status line
  if [ -z "${_steer_line:-}" ]; then
    _steer_line="$(tr '\0' ' ' < "/proc/$$/cmdline" 2>/dev/null)" || :
  fi
  [ -n "${_steer_line:-}" ] || _steer_line=$command
  if reply="$("$HOME/.local/bin/steer" pre --line "$_steer_line" --command "$command" --shell "${0##*/}" --done "${_arena_preview_done:-}")"; then
    status=0
  else
    status=$?
  fi
  if [ -n "$reply" ]; then
    while IFS= read -r line; do
      case "$line" in
        _arena_preview_done=*)
          _arena_preview_done=${line#_arena_preview_done=}
          _arena_preview_done=${_arena_preview_done#\"}
          _arena_preview_done=${_arena_preview_done%\"}
          ;;
        *) printf '%s\n' "$line" ;;
      esac
    done <<< "$reply"
  fi
  _steer_gate_running=
  case $status in
    2) exit 0 ;;
    130) exit 130 ;;
    0) return 0 ;;
    *)
      printf 'STEER WARNING: gate exited %s; work may continue.\n' "$status" >&2
      case "$command $_steer_line" in
        *"git push"*) printf 'PUSH BLOCKED: steering gate failed.\n' >&2; exit 130 ;;
      esac
      ;;
  esac
}
_steer_previous=$(trap -p DEBUG)
case $_steer_previous in
  *arena-steering-gate-trap*) ;;
  *)
    if [ -n "$_steer_previous" ]; then
      # Bash quotes trap -p output, so its original action stays one argument.
      eval "_steer_previous_parts=( ${_steer_previous#trap -- } )"
      _steer_previous_action=${_steer_previous_parts[0]}
      unset _steer_previous_parts
      printf -v _steer_hook '%s\n%s' "$_steer_previous_action" '_steer_gate : # arena-steering-gate-trap'
    else
      _steer_hook='_steer_gate : # arena-steering-gate-trap'
    fi
    trap "$_steer_hook" DEBUG
    unset _steer_hook _steer_previous_action
    ;;
esac
unset _steer_previous
EOF
fi
printf 'Installed steer in %s. Open a new login shell or source %s.\n' "$COMMAND" "$PROFILE"
