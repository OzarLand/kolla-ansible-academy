# e4 helpers, sourced by run.sh.
# Paths (override through the environment):
#   KOLLA_ANSIBLE_SRC  kolla-ansible checkout, tag ussuri-eol (8a94fe9)
#   E4_WORK            host work dir (default /run/e4-lab): rendered config, the host directory mounted as the
#                      container's /run, an empty stand-in for /lib/modules, raw traces
E4=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
OUT=$E4/out
WORK=${E4_WORK:-/run/e4-lab}
IMG=e4-nova-libvirt:ussuri
CTR=e4_nova_libvirt
VOLUMES="e4_kolla_logs e4_libvirtd e4_nova_compute e4_nova_libvirt_qemu"
CG_NAME=e4-machine
PY="python3 -I"

note() { echo "== $*"; }
now() { date +%s.%N; }
dt() { python3 -c "import sys; print('%.2f' % (float(sys.argv[2]) - float(sys.argv[1])))" "$1" "$2"; }

# The host /run stand-in: a dedicated host directory, made its own mount point with shared propagation, because
# this sandbox's / is a private mount and Docker refuses "/run/:/run/:shared" ("path /run is mounted on / but it
# is not a shared mount"). Making the host / shared would change propagation for every concurrent experiment.
setup_hostrun() {
  mkdir -p "$WORK/hostrun" "$WORK/lib-modules" "$WORK/raw"
  if ! mountpoint -q "$WORK/hostrun"; then mount --bind "$WORK/hostrun" "$WORK/hostrun"; fi
  mount --make-shared "$WORK/hostrun"
}

# docker run with the parameters kolla_docker gives nova_libvirt (kolla-ansible ussuri-eol):
#   roles/nova-cell/defaults/main.yml:2-11 (pid_mode host, privileged, volumes :237-250),
#   library/kolla_docker.py:717-775 (network_mode host, restart policy, KOLLA_SERVICE_NAME),
#   group_vars/all.yml:43,134,157-167 (KOLLA_CONFIG_STRATEGY=COPY_ALWAYS, restart_policy unless-stopped).
# Lab substitutions: e4_ prefixes on names and volumes; $WORK/hostrun for /run (see setup_hostrun);
# $WORK/lib-modules for /lib/modules (the sandbox host has no /lib/modules).
# Usage: run_ctr [--no-pid-host]
run_ctr() {
  local pid=(--pid host)
  [ "${1:-}" = "--no-pid-host" ] && pid=()
  docker run -d --name "$CTR" --net host "${pid[@]}" --privileged --restart unless-stopped \
    -e KOLLA_CONFIG_STRATEGY=COPY_ALWAYS -e KOLLA_SERVICE_NAME=nova-libvirt \
    -v "$WORK/config/nova-libvirt/:/var/lib/kolla/config_files/:ro" \
    -v /etc/localtime:/etc/localtime:ro \
    -v /etc/timezone:/etc/timezone:ro \
    -v "$WORK/lib-modules:/lib/modules:ro" \
    -v "$WORK/hostrun/:/run/:shared" \
    -v /dev:/dev \
    -v /sys/fs/cgroup:/sys/fs/cgroup \
    -v e4_kolla_logs:/var/log/kolla/ \
    -v e4_libvirtd:/var/lib/libvirt \
    -v e4_nova_compute:/var/lib/nova/ \
    -v e4_nova_libvirt_qemu:/etc/libvirt/qemu \
    "$IMG" >/dev/null
}

virsh() { docker exec "$CTR" virsh -c qemu:///system "$@"; }

wait_libvirtd() { # max 60 s
  local i
  for i in $(seq 1 120); do
    virsh version >/dev/null 2>&1 && return 0
    sleep 0.5
  done
  echo "libvirtd did not answer within 60 s" >&2; return 1
}

define_start() { # VM
  sed "s/@NAME@/$1/" "$E4/domain.xml.in" | docker exec -i "$CTR" sh -c 'cat > /tmp/dom.xml'
  virsh define /tmp/dom.xml && virsh start "$1"
}

qemu_pid() { $PY "$E4/proc.py" qemu "$1" | head -1; }

init_pid() { docker inspect -f '{{.State.Pid}}' "$CTR" 2>/dev/null; }

# snap FILE LABEL VM [QEMU_PID]: container, dumb-init, libvirtd and QEMU (cgroups, namespaces), libvirt's view.
snap() {
  local f=$1 label=$2 vm=$3 qp=${4:-} ip lp cid
  {
    echo "################ $label  ($(date -u +%H:%M:%S.%N | cut -c1-12) UTC)"
    docker inspect -f 'container {{.Name}} id={{printf "%.12s" .Id}} status={{.State.Status}} started={{.State.StartedAt}} pid_mode={{.HostConfig.PidMode}}' "$CTR" 2>&1
    ip=$(init_pid)
    if [ -n "$ip" ] && [ "$ip" != 0 ]; then
      $PY "$E4/proc.py" show init "$ip"
      for lp in $($PY "$E4/proc.py" kids "$ip"); do $PY "$E4/proc.py" show "init's child" "$lp"; done
    fi
    [ -z "$qp" ] && qp=$(qemu_pid "$vm")
    if [ -n "$qp" ]; then $PY "$E4/proc.py" show "qemu $vm" "$qp"; else echo "[qemu $vm] no qemu-system process with guest=$vm on the host"; fi
    cid=$(docker inspect -f '{{.Id}}' "$CTR" 2>/dev/null)
    if [ -n "$qp" ] && [ -d "/proc/$qp" ] && [ -n "$cid" ]; then
      echo "[qemu $vm] inside this container's cgroup /docker/${cid:0:12}? $($PY "$E4/proc.py" inside "$qp" "$cid")"
      echo "    pids under unified:/docker/${cid:0:12} (what cgroup.kill kills): $($PY "$E4/proc.py" subtree "/sys/fs/cgroup/unified/docker/$cid")"
      echo "    pids under devices:/docker/${cid:0:12} (what runc <= 1.1 GetAllPids lists): $($PY "$E4/proc.py" subtree "/sys/fs/cgroup/devices/docker/$cid")"
    fi
    for p in $($PY "$E4/proc.py" qemu "$vm"); do [ "$p" != "$qp" ] && echo "[qemu $vm] other pid now: $p"; done
    echo "--- virsh list --all"; virsh list --all 2>&1 | sed '/^\s*$/d'
    echo "--- virsh domstate $vm --reason: $(virsh domstate "$vm" --reason 2>&1 | sed '/^\s*$/d')"
    echo "--- host $WORK/hostrun/libvirt/qemu: $(ls "$WORK/hostrun/libvirt/qemu" 2>&1 | tr '\n' ' ')"
  } >> "$f" 2>&1
}

# Trace the container's containerd shim (parent of dumb-init) for runc invocations and kill() calls.
shim_trace_start() { # TAG
  local ip shim
  ip=$(init_pid); shim=$(ps -o ppid= -p "$ip" | tr -d ' ')
  echo "shim: $(ps -o pid=,args= -p "$shim" | sed -E 's/([0-9a-f]{12})[0-9a-f]{52}/\1/g')" > "$WORK/raw/$1.shim.hdr"
  strace -ttt -f -q -y -e trace=execve,kill,tgkill,pidfd_send_signal,write,rmdir -e signal=none -s 300 \
    -o "$WORK/raw/$1.shim.raw" -p "$shim" 2> "$WORK/raw/$1.strace.err" &
  SHIM_STRACE=$!
  sleep 1
}
shim_trace_end() { # TAG T0 OUTFILE QEMU_PID
  local i
  for i in $(seq 1 40); do kill -0 "$SHIM_STRACE" 2>/dev/null || break; sleep 0.25; done
  kill "$SHIM_STRACE" 2>/dev/null; wait "$SHIM_STRACE" 2>/dev/null
  { cat "$WORK/raw/$1.shim.hdr"; echo "# shim strace (-f, children = runc): runc invocations, kill()/pidfd_send_signal(), writes and rmdir under /sys/fs/cgroup; times relative to the docker command"
    $PY "$E4/proc.py" shim "$WORK/raw/$1.shim.raw" "$2" "$4"; } > "$3"
}

# Move a process (all threads, via cgroup.procs) into $CG_NAME at the root of every hierarchy it belongs to,
# from the host. Models systemd-machined placing QEMU in machine.slice, outside the container's cgroup.
move_cgroup() { # PID LOG [all|unified-only|all-but-unified]
  local pid=$1 log=$2 mode=${3:-all} line ctrl dir
  while IFS= read -r line; do
    ctrl=$(echo "$line" | cut -d: -f2)
    case "$mode:$ctrl" in
      unified-only:?*) continue ;;
      all-but-unified:) continue ;;
    esac
    case "$ctrl" in
      "") dir=/sys/fs/cgroup/unified ;;
      name=systemd) dir=/sys/fs/cgroup/systemd ;;
      *) dir=/sys/fs/cgroup/${ctrl%%,*} ;;
    esac
    mkdir -p "$dir/$CG_NAME"
    if [ -f "$dir/$CG_NAME/cpuset.cpus" ]; then
      cat "$dir/cpuset.cpus" > "$dir/$CG_NAME/cpuset.cpus"; cat "$dir/cpuset.mems" > "$dir/$CG_NAME/cpuset.mems"
    fi
    if echo "$pid" > "$dir/$CG_NAME/cgroup.procs"; then echo "moved $pid to $dir/$CG_NAME" >> "$log"
    else echo "FAILED to move $pid to $dir/$CG_NAME" >> "$log"; fi
  done < "/proc/$pid/cgroup"
}

rm_cgroups() {
  local d
  for d in /sys/fs/cgroup/*/"$CG_NAME"; do [ -d "$d" ] && rmdir "$d" 2>/dev/null; done
}

libvirtd_log() { # OUTFILE: warnings/errors libvirtd logged (log_level 3), from the e4_kolla_logs volume
  local mp
  mp=$(docker volume inspect -f '{{.Mountpoint}}' e4_kolla_logs 2>/dev/null) || return 0
  sed -E 's/^[0-9-]+ ([0-9:.]+)\+[0-9]+: /\1 /' "$mp/libvirt/libvirtd.log" 2>/dev/null > "$1"
}

# Kill only QEMU processes this experiment started (command line guest=e4-*), after asking libvirtd first.
kill_e4_qemu() {
  local vm p
  for vm in "$@"; do
    virsh destroy "$vm" >/dev/null 2>&1
    for p in $($PY "$E4/proc.py" qemu "$vm"); do
      grep -qa "guest=$vm" "/proc/$p/cmdline" && kill -9 "$p"
    done
  done
}

cleanup() {
  kill_e4_qemu e4-vm-a e4-vm-b e4-vm-c e4-vm-d1 e4-vm-d2
  docker rm -f "$CTR" >/dev/null 2>&1
  local v; for v in $VOLUMES; do docker volume rm "$v" >/dev/null 2>&1; done
  rm_cgroups
  if mountpoint -q "$WORK/hostrun"; then umount -R "$WORK/hostrun"; fi
  rm -rf "$WORK"
}
