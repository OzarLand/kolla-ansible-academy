#!/bin/bash
# Fetch the upstream runc / containerd code that decides which processes "kill all" reaches, and write the decisive
# lines to out/upstream-excerpts.txt. Needs raw.githubusercontent.com (through the normal proxy).
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
get() { curl -sSf -o "$tmp/$1" "https://raw.githubusercontent.com/$2"; }
get rc10-init opencontainers/runc/v1.0.0-rc10/libcontainer/init_linux.go
get rc10-fs opencontainers/runc/v1.0.0-rc10/libcontainer/cgroups/fs/apply_raw.go
get rc10-state opencontainers/runc/v1.0.0-rc10/libcontainer/state_linux.go
get rc10-utils opencontainers/runc/v1.0.0-rc10/libcontainer/cgroups/utils.go
get v1115-fs opencontainers/runc/v1.1.15/libcontainer/cgroups/fs/fs.go
get v1115-init opencontainers/runc/v1.1.15/libcontainer/init_linux.go
get v152-init opencontainers/runc/v1.5.2/libcontainer/init_linux.go
get v152-ctr opencontainers/runc/v1.5.2/libcontainer/container_linux.go
get ctrd1213 containerd/containerd/v1.2.13/runtime/v2/runc/service.go
ex() { # LABEL FILE FROM TO
  echo "== $1 ($3-$4)"; sed -n "$3,$4p" "$tmp/$2" | sed 's/^/    /'; }
{
  echo "# Upstream code on the 'kill all processes of a host-PID container' path, fetched $(date -u +%Y-%m-%d)"
  ex "containerd v1.2.13 runtime/v2/runc/service.go: init exit -> KillAll when the bundle has no PID namespace" \
     ctrd1213 651 662
  ex "containerd v1.2.13 runtime/v2/runc/service.go: shouldKillAllOnExit" ctrd1213 677 693
  ex "runc v1.0.0-rc10 libcontainer/state_linux.go: destroy (runc delete)" rc10-state 40 46
  ex "runc v1.0.0-rc10 libcontainer/init_linux.go: signalAllProcesses" rc10-init 475 498
  ex "runc v1.0.0-rc10 libcontainer/cgroups/fs/apply_raw.go: GetAllPids walks the devices hierarchy" rc10-fs 301 304
  ex "runc v1.0.0-rc10 libcontainer/cgroups/utils.go: RemovePaths error" rc10-utils 484 487
  echo "== runc v1.1.15 libcontainer/init_linux.go: mentions of cgroup.kill: $(grep -c 'cgroup.kill' "$tmp/v1115-init")"
  ex "runc v1.1.15 libcontainer/cgroups/fs/fs.go: GetAllPids walks the devices hierarchy" v1115-fs 225 227
  ex "runc v1.5.2 libcontainer/container_linux.go: SIGKILL of a shared-PID-namespace container" v152-ctr 407 409
  ex "runc v1.5.2 libcontainer/init_linux.go: signalAllProcesses uses cgroup.kill (v2 or hybrid) first" v152-init 684 703
} > "$here/out/upstream-excerpts.txt"
echo "wrote $here/out/upstream-excerpts.txt"
