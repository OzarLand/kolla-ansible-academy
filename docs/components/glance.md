---
title: Glance
---

# Glance

<!-- TODO editorial: intro -->

## Where to look

- **Fact sheet:** [fact sheet C §1](../reference/factsheets/c-glance-placement-cinder-horizon-heat.md#1-glance)
- **Dependencies:** [Component dependencies §3](dependencies.md#3-control-plane-services)
- **Image side:** [Kolla images
  §4](../concepts/kolla-images.md#4-one-shot-containers-what-the-environment-variables-run) (row `glance-api`), [Kolla
  images §5](../concepts/kolla-images.md#5-per-image-start-behaviour)
- **What the tag executes (`glance`):** [Tags §3](../risk/tags.md#3-what-a-tag-really-executes-master-table), row
  `<svc>`; [Tags §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), row
  `<svc>` API service
- **Scenario:** [Reconfigure a single service
  §2](../operations/reconfigure-a-service.md#2-execute-a-service-specific-tag-implicit-effects), [Reconfigure a single
  service §3](../operations/reconfigure-a-service.md#3-sequence-impact-risks-and-verification-of--t-svc-reconfigure)
- **Command:** [Command quick lookup by tag](../operations/command-quick-lookup.md)
- **Risks:** [R20](../risk/risk-register.md#r20), [R21](../risk/risk-register.md#r21),
  [R8](../risk/risk-register.md#r8), [R24](../risk/risk-register.md#r24)

## Service card

<!-- BEGIN GENERATED: tools/service_cards.py glance -->

| Item | Value |
|---|---|
| Play | site.yml:657 |
| Tags | glance |
| Play host patterns | glance-api |
| Node types in play (example inventory) | control |
| Node types running its containers | control |
| Containers | `glance_api`, `glance_tls_proxy` |
| deploy/reconfigure flow (`tasks/deploy.yml`) | register → config → check-containers → clone (if) → bootstrap → flush handlers → check |
| Task files | bootstrap.yml, bootstrap_service.yml, check-containers.yml, check.yml, clone.yml, config.yml, copy-certs.yml, deploy-containers.yml, deploy.yml, external_ceph.yml, legacy_upgrade.yml, loadbalancer.yml, main.yml, precheck.yml, pull.yml, reconfigure.yml, register.yml, rolling_upgrade.yml, stop.yml, stop_service.yml, upgrade.yml |
| Templates | `glance-api.conf.j2`, `glance-api.json.j2`, `glance-cache.conf.j2`, `glance-swift.conf.j2`, `glance-tls-proxy.cfg.j2`, `glance-tls-proxy.json.j2` |
| Handlers (definition order) | Restart glance-api container; Restart glance-tls-proxy container |
| Key variables | `enable_glance`, `glance_backend_*`, `glance_api_hosts`, `glance_enable_rolling_upgrade` |
| Role dependencies | `common` (meta) |

<!-- END GENERATED -->

<!-- TODO editorial: related -->
