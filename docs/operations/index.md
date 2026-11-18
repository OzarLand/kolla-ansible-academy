---
title: Operations
---

# Operations

<!-- TODO editorial -->

## Raw material (to integrate)

<!-- source: old 07, Day-2 Operational Impact: introduction -->

What Kolla-Ansible Ussuri commands do when they run against a live platform, read from the source of the **unmodified
`site.yml`**, its roles and Ansible 2.9.27. Nothing was run against a host.

Drift means what `compare_container` detects: a changed image or container parameter, or `kolla_set_configs --check`
exiting 1 (`library/kolla_docker.py:326-332`; [Kolla images
§3](../concepts/kolla-images.md#3-kolla_set_configs---check-what-it-compares-and-its-exit-codes)).

Every scenario assumes the same deployed state: 3 controllers, 2 network nodes, 3 computes, 1 storage node and 1
monitoring node, with Keystone, Glance, Placement, Nova, Neutron/OVS, Cinder/LVM, Heat and Horizon.

Throughout this document:

- **The code guarantees** = what Kolla will do (tasks, restarts) given the inputs.
- **Depends on the environment** = what that does to VMs and APIs; mostly [NOT AVAILABLE] in these sources.

The evidence labels **[CODE]** and **[NOT AVAILABLE]** are defined once, in the [Conventions and evidence
labels](../start/conventions.md#evidence-labels).

Three mechanisms explain almost every surprise below, so they are restated here:

1. **Config drift ⇒ full container stop/start.** It is never a reload. The stop timeout is effectively **10 s**
   ([Repository architecture
   §6](../concepts/repository-architecture.md#6-custom-modules--container-lifecycle-via-kolla_docker)).
2. **Loop-notify.** One changed container in a role's loop restarts *every* container of that role on that host ([Tags
   §2.4](../risk/tags.md#24-loop-notify-one-changed-item-notifies-the-handlers-of-all-items-code)).
3. **Global inputs.** `enable_*` flags, group membership and passwords are rendered into per-host files on every host
   ([Component dependencies §5](../components/dependencies.md#5-compute-node-dependency-summary)).

<!-- source: old 09, Practical Command Reference: introduction -->

Real `kolla-ansible` (Ussuri) invocations with what they select, their scope and their impact.

<!-- source: old 07, Day-2 Operational Impact: key answers that summarise sections now on several pages -->

> [!NOTE]
> **Key answers**
>
> - **A service tag also touches** the HAProxy frontends of the service, `common` on every host of the service play,
>   Keystone registration, for most services DB creation and schema sync (Neutron's DB sync only on `deploy` by
>   default), and hosts outside `--limit` ([Reconfigure a single service
>   §2](reconfigure-a-service.md#2-execute-a-service-specific-tag-implicit-effects)). A controller membership change is
>   a fleet-wide restart event for every messaging consumer ([Change control-plane membership
>   §2](change-control-plane-membership.md#2-change-control-plane-membership-add-or-remove-a-controller)); what adding a
>   compute with `deploy --limit` touches: [Add a compute node §2](add-a-compute-node.md#2-add-a-compute-node).
> - **Recommended pattern:** `genconfig`, then `deploy-containers --limit` batch by batch, with its caveats [CODE]
>   ([Write config first, apply in controlled batches
>   §2](controlled-batches.md#2-separate-write-config-from-apply-recommended-pattern)). Why a small change can create a
>   large workload: [Why a small change creates a large workload](../risk/small-change-large-workload.md).

<!-- source: old 07, Day-2 Operational Impact: related -->

- [Tags §3](../risk/tags.md#3-what-a-tag-really-executes-master-table) (what each tag executes)
- [Risk register](../risk/risk-register.md) (risks [R1–R25](../risk/risk-register.md#r1) and the pre-execution
  checklist)
- [Operations](#operations) (the commands)
- [Nova deep dive §5](../components/nova-deep-dive.md#5-nova-libvirt-why-its-restart-is-special) (nova-libvirt restarts)
- [Kolla Ansible Day 2](../index.md) (tag index, everything marked [NOT AVAILABLE])

<!-- source: old 09, Practical Command Reference: key answers that summarise sections now on several pages -->

> [!NOTE]
> **Key answers**
>
> - **Leave HAProxy alone:** `--skip-tags haproxy` ([Reconfigure a single service
>   §1.2](reconfigure-a-service.md#12-avoid-touching-haproxy-during-a-service-run)). **Push `common` changes:**
>   `-t chrony`, because `-t common` is a no-op ([Apply `common` changes (fluentd, cron, kolla_toolbox)
>   §1.1](apply-common-changes.md#11-apply-common-changes-fluentd-cron-kolla_toolbox)).
> - **Add a compute:** `bootstrap-servers`, `pull` and `deploy`, each with `--limit` ([Add a compute node
>   §1.1](add-a-compute-node.md#11-add-a-compute-node)). **Per-tag quick lookup** of hosts touched, possible restarts
>   and one-shot containers: [Command quick lookup by tag](command-quick-lookup.md).

<!-- source: old 09, Practical Command Reference: related -->

- [Repository architecture §2](../concepts/repository-architecture.md#2-from-cli-to-ansible-playbook) (the CLI →
  playbook mapping and the `kolla_serial` pass-through rules)
- [Tags](../risk/tags.md) (tag semantics)
- [Operations](#operations) (impact of each scenario)
- [Pre-execution checklist](pre-execution-checklist.md) (pre-execution checklist)
- [Conventions and evidence labels](../start/conventions.md#evidence-labels) (evidence labels)
