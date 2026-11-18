---
title: "Common: fluentd, cron, kolla_toolbox"
---

# Common: fluentd, cron, kolla_toolbox

<!-- TODO editorial: intro -->

## Where to look

- **Fact sheet:** – (see [Repository architecture
  §5.1](../concepts/repository-architecture.md#51-the-common-role-and-the-common_run-guard))
- **Dependencies:** [Component dependencies
  §1](dependencies.md#1-the-shared-substrate-what-every-openstack-service-uses), [Component dependencies
  §2](dependencies.md#2-infrastructure-components) (row "Fluentd"), [Component dependencies
  §5](dependencies.md#5-compute-node-dependency-summary)
- **Image side:** [Kolla images §5](../concepts/kolla-images.md#5-per-image-start-behaviour) (rows `fluentd`, `cron`,
  `kolla-toolbox`)
- **Also:** [Apply `common` changes (fluentd, cron, kolla_toolbox)](../operations/apply-common-changes.md); handlers:
  [Tags §5](../risk/tags.md#5-role--handler-map-core-services)
- **What the tag executes (`common`):** [Tags §3](../risk/tags.md#3-what-a-tag-really-executes-master-table) and [Tags
  §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), rows `common`; why it
  is a no-op: [Tags §2.1](../risk/tags.md#21-dynamic-include_tasks-and-tag-inheritance-code)
- **Scenario:** [Apply `common` changes (fluentd, cron, kolla_toolbox)](../operations/apply-common-changes.md)
- **Command:** [Apply `common` changes (fluentd, cron, kolla_toolbox)
  §1.1](../operations/apply-common-changes.md#11-apply-common-changes-fluentd-cron-kolla_toolbox)
- **Risks:** [R25](../risk/risk-register.md#r25), [R2](../risk/risk-register.md#r2)

## Service card

<!-- BEGIN GENERATED: tools/service_cards.py common -->

| Item | Value |
|---|---|
| Play | meta dependency of 68 roles (not `memcached`, `multipathd` or the helper roles); runs in the first play that reaches each host |
| Tags | inherits the tag of the first play reaching the host (`-t common` alone is a no-op) |
| Play host patterns | first play reaching each host (chrony by default) |
| Node types in play (example inventory) | compute, control, monitoring, network, storage |
| Node types running its containers | compute, control, monitoring, network, storage |
| Containers | `fluentd`, `kolla_toolbox`, `cron` |
| deploy/reconfigure flow (`tasks/deploy.yml`) | config → check-containers → bootstrap → flush handlers |
| Task files | bootstrap.yml, check-containers.yml, check.yml, config.yml, copy-certs.yml, deploy-containers.yml, deploy.yml, main.yml, precheck.yml, pull.yml, reconfigure.yml, stop.yml, upgrade.yml |
| Templates | `admin-openrc.sh.j2`, `conf/filter/00-record_transformer.conf.j2`, `conf/filter/01-rewrite-0.12.conf.j2`, `conf/filter/01-rewrite-0.14.conf.j2`, `conf/filter/02-parser.conf.j2`, `conf/format/apache_access.conf.j2`, `conf/format/wsgi_access.conf.j2`, `conf/format/wsgi_python.conf.j2`, `conf/input/00-global.conf.j2`, `conf/input/01-syslog.conf.j2`, `conf/input/02-mariadb.conf.j2`, `conf/input/03-rabbitmq.conf.j2`, `conf/input/04-openstack-wsgi.conf.j2`, `conf/input/05-libvirt.conf.j2`, `conf/input/06-zookeeper.conf.j2`, `conf/input/07-kafka.conf.j2`, `conf/input/09-monasca.conf.j2`, `conf/output/00-local.conf.j2`, `conf/output/01-es.conf.j2`, `conf/output/02-monasca.conf.j2`, `cron-logrotate-ansible.conf.j2`, `cron-logrotate-aodh.conf.j2`, `cron-logrotate-barbican.conf.j2`, `cron-logrotate-blazar.conf.j2`, `cron-logrotate-ceilometer.conf.j2` … (+63) |
| Handlers (definition order) | Restart fluentd container; Restart kolla-toolbox container; Initializing toolbox container using normal user; Restart cron container |
| Key variables | `enable_fluentd`, `enable_* (all, via td-agent/logrotate)`, `elasticsearch_address`, `enable_monasca` |
| Role dependencies | none |

<!-- END GENERATED -->

<!-- TODO editorial: related -->
