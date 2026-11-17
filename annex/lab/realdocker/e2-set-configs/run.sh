#!/bin/bash
# Experiment e2: kolla_set_configs and kolla_start inside real containers (see README.md).
# Usage: ./run.sh [a b c d e f g]   (default: all tests). Needs reallab/base:ussuri (../base/build.sh) and Docker.
# Optional: KOLLA_SRC / KA_SRC = kolla and kolla-ansible ussuri-eol checkouts, to verify the vendored copies.
# Idempotent: removes the containers and volumes it created (label e2.lab=1) before and after; keeps images.
set -uo pipefail
here=$(cd "$(dirname "$0")" && pwd)
WORK=${E2_WORK:-$here/work}
OUT=$here/out
cd "$here"
. ./lib.sh

tests=${*:-a b c d e f g}

docker image inspect reallab/base:ussuri >/dev/null 2>&1 || { echo "build reallab/base:ussuri first (../base/build.sh)"; exit 1; }

# Vendored sources: verify against checkouts when given.
if [ -n "${KOLLA_SRC:-}" ] && [ -n "${KA_SRC:-}" ]; then
  while read -r sum path; do
    case $path in
      kolla-ansible/*) src=$KA_SRC/${path#kolla-ansible/} ;;
      kolla/*) src=$KOLLA_SRC/${path#kolla/} ;;
    esac
    echo "$sum  $src" | sha256sum -c --quiet - || { echo "vendored $path differs from $src"; exit 1; }
  done < <(grep -v '^#' vendor/SOURCES.sha256)
fi

trap e2_cleanup EXIT
e2_cleanup
mkdir -p "$WORK" "$VAR" "$OUT"

log "building images"
for i in render nova-compute heat-api memcached; do
  docker build --network host -q -t "e2-$i:ussuri" -f "images/$i/Dockerfile" . >/dev/null || exit 1
done

log "rendering the real kolla-ansible templates"
docker run --rm --network none -v "$here/vendor:/vendor:ro" -v "$here/render.py:/render.py:ro" -v "$VAR:/out" \
  $IMG_RENDER python3 -I /render.py /vendor /out || exit 1
cp "$VAR/variants.txt" "$OUT/variants.txt"
cp "$VAR/nova-compute/base.json" "$OUT/rendered-nova-compute-base.json"

{
  echo "date: $(date -u +%FT%TZ)"
  echo "docker: $(docker version --format 'server {{.Server.Version}}, client {{.Client.Version}}')"
  docker info --format 'cgroup v{{.CgroupVersion}} ({{.CgroupDriver}}), storage {{.Driver}}, kernel {{.KernelVersion}}, runc {{.RuncCommit.ID}}' 2>/dev/null
  echo "reallab/base:ussuri: $(docker image inspect -f '{{.Id}}' reallab/base:ussuri)"
  for i in nova-compute heat-api memcached; do echo "e2-$i:ussuri: $(docker image inspect -f '{{.Id}}' e2-$i:ussuri)"; done
  echo "--- packages in the images:"
  docker run --rm --entrypoint dpkg-query reallab/base:ussuri -W -f '${Package} ${Version}\n' \
    dumb-init sudo python3.6 ca-certificates base-files | sed 's/^/base: /'
  docker run --rm --entrypoint dpkg-query $IMG_MC -W -f '${Package} ${Version}\n' memcached | sed 's/^/memcached image: /'
  docker run --rm --entrypoint dpkg-query $IMG_RENDER -W -f '${Package} ${Version}\n' python3-jinja2 openssl \
    | sed 's/^/render image: /'
} > "$OUT/versions.txt"

for t in $tests; do
  log "test $t"
  . "tests/$t.sh"
done
log "all done"
