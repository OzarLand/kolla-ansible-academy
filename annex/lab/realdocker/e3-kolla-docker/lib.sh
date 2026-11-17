# e3 helpers, sourced by run.sh.
# Paths (override through the environment):
#   E3_VENV           Ansible 2.9.27 + docker SDK 4.4.4 venv with requests 2.23.0 / urllib3 1.25.8 (setup-venv.sh)
#   KOLLA_ANSIBLE_SRC kolla-ansible checkout, tag ussuri-eol
#   KOLLA_SRC         kolla checkout, tag ussuri-eol (9107c5f)
E3=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
SCRATCH=${SCRATCH:-/tmp/claude-0/-home-user-kolla-ansible-day2/0f94a3d8-faad-5ead-a2f1-d2af8be54fca/scratchpad}
E3_VENV=${E3_VENV:-$SCRATCH/e3/venv}
KOLLA_ANSIBLE_SRC=${KOLLA_ANSIBLE_SRC:-$SCRATCH/src/kolla-ansible}
KOLLA_SRC=${KOLLA_SRC:-$SCRATCH/src/kolla}
WORK=${E3_WORK:-$E3/work}
OUT=$E3/out
PB=$E3/playbooks
CONTAINERS="e3_rabbitmq e3_rabbitmq_bootstrap e3_rmqv_bootstrap e3_bootstrap_heat e3_swift_rsyncd"
VOLUMES="e3_rabbitmq e3_rmqv e3_kolla_logs"
SRVNODE=$WORK/srv-node

export ANSIBLE_LIBRARY=$KOLLA_ANSIBLE_SRC/ansible/library
export ANSIBLE_CALLBACK_WHITELIST=profile_tasks,e3_record ANSIBLE_CALLBACK_PLUGINS=$E3/plugins
export ANSIBLE_NOCOLOR=1 ANSIBLE_RETRY_FILES_ENABLED=False ANSIBLE_DEPRECATION_WARNINGS=False
export ANSIBLE_TRANSFORM_INVALID_GROUP_CHARS=ignore ANSIBLE_LOCALHOST_WARNING=False ANSIBLE_HOST_KEY_CHECKING=False
export PYTHONWARNINGS=ignore PYTHONDONTWRITEBYTECODE=1

mark() { echo "$(date +%s%N) $*" >> "$WORK/markers.txt"; }

# ap STEP PLAYBOOK [ansible-playbook args]: run one step; raw output in work/, trimmed copy in out/ansible/.
ap() {
  local step=$1 pb=$2; shift 2
  echo "== $step ($pb $*)"
  mark BEGIN "$step"
  E3_RECORD=$WORK/json/$step.jsonl "$E3_VENV/bin/ansible-playbook" -i "$PB/inventory.ini" "$PB/$pb" \
    -e "kolla_ansible_src=$KOLLA_ANSIBLE_SRC e3_work=$WORK e3_json=$WORK/json e3_step=$step" \
    -e "ansible_python_interpreter=$E3_VENV/bin/python" "$@" > "$WORK/ansible/$step.txt" 2>&1
  local rc=$?
  mark END "$step"
  echo "$step rc=$rc" >> "$OUT/ansible-rc.txt"
  # trim: drop the python 3.8 / cryptography deprecation noise and the profile_tasks date banners' blank lines
  grep -v -E 'CryptographyDeprecationWarning|from cryptography.exceptions|^\s*$' "$WORK/ansible/$step.txt" \
    > "$OUT/ansible/$step.txt"
  "$E3_VENV/bin/python" "$E3/trim.py" "$WORK/json/$step.jsonl" > "$OUT/results/$step.json" 2>/dev/null || true
  [ -s "$OUT/results/$step.json" ] || rm -f "$OUT/results/$step.json"
  return 0
}

# state LABEL CONTAINER: one line with the container id, start time, restart count and status.
state() {
  printf '%-34s %s\n' "$1" "$(docker inspect -f '{{.Name}} id={{printf "%.12s" .Id}} started={{.State.StartedAt}} status={{.State.Status}} restarts={{.RestartCount}}' "$2" 2>&1)" >> "$OUT/state.txt"
}

# check_rc LABEL CONTAINER: the exact command compare_container runs (kolla_docker.py:244,545-549), by hand.
check_rc() {
  local o rc
  o=$(docker exec -u root "$2" /usr/local/bin/kolla_set_configs --check 2>&1); rc=$?
  printf '%-34s rc=%s  last line: %s\n' "$1" "$rc" "$(echo "$o" | tail -1)" >> "$OUT/check-rc.txt"
}

# svclog: the stand-in rabbitmq-server log (on the e3_kolla_logs volume).
svclog() { cat "$(docker volume inspect -f '{{.Mountpoint}}' e3_kolla_logs)/e3_rabbitmq/standin.log"; }

wait_svc_starts() { # wait until the stand-in log holds N start lines (max 20 s)
  local n=$1 i
  for i in $(seq 1 40); do
    [ "$(svclog 2>/dev/null | grep -c ' start ')" -ge "$n" ] && return 0; sleep 0.5
  done
  echo "timeout waiting for start #$n" >&2
}

rsync_modules() { # LABEL: list the modules the running rsync daemon serves
  local i o
  for i in $(seq 1 20); do
    o=$(docker exec e3_swift_rsyncd rsync rsync://127.0.0.1:18373/ 2>&1) && break; sleep 0.5
  done
  printf '%-34s %s\n' "$1" "$(echo $o)" >> "$OUT/e-rsync-modules.txt"
}

cleanup() {
  local c v
  for c in $CONTAINERS; do docker rm -f "$c" >/dev/null 2>&1; done
  for v in $VOLUMES; do docker volume rm "$v" >/dev/null 2>&1; done
  if mountpoint -q "$SRVNODE"; then umount "$SRVNODE"; fi
}
