# Fact sheet C: glance, placement, cinder, horizon, heat (Kolla-Ansible `ussuri-eol`)

All paths are relative to the repo root (`$SRC`). Unless marked otherwise, every claim comes from reading the code at the tag `ussuri-eol`.
- **HYPOTHESIS**: an inference from code plus general/upstream OpenStack behaviour. The code in this repo does not prove it.
- **NEEDS-LAB**: has to be confirmed by running it.

Behaviour inside the images (what `KOLLA_BOOTSTRAP`, `KOLLA_UPGRADE`, `KOLLA_OSM`, `GLANCE_DB_EXPAND` and similar variables actually run) is defined in the separate `kolla` images repo. That repo is **not** in this checkout, but its `ussuri-eol` tag was read separately (see [annex/kolla-images.md](../kolla-images.md)). A statement that cites a kolla path, written as kolla `docker/...` (for example kolla `docker/glance/glance-api/extend_start.sh` or kolla `docker/base/set_configs.py`), is read from that source like any other code claim. Any description of image-side behaviour without such a citation remains a HYPOTHESIS.

---

## 0. Cross-cutting facts (apply to all five roles)

| Topic | Fact | Evidence |
|---|---|---|
| Task dispatch | Every role's `tasks/main.yml` is `- include_tasks: "{{ kolla_action }}.yml"`. | e.g. `ansible/roles/glance/tasks/main.yml:2` (identical in placement/cinder/horizon/heat) |
| `reconfigure` | `reconfigure.yml` is just `- import_tasks: deploy.yml` in **all five** roles, so reconfigure performs keystone registration, DB create/grant and **the bootstrap (db sync) container**, exactly as deploy does. | `ansible/roles/{glance,placement,cinder,horizon,heat}/tasks/reconfigure.yml:2` |
| `common` | Each role has `meta/main.yml` → `dependencies: - { role: common }`. | e.g. `ansible/roles/heat/meta/main.yml:2-3` |
| Serial | Every play uses `serial: '{{ kolla_serial|default("0") }}'`. The CLI passes `kolla_serial=${ANSIBLE_SERIAL}` (default `0`) only for `upgrade` and `reconfigure`. | `ansible/site.yml:662,691,702,800,811`; `tools/kolla-ansible:236,430,439` |
| run_once + serial | Bootstrap, DB and keystone tasks are `run_once: True`. When `kolla_serial` > 0, Ansible runs `run_once` tasks **once per batch**. So db sync and keystone registration repeat for each batch. HYPOTHESIS (standard Ansible semantics); this matters for glance rolling upgrade (§1.8). | e.g. `ansible/roles/cinder/tasks/bootstrap_service.yml:19-20` |
| Bootstrap container | `kolla_docker action=start_container, detach: False`. The module waits for exit and then removes the container (`remove_on_exit` defaults to True). Nothing guards it with "already bootstrapped", so it **runs on every deploy/reconfigure**. | `ansible/library/kolla_docker.py:805-845,837-839,992` |
| Restart semantics | Handlers use `recreate_or_restart_container`. The stop timeout is `graceful_timeout`, default **10 s**, and no role here overrides it. Docker sends SIGTERM, then SIGKILL if the container is still running after 10 s. | `ansible/library/kolla_docker.py:781-803,873-875,894-904,991` |
| Handler skip | All handlers have `when: kolla_action != "config"`, so `genconfig` never restarts anything. | e.g. `ansible/roles/cinder/handlers/main.yml:14-15` |
| Network | All containers run with `network_mode: host`, so the container hostname is the node hostname (this matters for cinder `host`). | `ansible/library/kolla_docker.py:719` |
| Empty volume strings | Volume lists contain `''` entries (timezone, dev-mode). `generate_volumes` skips empty entries, so the places that pass lists without `reject('equalto','')` (placement/cinder upgrade OSM, horizon) are harmless. | `ansible/library/kolla_docker.py:659-661` |
| Shared endpoints | `database_address: "{{ kolla_internal_fqdn }}"` (DB is reached through the VIP). `rpc_transport_url` / `notify_transport_url` enumerate **every** host in the rabbit groups. | `ansible/group_vars/all.yml:105,206,216` |
| memcached | Every service template (glance, placement, cinder, heat, horizon) enumerates **all** `groups['memcached']` hosts. Adding or removing a memcached or rabbitmq node therefore changes the config of all five services, and they restart on the next deploy/reconfigure. | e.g. `ansible/roles/heat/templates/heat.conf.j2:60,66` |
| Workers | `openstack_service_workers: "{{ [ansible_facts.processor_vcpus, 5]|min }}"`. The value is per host. | `ansible/group_vars/all.yml:550` |
| Sanity checks | `kolla_enable_sanity_checks: "no"`, so glance/cinder `check.yml` are no-ops by default. | `ansible/group_vars/all.yml:56,60-61` |
| HAProxy | Each role's `loadbalancer.yml` is applied from the **haproxy play** (`site.yml:126-392`), which only runs for `kolla_action in ['deploy','reconfigure','upgrade','config']`. | `ansible/site.yml:390-392` |
| TLS backend certs | `service-cert-copy` copies `<project>-cert.pem`/`-key.pem` into a service's config dir only when one of its haproxy entries has `tls_backend` true. It notifies the container restart. | `ansible/roles/service-cert-copy/tasks/main.yml:14-54` |
| Service-to-host mapping | `host_in_groups` (used only by glance) takes precedence over `group` in the filter `select_services_enabled_and_mapped_to_host`. That filter drives pull/stop/cert-copy. | `kolla_ansible/filters.py:42-66,82-91` |
| Ansible forks | No `ansible.cfg` ships in the repo, so "all hosts restart together" really means up to `forks` hosts at once (Ansible default 5). HYPOTHESIS: depends on the operator's config. | `find . -name ansible.cfg` → none |

### site.yml order (relevant slice)
`haproxy` play (126) → … → **glance** (657) → ironic (668) → **cinder** (683) → **placement** (697) → `import_playbook: nova.yml` (710) → … → **heat** (793) → **horizon** (806). Placement is therefore (re)deployed before nova, and glance before cinder.

---

## 1. GLANCE

### 1.1 Play
```yaml
# ansible/site.yml:657-666
- name: Apply role glance
  hosts:
    - glance-api
    - '&enable_glance_True'
  serial: '{{ kolla_serial|default("0") }}'
  roles:
    - { role: glance, tags: glance, when: enable_glance | bool }
```
- The LB include is at `ansible/site.yml:189-193` (tag `glance`, `when: enable_glance`).
- `enable_glance: "{{ enable_openstack_core | bool }}"` (`ansible/group_vars/all.yml:573`).

### 1.2 `glance_services` (`ansible/roles/glance/defaults/main.yml:2-64`)
| key | container | group / mapping | enabled | flags |
|---|---|---|---|---|
| glance-api | `glance_api` | `group: glance-api`, **`host_in_groups: inventory_hostname in glance_api_hosts`** (:6) | `true` | `privileged: enable_cinder and enable_cinder_backend_iscsi` (:10); `environment: container_proxy` (:9). This is the only service in scope that receives http(s)_proxy. Volumes (:131-140): `glance_file_datadir_volume:/var/lib/glance/` (default named volume `glance`), and **`iscsi_info:/etc/iscsi` plus `/dev:/dev` when cinder iSCSI is enabled** (:138-140). |
| glance-tls-proxy | `glance_tls_proxy` | same `host_in_groups` (:37) | `glance_enable_tls_backend` (= `kolla_enable_tls_backend`, `all.yml:871`) | HAProxy image (`...-haproxy`, :124-126). It listens on `api_interface_address:9292` with TLS and forwards to glance-api on `127.0.0.1:9292` (`templates/glance-tls-proxy.cfg.j2:32-37`; glance-api `bind_host = 127.0.0.1` when TLS, `templates/glance-api.conf.j2:8-12`). |

**Critical mapping rule:**
```yaml
# ansible/group_vars/all.yml:862,866-869
glance_backend_file: "{{ not (glance_backend_ceph | bool or glance_backend_swift | bool or glance_backend_vmware | bool) }}"
glance_backend_swift: "{{ enable_swift | bool }}"
glance_file_datadir_volume: "glance"
glance_api_hosts: "{{ [groups['glance-api']|first] if glance_backend_file | bool and glance_file_datadir_volume == 'glance' else groups['glance-api'] }}"
```
With the default file backend on a local named volume, glance-api runs **only on the first host of `glance-api`**. HAProxy members are built from `glance_api_hosts` too (`defaults/main.yml:69-70`), so glance has **no HA**. A glance-api restart is a full Image API outage. The docs confirm this: "By default when using file backend only one glance-api container can be running" (`doc/source/reference/shared-services/glance-guide.rst:27`).

HAProxy: client and server timeouts are **6h** (`defaults/main.yml:110-111`). In TLS mode the HAProxy members always get `ssl verify required ca-file ...` and **ignore `kolla_verify_tls_backend`** (`defaults/main.yml:70`). Other services honour it in `haproxy-config/templates/haproxy_single_service_split.cfg.j2:83-89`.

### 1.3 Task flow per action
| action | flow |
|---|---|
| deploy / reconfigure | `deploy.yml`: `register.yml` → `config.yml` → `check-containers.yml` → (`clone.yml` if dev) → `bootstrap.yml` → `meta: flush_handlers` → `check.yml` (`tasks/deploy.yml:1-17`; `reconfigure.yml:2`) |
| upgrade | `upgrade.yml:1-6`: `rolling_upgrade.yml` if `glance_enable_rolling_upgrade` (default `no`, `all.yml:868`), else `legacy_upgrade.yml`. **No `register.yml`** in either path, so endpoints are not refreshed on upgrade. |
| legacy upgrade | `config.yml` → `check-containers.yml` → `bootstrap_service.yml` (db sync, new image) → flush (`tasks/legacy_upgrade.yml:1-9`). It does **not** stop glance-api first. The docs claim "This upgrade method will stop APIs during database schema migrations" (`glance-guide.rst:115`), but the code does not do that: the old glance-api keeps serving while the new-image bootstrap migrates the schema. |
| rolling upgrade | see §1.8 |
| deploy-containers | `check-containers.yml` only, then handlers (`tasks/deploy-containers.yml:2`) |
| pull | `service-images-pull`. Only hosts where `host_in_groups` is true pull (`roles/service-images-pull/tasks/main.yml:14`). |
| stop | `service-stop` with `glance_services` (`tasks/stop.yml:2-6`) |
| precheck | `service-precheck` (groups exist) plus a free-port check on 9292 when glance_api is not running (`tasks/precheck.yml:1-24`) |
| check | `check.yml`: create/delete a `glance_sanity_check` image, delegated to `groups['glance-api'][0]`, only if `kolla_enable_sanity_glance` (`tasks/check.yml:1-32`). This file **also runs at the end of every deploy/reconfigure** (`deploy.yml:17`). |
| config | `config.yml` only. Handlers are notified but skipped. |

### 1.4 Config files (`ansible/roles/glance/tasks/config.yml`)
| dest (under `/etc/kolla/`) | source / merge order | when | notifies |
|---|---|---|---|
| `glance-api/` and `glance-tls-proxy/` dirs | `file` | enabled and mapped (:2-13) | – |
| `glance-api/ceph.conf` | `template: {{node_custom_config}}/glance/ceph.conf` (a single file, no merge) | `glance_backend_ceph` (`config.yml:15-17`; `external_ceph.yml:2-10`) | Restart glance-api |
| `glance-api/<ceph_glance_keyring>` | `copy {{node_custom_config}}/glance/ceph.client.glance.keyring` | ceph (`external_ceph.yml:12-20`) | Restart glance-api |
| policy file | first found of `supported_policy_format_list` in `{{node_custom_config}}/glance/` (:19-36, :126-139) | if found | Restart glance-api |
| CA/TLS certs | `copy-certs.yml` → service-cert-copy (:38-40) | `kolla_copy_ca_into_containers or glance_enable_tls_backend` | Restart <svc> |
| `glance-tls-proxy/glance-cert-and-key.pem` | `assemble` of `glance-(cert|key).pem` (:42-54) | TLS proxy enabled | **no notify** (the cert copy notifies instead) |
| `<svc>/config.json` | `glance-api.json.j2`, `glance-tls-proxy.json.j2` (:56-67) | – | Restart <svc> |
| `glance-api/glance-api.conf` | merge: `templates/glance-api.conf.j2` → `global.conf` → `glance.conf` → `glance/glance-api.conf` → `glance/<host>/glance-api.conf` (:69-86) | – | Restart glance-api |
| `glance-api/glance-cache.conf` | merge: template → `glance-cache.conf` → `glance/glance-cache.conf` → `glance/<host>/glance-cache.conf` (:88-105). Note that **no `global.conf`** is in this merge. | `enable_glance_image_cache` | Restart glance-api |
| `glance-api/glance-swift.conf` | merge: template → `glance-swift.conf` → `glance/glance-swift.conf` → `glance/<host>/...` (:107-124) | `glance_backend_swift` | Restart glance-api |
| `glance-tls-proxy/glance-tls-proxy.cfg` | first_found: `glance/<host>/glance-tls-proxy.cfg` → `glance/glance-tls-proxy.cfg` → role template (:141-157) | TLS proxy | Restart glance-tls-proxy |

`glance-api.json.j2:41-52` has `"permissions": [{"path": "/var/lib/glance", "owner": "glance:glance", "recurse": true}]`. `/var/lib/glance` is the `glance_file_datadir_volume` mount (`defaults/main.yml:135`), which with the file backend is the **entire image store** (`filesystem_store_datadir = /var/lib/glance/images/`, `templates/glance-api.conf.j2:71`). kolla_set_configs walks it and calls `os.chown` on every directory and file, unconditionally (kolla `docker/base/set_configs.py:353-363,378-385`). It does this at every container start under the default `COPY_ALWAYS` (kolla `docker/base/start.sh:8`, `set_configs.py:391-393`; `ansible/group_vars/all.yml:43`), and only on a container's first start under `COPY_ONCE` (kolla `set_configs.py:394-402`); see [annex/kolla-images.md §2](../kolla-images.md). HYPOTHESIS: with a big NFS-backed `glance_file_datadir_volume` this could make starts slow (NEEDS-LAB).

### 1.5 Handlers (`ansible/roles/glance/handlers/main.yml`)
- `Restart glance-api container` (:2-17): recreate_or_restart. It passes `privileged`, `environment` (the proxy), volumes and dimensions.
- `Restart glance-tls-proxy container` (:19-32): recreate_or_restart.
- Neither has special logic beyond `kolla_action != "config"`. There is no rolling restart and no wait for the API to come back.

### 1.6 Bootstrap
| step | where | re-runs on reconfigure? |
|---|---|---|
| `mysql_db glance` | `tasks/bootstrap.yml:2-15`, run_once, delegate `groups['glance-api'][0]`, unless `use_preconfigured_databases` | yes (idempotent) |
| `mysql_user glance` with password and `ALL` on `glance.*` | `bootstrap.yml:17-34` | yes. HYPOTHESIS: the mysql_user module re-asserts the password each run. |
| **Set GLOBAL `log_bin_trust_function_creators=1`** | `bootstrap_service.yml:2-16`, uses DB root creds | **yes, on every deploy/reconfigure** |
| `bootstrap_glance` container, `KOLLA_BOOTSTRAP`: `glance-manage db_sync` then `glance-manage db_load_metadefs` (kolla `docker/glance/glance-api/extend_start.sh:5-9`) | `bootstrap_service.yml:18-36`, delegate `glance_api_hosts[0]` | **yes, so a schema sync runs on every reconfigure** |
| Set `log_bin_trust_function_creators=0` | `bootstrap_service.yml:38-52` | yes |
| Keystone: service `glance`/`image`, 3 endpoints, user `glance` (admin in `service`) | `tasks/register.yml`; `defaults/main.yml:75-88` | yes (deploy/reconfigure); **not** on upgrade |

**Oddity / risk:** the enable/db_sync/disable sequence is not wrapped in `block/always`. If the bootstrap container fails, the global MariaDB variable stays at `1`. HYPOTHESIS: a security-relevant leftover state. A related upstream fix for keystone appears in `releasenotes/notes/bug-1987982-fix-keystone-log_bin_trust_function_creators-variables-*.yaml`.

**Reconfigure as uncontrolled upgrade:** if an operator bumps `openstack_tag`/`glance_tag` and runs `reconfigure`, the new image runs the `KOLLA_BOOTSTRAP` branch (`glance-manage db_sync` and `db_load_metadefs`, kolla `docker/glance/glance-api/extend_start.sh:5-9`) and the handler recreates glance-api on the new image. For the glance role that is the default legacy upgrade (`glance_enable_rolling_upgrade: "no"`, `all.yml:868`): `legacy_upgrade.yml:2-9` runs the same config, check-containers, `bootstrap_service.yml` and flush steps, and reconfigure only adds registration, DB/user creation, the dev-mode clone and the sanity check, off by default (`deploy.yml:2-17`).

### 1.7 Dependencies (from `templates/glance-api.conf.j2`)
- **MariaDB** via the VIP (:33-37); **RabbitMQ**: `transport_url = rpc_transport_url` (:26) and notifications (:111-118; topics only if ceilometer or searchlight, `defaults/main.yml:93-97`).
- **Keystone**: `www_authenticate_uri = keystone_internal_url`, `auth_url = keystone_admin_url` (:39-49). **memcached**: all hosts (:51-53).
- **Cinder**: `cinder_catalog_info = volume:cinder:internalURL` (:24), and `enabled_backends` contains `cinder:cinder` whenever `enable_cinder` (`defaults/main.yml:167-169`; template :16-18). **Oddity:** cinder registers only `cinderv2/volumev2` and `cinderv3/volumev3` (`roles/cinder/defaults/main.yml:201-215`). No `volume/cinder` catalog entry exists, and the template has no `[cinder]` store section. HYPOTHESIS: the glance cinder store is half-configured and would fail if used (NEEDS-LAB). Nova, by contrast, uses `catalog_info = volumev3:cinderv3:internalURL` (`roles/nova-cell/templates/nova.conf.j2:113`).
- **Ceph**: `[rbd] rbd_store_user/pool` (:74-79). `show_multiple_locations = True` is set when ceph is the backend (:20-22). It exposes image locations; it is needed for COW clones but it is security-sensitive.
- **Swift**: `[swift]` section (:81-91) with **`swift_store_auth_insecure = True` hard-coded**. `glance-swift.conf` authenticates against `openstack_auth.auth_url/v3` (the keystone admin URL) as `service:glance` (`templates/glance-swift.conf.j2:1-8`).
- **Barbican** (:133-138), **osprofiler** (:125-131), **VMware** (:93-100).
- Cinder iSCSI flag toggles glance-api `privileged`, `/dev` and `iscsi_info` (`defaults/main.yml:10,139-140`). HYPOTHESIS: this is for os-brick attach in the glance cinder store.

### 1.8 Operational notes
1. **Backend switch via unrelated flags:** `glance_backend_swift` defaults to `enable_swift` (`all.yml:866`), and `glance_backend_file` is the negation of ceph/swift/vmware (`all.yml:862`). Enabling Swift (or `glance_backend_ceph`) on a running cloud does three things:
   - removes `file` from `enabled_backends` and drops the `[file]` section (`defaults/main.yml:155-157`; template :17,69-72);
   - changes `default_backend` (:58-67);
   - expands `glance_api_hosts` to every `glance-api` host (`all.yml:869`).

   HYPOTHESIS: existing images in the file store become unreadable. NEEDS-LAB.

   A related doc mismatch: the guide says ceph is enabled "automatically" (`glance-guide.rst:43`), but the default is `glance_backend_ceph: "no"` (`all.yml:863`).
2. **Inventory order matters:** with the file backend, glance runs on `groups['glance-api']|first`. HYPOTHESIS: reordering the inventory moves glance-api to a host with an empty `glance` volume, and HAProxy follows it.
3. **Restart impact:** the HAProxy timeouts are 6h because uploads and downloads are long. HYPOTHESIS: restarting glance-api (10 s graceful) aborts in-flight uploads, downloads, nova snapshots and cinder upload-to-image operations, leaving images in `saving`/`queued`. With the file backend this is a total Image API outage, and nova boots that need an uncached image fail during the window.
4. **Rolling upgrade** (`tasks/rolling_upgrade.yml`):
   - Sequence: config on host[0] (:7-8) → **stop glance-api on host[0]** (:10-11) → enable log_bin (:13-27) → `GLANCE_DB_EXPAND` (:29-48) → `GLANCE_DB_MIGRATE`, which notifies restart (:50-71) → config on the other hosts (:74-75) → check-containers (:77) → **flush handlers**, so all glance-api containers restart in the same handler run (:79-80) → `GLANCE_DB_CONTRACT` (:82-101) → disable log_bin (:103-117).
   - The `glance_upgrading` fact (:2-4, :119-121) is set but never read anywhere (dead code).
   - HYPOTHESIS, with `kolla_serial` > 0: each batch re-runs the run_once expand/migrate/**contract**. The contract would run at the end of batch 1 while hosts in later batches still run old code. NEEDS-LAB.
   - The docs warn that rolling upgrade with a non-shared file backend leads to "a corrupt state" (`glance-guide.rst:108`).
5. **Image cache** is never pruned. The docs say "Glance caches are not cleaned up automatically" (`glance-guide.rst:145`); there is no cron/pruner container.
6. **Sanity check** (if enabled) creates and deletes an image on every deploy/reconfigure (`deploy.yml:17`).
7. Glance does not touch compute hosts. Nova-compute reaches glance through `[glance] api_servers` = internal VIP (`roles/nova-cell/templates/nova.conf.j2:105-109`), and cinder through `glance_api_servers` (`roles/cinder/templates/cinder.conf.j2:19`).

---

## 2. PLACEMENT

### 2.1 Play
```yaml
# ansible/site.yml:697-706
- name: Apply role placement
  hosts: [placement-api, '&enable_placement_True']
  serial: '{{ kolla_serial|default("0") }}'
  roles: [{ role: placement, tags: placement, when: enable_placement | bool }]
```
- `enable_placement: "{{ enable_nova | bool or enable_zun | bool }}"` (`all.yml:689`).
- **Oddity:** the LB include for placement **has no `when: enable_placement`** (`site.yml:289-292`), unlike every other service. HYPOTHESIS: when placement is disabled it still writes an (effectively empty) `services.d/placement-api.cfg`, because `placement-api.enabled: True` and only the inner haproxy entries carry `enable_placement`.
- The play sits right before `import_playbook: nova.yml` (`site.yml:710`).

### 2.2 `placement_services` (`ansible/roles/placement/defaults/main.yml:2-24`)
| key | container | group | enabled | flags |
|---|---|---|---|---|
| placement-api | `placement_api` | `placement-api` | `True` | Plain Apache/mod_wsgi. No privileged, no host paths beyond config, localtime and logs (:45-50). HAProxy internal and external on 8780, `tls_backend: placement_enable_tls_backend` (:10-24). |

### 2.3 Task flow
| action | flow |
|---|---|
| deploy / reconfigure | `register.yml` → (clone) → `config.yml` → `check-containers.yml` → `bootstrap.yml` → flush (`tasks/deploy.yml:1-14`) |
| upgrade | `register.yml` → (clone) → `config.yml` → `check-containers.yml` → `bootstrap.yml` (`KOLLA_BOOTSTRAP` with the new image: `placement-manage db sync` **and** `db online_data_migrations`, kolla `docker/placement/placement-api/extend_start.sh:5-9`, while the old placement-api is still running; the image's `KOLLA_UPGRADE` branch, db sync only, `:11-15`, is not used) → flush (all placement-api restart) → **`KOLLA_OSM` online data migrations** container, which runs them a second time (`tasks/upgrade.yml:1-34`) |
| deploy-containers | `check-containers.yml` |
| pull / stop | service-images-pull / service-stop |
| precheck | groups exist, port 8780 free if not running (`tasks/precheck.yml:1-27`) |
| check | empty file (`tasks/check.yml:1`) |
| config | `config.yml` |

### 2.4 Config files (`ansible/roles/placement/tasks/config.yml`)
| dest | sources | notifies |
|---|---|---|
| `placement-api/config.json` | `placement-api.json.j2` (:38-49) | Restart placement-api |
| `placement-api/placement.conf` | merge: template → `global.conf` → `placement.conf` → `placement/placement-api.conf` → `placement/<host>/placement.conf` (:51-69) | Restart |
| `placement-api/placement-api-wsgi.conf` | first_found: `placement/<host>/placement-api-wsgi.conf` → `placement/placement-api-wsgi.conf` → template (:71-87) | Restart |
| `placement-api/migrate-db.rc` | `migrate-db.rc.j2` (:89-101) | Restart |
| policy | `{{node_custom_config}}/placement/` (:15-32, :103-115) | Restart |
| certs | service-cert-copy (:34-36) | Restart |

`migrate-db.rc` contains the **nova_api DB user and password** together with the placement DB creds (`templates/migrate-db.rc.j2:1-8`; vars at `defaults/main.yml:89-92`). It is a leftover from the Stein→Train extraction of placement from nova_api. It spreads a nova secret into the placement container and is notified on change.

### 2.5 Handlers
`Restart placement-api container`: recreate_or_restart, no special logic (`handlers/main.yml:2-15`).

### 2.6 Bootstrap
- `mysql_db placement` and `mysql_user` (`tasks/bootstrap.yml:2-34`) re-run on reconfigure.
- `bootstrap_placement` with `KOLLA_BOOTSTRAP` (kolla image: `placement-manage db sync` then `placement-manage db online_data_migrations`, kolla `docker/placement/placement-api/extend_start.sh:5-9`) runs once, delegated to `groups['placement-api'][0]` (`bootstrap_service.yml:2-20`). **It re-runs on every reconfigure.**
- Keystone registration (service `placement`, 3 endpoints, user `placement`) happens in deploy, reconfigure **and upgrade** (`upgrade.yml:2`), unlike glance/cinder/heat.
- Online data migrations: the separate `KOLLA_OSM` container runs **only** in upgrade (`upgrade.yml:16-34`). Because the bootstrap container above also runs `db online_data_migrations`, placement OSM also runs on every deploy/reconfigure (`deploy.yml:11`, `reconfigure.yml:2`) and twice in upgrade (bootstrap at `upgrade.yml:11`, then `KOLLA_OSM`).

### 2.7 Dependencies (`templates/placement.conf.j2`)
- MariaDB `[placement_database]` with **`max_overflow = 1000` hard-coded** (:24-29).
- memcached `[cache]` and `keystone_authtoken` (:31-51); Keystone (:37-47).
- `transport_url = rpc_transport_url` (:13) is configured even though placement does no RPC.
- Leftovers: `osapi_compute_listen`, `my_ip` (:8-11).
- **Dead variables:** `placement_notification_topics` / `placement_enabled_notification_topics` (`defaults/main.yml:69-75`) are not referenced by any template. There is no `[oslo_messaging_notifications]` section.

### 2.8 Operational notes and the relation to nova
- **Consumers authenticate as the placement user.** nova-api/conductor/scheduler (`roles/nova/templates/nova.conf.j2:169-179`) and **nova-compute on every compute host** (`roles/nova-cell/templates/nova.conf.j2:203-213`) use `username = {{ placement_keystone_user }}` / `password = {{ placement_keystone_password }}`, `valid_interfaces = internal`. Neutron does the same (`roles/neutron/templates/neutron.conf.j2:172-183`), as do zun and cyborg. Rotating `placement_keystone_password` therefore needs a reconfigure of placement **and** nova (all computes) **and** neutron. This dependency scales with the number of compute hosts.
- HYPOTHESIS (upstream nova): during a placement-api outage or restart, scheduling fails with NoValidHost and the nova-compute resource tracker periodic task logs errors. With serial=0 every placement-api restarts in the same handler flush, so there is a short full outage.
- The upgrade db sync and online data migrations (bootstrap container) run while the old placement-api is still serving (no stop).

---

## 3. CINDER

### 3.1 Play
```yaml
# ansible/site.yml:683-695
- name: Apply role cinder
  hosts: [cinder-api, cinder-backup, cinder-scheduler, cinder-volume, '&enable_cinder_True']
  serial: '{{ kolla_serial|default("0") }}'
  roles: [{ role: cinder, tags: cinder, when: enable_cinder | bool }]
```
- LB include: `site.yml:154-158`.
- Defaults: `enable_cinder: "no"`, `enable_cinder_backup: "yes"`, `enable_cinder_backend_iscsi: "{{ enable_cinder_backend_lvm }}"`, `enable_cinder_backend_lvm: "no"` (`all.yml:598-604`). `cinder_backend_ceph: "no"`, `cinder_backup_driver: "ceph"` (`all.yml:901,909`).
- Sample inventory: `cinder-api`/`cinder-scheduler` sit under `[cinder:children] control`. **`cinder-volume`/`cinder-backup` sit under `storage`** (`ansible/inventory/multinode:149-150,340-350`).

### 3.2 `cinder_services` (`ansible/roles/cinder/defaults/main.yml:2-48`)
| key | container | group | enabled | flags / host volumes |
|---|---|---|---|---|
| cinder-api | `cinder_api` | cinder-api | true | Apache/mod_wsgi on 8776; HAProxy internal and external (:10-24) |
| cinder-scheduler | `cinder_scheduler` | cinder-scheduler | true | – |
| cinder-volume | `cinder_volume` | cinder-volume | true | **`privileged: True`, `ipc_mode: host`** (:37-38). Volumes (:107-118): **`/dev/:/dev/`, `/lib/modules:ro`, `/run/:/run/:shared`**, `cinder:/var/lib/cinder`, **`iscsi_info:/etc/iscsi`** (if `enable_iscsid`), **`target_config:/etc/target`** (LVM and `lioadm`). |
| cinder-backup | `cinder_backup` | cinder-backup | `enable_cinder_backup` | **`privileged: True`** (no ipc host). Volumes (:90-100): `/dev/`, `/lib/modules`, `/run/:shared`, `cinder:/var/lib/cinder`, `iscsi_info`. |

Related: `cinder_target_helper` is `lioadm` on RedHat and `tgtadm` otherwise (`all.yml:904`). With `tgtadm` the targets are served by a **separate `tgtd` container** from the `iscsi` role, which also deploys `iscsid` on `compute`, `cinder-volume` and `cinder-backup` hosts (`roles/iscsi/defaults/main.yml:2-20,67-78`; play `site.yml:512-522`).

### 3.3 Task flow
| action | flow |
|---|---|
| deploy / reconfigure | `register.yml` → `config.yml` → `check-containers.yml` → (clone) → `bootstrap.yml` → flush → `check.yml` (`tasks/deploy.yml:1-16`) |
| upgrade | `config.yml` **only on `groups['cinder-api'][0]`** (:4-5) → `bootstrap_service.yml` (db sync, new image, old services still running) (:7) → `config.yml` on all (:9) → `check-containers.yml` (:11) → flush, so **every cinder container on every host restarts in this flush (serial 0)**, cinder-volume and cinder-backup included (:13-14) → `KOLLA_OSM` online migrations (:16-34). No `register.yml`. |
| deploy-containers | check-containers |
| pull / stop | helpers |
| precheck | groups; API port free; **at least one backend enabled** unless `skip_cinder_backend_check` (:26-38); **`vgs cinder-volumes`** on cinder-volume hosts if LVM (`tasks/precheck.yml:40-49`) |
| check | create a 1 GB `kolla_test_volume` and delete it, if `kolla_enable_sanity_cinder` (`tasks/check.yml`). This also runs at the end of deploy/reconfigure. |
| config | `config.yml` |

### 3.4 Config files (`ansible/roles/cinder/tasks/config.yml`)
| dest | sources | when | notifies |
|---|---|---|---|
| `<svc>/ceph.conf` (cinder-volume, cinder-backup) | **merge** `cinder/ceph.conf` + `cinder/<svc>/ceph.conf` (`external_ceph.yml:2-20`) | `cinder_backend_ceph` and host in volume/backup (`config.yml:15-19`) | Restart <svc> |
| `cinder-volume/<ceph_cinder_keyring>` | `cinder/cinder-volume/ceph.client.cinder.keyring` (`external_ceph.yml:22-33`) | cephx | Restart cinder-volume |
| `cinder-backup/` keyrings (cinder plus cinder-backup) | `cinder/cinder-backup/...` (`external_ceph.yml:35-50`) | cephx | Restart cinder-backup |
| policy | `{{node_custom_config}}/cinder/` (:21-38, :95-107) | | Restart <svc> |
| certs | service-cert-copy (:40-42) | | |
| `<svc>/config.json` | `<svc>.json.j2` (:44-55) | | Restart <svc> |
| `cinder-api/cinder-wsgi.conf` | first_found: `cinder/<host>/cinder-wsgi.conf` → `cinder/cinder-wsgi.conf` → template (:57-73) | | Restart cinder-api |
| `<svc>/cinder.conf` (one per service, `service_name` var) | merge: template → `global.conf` → `cinder.conf` → `cinder/<svc>.conf` → `cinder/<host>/cinder.conf` (:75-93) | | Restart <svc> |
| `cinder-volume/nfs_shares` | first_found among 8 paths (`nfs_shares.j2` variants, then plain), `skip` unless NFS or HNAS (:109-128) | host in cinder-volume | Restart cinder-volume |

### 3.5 Handlers (`ansible/roles/cinder/handlers/main.yml`)
Four handlers (api :2-15, scheduler :17-30, volume :32-47, backup :49-63), all recreate_or_restart. The volume handler passes `privileged` and `ipc_mode`; the backup handler passes `privileged`. There is no drain or wait logic.

### 3.6 Bootstrap
- `mysql_db cinder` and `mysql_user` run every deploy/reconfigure (`bootstrap.yml:2-34`).
- `bootstrap_cinder` (`KOLLA_BOOTSTRAP`: `cinder-manage db sync`, kolla `docker/cinder/cinder-api/extend_start.sh:6-9`), run_once on `groups['cinder-api'][0]` (`bootstrap_service.yml:2-20`). **It re-runs on every reconfigure.**
- Online data migrations (`KOLLA_OSM`) run only in upgrade.
- Keystone: `cinderv2/volumev2` and `cinderv3/volumev3`, each with 3 `/vN/%(tenant_id)s` endpoints, plus user `cinder` (`defaults/main.yml:201-221`). Registered on deploy/reconfigure, not on upgrade.

### 3.7 Dependencies (`templates/cinder.conf.j2`)
- **Glance**: `glance_api_servers` = internal VIP:9292 (:19). **`glance_num_retries = {{ groups['glance-api'] | length }}`** (:21) scales with the number of glance hosts. With the glance file backend only one glance-api exists, yet retries equal the group size.
- **Nova**: `[nova]` section authenticates with **`nova_keystone_user`/`nova_keystone_password`** (:83-93), so rotating the nova password needs a cinder reconfigure. In the other direction, nova-api and nova-compute use **`cinder_keystone_user/password`** (`roles/nova-cell/templates/nova.conf.j2:111-122`, `roles/nova/templates/nova.conf.j2:66-76`), so rotating the cinder password needs a reconfigure of all computes. Manila also uses the cinder creds (`roles/manila/templates/manila-share.conf.j2:29-30`).
- MariaDB (:95-99); RabbitMQ RPC and notify (:64-73; topics for ceilometer/vitrage, `defaults/main.yml:165-171`); Keystone and memcached (:101-115); Barbican (:198-203); osprofiler (:190-196).
- **Ceph**: `[rbd-1]` with `rbd_secret_uuid = cinder_rbd_secret_uuid` (:131-145). The same UUID is installed into libvirt on computes by `roles/nova-cell/tasks/external_ceph.yml:92,134`, so the two must stay in sync.
- **Swift** backup: `backup_swift_url` internal (:47-53).
- **Coordination**: redis or **etcd: only `groups['etcd'][0]`** (:205-214; the comment says multiple endpoints are not supported). The etcd lock service is therefore a single point of failure. Default `cinder_coordination_backend` is `''` unless redis or etcd is enabled (`all.yml:906`).
- **LVM/iSCSI**: `target_helper`, `target_protocol = iscsi` (:122-129).

### 3.8 Operational notes
1. **No `host`/`backend_host`/`cluster` set in cinder.conf** (`templates/cinder.conf.j2` has none; `grep backend_host ansible/roles/cinder` returns nothing). Because of `network_mode: host`, each cinder-volume registers as `<node-hostname>@<backend>`.
   - HYPOTHESIS (upstream cinder): with a shared backend (ceph `rbd-1`) on several cinder-volume hosts, every volume is owned by the host that created it.
   - If that node is down, its volumes cannot be attached, detached, deleted or snapshotted until the node returns or `cinder-manage volume update_host` is run.
   - Renaming or replacing a storage node has the same effect. The docs also note LVM issues in a multi-controller setup (`doc/source/reference/storage/cinder-guide.rst:52-55`).
2. **cinder-volume restart impact** (HYPOTHESIS, upstream cinder and os-brick):
   - The **data path for attached volumes does not go through cinder-volume**. Ceph RBD is accessed by libvirt/librbd on computes. LVM is exported by LIO (kernel, config persisted in the `target_config` volume) or by the separate `tgtd` container. Existing attachments therefore survive a cinder-volume restart.
   - In-flight operations are a different matter. The 10 s graceful timeout can SIGKILL `qemu-img`/`dd` copies (image→volume, volume→image, migrate, retype).
   - On start, `init_host` moves stuck resources (`creating`/`downloading` → `error`, `uploading` → reverted) and re-runs `ensure_export` for in-use volumes. NEEDS-LAB.
3. **cinder-backup restart:** HYPOTHESIS: backups and restores in progress are killed and marked `error` on the next start. Because of the `cinder_backup_driver` default, see oddity 5.
4. **Upgrade restarts every cinder-volume and cinder-backup at once** (flush at `upgrade.yml:13-14`; serial 0 unless `ANSIBLE_SERIAL` is set). There is no `[upgrade_levels]` pinning in the template. HYPOTHESIS: cinder's automatic RPC version pinning needs one more restart of all services after the upgrade to unpin, and the role does not do that. NEEDS-LAB.
5. **Oddity: backup driver vs. ceph files.** `cinder_backup_driver: "ceph"` is the default even when `cinder_backend_ceph` is `no`. cinder.conf then sets `backup_driver = ...CephBackupDriver`, `backup_ceph_conf=/etc/ceph/ceph.conf` (:31-40). But `cinder-backup.json.j2` only lists ceph.conf and the keyrings `{% if cinder_backend_ceph %}` (:15-36), and `external_ceph.yml` only runs for `cinder_backend_ceph`. HYPOTHESIS: with an LVM or NFS-only deployment and default backup settings, cinder-backup starts without a ceph config and its driver fails. NEEDS-LAB.
6. **Multipath** is never configured: no `use_multipath_for_image_xfer` / `volume_use_multipath` in cinder or nova templates (`grep multipath` returns nothing). The `multipathd` container is off by default (`all.yml:666`).
7. **Compute-host touchpoints:** the cinder role itself does not target computes. However, `iscsid` on computes (iscsi role) shares `iscsi_info`, nova-compute uses the cinder creds, and the RBD secret is shared with nova-libvirt. Enabling `enable_cinder_backend_iscsi`/LVM also flips glance-api to privileged with `/dev`, so **glance-api is recreated** (`roles/glance/defaults/main.yml:10,139-140`).
8. External Ceph needs cinder-volume and cinder-backup hosts in the `storage` group, otherwise "Cinder and related services relying on this group [will] fail" (`doc/source/reference/storage/external-ceph-guide.rst:73-80`).
9. The sanity check (if enabled) creates a 1 GB volume on every deploy/reconfigure.

---

## 4. HORIZON

### 4.1 Play
```yaml
# ansible/site.yml:806-815
- name: Apply role horizon
  hosts: [horizon, '&enable_horizon_True']
  serial: '{{ kolla_serial|default("0") }}'
  roles: [{ role: horizon, tags: horizon, when: enable_horizon | bool }]
```
- LB include: `site.yml:209-213`. `enable_horizon: "{{ enable_openstack_core | bool }}"` (`all.yml:617`).
- Horizon is the last of these plays.

### 4.2 `horizon_services` (`ansible/roles/horizon/defaults/main.yml:2-69`)
| key | container | group | enabled | flags |
|---|---|---|---|---|
| horizon | `horizon` | horizon | true | **`environment`: 27 `ENABLE_<PLUGIN>` flags plus `FORCE_GENERATE`** (:8-36). **Host `/tmp:/tmp` bind** (:98). Settings use `LOCAL_PATH = '/tmp'` (`templates/local_settings.j2:154`). HAProxy uses `balance source` (:46-47, :61-62) and adds http→https redirect frontends when TLS is on (:49-54, :64-69). |

Because the plugin flags live in the container environment, and `check-containers` compares `environment` (`tasks/check-containers.yml:11`), **enabling or disabling any service that has a horizon plugin** (designate, octavia, magnum, …) changes the env. The horizon container is then **recreated** on the next deploy/reconfigure even if no horizon config changed.

### 4.3 Task flow
| action | flow |
|---|---|
| deploy / reconfigure | `config.yml` → `check-containers.yml` → (clone) → `bootstrap.yml` **only if `horizon_backend_database`** → flush (`tasks/deploy.yml:1-14`). There is **no keystone registration**. |
| upgrade | `config.yml` → `check-containers.yml` → (clone) → `bootstrap_service.yml` if DB backend → flush (`tasks/upgrade.yml:1-14`) |
| precheck | groups; port 80 (`horizon_listen_port`) free (`tasks/precheck.yml`) |
| check | empty |
| pull / stop / deploy-containers / config | standard |

### 4.4 Config files (`ansible/roles/horizon/tasks/config.yml`)
| dest | source | notifies |
|---|---|---|
| per-service policy files (`<svc>_policy.json/yaml`) | for each enabled service in the list (:19-51), `policy_item.yml` looks for `{{node_custom_config}}/horizon/<svc>_<policy file>` (`tasks/policy_item.yml:1-25`) and copies the matches (:121-134) | Restart horizon |
| `horizon/config.json` | `horizon.json.j2` (:53-65) | Restart horizon |
| `horizon/horizon.conf` (Apache) | first_found: `horizon/<host>/horizon.conf` → `horizon/horizon.conf` → template (:67-83). This is a **whole-file override**, not a merge. | Restart horizon |
| `horizon/local_settings` | first_found: `horizon/<host>/local_settings` → `horizon/local_settings` → `local_settings.j2` (:85-101). Whole-file override. | Restart horizon |
| `horizon/custom_local_settings` | first_found, same pattern; the default template is empty (:103-119). It is imported last by `local_settings` (`local_settings.j2:859-860`). | Restart horizon |
| certs | service-cert-copy (:136-138) | |

### 4.5 Handlers
`Restart horizon container` (`handlers/main.yml:2-16`): recreate_or_restart. It passes `environment`; there is no other logic.

### 4.6 Bootstrap
- `horizon_backend_database: "{{ enable_murano | bool }}"` (`all.yml:982`). Only then does deploy/reconfigure create the DB and user and run `bootstrap_horizon` (`KOLLA_BOOTSTRAP`: Django `manage.py migrate --noinput`, then exits; kolla `docker/horizon/extend_start.sh:46-49`) (`tasks/bootstrap.yml`, `bootstrap_service.yml:2-20`). In that case **the bootstrap re-runs on every reconfigure**.
- There is no keystone registration at all.

### 4.7 Dependencies (`templates/local_settings.j2`)
- **Keystone**: `OPENSTACK_KEYSTONE_URL = horizon_keystone_url` = `keystone_internal_url/v3` (`defaults/main.yml:106`; template :209). `OPENSTACK_HOST = kolla_internal_fqdn` (:207). `OPENSTACK_ENDPOINT_TYPE = "internalURL"` (:420), so Horizon talks to **every** service's internal endpoint from its own container.
- **memcached**: `SESSION_ENGINE = cache` with all memcached hosts **unless** the DB backend is used (:177-185). With the DB backend: `SESSION_ENGINE = db` plus MariaDB (:32-44).
- **Cinder**: `enable_backup` follows `enable_cinder_backup` (:310). **Murano + Barbican**: `KEY_MANAGER` with murano creds (:845-854).
- `SECRET_KEY = horizon_secret_key` (:165), which is the same on all nodes.
- Multi-region `AVAILABLE_REGIONS` (:198-205).
- TLS: `SECURE_PROXY_SSL_HEADER` and secure cookies when either internal or external TLS is on (:58-62). `horizon.conf.j2:99-102` has a FIXME: "enabling of either tls will break the other if not enabled too".

### 4.8 Operational notes
- HYPOTHESIS: a horizon restart does not log users out (sessions live in memcached), but a **memcached restart does**. With `balance source`, users stick to one backend. Restarting a node drops in-flight requests, including legacy image uploads that go through Horizon. Those are staged in `LOCAL_PATH=/tmp`, which is the **host's** `/tmp`.
- Image side (kolla `docker/horizon/extend_start.sh`): every start syncs each `ENABLE_<PLUGIN>` dashboard file into `openstack_dashboard/local/enabled` (`:51-65,339-366`). `manage.py collectstatic --noinput --clear` and `compress --force` run **only** when `/var/lib/kolla/.settings.md5sum.txt` is missing, the md5 of `local_settings` + `custom_local_settings` + `local_settings.d` differs from it, a plugin file was just copied in or removed, or `FORCE_GENERATE=yes` (`:57-63,322-337,368-372`). kolla-ansible sets `FORCE_GENERATE=yes` only when `horizon_dev_mode` is on, and `no` otherwise (`defaults/main.yml:36,123`). The settings set `COMPRESS_OFFLINE = True` (`local_settings.j2:13`). `/var/lib/kolla` is not a volume (`defaults/main.yml:90-98`), so the hash file lives in the container layer. The handler restarts the container under `COPY_ALWAYS` (default, `all.yml:43`) and recreates it when image, env or volumes differ, or under `COPY_ONCE` (`kolla_docker.py:793-803`). HYPOTHESIS: the next start is slow after a recreate (new image, plugin flag change, `COPY_ONCE`) or a `local_settings`/`custom_local_settings` change, and not after a plain restart with unchanged settings. NEEDS-LAB: duration. See [annex/kolla-images.md §5](../kolla-images.md).
- Horizon config is independent of host count except for the memcached list.

---

## 5. HEAT

### 5.1 Play
```yaml
# ansible/site.yml:793-804
- name: Apply role heat
  hosts: [heat-api, heat-api-cfn, heat-engine, '&enable_heat_True']
  serial: '{{ kolla_serial|default("0") }}'
  roles: [{ role: heat, tags: heat, when: enable_heat | bool }]
```
- LB include: `site.yml:204-208`. `enable_heat: "{{ enable_openstack_core | bool }}"` (`all.yml:616`).

### 5.2 `heat_services` (`ansible/roles/heat/defaults/main.yml:2-53`)
| key | container | group | enabled | flags |
|---|---|---|---|---|
| heat-api | `heat_api` | heat-api | true | Apache/mod_wsgi on 8004, HAProxy internal and external (:10-24) |
| heat-api-cfn | `heat_api_cfn` | heat-api-cfn | true | Apache/mod_wsgi on 8000, HAProxy internal and external (:32-46) |
| heat-engine | `heat_engine` | heat-engine | true | No haproxy, not privileged. Volumes are config, localtime and logs only (:97-102). |

### 5.3 Task flow
| action | flow |
|---|---|
| deploy / reconfigure | `register.yml` → `config.yml` → `check-containers.yml` → (clone) → `bootstrap.yml` → flush (`tasks/deploy.yml:1-15`) |
| upgrade | `config.yml` → `check-containers.yml` → `bootstrap_service.yml` (db sync with new image while the old engine and APIs still run) → remove `heat-engine/_deprecated.yaml` (:8-13) → flush, which restarts **all** heat-api, heat-api-cfn and heat-engine containers together (`tasks/upgrade.yml:1-16`). No `register.yml`. |
| precheck | ports 8004/8000 free on api/cfn hosts (`tasks/precheck.yml:16-36`). heat-engine is not checked. |
| check | empty |
| pull / stop / deploy-containers / config | standard |

### 5.4 Config files (`ansible/roles/heat/tasks/config.yml`)
| dest | sources | notifies |
|---|---|---|
| `<svc>/config.json` | `<svc>.json.j2` (:38-49) | Restart <svc> |
| `<svc>/heat.conf` (`service_name` per container) | merge: template → `global.conf` → `heat.conf` → `heat/<svc>.conf` → `heat/<host>/heat.conf` (:51-69) | Restart <svc> |
| policy | `{{node_custom_config}}/heat/` (:15-32, :71-83) | Restart <svc> |
| `heat-api/wsgi-heat-api.conf`, `heat-api-cfn/wsgi-heat-api-cfn.conf` | `src: "{{ role_path }}/templates/..."` (:85-111). **No override path exists**, unlike cinder/placement wsgi. | Restart heat-api / heat-api-cfn |
| certs | service-cert-copy (:34-36) | |

**Oddity:** in `templates/wsgi-heat-api.conf.j2:2-6` (and in the cfn twin) `python_path` is `/usr/lib/python2.7/site-packages` for CentOS binary and `/usr/lib/python<ver>/site-packages` for source. That is **not** the venv path, which placement and cinder use (`roles/placement/templates/placement-api-wsgi.conf.j2:2-6`). HYPOTHESIS: it is a harmless leftover because `WSGIScriptAlias` points at the venv binary (:37), but it is inconsistent. NEEDS-LAB.

### 5.5 Handlers
Three handlers: heat-api (:2-15), heat-api-cfn (:17-30), heat-engine (:32-45). All recreate_or_restart, with no special logic.

### 5.6 Bootstrap
- `mysql_db heat` and `mysql_user` (`tasks/bootstrap.yml:2-34`) run every deploy/reconfigure.
- `bootstrap_heat` container (`bootstrap_service.yml:2-29`) gets `KOLLA_BOOTSTRAP` plus the **cloud admin credentials as env vars** (`OS_AUTH_URL`, `OS_USERNAME`, `OS_PASSWORD`, `OS_PROJECT_NAME`, …) and `HEAT_DOMAIN_ADMIN_PASSWORD`. The image runs `heat-manage db_sync`, then `openstack domain list`. Only if `heat_user_domain` is absent does it create the domain, the `heat_domain_admin` user (password `HEAT_DOMAIN_ADMIN_PASSWORD`) and that user's `admin` role on the domain (kolla `docker/heat/heat-api/extend_start.sh:5-17`). **It re-runs on every reconfigure** (and on upgrade, `tasks/upgrade.yml:6`), but once the domain exists it never touches the user. A changed `heat_domain_admin_password` (`etc/kolla/passwords.yml:117`) is therefore **not** pushed to Keystone, while `heat.conf` gets the new value (`templates/heat.conf.j2:12-13`). HYPOTHESIS: stack-domain operations then fail authentication. The check looks only at the domain name, so if a run fails partway and leaves the domain without the user or its role, no later run repairs it. The container is removed on exit, after a failure too (`kolla_docker.py:837-845`), so the passwords do not linger in `docker inspect`. But `kolla_start` runs with xtrace: when the bootstrap creates the domain, the `openstack user create … --password` line goes to stderr with `HEAT_DOMAIN_ADMIN_PASSWORD` expanded. `kolla_docker` returns that stderr in the task result, which Ansible prints on failure or with `-v`, and the task sets no `no_log` (kolla `docker/base/start.sh:3`, `docker/heat/heat-api/extend_start.sh:12`; [annex/kolla-images.md §2.2](../kolla-images.md)).
- Keystone: services `heat/orchestration` (`/v1/%(tenant_id)s`) and `heat-cfn/cloudformation` (`/v1`); user `heat`; roles `heat_stack_owner` and `heat_stack_user`; **`heat_stack_owner` granted to the cloud admin user in the admin project** (`defaults/main.yml:148-177`; `tasks/register.yml:2-9`). This runs on deploy/reconfigure, not on upgrade.

### 5.7 Dependencies (`templates/heat.conf.j2`)
- **Public endpoints reached from inside VMs:** `heat_metadata_server_url` and `heat_waitcondition_server_url` use **`public_protocol` and `heat_cfn_external_fqdn`** (:7-8). `server_keystone_endpoint_type = public` (:24). Instances that use wait conditions or software deployments must be able to reach the **external** VIP on 8000 and the public keystone endpoint.
- **All other services:** `[clients] endpoint_type = internalURL` (:94-96). heat-engine calls nova, neutron, cinder, glance, swift, etc. through their internal catalog endpoints. The real dependency set is whatever the users' templates use.
- Keystone: `keystone_authtoken`, plus `[trustee]` with the heat service user (:69-75), plus `[ec2authtoken]` (:77-78). `stack_domain_admin` = `heat_domain_admin` / `heat_domain_admin_password` (:12-14).
- MariaDB (:40-44); RabbitMQ RPC (:20) and notifications (ceilometer only, `defaults/main.yml:139-143`); memcached for authtoken and `[cache]` (:58-66).
- `num_engine_workers = openstack_service_workers` (≤5) per engine host (:16-18).

### 5.8 Operational notes
- **heat-engine restarts with stacks in progress:** HYPOTHESIS (upstream heat). Docker sends SIGTERM and then SIGKILL after 10 s (`kolla_docker.py:873-875`), which is shorter than any long resource create. Stacks that a killed engine owned stay `*_IN_PROGRESS` until some engine starts again. At startup heat-engine's `reset_stack_status` marks stacks whose owning engine is no longer alive as `FAILED` ("Engine went down during stack …"). Users must then run `stack update` or a check/resume. NEEDS-LAB.
- With serial 0, **every heat-engine restarts in the same handler flush** on any heat.conf change. A memcached or rabbit membership change, a password rotation or an `openstack_service_workers` change is enough. Every in-progress stack in the cloud is therefore affected, not just a fraction.
- On upgrade the db sync runs while old engines are still active, and all engines restart together after it.
- Heat does not touch compute hosts. Its dependency on instance reachability to the external VIP (above) is the main network coupling.

---

## 6. Summary matrix: what `reconfigure` does per role

| role | keystone register | DB create/grant | bootstrap container (schema sync) on reconfigure | extra side effects on reconfigure | restarts (serial 0) |
|---|---|---|---|---|---|
| glance | yes | yes | **yes** (`KOLLA_BOOTSTRAP` on `glance_api_hosts[0]`) | **toggles GLOBAL `log_bin_trust_function_creators` 1→0**; optional sanity image | glance-api (and tls-proxy) on `glance_api_hosts` only (1 host with the file backend) |
| placement | yes | yes | **yes** (also runs online data migrations) | – | all placement-api |
| cinder | yes | yes | **yes** | optional sanity volume | api, scheduler, **volume, backup on all storage hosts** at once if their config changed |
| horizon | **no** | only if `horizon_backend_database` | only if `horizon_backend_database` | env-driven recreate when plugin flags change | all horizon |
| heat | yes (also roles and a grant to admin) | yes | **yes** (with admin creds in env) | – | api, api-cfn, **all engines** |

The separate online-data-migration container (`KOLLA_OSM`) runs **only on `upgrade`**, for placement (`upgrade.yml:16-34`) and cinder (`upgrade.yml:16-34`). Glance's expand/migrate/contract runs only in the rolling path. A reconfigure with a bumped image tag therefore runs cinder's `db sync` without its OSM step (kolla `docker/cinder/cinder-api/extend_start.sh:6-18`), while placement's bootstrap container runs both `db sync` and `db online_data_migrations` (kolla `docker/placement/placement-api/extend_start.sh:5-9`). HYPOTHESIS: for cinder that is a partially executed upgrade. See [annex/kolla-images.md §4](../kolla-images.md).

## 7. Things that scale with host count
- memcached and rabbit host lists in every config (§0). Any membership change rewrites the config of all 5 services and restarts every container of every service.
- `glance_num_retries = len(groups['glance-api'])` (`roles/cinder/templates/cinder.conf.j2:21`).
- HAProxy backend lists: glance uses `glance_api_hosts` (`roles/glance/defaults/main.yml:69-70`); the others use `groups[service.group]` (`roles/haproxy-config/templates/haproxy_single_service_split.cfg.j2:92-97`).
- Placement and cinder credentials are embedded in nova-compute config on **every compute**. Password rotation therefore needs a reconfigure of the whole compute fleet (§2.8, §3.7).
- `run_once` tasks repeat per batch when `ANSIBLE_SERIAL` is set (§0).

## 8. NEEDS-LAB list
1. Glance: an existing file-store image after `enable_swift: yes` or `glance_backend_ceph: yes` is applied by reconfigure.
2. Glance rolling upgrade with `ANSIBLE_SERIAL=1`: does the contract run before later batches are upgraded?
3. Glance-api start time with a large NFS `glance_file_datadir_volume` (recursive chown, `glance-api.json.j2:42-46`).
4. Glance cinder store with `cinder_catalog_info = volume:cinder:internalURL` and no `[cinder]` store section.
5. Cinder-backup with default `cinder_backup_driver=ceph` and `cinder_backend_ceph=no`.
6. Cinder-volume ownership (`host`) loss when one of several RBD cinder-volume nodes is down; the state of in-flight create-from-image after a cinder-volume restart.
7. Cinder RPC pinning after `kolla-ansible upgrade` (is a second restart needed?).
8. Heat-engine restart with `CREATE_IN_PROGRESS` stacks: final state and recovery steps.
9. Horizon restart: session survival (memcached) and start-up duration (collectstatic/compress).
10. Answered from kolla source: `bootstrap_heat` does **not** update the `heat_domain_admin` password once `heat_user_domain` exists (kolla `docker/heat/heat-api/extend_start.sh:10-14`; §5.6). Remaining NEEDS-LAB: how heat behaves after `heat_domain_admin_password` changes, when `heat.conf` gets the new value (`roles/heat/templates/heat.conf.j2:13`) but Keystone keeps the old one.
