---
title: HAProxy + Keepalived
---

# HAProxy + Keepalived

<!-- TODO editorial: intro -->

## Where to look

- **Fact sheet:** [fact sheet A §1](../reference/factsheets/a-infra-lb-ovn.md#1-haproxy-role-haproxy--keepalived);
  `haproxy-config`: [fact sheet A §2](../reference/factsheets/a-infra-lb-ovn.md#2-haproxy-config-role)
- **Dependencies:** [Component dependencies
  §1](dependencies.md#1-the-shared-substrate-what-every-openstack-service-uses), [Component dependencies
  §2](dependencies.md#2-infrastructure-components)
- **Image side:** [Kolla images §5](../concepts/kolla-images.md#5-per-image-start-behaviour) (rows `haproxy`,
  `keepalived`)
- **Also:** handlers: [Tags §5](../risk/tags.md#5-role--handler-map-core-services)
- **What the tag executes (`haproxy`):** [Tags §3](../risk/tags.md#3-what-a-tag-really-executes-master-table) and [Tags
  §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), rows `haproxy`; the
  haproxy play under a service tag: [Tags
  §2.3](../risk/tags.md#23-include_role--tags-always-inside-the-haproxy-play-code)
- **Scenario:** [Reconfigure a single service
  §2](../operations/reconfigure-a-service.md#2-execute-a-service-specific-tag-implicit-effects)
  (`-t haproxy reconfigure` on an unchanged cloud)
- **Command:** [Reconfigure a single service
  §1.2](../operations/reconfigure-a-service.md#12-avoid-touching-haproxy-during-a-service-run), [Command quick lookup by
  tag](../operations/command-quick-lookup.md)
- **Risks:** [R8](../risk/risk-register.md#r8)

## Service card

<!-- BEGIN GENERATED: tools/service_cards.py haproxy -->

| Item | Value |
|---|---|
| Play | site.yml:126 |
| Tags | haproxy; each of the 49 per-service `include_role … tasks_from: loadbalancer` tasks in this play also carries its service tag |
| Play host patterns | haproxy |
| Node types in play (example inventory) | network |
| Node types running its containers | network |
| Containers | `haproxy`, `keepalived` |
| deploy/reconfigure flow (`tasks/deploy.yml`) | config-host → config → check-containers |
| Task files | check-containers.yml, check.yml, config-host.yml, config.yml, copy-certs.yml, deploy-containers.yml, deploy.yml, main.yml, precheck.yml, pull.yml, reconfigure.yml, stop.yml, upgrade.yml |
| Templates | `haproxy.json.j2`, `haproxy_main.cfg.j2`, `haproxy_run.sh.j2`, `keepalived.conf.j2`, `keepalived.json.j2` |
| Handlers (definition order) | Restart haproxy container; Restart keepalived container; Waiting for haproxy to start; Waiting for virtual IP to appear |
| Key variables | `enable_haproxy`, `enable_keepalived`, `kolla_internal_vip_address`, `kolla_external_vip_address`, `keepalived_virtual_router_id`, `kolla_enable_tls_*` |
| Role dependencies | `common` (meta) |

<!-- END GENERATED -->

<!-- TODO editorial: related -->
