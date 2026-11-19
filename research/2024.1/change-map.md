# Change map 2023.1 → 2024.1 (working notes for the 2024.1 re-study)

Working document, not a site page. It lists what changed between the two studied trees in the parts of the code that
decide what Day-2 commands do, and which 2023.1 pages each change touches. Every item below was checked by reading or
diffing the two source trees; it is a map for the re-study, not a substitute for it: each 2024.1 page must still
re-read its own statements in the 2024.1 sources (brief, rules 1-3).

## 0. Sources and conventions

| Source | 2024.1 (studied) | 2023.1 (compared against) |
|---|---|---|
| kolla-ansible | tag `2024.1-eom`, commit `890396f`, 18.x, `openstack_release: "2024.1"` (`ansible/group_vars/all.yml:679`) | tag `2023.1-eol`, commit `4891a21` (`openstack_release: "2023.1"`, `group_vars/all.yml:578`) |
| kolla (images) | tag `2024.1-eom`, commit `ed7a36a` | tag `2023.1-eol`, commit `de82941` |
| ansible-collection-kolla | tag `2024.1-eom`, commit `82a0f5c`; kolla-ansible `requirements.yml:5` pins `stable/2024.1` | tag `2023.1-eol` |
| ansible-core | 2.16.20 (`tools/kolla-ansible:10-11` accepts 2.15-2.16) | 2.14.18 was used for 2023.1; **not on disk**, so no ansible-core diff was made |

Conventions of this file:

- kolla-ansible paths are repository-relative (`ansible/site.yml:88`, `tools/kolla-ansible:10`); kolla paths start with
  `docker/`; collection paths start with `roles/` and are marked "collection". "2024.1 `x:n`" is a 2024.1 line,
  "2023.1 `x:n`" the old behaviour.
- "Rename-normalised diff": the 2023.1 `ansible/` tree with every `kolla_docker:` replaced by `kolla_container:`,
  diffed against 2024.1 `ansible/`. 250 files differ after normalisation; most of the other ~195 files that used
  `kolla_docker:` differ only by the module name.
- Labels: [CODE] = read in the code; [NOT AVAILABLE] = the sources do not establish it. Items marked "re-read" are
  pointers for the re-study, not conclusions.

## 1. Cross-cutting changes 2023.1 → 2024.1

Short IDs (X1…X18) are used in the impact table (§2).

### X1 — CLI: still the bash `tools/kolla-ansible`; ansible-core 2.15-2.16 [CODE]

- **Still holds:** the CLI is the bash script `tools/kolla-ansible`, installed as a script (`setup.cfg:43-44`); there is
  no Python CLI in 2024.1 (`kolla_ansible/cmd/` holds only `genpwd`, `mergepwd`, `readpwd`, `writepwd`). It still
  builds one `ansible-playbook` command (2024.1 `tools/kolla-ansible:603-604`; 2023.1 `:586-587`), and `upgrade` /
  `reconfigure` still pass `-e kolla_serial=${ANSIBLE_SERIAL}` (2024.1 `:522,531`; 2023.1 `:508,517`).
- **Changed:** accepted ansible-core range `2.15`-`2.16` (2024.1 `tools/kolla-ansible:10-11`; 2023.1 `2.13`-`2.14`).
- **Changed:** `install-deps` installs `requirements-core.yml` (pinned galaxy collections incl. `community.docker <4`
  and `containers.podman <2`) when the `ansible` package is not installed (2024.1 `tools/kolla-ansible:131-144`;
  `requirements-core.yml`).
- **Removed:** the `monasca_cleanup` command and playbook (2023.1 `tools/kolla-ansible:184,235,447-451`;
  `ansible/monasca_cleanup.yml` is gone).
- **New:** `destroy` passes the list of inventories as `-e inventories_comma_separated=…` (2024.1
  `tools/kolla-ansible:458-474`), forwarded to `tools/cleanup-host` as `kolla_ansible_inventories`
  (`ansible/roles/destroy/tasks/cleanup_host.yml:17`) so that the inventory directories are skipped when
  `/etc/kolla` content is removed (`tools/cleanup-host`, skip loop). `tools/cleanup-containers` now also disables and
  resets the `kolla-<name>-container.service` units.
- **New:** `octavia-certificates --check-expiry <days>` (2024.1 `tools/kolla-ansible:207,411,550-555`;
  `ansible/roles/octavia-certificates/tasks/check_expiry.yml`).

### X2 — Container module: `kolla_docker` → `kolla_container`, with a Podman worker [CODE]

- `ansible/library/kolla_docker.py` is gone; `ansible/library/kolla_container.py` replaces it (2024.1: 0 `kolla_docker:`
  tasks, 180 files with `kolla_container:`; 2023.1: 195 files with `kolla_docker:`). Same 15 actions (2024.1
  `kolla_container.py:273-287`; 2023.1 `kolla_docker.py:264-278`).
- **Engine dispatch:** new parameter `container_engine` (2024.1 `kolla_container.py:294`), default `'docker'` in
  `common_options_defaults` (`:361-373`, value at `:372`); `main()` imports `DockerWorker` for `docker`, otherwise
  `PodmanWorker` (`:410-428`, branch `:415-420`). 2023.1 imported only `DockerWorker` (`kolla_docker.py:22,404`), the
  basis of the 2023.1 statement "Docker only" (`concepts/repository-architecture.md` line 457, line 514-516; method
  page phase 3) — **no longer holds in 2024.1**.
- The engine reaches the module through `docker_common_options.container_engine: "{{ kolla_container_engine }}"`
  (2024.1 `ansible/group_vars/all.yml:142-153`, key at `:153`). `kolla_container_engine` still defaults to `"docker"`
  (`group_vars/all.yml:92`, both releases). Only one `kolla_container:` task passes neither `common_options` nor
  `container_engine` (2024.1 `ansible/roles/grafana/tasks/post_config.yml:19`), so it always uses Docker.
- New `ansible/module_utils/kolla_podman_worker.py` (677 lines): talks to `http+unix:/run/podman/podman.sock` (`:21,73`);
  `compare_container` = missing or `check_container_differs()` or `compare_config()` (in-container
  `kolla_set_configs --check`) or `systemd.check_unit_change()` (`:294-301`), same shape as the shared one;
  `recreate_or_restart_container` (`:507-524`) does **not** set `changed=True` up front (Docker does,
  `kolla_docker_worker.py:342`); restart policy is dropped from the container and left to systemd (`:57-59,142`).
  Podman behaviour as a whole is outside what the 2023.1 pages cover → [NOT AVAILABLE] beyond reading this file.
- `kolla_toolbox` and `kolla_container_facts` modules now have `use_docker` / `use_podman` paths
  (2024.1 `ansible/library/kolla_toolbox.py:145,210,253`; `kolla_container_facts.py:73,90,113`). Docker path of
  `kolla_toolbox`: `exec_start(job)` without `demux`, so inner stderr is no longer logged separately (2024.1
  `kolla_toolbox.py:158-165`; 2023.1 `:184-186`). `module_args` given as a string are now split with `shlex`
  (2024.1 `:117-131`).
- Podman-only host side effects added to roles: `/etc/tmpfiles.d/kolla.conf` + `systemd-tmpfiles --create` in common
  (2024.1 `ansible/roles/common/tasks/config.yml:30-40`); `/run/openvswitch` created on the host
  (`ansible/roles/openvswitch/tasks/config-host.yml:12-20`); `/run` mounts lose `:shared` under Podman and get the
  `run_default_volumes_podman` sub-mounts instead (`group_vars/all.yml:165-179`; e.g.
  `roles/nova-cell/defaults/main.yml:11,62,374-376`; `roles/common/defaults/main.yml:22,111`); `prune-images` uses
  `podman image prune` (2024.1 `ansible/roles/prune-images/tasks/prune_images.yml:9,13-16`); Docker version precheck
  only for Docker (2024.1 `ansible/roles/prechecks/tasks/service_checks.yml:15-17`); volume paths via
  `container_engine_volumes_path` (`group_vars/all.yml:156-158`), used by `common/tasks/bootstrap.yml:13` and
  `mariadb/tasks/recover_cluster.yml:47,106` (2023.1 hard-coded `/var/lib/docker/volumes`).
- `ansible/` mentions `podman` in 11 files in 2024.1 (0 in 2023.1).

### X3 — Docker worker / compare logic [CODE]

- **Still holds (Docker):** `compare_container` = missing or `check_container_differs()` or `compare_config()` or
  `systemd.check_unit_change()` (2024.1 `ansible/module_utils/kolla_container_worker.py:58-65`; 2023.1 `:59-66`); the
  same 16 comparisons in `check_container_differs` (2024.1 `:67-89`); `compare_config` runs
  `/usr/local/bin/kolla_set_configs --check` (`COMPARE_CONFIG_CMD`, `:20`; Docker `kolla_docker_worker.py:146-181`,
  2023.1 `:155-190`); `recreate_or_restart_container`: COPY_ONCE or differs → pull if needed, stop, remove, start;
  COPY_ALWAYS → restart via the unit (2024.1 `kolla_docker_worker.py:341-363`; 2023.1 `:362-384`);
  `restart_container` goes through `systemd.create_unit_file()` + `systemd.restart()` (2024.1 `:439-459`).
- **Changed:** cgroupns is always compared and set (no API-version guard): 2024.1
  `kolla_container_worker.py:142-155`, `kolla_docker_worker.py:300-304`; `kernel_memory` always dropped from the
  dimension map (`kolla_docker_worker.py:39-40`). 2023.1 gated both on Docker API ≥ 1.41/1.42
  (2023.1 `kolla_docker_worker.py:43-49`).
- `KOLLA_SERVICE_NAME` injection moved from the Docker worker to the base class (2024.1
  `kolla_container_worker.py:569-578`); behaviour for Docker unchanged.
- Line numbers of every `module_utils` citation shift (e.g. `kolla_docker_worker.py:155-190` → `:146-181`,
  `kolla_container_worker.py:59-66` → `:58-65`).

### X4 — systemd unit template text changed → first 2024.1 check flags every unit [CODE]

- 2024.1 `ansible/module_utils/kolla_systemd_worker.py:20-39`: `Description=${engine} …`, `After=/Wants=${deps}`,
  `StartLimitInterval=` (no blank line after it), `ExecStart/ExecStop=/usr/bin/${engine} …`; `deps` is
  `docker.service` for Docker, `network-online.target` otherwise (`:50-54`). 2023.1 `:20-39` had
  `StartLimitIntervalSec=` followed by a blank line and literal `docker`.
- `check_unit_change` compares the whole file text (2024.1 `:154-167`) and is part of `compare_container` (X3). So for a
  unit written by 2023.1 code, the first 2024.1 `compare_container` returns changed even with Docker and no other
  difference, and `create_unit_file` rewrites + `daemon-reload` + enable (`:172-185`). In an upgrade most containers
  are recreated anyway (new image); a container that is not recreated is flagged at its next 2024.1
  `deploy`/`reconfigure` check. Exact unit-file bytes before/after on a real host: re-read when writing R24/F3.
  Handler and restart consequences on a live system: [NOT AVAILABLE] beyond the code path.
- Still holds: `restart_timeout = client_timeout`, `restart_duration = timeout // retries - 1`, `unless-stopped` →
  `Restart=always` (2024.1 `:56-66`).

### X5 — `max_fail_percentage` on every play; new `any_errors_fatal`; etcd loses `serial` [CODE]

- All 51 plays of `site.yml` (2024.1 `ansible/site.yml`, e.g. `:10-13`, `:81-84`, common `:96-99`, loadbalancer
  `:111-114`), and of `gather-facts.yml:7,36`, `kolla-host.yml:8`, `nova.yml`,
  `mariadb.yml:8-11,25-28,…`, `rabbitmq.yml:8-11,37-40,…`, `destroy.yml:4-7`, `prune-images.yml:8`,
  `mariadb_backup.yml:4`, `mariadb_recovery.yml:4`, `nova-libvirt-cleanup.yml:9`, `rabbitmq-upgrade.yml:7` now sets
  `max_fail_percentage: {{ <svc>_max_fail_percentage | default(kolla_max_fail_percentage) | default(100) }}`.
  `kolla_max_fail_percentage` is unset by default (2024.1 `etc/kolla/globals.yml:27-31`, commented).
- With 100, ansible-core 2.16.20 adds nothing: the check breaks the play only when
  `len(_failed_hosts) / batch_size > 1.0` (`lib/ansible/plugins/strategy/linear.py:336-350`); the "whole batch failed →
  stop" rule still applies (`lib/ansible/executor/playbook_executor.py:204-208,219-220`). Checked on
  review: `_failed_hosts` is per batch, not per run. `PlaybookExecutor` calls `TaskQueueManager.run()` once per
  batch (`lib/ansible/executor/playbook_executor.py:184-190`), and `run()` marks the hosts that failed before as
  failed in the iterator, then clears `_failed_hosts` (`lib/ansible/executor/task_queue_manager.py:330-338`), so the
  ratio of `linear.py:340` counts the failures of the current batch against `batch_size` [CODE].
- **No longer holds:** "the MariaDB restart plays set neither `any_errors_fatal` nor `max_fail_percentage`"
  (2023.1 `components/mariadb.md` line 77-78, factsheet B line 150): 2024.1 `ansible/mariadb.yml:18-35` sets
  `max_fail_percentage` (default 100, so same effect unless the operator sets it).
- **New `any_errors_fatal: true`** on "Run Nova API online data migrations" (2024.1 `ansible/nova.yml:258-270`); the
  cell-DB bootstrap (`:79`) and cell online-migration (`:295`) plays already had it (2023.1 `nova.yml:75,265`).
- **etcd play has no `serial` any more** (2024.1 `ansible/site.yml:470-482`; 2023.1 `site.yml:440-449` had
  `serial: kolla_serial`), and its handlers are rewritten (X6).

### X6 — Handlers and restart logic [CODE]

- **Unchanged after the rename** (rename-normalised diff empty): handlers of `mariadb`, `rabbitmq`, `keystone`,
  `neutron`, `openvswitch`; `ovn-controller` role entirely; `rabbitmq/tasks/restart_services.yml`,
  `mariadb/tasks/restart_services.yml`; nova-cell handlers except the fake-driver volumes
  (2024.1 `ansible/roles/nova-cell/handlers/main.yml:201-206`). Line numbers inside these files are unchanged; the
  module name changed.
- **etcd rewritten:** handlers are `include_tasks` with `listen` (2024.1 `ansible/roles/etcd/handlers/main.yml:1-72`):
  look up leader (`:9-17`), bootstrap new services (`:19-27`), upgrade = non-leaders one by one (`:29-38`), otherwise
  rolling restart of non-leaders in 4 groups by `index % 4` (`:40-55`), then the leader (`:57-65`), then remove
  deleted members (`:67-72`); new task files `bootstrap*.yml`, `lookup_*.yml`, `restart_services.yml`,
  `remove_deleted_members.yml`. 2023.1 had one `recreate_or_restart_container` handler.
- **loadbalancer:** new `Restart haproxy-ssh container` handler (2024.1 `ansible/roles/loadbalancer/handlers/main.yml:331-345`);
  the other handlers unchanged.
- **prometheus:** `Restart prometheus-haproxy-exporter container` handler removed; **ironic:** new
  `Restart ironic-prometheus-exporter container` (2024.1 `ansible/roles/ironic/handlers/main.yml:100-113`).
- ansible-core 2.16 handler semantics (loop-notify, `listen`, handlers that `include_tasks`, `run_once` on handlers)
  must be re-read in 2.16.20 for F1, F10 and the etcd handlers; 2.14 is not on disk, so no "changed" claim can be made
  about ansible-core itself.

### X7 — common play: fluentd, cron, kolla_toolbox [CODE]

- Play unchanged in shape (hosts `cron`, `fluentd`, `kolla-logs`, `kolla-toolbox`, tag `common`, `serial`), plus
  `max_fail_percentage` (2024.1 `ansible/site.yml:88-103`; 2023.1 `:86-97`). `common/handlers` unchanged.
- **New in `config.yml` (so also in `genconfig`, `kolla_action=config`):** `ensure_image` of the fluentd image
  (2024.1 `ansible/roles/common/tasks/config.yml:42-51`), then `docker_image_info` / `podman_image_info` of it and
  `set_fact fluentd_cmd/fluentd_user` from image labels `fluentd_binary`/`fluentd_user`, default `td-agent`
  (`:53-91`). A config-only run can therefore pull the fluentd image when it is absent (`ensure_image`). 2023.1 set
  `fluentd_cmd`/`fluentd_user` in the template (2023.1 `common/templates/fluentd.json.j2:1,4`).
- fluentd command now `{{ fluentd_cmd }} -c /etc/<cmd>/<cmd>.conf -o …` (2024.1 `common/templates/fluentd.json.j2:1-5`);
  new inputs `11-letsencrypt.conf.j2` and `12-systemd.conf.j2` (journal, when `enable_fluentd_systemd`,
  `group_vars/all.yml:766`) (`config.yml:166-169`); fluentd always mounts `/var/log/journal:ro`
  (`common/defaults/main.yml:124`) → the fluentd container differs (volumes) from a 2023.1 one.
- kolla_toolbox: command `kolla_toolbox` instead of `sleep infinity` (2024.1 `common/templates/kolla-toolbox.json.j2:2`),
  i.e. kolla `docker/kolla-toolbox/kolla_toolbox.sh:1-16` (traps SIGTERM/SIGQUIT and exits 0; loop of `sleep 1`);
  `/run` mount `:shared` only with Docker plus `run_default_volumes_<engine>` (`common/defaults/main.yml:22,111`);
  toolbox image now ships `ansible-core==2.16.*` (kolla `docker/kolla-toolbox/Dockerfile.j2:76`; 2023.1 `2.14.*`, `:73`).
- cron/fluentd service lists: freezer, murano, outward-rabbitmq, sahara, senlin, solum, vitrage removed; `redis`
  logrotate and `placement` fluentd input added (2024.1 `common/tasks/config.yml:205-262`; `common/defaults/main.yml`
  input list).
- `-t common` (F2) and the "common changes" page must be re-checked against these new tasks.

### X8 — loadbalancer / HAProxy / keepalived / ProxySQL [CODE]

- Play: same hosts and tags + `max_fail_percentage` (2024.1 `ansible/site.yml:105-327`; 2023.1 `:99-341`); the
  per-service `loadbalancer.yml` includes lose freezer, murano, sahara, senlin, solum, vitrage and gain `letsencrypt`
  (`:208-212`); the rabbitmq include is `when: enable_rabbitmq | bool` only (`:288`).
- **New play** "Apply role letsencrypt" between loadbalancer and collectd (2024.1 `ansible/site.yml:328-340`;
  `enable_letsencrypt: "no"`, `group_vars/all.yml:796`).
- **New container `haproxy_ssh`** in `loadbalancer_services`, enabled only with letsencrypt (2024.1
  `ansible/roles/loadbalancer/defaults/main.yml:29-36`), its files (`tasks/config.yml:289-304`) and handler (X6).
- haproxy volumes always include `letsencrypt_certificates:/etc/haproxy/certificates` (2024.1 `defaults/main.yml:121`)
  → the haproxy container differs from a 2023.1 one. `haproxy_socket_level_admin` now follows `enable_letsencrypt`
  (`:182`). `haproxy_processes`/`haproxy_process_cpu_map` renamed `haproxy_threads`/`haproxy_thread_cpu_map`
  (2024.1 `:66-67`; 2023.1 `:54-55`): an old override name is no longer read.
- **Single external frontend** (off by default, `group_vars/all.yml:931-932`): extra template
  (`loadbalancer/tasks/config.yml:162-176`) and an `external-frontend-map` block per service
  (`ansible/roles/haproxy-config/tasks/main.yml:25-53`), both notify `Restart haproxy container`; every
  `<svc>_public_port` now depends on it (`group_vars/all.yml:332-665`).
- Keepalived: the "stop/remove disabled services" task now also requires `keepalived_track_script_enabled`
  (2024.1 `loadbalancer/tasks/config.yml:83`), and both service-check tasks skip `haproxy-ssh` (`:86,107`). kolla
  `docker/keepalived/check_alive.sh` lost the legacy single `socat` haproxy check (2023.1 `:33-37`; 2024.1 file ends
  at `:33`).
- `config-host.yml` sysctl settings now go through the new `sysctl` role (2024.1
  `ansible/roles/loadbalancer/tasks/config-host.yml:8-18`; `ansible/roles/sysctl/tasks/main.yml:1-20`); same
  values, same `KOLLA_UNSET`/`KOLLA_SKIP` logic.
- `upgrade.yml` first stops/removes `prometheus_haproxy_exporter` and its config on every loadbalancer host (2024.1
  `ansible/roles/loadbalancer/tasks/upgrade.yml:2-19`).
- ProxySQL: `proxysql-config` and `hacluster` roles unchanged (normalised diff empty); `loadbalancer/templates/proxysql/proxysql.yaml.j2` changed (re-read).

### X9 — MariaDB [CODE]

- **Still holds:** play structure of `ansible/mariadb.yml` (apply role → restart `serial: "33%"` → start
  `serial: "33%"` → bootstrap restart → post-config; 2024.1 `:3,18,36,54,70`), handlers and `restart_services.yml`
  unchanged (X6); only `max_fail_percentage` added (X5).
- `recover_cluster.yml` uses `container_engine_volumes_path` (2024.1 `ansible/roles/mariadb/tasks/recover_cluster.yml:47,106`)
  and passes `common_options` to `stop_container` (`:21-25`).
- Mariabackup: schema `mysql` instead of `PERCONA_SCHEMA` (2024.1 `ansible/roles/mariadb/defaults/main.yml:124`);
  the "Creating the Mariabackup database" task is gone; backup user privileges now
  `RELOAD,PROCESS,LOCK TABLES,BINLOG MONITOR` + `mysql.mariadb_backup_history:CREATE,ALTER,INSERT`
  (`roles/mariadb/tasks/register.yml:49`). kolla adds `docker/mariadb/mariadb-server/backup_replica.sh` and
  `docker/mariadb/mariadb-clustercheck/socat_wrapper.sh` (re-read for database-operations).
- kolla `docker/mariadb/mariadb-server/extend_start.sh:55` logs `mysql_upgrade` to `mariadb-upgrade.log`.

### X10 — RabbitMQ: quorum queues on by default, stricter prechecks, outward RabbitMQ removed [CODE]

- **Default flipped:** `om_enable_rabbitmq_quorum_queues: true` (2024.1 `ansible/group_vars/all.yml:268`; 2023.1
  `false`, `:231`). New `om_enable_queue_manager: false` (`:269`), `om_enable_rabbitmq_transient_quorum_queue`
  (`:274`), `om_enable_rabbitmq_stream_fanout` (`:279`), `om_rabbitmq_qos_prefetch_count: "1"` (`:264`).
  `rabbit_quorum_queue = true` is rendered in the `[oslo_messaging_rabbit]` section of 26 templates in 24 roles (e.g.
  `ansible/roles/nova/templates/nova.conf.j2:156-165`, `ansible/roles/nova-cell/templates/nova.conf.j2:207-216`). A
  cloud that kept the 2023.1 default therefore gets a changed service config on its first 2024.1 run. What
  oslo.messaging does with existing classic queues: [NOT AVAILABLE].
- **Precheck stricter:** "Validate rabbitmq variables" fails when HA and quorum are **equal**, i.e. also when both are
  false (2024.1 `ansible/roles/prechecks/tasks/service_checks.yml:67-72`); 2023.1 failed only when both were true
  (2023.1 `:65-71`). New check: stream fanout requires transient quorum (`:74-81`).
- **Queue-type assertions** (precheck only, tag `rabbitmq-ha-precheck`, when a `rabbitmq` container exists and quorum
  is on): every non-`reply_`/`_fanout` queue must be `quorum`; transient and stream variants
  (2024.1 `ansible/roles/rabbitmq/tasks/precheck.yml:131-189`).
- **Upgrade gate:** `upgrade.yml` now imports `version-check.yml` (2024.1 `ansible/roles/rabbitmq/tasks/upgrade.yml:2`),
  which asserts the running RabbitMQ is at most one minor version behind (3.13 → 4.0/4.1 allowed)
  (`ansible/roles/rabbitmq/tasks/version-check.yml:44-64`). kolla 2024.1 images: `docker/rabbitmq/rabbitmq` plus
  `docker/rabbitmq/rabbitmq-4-1` (2023.1 had `rabbitmq-3-12`, `rabbitmq-3-13`); `rabbitmq-upgrade.yml` selects
  `rabbitmq-<suffix>` (2024.1 `ansible/rabbitmq-upgrade.yml:18-21`). Exact image versions: re-read the Dockerfiles.
- **Still holds:** restart play `serial: "33%"` (2024.1 `ansible/rabbitmq.yml:30-49`), handlers, `restart_services.yml`.
- **Removed:** outward RabbitMQ (three plays, 2023.1 `ansible/rabbitmq.yml:60-115`; its haproxy entries, prechecks,
  `enable_outward_rabbitmq`, 2023.1 `group_vars/all.yml:632`). Data volume name now `rabbitmq_datadir_volume`
  (default `rabbitmq`, `group_vars/all.yml:913`; `roles/rabbitmq/defaults/main.yml:52`).
- `remove-ha-all-policy.yml` now uses `{{ kolla_container_engine }} exec` (2024.1 `:14,20`), which closes the 2023.1
  oddity "calls `docker exec` literally" (factsheet B line 265).
- `om_enable_queue_manager` adds `/dev/shm:/dev/shm` to several service volumes (e.g.
  `roles/nova-cell/defaults/main.yml:397,404,411,418,438`; `roles/keystone/defaults/main.yml:159`).

### X11 — service-images-pull, service-stop, service-config-validate [CODE]

- Rename-normalised diff empty for `service-images-pull`, `service-stop`, `service-config-validate`,
  `service-precheck`, `service-cert-copy`, `module-load`: same tasks and line numbers
  (e.g. `ansible/roles/service-images-pull/tasks/main.yml:14` still cited correctly), module now `kolla_container`.
- The pull now dispatches per engine (X2). `prune-images` has a Podman branch (X2).
- Exception to "pull only pulls": the common role's `config.yml` now runs `ensure_image` for fluentd (X7).

### X12 — bootstrap-servers (ansible-collection-kolla) [CODE]

- `kolla-host.yml` unchanged except `max_fail_percentage` (2024.1 `ansible/kolla-host.yml:8-11`).
- Collection `roles/baremetal/defaults/main.yml:37` `container_engine: "{{ kolla_container_engine | default('docker') }}"`;
  `roles/baremetal/tasks/install.yml:38` imports `openstack.kolla.{{ container_engine }}` and
  `roles/baremetal/tasks/post-install.yml:7` `openstack.kolla.{{ container_engine }}_sdk` (2023.1 hard-coded `docker`,
  `docker_sdk`). New collection roles `podman`, `podman_sdk`.
- `docker` role: apt repository now written as deb822 `/etc/apt/sources.list.d/docker.sources` and old `docker.list`
  removed, then cache update (collection `roles/docker/tasks/repo-Debian.yml:45-70`); new `docker_registry_mirrors`
  and `docker_debug` merged into `daemon.json` (`roles/docker/tasks/config.yml:15-16,33-34,39,46`) — daemon.json
  content changes only when set. Ceph apt key/repo for Zun likewise moved to keyring + deb822.
- `docker_sdk`: `docker>=6.0.0,<7.0.0`, `dbus-python`, and dbus build dependencies when a virtualenv is used
  (collection `roles/docker_sdk/defaults/main.yml:1-41`).
- Whether a re-run on a live host restarts Docker: re-read `roles/docker/handlers` and `tasks/config.yml` (the
  restart trigger logic of 2023.1 factsheet E §2.2).

### X13 — Removed and new services [CODE]

- **Removed roles:** `freezer`, `kafka`, `monasca`, `murano`, `sahara`, `senlin`, `solum`, `storm`, `vitrage`,
  `zookeeper` (directories absent under 2024.1 `ansible/roles/`); their `site.yml` plays and `group_by` keys
  (2023.1 `site.yml` murano `:653-663`, solum `:664-678`, etc.), inventory groups (2024.1 `ansible/inventory/multinode`
  lost `kafka`, `outward-rabbitmq`, `monasca*`, `storm`, `freezer*`, `murano`, `solum`, `sahara`, `senlin`, `vitrage`,
  `zookeeper`), `enable_*` flags (2023.1 `group_vars/all.yml:666,715,744,745,747,756`), Horizon plugin entries
  (2024.1 `roles/horizon/tasks/config.yml:24-41`), logrotate/fluentd entries (X7). kolla removes the matching images
  (`docker/freezer`, `murano`, `sahara`, `senlin`, `solum`, `vitrage`) and `prometheus-haproxy-exporter`,
  `openvswitch-netcontrold`.
- **Removed container:** `prometheus_haproxy_exporter` (play host group gone, 2024.1 `ansible/site.yml:416-437`;
  removed during loadbalancer upgrade, X8).
- **New:** `letsencrypt` role/play/group (`inventory/multinode` `[letsencrypt:children] loadbalancer`), `haproxy-ssh`,
  `ironic-prometheus-exporter` (`enable_ironic_prometheus_exporter`, `group_vars/all.yml`), neutron FWaaS
  (`roles/neutron/tasks/config.yml:327-347`) and TaaS (`:526-547`), Skyline split into apiserver/console FQDNs and
  ports, fluentd systemd input, Octavia jobboard (`enable_octavia_jobboard` default true with the amphora driver,
  `group_vars/all.yml:832`) whose precheck **requires `enable_redis`** (default `no`, `:840`;
  `roles/octavia/tasks/precheck.yml:67-73`), and an Octavia persistence DB created in `upgrade.yml`
  (`roles/octavia/tasks/upgrade.yml:7-40`). `inventory/multinode` adds `network` to `tls-backend`.
- `generated-inventory.md`, the component index cards and the tag index need regeneration from the 2024.1 tree.

### X14 — New defaults in `group_vars/all.yml` that change rendered config [CODE]

- `openstack_previous_release_name: "2023.2"` (2024.1 `:688`; 2023.1 `"zed"`, `:587`): the upgrade path is SLURP
  2023.1 → 2024.1.
- Keystone: `keystone_admin_port`/`keystone_admin_listen_port` (2023.1 `:375-376`), `keystone_admin_url` (2023.1
  `:864`) and `admin_protocol` (2023.1 `:567`) removed; new `keystone_internal_port: "5000"` (2024.1 `:446`);
  `keystone_public_port` follows the single-frontend option (`:444`); URLs built with the new `kolla_url` filter
  (`:960-961`; `ansible/filter_plugins/address.py:18,28`; `kolla_ansible/kolla_url.py`). The `keystone_admin` HAProxy
  entry "kept only for upgrade" and the admin-endpoint removal in `keystone/tasks/upgrade.yml` (2023.1
  `roles/keystone/defaults/main.yml:30-40`, `roles/keystone/tasks/upgrade.yml:52-59`) are gone; the `admin` endpoint
  entry with `state: absent` is gone from `keystone_service_endpoints` (2024.1 `roles/keystone/defaults/main.yml:200-202`),
  and `service-ks-register` no longer supports `state` (2024.1 `roles/service-ks-register/tasks/main.yml:24-45`);
  `service_ks_register_roles` still exists (`roles/service-ks-register/defaults/main.yml:29`, used at
  `tasks/main.yml:97`; corrected on review), only the keystone role stopped passing it; role assignments accept
  `domain`/`system` (`:103-112`).
- Every `<svc>_internal_endpoint`/`_public_endpoint` uses `kolla_url` and `<svc>_public_port` (`:332-665`, `:1015-1334`).
- Debian base `bookworm`, python `3.11` (2024.1 `:1262,1269`).
- Ceph keyrings now `client.<user>.keyring` (2024.1 `:1182-1186`; 2023.1 `ceph.client.<user>.keyring`) — see X18.
- `designate_enable_notifications_sink: "no"` (was `enable_designate`); `horizon_backend_database: false`;
  `glance_backend_s3` (with S3 precheck, `roles/glance/tasks/precheck.yml:28-38`); `docker_zun_config: {}`;
  `redis_connection_string` user `default`; `haproxy_enable_http2: "yes"` (`:920`).

### X15 — kolla images, `config_strategy`, `kolla_set_configs` [CODE]

- **Still holds:** kolla `docker/base/set_configs.py` and `docker/base/start.sh` are byte-identical between the two
  tags, so `kolla_set_configs` (incl. `--check`, F14) and the start path are unchanged; base `ENTRYPOINT
  ["dumb-init", "--single-child", "--"]` and `CMD ["kolla_start"]` (2024.1 `docker/base/Dockerfile.j2:370,399`).
  `config_strategy: "COPY_ALWAYS"` (`group_vars/all.yml:43`, both) and `KOLLA_CONFIG_STRATEGY` in
  `docker_common_options` (2024.1 `:147-148`).
- **Changed start scripts (Day-2 relevant):** `openvswitch-db-server/extend_start.sh:8-10` runs `ovsdb-tool convert`
  when `needs-conversion` says yes (new: schema conversion at container start); OVS/OVN images create and chown their
  log files (`openvswitch-vswitchd/extend_start.sh:3-6`, `ovn-controller/extend_start.sh`, sourced via `ovn-base/extend_start.sh:13`);
  fluentd `extend_start.sh` always uses `fluentd:kolla` (2024.1 `:12-19`); keepalived `check_alive.sh` legacy branch
  removed (X8); kolla-toolbox `kolla_toolbox.sh` (X7); mariadb upgrade log (X9). `openvswitch-base` ships
  `/usr/local/bin/ovs_wrapper` (`Dockerfile.j2:36,42`) but no kolla-ansible template uses it (grep of
  `ansible/` finds none) → not on the Day-2 path.
- Open vSwitch bridge setup no longer calls the image script `kolla_ensure_openvswitch_configured` (2023.1
  `roles/openvswitch/tasks/post-config.yml:24-34`) but the `openvswitch_bridge` (fail_mode standalone) and
  `openvswitch_port` modules through `kolla_toolbox` (2024.1 `:25-53`); new `external_ids:hostname` =
  `ansible_facts.fqdn` (`:18`; `defaults/main.yml:106`). The script still ships in the image
  (kolla `docker/openvswitch/openvswitch-db-server/Dockerfile.j2:8`).
- `docker/base` repo files: RabbitMQ Erlang 26/27 copr repos; Ubuntu jammy and noble source lists; CentOS caracal
  and Ceph reef release packages.

### X16 — ansible-core 2.14 → 2.16 [CODE for 2.16 only]

- Only 2.16.20 is on disk; nothing can be said about what changed in ansible-core itself from code. Every
  statement that cites ansible-core 2.14.18 (`lib/ansible/...`) must be re-read in 2.16.20 (F1 loop-notify, F7
  listings, F9 `--limit` facts, F10 `run_once` with `serial`, tag inheritance, handler semantics). The playbook
  batch-failure rule is at the same lines in 2.16.20 (`playbook_executor.py:204-208,219-220`).
- The Ansible listings (`reference/listings/`) are 2.14.18 output and must be regenerated with 2.16.20 on the 2024.1
  tree.
- ansible-core 2.15 behaviour (still accepted by the CLI) is [NOT AVAILABLE].

### X17 — Nova specifics [CODE]

- Roles `nova`/`nova-cell` changes: `/run` and `devpts` mounts for Podman, `/dev/shm` with queue manager (X2/X10),
  `nova_ceph_cluster` (`roles/nova-cell/defaults/main.yml:536`), console URLs via `kolla_url`
  (`roles/nova-cell/templates/nova.conf.j2:57,69,82`), `use_queue_manager` (`:193-198`), `discover_hosts` with
  `exec -t` (`roles/nova-cell/tasks/discover_computes.yml:17`), `remove_volume`/`stop_and_remove_container` get
  `container_engine`/`common_options` (`post-config.yml:6`, `libvirt-cleanup.yml:40,48`). `reload.yml` and handlers
  unchanged apart from comments / nova-compute-fake. New `any_errors_fatal` on the API online-migration play (X5).

### X18 — External Ceph: multi-cluster layout [CODE]

- `cinder`, `glance`, `nova-cell`, `manila`, `gnocchi`, `zun` `external_ceph.yml` changed: per-service `ceph/`
  sub-directory and one `<cluster>.conf` per backend (e.g. 2024.1 `ansible/roles/cinder/tasks/external_ceph.yml:2-42`,
  `cinder_ceph_backends` with `cluster: "ceph"` at `roles/cinder/defaults/main.yml:270-273`); keyrings named
  `<cluster>.client.<user>.keyring`. Operator source files in `/etc/kolla/config/<svc>/` keep the `ceph.conf` /
  `ceph.client.<user>.keyring` names for the default cluster `ceph`, but the destination inside the service config
  directory moves → `kolla_set_configs` copies differ → restart on first run (config.json content to re-read per role).
- Horizon (not Ceph, same kind of override-path change): `local_settings` → `_9998-kolla-settings.py` and
  `custom_local_settings` → `_9999-custom-settings.py`, both looked up with `with_first_found` (2024.1
  `ansible/roles/horizon/tasks/config.yml:75-104`; 2023.1 `:80-115`): an override at the old file name is no longer
  picked up.

## 2. Impact on the 2023.1 pages

69 pages (`find docs/2023.1 -name '*.md'`). "Cited lines" counts the `path:line` citations of the page that resolve
in the 2023.1 trees (kolla-ansible root or `ansible/`, kolla, collection), compared with the same path in 2024.1
after the module rename: **same** = identical text at the same lines; **moved** = the cited text exists elsewhere in
the 2024.1 file; **changed** = cited text not found verbatim (edited, removed, or file gone). Citations that are
relative to a role directory (common in the fact sheets) or to ansible-core do not resolve and are not counted;
`lib/ansible` citations (ansible-core 2.14.18) always need a re-read (X16). Rework: light = mostly line numbers and
the release name; medium = some statements change; heavy = sections must be rewritten.

| Page | Cross-cutting changes | Cited lines same / moved / changed | Rework | Notes |
|---|---|---|---|---|
| `components/barbican.md` | X2, X14 | 3 / 8 / 1 | light | endpoints via `kolla_url`/`public_port` |
| `components/chrony.md` | X7, X13 | 8 / 3 / 3 | light | still no chrony role in 2024.1 (`ansible/roles/` has none) |
| `components/cinder.md` | X2, X10, X14, X18 | 8 / 10 / 9 | medium | multi-cluster Ceph, `hostnqn` file (2024.1 `roles/cinder/tasks/config.yml:95-108`) |
| `components/common.md` | X2, X4, X7, X11, X15, X16 | 3 / 2 / 4 | heavy | fluentd `ensure_image`+labels in config, toolbox command, journal mount |
| `components/dependencies.md` | X8, X10, X13, X14, X18 | 15 / 24 / 21 | heavy | keystone admin URL gone; letsencrypt; octavia→redis; quorum defaults |
| `components/glance.md` | X2, X14, X18 | 4 / 1 / 6 | medium | S3 backend + precheck; Ceph layout |
| `components/haproxy-keepalived.md` | X5, X8, X15 | 5 / 8 / 5 | heavy | haproxy-ssh, single frontend, threads rename, new volume, check_alive |
| `components/heat.md` | X2, X14 | 6 / 1 / 4 | light | |
| `components/horizon.md` | X13, X18 | 1 / 3 / 3 | medium | `local_settings.j2` gone → `_9998`/`_9999` files; plugins removed |
| `components/index.md` | X13 | 0 / 1 / 3 | light | regenerate service cards; removed services |
| `components/iscsi.md` | X2 | 2 / 5 / 3 | light | Podman `/run` sub-mounts |
| `components/keystone.md` | X10, X14 | 5 / 4 / 2 | medium | admin port/endpoint code removed; `kolla_url`; `/dev/shm` |
| `components/manila.md` | X2, X18 | 7 / 2 / 4 | medium | Ceph layout |
| `components/mariadb.md` | X2, X5, X9 | 5 / 2 / 3 | medium | "no max_fail_percentage" no longer holds; recovery path var |
| `components/memcached.md` | X5 | 1 / 4 / 2 | light | role unchanged; cites removed `horizon/templates/local_settings.j2` |
| `components/neutron.md` | X2, X10, X13 | 5 / 2 / 3 | medium | sysctl role, FWaaS/TaaS files, handlers unchanged |
| `components/nova-deep-dive.md` | X2, X4, X5, X10, X17, X18 | 42 / 26 / 30 | heavy | largest component page; new `any_errors_fatal`; libvirt volumes |
| `components/nova.md` | X5, X17 | 0 / 0 / 2 | medium | play table (`nova.yml` lines shift, new fatal flag) |
| `components/octavia.md` | X1, X13 | 6 / 4 / 2 | medium | jobboard + redis precheck; persistence DB in upgrade; `--check-expiry` |
| `components/openvswitch.md` | X2, X15 | 5 / 1 / 3 | heavy | bridge/port setup via `kolla_toolbox` modules; ovsdb convert at start; hostname id |
| `components/ovn.md` | X15 | 4 / 2 / 2 | light | `ovn-db` bootstrap retries (`roles/ovn-db/tasks/bootstrap-db.yml:22-55`); extend_start logs |
| `components/placement.md` | X14 | 5 / 5 / 0 | light | error log file name, public port |
| `components/rabbitmq.md` | X5, X10, X13 | 7 / 2 / 9 | heavy | quorum default, precheck, version-check, outward removed |
| `components/swift.md` | X2 | 8 / 5 / 3 | light | |
| `concepts/compute-scaling-and-performance.md` | X2, X4, X5, X16 | 24 / 20 / 22 | medium | counts from code; ansible-core 2.16 re-read |
| `concepts/deployment-execution-flow.md` | X5, X7, X8, X13, X16 | 55 / 22 / 27 | heavy | play list (letsencrypt, removed plays, etcd serial), mermaid diagrams |
| `concepts/index.md` | – | – | light | |
| `concepts/kolla-images.md` | X2, X7, X15 | 155 / 62 / 39 | medium | `set_configs.py`/`start.sh` identical; toolbox signals; OVS/OVN start scripts |
| `concepts/repository-architecture.md` | X1, X2, X3, X4, X12, X13, X16 | 36 / 29 / 22 | heavy | "Docker only" no longer holds; module/worker table; counts |
| `index.md` | X1 | 0 / 0 / 2 | light | release identity |
| `operations/add-a-compute-node.md` | X2, X5, X12 | 7 / 1 / 4 | medium | bootstrap-servers engine roles; discover_hosts |
| `operations/apply-common-changes.md` | X4, X7, X11 | 5 / 5 / 12 | heavy | common config now pulls/inspects fluentd image |
| `operations/change-control-plane-membership.md` | X6, X9, X10 | 7 / 4 / 1 | medium | etcd membership handlers rewritten; rabbitmq/mariadb restart unchanged |
| `operations/command-quick-lookup.md` | X1, X8, X13 | 2 / 0 / 5 | medium | `monasca_cleanup` gone, `--check-expiry`, letsencrypt tag |
| `operations/controlled-batches.md` | X5, X16 | 7 / 5 / 3 | heavy | `max_fail_percentage` everywhere; etcd without `serial` |
| `operations/database-operations.md` | X1, X9 | 2 / 3 / 3 | medium | mariabackup schema/privileges; new kolla backup script |
| `operations/index.md` | X1 | 0 / 3 / 2 | light | |
| `operations/pre-execution-checklist.md` | X1, X5, X10 | 2 / 2 / 1 | medium | ansible-core range; RabbitMQ HA/quorum precheck |
| `operations/predict-a-run.md` | X2, X7, X16 | 3 / 5 / 3 | medium | genconfig can pull fluentd image; listings regenerated |
| `operations/reconfigure-a-service.md` | X2, X4, X7, X8 | 10 / 5 / 12 | medium | haproxy-config single frontend task; unit-file transition |
| `operations/reconfigure-neutron.md` | X2, X13 | 5 / 4 / 2 | light | handlers unchanged; new optional config files |
| `operations/reconfigure-nova.md` | X5, X10, X17 | 6 / 12 / 8 | medium | quorum/queue-manager config; play list |
| `operations/stop-and-destroy.md` | X1, X2 | 3 / 4 / 0 | light | destroy inventories; cleanup scripts disable units |
| `operations/update-container-images.md` | X2, X4, X11 | 19 / 13 / 7 | medium | pull unchanged; Podman paths; prune Podman branch |
| `reference/factsheets/a-infra-lb-ovn.md` | X2, X5, X7, X8, X15 | 81 / 60 / 35 | heavy | common, loadbalancer, OVS/OVN sections |
| `reference/factsheets/b-mariadb-rabbitmq-keystone.md` | X5, X9, X10, X14 | 44 / 36 / 63 | heavy | outward RabbitMQ, quorum, keystone admin entries |
| `reference/factsheets/c-glance-placement-cinder-horizon-heat.md` | X14, X18 | 42 / 27 / 32 | heavy | Ceph layout, Horizon settings files, S3 |
| `reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md` | X1, X13, X18 | 29 / 37 / 35 | heavy | cites `monasca_cleanup.yml` and `roles/monasca/tasks/cleanup.yml` (gone); Octavia jobboard |
| `reference/factsheets/e-host-bootstrap-ops-playbooks.md` | X1, X5, X9, X12, X13 | 38 / 27 / 28 | heavy | collection engine roles, deb822 repos, destroy, prune, mariabackup |
| `reference/factsheets/index.md` | X13 | 17 / 7 / 13 | medium | role list |
| `reference/findings.md` | X2, X3, X4, X15, X16 | 29 / 9 / 17 | medium | F1/F7/F9/F10 re-read in 2.16; F3/R24 unit template; F14 unchanged code |
| `reference/generated-inventory.md` | X13, X14 | n/a (no line cites) | heavy | regenerate with `tools/extract_kolla_inventory.py`; cites 7 removed templates |
| `reference/glossary.md` | X2 | 1 / 0 / 1 | light | `kolla_docker` → `kolla_container` terms |
| `reference/index.md` | – | – | light | |
| `reference/listings/index.md` | X16 | 0 / 2 / 0 | medium | regenerate with ansible-core 2.16.20 |
| `reference/method-and-limits.md` | X1, X2, X16 | 1 / 0 / 3 | medium | sources table; "Docker only" statement; phases 3 and 7 |
| `risk/index.md` | – | – | light | |
| `risk/risk-register.md` | X1, X2, X4, X5, X7, X8, X9, X10, X12, X13 | 49 / 25 / 40 | heavy | R2, R3, R8, R9, R10, R14, R16, R17, R24 touched |
| `risk/small-change-large-workload.md` | X2, X4 | 4 / 6 / 2 | light | |
| `risk/tag-index.md` | X13 | 0 / 0 / 2 | light | tags of removed services |
| `risk/tags.md` | X5, X7, X8, X13, X16 | 38 / 27 / 35 | heavy | tag → play mapping, `-t common`, `--list-tasks` |
| `start/conventions.md` | – | 2 / 0 / 0 | light | |
| `start/find-it-fast.md` | – | – | light | links only |
| `start/learning-journey.md` | – | – | light | |
| `start/ten-things-to-know.md` | X5, X10 | – | medium | the "ten things" include batching and RabbitMQ |
| `troubleshooting/index.md` | X2, X5, X7, X8, X9, X10, X13 | 89 / 41 / 40 | heavy | largest troubleshooting page |
| `troubleshooting/known-bugs-and-limitations.md` | X2, X3, X5, X10 | 47 / 10 / 22 | medium | |
| `troubleshooting/open-questions.md` | X15, X16 | 4 / 0 / 4 | medium | Q-items on signals (toolbox trap), ansible-core |
| `troubleshooting/what-is-not-known.md` | X10 | 0 / 1 / 0 | light | |

Files cited by 2023.1 pages that no longer exist in 2024.1: `ansible/roles/horizon/templates/local_settings.j2`
(horizon, memcached, factsheet A, factsheet index, generated inventory), `ansible/monasca_cleanup.yml` and
`ansible/roles/monasca/tasks/cleanup.yml` (factsheet D), the freezer/murano/sahara/senlin/solum/vitrage templates
(generated inventory), and every citation of `library/kolla_docker.py` (now `kolla_container.py`).

## 3. Suggested lots for the re-study

Foundational pages first, because the others link to and reuse their statements.

1. **Lot 1 — Method and foundations:** `reference/method-and-limits.md`, `concepts/repository-architecture.md`
   (X1, X2, X3, X4), `reference/glossary.md`, `start/conventions.md`. Decide here how Podman is scoped (Docker
   remains the default; Podman paths described from code only, behaviour [NOT AVAILABLE]).
2. **Lot 2 — Regenerated material:** `reference/listings/index.md` (ansible-core 2.16.20 listings),
   `reference/generated-inventory.md`, component service cards / `components/index.md`, `risk/tag-index.md`
   (tools, not hand edits).
3. **Lot 3 — Execution model:** `concepts/deployment-execution-flow.md`, `risk/tags.md`,
   `operations/controlled-batches.md`, `concepts/compute-scaling-and-performance.md`, `reference/findings.md`
   (X5, X6, X16; F1/F7/F9/F10 re-read in 2.16.20).
4. **Lot 4 — Images and start path:** `concepts/kolla-images.md`, `troubleshooting/open-questions.md` (X15; signals of
   the new toolbox script).
5. **Lot 5 — Shared infrastructure:** `components/common.md`, `operations/apply-common-changes.md`,
   `components/haproxy-keepalived.md`, `reference/factsheets/a-infra-lb-ovn.md`, `components/openvswitch.md`,
   `components/ovn.md`, `components/chrony.md`, `components/iscsi.md`, `components/memcached.md` (X7, X8, X15).
6. **Lot 6 — Stateful services:** `components/rabbitmq.md`, `components/mariadb.md`, `operations/database-operations.md`,
   `operations/change-control-plane-membership.md`, `components/keystone.md`,
   `reference/factsheets/b-mariadb-rabbitmq-keystone.md` (X9, X10, X14, etcd X6).
7. **Lot 7 — Nova and Neutron:** `components/nova-deep-dive.md`, `components/nova.md`, `operations/reconfigure-nova.md`,
   `components/neutron.md`, `operations/reconfigure-neutron.md`, `operations/add-a-compute-node.md` (X17, X10, X12).
8. **Lot 8 — Other services:** `components/cinder.md`, `glance.md`, `manila.md`, `horizon.md`, `octavia.md`,
   `placement.md`, `heat.md`, `barbican.md`, `swift.md`, `reference/factsheets/c-…md`, `reference/factsheets/d-…md`,
   `reference/factsheets/index.md`, `components/dependencies.md` (X13, X14, X18).
9. **Lot 9 — Host and ops playbooks:** `reference/factsheets/e-host-bootstrap-ops-playbooks.md`,
   `operations/update-container-images.md`, `operations/stop-and-destroy.md`, `operations/predict-a-run.md`,
   `operations/reconfigure-a-service.md`, `operations/pre-execution-checklist.md`, `operations/command-quick-lookup.md`
   (X1, X11, X12).
10. **Lot 10 — Synthesis pages (last):** `risk/risk-register.md`, `risk/small-change-large-workload.md`,
    `troubleshooting/index.md`, `troubleshooting/known-bugs-and-limitations.md`,
    `troubleshooting/what-is-not-known.md`, `start/ten-things-to-know.md`, `start/learning-journey.md`,
    `start/find-it-fast.md`, `operations/index.md`, `concepts/index.md`, `components/index.md` (text),
    `reference/index.md`, `risk/index.md`, `index.md`.
