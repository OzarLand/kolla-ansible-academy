#!/bin/bash
# Build e4-nova-libvirt:ussuri FROM reallab/base:ussuri (../base/build.sh) with the unmodified kolla ussuri-eol
# docker/nova/nova-libvirt/extend_start.sh. KOLLA_SRC must point at a kolla checkout of tag ussuri-eol (9107c5f).
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
: "${KOLLA_SRC:?set KOLLA_SRC to a kolla ussuri-eol checkout (commit 9107c5f)}"
cp "$KOLLA_SRC/docker/nova/nova-libvirt/extend_start.sh" "$here/images/nova-libvirt/extend_start.sh"
docker build --network host -t e4-nova-libvirt:ussuri "$here/images/nova-libvirt"
