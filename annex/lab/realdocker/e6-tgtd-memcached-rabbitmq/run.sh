#!/bin/bash
# e6: tgtd target persistence, memcached contents and the RabbitMQ Erlang cookie across a kolla-style restart or
# recreate, on real Docker. Reproducible and idempotent: every run starts from fresh e6_* containers and volumes and
# removes them at the end (images are kept). Needs root (bind mount for the shared /run stand-in, strace on the host).
#   KOLLA_SRC=<kolla ussuri-eol> KOLLA_ANSIBLE_SRC=<kolla-ansible ussuri-eol> ./run.sh
set -uo pipefail
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"
: "${KOLLA_SRC:?set KOLLA_SRC}" "${KOLLA_ANSIBLE_SRC:?set KOLLA_ANSIBLE_SRC}"

note "build images and render the kolla-ansible templates"
"$E6/build.sh" >/dev/null || exit 1
cleanup
setup_work
$PY "$E6/render.py" "$KOLLA_ANSIBLE_SRC" "$WORK/cfg" "$(hostname)" >/dev/null || exit 1
rm -rf "${OUT:?}"; mkdir -p "$OUT"
{
  echo "date (UTC): $(date -u +%FT%TZ)"
  echo "docker: $(docker version --format 'server {{.Server.Version}} client {{.Client.Version}}'); $(docker info --format 'cgroup v{{.CgroupVersion}} {{.CgroupDriver}}, storage {{.Driver}}, kernel {{.KernelVersion}}')"
  echo "runc: $(docker info --format '{{.DefaultRuntime}}') $(runc --version 2>/dev/null | head -1)"
  echo "strace (host): $(strace -V | head -1)"
  for i in tgtd memcached rabbitmq; do
    echo "e6-$i:ussuri $(docker image inspect -f '{{.Id}}' e6-$i:ussuri | cut -c1-19): $(docker run --rm --network none --user 0 --entrypoint sh e6-$i:ussuri -c \
      'dpkg-query -W -f "\${Package} \${Version}; " dumb-init tgt memcached rabbitmq-server erlang-base 2>/dev/null')"
  done
  echo "rendered config (kolla-ansible templates): $WORK/cfg, copied to out/cfg/"
} > "$OUT/versions.txt"
cp -r "$WORK/cfg" "$OUT/cfg"

########################################################################################################## (a) tgtd
note "(a) tgtd"
{
  hdr "image: packages and the kolla sed line (docker/tgtd/Dockerfile.j2:19)"
  docker run --rm --network none --entrypoint bash e6-tgtd:ussuri -c '
    echo "\$ head -3 /etc/tgt/targets.conf"; head -3 /etc/tgt/targets.conf
    echo "\$ grep -c -a /etc/tgt /usr/sbin/tgtd   (does the daemon binary know any config path?)"; grep -c -a /etc/tgt /usr/sbin/tgtd
    echo "\$ grep -n \"my \$configfile\" /usr/sbin/tgt-admin"; grep -n "my \$configfile" /usr/sbin/tgt-admin
    echo "\$ grep Exec /lib/systemd/system/tgt.service   (what loads targets on a host: systemd, not tgtd)"
    grep Exec /lib/systemd/system/tgt.service'
} > "$OUT/a0-image.txt" 2>&1

docker volume create e6_cinder >/dev/null; docker volume create e6_iscsi_info >/dev/null
docker volume create e6_kolla_logs >/dev/null
run_tgtd && wait_tgtd
{
  hdr "docker run (kolla parameters, see lib.sh run_tgtd)"
  docker inspect -f 'NetworkMode={{.HostConfig.NetworkMode}} IpcMode={{.HostConfig.IpcMode}} Privileged={{.HostConfig.Privileged}} Restart={{.HostConfig.RestartPolicy.Name}}' e6_tgtd
  docker inspect -f '{{range .Mounts}}{{.Destination}} <- {{if .Name}}volume {{.Name}}{{else}}{{.Source}}{{end}} ({{.Mode}}{{if .Propagation}},{{.Propagation}}{{end}}){{"\n"}}{{end}}' e6_tgtd
  hdr "docker logs (start)"; docker logs e6_tgtd 2>&1 | grep -v '^INFO:__main__' | tail -14
  hdr "processes (container view)"; docker exec e6_tgtd ps -eo pid,ppid,user,args
  hdr "signal dispositions of tgtd (host /proc)"
  init=$(docker inspect -f '{{.State.Pid}}' e6_tgtd); decode_sig "$(descendants "$init" | head -1)"
  hdr "portal (host network)"; docker exec e6_tgtd ss -ltn 'sport = :18601'
  hdr "targets after the first start"; show_targets
} > "$OUT/a1-start.txt" 2>&1

# (a2) create a volume export the way cinder's TgtAdm does: persistence file in volumes_dir (VOLUME_CONF,
# cinder/volume/targets/tgt.py:38-46,142-154) + "tgt-admin --update <iqn>" (:173, privsep/targets/tgt.py:32-37).
# Lab substitution: a 16 MB file instead of an LVM logical volume as backing store.
{
  hdr "cinder stand-in: write the persistence file, then tgt-admin --update <iqn>"
  cinder_standin "set -e
    mkdir -p /var/lib/cinder/volumes /var/lib/cinder/e6-backing
    truncate -s 16M /var/lib/cinder/e6-backing/$VOL
    printf '\n<target %s>\n    backing-store %s\n    driver iscsi\n    \n    \n    write-cache on\n</target>\n' \
      $IQN /var/lib/cinder/e6-backing/$VOL > /var/lib/cinder/volumes/$VOL
    echo \"\\\$ cat /var/lib/cinder/volumes/$VOL\"; cat /var/lib/cinder/volumes/$VOL
    echo \"\\\$ tgt-admin --update $IQN\"; tgt-admin --update $IQN; echo \"rc=\$?\""
  hdr "targets"; show_targets
} > "$OUT/a2-create.txt" 2>&1

# (a3) restart as kolla_docker.restart_container does it (library/kolla_docker.py:892-905): stop with the
# 10 s timeout (F3), then start. Traced from the host.
{
  hdr "restart 1: docker stop -t 10 + docker start (= kolla_docker restart_container)"
  trace_start e6_tgtd "$WORK/raw/a3.strace"
  t0=$(now); docker stop -t 10 e6_tgtd >/dev/null; t1=$(now)
  trace_finish
  echo "docker stop -t 10 took $(dt "$t0" "$t1") s; $(docker inspect -f 'exit code {{.State.ExitCode}}' e6_tgtd)"
  echo "# strace (host pids; traced: $TRACED = dumb-init, tgtd), times relative to the docker stop call"
  trace_summary "$WORK/raw/a3.strace" "$t0"
  docker start e6_tgtd >/dev/null && wait_tgtd
  hdr "after the start"; show_targets
  echo "\$ ls /var/lib/cinder/volumes  (persistence file still on the cinder volume)"
  docker exec e6_tgtd ls /var/lib/cinder/volumes
  echo "\$ head -1 /etc/tgt/targets.conf"; docker exec e6_tgtd head -1 /etc/tgt/targets.conf
  echo "# tgtd log lines of the new start (no config file is read):"
  docker logs --since "$(date -u -d @"${t1%.*}" +%FT%TZ)" e6_tgtd 2>&1 | grep '^tgtd:' | head -8
} > "$OUT/a3-restart-stop-start.txt" 2>&1

# (a4) restore with "tgt-admin -e" (the tgt.service ExecStartPost of a host install)
{
  hdr "restore: tgt-admin -e (reads /etc/tgt/targets.conf and its includes)"
  docker exec e6_tgtd tgt-admin -e -v > "$WORK/raw/a4.out" 2>&1; rc=$?
  head -12 "$WORK/raw/a4.out"; echo "rc=$rc"
  show_targets
} > "$OUT/a4-restore-execute.txt" 2>&1

# (a5) docker restart -t 10, then restore with "tgt-admin --update ALL" (the tgt.service ExecReload)
{
  hdr "restart 2: docker restart -t 10"
  trace_start e6_tgtd "$WORK/raw/a5.strace"
  t0=$(now); docker restart -t 10 e6_tgtd >/dev/null; t1=$(now)
  trace_finish
  echo "docker restart -t 10 took $(dt "$t0" "$t1") s"
  trace_summary "$WORK/raw/a5.strace" "$t0" | grep -v 'rt_sigreturn'
  wait_tgtd; show_targets
  hdr "restore: tgt-admin --update ALL"
  docker exec e6_tgtd tgt-admin --update ALL; echo "rc=$?"
  show_targets
} > "$OUT/a5-restart-update-all.txt" 2>&1

# (a6) docker restart -t 10, then restore with cinder's own call from the cinder stand-in
{
  hdr "restart 3: docker restart -t 10"
  t0=$(now); docker restart -t 10 e6_tgtd >/dev/null; t1=$(now)
  echo "docker restart -t 10 took $(dt "$t0" "$t1") s"
  wait_tgtd; show_targets
  hdr "restore: cinder stand-in runs tgt-admin --update <iqn> (what TgtAdm.create_iscsi_target runs, also on"
  echo "### ensure_export at cinder-volume start: cinder/volume/targets/iscsi.py:245-259)"
  cinder_standin "tgt-admin --update $IQN; echo rc=\$?"
  show_targets
} > "$OUT/a6-restart-cinder-update.txt" 2>&1

# (a7) recreate (what kolla_docker does when a parameter or the image changes: stop, remove, create)
{
  hdr "recreate: docker stop -t 10, docker rm, docker run (same parameters, same volumes)"
  t0=$(now); docker stop -t 10 e6_tgtd >/dev/null; t1=$(now)
  echo "docker stop -t 10 took $(dt "$t0" "$t1") s; $(docker inspect -f 'exit code {{.State.ExitCode}}' e6_tgtd)"
  docker rm e6_tgtd >/dev/null && run_tgtd && wait_tgtd
  show_targets
  echo "\$ ls /var/lib/cinder/volumes"; docker exec e6_tgtd ls /var/lib/cinder/volumes
} > "$OUT/a7-recreate.txt" 2>&1
docker rm -f e6_tgtd >/dev/null

##################################################################################################### (b) memcached
note "(b) memcached"
run_memcached
for i in $(seq 1 50); do mc stats >/dev/null 2>&1 && break; sleep 0.2; done
{
  hdr "docker logs (start)"; docker logs e6_memcached 2>&1 | grep -v '^INFO:__main__' | tail -4
  hdr "processes (container view)"; docker exec e6_memcached ps -eo pid,ppid,user,args
  docker inspect -f 'Mounts: {{range .Mounts}}{{.Destination}} {{end}}' e6_memcached
  hdr "set and read three keys"
  mc set token1=abc session1=def cache1=ghi
  mc get token1 session1 cache1
  mc stats
  hdr "restart: docker restart -t 10"
  trace_start e6_memcached "$WORK/raw/b.strace"
  t0=$(now); docker restart -t 10 e6_memcached >/dev/null; t1=$(now)
  trace_finish
  echo "docker restart -t 10 took $(dt "$t0" "$t1") s"
  echo "# strace (host pids; traced: $TRACED = dumb-init, memcached), times relative to the docker restart call"
  trace_summary "$WORK/raw/b.strace" "$t0"
  echo "# docker logs line printed by memcached's signal handler:"
  docker logs e6_memcached 2>&1 | grep -n 'Signal handled'
  for i in $(seq 1 50); do mc stats >/dev/null 2>&1 && break; sleep 0.2; done
  hdr "after the restart"
  mc get token1 session1 cache1
  mc stats
} > "$OUT/b-memcached.txt" 2>&1
docker rm -f e6_memcached >/dev/null

###################################################################################################### (c) rabbitmq
note "(c) rabbitmq"
{
  hdr "which installed file mentions RABBITMQ_CLUSTER_COOKIE or a cookie variable? (image e6-rabbitmq, 3.6.10)"
  docker run --rm --network none --user 0 --entrypoint bash e6-rabbitmq:ussuri -c '
    echo "\$ grep -rl RABBITMQ_CLUSTER_COOKIE /usr/lib/rabbitmq /usr/lib/erlang /usr/sbin /etc /usr/local/bin"
    grep -rl RABBITMQ_CLUSTER_COOKIE /usr/lib/rabbitmq /usr/lib/erlang /usr/sbin /etc /usr/local/bin
    echo "\$ grep -rn -i cookie <the rabbitmq shell scripts>"
    grep -n -i cookie /usr/lib/rabbitmq/bin/rabbitmq-script-wrapper /usr/lib/rabbitmq/lib/rabbitmq_server-*/sbin/*
    echo "\$ grep -rln -i -E \"ERLANG_COOKIE|setcookie\" /usr/lib/rabbitmq /usr/sbin /etc/rabbitmq   (text and .beam)"
    grep -rln -i -E "ERLANG_COOKIE|setcookie" /usr/lib/rabbitmq /usr/sbin /etc/rabbitmq; echo "(rc $?: 1 = no match)"'
} > "$OUT/c0-grep.txt" 2>&1

docker volume create e6_kolla_logs >/dev/null
{
  hdr "kolla creates the volume, then runs the bootstrap container only because the volume is new"
  echo "(roles/rabbitmq/tasks/bootstrap.yml:2-8,26)"
  docker volume create e6_rabbitmq
  hdr "bootstrap one-shot: KOLLA_BOOTSTRAP= RABBITMQ_CLUSTER_COOKIE=cookieA"
  run_rabbitmq_bootstrap cookieA > "$WORK/raw/c1-bootstrap.log" 2>&1
  echo "exit code $(docker inspect -f '{{.State.ExitCode}}' e6_rabbitmq_bootstrap)"
  echo "# docker logs, from the sourced kolla_extend_start on (xtrace):"
  sed -n '/kolla_extend_start/,$p' "$WORK/raw/c1-bootstrap.log"
  hdr "volume content after the bootstrap"
  docker run --rm --network none --user 0 --entrypoint sh -v e6_rabbitmq:/v:ro e6-rabbitmq:ussuri -c \
    'ls -la /v; printf "content of .erlang.cookie: "; cat /v/.erlang.cookie'
} > "$OUT/c1-bootstrap.txt" 2>&1

# cookie_state <label>: what the running node uses
cookie_state() {
  hdr "$1"
  docker exec e6_rabbitmq sh -c 'printf "file /var/lib/rabbitmq/.erlang.cookie: %s (mode %s, owner %s)\n" \
    "$(cat /var/lib/rabbitmq/.erlang.cookie)" "$(stat -c %a /var/lib/rabbitmq/.erlang.cookie)" \
    "$(stat -c %U /var/lib/rabbitmq/.erlang.cookie)"
    b=$(pgrep -x beam.smp); printf "beam.smp pid %s, its environment: " "$b"
    tr "\0" "\n" < /proc/$b/environ | grep -E "^(RABBITMQ_CLUSTER_COOKIE|HOME)=" | tr "\n" " "; echo'
  echo "\$ rabbitmqctl eval 'erlang:get_cookie().'"; docker exec e6_rabbitmq rabbitmqctl eval 'erlang:get_cookie().'
  echo "# last 'cookie hash' line of the broker log (base64 of the md5 of the cookie; see c5 for the values):"
  docker exec e6_rabbitmq sh -c 'grep -h -i "cookie hash" /var/log/kolla/rabbitmq/*.log | tail -1' 2>/dev/null || true
}
{
  hdr "service container: RABBITMQ_CLUSTER_COOKIE=cookieA"
  run_rabbitmq cookieA; wait_rabbitmq
  docker exec e6_rabbitmq ps -eo pid,ppid,user,args | cut -c1-120
  cookie_state "cookie in use (service created with cookieA)"
  docker exec e6_rabbitmq rabbitmqctl list_users
} > "$OUT/c2-service-cookieA.txt" 2>&1

{
  hdr "cookie change: kolla_docker sees a different environment (check_container_differs) and recreates the"
  echo "### container: stop -t 10, remove, create (library/kolla_docker.py:781-803). The bootstrap task is skipped:"
  echo "### the volume exists (bootstrap.yml:26)."
  t0=$(now); docker stop -t 10 e6_rabbitmq >/dev/null; t1=$(now)
  echo "docker stop -t 10 took $(dt "$t0" "$t1") s; $(docker inspect -f 'exit code {{.State.ExitCode}}' e6_rabbitmq)"
  docker rm e6_rabbitmq >/dev/null
  run_rabbitmq cookieB; wait_rabbitmq
  docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' e6_rabbitmq | grep COOKIE
  cookie_state "cookie in use (service recreated with cookieB)"
} > "$OUT/c3-recreate-cookieB.txt" 2>&1

# (c4) a client holding the NEW cookie, as kolla_toolbox does after the change (roles/common/tasks/config.yml:242-250,
# templates/kolla-toolbox.json.j2:1-8). Stand-in: rabbitmqctl of the broker image run with another HOME (the real
# rabbitmqctl, called past the Debian wrapper, which would reset HOME to /var/lib/rabbitmq).
client() { # cookie
  docker exec e6_rabbitmq sh -c "rm -rf /tmp/e6-client && mkdir /tmp/e6-client && printf %s $1 > /tmp/e6-client/.erlang.cookie \
    && chmod 400 /tmp/e6-client/.erlang.cookie && cd /tmp && HOME=/tmp/e6-client /usr/lib/rabbitmq/bin/rabbitmqctl -n rabbit@$(hostname) status; echo rc=\$?"
}
{
  hdr "client with cookieB (new value, what kolla_toolbox holds after the change)"
  client cookieB 2>&1 | grep -E 'Status of|Error|Authentication|cookie hash|rc=|epmd reports'
  hdr "client with cookieA (control)"
  client cookieA 2>&1 | grep -E 'Status of|Error|Authentication|running_applications|rc='
} > "$OUT/c4-client-cookie.txt" 2>&1
docker rm -f e6_rabbitmq e6_rabbitmq_bootstrap >/dev/null

# (c5) cross-check on RabbitMQ 3.8 (the Ussuri major version): the docker-library image, NOT a kolla image, started
# past its entrypoint (which handles only RABBITMQ_ERLANG_COOKIE) with a cookie file A and RABBITMQ_CLUSTER_COOKIE=B.
{
  hdr "RabbitMQ 3.8 cross-check ($RMQ38_IMAGE, docker-library image, entrypoint bypassed)"
  docker image inspect "$RMQ38_IMAGE" >/dev/null 2>&1 || docker pull -q "$RMQ38_IMAGE" >/dev/null
  docker image inspect -f 'image {{.Id}}' "$RMQ38_IMAGE" | cut -c1-25
  docker run --rm --network none --entrypoint sh "$RMQ38_IMAGE" -c '
    echo "\$ grep -rl RABBITMQ_CLUSTER_COOKIE /opt/rabbitmq /usr/local/bin /etc/rabbitmq /usr/local/lib/erlang"
    grep -rl RABBITMQ_CLUSTER_COOKIE /opt/rabbitmq /usr/local/bin /etc/rabbitmq /usr/local/lib/erlang; echo "(rc $?: 1 = no match)"'
  docker volume create e6_rabbitmq38 >/dev/null
  docker run -d --name e6_rmq38 --network none --user rabbitmq --entrypoint sh -e RABBITMQ_CLUSTER_COOKIE=cookieB \
    -v e6_rabbitmq38:/var/lib/rabbitmq "$RMQ38_IMAGE" -c \
    'echo cookieA > /var/lib/rabbitmq/.erlang.cookie && chmod 400 /var/lib/rabbitmq/.erlang.cookie && exec rabbitmq-server' >/dev/null
  for i in $(seq 1 120); do docker logs e6_rmq38 2>&1 | grep -q 'Server startup complete' && break; sleep 0.5; done
  docker logs e6_rmq38 2>&1 | grep -E 'Starting RabbitMQ|cookie hash' | sed 's/^ *//'
  python3 -c 'import base64, hashlib; print("; ".join("base64(md5(%s)) = %s" % (c, base64.b64encode(hashlib.md5(c.encode()).digest()).decode()) for c in ("cookieA", "cookieB")))'
  docker exec e6_rmq38 sh -c 'printf "beam.smp environment: "; tr "\0" "\n" < /proc/$(pgrep -x beam.smp)/environ | grep COOKIE'
  echo "\$ rabbitmqctl eval 'erlang:get_cookie().'"; docker exec --user rabbitmq e6_rmq38 rabbitmqctl eval 'erlang:get_cookie().'
} > "$OUT/c5-rabbitmq38.txt" 2>&1

cleanup
teardown_work
note "done; outputs in $OUT"
