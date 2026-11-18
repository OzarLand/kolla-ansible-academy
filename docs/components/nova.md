---
title: Nova
---

# Nova

<!-- TODO editorial: intro -->

## Where to look

- **Dependencies (role `nova`):** [Component dependencies §3](dependencies.md#3-control-plane-services)
- **Image side (role `nova`):** [Kolla images
  §4](../concepts/kolla-images.md#4-one-shot-containers-what-the-environment-variables-run) (row `nova-api`), [Kolla
  images §4.1](../concepts/kolla-images.md#41-one-shots-that-bypass-kolla_start), [Kolla images
  §5](../concepts/kolla-images.md#5-per-image-start-behaviour)
- **Also (role `nova`):** **[Nova deep dive](nova-deep-dive.md)**; handlers: [Tags
  §5](../risk/tags.md#5-role--handler-map-core-services)
- **Dependencies (role `nova-cell`):** [Component dependencies §3](dependencies.md#3-control-plane-services), [Component
  dependencies §5](dependencies.md#5-compute-node-dependency-summary)
- **Image side (role `nova-cell`):** [Kolla images
  §4](../concepts/kolla-images.md#4-one-shot-containers-what-the-environment-variables-run) (row `nova-conductor`),
  [Kolla images §5](../concepts/kolla-images.md#5-per-image-start-behaviour), [Kolla images
  §5.1](../concepts/kolla-images.md#51-nova-libvirt-the-start-path-is-passive)
- **Also (role `nova-cell`):** **[Nova deep dive](nova-deep-dive.md)**, in particular [Nova deep dive
  §5](nova-deep-dive.md#5-nova-libvirt-why-its-restart-is-special); handlers: [Tags
  §5](../risk/tags.md#5-role--handler-map-core-services)
- **What the tag executes (`nova`):** [Tags §3](../risk/tags.md#3-what-a-tag-really-executes-master-table) and [Tags
  §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), rows `nova`
- **Scenario (`nova`):** [Reconfigure Nova](../operations/reconfigure-nova.md); batched apply: [Write config first,
  apply in controlled batches
  §2](../operations/controlled-batches.md#2-separate-write-config-from-apply-recommended-pattern)
- **Command (`nova`):** [Reconfigure Nova
  §1.1](../operations/reconfigure-nova.md#11-reconfigure-nova-control-plane-and-computes), [Write config first, apply in
  controlled batches §1.2](../operations/controlled-batches.md#12-rolling-reconfigure-with-ansible_serial), [Reconfigure
  a single service §1.2](../operations/reconfigure-a-service.md#12-avoid-touching-haproxy-during-a-service-run)
- **Risks (`nova`):** [R1](../risk/risk-register.md#r1), [R2](../risk/risk-register.md#r2),
  [R3](../risk/risk-register.md#r3), [R24](../risk/risk-register.md#r24)
- **What the tag executes (`nova-api`):** [Tags §3](../risk/tags.md#3-what-a-tag-really-executes-master-table) and [Tags
  §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), rows `nova-api`
- **Scenario (`nova-api`):** [Reconfigure Nova
  §2](../operations/reconfigure-nova.md#2-execution-sequence-kolla-ansible--t-nova-reconfigure) (plays 1, 3 and 5)
- **Command (`nova-api`):** [Reconfigure Nova
  §1.2](../operations/reconfigure-nova.md#12-reconfigure-only-the-nova-control-plane-no-compute-impact)
- **What the tag executes (`nova-cell`):** [Tags §3](../risk/tags.md#3-what-a-tag-really-executes-master-table) and
  [Tags §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), rows
  `nova-cell`
- **Scenario (`nova-cell`):** [Reconfigure Nova
  §2](../operations/reconfigure-nova.md#2-execution-sequence-kolla-ansible--t-nova-reconfigure) (plays 2 and 4),
  [Reconfigure Nova
  §4](../operations/reconfigure-nova.md#4-are-all-compute-nodes-affected-does-nova-compute-restart-on-every-compute)
- **Command (`nova-cell`):** [Reconfigure Nova
  §1.3](../operations/reconfigure-nova.md#13-reconfigure-only-the-cell-part-conductors-consoles-computes), [Write config
  first, apply in controlled batches
  §1.1](../operations/controlled-batches.md#11-compute-changes-in-controlled-batches-recommended-pattern)
- **Risks (`nova-cell`):** [R1](../risk/risk-register.md#r1)
- **What the tag executes (`nova-bootstrap`, `nova-reload`, `nova-online-data-migrations` (with their `-api-`/`-cell-`
  variants) and `nova-refresh-scheduler-cell-cache`):** [Tags
  §3](../risk/tags.md#3-what-a-tag-really-executes-master-table), one row each; use as narrower play tags: [Tags
  §4](../risk/tags.md#4-practical-consequences) (item 4)
- **Scenario (`nova-bootstrap`, `nova-reload`, `nova-online-data-migrations` (with their `-api-`/`-cell-` variants) and
  `nova-refresh-scheduler-cell-cache`):** the plays themselves: [Nova deep dive
  §4](nova-deep-dive.md#4-the-nova-plays-step-by-step-ansiblenovayml)

## Service card

<!-- BEGIN GENERATED: tools/service_cards.py nova nova-cell -->

### Nova (API level) — role `nova`

| Item | Value |
|---|---|
| Play | nova.yml (`import_playbook` at site.yml:710) |
| Tags | nova, nova-api(-*) |
| Play host patterns | nova-api, nova-scheduler, nova-super-conductor |
| Node types in play (example inventory) | control |
| Node types running its containers | control |
| Containers | `nova_api`, `nova_scheduler`, `nova_super_conductor` |
| deploy/reconfigure flow (`tasks/deploy.yml`) | register → config → check-containers → flush handlers |
| Task files | bootstrap.yml, bootstrap_service.yml, bootstrap_upgrade.yml, check-containers.yml, check.yml, clone.yml, config.yml, config_bootstrap.yml, copy-certs.yml, deploy-containers.yml, deploy.yml, loadbalancer.yml, main.yml, map_cell0.yml, online_data_migrations.yml, precheck.yml, pull.yml, reconfigure.yml, refresh_scheduler_cell_cache.yml, register.yml, reload_api.yml, reload_super_conductor.yml, rolling_upgrade.yml, stop.yml, upgrade.yml |
| Templates | `nova-api-bootstrap.json.j2`, `nova-api.json.j2`, `nova-scheduler.json.j2`, `nova-super-conductor.json.j2`, `nova.conf.j2` |
| Handlers (definition order) | Restart nova-super-conductor container; Restart nova-scheduler container; Restart nova-api container |
| Key variables | `enable_nova`, `enable_cells`, `nova_safety_upgrade`, `nova_console` |
| Role dependencies | `common` (meta) |

### Nova (cell level) — role `nova-cell`

| Item | Value |
|---|---|
| Play | nova.yml (`import_playbook` at site.yml:710) |
| Tags | nova, nova-cell(-*) |
| Play host patterns | compute, nova-compute-ironic, nova-conductor, nova-novncproxy, nova-serialproxy, nova-spicehtml5proxy |
| Node types in play (example inventory) | compute, control |
| Node types running its containers | compute, control |
| Containers | `nova_libvirt`, `nova_ssh`, `nova_novncproxy`, `nova_spicehtml5proxy`, `nova_serialproxy`, `nova_conductor`, `nova_compute`, `nova_compute_ironic` |
| deploy/reconfigure flow (`tasks/deploy.yml`) | bootstrap_xenapi (if) → clone (if) → config-host → config → check-containers → config-nova-fake (if) → flush handlers → wait_discover_computes (if) |
| Task files | bootstrap.yml, bootstrap_service.yml, bootstrap_upgrade.yml, bootstrap_xenapi.yml, cell_proxy_loadbalancer.yml, check-containers.yml, check.yml, clone.yml, config-host.yml, config-libvirt-tls.yml, config-nova-fake.yml, config.yml, config_bootstrap.yml, copy-certs.yml, create_cells.yml, deploy-containers.yml, deploy.yml, discover_computes.yml, external_ceph.yml, get_cell_settings.yml, loadbalancer.yml, main.yml, online_data_migrations.yml, precheck.yml, proxy_loadbalancer.yml, pull.yml, rabbitmq.yml, reconfigure.yml, reload.yml, rolling_upgrade.yml, stop.yml, upgrade.yml, wait_discover_computes.yml |
| Templates | `99-kolla-kvm.rules.j2`, `auth.conf.j2`, `libvirtd.conf.j2`, `nova-cell-bootstrap.json.j2`, `nova-compute-ironic.json.j2`, `nova-compute.json.j2`, `nova-conductor.json.j2`, `nova-libvirt.json.j2`, `nova-novncproxy.json.j2`, `nova-serialproxy.json.j2`, `nova-spicehtml5proxy.json.j2`, `nova-ssh.json.j2`, `nova.conf.d/libvirt.conf.j2`, `nova.conf.j2`, `qemu.conf.j2`, `sasl.conf.j2`, `secret.xml.j2`, `ssh_config.j2`, `sshd_config.j2` |
| Handlers (definition order) | Restart nova-conductor container; Restart nova-novncproxy container; Restart nova-spicehtml5proxy container; Restart nova-serialproxy container; Restart nova-ssh container; Restart nova-libvirt container; Create libvirt SASL user; Restart nova-compute container; Restart nova-compute-ironic container; Restart nova-compute-fake containers; Wait for nova-compute services to update service versions |
| Key variables | `nova_compute_virt_type`, `nova_backend_ceph`, `libvirt_tls`, `libvirt_enable_sasl`, `nova_cell_*_group`, `migration_interface` |
| Role dependencies | `common` (meta) |

<!-- END GENERATED -->

<!-- TODO editorial: related -->
