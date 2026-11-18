---
title: Swift
---

# Swift

<!-- TODO editorial: intro -->

## Where to look

- **Fact sheet:** [fact sheet D §3](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#3-swift)
- **Dependencies:** [Component dependencies §3](dependencies.md#3-control-plane-services)
- **Image side:** [Kolla images §5](../concepts/kolla-images.md#5-per-image-start-behaviour) (rows `swift-*`)

## Service card

<!-- BEGIN GENERATED: tools/service_cards.py swift -->

| Item | Value |
|---|---|
| Play | site.yml:643 |
| Tags | swift |
| Play host patterns | swift-account-server, swift-container-server, swift-object-server, swift-proxy-server |
| Node types in play (example inventory) | control, storage |
| Node types running its containers | control, storage |
| Containers | `swift_proxy_server`, `swift_rsyncd`, `swift_account_server`, `swift_account_auditor`, `swift_account_replication_server`, `swift_account_replicator`, `swift_account_reaper`, `swift_container_server`, `swift_container_auditor`, `swift_container_replication_server`, `swift_container_replicator`, `swift_container_updater`, `swift_object_server`, `swift_object_auditor`, `swift_object_replication_server`, `swift_object_replicator`, `swift_object_updater`, `swift_object_expirer` |
| deploy/reconfigure flow (`tasks/deploy.yml`) | register → config → start → check |
| Task files | check.yml, config.yml, copy-certs.yml, deploy-containers.yml, deploy.yml, legacy_upgrade.yml, loadbalancer.yml, main.yml, precheck.yml, pull.yml, reconfigure.yml, register.yml, rolling_upgrade.yml, start.yml, stop.yml, upgrade.yml |
| Templates | `account.conf.j2`, `container.conf.j2`, `object.conf.j2`, `proxy-server.conf.j2`, `rsyncd.conf.j2`, `swift-account-auditor.json.j2`, `swift-account-reaper.json.j2`, `swift-account-replication-server.json.j2`, `swift-account-replicator.json.j2`, `swift-account-server.json.j2`, `swift-container-auditor.json.j2`, `swift-container-replication-server.json.j2`, `swift-container-replicator.json.j2`, `swift-container-server.json.j2`, `swift-container-updater.json.j2`, `swift-object-auditor.json.j2`, `swift-object-expirer.json.j2`, `swift-object-replication-server.json.j2`, `swift-object-replicator.json.j2`, `swift-object-server.json.j2`, `swift-object-updater.json.j2`, `swift-proxy-server.json.j2`, `swift-rsyncd.json.j2`, `swift.conf.j2` |
| Handlers (definition order) | Restart swift-proxy-server container |
| Key variables | `enable_swift`, `swift_devices_*`, `swift_*_server ports` |
| Role dependencies | `common` (meta) |

<!-- END GENERATED -->

<!-- TODO editorial: related -->
