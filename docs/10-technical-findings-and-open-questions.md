# 10 — Technical Findings and Open Questions

This document consolidates three things:

1. what was established and how (evidence level);
2. implementation limitations and bugs found in `ussuri-eol`;
3. what remains uncertain and which experiments would settle it.

Evidence levels:

- **[CODE]** read in the source.
- **[ANSIBLE]** Ansible 2.9.27 semantics, read in Ansible's source and/or reproduced with a minimal playbook.
- **[LAB]** observed by executing the real `site.yml` in the stub lab.
- **[HYPOTHESIS]** reasoned but not proven.
- **[NEEDS-LAB]** requires a real environment.

---

## 1. Headline findings

| # | Finding | Evidence | Why it matters |
|---|---|---|---|
| F1 | **Loop-notify amplification.** When a config/check task loops over a role's services and *one* item changes, Ansible 2.9 notifies the handlers of *all* executed items. In Kolla this means a change for one container restarts every container of that role on that host. A nova-compute-only change restarts `nova_libvirt` and `nova_ssh`; a scheduler-only change restarts `nova_api`; a change on a network node restarts all neutron agents there | [ANSIBLE] `plugins/strategy/__init__.py:616-623`, `executor/task_executor.py:790`; minimal repro `annex/lab/notify-loop.*`; [LAB s03, s04, s05, s07, s09c] | Restart blast radius is per *role-on-host*, not per container. libvirt restarts far more often than operators expect |
| F2 | **`-t common` is a no-op.** Tags on the dynamic `include_tasks` do not propagate to the included tasks | [ANSIBLE] repro `annex/lab/tagdemo*`; [LAB s08] | `common` changes (fluentd/cron/toolbox) are applied by whatever run first reaches the host, often unexpectedly |
| F3 | **`docker_graceful_timeout` and `docker_client_timeout` are ignored.** The `kolla_docker` argument defaults (10 s, 120 s) override `common_options`, so every stop sends SIGKILL to a container still running **10 s** after SIGTERM | [CODE] `kolla_docker.py:991,1011,1037-1047`; [LAB] real module code fed handler arguments (`annex/lab/kolla_docker_params.out`) | On every restart, a service still running 10 s after SIGTERM is SIGKILLed with its in-flight work (heat-engine, cinder copies, glance uploads); for `nova_libvirt` this matters only if libvirtd has not exited by then ([05 §5](05-nova-deep-dive.md)). [HYPOTHESIS] Services started by a shell wrapper that does not `exec` them (e.g. `neutron-l3-agent`, `haproxy`) get no SIGTERM at all ([annex/kolla-images.md §2.6](../annex/kolla-images.md)). The release note claiming 60 s has no effect |
| F4 | **Same-tag image rebuilds are not picked up by `deploy`/`reconfigure`/`upgrade`.** Only absent images are pulled; an explicit `pull` is required | [CODE] `kolla_docker.py:805-808`; [LAB s09a-c] | Mutable tags create silent drift between hosts. A later unrelated `pull` turns into a mass recreate |
| F5 | **`reconfigure` = `deploy`** for 70 of the 72 roles that have a `tasks/reconfigure.yml` (67 via `import_tasks: deploy.yml`, plus congress, mongodb and nova-hyperv via `include_tasks: deploy.yml`; only swift and bifrost have their own logic). A reconfigure re-runs Keystone registration, DB creation/grants and the DB-sync bootstrap containers of most services. Neutron is the exception: with the default `neutron_enable_rolling_upgrade: "yes"`, `bootstrap_neutron` runs on `deploy` but is skipped on `reconfigure`, so a reconfigure re-runs Neutron's DB create/grant tasks but not its DB sync | [CODE] `roles/*/tasks/reconfigure.yml`; `roles/neutron/tasks/bootstrap_service.yml:21-22,24-46`, `roles/neutron/defaults/main.yml:411`; [LAB t1: 8 DB-sync bootstrap containers + 3 cell-management one-shots; s01: 5 one-shot runs for `-t nova`; s18: 10 for a no-tag `reconfigure` (7 DB-sync, no `bootstrap_neutron`, + 3 cell-management); s05/s06 (`-t neutron reconfigure`): none] | A "reconfigure" can apply schema migrations if the image tag moved, for most services; for Neutron only with non-default flags: `enable_neutron_sfc` (the `bootstrap_neutron_sfc` container runs `neutron-db-manage --subproject networking-sfc … upgrade head` on every reconfigure) or `neutron_enable_rolling_upgrade: "no"` (full `bootstrap_neutron`). There is never a "config only" path except `genconfig` + `deploy-containers` |
| F6 | **Global inputs are rendered into per-host files.** `enable_*` flags, RabbitMQ/memcached membership, service passwords and the external FQDN end up in compute-side files | [CODE] `group_vars/all.yml:206,216`; `nova-cell/templates/nova.conf.j2`; `neutron/templates/neutron.conf.j2:119` (memcached list, shared by the OVS agent on computes); `common/tasks/config.yml:109-240`; [LAB s07, s12] | Small central changes cause fleet-wide restarts |
| F7 | **`--list-tasks` cannot show what a tag runs**, and `--list-hosts` shows 0 hosts for `&enable_*` plays | [LAB] `annex/lab/list-tasks-nova.txt` | Operators need `genconfig`, the lab approach or staging to predict a run |
| F8 | **`--limit` does not confine actions.** `delegate_to: groups[x][0]` runs work on hosts outside the limit. In s17 (`deploy --limit compute004`) control01 ran the Neutron DB create/grant and the `bootstrap_neutron` container, plus cell discovery (`nova_list_cells`, `openstack compute service list`, `nova-manage cell_v2 discover_hosts`). The nova-cell RabbitMQ user/vhost creation is also delegated (to the first RabbitMQ host), but it runs only when the first nova-conductor is inside the limit, so s17 did not run it | [LAB s17]; [CODE] `roles/nova-cell/tasks/rabbitmq.yml` | "Only the new compute" still executes DB-sync containers on a controller |
| F9 | **With `--limit`, all hosts' facts are gathered sequentially** by the limited hosts (delegated loop) | [CODE] `gather-facts.yml:29-50`; [LAB s13: 1 host gathered 11] | O(total hosts) serial latency on every limited run without fact caching |
| F10 | **`kolla_serial` makes `run_once` steps repeat per batch** (API DB sync ×3 with serial 1) and orders a play's restarts by host-pattern order (computes before conductors in the nova-cell play) | [LAB s16] | Batching reduces blast radius but multiplies bootstrap work, and exposes ordering within a play |
| F11 | **The `openvswitch_agent.ini` merge** includes the operator's `ml2_conf.ini` overrides | [CODE] `roles/neutron/tasks/config.yml:172-190`; [LAB s05] | Server-side ML2 changes restart every OVS agent |
| F12 | **The L3 agent wrapper deletes all L3 namespaces at start** when `enable_neutron_agent_ha: yes` | [CODE] `neutron-l3-agent-wrapper.sh.j2:5-12` | Every L3 agent restart becomes a router data-plane outage on that node |
| F13 | **The Nova deploy order** puts nova-compute before OVS and the Neutron agents on new computes | [CODE] `site.yml:710-780`, [LAB t0 trace] | Expected and harmless on a running cloud; relevant when adding computes one by one |
| F14 | **`kolla_set_configs --check` has blind spots.** It compares only the `config_files` entries of `config.json` (content, mode, owner). A change confined to `config.json` itself (`command`, `permissions`; all of memcached's settings) is never detected. A newly added optional file makes it exit 2, which fails `check-containers`. `preserve_properties` entries (prometheus extras) and directory sources with subdirectories report drift on every run. A restart never removes the files of a dropped entry | [CODE] kolla `docker/base/set_configs.py:60-65,131-151,160-235,310-330,388-393,407-432`; `kolla_docker.py:566-578`; scratch run of the real script, outside a container ([annex/kolla-images.md §3](../annex/kolla-images.md)) | "`genconfig` + `--check`" ([09 §1](09-practical-command-reference.md)) under-reports some changes and over-reports others. A `config.json`-only change is applied by a normal deploy/reconfigure, because the changed template task notifies the restart handler. Once `genconfig` has written it, neither `deploy-containers` nor a later run (its template task is then unchanged) applies it until the container restarts for another reason |
| F15 | **What the bootstrap containers run differs per image.** Nova's bootstrap containers run with `KOLLA_UPGRADE` (schema sync, no online data migrations outside `upgrade`). Placement's `KOLLA_BOOTSTRAP` container also runs `online_data_migrations`, on every deploy/reconfigure. Heat's does not re-apply a changed `heat_domain_admin_password` to Keystone. neutron-server's migrates `neutron-dynamic-routing`, which the rolling `upgrade` never migrates | [CODE] kolla `docker/nova/nova-api/extend_start.sh:9-25`, `docker/nova/nova-conductor/extend_start.sh:3-17`, `docker/placement/placement-api/extend_start.sh:5-9`, `docker/heat/heat-api/extend_start.sh:5-17`, `docker/neutron/neutron-server/extend_start.sh:5-12,34-38`; `roles/nova/tasks/bootstrap_service.yml:13`, `roles/nova-cell/tasks/bootstrap_service.yml:11`, `roles/placement/tasks/bootstrap_service.yml:11`, `roles/heat/tasks/bootstrap_service.yml:11,21`, `roles/neutron/defaults/main.yml:412`; [LAB s04, s11] | What a "reconfigure" or a tag-changing "deploy" does to databases depends on the image, not only on kolla-ansible ([annex/kolla-images.md §4](../annex/kolla-images.md)) |

---

## 2. Implementation limitations and bugs (`ussuri-eol`)

| Area | Issue | Evidence | Status |
|---|---|---|---|
| CLI | `-e kolla_serial=N` is overridden by `ANSIBLE_SERIAL` (default 0) for `reconfigure`/`upgrade`; it is not passed for `deploy` | `tools/kolla-ansible:236,430,439` | [CODE] |
| CLI | `--ask-vault-pass` overwrites `VERBOSITY` with a copy of `EXTRA_OPTS` | `tools/kolla-ansible:320-323` | [CODE] |
| CLI | `--include-dev:` declared with an argument but used as a flag; the command line is executed unquoted | `tools/kolla-ansible:116,216,284-287` | [CODE] fact sheet E |
| site.yml | cyborg play uses `serial` instead of `kolla_serial` | `site.yml:1028` | [CODE] |
| site.yml | placement haproxy include lacks `when: enable_placement` | `site.yml:289-292` | [CODE] |
| kolla_docker | `graceful_timeout`/`client_timeout` from `docker_common_options` ignored (F3); `restart_policy` never compared (FIXME `:21`) | `kolla_docker.py` | [CODE+LAB] |
| kolla images | `kolla_set_configs --check` compares only `config_files` entries (F14): changes confined to `config.json` (`command`, `permissions`; all of memcached's settings) are never detected, so neither `genconfig` + `deploy-containers` nor a later run applies them until the container restarts for another reason; a newly added optional file makes it exit 2 and fails `check-containers`; `preserve_properties` entries (prometheus extras) and directory sources with subdirectories report drift on every run; a restart never removes files whose entry was dropped | kolla `docker/base/set_configs.py:60-65,131-151,160-235,310-330,388-393,407-432`; `kolla_docker.py:566-578` | [CODE], scratch run of the real script |
| common | `-t common` no-op (F2) | – | [LAB] |
| haproxy | Restart instead of reload; stale `services.d` files never removed; keepalived priority from inventory order; upgrade "Stopping all slave keepalived" without an `enable_keepalived` guard and with raw interface names | fact sheet A §1.8 | [CODE], [NEEDS-LAB] for the upgrade bugs |
| openvswitch | `Set system-id` always reports changed | `roles/openvswitch/tasks/post-config.yml:3-5` | [CODE+LAB] |
| neutron | `upgrade` with the default `neutron_enable_rolling_upgrade: "yes"` expands/contracts only `neutron`, `neutron-fwaas` and `neutron-vpnaas`: `neutron-dynamic-routing`, which the `KOLLA_BOOTSTRAP` container migrates on `deploy`, is never migrated by `upgrade`, and the image's rolling `neutron-db-manage` calls pass no `--config-file`. `has_offline_migrations` runs on the first neutron-server host with `ignore_errors`; any non-zero rc (a failed `docker exec` included) stops `neutron_server` on every neutron-server host in the play until the handler flush after the contract container: a Neutron API outage | `roles/neutron/defaults/main.yml:411-412`; `roles/neutron/tasks/upgrade.yml:2-3`; `roles/neutron/tasks/rolling_upgrade.yml:13-33,43-67,69-93`; `roles/neutron/tasks/bootstrap_service.yml:21-22`; kolla `docker/neutron/neutron-server/extend_start.sh:5-12,34-38` | [CODE]; impact [HYPOTHESIS] |
| ovs-dpdk | `pull` looks up a non-existent `ovs_services` variable; the NIC mapping file is written once; the 300 s wait handler has no port | fact sheet A §6 | [CODE] |
| rabbitmq | outward RabbitMQ `pull` looks up `outward_rabbitmq_services` | fact sheet B §2.8 (item 6) | [HYPOTHESIS] |
| rabbitmq | the image writes `.erlang.cookie` only in the bootstrap container (new volume); a cookie change recreates the brokers (env compare) but they keep the old cookie, while `kolla_toolbox` gets the new one | kolla `docker/rabbitmq/extend_start.sh:7-18`; `roles/rabbitmq/tasks/bootstrap.yml:26`; `roles/common/tasks/config.yml:242-250` | [CODE]; consequences [HYPOTHESIS] |
| mariadb | restart waves continue after a failed WSREP wait (no `any_errors_fatal`); recovery stops healthy nodes; clustercheck started even when disabled | fact sheet B §1.5, §1.8 (items 5–6) | [CODE], wave behaviour [HYPOTHESIS] |
| keystone | fernet cron generator hour calculation; precheck vs generator expiry limits; push script stops at the first unreachable peer | fact sheet B §3.9 (items 3–5) | [CODE + executed generator] |
| glance | global `log_bin_trust_function_creators` toggle on every deploy/reconfigure; file backend = single host; backend switches silently when Swift/Ceph is enabled | fact sheet C §1 | [CODE] |
| cinder | no `host`/`backend_host`/`cluster`; etcd coordination uses only the first etcd host; Ceph backup driver default without a Ceph config | fact sheet C §3 | [CODE] |
| heat | `bootstrap_heat` creates `heat_user_domain`/`heat_domain_admin` only when the domain is absent: a changed `heat_domain_admin_password` reaches `heat.conf` but never Keystone | kolla `docker/heat/heat-api/extend_start.sh:8-14`; `roles/heat/templates/heat.conf.j2:12-13` | [CODE]; impact [HYPOTHESIS] |
| swift | no handlers are notified (deploy does not apply config/ring changes); `stop.yml` wrong container name; precheck probes rsync port 873 vs 10873 | fact sheet D | [CODE], [NEEDS-LAB] |
| octavia | upgrade removes the octavia admin role on `admin` without re-registering; no amphora resources are created | fact sheet D | [CODE] |
| masakari | instancemonitor uses `qemu+tcp` without SASL while nova-libvirt enables SASL | fact sheet D | [HYPOTHESIS] |
| baremetal | Docker restarted on `daemon.json` change on all hosts at once; `docker_custom_option` changes are never applied; Docker masked during re-runs on Debian/Ubuntu; `/etc/hosts` lists every baremetal host (O(N²) templating, stale with `--limit`) | fact sheet E §1–5 | [CODE], [NEEDS-LAB] |
| certificates | test CA only; certs never renewed; new backend hosts not added | fact sheet A §8, E | [CODE] |

---

## 3. Corrections to the annex fact sheets

The fact sheets were produced by parallel source-reading agents and spot-checked (MariaDB restart waves, glance
`log_bin_trust_function_creators`, the Docker restart gate, keepalived priority, compute-side memcached lists: all
confirmed). Eleven corrections apply. All are listed with their evidence under "Verification and errata" in
[annex/factsheets/README.md](../annex/factsheets/README.md). The last four bullets (seven corrections) were also made in
the sheets themselves:

- **Fact sheet A** (and any sentence elsewhere) stating that `docker stop` uses `docker_graceful_timeout` = 60 s is
  wrong. The effective timeout is **10 s** (F3). Fact sheet C states this correctly. This is the correction with the
  widest effect.
- **Fact sheet A**, "no reload path anywhere": true for handlers, but `nova_scheduler` receives a `SIGHUP` on every
  `deploy`/`reconfigure` that runs the `nova`, `nova-api` or `nova-refresh-scheduler-cell-cache` tag (or no tag) and
  whose `--limit` includes the `nova-scheduler` hosts (`ansible/nova.yml:139-156`).
- **Fact sheet B §3.10**, memcached counts: 35 roles use `memcache_secret_key`, and 38 embed the memcached host list.
- **Fact sheet A**, `tags: always` on `import_role: haproxy-config` "in every `loadbalancer.yml`": 48 of 49 files do
  it directly; nova-cell reaches it through a chain of includes.
- **Fact sheet B**, "Graceful stop" row: it also stated 60 s; the sheet now states 10 s (F3).
- **Fact sheet B**, Erlang cookie: the kolla image writes `.erlang.cookie` only in the `KOLLA_BOOTSTRAP` container,
  which runs only on a new volume, not at every start. The sheet's former hypothesis of a partition during the
  rolling recreate rested on that wrong premise; the corrected behaviour is in the second rabbitmq row of §2.
- **Fact sheet C**, four image-side statements, checked against the kolla `ussuri-eol` sources (F15):
  - Placement online data migrations also run on every deploy/reconfigure, inside `bootstrap_placement`, not only on
    upgrade.
  - The heat domain admin is created only when `heat_user_domain` is absent, so a changed password is not
    re-applied.
  - Horizon's collectstatic/compress is conditional (settings hash changed or missing, a plugin toggled, or
    `FORCE_GENERATE=yes`), not run on every start.
  - The glance bootstrap also runs `glance-manage db_load_metadefs`.
- **Fact sheet E**, "For every other command, `-e kolla_serial=...` works": `upgrade` overrides it like
  `reconfigure` does (`tools/kolla-ansible:430`); use `ANSIBLE_SERIAL`.

---

## 4. Open questions and required experiments

These questions cannot be settled by static analysis or the stub lab, except Q10 and Q14, which are answered in their
rows: Q10 by re-running the reproductions on Ansible 2.8, Q14 by reading the kolla image sources. Each of the others
comes with a proposed experiment, to run on a staging environment that matches production: same kernel, cgroup
version, Docker version, Kolla images, network hardware.

| # | Question | Why it matters | Experiment | Observables |
|---|---|---|---|---|
| Q1 | Do running VMs survive a `nova_libvirt` restart or recreate? | F1 makes libvirt restarts frequent | 5 VMs on one compute; `docker restart nova_libvirt`; then a nova-compute-only override + `-t nova reconfigure --limit` that host; then an image change + `deploy` (recreate) | QEMU PIDs before/after, `/proc/<pid>/cgroup`, `readlink /proc/<qemu-pid>/ns/mnt` vs the new libvirtd's, guest ping, `virsh list`, `nova show` power state, whether the `Restart nova-libvirt container` handler needed its retries (`retries: 5`); repeat on cgroup v1 and v2 hosts |
| Q2 | Data-plane loss during a `neutron_openvswitch_agent` restart | R5 | Continuous ping/iperf between VMs on two computes; restart the agent; then a `-t neutron` drift | packet loss duration, `ovs-ofctl dump-flows br-int` cookie changes |
| Q3 | Data-plane loss during an `openvswitch_vswitchd` restart or recreate | R7 | Same, with an OVS image change | packet loss, time to flow restoration |
| Q4 | L3 agent restart with and without `enable_neutron_agent_ha` | R6 | FIP ping during a restart; router failover observation | loss duration, keepalived state changes, `ip netns` |
| Q5 | HAProxy restart: VIP behaviour | R8 | Continuous API polling + DB pings through the VIP during `-t haproxy` drift with serial 0 vs `ANSIBLE_SERIAL=1` | error window, keepalived transitions, VIP location |
| Q6 | MariaDB rolling restart under load with an induced failure in wave 1 | R9 | Block one node's WSREP sync (e.g. firewall the Galera ports) during a reconfigure | do later waves proceed? cluster size over time |
| Q7 | Real timing at scale (SSH, pipelining, fact caching, forks) | doc 06 model | Run `-t nova reconfigure` (no drift) with 50/100/200 computes on a test fleet or VMs, with forks 20/50/100, pipelining on/off, fact cache on/off | wall time per play, deploy-host CPU, SSH connection count |
| Q8 | Image sizes and registry throughput | doc 06 model | `docker image inspect -f '{{.Size}}'` for the Ussuri images in use; registry egress during `pull` | GB per compute, pull wall time vs forks |
| Q9 | Check mode (`--check --diff`) usability | doc 09 | `EXTRA_OPTS="--check --diff" kolla-ansible -t nova reconfigure` on staging | which tasks fail; is the diff output useful? |
| Q10 | Ansible 2.8 vs 2.9 behaviour for F1/F2 | Ussuri allows 2.8 | Done: both reproductions re-run on Ansible 2.8.20 and 2.9.27 | **Answered: identical** (`annex/lab/*.ansible-2.8.out`); the responsible code blocks are unchanged between the two versions (03 §2.1, §2.4) |
| Q11 | Fernet key distribution failure modes | R19 | Stop one keystone node during `-t keystone reconfigure` | key directory contents per node; token validation across nodes |
| Q12 | Glance backend switch on enabling Swift | R21 | Enable Swift on staging with images in the file store | image download success |
| Q13 | `bootstrap-servers` re-run effects on a live compute | R14 | Re-run with an unchanged and a changed `daemon.json` on a staging compute with VMs | Docker restart?, container restarts, VM state |
| Q14 | Behaviour of the kolla images' `extend_start.sh` (what `KOLLA_BOOTSTRAP`/`KOLLA_UPGRADE` run) | F5, F15 | Done: read the kolla `ussuri-eol` image sources (no image was run) | **Answered (source)**, see [annex/kolla-images.md §4](../annex/kolla-images.md). Nova's bootstrap containers run with `KOLLA_UPGRADE`: `api_db sync` + `db sync` (nova-api), `db sync --local_cell` (nova-conductor), so Nova's online data migrations never run outside `upgrade`; the images' `KOLLA_BOOTSTRAP` branches are unreachable. Placement's `KOLLA_BOOTSTRAP` runs `db sync` + `online_data_migrations` on every deploy/reconfigure. Glance adds `db_load_metadefs`. Heat creates `heat_user_domain`/`heat_domain_admin` only if the domain is absent, so a changed `heat_domain_admin_password` is never pushed to Keystone. neutron-server's `KOLLA_BOOTSTRAP` migrates neutron, -dynamic-routing, -fwaas and -vpnaas; the rolling upgrade list omits -dynamic-routing. RabbitMQ writes the Erlang cookie only in its bootstrap container. Agent, OVS and OVN images have no one-shot branch |

---

## 5. Limits of this study

- **The lab simulates hosts.** The real `site.yml`, roles, filters, action plugins (`merge_configs`) and the
  `template`, `copy` and `file` modules run for real; files are written per simulated host. Modules that need Docker
  or change the host (`kolla_docker`, `kolla_toolbox`, `command`/`shell`, `sysctl`, `modprobe`, `systemd`,
  `wait_for`, `setup`, `slurp`, `docker_image_info`, `kolla_container_facts`) are replaced by stubs. The
  `kolla_docker` stub mirrors `check_container_differs()` and `recreate_or_restart_container()`. It is validated by
  the idempotency run: the second `deploy` produced **zero** restarts. The stub approximates
  `kolla_set_configs --check` with a content hash of the whole `/etc/kolla/<svc>/` directory, so LAB results do not
  validate the real `--check` semantics ([annex/kolla-images.md §3](../annex/kolla-images.md)).
- **Lab wall times are not production times.** They use a local connection with no SSH, on a 4-vCPU deploy host.
  They are useful only for relative comparisons and for counting work ([06](06-compute-scaling-and-performance.md)).
- **No real container or VM behaviour was observed.** Every statement about data-plane or VM impact is
  [HYPOTHESIS] or [NEEDS-LAB].
- **The lab service set is limited.** The core set was covered; the other roles were covered by static analysis
  only (fact sheets).
- **The kolla image sources were read, not built or run.** From the kolla `ussuri-eol` repository: the base start
  path (`docker/base`: `Dockerfile.j2`, `start.sh`, `set_configs.py`, `copy_cacerts.sh`, `httpd_setup.sh`,
  `sudoers`, healthcheck scripts) and the start scripts of the images listed in
  [annex/kolla-images.md](../annex/kolla-images.md) (Nova, Neutron, Open vSwitch, OVN, Keystone, Glance, Placement,
  Cinder, Heat, Horizon, Barbican, Octavia, Manila, Swift, MariaDB, RabbitMQ, memcached, HAProxy, keepalived incl.
  `check_alive.sh`, fluentd, cron, kolla-toolbox, chrony, iscsid, tgtd). Of the other images only the `ironic-api`
  bootstrap branch was read. What the scripts do against real services and data stays [HYPOTHESIS] or [NEEDS-LAB].
  `set_configs.py --check` was exercised standalone on a scratch tree, outside a container.
