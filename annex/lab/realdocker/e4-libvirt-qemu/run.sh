#!/bin/bash
# e4: do QEMU processes survive a nova_libvirt restart or recreate (study Q1)? Real libvirtd + QEMU (TCG) in a
# container that mirrors kolla-ansible ussuri-eol's nova_libvirt, on a real Docker daemon.
# Usage: KOLLA_ANSIBLE_SRC=<kolla-ansible ussuri-eol> ./run.sh [a b c d]   (default: all)
#   a   docker restart -t 10 (kolla_docker restart_container: stop timeout 10 + start)
#   b   recreate: docker stop -t 10, docker rm -f, docker run (kolla_docker recreate_or_restart_container)
#   c   QEMU moved to another cgroup from the host before the stop (c1 every hierarchy = machined model, restart
#       then recreate; c2 only the unified v2 hierarchy, restart then recreate; c3 every hierarchy except the
#       unified one, restart)
#   d   control without --pid host (d1 as placed by libvirt, d2 after the c1 move)
# Needs: root, docker, strace, python3 with jinja2, the image e4-nova-libvirt:ussuri (./build.sh, which needs
# reallab/base:ussuri). Idempotent: removes its own container, volumes, cgroups and work dir first.
# Creates only: container e4_nova_libvirt, volumes e4_*, cgroups e4-machine, work dir /run/e4-lab, host TCP port
# 18409 (libvirtd --listen on 127.0.0.1). Kills only QEMU processes whose command line has guest=e4-vm-*.
set -u
here=$(cd "$(dirname "$0")" && pwd)
source "$here/lib.sh"
: "${KOLLA_ANSIBLE_SRC:?set KOLLA_ANSIBLE_SRC to a kolla-ansible ussuri-eol checkout (commit 8a94fe9)}"
[ "$(id -u)" = 0 ] || { echo "run as root (host cgroup writes, strace of the containerd shim)"; exit 1; }
command -v strace >/dev/null || { echo "strace is required on the host"; exit 1; }
python3 -c 'import jinja2' || { echo "python3 jinja2 is required"; exit 1; }
docker image inspect "$IMG" >/dev/null 2>&1 || { echo "build $IMG first: KOLLA_SRC=... ./build.sh"; exit 1; }
[ -e /run/dbus/system_bus_socket ] && echo "NOTE: this host has a D-Bus socket; the lab assumes none (no machined)"
TESTS=${*:-a b c d}

# fresh VM [--no-pid-host]: new container on empty volumes and an empty host /run stand-in, one running guest.
fresh() {
  local vm=$1 i; shift
  if docker inspect "$CTR" >/dev/null 2>&1; then kill_e4_qemu $ALL_VMS; fi
  docker rm -f "$CTR" >/dev/null 2>&1
  for v in $VOLUMES; do docker volume rm "$v" >/dev/null 2>&1; done
  kill_e4_qemu $ALL_VMS; rm_cgroups
  rm -rf "${WORK:?}/hostrun/"*
  run_ctr "$@" || { echo "docker run failed"; return 1; }
  wait_libvirtd || return 1
  define_start "$vm" >/dev/null || { echo "virsh start $vm failed"; return 1; }
  for i in $(seq 1 20); do [ -n "$(qemu_pid "$vm")" ] && break; sleep 0.5; done
  sleep 2   # let SeaBIOS run
}

# verdict TEST STEP VM QPID: one summary line after the step.
verdict() {
  local t=$1 step=$2 vm=$3 qp=$4 alive state mon
  if [ -d "/proc/$qp" ] && grep -qa "guest=$vm" "/proc/$qp/cmdline"; then alive="ALIVE (same pid)"; else alive="GONE"; fi
  state=$(virsh domstate "$vm" --reason 2>&1 | sed '/^\s*$/d' | tr '\n' ' ')
  # suspend + resume go through the QEMU monitor: they work only if libvirtd holds a live monitor connection
  if virsh suspend "$vm" >/dev/null 2>&1 && virsh resume "$vm" >/dev/null 2>&1; then mon="suspend+resume OK"
  else mon="suspend+resume failed: $(virsh suspend "$vm" 2>&1 | sed '/^\s*$/d' | tail -1)"; fi
  printf '%-4s %-30s qemu pid %-7s %-17s virsh domstate: %-22s monitor: %s\n' "$t" "$step" "$qp" "$alive" \
    "$(echo "$state" | sed -E 's/([0-9a-f]{12})[0-9a-f]{52}/\1/g')" \
    "$(echo "$mon" | sed -E 's/([0-9a-f]{12})[0-9a-f]{52}/\1/g')" >> "$OUT/${t:0:1}/summary.txt"
}

# timed LOGFILE CMD...: run a docker command, log its rc, wall time and output.
timed() {
  local log=$1 t0 t1 rc o; shift
  t0=$(now); o=$("$@" 2>&1); rc=$?; t1=$(now)
  echo "\$ $* -> rc=$rc, $(dt "$t0" "$t1") s${o:+, output: $(echo "$o" | tr '\n' ' ')}" \
    | sed -E 's/([0-9a-f]{12})[0-9a-f]{52}/\1/g' >> "$log"
  T0=$t0; RC=$rc
}

# Snapshots of a step go to $SNAPF.
# kolla_docker's restart (restart_container: stop timeout 10 + start). The "Restart nova-libvirt container" handler
# retries a failed attempt 5 times (retries: 5, Ansible's default delay 5 s; roles/nova-cell/handlers/main.yml:87-109);
# a retry of restart_container is again stop (a no-op on a stopped container) + start.
restart_step() { # TEST TAG VM QPID DIR
  local t=$1 tag=$2 vm=$3 qp=$4 d=$5 i t0
  shim_trace_start "$tag"
  timed "$d/commands.txt" docker restart -t 10 "$CTR"; t0=$T0
  if [ "$RC" != 0 ]; then
    for i in 1 2 3 4 5; do
      sleep 5
      timed "$d/commands.txt" docker stop -t 10 "$CTR"
      timed "$d/commands.txt" docker start "$CTR"
      [ "$RC" = 0 ] && break
    done
    echo "$tag: after the handler-style retries: container $(docker inspect -f '{{.State.Status}}' "$CTR")" >> "$d/commands.txt"
  fi
  wait_libvirtd; sleep 3
  shim_trace_end "$tag" "$t0" "$d/shim-$tag.txt" "$qp"
  snap "$SNAPF" "$tag: after docker restart -t 10" "$vm" "$qp"
  verdict "$t" "docker restart -t 10" "$vm" "$qp"
}

# kolla_docker's recreate (recreate_or_restart_container: stop_container timeout 10, remove_container force,
# start_container = create + start), with the handler's 5 retries; on a retry an exited container is not stopped
# again and a removed one is not removed again.
recreate_step() { # TEST TAG VM QPID DIR [run_ctr args]
  local t=$1 tag=$2 vm=$3 qp=$4 d=$5 i ok; shift 5
  shim_trace_start "$tag"
  timed "$d/commands.txt" docker stop -t 10 "$CTR"
  shim_trace_end "$tag" "$T0" "$d/shim-$tag.txt" "$qp"
  echo "$tag: after docker stop, before rm: qemu $qp $([ -d /proc/$qp ] && echo ALIVE || echo GONE)," \
       "container status $(docker inspect -f '{{.State.Status}} exit={{.State.ExitCode}}' "$CTR")" >> "$d/commands.txt"
  for i in 0 1 2 3 4 5; do
    ok=1
    if [ "$i" -gt 0 ]; then
      sleep 5
      if [ "$(docker inspect -f '{{.State.Status}}' "$CTR" 2>/dev/null)" = running ]; then
        timed "$d/commands.txt" docker stop -t 10 "$CTR"; [ "$RC" = 0 ] || ok=0
      fi
    fi
    if [ "$ok" = 1 ] && docker inspect "$CTR" >/dev/null 2>&1; then
      timed "$d/commands.txt" docker rm -f "$CTR"; [ "$RC" = 0 ] || ok=0
    fi
    if [ "$ok" = 1 ]; then timed "$d/commands.txt" run_ctr "$@"; [ "$RC" = 0 ] && break; fi
  done
  wait_libvirtd; sleep 3
  snap "$SNAPF" "$tag: after recreate (stop, rm -f, run)" "$vm" "$qp"
  verdict "$t" "recreate (stop, rm -f, run)" "$vm" "$qp"
}

test_a() {
  local d=$OUT/a vm=e4-vm-a qp
  note "a: docker restart -t 10"
  SNAPF=$d/snapshots.txt
  fresh "$vm" || return 1; qp=$(qemu_pid "$vm")
  snap "$SNAPF" "a: before" "$vm" "$qp"
  restart_step a a-restart "$vm" "$qp" "$d"
  libvirtd_log "$d/libvirtd.log"
}

test_b() {
  local d=$OUT/b vm=e4-vm-b qp
  note "b: recreate"
  SNAPF=$d/snapshots.txt
  fresh "$vm" || return 1; qp=$(qemu_pid "$vm")
  snap "$SNAPF" "b: before" "$vm" "$qp"
  recreate_step b b-recreate "$vm" "$qp" "$d"
  libvirtd_log "$d/libvirtd.log"
}

test_c() {
  local d=$OUT/c vm qp lp oldid
  note "c1: QEMU moved to $CG_NAME in every hierarchy (machined model); restart, then recreate"
  vm=e4-vm-c1; SNAPF=$d/snapshots-c1.txt
  fresh "$vm" || return 1; qp=$(qemu_pid "$vm")
  snap "$SNAPF" "c1: before the move" "$vm" "$qp"
  move_cgroup "$qp" "$d/commands.txt" all
  snap "$SNAPF" "c1: after the move" "$vm" "$qp"
  lp=$($PY "$E4/proc.py" kids "$(init_pid)" | head -1)
  { echo "c1 before restart: qemu mnt ns $(readlink /proc/$qp/ns/mnt), libvirtd $lp mnt ns $(readlink /proc/$lp/ns/mnt)"
    $PY "$E4/proc.py" rootmnt "qemu" "$qp"; $PY "$E4/proc.py" rootmnt "libvirtd" "$lp"; } >> "$d/mountns-c1.txt"
  restart_step c1 c1-restart "$vm" "$qp" "$d"
  recreate_step c1 c1-recreate "$vm" "$qp" "$d"
  lp=$($PY "$E4/proc.py" kids "$(init_pid)" | head -1)
  { echo "c1 after recreate: qemu mnt ns $(readlink /proc/$qp/ns/mnt), new libvirtd $lp mnt ns $(readlink /proc/$lp/ns/mnt)"
    $PY "$E4/proc.py" rootmnt "qemu" "$qp"; $PY "$E4/proc.py" rootmnt "new libvirtd" "$lp"
    echo "qemu exe: $(readlink /proc/$qp/exe); qemu ppid: $(awk '/^PPid/{print $2}' /proc/$qp/status)" \
         "($(cat /proc/$(awk '/^PPid/{print $2}' /proc/$qp/status)/comm))"
  } >> "$d/mountns-c1.txt"
  timed "$d/commands.txt" docker exec "$CTR" virsh -c qemu:///system destroy "$vm"
  echo "c1: after virsh destroy through the new libvirtd: qemu $qp $([ -d /proc/$qp ] && echo ALIVE || echo GONE)" \
    >> "$d/commands.txt"
  libvirtd_log "$d/libvirtd-c1.log"

  note "c2: QEMU moved to $CG_NAME in the unified (v2) hierarchy only; restart, then recreate"
  vm=e4-vm-c2; SNAPF=$d/snapshots-c2.txt
  fresh "$vm" || return 1; qp=$(qemu_pid "$vm")
  move_cgroup "$qp" "$d/commands.txt" unified-only
  snap "$SNAPF" "c2: after the move" "$vm" "$qp"
  restart_step c2 c2-restart "$vm" "$qp" "$d"
  # what an operator or a later kolla-ansible run would do next with the exited container: recreate it
  oldid=$(docker inspect -f '{{.Id}}' "$CTR")
  echo "c2 before recreate: $(containerd_state "$oldid")" >> "$d/commands.txt"
  recreate_step c2 c2-recreate-after-failed-restart "$vm" "$qp" "$d"
  echo "c2 after recreate (old container removed by docker rm -f): $(containerd_state "$oldid");" \
       "old cgroup dirs: $(ls -d /sys/fs/cgroup/*/docker/"$oldid" 2>/dev/null | sed -E 's#/sys/fs/cgroup/([^/]+)/.*#\1#' | tr '\n' ' ')" \
       >> "$d/commands.txt"
  lp=$($PY "$E4/proc.py" kids "$(init_pid)" | head -1)
  { echo "c2 after recreate: qemu mnt ns $(readlink /proc/$qp/ns/mnt), new libvirtd $lp mnt ns $(readlink /proc/$lp/ns/mnt)"
    $PY "$E4/proc.py" rootmnt "qemu" "$qp"; $PY "$E4/proc.py" rootmnt "new libvirtd" "$lp"; } >> "$d/mountns-c2.txt"
  libvirtd_log "$d/libvirtd-c2.log"

  note "c3: QEMU moved to $CG_NAME in every hierarchy except the unified one; restart"
  vm=e4-vm-c3; SNAPF=$d/snapshots-c3.txt
  fresh "$vm" || return 1; qp=$(qemu_pid "$vm")
  move_cgroup "$qp" "$d/commands.txt" all-but-unified
  snap "$SNAPF" "c3: after the move" "$vm" "$qp"
  restart_step c3 c3-restart "$vm" "$qp" "$d"
}

test_d() {
  local d=$OUT/d vm qp
  note "d1: no --pid host; restart"
  vm=e4-vm-d1; SNAPF=$d/snapshots-d1.txt
  fresh "$vm" --no-pid-host || return 1; qp=$(qemu_pid "$vm")
  snap "$SNAPF" "d1: before" "$vm" "$qp"
  restart_step d1 d1-restart "$vm" "$qp" "$d"
  libvirtd_log "$d/libvirtd-d1.log"

  note "d2: no --pid host, QEMU moved to $CG_NAME in every hierarchy; restart"
  vm=e4-vm-d2; SNAPF=$d/snapshots-d2.txt
  fresh "$vm" --no-pid-host || return 1; qp=$(qemu_pid "$vm")
  move_cgroup "$qp" "$d/commands.txt" all
  snap "$SNAPF" "d2: after the move" "$vm" "$qp"
  restart_step d2 d2-restart "$vm" "$qp" "$d"
}

environment() {
  local f=$OUT/environment.txt
  {
    echo "# e4 environment ($(date -u +%Y-%m-%dT%H:%MZ))"
    echo "kernel: $(uname -r)"
    docker version -f 'docker server {{.Server.Version}}; {{range .Server.Components}}{{.Name}} {{.Version}}; {{end}}'
    docker info -f 'cgroup driver {{.CgroupDriver}}, cgroup version {{.CgroupVersion}}, storage {{.Driver}}'
    echo "host cgroup mounts:"; grep -E ' cgroup2? ' /proc/mounts | awk '{print "  "$2, $3, $4}'
    echo "host CapBnd: $(awk '/CapBnd/{print $2}' /proc/self/status) (bit 24 CAP_SYS_RESOURCE: $(( (0x$(awk '/CapBnd/{print $2}' /proc/self/status) >> 24) & 1 )))"
    echo "host D-Bus system socket: $(ls /run/dbus/system_bus_socket 2>&1)"
    echo "host PID 1: $(cat /proc/1/comm) (no systemd, no systemd-machined)"
    echo "host / propagation: $(findmnt -no PROPAGATION /)"
    echo "image $IMG: $(docker image inspect -f '{{.Id}}' "$IMG" | cut -c1-19)"
    docker run --rm --name e4-env "$IMG" bash -c '
      dpkg-query -W -f="  \${Package} \${Version}\n" libvirt-daemon-system libvirt0 qemu-system-x86 dumb-init sasl2-bin
      grep VERSION= /etc/os-release | sed "s/^/  /"
      echo "  /var/run -> $(readlink /var/run)"
      echo "  hard limits in a container: nofile $(ulimit -Hn), nproc $(ulimit -Hu)"'
  } > "$f" 2>&1
}

note "prepare"
cleanup
mkdir -p "$OUT"
for t in $TESTS; do rm -rf "${OUT:?}/$t"; mkdir -p "$OUT/$t"; done
setup_hostrun
read -r HN HU < <(docker run --rm --name e4-limits "$IMG" bash -c 'echo $(ulimit -Hn) $(ulimit -Hu)')
# libvirt sets RLIMIT_NOFILE to max_files + 1 (virProcessSetMaxFiles), RLIMIT_NPROC to max_processes
E4_QEMU_MAX_FILES=$((HN - 1)) E4_QEMU_MAX_PROCESSES=$HU \
  python3 "$E4/render.py" "$KOLLA_ANSIBLE_SRC" "$WORK/config/nova-libvirt" >/dev/null
rm -rf "$OUT/config"; mkdir -p "$OUT/config"; cp "$WORK/config/nova-libvirt/"* "$OUT/config/"
environment
for t in $TESTS; do "test_$t"; done
note "cleanup"
cleanup
{ printf '# e4 summary: one line per step; "monitor" = virsh suspend + resume through the libvirtd running after the step\n'
  cat "$OUT"/[abcd]/summary.txt 2>/dev/null; } > "$OUT/summary.txt"
cat "$OUT/summary.txt"
