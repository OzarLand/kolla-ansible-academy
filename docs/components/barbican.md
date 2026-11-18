---
title: Barbican
---

# Barbican

<!-- TODO editorial: intro -->

## Where to look

- **Fact sheet:** [fact sheet D §1](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#1-barbican)
- **Dependencies:** [Component dependencies §3](dependencies.md#3-control-plane-services)
- **Image side:** [Kolla images
  §4](../concepts/kolla-images.md#4-one-shot-containers-what-the-environment-variables-run) (row `barbican-api`), [Kolla
  images §5](../concepts/kolla-images.md#5-per-image-start-behaviour)

## Service card

<!-- BEGIN GENERATED: tools/service_cards.py barbican -->

| Item | Value |
|---|---|
| Play | site.yml:995 |
| Tags | barbican |
| Play host patterns | barbican-api, barbican-keystone-listener, barbican-worker |
| Node types in play (example inventory) | control |
| Node types running its containers | control |
| Containers | `barbican_api`, `barbican_keystone_listener`, `barbican_worker` |
| deploy/reconfigure flow (`tasks/deploy.yml`) | register → config → check-containers → clone (if) → bootstrap → flush handlers |
| Task files | bootstrap.yml, bootstrap_service.yml, check-containers.yml, check.yml, clone.yml, config.yml, copy-certs.yml, deploy-containers.yml, deploy.yml, loadbalancer.yml, main.yml, precheck.yml, pull.yml, reconfigure.yml, register.yml, stop.yml, upgrade.yml |
| Templates | `barbican-api.ini.j2`, `barbican-api.json.j2`, `barbican-keystone-listener.json.j2`, `barbican-worker.json.j2`, `barbican.conf.j2` |
| Handlers (definition order) | Restart barbican-api container; Restart barbican-keystone-listener container; Restart barbican-worker container |
| Key variables | `enable_barbican`, `barbican_crypto_key (passwords.yml)` |
| Role dependencies | `common` (meta) |

<!-- END GENERATED -->

<!-- TODO editorial: related -->
