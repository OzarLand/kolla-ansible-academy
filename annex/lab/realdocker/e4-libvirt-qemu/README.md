# e4: do QEMU processes survive a `nova_libvirt` restart or recreate? (Q1 mechanism)

## Purpose

Study question Q1 (`docs/10-technical-findings-and-open-questions.md:116`) asks whether running VMs survive a
`nova_libvirt` restart or recreate. The study gives a mechanism hypothesis (`docs/05-nova-deep-dive.md:233-252`):
under `pid_mode: host` the runtime kills what is still in the container's cgroup when its init exits, so survival
depends on where libvirt put QEMU. This experiment runs a real libvirtd and a real QEMU (TCG) in a container that
mirrors Kolla-Ansible ussuri-eol's `nova_libvirt` on a real Docker daemon. It records where QEMU lands in the cgroup
tree, who kills it and how, and whether libvirtd re-attaches after a restart or recreate. The lab is not a production
compute: see Caveats before using any result.

## Versions and environment

All values are from `out/environment.txt` unless stated otherwise.

| Item | Lab | Ussuri era (for comparison, not tested) |
|---|---|---|
| Kernel | 6.18.44 (sandbox VM), cgroup v1 with the hybrid `cgroup2` mount at `/sys/fs/cgroup/unified` | 4.15 / 5.4 (Ubuntu 18.04 / 20.04), 4.18 (CentOS 8); no `cgroup.kill` (added in Linux 5.14) |
| Docker | 29.9.2, containerd v2.4.2, runc 1.5.2, cgroupfs driver, overlayfs | 19.03 / 20.10 with runc 1.0.0-rc8 to 1.1.x |
| Image | `e4-nova-libvirt:ussuri` FROM `reallab/base:ussuri` (ubuntu 18.04.6, dumb-init 1.2.1-1, unmodified kolla base scripts) | kolla `ubuntu-source-nova-libvirt:ussuri` |
| libvirt | 4.0.0-1ubuntu8.21 (bionic) | **6.0.0 from the Ubuntu Cloud Archive `bionic-updates/ussuri`** (kolla `docker/base/sources.list.ubuntu:13`) |
| QEMU | 1:2.11+dfsg-1ubuntu7.42 (bionic), TCG only (no `/dev/kvm` in the sandbox) | **4.2 from the Ubuntu Cloud Archive**, KVM |
| systemd-machined / D-Bus | none: host PID 1 is `process_api`, no `/run/dbus/system_bus_socket` | normally present on a systemd host |

The Ussuri Ubuntu image took libvirt 6.0 and QEMU 4.2 from UCA; UCA is not reachable from this lab, so the bionic
versions were used. libvirt 4.0 has no cgroup v2 support; libvirt 6.0 has a v2 backend whose behaviour on a hybrid
host was not tested here (see Caveats).

## Method

### Image (`build.sh`, `images/nova-libvirt/Dockerfile`)

FROM `reallab/base:ussuri`, following kolla `docker/nova/nova-libvirt/Dockerfile.j2`: the kolla users (`qemu` 42427,
`nova` 42436 in groups `kolla,qemu`, `libvirt` 42473) created before any package, as `docker/base/Dockerfile.j2` and
`macros.j2` `configure_user` do; `apt-get install --no-install-recommends` of the subset of the Ussuri deb list that
is on the libvirt/QEMU path (`libvirt-clients libvirt-daemon-system qemu-system-x86 qemu-kvm qemu-block-extra
sasl2-bin libsasl2-modules-gssapi-mit ebtables dmidecode`, plus `libsasl2-modules` for the DIGEST-MD5 mechanism and
`kmod` for `lsmod`); left out: ceph, openvswitch, xen-utils, trousers, ovmf, pm-utils. The default network XML is
removed and the **unmodified** kolla `docker/nova/nova-libvirt/extend_start.sh` is installed as `kolla_extend_start`.

### Container (`lib.sh` `run_ctr`)

The parameters `kolla_docker` gives `nova_libvirt` (kolla-ansible ussuri-eol, 8a94fe9):

- `--pid host --privileged` (`roles/nova-cell/defaults/main.yml:2-11`),
  `--net host` (`library/kolla_docker.py:717-720`), `--restart unless-stopped`, `KOLLA_CONFIG_STRATEGY=COPY_ALWAYS` (`group_vars/all.yml:43,134,157-167`),
  `KOLLA_SERVICE_NAME=nova-libvirt` (`kolla_docker.py:751-755`); no command, so the image runs
  `dumb-init --single-child -- kolla_start`, which execs `/usr/sbin/libvirtd --listen` (rendered `config.json`).
- The volumes of `nova_libvirt_default_volumes` (`defaults/main.yml:237-250`): config dir `:ro`, `/etc/localtime:ro`,
  `/etc/timezone:ro`, `/lib/modules:ro`, `/run/:/run/:shared`, `/dev:/dev`, `/sys/fs/cgroup:/sys/fs/cgroup`,
  `kolla_logs`, `libvirtd:/var/lib/libvirt`, `nova_compute:/var/lib/nova/`, `nova_libvirt_qemu:/etc/libvirt/qemu`
  (volume names prefixed `e4_`).
- Lab substitutions: the sandbox's `/` is a private mount and Docker refuses `/run/:/run/:shared` ("path /run is
  mounted on / but it is not a shared mount"), so a dedicated host directory `/run/e4-lab/hostrun`, made its own
  mount point with shared propagation, is mounted as the container's `/run`. It persists across container restart
  and recreate like the host `/run`; the only content of the real host `/run` that matters here, the D-Bus socket,
  does not exist on this host anyway. The host has no `/lib/modules`, so an empty directory is mounted there.
- Config: the real kolla-ansible templates `nova-libvirt.json.j2`, `libvirtd.conf.j2`, `qemu.conf.j2`, `sasl.conf.j2`,
  `auth.conf.j2` rendered with jinja2 (`render.py`; result in `out/config/`). Role defaults, except
  `nova_libvirt_port` 18409 (lab port range), `migration_interface_address` 127.0.0.1, a lab-only SASL password, and
  `qemu_max_files`/`qemu_max_processes` lowered to 19999/64272: the sandbox has no `CAP_SYS_RESOURCE` in its bounding
  set (`CapBnd 000001fffeffffff`, bit 24 clear) and its hard limits (nofile 20000, nproc 64272) are below the
  defaults, so with 32768/131072 libvirt failed to start QEMU ("cannot limit number of subprocesses to 131072:
  Operation not permitted"); libvirt sets RLIMIT_NOFILE to `max_files + 1`.

### Guest (`domain.xml.in`)

A persistent domain (`virsh define` + `virsh start`, as nova-compute does), `type='qemu'` (TCG), 64 MiB, 1 vCPU, no
disk, no NIC, no display. SeaBIOS finds no boot device and the QEMU process stays alive.

### Steps (`run.sh`) and observables

Each test starts from empty volumes, an empty host `/run` stand-in and a fresh container, then starts one guest.

- **a** `docker restart -t 10` = `kolla_docker` `restart_container` (stop with timeout 10, then start;
  `kolla_docker.py:892-904`).
- **b** recreate = `recreate_or_restart_container` (`kolla_docker.py:781-803`): `docker stop -t 10`, `docker rm -f`
  (`remove_container` uses `force=True`, `:635-649`), `docker run` with the same parameters.
- **c** QEMU moved from the host into `/e4-machine` before the stop, by writing its PID to `cgroup.procs` (all threads
  move): **c1** in every hierarchy (the model of systemd-machined placing QEMU in `machine.slice`), restart then
  recreate; **c2** in the unified (v2) hierarchy only, restart then recreate; **c3** in every hierarchy except the
  unified one, restart.
- **d** control without `--pid host`: **d1** as libvirt placed QEMU; **d2** after the c1 move.

A failed restart is retried as the `Restart nova-libvirt container` handler does (`retries: 5`, Ansible's default
5 s delay, `roles/nova-cell/handlers/main.yml:87-109`): `docker stop -t 10` + `docker start`.

Recorded per step: QEMU PID, parent, `/proc/<pid>/cgroup` grouped by path, mount and PID namespace, root overlay
(`snapshots*.txt`); per hierarchy whether QEMU is inside the container's `/docker/<id>`, the PIDs under
`unified:/docker/<id>` and `devices:/docker/<id>`; `virsh list --all`, `virsh domstate --reason`, the libvirt state
files in the host `/run` stand-in; a `strace -f` of the container's containerd shim during the stop: runc invocations,
signals, writes and `rmdir` under `/sys/fs/cgroup` (`shim-*.txt`); `docker` command rc, wall time and output
(`commands.txt`); libvirtd's log (`libvirtd*.log`, sandbox capability-probe noise removed); a monitor check after
each step: `virsh suspend` + `virsh resume`, which only work if libvirtd holds a live QEMU monitor connection.
`upstream.sh` fetches the runc/containerd code on the kill path into `out/upstream-excerpts.txt`.

Run: `KOLLA_SRC=<kolla ussuri-eol> ./build.sh`, then `KOLLA_ANSIBLE_SRC=<kolla-ansible ussuri-eol> ./run.sh [a b c d]`
as root (strace and jinja2 required). It creates only `e4_*` containers/volumes, `e4-machine` cgroups and
`/run/e4-lab`, kills only QEMU processes whose command line holds `guest=e4-vm-*`, and removes all of it at the end
(images kept), including containerd leftovers of its own containers (see c2).

## Results

`out/summary.txt`, abridged (last run; the full suite ran four times with this logic, runs 2-5, with the same outcome
at every step; c2's recreate step was added from run 3):

```
a    docker restart -t 10           qemu pid 13570   GONE              virsh domstate: shut off (crashed)
b    recreate (stop, rm -f, run)    qemu pid 14758   GONE              virsh domstate: shut off (crashed)
c1   docker restart -t 10           qemu pid 15990   ALIVE (same pid)  virsh domstate: running (booted)   monitor: suspend+resume OK
c1   recreate (stop, rm -f, run)    qemu pid 15990   ALIVE (same pid)  virsh domstate: running (unpaused) monitor: suspend+resume OK
c2   docker restart -t 10           qemu pid 17886   ALIVE (same pid)  virsh domstate: Error ... container 680b3a0ca948 is not running
c2   recreate (stop, rm -f, run)    qemu pid 17886   ALIVE (same pid)  virsh domstate: running (booted)   monitor: suspend+resume OK
c3   docker restart -t 10           qemu pid 21054   GONE              virsh domstate: shut off (crashed)
d1   docker restart -t 10           qemu pid 22321   GONE              virsh domstate: shut off (crashed)
d2   docker restart -t 10           qemu pid 23502   GONE              virsh domstate: shut off (crashed)
```

("unpaused" is the reason left by the monitor check's suspend + resume after the c1 restart.)

### Where libvirt puts QEMU (no machined)

libvirtd tries D-Bus first and falls back to writing cgroups itself (`out/a/libvirtd.log`):

```
error : virDBusGetSystemBus:109 : internal error: Unable to get DBus system bus connection: Failed to connect to socket /var/run/dbus/system_bus_socket: No such file or directory
```

QEMU's placement before any stop (`out/a/snapshots.txt:9-16`):

```
[qemu e4-vm-a] pid 13570 comm=qemu-system-x86 ppid=13323(containerd-shim) uid=42436 nspid=13570
    cgroup /docker/9468e5de1e14                                 <- name=systemd,pids,unified(v2)
    cgroup /machine/qemu-1-e4-vm-a.libvirt-qemu                 <- blkio,freezer,devices,memory
    cgroup /machine/qemu-1-e4-vm-a.libvirt-qemu/emulator        <- cpuset,cpuacct,cpu
    pids under unified:/docker/9468e5de1e14 (what cgroup.kill kills): 13348 13360 13570
    pids under devices:/docker/9468e5de1e14 (what runc <= 1.1 GetAllPids lists): 13348 13360
```

So the answer to "in the container's cgroup or elsewhere?" is **both**. libvirt 4.0 creates its `/machine` partition
at the root of the seven v1 controller hierarchies it manages, outside the container's `/docker/<id>`. It leaves
QEMU in the container's cgroup in the three hierarchies it does not manage: `name=systemd`, `pids` and the hybrid
unified (v2) hierarchy. Through `--pid host` and the rw `/sys/fs/cgroup` bind mount it writes the host tree directly.
QEMU shares libvirtd's mount namespace (same `mnt:[...]`), so libvirt's per-domain mount namespace was not used. QEMU
runs as `nova` (uid 42436, `qemu.conf` `user = "nova"`). Its parent is the containerd shim, a child subreaper:
dumb-init is not one under `--pid host`. Without `--pid host` (d) the parent is dumb-init, PID 1 of the container's
PID namespace (`out/d/snapshots-d1.txt:14`: `ppid=22072(dumb-init) ... nspid=22321,123`). The libvirt runtime
state is on the host `/run` stand-in: `--- host /run/e4-lab/hostrun/libvirt/qemu: e4-vm-a.pid e4-vm-a.xml`, because
the image's `/var/run` is a symlink to `/run` (`out/environment.txt`: `/var/run -> /run`).

### (a) restart and (b) recreate: QEMU is killed by runc's `cgroup.kill`

`out/a/shim-a-restart.txt` (times from the `docker restart` command):

```
  +0.058 s  pid 13716  pidfd_send_signal(9<anon_inode:[pidfd]>, SIGTERM, NULL, 0) = 0
  +0.087 s  pid 13723  execve runc kill --all 9468e5de1e14 9
  +0.112 s  pid 13723  write(9</sys/fs/cgroup/unified/docker/9468e5de1e14/cgroup.kill>, "1") = 1
  +0.126 s  pid 13729  execve runc delete 9468e5de1e14
  +0.155 s  pid 13729  write(9</sys/fs/cgroup/unified/docker/9468e5de1e14/cgroup.kill>, "1") = 1
```

SIGTERM goes to dumb-init (container init), which forwards it to libvirtd. libvirtd and dumb-init exit within about
30 ms, and the shim then runs `runc kill --all <id> 9` because the container shares the host PID namespace (the same
`runc kill --all` that e1 recorded for `--pid host` containers, `../e1-signals/out/g3/shim.txt`). runc 1.5.2
implements it, and again `runc delete`, by writing `1` to `cgroup.kill` of the container's **unified** cgroup
(`out/upstream-excerpts.txt`, runc v1.5.2 `init_linux.go:684-697`: "Either cgroup v2 or hybrid"). The kernel kills
every process in that v2 subtree; QEMU is one of them. No `kill()` of the QEMU PID is issued: the kill is a cgroup
write. `docker restart -t 10` returned in 0.25 s (`out/a/commands.txt`), so the 10 s timer never mattered. On start,
the new libvirtd tried to re-attach and found no process (`out/a/libvirtd.log`):

```
error : qemuMonitorOpenUnix:385 : failed to connect to monitor socket: No such process
```

and reports the domain `shut off (crashed)`; the status XML is gone from the host `/run` stand-in
(`out/a/snapshots.txt:31-37`, against `:22` before the restart). (b) is identical: QEMU is already gone after `docker stop` (`out/b/commands.txt`:
`b-recreate: after docker stop, before rm: qemu 14758 GONE, container status exited exit=0`), with the same shim
trace (`out/b/shim-b-recreate.txt`).

### (c1) QEMU outside the container's cgroup in every hierarchy: survives restart and recreate, libvirtd re-attaches

After the move (`out/c/snapshots-c1.txt:31-34`) QEMU is in `/e4-machine` in all ten hierarchies. The restart and
the recreate run the same `runc kill --all` + `cgroup.kill` (`out/c/shim-c1-restart.txt`, `shim-c1-recreate.txt`),
but QEMU is outside the killed subtree:

```
[qemu e4-vm-c1] pid 15990 comm=qemu-system-x86 ppid=1(process_api) uid=42436 nspid=15990     (after restart, :51)
--- virsh domstate e4-vm-c1 --reason: running (booted)                                        (:61)
c1-recreate: after docker stop, before rm: qemu 15990 ALIVE, container status exited exit=0 (commands.txt)
$ docker rm -f e4_nova_libvirt -> rc=0, 0.05 s
--- virsh domstate e4-vm-c1 --reason: running (unpaused)                                      (after recreate, :81)
$ docker exec e4_nova_libvirt virsh -c qemu:///system destroy e4-vm-c1 -> rc=0, 1.28 s, output: Domain e4-vm-c1 destroyed
c1: after virsh destroy through the new libvirtd: qemu 15990 GONE
```

The same PID survives both operations. The new libvirtd, in a new container on the same volumes and host `/run`
stand-in, re-attaches: `virsh list` shows it running, suspend/resume through the monitor work, and it can destroy
the guest. When the old shim exits, QEMU is re-parented to host PID 1. After the recreate, QEMU still runs in the
**old** container's mount namespace and root filesystem (`out/c/mountns-c1.txt`):

```
c1 after recreate: qemu mnt ns mnt:[4026532264], new libvirtd 16863 mnt ns mnt:[4026532268]
[qemu] pid 15990 root mount: overlay upperdir=.../snapshots/1405/fs (ABSENT on the host)
[new libvirtd] pid 16863 root mount: overlay upperdir=.../snapshots/1407/fs (exists on the host)
```

The old container's writable layer has been deleted from the host, but QEMU's namespace still holds the old overlay
mount.

### (c2) QEMU out of the unified hierarchy only: survives, but the container cannot be restarted

QEMU stays in the container's `name=systemd` and `pids` cgroups, which is libvirt 4.0's own placement minus the
unified hierarchy (`out/c/snapshots-c2.txt`). `cgroup.kill` misses it, but `runc delete` can no longer remove the
container's cgroup (`out/c/shim-c2-restart.txt`):

```
  +0.155 s  pid 18087  write(9</sys/fs/cgroup/unified/docker/680b3a0ca948/cgroup.kill>, "1") = 1
  +2.223 s  pid 18087  runc stderr: unable to destroy container: unable to remove container's cgroup: Failed to remove paths: map[name=systemd:/sys/fs/cgroup/systemd/docker/680b3a0ca948...
```

`out/c/commands.txt`: the restart and all 5 handler-style retries fail, and the container stays exited, so libvirtd
is down while QEMU keeps running unmanaged:

```
$ docker restart -t 10 e4_nova_libvirt -> rc=1, 4.40 s, output: Error response from daemon: Cannot restart container e4_nova_libvirt: could not delete stale containerd task object: failed to delete task: ... unable to remove container's cgroup: Failed to remove paths: map[name=systemd:... pids:...]
$ docker start e4_nova_libvirt -> rc=1, 2.18 s, output: Error response from daemon: could not delete stale containerd task object: ...   (x5)
c2-restart: after the handler-style retries: container exited
```

A recreate then works: `docker rm -f` returns 0, the new container starts, and its libvirtd re-attaches
(`summary.txt`: `running (booted)`, suspend+resume OK; QEMU again in the old mount namespace, `out/c/mountns-c2.txt`).
But it leaks: `c2 after recreate (old container removed by docker rm -f): containerd task 680b3a0ca948: STOPPED;
shim process: 17640; old cgroup dirs: pids systemd`. The containerd task, container record and shim of the removed
container remain, and QEMU stays in the removed container's `name=systemd` and `pids` cgroups, until QEMU exits.
`run.sh` deletes these leftovers of its own containers with `ctr` at cleanup.

### (c3) QEMU out of every hierarchy except the unified one: killed

`out/c/snapshots-c3.txt:13`: `... unified=IN`, and after the restart `pid 21054: GONE`, `shut off (crashed)`. With
c2, this isolates the decisive hierarchy for runc 1.5.2: membership in the container's unified cgroup alone decides
death; the v1 hierarchies (devices, freezer, pids, ...) do not.

### (d) without `--pid host`: killed whatever the cgroup placement

d1: QEMU is in the container's PID namespace (`nspid=22321,123`). The shim issues **no** `runc kill --all` and runc
writes no `cgroup.kill` (`out/d/shim-d1-restart.txt`: only `runc kill <id> 15` and `runc delete`). QEMU is
nevertheless gone after the restart. d2: after the move out of every hierarchy (`out/d/snapshots-d2.txt:15`, all
`out`) it is also killed. QEMU dies when the namespace's init (dumb-init) exits: the kernel kills every process of a
PID namespace whose init terminates (pid_namespaces(7)). By elimination, nothing in the traced runtime path killed it.

## What this settles in the study

| Study statement | Verdict | Evidence |
|---|---|---|
| `docs/05-nova-deep-dive.md:233-236`: "Under `pid_mode: host` the runtime kills whatever is still in the container's cgroup when its init exits. Whether VMs survive therefore depends on QEMU's cgroup membership at stop time, not on the 10 s timer." | **Confirmed, refined** (lab stack). "The container's cgroup" is one specific hierarchy: runc ≥ 1.2 kills by `cgroup.kill` on the unified (v2) cgroup (hybrid or v2 host, kernel ≥ 5.14); runc ≤ 1.1 enumerated the `devices` hierarchy (source only, not run). libvirtd exits on SIGTERM in about 30 ms; the timer is irrelevant | a, b, c1-c3; `out/upstream-excerpts.txt` |
| `docs/05-nova-deep-dive.md:237-241`: "Without machined, libvirtd writes the cgroups directly. … QEMU then survives the stop of the libvirtd container." | **Refuted for this lab stack** (libvirt 4.0, runc 1.5.2, hybrid cgroup v1). Direct placement covers 7 of 10 hierarchies; QEMU stays in the container's `name=systemd`, `pids` and unified cgroups and is killed on restart and recreate. On a Ussuri-era stack (runc ≤ 1.1, kernel without `cgroup.kill`) the same placement would not be signalled (QEMU is not under `devices:/docker/<id>`), but it would block the container's cgroup removal as in c2: [HYPOTHESIS], from the observed placement and the runc rc10 source | a, b, c2; `out/a/snapshots.txt:9-16` |
| `docs/05-nova-deep-dive.md:241-244`: "On start, libvirtd re-attaches to running domains using the status XML under `/var/run/libvirt/qemu` (on the host `/run`) and the monitor sockets under `/var/lib/libvirt/qemu` (the `libvirtd` volume)" | **Confirmed** whenever QEMU survived, after a restart and after a recreate (c1, c2) | `summary.txt`; `out/c/commands.txt` (destroy through the new libvirtd) |
| `docs/05-nova-deep-dive.md:193-194` and `annex/kolla-images.md:559-560`: "The image's `/var/run` is a symlink to `/run`" [HYPOTHESIS] | **Confirmed** for the Ubuntu 18.04 base: `/var/run -> /run`, libvirt's `e4-vm-a.xml`/`.pid` land on the host-side `/run` mount (CentOS images not checked) | `out/environment.txt`; `out/a/snapshots.txt:22` |
| `docs/05-nova-deep-dive.md:250-252`: "Surviving QEMU processes keep the old container's mount namespace. After a recreate with a new image, they keep running the old QEMU binary" | **Confirmed** (mount namespace and root overlay of the removed container, its upper layer deleted on the host). The recreate used the same image, so "old binary" is shown through the old root, not through a version difference | `out/c/mountns-c1.txt`, `mountns-c2.txt` |
| `docs/05-nova-deep-dive.md:257`: "on cgroup v2 hosts, or wherever QEMU is still in the container's cgroup at stop, QEMU processes could be killed" | **Confirmed** for "still in the container's cgroup" on a cgroup v1 (hybrid) host: the unified membership is enough (a, b, c3). A pure cgroup v2 host was not available | a, b, c3 |
| `docs/05-nova-deep-dive.md:205-208` (handler `retries: 5`: "when guests running, nova_libvirt will raise error even though it is removed") and kolla-ansible `tools/cleanup-containers:6-9` ("Docker will not be able to stop the nova_libvirt container with those running") | **Consistent with c2, refined**: QEMU alive inside the container's `pids`/`name=systemd` cgroup makes `runc delete` fail ("Failed to remove paths"); in this Docker version the restart and all 5 retries fail and leave libvirtd down, while a recreate succeeds but leaks the containerd task, shim and cgroups. The exact Docker 19.03 error is not reproduced | c2 |
| `docs/05-nova-deep-dive.md:216-221` (both signals go to dumb-init; libvirtd SIGKILLed only if still running after 10 s) | **Confirmed**: SIGTERM to the container init via `pidfd_send_signal`, then `runc kill --all` about 30 ms later; no SIGKILL at 10 s | `out/a/shim-a-restart.txt` |
| `docs/08-operational-risk-matrix.md:19` (R1): "libvirtd restart: … VMs normally keep running [NEEDS-LAB]" | **Not generally true; depends on the host stack.** Here VMs were killed on every restart and recreate unless QEMU was moved out of the container's unified cgroup. It holds where QEMU is outside the cgroup the runtime kills by (machined placement, c1) | a, b, c1 |
| `annex/kolla-images.md:545-546` (§7): "The runtime killing the container's cgroup when its init exits, and how that applies under `pid_mode: host`" | **Settled for this stack**: on init exit the containerd shim runs `runc kill --all … 9` only for a host-PID container (containerd v1.2.13 `shouldKillAllOnExit` has the same rule); runc 1.5.2 uses `cgroup.kill`. With a private PID namespace no kill-all runs; the PID namespace teardown kills | a, d1; `out/upstream-excerpts.txt` |
| `annex/kolla-images.md:547-548` (§7) and `docs/10-…:116` (Q1) | **Partly answered (mechanism only)**: QEMU PIDs, `/proc/<pid>/cgroup`, mount namespaces, `virsh list` and the handler retries recorded. Not covered: guest ping, `nova show` power state, nova-compute, real machined placement, cgroup v2 host, the Ussuri Docker/runc and libvirt 6.0 | all |

## Caveats

- **The decisive mechanism is version-dependent.** In this lab QEMU is killed by runc 1.5.2's `cgroup.kill` on the
  hybrid unified hierarchy, which needs runc ≥ 1.2 and Linux ≥ 5.14. The Ussuri-era stack (Docker 19.03/20.10,
  runc ≤ 1.1, kernels 4.15-5.4) enumerated the `devices` hierarchy instead (`out/upstream-excerpts.txt`), where
  libvirt's direct placement puts QEMU outside the container. Results a and b therefore do **not** show what happened
  on an Ussuri-era compute; they show what happens on a current Docker/runc on a kernel ≥ 5.14 with libvirt's direct
  placement. A Ussuri cloud whose computes have since received a newer docker-ce and an HWE kernel falls in this case.
- **libvirt 4.0 instead of 6.0.** libvirt 4.0 ignores the unified hierarchy. libvirt 6.0 has a cgroup v2 backend; if
  it also places QEMU in a unified `/machine` cgroup on a hybrid host, `cgroup.kill` would miss QEMU as in c2. Not
  tested.
- **No systemd-machined.** c1 is a manual model: one flat `/e4-machine` cgroup in every hierarchy, written from the
  host, not machined's `machine.slice/machine-qemu…scope` created over D-Bus. Whether a real compute's libvirtd
  reaches machined through the host `/run` bind mount was not testable here.
- The host `/run` is replaced by a dedicated shared mount, and `/lib/modules` by an empty directory (sandbox has
  neither a shared `/` nor `/lib/modules`); `extend_start.sh` logs a harmless `lsmod` error (no `/proc/modules`).
  `qemu_max_files`/`qemu_max_processes` were lowered (no `CAP_SYS_RESOURCE`).
- TCG guest without disk or NIC; no nova-compute. The observable is the QEMU process and libvirt's view, not guest
  I/O. The monitor check (suspend + resume) changes the domain state reason to "unpaused".
- The containerd shim was ptrace'd (`strace -f`) during every stop. Timings (0.25 s restarts, ~2.2 s per failing
  `runc delete`) are lab measurements on this sandbox only.
- Run 1 of the suite had a bug (the cgroup move read `/proc/<pid>/cgroup` while changing it and wrote stray
  directories into the host's `/sys/fs/cgroup` tmpfs, removed afterwards); its c1, c3 and d2 results were discarded.
  The fixed `move_cgroup` reads the file first and only writes into cgroup filesystems.

## Files

`build.sh`, `images/nova-libvirt/Dockerfile` (image); `render.py` (templates); `domain.xml.in` (guest); `lib.sh`,
`run.sh` (tests); `proc.py` (host `/proc` and strace helpers); `upstream.sh` (runc/containerd excerpts);
`out/environment.txt`, `out/summary.txt`, `out/config/`, `out/upstream-excerpts.txt`, `out/{a,b,c,d}/`.
