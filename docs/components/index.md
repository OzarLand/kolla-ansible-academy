---
title: Components
---

# Components

<!-- TODO editorial -->

## Raw material (to integrate)

<!-- source: old annex/index.md, section "Service index" (the other columns are on the component pages) -->

One row per service card. "Fact sheet" is the per-role evidence; "–" means no fact sheet covers the role, and the last
column says where it is traced instead.

| Service (role) | Service card |
|---|---|
| MariaDB/Galera (`mariadb`) | [MariaDB/Galera](mariadb.md#service-card) |
| RabbitMQ (`rabbitmq`) | [RabbitMQ](rabbitmq.md#service-card) |
| Memcached (`memcached`) | [Memcached](memcached.md#service-card) |
| HAProxy + Keepalived (`haproxy`) | [HAProxy + Keepalived](haproxy-keepalived.md#service-card) |
| Fluentd / cron / kolla-toolbox (`common`) | [Fluentd / cron / kolla-toolbox](common.md#service-card) |
| Open vSwitch (`openvswitch`) | [Open vSwitch](openvswitch.md#service-card) |
| OVN (`ovn`) | [OVN](ovn.md#service-card) |
| Chrony (`chrony`) | [Chrony](chrony.md#service-card) |
| iscsid / tgtd (`iscsi`) | [iscsid / tgtd](iscsi.md#service-card) |
| Keystone (`keystone`) | [Keystone](keystone.md#service-card) |
| Glance (`glance`) | [Glance](glance.md#service-card) |
| Placement (`placement`) | [Placement](placement.md#service-card) |
| Nova (API level) (`nova`) | [Nova (API level)](nova.md#nova-api-level--role-nova) |
| Nova (cell level) (`nova-cell`) | [Nova (cell level)](nova.md#nova-cell-level--role-nova-cell) |
| Neutron (`neutron`) | [Neutron](neutron.md#service-card) |
| Cinder (`cinder`) | [Cinder](cinder.md#service-card) |
| Horizon (`horizon`) | [Horizon](horizon.md#service-card) |
| Heat (`heat`) | [Heat](heat.md#service-card) |
| Barbican (`barbican`) | [Barbican](barbican.md#service-card) |
| Octavia (`octavia`) | [Octavia](octavia.md#service-card) |
| Swift (`swift`) | [Swift](swift.md#service-card) |
| Manila (`manila`) | [Manila](manila.md#service-card) |

Other roles: the roles that place containers on compute hosts (ceilometer, multipathd, collectd, telegraf, prometheus
exporters, masakari, zun, kuryr, cyborg, skydive, monasca, nova-hyperv) are in [fact sheet D
§5](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#50-summary-table-compute-side);
`bootstrap-servers` and the operational playbooks are in [fact sheet
E](../reference/factsheets/e-host-bootstrap-ops-playbooks.md); every play, container, role and handler is listed in
[Generated inventory](../reference/generated-inventory.md).

<!-- source: old annex/service-cards.md, introduction -->

For each core service: Kolla role, play in `site.yml`, tags, task flow for `deploy`/`reconfigure`, templates, handlers, key variables, and the node types its play touches with the Ussuri example `multinode` inventory. "Play hosts" = every host matched by the play's host patterns (before `enable_*` filtering). "Container hosts" = hosts where at least one container of the role is placed (group-based placement; `host_in_groups` expressions are summarised by their groups).
