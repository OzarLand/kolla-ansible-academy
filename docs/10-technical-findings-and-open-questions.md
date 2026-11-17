# 10 — Technical Findings and Open Questions

This document consolidates three things:

1. what was established and how (evidence level);
2. implementation limitations and bugs found in `ussuri-eol`;
3. what the sources do not establish.

> **Key answers**
>
> - **Fifteen headline findings ([F1–F15](#1-headline-findings))**, each with its evidence and why it matters, among
>   them loop-notify amplification ([F1](#1-headline-findings)), the `-t common` no-op ([F2](#1-headline-findings)), the
>   ignored stop timeout ([F3](#1-headline-findings)), same-tag image rebuilds ([F4](#1-headline-findings)) and
>   `reconfigure` = `deploy` ([F5](#1-headline-findings)) ([§1](#1-headline-findings)).
> - **Implementation limitations and bugs of `ussuri-eol`, by area:** CLI, `site.yml`, `kolla_docker`, the kolla images
>   and individual roles ([§2](#2-implementation-limitations-and-bugs-ussuri-eol)).
> - **Eleven corrections to the fact sheets.** The one with the widest effect: `docker stop` does not use
>   `docker_graceful_timeout` = 60 s; the effective timeout is 10 s ([§3](#3-corrections-to-the-annex-fact-sheets)).
> - **Open questions [Q1–Q14](#4-open-questions):** all are [NOT AVAILABLE], except [Q10](#4-open-questions) and
>   [Q14](#4-open-questions), which are answered from the source [CODE] ([§4](#4-open-questions)).
>   [Q1](#4-open-questions) asks whether running VMs survive a `nova_libvirt` restart or recreate.
> - **Limits of the study:** source code only and no timings; every statement about data-plane or VM impact is
>   [NOT AVAILABLE] ([§5](#5-limits-of-this-study)).

**Contents**

- [1. Headline findings](#1-headline-findings)
- [2. Implementation limitations and bugs (`ussuri-eol`)](#2-implementation-limitations-and-bugs-ussuri-eol)
- [3. Corrections to the annex fact sheets](#3-corrections-to-the-annex-fact-sheets)
- [4. Open questions](#4-open-questions)
- [5. Limits of this study](#5-limits-of-this-study)

**Related:** [08](08-operational-risk-matrix.md) (the risks [R1–R25](08-operational-risk-matrix.md#1-matrix) that the
open questions refer to) · [annex/kolla-images.md](../annex/kolla-images.md) (the answer to [Q14](#4-open-questions)) ·
[annex/factsheets/README.md](../annex/factsheets/README.md) (errata with their evidence) ·
[annex/index.md](../annex/index.md#everything-marked-not-available) (everything marked [NOT AVAILABLE], by topic)

Evidence levels: **[CODE]** and **[NOT AVAILABLE]**, defined once, in the [README](../README.md#evidence-labels). The
study rests only on reading source code; no run against a host is used as evidence.

---

## 1. Headline findings

| # | Finding | Evidence | Why it matters |
|---|---|---|---|
| F1 | **Loop-notify amplification.** When a config/check task loops over a role's services and *one* item changes, Ansible 2.9 notifies the handlers of *all* executed items. In Kolla this means a change for one container restarts every container of that role on that host. A nova-compute-only change restarts `nova_libvirt` and `nova_ssh`; a scheduler-only change restarts `nova_api`; a change on a network node restarts all neutron agents there | [CODE] ansible 2.9.27 `lib/ansible/plugins/strategy/__init__.py:616-623`, `lib/ansible/executor/task_executor.py:790`; `roles/nova-cell/tasks/check-containers.yml:2-20`, `roles/nova/tasks/config.yml:51-69`, `roles/neutron/tasks/check-containers.yml:2-18`; walk-through in [03 §2.4](03-ansible-roles-and-tags-mapping.md#24-loop-notify-one-changed-item-notifies-the-handlers-of-all-items-code) | Restart blast radius is per *role-on-host*, not per container. libvirt restarts far more often than operators expect |
| F2 | **`-t common` is a no-op.** Tags on the dynamic `include_tasks` do not propagate to the included tasks | [CODE] `roles/common/tasks/main.yml:1-10`; ansible 2.9.27 `lib/ansible/playbook/task_include.py:135-154`, `lib/ansible/playbook/block.py:311-314,329-360,378-380`, `lib/ansible/plugins/strategy/linear.py:371` ([03 §2.1](03-ansible-roles-and-tags-mapping.md#21-dynamic-include_tasks-and-tag-inheritance-code)) | `common` changes (fluentd/cron/toolbox) are applied by whatever run first reaches the host, often unexpectedly |
| F3 | **`docker_graceful_timeout` and `docker_client_timeout` are ignored.** The `kolla_docker` argument defaults (10 s, 120 s) override `common_options`, so every stop sends SIGKILL to a container still running **10 s** after SIGTERM | [CODE] `kolla_docker.py:991,1011,1037-1047`; `group_vars/all.yml:154,166-167`; ansible 2.9.27 `lib/ansible/module_utils/basic.py:755,1929-1939` (argument defaults are filled in before the merge, so they are never `None`) | On every restart, a service still running 10 s after SIGTERM is SIGKILLed with its in-flight work (heat-engine, cinder copies, glance uploads); for `nova_libvirt` this matters only if libvirtd has not exited by then ([05 §5](05-nova-deep-dive.md#5-nova-libvirt-why-its-restart-is-special)). [NOT AVAILABLE] Whether services started by a shell wrapper that does not `exec` them (e.g. `neutron-l3-agent`, `haproxy`) receive SIGTERM at all ([annex/kolla-images.md §2.6](../annex/kolla-images.md#26-signals-and-pid-1)). The release note claiming 60 s (`releasenotes/notes/docker-stop-timeout-c8089f6bf92d6c28.yaml`) has no effect |
| F4 | **Same-tag image rebuilds are not picked up by `deploy`/`reconfigure`/`upgrade`.** Only absent images are pulled; an explicit `pull` is required | [CODE] `kolla_docker.py:805-808`, `:403-413` | Mutable tags create silent drift between hosts. A later unrelated `pull` turns into a mass recreate |
| F5 | **`reconfigure` = `deploy`** for 70 of the 72 roles that have a `tasks/reconfigure.yml` (67 via `import_tasks: deploy.yml`, plus congress, mongodb and nova-hyperv via `include_tasks: deploy.yml`; only swift and bifrost have their own logic). A reconfigure re-runs Keystone registration, DB creation/grants and the DB-sync bootstrap containers of most services. Neutron is the exception: with the default `neutron_enable_rolling_upgrade: "yes"`, `bootstrap_neutron` runs on `deploy` but is skipped on `reconfigure`, so a reconfigure re-runs Neutron's DB create/grant tasks but not its DB sync | [CODE] `roles/*/tasks/reconfigure.yml`; `roles/neutron/tasks/bootstrap_service.yml:21-22,24-46`, `roles/neutron/defaults/main.yml:411`. One-shot containers counted from the code: `-t nova` starts 5 on `control01` when cell0 is mapped and the cell is unchanged (API DB sync, `map_cell0`, cell DB sync, `list_cells` ×2: `roles/nova/tasks/bootstrap.yml:52-54`, `map_cell0.yml:2-26`, `roles/nova-cell/tasks/bootstrap.yml:38-40`, `create_cells.yml:2-3`, `discover_computes.yml:5`); on `-t neutron reconfigure` with default flags the neutron role starts none (`roles/neutron/tasks/bootstrap_service.yml:21-22,41-42`, `group_vars/all.yml:677`). [NOT AVAILABLE] Totals for a run without a tag, which depend on the enabled services | A "reconfigure" can apply schema migrations if the image tag moved, for most services; for Neutron only with non-default flags: `enable_neutron_sfc` (the `bootstrap_neutron_sfc` container runs `neutron-db-manage --subproject networking-sfc … upgrade head` on every reconfigure) or `neutron_enable_rolling_upgrade: "no"` (full `bootstrap_neutron`). There is never a "config only" path except `genconfig` + `deploy-containers` |
| F6 | **Global inputs are rendered into per-host files.** `enable_*` flags, RabbitMQ/memcached membership, service passwords and the external FQDN end up in compute-side files | [CODE] `group_vars/all.yml:206,216`; `nova-cell/templates/nova.conf.j2`; `neutron/templates/neutron.conf.j2:119` (memcached list, shared by the OVS agent on computes); `common/tasks/config.yml:109-240` | Small central changes cause fleet-wide restarts |
| F7 | **`--list-tasks` cannot show what a tag runs**, and `--list-hosts` shows 0 hosts for `&enable_*` plays | [CODE] ansible 2.9.27 `lib/ansible/cli/playbook.py:145-147,180-185` (the listing walks the statically compiled play and resolves host patterns before any task runs), `lib/ansible/inventory/manager.py:425`; `site.yml:21-25` (the `enable_*` groups are created by `group_by` at run time); [annex/listings/list-tasks-nova.txt](../annex/listings/list-tasks-nova.txt) | Operators need `genconfig` or staging to predict a run |
| F8 | **`--limit` does not confine actions.** `delegate_to: groups[x][0]` runs work on hosts outside the limit. With `deploy --limit` set to a compute host, `control01` (the first `neutron-server` and `nova-conductor` host of the `multinode` inventory) runs the Neutron DB create/grant and the `bootstrap_neutron` container, plus cell discovery (`nova_list_cells`, `openstack compute service list`, `nova-manage cell_v2 discover_hosts`). The nova-cell RabbitMQ user/vhost creation is also delegated (to the first RabbitMQ host), but it runs only when the first nova-conductor is inside the limit, so a limit to compute hosts does not run it | [CODE] `site.yml:761-775` and `nova.yml:117-126` (both plays include `compute`); `roles/neutron/tasks/bootstrap.yml:12-13,31-32`, `bootstrap_service.yml:19-22`; `roles/nova-cell/tasks/wait_discover_computes.yml:41-42,86-89`, `discover_computes.yml:4-21`, `get_cell_settings.yml:2-16`; `roles/nova-cell/tasks/rabbitmq.yml:10-12`; `inventory/multinode:3-5,138-139,290-291,312-313` | "Only the new compute" still executes DB-sync containers on a controller |
| F9 | **With `--limit`, all hosts' facts are gathered sequentially** by the limited hosts (delegated loop) | [CODE] `gather-facts.yml:29-50`; loop items run one after another (ansible 2.9.27 `lib/ansible/executor/task_executor.py:317,367`) | O(total hosts) serial latency on every limited run without fact caching |
| F10 | **`kolla_serial` makes `run_once` steps repeat per batch** (API DB sync ×3 with serial 1 and the three controllers of the `multinode` inventory) and orders a play's restarts by host-pattern order (computes before conductors in the nova-cell play) | [CODE] ansible 2.9.27 `lib/ansible/executor/playbook_executor.py:161-169,257`, `lib/ansible/plugins/strategy/linear.py:288,315-316`, `lib/ansible/inventory/manager.py:411,428`; `roles/nova/tasks/bootstrap_service.yml:4-23`; `nova.yml:29-39,119-126`; `inventory/multinode:3-7,138-139,287-288` ([03 §2.5](03-ansible-roles-and-tags-mapping.md#25-run_once-with-serial-code)) | Batching reduces blast radius but multiplies bootstrap work, and exposes ordering within a play |
| F11 | **The `openvswitch_agent.ini` merge** includes the operator's `ml2_conf.ini` overrides | [CODE] `roles/neutron/tasks/config.yml:172-190` | Server-side ML2 changes restart every OVS agent |
| F12 | **The L3 agent wrapper runs `neutron-netns-cleanup --force --agent-type l3` at start** when `enable_neutron_agent_ha: yes`; its comment says this removes all L3 namespaces (what the command does is neutron code: NOT AVAILABLE) | [CODE] `neutron-l3-agent-wrapper.sh.j2:5-12` | [NOT AVAILABLE] Whether an L3 agent restart interrupts router traffic on that node ([Q4](#4-open-questions)) |
| F13 | **The Nova deploy order** puts nova-compute before OVS and the Neutron agents on new computes | [CODE] `site.yml:710-780` | [NOT AVAILABLE] Whether instances can be scheduled on such a compute before the later plays finish ([04 §2.4](04-deployment-execution-flow.md#24-compute-node-deployment-what-one-compute-host-experiences)); relevant when adding computes one by one |
| F14 | **`kolla_set_configs --check` has blind spots.** It compares only the `config_files` entries of `config.json` (content, mode, owner). A change confined to `config.json` itself (`command`, `permissions`; all of memcached's settings) is never detected. A newly added optional file makes it exit 2, which fails `check-containers`, unless an entry listed before it already differs (then 1). `preserve_properties` entries (prometheus extras) and directory sources with subdirectories report drift on every run. A restart never removes the files of a dropped entry | [CODE] kolla `docker/base/set_configs.py:60-65,131-151,160-235,310-330,388-393,407-432`; `kolla_docker.py:566-578` ([annex/kolla-images.md §3](../annex/kolla-images.md#3-kolla_set_configs---check-what-it-compares-and-its-exit-codes)) | "`genconfig` + `--check`" ([09 §1](09-practical-command-reference.md#1-inspection-no-changes)) under-reports some changes and over-reports others. A `config.json`-only change is applied by a normal deploy/reconfigure, because the changed template task notifies the restart handler. Once `genconfig` has written it, neither `deploy-containers` nor a later run (its template task is then unchanged) applies it until the container restarts for another reason |
| F15 | **What the bootstrap containers run differs per image.** Nova's bootstrap containers run with `KOLLA_UPGRADE` (schema sync, no online data migrations outside `upgrade`). Placement's `KOLLA_BOOTSTRAP` container also runs `online_data_migrations`, on every deploy/reconfigure. Heat's does not re-apply a changed `heat_domain_admin_password` to Keystone. neutron-server's migrates `neutron-dynamic-routing`, which the rolling `upgrade` never migrates | [CODE] kolla `docker/nova/nova-api/extend_start.sh:9-25`, `docker/nova/nova-conductor/extend_start.sh:3-17`, `docker/placement/placement-api/extend_start.sh:5-9`, `docker/heat/heat-api/extend_start.sh:5-17`, `docker/neutron/neutron-server/extend_start.sh:5-12,34-38`; `roles/nova/tasks/bootstrap_service.yml:13`, `roles/nova-cell/tasks/bootstrap_service.yml:11`, `roles/placement/tasks/bootstrap_service.yml:11`, `roles/heat/tasks/bootstrap_service.yml:11,21`, `roles/neutron/defaults/main.yml:412` | What a "reconfigure" or a tag-changing "deploy" does to databases depends on the image, not only on kolla-ansible ([annex/kolla-images.md §4](../annex/kolla-images.md#4-one-shot-containers-what-the-environment-variables-run)) |

---

## 2. Implementation limitations and bugs (`ussuri-eol`)

| Area | Issue | Evidence | Status |
|---|---|---|---|
| CLI | `-e kolla_serial=N` is overridden by `ANSIBLE_SERIAL` (default 0) for `reconfigure`/`upgrade`; it is not passed for `deploy` | `tools/kolla-ansible:236,430,439` | [CODE] |
| CLI | `--ask-vault-pass` overwrites `VERBOSITY` with a copy of `EXTRA_OPTS` | `tools/kolla-ansible:320-323` | [CODE] |
| CLI | `--include-dev:` declared with an argument but used as a flag; the command line is executed unquoted | `tools/kolla-ansible:116,216,284-287` | [CODE] [fact sheet E](../annex/factsheets/E-host-bootstrap-ops-playbooks.md) |
| site.yml | cyborg play uses `serial` instead of `kolla_serial` | `site.yml:1028` | [CODE] |
| site.yml | placement haproxy include lacks `when: enable_placement` | `site.yml:289-292` | [CODE] |
| kolla_docker | `graceful_timeout`/`client_timeout` from `docker_common_options` ignored ([F3](#1-headline-findings)); `restart_policy` never compared (FIXME `:21`) | `kolla_docker.py:21,991,1011,1037-1047` | [CODE] |
| kolla images | `kolla_set_configs --check` compares only `config_files` entries ([F14](#1-headline-findings)): changes confined to `config.json` (`command`, `permissions`; all of memcached's settings) are never detected, so neither `genconfig` + `deploy-containers` nor a later run applies them until the container restarts for another reason; a newly added optional file makes it exit 2 and fails `check-containers` unless an entry listed before it differs (then 1); `preserve_properties` entries (prometheus extras) and directory sources with subdirectories report drift on every run; a restart never removes files whose entry was dropped | kolla `docker/base/set_configs.py:60-65,131-151,160-235,310-330,388-393,407-432`; `kolla_docker.py:566-578` | [CODE] |
| common | `-t common` no-op ([F2](#1-headline-findings)) | `roles/common/tasks/main.yml:1-10`; [03 §2.1](03-ansible-roles-and-tags-mapping.md#21-dynamic-include_tasks-and-tag-inheritance-code) | [CODE] |
| haproxy | Restart instead of reload; stale `services.d` files never removed; keepalived priority from inventory order; upgrade "Stopping all slave keepalived" without an `enable_keepalived` guard and with raw interface names | [fact sheet A §1.8](../annex/factsheets/A-infra-lb-ovn.md#18-operationally-notable-behaviour) | [CODE]; effect of the upgrade bugs [NOT AVAILABLE] |
| openvswitch | `Set system-id` always reports changed | `roles/openvswitch/tasks/post-config.yml:3-5` (a `command` task with no `changed_when`; `command` always returns changed, ansible 2.9.27 `lib/ansible/modules/commands/command.py:334`) | [CODE] |
| neutron | `upgrade` with the default `neutron_enable_rolling_upgrade: "yes"` expands/contracts only `neutron`, `neutron-fwaas` and `neutron-vpnaas`: `neutron-dynamic-routing`, which the `KOLLA_BOOTSTRAP` container migrates on `deploy`, is never migrated by `upgrade`, and the image's rolling `neutron-db-manage` calls pass no `--config-file`. `has_offline_migrations` runs on the first neutron-server host with `ignore_errors`; any non-zero rc (a failed `docker exec` included) stops `neutron_server` on every neutron-server host in the play until the handler flush after the contract container | `roles/neutron/defaults/main.yml:411-412`; `roles/neutron/tasks/upgrade.yml:2-3`; `roles/neutron/tasks/rolling_upgrade.yml:13-33,43-67,69-93`; `roles/neutron/tasks/bootstrap_service.yml:21-22`; kolla `docker/neutron/neutron-server/extend_start.sh:5-12,34-38` | [CODE]; impact on the Neutron API [NOT AVAILABLE] |
| ovs-dpdk | `pull` looks up a non-existent `ovs_services` variable; the NIC mapping file is written once; the 300 s wait handler has no port | [fact sheet A §6](../annex/factsheets/A-infra-lb-ovn.md#6-ovs-dpdk-role) | [CODE] |
| rabbitmq | outward RabbitMQ `pull` looks up `outward_rabbitmq_services` | [fact sheet B §2.8](../annex/factsheets/B-mariadb-rabbitmq-keystone.md#28-operationally-notable-behaviour-risks-and-oddities) (item 6); `site.yml:563` (`project_name: outward_rabbitmq`), `roles/service-images-pull/tasks/main.yml:14` | [CODE]; effect on `pull` [NOT AVAILABLE] |
| rabbitmq | the image writes `.erlang.cookie` only in the bootstrap container (new volume); a cookie change recreates the brokers (env compare) but they keep the old cookie, while `kolla_toolbox` gets the new one | kolla `docker/rabbitmq/extend_start.sh:7-18`; `roles/rabbitmq/tasks/bootstrap.yml:26`; `roles/common/tasks/config.yml:242-250` | [CODE]; consequences [NOT AVAILABLE] |
| mariadb | the restart waves have no `any_errors_fatal`; recovery stops healthy nodes; clustercheck started even when disabled | [fact sheet B §1.5](../annex/factsheets/B-mariadb-rabbitmq-keystone.md#15-handlers-ansiblerolesmariadbhandlersmainyml-in-definition-order), [§1.8](../annex/factsheets/B-mariadb-rabbitmq-keystone.md#18-operationally-notable-behaviour-risks-and-oddities) (items 5–6) | [CODE]; whether later waves continue after a failed WSREP wait [NOT AVAILABLE] |
| keystone | fernet cron generator hour calculation; precheck vs generator expiry limits; push script stops at the first unreachable peer | [fact sheet B §3.9](../annex/factsheets/B-mariadb-rabbitmq-keystone.md#39-operationally-notable-behaviour-risks-and-oddities) (items 3–5); `roles/keystone/files/fernet_rotate_cron_generator.py:61-64,70-72`, `roles/keystone/templates/fernet-push.sh.j2:3-10` | [CODE] |
| glance | global `log_bin_trust_function_creators` toggle on every deploy/reconfigure; file backend = single host; backend switches silently when Swift/Ceph is enabled | [fact sheet C §1](../annex/factsheets/C-glance-placement-cinder-horizon-heat.md#1-glance) | [CODE] |
| cinder | no `host`/`backend_host`/`cluster`; etcd coordination uses only the first etcd host; Ceph backup driver default without a Ceph config | [fact sheet C §3](../annex/factsheets/C-glance-placement-cinder-horizon-heat.md#3-cinder) | [CODE] |
| heat | `bootstrap_heat` creates `heat_user_domain`/`heat_domain_admin` only when the domain is absent: a changed `heat_domain_admin_password` reaches `heat.conf` but never Keystone | kolla `docker/heat/heat-api/extend_start.sh:8-14`; `roles/heat/templates/heat.conf.j2:12-13` | [CODE]; impact [NOT AVAILABLE] |
| swift | no handlers are notified (deploy does not apply config/ring changes); `stop.yml` wrong container name; precheck probes rsync port 873 vs 10873 | [fact sheet D](../annex/factsheets/D-barbican-octavia-swift-manila-compute-roles.md) | [CODE]; runtime effects [NOT AVAILABLE] |
| octavia | upgrade removes the octavia admin role on `admin` without re-registering; no amphora resources are created | [fact sheet D](../annex/factsheets/D-barbican-octavia-swift-manila-compute-roles.md) | [CODE] |
| masakari | instancemonitor uses `qemu+tcp` without SASL while nova-libvirt enables SASL | [fact sheet D](../annex/factsheets/D-barbican-octavia-swift-manila-compute-roles.md); `roles/masakari/templates/masakari-monitors.conf.j2:17`, `roles/nova-cell/defaults/main.yml:431`, `roles/nova-cell/templates/libvirtd.conf.j2:12` | [CODE]; effect on the instancemonitor [NOT AVAILABLE] |
| baremetal | Docker restarted on `daemon.json` change on all hosts at once; `docker_custom_option` changes are never applied; Docker masked during re-runs on Debian/Ubuntu; `/etc/hosts` lists every baremetal host (O(N²) templating, stale with `--limit`) | [fact sheet E §1–5](../annex/factsheets/E-host-bootstrap-ops-playbooks.md#1-ansiblekolla-hostyml-the-bootstrap-servers-command) | [CODE]; runtime effects [NOT AVAILABLE] |
| certificates | test CA only; certs never renewed; new backend hosts not added | [fact sheet A §8](../annex/factsheets/A-infra-lb-ovn.md#8-certificatesyml-playbook--certificates-role), [E](../annex/factsheets/E-host-bootstrap-ops-playbooks.md) | [CODE] |

---

## 3. Corrections to the annex fact sheets

The fact sheets were produced by parallel source-reading agents and spot-checked (MariaDB restart waves, glance
`log_bin_trust_function_creators`, the Docker restart gate, keepalived priority, compute-side memcached lists: all
confirmed). Eleven corrections apply. All are listed with their evidence under "Verification and errata" in
[annex/factsheets/README.md](../annex/factsheets/README.md). The first bullet (in sheets A, B and E) and the last four
bullets (eight corrections) were also made in the sheets themselves:

- **Fact sheets [A](../annex/factsheets/A-infra-lb-ovn.md), [B](../annex/factsheets/B-mariadb-rabbitmq-keystone.md) and
  [E](../annex/factsheets/E-host-bootstrap-ops-playbooks.md)** (and any sentence elsewhere) stating that `docker stop`
  uses `docker_graceful_timeout` = 60 s are wrong. The effective timeout is **10 s** ([F3](#1-headline-findings)). Sheet
  E also listed `docker_client_timeout` as a working knob; it is ignored the same way. [Fact sheet
  C](../annex/factsheets/C-glance-placement-cinder-horizon-heat.md) states this correctly. This is the correction with
  the widest effect.
- **[Fact sheet A](../annex/factsheets/A-infra-lb-ovn.md)**, "no reload path anywhere": true for handlers, but
  `nova_scheduler` receives a `SIGHUP` on every `deploy`/`reconfigure` that runs the `nova`, `nova-api` or
  `nova-refresh-scheduler-cell-cache` tag (or no tag) and whose `--limit` includes the `nova-scheduler` hosts
  (`ansible/nova.yml:139-156`).
- **[Fact sheet B §3.10][sheet-b-310]**, memcached counts: 35 roles use `memcache_secret_key`, and 38 embed the
  memcached host list.
- **[Fact sheet A](../annex/factsheets/A-infra-lb-ovn.md)**, `tags: always` on `import_role: haproxy-config` "in every
  `loadbalancer.yml`": 48 of 49 files do it directly; nova-cell reaches it through a chain of includes.
- **[Fact sheet B](../annex/factsheets/B-mariadb-rabbitmq-keystone.md)**, "Graceful stop" row: it also stated 60 s; the
  sheet now states 10 s ([F3](#1-headline-findings)).
- **[Fact sheet B](../annex/factsheets/B-mariadb-rabbitmq-keystone.md)**, Erlang cookie: the kolla image writes
  `.erlang.cookie` only in the `KOLLA_BOOTSTRAP` container, which runs only on a new volume, not at every start. The
  sheet's former claim of a partition during the rolling recreate rested on that wrong premise; the corrected behaviour
  is in the second rabbitmq row of [§2](#2-implementation-limitations-and-bugs-ussuri-eol).
- **[Fact sheet C](../annex/factsheets/C-glance-placement-cinder-horizon-heat.md)**, four image-side statements, checked
  against the kolla `ussuri-eol` sources ([F15](#1-headline-findings), [Q14](#4-open-questions) and
  [annex/kolla-images.md §4](../annex/kolla-images.md#4-one-shot-containers-what-the-environment-variables-run),
  [§5.2](../annex/kolla-images.md#52-horizon-static-assets)):
  - Placement online data migrations also run on every deploy/reconfigure, inside `bootstrap_placement`, not only on
    upgrade.
  - The heat domain admin is created only when `heat_user_domain` is absent, so a changed password is not
    re-applied.
  - Horizon's collectstatic/compress is conditional (settings hash changed or missing, a plugin toggled, or
    `FORCE_GENERATE=yes`), not run on every start.
  - The glance bootstrap also runs `glance-manage db_load_metadefs`.
- **[Fact sheet E](../annex/factsheets/E-host-bootstrap-ops-playbooks.md)**, "For every other command, `-e
  kolla_serial=...` works": `upgrade` overrides it like `reconfigure` does (`tools/kolla-ansible:430`); use
  `ANSIBLE_SERIAL`.

[sheet-b-310]: ../annex/factsheets/B-mariadb-rabbitmq-keystone.md#310-runtime-dependency-of-other-services-on-keystone-grep-across-ansiblerolestemplates

---

## 4. Open questions

These questions cannot be settled by reading the sources, except Q10 and Q14, which are answered from the source in
their rows: Q10 by comparing the Ansible 2.8.20 and 2.9.27 code, Q14 by reading the kolla image sources. The others
are [NOT AVAILABLE].

| # | Question | Why it matters | Status |
|---|---|---|---|
| Q1 | Do running VMs survive a `nova_libvirt` restart or recreate? | [F1](#1-headline-findings) makes libvirt restarts frequent | [NOT AVAILABLE] |
| Q2 | Data-plane loss during a `neutron_openvswitch_agent` restart | [R5](08-operational-risk-matrix.md#1-matrix) | [NOT AVAILABLE] |
| Q3 | Data-plane loss during an `openvswitch_vswitchd` restart or recreate | [R7](08-operational-risk-matrix.md#1-matrix) | [NOT AVAILABLE] |
| Q4 | L3 agent restart with and without `enable_neutron_agent_ha` | [R6](08-operational-risk-matrix.md#1-matrix) | [NOT AVAILABLE] |
| Q5 | HAProxy restart: VIP behaviour | [R8](08-operational-risk-matrix.md#1-matrix) | [NOT AVAILABLE] |
| Q6 | MariaDB rolling restart under load with a failure in wave 1: do later waves proceed? | [R9](08-operational-risk-matrix.md#1-matrix) | [NOT AVAILABLE] |
| Q7 | Real timing at scale (SSH, pipelining, fact caching, forks) | [doc 06](06-compute-scaling-and-performance.md) model | [NOT AVAILABLE] |
| Q8 | Image sizes and registry throughput | [doc 06](06-compute-scaling-and-performance.md) model | [NOT AVAILABLE] |
| Q9 | Check mode (`--check --diff`) usability | [doc 09](09-practical-command-reference.md), [03 §2.6](03-ansible-roles-and-tags-mapping.md#26---list-tasks-is-not-usable-for-kolla-code): `kolla_docker` is skipped under `--check` [CODE] | [NOT AVAILABLE] |
| Q10 | Ansible 2.8 vs 2.9 behaviour for [F1](#1-headline-findings)/[F2](#1-headline-findings) | Ussuri allows 2.8 | **Answered from the source** [CODE]: the code that produces [F1](#1-headline-findings) and [F2](#1-headline-findings) is the same in both versions. Loop notify: ansible 2.8.20 `lib/ansible/plugins/strategy/__init__.py:540-557` matches 2.9.27 `:609-626`, and `_ansible_notify` is set the same way (2.8.20 `lib/ansible/executor/task_executor.py:784`, 2.9.27 `:790`). Tag inheritance: `Task._get_parent_attribute`, `Block._get_parent_attribute` and `TaskInclude.build_parent_block` (2.8.20 `lib/ansible/playbook/task.py:427-458`, `block.py:300-364`, `task_include.py:124-143`) match 2.9.27's `task.py:458-489`, `block.py:300-364` and `task_include.py:135-154` ([03 §2.1](03-ansible-roles-and-tags-mapping.md#21-dynamic-include_tasks-and-tag-inheritance-code), [§2.4](03-ansible-roles-and-tags-mapping.md#24-loop-notify-one-changed-item-notifies-the-handlers-of-all-items-code)) |
| Q11 | Fernet key distribution failure modes | [R19](08-operational-risk-matrix.md#1-matrix) | [NOT AVAILABLE] |
| Q12 | Glance backend switch on enabling Swift | [R21](08-operational-risk-matrix.md#1-matrix) | [NOT AVAILABLE] |
| Q13 | `bootstrap-servers` re-run effects on a live compute | [R14](08-operational-risk-matrix.md#1-matrix) | [NOT AVAILABLE] |
| Q14 | Behaviour of the kolla images' `extend_start.sh` (what `KOLLA_BOOTSTRAP`/`KOLLA_UPGRADE` run) | [F5](#1-headline-findings), [F15](#1-headline-findings) | **Answered from the source** [CODE], see [annex/kolla-images.md §4](../annex/kolla-images.md#4-one-shot-containers-what-the-environment-variables-run). Nova's bootstrap containers run with `KOLLA_UPGRADE`: `api_db sync` + `db sync` (nova-api), `db sync --local_cell` (nova-conductor), so Nova's online data migrations never run outside `upgrade`; the images' `KOLLA_BOOTSTRAP` branches are unreachable. Placement's `KOLLA_BOOTSTRAP` runs `db sync` + `online_data_migrations` on every deploy/reconfigure. Glance adds `db_load_metadefs`. Heat creates `heat_user_domain`/`heat_domain_admin` only if the domain is absent, so a changed `heat_domain_admin_password` is never pushed to Keystone. neutron-server's `KOLLA_BOOTSTRAP` migrates neutron, -dynamic-routing, -fwaas and -vpnaas; the rolling upgrade list omits -dynamic-routing. RabbitMQ writes the Erlang cookie only in its bootstrap container. Agent, OVS and OVN images have no one-shot branch |

---

## 5. Limits of this study

- **Source code only.** The study rests only on reading source code: kolla-ansible `ussuri-eol`, the kolla
  image repository `ussuri-eol`, and the Ansible 2.9.27 source (2.8.20 for comparison). The only Ansible output used
  is its `--list-tags`/`--list-tasks` parse of the playbooks ([annex/listings/](../annex/listings/README.md)), which
  runs nothing against a host. The semantics of `kolla_set_configs --check` are read from the kolla source
  ([annex/kolla-images.md
  §3](../annex/kolla-images.md#3-kolla_set_configs---check-what-it-compares-and-its-exit-codes)).
- **There are no timings.** No run is used, so no wall time is known; work can only be counted from the code
  ([06](06-compute-scaling-and-performance.md)).
- **No container or VM behaviour is used as evidence.** Every statement about data-plane or VM impact is
  [NOT AVAILABLE].
- **The depth of reading varies.** The core services are traced in the main documents; the other roles are covered
  by the fact sheets only.
- **The kolla image sources were read, not built or run.** From the kolla `ussuri-eol` repository: the base start
  path (`docker/base`: `Dockerfile.j2`, `start.sh`, `set_configs.py`, `copy_cacerts.sh`, `httpd_setup.sh`,
  `sudoers`, healthcheck scripts) and the start scripts of the images listed in
  [annex/kolla-images.md](../annex/kolla-images.md) (Nova, Neutron, Open vSwitch, OVN, Keystone, Glance, Placement,
  Cinder, Heat, Horizon, Barbican, Octavia, Manila, Swift, MariaDB, RabbitMQ, memcached, HAProxy, keepalived incl.
  `check_alive.sh`, fluentd, cron, kolla-toolbox, chrony, iscsid, tgtd). Of the other images only the `ironic-api`
  bootstrap branch and the `bifrost-deploy` `ENTRYPOINT`/`CMD` were read, and every Dockerfile was searched for
  `HEALTHCHECK` and for `ENTRYPOINT`/`CMD` overrides. What the scripts do against real services and data is
  [NOT AVAILABLE].
