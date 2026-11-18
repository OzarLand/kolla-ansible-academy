---
title: Chrony
---

# Chrony

<!-- TODO editorial: intro -->

## Where to look

- **Fact sheet:** [fact sheet A §4](../reference/factsheets/a-infra-lb-ovn.md#4-chrony-role)
- **Dependencies:** [Component dependencies §2](dependencies.md#2-infrastructure-components), [Component dependencies
  §5](dependencies.md#5-compute-node-dependency-summary)
- **Image side:** [Kolla images §5](../concepts/kolla-images.md#5-per-image-start-behaviour) (row `chrony`)
- **What the tag executes (`chrony`):** [Tags §3](../risk/tags.md#3-what-a-tag-really-executes-master-table) and [Tags
  §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), rows `chrony`
- **Scenario:** [Apply `common` changes (fluentd, cron, kolla_toolbox)
  §3](../operations/apply-common-changes.md#3-how-common-actually-reaches-hosts) (the way to push `common` changes)
- **Command:** [Apply `common` changes (fluentd, cron, kolla_toolbox)
  §1.1](../operations/apply-common-changes.md#11-apply-common-changes-fluentd-cron-kolla_toolbox)
- **Risks:** through `common`: [R2](../risk/risk-register.md#r2), [R25](../risk/risk-register.md#r25)

## Service card

<!-- BEGIN GENERATED: tools/service_cards.py chrony -->

| Item | Value |
|---|---|
| Play | site.yml:114 |
| Tags | chrony |
| Play host patterns | chrony-server, chrony |
| Node types in play (example inventory) | compute, control, monitoring, network, storage |
| Node types running its containers | compute, control, monitoring, network, storage |
| Containers | `chrony` |
| deploy/reconfigure flow (`tasks/deploy.yml`) | config → check-containers → flush handlers |
| Task files | check-containers.yml, check.yml, config.yml, deploy-containers.yml, deploy.yml, main.yml, precheck.yml, pull.yml, reconfigure.yml, stop.yml, upgrade.yml |
| Templates | `chrony.conf.j2`, `chrony.json.j2` |
| Handlers (definition order) | Restart chrony container |
| Key variables | `enable_chrony`, `external_ntp_servers` |
| Role dependencies | `common` (meta) |

<!-- END GENERATED -->

<!-- TODO editorial: related -->
