---
title: Horizon
---

# Horizon

<!-- TODO editorial: intro -->

## Where to look

- **Fact sheet:** [fact sheet C §4](../reference/factsheets/c-glance-placement-cinder-horizon-heat.md#4-horizon)
- **Dependencies:** [Component dependencies §3](dependencies.md#3-control-plane-services)
- **Image side:** [Kolla images
  §4](../concepts/kolla-images.md#4-one-shot-containers-what-the-environment-variables-run) (row `horizon`), [Kolla
  images §5.2](../concepts/kolla-images.md#52-horizon-static-assets)
- **What the tag executes (`horizon`):** [Tags §3](../risk/tags.md#3-what-a-tag-really-executes-master-table), row
  `<svc>` and the paragraph below the table; [Tags
  §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), row `<svc>` API
  service
- **Scenario:** [Reconfigure a single service
  §2](../operations/reconfigure-a-service.md#2-execute-a-service-specific-tag-implicit-effects)
- **Risks:** [R8](../risk/risk-register.md#r8), [R24](../risk/risk-register.md#r24)

## Service card

<!-- BEGIN GENERATED: tools/service_cards.py horizon -->

| Item | Value |
|---|---|
| Play | site.yml:806 |
| Tags | horizon |
| Play host patterns | horizon |
| Node types in play (example inventory) | control |
| Node types running its containers | control |
| Containers | `horizon` |
| deploy/reconfigure flow (`tasks/deploy.yml`) | config → check-containers → clone (if) → bootstrap (if) → flush handlers |
| Task files | bootstrap.yml, bootstrap_service.yml, check-containers.yml, check.yml, clone.yml, config.yml, copy-certs.yml, deploy-containers.yml, deploy.yml, loadbalancer.yml, main.yml, policy_item.yml, precheck.yml, pull.yml, reconfigure.yml, stop.yml, upgrade.yml |
| Templates | `custom_local_settings.j2`, `horizon.conf.j2`, `horizon.json.j2`, `local_settings.j2` |
| Handlers (definition order) | Restart horizon container |
| Key variables | `enable_horizon`, `enable_horizon_*`, `horizon_backend_database` |
| Role dependencies | `common` (meta) |

<!-- END GENERATED -->

<!-- TODO editorial: related -->
