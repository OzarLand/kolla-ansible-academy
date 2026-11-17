# e6 helpers, sourced by run.sh. Everything created here is named e6_* / e6-*; nothing else is touched.
# Paths (override through the environment):
#   KOLLA_SRC          kolla checkout, tag ussuri-eol (9107c5f)       (build.sh: docker/rabbitmq/extend_start.sh)
#   KOLLA_ANSIBLE_SRC  kolla-ansible checkout, tag ussuri-eol (8a94fe9) (render.py: the role templates)
#   E6_WORK            host work dir (default /run/e6-lab): rendered config, the host directory mounted as /run,
#                      empty stand-ins for /lib/modules and /sys/kernel/config, raw strace files
E6=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
OUT=$E6/out
WORK=${E6_WORK:-/run/e6-lab}
PY="python3 -P"   # -P: never import from the script or current directory (jinja2 lives in the user site)
CONTAINERS="e6_tgtd e6_memcached e6_rabbitmq_bootstrap e6_rabbitmq e6_rmq38"
VOLUMES="e6_cinder e6_iscsi_info e6_kolla_logs e6_rabbitmq e6_rabbitmq38"
IQN=iqn.2010-10.org.openstack:volume-e6000000-0000-4000-8000-000000000001   # cinder target_prefix + volume name
VOL=volume-e6000000-0000-4000-8000-000000000001
RMQ38_IMAGE=mirror.gcr.io/library/rabbitmq:3.8

now() { date +%s.%N; }
dt() { python3 -c "import sys; print('%.2f' % (float(sys.argv[2]) - float(sys.argv[1])))" "$1" "$2"; }
note() { echo "== $*"; }
hdr() { echo; echo "### $*"; }

cleanup() {
  local c v
  for c in $CONTAINERS; do docker rm -f "$c" >/dev/null 2>&1 || true; done
  for v in $VOLUMES; do docker volume rm "$v" >/dev/null 2>&1 || true; done
}

# The host /run stand-in (same technique as e4): kolla mounts "/run/:/run/:shared" into tgtd (and cinder-volume),
# which is how tgt-admin in another container reaches tgtd's control socket /run/tgtd/socket.0. This sandbox's / is a
# private mount, so Docker refuses ":shared" on the real /run; a dedicated directory made its own shared mount
# point is used instead (making / shared would change propagation for every concurrent experiment).
setup_work() {
  mkdir -p "$WORK/hostrun" "$WORK/lib-modules" "$WORK/configfs" "$WORK/raw"
  if ! mountpoint -q "$WORK/hostrun"; then mount --bind "$WORK/hostrun" "$WORK/hostrun"; fi
  mount --make-shared "$WORK/hostrun"
  rm -rf "${WORK:?}/hostrun/tgtd" "${WORK:?}/raw/"*
}

teardown_work() {
  if mountpoint -q "$WORK/hostrun"; then umount "$WORK/hostrun"; fi
}

# ---------------------------------------------------------------- docker run with kolla_docker's parameters
# Common to every kolla container (library/kolla_docker.py:717-775, group_vars/all.yml:43,134,157-167):
# network_mode host, restart_policy unless-stopped, KOLLA_CONFIG_STRATEGY=COPY_ALWAYS, KOLLA_SERVICE_NAME = the
# container name with '_' -> '-', the config dir read-only, /etc/localtime and (Debian hosts) /etc/timezone.
KOLLA_COMMON=(--network host --restart unless-stopped -e KOLLA_CONFIG_STRATEGY=COPY_ALWAYS
              -v /etc/localtime:/etc/localtime:ro -v /etc/timezone:/etc/timezone:ro)

# tgtd: roles/iscsi/defaults/main.yml:12-20 (ipc_mode host, privileged) and :52-63 (tgtd_default_volumes).
# Lab substitutions: $WORK/hostrun for /run (setup_work), empty dirs for /lib/modules and /sys/kernel/config (this
# sandbox has neither), e6_ prefixes on the named volumes cinder, iscsi_info and kolla_logs.
run_tgtd() {
  docker run -d --name e6_tgtd "${KOLLA_COMMON[@]}" --ipc host --privileged -e KOLLA_SERVICE_NAME=e6-tgtd \
    -v "$WORK/cfg/tgtd/:/var/lib/kolla/config_files/:ro" \
    -v e6_kolla_logs:/var/log/kolla/ \
    -v /dev/:/dev/ \
    -v "$WORK/hostrun/:/run/:shared" \
    -v /sys/fs/cgroup:/sys/fs/cgroup:ro \
    -v "$WORK/lib-modules:/lib/modules:ro" \
    -v "$WORK/configfs:/configfs" \
    -v e6_cinder:/var/lib/cinder \
    -v e6_iscsi_info:/etc/iscsi \
    e6-tgtd:ussuri >/dev/null
}

# Wait until tgtd answers on its control socket (max 30 s).
wait_tgtd() {
  local i
  for i in $(seq 1 150); do
    docker exec e6_tgtd tgtadm --lld iscsi --op show --mode sys >/dev/null 2>&1 && return 0
    sleep 0.2
  done
  echo "tgtd did not answer within 30 s" >&2; return 1
}

# The command cinder's TgtAdm runs to list targets (cinder/privsep/targets/tgt.py:50-52), condensed to the lines
# that identify targets and LUNs.
show_targets() {
  local out rc
  out=$(docker exec e6_tgtd tgtadm --lld iscsi --op show --mode target 2>&1); rc=$?
  echo "\$ tgtadm --lld iscsi --op show --mode target   (rc $rc, $(printf '%s' "$out" | grep -c '^Target') target(s))"
  if [ -z "$out" ]; then echo "(empty output: no targets)"; else
    printf '%s\n' "$out" | grep -E '^Target|^ +LUN: |Backing store path|State:'; fi
}

# A cinder-volume stand-in: the e6-tgtd image (same bionic tgt package that kolla's cinder-volume image installs,
# kolla docker/cinder/cinder-volume/Dockerfile.j2:33) with the two mounts that matter here: the shared /run (tgtd's
# control socket) and the cinder volume (persistence files). It runs the tgt-admin calls cinder's TgtAdm makes.
cinder_standin() {
  docker run --rm --network host --ipc host --privileged --entrypoint bash \
    -v "$WORK/hostrun/:/run/:shared" -v e6_cinder:/var/lib/cinder e6-tgtd:ussuri -c "$1"
}

# memcached: roles/memcached/defaults/main.yml:2-9,36-40 (no data volume, no privileges).
run_memcached() {
  docker run -d --name e6_memcached "${KOLLA_COMMON[@]}" -e KOLLA_SERVICE_NAME=e6-memcached \
    -v "$WORK/cfg/memcached/:/var/lib/kolla/config_files/:ro" e6-memcached:ussuri >/dev/null
}

# rabbitmq: roles/rabbitmq/defaults/main.yml:2-17 (environment / bootstrap_environment), :62-67 (volumes);
# tasks/bootstrap.yml:10-26 (bootstrap: detach False, labels BOOTSTRAP, restart_policy no). project_name rabbitmq.
rmq_volumes() {
  echo -v "$WORK/cfg/rabbitmq/:/var/lib/kolla/config_files/:ro" -v e6_rabbitmq:/var/lib/rabbitmq/ \
       -v e6_kolla_logs:/var/log/kolla/
}
run_rabbitmq_bootstrap() { # cookie
  # shellcheck disable=SC2046
  docker run --name e6_rabbitmq_bootstrap "${KOLLA_COMMON[@]}" --restart no --label BOOTSTRAP= \
    -e KOLLA_BOOTSTRAP= -e RABBITMQ_CLUSTER_COOKIE="$1" -e RABBITMQ_LOG_DIR=/var/log/kolla/rabbitmq \
    -e KOLLA_SERVICE_NAME=e6-rabbitmq-bootstrap $(rmq_volumes) e6-rabbitmq:ussuri
}
run_rabbitmq() { # cookie
  # shellcheck disable=SC2046
  docker run -d --name e6_rabbitmq "${KOLLA_COMMON[@]}" \
    -e RABBITMQ_CLUSTER_COOKIE="$1" -e RABBITMQ_LOG_DIR=/var/log/kolla/rabbitmq \
    -e KOLLA_SERVICE_NAME=e6-rabbitmq $(rmq_volumes) e6-rabbitmq:ussuri >/dev/null
}
# The handler's wait (roles/rabbitmq/tasks/restart_services.yml:16-21)
wait_rabbitmq() { docker exec e6_rabbitmq rabbitmqctl wait /var/lib/rabbitmq/mnesia/rabbitmq.pid; }

# ---------------------------------------------------------------- signal tracing from the host
# trace_start <container> <raw file>: strace every process of the container (dumb-init and its descendants, all
# threads) from the host, recording signals, kill() calls and exits. strace -p seizes without stopping or signalling.
trace_start() {
  local init pids p args=()
  init=$(docker inspect -f '{{.State.Pid}}' "$1")
  pids=$init
  for p in $(descendants "$init"); do pids="$pids $p"; done
  for p in $pids; do args+=(-p "$p"); done
  strace -ttt -f -q -e trace=kill,tgkill,exit_group,rt_sigreturn -e signal=all -o "$2" "${args[@]}" 2>/dev/null &
  STRACE_PID=$!
  TRACED="$pids"
  sleep 1.5
}
descendants() {
  local c
  for c in $(cat /proc/"$1"/task/*/children 2>/dev/null); do echo "$c"; descendants "$c"; done
}
trace_finish() {
  local i
  for i in $(seq 1 50); do kill -0 "$STRACE_PID" 2>/dev/null || break; sleep 0.2; done
  kill -INT "$STRACE_PID" 2>/dev/null; wait "$STRACE_PID" 2>/dev/null || true
}
# trace_summary <raw> <t0>: the signal lines, times relative to t0, one "+++ killed" line per process (not thread)
trace_summary() {
  python3 - "$1" "$2" "$TRACED" <<'PY'
import re, sys
raw, t0, procs = sys.argv[1], float(sys.argv[2]), set(sys.argv[3].split())
killed_threads = 0
for line in open(raw, errors='replace'):
    m = re.match(r'^(\d+)\s+(\d+\.\d+) (.*)$', line.rstrip())
    if not m:
        continue
    pid, t, what = m.group(1), float(m.group(2)), m.group(3)
    if 'SIGURG' in what:
        continue
    if what.startswith('+++ killed by') and pid not in procs:
        killed_threads += 1
        continue
    if what.startswith(('kill(', 'tgkill(', '--- SIG', '+++', 'exit_group(', 'rt_sigreturn')):
        print('%+8.3f s  pid %-7s %s' % (t - t0, pid, what[:150]))
if killed_threads:
    print('(+ %d further threads of the traced processes: +++ killed by SIGKILL, not listed)' % killed_threads)
PY
}

# decode_sig <host pid>: SigBlk/SigIgn/SigCgt of a process, as signal names
decode_sig() {
  local k v
  for k in SigBlk SigIgn SigCgt; do
    v=$(awk -v k="$k:" '$1==k {print $2}' /proc/"$1"/status)
    python3 -c "import signal,sys; v=int(sys.argv[2],16); n={s.value:s.name for s in signal.Signals}; print('%s %s %s' % (sys.argv[1], sys.argv[2], [n.get(i, 'SIG%d' % i) for i in range(1,65) if v>>(i-1)&1]))" "$k" "$v"
  done
}

# memcached client (plain text protocol) from the host
mc() { $PY "$E6/mc.py" 127.0.0.1 18611 "$@"; }
