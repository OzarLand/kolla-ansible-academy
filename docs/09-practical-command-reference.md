# 09 — Practical Command Reference

Real `kolla-ansible` (Ussuri) invocations with what they select, their scope and their impact. The examples assume:

- the inventory is `/etc/kolla/multinode` (adapt `-i`);
- `globals.yml` and `passwords.yml` are in `/etc/kolla`;
- Ansible is 2.9.

The CLI → playbook mapping and the `kolla_serial` pass-through rules are in
[01 §2](01-repository-architecture.md); tag semantics are in [03](03-ansible-roles-and-tags-mapping.md).

Conventions:

- **Scope** = plays and hosts touched.
- **Restarts** = containers that *can* restart (only if drift is detected).
- **One-shot** = bootstrap containers that run regardless of drift.

---

## 1. Inspection (no changes)

| Goal | Command | Notes |
|---|---|---|
| List tags as Ansible sees them | `EXTRA_OPTS="--list-tags" kolla-ansible -i multinode deploy` | Works. Shows the inherited task tags (`common` appears nearly everywhere) |
| List hosts a run would target | `EXTRA_OPTS="--list-hosts" kolla-ansible -i multinode -t nova reconfigure` | Plays with `&enable_<svc>_True` patterns show **0 hosts**: the groups are created at run time |
| List tasks | `EXTRA_OPTS="--list-tasks" …` | **Not useful**: only `include_tasks` placeholders are shown (03 §2.6) |
| Render configs without restarting | `kolla-ansible -i multinode genconfig [-t <svc>] [--limit <hosts>]` | Writes `/etc/kolla/<svc>/` on the targets. All handlers are skipped. Also re-renders haproxy `services.d` for the tagged services |
| See what will restart | on each host: `docker exec -u root <container> /usr/local/bin/kolla_set_configs --check; echo $?` | 0 = no drift; 1 = drift → will restart on the next `deploy`/`reconfigure`/`deploy-containers`; 137 is also treated as drift; any other code (e.g. 2) is an error, not drift. Keep `-u root`: Kolla runs the check as root (`kolla_docker.py:544-578`), and containers that run as a service user cannot read the root-owned 0660 files in `/var/lib/kolla/config_files` |
| Check-mode run | `EXTRA_OPTS="--check --diff" kolla-ansible … reconfigure` | [NEEDS-LAB] `kolla_docker` does not support check mode, and many tasks register outputs used later. Expect failures or partial results; staging only |
| Pre-deployment checks | `kolla-ansible -i multinode prechecks [-t <svc>]` | Read-only (fact sheet E). `-t <svc>` skips the `prechecks` role (untagged) but runs `<svc>/precheck.yml` |

---

## 2. Day-2 commands

### 2.1 Reconfigure a single service

```bash
kolla-ansible -i multinode -t keystone reconfigure
```

- **Scope:**
  - haproxy play: keystone frontend only, on haproxy hosts;
  - keystone play: `common` on keystone hosts, then config, check-containers, bootstrap (db sync), a handler flush
    (restarts happen here), Fernet key distribution, Keystone registration and the sanity check
    (`roles/keystone/tasks/deploy.yml`; the sanity check is off by default, `kolla_enable_sanity_checks`). Unlike
    glance, placement, neutron and nova, keystone registers last.
- **Restarts:**
  - haproxy, on all haproxy hosts, only if the frontend changed;
  - per host (loop-notify): on each keystone host where any keystone container drifted, all keystone containers of
    that host restart (`keystone`, plus `keystone_ssh` and `keystone_fernet` with Fernet tokens). Hosts without drift
    do not restart. Drifted hosts restart in parallel, so a change common to all hosts (globals, `keystone.conf`, a
    new image) restarts keystone on all keystone hosts at once.
- **One-shot:** keystone db sync. Fernet keys are re-distributed.
- **Impact:** short identity outage if restarted.

### 2.2 Reconfigure Nova (control plane and computes)

```bash
kolla-ansible -i multinode -t nova reconfigure
```

- **Scope:**
  - haproxy (nova and nova-cell frontends);
  - the 10 nova plays;
  - `common` on every nova host **and every compute**.
- **One-shot:** 5 container runs (API DB sync, map_cell0, cell DB sync, list_cells ×2) plus RabbitMQ user/vhost, Keystone
  registration, SIGHUP of `nova_scheduler`, `discover_hosts` [LAB s01].
- **Restarts:** depend on the drift ([07](07-day2-operational-impact.md) §A). A nova-compute drift restarts
  `nova_compute`, `nova_libvirt` and `nova_ssh` on each compute where it occurs, so a change common to all computes
  restarts them on every compute [LAB s03].

### 2.3 Reconfigure only the Nova control plane (no compute impact)

```bash
kolla-ansible -i multinode -t nova-api reconfigure
```

- **Scope:** the `nova-api`-tagged plays (API DB bootstrap, nova role, scheduler refresh) on controllers, plus the
  haproxy nova include.
- **Not touched:** conductors and computes (`nova-cell` plays).

### 2.4 Reconfigure only the cell part (conductors, consoles, computes)

```bash
kolla-ansible -i multinode -t nova-cell reconfigure
```

### 2.5 Compute changes in controlled batches (recommended pattern)

```bash
# 1. write the config everywhere, restart nothing
kolla-ansible -i multinode -t nova-cell genconfig
# 2. review: diff /etc/kolla/nova-compute/nova.conf on a sample of hosts
# 3. apply batch by batch (only check-containers + handlers run)
kolla-ansible -i multinode -t nova-cell deploy-containers --limit 'compute[0:9]'
kolla-ansible -i multinode -t nova-cell deploy-containers --limit 'compute[10:19]'
```

- `deploy-containers` runs only `check-containers.yml`, which detects the config drift written by `genconfig`
  through `kolla_set_configs --check` [LAB s14 → s15].
- Each batch restarts only its hosts. No bootstrap containers, no Keystone registration and no haproxy play run.
- **Caveat:** `genconfig -t nova-cell` also renders the conductor and console config on controllers. Include them
  in a batch too, or the drift stays pending there.
- The `compute[0:9]` slice syntax is standard Ansible host-pattern slicing.

### 2.6 Rolling reconfigure with `ANSIBLE_SERIAL`

```bash
ANSIBLE_SERIAL=10 kolla-ansible -i multinode -t nova reconfigure
```

- Plays that set `serial: kolla_serial` run in batches of 10 hosts: gather-facts, the haproxy play, all nova plays
  and almost every service play. Not batched: mariadb, rabbitmq and outward rabbitmq (no `serial`; their rolling
  logic is in the handlers); cyborg, which uses `serial` instead of `kolla_serial` and so ignores `ANSIBLE_SERIAL`
  (bug, `site.yml:1028`); and the helper plays (group-by, CentOS check, prechecks), which change nothing.
- A `run_once` task runs once per batch of its own play. For `-t nova`, the API DB sync (`nova_api_bootstrap`,
  `map_cell0`) and the Keystone registration are `run_once` in plays that target only controller groups (nova-api,
  nova-scheduler, nova-super-conductor), so they repeat only if those groups are larger than the batch. The cell DB
  sync (`nova_cell_bootstrap`) is not `run_once`: it is gated on the first nova-conductor and runs once at any serial
  value. Compute discovery runs on the first compute of each nova-cell batch, so it repeats once per batch that
  contains computes [LAB s16, serial=1: `nova_api_bootstrap` ×3, `nova_cell_bootstrap` ×1, discover_hosts ×3].
- Batches apply per play: the whole fleet passes the nova-cell play before the next play starts.

### 2.7 Neutron

```bash
kolla-ansible -i multinode -t neutron reconfigure                        # server + all agents (+ computes)
kolla-ansible -i multinode -t neutron reconfigure --limit network01       # one network node at a time
kolla-ansible -i multinode -t openvswitch reconfigure --limit compute042  # OVS on one host
```

- `-t neutron` targets every compute (the neutron play includes `compute`).
- Network nodes should be done one at a time. Restarting `neutron_l3_agent` deletes namespaces if
  `enable_neutron_agent_ha` (R6).

### 2.8 Avoid touching HAProxy during a service run

```bash
kolla-ansible -i multinode -t nova --skip-tags haproxy reconfigure
```

- `--skip-tags haproxy` drops the whole haproxy play, including the per-service frontend includes.
- Use it when frontends are not meant to change. Otherwise a changed `services.d/<svc>.cfg` restarts HAProxy on all
  haproxy hosts.

### 2.9 Apply `common` changes (fluentd, cron, kolla_toolbox)

```bash
# -t common is a NO-OP in Ussuri (LAB s08). Use a play that reaches the hosts first:
kolla-ansible -i multinode -t chrony reconfigure            # chrony play includes all hosts by default
kolla-ansible -i multinode -t chrony reconfigure --limit 'compute[0:49]'
```

- This also reconfigures chrony on those hosts.
- If `enable_chrony` is `no`, use any service tag whose play covers the hosts, e.g. `-t openvswitch` for network and
  compute hosts.

### 2.10 Images

```bash
kolla-ansible -i multinode pull                         # all enabled images on all hosts
kolla-ansible -i multinode -t nova pull --limit compute # nova-cell + common images on computes
kolla-ansible -i multinode upgrade                      # recreate from new images (after pull)
ANSIBLE_SERIAL=20 kolla-ansible -i multinode -t nova upgrade
```

- `pull` never changes running containers [LAB s10].
- `deploy`/`reconfigure` never pull an image that is already present locally, even if the registry has a newer
  build under the same tag [LAB s09a].
- After a `pull` that downloaded something, the next `deploy`, `reconfigure` or `upgrade` **recreates** the affected
  containers. Loop-notify restarts their siblings [LAB s09c].

### 2.11 Add a compute node

```bash
kolla-ansible -i multinode bootstrap-servers --limit compute501
kolla-ansible -i multinode pull --limit compute501
kolla-ansible -i multinode deploy --limit compute501
```

[LAB s17: details in [07](07-day2-operational-impact.md) §G]

- Facts for **all** hosts are still gathered, sequentially from `compute501` (`gather-facts.yml:29-50`). Enable fact
  caching for large inventories.
- Discovery runs from the first compute of the batch, delegated to `nova-conductor[0]`. That host is outside the
  limit, but `delegate_to` works.
- `/etc/hosts` on existing hosts is **not** updated with the new compute (`bootstrap-servers` was limited). Live
  migration with `libvirt_tls` (hostname-based) and RabbitMQ name resolution may need a full `bootstrap-servers` run
  later (fact sheet E §3).

### 2.12 Remove or replace a controller

- Changing the `rabbitmq` membership changes the transport URL everywhere, and changing `memcached` changes the
  memcache server lists. In the default inventory both are children of `control`, so a controller change does both.
  That restarts all nova and neutron containers on all computes, and most control-plane services
  (R3, R4, [LAB s12]). A `memcached`-only change does not touch nova-compute (the compute `nova.conf` has no
  memcache list) but still restarts the neutron agents on computes (`neutron.conf`).
- Galera and RabbitMQ membership changes need their own procedures. Ussuri has no automated member removal
  (fact sheets A, B).

### 2.13 Database operations

```bash
kolla-ansible -i multinode mariadb_backup               # full (default) or --incremental
kolla-ansible -i multinode mariadb_recovery             # ONLY when the whole Galera cluster is down
```

### 2.14 Stop and destroy (dangerous)

```bash
kolla-ansible -i multinode stop --yes-i-really-really-mean-it -t heat --limit control03
kolla-ansible -i multinode destroy --yes-i-really-really-mean-it   # never on production
```

- `stop` honours `skip_stop_containers` (e.g. `-e '{"skip_stop_containers": ["nova_libvirt"]}'`).

---

## 3. Quick lookup: tag → scope → typical impact

| Command | Hosts touched (default inventory) | Can restart | One-shot containers | Typical duration driver |
|---|---|---|---|---|
| `-t keystone reconfigure` | haproxy, control | keystone ×3, haproxy | keystone db sync | small |
| `-t glance reconfigure` | haproxy, `glance-api` | glance-api, haproxy | db sync + MariaDB global flag toggle | small |
| `-t placement reconfigure` | haproxy, control | placement-api, haproxy | db sync | small |
| `-t nova reconfigure` | haproxy, control, **all computes** | all nova incl. **libvirt**, haproxy | 5 runs | number of computes |
| `-t nova-api reconfigure` | haproxy, control | nova-api, scheduler, haproxy | 2 | small |
| `-t nova-cell reconfigure` | haproxy (console-proxy frontends), control (conductor, consoles), **all computes** | conductor, consoles, compute, libvirt, ssh; haproxy if a console-proxy frontend changed | 2 + discovery | number of computes |
| `-t neutron reconfigure` | haproxy, control, network, **all computes** | server, all agents, haproxy | none by default (neutron db sync is deploy-only while `neutron_enable_rolling_upgrade` is `yes`) | number of computes |
| `-t openvswitch reconfigure` | network, **all computes** | openvswitch_db/vswitchd | – | number of computes |
| `-t haproxy reconfigure` | haproxy | haproxy, keepalived, common | – | small |
| `-t chrony reconfigure` | **all hosts** | chrony + common (fluentd, cron, toolbox) | – | number of hosts |
| `-t mariadb reconfigure` | haproxy, mariadb | mariadb (4 waves), clustercheck, haproxy | – | Galera sync |
| `-t rabbitmq reconfigure` | haproxy, rabbitmq (+outward) | rabbitmq one by one, haproxy | – | broker start |
| `reconfigure` (no tag) | all | everything that drifted | db sync of every enabled service except neutron (see the neutron row) | number of hosts × tasks |
| `deploy-containers -t X` | X's hosts | X (drifted only) | none | small per host |
| `genconfig -t X` | X's hosts (+haproxy) | none | none | templating |
| `pull -t X` | X's hosts | none | none | image size × hosts |
