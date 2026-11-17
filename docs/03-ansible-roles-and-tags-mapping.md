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
| **`tags: always`** | gather-facts and group_by plays (`gather-facts.yml:21,50`, `site.yml:95`). `import_role: haproxy-config` in 48 of the 49 `loadbalancer.yml` files. nova-cell's `loadbalancer.yml` reaches it through `import_tasks: proxy_loadbalancer.yml` → looped `include_tasks: cell_proxy_loadbalancer.yml` → `import_role`, with `tags: always` at every level (`roles/nova-cell/tasks/loadbalancer.yml:21,57,93`). `congress/tasks/register.yml:8` | runs regardless of `--tags`, unless the enclosing dynamic include is skipped |
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

Run it with `-e kolla_action=reconfigure`, which the included file name needs. Ansible 2.8.20 selects exactly the same
tasks ([annex/lab/tagdemo.ansible-2.8.out](../annex/lab/tagdemo.ansible-2.8.out)). The code that drops the include's
own tags, `Task._get_parent_attribute` in `playbook/task.py`, is identical in 2.8.20 and 2.9.27 [LAB].

### 2.2 Handlers ignore tags [ANSIBLE]

A notified handler runs even if its own tags do not match `--tags`. This is why `-t keystone` can restart HAProxy:
the `haproxy-config` task under `tags: always` notifies `Restart haproxy container` (fact sheet A §1.9, toy
reproduction).

### 2.3 `include_role` + `tags: always` inside (the haproxy play) [CODE, ANSIBLE]

The haproxy play's per-service `include_role` statements are dynamic too. Their own tags (`keystone`, `nova`, …)
only select the include statement. For the work inside to run, 48 of the 49 `loadbalancer.yml` files wrap a single
`import_role: haproxy-config` with `tags: always` (e.g. `roles/keystone/tasks/loadbalancer.yml:2-7`). nova-cell's file
reaches the same role through `import_tasks: proxy_loadbalancer.yml`, a looped `include_tasks:
cell_proxy_loadbalancer.yml` and then `import_role` (`cell_proxy_loadbalancer.yml:3-12`), with `tags: always` at
every level, so the effect is the same. Net effect: `-t <svc>` runs that service's haproxy config on all haproxy hosts.

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

Ussuri supports only Ansible 2.8–2.9 (`tools/kolla-ansible:58-59`). The behaviour is **identical on Ansible 2.8.20**
[LAB]. The reproduction gives the same three handler runs
([annex/lab/notify-loop.ansible-2.8.out](../annex/lab/notify-loop.ansible-2.8.out)), and the code block is unchanged:
in 2.8.20 it is `plugins/strategy/__init__.py:540-557`, the same as 2.9.27's `:609-626`. Newer Ansible is irrelevant
to Ussuri and was not tested.

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
(fluentd/cron/kolla_toolbox config + container check). Apart from the `common`, `service-rabbitmq` and `baremetal`
rows, every role below except memcached has `common` as a meta dependency. A tag that selects a haproxy include
can also restart `haproxy` if that frontend changed (§2.2).

| Tag | Plays / roles selected | Tasks executed | Target hosts | Containers that can restart | Other side effects | Potential impact |
|---|---|---|---|---|---|---|
| *(no tag)* | all 84 plays | everything for `kolla_action` | all | all | all bootstrap/DB-sync containers, Keystone registration of all services | Full blast radius |
| `common` | include + `set_fact` in each play | **nothing else** [LAB s08] | all (no-op) | none | sets `common_run=True` | **No-op.** It does *not* reconfigure fluentd/cron/toolbox |
| `haproxy` | haproxy play: `common`, haproxy role (config-host, config, check-containers), all 49 loadbalancer includes evaluated, but only those of enabled services run (12 in the lab [LAB s19]; placement's include has no `when`) | sysctl, `ip_vs`, `haproxy.cfg`, `keepalived.conf`, certs, the `services.d/*.cfg` of every enabled service | haproxy hosts | `haproxy`, `keepalived`, `fluentd`/`cron`/`kolla_toolbox` (via common) | – | API and DB path interruption if anything changed; VIP may move (A §1.8) |
| `<svc>` (e.g. `keystone`, `glance`, `cinder`, `heat`, `placement`; `horizon` differs, see below the table) | haproxy play (that service's include only) + the service play | haproxy `services.d/<svc>*.cfg`; `common` on the service hosts; register, config, check-containers, bootstrap of the service | haproxy hosts + service hosts | haproxy (if its frontend changed), all of the service's containers on a host if any changed (§2.4), common containers | DB sync container, Keystone registration | Service API outage during the parallel restart; HAProxy restart if the frontend changed |
| `nova` | haproxy (nova + nova-cell includes), all 10 `nova.yml` plays | API/cell0/cell DB bootstrap, cell create/update, nova + nova-cell config/check, discovery, scheduler SIGHUP; reload/online-migration plays are no-ops except on `upgrade` | haproxy, `nova-api`, `nova-scheduler`, `nova-conductor`, consoles, **every `compute`** | nova API/scheduler/conductor/console proxies, **nova_compute, nova_libvirt, nova_ssh on all computes**, common containers | 5 one-shot container runs on `control01` (API DB sync, map_cell0, cell DB sync, list_cells ×2) [LAB s01]; RabbitMQ vhost/user for the cell; `kill -HUP` of nova_scheduler on every scheduler | See [05](05-nova-deep-dive.md), [07](07-day2-operational-impact.md) §A |
| `nova-api` | haproxy nova include, API DB bootstrap play, nova play, scheduler cell-cache refresh, API reload/migrations | haproxy-config for the nova API/metadata frontends; `common` on nova-api and nova-scheduler hosts; nova_api + nova_cell0 DB/user creation, API DB sync and `map_cell0` on `nova-api[0]`; nova role: Keystone registration, config, check-containers, flush; scheduler SIGHUP | controllers + haproxy | nova_api, nova_scheduler, nova_super_conductor, fluentd/cron/kolla_toolbox (via common) | API DB sync, map_cell0 | Does **not** touch computes |
| `nova-cell` | haproxy nova-cell include, cell DB bootstrap, nova-cell play, cell reload/migrations | haproxy-config for the console-proxy frontends; `common` on conductors, console hosts and computes; on the first conductor: cell DB/user, RabbitMQ vhost/user, cell DB sync, cell create/update; nova-cell role: config-host (`br_netfilter`, sysctl), config, check-containers, flush, then compute discovery delegated to the first conductor | conductors, consoles, **all computes** | nova_conductor, consoles, nova_compute, nova_libvirt, nova_ssh, fluentd/cron/kolla_toolbox (via common, on conductors, consoles and every compute) | cell DB sync, cell create/update, RabbitMQ vhost/user for the cell, discovery | Touches every compute |
| `nova-bootstrap`, `nova-api-bootstrap`, `nova-cell-bootstrap` | the two bootstrap plays (`nova.yml:29-96`); their `include_role` of nova / nova-cell also pulls in the `common` meta dependency | `common`, then DB creation, DB sync containers, cell mapping | `common`: all `nova-api` hosts (API play) and all `nova-conductor` hosts (cell play); DB tasks and one-shot containers: `nova-api[0]`, `nova-conductor[0]` | fluentd/cron/kolla_toolbox (via common) [LAB s07, under `-t nova`]; no nova service; one-shot bootstrap containers | RabbitMQ vhost/user for the cell | Schema changes only if images are newer |
| `nova-reload`, `nova-api-reload`, `nova-cell-reload` | reload plays (`nova.yml:164-225`) | `recreate_or_restart` of nova services **only when `kolla_action == upgrade`** | as named | on upgrade: all nova services | – | No-op outside upgrade |
| `nova-online-data-migrations` (+ `-api-`, `-cell-`) | `nova.yml:230-272` | `nova-manage db online_data_migrations` | `nova-api[0]`, `nova-conductor[0]` | – | upgrade only | – |
| `nova-refresh-scheduler-cell-cache` | `nova.yml:140-156` (`import_role: nova`, which pulls in the `common` dependency) | `common` (if not yet run on the host in this run), then `kill -HUP` of `nova_scheduler` (`roles/nova/tasks/refresh_scheduler_cell_cache.yml:10`) | nova-scheduler hosts | `nova_scheduler` only gets SIGHUP (no restart); fluentd/cron/kolla_toolbox (via common) when the tag is used alone | – | Runs on **every** deploy/reconfigure with `nova` or `nova-api`, where common has already run, so it adds only the signal ([list-tasks-nova.txt](../annex/lab/list-tasks-nova.txt) play #37) |
| `neutron` | haproxy neutron include, neutron play (hosts include **`compute`** and `manila-share`) | register, config-host (sysctl, modules), config, check-containers, DB and DB-user creation (every deploy and reconfigure), `bootstrap_neutron` DB-sync container (deploy only while `neutron_enable_rolling_upgrade` keeps its default `yes`, `bootstrap_service.yml:21-22`) | haproxy, neutron-server, network agent hosts, **every compute** | neutron_server, all agents on a host if any changed (§2.4), common | – | Data-plane flows resync; L3/DHCP agent restarts on network nodes ([07](07-day2-operational-impact.md) §B) |
| `openvswitch` | openvswitch play | module load, config, check-containers, **post-config** (`ovs-vsctl set … system-id`, bridge ensure) | `openvswitch` group (network + **compute**) | `openvswitch_db`, `openvswitch_vswitchd`, fluentd/cron/kolla_toolbox (via common) | `Set system-id` reports *changed* on every run | A vswitchd restart interrupts **all VM traffic** on that host |
| `ovn` | ovn play | config, check-containers, chassis bootstrap (`ovs-vsctl` × ~5 per host) | OVN DB hosts, **every compute and network** | ovn NB/SB DB, northd, ovn-controller, fluentd/cron/kolla_toolbox (via common) | overwrites `ovn-cms-options` | A §5.8 |
| `mariadb` | haproxy mariadb include, mariadb play (no serial) | cluster lookup, config, check, rolling restart handlers | mariadb hosts | mariadb (modulo-4 waves), clustercheck, fluentd/cron/kolla_toolbox (via common) | – | B §1 |
| `rabbitmq` | haproxy include, **both** rabbitmq plays (`rabbitmq` and `outward-rabbitmq` share the tag) | haproxy-config for the `rabbitmq_management` frontend; `common`; config (`config.json`, `rabbitmq-env.conf`, `rabbitmq.conf`, `erl_inetrc`, `advanced.config`, `definitions.json`), check-containers, volume creation and, only for a new volume, the `rabbitmq_bootstrap` container; flush | rabbitmq hosts | rabbitmq (one by one), fluentd/cron/kolla_toolbox (via common) | – | B §2 |
| `memcached` / `memcache` | memcached play (`memcache` does **not** select the haproxy include) | config dir + `config.json`, check-containers. No `common` and no flush: the restart handler runs at the end of the play. `memcached` also selects the haproxy include, which renders a frontend only with `enable_haproxy_memcached` (default `no`) | memcached hosts | memcached (all at once) | – | Token cache and Horizon session flush |
| `chrony` | chrony play (first play for **every** host) | `common` + chrony on all hosts | **all hosts** | chrony, fluentd, cron, kolla_toolbox | – | The cheapest way to reconfigure `common` fleet-wide (§4) |
| `iscsi` | iscsi play | `common`; config-host (load and persist `configfs`), config dirs + `config.json`, check-containers, flush | iscsid (compute + storage), tgtd | iscsid, tgtd, fluentd/cron/kolla_toolbox (via common) | – | Volume attach path on computes (D §5.2) |
| `service-rabbitmq` | the RabbitMQ user/vhost blocks inside roles | **nothing** on its own (inside dynamic includes) | – | – | – | Not usable as a selector |
| `baremetal` | `kolla-host.yml` only | host preparation | all | **Docker daemon restart if `daemon.json` changed** | packages, users, `/etc/hosts` | E §1–3 |

`horizon` follows the `<svc>` row without registration and, by default, without bootstrap. The role has no
`register.yml`, so it is never registered in Keystone. Its DB creation and `bootstrap_horizon` DB sync run only when
`horizon_backend_database` is true (default `{{ enable_murano | bool }}`, `group_vars/all.yml:982`;
`roles/horizon/tasks/deploy.yml:10-11`). With defaults, `-t horizon` runs the haproxy horizon include, `common`,
config, check-containers and, if anything changed, the horizon restart handler.

### 3.1 Per-tag answers: files, VMs, APIs, networking/storage, safety, prerequisites

This table answers the remaining per-tag questions. What runs, which services are affected and which containers can
restart are in the master table above. Which handlers can fire is in §5: handlers fire only on drift, and tags never
filter them (§2.2). "R*n*" refers to [08](08-operational-risk-matrix.md). Everything assumes a change was detected;
on an unchanged cloud no tag restarts anything [LAB t1, s01, s19].

| Tag | Config files that can change | Running VMs | API availability | Networking / storage | Safe on its own? | Prerequisites |
|---|---|---|---|---|---|---|
| `haproxy` | `haproxy.cfg`, `services.d/*.cfg` of enabled services, `keepalived.conf`, TLS PEMs, sysctl; common files | no direct effect; instance metadata requests fail while HAProxy is down | **yes**: HAProxy restarts (never reloads) on all haproxy hosts at once; all APIs and the DB path through the VIP drop; keepalived can move the VIP (R8) | control plane only | yes if unchanged [LAB s19]; with a change, batch with `ANSIBLE_SERIAL=1 … reconfigure` | facts of every backend host; certificates if TLS is on |
| `<svc>` API service (`keystone`, `glance`, `cinder`, `heat`, `placement`, `horizon`) | service configs on its hosts, its `services.d` frontend, common files | none for keystone/heat/placement/horizon; glance/cinder transfers in progress are SIGKILLed after 10 s (R24) | **yes**: the service restarts on all its hosts at once; a Keystone restart blocks every API (R19); Placement down = no scheduling | cinder: volume operations, not the data path of attached volumes | yes, it is the intended unit; it still runs Keystone registration and DB sync (horizon: neither, by default); batch with `ANSIBLE_SERIAL`; the glance file backend has one host (R20) | MariaDB, RabbitMQ, memcached, Keystone (registration), HAProxy VIP |
| `nova` | API and cell `nova.conf`, `config.json`, policy, libvirt (`libvirtd.conf`, `qemu.conf`, SASL), nova-ssh files, Ceph keyrings when enabled, nova frontends, common files | **yes**: `nova_libvirt` restarts with any nova-cell drift on a compute (loop-notify, R1); live migrations in progress fail; VM survival is [NEEDS-LAB] (05 §5, 07 §A.4) | nova API, scheduler and conductors restart at once; instance actions fail briefly | attach/detach and port binding in flight can fail; no OVS change | only with batching and a window; prefer `genconfig` + `deploy-containers --limit` (07 §H) | MariaDB, RabbitMQ, memcached, Keystone, Placement, Glance, Neutron registered |
| `nova-api` | API-side `nova.conf`, `config.json`, policy, nova frontends, common files on controllers | none | nova API, scheduler, super-conductor | none | yes; does not touch computes | as `nova` |
| `nova-cell` | cell `nova.conf`, libvirt, nova-ssh and Ceph files on computes and conductors, console frontends, common files | **yes**, as `nova` | conductors and console proxies | as `nova` | as `nova` | the API DB and cell0 mapping (`nova-api`/`nova`), RabbitMQ |
| `neutron` | `neutron.conf`, `ml2_conf.ini`, `openvswitch_agent.ini`, `l3_agent.ini`, `dhcp_agent.ini`, `metadata_agent.ini` (+ enabled features), neutron frontend, common files | **yes**: OVS agent resync on every compute [NEEDS-LAB loss], L3/DHCP/metadata agent restarts on network nodes; L3 HA cleanup deletes router namespaces (R6) | neutron-server restarts on all controllers at once | **networking: yes** (07 §B.3); storage: no | risky without batching (R5, R6) | Open vSwitch or OVN running, MariaDB, RabbitMQ, Keystone |
| `openvswitch` | `config.json` of `openvswitch_db`/`openvswitch_vswitchd`; `system-id`, and bridges on network nodes, via `ovs-vsctl` | **yes** if `openvswitch_vswitchd` restarts or is recreated: all VM traffic on the host stops until flows are reinstalled (R7) | none | **networking: yes** | yes if unchanged (`Set system-id` reports *changed* without restarting); image changes per host batch | `openvswitch` kernel module |
| `ovn` | `config.json` of the OVN containers; chassis `external_ids` (`ovn-cms-options` overwritten) | [HYPOTHESIS] an ovn-controller restart re-programs flows on the host | NB/SB DB restarts interrupt neutron-server's OVN driver | **networking: yes** | check manual `ovn-cms-options` first (A §5.8) | Open vSwitch |
| `mariadb` | `galera.cnf` (lists all nodes), `config.json`, clustercheck files, `wsrep-notify.sh` | none directly | rolling restart in 4 waves; the active HAProxy backend restarts first (R9) | DB only | only on a healthy, fully synced cluster | every node `Synced` |
| `rabbitmq` | `rabbitmq.conf`, `rabbitmq-env.conf`, `erl_inetrc`, `advanced.config`, `definitions.json`, `config.json` | none directly; nova-compute and agents lose RPC while their broker restarts | RPC-backed API calls can time out; restarts are one by one | agents reconnect; no data-plane effect | yes on a healthy cluster; membership changes are R3 | no partitions, all nodes running |
| `memcached` / `memcache` | `config.json` | none | token cache flushed (Keystone load spike), Horizon sessions on memcached lost; all memcached hosts at once | none | yes, off-peak | none |
| `chrony` | `chrony.conf` and common files on **every** host | none | none (common containers only) | none | yes; also the cheapest way to push common config fleet-wide (§4) | VIP up for the chrony clients |
| `common` | none (no-op) [LAB s08] | none | none | none | safe but does nothing | – |
| `iscsi` | `config.json` of `iscsid`/`tgtd`; `configfs` persistence | [HYPOTHESIS] existing sessions are kernel-held; attach/detach during the window fails | none | **storage path on computes** (D §5.2) | with care, per host batch | – |
| `baremetal` (`bootstrap-servers`) | `daemon.json`, `/etc/hosts`, packages, users | **yes** if `daemon.json` changes: the Docker restart stops every container, `nova_libvirt` and OVS included (R14) | yes on controllers | yes | no on a live host unless `daemon.json` is unchanged; use `--limit` | – |

Validation: `--list-tags` lists every tag defined (annex/lab/list-tags-site.txt). `--list-tasks` cannot show the
tasks inside roles, because they come from dynamic includes (§2.6). Use `genconfig` plus
`docker exec -u root <c> /usr/local/bin/kolla_set_configs --check` to predict restarts (09 §1).

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
   `--skip-tags haproxy` is valid. Most service tags (`keystone`, `glance`, `neutron`, `nova`, …) select both the
   service's haproxy include and the service play(s), so for a single-tag service such as keystone this is the
   tag-based way to drop the haproxy part. Some tags select no haproxy include at all:
   - `memcache` (only the memcached play);
   - nova's narrower play tags: `-t nova-bootstrap,nova-api-deploy,nova-cell-deploy,nova-refresh-scheduler-cell-cache`
     does what a `-t nova` deploy/reconfigure does, minus the haproxy includes (`site.yml:293-306`);
   - `chrony`, `openvswitch`, `ovn`, `iscsi` (one play each).
5. **Tags do not change `kolla_action` logic.** For a given tag, `deploy` and `reconfigure` execute the same tasks
   (e.g. `-t nova deploy` and `-t nova reconfigure`; 01 §4.2). Apart from swift and bifrost, whose `reconfigure.yml`
   has its own logic, the only role-level exception is Neutron's `bootstrap_neutron` DB-sync container, which runs
   on deploy only while `neutron_enable_rolling_upgrade` keeps its default `yes`; Neutron DB and DB-user creation
   run on both. The other difference is the `kolla_serial` pass-through (01 §2).

---

## 5. Role → handler map (core services)

Handlers run in **definition order** after `meta: flush_handlers` (end of `deploy.yml`) or at the end of the play.
All use `kolla_docker` `recreate_or_restart_container` unless noted. The complete list for all roles is in
[annex/generated-inventory.md §3](../annex/generated-inventory.md).

| Role | Handlers (definition order) | Special logic | Evidence |
|---|---|---|---|
| common | Restart fluentd → Restart kolla-toolbox (→ Initializing toolbox: `docker exec … ansible --version`) → Restart cron | – | `roles/common/handlers/main.yml` |
| haproxy | Restart haproxy → Restart keepalived → Waiting for haproxy → Waiting for VIP | `wait_for` on the monitor port | A §1.5 |
| mariadb | Bootstrap MariaDB cluster (listen) … → Restart MariaDB on existing cluster members (`include_tasks restart_services.yml`, loop 0..3, `index % 4 == item`) → Start MariaDB on new nodes … | 4 restart waves, waiting for port + WSREP `Synced` | `roles/mariadb/handlers/main.yml:66-78`, B §1.5 |
| rabbitmq | Restart rabbitmq: first node, then the others one by one | `rabbitmqctl wait` | B §2.5 |
| keystone | (Init keystone database upgrade, upgrade only) → Restart keystone-ssh → Restart keystone-fernet → Restart keystone → (Finish keystone database upgrade, upgrade only) | all hosts at once | `roles/keystone/handlers/main.yml:5-95`, B §3.5 |
| nova | Restart nova-super-conductor → nova-scheduler → nova-api | skipped on upgrade when `nova_safety_upgrade` | `roles/nova/handlers/main.yml` |
| nova-cell | Restart nova-conductor → novncproxy → spicehtml5proxy → serialproxy → nova-ssh → **nova-libvirt** (retries 5; notifies Create libvirt SASL user) → Create libvirt SASL user → nova-compute → nova-compute-ironic → fake → Wait for nova-compute services (upgrade only, 30 s pause) | libvirt is restarted **before** nova-compute | `roles/nova-cell/handlers/main.yml:1-196` |
| neutron | one handler per agent/server | none | `roles/neutron/handlers/main.yml` |
| openvswitch | Restart openvswitch-db-server (→ Waiting for openvswitch_db) → Restart openvswitch-vswitchd | – | `roles/openvswitch/handlers/main.yml:1-42` |
