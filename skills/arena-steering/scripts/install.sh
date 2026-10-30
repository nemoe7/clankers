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
printf 'Installed steer in %s. Open a new login shell or source %s.\n' "$COMMAND" "$PROFILE"
