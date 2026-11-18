---
title: Memcached
---

# Memcached

<!-- TODO editorial: intro -->

## Where to look

- **Fact sheet:** [fact sheet A §3](../reference/factsheets/a-infra-lb-ovn.md#3-memcached-role)
- **Dependencies:** [Component dependencies
  §1](dependencies.md#1-the-shared-substrate-what-every-openstack-service-uses), [Component dependencies
  §2](dependencies.md#2-infrastructure-components)
- **Image side:** [Kolla images §5](../concepts/kolla-images.md#5-per-image-start-behaviour) (row `memcached`)
- **What the tag executes (`memcached` / `memcache`):** [Tags
  §3](../risk/tags.md#3-what-a-tag-really-executes-master-table) and [Tags
  §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), rows `memcached` /
  `memcache`
- **Scenario:** [Change control-plane membership
  §2](../operations/change-control-plane-membership.md#2-change-control-plane-membership-add-or-remove-a-controller),
  [Reconfigure Neutron §3](../operations/reconfigure-neutron.md#3-what-restarts-code)
- **Command:** [Change control-plane membership
  §1.1](../operations/change-control-plane-membership.md#11-remove-or-replace-a-controller)
- **Risks:** [R4](../risk/risk-register.md#r4)

## Service card

<!-- BEGIN GENERATED: tools/service_cards.py memcached -->

| Item | Value |
|---|---|
| Play | site.yml:481 |
| Tags | memcache, memcached |
| Play host patterns | memcached |
| Node types in play (example inventory) | control |
| Node types running its containers | control |
| Containers | `memcached` |
| deploy/reconfigure flow (`tasks/deploy.yml`) | config → check-containers |
| Task files | check-containers.yml, check.yml, config.yml, deploy-containers.yml, deploy.yml, loadbalancer.yml, main.yml, precheck.yml, pull.yml, reconfigure.yml, stop.yml, upgrade.yml |
| Templates | `memcached.json.j2` |
| Handlers (definition order) | Restart memcached container |
| Key variables | `enable_memcached`, `memcached_port` |
| Role dependencies | none |

<!-- END GENERATED -->

<!-- TODO editorial: related -->
