/bin/bash -l -c [ -d '/tmp/arena-workspace/procs' ] || exit 0
ports_observed=
if command -v ss >/dev/null 2>&1; then
  sockets=$(ss -ltnpH) || exit 1
  ports_observed=1
elif command -v netstat >/dev/null 2>&1; then
  sockets=$(netstat -ltnp) || exit 1
  ports_observed=1
fi
if [ -n "$ports_observed" ]; then groups=$(ps -eo pid=,pgid=) || exit 1; fi
for dir in '/tmp/arena-workspace/procs'/*/; do
  [ -f "$dir/meta.json" ] || continue
  echo '===ARENA_ENTRY==='
  cat "$dir/meta.json"
  echo
  if [ -f "$dir/exit" ]; then echo "STATUS exited $(cat "$dir/exit" 2>/dev/null)"
  elif pid=$(cat "$dir/pid" 2>/dev/null) && [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
    echo "STATUS running $pid"
    if [ -n "$ports_observed" ]; then
      echo '===ARENA_PORTS==='
      printf '%s\n' "$groups" "$sockets" | awk -v group="$pid" '
        NF == 2 { if ($2 == group) members[$1] = 1; next }
        $1 ~ /^tcp/ && $7 ~ /^[0-9]+\// { if (($7 + 0) in members) print; next }
        { n = split($0, parts, "pid="); for (i = 2; i <= n; i++) if ((parts[i] + 0) in members) { print; break } }
      '
    fi
  else echo "STATUS exited"
  fi
done
