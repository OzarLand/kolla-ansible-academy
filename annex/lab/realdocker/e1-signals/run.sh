#!/bin/bash
# e1: signal delivery and the stop path of Kolla (Ussuri) containers, on a real Docker daemon.
# Usage: KOLLA_SRC=<kolla ussuri-eol> KOLLA_ANSIBLE_SRC=<kolla-ansible ussuri-eol> ./run.sh [test ...]
#   tests: a b c d e f g (default: all). Needs root (host strace), docker, python3 with jinja2, curl,
#   and the image reallab/base:ussuri (../base/build.sh). Idempotent: every run recreates its containers,
#   work/ and out/<case>/. Creates only e1-* containers, volumes and images; host ports 18110-18133.
set -u
here=$(cd "$(dirname "$0")" && pwd)
source "$here/lib.sh"
: "${KOLLA_SRC:?set KOLLA_SRC to a kolla ussuri-eol checkout (commit 9107c5f)}"
: "${KOLLA_ANSIBLE_SRC:?set KOLLA_ANSIBLE_SRC to a kolla-ansible ussuri-eol checkout (commit 8a94fe9)}"
command -v strace >/dev/null || { echo "strace is required on the host"; exit 1; }
python3 -c 'import jinja2' || { echo "python3 jinja2 is required (pip install --user jinja2)"; exit 1; }

PW=e1-lab-only          # lab-only database password, not a secret
export E1_TRACE_SHIM=1  # also strace the container's containerd shim (runc calls, kill calls) during each stop
L3_SPAWN=e1-rootwrap-daemon,e1-keepalived@daemon,e1-haproxy-ns@daemon
L3_OPTS=(--privileged -v e1-neutron_metadata_socket:/var/lib/neutron/kolla/ -e KOLLA_LEGACY_IPTABLES=false
         -e E1_SPAWN=$L3_SPAWN)

# ---------------------------------------------------------------------------------------------------------------
# (a) exec'd service. (b) exec'd service that ignores SIGTERM. Both spawn a plain child and a daemonized grandchild.
test_a() {
  note "a1: exec'd service, docker stop -t 10"
  ctr_run a1 sigsvc e1-sigsvc -u root -e E1_SPAWN=e1-worker,e1-daemon@daemon -- e1-svc:ussuri
  wait_for 30 grep -q ready "$WORK/a1/logs/e1/e1-sigsvc.log"; sleep 1
  snapshot a1; strace_start a1; stop_case a1; rm_case a1
}
test_b() {
  note "b1: exec'd service that ignores SIGTERM"
  ctr_run b1 sigsvc e1-sigsvc -u root -e E1_TERM=ignore -e E1_SPAWN=e1-worker,e1-daemon@daemon -- e1-svc:ussuri
  wait_for 30 grep -q ready "$WORK/b1/logs/e1/e1-sigsvc.log"; sleep 1
  snapshot b1; strace_start b1; stop_case b1; rm_case b1
}

# ---------------------------------------------------------------------------------------------------------------
# (c) the real neutron-l3-agent-wrapper.sh; neutron-l3-agent and neutron-netns-cleanup are stand-ins on PATH.
l3_stop_case() { # <case> <cfgset> [extra docker options]
  local c=$1 cfgset=$2; shift 2
  ctr_run "$c" "$cfgset" neutron-l3-agent "${L3_OPTS[@]}" "$@" -- e1-svc:ussuri
  wait_for 30 grep -q ready "$WORK/$c/logs/e1/neutron-l3-agent.log"; sleep 1
  snapshot "$c" "$([[ " $* " == *" --pid host "* ]] && echo host || echo ctr)"
  strace_start "$c"; stop_case "$c"; rm_case "$c"
}
test_c() {
  note "c1: l3 wrapper, enable_neutron_agent_ha=false"
  l3_stop_case c1 l3-ha-false
  note "c2: l3 wrapper, enable_neutron_agent_ha=true, cleanup succeeds"
  l3_stop_case c2 l3-ha-true -e E1_CLEANUP_SECS=1 -e E1_CLEANUP_RC=0

  note "c3: l3 wrapper, ha=true, cleanup fails (errexit), restart policy unless-stopped, observed 15 s"
  ctr_run c3 l3-ha-true neutron-l3-agent "${L3_OPTS[@]}" -e E1_CLEANUP_SECS=0.2 -e E1_CLEANUP_RC=1 -- e1-svc:ussuri
  sleep 15
  {
    docker inspect -f 'after 15 s: status {{.State.Status}}; restarts {{.RestartCount}}; last exit code {{.State.ExitCode}}' e1-c3
    echo "neutron-netns-cleanup runs: $(grep -c ' start ' "$WORK/c3/logs/e1/neutron-netns-cleanup.log")"
    echo "neutron-l3-agent starts: $(cat "$WORK/c3/logs/e1/neutron-l3-agent.log" 2>/dev/null | grep -c ' start ')"
    echo "# kolla_start 'Running command' lines (one per container start):"
    docker logs -t e1-c3 2>&1 | grep 'Z Running command'
    echo "# stand-in neutron-netns-cleanup log:"
    cat "$WORK/c3/logs/e1/neutron-netns-cleanup.log"
  } > "$OUT/c3/restart-loop.txt"
  docker stop -t 10 e1-c3 >/dev/null; collect_logs c3; rm_case c3

  note "c4: l3 wrapper, ha=true, docker stop while a 60 s cleanup is running"
  ctr_run c4 l3-ha-true neutron-l3-agent "${L3_OPTS[@]}" -e E1_CLEANUP_SECS=60 -- e1-svc:ussuri
  wait_for 30 grep -q ' start ' "$WORK/c4/logs/e1/neutron-netns-cleanup.log"; sleep 1
  snapshot c4; strace_start c4; stop_case c4; rm_case c4
}

# ---------------------------------------------------------------------------------------------------------------
# (d) the real start-ovsdb-server and start-ovs with stand-in daemons (signal delivery only; e5 tests real OVS).
test_d() {
  note "d1: openvswitch_db (start-ovsdb-server)"
  ctr_run d1 ovsdb openvswitch-db -v e1-openvswitch_db:/var/lib/openvswitch/ \
    -v "$WORK/d1/run-openvswitch:/run/openvswitch" -- e1-ovsdb:ussuri
  wait_for 30 grep -q ready "$WORK/d1/logs/e1/ovsdb-server.log"; sleep 1
  snapshot d1; strace_start d1; stop_case d1; rm_case d1
  note "d2: openvswitch_vswitchd (start-ovs)"
  ctr_run d2 ovsvswitchd openvswitch-vswitchd --privileged -v "$WORK/d2/run-openvswitch:/run/openvswitch" \
    -- e1-ovsvswitchd:ussuri
  wait_for 30 grep -q ready "$WORK/d2/logs/e1/ovs-vswitchd.log"; sleep 1
  snapshot d2; strace_start d2; stop_case d2; rm_case d2
}

# ---------------------------------------------------------------------------------------------------------------
# (e) real haproxy 1.8 via the real haproxy_run.sh; a client holds a 20 s download through it during the stop.
backend_up() {
  docker rm -f e1-backend >/dev/null 2>&1
  rm -rf "$WORK/backend"; mkdir -p "$WORK/backend"
  docker run -d --name e1-backend --network host -v "$E1/images/backend:/e1:ro" -v "$WORK/backend:/log" \
    reallab/base:ussuri python3 /e1/backend.py 18113 18114 /log >/dev/null
  wait_for 20 grep -q listening "$WORK/backend/backend.log"
}
haproxy_case() { # <case> <cfgset>
  local c=$1 cfgset=$2 t0 cpid
  ctr_run "$c" "$cfgset" haproxy --privileged -v e1-haproxy_socket:/var/lib/kolla/haproxy/ -- e1-haproxy:ussuri
  wait_for 30 curl -sf http://127.0.0.1:18112/; sleep 2
  : > "$WORK/backend/backend.log"; : > "$WORK/backend/haproxy-syslog.log"
  snapshot "$c"
  ( s=$(now); curl -sS -o /dev/null -w 'http_code=%{http_code} bytes_received=%{size_download} ' --max-time 60 \
      http://127.0.0.1:18112/slow > "$WORK/$c/client.out" 2> "$WORK/$c/client.err"; rc=$?
    echo "curl_rc=$rc started=$s ended=$(now)" >> "$WORK/$c/client.out" ) &
  cpid=$!
  sleep 3; strace_start "$c"; stop_case "$c"; wait "$cpid"
  read -r t0 _ < "$WORK/$c/t0t1"
  python3 - "$WORK/$c/client.out" "$WORK/$c/client.err" "$t0" > "$OUT/$c/client.txt" <<'PY'
import re, sys
out = open(sys.argv[1]).read().strip(); err = open(sys.argv[2]).read().strip(); t0 = float(sys.argv[3])
s, e = (float(x) for x in re.findall(r'(?:started|ended)=([\d.]+)', out))
print('client: curl GET /slow through haproxy :18112 (backend sends 81920 bytes over 20 s, Content-Length set)')
print(out.split(' started')[0])
print('curl stderr: %s' % (err or '(none)'))
print('request started %+.3f s, ended %+.3f s relative to docker stop' % (s - t0, e - t0))
PY
  { echo "# backend log (epoch s)"; cat "$WORK/backend/backend.log";
    echo "# haproxy log lines received on the syslog sink (UDP 18114) during the test";
    if [ -s "$WORK/backend/haproxy-syslog.log" ]; then cat "$WORK/backend/haproxy-syslog.log"; else echo "(none)"; fi; } \
    > "$OUT/$c/backend-and-syslog.txt"
  rm_case "$c"
}
test_e() {
  backend_up
  note "e1: haproxy via the real haproxy_run.sh, long download in flight"
  haproxy_case e1 haproxy
  note "e2: control (not kolla): haproxy exec'd by kolla_start, same download"
  haproxy_case e2 haproxy-exec
  docker rm -f e1-backend >/dev/null
}

# ---------------------------------------------------------------------------------------------------------------
# (f) real MariaDB (bionic 10.1 + galera-3), started like kolla: bootstrap one-shot, then mysqld_safe.
mariadb_case() { # <case> <image> <entrypoint: kolla|single-child>
  local c=$1 img=$2 ep=$3 vol=e1-mariadb-$1 log off
  fresh_case "$c"; docker rm -f "e1-$c" "e1-$c-writer" >/dev/null 2>&1
  docker volume rm -f "$vol" >/dev/null; docker volume create "$vol" >/dev/null
  # bootstrap_mariadb (roles/mariadb/tasks/bootstrap_cluster.yml:2-23): one-shot with KOLLA_BOOTSTRAP
  docker run --rm --name "e1-$c-bootstrap" --network host -e KOLLA_BOOTSTRAP= -e KOLLA_CONFIG_STRATEGY=COPY_ALWAYS \
    -e DB_ROOT_PASSWORD=$PW -e DB_MAX_TIMEOUT=120 -e KOLLA_SERVICE_NAME=bootstrap-mariadb \
    -v "$CFG/mariadb:/var/lib/kolla/config_files/:ro" -v /etc/localtime:/etc/localtime:ro \
    -v /etc/timezone:/etc/timezone:ro -v "$vol:/var/lib/mysql" -v "$WORK/$c/logs:/var/log/kolla/" "$img" \
    > "$WORK/$c/bootstrap.log" 2>&1
  echo "bootstrap_mariadb exit code: $?" > "$OUT/$c/bootstrap.txt"
  grep -E '^\++ (mysql_install_db|mysqld_safe|sudo -E kolla_security_reset|mysqladmin|exit 0)' \
    "$WORK/$c/bootstrap.log" | sed "s/$PW/<pw>/g" | head -12 >> "$OUT/$c/bootstrap.txt"
  log=$WORK/$c/logs/mariadb/mariadb.log
  off=$(stat -c %s "$log" 2>/dev/null || echo 0)
  if [ "$ep" = single-child ]; then
    E1_KEEP=1 ctr_run "$c" mariadb mariadb -v "$vol:/var/lib/mysql" --entrypoint dumb-init -- "$img" \
      --single-child -- kolla_start
  else
    E1_KEEP=1 ctr_run "$c" mariadb mariadb -v "$vol:/var/lib/mysql" -- "$img"
  fi
  wait_for 90 sh -c "tail -c +$((off+1)) '$log' | grep -q 'ready for connections'"
  # a writer in its own container: one connection inserting rows back to back
  docker run -d --name "e1-$c-writer" --network host --entrypoint bash "$img" -c \
    "mysql -h127.0.0.1 -P18130 -uroot -p$PW -e 'CREATE DATABASE IF NOT EXISTS e1; CREATE TABLE IF NOT EXISTS e1.t
     (id INT AUTO_INCREMENT PRIMARY KEY, v VARCHAR(200)) ENGINE=InnoDB'; yes \"INSERT INTO t (v) VALUES
     (REPEAT('x',200));\" | mysql -h127.0.0.1 -P18130 -uroot -p$PW e1" >/dev/null
  sleep 3
  snapshot "$c"
  off=$(stat -c %s "$log")
  strace_start "$c"; stop_case "$c"
  docker logs "e1-$c-writer" 2>&1 | tail -3 > "$OUT/$c/writer.txt"; docker rm -f "e1-$c-writer" >/dev/null
  { echo "# mariadb.log written during the stop ($(tail -c +$((off+1)) "$log" | grep -c .) lines; decisive lines kept)"
    tail -c +$((off+1)) "$log" | grep -E 'Normal shutdown|Got signal|Shutdown complete|InnoDB: Shutdown|InnoDB: Starting shutdown|SYNCED -> CLOSED|mysqld_safe|ERROR|Killed|Aborted' \
      | cut -c1-180; } > "$OUT/$c/mariadb-log-stop.txt"
  docker run --rm -v "$vol:/v:ro" --entrypoint cat reallab/base:ussuri /v/grastate.dat > "$OUT/$c/grastate-after-stop.txt"
  # restart the same container, as kolla_docker's restart_container does (stop, then start)
  off=$(stat -c %s "$log")
  docker start "e1-$c" >/dev/null
  $PY "$E1/recovery_capture.py" "$(docker inspect -f '{{.State.Pid}}' "e1-$c")" "$WORK/$c/wsrep-recovery.txt" &
  wait_for 60 sh -c "tail -c +$((off+1)) '$log' | grep -q 'ready for connections'" || true
  sleep 2
  { echo "# mariadb.log written at the restart ($(tail -c +$((off+1)) "$log" | grep -c .) lines; decisive lines kept)"
    tail -c +$((off+1)) "$log" | grep -E 'mysqld_safe|crash|recover|Recovered|SST complete|safe_to_bootstrap|log sequence number|ready for connections|ERROR|abort' \
      | cut -c1-180; } > "$OUT/$c/mariadb-log-restart.txt"
  wait
  { head -1 "$WORK/$c/wsrep-recovery.txt"
    grep -E 'InnoDB: (Database was not shut|Starting crash|Starting final batch|Doing recovery|Restoring possible|Apply batch|Rollback|Last MySQL binlog|Transaction .* was in the XA|[0-9]+ transaction)|crash recovery|Recovered position|was not shut' \
      "$WORK/$c/wsrep-recovery.txt" | cut -c1-200 | head -25
    echo "($(grep -c . "$WORK/$c/wsrep-recovery.txt") lines in the recovery log; only crash-recovery lines are kept here)"
  } > "$OUT/$c/wsrep-recovery-pass.txt"
  {
    docker inspect -f 'after restart: status {{.State.Status}}; restarts {{.RestartCount}}; exit code {{.State.ExitCode}}' "e1-$c"
    docker run --rm --network host --entrypoint mysql "$img" -h127.0.0.1 -P18130 -uroot -p$PW -N \
      -e 'SELECT COUNT(*) AS rows_in_e1_t FROM e1.t' 2>&1 | sed 's/^/rows in e1.t after restart: /'
  } > "$OUT/$c/restart.txt"
  docker stop -t 10 "e1-$c" >/dev/null; rm_case "$c"; docker volume rm -f "$vol" >/dev/null
}
test_f() {
  { echo "# /usr/bin/mysqld_safe of mariadb-server-10.1 1:10.1.48-0ubuntu0.18.04.1 (bionic), all 'trap' lines:"
    docker run --rm --entrypoint grep e1-mariadb:ussuri -n 'trap' /usr/bin/mysqld_safe
    echo "# e1-mariadb-upstreamtrap:ussuri (f3, f4): the same file after the e1 edit:"
    docker run --rm --entrypoint grep e1-mariadb-upstreamtrap:ussuri -n 'trap' /usr/bin/mysqld_safe
    echo "# how mysqld is started (bionic mysqld_safe): eval_log_error, logging=file"
    docker run --rm --entrypoint sed e1-mariadb:ussuri -n '174,178p;199,202p' /usr/bin/mysqld_safe
  } > "$OUT/f-mysqld_safe-traps.txt"
  note "f1: mariadb, kolla entrypoint (dumb-init --), bionic mysqld_safe as packaged"
  mariadb_case f1 e1-mariadb:ussuri kolla
  note "f2: control: same, base entrypoint (dumb-init --single-child --)"
  mariadb_case f2 e1-mariadb:ussuri single-child
  note "f3: kolla entrypoint, mysqld_safe with upstream MariaDB's trap '' 1 2 3 15 (Ussuri's 10.3 packages)"
  mariadb_case f3 e1-mariadb-upstreamtrap:ussuri kolla
  note "f4: control: upstream trap with --single-child (the case the kolla Dockerfile comment describes)"
  mariadb_case f4 e1-mariadb-upstreamtrap:ussuri single-child
}

# ---------------------------------------------------------------------------------------------------------------
# (g) pid_mode host, as nova_libvirt uses: (a) and (c) again, then a grandchild that leaves the container cgroup.
escape_cgroups() { # create|remove the e1-escape cgroup in every hierarchy of the host
  local d
  for d in /sys/fs/cgroup/*/; do
    if [ "$1" = create ]; then
      mkdir -p "$d/e1-escape"
      if [ -f "$d/cpuset.cpus" ]; then cat "$d/cpuset.cpus" > "$d/e1-escape/cpuset.cpus"; cat "$d/cpuset.mems" > "$d/e1-escape/cpuset.mems"; fi
    else
      [ -d "$d/e1-escape" ] && rmdir "$d/e1-escape"
    fi
  done
  return 0
}
escape_case() { # <case> [--pid host]
  local c=$1 view=ctr p; shift
  [ "$*" = "--pid host" ] && view=host
  escape_cgroups create
  ctr_run "$c" sigsvc e1-sigsvc -u root --privileged -v /sys/fs/cgroup:/sys/fs/cgroup "$@" \
    -e E1_SPAWN=e1-worker,e1-qemu@escape -- e1-svc:ussuri
  wait_for 30 grep -q ready "$WORK/$c/logs/e1/e1-qemu.log"; sleep 1
  snapshot "$c" "$view"; strace_start "$c"; stop_case "$c"
  sleep 3
  {
    echo "# 3 s after docker stop returned:"
    $PY "$E1/proctab.py" alive "$WORK/$c/proctab.json"
    for p in $(python3 -c 'import json,sys; print(" ".join(str(r["hpid"]) for r in json.load(open(sys.argv[1])) if "e1-qemu" in r["cmd"]))' "$WORK/$c/proctab.json"); do
      [ -d "/proc/$p" ] || continue
      echo "# host ps of e1-qemu (host pid $p) and its cgroups:"; ps -o pid,ppid,stat,args -p "$p"
      grep -E 'devices|pids|memory|name=systemd' "/proc/$p/cgroup"
      echo "# parent: $(ps -o pid=,args= -p "$(ps -o ppid= -p "$p" | tr -d ' ')" | cut -c1-100)"
      echo "# last heartbeat $(cat "$WORK/$c"/logs/e1/hb/e1-qemu.* 2>/dev/null) vs now $(now)"
    done
  } > "$OUT/$c/after-stop.txt"
  kill_survivors "$c"; sleep 0.5
  collect_logs "$c"; rm_case "$c"; escape_cgroups remove
}
escape_stdio_case() { # g5: like g3, but the escaped daemon keeps the container's stdout/stderr pipes
  local c=g5 spid t0 t1 t2 p
  escape_cgroups create
  ctr_run $c sigsvc e1-sigsvc -u root --privileged -v /sys/fs/cgroup:/sys/fs/cgroup --pid host \
    -e E1_DAEMON_STDIO=keep -e E1_SPAWN=e1-worker,e1-qemu@escape -- e1-svc:ussuri
  wait_for 30 grep -q ready "$WORK/$c/logs/e1/e1-qemu.log"; sleep 1
  snapshot $c host
  t0=$(now); docker stop -t 10 e1-$c >/dev/null & spid=$!
  sleep 30
  {
    echo "# 30 s after 'docker stop -t 10 e1-$c' was started:"
    kill -0 $spid 2>/dev/null && echo "docker stop is still running (pid $spid)" || echo "docker stop has returned"
    $PY "$E1/proctab.py" alive "$WORK/$c/proctab.json"
    p=$(python3 -c 'import json,sys; print([r["hpid"] for r in json.load(open(sys.argv[1])) if "e1-qemu" in r["cmd"]][0])' "$WORK/$c/proctab.json")
    echo "# fds 0-2 of e1-qemu (host pid $p), and the shim's fds on the same pipes:"
    for fd in 0 1 2; do echo "fd $fd -> $(readlink /proc/$p/fd/$fd)"; done
    shim=$(ps -o ppid= -p "$p" | tr -d ' ')
    echo "parent of e1-qemu: $(ps -o pid=,args= -p "$shim" | cut -c1-80)"
    for pipe in $(readlink /proc/$p/fd/1 /proc/$p/fd/2); do
      for fd in /proc/$shim/fd/*; do [ "$(readlink "$fd")" = "$pipe" ] && echo "shim fd $(basename "$fd") -> $pipe"; done
    done
    t1=$(now); kill_survivors $c
    while kill -0 $spid 2>/dev/null; do sleep 0.05; done; t2=$(now)
    echo "# after SIGKILL of the escaped e1-qemu:"
    python3 -c "print('docker stop returned %.3f s after the kill, %.3f s after it was started' % ($t2-$t1, $t2-$t0))"
    docker inspect -f 'container exit code {{.State.ExitCode}}; finished {{.State.FinishedAt}} (the init exit)' e1-$c
  } > "$OUT/$c/stop.txt" 2>&1
  collect_logs $c; rm_case $c; escape_cgroups remove
}
test_g() {
  note "g1: (a) with --pid host"
  ctr_run g1 sigsvc e1-sigsvc -u root --pid host -e E1_SPAWN=e1-worker,e1-daemon@daemon -- e1-svc:ussuri
  wait_for 30 grep -q ready "$WORK/g1/logs/e1/e1-sigsvc.log"; sleep 1
  snapshot g1 host; strace_start g1; stop_case g1; rm_case g1
  note "g2: (c1) with --pid host"
  l3_stop_case g2 l3-ha-false --pid host
  note "g6: (b) with --pid host: SIGTERM ignored, so SIGKILL after 10 s"
  ctr_run g6 sigsvc e1-sigsvc -u root --pid host -e E1_TERM=ignore -e E1_SPAWN=e1-worker,e1-daemon@daemon -- e1-svc:ussuri
  wait_for 30 grep -q ready "$WORK/g6/logs/e1/e1-sigsvc.log"; sleep 1
  snapshot g6 host; strace_start g6; stop_case g6; rm_case g6
  note "g3: --pid host, a grandchild moved out of the container cgroup (like QEMU into machine.slice)"
  escape_case g3 --pid host
  note "g4: control: the same without --pid host"
  escape_case g4
  note "g5: g3, but the escaped daemon keeps the container's stdout/stderr (stand-in default is /dev/null)"
  escape_stdio_case
}

# ---------------------------------------------------------------------------------------------------------------
cleanup() {
  docker ps -a --format '{{.Names}}' | grep -E '^e1-' | xargs -r docker rm -f >/dev/null
  docker volume ls -q | grep -E '^e1-' | xargs -r docker volume rm -f >/dev/null
  escape_cgroups remove 2>/dev/null
}
trap cleanup EXIT

note "build images"; KOLLA_SRC=$KOLLA_SRC "$here/build.sh" || exit 1
note "render the kolla-ansible templates into cfg/"; $PY "$here/render.py" "$KOLLA_ANSIBLE_SRC" "$CFG" || exit 1
{ echo "e1 environment, $(date -u +%FT%TZ)"
  docker version --format 'docker client {{.Client.Version}}, server {{.Server.Version}}'
  docker info --format 'cgroup v{{.CgroupVersion}} driver {{.CgroupDriver}}, storage {{.Driver}}, runtime {{.DefaultRuntime}}, kernel {{.KernelVersion}}'
  containerd --version 2>/dev/null; runc --version 2>/dev/null | head -1; strace -V | head -1
  for i in reallab/base:ussuri e1-svc:ussuri e1-haproxy:ussuri e1-mariadb:ussuri; do
    echo "$i $(docker image inspect -f '{{.Id}}' "$i" | cut -c1-19)"; done
  docker run --rm --entrypoint dpkg-query reallab/base:ussuri -W dumb-init bash python3.6
  docker run --rm --entrypoint dpkg-query e1-haproxy:ussuri -W haproxy
  docker run --rm --entrypoint dpkg-query e1-mariadb:ussuri -W mariadb-server-10.1 galera-3
} > "$OUT/environment.txt" 2>&1
tests=${*:-a b c d e f g}
for t in $tests; do "test_$t"; done
{ for d in "$OUT"/*/; do
    c=$(basename "$d"); echo "=== $c"; [ -f "$d/stop.txt" ] && head -2 "$d/stop.txt"
    [ -f "$d/timeline.txt" ] && sed -n '/^# fate/,$p' "$d/timeline.txt" | tail -n +2
  done; } > "$OUT/summary.txt"
note "done: see $OUT"
