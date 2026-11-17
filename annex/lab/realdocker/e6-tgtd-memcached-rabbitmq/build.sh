#!/bin/bash
# Build the three e6 images FROM reallab/base:ussuri (built by ../base/build.sh).
# KOLLA_SRC: kolla checkout at tag ussuri-eol (9107c5f); only docker/rabbitmq/extend_start.sh is taken from it.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
: "${KOLLA_SRC:?set KOLLA_SRC to a kolla ussuri-eol checkout}"
docker image inspect reallab/base:ussuri >/dev/null
cp "$KOLLA_SRC/docker/rabbitmq/extend_start.sh" "$here/images/rabbitmq/extend_start.sh"
for i in tgtd memcached rabbitmq; do
  docker build --network host -q -t "e6-$i:ussuri" "$here/images/$i"
done
