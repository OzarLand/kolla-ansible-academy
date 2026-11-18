---
title: RabbitMQ
---

# RabbitMQ

<!-- TODO editorial: intro -->

## Where to look

- **Fact sheet:** [fact sheet B
  §2](../reference/factsheets/b-mariadb-rabbitmq-keystone.md#2-rabbitmq-ansiblerolesrabbitmq-used-twice)
- **Dependencies:** [Component dependencies
  §1](dependencies.md#1-the-shared-substrate-what-every-openstack-service-uses), [Component dependencies
  §2](dependencies.md#2-infrastructure-components)
- **Image side:** [Kolla images
  §4](../concepts/kolla-images.md#4-one-shot-containers-what-the-environment-variables-run) (row `rabbitmq`), [Kolla
  images §5](../concepts/kolla-images.md#5-per-image-start-behaviour)
- **Also:** handlers: [Tags §5](../risk/tags.md#5-role--handler-map-core-services)
- **What the tag executes (`rabbitmq`):** [Tags §3](../risk/tags.md#3-what-a-tag-really-executes-master-table) and [Tags
  §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), rows `rabbitmq`
- **Scenario:** [Change control-plane membership
  §2](../operations/change-control-plane-membership.md#2-change-control-plane-membership-add-or-remove-a-controller)
- **Command:** [Change control-plane membership
  §1.1](../operations/change-control-plane-membership.md#11-remove-or-replace-a-controller), [Command quick lookup by
  tag](../operations/command-quick-lookup.md)
- **Risks:** [R3](../risk/risk-register.md#r3), [R10](../risk/risk-register.md#r10)

## Service card

<!-- BEGIN GENERATED: tools/service_cards.py rabbitmq -->

| Item | Value |
|---|---|
| Play | site.yml:535, site.yml:555 |
| Tags | rabbitmq |
| Play host patterns | rabbitmq, outward-rabbitmq |
| Node types in play (example inventory) | control |
| Node types running its containers | control |
| Containers | `rabbitmq`, `outward_rabbitmq` |
| deploy/reconfigure flow (`tasks/deploy.yml`) | config → check-containers → bootstrap → flush handlers |
| Task files | bootstrap.yml, check-containers.yml, check.yml, config.yml, deploy-containers.yml, deploy.yml, loadbalancer.yml, main.yml, precheck.yml, pull.yml, reconfigure.yml, restart_services.yml, stop.yml, upgrade.yml |
| Templates | `advanced.config.j2`, `definitions.json.j2`, `erl_inetrc.j2`, `rabbitmq-env.conf.j2`, `rabbitmq.conf.j2`, `rabbitmq.json.j2` |
| Handlers (definition order) | Restart first rabbitmq container; Restart remaining rabbitmq containers |
| Key variables | `enable_rabbitmq`, `om_rpc_*`, `rabbitmq_*`, `rpc_transport_url` |
| Role dependencies | `common` (meta) |

<!-- END GENERATED -->

<!-- TODO editorial: related -->
