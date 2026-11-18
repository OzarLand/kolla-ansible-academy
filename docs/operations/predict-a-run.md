---
title: Predict and inspect a run
---

# Predict and inspect a run

<!-- TODO editorial: intro, key answers (old section heading: "Inspection (no changes)") -->

> [!NOTE]
> **Key answers**
>
> - **Predict a run:** `genconfig`, then `kolla_set_configs --check` in each container; the meaning of exit codes 0, 1,
>   2 and 137 is in the same table [CODE]. `--list-tasks` is not useful ([Predict and inspect a
>   run](#predict-and-inspect-a-run)).

| Goal | Command | Notes |
|---|---|---|
| List tags as Ansible sees them | `EXTRA_OPTS="--list-tags" kolla-ansible -i multinode deploy` | Works. Shows the inherited task tags (`common` appears nearly everywhere; [list-tags-site.txt](../reference/listings/list-tags-site.txt)) |
| List hosts a run would target | `EXTRA_OPTS="--list-hosts" kolla-ansible -i multinode -t nova reconfigure` | Plays with `&enable_<svc>_True` patterns show **0 hosts**: the groups are created at run time ([Tags §2.6](../risk/tags.md#26---list-tasks-is-not-usable-for-kolla-code)) |
| List tasks | `EXTRA_OPTS="--list-tasks" …` | **Not useful**: only `include_tasks` placeholders are shown ([Tags §2.6](../risk/tags.md#26---list-tasks-is-not-usable-for-kolla-code)) |
| Render configs without restarting | `kolla-ansible -i multinode genconfig [-t <svc>] [--limit <hosts>]` | Writes `/etc/kolla/<svc>/` on the targets. All handlers are skipped. Also re-renders haproxy `services.d` for the tagged services |
| See what will restart | on each host: `docker exec -u root <container> /usr/local/bin/kolla_set_configs --check; echo $?` | 0 = every file listed in `config.json`'s `config_files` matches its live copy (content, mode, owner). `command`, `permissions`, removed entries and stale optional files are **not** compared, so memcached (`"config_files": []`) always returns 0. 1 = a listed file differs or a non-optional one is missing from the container → restart on the next `deploy`/`reconfigure`/`deploy-containers`. 1 is also returned for a required source missing from `/var/lib/kolla/config_files` or an invalid `config.json`; the restarted container then fails `kolla_set_configs` at start. `preserve_properties` entries (e.g. prometheus extras already copied into the container) and, in practice, directory sources with subdirectories return 1 on every run ([Tags §3](../risk/tags.md#3-what-a-tag-really-executes-master-table)). 137 is also treated as drift. 2 = an unexpected exception, such as a missing `config.json` or a newly rendered `optional` file not yet in the container (e.g. nova-compute `release`); the latter is real drift, and it gives 2 only if no entry listed before it differs (otherwise 1). On 2, or any code other than 0, 1 and 137, `kolla_docker` fails the check task instead of restarting [CODE `kolla_docker.py:566-578,1071-1073`, kolla `docker/base/set_configs.py:60-65,135-136,160-211,217-253,280-296,407-410,427-432`, kolla `docker/base/start.sh:2,8`]. Details: [Kolla images §3](../concepts/kolla-images.md#3-kolla_set_configs---check-what-it-compares-and-its-exit-codes). Keep `-u root`: Kolla runs the check as root (`kolla_docker.py:544-578`), and containers that run as a service user cannot read the root-owned 0660 files in `/var/lib/kolla/config_files` |
| Check-mode run | `EXTRA_OPTS="--check --diff" kolla-ansible … reconfigure` | [CODE] `kolla_docker` does not declare check-mode support (`kolla_docker.py:1031-1035`), so Ansible skips it under `--check` (ansible 2.9.27 `lib/ansible/module_utils/basic.py:1595-1596`). Many tasks register outputs used later. [NOT AVAILABLE] Whether such a run fails or gives partial results; staging only |
| Pre-deployment checks | `kolla-ansible -i multinode prechecks [-t <svc>]` | Read-only ([fact sheet E](../reference/factsheets/e-host-bootstrap-ops-playbooks.md)). `-t <svc>` skips the `prechecks` role (untagged) but runs `<svc>/precheck.yml` |

<!-- TODO editorial: related -->
