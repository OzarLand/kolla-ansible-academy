---
template: home.html
title: Kolla Ansible Day 2
# TODO editorial: verify (restates the introduction of reference/method-and-limits.md)
description: "Source-level study of Kolla-Ansible ussuri-eol: what each tag really executes and what Kolla-Ansible commands do to a running production platform."
---

# Kolla Ansible Day 2

<!-- TODO editorial: home page skeleton. Finalise every sentence from the corpus; add no fact that a page does not state. -->

## Start from what you need

<div class="grid cards" markdown>

- **[I am about to run a command](operations/index.md)**

    ---

    Operations: the Day-2 procedures, the pre-execution checklist and the command lookup by tag.

- **[Something did not behave as expected](troubleshooting/index.md)**

    ---

    Troubleshooting: known bugs and limitations, open questions, and what the sources do not establish.

- **[I need the facts about one component](components/index.md)**

    ---

    Components: one page per OpenStack service and per infrastructure dependency, with its service card.

- **[I need to judge the risk of a change](risk/index.md)**

    ---

    Risk and impact: the risk register, what a tag really executes, and the tag index.

- **[I want to understand how a run works](concepts/index.md)**

    ---

    Concepts: repository architecture, execution flow, compute scaling and the Kolla images.

- **[I need the detailed evidence](reference/index.md)**

    ---

    Reference: findings, glossary, generated inventory, per-role fact sheets, listings and method.

</div>

<!-- TODO editorial: check each card against the hub page it links to. -->

## Frequently used procedures

<!-- TODO editorial: confirm the selection and the order. -->

- [Pre-execution checklist](operations/pre-execution-checklist.md)
- [Predict and inspect a run](operations/predict-a-run.md)
- [Reconfigure a single service](operations/reconfigure-a-service.md)
- [Reconfigure Nova](operations/reconfigure-nova.md)
- [Reconfigure Neutron](operations/reconfigure-neutron.md)
- [Write config first, apply in controlled batches](operations/controlled-batches.md)
- [Update container images](operations/update-container-images.md)
- [Add a compute node](operations/add-a-compute-node.md)
- [Command quick lookup by tag](operations/command-quick-lookup.md)

## Recently updated

<div data-portal-recent="8" markdown>

Every change is in the [commit history of the repository](https://github.com/OzarLand/kolla-ansible-day2/commits/main/docs).

</div>

## How to read this portal

Every statement carries one of two evidence labels:

- [CODE] shown by the sources, with a `path:line` citation nearby. <!-- TODO editorial: verify -->
- [NOT AVAILABLE] the sources do not establish it. <!-- TODO editorial: verify -->

The study rests only on reading source code; nothing was run against a host. <!-- TODO editorial: verify -->

Operation pages show their impact classes under the title, for example `read-only`, `restarts-on-drift` or `critical`.
<!-- TODO editorial: verify, and link to start/conventions.md#operation-impact-classes once that section exists -->
The labels are defined in [Conventions and evidence labels](start/conventions.md#evidence-labels).

Not sure where to look? [Find it fast](start/find-it-fast.md) lists typical operator questions and the section that
answers each one, and [Ten things to know before a production run](start/ten-things-to-know.md) is the short list to
read first. <!-- TODO editorial: verify -->

## Raw material (to integrate)

<!-- source: old README.md, section "Documents" (document table and list of annexes) -->

| # | Document | Answers |
|---|---|---|
| 01 | [Repository Architecture](concepts/repository-architecture.md) | How a CLI command becomes an `ansible-playbook` run; site.yml anatomy; role skeleton; `kolla_docker`; config overrides; inventory |
| 02 | [OpenStack Component Dependencies](components/dependencies.md) | Installation, configuration, runtime and operational dependencies of infra and control-plane services |
| 03 | [Ansible Roles and Tags Mapping](risk/tags.md) | What each tag executes, on which hosts, with which handlers, and why tag names mislead |
| 04 | [Deployment Execution Flow](concepts/deployment-execution-flow.md) | Play order, intra-role order, handler flush points, batching; 5 Mermaid flow diagrams plus a batching Gantt chart |
| 05 | [Nova Deep Dive](components/nova-deep-dive.md) | Nova roles, plays, cells, discovery, dependencies, libvirt restart semantics |
| 06 | [Compute Scaling and Performance](concepts/compute-scaling-and-performance.md) | What grows with compute count; per-compute task chains; model for 10–500 computes; optimisations |
| 07 | [Day-2 Operational Impact](operations/index.md) | Scenarios A–I (reconfigure Nova/Neutron/common, images, service tags, membership changes, adding computes) |
| 08 | [Operational Risk Matrix](risk/risk-register.md) | 25 risks with blast radius, VM/API impact, precautions; pre-execution checklist |
| 09 | [Practical Command Reference](operations/index.md) | Real commands, their scope and impact; safe patterns |
| 10 | [Technical Findings and Open Questions](reference/findings.md) | Findings, bugs and limitations, open questions (each answered from the code or marked not available) |

Annexes:

- [Kolla Ansible Day 2](#kolla-ansible-day-2) — navigation index: tag index, service index, glossary, and the list of
  everything marked [NOT AVAILABLE].
- [Components](components/index.md) — one card per core service (22 cards): role, play, tags, task flow, templates,
  handlers, key variables, node types touched. Generated by
  [tools/service_cards.py](https://github.com/OzarLand/kolla-ansible-day2/blob/main/tools/service_cards.py).
- [Generated inventory](reference/generated-inventory.md) — every play, container, role and handler, extracted from the
  source by [tools/extract_kolla_inventory.py][extract-kolla-inventory].
- [Per-role fact sheets](reference/factsheets/index.md) — per-role fact sheets with `path:line` evidence: A
  infra/LB/OVN, B MariaDB/RabbitMQ/Keystone, C Glance/Placement/Cinder/Horizon/Heat, D Barbican/Octavia/Swift/Manila and
  compute-side roles, E host bootstrap and operational playbooks. Read the correction in [Fact sheet
  corrections](reference/factsheets/index.md#corrections).
- [Kolla images](concepts/kolla-images.md) — what the kolla images do at start and in one-shot containers:
  `kolla_start`, `kolla_set_configs` and its `--check`, `KOLLA_BOOTSTRAP`/`KOLLA_UPGRADE`/`KOLLA_OSM` per image; read
  from the kolla `ussuri-eol` image sources.
- [Ansible listings](reference/listings/index.md) — Ansible 2.9.27's own parse of the unmodified playbooks: the
  `--list-tags` output of `site.yml` and its `--list-tasks -t nova` output. Nothing was executed against a host.

<!-- source: old annex/index.md, introduction -->

Four ways into the study: by tag, by service, by term, and by what is not known. This page adds no finding of its own:
every entry restates what the linked section says, and the linked section is the reference. Start from the [Find it
fast](start/find-it-fast.md) for a lookup by question.

[extract-kolla-inventory]: https://github.com/OzarLand/kolla-ansible-day2/blob/main/tools/extract_kolla_inventory.py
