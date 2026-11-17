# e2: `kolla_set_configs` and `kolla_start` inside real containers

## Purpose

The study read kolla's base start path and ran `set_configs.py --check` only on a scratch tree, outside a container
(annex/kolla-images.md:29-31, docs/10-technical-findings-and-open-questions.md:158). This experiment runs the
unmodified kolla `ussuri-eol` base scripts (`kolla_start`, `kolla_set_configs`, `kolla_copy_cacerts`, `sudoers`) in
real Docker containers laid out the way Kolla-Ansible `ussuri-eol` lays them out, and observes:

- (a) the `--check` exit codes, as the image user and as root;
- (b) what a restart and a recreate apply;
- (c) a restart with a missing required source under `unless-stopped`;
- (d) whether xtrace writes a one-shot's password to `docker logs`;
- (e) `kolla_copy_cacerts` when custom CAs are removed;
- (f) the recursive `permissions` under `COPY_ALWAYS` and `COPY_ONCE`;
- (g) a memcached-shaped `config.json` with a changed command.

Evidence label for everything below: [LAB e2], Docker 29.9.2. Behaviour that depends on Docker itself (the restart
back-off in (c), volume copy-up) is marked as such in the caveats.

## Environment and exact versions

From [out/versions.txt](out/versions.txt):

- Docker server and client 29.9.2, runc v1.5.2, cgroup v1 (cgroupfs driver), overlayfs, kernel 6.18.44. This is
  **not** the Docker 19.03/20.10 of the Ussuri era.
- `reallab/base:ussuri` (`sha256:891f52f2…`, recipe [../base/](../base/)): `ubuntu:18.04`, `dumb-init 1.2.1-1`,
  `sudo 1.8.21p2-3ubuntu1.6`, `python3.6 3.6.9-1~18.04ubuntu1.12`, `ca-certificates 20230311ubuntu0.18.04.1`, and the
  unmodified kolla `docker/base` scripts of `ussuri-eol` (commit `9107c5f`). `ENTRYPOINT ["dumb-init",
  "--single-child", "--"]`, `CMD ["kolla_start"]`.
- Images built here, all `FROM reallab/base:ussuri` with `docker build --network host`:
  - `e2-nova-compute:ussuri` ([images/nova-compute/Dockerfile](images/nova-compute/Dockerfile)): users `nova` (42436)
    and `qemu` (42427) as kolla creates them, `configure_user(name='nova', groups='qemu')` (kolla
    `docker/macros.j2:45-59`, `docker/nova/nova-base/Dockerfile.j2:10`), so `nova` is in group `kolla`; the real
    nova-base `extend_start.sh` as `kolla_extend_start` and the real nova-compute `extend_start.sh` as
    `kolla_nova_extend_start`; `USER nova` (kolla `docker/nova/nova-compute/Dockerfile.j2:196`). The service binary
    `/usr/bin/nova-compute` is a **stand-in** that logs its user, argv and every signal and reads no configuration.
  - `e2-heat-api:ussuri` ([images/heat-api/Dockerfile](images/heat-api/Dockerfile)): user `heat` (42418) in group
    `kolla`, the real heat-base `extend_start.sh` as `kolla_extend_start` and the real heat-api `extend_start.sh` as
    `kolla_heat_extend_start`, no `USER` (root), like heat-api. `heat-manage` and `openstack` are **stand-ins** that
    never print their arguments beyond the first two words.
  - `e2-memcached:ussuri` ([images/memcached/Dockerfile](images/memcached/Dockerfile)): user `memcached` (42457),
    the **real** `memcached` binary, bionic package `1.5.6-0ubuntu1.2`, `USER memcached`. Whether the Ussuri image
    took a newer memcached from the Ubuntu Cloud Archive was not checked (the archive is unreachable here).
  - `e2-render:ussuri`: a tool image only (bionic `python3-jinja2 2.10-1ubuntu0.18.04.1`, `openssl 1.1.1`).
- Package versions that differ from an Ussuri-era build: `ca-certificates` is the 2023 bionic update, newer than
  what an Ussuri image built in 2020-2022 shipped; it matters for (e) only. No OVS, libvirt, QEMU, MariaDB or
  RabbitMQ package is used.
- Kolla-Ansible `ussuri-eol` (`8a94fe9`) templates and kolla `ussuri-eol` (`9107c5f`) start scripts are vendored
  verbatim in [vendor/](vendor/) with their SHA-256 in [vendor/SOURCES.sha256](vendor/SOURCES.sha256). `run.sh`
  verifies them against checkouts when `KOLLA_SRC` and `KA_SRC` are set (it did for the run reported here).

## Method

- **Config files.** The real templates `roles/nova-cell/templates/nova-compute.json.j2`,
  `roles/memcached/templates/memcached.json.j2` and `roles/heat/templates/heat-api.json.j2` are rendered with Jinja2
  2.10, `trim_blocks=True` and a re-implementation of Ansible's `bool` filter ([render.py](render.py)). The nova
  baseline uses the Ussuri defaults `libvirt_tls: false`, `libvirt_enable_sasl: true`
  (`roles/nova-cell/defaults/main.yml:414,431`) and a custom `policy.yaml` (`nova_policy_file` defined); it is in
  [out/rendered-nova-compute-base.json](out/rendered-nova-compute-base.json). Variants that Kolla-Ansible would get
  from other inputs (a changed `command`, `permissions`, `perm` or `owner`; a prometheus `extras/*`
  `preserve_properties` entry; a haproxy `services.d/`-style directory entry) are edits of the rendered JSON, each
  listed in [out/variants.txt](out/variants.txt). The other files (`nova.conf`, `policy.yaml`, `auth.conf`,
  `release`, `heat.conf`) are short stand-ins: `kolla_set_configs` only copies and compares them.
- **Host layout.** The config directory is owned `root:root` with mode 0770 and its files 0660
  (`group_vars/all.yml:20-21`, `roles/nova-cell/tasks/config.yml:2-13` and its 0660 template/copy tasks), and
  `ca-certificates/` holds 0644 files (`roles/service-cert-copy/tasks/main.yml:2-12`); see `fix_layout` in
  [lib.sh](lib.sh). It is bind-mounted read-only at `/var/lib/kolla/config_files/`
  (`roles/nova-cell/defaults/main.yml:284`).
- **Container parameters** (`run_nova` in [lib.sh](lib.sh)), mirrored from `roles/nova-cell/defaults/main.yml:47-57,
  283-295`, `group_vars/all.yml:134,157-168` and `library/kolla_docker.py:717-749`: `--network host`, `--ipc host`,
  `--privileged`, `--restart unless-stopped`, `KOLLA_CONFIG_STRATEGY=COPY_ALWAYS` (unless stated),
  `LIBGUESTFS_BACKEND=direct`, the config mount, `/etc/localtime` and `/etc/timezone` read-only, and named volumes for
  `kolla_logs:/var/log/kolla/`, `libvirtd:/var/lib/libvirt` and `nova_compute:/var/lib/nova/` (each prefixed
  `e2-<test>-`). Omitted on purpose: `/lib/modules`, `/run:/run:shared`, `/dev:/dev` (nothing that
  `kolla_set_configs` or the start scripts touch is under them; mounting the sandbox's `/run` and `/dev` would reach
  other experiments), `iscsi_info` and the dev-mode mount. memcached and the heat one-shot use their own roles'
  volumes (`roles/memcached/defaults/main.yml:37-40`, `roles/heat/defaults/main.yml:85-90`).
- **kolla_docker actions, mimicked with the Docker CLI** (the module itself was not run): the drift check is
  `docker exec -u root <c> /usr/local/bin/kolla_set_configs --check` (`library/kolla_docker.py:543-549`); a restart
  is `docker stop -t 10` then `docker start` of the same container (`restart_container`, `:892-904`, with the
  effective 10 s timeout of docs/10 F3); a recreate is `docker stop` + `docker rm` + `docker run` with the same
  parameters and volumes; the one-shot is a detached `docker run` + `docker wait` + `docker logs` with stdout and
  stderr split, as `start_container` reads them (`:832-836`).
- **Isolation.** Every container and volume is named `e2-…` and labelled `e2.lab=1`; cleanup removes only that
  label. Host ports used: 18211, 18212 (memcached, host network); 18235 appears only as an unused `OS_AUTH_URL`.

Run: `./run.sh [a b c d e f g]` (all by default; about 3 minutes, of which (c) takes 105 s). It builds the images,
renders the templates, runs the tests, writes [out/](out/) and removes its containers, volumes and `work/`
directory; images are kept.

## Results

### (a) `--check` exit codes in a running container

Container `e2-a-nova_compute` (USER nova). Full table: [out/a-check-exit-codes.txt](out/a-check-exit-codes.txt); the
error lines of every run: [out/a-check-raw.txt](out/a-check-raw.txt). "expected" is the annex §3.3 prediction.

| Case | expected | as `nova` | `-u root` | decisive line (root run) |
|---|---|---|---|---|
| a01 no change | 0 | 2 | 0 | (none); `sudo kolla_set_configs --check` as `nova`: rc 0 |
| a02 changed content (`nova.conf` on the host) | 1 | 2 | 1 | `The content of source file(...nova.conf) and dest file(/etc/nova/nova.conf) are not equal.` |
| a03 `perm` of the entry 0600 -> 0640 | 1 | 2 | 1 | `Dest file does not have expected perm: 0640, actual: 0600` |
| a04 `owner` of the entry nova -> root:nova | 1 | 2 | 1 | `Dest file does not have expected user: root, actual: nova` |
| a05 / a05b dest chmod 0644 / chown root inside the container | 1 | 2 | 1 | `expected perm: 0600, actual: 0644` / `expected user: nova, actual: root` |
| a06 `command` only | 0 | 2 | 0 | – |
| a07 `permissions` only | 0 | 2 | 0 | – |
| a08 / a08b dropped entry (`auth.conf` / custom policy) | 0 | 2 | 0 | – |
| a09 new optional file (`release`), alone | 2 | 2 | 2 | `Unexpected error: FileNotFoundError: [Errno 2] No such file or directory: '/etc/nova/release'` |
| a10 new optional file + an earlier entry changed (`nova.conf`) | 1 | 2 | 1 | `The content of source file(...nova.conf) ... are not equal.` |
| a10b new optional file + a later entry changed (`auth.conf`) | 2 | 2 | 2 | `FileNotFoundError: ... '/etc/nova/release'` |
| a11b optional source removed from the host (dest still in the container) | 0 | 2 | 0 | – |
| a12 / a12b `preserve_properties` entry, right after a restart / again | 1 | 2 | 1 | `Dest file does not have expected perm: None, actual: 0660` |
| a13 flat directory source (control) | 0 | 2 | 0 | – |
| a13b / a13c directory source with a subdirectory, after a restart / again | 1 | 2 | 1 | `Dest dir does not have expected perm: 0700, actual 0755` |
| a14b missing required source | 1 | 2 | 1 | `MissingRequiredSource: /var/lib/kolla/config_files/nova.conf file is not found` |
| a15 invalid JSON | 1 | 2 | 1 | `InvalidConfig: Invalid json file found at /var/lib/kolla/config_files/config.json` |

As the image user every case exits 2, before any comparison:
`PermissionError: [Errno 13] Permission denied: '/var/lib/kolla/config_files/config.json'`. In a13b the mode compared
is that of `/etc/nova` (`755 root:root /etc/nova`), while `/etc/nova/e2.d` and its subdirectory are `700 nova:nova`:
the reversed `relpath` of kolla `docker/base/set_configs.py:197-198`.

**What it settles.** Every root exit code matches the prediction; the scratch-run results now hold inside a real
container with the image's Python 3.6:

- Confirms annex/kolla-images.md:230-243 (§3.3 table and "Scratch run of the unmodified script ... rc 2 for a new
  optional file and a missing `config.json`") and its §3.1/§3.2 statements: "A directory source that contains a
  subdirectory therefore reports drift on every run" (:214), `preserve_properties` entries "report drift on every
  run" (:215-216), `command` and `permissions` are never compared (:221-224).
- Confirms annex/kolla-images.md:470-473 (§6 item 3, "`--check` exits 2 when an optional file is rendered for the
  first time ... and no entry listed before it differs"). a10b adds that an entry listed **after** the optional file
  does not help: the check stops at the first entry, so the result is still 2.
- Confirms annex/kolla-images.md:250-253 (§3.4): "a plain `docker exec <c> kolla_set_configs --check` cannot open
  them and exits 2"; `docker exec -u root` and `sudo kolla_set_configs --check` both work (a01, a01b).
- Confirms docs/10-technical-findings-and-open-questions.md:36 (F14) and :51 for the `--check` part, now [LAB e2]
  rather than only "scratch run of the real script, outside a container".

### (b) What a restart and a recreate apply (COPY_ALWAYS)

Container `e2-b-nova_compute`, [out/b-restart-applies.txt](out/b-restart-applies.txt).

- b1, `nova.conf` revision 2 and command changed on the host, then stop/start:
  `/run_command: nova-compute --e2-marker=command-v2`,
  `service process: /bin/bash /usr/bin/nova-compute --e2-marker=command-v2`,
  `nova.conf in container: # e2 stand-in nova.conf, revision 2`; `--check` rc 0 afterwards.
- b2, `config.json` re-rendered with `libvirt_enable_sasl: false` and without `nova_policy_file` (the host files stay,
  as Kolla-Ansible never deletes them), and `release` deleted on the host, then stop/start: all three destinations
  are still there and `--check` is 0:
  `nova:nova 600 /etc/nova/policy.yaml`, `nova:nova 600 /etc/nova/release`,
  `nova:nova 600 /var/lib/nova/.config/libvirt/auth.conf`, `--check as root: rc 0`. (The b2 `config.json` also has the
  original command, and `/run_command` went back to `nova-compute`: a second command change applied by a restart.)
- b3, recreate with the same volumes: `cannot stat '/etc/nova/policy.yaml': No such file or directory`,
  `cannot stat '/etc/nova/release': No such file or directory`, but
  `nova:nova 600 /var/lib/nova/.config/libvirt/auth.conf` (on the `nova_compute` volume).

**What it settles.** Confirms annex/kolla-images.md:260-268 (§3.5): a `COPY_ALWAYS` restart "re-copies the listed
entries and rewrites `/run_command`"; "Removals do not apply ... They stay in the container's writable layer until the
container is recreated; a destination on a volume survives recreates as well, e.g. nova-compute's SASL `auth.conf`";
"`--check` does not flag them". Confirms annex/kolla-images.md:474-475 (§6 item 4) and the last sentence of docs/10
F14 (:36), "A restart never removes the files of a dropped entry". Whether a service still **reads** such a file
(the Keystone policy example, annex :269-270) is service behaviour and stays [HYPOTHESIS].

### (c) Missing required source + restart under `unless-stopped`

Container `e2-c-nova_compute`, [out/c-restart-loop.txt](out/c-restart-loop.txt). `nova.conf` was moved out of the
host directory, then `docker stop -t 10` + `docker start`.

- `docker start rc=0`: the start call succeeds; the container dies about 0.1 s later in `kolla_set_configs`
  (`ERROR:__main__:MissingRequiredSource: /var/lib/kolla/config_files/nova.conf file is not found`, exit 1).
- Docker restarts it with a growing delay. `docker events` show the manual start at +0.15 s, then policy restarts at
  +0.39, 0.73, 1.26, 2.21, 3.96, 7.32, 13.86, 26.83 and 52.58 s, each followed by a die with `exitCode=1`: the gap
  from die to next start doubles from about 0.16 s to 25.7 s.
- `t=60s RestartCount=10 Status=restarting Restarting=true ExitCode=1 Policy=unless-stopped | docker ps: Restarting (1)
  7 seconds ago`; 10 `MissingRequiredSource` lines in `docker logs` (10 failed starts; the count of 10 includes the
  restart then pending).
- During the loop, the drift check cannot run: `docker exec -u root ... kolla_set_configs --check` fails with
  `Error response from daemon: Container ... is restarting, wait until the container is running` (CLI rc 1). This
  is a daemon-side client error, which `kolla_docker` treats as drift (`library/kolla_docker.py:552-558`).
- After `nova.conf` was put back at t=60 s, the container came back on its own at the next scheduled attempt:
  `service started again without operator action: yes, after 44s: RestartCount=10 Status=running`.

**What it settles.** Confirms the [HYPOTHESIS] of annex/kolla-images.md:142-144 (§2.3), "With the default restart
policy `unless-stopped` ... the container then restarts in a loop until the input is fixed", and the bracketed
"[HYPOTHESIS] restart loop" of the §3.3 exit-1 row (:235). Removes this item from annex §7 (:561). Refinements, at the
CLI level: (1) the restart itself reports success (`docker start` rc 0), so a `kolla_docker` restart of a container
with a missing required source would not fail the task [CODE `library/kolla_docker.py:892-904` + this observation;
the module was not run]; (2) once the input is fixed, recovery waits for the next back-off attempt (here 44 s; the
delay grows with every failed start).

### (d) xtrace and a one-shot's password

One-shot `e2-d-bootstrap_heat`, started like `roles/heat/tasks/bootstrap_service.yml:2-29` (`KOLLA_BOOTSTRAP=` empty,
`--restart no`, label `BOOTSTRAP`) with `HEAT_DOMAIN_ADMIN_PASSWORD=s3cr3t` and `OS_PASSWORD=e2-admin-pw`. The image
runs the real kolla heat scripts, so the command is kolla `docker/heat/heat-api/extend_start.sh:12` itself (the task's
`SOME_PASSWORD` is this variable). [out/d-xtrace-password.txt](out/d-xtrace-password.txt):

```
container exit code: 0
lines containing 's3cr3t' in docker logs stderr: 1
lines containing 's3cr3t' in docker logs stdout: 0
lines containing 'e2-admin-pw' (OS_PASSWORD, environment only) in stdout+stderr: 0
  ++ . /usr/local/bin/kolla_heat_extend_start
  +++ [[ -n 0 ]]
  +++ heat-manage db_sync
  +++ openstack user create --domain heat_user_domain heat_domain_admin --password s3cr3t
  +++ exit 0
```

**What it settles.** Confirms annex/kolla-images.md:87-91 (§2.2 item 1): xtrace "also echoes each command of that
script, and of the `kolla_<service>_extend_start` it sources ... to stderr with its variables expanded ... heat's
`--password ${HEAT_DOMAIN_ADMIN_PASSWORD}`", now in a real container ([LAB e2] instead of "checked in bash"). A
secret passed only through the environment (`OS_PASSWORD`) is not echoed. The value is also in the container's
`Config.Env` (`docker inspect`), independently of xtrace. Not tested: what Ansible prints. `kolla_docker` returns
that stderr in its result and removes the one-shot afterwards (`remove_on_exit` default true,
`library/kolla_docker.py:832-839,992`), so after a real run the text survives in the task result, not in
`docker logs`.

### (e) `kolla_copy_cacerts` when custom CAs are removed

Container `e2-e-nova_compute` (USER nova, the script runs through `sudo`), two throw-away self-signed CAs,
[out/e-cacerts.txt](out/e-cacerts.txt). "verify" is `openssl verify` of the CA itself against the bundle file
(`-CAfile /etc/ssl/certs/ca-certificates.crt -no-CApath`) and against the hashed directory
(`-CApath /etc/ssl/certs -no-CAfile`); error 18 means not trusted. `5951f13c.0` is the subject-hash link of ca1.

| Step | bundle has ca1 / ca2 | verify ca1 file / dir | update-ca-certificates output |
|---|---|---|---|
| e1 start with ca1 | 1 / 0 | OK / OK | `1 added, 0 removed` |
| e2 ca1 removed on the host (dir empty), restart | **1** / 0 | **OK** / error 18 | (not run) |
| e2b same, recreate | 0 / 0 | error 18 / error 18 | (not run) |
| e3 ca1 + ca2, restart | 1 / 1 | OK / OK | `2 added, 0 removed` |
| e4 ca2 removed, ca1 kept, restart | 1 / **0** | ca2: error 18 / error 18 | `0 added, 0 removed` |
| e5 whole `ca-certificates/` removed, restart | **1** / 0 | **OK** / error 18 | (not run) |

In e2 the copy in `/usr/local/share/ca-certificates` is gone, and `/etc/ssl/certs/kolla-customca-ca1.pem` and its
hash link are left dangling: `dangling symlinks in /etc/ssl/certs: [/etc/ssl/certs/kolla-customca-ca1.pem
/etc/ssl/certs/5951f13c.0 ]`. In e4 `update-ca-certificates` rebuilds the bundle from the remaining sources, so ca2
leaves the bundle although it reports `0 removed`, and the ca2 links stay dangling (this version removes orphan
links only when something was added or removed, `/usr/sbin/update-ca-certificates` in the image).

**What it settles.** Confirms the [HYPOTHESIS] of annex/kolla-images.md:150-152 (§2.4), "When the last custom CA is
removed, the generated trust bundle in the container layer therefore keeps it until the container is recreated",
and of :274-275 (§3.5) and :478 (§6 item 4), "the generated bundle probably keeps it". Removes it from annex §7
(:561-562). Refinements: the stale CA stays trusted only by clients that read the bundle file; lookups through the
hashed directory no longer find it. Removing one CA while another remains does remove it from the bundle. Which
OpenStack clients read the file and which the directory was not tested and stays [HYPOTHESIS].

### (f) `permissions` with `recurse` on every start

[out/f-permissions-recurse.txt](out/f-permissions-recurse.txt). After the first start, 5000 files plus a probe under
`/var/lib/nova/instances` and a probe log in `/var/log/kolla/nova` were chowned to `root:root` inside the container
(5007 entries under `/var/lib/nova`, 3 under `/var/log/kolla/nova`). `kolla_set_configs` logs one
`Setting permission for <path>` line per `set_perms` call (kolla `docker/base/set_configs.py:354`).

- `COPY_ALWAYS`, restart: `Setting-permission lines: /var/lib/nova 5008, /var/log/kolla/nova 3`, i.e. one call per
  entry walked (5007) plus one for the copied `auth.conf`; the probes are back to `nova:nova`. A further restart with
  nothing changed: again `/var/lib/nova 5008, /var/log/kolla/nova 3`. `--check` is 0 while the probes are
  `root:root` (permissions are not compared).
- `COPY_ONCE`, restart of the same container: `Setting-permission lines: /var/lib/nova 0, /var/log/kolla/nova 0`,
  `ERROR:__main__:ImmutableConfig: The config strategy prevents copying new configs` (exit 0, `kolla_start` goes on),
  the probes stay `root:root`, and `/run_command` keeps `nova-compute` although `config.json` now has another command.
- Lab timing only: the `/var/lib/nova` walk took 135-187 ms in the log timestamps across runs for 5007 entries on an
  overlayfs-backed named volume, with per-entry logging to Docker's json-file driver. Not a production figure.

**What it settles.** Confirms annex/kolla-images.md:139-140 (§2.3, "one unconditional `os.chown` per entry") and
:501-503 (§6 item 10, "one `chown` per file ... on every `COPY_ALWAYS` start"), and annex/kolla-images.md:116-118
(§2.3, under `COPY_ONCE` "nothing is copied, permissions are not re-applied and `/run_command` keeps its first
value"). Such a second start of the same container happens through the restart policy, a Docker or host restart, or
a manual restart; `kolla_docker` itself always recreates under `COPY_ONCE` (annex :276-277). The cost on large or
NFS-backed trees (annex §7) is not settled by this small, local measurement.

### (g) Empty `config_files` and a changed command (memcached)

Container `e2-g-memcached`, real memcached, rendered `memcached.json.j2`,
[out/g-memcached-command.txt](out/g-memcached-command.txt):

```
## g2 host config.json changed to v2.json: "command": "/usr/bin/memcached -v -l 127.0.0.1 -p 18212 -c 5000 -U 0 -m 128",
  --check as root: rc 0 (INFO:__main__:Validating config file)
## g2 container still running the old command (no restart yet)
  process: memcach+ /usr/bin/memcached -v -l 127.0.0.1 -p 18211 -c 5000 -U 0 -m 64
## g3 after a plain restart (docker stop -t 10 + docker start)
  process: memcach+ /usr/bin/memcached -v -l 127.0.0.1 -p 18212 -c 5000 -U 0 -m 128
  port 18211: port 18211: [Errno 111] Connection refused | port 18212: pid 7 limit_maxbytes 134217728
```

**What it settles.** Confirms annex/kolla-images.md:221-223 (§3.2, a manifest with `"config_files": []`, "like
memcached's ... always returns 0") and the mechanism of §6 item 1 (:459-464): `--check` never sees the change, and a
plain restart for any reason applies it. That `deploy-containers` then skips the restart is the `kolla_docker`
decision logic (`library/kolla_docker.py:566-567`), not re-run here.

## Summary against the study

| Study statement | Result |
|---|---|
| annex/kolla-images.md:230-243 (§3.3 exit codes, scratch run) | confirmed in a real container (a) |
| annex/kolla-images.md:214-216, :221-224 (§3.1 drift on every run; §3.2 never compared) | confirmed (a, g) |
| annex/kolla-images.md:250-253 (§3.4: as the service user `--check` exits 2) | confirmed (a) |
| annex/kolla-images.md:470-473 (§6 item 3, new optional file exits 2) | confirmed; an entry listed after it does not change the result (a10b) |
| annex/kolla-images.md:260-268, :474-475; docs/10:36 (restart applies changes, never removals; volume survives recreate) | confirmed (b) |
| annex/kolla-images.md:142-144, :235, :561 (restart loop, [HYPOTHESIS]) | confirmed (c); restart call itself succeeds; recovery waits for the back-off |
| annex/kolla-images.md:87-91 (xtrace echoes the expanded password) | confirmed (d) |
| annex/kolla-images.md:150-152, :274-275, :478, :561-562 (bundle keeps the last CA, [HYPOTHESIS]) | confirmed (e); only for bundle-file readers; a non-last CA is removed |
| annex/kolla-images.md:116-118, :139-140, :501-503 (recurse chown every start; COPY_ONCE second start) | confirmed (f) |
| annex/kolla-images.md:459-464 (§6 item 1, memcached command change) | confirmed for the image side (g) |
| docs/10-technical-findings-and-open-questions.md:158 ("exercised standalone on a scratch tree, outside a container") | can now add [LAB e2]: run inside real containers |

## Caveats

- **Docker version.** Docker 29.9.2 / runc 1.5.2, not Docker 19.03/20.10. The `kolla_set_configs`,
  `kolla_copy_cacerts` and xtrace results do not depend on Docker. Docker-dependent: the restart back-off in (c)
  (timings and the observed doubling are this daemon's), the `docker exec` error text for a restarting container, the
  copy-up of image content into new named volumes (used for `/var/log/kolla` and `/var/lib/nova` ownership), and the
  `docker logs` stdout/stderr split.
- **Stand-ins.** nova-compute, heat-manage and openstack are stand-ins; the config files are short stand-ins, not
  rendered `nova.conf`/`heat.conf`. memcached is real. No service behaviour (does nova read a stale policy file, does
  a client trust a stale CA) was observed.
- **kolla_docker and Ansible were not run.** Their calls were reproduced with the Docker CLI; what the module or
  Ansible would report (task failure, printed stderr) is from source only.
- **Rendering.** Jinja2 2.10 with Ansible-like settings, not Ansible's template module. Several variants are JSON
  edits, listed in [out/variants.txt](out/variants.txt).
- **Images.** Built from `reallab/base:ussuri`, not by kolla-build: only the users needed are created, and the
  `/run`, `/dev` and `/lib/modules` mounts of `nova_compute` are omitted (see Method). `ca-certificates` is the 2023
  bionic update.
- **Timing.** The 44 s recovery in (c) and the 135-187 ms walk in (f) are lab measurements in this sandbox only.

## Files

- [run.sh](run.sh), [lib.sh](lib.sh), [tests/](tests/) `a.sh` … `g.sh`, [render.py](render.py), [images/](images/),
  [vendor/](vendor/).
- [out/](out/): `versions.txt`, `variants.txt`, `rendered-nova-compute-base.json`, and one file per test
  (`a-check-exit-codes.txt`, `a-check-raw.txt`, `b-restart-applies.txt`, `c-restart-loop.txt`,
  `d-xtrace-password.txt`, `e-cacerts.txt`, `f-permissions-recurse.txt`, `g-memcached-command.txt`).
