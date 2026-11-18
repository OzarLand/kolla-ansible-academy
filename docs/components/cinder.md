---
title: Cinder
---

# Cinder

<!-- TODO editorial: intro -->

## Where to look

- **Fact sheet:** [fact sheet C §3](../reference/factsheets/c-glance-placement-cinder-horizon-heat.md#3-cinder)
- **Dependencies:** [Component dependencies §3](dependencies.md#3-control-plane-services)
- **Image side:** [Kolla images
  §4](../concepts/kolla-images.md#4-one-shot-containers-what-the-environment-variables-run) (row `cinder-api`), [Kolla
  images §5](../concepts/kolla-images.md#5-per-image-start-behaviour)
- **What the tag executes (`cinder`):** [Tags §3](../risk/tags.md#3-what-a-tag-really-executes-master-table), row
  `<svc>`; [Tags §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), row
  `<svc>` API service
- **Scenario:** [Reconfigure a single service
  §2](../operations/reconfigure-a-service.md#2-execute-a-service-specific-tag-implicit-effects), [Reconfigure a single
  service §3](../operations/reconfigure-a-service.md#3-sequence-impact-risks-and-verification-of--t-svc-reconfigure)
- **Risks:** [R8](../risk/risk-register.md#r8), [R24](../risk/risk-register.md#r24)

## Service card

<!-- BEGIN GENERATED: tools/service_cards.py cinder -->

| Item | Value |
|---|---|
| Play | site.yml:683 |
| Tags | cinder |
| Play host patterns | cinder-api, cinder-backup, cinder-scheduler, cinder-volume |
| Node types in play (example inventory) | control, storage |
| Node types running its containers | control, storage |
| Containers | `cinder_api`, `cinder_scheduler`, `cinder_volume`, `cinder_backup` |
| deploy/reconfigure flow (`tasks/deploy.yml`) | register → config → check-containers → clone (if) → bootstrap → flush handlers → check |
| Task files | bootstrap.yml, bootstrap_service.yml, check-containers.yml, check.yml, clone.yml, config.yml, copy-certs.yml, deploy-containers.yml, deploy.yml, external_ceph.yml, loadbalancer.yml, main.yml, precheck.yml, pull.yml, reconfigure.yml, register.yml, stop.yml, upgrade.yml |
| Templates | `cinder-api.json.j2`, `cinder-backup.json.j2`, `cinder-scheduler.json.j2`, `cinder-volume.json.j2`, `cinder-wsgi.conf.j2`, `cinder.conf.j2` |
| Handlers (definition order) | Restart cinder-api container; Restart cinder-scheduler container; Restart cinder-volume container; Restart cinder-backup container |
| Key variables | `enable_cinder`, `enable_cinder_backend_*`, `cinder_backend_ceph`, `cinder_backup_driver`, `cinder_coordination_backend` |
| Role dependencies | `common` (meta) |

<!-- END GENERATED -->

<!-- TODO editorial: related -->
