---
title: Heat
---

# Heat

<!-- TODO editorial: intro -->

## Where to look

- **Fact sheet:** [fact sheet C §5](../reference/factsheets/c-glance-placement-cinder-horizon-heat.md#5-heat)
- **Dependencies:** [Component dependencies §3](dependencies.md#3-control-plane-services)
- **Image side:** [Kolla images
  §4](../concepts/kolla-images.md#4-one-shot-containers-what-the-environment-variables-run) (row `heat-api`), [Kolla
  images §5](../concepts/kolla-images.md#5-per-image-start-behaviour)
- **What the tag executes (`heat`):** [Tags §3](../risk/tags.md#3-what-a-tag-really-executes-master-table), row `<svc>`;
  [Tags §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), row `<svc>` API
  service
- **Scenario:** [Reconfigure a single service
  §2](../operations/reconfigure-a-service.md#2-execute-a-service-specific-tag-implicit-effects), [Reconfigure a single
  service §3](../operations/reconfigure-a-service.md#3-sequence-impact-risks-and-verification-of--t-svc-reconfigure)
- **Risks:** [R8](../risk/risk-register.md#r8), [R24](../risk/risk-register.md#r24)

## Service card

<!-- BEGIN GENERATED: tools/service_cards.py heat -->

| Item | Value |
|---|---|
| Play | site.yml:793 |
| Tags | heat |
| Play host patterns | heat-api, heat-api-cfn, heat-engine |
| Node types in play (example inventory) | control |
| Node types running its containers | control |
| Containers | `heat_api`, `heat_api_cfn`, `heat_engine` |
| deploy/reconfigure flow (`tasks/deploy.yml`) | register → config → check-containers → clone (if) → bootstrap → flush handlers |
| Task files | bootstrap.yml, bootstrap_service.yml, check-containers.yml, check.yml, clone.yml, config.yml, copy-certs.yml, deploy-containers.yml, deploy.yml, loadbalancer.yml, main.yml, precheck.yml, pull.yml, reconfigure.yml, register.yml, stop.yml, upgrade.yml |
| Templates | `heat-api-cfn.json.j2`, `heat-api.json.j2`, `heat-engine.json.j2`, `heat.conf.j2`, `wsgi-heat-api-cfn.conf.j2`, `wsgi-heat-api.conf.j2` |
| Handlers (definition order) | Restart heat-api container; Restart heat-api-cfn container; Restart heat-engine container |
| Key variables | `enable_heat`, `heat_*_external_fqdn` |
| Role dependencies | `common` (meta) |

<!-- END GENERATED -->

<!-- TODO editorial: related -->
