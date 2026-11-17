# Helpers for experiment e2 (sourced by run.sh). Every object created carries the label e2.lab=1 and an e2- prefix.
E2_LABEL=e2.lab=1
IMG_NOVA=e2-nova-compute:ussuri
IMG_HEAT=e2-heat-api:ussuri
IMG_MC=e2-memcached:ussuri
IMG_RENDER=e2-render:ussuri
CCD=/var/lib/kolla/config_files          # group_vars/all.yml:7
VAR="$WORK/variants"

log() { echo "[$(date -u +%T)] $*" >&2; }

# Remove only what this experiment created (label e2.lab=1). Images are kept.
e2_cleanup() {
  local ids
  ids=$(docker ps -aq --filter label=$E2_LABEL)
  [ -n "$ids" ] && docker rm -f $ids >/dev/null
  ids=$(docker volume ls -q --filter label=$E2_LABEL)
  [ -n "$ids" ] && docker volume rm $ids >/dev/null
  rm -rf "$WORK"
}

# Kolla-Ansible host layout: directory owned config_owner_user:config_owner_group = root:root (group_vars/all.yml:20-21),
# mode 0770 (roles/nova-cell/tasks/config.yml:2-13); files 0660 (the template/copy tasks, e.g. config.yml:161-178).
# ca-certificates/ is written by the copy task with mode 0644 for files (roles/service-cert-copy/tasks/main.yml:2-12);
# the directory gets the default 0755.
fix_layout() {
  local d=$1
  chown -R root:root "$d"
  find "$d" -type d -exec chmod 0770 {} +
  find "$d" -type f -exec chmod 0660 {} +
  if [ -d "$d/ca-certificates" ]; then
    chmod 0755 "$d/ca-certificates"
    find "$d/ca-certificates" -type f -exec chmod 0644 {} +
  fi
}

cfgdir() { echo "$WORK/$1/nova-compute"; }

# setup_nova_cfg <test> <variant>: host config dir with the variant config.json and stand-in files.
setup_nova_cfg() {
  local d; d=$(cfgdir "$1")
  mkdir -p "$d"
  cp "$VAR/nova-compute/$2.json" "$d/config.json"
  printf '[DEFAULT]\n# e2 stand-in nova.conf, revision 1\n' > "$d/nova.conf"
  printf '# e2 stand-in custom policy file\n"os_compute_api:servers:index": "rule:admin_api"\n' > "$d/policy.yaml"
  printf '[credentials-default]\nusername = nova\npassword = e2-not-a-secret\n' > "$d/auth.conf"
  fix_layout "$d"
}
set_variant() { cp "$VAR/nova-compute/$2.json" "$(cfgdir "$1")/config.json"; fix_layout "$(cfgdir "$1")"; }

# run_nova <test> [docker run args...]: the nova_compute container as kolla_docker creates it
# (roles/nova-cell/defaults/main.yml:47-57 service, :283-295 volumes; group_vars/all.yml:134,157-168 common options;
# library/kolla_docker.py:717-749 host config: network_mode host). Volumes omitted on purpose: /lib/modules, /run, /dev
# (nothing that kolla_set_configs or the start scripts touch is under them), iscsi_info and the dev-mode mount.
run_nova() {
  local t=$1; shift
  local v
  for v in kolla_logs libvirtd nova_compute; do
    docker volume create --label $E2_LABEL "e2-$t-$v" >/dev/null
  done
  docker run -d --name "e2-$t-nova_compute" --label $E2_LABEL \
    --network host --ipc host --privileged --restart unless-stopped \
    -e KOLLA_CONFIG_STRATEGY="${STRATEGY:-COPY_ALWAYS}" -e LIBGUESTFS_BACKEND=direct \
    -v "$(cfgdir "$t")/:$CCD/:ro" \
    -v /etc/localtime:/etc/localtime:ro -v /etc/timezone:/etc/timezone:ro \
    -v "e2-$t-kolla_logs:/var/log/kolla/" -v "e2-$t-libvirtd:/var/lib/libvirt" -v "e2-$t-nova_compute:/var/lib/nova/" \
    "$@" $IMG_NOVA >/dev/null
}

# Number of times the stand-in service has started in this container.
starts() { docker logs "$1" 2>&1 | grep -c 'standin\[[0-9]*\] start' || true; }

# wait_starts <container> <n>: wait until the service has started n times (timeout 60 s).
wait_starts() {
  local i
  for i in $(seq 1 120); do
    [ "$(starts "$1")" -ge "$2" ] && return 0
    sleep 0.5
  done
  log "timeout waiting for start #$2 of $1"; return 1
}

# kolla_restart <container>: what kolla_docker restart_container does (library/kolla_docker.py:892-904):
# stop with graceful_timeout (10 s, see docs/10 F3), then start the same container.
kolla_restart() { docker stop -t 10 "$1" >/dev/null && docker start "$1" >/dev/null; }

# check <container> <user|root|sudo> <output file>: run kolla_set_configs --check, print the exit code.
check() {
  local c=$1 who=$2 f=$3 rc
  case $who in
    user) docker exec "$c" /usr/local/bin/kolla_set_configs --check >"$f" 2>&1; rc=$? ;;
    root) docker exec -u root "$c" /usr/local/bin/kolla_set_configs --check >"$f" 2>&1; rc=$? ;;
    sudo) docker exec "$c" sudo /usr/local/bin/kolla_set_configs --check >"$f" 2>&1; rc=$? ;;
  esac
  echo $rc
}

# Last decisive line of a --check output (the ERROR line, or the last line).
decisive() { { grep -E 'ERROR|Error|error' "$1" || tail -n 1 "$1"; } | tail -n 2 | tr '\n' ' ' | cut -c1-230; }

# stat_in <container> <path...>: owner, group, mode of paths inside the container (as root).
stat_in() { local c=$1; shift; docker exec -u root "$c" stat -c '%U:%G %a %n' "$@" 2>&1; }
