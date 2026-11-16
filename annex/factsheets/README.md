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
([../lab/kolla_docker_params.out](../lab/kolla_docker_params.out)). Sheet C states it correctly.

**Context the sheets do not repeat.** The sheets were written before the lab showed that Ansible 2.9 notifies the
handlers of *every* executed loop item when any item changes. Wherever a sheet says "restarts container X if its
config changed", read it as "restarts **all containers of that role on that host** if any of them changed" (see
[docs/03 §2.4](../../docs/03-ansible-roles-and-tags-mapping.md)).
