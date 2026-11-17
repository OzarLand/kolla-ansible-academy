# Factsheet E: Host bootstrap and the operational playbooks (Kolla-Ansible `ussuri-eol`)

Source: `kolla-ansible` at tag `ussuri-eol` (HEAD `8a94fe9`). All paths below are relative to the repo root.
The Ansible behaviour claims were checked against the **Ansible 2.9.27** module source in the
scratchpad venv (`venv-ansible/lib/python3.8/site-packages/ansible/...`). Ussuri pins Ansible to
2.8–2.9 (`tools/kolla-ansible:58-65`, `test-requirements.txt:16`, `ansible/roles/prechecks/vars/main.yml:4-5`).

Labels: **FACT** = read directly from code. **HYPOTHESIS** = inferred from code or from known Docker, systemd or Galera behaviour, not run. **NEEDS-LAB** = needs an experiment to confirm.

---

## 0. Most important findings

1. **When Docker restarts.** `bootstrap-servers` restarts the Docker daemon only through one task,
   `post-install.yml:231-237`, gated by `docker_configured.changed or docker_reloaded.changed`.
   In Ansible 2.8–2.9, `docker_reloaded` (a `systemd: daemon_reload: yes` task) **never reports changed**
   (Ansible `systemd.py:380-391` runs `daemon-reload` but never sets `changed`). **In practice, Docker restarts if and only if the
   rendered `/etc/docker/daemon.json` content differs** (`post-install.yml:139-145`).
   The restart is a plain task, not a handler. It runs at the same moment on every host in the batch, and the batch is all hosts by
   default: `kolla_serial` defaults to `0` (`kolla-host.yml:6`) and the CLI never passes it for `bootstrap-servers`.
2. **The systemd drop-in is never applied.** `docker_custom_option` is written to `/etc/systemd/system/docker.service.d/kolla.conf`.
   Adding, changing or removing it does **not** restart Docker (`post-install.yml:147-180`, the template is not registered, and the
   daemon-reload never reports changed). The new flags therefore take effect at the next unrelated Docker restart or reboot.
3. **Docker is masked on Debian/Ubuntu during every run.** On every run, `install.yml:54-69` symlinks
   `/etc/systemd/system/docker.service -> /dev/null` whenever that file does not exist. That is the normal state on a host that
   has already been bootstrapped. The unit is unmasked only at `post-install.yml:224-229`. If the run fails or is interrupted in
   between (package installs, PyPI pip installs, package removals, user creation, daemon.json), **docker stays masked and will not
   start at the next reboot**. HYPOTHESIS, high confidence. NEEDS-LAB.
4. **`/etc/hosts` lists every host.** The block loops over **all `groups['baremetal']` hosts** (`pre-install.yml:25-42`). So:
   (a) adding one host changes `/etc/hosts` on every host that bootstrap-servers runs on;
   (b) every baremetal host's facts are required, and an unreachable or fact-less host makes
   `kolla_address` raise on **every** host (`kolla_ansible/kolla_address.py:88-95`), which aborts the run (HYPOTHESIS, NEEDS-LAB);
   (c) the per-run template work is O(N) per host, O(N²) in total.
5. **Fact gathering with `--limit` is serial per limited host.** With `--limit` covering L of N hosts, the second play of
   `gather-facts.yml` makes each limited host loop over about N/L other hosts **in sequence**
   (`gather-facts.yml:34-49`). With `--limit one-compute` on a 1000-host inventory, one worker runs about 999 `setup` calls one
   after another. Fact caching (documented in `doc/source/user/ansible-tuning.rst:34-63`) is the only way to avoid this.
6. **Re-running `bootstrap-servers` changes the host.** It disables ufw/firewalld (`install.yml:9-38`, default
   `disable_firewall: True`), sets SELinux permissive (`post-install.yml:289-296`), unloads AppArmor profiles, **removes host
   packages** `open-iscsi`/`iscsi-initiator-utils`, `libvirt*`, `lxd`/`lxc` and `chrony` (`install.yml:150-162`,
   `defaults/main.yml:62-73`), and runs `apt-get update` twice (Debian). None of this restarts containers. But it is not a
   no-op on a hardened production host.
7. **`kolla_serial` reaches only some commands.** The CLI injects `-e kolla_serial=${ANSIBLE_SERIAL}` **only for `upgrade` and
   `reconfigure`** (`tools/kolla-ansible:430,439`). It does this *after* user `-e` options, so a user `-e kolla_serial=30%` is
   **silently overridden to `0`** for those two commands. You must set the environment variable `ANSIBLE_SERIAL`. For
   `bootstrap-servers`, `deploy`, `prune-images` and the others, `-e kolla_serial=...` does work (as the docs suggest:
   `bootstrap-servers.rst:83`).
8. **CLI bugs.** `--ask-vault-pass` overwrites `VERBOSITY` with `$EXTRA_OPTS --ask-vault-pass` (`tools/kolla-ansible:320-323`).
   This drops earlier `-v` flags and duplicates the extra options given so far. `--include-dev` is declared as taking an argument
   (`include-dev:` at `:216`) but is handled as a flag (`:284-287`). `$CMD` is run unquoted (`:116`), so it is word-split and
   glob-expanded.
9. **No `ansible.cfg` is shipped for users.** The only ones are the CI template `tests/templates/ansible.cfg.j2` and a vagrant
   heredoc. The docs recommend pipelining, `forks` (20 in the tuning guide, 100 in the quickstart), `gathering = smart` with jsonfile
   fact caching, `inject_facts_as_vars = False`, `kolla_ansible_setup_filter: "ansible_[!qt]*"` and
   `kolla_ansible_setup_gather_subset`. **They say nothing about ControlPersist, mitogen, strategy or `serial` for scale**
   (grep is empty).
10. **`destroy` acts on `hosts: all`, including the deploy host** (`localhost` is in `[deployment]`, `ansible/inventory/multinode:32-33`).
    `tools/cleanup-host` deletes **every** network namespace and every link whose line matches `tap`, `brq` or `vxlan`, and
    `rm -rf`s `/etc/kolla/*` except six names (`tools/cleanup-host:5-23,76-95`). `prune-images` removes **only dangling**
    kolla-labelled images (`docker_prune` default, `prune_images.yml:4-8`), so old release tags are not reclaimed.

---

## 1. `ansible/kolla-host.yml` (the `bootstrap-servers` command)

```yaml
# ansible/kolla-host.yml:1-10
- import_playbook: gather-facts.yml
- name: Apply role baremetal
  hosts: baremetal
  serial: '{{ kolla_serial|default("0") }}'
  gather_facts: false
  roles:
    - { role: baremetal, tags: baremetal }
```

- FACT: the CLI maps `bootstrap-servers` to `kolla-host.yml` with `-e kolla_action=bootstrap-servers` (`tools/kolla-ansible:397-401`).
  `baremetal/tasks/main.yml:2` runs `include_tasks: "{{ kolla_action }}.yml"`, which resolves to `bootstrap-servers.yml`. That file
  runs pre-install, then install, then post-install, then optionally Zun containerd (`bootstrap-servers.yml:1-11`).
- FACT: the target is `hosts: baremetal`, which in the sample inventories is control, network, compute, storage and monitoring
  (`ansible/inventory/multinode:35-40`). The deploy host (`[deployment]`) is **not** bootstrapped.
- FACT: there are no task-level tags inside the role. `--tags` can only select `baremetal` plus the `always`-tagged gather-facts
  plays. A subset of bootstrap tasks cannot be chosen with tags.
- FACT: the default `serial` is `"0"`, meaning one batch of all hosts. Parallelism is limited only by `--forks`.
- FACT: `kolla-host.yml` does **not** run the "Check CentOS variant" slurp (`site.yml:97-105`). That is irrelevant here because
  no images are used.
- CI coverage: `bootstrap-servers` runs **once, on fresh hosts** (`tests/setup_gate.sh:113`). Re-running it against a live
  deployment is **not exercised in CI**, so every re-run hazard below is NEEDS-LAB.

### 1.1 Task-by-task: `pre-install.yml`

| Lines | Task | Change made | Scale | Safe to re-run on a prod host with VMs? |
|---|---|---|---|---|
| 2-9 | Ensure `127.0.0.1 localhost` (lineinfile, regexp `^127.0.0.1.*`) | Replaces the **last** `127.0.0.1` line with exactly `127.0.0.1 localhost` | per host, O(1) | Yes. It may strip extra aliases from a hand-edited 127.0.0.1 line. |
| 17-23 | Remove `127.0.1.1 ... <hostname>` line | Deletes the Ubuntu-style hostname→127.0.1.1 mapping (RabbitMQ bug refs in comment, lines 11-16) | per host | Yes |
| 25-42 | **Generate /etc/hosts for all of the nodes** (blockinfile `# {mark} ANSIBLE GENERATED HOSTS`) | One line per **every host in `groups['baremetal']`**: `<api addr> <nodename> <hostname>` | **O(N) lines per host, O(N²) Jinja/hostvars work in total**. Needs facts of all N hosts. | Yes (no restart is attached). But see §3. |
| 44-51 | sysctl `net.ipv4.ping_group_range=0 2147483647` (RedHat only) into `kolla_sysctl_conf_path` | Writes the file and reloads sysctl when changed | per host | Yes |
| 57-71 | If `/etc/cloud/cloud.cfg` exists, write `/etc/cloud/cloud.cfg.d/99-kolla.cfg` = `manage_etc_hosts: false` | Stops cloud-init from rewriting /etc/hosts at boot | per host | Yes |
| 73-77 | Ensure group `sudo` | | per host | Yes |
| 79-84 | Ensure group `kolla_group` (default `kolla`) when `create_kolla_user` | | per host | Yes |
| 86-122 (Debian, `enable_docker_repo`) | `apt update_cache` (88-91); `ca-certificates`, `apt-transport-https`, `gnupg` **`state: latest`** (93-101); apt_key from `download.docker.com` (110-115); apt repo `deb https://download.docker.com/linux/<distro> <release> stable` (117-121) | Upgrades those 3 packages on **every** run. Needs network access to the Docker repo. | per host. N hosts hit mirrors at once (bounded by forks). | Mostly yes. Upgrading `ca-certificates` and `gnupg` is low risk. Fails without internet or proxy. |
| 124-159 (RedHat) | yum repo `docker` (132-139), `module_hotfixes = True` (145-151), rpm_key (153-158) | Repo config | per host | Yes |

Defaults: `enable_docker_repo: true`, `customize_etc_hosts: True`, `create_kolla_user: True` (`ansible/roles/baremetal/defaults/main.yml:3,19,21`).

### 1.2 Task-by-task: `install.yml`

| Lines | Task | Notes, scale, re-run safety |
|---|---|---|
| 2-6 | `apt update_cache` (Debian) | This is the **second** `apt-get update` per run on Debian (the first is pre-install.yml:88-91). No `cache_valid_time`. |
| 9-38 | **Firewall** (`when: disable_firewall`, default `True`, `defaults/main.yml:34`): `ufw state=disabled policy=allow` (Debian, `ignore_errors`), `rpm -q firewalld`, then **stop and disable firewalld** (RedHat) | **Silently removes any host firewall an operator added since the last run.** Per host. Containers are not restarted. |
| 43-49 | `docker ps -f status=running -q` → `running_containers` | Snapshot taken before package changes |
| 54-57 | stat `/etc/systemd/system/docker.service` | `stat` does not follow symlinks by default |
| **59-69** | **Mask docker (symlink to /dev/null) on Debian/Ubuntu when that file does not exist** | Intended to stop apt from auto-starting docker on first install (comment 51-52). It also fires on **every re-run**, because the unmask (post-install 224-229) deletes the symlink again. See §2.3. |
| 71-77 / 87-94 | Install `debian_pkg_install` / `redhat_pkg_install` with **`state: present`** (RedHat also `update_cache: yes`) | **An already-installed `docker-ce` is NOT upgraded** (`present`, not `latest`). Lists: `defaults/main.yml:43-60` (docker-ce, git, python3-setuptools, python3-pip, python3-virtualenv if `virtualenv`, ntp if `enable_host_ntp`, sg3-utils-udev if `enable_multipathd`, iptables if `not docker_disable_default_iptables_rules`; RedHat adds `sudo`). A Docker upgrade only happens if `docker_apt_package`/`docker_yum_package` is changed to a pinned version, or on a first install or migration from legacy docker (doc: `bootstrap-servers.rst:64-67,90-93`). |
| 79-85 | Install `drpm` (RedHat, `update_cache: yes`) | Refreshes the metadata cache each run |
| 99-127 | If the install result changed **and** containers were running: `systemd docker started/enabled/unmasked`, wait for `docker info` (6×10 s), then `docker start <previously running IDs>` | Recovery path after a package change. `docker start` on running containers is a no-op. |
| 129-137 | `pip>19.3` into `virtualenv` (only if `virtualenv` is set; default unset, `defaults/main.yml:77`) | Needs PyPI |
| 139-148 | **Docker SDK** `docker>=2.4.2,<5.0.0` via `pip3` (or into the venv) | `state` defaults to present, so no change if a matching version is installed. Needs PyPI if not. Per host. |
| 150-162 | **Remove packages** (`state: absent`): Ubuntu `lxd, lxc, libvirt-bin, open-iscsi, chrony` (chrony only if `enable_chrony`); RedHat `libvirt, libvirt-daemon, iscsi-initiator-utils, chrony` (`defaults/main.yml:62-73`) | `enable_chrony` defaults to `yes` (`group_vars/all.yml:597`), so **host chrony is removed** in favour of the chrony container. **A host that uses host-level iSCSI (for example boot-from-SAN, or a storage agent) loses `open-iscsi`/`iscsi-initiator-utils`.** Re-running is a no-op only if the packages are already gone. |

### 1.3 Task-by-task: `post-install.yml`

| Lines | Task | Notes |
|---|---|---|
| 2-10 | user `kolla` (group `kolla`, `groups: sudo`, append) | `create_kolla_user` (default True) |
| 12-17 | `authorized_key` from `kolla_ssh_key.public_key` (passwords.yml) | Rotating that key in passwords.yml adds a key; the old one is **not** removed |
| 19-28 | `/etc/sudoers.d/kolla-ansible-users`: `kolla ALL=(ALL) NOPASSWD: ALL` | |
| 30-38 | `chown -R` the virtualenv (if set) | Cost is O(files in venv) per run |
| 40-56 | `node_config_directory` (`/etc/kolla`) owned by kolla:kolla, mode 0755 | |
| 58-62 | `/etc/docker` dir | |
| 64-137 | **Build `docker_config` dict** (see §2.1) | set_fact only |
| **139-145** | **Write `/etc/docker/daemon.json`** (`copy content: docker_config | to_nice_json`), `register: docker_configured` | **The only effective trigger of a Docker restart** |
| 147-154 | Remove `/etc/systemd/system/docker.service.d/kolla.conf` when `docker_custom_option` is empty and not a Zun compute | Not registered, so it **does not restart docker** |
| 156-173 | Create the drop-in dir, then template `kolla.conf` (`templates/docker_systemd_service.j2`: overrides `ExecStart=/usr/bin/dockerd -H fd:// --containerd=... {{ docker_custom_option }} {{ docker_zun_options }}`) | Not registered, so it **does not restart docker** |
| 175-180 | `systemd: name=docker daemon_reload=yes`, `register: docker_reloaded` | In Ansible 2.9, `changed` is always **False** here (§2.2) |
| 182-193 | Ubuntu: if `/etc/apparmor.d/usr.sbin.libvirtd` exists, `apparmor_parser -R` it | No `changed_when`, so it runs every time the file exists. NEEDS-LAB: does `apparmor_parser -R` fail when the profile is already unloaded? (The file is not deleted, so a 2nd run before reboot may hit this.) |
| 195-209 | Debian + `enable_chrony`: same for `usr.sbin.chronyd` | Same caveat |
| 211-222 | group `docker`; add `kolla` to it | |
| 224-229 | **`systemd docker state=started masked=no`** | **Unmasks** docker (§2.3). `started` does not restart a running daemon. |
| **231-237** | **`systemd docker state=restarted` when `docker_configured.changed or docker_reloaded.changed`** | A **task, not a handler**. Runs at this point on all hosts in the batch. |
| 239-244 | enable docker | |
| 246-287 | `enable_host_ntp` (default **False**, `defaults/main.yml:27`): stop ntp/ntpd, then **`ntpd -gq` (one-shot clock step, no `changed_when`, runs every time)**, then start and enable ntp | With `enable_host_ntp: true`, every re-run **steps the clock** on every host. That is risky for Galera and RabbitMQ (HYPOTHESIS). It also conflicts with the default `enable_chrony: yes` container. |
| 289-296 | `selinux: policy=targeted state={{ selinux_state }}` (default `permissive`, `change_selinux: True`) on RedHat | Runtime `setenforce` plus config. No reboot is done by the role. |

`configure-containerd-for-zun.yml` (only `containerd_configure_for_zun` **and** host in `zun-cni-daemon`, `bootstrap-servers.yml:8-11`):
it writes the CNI config and script and **overwrites `/etc/containerd/config.toml`** with only `[grpc] gid = ...`
(`templates/containerd_config.toml.j2:1-2`). It **restarts containerd** when either file changed (`configure-containerd-for-zun.yml:45-50`).
HYPOTHESIS: container shims survive a containerd restart. NEEDS-LAB.

Kernel modules: the baremetal role loads **none**. Modules and sysctls are applied during `deploy`/`reconfigure` by
`config-host.yml` in service roles (`openvswitch`, `neutron`, `nova-cell`, `iscsi`, `haproxy`, `multipathd`, `ironic`, and the
`module-load` role).

---

## 2. Docker daemon configuration and restart: the exact trigger

### 2.1 What goes into `/etc/docker/daemon.json`

Base dict (`ansible/roles/baremetal/vars/main.yml:2-5`): `log-opts: {max-file: docker_log_max_file, max-size: docker_log_max_size}`
(defaults `"5"` / `"50m"`, `group_vars/all.yml:130-131`). Keys merged in by `post-install.yml`:

| Key | Source / condition | Default | Line |
|---|---|---|---|
| `cluster-store: etcd://<every etcd host>:2379,...` (Zun) | `docker_configure_for_zun` **and** host in `zun-compute` | off | 64-69; value `group_vars/all.yml:142-143` loops over `groups['etcd']` |
| `insecure-registries: [docker_registry]` | `docker_registry_insecure` = **`yes` whenever `docker_registry` is set** | follows registry | 77-82; `all.yml:119` |
| `storage-driver` | `docker_storage_driver` non-empty | `""` | 84-87 |
| `data-root` | `docker_runtime_directory` non-empty | `""` | 89-92; `all.yml:120` |
| `iptables: false` | `docker_disable_default_iptables_rules` | `"no"` (warning says the default flips in Wallaby, lines 94-100) | 102-105; `all.yml:125` |
| `bridge: none` | `docker_disable_default_network` | `"no"` | 116-119; `all.yml:126` |
| `ip-forward: false` | `docker_disable_ip_forward` | `"no"` | 130-133; `all.yml:127` |
| anything | `docker_custom_config` (dict) | `{}` | 135-137; `defaults/main.yml:38` |

FACT: the file is rendered with Ansible's `to_nice_json`, which uses `sort_keys=True` (Ansible 2.9 `plugins/filter/core.py:81-84`),
so key order is stable and does not cause spurious changes. FACT: `copy content:` **overwrites the whole file**. Any key added by
hand (for example `"live-restore": true` added outside `docker_custom_config`) is **removed**, and that removal itself triggers a
restart.

### 2.2 Why `docker_reloaded` never triggers a restart

```python
# ansible 2.9.27 modules/system/systemd.py:380-391
result = dict(name=unit, changed=False, status=dict())
# Run daemon-reload first, if requested
if module.params['daemon_reload'] and not module.check_mode:
    (rc, out, err) = module.run_command("%s daemon-reload" % (systemctl))
    if rc != 0: module.fail_json(...)
```
`changed` is set to True only by the `masked`, `enabled` and `state` branches (lines 472/515/547). The task at `post-install.yml:175-180`
passes only `name` and `daemon_reload`, so `docker_reloaded.changed` is always False. (Verified on Ansible 2.9.27. 2.8 is
assumed to behave the same: NEEDS-LAB if you run 2.8.)

**Conclusion (FACT for Ansible 2.9):** during `bootstrap-servers`, the Docker daemon restarts **only** when the rendered
daemon.json differs from the file on disk. Triggers:
- first bootstrap of a host (the file does not exist yet), or any hand-edited daemon.json;
- changing `docker_registry` (because `insecure-registries` follows it automatically), `docker_registry_insecure`,
  `docker_log_max_file`, `docker_log_max_size`, `docker_storage_driver`, `docker_runtime_directory`,
  `docker_disable_default_iptables_rules`, `docker_disable_default_network`, `docker_disable_ip_forward` or `docker_custom_config`;
- on **Zun compute hosts** with `docker_configure_for_zun`: **adding or removing an etcd host** (changes `cluster-store`);
- a **package change** does not trigger the restart task by itself. A docker-ce package upgrade restarts the daemon through the
  package scripts. Kolla then runs `docker start` on previously running containers (`install.yml:99-127`).

**Not** triggers (latent changes): adding, changing or removing `docker_custom_option`, and the Zun `docker_zun_options` systemd
drop-in (`post-install.yml:147-173`). These are written to disk and daemon-reloaded but not applied until the next restart or
reboot. HYPOTHESIS: if the same option ends up both as a dockerd flag in the drop-in and in daemon.json, dockerd refuses to start
at that later restart. NEEDS-LAB.

### 2.3 The Debian/Ubuntu mask window

Sequence per run on Debian/Ubuntu:
`install.yml:59-69` mask (symlink created, because after a previous run's unmask the file is absent again), then package and pip
work, then `post-install.yml:175-180` daemon-reload (systemd now sees docker as *masked*, but it keeps running), then
`post-install.yml:224-229` `masked: no` (the symlink is removed).
HYPOTHESIS (high confidence; NEEDS-LAB): a failure anywhere between those points leaves `docker.service` masked. The running
daemon is not affected, but **after the next reboot Docker, and therefore every Kolla container and VM on that host, will not
start** until someone runs `systemctl unmask docker`. Check after any failed run:
`ls -l /etc/systemd/system/docker.service` should **not** point to `/dev/null`.

### 2.4 Blast radius of a restart

- FACT: restart is `systemd state=restarted` on each host of the current batch. With default `serial: 0`, **all baremetal hosts
  restart Docker in the same task** (subject to forks). That includes all controllers at once.
- FACT: Kolla containers use `restart_policy: unless-stopped` (`group_vars/all.yml:134`), so they come back after the daemon
  restarts. FACT: `kolla_docker` sets no container `StopTimeout` (grep for `stop_timeout|StopTimeout` in
  `ansible/library/kolla_docker.py` is empty). HYPOTHESIS: on a daemon restart, containers get Docker's default stop timeout
  (about 10 s), **not** `docker_graceful_timeout: 60` (`all.yml:154`), which only applies to `kolla_docker` stop actions.
- HYPOTHESIS (Galera semantics): restarting Docker on all MariaDB hosts at once is a full-cluster stop. Galera does not
  re-bootstrap itself, so `kolla-ansible mariadb_recovery` is likely needed. NEEDS-LAB.
- Compute nodes: `nova_libvirt` runs with `pid_mode: host` and bind-mounts `/sys/fs/cgroup` (`nova-cell/defaults/main.yml:8,244`).
  Whether running QEMU processes survive the container restart depends on the cgroup placement of guests (machined slices
  versus the container cgroup). NEEDS-LAB. Note `tools/cleanup-containers:5-11`: "Docker will not be able to stop the
  nova_libvirt container with those [qemu processes] running".
- **Optional unit hazard:** `tools/setup-compute-libvirt.yml` (not run by any kolla-ansible command) installs
  `kolla-libvirt-guests.service` with `Requires=docker.service`, and its `ExecStop` stops nova_compute and runs
  `libvirt-guests.sh shutdown` (`tools/kolla-libvirt-guests.service:6,18-19`). HYPOTHESIS: systemd propagates a restart of
  `docker.service` to units that `Requires=` it, so on hosts where an operator installed this unit, **a Docker restart
  shuts down or managed-saves every guest**. NEEDS-LAB.
- Documented mitigations (`doc/source/reference/deployment-and-bootstrapping/bootstrap-servers.rst:59-93`): `--limit` batches
  keeping quorum, `-e kolla_serial=30%`, or Docker `live-restore` ("issues reported ... use it at your own risk"). The way to
  set live-restore in a supported way is `docker_custom_config: {"live-restore": true}`. HYPOTHESIS: the first run that adds it
  still restarts all containers, because the restart happens under the old config. Pre-seeding daemon.json by hand and running
  `systemctl reload docker` (live-restore can be reloaded) before bootstrap-servers would avoid that. NEEDS-LAB.
- Interaction with `config_strategy: COPY_ALWAYS` (`all.yml:43`, passed as `KOLLA_CONFIG_STRATEGY` in `docker_common_options`,
  `all.yml:162-163`). HYPOTHESIS: every container re-copies its config from `/etc/kolla/<svc>/` when it starts. A Docker restart
  therefore **activates any config that was rendered but not yet applied**, for example by `kolla-ansible genconfig`
  (`tools/kolla-ansible:458-461`) or a failed reconfigure.

---

## 3. `/etc/hosts` generation

```jinja
# ansible/roles/baremetal/tasks/pre-install.yml:29-36
{% for host in groups['baremetal'] %}
{% set api_interface = hostvars[host]['api_interface'] %}
{% if host not in groups['bifrost'] or api_interface in hostvars[host].ansible_facts %}
{% set hostnames = [hostvars[host].ansible_facts.nodename, hostvars[host].ansible_facts.hostname] %}
{{ 'api' | kolla_address(host) }} {{ hostnames | unique | join(' ') }}
```
- FACT: **it loops over all baremetal hosts**. Adding a host changes the managed block on **every** host bootstrap-servers runs
  against. No handler or restart is attached, so a change is harmless in itself.
- FACT: it needs facts for **all** baremetal hosts. `kolla_address` raises `FilterError("Interface ... not present on host ...")`
  when `hostvars[host]['ansible_facts']` lacks the interface (`kolla_ansible/kolla_address.py:88-95`). HYPOTHESIS: **one
  unreachable or fact-less baremetal host fails this task on every host**. Those hosts are then removed from the play, and
  nothing after pre-install runs. In practice every inventory host must be reachable for bootstrap-servers. NEEDS-LAB.
- Minor bug: the template checks `api_interface in hostvars[host].ansible_facts` without the `-`→`_` replacement that the `when:`
  clause uses (line 42 uses `| replace('-', '_')`).
- With `--limit new-hosts`, only the limited hosts get the full list. **Existing hosts never learn the new names.** The docs
  require including all controllers in the limit for RabbitMQ (`doc/source/user/adding-and-removing-hosts.rst:22-29`). For
  computes this is usually harmless because nova uses IPs (`nova.conf.d/libvirt.conf.j2:7-8`). **Exception (HYPOTHESIS):** with
  `libvirt_tls`, `live_migration_inbound_addr = migration_hostname = ansible_facts.nodename`
  (`nova-cell/templates/nova.conf.d/libvirt.conf.j2:2-5`, `nova-cell/defaults/main.yml:423`). Live migration from old computes
  to a new compute then depends on name resolution. Without DNS, re-run bootstrap-servers on all computes (or use DNS).
- HYPOTHESIS: running host-network containers keep the `/etc/hosts` copy taken when the container was created, so new entries
  reach them only after the container is recreated. NEEDS-LAB.
- Disable the whole mechanism with `customize_etc_hosts: false` (`defaults/main.yml:19`) when DNS is authoritative. At large N,
  this also removes the O(N²) templating.

---

## 4. `ansible/gather-facts.yml` (confirmed) and its cost model

```yaml
# gather-facts.yml:5-21 (play 1, hosts: all, serial: kolla_serial)
- setup: {filter: kolla_ansible_setup_filter, gather_subset: kolla_ansible_setup_gather_subset}
  when: not ansible_facts
- group_by: key: "all_using_limit_{{ (ansible_play_batch | length) != (groups['all'] | length) }}"
# gather-facts.yml:29-50 (play 2, hosts: all_using_limit_True)
vars:
  batch_index: "{{ ansible_play_batch.index(inventory_hostname) }}"
  batch_size: "{{ ansible_play_batch | length }}"
  delegate_hosts: "{{ groups['all'][batch_index | int::batch_size | int] }}"
setup: ... delegate_facts: True, delegate_to: "{{ item }}", with_items: "{{ delegate_hosts }}"
when: not hostvars[item].ansible_facts
```
Cost model, with N = |groups['all']| (this **includes `localhost`** from `[deployment]`) and L = hosts selected by `--limit`:
- **No limit, serial 0:** play 1 runs N `setup` calls in parallel (forks). Play 2 is empty.
- **`--limit` with L hosts:** play 1 runs L parallel `setup` calls. Play 2 runs on the same L hosts. Limited host *i* loops
  **sequentially** over `groups['all'][i::L]`, about N/L items, each a delegated `setup` (SSH from the deploy host to the
  *item* host, facts stored on the item). Total is N−L delegated setups, but only **L run at the same time**. Wall time is
  about (N/L) × t_setup. **L=1 means fully serial fact gathering of the whole inventory.**
- **With `kolla_serial` (no limit):** each batch is smaller than N, so every host joins `all_using_limit_True`. But by the time
  play 2 runs, play 1 has gathered all facts, so every item is skipped (loop evaluation only, no SSH).
- **With fact caching** (`gathering = smart` + `fact_caching`, `ansible-tuning.rst:34-63`): `when: not ansible_facts` is false
  for cached hosts, so both plays skip `setup`. This is the only documented way to make `--limit` runs cheap at scale. Stale-cache
  risk: IP or interface changes will not be seen until the cache expires (`fact_caching_timeout`).
- HYPOTHESIS: an unreachable *other* host in play 2 makes the delegated item fail. That fails the **limited** host's task and
  drops it from the run, so `--limit newnode` can fail because an unrelated node is down. NEEDS-LAB.
- FACT: `kolla_ansible_setup_filter` and `kolla_ansible_setup_gather_subset` apply **only** in `gather-facts.yml`. Playbooks that do
  not import it (`destroy.yml`, `mariadb_backup.yml`, `mariadb_recovery.yml`, `post-deploy.yml`, and `certificates.yml` when TLS
  backend is off) use implicit full play-level fact gathering.
- HYPOTHESIS: the documented filter `"ansible_[!qt]*"` (`ansible-tuning.rst:96`) also hides real interfaces whose names start
  with `q` or `t` (for example `team0`, `trunk0`, `tun0`). `kolla_address` would then fail for `api_interface`, `tunnel_interface`
  and so on if they are named that way.

---

## 5. `ansible/roles/prechecks` (`kolla-ansible prechecks`)

- FACT: `prechecks` runs `site.yml` with `-e kolla_action=precheck` (`tools/kolla-ansible:360-363`). The common `prechecks` role
  runs on `hosts: kolla_action_precheck`, which is **all** hosts (`site.yml:107-112`). Each service play then runs its own
  `<role>/tasks/precheck.yml` (73 files, about 3.3k lines in total).
- The common role (`ansible/roles/prechecks/tasks/main.yml:1-17`) checks:
  - host OS (`host_os_checks.yml`): CentOS 8, Debian buster, RHEL 8, Ubuntu bionic (`vars/main.yml:11-19`). Can be skipped with
    `prechecks_enable_host_os_checks: false`.
  - `/etc/localtime` exists, plus `/etc/timezone` on Debian (`datetime_checks.yml`).
  - `api_interface` present, active, with an address (`port_checks.yml`; skipped for `deployment` group hosts).
  - `docker --version` ≥ 1.10.0 and Docker SDK ≥ 2.0.0 (baremetal only), Ansible 2.8–2.9 (`package_checks.yml`, `service_checks.yml:2-9`).
  - empty values in passwords.yml (`grep`, `delegate_to: localhost`, `run_once`) (`service_checks.yml:14-21`; passes vacuously
    if the vault is encrypted, per the note at 11-13).
  - fails if `nscd` is running (`service_checks.yml:23-36`).
  - TLS VIP consistency and `enable_ceph` removed (`service_checks.yml:38-53`).
  - `config_owner_user` and group exist; passwordless sudo works (`user_checks.yml`).
  - external DB reachable when `enable_mariadb` is false (`database_checks.yml`).
- Service prechecks use `kolla_container_facts`, `wait_for ... state: stopped timeout: 1` port checks (skipped when the owning
  container already exists, for example `nova-cell/tasks/precheck.yml:8-17,85-98`), `stat`, `getent`, `vgs`, `ping` of the VIP,
  `ip addr`, and a read-only HAProxy `show stat` via `docker exec` (`haproxy/tasks/precheck.yml:155-160`).
- **Does it change anything?** FACT: no module that modifies state was found. Every `command`/`shell` has `changed_when: false`
  or is read-only, and there are no `template`/`copy`/`file`/`kolla_docker` tasks in the precheck files. It is **safe on a
  running production cloud**.
- **Cost:** O(1) tasks per host per enabled service, plus full `gather-facts.yml`. Loops over other hosts exist only for
  `rabbitmq`/`qdrouterd` hostname resolution (`rabbitmq/tasks/precheck.yml:61-72`, for the rabbitmq group only). There is no
  N² behaviour. The dominant cost at scale is Ansible's per-task overhead across about 70 plays. Prechecks plays inherit
  `serial: kolla_serial` from site.yml where it is set.

---

## 6. `destroy` (`ansible/destroy.yml`, role `destroy`, `tools/cleanup-*`)

```yaml
# ansible/destroy.yml:1-5
- name: Apply role destroy
  hosts: all          # includes localhost/[deployment] in the sample multinode inventory
  roles: [destroy]    # no serial, implicit gather_facts, no gather-facts.yml import
```
- CLI: needs `--yes-i-really-really-mean-it` spelled in full (`tools/kolla-ansible:378-396`; `RAW_ARGS` check at 271-277).
  `--include-images` sets `destroy_include_images=yes`. `--include-dev` sets `destroy_include_dev=yes`, **but see the bug in §11**.
- Role flow (`destroy/tasks/main.yml:1-8`): `validate-docker-execute.sh` (`sudo docker ps`), then `cleanup-containers`, then
  `cleanup-images --all` (only if `destroy_include_images`, default `enable_destroy_images: "no"`, `all.yml:730`), then
  `cleanup-host` (`become: true`, env vars passed in `cleanup_host.yml:5-17`). The role ignores `kolla_action` and has no tags.
- `tools/cleanup-containers`:
  - Safety guard (5-11): **aborts if `nova_libvirt` is running and non-Xen-dom0 qemu processes exist**.
  - If both `openvswitch_vswitchd` and `neutron_openvswitch_agent` are present: `neutron-ovs-cleanup --ovs_all_ports`, then
    **delete every OVS bridge** (24-30). HYPOTHESIS: the `docker exec -it` at line 29 fails without a TTY under Ansible's
    `script`, and stderr is discarded, so bridges may survive. NEEDS-LAB.
  - Stops (`-t 2`) and `rm -v -f` **all kolla-labelled containers**, then `docker volume rm` **every volume mounted by them**.
    That includes `mariadb`, `rabbitmq`, `nova_compute` (instance disks when the default volume is used), `libvirtd`, `kolla_logs`
    and so on (14-44). It also removes the `/var/log/kolla` link.
- `tools/cleanup-host`:
  - **Deletes ALL network namespaces** (`ip netns list`, 5-8). This is not limited to kolla's. HYPOTHESIS: lines of the form
    `name (id: N)` are word-split, so the delete may error. NEEDS-LAB.
  - Deletes every link whose `ip -o link` line matches `/tap/`, `/brq/` or `/vxlan/` (10-23).
  - Removes the VIPs from interfaces when `enable_haproxy == yes` (27-35).
  - Swift: `cat /etc/fstab | grep "/srv/node/d*" | xargs umount` (42). This **feeds whole fstab lines to umount** (bug), then
    deletes those fstab lines.
  - `rm -rfv` of custom datadirs when they differ from the default volume names (46-74). For example
    `nova_instance_datadir_volume` set to a host path means **instance storage is wiped**.
  - **`rm -rfv /etc/kolla/*` except `passwords.yml`, `globals.yml`, `kolla-build.conf`, `config`, `kolla-cli`, `certificates`**
    (76-95). The path is hard-coded and ignores `node_config_directory`. Because `localhost` is in `hosts: all`, this also runs on
    the **deploy host** unless `--limit` excludes it, which deletes `admin-openrc.sh` and anything else stored under `/etc/kolla`.
- `tools/cleanup-images`: `REAL_PATH=$(python -c "import os;print os.path.realpath('$0')")` (line 4) is **Python 2 syntax**.
  On python3-only hosts (CentOS 8, bionic without python2) it fails, but the `cd` is not needed under `script:`, so this is
  harmless (HYPOTHESIS). `--all` runs `docker rmi -f` on every kolla-labelled image.
- Scale and safety: per host, all hosts in parallel (forks), **no serial and no batch protection**. Never run it on production
  without `--limit`. For decommissioning, the docs use `stop` plus inventory removal, **not** `destroy`
  (`doc/source/user/adding-and-removing-hosts.rst:144-172,203-224`).
- CI: no Ussuri CI job runs `destroy` (grep of `tests/*.sh`).

## 7. `prune-images` (`ansible/prune-images.yml`, role `prune-images`)

```yaml
# ansible/prune-images.yml:1-8
- import_playbook: gather-facts.yml
- name: Apply role prune-images
  hosts: baremetal
  serial: '{{ kolla_serial|default("0") }}'
  gather_facts: false
  roles: [prune-images]
# roles/prune-images/tasks/prune_images.yml:2-8
docker_prune: {images: yes, images_filters: {label: kolla_version}, timeout: "{{ docker_image_prune_timeout }}"}  # default 300
```
- CLI needs `--yes-i-really-really-mean-it` (`tools/kolla-ansible:462-473`).
- FACT: Ansible's `docker_prune` with `images: yes` uses Docker's default `dangling=true`. Its own example sets
  `dangling: false` to "Prune everything (including non-dangling images)" (Ansible 2.9 `docker_prune.py:109-114`). So only
  **untagged (dangling) kolla images not used by any container** are removed, for example the previous image after a same-tag
  re-pull. **Old-release tags (for example `train` after an upgrade to `ussuri`) are kept.** To reclaim them you need
  `tools/cleanup-images --image-version <tag>` or manual `docker rmi`.
- Safe on production: Docker never prunes images that containers use. Cost is one Docker API call per host, plus the full
  `gather-facts.yml` (which is not needed by the role, but is imported and pays the --limit fact cost from §4).
- CI: not covered.

## 8. `post-deploy` (`ansible/post-deploy.yml`)

- `hosts: localhost`, implicit fact gathering, `become: true`. It templates `roles/common/templates/admin-openrc.sh.j2` to
  `{{ node_config }}/admin-openrc.sh` (`node_config` = `CONFIG_DIR`, default `/etc/kolla`, `all.yml:10`), owned by the invoking
  user's uid/gid, mode `0600` (`post-deploy.yml:1-11`).
- Contents: `OS_PASSWORD={{ keystone_admin_password }}` in plaintext, `OS_AUTH_URL={{ keystone_admin_url }}/v3` (the **admin**
  endpoint, `all.yml:822`), `OS_INTERFACE=internal`, and optional `OS_CACERT` from `kolla_admin_openrc_cacert`
  (`admin-openrc.sh.j2:1-25`).
- No `kolla_action` is passed (`tools/kolla-ansible:420-423`). Cost is O(1) and it is safe to re-run. **`destroy` deletes this
  file on the deploy host** (§6).

## 9. `mariadb_backup.yml` and `mariadb_recovery.yml` (playbook level only)

```yaml
# ansible/mariadb_backup.yml:1-6
- name: Backup MariaDB
  hosts: mariadb
  roles: [{ role: mariadb, tags: mariadb, when: enable_mariabackup | bool }]
# ansible/mariadb_recovery.yml:1-8
- name: Recover mariadb
  hosts: mariadb
  roles: [{ role: mariadb, tags: mariadb, when: enable_mariadb | bool }]
  vars: { mariadb_recover: true }
```
- CLI: `mariadb_backup` passes `-e kolla_action=backup -e mariadb_backup_type={full|incremental} -e common_run=true`. `mariadb_recovery`
  passes `-e kolla_action=deploy -e common_run=true` (`tools/kolla-ansible:368-377`). `common_run=true` stops the `common` role
  meta-dependency (fluentd, kolla-toolbox, cron) from running (`roles/common/tasks/main.yml:1-10`).
- Neither playbook imports `gather-facts.yml`, and neither has `serial`. Implicit full fact gathering covers the **mariadb hosts only**.
- Backup runs only on `mariadb_backup_host` = `groups['mariadb'][0]` (`roles/mariadb/defaults/main.yml:109`, `backup.yml:21-22`). It
  requires `enable_mariabackup: yes` (default `no`, `all.yml:661`). Otherwise every task is skipped silently.
- **HYPOTHESIS (image-tag pitfall):** `mariabackup_tag: "{{ openstack_tag }}"` (`mariadb/defaults/main.yml:105-106`), and
  `openstack_tag_suffix` gives `-centos8s` only when `kolla_centos_release` is registered. That happens **only in `site.yml:97-105`**.
  In `mariadb_backup.yml` and `mariadb_recovery.yml` the variable is undefined, so `AnsibleUndefined.__getitem__` returns
  undefined and the suffix becomes `''`. On CentOS **Stream** hosts these two commands would therefore use `...:ussuri` instead of
  `...:ussuri-centos8s`, unless `openstack_tag`/`openstack_tag_suffix` is pinned in globals.yml. NEEDS-LAB.
- CI: `mariadb_recovery` is tested with `--tags mariadb --skip-tags common` (`tests/test-mariadb.sh:21-25`). `mariadb_backup` is
  not tested in CI.

## 10. `certificates.yml` (playbook level)

```yaml
# ansible/certificates.yml:1-7
- import_playbook: gather-facts.yml
  when: kolla_enable_tls_backend | default(false) | bool
- name: Apply role certificates
  hosts: localhost
  roles: [certificates]
```
- It runs on the deploy host only. Facts of all hosts are needed only for the backend certificate's SAN list, which loops over
  `groups['tls-backend']` with `kolla_address` (`roles/certificates/templates/openssl-kolla-backend.cnf.j2:16-18`).
- FACT: every openssl step is guarded with `creates:` (for example `generate-backend.yml:21,32,46`; `generate.yml:28,39,53,96,107,121`),
  so re-runs never regenerate. **HYPOTHESIS:** after adding a `tls-backend` (controller) host, the backend cert keeps its old SANs
  until `backend.csr`/`backend.crt` are deleted by hand. The docs mark this command "For Development Only" (`tools/kolla-ansible:166`).

---

## 11. `tools/kolla-ansible` CLI

- **`--tags`, `--skip-tags`, `--limit`, `--forks`, `-e`, `--vault-*`** are global options appended to `EXTRA_OPTS`
  (`tools/kolla-ansible:251-259,295-298,305-318`), so **every subcommand accepts `--tags`**. Whether they mean anything depends on
  the playbook: `kolla-host.yml` only has the `baremetal` tag, and `destroy`/`prune-images`/`post-deploy` have no role tags. The
  extra environment variable `EXTRA_OPTS` is honoured (`:228`), for example `EXTRA_OPTS="--check --diff"`.
- **`kolla_serial`:** `ANSIBLE_SERIAL=${ANSIBLE_SERIAL:-0}` (`:234-236`, comment: "Serial is not recommended and disabled by
  default"). It is passed **only** by `upgrade` (`:430`) and `reconfigure` (`:439`) as `-e kolla_serial=${ANSIBLE_SERIAL}`.
  Because that `-e` is appended **after** the user's `--extra` options, Ansible's last-wins rule for extra-vars means
  **`kolla-ansible reconfigure -e kolla_serial=1` silently runs with `0`**. Use `ANSIBLE_SERIAL=1 kolla-ansible reconfigure`.
  `kolla-ansible upgrade -e kolla_serial=1` is overridden the same way (`:430`); use `ANSIBLE_SERIAL=1` there too.
  For every other command, `-e kolla_serial=...` works. Plays that **ignore** `kolla_serial` are listed below.
  - `site.yml`: "Group hosts", "Check CentOS variant", prechecks, mariadb, rabbitmq, rabbitmq-outward (no `serial` key),
    and cyborg, whose play reads `serial: '{{ serial|default("0") }}'` (`site.yml:1028`). The two imported
    gather-facts plays do use `kolla_serial` (`gather-facts.yml:7,31`).
  - `destroy.yml`, `mariadb_backup.yml`, `mariadb_recovery.yml`, `post-deploy.yml`, `certificates.yml`, `bifrost.yml` (grep `serial:` count 0).
- **Bug: `--ask-vault-pass`** (`:320-323`):
  ```bash
  (--ask-vault-pass)
          VERBOSITY="$EXTRA_OPTS --ask-vault-pass"
  ```
  It should append to `EXTRA_OPTS`. Effects: any `-v` given **before** it is lost, and all `EXTRA_OPTS` collected so far
  (including the `EXTRA_OPTS` environment variable) are **repeated** after the playbook path (`:485`). Usually harmless, because
  the duplicated `-e`, `--tags` and `--limit` values are identical, but verbosity silently disappears.
- **Bug: `--include-dev`** is declared `include-dev:` (requires an argument) in `LONG_OPTS` (`:216`) but handled as a flag with
  `shift 1` (`:284-287`). getopt swallows the next word as its argument. `destroy --include-dev --yes-i-really-really-mean-it`
  only works by accident (the swallowed word is then re-parsed). `destroy --include-dev -i inv` mis-parses, and a trailing
  `--include-dev` errors out.
- **Bug/limitation:** `CMD="ansible-playbook -i $INVENTORY $CONFIG_OPTS $EXTRA_OPTS $PLAYBOOK $VERBOSITY"` runs unquoted (`:116,485`).
  It is word-split (no spaces are possible inside `-e` JSON values) and pathname-expanded (for example `--limit compute[0-1]`
  could glob-match a file in the current directory).
- Environment check: refuses Ansible outside 2.8–2.9 (`:58-65`) and requires `kolla_ansible` importable by Ansible's Python (`:33-38`).
- Confirmation guard: `destroy`, `stop` and `prune-images` require `--yes-i-really-really-mean-it` (`:387,444,465`).
  `bootstrap-servers` (which can restart Docker everywhere) has **no** confirmation.

---

## 12. Ansible configuration and documented tuning

- FACT: **no `ansible.cfg` ships for users.** Repo-wide search found only:
  - `tests/templates/ansible.cfg.j2:1-13` (CI): `host_key_checking = False`; `inject_facts_as_vars = False` **except** for upgrade
    jobs whose previous release is train, ussuri, victoria or wallaby (lines 4-9); `[ssh_connection] pipelining = True`, `retries = 3`.
  - `contrib/dev/vagrant/bootstrap.sh:250-258` (dev): `forks=100`, `remote_user = root`, `scp_if_ssh=True`.
- Documentation recommendations:
  - `doc/source/user/quickstart.rst:251-267`: `/etc/ansible/ansible.cfg` with `[defaults] host_key_checking=False`,
    `pipelining=True`, `forks=100`, and a link to the Ansible performance-tuning blog.
    (Note: under `[defaults]`, `pipelining` is read by the ssh plugin option in Ansible 2.9, `plugins/connection/ssh.py:181-201`.
    The base setting reads `[connection]`/`[ssh_connection]`, `config/base.yml:80-99`.)
  - `doc/source/user/ansible-tuning.rst`:
    - SSH pipelining `[ssh_connection] pipelining = True` (8-17).
    - `forks = 20` as an example; "experiment to find out the CPU, memory and IO limits" (19-32).
    - Fact caching: `gathering = smart`, `fact_caching = jsonfile`, `fact_caching_connection = /tmp/ansible-facts`, and an
      optional `fact_caching_timeout` (34-63).
    - `inject_facts_as_vars = False` (65-81). FACT: Ussuri's playbooks and filters reference facts only through `ansible_facts`
      (grep for `ansible_[a-z_]+` other than `ansible_facts` returns only magic and connection vars), so this is safe for this tree.
    - Fact filtering `kolla_ansible_setup_filter: "ansible_[!qt]*"`, "reported to be as large as 18x" (83-106).
    - `kolla_ansible_setup_gather_subset: "all,!facter"` (108-118).
  - **Not documented anywhere in `doc/source`:** ControlPersist/`ssh_args`, mitogen, `strategy` (free/linear), `ANSIBLE_SERIAL`
    or `serial` for scale. The only `kolla_serial` mention is `bootstrap-servers.rst:83`. Large-scale guidance amounts to
    `--limit` per cell (`doc/source/reference/compute/nova-cells-guide.rst:376-400,419-457`) and the tuning page above.

---

## 13. Day-2 and scale knobs: `etc/kolla/globals.yml` and `ansible/group_vars/all.yml`

Defaults live in `all.yml`. `globals.yml` shows commented examples. **Several Docker knobs are not listed in globals.yml at all**
(`docker_log_max_*`, `docker_disable_*`, `docker_custom_config`, `docker_graceful_timeout`, `docker_restart_policy`), but they can
still be overridden there.

| Knob | Default (file:line) | Day-2 / scale relevance |
|---|---|---|
| `kolla_ansible_setup_filter` / `kolla_ansible_setup_gather_subset` | `omit` (`all.yml:31,37`; `globals.yml:12-22`) | Fact size and time per host. Biggest win on computes with many tap/qvo interfaces. |
| `config_strategy` | `COPY_ALWAYS` (`all.yml:43`; `globals.yml:28`) | Containers re-copy config at every start, so a Docker restart or reboot applies pending rendered config (§2.4) |
| `openstack_release` / `openstack_tag` / `openstack_tag_suffix` | `ussuri` / `release~suffix` / `-centos8s` on Stream (`all.yml:530-533`; `globals.yml:37-43`) | Image tag. The suffix depends on `site.yml`-only facts (§9). Pin it explicitly for consistent ops playbooks. |
| `docker_registry`, `docker_registry_insecure`, `docker_namespace` | empty / `yes if registry` / `kolla` (`all.yml:116-119`; `globals.yml:79-85`) | **Changing the registry rewrites daemon.json, which restarts Docker on every host** at the next bootstrap-servers |
| `docker_log_max_file` / `docker_log_max_size` | `"5"` / `"50m"` (`all.yml:130-131`) | daemon.json, so a change means a restart |
| `docker_disable_default_iptables_rules` / `_network` / `ip_forward` | `"no"` x3 (`all.yml:125-127`) | daemon.json, so a change means a restart. Defaults flip in Wallaby (warnings at `post-install.yml:94-133`). |
| `docker_storage_driver` / `docker_runtime_directory` / `docker_custom_config` / `docker_custom_option` | `""`/`""`/`{}`/`""` (`baremetal/defaults/main.yml:36-38`, `all.yml:120`) | The first three are in daemon.json (restart). `docker_custom_option` is a systemd drop-in that is **never applied by Kolla** (§2.2). |
| `docker_restart_policy` / `docker_restart_policy_retry` | `unless-stopped` / `10` (`all.yml:134,137`) | Containers return after a daemon restart or reboot |
| `docker_graceful_timeout` | `60` (`all.yml:154`) | SIGTERM→SIGKILL for kolla_docker stop and restart. Not for daemon restarts (HYPOTHESIS §2.4). |
| `docker_client_timeout` | `120` (`all.yml:122`; `globals.yml:88`) | Docker API timeout for slow pulls and stops on busy hosts |
| `docker_configure_for_zun` / `containerd_configure_for_zun` | `no` (`all.yml:140,146`) | Zun hosts: daemon.json includes **all etcd hosts**, and the containerd config is overwritten and restarted |
| `customize_etc_hosts`, `create_kolla_user`, `disable_firewall`, `change_selinux`/`selinux_state`, `enable_host_ntp`, `enable_docker_repo`, `virtualenv` | True, True, True, True/permissive, False, true, none (`baremetal/defaults/main.yml`) | Host mutations made by bootstrap-servers (§1) |
| `enable_chrony` | `yes` (`all.yml:597`; `globals.yml:262`) | Removes host chrony packages during bootstrap |
| `neutron_plugin_agent` | `openvswitch` (`all.yml:257`; `globals.yml:155`) | Drives OVS and agent containers on every compute |
| `enable_neutron_dvr` / `neutron_compute_dvr_mode` / `computes_need_external_bridge` | `no` / `dvr` / derived (`all.yml:670,948-949`; `globals.yml:339`) | DVR puts L3 and metadata agents on **every compute**, and an external bridge per compute |
| `enable_neutron_agent_ha` | `no` (`all.yml:673`; `globals.yml:342`) | L3/DHCP agent HA on network nodes |
| `enable_neutron_provider_networks` | `no` (`all.yml:675`; `globals.yml:344`) | External bridge on computes |
| `nova_compute_virt_type` | `kvm` (`all.yml:966`; `globals.yml:536`) | `nova_libvirt` is enabled for kvm and qemu |
| `enable_nova_ssh` | `yes` (`all.yml:682`) | nova_ssh container per compute (cold migration and resize) |
| `enable_cells` | `no` (`all.yml:595`; `globals.yml:260`) | Cell sharding for scale, together with `--limit cellNN` (nova-cells guide) |
| `openstack_service_workers` / `openstack_service_rpc_workers` | `min(vcpus,5)` / `min(vcpus,3)` (`all.yml:550-551`) | Caps API and RPC workers on large controllers (62 template references) |
| `database_max_pool_size` / `database_connection_recycle_time` | `1` / `10` (`all.yml:108-109`) | oslo.db pool per worker (used in 37 role template sets) |
| `openstack_logging_debug` | `False` (`all.yml:534`; `globals.yml:235`) | Log volume. Combine with docker log rotation. |
| `enable_fluentd` / `enable_central_logging` | `yes` / `no` (`all.yml:611,596`) | Per-host fluentd container |
| `set_sysctl` / `kolla_sysctl_conf_path` | `yes` / `/etc/sysctl.conf` (`all.yml:554,557`) | Host sysctl writes from service `config-host.yml` |
| `skip_stop_containers` | `[]` (`all.yml:752`) | Protects containers from `kolla-ansible stop` |
| `enable_destroy_images` | `no` (`all.yml:730`; `globals.yml:275`) | Whether destroy also removes images |
| `enable_mariabackup` | `no` (`all.yml:661`; `globals.yml:330`) | Must be `yes` or `mariadb_backup` silently does nothing |
| `kolla_enable_tls_backend` | `no` (`all.yml:807`) | Pulls `gather-facts.yml` into `certificates` |
| `keepalived_virtual_router_id` | `51` (`all.yml:186`; `globals.yml:174`) | Must be unique per L2 segment in multi-region setups |
| `<container>_dimensions` | `{}` (`all.yml:173`; `globals.yml:176-197`) | CPU and memory limits per container |

---

## 14. HYPOTHESIS / NEEDS-LAB register

| # | Claim | Status | Suggested experiment |
|---|---|---|---|
| H1 | daemon-reload never reports changed in Ansible 2.8 either | Verified for 2.9.27 only; NEEDS-LAB for 2.8 | Run `systemd: daemon_reload=yes` on 2.8 and inspect `changed` |
| H2 | Interrupted bootstrap leaves docker masked on Ubuntu, and docker does not start after reboot | NEEDS-LAB | Ubuntu VM: start bootstrap-servers, kill it after "Mask the docker systemd unit", reboot |
| H3 | One unreachable baremetal host aborts bootstrap-servers on all hosts (`/etc/hosts` task) | NEEDS-LAB | Inventory with one powered-off host |
| H4 | Unreachable non-limited host breaks `--limit` runs through delegated facts | NEEDS-LAB | `deploy --limit compute1` with compute2 down |
| H5 | `--limit` fact gathering wall time is about (N/L)·t_setup | NEEDS-LAB | Time gather-facts with fake hosts and L=1 vs L=10 |
| H6 | Daemon restart uses about 10 s stop timeout, not `docker_graceful_timeout` | NEEDS-LAB | `docker inspect` StopTimeout; restart dockerd and time the MariaDB shutdown |
| H7 | Simultaneous Docker restart on all controllers needs `mariadb_recovery` | NEEDS-LAB | 3-node lab, change `docker_log_max_size`, run bootstrap-servers |
| H8 | QEMU guests survive a nova_libvirt container restart | NEEDS-LAB | Restart dockerd on a compute with running VMs; compare `virsh list` and qemu PIDs |
| H9 | `kolla-libvirt-guests.service` (optional) shuts guests down on a Docker restart | NEEDS-LAB | Install via `tools/setup-compute-libvirt.yml`, then `systemctl restart docker` |
| H10 | Drop-in vs daemon.json duplicate option makes dockerd fail at the next restart | NEEDS-LAB | Set an insecure registry in both |
| H11 | `apparmor_parser -R` fails on an already-unloaded profile (second run) | NEEDS-LAB | Ubuntu with libvirt profile file present; run twice |
| H12 | mariadb_backup and mariadb_recovery use the un-suffixed tag on CentOS Stream | NEEDS-LAB | `-e` debug of `mariabackup_image_full` via those playbooks on a Stream host |
| H13 | Backend TLS cert not regenerated for new hosts | HYPOTHESIS (code is clear) | Add a tls-backend host; rerun certificates; check SANs |
| H14 | `EXTRA_OPTS="--check --diff" kolla-ansible bootstrap-servers --limit X` previews daemon.json changes safely | NEEDS-LAB (some command tasks are skipped in check mode) | Run in lab and compare |
| H15 | Running containers do not see `/etc/hosts` updates | NEEDS-LAB | Add a host, check `/etc/hosts` inside `rabbitmq` |
| H16 | `ansible_[!qt]*` filter breaks hosts whose api/tunnel interface starts with q or t | HYPOTHESIS | Name the api interface `team0` and run prechecks |

## 15. Operational recommendations from this code

1. Before any `bootstrap-servers` re-run on production, render the target daemon.json and compare it with the hosts
   (`EXTRA_OPTS="--check --diff" ... --limit <one host>`, NEEDS-LAB H14). If it differs, run with `-e kolla_serial=1`, or with
   `--limit` per controller and in compute batches, keeping Galera and RabbitMQ quorum.
2. Do not rely on `docker_custom_option`. Put options in `docker_custom_config` (daemon.json) so changes are applied, and are
   applied visibly.
3. After any failed or interrupted run on Debian/Ubuntu, check for a masked `docker.service`.
4. Set `disable_firewall: false`, `change_selinux: false` and the package-removal lists explicitly if the hosts are managed by
   other tooling. Check `open-iscsi` and `iscsi-initiator-utils` before the first run on hosts that use host iSCSI.
5. At scale, enable jsonfile fact caching with `gathering = smart`, `inject_facts_as_vars = False` and a setup filter. Without
   them, `--limit` runs gather facts for the whole inventory, one host at a time per limited host.
6. Use `ANSIBLE_SERIAL` (not `-e kolla_serial`) for `reconfigure` and `upgrade`.
7. Never run `destroy` without `--limit`. Exclude the deploy host (`--limit '!localhost'`) unless you want its `/etc/kolla` wiped.
