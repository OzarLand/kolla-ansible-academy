#!/bin/bash
# docker stop on a kolla-style container whose command is a bash wrapper that does not exec its service.
set -u
here=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$here/logs" && chmod 777 "$here/logs" && rm -f "$here/logs/svc.log"
docker rm -f smoke >/dev/null 2>&1
docker run -d --name smoke -e KOLLA_CONFIG_STRATEGY=COPY_ALWAYS \
  -v "$here/cfg:/var/lib/kolla/config_files:ro" -v "$here/logs:/var/log/kolla" reallab/base:ussuri >/dev/null
sleep 3
docker exec smoke ps -eo pid,ppid,pgid,sid,cmd
t0=$(date +%s.%N); docker stop -t 10 smoke >/dev/null; t1=$(date +%s.%N)
echo "docker stop -t 10 took $(python3 -c "print(round($t1-$t0,2))") s; exit code $(docker inspect -f '{{.State.ExitCode}}' smoke)"
echo "--- service log:"; cat "$here/logs/svc.log"
docker rm smoke >/dev/null
