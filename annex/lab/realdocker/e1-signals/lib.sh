#!/bin/bash
# Helpers for run.sh (sourced). Everything created here is named e1-*; nothing else is touched.
E1=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
WORK=$E1/work
OUT=$E1/out
CFG=$E1/cfg
PY="python3 -P"   # -P: never import from the script or current directory

now() { date +%s.%N; }
note() { echo "[$(date +%H:%M:%S)] $*"; }

# ctr_run <case> <cfgset> <kolla service name> [docker run options...] -- <image> [command...]
# The options mirror kolla_docker's create: network_mode host (kolla_docker.py:719), restart unless-stopped
# (group_vars/all.yml docker_restart_policy), KOLLA_CONFIG_STRATEGY (all.yml:162-163), KOLLA_SERVICE_NAME
# (kolla_docker.py:752), the config dir read-only, localtime/timezone, and a host dir in place of the kolla_logs volume.
ctr_run() {
  local c=$1 cfgset=$2 svc=$3; shift 3
  local opts=()
  while [ "$1" != "--" ]; do opts+=("$1"); shift; done; shift
  docker rm -f "e1-$c" >/dev/null 2>&1 || true
  [ -n "${E1_KEEP:-}" ] || fresh_case "$c"
  docker run -d --name "e1-$c" --network host --restart unless-stopped \
    -e KOLLA_CONFIG_STRATEGY=COPY_ALWAYS -e KOLLA_SERVICE_NAME="$svc" -e E1_TAG="e1-$c" \
    -v "$CFG/$cfgset:/var/lib/kolla/config_files/:ro" -v /etc/localtime:/etc/localtime:ro \
    -v /etc/timezone:/etc/timezone:ro -v "$WORK/$c/logs:/var/log/kolla/" "${opts[@]}" "$@" >/dev/null
  echo "docker run ... ${opts[*]} $*" > "$OUT/$c/docker-run.txt"
}

# fresh_case <case>: empty work and output dirs for a case
fresh_case() {
  rm -rf "${WORK:?}/$1" "${OUT:?}/$1"; mkdir -p "$WORK/$1/logs/e1" "$OUT/$1"; chmod -R 777 "$WORK/$1/logs"
}

# wait_for <timeout s> <command...>: poll until the command succeeds
wait_for() {
  local end=$(( $(date +%s) + $1 )); shift
  until "$@" >/dev/null 2>&1; do
    [ "$(date +%s)" -ge "$end" ] && { note "timeout waiting for: $*"; return 1; }
    sleep 0.2
  done
}

# snapshot <case> [ctr-view]: process tree before the stop (host /proc view; plus `ps` inside unless pid=host)
snapshot() {
  local c=$1
  $PY "$E1/proctab.py" snap "e1-$c" "e1-$c" "$WORK/$c/proctab.json" > "$OUT/$c/tree.txt"
  if [ "${2:-ctr}" = ctr ]; then
    { echo; echo "# docker exec e1-$c ps -eo pid,ppid,pgid,sid,user,args  (container view; the ps line is the exec)";
      docker exec "e1-$c" ps -eo pid,ppid,pgid,sid,user,args; } >> "$OUT/$c/tree.txt"
  fi
}

# strace_start <case>: attach to every process of the snapshot (and follow forks) from the host
strace_start() {
  local c=$1 args=()
  for p in $(python3 -c 'import json,sys; print(" ".join(str(r["hpid"]) for r in json.load(open(sys.argv[1]))))' \
             "$WORK/$c/proctab.json"); do args+=(-p "$p"); done
  strace -ttt -T -f -q --decode-pids=pidns -s 120 \
    -e trace=kill,tgkill,tkill,rt_sigtimedwait,wait4,exit_group,execve,clone,clone3,fork,vfork -e signal=all \
    -o "$WORK/$c/strace.raw" "${args[@]}" 2> "$WORK/$c/strace.err" &
  STRACE_PID=$!
  SHIM_STRACE_PID=
  if [ -n "${E1_TRACE_SHIM:-}" ]; then
    # the per-container containerd shim (parent of the container's init): which runc commands and kill() calls
    # it makes during the stop. strace -p seizes the process without stopping or signalling it.
    local shim
    shim=$(python3 -c 'import json,sys; print([r["hppid"] for r in json.load(open(sys.argv[1])) if r["nspid"] in (1,) or r["cmd"].startswith("dumb-init")][0])' "$WORK/$c/proctab.json")
    echo "shim: $(ps -o pid=,args= -p "$shim")" > "$WORK/$c/shim.pid"
    strace -ttt -f -q -e trace=execve,kill,tgkill -e signal=none -s 200 -o "$WORK/$c/shim.raw" -p "$shim" \
      2>> "$WORK/$c/strace.err" &
    SHIM_STRACE_PID=$!
  fi
  sleep 1.5
  $PY "$E1/proctab.py" tids "$WORK/$c/proctab.json"   # threads started between the snapshot and the attach
}

strace_finish() {
  local i
  for i in $(seq 1 100); do kill -0 "$STRACE_PID" 2>/dev/null || break; sleep 0.2; done
  kill -INT "$STRACE_PID" 2>/dev/null; wait "$STRACE_PID" 2>/dev/null
  if [ -n "${SHIM_STRACE_PID:-}" ]; then
    sleep 1; kill -INT "$SHIM_STRACE_PID" 2>/dev/null; wait "$SHIM_STRACE_PID" 2>/dev/null
  fi
}

# stop_case <case> [extra note]: docker stop -t 10 (what kolla_docker sends), then record everything
stop_case() {
  local c=$1 t0 t1
  t0=$(now); docker stop -t 10 "e1-$c" >/dev/null; t1=$(now)
  strace_finish
  echo "$t0 $t1" > "$WORK/$c/t0t1"
  {
    echo "docker stop -t 10 e1-$c took $(python3 -c "print('%.3f' % ($t1-$t0))") s (wall clock around the CLI call)"
    docker inspect -f 'container exit code {{.State.ExitCode}}; OOMKilled {{.State.OOMKilled}}; started {{.State.StartedAt}}; finished {{.State.FinishedAt}}; restarts {{.RestartCount}}' "e1-$c"
    $PY "$E1/proctab.py" alive "$WORK/$c/proctab.json"
  } > "$OUT/$c/stop.txt"
  $PY "$E1/analyze.py" "$WORK/$c/strace.raw" "$WORK/$c/proctab.json" "$t0" "$t1" > "$OUT/$c/timeline.txt"
  if [ -n "${SHIM_STRACE_PID:-}" ]; then
    { cat "$WORK/$c/shim.pid"; echo "# shim strace: runc invocations and kill() calls; times relative to t0"
      python3 - "$WORK/$c/shim.raw" "$t0" <<'PY'
import re, sys
t0 = float(sys.argv[2])
for line in open(sys.argv[1], errors='replace'):
    m = re.match(r'^(\d+)\s+(\d+\.\d+) (.*)$', line.rstrip())
    if not m:
        continue
    what = m.group(3)
    if what.startswith('execve(') and 'runc' in what:
        args = re.findall(r'"([^"]*)"', what.split('], ')[0])[1:]
        args = [a for a in args if not a.startswith(('/run/', '/var/run/', '--root', '--log', 'json'))]
        print('%+8.3f s  pid %s execve runc %s' % (float(m.group(2)) - t0, m.group(1), ' '.join(args[1:])[:160]))
    elif re.match(r'(kill|tgkill)\(', what) and 'SIGURG' not in what:
        print('%+8.3f s  pid %s %s' % (float(m.group(2)) - t0, m.group(1), what[:120]))
PY
    } > "$OUT/$c/shim.txt"
  fi
  # raw strace, minus the stand-ins' 0.2 s sigtimedwait timeouts, capped
  { echo "# strace -ttt -T -f (host pids; see tree.txt), t0=$t0 t1=$t1"; grep -v -E 'EAGAIN|rt_sigtimedwait\(\[HUP INT.*<unfinished' "$WORK/$c/strace.raw" | head -150; } \
    > "$OUT/$c/strace.txt"
  collect_logs "$c"
}

# collect_logs <case>: stand-in logs (sorted by time) and the container's stdout/stderr, trimmed
collect_logs() {
  local c=$1
  cat "$WORK/$c"/logs/e1/*.log 2>/dev/null | sort -n > "$OUT/$c/standin.log"
  [ -s "$OUT/$c/standin.log" ] || rm -f "$OUT/$c/standin.log"
  docker logs -t "e1-$c" > "$OUT/$c/docker-logs.txt" 2>&1
  if [ "$(wc -l < "$OUT/$c/docker-logs.txt")" -gt 60 ]; then
    { head -30 "$OUT/$c/docker-logs.txt"; echo "[... $(wc -l < "$OUT/$c/docker-logs.txt") lines, trimmed ...]";
      tail -25 "$OUT/$c/docker-logs.txt"; } > "$OUT/$c/docker-logs.tmp" && mv "$OUT/$c/docker-logs.tmp" "$OUT/$c/docker-logs.txt"
  fi
}

# kill_survivors <case>: SIGKILL leftover processes of this case only (argv must carry --tag e1-<case>)
kill_survivors() {
  local c=$1 p
  for p in $(python3 -c 'import json,sys; print(" ".join(str(r["hpid"]) for r in json.load(open(sys.argv[1]))))' \
             "$WORK/$c/proctab.json" 2>/dev/null); do
    if [ -r "/proc/$p/cmdline" ] && tr '\0' ' ' < "/proc/$p/cmdline" | grep -q -- "--tag e1-$c"; then
      kill -KILL "$p" && note "killed leftover e1-$c process $p"
    fi
  done
}

rm_case() { docker rm -f "e1-$1" >/dev/null 2>&1 || true; }
