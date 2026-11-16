# 03 — Ansible Roles and Tags Mapping

How tags actually select work in Kolla-Ansible Ussuri, and what each important tag executes. Read
[01](01-repository-architecture.md) §3–4 first for the play and role skeleton.

> **The single most important rule:** a tag name does **not** describe the work a run performs. What runs depends on:
>
> - which plays carry or inherit the tag;
> - the `common` role reaching each host for the first time;
> - the haproxy play's per-service includes;
> - handlers, which are **never filtered by tags**;
> - Ansible 2.9's loop-notify semantics.
>
> Everything below was verified against the source and, where marked [LAB], by executing the real `site.yml` in the
> lab ([annex/lab](../annex/lab/README.md)).

---

## 1. Where tags are defined

| Source | Example (evidence) | Inherited by |
|---|---|---|
| **Play-level tags** | `haproxy` play: `tags: [haproxy]` (`site.yml:132-133`). All 10 plays of `nova.yml`, e.g. `tags: [nova, nova-cell, nova-cell-deploy, nova-cell-upgrade]` (`nova.yml:127-131`) | every task of the play, including role dependencies (`common`) and statically imported roles |
| **Role-level tags** in `roles:` | `- { role: neutron, tags: neutron, when: … }` (`site.yml:777-780`). memcached has `tags: [memcache, memcached]` (`:489`) | every task of the role, **including its meta dependency `common`** |
| **Task-level tags on `include_role`** | haproxy block: `include_role: {name: nova, tasks_from: loadbalancer}` with `tags: [nova, nova-api]` (`site.yml:293-299`) | the include statement only; see §2.3 |
| **`tags: always`** | gather-facts and group_by plays (`gather-facts.yml:21,50`, `site.yml:95`). `import_role: haproxy-config` in **every** one of the 49 `loadbalancer.yml` files (plus nova-cell's `proxy_loadbalancer.yml` and `cell_proxy_loadbalancer.yml`). `congress/tasks/register.yml:8` | runs regardless of `--tags`, unless the enclosing dynamic include is skipped |
| **Tags inside roles** | `common/tasks/main.yml:3,9` (`tags: common`). `nova/tasks/stop.yml:7` (`tags: nova`). `service-rabbitmq/tasks/main.yml:43` (`tags: [service-rabbitmq]`) | – |
| **Other playbooks** | `kolla-host.yml:10` (`baremetal`), `mariadb_backup.yml:6`, `mariadb_recovery.yml:6` (`mariadb`), `bifrost.yml:6` (`bifrost`) | – |

The full per-play tag list is generated in [annex/generated-inventory.md §1](../annex/generated-inventory.md). Per-service
cards (tags, task flow, handlers, node types) are in [annex/service-cards.md](../annex/service-cards.md). The
output of `ansible-playbook --list-tags` against the real `site.yml` is in
[annex/lab/list-tags-site.txt](../annex/lab/list-tags-site.txt). Per play it shows the *task tags* after inheritance;
note that **`common` appears in almost every play**.

---

## 2. Ansible 2.9 semantics that Kolla relies on

### 2.1 Dynamic `include_tasks` and tag inheritance [ANSIBLE, LAB]

Every role starts with `include_tasks: "{{ kolla_action }}.yml"` (dynamic). In Ansible 2.9, tasks inside a
dynamically included file:

- **do inherit** the tags of the enclosing *role* and *play*: `nova`, `neutron`, `chrony`, `haproxy`, …;
- **do not inherit** tags written on the `include_tasks` statement itself (they apply to the include only, unless
  `apply:` is used — Kolla never uses `apply:`).

Minimal reproduction ([annex/lab/tagdemo](../annex/lab/tagdemo/), output in
[annex/lab/tagdemo.out](../annex/lab/tagdemo.out)):

```
===== --tags common      → include_tasks runs, but "COMMON task inside included file" does NOT run
===== --tags nova        → the common task DOES run (inherited play tag), then the service task
===== --tags chrony      → common task runs in the chrony play (first play the host appears in)
```

### 2.2 Handlers ignore tags [ANSIBLE]

A notified handler runs even if its own tags do not match `--tags`. This is why `-t keystone` can restart HAProxy:
the `haproxy-config` task under `tags: always` notifies `Restart haproxy container` (fact sheet A §1.9, toy
reproduction).

### 2.3 `include_role` + `tags: always` inside (the haproxy play) [CODE, ANSIBLE]

The haproxy play's per-service `include_role` statements are dynamic too. Their own tags (`keystone`, `nova`, …)
only select the include statement. For the work inside to run, every `loadbalancer.yml` wraps its single
`import_role: haproxy-config` with `tags: always` (e.g. `roles/keystone/tasks/loadbalancer.yml:2-7`). Net effect:
`-t <svc>` runs that service's haproxy config on all haproxy hosts.

### 2.4 Loop notify: one changed item notifies the handlers of all items [ANSIBLE, LAB — new finding]

Ansible 2.9.27 `plugins/strategy/__init__.py:616-623`:

```python
for result_item in result_items:
    if '_ansible_notify' in result_item:
        if task_result.is_changed():          # <- aggregate status of the WHOLE loop
            for handler_name in result_item['_ansible_notify']:
                ... notify handler_name
```

`_ansible_notify` is attached to every executed (non-skipped) loop item (`executor/task_executor.py:790`). If *any*
item changed, the templated handler name of *every* executed item is notified. Kolla's `config.yml` and
`check-containers.yml` loop over `<role>_services` with `notify: "Restart {{ item.key }} container"`. So **a change
that concerns one container restarts every container of that role on that host.**

Minimal reproduction ([annex/lab/notify-loop.yml](../annex/lab/notify-loop.yml),
[output](../annex/lab/notify-loop.out)): only `nova-compute` reports changed, yet the handlers for `nova-libvirt`,
`nova-ssh` and `nova-compute` all run. Skipped items do not notify.

Confirmed on the real playbook [LAB s03]. An override that only touches `/etc/kolla/config/nova/nova-compute.conf`
restarted `nova_compute`, **`nova_libvirt` and `nova_ssh`** on every compute host. In s04, a scheduler-only override
restarted `nova_api` *and* `nova_scheduler`. Impact analysis in [07](07-day2-operational-impact.md).

Ussuri supports only Ansible 2.8–2.9 (`tools/kolla-ansible:58-59`). Whether newer Ansible changed this behaviour is
irrelevant to Ussuri. It was not tested here.

### 2.5 `run_once` with `serial` [ANSIBLE]

With `kolla_serial` > 0, a `run_once` task runs once **per batch**, not once per play. This applies to bootstrap
containers, Keystone registration and DB creation. It is not harmful for idempotent steps, but it multiplies the
number of DB-sync containers and Keystone API calls (fact sheet C, cross-cutting table).

Confirmed [LAB s16, `kolla_serial=1`]:

- `nova_api_bootstrap` ran 3 times, once per controller batch, and each time on that batch's host.
- `map_cell0` ran 3 times.
- The compute registration wait plus `list_cells` ran once per compute batch.
- Nova containers restarted strictly one host at a time.

### 2.6 `--list-tasks` is not usable for Kolla [LAB]

Because of §2.1, `ansible-playbook site.yml --list-tasks -t nova` lists only `include_tasks` placeholders for each role.
`common`'s inner tasks, `config.yml` and `check-containers.yml` are invisible
([annex/lab/list-tasks-nova.txt](../annex/lab/list-tasks-nova.txt)). Plays whose host pattern depends on the
`group_by` groups (`&enable_nova_True`) also resolve to **0 hosts** at list time. Those groups are created at run time
(`[WARNING]: Could not match supplied host pattern, ignoring: enable_nova_True`). Use the execution lab, or
`--check` on a staging environment, instead.

---

## 3. What a tag really executes (master table)

"Target hosts" assumes the Ussuri `multinode` example inventory. "Containers" lists those that *can* be restarted
or recreated, **only if** a config, parameter or image change is detected. With no change, nothing restarts
[LAB t1, s01]. "common" means the `common` role runs on every host of the first matching play
(fluentd/cron/kolla_toolbox config + container check).

| Tag | Plays / roles selected | Tasks executed | Target hosts | Containers that can restart | Other side effects | Potential impact |
|---|---|---|---|---|---|---|
| *(no tag)* | all 84 plays | everything for `kolla_action` | all | all | all bootstrap/DB-sync containers, Keystone registration of all services | Full blast radius |
| `common` | include + `set_fact` in each play | **nothing else** [LAB s08] | all (no-op) | none | sets `common_run=True` | **No-op.** It does *not* reconfigure fluentd/cron/toolbox |
| `haproxy` | haproxy play: `common`, haproxy role (config-host, config, check-containers), all 49 loadbalancer includes | sysctl, `ip_vs`, `haproxy.cfg`, `keepalived.conf`, certs, every `services.d/*.cfg` | haproxy hosts | `haproxy`, `keepalived`, `fluentd`/`cron`/`kolla_toolbox` (via common) | – | API and DB path interruption if anything changed; VIP may move (A §1.8) |
| `<svc>` (e.g. `keystone`, `glance`, `cinder`, `heat`, `horizon`, `placement`) | haproxy play (that service's include only) + the service play | haproxy `services.d/<svc>.cfg`; `common` on the service hosts; register, config, check-containers, bootstrap of the service | haproxy hosts + service hosts | haproxy (if its frontend changed), all of the service's containers on a host if any changed (§2.4), common containers | DB sync container, Keystone registration | Service API outage during the parallel restart; HAProxy restart if the frontend changed |
| `nova` | haproxy (nova + nova-cell includes), all 10 `nova.yml` plays | API/cell0/cell DB bootstrap, cell create/update, nova + nova-cell config/check, discovery, scheduler SIGHUP; reload/online-migration plays are no-ops except on `upgrade` | haproxy, `nova-api`, `nova-scheduler`, `nova-conductor`, consoles, **every `compute`** | nova API/scheduler/conductor/console proxies, **nova_compute, nova_libvirt, nova_ssh on all computes**, common containers | 5 one-shot container runs on `control01` (API DB sync, map_cell0, cell DB sync, list_cells ×2) [LAB s01]; `kill -HUP` of nova_scheduler on every scheduler | See [05](05-nova-deep-dive.md), [07](07-day2-operational-impact.md) §A |
| `nova-api` | haproxy nova include, API DB bootstrap play, nova play, scheduler cell-cache refresh, API reload/migrations | – | controllers + haproxy | nova_api, nova_scheduler, nova_super_conductor | API DB sync, map_cell0 | Does **not** touch computes |
| `nova-cell` | haproxy nova-cell include, cell DB bootstrap, nova-cell play, cell reload/migrations | – | conductors, consoles, **all computes** | nova_conductor, consoles, nova_compute, nova_libvirt, nova_ssh | cell DB sync, cell create/update, discovery | Touches every compute |
| `nova-bootstrap`, `nova-api-bootstrap`, `nova-cell-bootstrap` | the two bootstrap plays (`nova.yml:29-96`) | DB creation, DB sync containers, cell mapping | `nova-api[0]`, `nova-conductor[0]` | none (one-shot containers) | – | Schema changes only if images are newer |
| `nova-reload`, `nova-api-reload`, `nova-cell-reload` | reload plays (`nova.yml:164-225`) | `recreate_or_restart` of nova services **only when `kolla_action == upgrade`** | as named | on upgrade: all nova services | – | No-op outside upgrade |
| `nova-online-data-migrations` (+ `-api-`, `-cell-`) | `nova.yml:230-272` | `nova-manage db online_data_migrations` | `nova-api[0]`, `nova-conductor[0]` | – | upgrade only | – |
| `nova-refresh-scheduler-cell-cache` | `nova.yml:140-156` | `kill -HUP` of `nova_scheduler` (`roles/nova/tasks/refresh_scheduler_cell_cache.yml:10`) | nova-scheduler hosts | none (signal) | – | Runs on **every** deploy/reconfigure with `nova` or `nova-api` |
| `neutron` | haproxy neutron include, neutron play (hosts include **`compute`** and `manila-share`) | register, config-host (sysctl, modules), config, check-containers, DB bootstrap (deploy only) | haproxy, neutron-server, network agent hosts, **every compute** | neutron_server, all agents on a host if any changed (§2.4), common | – | Data-plane flows resync; L3/DHCP agent restarts on network nodes ([07](07-day2-operational-impact.md) §B) |
| `openvswitch` | openvswitch play | module load, config, check-containers, **post-config** (`ovs-vsctl set … system-id`, bridge ensure) | `openvswitch` group (network + **compute**) | `openvswitch_db`, `openvswitch_vswitchd` | `Set system-id` reports *changed* on every run | A vswitchd restart interrupts **all VM traffic** on that host |
| `ovn` | ovn play | config, check-containers, chassis bootstrap (`ovs-vsctl` × ~5 per host) | OVN DB hosts, **every compute and network** | ovn NB/SB DB, northd, ovn-controller | overwrites `ovn-cms-options` | A §5.8 |
| `mariadb` | haproxy mariadb include, mariadb play (no serial) | cluster lookup, config, check, rolling restart handlers | mariadb hosts | mariadb (modulo-4 waves), clustercheck | – | B §2 |
| `rabbitmq` | haproxy include, **both** rabbitmq plays (`rabbitmq` and `outward-rabbitmq` share the tag) | – | rabbitmq hosts | rabbitmq (one by one) | – | B §6 |
| `memcached` / `memcache` | memcached play (`memcache` does **not** select the haproxy include) | – | memcached hosts | memcached (all at once) | – | Token cache and Horizon session flush |
| `chrony` | chrony play (first play for **every** host) | `common` + chrony on all hosts | **all hosts** | chrony, fluentd, cron, kolla_toolbox | – | The cheapest way to reconfigure `common` fleet-wide (§4) |
| `iscsi` | iscsi play | – | iscsid (compute + storage), tgtd | iscsid, tgtd | – | Volume attach path on computes (D part 2) |
| `service-rabbitmq` | the RabbitMQ user/vhost blocks inside roles | **nothing** on its own (inside dynamic includes) | – | – | – | Not usable as a selector |
| `baremetal` | `kolla-host.yml` only | host preparation | all | **Docker daemon restart if `daemon.json` changed** | packages, users, `/etc/hosts` | E §1–7 |

---

## 4. Practical consequences

1. **"Only reconfigure `common`" is not possible with a tag.** `-t common` is a no-op [LAB s08]. Changes to fluentd,
   cron or kolla_toolbox config reach a host only when *some* service play that includes the host runs with
   matching tags, or with no tags:
   - `-t chrony` reaches every host (chrony runs everywhere by default);
   - `-t nova` reaches all nova hosts;
   - `-t neutron` reaches network and compute hosts.
2. **A service tag drags in shared infrastructure.**
   - `-t nova` also runs the haproxy play (nova frontends), `common` on every nova host and compute, Keystone
     registration and the DB bootstrap containers [LAB s01].
   - `-t neutron` also runs `common` on all computes.
   - A tag never restricts *which hosts* a play targets; use `--limit` for that.
3. **Handlers make the impact data-dependent.** The same command can be a no-op or a fleet-wide restart, depending
   on whether a rendered file changed. That in turn depends on *global* variables (`enable_*`, group membership,
   passwords), not only on the tagged service [LAB s07].
4. **`--skip-tags` can avoid the haproxy play.** `--skip-tags haproxy` skips the entire haproxy play, including the
   per-service includes (fact sheet A §1.9), while leaving the service play untouched. Combining `-t nova` with
   `--skip-tags haproxy` is valid. Since every tag selects across plays, `--skip-tags` is the only way to cut the
   haproxy part out of a service run.
5. **Tags do not change `kolla_action` logic.** `-t nova deploy` and `-t nova reconfigure` execute the same tasks,
   except for the `deploy`-only Neutron bootstrap and the `kolla_serial` pass-through (01 §2).

---

## 5. Role → handler map (core services)

Handlers run in **definition order** after `meta: flush_handlers` (end of `deploy.yml`) or at the end of the play.
All use `kolla_docker` `recreate_or_restart_container` unless noted. The complete list for all roles is in
[annex/generated-inventory.md §3](../annex/generated-inventory.md).

| Role | Handlers (definition order) | Special logic | Evidence |
|---|---|---|---|
| common | Restart fluentd → Restart kolla-toolbox (→ Initializing toolbox: `docker exec … ansible --version`) → Restart cron | – | `roles/common/handlers/main.yml` |
| haproxy | Restart haproxy → Restart keepalived → Waiting for haproxy → Waiting for VIP | `wait_for` on the monitor port | A §1.5 |
| mariadb | Bootstrap MariaDB cluster (listen) … → Restart MariaDB on existing cluster members (`include_tasks restart_services.yml`, loop 0..3, `index % 4 == item`) → Start MariaDB on new nodes … | 4 restart waves, waiting for port + WSREP `Synced` | `roles/mariadb/handlers/main.yml:66-78`, B §2 |
| rabbitmq | Restart rabbitmq: first node, then the others one by one | `rabbitmqctl wait` | B §6 |
| keystone | Restart keystone, keystone-ssh, keystone-fernet | all hosts at once | B §8 |
| nova | Restart nova-super-conductor → nova-scheduler → nova-api | skipped on upgrade when `nova_safety_upgrade` | `roles/nova/handlers/main.yml` |
| nova-cell | Restart nova-conductor → novncproxy → spicehtml5proxy → serialproxy → nova-ssh → **nova-libvirt** (retries 5; notifies Create libvirt SASL user) → Create libvirt SASL user → nova-compute → nova-compute-ironic → fake → Wait for nova-compute services (upgrade only, 30 s pause) | libvirt is restarted **before** nova-compute | `roles/nova-cell/handlers/main.yml:1-196` |
| neutron | one handler per agent/server | none | `roles/neutron/handlers/main.yml` |
| openvswitch | Restart openvswitch-db-server (→ Waiting for openvswitch_db) → Restart openvswitch-vswitchd | – | `roles/openvswitch/handlers/main.yml:1-42` |
