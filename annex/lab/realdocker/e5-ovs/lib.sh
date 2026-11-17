# shellcheck shell=bash
# e5 helpers, sourced by run.sh. Everything created here is prefixed e5 (containers, volumes, images, host links).

here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
WORK=${E5_WORK:-$here/work}
OUT=$here/out
CFG=$here/cfg
KV=$(uname -r)
DB=e5_openvswitch_db
VS=e5_openvswitch_vswitchd
PEERS="e5-peer1 e5-peer2"
LOGVOL=e5_kolla_logs
DBVOL=e5_openvswitch_db
RUNDIR=$WORK/run-openvswitch          # stands in for the host's /run/openvswitch
MODDIR=$WORK/lib-modules              # stands in for the host's /lib/modules (see prepare_modules)
SEC=e5-br-sec                         # fail_mode=secure, as neutron sets on its bridges
STD=e5-br-std                         # fail_mode unset (standalone)

now() { date +%s.%N; }
ev() { echo "$(now) $*" >> "$T/timeline.raw"; }       # timeline event of the current test dir $T
nsh() { docker run --rm --network host --pid host --privileged e5-peer:ussuri sh -c "$1"; }  # host-netns iproute2
logdir() { echo "$(docker volume inspect -f '{{.Mountpoint}}' $LOGVOL)/openvswitch"; }
loglines() { wc -l < "$(logdir)/$1" 2>/dev/null || echo 0; }

# Container parameters as kolla_docker creates them for the openvswitch role (roles/openvswitch/defaults/main.yml:2-66,
# handlers/main.yml; kolla_docker.py build_host_config: network_mode host; docker_common_options: COPY_ALWAYS,
# restart unless-stopped; KOLLA_SERVICE_NAME = container name with '_' -> '-').
# Substitutions: e5 names; $CFG/<svc> for /etc/kolla/<svc>; $MODDIR for /lib/modules; $RUNDIR for /run/openvswitch
# (a bind mount made shared, so ':shared' is accepted as in the role); e5 volumes for kolla_logs and openvswitch_db.
common_args() {
  echo --network host --restart unless-stopped -e KOLLA_CONFIG_STRATEGY=COPY_ALWAYS \
    -v /etc/localtime:/etc/localtime:ro -v /etc/timezone:/etc/timezone:ro \
    -v "$MODDIR:/lib/modules:ro" -v "$RUNDIR:/run/openvswitch:shared" -v "$LOGVOL:/var/log/kolla/"
}
run_db() {
  # shellcheck disable=SC2046
  docker run -d --name $DB $(common_args) -e KOLLA_SERVICE_NAME=openvswitch-db \
    -v "$CFG/openvswitch-db-server/:/var/lib/kolla/config_files/:ro" -v "$DBVOL:/var/lib/openvswitch/" \
    e5-openvswitch-db-server:ussuri >/dev/null
}
run_vs() {
  # shellcheck disable=SC2046
  docker run -d --name $VS --privileged $(common_args) -e KOLLA_SERVICE_NAME=openvswitch-vswitchd \
    -v "$CFG/openvswitch-vswitchd/:/var/lib/kolla/config_files/:ro" e5-openvswitch-vswitchd:ussuri >/dev/null
}

# The "Waiting for openvswitch_db service to be ready" handler: docker exec ... ovs-vsctl --no-wait show, 30 x 2 s.
wait_db() {
  local i
  for i in $(seq 30); do docker exec $DB ovs-vsctl --no-wait show >/dev/null 2>&1 && return 0; sleep 2; done
  return 1
}
# vswitchd is up with its bridges when ovs-ofctl can talk to the bridge's management socket (polled every 50 ms).
wait_bridge() {
  local i
  for i in $(seq 600); do
    docker exec $DB ovs-ofctl dump-flows $SEC >/dev/null 2>&1 && return 0
    sleep 0.05
  done
  return 1
}

# /lib/modules stand-in. Mode "empty": an empty directory (this host has no /lib/modules at all), so kolla's
# vswitchd extend_start "modprobe openvswitch" fails. Mode "builtin": modules.builtin lists openvswitch and depmod
# indexes it, so the real kmod modprobe exits 0 ("built in") without loading anything. Image and scripts unchanged.
prepare_modules() {
  rm -rf "$MODDIR" && mkdir -p "$MODDIR"
  if [ "$1" = builtin ]; then
    mkdir -p "$MODDIR/$KV" && echo kernel/net/openvswitch/openvswitch.ko > "$MODDIR/$KV/modules.builtin"
    docker run --rm --network none -v "$MODDIR:/lib/modules" --entrypoint depmod e5-openvswitch-vswitchd:ussuri \
      -a "$KV" 2>/dev/null
  fi
}

# Host pids of the container's processes: dumb-init, its child, and the grandchild (the daemon).
proc_tree() {
  local p1 p2 p3
  p1=$(docker inspect -f '{{.State.Pid}}' "$1")
  p2=$(cat /proc/$p1/task/$p1/children | awk '{print $1}')
  p3=$(cat /proc/$p2/task/$p2/children | awk '{print $1}')
  echo "$p1 $p2 $p3"
}
ps_tree() { # host view: pid, ppid and command of the three processes
  local p
  for p in $(proc_tree "$1"); do
    printf '%-8s ppid=%-8s %s\n' "$p" "$(awk '/^PPid/{print $2}' /proc/$p/status)" "$(tr '\0' ' ' < /proc/$p/cmdline)"
  done
}
# strace on the host, all threads (-f): signals, exits, and only the syscalls dumb-init uses to take and forward a
# signal (rt_sigtimedwait, kill) and to exit (exit_group). Attaching with -p does not signal the tracees.
strace_start() { # also writes pids.txt: "<host pid> <comm>(<pid in the container>)" for analyze.py
  local args=() p
  for p in $(proc_tree "$1"); do
    args+=(-p "$p")
    echo "$p $(cat /proc/$p/comm)($(awk '/^NSpid/{print $NF}' /proc/$p/status))" >> "$T/pids.txt"
  done
  strace -ttt -T -f -q -e trace=rt_sigtimedwait,kill,exit_group${STRACE_EXTRA:+,$STRACE_EXTRA} -e signal=all -o "$T/strace.raw" "${args[@]}" 2>"$T/strace.err" &
  STRACE=$!
  sleep 0.5
}
strace_stop() { sleep 1; kill "$STRACE" 2>/dev/null; wait "$STRACE" 2>/dev/null || true; }

# Traffic probe: peers in their own netns, each with one veth end per bridge; the host ends are OVS ports.
#   e5-peer1: e5-v1b 10.55.1.1 (on $SEC)  e5-v3b 10.55.2.1 (on $STD)
#   e5-peer2: e5-v2b 10.55.1.2 (on $SEC)  e5-v4b 10.55.2.2 (on $STD)
setup_peers() {
  local p i pid
  for p in $PEERS; do
    docker run -d --name "$p" --network none --cap-add NET_ADMIN e5-peer:ussuri >/dev/null
  done
  for i in 1 2 3 4; do
    if [ $i -eq 1 ] || [ $i -eq 3 ]; then p=e5-peer1; else p=e5-peer2; fi
    pid=$(docker inspect -f '{{.State.Pid}}' $p)
    nsh "ip link add e5-v${i}a type veth peer name e5-v${i}b && ip link set e5-v${i}b netns $pid \
         && ip link set e5-v${i}a up"   # no IPv6 in this kernel: no IPv6 noise on the probes
  done
  docker exec e5-peer1 sh -c 'ip a add 10.55.1.1/24 dev e5-v1b && ip l set e5-v1b up &&
                              ip a add 10.55.2.1/24 dev e5-v3b && ip l set e5-v3b up'
  docker exec e5-peer2 sh -c 'ip a add 10.55.1.2/24 dev e5-v2b && ip l set e5-v2b up &&
                              ip a add 10.55.2.2/24 dev e5-v4b && ip l set e5-v4b up'
}

# Bridges, ports and conf.db settings (the "state" whose persistence is tested), all through ovsdb.
setup_bridges() {
  docker exec $VS ovs-vsctl set Open_vSwitch . external_ids:system-id=e5-lab-host   # as post-config.yml does
  docker exec $DB ovs-vsctl set Open_vSwitch . other_config:max-idle=15000
  docker exec $DB ovs-vsctl \
    -- add-br $SEC -- set Bridge $SEC datapath_type=netdev fail_mode=secure protocols=OpenFlow10,OpenFlow13 \
         external_ids:bridge-id=$SEC other_config:mac-table-size=4096 \
    -- add-br $STD -- set Bridge $STD datapath_type=netdev other_config:mac-table-size=2048 \
    -- add-port $SEC e5-v1a -- set Interface e5-v1a external_ids:iface-id=e5-port-1 \
         external_ids:attached-mac='"02:e5:00:00:00:01"' external_ids:iface-status=active \
    -- add-port $SEC e5-v2a -- set Interface e5-v2a external_ids:iface-id=e5-port-2 \
    -- add-port $STD e5-v3a -- add-port $STD e5-v4a \
    -- add-port $SEC e5-patch-std -- set Interface e5-patch-std type=patch options:peer=e5-patch-sec \
    -- add-port $STD e5-patch-sec -- set Interface e5-patch-sec type=patch options:peer=e5-patch-std \
    -- set Port e5-v1a tag=101 -- set Port e5-v2a tag=101
}
ofport() { docker exec $DB ovs-vsctl get Interface "$1" ofport; }
# OpenFlow flows with cookies (what an agent would program). $SEC has no default flow (fail_mode secure): only these
# forward the probe traffic. Table 23 holds a drop flow like neutron's canary flow (CANARY_TABLE = 23).
add_flows() {
  local p1 p2 p3
  p1=$(ofport e5-v1a); p2=$(ofport e5-v2a); p3=$(ofport e5-v3a)
  docker exec -i $DB ovs-ofctl add-flows $SEC - <<EOF
cookie=0xe5000001,table=0,priority=100,in_port=$p1,actions=output:$p2
cookie=0xe5000002,table=0,priority=100,in_port=$p2,actions=output:$p1
cookie=0xe5000003,table=0,priority=1,actions=drop
cookie=0xe5000017,table=23,priority=0,actions=drop
EOF
  docker exec -i $DB ovs-ofctl add-flows $STD - <<EOF
cookie=0xe5000011,table=0,priority=200,dl_type=0x88cc,actions=drop
cookie=0xe5000012,table=0,priority=100,in_port=$p3,ip,nw_dst=10.55.2.0/24,actions=NORMAL
EOF
}

# State snapshot through a given container's OVS clients (both containers share /run/openvswitch).
snap() { # snap <file> <container>
  local c=$2
  {
    echo "### ovs-vsctl show"; docker exec "$c" ovs-vsctl --timeout=5 --no-wait show 2>&1
    echo "### Open_vSwitch row"
    docker exec "$c" ovs-vsctl --timeout=5 --no-wait --columns=external_ids,other_config,cur_cfg,next_cfg \
      list Open_vSwitch 2>&1
    echo "### Bridge rows"
    docker exec "$c" ovs-vsctl --timeout=5 --no-wait --columns=name,datapath_type,fail_mode,protocols,other_config,external_ids \
      list Bridge 2>&1
    echo "### Interface rows (name, type, ofport, options, external_ids)"
    docker exec "$c" ovs-vsctl --timeout=5 --no-wait --format=table --columns=name,type,ofport,options,external_ids \
      list Interface 2>&1
    local b
    for b in $SEC $STD; do
      echo "### ovs-ofctl dump-flows $b"
      docker exec "$c" ovs-ofctl dump-flows $b 2>&1 | sed -E 's/ duration=[0-9.]+s,//; s/ idle_age=[0-9]+,?//; s/ hard_age=[0-9]+,?//'
    done
  } > "$1"
}

# Pings every 50 ms from e5-peer1 over both bridges; -D timestamps every line, -O reports each missing reply.
ping_start() {
  docker exec e5-peer1 sh -c 'rm -f /tmp/ping-*; for d in 10.55.1.2 10.55.2.2; do
      (ping -D -O -n -i 0.05 -W 1 $d > /tmp/ping-$d.log 2>&1 & echo $! > /tmp/ping-$d.pid); done'
  ev "pings started"
}
ping_stop() {
  local d
  ev "pings stopped"
  docker exec e5-peer1 sh -c 'for f in /tmp/ping-*.pid; do kill -INT $(cat $f); done; sleep 0.5'
  for d in 10.55.1.2 10.55.2.2; do docker cp -q e5-peer1:/tmp/ping-$d.log "$T/ping-$d.raw"; done
}
container_events() { # die/start events of container $1 since epoch $2 until now
  docker events --since "$2" --until "$(date +%s.%N)" --filter container="$1" \
    --format '{{.TimeNano}} {{.Action}} exitCode={{index .Actor.Attributes "exitCode"}}' \
    | grep -E ' (kill|die|stop|start|restart|destroy|create)' | sed 's/exitCode=<no value>//'
}

cleanup() {
  local c
  for c in $VS $DB $PEERS; do docker rm -f "$c" >/dev/null 2>&1 || true; done
  # netdev bridges leave persistent tap devices in the host netns (see README); veths die with the peers' netns.
  nsh 'for l in e5-br-sec e5-br-std e5-int9 e5-v1a e5-v2a e5-v3a e5-v4a; do ip link del $l 2>/dev/null; done; true' || true
  docker volume rm $LOGVOL $DBVOL >/dev/null 2>&1 || true
  if mountpoint -q "$RUNDIR" 2>/dev/null; then umount "$RUNDIR"; fi
  rm -rf "$RUNDIR" "$MODDIR"
}

# Summarise test dir $T (analyze.py), then drop the bulky raw inputs it has condensed.
finish() {
  python3 "$here/analyze.py" "$T" > /dev/null || return 1
  rm -f "$T"/ping-*.raw "$T/strace.raw" "$T/timeline.raw" "$T/events.raw" "$T/pids.txt"
  [ -s "$T/strace.err" ] || rm -f "$T/strace.err"
}
