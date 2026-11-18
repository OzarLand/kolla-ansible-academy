---
title: Placement
---

# Placement

<!-- TODO editorial: intro -->

## Where to look

- **Fact sheet:** [fact sheet C §2](../reference/factsheets/c-glance-placement-cinder-horizon-heat.md#2-placement)
- **Dependencies:** [Component dependencies §3](dependencies.md#3-control-plane-services)
- **Image side:** [Kolla images
  §4](../concepts/kolla-images.md#4-one-shot-containers-what-the-environment-variables-run) (row `placement-api`),
  [Kolla images §5](../concepts/kolla-images.md#5-per-image-start-behaviour)
- **What the tag executes (`placement`):** [Tags §3](../risk/tags.md#3-what-a-tag-really-executes-master-table), row
  `<svc>`; [Tags §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), row
  `<svc>` API service
- **Scenario:** [Reconfigure a single service
  §2](../operations/reconfigure-a-service.md#2-execute-a-service-specific-tag-implicit-effects), [Reconfigure a single
  service §3](../operations/reconfigure-a-service.md#3-sequence-impact-risks-and-verification-of--t-svc-reconfigure)
- **Command:** [Command quick lookup by tag](../operations/command-quick-lookup.md)
- **Risks:** [R8](../risk/risk-register.md#r8), [R24](../risk/risk-register.md#r24)

## Service card

<!-- BEGIN GENERATED: tools/service_cards.py placement -->

| Item | Value |
|---|---|
| Play | site.yml:697 |
| Tags | placement |
| Play host patterns | placement-api |
| Node types in play (example inventory) | control |
| Node types running its containers | control |
| Containers | `placement_api` |
| deploy/reconfigure flow (`tasks/deploy.yml`) | register → clone (if) → config → check-containers → bootstrap → flush handlers |
| Task files | bootstrap.yml, bootstrap_service.yml, check-containers.yml, check.yml, clone.yml, config.yml, copy-certs.yml, deploy-containers.yml, deploy.yml, loadbalancer.yml, main.yml, precheck.yml, pull.yml, reconfigure.yml, register.yml, stop.yml, upgrade.yml |
| Templates | `migrate-db.rc.j2`, `placement-api-wsgi.conf.j2`, `placement-api.json.j2`, `placement.conf.j2` |
| Handlers (definition order) | Restart placement-api container |
| Key variables | `enable_placement` |
| Role dependencies | `common` (meta) |

<!-- END GENERATED -->

<!-- TODO editorial: related -->
