---
title: Octavia
---

# Octavia

<!-- TODO editorial: intro -->

## Where to look

- **Fact sheet:** [fact sheet D §2](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#2-octavia)
- **Dependencies:** [Component dependencies §3](dependencies.md#3-control-plane-services)
- **Image side:** [Kolla images
  §4](../concepts/kolla-images.md#4-one-shot-containers-what-the-environment-variables-run) (row `octavia-api`), [Kolla
  images §5](../concepts/kolla-images.md#5-per-image-start-behaviour)

## Service card

<!-- BEGIN GENERATED: tools/service_cards.py octavia -->

| Item | Value |
|---|---|
| Play | site.yml:1183 |
| Tags | octavia |
| Play host patterns | octavia-api, octavia-health-manager, octavia-housekeeping, octavia-worker |
| Node types in play (example inventory) | control |
| Node types running its containers | control |
| Containers | `octavia_api`, `octavia_health_manager`, `octavia_housekeeping`, `octavia_worker` |
| deploy/reconfigure flow (`tasks/deploy.yml`) | register → config → check-containers → bootstrap → flush handlers |
| Task files | bootstrap.yml, bootstrap_service.yml, check-containers.yml, check.yml, config.yml, copy-certs.yml, deploy-containers.yml, deploy.yml, loadbalancer.yml, main.yml, precheck.yml, pull.yml, reconfigure.yml, register.yml, stop.yml, upgrade.yml |
| Templates | `octavia-api.json.j2`, `octavia-health-manager.json.j2`, `octavia-housekeeping.json.j2`, `octavia-worker.json.j2`, `octavia.conf.j2` |
| Handlers (definition order) | Restart octavia-api container; Restart octavia-health-manager container; Restart octavia-housekeeping container; Restart octavia-worker container |
| Key variables | `enable_octavia`, `octavia_amp_*`, `octavia_network_interface` |
| Role dependencies | `common` (meta) |

<!-- END GENERATED -->

<!-- TODO editorial: related -->
