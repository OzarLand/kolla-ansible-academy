---
title: Change control-plane membership
---

# Change control-plane membership

<!-- TODO editorial: intro, key answers -->

## 1. Commands

### 1.1 Remove or replace a controller

- Changing the `rabbitmq` membership changes the transport URL everywhere, and changing `memcached` changes the memcache
  server lists. In the default inventory both are children of `control`, so a controller change does both. That restarts
  all nova and neutron containers on all computes, and most control-plane services ([R3](../risk/risk-register.md#r3)
  and [R4](../risk/risk-register.md#r4) in [Risk register](../risk/risk-register.md)). A `memcached`-only change does
  not touch nova-compute (the compute `nova.conf` has no memcache list) but still restarts the neutron agents on
  computes (`neutron.conf`).
- Galera and RabbitMQ membership changes need their own procedures. Ussuri has no automated member removal (fact sheets
  [A](../reference/factsheets/a-infra-lb-ovn.md), [B](../reference/factsheets/b-mariadb-rabbitmq-keystone.md)).

## 2. Change control-plane membership (add or remove a controller)

[CODE] Adding `control04` to `control` (and therefore to `rabbitmq`, `memcached`, `mariadb`, …) and running
`-t nova,neutron reconfigure`, read from the templates:

- **Restarted on every compute:** nova_compute, nova_libvirt, nova_ssh, neutron_openvswitch_agent.
- **Restarted on every controller:** all nova and neutron containers.
- **Restarted on both network nodes:** all neutron agents; haproxy (backend lists changed).
- **Why:** `rpc_transport_url` lists every RabbitMQ host (`group_vars/all.yml:206`,
  `roles/nova-cell/defaults/main.yml:174`), and the haproxy backends list every API host
  (`roles/haproxy-config/templates/haproxy_single_service_split.cfg.j2:93`). Loop-notify ([Tags
  §2.4](../risk/tags.md#24-loop-notify-one-changed-item-notifies-the-handlers-of-all-items-code)) restarts the sibling
  containers.
- **Plus:** RabbitMQ and Galera cluster joins, which need their own plays (`-t rabbitmq`, `-t mariadb`). Galera
  membership changes restart all DB nodes (`galera.cnf` lists all nodes, [fact sheet B §1.4][sheet-b-14] and
  [§1.8](../reference/factsheets/b-mariadb-rabbitmq-keystone.md#18-operationally-notable-behaviour-risks-and-oddities)
  item 11).

**Takeaway:** controller membership changes are fleet-wide restart events for every messaging consumer. Schedule them
as such, and batch the compute side.

<!-- TODO editorial: related -->

[sheet-b-14]: ../reference/factsheets/b-mariadb-rabbitmq-keystone.md#14-config-files-generated-ansiblerolesmariadbtasksconfigyml
