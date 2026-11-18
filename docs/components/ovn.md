---
title: OVN
---

# OVN

<!-- TODO editorial: intro -->

## Where to look

- **Fact sheet:** [fact sheet A §5](../reference/factsheets/a-infra-lb-ovn.md#5-ovn-role)
- **Dependencies:** [Component dependencies §2](dependencies.md#2-infrastructure-components), [Component dependencies
  §4](dependencies.md#4-networking-components-ml2ovs-default-ml2ovn-optional)
- **Image side:** [Kolla images §5](../concepts/kolla-images.md#5-per-image-start-behaviour) (rows `ovn-*`)
- **What the tag executes (`ovn`):** [Tags §3](../risk/tags.md#3-what-a-tag-really-executes-master-table) and [Tags
  §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), rows `ovn`
- **Scenario:** [Reconfigure Neutron §4](../operations/reconfigure-neutron.md#4-impact-on-networking) (row "OVN")

## Service card

<!-- BEGIN GENERATED: tools/service_cards.py ovn -->

| Item | Value |
|---|---|
| Play | site.yml:734 |
| Tags | ovn |
| Play host patterns | ovn-controller, ovn-nb-db, ovn-northd, ovn-sb-db |
| Node types in play (example inventory) | compute, control, network |
| Node types running its containers | compute, control, network |
| Containers | `ovn_controller`, `ovn_northd`, `ovn_nb_db`, `ovn_sb_db` |
| deploy/reconfigure flow (`tasks/deploy.yml`) | config → check-containers → bootstrap → flush handlers |
| Task files | bootstrap.yml, check-containers.yml, check.yml, config.yml, deploy-containers.yml, deploy.yml, main.yml, precheck.yml, pull.yml, reconfigure.yml, stop.yml, upgrade.yml |
| Templates | `ovn-controller.json.j2`, `ovn-nb-db.json.j2`, `ovn-northd.json.j2`, `ovn-sb-db.json.j2` |
| Handlers (definition order) | Restart ovn-nb-db container; Restart ovn-sb-db container; Wait for ovn-nb-db; Wait for ovn-sb-db; Restart ovn-northd container; Restart ovn-controller container |
| Key variables | `enable_ovn`, `neutron_plugin_agent: ovn`, `neutron_ovn_distributed_fip` |
| Role dependencies | `common` (meta) |

<!-- END GENERATED -->

<!-- TODO editorial: related -->
