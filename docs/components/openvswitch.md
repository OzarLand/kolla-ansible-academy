---
title: Open vSwitch
---

# Open vSwitch

<!-- TODO editorial: intro -->

## Where to look

- **Fact sheet:** – (`ovs-dpdk`: [fact sheet A §6](../reference/factsheets/a-infra-lb-ovn.md#6-ovs-dpdk-role))
- **Dependencies:** [Component dependencies §2](dependencies.md#2-infrastructure-components), [Component dependencies
  §4](dependencies.md#4-networking-components-ml2ovs-default-ml2ovn-optional)
- **Image side:** [Kolla images §5](../concepts/kolla-images.md#5-per-image-start-behaviour) (rows `openvswitch-*`)
- **Also:** handlers: [Tags §5](../risk/tags.md#5-role--handler-map-core-services)
- **What the tag executes (`openvswitch`):** [Tags §3](../risk/tags.md#3-what-a-tag-really-executes-master-table) and
  [Tags §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), rows
  `openvswitch`
- **Scenario:** [Reconfigure Neutron §4](../operations/reconfigure-neutron.md#4-impact-on-networking) (row "Open
  vSwitch"), [Update container images §4](../operations/update-container-images.md#4-risks) (OVS image change)
- **Command:** [Reconfigure Neutron §1.1](../operations/reconfigure-neutron.md#11-neutron)
- **Risks:** [R7](../risk/risk-register.md#r7)

## Service card

<!-- BEGIN GENERATED: tools/service_cards.py openvswitch -->

| Item | Value |
|---|---|
| Play | site.yml:712 |
| Tags | openvswitch |
| Play host patterns | openvswitch |
| Node types in play (example inventory) | compute, network |
| Node types running its containers | compute, network |
| Containers | `openvswitch_db`, `openvswitch_vswitchd` |
| deploy/reconfigure flow (`tasks/deploy.yml`) | config-host → config → check-containers → flush handlers → post-config |
| Task files | check-containers.yml, check.yml, config-host.yml, config.yml, deploy-containers.yml, deploy.yml, main.yml, post-config.yml, precheck.yml, pull.yml, reconfigure.yml, stop.yml, upgrade.yml |
| Templates | `openvswitch-db-server.json.j2`, `openvswitch-vswitchd.json.j2`, `start-ovs.j2`, `start-ovsdb-server.j2` |
| Handlers (definition order) | Restart openvswitch-db-server container; Waiting for openvswitch_db service to be ready; Restart openvswitch-vswitchd container |
| Key variables | `enable_openvswitch`, `neutron_bridge_name`, `neutron_external_interface`, `computes_need_external_bridge` |
| Role dependencies | `common` (meta) |

<!-- END GENERATED -->

<!-- TODO editorial: related -->
