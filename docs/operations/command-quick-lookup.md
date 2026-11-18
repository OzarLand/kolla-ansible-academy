---
title: Command quick lookup by tag
---

# Command quick lookup by tag

<!-- TODO editorial: intro, key answers (old section heading: "Quick lookup: tag → scope → typical impact") -->

The examples assume:

- the inventory is `/etc/kolla/multinode` (adapt `-i`);
- `globals.yml` and `passwords.yml` are in `/etc/kolla`;
- Ansible is 2.9.

Conventions:

- **Scope** = plays and hosts touched.
- **Restarts** = containers that *can* restart (only if drift is detected).
- **One-shot** = bootstrap containers that run regardless of drift.

| Command | Hosts touched (default inventory) | Can restart | One-shot containers | Typical duration driver |
|---|---|---|---|---|
| `-t keystone reconfigure` | haproxy, control | keystone ×3, haproxy | keystone db sync | small |
| `-t glance reconfigure` | haproxy, `glance-api` | glance-api, haproxy | db sync + metadefs load + MariaDB global flag toggle | small |
| `-t placement reconfigure` | haproxy, control | placement-api, haproxy | db sync + online data migrations (one `bootstrap_placement` container) | small |
| `-t nova reconfigure` | haproxy, control, **all computes** | all nova incl. **libvirt**, haproxy | 5 runs (those of `nova-api` and `nova-cell` below) | number of computes |
| `-t nova-api reconfigure` | haproxy, control | nova-api, scheduler, haproxy | 2 (API DB sync, `map_cell0`) | small |
| `-t nova-cell reconfigure` | haproxy (console-proxy frontends), control (conductor, consoles), **all computes** | conductor, consoles, compute, libvirt, ssh; haproxy if a console-proxy frontend changed | 3 (cell DB sync, `list_cells` ×2: cell lookup and discovery; `discover_hosts` itself is a `docker exec` into `nova_conductor`) | number of computes |
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

<!-- TODO editorial: related -->
