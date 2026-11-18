---
title: Pre-execution checklist
---

# Pre-execution checklist

<!-- TODO editorial: intro, key answers (old section heading: "Pre-execution checklist (applies to every production run)") -->

> [!NOTE]
> **Key answers**
>
> - **Before every production run:** the pre-execution checklist. Know the diff, the restart set and the batch size;
>   pull first; health gates and workload gates; scope; rollback material ([Pre-execution
>   checklist](#pre-execution-checklist)).

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

<!-- TODO editorial: related -->
