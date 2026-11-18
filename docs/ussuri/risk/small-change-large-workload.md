---
title: Why a small change creates a large workload
description: Six small changes that become a large workload in Kolla-Ansible Ussuri, each with the reason and the source.
tags: [risk, scaling, loop-notify, nova, neutron, rabbitmq, images, reconfigure]
---

# Why a small change creates a large workload

Why a small change can create a large workload: six small changes, each with why it is large and the source lines and
sections that show it. The per-host work that every run pays, independently of restarts, closes the page.

| Small change | Why it is large | Source |
|---|---|---|
| One option for nova-compute | targets every compute; loop-notify adds libvirt + ssh restarts | `nova.yml:117-135`; [Tags §2.4](tags.md#24-loop-notify-one-changed-item-notifies-the-handlers-of-all-items-code); [Reconfigure Nova §3](../operations/reconfigure-nova.md#3-what-changes-per-type-of-change-code) |
| `enable_<new service>: yes` | changes fluentd/logrotate on every host and `nova.conf` sections on every compute | `roles/common/defaults/main.yml:105-109`, `roles/common/tasks/config.yml:163-173`; [Reconfigure Nova §3](../operations/reconfigure-nova.md#3-what-changes-per-type-of-change-code) |
| One extra controller | changes the transport URL in every messaging service everywhere | `group_vars/all.yml:206`; [Change control-plane membership §2](../operations/change-control-plane-membership.md#2-change-control-plane-membership-add-or-remove-a-controller) |
| A server-side ML2 option | also merged into every OVS agent config | `roles/neutron/tasks/config.yml:172-190`; [Reconfigure Neutron §3](../operations/reconfigure-neutron.md#3-what-restarts-code) |
| Rebuilt image of one service | its siblings on the same host restart too | `library/kolla_docker.py:403-418`; [Tags §2.4](tags.md#24-loop-notify-one-changed-item-notifies-the-handlers-of-all-items-code); [Update container images §2](../operations/update-container-images.md#2-how-image-pulling-and-recreation-work-code) |
| Any OpenStack API service `-t <svc>` | runs common, the service's haproxy include and Keystone registration even with no change; the DB sync runs on every `deploy` and, for most services, on every reconfigure (Neutron: `deploy` only by default). Infrastructure tags such as `-t haproxy` run no Keystone registration or DB sync | [Reconfigure Neutron §2](../operations/reconfigure-neutron.md#2-execution-and-targets), [Reconfigure a single service §2](../operations/reconfigure-a-service.md#2-execute-a-service-specific-tag-implicit-effects); `site.yml:126-392` |

And independently of restarts, **every run pays the per-host work** [CODE]. Per compute, a no-change `-t nova` run makes
46 remote module invocations (53 on compute001), and every full `deploy` or `reconfigure` makes 11 `compare_container`
calls, counted from the task files in [Compute scaling
§2](../concepts/compute-scaling-and-performance.md#2-work-per-compute-host-read-from-the-task-files). The number of task
results per compute is [NOT AVAILABLE].

## Related

- [Compute scaling §5](../concepts/compute-scaling-and-performance.md#5-why-a-small-change-becomes-a-large-workload) —
  the work multiplier and the restart multiplier
- [Tags §2.4](tags.md#24-loop-notify-one-changed-item-notifies-the-handlers-of-all-items-code) — loop-notify
- [Technical findings](../reference/findings.md) — [F6](../reference/findings.md#f6): global inputs are rendered into
  per-host files
- [Write config first, apply in controlled batches](../operations/controlled-batches.md) — `genconfig`, then
  `deploy-containers --limit` batch by batch
- [Risk register](risk-register.md) — the risks [R1–R25](risk-register.md#r1)
