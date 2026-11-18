---
title: Tag index
---

# Tag index

For each tag: where [Tags](tags.md) says what it executes, the [Operations](../operations/index.md) scenario that covers
it, the [Operations](../operations/index.md) command, the [Risk register](risk-register.md) risks, and its service card.
The [Tags](tags.md) tables have one row per tag; the row to read is named after the link. Risk numbers link to the risk
matrix, [Risk register](risk-register.md#matrix).

| Tag | What it executes ([Tags](tags.md)) | Scenario ([Operations](../operations/index.md)) | Command ([Operations](../operations/index.md)) | Risks ([Risk register](risk-register.md)) | Service card |
|---|---|---|---|---|---|
| *(no tag)* | [Tags §3](tags.md#3-what-a-tag-really-executes-master-table), row *(no tag)* | [Apply `common` changes (fluentd, cron, kolla_toolbox) §3](../operations/apply-common-changes.md#3-how-common-actually-reaches-hosts) (`common` on all hosts), [Update container images §2](../operations/update-container-images.md#2-how-image-pulling-and-recreation-work-code) (new `openstack_tag` and `deploy`) | [Command quick lookup by tag](../operations/command-quick-lookup.md), row `reconfigure` (no tag) | [R2](risk-register.md#r2), [R12](risk-register.md#r12) | – |
| `common` | → [Common: fluentd, cron, kolla_toolbox](../components/common.md#where-to-look) | | | | [Fluentd / cron / kolla-toolbox](../components/common.md#service-card) |
| `nova` | → [Nova](../components/nova.md#where-to-look) | | | | [Nova (API level)](../components/nova.md#nova-api-level--role-nova), [Nova (cell level)](../components/nova.md#nova-cell-level--role-nova-cell) |
| `nova-api` | → [Nova](../components/nova.md#where-to-look) | | | | [Nova (API level)](../components/nova.md#nova-api-level--role-nova) |
| `nova-cell` | → [Nova](../components/nova.md#where-to-look) | | | | [Nova (cell level)](../components/nova.md#nova-cell-level--role-nova-cell) |
| `nova-bootstrap`, `nova-reload`, `nova-online-data-migrations` (with their `-api-`/`-cell-` variants) and `nova-refresh-scheduler-cell-cache` | → [Nova](../components/nova.md#where-to-look) | | | | [Nova (API level)](../components/nova.md#nova-api-level--role-nova), [Nova (cell level)](../components/nova.md#nova-cell-level--role-nova-cell) |
| `neutron` | → [Neutron](../components/neutron.md#where-to-look) | | | | [Neutron](../components/neutron.md#service-card) |
| `openvswitch` | → [Open vSwitch](../components/openvswitch.md#where-to-look) | | | | [Open vSwitch](../components/openvswitch.md#service-card) |
| `ovn` | → [OVN](../components/ovn.md#where-to-look) | | | | [OVN](../components/ovn.md#service-card) |
| `haproxy` | → [HAProxy + Keepalived](../components/haproxy-keepalived.md#where-to-look) | | | | [HAProxy + Keepalived](../components/haproxy-keepalived.md#service-card) |
| `keystone` | → [Keystone](../components/keystone.md#where-to-look) | | | | [Keystone](../components/keystone.md#service-card) |
| `glance` | → [Glance](../components/glance.md#where-to-look) | | | | [Glance](../components/glance.md#service-card) |
| `cinder` | → [Cinder](../components/cinder.md#where-to-look) | | | | [Cinder](../components/cinder.md#service-card) |
| `heat` | → [Heat](../components/heat.md#where-to-look) | | | | [Heat](../components/heat.md#service-card) |
| `placement` | → [Placement](../components/placement.md#where-to-look) | | | | [Placement](../components/placement.md#service-card) |
| `horizon` | → [Horizon](../components/horizon.md#where-to-look) | | | | [Horizon](../components/horizon.md#service-card) |
| `mariadb` | → [MariaDB/Galera](../components/mariadb.md#where-to-look) | | | | [MariaDB/Galera](../components/mariadb.md#service-card) |
| `rabbitmq` | → [RabbitMQ](../components/rabbitmq.md#where-to-look) | | | | [RabbitMQ](../components/rabbitmq.md#service-card) |
| `memcached` / `memcache` | → [Memcached](../components/memcached.md#where-to-look) | | | | [Memcached](../components/memcached.md#service-card) |
| `chrony` | → [Chrony](../components/chrony.md#where-to-look) | | | | [Chrony](../components/chrony.md#service-card) |
| `iscsi` | → [iscsid / tgtd](../components/iscsi.md#where-to-look) | | | | [iscsid / tgtd](../components/iscsi.md#service-card) |
| `service-rabbitmq` | [Tags §3](tags.md#3-what-a-tag-really-executes-master-table), row `service-rabbitmq` (not usable as a selector) | – | – | – | – |
| `baremetal` (`bootstrap-servers`) | [Tags §3](tags.md#3-what-a-tag-really-executes-master-table) and [Tags §3.1](tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), rows `baremetal` | [Add a compute node §2](../operations/add-a-compute-node.md#2-add-a-compute-node) | [Add a compute node §1.1](../operations/add-a-compute-node.md#11-add-a-compute-node) | [R14](risk-register.md#r14) | – |

Which tags reach the compute hosts is the "Target hosts" column of [Tags
§3](tags.md#3-what-a-tag-really-executes-master-table). Handlers are never filtered by tags ([Tags
§2.2](tags.md#22-handlers-ignore-tags-code)), and a tag never restricts which hosts a play targets ([Tags
§4](tags.md#4-practical-consequences)).
