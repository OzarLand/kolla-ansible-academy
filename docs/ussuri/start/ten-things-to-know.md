---
title: Ten things to know before a production run
description: Ten things to know before running Kolla-Ansible Ussuri on production, most of them with the section that gives the evidence.
tags: [reconfigure, deploy, loop-notify, serial, tags, limit, images, kolla-set-configs, genconfig, handlers, risk]
---

# Ten things to know before a production run

Ten things to know before running Kolla-Ansible Ussuri on production. Most items link to the section that gives the
evidence.

1. **`reconfigure` is `deploy`** for 70 of the 72 roles that have a `reconfigure.yml`. It re-runs Keystone registration,
   DB creation and the DB-sync bootstrap containers for most services; Neutron's DB sync is the default exception. The
   only lightweight path is `genconfig` followed by `deploy-containers` ([Execution flow
   §4](../concepts/deployment-execution-flow.md#4-action-matrix-what-each-kolla_action-does)).
2. **Config is applied by a full stop/start, never a reload, and the effective SIGKILL timeout is 10 s.**
   `docker_graceful_timeout` is silently ignored ([Repository architecture
   §6](../concepts/repository-architecture.md#6-custom-modules--container-lifecycle-via-kolla_docker)). The only signal
   Kolla sends is a `SIGHUP` to `nova_scheduler`, which refreshes its cell cache.
3. **One changed container restarts all containers of its role on that host** (Ansible 2.9 loop-notify). With the
   default Nova settings, a nova-compute config change restarts **nova_libvirt** on every compute ([Tags
   §2.4][readme-03-loop-notify]).
4. **Without batching, handlers restart a service on every host of the play at once.** Batching is `ANSIBLE_SERIAL` for
   `reconfigure`/`upgrade` and `-e kolla_serial=N` for `deploy`, which ignores `ANSIBLE_SERIAL`. Only MariaDB (4 waves)
   and RabbitMQ (one by one) roll by themselves.
5. **A service tag is never just that service.** For a service with a frontend it also runs the haproxy frontend config
   (and can restart HAProxy). It runs the `common` role on every host of the play (memcached and multipathd excepted)
   and, for API services, Keystone registration and DB sync ([Tags
   §3](../risk/tags.md#3-what-a-tag-really-executes-master-table), [Reconfigure a single service
   §2](../operations/reconfigure-a-service.md#2-execute-a-service-specific-tag-implicit-effects)).
6. **`-t common` does nothing** ([Tags §2.1](../risk/tags.md#21-dynamic-include_tasks-and-tag-inheritance-code)). Use
   `-t chrony` or a service tag to push fluentd/cron changes.
7. **Global settings land in per-host files.** `enable_*`, RabbitMQ/memcached membership and passwords end up in
   compute-side configs, so small central changes cause fleet-wide restarts ([Why a small change creates a large
   workload](../risk/small-change-large-workload.md)).
8. **`deploy` never pulls an image that is already present.** Rebuilt images under the same tag need `pull`. A tag
   change applied with `deploy` recreates the entire fleet at once ([Update container
   images](../operations/update-container-images.md)).
9. **`--limit` does not contain everything.** Delegated tasks still run on `groups[x][0]` controllers, and all hosts'
   facts are gathered serially by the limited hosts ([Compute scaling](../concepts/compute-scaling-and-performance.md),
   [Add a compute node §2](../operations/add-a-compute-node.md#2-add-a-compute-node)).
10. **`--list-tasks` cannot predict a run.** Use `genconfig` plus `kolla_set_configs --check`, or staging ([Predict and
    inspect a run](../operations/predict-a-run.md)). Two things to know about the check:
    - **It compares only the files listed in `config.json`**, not its `command` or `permissions`: memcached lists no
      files, so a change to its command line never shows as drift. A plain `reconfigure` still applies it (the changed
      `config.json` notifies the restart handler), but once `genconfig` has written it, no later run restarts the
      container for it; it takes effect at the next restart for another reason ([Write config first, apply in controlled
      batches §1.1](../operations/controlled-batches.md#11-compute-changes-in-controlled-batches-recommended-pattern)).
    - **A newly rendered optional file** whose destination is not yet in the container makes `--check` exit 2, unless an
      entry listed before it already differs (then it exits 1 and the container restarts). Exit 2 is real drift, but the
      check task fails instead of restarting the container ([Kolla images
      §3](../concepts/kolla-images.md#3-kolla_set_configs---check-what-it-compares-and-its-exit-codes)).

## Related

- [Find it fast](find-it-fast.md) — typical operator questions and the section that answers them
- [Pre-execution checklist](../operations/pre-execution-checklist.md) — what to check before a run
- [Risk register](../risk/risk-register.md) — the risks [R1–R25](../risk/risk-register.md#r1), with their precautions
- [Technical findings](../reference/findings.md) — the fifteen headline findings, each with its evidence
- [Operations](../operations/index.md) — the operation pages, each with its commands

[readme-03-loop-notify]: ../risk/tags.md#24-loop-notify-one-changed-item-notifies-the-handlers-of-all-items-code
