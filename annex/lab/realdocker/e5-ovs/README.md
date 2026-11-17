# e5: Open vSwitch restarts (Q3 mechanism, real Docker, real OVS)

Experiment e5 of the real-Docker lab. It runs the Kolla-Ansible Ussuri `openvswitch_db` and `openvswitch_vswitchd`
containers with real Open vSwitch daemons, the real kolla-ansible templates and the role's container parameters, and
answers, for the mechanism behind Q3 ([docs/10 §4](../../../../docs/10-technical-findings-and-open-questions.md),
line 118) and R7 ([docs/08](../../../../docs/08-operational-risk-matrix.md), line 25):

- what a `docker restart -t 10` and a recreate of `openvswitch_vswitchd` do to OpenFlow flows, bridges and ports;
- whether `ovs-vswitchd` and `ovsdb-server`, started by the non-`exec` wrappers `start-ovs` and
  `start-ovsdb-server`, receive SIGTERM;
- what a restart of `openvswitch_db` does to `conf.db` and to the running `ovs-vswitchd`;
- whether anything on the Kolla start path saves or restores flows.

It does not run Neutron. It measures how long the OVS part takes in this lab; it does not measure how long an agent
takes to reprogram flows. All durations are **lab measurements** in the environment of §1. They are not production
numbers.

## 1. Environment and versions

From [out/environment.txt](out/environment.txt):

| Item | Version |
|---|---|
| Docker | client and server 29.9.2, containerd v2.4.2, runc 1.5.2, cgroup v1, cgroupfs driver, overlayfs |
| Kernel | 6.18.44 (Firecracker VM, 4 vCPU). **No openvswitch kernel module** (`/sys/module/openvswitch` absent, no `/lib/modules` on the host), no IPv6 |
| Base image | `reallab/base:ussuri` (`sha256:891f52f2b6a9`): ubuntu:18.04, `dumb-init 1.2.1-1`, `bash 4.4.18-2ubuntu1.3`, unmodified kolla ussuri-eol base scripts |
| Open vSwitch | `openvswitch-switch`, `openvswitch-common`, `python3-openvswitch` **2.9.8-0ubuntu0.18.04.5** (bionic-updates). **Ussuri's Ubuntu images used OVS 2.13** from the Ubuntu Cloud Archive pocket `bionic-updates/ussuri` (kolla `docker/base/sources.list.ubuntu:13`), which this lab cannot reach |
| Other | `kmod 24-1ubuntu3.5`; strace 6.8 on the host |
| Images | `e5-openvswitch-base:ussuri`, `e5-openvswitch-db-server:ussuri`, `e5-openvswitch-vswitchd:ussuri`, `e5-peer:ussuri` (IDs of the cited run in [out/environment.txt](out/environment.txt)) |
| Sources | kolla ussuri-eol `9107c5f`, kolla-ansible ussuri-eol `8a94fe9`. For cross-references only (read, not run): Open vSwitch `v2.9.8` and `v2.13.0` `ofproto/ofproto-dpif.c` and `v2.9.8` `vswitchd/vswitch.xml`; neutron `ussuri-eol` `ovs_neutron_agent.py`, `openflow/native/br_int.py`, `agent/common/ovs_lib.py`, `common/constants.py` (from GitHub) |

**Docker caveat.** Ussuri ran on Docker 19.03/20.10 (runc 1.0-rc). The signal path seen here (dumb-init forwards
SIGTERM to its child; the kernel kills the rest of the PID namespace when dumb-init exits) does not depend on the
Docker version. How fast the runtime reports the exit and restarts the container does; the durations are not
transferable to the older stack.

## 2. Method

### 2.1 Images ([build.sh](build.sh), [images/](images/))

All `FROM reallab/base:ussuri`, built with `docker build --network host`:

- `e5-openvswitch-base`: kolla `docker/openvswitch/openvswitch-base/Dockerfile.j2` rendered for `deb`: the kolla
  package list (`openvswitch-switch python3-openvswitch python3-netifaces tcpdump`) plus `kmod`, which kolla's own
  base image installs (kolla `docker/base/Dockerfile.j2`, `base_apt_packages`) and the lab base does not; the
  unmodified `extend_start.sh` as `kolla_extend_start`; the `tcpdump` move; the empty
  `kolla_openvswitch_extend_start`.
- `e5-openvswitch-db-server`, `e5-openvswitch-vswitchd`: the steps of the kolla Dockerfiles, with the unmodified
  `extend_start.sh` (`mkdir -p /run/openvswitch` + `ovsdb-tool create`; `modprobe openvswitch`) and
  `ovs_ensure_configured.sh`.
- `e5-peer` (not a kolla image): `iputils-ping`, to hold a network namespace for the traffic probe, and `iproute2`
  for the veth set-up (this host has no iproute2).

### 2.2 Real templates and container parameters

[render.py](render.py) renders the four real templates of `roles/openvswitch/templates/` with jinja2 into
[cfg/](cfg/), as `roles/openvswitch/tasks/config.yml` does: `openvswitch-db-server.json.j2`,
`start-ovsdb-server.j2`, `openvswitch-vswitchd.json.j2`, `start-ovs.j2`. The only change: `ovsdb_port` 6640
(`group_vars/all.yml:427`) becomes **18540** (e5's port range; every kolla container uses the host network).

[lib.sh](lib.sh) (`run_db`, `run_vs`) creates the containers as `kolla_docker` does for this role
(`roles/openvswitch/defaults/main.yml:2-66`, `handlers/main.yml:2-42`, `kolla_docker.py` `build_host_config`):
`--network host`, `--restart unless-stopped`, `KOLLA_CONFIG_STRATEGY=COPY_ALWAYS`, `KOLLA_SERVICE_NAME`
(`openvswitch-db`, `openvswitch-vswitchd`), `privileged` for vswitchd only, no `pid_mode`, the config directory
read-only at `/var/lib/kolla/config_files/`, `/etc/localtime` and `/etc/timezone` read-only, `/lib/modules:ro`,
`/run/openvswitch:/run/openvswitch:shared`, `kolla_logs:/var/log/kolla/`, and for the db
`openvswitch_db:/var/lib/openvswitch/`. Substitutions: names prefixed `e5_`; `cfg/<svc>` for `/etc/kolla/<svc>`;
volumes `e5_kolla_logs` and `e5_openvswitch_db`; a scratch directory, bind-mounted onto itself and made a shared
mount, for the host's `/run/openvswitch` (so `:shared` is accepted as in the role); a scratch directory for
`/lib/modules` (§3 s). The restart and the recreate are done as `kolla_docker` does them: `restart_container` is
`stop(timeout=10)` + `start` (here `docker restart -t 10`); `recreate_or_restart_container` on a changed container is
`stop_container` (10 s), `remove_container`, `start_container` (here `docker stop -t 10`, `docker rm`, `docker run`).
The role's post-config `ovs-vsctl set Open_vSwitch . external_ids:system-id=...` is run through the vswitchd
container (`roles/openvswitch/tasks/post-config.yml:3-5`), and the handler's readiness check
(`docker exec openvswitch_db ovs-vsctl --no-wait show`, 30 x 2 s) is `wait_db`.

### 2.3 Datapath, bridges, flows and probes

- **Userspace (netdev) datapath.** This kernel has no openvswitch module, so both bridges use
  `datapath_type=netdev`. `ovs-vswitchd` confirms it at every start: `Generic Netlink family 'ovs_datapath' does not
  exist. The Open vSwitch kernel module is probably not loaded.`
  ([out/s-start-path/datapath-and-probe.txt](out/s-start-path/datapath-and-probe.txt)).
- `e5-br-sec`: `fail_mode=secure` (what neutron sets on `br-int` and the physical bridges, §4),
  `protocols=OpenFlow10,OpenFlow13`, `external_ids:bridge-id`, `other_config:mac-table-size=4096`; ports `e5-v1a`,
  `e5-v2a` (`tag=101`, `external_ids:iface-id/attached-mac/iface-status` as nova/os-vif set them) and a patch port.
  `e5-br-std`: no fail mode (standalone), `other_config:mac-table-size=2048`; ports `e5-v3a`, `e5-v4a`, patch peer.
  `Open_vSwitch` row: `external_ids:system-id`, `other_config:max-idle=15000`.
- **Flows with cookies** (`add_flows`): on `e5-br-sec`, `cookie=0xe5000001`/`0xe5000002` forward between the two
  probe ports, `0xe5000003` is a priority-1 drop and `0xe5000017` a drop in table 23 (shaped like neutron's canary
  flow, `CANARY_TABLE = 23`); on `e5-br-std`, `0xe5000011` (LLDP drop) and `0xe5000012` (IP to `NORMAL`). A secure
  bridge has no default flow, so only these flows carry the probe traffic on `e5-br-sec`; a standalone bridge with no
  controller gets OVS's own `priority=0 actions=NORMAL` flow (cookie 0).
- **Probe**: two peer containers (`--network none`) hold the other ends of four veth pairs whose host ends are the
  OVS ports. `ping -D -O -i 0.05` runs from `e5-peer1` to `10.55.1.2` (through `e5-br-sec`) and to `10.55.2.2`
  (through `e5-br-std`). [analyze.py](analyze.py) reports every gap of more than 0.25 s between replies.
- **Observation**: `snap` records `ovs-vsctl show`, the `Open_vSwitch`, `Bridge` and `Interface` rows and
  `ovs-ofctl dump-flows` of both bridges (counters' age fields removed). In a, b, c and e1, strace runs on the host
  attached to dumb-init, the wrapper and the daemon (all threads): signals, exits, and dumb-init's
  `rt_sigtimedwait`/`kill`/`exit_group` (e1 adds `unlink`). Docker events give the exit code. Each test keeps the
  delta of `ovs-vswitchd.log` (and `ovsdb-server.log` in c). "vswitchd answers" means
  `docker exec e5_openvswitch_db ovs-ofctl dump-flows e5-br-sec` succeeds, polled every 50 ms (each poll includes a
  `docker exec`, so these times are upper bounds by about 0.1 s).

### 2.4 Tests ([run.sh](run.sh), one pass, about 2.5 minutes)

| Id | What |
|---|---|
| s | start path: vswitchd unmodified with this host's `/lib/modules`, then with the minimal override; bridges, flows, probe |
| a | `docker restart -t 10 e5_openvswitch_vswitchd`, strace attached; snapshots before, right after, +10 s; then flows re-added |
| a2 | the same restart three more times without strace (timing); flows re-added 2 s after vswitchd answers |
| b | recreate: `docker stop -t 10`, observations while stopped, `docker rm`, `docker run`; strace attached |
| b2 | the same recreate back to back, no pause, no strace (timing) |
| c | `docker restart -t 10 e5_openvswitch_db`, strace attached; conf.db and flows after; a new port through vswitchd |
| d | grep of the images, the rendered templates, kolla-ansible `ansible/` and kolla `docker/` for flow save/restore |
| e1 | control: a direct SIGTERM to `ovs-vswitchd` (not a Kolla path): what OVS does when it does get SIGTERM |
| e2 | control: OVS's own save/restore (`ovs-save` + `flow-restore-wait`, as `ovs-lib` `restart()` does) around the same `docker restart` |

## 3. Results

### s. Start path ([out/s-start-path/](out/s-start-path/))

**Unmodified, vswitchd does not start here.** With `/lib/modules` an empty directory, kolla's
`kolla_openvswitch_extend_start` fails and `kolla_start` (`set -o errexit`) exits 1; the restart policy loops
([vswitchd-unmodified.txt](out/s-start-path/vswitchd-unmodified.txt)):

```
state=restarting exitCode=1 restartCount=7
+++ modprobe openvswitch
modprobe: FATAL: Module openvswitch not found in directory /lib/modules/6.18.44-fc-v553
```

On a real compute the module exists and `modprobe` succeeds, so this is a lab artefact.

**Minimal override (e5's, not Kolla's).** The `/lib/modules` mount source is a directory whose
`<kernel>/modules.builtin` lists `kernel/net/openvswitch/openvswitch.ko`, indexed by `depmod`. The real kmod
`modprobe openvswitch` then exits 0 ("built in") and loads nothing. Image, kolla scripts and templates are unchanged
([vswitchd-override.txt](out/s-start-path/vswitchd-override.txt)): `state=running exitCode=0 restartCount=0`.

**Process tree** (host view, same file): dumb-init's child is bash, the daemon is bash's child, as the templates imply:

```
dumb-init --single-child -- kolla_start
bash /usr/local/bin/start-ovs
/usr/sbin/ovs-vswitchd unix:/run/openvswitch/db.sock ... --mlockall --log-file=... --pidfile
```

[db-start.txt](out/s-start-path/db-start.txt) shows the same for `start-ovsdb-server` / `ovsdb-server`, and the image
creating `conf.db` on the empty volume (`ovsdb-tool create /var/lib/openvswitch/conf.db`). The probe passes through
both bridges (3/3 replies each, [datapath-and-probe.txt](out/s-start-path/datapath-and-probe.txt)); the initial
state is in [initial-state.txt](out/s-start-path/initial-state.txt).

### a. `docker restart -t 10` of `openvswitch_vswitchd` ([out/a-restart-vswitchd/](out/a-restart-vswitchd/))

**Signals** ([strace.txt](out/a-restart-vswitchd/strace.txt)): dumb-init takes SIGTERM and forwards it to bash only;
bash dies of it; `ovs-vswitchd` never receives SIGTERM and is killed by SIGKILL when dumb-init exits:

```
+0.035 s  dumb-init(1)     rt_sigtimedwait(...) = 15 (SIGTERM)
+0.035 s  dumb-init(1)     kill(7, SIGTERM) = 0
+0.035 s  bash(7)          --- SIGTERM {si_signo=SIGTERM, si_code=SI_USER, si_pid=1, si_uid=0} ---
+0.035 s  bash(7)          +++ killed by SIGTERM +++
+0.036 s  dumb-init(1)     exit_group(143) = ?
+0.036 s  thread 25753     +++ killed by SIGKILL +++
...
+0.132 s  ovs-vswitchd(18) +++ killed by SIGKILL +++
+0.132 s  dumb-init(1)     +++ exited with 143 +++
```

The SIGKILL reaches the daemon's threads in the same millisecond as dumb-init's `exit_group(143)`, as when a PID
namespace loses its init ([e1](../e1-signals/README.md) analyses that mechanism); the main thread is reaped at
+0.132 s.

The OVS log confirms it independently: `ovs-vswitchd` logs `terminating with signal 15` when it gets SIGTERM (e1),
and the log of the whole run has exactly one such line, from e1
([out/log-starts-and-signals.txt](out/log-starts-and-signals.txt), line 271 of `ovs-vswitchd.log`). The delta of
test a starts directly with the new daemon's `opened log file`
([ovs-vswitchd.log](out/a-restart-vswitchd/ovs-vswitchd.log)).

**Exit code and duration** ([timeline.txt](out/a-restart-vswitchd/timeline.txt)): `die exitCode=143` at +0.164 s;
`docker restart returned` at +0.243 s; vswitchd answers on the bridge management socket at +0.461 s. The 10 s
timeout is never reached.

**Flows are lost; bridges, ports and settings are kept.** The diff before / right after the restart
([diff-before-vs-after-restart.txt](out/a-restart-vswitchd/diff-before-vs-after-restart.txt)) contains only flows:

```
<  cookie=0xe5000001, table=0, n_packets=40, n_bytes=3864, priority=100,in_port=2 actions=output:1
<  cookie=0xe5000002, table=0, n_packets=40, n_bytes=3864, priority=100,in_port=1 actions=output:2
<  cookie=0xe5000003, table=0, n_packets=1, n_bytes=42, priority=1 actions=drop
<  cookie=0xe5000017, table=23, n_packets=0, n_bytes=0, priority=0 actions=drop
<  cookie=0xe5000011, table=0, n_packets=0, n_bytes=0, priority=200,dl_type=0x88cc actions=drop
<  cookie=0xe5000012, table=0, n_packets=47, n_bytes=4606, priority=100,ip,in_port=2,nw_dst=10.55.2.0/24 actions=NORMAL
<  cookie=0x0, table=0, n_packets=49, n_bytes=4690, priority=0 actions=NORMAL
---
>  cookie=0x0, table=0, n_packets=20, n_bytes=1848, priority=0 actions=NORMAL
```

Every cookie flow is gone, including the table-23 drop flow; `e5-br-sec` has no flow at all, `e5-br-std` only OVS's
default `NORMAL` flow. `ovs-vsctl show`, the `Open_vSwitch` row (`system-id`, `max-idle`), the `Bridge` rows
(`datapath_type`, `fail_mode`, `protocols`, `other_config`, `external_ids`) and the `Interface` rows (type,
**ofport**, `options`, `external_ids`) are identical before and after ([before.txt](out/a-restart-vswitchd/before.txt),
[after-restart.txt](out/a-restart-vswitchd/after-restart.txt)). Ten seconds later nothing has restored a flow
([after-restart+10s.txt](out/a-restart-vswitchd/after-restart+10s.txt): `e5-br-sec` empty).

**Traffic** ([ping.txt](out/a-restart-vswitchd/ping.txt)):

```
== 10.55.1.2 (... 66% packet loss ...)
   GAP: last reply before -0.009 s (seq 57) -> next reply +12.827 s (seq 285): 12.837 s without reply, 227 requests unanswered
== 10.55.2.2 (... 1% packet loss ...)
   GAP: last reply before +0.012 s (seq 57) -> next reply +0.355 s (seq 63): 0.344 s without reply, 5 requests unanswered
```

Through the secure bridge, traffic stops at the kill and resumes only when the flows are re-added (re-add started at
+12.488 s). Through the standalone bridge, it resumes after 0.34 s, as soon as the new daemon forwards with its
default `NORMAL` flow.

### a2. Three more restarts, no strace ([out/a2-restart-timing/summary.txt](out/a2-restart-timing/summary.txt))

| Run | die (143) | `docker restart` returned | vswitchd answers | flows right after (sec / std) | standalone gap | secure gap (flows re-added by) |
|---|---|---|---|---|---|---|
| 1 | +0.139 s | +0.238 s | +0.449 s | 0 / 1 (`NORMAL`) | 0.336 s | 2.944 s (+2.996 s) |
| 2 | +0.158 s | +0.231 s | +0.448 s | 0 / 1 | 0.352 s | 2.928 s (+3.012 s) |
| 3 | +0.162 s | +0.244 s | +0.328 s | 0 / 1 | 0.348 s | 2.823 s (+2.904 s) |

The result of a is reproducible, and strace did not change the timing materially. The secure-bridge gap is set by
when e5 re-adds the flows, not by OVS.

### b. Recreate of `openvswitch_vswitchd` ([out/b-recreate-vswitchd/](out/b-recreate-vswitchd/))

Same signal path ([strace.txt](out/b-recreate-vswitchd/strace.txt): `bash(7) +++ killed by SIGTERM +++`,
`ovs-vswitchd(18) +++ killed by SIGKILL +++`) and exit code
([stopped-state.txt](out/b-recreate-vswitchd/stopped-state.txt): `exitCode=143`, old container `7f10d6c9b7cc`, new
`06ff1754faf7`). Same result: the diff before / after
([diff-before-vs-after-recreate.txt](out/b-recreate-vswitchd/diff-before-vs-after-recreate.txt)) contains only the
lost flows; bridges, ports, ofports and settings are unchanged, because they live in `conf.db` on the db volume and
the new container reads them.

While vswitchd is stopped ([while-stopped.txt](out/b-recreate-vswitchd/while-stopped.txt),
[while-stopped-state.txt](out/b-recreate-vswitchd/while-stopped-state.txt)): `ovs-vsctl show` still works (ovsdb is
up), `ovs-ofctl` fails (`e5-br-sec.mgmt: failed to open socket (Connection refused)`), and the SIGKILLed daemon's
files are left in the shared `/run/openvswitch`: `ovs-vswitchd.pid`, `ovs-vswitchd.18.ctl`, `e5-br-*.mgmt`,
`e5-br-*.snoop`. They do not block the next start (`docker run` returned at +1.119 s and the new daemon answered at
+1.333 s). The netdev bridges' tap devices also stay in the host namespace (`e5-br-sec DOWN`), a property of the
netdev datapath.

Traffic ([ping.txt](out/b-recreate-vswitchd/ping.txt)): secure bridge 13.829 s without reply, until the flows were
re-added (+13.443 s); standalone bridge 1.263 s, which includes e5's 0.75 s observation pause between `docker stop`
and `docker rm` ([timeline.txt](out/b-recreate-vswitchd/timeline.txt)).

### b2. Recreate back to back ([out/b2-recreate-timing/](out/b2-recreate-timing/))

[timeline.txt](out/b2-recreate-timing/timeline.txt): `docker stop` returned +0.173 s (`die exitCode=143` at +0.167 s),
`docker rm` +0.218 s, `docker run` +0.368 s, vswitchd answers +0.589 s, and then `flows (cookie lines) after
recreate: e5-br-sec 0, e5-br-std 1`. [ping.txt](out/b2-recreate-timing/ping.txt): standalone bridge 0.508 s without
reply; secure bridge 3.112 s, ended by the re-add started at +2.754 s.

### c. `docker restart -t 10` of `openvswitch_db` ([out/c-restart-db/](out/c-restart-db/))

**Signals** ([strace.txt](out/c-restart-db/strace.txt)): the same pattern; `ovsdb-server` gets no SIGTERM:

```
+0.033 s  start-ovsdb-ser(7)   --- SIGTERM {si_signo=SIGTERM, si_code=SI_USER, si_pid=1, si_uid=0} ---
+0.033 s  start-ovsdb-ser(7)   +++ killed by SIGTERM +++
+0.034 s  dumb-init(1)         exit_group(143) = ?
+0.035 s  ovsdb-server(28)     +++ killed by SIGKILL +++
```

**Timing** ([timeline.txt](out/c-restart-db/timeline.txt)): `die exitCode=143` at +0.071 s, `docker restart returned`
at +0.189 s, Kolla's readiness check passes at +0.289 s.

**conf.db survives intact** and **flows are kept**: the diff before / after
([diff-before-vs-after-restart.txt](out/c-restart-db/diff-before-vs-after-restart.txt)) contains only packet
counters of flows that are still there (e.g. `cookie=0xe5000001 ... n_packets=81` then `n_packets=121`); bridges,
ports, `fail_mode`, `other_config`, `external_ids`, ofports and `system-id` are identical.

**vswitchd reconnects by itself** after its 1 s reconnect back-off
([ovs-vswitchd.log](out/c-restart-db/ovs-vswitchd.log)):

```
13:50:25.469Z|00038|reconnect|INFO|unix:/run/openvswitch/db.sock: connection closed by peer
13:50:26.469Z|00039|reconnect|INFO|unix:/run/openvswitch/db.sock: connecting...
13:50:26.469Z|00040|reconnect|INFO|unix:/run/openvswitch/db.sock: connected
13:50:27.273Z|00043|bridge|INFO|bridge e5-br-std: added interface e5-int9 on port 4
```

and applies new configuration: `ovs-vsctl add-port` without `--no-wait` (which waits until vswitchd has applied the
change) returned `rc=0; ofport=4` at +1.943 s. The new `ovsdb-server` logged nothing about its predecessor's end
([ovsdb-server.log](out/c-restart-db/ovsdb-server.log) starts with `opened log file`).

**Traffic** ([ping.txt](out/c-restart-db/ping.txt)): `0% packet loss` and `no interruption` on both bridges.

### d. Nothing on the Kolla start path saves or restores flows ([out/d-grep/grep.txt](out/d-grep/grep.txt))

Pattern `ovs-save|flow-restore-wait|flow_restore_wait|restore-flows|replace-flows|dump-flows|add-flows|ovs-ctl`:

- the start-path files of both images (`kolla_start`, `kolla_set_configs`, `kolla_extend_start`,
  `kolla_openvswitch_extend_start`, `kolla_copy_cacerts`): `grep rc=1` (no match);
- the rendered `config.json`, `start-ovs`, `start-ovsdb-server`: `grep rc=1`;
- kolla-ansible ussuri-eol `ansible/` and kolla ussuri-eol `docker/`: `git grep rc=1`;
- the live `Open_vSwitch` `other_config`: `{max-idle="15000"}` (e5's key only; no `flow-restore-wait`);
- the running containers hold only dumb-init, the wrapper and the daemon (`docker top`).

The images do contain OVS's own mechanism, unused: the only files mentioning `ovs-save` or `flow-restore-wait` are
`/usr/share/openvswitch/scripts/ovs-lib`, `ovs-save` and dpkg metadata. In `ovs-lib`, `restart ()` (line 649) and
`force_reload_kmod ()` (line 588) call `save_flows_if_required`, `flow_restore_wait`, `restore_flows` and
`flow_restore_complete`; they are reached through `ovs-ctl restart` / `force-reload-kmod` (`ovs-ctl` lines 524, 539),
which Kolla never runs: its command is `start-ovs`, which runs `ovs-vswitchd` directly.

### e1. Control: what `ovs-vswitchd` does when it does get SIGTERM ([out/e1-sigterm-control/](out/e1-sigterm-control/))

A direct `kill -TERM` to the daemon (not a Kolla path). [strace.txt](out/e1-sigterm-control/strace.txt): the daemon
takes SIGTERM, removes its pidfile, control socket and bridge sockets, then dies of SIGTERM; bash exits 143 and so
does dumb-init:

```
+0.069 s  ovs-vswitchd(18)  --- SIGTERM {si_signo=SIGTERM, si_code=SI_USER, si_pid=153, si_uid=0} ---
+0.070 s  thread 1072       unlink("/var/run/openvswitch/ovs-vswitchd.pid") = 0
+0.070 s  thread 1072       unlink("/var/run/openvswitch/ovs-vswitchd.18.ctl") = 0
+0.155 s  ovs-vswitchd(18)  +++ killed by SIGTERM +++
+0.157 s  bash(7)           exit_group(143) = ?
```

[ovs-vswitchd.log](out/e1-sigterm-control/ovs-vswitchd.log):
`fatal_signal(revalidator9)|WARN|terminating with signal 15 (Terminated)`. This validates the log observable of a
and b: there, no such line appeared, and b found the pidfile, control socket and bridge sockets still present after
the stop. The container then exited 143 and its `unless-stopped` policy restarted it
([timeline.txt](out/e1-sigterm-control/timeline.txt): `die exitCode=143`, `start`;
[restart-count.txt](out/e1-sigterm-control/restart-count.txt): `restartCount=1`), and the flows were gone
(`flows (cookie lines) now: e5-br-sec 0`): any exit of `ovs-vswitchd` (here by SIGTERM; a crash would take the same
container path, not tested) costs the flows like a restart.

### e2. Control: OVS's own save/restore around the same restart ([out/e2-…](out/e2-save-restore-control/))

The `ovs-lib` `restart()` sequence done by hand around Kolla's restart: `ovs-save save-flows` (to the shared
`/run/openvswitch`), `other_config:flow-restore-wait=true`, `docker restart -t 10`, run the saved script
([e5-restore-flows.sh](out/e2-save-restore-control/e5-restore-flows.sh): `ovs-ofctl ... replace-flows`), remove
`flow-restore-wait`. [timeline.txt](out/e2-save-restore-control/timeline.txt): restart returned +0.441 s, vswitchd
answers +0.525 s with `e5-br-sec 0` flows, saved flows restored +0.682 s, `flow-restore-wait` removed +0.799 s.
[diff-before-vs-after.txt](out/e2-save-restore-control/diff-before-vs-after.txt): the same cookie flows are back
(only counters and `cur_cfg` differ). [ping.txt](out/e2-save-restore-control/ping.txt): both bridges
`0.624 s` / `0.628 s` without reply, the secure bridge included. The flow loss in a and b is therefore a property of
Kolla's start path, which has no such step, not of Open vSwitch.

## 4. What this settles in the study

| Study statement (file:line) | Verdict | Evidence |
|---|---|---|
| [annex/kolla-images.md:389](../../../kolla-images.md): "`start-ovs` runs `ovs-vswitchd` without `exec` and without flow save or restore … [HYPOTHESIS] flows are lost (§6 item 13)" | **Confirmed** for flows (OVS 2.9.8, netdev datapath): every OpenFlow flow, all cookies and tables, is gone after a restart (a, a2) and a recreate (b, b2), and nothing restores them (d; +10 s snapshots). "The kernel module stays loaded" is **not tested** (no module here) | a, a2, b, b2, d |
| [annex/kolla-images.md:388](../../../kolla-images.md): "`conf.db` is on the `openvswitch_db` volume: bridges and ports survive restart and recreate" | **Confirmed**, and extended: bridges, ports, interface types, ofports, `fail_mode`, `protocols`, `other_config`, `external_ids` and `system-id` survive a vswitchd restart and recreate (a, b) and an ovsdb-server restart (c). The schema conversion branch was not exercised | a, b, c |
| [annex/kolla-images.md:512-514](../../../kolla-images.md) (§6 item 13): "replaces only the userspace daemon … `conf.db` keeps bridges and ports [CODE]. [HYPOTHESIS] The OpenFlow tables are lost and must be reprogrammed by the OVS agent or `ovn-controller`" | **Confirmed** that the OpenFlow tables are lost and are not reprogrammed by anything in the OVS containers. Who reprograms them was not run: [CODE, upstream neutron ussuri-eol, read for e5] the OVS agent detects the restart by the absence of its canary flow (`check_canary_table`, `br_int.py:58-64`; `ovs_neutron_agent.py:2391-2398`), which a showed is lost | a, a2, d |
| [annex/kolla-images.md:180-183](../../../kolla-images.md) (§2.6) and [docs/08:42](../../../../docs/08-operational-risk-matrix.md) (R24): services behind non-`exec` wrappers (`ovs-vswitchd`, `ovsdb-server`) "get no SIGTERM at all … killed when the container stops, at the latest by the SIGKILL after 10 s" | **Confirmed** (no SIGTERM, with the real daemons) and **refined**: SIGKILL reaches the daemon in the same millisecond as dumb-init's `exit_group(143)`, about 0.03-0.04 s after `docker stop`/`restart` starts; the container exits 143 within about 0.07-0.17 s; the 10 s timeout never comes into play. OVS does handle SIGTERM cleanly when it gets it (e1), so the wrappers are what deprives it of a clean shutdown | a, b, c, e1 |
| [docs/10:25](../../../../docs/10-technical-findings-and-open-questions.md) (F3): "[HYPOTHESIS] Services started by a shell wrapper that does not `exec` them … get no SIGTERM at all" | **Confirmed** for `start-ovs`/`ovs-vswitchd` and `start-ovsdb-server`/`ovsdb-server` | a, b, c |
| [docs/08:25](../../../../docs/08-operational-risk-matrix.md) (R7): "Bridges and ports persist in `conf.db` … [HYPOTHESIS] The OpenFlow tables held by the old daemon are lost … **all VM network traffic on the host interrupted** until flows are restored [HYPOTHESIS: seconds to minutes]" | **Mechanism confirmed, duration not settled.** On a `fail_mode=secure` bridge (neutron sets secure mode on `br-int` and the physical bridges: [CODE] neutron `ovs_neutron_agent.py:1356,1527`) traffic stopped at the kill and did not resume until the flows were re-added (12.8 s and 13.8 s in a and b, set by e5's re-add). The OVS part is short in this lab: about 0.3-0.6 s from the restart command to a daemon that accepts flows (a, a2, b2). The duration in production is the agent's resync time, NEEDS-LAB. On a standalone bridge without a controller, traffic resumed after 0.34-0.51 s through OVS's default `NORMAL` flow, which is not how neutron's bridges forward | a, a2, b, b2 |
| [docs/08:25](../../../../docs/08-operational-risk-matrix.md) (R7), first column: "also any `openvswitch_db`-only drift … loop-notify also notifies the vswitchd handler" | **Refined**: an `openvswitch_db` restart alone does not touch flows or traffic (0 % loss, flows kept, vswitchd reconnects after 1 s and applies new config). The data-plane cost of a db-only drift comes entirely from the vswitchd restart that loop-notify adds (03 §2.4), not from the db restart | c |
| [docs/03:163,194](../../../../docs/03-ansible-roles-and-tags-mapping.md): "[HYPOTHESIS] a vswitchd restart interrupts **all VM traffic** on that host"; "nothing saves or restores flows" | Second part **confirmed** (d). First part: **mechanism confirmed** as in R7 above | a, b, d |
| [docs/10:118](../../../../docs/10-technical-findings-and-open-questions.md) (Q3) and [annex/kolla-images.md:550](../../../kolla-images.md) (§7): "OVS flow loss … and the time to reprogram" | **Partly answered**: flow loss on restart and recreate is settled for OVS 2.9.8 with the netdev datapath, as is the OVS-side restart time in this lab. The time to reprogram (agent or `ovn-controller`) and the loss with the kernel datapath stay NEEDS-LAB | a-b2 |

Additional findings for the study:

- **OVS's own hot-restart procedure works with Kolla's containers** (e2): `ovs-save` + `flow-restore-wait` around
  `docker restart` brought back every flow and cut the secure-bridge outage to 0.62 s in this lab. Kolla Ussuri does
  not do this (d). It is a candidate mitigation for R7, to validate with the kernel datapath and OVS 2.13 first.
- **An exit of `ovs-vswitchd` has the same effect as a restart** (e1, exit by SIGTERM): the container exits, the
  `unless-stopped` policy restarts it, and the flows are gone. A crash was not tested.
- **Kernel datapath, from upstream code only.** [CODE, OVS `ofproto/ofproto-dpif.c` v2.9.8:757-761 and
  v2.13.0:790-794, read, not run] A starting `ovs-vswitchd` calls `dpif_flow_flush()` on the datapath unless
  `flow-restore-wait` is set. [HYPOTHESIS] With the kernel module, the datapath flows cached in the kernel keep
  forwarding established traffic between the kill and the new daemon's start, and the flush at start removes them;
  the interruption would then start at the new daemon's start rather than at the kill. This lab cannot show it.
- **Unhandled start failure.** Kolla's vswitchd image stops at `modprobe openvswitch` under `errexit` and the
  container loops on its restart policy (s). On a host whose `/lib/modules` lacks the module (kernel updated but
  modules missing, custom kernel), `openvswitch_vswitchd` would not start at all.

## 5. Caveats

- **OVS 2.9.8 (bionic), not 2.13 (UCA ussuri).** The restart, signal and `conf.db` behaviour shown here depends on
  code that has the same shape in both (fatal-signal handling; flows held in the daemon; datapath flush at start,
  `ofproto-dpif.c` cited above), but nothing here was run on 2.13.
- **Userspace (netdev) datapath, not the kernel datapath** Ussuri computes use. With netdev the datapath lives in the
  `ovs-vswitchd` process, so forwarding stops at the kill. With the kernel datapath, the module would keep its cached
  flows until the new daemon flushes them ([HYPOTHESIS], §4). The OpenFlow tables, which this experiment is about,
  are held by `ovs-vswitchd` in both cases.
- **No Neutron.** The flows are e5's, re-added by e5 with `ovs-ofctl`. Agent behaviour (restart detection, resync,
  its duration) is cited from source, not run. OVN was not tested.
- **Lab substitutions**: the `/lib/modules` override (§3 s); scratch directories for `/run/openvswitch` and the
  config directory; e5-prefixed names and volumes; `ovsdb_port` 18540; no `kolla_toolbox`, fluentd or cron. The
  container parameters are otherwise those of the role.
- **Docker 29.9.2 / runc 1.5.2**, not 19.03/20.10 (§1).
- **Measurement resolution**: ping every 50 ms; "vswitchd answers" polled every 50 ms through `docker exec` (upper
  bounds by about 0.1 s); event times are taken after each command returns. strace was attached in a, b, c and e1;
  a2 and b2 give the timings without it. In b, e5's observations add 0.75 s between `docker stop` and `docker rm`.
- **Only one host, idle.** Four vCPU, no load, eight OVS ports, a handful of flows. A production `br-int` holds
  thousands of flows; reprogramming them takes longer than e5's few `ovs-ofctl` calls.

## 6. Files and reproduction

- [build.sh](build.sh), [images/](images/): image recipes (the kolla files are copied from `$KOLLA_SRC` at build
  time). [render.py](render.py) renders the real templates into [cfg/](cfg/). [lib.sh](lib.sh): container
  parameters, probes, snapshots, strace, cleanup. [run.sh](run.sh): all tests. [analyze.py](analyze.py): timelines,
  strace rendering (host pids to names, return times of syscalls), ping gaps and excerpts.
- Run as root (it bind-mounts a scratch directory and creates veth pairs), with `reallab/base:ussuri` built:

  ```bash
  KOLLA_SRC=<kolla ussuri-eol> KA_SRC=<kolla-ansible ussuri-eol> E5_WORK=<scratch dir> ./run.sh
  ```

  It removes everything e5 created (containers `e5_openvswitch_*` and `e5-peer*`, volumes `e5_*`, host links `e5-*`,
  the bind mount) before and after the run, keeps the images, rewrites `out/` and uses host port 18540. No secrets.
- `out/`: one directory per test. `timeline.txt` (times relative to the T0 line, with docker events),
  `strace.txt`, `ping.txt` and `ping-excerpt.txt` (raw `ping -D -O` lines around each gap), snapshots
  (`before.txt`, `after-*.txt`) and their diffs, and the `ovs-vswitchd.log`/`ovsdb-server.log` deltas.
  [out/log-starts-and-signals.txt](out/log-starts-and-signals.txt) lists every daemon start and every
  `terminating with signal` line of the whole run.
