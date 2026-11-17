#!/bin/bash
# Build the e5 images FROM reallab/base:ussuri (must exist: see ../base/build.sh). Idempotent (Docker layer cache).
# KOLLA_SRC must point at a kolla checkout of tag ussuri-eol (commit 9107c5f): the real image scripts are copied from
# it into build contexts assembled under $E5_WORK/build (default ./work/build) and never edited.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
: "${KOLLA_SRC:?set KOLLA_SRC to a kolla ussuri-eol checkout}"
WORK=${E5_WORK:-$here/work}
docker image inspect reallab/base:ussuri >/dev/null
ctx=$WORK/build
rm -rf "$ctx" && mkdir -p "$ctx"
for img in openvswitch-base openvswitch-db-server openvswitch-vswitchd peer; do
  cp -r "$here/images/$img" "$ctx/$img" && mkdir -p "$ctx/$img/kolla"
done
d=$KOLLA_SRC/docker/openvswitch
cp "$d/openvswitch-base/extend_start.sh" "$ctx/openvswitch-base/kolla/openvswitch-base-extend_start.sh"
cp "$d/openvswitch-db-server/extend_start.sh" "$ctx/openvswitch-db-server/kolla/openvswitch-db-server-extend_start.sh"
cp "$d/openvswitch-db-server/ovs_ensure_configured.sh" "$ctx/openvswitch-db-server/kolla/ovs_ensure_configured.sh"
cp "$d/openvswitch-vswitchd/extend_start.sh" "$ctx/openvswitch-vswitchd/kolla/openvswitch-vswitchd-extend_start.sh"
build() { docker build --network host -q -t "$1" "$ctx/$2" >/dev/null && echo "built $1"; }
build e5-openvswitch-base:ussuri openvswitch-base
build e5-openvswitch-db-server:ussuri openvswitch-db-server
build e5-openvswitch-vswitchd:ussuri openvswitch-vswitchd
build e5-peer:ussuri peer
