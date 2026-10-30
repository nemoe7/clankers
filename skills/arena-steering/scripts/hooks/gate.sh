#!/bin/sh
# Pre-command gate for Arena Steering v2.
#
# A shell DEBUG trap calls this before a line runs. It exits 1 while a message or
# report answer waits for an acknowledgement, which refuses the line.
#
#   trap 'skills/arena-steering/scripts/hooks/gate.sh "$BASH_COMMAND"' DEBUG
#
# Set STEER to the entry point when `steer` is not on PATH.
set -u
line=${1:-}
steer=${STEER:-steer}
exec "$steer" gate -l "$line"
