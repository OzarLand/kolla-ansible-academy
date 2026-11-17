#!/bin/bash
# Build reallab/base:ussuri: ubuntu:18.04 + bionic dumb-init 1.2.1 + the unmodified kolla ussuri-eol base scripts.
# KOLLA_SRC must point at a kolla checkout of tag ussuri-eol (commit 9107c5f).
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
for f in set_configs.py start.sh copy_cacerts.sh httpd_setup.sh sudoers; do
  cp "$KOLLA_SRC/docker/base/$f" "$here/$f"
done
docker build --network host -t reallab/base:ussuri "$here"
