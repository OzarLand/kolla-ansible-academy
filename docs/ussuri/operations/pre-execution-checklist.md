---
title: Pre-execution checklist
description: The eight checks to make before every production run of kolla-ansible, from knowing the diff to keeping rollback material.
tags: [genconfig, kolla-set-configs, loop-notify, serial, pull, limit, mariadb-backup, risk]
impact: [writes-config]
quiz:
  - q: "What should you run before <code>upgrade</code> or <code>deploy</code>, so that restart windows do not include downloads?"
    options: ["<code>kolla-ansible pull</code>, with the same tags", "<code>kolla-ansible prechecks</code>", "Nothing: there is no way to avoid downloads during restarts"]
    answer: 0
    explain: "Step 4 of the checklist: pull first."
  - q: "Do <code>mariadb</code> and <code>rabbitmq</code> follow <code>ANSIBLE_SERIAL</code>?"
    options: ["Yes, like every other role", "No, they ignore it"]
    answer: 1
    explain: "They ignore it and always run all hosts in one batch (step 3)."
  - q: "What does <code>-t common</code> do?"
    options: ["Nothing: it is a no-op", "It runs the common role (fluentd, kolla-toolbox, cron) in its own play"]
    answer: 0
    explain: "Never use <code>-t common</code> expecting it to do something <span class=\"ev ev-code\">CODE</span> (step 7)."
---

# Pre-execution checklist

What to check before running `kolla-ansible` against a production cloud. The checklist applies to every production run.

> [!NOTE]
> **Key answers**
>
> - **Before every production run:** the pre-execution checklist. Know the diff, the restart set and the batch size;
>   pull first; health gates and workload gates; scope; rollback material (steps 1 to 8 below).

1. **Know the diff before you run.**
   - Run `kolla-ansible genconfig` with the same tags and `--limit`. This writes config but does not restart any
     Docker container: every container restart handler has `when: kolla_action != "config"`, and the handlers
     without that guard are no-ops, steps chained to guarded handlers, or bootstrap, check-containers or upgrade
     steps that genconfig never notifies. Exception: the deprecated nova-hyperv role's handlers
     (`roles/nova-hyperv/handlers/main.yml:2-15`) are unguarded and are notified directly by its `config.yml`, so
     with `enable_hyperv` genconfig can restart the Windows nova-compute, neutron-hyperv-agent and FreeRDP-WebConnect
     services; keep Hyper-V hosts out of the `--limit`.
   - Then diff `/etc/kolla/<service>/` against the previous version. Keep `/etc/kolla` under version control on
     every host, or snapshot it before the run.
   - On each container, `docker exec -u root <c> /usr/local/bin/kolla_set_configs --check` tells you whether it *will*
     be restarted (exit 1 = a listed file differs, a required source is missing or `config.json` is invalid; exit 2 =
     error, including a new optional file not yet in the container, which fails the check-containers task on that host
     instead of restarting; see [Predict and inspect a run](predict-a-run.md) and [Kolla images
     §3](../concepts/kolla-images.md#3-kolla_set_configs---check-what-it-compares-and-its-exit-codes)).
2. **Know the restart set.** Remember loop-notify: if one container of a role changes on a host, every container of that
   role on that host restarts ([Tags
   §2.4](../risk/tags.md#24-loop-notify-one-changed-item-notifies-the-handlers-of-all-items-code)).
3. **Know the batch size.**
   - `ANSIBLE_SERIAL` covers `reconfigure`/`upgrade`; `-e kolla_serial=N` covers `deploy`.
   - mariadb and rabbitmq ignore it.
   - cyborg uses the wrong variable.
4. **Pull first.** `kolla-ansible pull` (with the same tags) before `upgrade`/`deploy`, so that restart windows do not
   include downloads.
5. **Health gates.** Before the run, check:
   - Galera: `wsrep_cluster_size`, `wsrep_local_state_comment=Synced`;
   - RabbitMQ: cluster status, no partitions;
   - `openstack compute service list` and `openstack network agent list` all up;
   - HAProxy backends all UP.

   Repeat after each batch.
6. **Workload gates.** No live migrations, resizes, image uploads or volume migrations in flight on the targeted
   hosts. Check `openstack server list --all-projects --status MIGRATING|RESIZE` and `openstack volume list
   --status *ing`.
7. **Scope.**
   - Prefer `--limit` and the narrowest tag.
   - Add `--skip-tags haproxy` when the frontends are not meant to change.
   - Never use `-t common` expecting it to do something.
8. **Rollback material.**
   - Previous `/etc/kolla/config`, `globals.yml`, `passwords.yml` and inventory under git.
   - Previous image tags still present locally (do not `prune-images` before you are done).
   - A MariaDB backup (`kolla-ansible mariadb_backup`).

## Related

- [Risk register](../risk/risk-register.md) — the 25 risks, each with its precautions
- [Predict and inspect a run](predict-a-run.md) — the commands of step 1, with the exit codes of the check
- [Write config first, apply in controlled batches](controlled-batches.md) — `genconfig`, then
  `deploy-containers --limit` batch by batch
- [Tags §2.4](../risk/tags.md#24-loop-notify-one-changed-item-notifies-the-handlers-of-all-items-code) — loop-notify,
  the mechanism of step 2
- [Execution flow §5](../concepts/deployment-execution-flow.md#5-batching-serial-and-its-interaction-with-order) —
  batching with `serial`, and the plays that are not batched (step 3)
- [Update container images](update-container-images.md) — `pull` before `upgrade` (step 4)
- [Database operations](database-operations.md) — the `mariadb_backup` command of step 8
