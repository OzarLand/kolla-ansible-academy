---
title: MariaDB/Galera
---

# MariaDB/Galera

<!-- TODO editorial: intro -->

## Where to look

- **Fact sheet:** [fact sheet B
  §1](../reference/factsheets/b-mariadb-rabbitmq-keystone.md#1-mariadb-ansiblerolesmariadb)
- **Dependencies:** [Component dependencies
  §1](dependencies.md#1-the-shared-substrate-what-every-openstack-service-uses), [Component dependencies
  §2](dependencies.md#2-infrastructure-components)
- **Image side:** [Kolla images
  §4](../concepts/kolla-images.md#4-one-shot-containers-what-the-environment-variables-run) (row `mariadb`), [Kolla
  images §5](../concepts/kolla-images.md#5-per-image-start-behaviour), [Kolla images
  §5.4](../concepts/kolla-images.md#54-mariadb-what-the-image-does-not-do)
- **Also:** handlers: [Tags §5](../risk/tags.md#5-role--handler-map-core-services)
- **What the tag executes (`mariadb`):** [Tags §3](../risk/tags.md#3-what-a-tag-really-executes-master-table) and [Tags
  §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), rows `mariadb`
- **Scenario:** [Change control-plane membership
  §2](../operations/change-control-plane-membership.md#2-change-control-plane-membership-add-or-remove-a-controller)
- **Command:** [Database operations](../operations/database-operations.md), [Command quick lookup by
  tag](../operations/command-quick-lookup.md)
- **Risks:** [R9](../risk/risk-register.md#r9); `mariadb_recovery`: [R18](../risk/risk-register.md#r18)

## Service card

<!-- BEGIN GENERATED: tools/service_cards.py mariadb -->

| Item | Value |
|---|---|
| Play | site.yml:471 |
| Tags | mariadb |
| Play host patterns | mariadb |
| Node types in play (example inventory) | control |
| Node types running its containers | control |
| Containers | `mariadb`, `mariadb_clustercheck` |
| deploy/reconfigure flow (`tasks/deploy.yml`) | config → check-containers → bootstrap → flush handlers → register → check |
| Task files | backup.yml, bootstrap.yml, bootstrap_cluster.yml, check-containers.yml, check.yml, config.yml, deploy-containers.yml, deploy.yml, loadbalancer.yml, lookup_cluster.yml, main.yml, precheck.yml, pull.yml, reconfigure.yml, recover_cluster.yml, register.yml, restart_services.yml, stop.yml, upgrade.yml, wait_for_loadbalancer.yml |
| Templates | `backup.my.cnf.j2`, `galera.cnf.j2`, `mariabackup.json.j2`, `mariadb-clustercheck.json.j2`, `mariadb.json.j2`, `wsrep-notify.sh.j2`, `xinetd-clustercheck.j2` |
| Handlers (definition order) | Starting first MariaDB container; Wait for first MariaDB service port liveness; Wait for first MariaDB service to sync WSREP; Creating haproxy mysql user; Restart MariaDB on existing cluster members; Start MariaDB on new nodes; Ensure MariaDB is running normally on bootstrap host; Restart mariadb-clustercheck container |
| Key variables | `enable_mariadb`, `mariadb_*`, `database_address`, `enable_external_mariadb_load_balancer` |
| Role dependencies | `common` (meta) |

<!-- END GENERATED -->

<!-- TODO editorial: related -->
