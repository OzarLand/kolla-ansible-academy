#!/bin/bash
# e3: the real kolla-ansible ussuri-eol kolla_docker module, run through Ansible 2.9.27, against the real daemon.
# Prerequisite: reallab/base:ussuri (../base/build.sh). Idempotent: removes the e3 containers/volumes it created
# before and after; keeps the images. Usage: ./run.sh   (E3_KEEP_WORK=1 keeps work/: rendered files, raw logs)
set -u
source "$(dirname "$0")/lib.sh"
"$E3/setup-venv.sh" || { echo "venv setup failed"; exit 1; }
for i in rabbitmq heat-api swift-rsyncd; do
  docker image inspect "e3-$i:ussuri" >/dev/null 2>&1 || KOLLA_SRC=$KOLLA_SRC "$E3/build.sh" || exit 1
done

cleanup
rm -rf "$WORK" "$OUT"; mkdir -p "$WORK/json" "$WORK/ansible" "$SRVNODE" "$OUT/ansible" "$OUT/results"
filters=(); for c in $CONTAINERS; do filters+=(--filter "container=$c"); done
docker events --format '{{json .}}' "${filters[@]}" > "$WORK/events.jsonl" &
EVPID=$!
trap 'kill $EVPID 2>/dev/null; cleanup' EXIT
{ echo "date: $(date -u +%FT%TZ)"; docker version --format 'docker server {{.Server.Version}} api {{.Server.APIVersion}} (min {{.Server.MinAPIVersion}})';
  docker info --format 'cgroup v{{.CgroupVersion}} driver {{.CgroupDriver}} storage {{.Driver}} kernel {{.KernelVersion}}';
  "$E3_VENV/bin/python" -c 'import ansible,docker,requests,urllib3,sys; c=docker.APIClient(version="auto"); print("python %s ansible %s docker-sdk %s requests %s urllib3 %s negotiated-api %s" % (sys.version.split()[0], ansible.__version__, docker.__version__, requests.__version__, urllib3.__version__, c.api_version))';
  docker run --rm --entrypoint dpkg-query e3-swift-rsyncd:ussuri -W dumb-init rsync sudo python3;
  for i in rabbitmq heat-api swift-rsyncd; do echo "image e3-$i:ussuri $(docker image inspect -f '{{.Id}}' e3-$i:ussuri)"; done
  echo "kolla-ansible $(git -C "$KOLLA_ANSIBLE_SRC" describe --tags --always) $(git -C "$KOLLA_ANSIBLE_SRC" rev-parse --short HEAD)";
  echo "kolla $(git -C "$KOLLA_SRC" rev-parse --short HEAD)"; } > "$OUT/versions.txt" 2>&1

R() { "$E3_VENV/bin/python" "$E3/render.py" "$KOLLA_ANSIBLE_SRC" "$WORK" "$@"; }
RMQ=$WORK/etc-kolla/e3_rabbitmq

# ---------------------------------------------------------------- (a) stop duration, restart paths
R rabbitmq --marker v1
ap a0-common-options common-options.yml; cp "$WORK/json/a0-common-options.json" "$OUT/a0-common-options.json"
ap a1-deploy-fresh rmq-deploy.yml;                 wait_svc_starts 1; state a1-deploy-fresh e3_rabbitmq
# Docker 29 compatibility control: the same handler without the KernelMemory shim (expected: KeyError, no action)
E3_NO_SHIM=1 ap a1x-handler-without-shim rmq-handler.yml; state a1x-handler-without-shim e3_rabbitmq
ap a2-handler-unchanged rmq-handler.yml;           wait_svc_starts 2; state a2-handler-unchanged e3_rabbitmq
ap a3-restart_container rmq-restart.yml;           wait_svc_starts 3; state a3-restart_container e3_rabbitmq
ap a4-restart-task-gt20 rmq-restart.yml -e e3_task_graceful_timeout=20
                                                   wait_svc_starts 4; state a4-restart-task-gt20 e3_rabbitmq
ap a5-service-stop rmq-stop.yml;                   state a5-service-stop e3_rabbitmq
ap a6-deploy-after-stop rmq-deploy.yml;            wait_svc_starts 5; state a6-deploy-after-stop e3_rabbitmq

# client_timeout: docker_client_timeout raised to 300 (default 120 equals the module default, so only a changed value
# shows whether it is used)
ap a7-common-options-ct300 common-options.yml -e docker_client_timeout=300
cp "$WORK/json/a7-common-options-ct300.json" "$OUT/a7-common-options-ct300.json"
ap a7-client-timeout-300 rmq-check.yml -e docker_client_timeout=300

# ---------------------------------------------------------------- (b) compare_container vs --check rc 0 / 1 / 2
check_rc b0-unchanged e3_rabbitmq
ap b0-check-rc0 rmq-check.yml
sed -i 's/v1$/v1-edited/' "$RMQ/rabbitmq.conf"
check_rc b1-content-changed e3_rabbitmq
ap b1-check-rc1 rmq-check.yml
R rabbitmq --marker v1
echo '[rabbitmq_management].' > "$RMQ/enabled_plugins"; chmod 660 "$RMQ/enabled_plugins"
"$E3_VENV/bin/python" - "$RMQ/config.json" <<'PY'
import json, sys
p = sys.argv[1]; c = json.load(open(p))
c['config_files'].append({"source": "/var/lib/kolla/config_files/enabled_plugins",
                          "dest": "/etc/rabbitmq/enabled_plugins", "owner": "rabbitmq", "perm": "0600",
                          "optional": True})
json.dump(c, open(p, 'w'), indent=4)
PY
check_rc b2-new-optional-file e3_rabbitmq
ap b2-check-rc2 rmq-check.yml
sed -i 's/v1$/v1-edited/' "$RMQ/rabbitmq-env.conf"
check_rc b3-first-entry-and-optional e3_rabbitmq
ap b3-check-rc1-before-optional rmq-check.yml
R rabbitmq --marker v1; rm -f "$RMQ/enabled_plugins"
check_rc b4-restored e3_rabbitmq
cp "$RMQ/config.json" "$OUT/rendered-rabbitmq-config.json"

# ---------------------------------------------------------------- (c) recreate_or_restart: config vs env change
R rabbitmq --marker v2
check_rc c1-before-config-v2 e3_rabbitmq
ap c1-deploy-config-changed rmq-deploy.yml;        wait_svc_starts 6; state c1-deploy-config-changed e3_rabbitmq
check_rc c1-after e3_rabbitmq
ap c2-deploy-cookie-changed rmq-deploy.yml -e e3_cookie=e3-FAKE-cookie-B
                                                   wait_svc_starts 7; state c2-deploy-cookie-changed e3_rabbitmq
check_rc c2-after e3_rabbitmq
{ echo "# stand-in rabbitmq-server log (e3_kolla_logs volume): every start and every signal received"; svclog; } \
  > "$OUT/a-c-standin.log"
docker logs e3_rabbitmq > /dev/null 2>&1

# ---------------------------------------------------------------- (d) failing one-shot with stderr
R heat-api
ap d1-heat-bootstrap-fails heat-bootstrap.yml
{ echo "# docker ps -a --filter name=e3_bootstrap_heat (after the failed task):";
  docker ps -a --filter name=e3_bootstrap_heat --format '{{.Names}} {{.Status}}'; echo "# end"; } > "$OUT/d-container-after.txt"

# successful one-shot, displayed with -v: the rabbitmq bootstrap tasks on a fresh volume (project e3_rmqv)
R rabbitmq --marker v1 --project e3_rmqv
ap d2-rmq-bootstrap-ok-verbose rmq-bootstrap.yml -v -e project_name=e3_rmqv

# ---------------------------------------------------------------- (e) start_container on a running container
mount --bind "$SRVNODE" "$SRVNODE" && mount --make-shared "$SRVNODE"
R swift-rsyncd --swift-groups account
ap e1-swift-start-new swift-start.yml;              state e1-swift-start-new e3_swift_rsyncd
rsync_modules e1-after-first-start
R swift-rsyncd --swift-groups account,container,object
check_rc e2-before e3_swift_rsyncd
ap e2-swift-start-config-changed swift-start.yml;  state e2-swift-start-config-changed e3_swift_rsyncd
rsync_modules e2-after-start_container
check_rc e2-after e3_swift_rsyncd
ap e3-swift-handler-contrast swift-handler.yml;    state e3-swift-handler-contrast e3_swift_rsyncd
rsync_modules e3-after-restart
check_rc e3-after e3_swift_rsyncd
cp "$WORK/etc-kolla/swift-rsyncd/config.json" "$OUT/rendered-swift-rsyncd-config.json"
cp "$WORK/etc-kolla/swift-rsyncd/rsyncd.conf" "$OUT/rendered-rsyncd.conf"

# ---------------------------------------------------------------- (f) bifrost reconfigure: exec into a wrong name
"$E3_VENV/bin/python" "$E3/gen_bifrost.py" "$KOLLA_ANSIBLE_SRC" "$WORK"
ap f1-bifrost-reconfigure-full bifrost-reconfigure.yml -e e3_variant=full
ap f2-bifrost-reconfigure-noguard bifrost-reconfigure.yml -e e3_variant=noguard
{ echo '$ docker exec e3-bifrost-deploy /usr/local/bin/kolla_set_configs --check'
  docker exec e3-bifrost-deploy /usr/local/bin/kolla_set_configs --check 2>&1; echo "rc=$?"; } > "$OUT/f-docker-exec.txt"

# ---------------------------------------------------------------- wrap up
sleep 1; kill $EVPID 2>/dev/null; wait $EVPID 2>/dev/null
"$E3_VENV/bin/python" "$E3/analyze.py" "$WORK" "$OUT"
cleanup; trap - EXIT
[ -n "${E3_KEEP_WORK:-}" ] || rm -rf "$WORK"
echo "done; see $OUT"
