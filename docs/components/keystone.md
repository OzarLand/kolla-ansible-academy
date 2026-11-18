---
title: Keystone
---

# Keystone

<!-- TODO editorial: intro -->

## Where to look

- **Fact sheet:** [fact sheet B
  §3](../reference/factsheets/b-mariadb-rabbitmq-keystone.md#3-keystone-ansibleroleskeystone)
- **Dependencies:** [Component dependencies
  §1](dependencies.md#1-the-shared-substrate-what-every-openstack-service-uses), [Component dependencies
  §3](dependencies.md#3-control-plane-services)
- **Image side:** [Kolla images
  §4](../concepts/kolla-images.md#4-one-shot-containers-what-the-environment-variables-run) (row `keystone`), [Kolla
  images §4.1](../concepts/kolla-images.md#41-one-shots-that-bypass-kolla_start), [Kolla images
  §5](../concepts/kolla-images.md#5-per-image-start-behaviour)
- **Also:** handlers: [Tags §5](../risk/tags.md#5-role--handler-map-core-services)
- **What the tag executes (`keystone`):** [Tags §3](../risk/tags.md#3-what-a-tag-really-executes-master-table), row
  `<svc>`; [Tags §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), row
  `<svc>` API service
- **Scenario:** [Reconfigure a single service
  §2](../operations/reconfigure-a-service.md#2-execute-a-service-specific-tag-implicit-effects), [Reconfigure a single
  service §3](../operations/reconfigure-a-service.md#3-sequence-impact-risks-and-verification-of--t-svc-reconfigure)
- **Command:** [Reconfigure a single service
  §1.1](../operations/reconfigure-a-service.md#11-reconfigure-a-single-service)
- **Risks:** [R19](../risk/risk-register.md#r19), [R8](../risk/risk-register.md#r8), [R24](../risk/risk-register.md#r24)

## Service card

<!-- BEGIN GENERATED: tools/service_cards.py keystone -->

| Item | Value |
|---|---|
| Play | site.yml:596 |
| Tags | keystone |
| Play host patterns | keystone |
| Node types in play (example inventory) | control |
| Node types running its containers | control |
| Containers | `keystone`, `keystone_ssh`, `keystone_fernet` |
| deploy/reconfigure flow (`tasks/deploy.yml`) | config → check-containers → clone (if) → bootstrap → flush handlers → distribute_fernet (if) → register → check |
| Task files | bootstrap.yml, bootstrap_service.yml, check-containers.yml, check.yml, clone.yml, config.yml, copy-certs.yml, deploy-containers.yml, deploy.yml, distribute_fernet.yml, loadbalancer.yml, main.yml, precheck.yml, pull.yml, reconfigure.yml, register.yml, stop.yml, upgrade.yml |
| Templates | `crontab.j2`, `fernet-node-sync.sh.j2`, `fernet-push.sh.j2`, `fernet-rotate.sh.j2`, `keystone-fernet.json.j2`, `keystone-ssh.json.j2`, `keystone-startup.sh.j2`, `keystone.conf.j2`, `keystone.json.j2`, `ssh_config.j2`, `sshd_config.j2`, `wsgi-keystone.conf.j2` |
| Handlers (definition order) | Init keystone database upgrade; Restart keystone-ssh container; Restart keystone-fernet container; Restart keystone container; Finish keystone database upgrade |
| Key variables | `enable_keystone`, `keystone_token_provider`, `fernet_token_expiry`, `fernet_key_rotation_interval` |
| Role dependencies | `common` (meta) |

<!-- END GENERATED -->

<!-- TODO editorial: related -->
