# Per-role fact sheets

Five fact sheets produced by systematic source reading of `ussuri-eol`. Every claim carries a `path:line` reference
relative to the kolla-ansible repository root. Inferences are labelled **HYPOTHESIS**; anything that needs a real
environment is labelled **NEEDS-LAB**.

| Sheet | Scope |
|---|---|
| [A — infra / load balancing / OVN](A-infra-lb-ovn.md) | `haproxy` (+ keepalived, the 49 per-service `loadbalancer.yml` includes), `haproxy-config`, `memcached`, `chrony`, `ovn`, `ovs-dpdk`, `service-cert-copy`, `certificates.yml` |
| [B — MariaDB / RabbitMQ / Keystone](B-mariadb-rabbitmq-keystone.md) | Galera bootstrap/recovery/backup and rolling restart; RabbitMQ (incl. outward); Keystone fernet keys and runtime coupling |
| [C — Glance / Placement / Cinder / Horizon / Heat](C-glance-placement-cinder-horizon-heat.md) | per-role flow, bootstrap on reconfigure, dependencies, restart impact |
| [D — Barbican / Octavia / Swift / Manila + compute-side roles](D-barbican-octavia-swift-manila-compute-roles.md) | control-plane roles and every role that places containers on compute hosts; templates embedding host lists |
| [E — host bootstrap and operational playbooks](E-host-bootstrap-ops-playbooks.md) | `bootstrap-servers` (Docker restart conditions, `/etc/hosts`), prechecks, destroy, prune-images, fact gathering, CLI, tuning docs |

## Verification and errata

How the sheets were checked:

- **Spot checks against the source, all confirmed:**
  - MariaDB restart waves `index % 4` (`roles/mariadb/handlers/main.yml:66-78`);
  - glance `log_bin_trust_function_creators` toggle (`roles/glance/tasks/bootstrap_service.yml:2,38`);
  - Docker restart gate in `bootstrap-servers` (`roles/baremetal/tasks/post-install.yml:231-237`);
  - keepalived priority from inventory index (`roles/haproxy/templates/keepalived.conf.j2:13`);
  - compute-side memcached lists (`roles/ceilometer/templates/ceilometer.conf.j2:55`).
- **Behaviours re-verified by execution:** see [../lab](../lab/README.md).

**Erratum (applies to sheet A and any statement that `docker stop` honours `docker_graceful_timeout: 60`).** The
effective stop timeout of every `kolla_docker` stop/restart is **10 s**. In `kolla_docker.generate_module()`, a module
parameter that is not `None` overrides `common_options`, and `graceful_timeout` defaults to `10`. This was proven by
running the real module code
([../lab/kolla_docker_params.out](../lab/kolla_docker_params.out)). Sheet C states it correctly. The same error was in
sheet B's "Graceful stop" row, which is now corrected in the sheet.

**Erratum (sheet A, "There is no reload path anywhere in scope").** This holds for the handler path: every
handler stops and starts or recreates its container, and `kolla_docker` has no reload action. Outside the handlers,
Kolla sends one signal: the "Refresh nova scheduler cell cache" play sends `SIGHUP` to `nova_scheduler` on the
nova-scheduler hosts. It does so on `deploy` and `reconfigure` runs that select the `nova`, `nova-api` or
`nova-refresh-scheduler-cell-cache` tag, or no tag (`ansible/nova.yml:140-156`,
`roles/nova/tasks/refresh_scheduler_cell_cache.yml:10`).

**Erratum (sheet B §3.10, memcached counts).** In `ussuri-eol`, **35** roles have `memcache_secret_key` in their
templates, not 34, and **37** (not 36) have `memcache_servers`/`memcached_servers`. The memcached *host list* is
embedded by **38** roles:
- 37 loop over `groups['memcached']` in their templates (this includes horizon, whose `CACHES.LOCATION` uses the
  loop);
- monasca builds the list in `monasca_memcached_servers` (`roles/monasca/defaults/main.yml:127`).

The list includes `neutron.conf`, which the neutron agents on compute hosts also read, so a memcached membership
change reaches computes.

**Erratum (sheet A, "`tags: always` on the `import_role: haproxy-config` in every `loadbalancer.yml`").** This holds
for 48 of the 49 `loadbalancer.yml` files. `roles/nova-cell/tasks/loadbalancer.yml` does not import `haproxy-config`
itself. It reaches it through a chain: `import_tasks: proxy_loadbalancer.yml`, then `include_tasks:
cell_proxy_loadbalancer.yml`, then `import_role: haproxy-config`, with `tags: always` at every level. The effect is the
same.

**Erratum (image-side statements, kolla `ussuri-eol` read later).** The kolla image sources were read after the
sheets were written. The main changes, now made in the sheets, are:
- sheet A: keepalived's `/check_alive.sh` does query the haproxy stats socket (kolla
  `docker/keepalived/check_alive.sh:6`). The haproxy image ships a reload helper that kolla-ansible ussuri never calls
  (kolla `docker/haproxy/ensure_latest_config.sh:5-14`);
- sheet B: the broker's `.erlang.cookie` file is written only by the RabbitMQ bootstrap container, never on a
  normal broker start (kolla `docker/rabbitmq/extend_start.sh:7-18`);
- sheet C: the placement bootstrap container also runs `db online_data_migrations`, on every deploy and reconfigure
  (kolla `docker/placement/placement-api/extend_start.sh:5-9`). The glance bootstrap adds `db_load_metadefs` (kolla
  `docker/glance/glance-api/extend_start.sh:5-9`). The heat bootstrap creates the heat domain and user only when the
  domain is absent (kolla `docker/heat/heat-api/extend_start.sh:5-17`). Horizon runs `collectstatic` only when its
  settings hash is missing or differs, a dashboard plugin is added or removed, or `FORCE_GENERATE=yes` (kolla
  `docker/horizon/extend_start.sh:57-63,322-337,368-372`);
- sheet D: swift config and rings are copied into a container only at its start (kolla `docker/base/start.sh:8`,
  `docker/base/set_configs.py:391-393`). Only `swift_rsyncd` fixes `/srv/node` ownership at start (kolla
  `docker/swift/swift-rsyncd/extend_start.sh:3`).

In the same pass, sheet E §11 was corrected: like `reconfigure`, `upgrade` overrides a user `-e kolla_serial`
(`tools/kolla-ansible:430`). Sheets B and C also now cite the kolla source for several image-side statements that
were **HYPOTHESIS** and that it confirms, for example the keystone, cinder and horizon bootstrap commands and
glance's recursive chown of `/var/lib/glance`. Statements that cite a kolla path (kolla `docker/...`, relative to the
root of the kolla image repository at `ussuri-eol`) are [CODE]. Other image-side statements in the sheets remain
**HYPOTHESIS**. See [annex/kolla-images.md](../kolla-images.md).

**Context the sheets do not repeat.** The sheets were written before the lab showed that Ansible 2.9 notifies the
handlers of *every* executed loop item when any item changes. Wherever a sheet says "restarts container X if its
config changed", read it as "restarts **all containers of that role on that host** if any of them changed" (see
[docs/03 §2.4](../../docs/03-ansible-roles-and-tags-mapping.md)).
