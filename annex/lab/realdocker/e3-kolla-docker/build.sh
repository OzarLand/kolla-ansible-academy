#!/bin/bash
# Build the e3 images FROM reallab/base:ussuri. The kolla files are copied unmodified from KOLLA_SRC (kolla ussuri-eol).
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
: "${KOLLA_SRC:?KOLLA_SRC must point at a kolla checkout of tag ussuri-eol (9107c5f)}"
cp "$KOLLA_SRC/docker/rabbitmq/extend_start.sh"          "$here/images/rabbitmq/kolla-rabbitmq-extend_start.sh"
cp "$KOLLA_SRC/docker/heat/heat-base/extend_start.sh"    "$here/images/heat-api/kolla-heat-base-extend_start.sh"
cp "$KOLLA_SRC/docker/heat/heat-api/extend_start.sh"     "$here/images/heat-api/kolla-heat-api-extend_start.sh"
cp "$KOLLA_SRC/docker/swift/swift-base/swift_sudoers"    "$here/images/swift-rsyncd/kolla-swift_sudoers"
cp "$KOLLA_SRC/docker/swift/swift-rsyncd/extend_start.sh" "$here/images/swift-rsyncd/kolla-swift-rsyncd-extend_start.sh"
for i in rabbitmq heat-api swift-rsyncd; do
  docker build -q --network host -t "e3-$i:ussuri" "$here/images/$i"
done
rm -f "$here"/images/*/kolla-*   # the copies are only build context
