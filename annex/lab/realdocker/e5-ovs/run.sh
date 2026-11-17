#!/bin/bash
# e5: Open vSwitch restarts (Q3 mechanism) with the real kolla-ansible ussuri-eol openvswitch templates and container
# parameters, on images built FROM reallab/base:ussuri with bionic Open vSwitch 2.9.8 (Ussuri: 2.13 from UCA).
#
# Usage (as root, on a host whose Docker daemon has reallab/base:ussuri, see ../base/build.sh):
#   KOLLA_SRC=<kolla ussuri-eol checkout> KA_SRC=<kolla-ansible ussuri-eol checkout> [E5_WORK=<scratch dir>] ./run.sh
# Idempotent: removes everything e5 created (containers, volumes, host links, the bind mount) first and at the end,
# keeps the images, and rewrites out/. Host port used: 18540 (ovsdb-server ptcp, from e5's range 18500-18599).
set -uo pipefail
here=$(cd "$(dirname "$0")" && pwd)
: "${KOLLA_SRC:?set KOLLA_SRC}" "${KA_SRC:?set KA_SRC}"
# shellcheck source=lib.sh
. "$here/lib.sh"
mkdir -p "$WORK"
cleanup
"$here/build.sh" || exit 1
python3 "$here/render.py" "$KA_SRC" "$CFG" || exit 1
rm -rf "$OUT" && mkdir -p "$OUT"

# ---------------------------------------------------------------- environment
{
  echo "date: $(date -u +%FT%TZ)"
  docker version --format 'docker client {{.Client.Version}} server {{.Server.Version}}'
  docker info --format 'cgroup v{{.CgroupVersion}} driver {{.CgroupDriver}} storage {{.Driver}} runc {{.RuncCommit.ID}} containerd {{.ContainerdCommit.ID}}'
  echo "kernel $(uname -r); openvswitch kernel module: $(ls -d /sys/module/openvswitch 2>/dev/null || echo 'absent (/sys/module/openvswitch missing)'); /lib/modules on host: $(ls -d /lib/modules 2>/dev/null || echo absent); IPv6: $(ls -d /proc/sys/net/ipv6 2>/dev/null || echo absent)"
  echo "strace $(strace -V | head -1 | awk '{print $NF}')"
  for i in reallab/base:ussuri e5-openvswitch-base:ussuri e5-openvswitch-db-server:ussuri e5-openvswitch-vswitchd:ussuri e5-peer:ussuri; do
    echo "image $i $(docker image inspect -f '{{.Id}}' $i | cut -c1-19)"
  done
  docker run --rm --entrypoint dpkg-query e5-openvswitch-vswitchd:ussuri \
    -W -f='package ${Package} ${Version}\n' openvswitch-switch openvswitch-common python3-openvswitch kmod dumb-init bash
  echo "sources: kolla $(git -C "$KOLLA_SRC" log -1 --format=%h) kolla-ansible $(git -C "$KA_SRC" log -1 --format=%h)"
} > "$OUT/environment.txt"

# ---------------------------------------------------------------- s: start path (role parameters, real templates)
T=$OUT/s-start-path && mkdir -p "$T"
mkdir -p "$RUNDIR" && mount --bind "$RUNDIR" "$RUNDIR" && mount --make-shared "$RUNDIR"
docker volume create $LOGVOL >/dev/null && docker volume create $DBVOL >/dev/null
prepare_modules empty
run_db && wait_db && echo "openvswitch_db ready: $(docker exec $DB ovs-vsctl --no-wait get Open_vSwitch . _uuid)" > "$T/db-start.txt"
docker logs $DB 2>&1 | grep -E 'ovsdb-tool create|Running command' >> "$T/db-start.txt"
ps_tree $DB >> "$T/db-start.txt"
# 1. vswitchd exactly as the image and the role define it, with this host's (empty) /lib/modules
run_vs; sleep 8
{
  echo "### /lib/modules = empty directory (this host has none); after 8 s:"
  docker inspect -f 'state={{.State.Status}} exitCode={{.State.ExitCode}} restartCount={{.RestartCount}}' $VS
  echo "### docker logs: last lines of the last attempt"
  docker logs $VS 2>&1 | tail -3
  echo "### attempts that failed on modprobe: $(docker logs $VS 2>&1 | grep -c 'modprobe: FATAL')"
} > "$T/vswitchd-unmodified.txt"
docker rm -f $VS >/dev/null
# 2. minimal override: /lib/modules declares openvswitch built in (image and kolla scripts unchanged)
prepare_modules builtin
run_vs
for i in $(seq 100); do [ -s "$RUNDIR/ovs-vswitchd.pid" ] && break; sleep 0.1; done; sleep 1
{
  echo "### /lib/modules = modules.builtin listing openvswitch (depmod-indexed):"
  docker inspect -f 'state={{.State.Status}} exitCode={{.State.ExitCode}} restartCount={{.RestartCount}}' $VS
  docker logs $VS 2>&1 | grep -E 'modprobe|Running command'
  echo "### processes (host pid, host ppid, cmdline)"; ps_tree $VS
} > "$T/vswitchd-override.txt"
setup_peers
setup_bridges
add_flows
sleep 1
{
  echo "### ovs-vswitchd.log: datapath lines"
  grep -E "ovs_datapath|datapath ID|netdev@ovs-netdev: Datapath supports recirc" "$(logdir)/ovs-vswitchd.log" | head -4
  echo "### ovs-appctl dpif/show"; docker exec $VS ovs-appctl dpif/show
  echo "### probe: ping -c 3 over each bridge"
  docker exec e5-peer1 ping -c 3 -i 0.2 -n 10.55.1.2 | tail -2
  docker exec e5-peer1 ping -c 3 -i 0.2 -n 10.55.2.2 | tail -2
} > "$T/datapath-and-probe.txt"
snap "$T/initial-state.txt" $DB

# ---------------------------------------------------------------- a: docker restart -t 10 openvswitch_vswitchd
T=$OUT/a-restart-vswitchd && mkdir -p "$T"
ping_start; sleep 2
snap "$T/before.txt" $DB; ps_tree $VS > "$T/ps-before.txt"
L0=$(loglines ovs-vswitchd.log)
strace_start $VS
tstart=$(now)
ev "T0 docker restart -t 10 $VS"
docker restart -t 10 $VS >/dev/null; ev "docker restart returned (rc=$?)"
wait_bridge && ev "vswitchd answers on $SEC.mgmt again (ovs-ofctl dump-flows rc=0)"
snap "$T/after-restart.txt" $DB; ev "snapshot after-restart.txt taken"
strace_stop
ps_tree $VS > "$T/ps-after.txt"
sleep 10
snap "$T/after-restart+10s.txt" $DB; ev "snapshot after-restart+10s.txt taken"
ev "re-adding the flows with ovs-ofctl add-flows (what an agent resync would do)"; add_flows; ev "flows re-added"
sleep 3
ping_stop
container_events $VS "$tstart" > "$T/events.raw"
tail -n +$((L0 + 1)) "$(logdir)/ovs-vswitchd.log" | grep -v 'Datapath supports' > "$T/ovs-vswitchd.log"
diff "$T/before.txt" "$T/after-restart.txt" > "$T/diff-before-vs-after-restart.txt"
finish

# ---------------------------------------------------------------- a2: three more restarts without strace (timing)
for r in 1 2 3; do
  T=$OUT/a2-restart-timing/run$r && mkdir -p "$T"
  ping_start; sleep 1.5
  tstart=$(now); ev "T0 docker restart -t 10 $VS (no strace attached)"
  docker restart -t 10 $VS >/dev/null; ev "docker restart returned (rc=$?)"
  wait_bridge && ev "vswitchd answers on $SEC.mgmt again"
  ev "flows (cookie lines) after restart: $SEC $(docker exec $DB ovs-ofctl dump-flows $SEC | grep -c cookie), $STD $(docker exec $DB ovs-ofctl dump-flows $STD | grep -c cookie)"
  sleep 2; ev "re-adding the flows"; add_flows; ev "flows re-added"; sleep 2
  ping_stop
  container_events $VS "$tstart" > "$T/events.raw"
  finish
done
grep -H -E 'die|returned|answers|after restart|re-added|^==|GAP|no interruption' "$OUT"/a2-restart-timing/run*/timeline.txt \
  "$OUT"/a2-restart-timing/run*/ping.txt | sed "s#$OUT/a2-restart-timing/##" > "$OUT/a2-restart-timing/summary.txt"

# ---------------------------------------------------------------- b: recreate openvswitch_vswitchd (kolla_docker path)
T=$OUT/b-recreate-vswitchd && mkdir -p "$T"
ping_start; sleep 2
snap "$T/before.txt" $DB; ps_tree $VS > "$T/ps-before.txt"
L0=$(loglines ovs-vswitchd.log)
old_id=$(docker inspect -f '{{.Id}}' $VS | cut -c1-12)
strace_start $VS
tstart=$(now)
ev "T0 docker stop -t 10 $VS (kolla_docker recreate_or_restart_container: stop_container, remove, start)"
docker stop -t 10 $VS >/dev/null; ev "docker stop returned (rc=$?)"
docker inspect -f 'stopped container {{.Id}}: exitCode={{.State.ExitCode}} OOMKilled={{.State.OOMKilled}}' $VS | cut -c1-200 > "$T/stopped-state.txt"
{
  echo "### \$RUNDIR (the host's /run/openvswitch stand-in) while vswitchd is stopped"; ls -l --time-style=+%T "$RUNDIR"
  echo "### host links e5-* while vswitchd is stopped"; nsh 'ip -br link' | grep -E '^e5-' | sort
} > "$T/while-stopped.txt"
snap "$T/while-stopped-state.txt" $DB
ev "observations while stopped done (e5 pause, not part of kolla_docker's sequence)"
docker rm $VS >/dev/null; ev "docker rm returned"
run_vs; ev "docker run (create + start) returned"
wait_bridge && ev "vswitchd answers on $SEC.mgmt again (ovs-ofctl dump-flows rc=0)"
snap "$T/after-recreate.txt" $DB; ev "snapshot after-recreate.txt taken"
strace_stop
echo "old container $old_id, new container $(docker inspect -f '{{.Id}}' $VS | cut -c1-12)" >> "$T/stopped-state.txt"
ps_tree $VS > "$T/ps-after.txt"
sleep 10
snap "$T/after-recreate+10s.txt" $DB; ev "snapshot after-recreate+10s.txt taken"
ev "re-adding the flows with ovs-ofctl add-flows"; add_flows; ev "flows re-added"
sleep 3
ping_stop
container_events $VS "$tstart" > "$T/events.raw"
tail -n +$((L0 + 1)) "$(logdir)/ovs-vswitchd.log" | grep -v 'Datapath supports' > "$T/ovs-vswitchd.log"
diff "$T/before.txt" "$T/after-recreate.txt" > "$T/diff-before-vs-after-recreate.txt"
finish

# ---------------------------------------------------------------- b2: the same recreate back to back (timing, no strace)
T=$OUT/b2-recreate-timing && mkdir -p "$T"
ping_start; sleep 2
tstart=$(now)
ev "T0 docker stop -t 10 $VS; docker rm; docker run (no pause, no strace)"
docker stop -t 10 $VS >/dev/null; ev "docker stop returned (rc=$?)"
docker rm $VS >/dev/null; ev "docker rm returned"
run_vs; ev "docker run (create + start) returned"
wait_bridge && ev "vswitchd answers on $SEC.mgmt again"
ev "flows (cookie lines) after recreate: $SEC $(docker exec $DB ovs-ofctl dump-flows $SEC | grep -c cookie), $STD $(docker exec $DB ovs-ofctl dump-flows $STD | grep -c cookie)"
sleep 2; ev "re-adding the flows"; add_flows; ev "flows re-added"; sleep 2
ping_stop
container_events $VS "$tstart" > "$T/events.raw"
finish

# ---------------------------------------------------------------- c: docker restart -t 10 openvswitch_db
T=$OUT/c-restart-db && mkdir -p "$T"
ping_start; sleep 2
snap "$T/before.txt" $VS; ps_tree $DB > "$T/ps-before.txt"
L0=$(loglines ovs-vswitchd.log); L1=$(loglines ovsdb-server.log)
strace_start $DB
tstart=$(now)
ev "T0 docker restart -t 10 $DB"
docker restart -t 10 $DB >/dev/null; ev "docker restart returned (rc=$?)"
wait_db && ev "kolla's wait handler check passes (docker exec $DB ovs-vsctl --no-wait show)"
strace_stop
snap "$T/after-restart.txt" $VS; ev "snapshot after-restart.txt taken"
ps_tree $DB > "$T/ps-after.txt"
# Does vswitchd reconnect and apply new configuration? ovs-vsctl without --no-wait waits until vswitchd has applied it.
docker exec $VS ovs-vsctl --timeout=10 add-port $STD e5-int9 -- set Interface e5-int9 type=internal
ev "ovs-vsctl add-port $STD e5-int9 (waits for vswitchd to apply it) rc=$?; ofport=$(ofport e5-int9)"
docker exec $VS ovs-vsctl --timeout=10 del-port $STD e5-int9; ev "ovs-vsctl del-port rc=$?"
sleep 3
snap "$T/after-restart+5s.txt" $VS
ping_stop
container_events $DB "$tstart" > "$T/events.raw"
tail -n +$((L0 + 1)) "$(logdir)/ovs-vswitchd.log" | grep -v 'Datapath supports' > "$T/ovs-vswitchd.log"
tail -n +$((L1 + 1)) "$(logdir)/ovsdb-server.log" > "$T/ovsdb-server.log"
diff "$T/before.txt" "$T/after-restart.txt" > "$T/diff-before-vs-after-restart.txt"
finish

# ---------------------------------------------------------------- d: is anything on the start path saving/restoring flows?
T=$OUT/d-grep && mkdir -p "$T"
PAT='ovs-save|flow-restore-wait|flow_restore_wait|restore-flows|replace-flows|dump-flows|add-flows|ovs-ctl'
{
  for img in e5-openvswitch-db-server:ussuri e5-openvswitch-vswitchd:ussuri; do
    echo "### $img: start-path files (kolla_start, kolla_set_configs, kolla_extend_start, kolla_openvswitch_extend_start, kolla_copy_cacerts)"
    docker run --rm --entrypoint bash $img -c "grep -n -E '$PAT' /usr/local/bin/kolla_start /usr/local/bin/kolla_set_configs \
      /usr/local/bin/kolla_extend_start /usr/local/bin/kolla_openvswitch_extend_start /usr/local/bin/kolla_copy_cacerts; echo grep rc=\$?"
    echo "### $img: every file in the image that mentions ovs-save or flow-restore-wait"
    docker run --rm --entrypoint bash $img -c "grep -rlI -E 'ovs-save|flow-restore-wait' / --exclude-dir=proc --exclude-dir=sys 2>/dev/null | sort"
  done
  echo "### the package's own save/restore (ovs-lib restart(), reached only through 'ovs-ctl restart'; kolla never runs ovs-ctl)"
  docker run --rm --entrypoint bash e5-openvswitch-vswitchd:ussuri -c \
    "grep -n -E '^(restart|force_reload_kmod) \(\)|^ +(save_flows_if_required|flow_restore_wait|restore_flows|flow_restore_complete)$' /usr/share/openvswitch/scripts/ovs-lib;
     grep -n -E '^ +restart\)|^ +force-reload-kmod\)' /usr/share/openvswitch/scripts/ovs-ctl"
  echo "### rendered kolla-ansible files in cfg/ (config.json, start-ovs, start-ovsdb-server)"
  grep -rn -E "$PAT" "$CFG"; echo "grep rc=$?"
  echo "### kolla-ansible ussuri-eol ansible/ tree"
  (cd "$KA_SRC" && git grep -n -E "$PAT" -- ansible/); echo "git grep rc=$?"
  echo "### kolla ussuri-eol docker/ tree"
  (cd "$KOLLA_SRC" && git grep -n -E "$PAT" -- docker/); echo "git grep rc=$?"
  echo "### live conf.db: Open_vSwitch other_config (flow-restore-wait would be here)"
  docker exec $DB ovs-vsctl get Open_vSwitch . other_config
  echo "### live processes of both containers (docker top): nothing besides dumb-init, the wrapper and the daemon"
  for c in $VS $DB; do docker top $c -o pid,args | sed 1d | awk '{$1=""; print}'; done
} > "$T/grep.txt" 2>&1

# ---------------------------------------------------------------- e1: control - what ovs-vswitchd does when it DOES get SIGTERM
T=$OUT/e1-sigterm-control && mkdir -p "$T"
L0=$(loglines ovs-vswitchd.log)
STRACE_EXTRA=unlink,unlinkat strace_start $VS
tstart=$(now)
ev "T0 docker exec $VS kill -TERM <ovs-vswitchd pid> (direct SIGTERM to the daemon; not a kolla path)"
docker exec $VS sh -c 'kill -TERM $(cat /run/openvswitch/ovs-vswitchd.pid)'; ev "kill sent (rc=$?)"
sleep 1
wait_bridge && ev "vswitchd answers on $SEC.mgmt again (container restarted by its restart policy)"
strace_stop
ev "flows (cookie lines) now: $SEC $(docker exec $DB ovs-ofctl dump-flows $SEC | grep -c cookie)"
container_events $VS "$tstart" > "$T/events.raw"
docker inspect -f 'restartCount={{.RestartCount}}' $VS > "$T/restart-count.txt"
tail -n +$((L0 + 1)) "$(logdir)/ovs-vswitchd.log" | grep -v 'Datapath supports' | head -8 > "$T/ovs-vswitchd.log"
finish
add_flows

# ---------------------------------------------------------------- e2: control - OVS's own save/restore around the same restart
# The ovs-lib restart() sequence done by hand around kolla's restart: ovs-save save-flows, flow-restore-wait=true,
# restart, run the saved script, remove flow-restore-wait. Saved under /run/openvswitch (the shared bind mount).
T=$OUT/e2-save-restore-control && mkdir -p "$T"
ping_start; sleep 2
snap "$T/before.txt" $DB
tstart=$(now)
ev "T0 ovs-save save-flows $SEC $STD (TMPDIR=/run/openvswitch)"
docker exec $VS sh -c "TMPDIR=/run/openvswitch /usr/share/openvswitch/scripts/ovs-save save-flows $SEC $STD \
  > /run/openvswitch/e5-restore-flows.sh && chmod +x /run/openvswitch/e5-restore-flows.sh"; ev "flows saved (rc=$?)"
docker exec $DB ovs-vsctl set Open_vSwitch . other_config:flow-restore-wait=true; ev "flow-restore-wait=true set (rc=$?)"
docker restart -t 10 $VS >/dev/null; ev "docker restart -t 10 returned (rc=$?)"
wait_bridge && ev "vswitchd answers on $SEC.mgmt again"
ev "flows (cookie lines) before restore: $SEC $(docker exec $DB ovs-ofctl dump-flows $SEC | grep -c cookie)"
docker exec $VS sh /run/openvswitch/e5-restore-flows.sh; ev "saved flows restored (rc=$?)"
docker exec $DB ovs-vsctl --if-exists remove Open_vSwitch . other_config flow-restore-wait=true; ev "flow-restore-wait removed (rc=$?)"
sleep 3
snap "$T/after.txt" $DB
ping_stop
sed -E 's#/run/openvswitch/ovs-save\.[A-Za-z0-9]+#/run/openvswitch/ovs-save.XXXX#g' "$RUNDIR/e5-restore-flows.sh" > "$T/e5-restore-flows.sh"
diff "$T/before.txt" "$T/after.txt" > "$T/diff-before-vs-after.txt"
container_events $VS "$tstart" > "$T/events.raw"
finish

# ---------------------------------------------------------------- end
grep -n -E 'opened log file|terminating with signal|ovs-vswitchd \(Open vSwitch\)|ovsdb-server \(Open vSwitch\)' \
  "$(logdir)/ovs-vswitchd.log" "$(logdir)/ovsdb-server.log" | sed "s#$(logdir)/##" > "$OUT/log-starts-and-signals.txt"
cleanup
echo "e5 done; results in $OUT"
