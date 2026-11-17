# e1: signal delivery and the stop path (real Docker)

Experiment e1 of the real-Docker lab. It answers, by running real containers and tracing every signal from the host,
what `docker stop -t 10` (what `kolla_docker` sends) does to Kolla Ussuri containers: which process gets SIGTERM,
what kills the others and when, and what that means for the services the study names (neutron-l3-agent, Open
vSwitch, HAProxy, MariaDB, nova_libvirt's `pid_mode: host`). It settles the "dumb-init signal forwarding" and
"runtime killing the container's cgroup" items of [annex/kolla-images.md §7](../../../kolla-images.md) (lines
542-546), as far as a lab without real OpenStack services can.

All durations below are **lab measurements** in the environment of §1, with strace attached. They are not production
numbers.

## 1. Environment and versions

From [out/environment.txt](out/environment.txt):

| Item | Version |
|---|---|
| Docker | client and server 29.9.2, containerd v2.4.2, runc 1.5.2, cgroup v1, cgroupfs driver, overlayfs |
| Kernel | 6.18.44 (Firecracker VM, 4 vCPU), Ubuntu 24.04 userland, strace 6.8 on the host |
| Base image | `reallab/base:ussuri` (`sha256:891f52f2b6a9`): ubuntu:18.04, `dumb-init 1.2.1-1`, `bash 4.4.18-2ubuntu1.3`, `python3.6 3.6.9`, unmodified kolla ussuri-eol base scripts, `ENTRYPOINT ["dumb-init","--single-child","--"]` |
| HAProxy | `haproxy 1.8.8-1ubuntu0.13` (bionic main) |
| MariaDB | `mariadb-server-10.1 1:10.1.48-0ubuntu0.18.04.1` and `galera-3 25.3.20-1` (bionic). **Ussuri used MariaDB 10.3** from MariaDB's repository (kolla `kolla/template/repos.yaml:78`), which the lab proxy refuses (403); see §5 (f) |
| Sources | kolla ussuri-eol `9107c5f`, kolla-ansible ussuri-eol `8a94fe9`; dumb-init v1.2.1 `dumb-init.c` (read from GitHub) |

**Docker caveat.** Ussuri ran on Docker 19.03/20.10 (containerd 1.2-1.4, runc 1.0-rc). Here it is Docker 29 with
containerd 2.4 and runc 1.5. What dumb-init does and what the kernel does when a PID namespace loses its init do not
depend on Docker. What the containerd shim does after the init exits (`runc kill --all` under a shared PID namespace,
§5 (g)) and waiting for stdio (g5) are shim behaviour of this version; they were not checked on the older versions.

## 2. Method

### 2.1 What runs

- **Images** (all `FROM reallab/base:ussuri`, built by [build.sh](build.sh) with `docker build --network host`):
  - `e1-svc:ussuri`: user `neutron` (uid 42435, group kolla, as kolla's base creates it), the unmodified kolla
    `neutron-base/extend_start.sh` as `kolla_extend_start`, `USER neutron` as the l3-agent image ends, and the
    signal-logging stand-in [images/svc/e1-sigsvc](images/svc/e1-sigsvc) installed under several names.
  - `e1-ovsdb:ussuri`, `e1-ovsvswitchd:ussuri`: the unmodified kolla `openvswitch-base`, `openvswitch-db-server` and
    `openvswitch-vswitchd` `extend_start.sh`; stand-ins at `/usr/sbin/ovsdb-server` and `/usr/sbin/ovs-vswitchd`, a
    stub `/usr/bin/ovsdb-tool` (create, needs-conversion) and a logging stub `/sbin/modprobe` (this kernel has no
    openvswitch module and no `/lib/modules`). e5 tests real OVS.
  - `e1-haproxy:ussuri`: the kolla haproxy image steps with the **real** bionic haproxy.
  - `e1-mariadb:ussuri`: the kolla mariadb image steps (sudoers, `extend_start.sh`, `security_reset.expect`,
    `ENTRYPOINT ["dumb-init", "--"]`, `USER mysql`) with the **real** bionic mariadb-server 10.1 and galera-3.
    `mariadb-backup` does not exist in bionic and is left out (SST and backups only).
  - `e1-mariadb-upstreamtrap:ussuri`: the same with one e1 edit, not a kolla step: `mysqld_safe`'s two Debian `trap`
    lines replaced by upstream MariaDB's `trap '' 1 2 3 15` (see §5 (f)).
  - The haproxy and mariadb images also carry kolla base's `LAST_SYSTEM_UID=59999` edit (kolla
    `docker/base/Dockerfile.j2:289-292`), without which the bionic haproxy package refuses the pre-created user.
- **Real Kolla-Ansible templates**, rendered with jinja2 by [render.py](render.py) into [cfg/](cfg/) (Ansible's
  `trim_blocks`, plus `lstrip_blocks` when the template asks for it): `neutron-l3-agent-wrapper.sh.j2` with
  `enable_neutron_agent_ha` false and true, `neutron-l3-agent.json.j2`, `start-ovs.j2`, `start-ovsdb-server.j2`,
  `openvswitch-*.json.j2`, `haproxy_run.sh.j2`, `haproxy.json.j2`, `haproxy_main.cfg.j2`,
  `haproxy_single_service_listen.cfg.j2` (the default service template), `mariadb.json.j2`, `galera.cnf.j2`,
  `wsrep-notify.sh.j2`. Ports were moved into e1's range 18110-18133 and addresses to 127.0.0.1;
  `innodb_buffer_pool_size` is 256M (the template's 40 % of RAM, rendered with `memtotal_mb=640`). Not from a
  template: the minimal `config.json` of tests a, b and g (`{"command": "/usr/local/bin/e1-sigsvc"}`), the
  `haproxy-exec` control manifest of e2, and placeholder neutron config files.
- **Container parameters** mirror `kolla_docker` and the role defaults ([lib.sh](lib.sh) `ctr_run`): `--network host`
  (`kolla_docker.py:719`), `--restart unless-stopped`, `KOLLA_CONFIG_STRATEGY=COPY_ALWAYS`, `KOLLA_SERVICE_NAME`, the
  config dir read-only at `/var/lib/kolla/config_files/`, `/etc/localtime` and `/etc/timezone`, `privileged` where the
  role sets it (l3 agent, ovs-vswitchd, haproxy), `KOLLA_LEGACY_IPTABLES` for the l3 agent, `pid_mode: host` in g.
  Differences: a host directory replaces the `kolla_logs` volume; `/run/netns:shared`, `/run/openvswitch:shared` and
  `/lib/modules` are not mounted (the host root mount is not shared and `/lib/modules` does not exist; none of them
  is on the signal path); tests a, b and g run as root (`-u root`; nova-libvirt, the model for g, runs as root), c as
  the image's `neutron`.
- **Stand-in** ([e1-sigsvc](images/svc/e1-sigsvc), Python 3.6): blocks every catchable signal and takes them with
  `sigtimedwait`, so it logs each one with the sender's pid. On SIGTERM it logs, waits a 0.5 s "graceful shutdown" and
  exits 0, or (`E1_TERM=ignore`) logs and continues. It can spawn a plain child (`name`) and daemonized grandchildren
  (`name@daemon`: fork, setsid, fork, stdio to `/dev/null`, as keepalived, haproxy and radvd daemonize). As
  `neutron-netns-cleanup` it is a one-shot with a set duration and exit code. The L3 agent stand-in spawns
  `e1-rootwrap-daemon` (child), `e1-keepalived` and `e1-haproxy-ns` (daemons). It models signal receipt only, not
  what a real agent does on SIGTERM.

### 2.2 How each case is observed

For every case ([run.sh](run.sh)): start the container, wait until the service logs `ready`, record the process table
from the host's `/proc` ([proctab.py](proctab.py): host pid, pid/ppid/pgid/sid inside the container's PID namespace,
uid, devices cgroup; plus `docker exec ps` inside), attach **strace on the host** to every process of the container
(`-f`, following threads and forks; `kill`, `tgkill`, `rt_sigtimedwait`, `wait4`, `exit_group`, `execve`, `clone` and
all signals) and to the container's **containerd shim** (which `runc` commands it runs), then time `docker stop -t 10`,
read the exit code and check from the host which pre-stop processes still exist (same host pid and start time).
[analyze.py](analyze.py) turns the trace into `timeline.txt` (times relative to the start of `docker stop`) and a
per-process fate table. Two strace properties matter for reading the results: `si_pid` is the sender's pid in the
receiver's PID namespace (0 = from outside, i.e. `runc`), and a traced process is shown a signal even when it ignores
it (the kernel reports ignored signals to a tracer), so "receives SIGTERM" does not mean "acted on it".

## 3. Results at a glance

| Case | What | `docker stop` | Exit | SIGTERM reached | Everything else | Survivors |
|---|---|---|---|---|---|---|
| a1 | exec'd service | 0.656 s | 0 | the service (from dumb-init) | child and daemon: SIGKILL when dumb-init exits, no SIGTERM | none |
| b1 | exec'd, ignores SIGTERM | 10.194 s | 137 | the service (ignored) | all SIGKILL at +10.11 s | none |
| c1 | l3 wrapper, ha=false | 0.146 s | 143 | bash only | agent, its child and daemons: SIGKILL ~9 ms after bash died | none |
| c2 | l3 wrapper, ha=true | 0.151 s | 143 | bash only | same as c1 | none |
| c3 | ha=true, cleanup exits 1 | - | 1 | - | agent never starts; 7 starts in 15 s | - |
| c4 | ha=true, stop during cleanup | 0.165 s | 143 | bash only | cleanup SIGKILLed mid-run | none |
| d1 | start-ovsdb-server | 0.142 s | 143 | bash only | ovsdb-server stand-in: SIGKILL | none |
| d2 | start-ovs | 0.161 s | 143 | bash only | ovs-vswitchd stand-in: SIGKILL | none |
| e1 | real haproxy, haproxy_run.sh | 0.151 s | 143 | bash only | xargs, haproxy master and worker: SIGKILL; download cut | none |
| e2 | control: haproxy exec'd | 0.159 s | 143 | master, which sends it to the worker | worker dies of SIGTERM; download cut | none |
| f1 | MariaDB, `dumb-init --` | 4.947 s | 0 | mysqld_safe and mysqld | normal shutdown, no crash recovery | none |
| f2 | control: `--single-child` | 10.237 s | 137 | mysqld_safe only | mysqld SIGKILLed; InnoDB crash recovery | none |
| f3 | `dumb-init --`, upstream trap | 4.858 s | 0 | mysqld_safe (ignored) and mysqld | normal shutdown, no crash recovery | none |
| f4 | `--single-child`, upstream trap | 10.259 s | 137 | mysqld_safe only (ignored) | mysqld SIGKILLed; InnoDB crash recovery | none |
| g1 | a1 with `--pid host` | 0.676 s | 0 | the service | SIGKILL by the shim's `runc kill --all` | none |
| g2 | c1 with `--pid host` | 0.179 s | 143 | bash only | same set as c1, SIGKILL ~40 ms after bash died | none |
| g6 | b1 with `--pid host` | 10.219 s | 137 | the service (ignored) | all SIGKILL at +10.10 s | none |
| g3 | `--pid host`, grandchild out of the cgroup | 0.690 s | 0 | the service | in-cgroup child SIGKILLed | **the out-of-cgroup process** |
| g4 | g3 without `--pid host` | 0.651 s | 0 | the service | both SIGKILLed | none |
| g5 | g3, survivor keeps container stdio | **30.25 s** (bounded by the test) | 0 | the service | - | until killed by hand |

## 4. Results per test

### (a) exec'd service

[out/a1/timeline.txt](out/a1/timeline.txt), [tree.txt](out/a1/tree.txt), [shim.txt](out/a1/shim.txt):

```
  +0.060 s  dumb-init(1)          takes SIGTERM (sigwait/sigtimedwait), si_pid=0 SI_USER
  +0.060 s  dumb-init(1)          calls kill(7, SIGTERM) = 0
  +0.064 s  e1-sigsvc(7)          takes SIGTERM (sigwait/sigtimedwait), si_pid=1 SI_USER
  +0.571 s  e1-sigsvc(7)          exited with 0
  +0.571 s  dumb-init(1)          reaps child pid 7 (exit 0)
  +0.575 s  dumb-init(1)          calls kill(7, SIGTERM) = -1 ESRCH
  +0.579 s  dumb-init(1)          exit_group(0)
  +0.581 s  e1-worker(18)         killed by SIGKILL
  +0.581 s  e1-daemon(20)         killed by SIGKILL
  +0.581 s  dumb-init(1)          exited with 0
shim:  +0.032 s runc kill <id> 15 ;  +0.597 s runc delete <id>
```

Process tree before the stop: `dumb-init(1) -> e1-sigsvc(7) -> e1-worker(18)`, all in process group 1 and session 1
(dumb-init `--single-child` does no `setsid`); the daemon `e1-daemon(20)` has ppid 1 and its own process group and
session (19). The service, which `kolla_start` exec'd, gets SIGTERM from dumb-init 60 ms after `docker stop` starts
and exits after its 0.5 s grace; `docker stop` returns after 0.656 s with exit code 0 (dumb-init passes on its child's
status). Neither the plain child nor the daemon receives any signal before SIGKILL, which comes the moment dumb-init
exits. The shim runs only `runc kill <id> 15` and, after the deaths, `runc delete`, so the SIGKILL is the kernel's
tearing down a PID namespace whose init has exited (an inference from the trace and the kernel's semantics: a
kernel-sent SIGKILL leaves no trace of its sender). dumb-init's "SIGTERM to any remaining
children" when its child exits (`dumb-init.c:106`) goes, in single-child mode, to the already reaped child only
(`kill(7, SIGTERM) = -1 ESRCH`, `dumb-init.c:63`).

### (b) exec'd service that ignores SIGTERM

[out/b1/timeline.txt](out/b1/timeline.txt), [shim.txt](out/b1/shim.txt), [standin.log](out/b1/standin.log): the
service logs `signal SIGTERM from pid=1 ... ignoring SIGTERM`; the shim runs `runc kill <id> 15` at +0.032 s and
`runc kill <id> 9` at +10.076 s; all four processes are `killed by SIGKILL` at +10.11 s. `docker stop` 10.194 s,
exit code 137.

### (c) the real neutron-l3-agent-wrapper.sh

c1 (`enable_neutron_agent_ha: false`), [out/c1/timeline.txt](out/c1/timeline.txt), [tree.txt](out/c1/tree.txt):

```
    PID    PPID    PGID     SID USER     COMMAND
      1       0       1       1 neutron  dumb-init --single-child -- kolla_start
      7       1       1       1 neutron  /bin/bash /usr/local/bin/neutron-l3-agent-wrapper.sh
     18       7       1       1 neutron  /usr/bin/python3 /usr/local/bin/neutron-l3-agent --config-file ...
     19      18       1       1 neutron  /usr/bin/python3 /usr/local/bin/e1-rootwrap-daemon ...
     21       1      20      20 neutron  /usr/bin/python3 /usr/local/bin/e1-keepalived ...
     23       1      22      22 neutron  /usr/bin/python3 /usr/local/bin/e1-haproxy-ns ...

  +0.060 s  dumb-init(1)                    calls kill(7, SIGTERM) = 0
  +0.064 s  neutron-l3-agent-wrapper.sh(7)  receives SIGTERM (handler or default action), si_pid=1 SI_USER
  +0.065 s  neutron-l3-agent-wrapper.sh(7)  killed by SIGTERM
  +0.069 s  dumb-init(1)                    calls kill(7, SIGTERM) = -1 ESRCH
  +0.072 s  dumb-init(1)                    exit_group(143)
  +0.072-0.074 s  neutron-l3-agent(18), e1-rootwrap-daemon(19), e1-keepalived(21), e1-haproxy-ns(23): killed by SIGKILL
```

bash has no SIGTERM handler, so the default action kills it at once; dumb-init exits with 143 and the agent, its
child and its daemonized grandchildren are SIGKILLed 7-9 ms after bash died. The agent never sees SIGTERM. `docker stop`
0.146 s, exit code 143. The SIGKILL is not "at the latest after 10 s": it comes immediately, so the agent gets no
grace time at all.

c2 (`enable_neutron_agent_ha: true`, cleanup succeeds): the stop is identical (0.151 s, 143, agent SIGKILLed, no
SIGTERM; [out/c2/timeline.txt](out/c2/timeline.txt)). The start runs the cleanup before the agent
([out/c2/standin.log](out/c2/standin.log): `neutron-netns-cleanup ... --force --agent-type l3`, `cleanup done, exit 0`,
then `neutron-l3-agent ... start`).

c3 (cleanup exits 1), [out/c3/restart-loop.txt](out/c3/restart-loop.txt): errexit ends the wrapper before the agent;
the container exits 1 and `unless-stopped` restarts it, each time running the cleanup again:

```
after 15 s: status restarting; restarts 7; last exit code 1
neutron-netns-cleanup runs: 7
neutron-l3-agent starts: 0
Running command: '/usr/local/bin/neutron-l3-agent-wrapper.sh'  at 13:14:03.86, 04.35, 04.93, 05.71, 06.89, 08.88, 12.48
```

c4 (`docker stop` during a 60 s cleanup), [out/c4/timeline.txt](out/c4/timeline.txt): bash is killed by SIGTERM at
+0.072 s and `neutron-netns-cleanup(18)` is `killed by SIGKILL at +0.085 s` with no SIGTERM; the agent never started.
A real cleanup would stop at whatever namespace it had reached. `docker stop` 0.165 s.

So with `enable_neutron_agent_ha: true` the errexit and the cleanup do not change the stop path; they matter on the
start path: the cleanup runs at every start, including every restart-policy restart, a failing cleanup keeps the agent
from starting and the container restarts in a loop, and a stop during the cleanup cuts it off without a signal it could
handle.

### (d) the real start-ovsdb-server and start-ovs (stand-in daemons)

[out/d1/timeline.txt](out/d1/timeline.txt) and [out/d2/timeline.txt](out/d2/timeline.txt): `start-ovsdb-server(7)`
and `start-ovs(7)` (bash) receive SIGTERM from dumb-init and are killed by it; `ovsdb-server(26)` and
`ovs-vswitchd(20)` (stand-ins, exactly as the templates start them) are `killed by SIGKILL` 9 ms later with no SIGTERM.
`docker stop` 0.142 s and 0.161 s, exit code 143 for both. The kolla start scripts ran unchanged
([out/d1/standin.log](out/d1/standin.log): `ovsdb-tool ... create /var/lib/openvswitch/conf.db`, then
`needs-conversion`; the `modprobe openvswitch` stub was called in d2). The real daemons would therefore not run their
SIGTERM exit path (pidfile and socket cleanup on the `/run/openvswitch` bind mount); whether that matters is for e5.

### (e) the real haproxy_run.sh with real haproxy 1.8

e1, [out/e1/tree.txt](out/e1/tree.txt), [timeline.txt](out/e1/timeline.txt), [client.txt](out/e1/client.txt),
[backend-and-syslog.txt](out/e1/backend-and-syslog.txt):

```
      1       0       1       1 root     dumb-init --single-child -- kolla_start
      6       1       1       1 root     /bin/bash -x /etc/haproxy/haproxy_run.sh
     15       6       1       1 root     xargs /usr/sbin/haproxy -W -db -p /run/haproxy.pid -f /etc/haproxy/haproxy.cfg
     17      15       1       1 root     /usr/sbin/haproxy -W -db -p /run/haproxy.pid -f ... -f .../services.d/e1_web.cfg
     18      17      18      18 haproxy  /usr/sbin/haproxy -W -db -p /run/haproxy.pid -f ... -f .../services.d/e1_web.cfg

haproxy_run.sh(6)  receives SIGTERM (handler or default action) from si_pid=1  end: killed by SIGTERM at +0.066 s
xargs(15)          signals: none   end: killed by SIGKILL at +0.077 s
haproxy(17)        signals: none   end: killed by SIGKILL at +0.078 s     (master)
haproxy(18)        signals: none   end: killed by SIGKILL at +0.079 s     (worker)

http_code=200 bytes_received=19456 curl_rc=18
curl: (18) transfer closed with 62464 bytes remaining to read
request started -4.595 s, ended +0.082 s relative to docker stop
backend: GET /slow ... write failed after 20480 bytes: [Errno 32] Broken pipe
haproxy log lines received on the syslog sink: (none)
```

The pipeline `find | xargs echo | xargs haproxy` leaves `xargs` between bash and the haproxy master. Neither haproxy
process receives SIGTERM or SIGUSR1; both are SIGKILLed about 12 ms after the stop reached bash. A client in the middle
of a 20 s download through haproxy gets 19456 of 81920 bytes and an orderly close (curl error 18; a reset would be
error 56) 82 ms after `docker stop` started; the backend sees a broken pipe; haproxy logs nothing for the request.
`docker stop` 0.151 s, exit code 143.

e2, the control that Kolla does not use (haproxy exec'd by `kolla_start`), [out/e2/timeline.txt](out/e2/timeline.txt),
[docker-logs.txt](out/e2/docker-logs.txt): the master receives SIGTERM from dumb-init, sends `kill(14, SIGTERM)` to the
worker, the worker is `killed by SIGTERM`, the master logs `Exiting Master process...`, `Current worker 14 exited with
code 143` and exits 143. The client result is the same: `bytes_received=19456 curl_rc=18`. haproxy treats SIGTERM as
an immediate stop, so exec'ing it would change the log lines, not the cut connections. Its graceful (soft) stop is
SIGUSR1 [HYPOTHESIS: haproxy documentation, not run here], which neither path sends.

### (f) MariaDB: `dumb-init --` and mysqld_safe

`mysqld_safe` in bionic's package is not upstream's. [out/f-mysqld_safe-traps.txt](out/f-mysqld_safe-traps.txt):

```
927:trap '/usr/bin/mysqladmin --defaults-extra-file=/etc/mysql/debian.cnf refresh & wait' 1 # HUP
928:trap '/usr/bin/mysqladmin --defaults-extra-file=/etc/mysql/debian.cnf shutdown' 2 3 15 # INT QUIT and TERM
```

Upstream MariaDB's `scripts/mysqld_safe.sh` (10.1 and 10.3 branches, line 41, read on GitHub, not run) has instead
`trap '' 1 2 3 15			# we shouldn't let anyone kill us`, i.e. it ignores HUP, INT, QUIT and TERM. MariaDB's own
10.3 packaging, which Ussuri's Ubuntu image installed, has no `debian/patches/series` and its `debian/rules` does not
edit `mysqld_safe` (read on GitHub; the binary package could not be downloaded), so Ussuri's image most likely shipped
the upstream line [HYPOTHESIS]. f1 and f2 use bionic's script as packaged; f3 and f4 replace the two Debian lines by
upstream's (`e1-mariadb-upstreamtrap:ussuri`). Each run: the `bootstrap_mariadb` one-shot (`KOLLA_BOOTSTRAP`,
exit 0, [out/f1/bootstrap.txt](out/f1/bootstrap.txt)), then the `mariadb` container with `config.json` command
`/usr/bin/mysqld_safe` and the rendered `galera.cnf` (**wsrep ON**, single node, `gcomm://` empty), a writer container
inserting rows over one connection, `docker stop -t 10`, then `docker start` of the same container (what `kolla_docker`
`restart_container` does). Crash recovery is read from `mysqld_safe`'s `--wsrep_recover` pass, whose log
`mysqld_safe` deletes; [recovery_capture.py](recovery_capture.py) keeps it through an open handle.

f1, kolla's entrypoint, bionic script ([timeline.txt](out/f1/timeline.txt),
[mariadb-log-stop.txt](out/f1/mariadb-log-stop.txt), [grastate-after-stop.txt](out/f1/grastate-after-stop.txt),
[wsrep-recovery-pass.txt](out/f1/wsrep-recovery-pass.txt)):

```
      1       0       1       1 mysql    dumb-init -- kolla_start
      7       1       7       7 mysql    /bin/bash /usr/bin/mysqld_safe
    237       7       7       7 mysql    /usr/sbin/mysqld --basedir=/usr ... --wsrep_on=ON --log-error=... --port=18130 ...

  +0.057 s  dumb-init(1)                 calls kill(-7, SIGTERM) = 0
  +0.054 s  mysqld(237) thread           takes SIGTERM (sigwait/sigtimedwait), si_pid=1 SI_USER
  +0.057 s  mysqld_safe(7)               receives SIGTERM (handler or default action), si_pid=1 SI_USER
  +4.768 s  mysqld(237)                  exited with 0
  +4.776 s  mysqladmin<-mysqld_safe(7)   execs /usr/bin/mysqladmin --defaults-extra-file=/etc/mysql/debian.cnf shutdown
  +4.793 s  mysqladmin<-mysqld_safe(7)   exited with 1
2026-11-17 13:15:15 ... /usr/sbin/mysqld: Normal shutdown
2026-11-17 13:15:19 ... /usr/sbin/mysqld: Shutdown complete
261117 13:15:20 mysqld_safe mysqld from pid file /var/lib/mysql/mariadb.pid ended
grastate.dat: seqno: 8234  safe_to_bootstrap: 1
restart, recovery pass: WSREP: Recovered position: ea636846-...:8234   (no InnoDB crash-recovery line)
```

Without `--single-child`, dumb-init (which made its child a session and group leader) signals the whole group
(`kill(-7, SIGTERM)`, `dumb-init.c:63`), so mysqld's signal thread takes SIGTERM from dumb-init (si_pid=1) about
55 ms in (its timestamp lands before the `kill` line: strace times of different processes are not ordered within a
few ms, §6). mysqld logs a
normal shutdown; the Debian trap runs only after mysqld has exited and its `mysqladmin` fails (exit 1: there is no
`debian.cnf` in the kolla container), which is harmless. `docker stop` 4.947 s, exit code 0; Galera saved its seqno;
the restart found nothing to recover; rows in `e1.t` after the restart: 8232 (seqno 8234 minus the CREATE DATABASE and
CREATE TABLE write-sets). The writer's in-flight statement got `ERROR 1213 (40001) ... Deadlock found`
([writer.txt](out/f1/writer.txt)).

f3, kolla's entrypoint, upstream trap: the same outcome (4.858 s, exit 0, `Normal shutdown` ... `Shutdown complete`,
seqno 8436, no crash recovery). `mysqld_safe` is shown "receiving" SIGTERM only because it is traced; it ignores it.

f2 and f4, the controls with the base image's `--single-child` ([f2/timeline.txt](out/f2/timeline.txt),
[f2/shim.txt](out/f2/shim.txt), [f2/wsrep-recovery-pass.txt](out/f2/wsrep-recovery-pass.txt), f4 likewise):

```
  +0.056 s  dumb-init(1)          calls kill(7, SIGTERM) = 0
  +0.059 s  mysqld_safe(7)        receives SIGTERM (handler or default action), si_pid=1 SI_USER
 +10.068 s  shim: runc kill <id> 9
mysqld(237)  signals: none   end: killed by SIGKILL
mariadb.log written during the stop: 0 lines;  grastate.dat: seqno: -1
restart, recovery pass:
InnoDB: Starting crash recovery from checkpoint LSN=1616927
InnoDB: 1 transaction(s) which must be rolled back or cleaned up
InnoDB: Starting final batch to recover 273 pages from redo log
```

TERM reaches only `mysqld_safe`. With bionic's trap (f2) bash defers the trap until its foreground job, mysqld, ends,
which never happens; with upstream's (f4) the signal is ignored. Either way mysqld is SIGKILLed at 10 s: `docker stop`
10.237 s and 10.259 s, exit code 137, no log line, `seqno: -1`, and InnoDB crash recovery at the next start (which
then succeeded: single node, `safe_to_bootstrap: 1`). The writer got `ERROR 2013 ... Lost connection`. This is the
situation the kolla Dockerfile comment describes, and the override avoids it with either `mysqld_safe`.

Incidental: the bootstrap container's xtrace prints the root password on a command line
(`++ mysqladmin -uroot -p<pw> shutdown`, masked in [out/f1/bootstrap.txt](out/f1/bootstrap.txt)).

### (g) `--pid host`, as nova_libvirt uses

g1 (= a1 with `--pid host`), [out/g1/tree.txt](out/g1/tree.txt), [timeline.txt](out/g1/timeline.txt),
[shim.txt](out/g1/shim.txt):

```
  11736  ...  HPPID 11710  dumb-init --single-child -- kolla_start
  11766  ...  HPPID 11710  e1-daemon --child --mode daemon        (orphan reparented to the shim, pid 11710)
dumb-init(11736)  takes SIGTERM from si_pid=11806      end: exited with 0 at +0.570 s
e1-sigsvc(11749)  takes SIGTERM from si_pid=11736      end: exited with 0 at +0.569 s
e1-worker(11764)  signals: none                        end: killed by SIGKILL at +0.604 s
e1-daemon(11766)  signals: none                        end: killed by SIGKILL at +0.605 s
shim: +0.034 s runc kill <id> 15 (pid 11806) ; +0.578 s runc kill --all <id> 9 ; +0.618 s runc delete <id>
```

g2 (= c1 with `--pid host`): same pattern: bash killed by SIGTERM at +0.065 s, shim `runc kill --all <id> 9` at
+0.077 s, agent, rootwrap child, keepalived and haproxy stand-ins `killed by SIGKILL` at +0.104-0.105 s, `docker stop`
0.179 s, exit 143 ([out/g2/timeline.txt](out/g2/timeline.txt)). g6 (= b1 with `--pid host`): shim
`runc kill <id> 9` at +10.071 s, all four processes killed at +10.100 s, `runc kill --all <id> 9` at +10.108 s
(times are those of the `runc` execs; which of the two `runc` calls delivered the SIGKILL to the non-init processes is
not resolved), `docker stop` 10.219 s, exit 137 ([out/g6/shim.txt](out/g6/shim.txt)).

So `--pid host` kills the same processes as a private PID namespace, by a different mechanism: there is no namespace
to tear down, and the containerd shim kills every process still in the container's cgroup with `runc kill --all 9`
right after the init exits (in a1, c1, b1 the shim never runs `--all`). Orphans are reparented to the shim (a child
subreaper), not to dumb-init. The leftovers die 35-40 ms after the init instead of within 1 ms.

g3 and g4 test what that mechanism implies. The stand-in service spawns `e1-qemu@escape`: a daemon that moves itself
into a cgroup `e1-escape` in every host hierarchy through the host `/sys/fs/cgroup` bind mount (nova_libvirt mounts it
rw), as systemd-machined moves QEMU into `machine.slice`. [out/g3/after-stop.txt](out/g3/after-stop.txt):

```
# 3 s after docker stop returned:
  12406  12406       1     -1  12405  12405      0 S OUT /e1-escape   /usr/bin/python3 /usr/local/bin/e1-qemu ...
9:name=systemd:/e1-escape   8:pids:/e1-escape   5:devices:/e1-escape   4:memory:/e1-escape
# parent:     1 /process_api --firecracker-init ...
# last heartbeat 1794921533.414890 vs now 1794921533.430253095
```

Under `--pid host` the out-of-cgroup process survives the stop (reparented to host PID 1, still running), while the
in-cgroup `e1-worker` is SIGKILLed by `runc kill --all`. In g4, identical but without `--pid host`, `e1-qemu(21)` is
`killed by SIGKILL at +0.581 s` with dumb-init although it was outside the cgroup: in a private PID namespace cgroup
membership does not matter ([out/g4/timeline.txt](out/g4/timeline.txt)).

g5: the same as g3, but the escaped daemon keeps the container's stdout and stderr instead of pointing them to
`/dev/null` ([out/g5/stop.txt](out/g5/stop.txt)):

```
# 30 s after 'docker stop -t 10 e1-g5' was started:
docker stop is still running (pid 13118)
fd 1 -> pipe:[308212]    fd 2 -> pipe:[308213]          (e1-qemu)
shim fd 3 -> pipe:[308212]    shim fd 15 -> pipe:[308213]
docker stop returned 0.079 s after the kill, 30.250 s after it was started
container exit code 0; finished 2026-11-17T13:19:04.678535345Z (the init exit)
```

The shim does not report the container as stopped while any process holds the container's stdio pipes, so
`docker stop` blocks, here until the test killed the process; in the first, unbounded run it was still blocked after
about 9 minutes ([out/g5-first-observation.txt](out/g5-first-observation.txt)). The container's `FinishedAt` is the
init's exit, 30 s earlier. Whether a real QEMU started by libvirtd holds libvirtd's stdio was not tested
[HYPOTHESIS: libvirt starts QEMU with stdin on /dev/null and stdout/stderr on the domain log, so it does not].

## 5. What this settles in the study

| Study statement | Verdict | Evidence |
|---|---|---|
| [annex/kolla-images.md:171-175](../../../kolla-images.md) "[HYPOTHESIS: dumb-init semantics, not in these sources] In this mode dumb-init forwards `docker stop`'s SIGTERM only to that child." | **Confirmed**, refined | a1, c1: only `kill(7, SIGTERM)`; no other process receives a signal. Refinement: when that child exits, dumb-init's SIGTERM "to any remaining children" goes to the dead child only (`= -1 ESRCH`), dumb-init exits, and every other process gets SIGKILL at once, never SIGTERM |
| [annex/kolla-images.md:173-175](../../../kolla-images.md) without `--single-child`, "the TERM signal is sent to all subprocesses" | **Refined** | f1, f3: `kill(-7, SIGTERM)`: the child's process group (`dumb-init.c:63`), not all processes; a daemon that called `setsid` (as keepalived does) would not be in it |
| [annex/kolla-images.md:176-178](../../../kolla-images.md) "`mysqld_safe` ignores SIGTERM, and without `--single-child` TERM also reaches `mysqld` [HYPOTHESIS]" | **Confirmed** for mysqld; **refined** for mysqld_safe | f1, f3: mysqld's signal thread takes SIGTERM from dumb-init, normal shutdown, no crash recovery. Upstream's `mysqld_safe` ignores TERM (f3, f4); bionic's traps it to run `mysqladmin --defaults-extra-file=/etc/mysql/debian.cnf shutdown`, which fails in the container (f1). f2, f4: with `--single-child` mysqld is SIGKILLed at 10 s and InnoDB crash-recovers, with both scripts |
| [annex/kolla-images.md:179-184](../../../kolla-images.md) "[HYPOTHESIS] The service then gets no SIGTERM and is killed when the container stops, at the latest by the SIGKILL after 10 s" | **Confirmed**, refined | c1, d1, d2, e1: no SIGTERM to the service; SIGKILL 7-13 ms after bash died, not at 10 s. The wrapper turns the 10 s grace into none |
| [annex/kolla-images.md:436-442](../../../kolla-images.md) "A cleanup failure aborts the start. [HYPOTHESIS] ... `docker stop`'s SIGTERM reaches bash, not the agent, which gets no graceful shutdown; its keepalived, haproxy and radvd children die with the container." | **Confirmed** (stand-ins) | c1, c2: agent and daemonized children SIGKILLed with no SIGTERM. c3: a failing cleanup prevents the agent and the container restarts in a loop (7 cleanup runs in 15 s, 0 agent starts) |
| [annex/kolla-images.md:509-511](../../../kolla-images.md) §6 item 12 "[HYPOTHESIS] SIGTERM goes to bash and the agent is killed without a graceful shutdown" | **Confirmed** (stand-in) | c1, c2, g2 |
| [annex/kolla-images.md:542-544](../../../kolla-images.md) §7 "dumb-init signal forwarding ... and what happens to grandchildren" | **Settled** (lab) | a1, c1, e1: grandchildren never get SIGTERM; they are SIGKILLed when dumb-init exits, whether the service was exec'd or wrapped |
| [annex/kolla-images.md:545-546](../../../kolla-images.md) §7 "The runtime killing the container's cgroup when its init exits, and how that applies under `pid_mode: host`" | **Settled** for this Docker version | Private PID namespace: the kernel kills the namespace when dumb-init exits, whatever the cgroup (a1, g4). `--pid host`: the shim runs `runc kill --all <id> 9`, which spares a process outside the container's cgroup (g1, g3). Docker 29 / containerd 2.4 only |
| [annex/kolla-images.md:383](../../../kolla-images.md) and [docs/07:139](../../../../docs/07-day2-operational-impact.md) "dnsmasq children die with the container [HYPOTHESIS]" | **Confirmed by analogy** | a1: a daemonized grandchild of an exec'd service (stand-in, not dnsmasq) is SIGKILLed when the service exits |
| [annex/kolla-images.md:388-389](../../../kolla-images.md) `start-ovsdb-server` and `start-ovs` run the daemons without `exec` | **Confirmed**, consequence measured | d1, d2: the daemons get SIGKILL, never SIGTERM (stand-ins; e5 for real OVS) |
| [annex/factsheets/A-infra-lb-ovn.md:203-206](../../../factsheets/A-infra-lb-ovn.md) "haproxy is killed when the container stops, at the latest by the SIGKILL after 10 s, and established connections are cut. NEEDS-LAB to measure." | **Confirmed**, measured | e1: haproxy master and worker SIGKILLed ~12 ms after the stop reached bash; an in-flight download truncated 82 ms after `docker stop` started. e2: exec'ing haproxy would cut it too (SIGTERM is haproxy's hard stop) |
| [docs/10:25](../../../../docs/10-technical-findings-and-open-questions.md) F3 "[HYPOTHESIS] Services started by a shell wrapper that does not `exec` them (e.g. `neutron-l3-agent`, `haproxy`) get no SIGTERM at all" | **Confirmed** | c1, e1 |
| [docs/01:355-358](../../../../docs/01-repository-architecture.md) "every `docker stop` issued through `kolla_docker` in Ussuri SIGKILLs a container still running 10 s after SIGTERM" | **Confirmed** (Docker 29) | b1, f2, f4, g6: `runc kill <id> 9` at +10.06-10.08 s, exit 137 |
| [docs/02:186-193](../../../../docs/02-openstack-component-dependencies.md) agent-spawned processes "[HYPOTHESIS] They die with the container"; "[HYPOTHESIS] If dumb-init forwards SIGTERM only to its direct child ..., the SIGTERM of `docker stop` reaches bash, not the agent" | **Confirmed** (stand-ins) | c1; respawn on start is agent behaviour, not tested |
| [docs/05:216-221](../../../../docs/05-nova-deep-dive.md) "`docker stop` ... sends SIGTERM to dumb-init and, after 10 s, SIGKILL to dumb-init" | **Confirmed** | b1, g6 shim traces: `runc kill <id> 15`, then `runc kill <id> 9` at +10.07 s |
| [docs/05:233-236](../../../../docs/05-nova-deep-dive.md) "Under `pid_mode: host` the runtime kills whatever is still in the container's cgroup when its init exits. Whether VMs survive therefore depends on QEMU's cgroup membership at stop time" | **Confirmed for the mechanism**, with a stand-in | g1, g3: `runc kill --all 9` after the init exit; an out-of-cgroup process survives. Not tested: real libvirt/QEMU/machined, cgroup v2. Q1 stays NEEDS-LAB for real VMs |
| [docs/05:258-259](../../../../docs/05-nova-deep-dive.md) "if libvirtd does not exit within 10 s of SIGTERM, it is killed with the container (SIGKILL to dumb-init, then the cgroup kill described above)" | **Confirmed** (stand-in) | g6 |
| [annex/kolla-images.md:142-144](../../../kolla-images.md) "[HYPOTHESIS] With the default restart policy `unless-stopped` ... the container then restarts in a loop" (failing `kolla_set_configs`) | **Related, not tested** | c3 shows the loop for a failure in the wrapper (exit 1, 7 starts in 15 s, growing back-off), not in `kolla_set_configs` |

New facts the study does not have yet:

1. A non-`exec` wrapper does not delay the kill until the 10 s timeout; it removes the grace period: the wrapped
   service is SIGKILLed 7-13 ms after `docker stop` kills bash (c1, d1, d2, e1).
2. haproxy exec'd would not save in-flight requests either: on SIGTERM the master hard-stops the worker (e2).
3. Bionic's MariaDB 10.1 `mysqld_safe` traps TERM instead of ignoring it; Kolla's `dumb-init --` gives a clean
   shutdown with both variants; with `--single-child` both end in SIGKILL and InnoDB crash recovery (f1-f4).
4. Under `pid_mode: host`, a process that survives the stop and still holds the container's stdout or stderr makes
   `docker stop` block until it exits (g5).
5. A stop during the HA netns cleanup kills the cleanup mid-run with SIGKILL (c4).

## 6. Caveats

- Docker 29.9.2 / containerd 2.4.2 / runc 1.5.2, cgroup v1, kernel 6.18, not the Ussuri-era Docker 19.03/20.10. The
  dumb-init and kernel parts (a-f) do not depend on it; the shim's `runc kill --all` (g) and the stdio wait (g5) were
  observed on this version only. cgroup v2 was not tested.
- Stand-ins replace neutron-l3-agent, neutron-netns-cleanup, keepalived, haproxy (metadata), rootwrap-daemon,
  ovsdb-server, ovs-vswitchd and QEMU. They show which signal a process receives, not what the real program would do
  with it. haproxy (e) and MariaDB (f) are real.
- MariaDB is bionic's 10.1.48 with galera-3 25.3.20, single node (`gcomm://` empty), 256M buffer pool; Ussuri used
  10.3 from MariaDB's repository. f3/f4 edit `mysqld_safe` to upstream's trap to stand for it. Multi-node Galera
  (`safe_to_bootstrap`, IST/SST after a SIGKILL) was not tested.
- HAProxy is bionic's 1.8.8; whether Ussuri's Ubuntu image took haproxy from bionic or from the Ubuntu Cloud Archive
  could not be checked (the Cloud Archive is unreachable). No keepalived and no VIP.
- strace is attached during every stop: it adds latency (milliseconds), it reports ignored signals as received, and
  times are strace's (entry time plus `-T` duration for blocking calls), so ordering between processes within about
  1 ms is not reliable. Durations are wall clock around the `docker stop` CLI call.
- Mounts that are not on the signal path were left out or replaced (§2.1); the neutron-base iptables alternatives
  branch was skipped because iptables is not installed.
- Each case ran once in the final run cited here. In the earlier development runs (two to four per case, partly
  with an earlier version of the analyzer) every case gave the same signals, ends and exit codes; only times varied,
  by tens of milliseconds. g3 in its first version is the exception described in g5.

## 7. Reproduce

```
cd annex/lab/realdocker/base && KOLLA_SRC=<kolla ussuri-eol> ./build.sh      # reallab/base:ussuri
cd ../e1-signals
KOLLA_SRC=<kolla ussuri-eol> KOLLA_ANSIBLE_SRC=<kolla-ansible ussuri-eol> ./run.sh [a b c d e f g]
```

Needs root on the Docker host (strace attaches to container processes and the shim), docker, python3 with jinja2,
curl, and bionic packages reachable from `docker build --network host`. Uses host ports 18110-18133 on 127.0.0.1.
Creates only `e1-*` containers, volumes, images and the `/sys/fs/cgroup/*/e1-escape` cgroups (g3-g5), and removes
all of them except the images at the end. A full run takes about 6 minutes. `work/` (build contexts, raw traces,
container logs) is scratch and is recreated by each run; `cfg/` holds the rendered templates; `out/<case>/` holds
`tree.txt`, `stop.txt`, `timeline.txt`, `shim.txt`, `strace.txt` (raw, capped), `standin.log`, `docker-logs.txt`
(trimmed) and the case-specific files cited above. [out/summary.txt](out/summary.txt) lists every case's stop line
and fate table.
