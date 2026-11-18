---
title: Manila
---

# Manila

<!-- TODO editorial: intro -->

## Where to look

- **Fact sheet:** [fact sheet D §4](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#4-manila)
- **Dependencies:** [Component dependencies §3](dependencies.md#3-control-plane-services)
- **Image side:** [Kolla images
  §4](../concepts/kolla-images.md#4-one-shot-containers-what-the-environment-variables-run) (row `manila-api`), [Kolla
  images §5](../concepts/kolla-images.md#5-per-image-start-behaviour)

## Service card

<!-- BEGIN GENERATED: tools/service_cards.py manila -->

| Item | Value |
|---|---|
| Play | site.yml:917 |
| Tags | manila |
| Play host patterns | manila-api, manila-data, manila-share, manila-scheduler |
| Node types in play (example inventory) | control, network |
| Node types running its containers | control, network |
| Containers | `manila_api`, `manila_scheduler`, `manila_share`, `manila_data` |
| deploy/reconfigure flow (`tasks/deploy.yml`) | clone (if) → register → config → check-containers → bootstrap → flush handlers → fix_cephfs_owner (if) |
| Task files | bootstrap.yml, bootstrap_service.yml, check-containers.yml, check.yml, clone.yml, config.yml, copy-certs.yml, deploy-containers.yml, deploy.yml, external_ceph.yml, fix_cephfs_owner.yml, loadbalancer.yml, main.yml, precheck.yml, pull.yml, reconfigure.yml, register.yml, stop.yml, upgrade.yml |
| Templates | `manila-api.json.j2`, `manila-data.json.j2`, `manila-scheduler.json.j2`, `manila-share.conf.j2`, `manila-share.json.j2`, `manila.conf.j2` |
| Handlers (definition order) | Restart manila-api container; Restart manila-data container; Restart manila-scheduler container; Restart manila-share container |
| Key variables | `enable_manila`, `enable_manila_backend_*` |
| Role dependencies | `common` (meta) |

<!-- END GENERATED -->

<!-- TODO editorial: related -->
