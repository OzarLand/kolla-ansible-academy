---
title: iscsid / tgtd
---

# iscsid / tgtd

<!-- TODO editorial: intro -->

## Where to look

- **Fact sheet:** [fact sheet D
  §5.2](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#52-iscsi-iscsid-tgtd)
- **Dependencies:** [Component dependencies §2](dependencies.md#2-infrastructure-components), [Component dependencies
  §5](dependencies.md#5-compute-node-dependency-summary)
- **Image side:** [Kolla images §5](../concepts/kolla-images.md#5-per-image-start-behaviour) (rows `iscsid`, `tgtd`)
- **What the tag executes (`iscsi`):** [Tags §3](../risk/tags.md#3-what-a-tag-really-executes-master-table) and [Tags
  §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), rows `iscsi`
- **Scenario:** [Reconfigure a single service
  §3](../operations/reconfigure-a-service.md#3-sequence-impact-risks-and-verification-of--t-svc-reconfigure) (VM impact:
  [NOT AVAILABLE])

## Service card

<!-- BEGIN GENERATED: tools/service_cards.py iscsi -->

| Item | Value |
|---|---|
| Play | site.yml:512 |
| Tags | iscsi |
| Play host patterns | iscsid, tgtd |
| Node types in play (example inventory) | compute, control, storage |
| Node types running its containers | compute, control, storage |
| Containers | `iscsid`, `tgtd` |
| deploy/reconfigure flow (`tasks/deploy.yml`) | config-host → config → check-containers → flush handlers |
| Task files | check-containers.yml, check.yml, config-host.yml, config.yml, deploy-containers.yml, deploy.yml, main.yml, precheck.yml, pull.yml, reconfigure.yml, stop.yml, upgrade.yml |
| Templates | `iscsid.json.j2`, `tgtd.json.j2` |
| Handlers (definition order) | Restart iscsid container; Restart tgtd container |
| Key variables | `enable_iscsid`, `enable_cinder_backend_lvm` |
| Role dependencies | `common` (meta) |

<!-- END GENERATED -->

<!-- TODO editorial: related -->
