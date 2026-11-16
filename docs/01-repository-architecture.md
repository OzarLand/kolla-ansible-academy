# 01 — Repository Architecture (Kolla-Ansible `ussuri-eol`)

> Scope: the `ussuri-eol` tag of `openstack/kolla-ansible` (HEAD `8a94fe9`). Every path below is relative to the
> root of that checkout. Evidence labels used in all documents: **[CODE]** read in the source,
> **[LAB]** observed in the execution lab (see [annex/lab](../annex/lab/README.md)),
> **[ANSIBLE]** Ansible 2.9 semantics (verified in the lab or in Ansible's own source),
> **[HYPOTHESIS]** inferred, not proven, **[NEEDS-LAB]** requires a real environment to confirm.

This document explains *how the machine is built*: which entry points exist, how a CLI command becomes an
`ansible-playbook` run, how `site.yml` is laid out, what every service role has in common, and which custom modules
actually touch the hosts. The other documents build on the vocabulary defined here.

---

## 1. Top-level layout

| Path | What it is | Why it matters for Day 2 |
|---|---|---|
| `tools/kolla-ansible` | Bash wrapper. Maps sub-commands to a playbook plus `-e kolla_action=<action>` | Decides which playbook runs and whether `kolla_serial` is passed (§2) |
| `ansible/site.yml` | The main playbook (84 plays once `nova.yml` and `gather-facts.yml` are expanded) | Every `deploy`, `reconfigure`, `upgrade`, `pull`, `stop`, `prechecks`, `genconfig`, `deploy-containers` run goes through it |
| `ansible/gather-facts.yml` | Imported first by `site.yml` | Fact gathering, including the special `--limit` path (see [06](06-compute-scaling-and-performance.md)) |
| `ansible/nova.yml` | Imported by `site.yml:710` | Nova is split into 10 plays (see [05](05-nova-deep-dive.md)) |
| `ansible/kolla-host.yml` + `roles/baremetal` | `bootstrap-servers` | Installs Docker and changes the host OS. Can restart the Docker daemon |
| `ansible/destroy.yml`, `prune-images.yml`, `mariadb_backup.yml`, `mariadb_recovery.yml`, `post-deploy.yml`, `certificates.yml`, `bifrost.yml` | Single-purpose playbooks | See [09](09-practical-command-reference.md) |
| `ansible/roles/` | 85 roles: 68 with a `common` meta-dependency (service roles); 17 without — the helper or utility roles plus `memcached` and `multipathd` | §4 and §5 |
| `ansible/group_vars/all.yml` | 1,130 lines of defaults (every `enable_*`, ports, transport URLs, Docker options) | Lowest-priority defaults. `globals.yml` overrides them |
| `ansible/inventory/{all-in-one,multinode}` | Example inventories that define about 200 groups | Group membership drives where every container runs |
| `ansible/library/` | Custom modules: `kolla_docker`, `kolla_toolbox`, `kolla_container_facts`, `bslurp` | The only code that talks to Docker (§6) |
| `ansible/action_plugins/` | `merge_configs` (INI merge) and `merge_yaml` | How `/etc/kolla/config` overrides are merged (§7) |
| `ansible/filter_plugins/`, `kolla_ansible/*.py` | Jinja filters: `service_enabled_and_mapped_to_host`, `kolla_address`, `extract_cell`, `customise_fluentd`, … | Decide placement of a service on a host (§5.3) |
| `etc/kolla/globals.yml`, `etc/kolla/passwords.yml` | Templates copied to `/etc/kolla/` by the operator | `globals.yml` is passed as **extra-vars** (§3) |
| `tools/cleanup-*`, `tools/kolla-libvirt-guests.service`, `tools/virt-guest-shutdown.target` | Host utilities | `cleanup-host` deletes network namespaces and links (see [08](08-operational-risk-matrix.md)) |
| `doc/source/` | Documentation (`ansible-tuning.rst`, `bootstrap-servers.rst`, …) | Used only to cross-check, never as the source of truth |

No `ansible.cfg` is shipped for operators [CODE, fact sheet E §9]. Forks, pipelining, fact caching and SSH settings
come from whatever `ansible.cfg` or environment the operator provides.

---

## 2. From CLI to `ansible-playbook`

`tools/kolla-ansible` builds a single command line (`tools/kolla-ansible:483-486`):

```bash
CONFIG_OPTS="-e @${CONFIG_DIR}/globals.yml -e @${PASSWORDS_FILE} -e CONFIG_DIR=${CONFIG_DIR}"
CMD="ansible-playbook -i $INVENTORY $CONFIG_OPTS $EXTRA_OPTS $PLAYBOOK $VERBOSITY"
```

| Command | Playbook | Extra vars added | `kolla_serial` passed? | Evidence |
|---|---|---|---|---|
| `prechecks` | `site.yml` | `kolla_action=precheck` | no | `tools/kolla-ansible:360-363` |
| `check` | `site.yml` | `kolla_action=check` | no | `:364-367` |
| `bootstrap-servers` | `kolla-host.yml` | `kolla_action=bootstrap-servers` | no (the playbook has its own `serial: kolla_serial`) | `:397-401` |
| `deploy` | `site.yml` | `kolla_action=deploy` | **no** | `:402-405` |
| `deploy-containers` | `site.yml` | `kolla_action=deploy-containers` | no | `:411-414` |
| `pull` | `site.yml` | `kolla_action=pull` | no | `:424-427` |
| `upgrade` | `site.yml` | `kolla_action=upgrade -e kolla_serial=${ANSIBLE_SERIAL}` | **yes** | `:428-431` |
| `reconfigure` | `site.yml` | `kolla_action=reconfigure -e kolla_serial=${ANSIBLE_SERIAL}` | **yes** | `:437-440` |
| `genconfig` | `site.yml` | `kolla_action=config` | no | `:458-461` |
| `stop` | `site.yml` | `kolla_action=stop` (needs `--yes-i-really-really-mean-it`) | no | `:441-453` |
| `destroy` | `destroy.yml` | (needs `--yes-i-really-really-mean-it`) | no | `:378-396` |
| `mariadb_recovery` | `mariadb_recovery.yml` | `kolla_action=deploy common_run=true` | no | `:368-372` |
| `mariadb_backup` | `mariadb_backup.yml` | `kolla_action=backup common_run=true` | no | `:373-377` |
| `post-deploy` | `post-deploy.yml` | – | no | `:420-423` |
| `prune-images` | `prune-images.yml` | (needs `--yes-i-really-really-mean-it`) | no | `:462-473` |

Consequences [CODE]:

- **`ANSIBLE_SERIAL` defaults to 0** (`tools/kolla-ansible:234-236`), which means *all hosts of a play in one batch*.
  The comment there reads "Serial is not recommended and disabled by default".
- **`kolla_serial` is overridden for `reconfigure` and `upgrade`.** The wrapper appends `-e kolla_serial=${ANSIBLE_SERIAL}`
  *after* the user's `-e` options. For those two commands a user-supplied `-e kolla_serial=N` is therefore silently
  replaced by `ANSIBLE_SERIAL`. Use the environment variable instead (fact sheet E §1).
- **Other commands default to 0.** For `deploy` and the rest, `kolla_serial` is not passed, and the plays fall back
  to `kolla_serial|default("0")`.
- **`--tags`, `--skip-tags`, `--limit` and `--forks` pass straight through** (`:251-259`, `:305-313`). `EXTRA_OPTS` from
  the environment is passed through as well, which is the only way to reach `--check`, `--diff`, `--list-tasks` or
  `--list-hosts` through the wrapper.
- **Bug: `--ask-vault-pass`.** The branch sets `VERBOSITY="$EXTRA_OPTS --ask-vault-pass"` (`:320-323`), which
  duplicates all options seen so far and drops earlier `-v` flags.

### 2.1 Variable precedence that matters

`globals.yml` and `passwords.yml` are passed with `-e @file`. That is **extra-vars, the highest precedence in Ansible**.
Consequences [ANSIBLE]:

- A value in `globals.yml` cannot be overridden per host or per group in the inventory. Per-host variation
  must come from variables that are *not* set in `globals.yml`. Inventory `host_vars` override role defaults and
  `group_vars/all.yml`, but not extra-vars.
- Anything placed in `globals.yml` applies to **every play and every host**. This is why "global" switches such as
  `enable_barbican`, `openstack_tag` or `nova_compute_virt_type` have fleet-wide effects (see
  [07](07-day2-operational-impact.md)).

---

## 3. Anatomy of `site.yml`

```mermaid
flowchart TB
  subgraph pre["Always-run plays (tag: always)"]
    GF1["gather-facts.yml play 1<br/>setup on all hosts<br/>(skipped if facts cached)"] --> GF2["gather-facts.yml play 2<br/>delegated setup when --limit is used"]
    GF2 --> GB["Group hosts based on configuration<br/>group_by: kolla_distribution_*, kolla_action_*,<br/>enable_&lt;svc&gt;_True/False"]
  end
  GB --> CEN["Check CentOS variant (slurp /etc/centos-release)"]
  CEN --> PRE["Apply role prechecks<br/>(hosts: kolla_action_precheck)"]
  PRE --> INFRA["chrony → haproxy(+49 loadbalancer includes) → collectd → zookeeper → elasticsearch → influxdb<br/>→ telegraf → redis → kibana → mariadb → memcached → prometheus → iscsi → multipathd<br/>→ rabbitmq → outward rabbitmq → qdrouterd → etcd"]
  INFRA --> CP1["keystone → kafka → storm → karbor → swift → glance → ironic → cinder → placement"]
  CP1 --> NOVA["nova.yml (10 plays)"]
  NOVA --> NET["openvswitch | ovs-dpdk → ovn → nova-hyperv → neutron → kuryr"]
  NET --> CP2["heat → horizon → murano → solum → magnum → mistral → qinling → sahara → mongodb → panko → manila<br/>→ gnocchi → ceilometer → monasca → aodh → barbican → congress → cyborg → tempest → designate → rally<br/>→ vmtp → trove → watcher → grafana → cloudkitty → freezer → senlin → searchlight → tacker → octavia<br/>→ zun → skydive → vitrage → blazar → masakari"]
```

Facts about the structure [CODE, `ansible/site.yml`]:

1. **One play per service, in a fixed order.** There is no dependency resolver. The deployment order *is* the order
   of plays in `site.yml` (see [04](04-deployment-execution-flow.md)). The only exception is the haproxy play
   (`site.yml:126-392`): it runs *before* the services it fronts, and configures all of their frontends in one place.
2. **The "group by configuration" optimisation.** The play at `site.yml:7-95` puts every host into groups such as
   `enable_nova_True`. Every service play then intersects its host list with `&enable_<svc>_True`, for example
   `hosts: [compute, …, '&enable_nova_True']`. If a service is disabled, the play matches no host and Ansible skips
   it entirely, which avoids evaluating hundreds of `when:` clauses per host. The NOTE at `site.yml:4-6` says this
   exists because "in large environments, even tasks that are skipped can take a significant amount of time".
3. **Serial and tags differ between plays.** Almost every play has `serial: '{{ kolla_serial|default("0") }}'`.
   - **Exceptions with no `serial` key:** `mariadb` (`site.yml:471-479`), `rabbitmq` and `outward rabbitmq`
     (`:535-572`). Their clustering logic needs all members in one batch. Rolling behaviour is implemented *inside*
     their handlers instead (fact sheet B §1–2).
   - **Bug: `cyborg` (`:1028`)** uses `serial|default("0")`, not `kolla_serial`, so `ANSIBLE_SERIAL` has no effect on
     cyborg.
   - **Tag placement varies:**
     - Most plays tag the *role*, e.g. `roles: - { role: nova-hyperv, tags: nova-hyperv }`.
     - The haproxy play and all `nova.yml` plays put tags at *play* level.
     - `memcached` has two tags, `[memcache, memcached]` (`site.yml:489`).
     - The `prechecks` play has no tag at all.
4. **`common` is reached through meta dependencies.** Almost every service role declares
   `dependencies: - { role: common }` in `meta/main.yml`. Exceptions are the helper roles plus `memcached` and
   `multipathd`, which have no `meta/`. `common` therefore runs in the *first* play in which a host appears, guarded by
   a host fact (§5.4).

The complete table of 84 plays (hosts, tags, serial) is generated from the source in
[annex/generated-inventory.md §1](../annex/generated-inventory.md).

---

## 4. Anatomy of a service role

Every service role follows the same skeleton. `nova` is a typical example:

```
roles/<svc>/
  defaults/main.yml      <svc>_services dict (containers), images, volumes, ks users/endpoints, ports
  meta/main.yml          dependencies: [ { role: common } ]
  vars/main.yml          project_name (and, for nova-cell, kolla_role_name)
  handlers/main.yml      "Restart <service-key> container" handlers (kolla_docker recreate_or_restart_container)
  tasks/main.yml         - include_tasks: "{{ kolla_action }}.yml"          <-- dynamic dispatch
  tasks/deploy.yml       register.yml → config.yml → check-containers.yml → bootstrap.yml → flush_handlers
  tasks/reconfigure.yml  - import_tasks: deploy.yml                          <-- reconfigure == deploy
  tasks/upgrade.yml      service-specific (stop/rolling, DB migrations, check-containers, flush)
  tasks/deploy-containers.yml  - import_tasks: check-containers.yml
  tasks/pull.yml         import_role: service-images-pull
  tasks/stop.yml         import_role: service-stop
  tasks/precheck.yml     import_role: service-precheck + port checks
  tasks/check.yml        (usually empty)
  tasks/config.yml       (also run alone for kolla_action=config, i.e. `genconfig`)
  tasks/loadbalancer.yml import_role: haproxy-config (tags: always)  <-- called from the haproxy play
  templates/             <service>.json.j2 (kolla_set_configs manifest), <svc>.conf.j2, …
```

### 4.1 `kolla_action` dispatch

`tasks/main.yml` is a **dynamic** `include_tasks: "{{ kolla_action }}.yml"`. Two consequences follow [ANSIBLE, LAB]:

- **`--list-tasks` is blind to role internals.** It shows only the `include_tasks` placeholder of every role (lab
  output in [annex/lab/list-tasks-nova.txt](../annex/lab/list-tasks-nova.txt)). You cannot use `--list-tasks` to see
  what a tag will do in Kolla-Ansible. That is why this study built an execution lab.
- **Tags reach the role's tasks only through inheritance.** The included tasks inherit the *role and play* tags (e.g.
  `nova`), not tags written on the `include_tasks` statement itself (see [03](03-ansible-roles-and-tags-mapping.md) §2).

### 4.2 `reconfigure` is `deploy`

Of the roles, 67 have a `reconfigure.yml` that only does `import_tasks: deploy.yml`. `mongodb` and `nova-hyperv` do the
same with `include_tasks`. `swift` and `bifrost` have their own reconfigure logic: they fail if a container is down,
run `kolla_set_configs --check` and restart only drifted containers (`roles/swift/tasks/reconfigure.yml`). See the
generated column "reconf→deploy" in [annex/generated-inventory.md §3](../annex/generated-inventory.md).
So `reconfigure` re-runs Keystone registration, DB creation and the **bootstrap (DB sync) container** of most
services, exactly like `deploy` [CODE, LAB scenario s01]. The only built-in differences between `deploy` and
`reconfigure` are:

- **`kolla_serial`** is passed from `ANSIBLE_SERIAL` (§2).
- **A few `when: kolla_action == ...` conditions.** Example: Neutron's bootstrap container runs only on `deploy`,
  because `neutron_enable_rolling_upgrade` is `yes` (`roles/neutron/tasks/bootstrap_service.yml:21-22`). Nova's
  bootstrap plays run on both `deploy` and `reconfigure` (`ansible/nova.yml:49-51,85-87`).

### 4.3 The config → check → handler pattern

This is the heart of Day-2 behaviour:

```mermaid
sequenceDiagram
  autonumber
  participant DH as Deploy host (ansible-playbook)
  participant H as Target host
  participant C as Container
  DH->>DH: render template / merge_configs locally (Jinja + INI merge)
  DH->>H: copy module: compare checksum of /etc/kolla/<svc>/<file>
  alt content differs
    DH->>H: write file (changed) → notify "Restart <svc> container"
  end
  DH->>H: kolla_docker compare_container (check-containers.yml)
  H->>C: docker inspect (image id/tag, volumes, env, privileged, pid/ipc, dimensions, labels, command, state)
  H->>C: docker exec kolla_set_configs --check (config drift between /var/lib/kolla/config_files and live files)
  alt differs or drift
    DH-->>DH: notify "Restart <svc> container"
  end
  Note over DH,H: meta: flush_handlers (end of deploy.yml) or end of play
  DH->>H: handler: kolla_docker recreate_or_restart_container
  alt image or container params differ
    H->>C: pull image if absent → docker stop (10 s, see §6) → rm → create → start  (RECREATE)
  else only config changed (COPY_ALWAYS)
    H->>C: docker stop (10 s, see §6) → docker start  (RESTART)
  end
```

- **Files are rendered on the deploy host and copied.** The `template` and `merge_configs` steps render on the deploy
  host, then the `copy` logic compares checksums on the target. So *every* config task costs one SSH round trip per
  host per item, even when nothing changes (see [06](06-compute-scaling-and-performance.md)).
- **Two independent triggers lead to the same handler.** A changed file notifies directly. The `compare_container`
  task (`ansible/library/kolla_docker.py:326-350`) also notifies when:
  - the container's definition differs (image ID or tag, volumes, environment, privileged, pid/ipc, dimensions,
    labels, command, state); or
  - **`kolla_set_configs --check`** inside the running container reports drift (`kolla_docker.py:244,543-578`).

  The second path means a config file changed by an earlier `genconfig`, or by hand, will still restart the container
  on the next `deploy`/`reconfigure`/`deploy-containers` [CODE, LAB s14→s15].
- **Restart and recreate are both full stop/start cycles.** There is no "reload" anywhere. The handler calls
  `recreate_or_restart_container` (`kolla_docker.py:781-803`):
  - **recreate** when the image or parameters differ;
  - otherwise **restart** (`dc.stop(timeout=graceful_timeout)` then `dc.start`, `:892-904`).

  The effective stop timeout is **10 s**, not the 60 s of `docker_graceful_timeout` (§6, proven in the lab).
- **Handlers run in definition order, on every notified host of the batch at once.** Unless `kolla_serial` is set,
  "Restart nova-compute container" restarts nova_compute on all notified computes in the same step [ANSIBLE, LAB].

### 4.4 Containers and placement

Each role's `defaults/main.yml` defines a `<role>_services` dict with an entry per container. The fields are
`container_name`, `group` *or* `host_in_groups`, `enabled`, `image`, `volumes`, `dimensions`, `privileged`,
`pid_mode`/`ipc_mode`, and `haproxy`. The filter `service_enabled_and_mapped_to_host`
(`kolla_ansible/filters.py:42-79`) decides placement:

- `host_in_groups` (a per-host boolean expression) wins over `group`.
- `group: all` means every host.

All 195 container definitions are listed in [annex/generated-inventory.md §2](../annex/generated-inventory.md).

---

## 5. Shared helper roles

| Role | Used by | What it does | Scope |
|---|---|---|---|
| `common` | meta dependency of ~66 roles | Deploys `fluentd`, `kolla_toolbox`, `cron` on **every** host (`group: all`). Renders `td-agent.conf` and `logrotate.conf` | Once per host per run (guarded by the `common_run` fact) |
| `service-ks-register` | 39 roles | Creates the Keystone service, endpoints, project, user, role and grants through `kolla_toolbox` | `run_once` per play (`roles/service-ks-register/tasks/main.yml:125-126`) |
| `service-rabbitmq` | nova-cell and others | Creates RabbitMQ vhost and user through `kolla_toolbox`, delegated to a RabbitMQ host | once per cell/service |
| `service-images-pull` | every role's `pull.yml` | `kolla_docker pull_image` for every enabled container mapped to the host | per host × per container |
| `service-stop` | every role's `stop.yml` | `kolla_docker stop_container`, honouring `skip_stop_containers` | per host × per container |
| `service-precheck` | every role's `precheck.yml` | Validates that the inventory groups exist | per host |
| `service-cert-copy` | `copy-certs.yml` of 52 roles | Copies the CA (and backend certs) into each service config dir when `kolla_copy_ca_into_containers` is set | per host × per service |
| `haproxy-config` | every role's `loadbalancer.yml` | Renders `/etc/kolla/haproxy/services.d/<svc>.cfg` | per haproxy host |
| `module-load` | nova-cell, neutron, openvswitch, haproxy | `modprobe` and persistence in `/etc/modules-load.d` | per host |

### 5.1 The `common` role and the `common_run` guard

`roles/common/tasks/main.yml:1-10`:

```yaml
- include_tasks: "{{ kolla_action }}.yml"
  tags: common
  when: not common_run
- name: Registering common role has run
  set_fact:
    common_run: True
  tags: common
  when: not common_run
```

- **`common_run` is a per-host fact** (`roles/common/defaults/main.yml:4`), and facts persist across plays.
  `common` therefore executes **in the first play in which a host appears**, and is skipped (as cheap
  `skipped` results) in all later plays. Example from the lab: on a compute host, `common` runs in the `chrony` play
  for a full `deploy` but in the `nova-cell` play for `-t nova`.
- **`common` inherits the play or role tags of whatever play reaches the host first.** `-t nova` therefore runs the
  whole `common` role (fluentd, cron, kolla_toolbox config and container checks) on every nova host, computes
  included [LAB s01: 20 `common` tasks executed on `compute001` under `-t nova`].
- **`fluentd` and `cron` configs are global.** `td-agent.conf` (inputs per enabled service) and `logrotate.conf` are
  rendered from the **global** `enable_*` flags (`roles/common/tasks/config.yml:109-240`). Enabling *any* service
  changes these two files on *every* host, which restarts `fluentd` and `cron` fleet-wide on the next run that
  executes `common` [CODE, LAB s07/s08].

---

## 6. Custom modules — the only code that touches Docker

| Module | Purpose | Key behaviour (evidence) |
|---|---|---|
| `kolla_docker` (`ansible/library/kolla_docker.py`, 1,077 lines) | Every container operation | Actions: `compare_container`, `compare_image`, `create_volume`, `ensure_image`, `get_container_env`, `get_container_state`, `pull_image`, `recreate_or_restart_container`, `remove_container`, `remove_image`, `remove_volume`, `restart_container`, `start_container`, `stop_container`, `stop_and_remove_container`. Uses host networking (`build_host_config`). `restart_policy` defaults from `docker_restart_policy: unless-stopped`, and is **not compared** (FIXME at `:21`). |
| `kolla_toolbox` (`library/kolla_toolbox.py`) | Runs an Ansible module *inside* the `kolla_toolbox` container (`docker exec … ansible localhost -m <module>`) | Used for MySQL, Keystone (`os_*`) and RabbitMQ (`rabbitmq_user/vhost`) operations. Needs a running `kolla_toolbox` on the target |
| `kolla_container_facts` | Returns the running containers by name | Used by prechecks and upgrade logic |
| `bslurp` | Chunked file transfer between hosts | Used to distribute e.g. Swift rings and Keystone fernet material |

How `kolla_docker` decides [CODE]:

- **`start_container`** pulls the image **only if it is absent locally** (`kolla_docker.py:805-808`). A rebuilt image
  pushed under the same tag is therefore *not* fetched by `deploy` or `reconfigure`. It takes an explicit `pull`
  (`kolla-ansible pull`) to download it, after which `compare_image` sees a new image ID and recreates the container
  [LAB s09a/b/c].
- **`compare_image` compares image ID and tag**, using the local image for that reference (`:403-418`).
- **`pull_image` reports changed only if the local image ID changed** (`:599-633`).
- **`docker_graceful_timeout` and `docker_client_timeout` are silently ignored.**
  - `generate_module()` starts from `common_options` (= `docker_common_options`, which carries
    `graceful_timeout: 60` and `client_timeout: {{ docker_client_timeout }}`, `group_vars/all.yml:157-167`). It then
    overwrites every key whose module parameter is not `None` (`kolla_docker.py:1036-1046`).
  - `graceful_timeout` has `default=10` and `client_timeout` has `default=120` in the argument spec
    (`kolla_docker.py:991,1011`), so the module defaults always win.
  - Proven by feeding the real module code the arguments a handler sends
    ([annex/lab/kolla_docker_params.out](../annex/lab/kolla_docker_params.out)):
    `graceful_timeout common_options='60' -> effective=10`.
  - Practical effect: **every `docker stop` issued by Kolla-Ansible Ussuri sends SIGKILL after 10 s**. This holds for
    handler restarts, recreates and `stop`. The release note `docker-stop-timeout-c8089f6bf92d6c28.yaml` claims the
    default was raised to 60 s; it has no effect. A service needing a longer graceful shutdown (in-flight image
    uploads, cinder copies, heat-engine) is killed after 10 s. [CODE + LAB]

---

## 7. Configuration generation and overrides

1. **INI files go through `merge_configs`.** `merge_configs` (`ansible/action_plugins/merge_configs.py`) renders each
   listed source as a Jinja template *on the deploy host*, merges them as INI (later sources win), then calls the
   `copy` action. For nova-compute the sources are (`roles/nova-cell/tasks/config.yml:63-75`):
   `templates/nova.conf.j2` → `/etc/kolla/config/global.conf` → `/etc/kolla/config/nova.conf` →
   `/etc/kolla/config/nova/nova-compute.conf` → `/etc/kolla/config/nova/<inventory_hostname>/nova.conf`.
2. **Overrides are scoped by file location.** Putting a value into `/etc/kolla/config/nova.conf` affects **every nova
   container on every host** (nova-api, scheduler, conductor, novncproxy and every nova-compute). The file
   `/etc/kolla/config/nova/nova-compute.conf` affects nova-compute only [LAB s02 vs s03].
3. **Some overrides leak to other services.** Neutron's `openvswitch_agent.ini` merges
   `/etc/kolla/config/neutron/ml2_conf.ini` on top of the agent template (`roles/neutron/tasks/config.yml:172-190`,
   "TODO(mnasiadka): Remove in V"). A change meant for `neutron-server` therefore also restarts
   `neutron_openvswitch_agent` on every compute and network node [CODE, LAB s05].
4. **The container receives its config through a manifest.** The `config.json` (rendered from `<service>.json.j2`)
   tells `kolla_set_configs`, inside the image, which files to copy from `/var/lib/kolla/config_files` (bind-mounted
   from `/etc/kolla/<service>/`) to their final location. It also names the command to start. With
   `config_strategy: COPY_ALWAYS` (`group_vars/all.yml:43`) the copy happens at every container start. That is why a
   restart is enough to apply a config change, and why there is no reload.

---

## 8. Inventory model

- **Groups are mostly aliases of a few physical groups.** The physical groups are `control`, `network`, `compute`,
  `storage`, `monitoring` and `deployment` (`ansible/inventory/multinode`). Service groups are defined as children.
  Examples:
  - `[nova-api:children] nova`, `[nova:children] control`.
  - `[haproxy:children] network`. In the Ussuri example inventory, HAProxy and keepalived sit on the **network**
    nodes.
  - `[openvswitch:children] network, compute, manila-share`.
- **Groups that include `compute` in the example inventory:** `compute`, `openvswitch`, `neutron-ovn-metadata-agent`,
  `iscsid`, `multipathd`, `chrony`, `collectd`, `telegraf`, `monasca-agent`, `ceilometer-compute`,
  `ceilometer-ipmi`, `cyborg-agent`, `zun-compute`, `zun-cni-daemon`, `skydive-agent`, `prometheus-node-exporter`,
  `prometheus-cadvisor`, `masakari-monitors`, `ovn-controller-compute`.
- **The neutron play also targets every compute host.** It lists `compute` and `manila-share` explicitly
  (`site.yml:761-780`); the agents' `host_in_groups` decides what lands there.
- **Inventory order is semantically significant** [CODE]. `groups['<grp>'][0]` is the target of almost every
  `run_once`/`delegate_to` bootstrap step. Examples: `groups['nova-conductor'][0]` for cell creation and compute
  discovery; `groups['glance-api'][0]` as the only glance host with the default file backend (fact sheet C). Other
  index-sensitive logic:
  - keepalived priority is the index in `groups['haproxy']` (fact sheet A §1.8 C);
  - MariaDB restart waves use the index modulo 4 (fact sheet B §2).
