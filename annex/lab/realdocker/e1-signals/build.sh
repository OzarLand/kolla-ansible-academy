#!/bin/bash
# Build the e1 images FROM reallab/base:ussuri (must exist: see ../base/build.sh). Idempotent (Docker layer cache).
# KOLLA_SRC must point at a kolla checkout of tag ussuri-eol (commit 9107c5f): the real start scripts are copied
# from it into the build contexts, which are assembled under work/build/ and never edited by hand.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
: "${KOLLA_SRC:?set KOLLA_SRC to a kolla ussuri-eol checkout}"
docker image inspect reallab/base:ussuri >/dev/null
ctx=$here/work/build
rm -rf "$ctx" && mkdir -p "$ctx"
for img in svc ovsdb ovsvswitchd haproxy mariadb mariadb-upstreamtrap; do
  cp -r "$here/images/$img" "$ctx/$img" && mkdir -p "$ctx/$img/kolla"
done
for img in ovsdb ovsvswitchd; do cp "$here/images/svc/e1-sigsvc" "$ctx/$img/"; done
d=$KOLLA_SRC/docker
cp "$d/neutron/neutron-base/extend_start.sh" "$ctx/svc/kolla/neutron-base-extend_start.sh"
for img in ovsdb ovsvswitchd; do
  cp "$d/openvswitch/openvswitch-base/extend_start.sh" "$ctx/$img/kolla/openvswitch-base-extend_start.sh"
done
cp "$d/openvswitch/openvswitch-db-server/extend_start.sh" "$ctx/ovsdb/kolla/openvswitch-db-server-extend_start.sh"
cp "$d/openvswitch/openvswitch-vswitchd/extend_start.sh" "$ctx/ovsvswitchd/kolla/openvswitch-vswitchd-extend_start.sh"
for f in mariadb_sudoers extend_start.sh security_reset.expect; do cp "$d/mariadb/mariadb/$f" "$ctx/mariadb/kolla/"; done
build() { docker build --network host -q -t "$1" "$ctx/$2" >/dev/null && echo "built $1"; }
build e1-svc:ussuri svc
build e1-ovsdb:ussuri ovsdb
build e1-ovsvswitchd:ussuri ovsvswitchd
build e1-haproxy:ussuri haproxy
build e1-mariadb:ussuri mariadb
build e1-mariadb-upstreamtrap:ussuri mariadb-upstreamtrap
