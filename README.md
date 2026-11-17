# Kolla-Ansible Ussuri — Reverse Engineering for Day-2 Operations

A source-level study of **Kolla-Ansible `ussuri-eol`** (`openstack/kolla-ansible`, tag `ussuri-eol`, HEAD `8a94fe9`). It
covers how Kolla-Ansible orchestrates an OpenStack platform, what each tag really executes, how runs scale with the
number of compute nodes, and what Kolla-Ansible commands do to a running production platform.

All conclusions come from the Ussuri implementation, not from newer releases. Each one is labelled with its evidence
level: **[CODE]** or **[NOT AVAILABLE]** (see [Evidence labels](#evidence-labels)).

## Find it fast

Typical operator questions and the section that answers them. The last column says how the answer is labelled there. To
look something up by tag, by service or by term, use [annex/index.md](annex/index.md): tag index, service index,
glossary, and the list of everything marked [NOT AVAILABLE].

| Topic | Question | Go to | Evidence there |
|---|---|---|---|
| Tags | If I run `-t nova reconfigure`, what runs and what restarts? | [docs/07 §A.1](docs/07-day2-operational-impact.md#a1-execution-sequence-kolla-ansible--t-nova-reconfigure) (sequence), [docs/07 §A.2](docs/07-day2-operational-impact.md#a2-what-changes-per-type-of-change-code) (restarts per type of change), [docs/09 §2.2](docs/09-practical-command-reference.md#22-reconfigure-nova-control-plane-and-computes) (command) | [CODE]; whether every task reports unchanged on an unchanged cloud is [NOT AVAILABLE] |
| Tags | What does a given tag execute, on which hosts, and which containers can restart? | [docs/03 §3](docs/03-ansible-roles-and-tags-mapping.md#3-what-a-tag-really-executes-master-table) (master table) | [CODE]; whether nothing restarts on an unchanged cloud is [NOT AVAILABLE] |
| Tags | Does this tag touch the computes? | [docs/03 §3](docs/03-ansible-roles-and-tags-mapping.md#3-what-a-tag-really-executes-master-table) ("Target hosts" column), [docs/09 §3](docs/09-practical-command-reference.md#3-quick-lookup-tag--scope--typical-impact) (quick lookup) | [CODE] |
| Tags | Is this tag safe on its own? What does it do to VMs, APIs, networking and storage? | [docs/03 §3.1](docs/03-ansible-roles-and-tags-mapping.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites) (per-tag answers) | [CODE] for what restarts; [NOT AVAILABLE] for what happens to VMs and traffic under `nova`, `nova-cell`, `neutron`, `openvswitch`, `ovn` and `iscsi` |
| Restarts | Why did containers restart although their config did not change (loop-notify)? | [docs/03 §2.4](docs/03-ansible-roles-and-tags-mapping.md#24-loop-notify-one-changed-item-notifies-the-handlers-of-all-items-code) | [CODE] |
| Restarts | Is a config change ever applied by a reload? What is the stop timeout? | [docs/01 §4.3](docs/01-repository-architecture.md#43-the-config--check--handler-pattern), [docs/01 §6](docs/01-repository-architecture.md#6-custom-modules--container-lifecycle-via-kolla_docker) | [CODE] |
| Restarts | Can a service tag restart HAProxy, and how do I avoid it? | [docs/03 §2.2](docs/03-ansible-roles-and-tags-mapping.md#22-handlers-ignore-tags-code) (why), [docs/09 §2.8](docs/09-practical-command-reference.md#28-avoid-touching-haproxy-during-a-service-run) (`--skip-tags haproxy`), [docs/08 §1](docs/08-operational-risk-matrix.md#1-matrix) ([R8](docs/08-operational-risk-matrix.md#1-matrix)) | [CODE]; what keepalived does with the VIP meanwhile is [NOT AVAILABLE] |
| Compute impact | Does nova-compute restart on every compute? Does libvirt restart with it? | [docs/07 §A.3](docs/07-day2-operational-impact.md#a3-are-all-compute-nodes-affected-does-nova-compute-restart-on-every-compute), [docs/05 §2.4](docs/05-nova-deep-dive.md#24-operational-dependencies-what-restarts-what) | [CODE] |
| Compute impact | Which inputs change `nova.conf` on every compute? | [docs/05 §2.3](docs/05-nova-deep-dive.md#23-configuration-dependencies-inputs-that-change-novas-files), [docs/02 §5](docs/02-openstack-component-dependencies.md#5-compute-node-dependency-summary) | [CODE] |
| VM impact | Do running VMs survive a `nova_libvirt` restart or recreate? | [docs/05 §5](docs/05-nova-deep-dive.md#5-nova-libvirt-why-its-restart-is-special), [docs/10 §4](docs/10-technical-findings-and-open-questions.md#4-open-questions) ([Q1](docs/10-technical-findings-and-open-questions.md#4-open-questions)) | [NOT AVAILABLE]; what the container and its start path do is [CODE] |
| Data-plane impact | Is VM network traffic interrupted when the OVS agent, `openvswitch_vswitchd` or the L3 agent restarts? | [docs/07 §B.3](docs/07-day2-operational-impact.md#b3-impact-on-networking), [docs/08 §1](docs/08-operational-risk-matrix.md#1-matrix) ([R5](docs/08-operational-risk-matrix.md#1-matrix), [R6](docs/08-operational-risk-matrix.md#1-matrix), [R7](docs/08-operational-risk-matrix.md#1-matrix)), [docs/10 §4](docs/10-technical-findings-and-open-questions.md#4-open-questions) ([Q2–Q4](docs/10-technical-findings-and-open-questions.md#4-open-questions)) | [NOT AVAILABLE]; that the restarts happen is [CODE] |
| `--limit` | What does `--limit` not limit? | [docs/07 §E](docs/07-day2-operational-impact.md#e-execute-a-service-specific-tag-implicit-effects) (row "Actions on hosts outside `--limit`"), [docs/07 §G](docs/07-day2-operational-impact.md#g-add-a-compute-node), [docs/10 §1](docs/10-technical-findings-and-open-questions.md#1-headline-findings) ([F8](docs/10-technical-findings-and-open-questions.md#1-headline-findings), [F9](docs/10-technical-findings-and-open-questions.md#1-headline-findings)) | [CODE] |
| Batching | How do I batch restarts: `ANSIBLE_SERIAL` or `-e kolla_serial=N`? | [docs/04 §5](docs/04-deployment-execution-flow.md#5-batching-serial-and-its-interaction-with-order), [docs/01 §2](docs/01-repository-architecture.md#2-from-cli-to-ansible-playbook), [docs/09 §2.6](docs/09-practical-command-reference.md#26-rolling-reconfigure-with-ansible_serial) | [CODE] |
| Batching | What repeats per batch when `serial` is set? | [docs/03 §2.5](docs/03-ansible-roles-and-tags-mapping.md#25-run_once-with-serial-code) | [CODE] |
| `genconfig` / `deploy-containers` | How do I write the config without restarting, then apply it batch by batch? | [docs/07 §H](docs/07-day2-operational-impact.md#h-separate-write-config-from-apply-recommended-pattern), [docs/09 §2.5](docs/09-practical-command-reference.md#25-compute-changes-in-controlled-batches-recommended-pattern) | [CODE] |
| `genconfig` / `deploy-containers` | What does each action do (`deploy`, `reconfigure`, `upgrade`, `deploy-containers`, `genconfig`, `pull`, `stop`)? | [docs/04 §4](docs/04-deployment-execution-flow.md#4-action-matrix-what-each-kolla_action-does) (action matrix) | [CODE] |
| `genconfig` / `deploy-containers` | Is `reconfigure` lighter than `deploy`? | [docs/01 §4.2](docs/01-repository-architecture.md#42-reconfigure-is-deploy) | [CODE] |
| `kolla_set_configs --check` | How do I see what will restart before a run? | [docs/09 §1](docs/09-practical-command-reference.md#1-inspection-no-changes) (row "See what will restart"), [docs/08 §3](docs/08-operational-risk-matrix.md#3-pre-execution-checklist-applies-to-every-production-run) (step 1) | [CODE] |
| `kolla_set_configs --check` | What does the check compare, what does it never compare, and what do its exit codes mean? | [annex/kolla-images.md §3.1](annex/kolla-images.md#31-what-is-compared), [annex/kolla-images.md §3.2](annex/kolla-images.md#32-what-is-never-compared), [annex/kolla-images.md §3.3](annex/kolla-images.md#33-exit-codes) | [CODE] |
| Images and pull | Why did `deploy` not pick up my rebuilt image? When are images pulled? | [docs/07 §D.1](docs/07-day2-operational-impact.md#d1-how-image-pulling-and-recreation-work-code), [docs/09 §2.10](docs/09-practical-command-reference.md#210-images), [docs/01 §6](docs/01-repository-architecture.md#6-custom-modules--container-lifecycle-via-kolla_docker) | [CODE] |
| Images and pull | What happens if I change the image tag and run `deploy` instead of `upgrade`? | [docs/07 §D.3](docs/07-day2-operational-impact.md#d3-risks), [docs/08 §1](docs/08-operational-risk-matrix.md#1-matrix) ([R12](docs/08-operational-risk-matrix.md#1-matrix)) | [CODE]; whether Neutron's contract migrations then run under live old-version servers is [NOT AVAILABLE] |
| One-shot containers | Which bootstrap (one-shot) containers run on every `deploy`/`reconfigure`, and what do they run inside the image? | [docs/04 §6](docs/04-deployment-execution-flow.md#6-initial-deployment-vs-reconfiguration-what-actually-differs) (which ones still run on `reconfigure`), [annex/kolla-images.md §4](annex/kolla-images.md#4-one-shot-containers-what-the-environment-variables-run) (what each one runs) | [CODE] |
| Scaling | What grows with the number of computes? How many operations at 100 or 500 computes? | [docs/06 §2](docs/06-compute-scaling-and-performance.md#2-work-per-compute-host-read-from-the-task-files), [docs/06 §4.2](docs/06-compute-scaling-and-performance.md#42-operation-counts-by-fleet-size) | [CODE] for the counts; timings are [NOT AVAILABLE] |
| Scaling | Why is a `--limit` run slow on a large inventory? | [docs/06 §6](docs/06-compute-scaling-and-performance.md#6-scaling-at-3-10-and-30-computes-read-from-the-code) (item 5), [docs/08 §1](docs/08-operational-risk-matrix.md#1-matrix) ([R23](docs/08-operational-risk-matrix.md#1-matrix)) | [CODE]; its duration is [NOT AVAILABLE] |
| Scaling | How do I make runs cheaper at scale? | [docs/06 §8](docs/06-compute-scaling-and-performance.md#8-bottlenecks-and-optimisation-opportunities-ranked) (ranked optimisations) | recommendations; item 2 is labelled [CODE] |
| Adding a compute | How do I add a compute node, and what else does the run touch? | [docs/09 §2.11](docs/09-practical-command-reference.md#211-add-a-compute-node) (commands), [docs/07 §G](docs/07-day2-operational-impact.md#g-add-a-compute-node) (what runs where) | [CODE] |
| Membership | What happens when a controller (a RabbitMQ or memcached member) is added or removed? | [docs/07 §F](docs/07-day2-operational-impact.md#f-change-control-plane-membership-add-or-remove-a-controller), [docs/09 §2.12](docs/09-practical-command-reference.md#212-remove-or-replace-a-controller), [docs/08 §1](docs/08-operational-risk-matrix.md#1-matrix) ([R3](docs/08-operational-risk-matrix.md#1-matrix), [R4](docs/08-operational-risk-matrix.md#1-matrix)) | [CODE] for the restarts; the effect on flows and cached tokens is [NOT AVAILABLE] |
| `common` | How do I push fluentd/cron (`common`) changes? Why does `-t common` do nothing? | [docs/03 §2.1](docs/03-ansible-roles-and-tags-mapping.md#21-dynamic-include_tasks-and-tag-inheritance-code) (why), [docs/07 §C.2](docs/07-day2-operational-impact.md#c2-how-common-actually-reaches-hosts) (how `common` reaches hosts), [docs/09 §2.9](docs/09-practical-command-reference.md#29-apply-common-changes-fluentd-cron-kolla_toolbox) (command) | [CODE] |
| Risks | Which operations are dangerous, and what do I check before a run? | [docs/08 §1](docs/08-operational-risk-matrix.md#1-matrix) (25 risks), [docs/08 §3](docs/08-operational-risk-matrix.md#3-pre-execution-checklist-applies-to-every-production-run) (pre-execution checklist) | [CODE] for what Kolla does; [NOT AVAILABLE] for many VM and traffic outcomes |
| Not known | What is not known? | [annex/index.md](annex/index.md#everything-marked-not-available) (everything marked [NOT AVAILABLE], by topic), [docs/10 §4](docs/10-technical-findings-and-open-questions.md#4-open-questions) (open questions), [docs/10 §5](docs/10-technical-findings-and-open-questions.md#5-limits-of-this-study) (limits of the study), [annex/kolla-images.md §7](annex/kolla-images.md#7-what-is-not-available-from-the-sources) | [NOT AVAILABLE] |

## Documents

| # | Document | Answers |
|---|---|---|
| 01 | [Repository Architecture](docs/01-repository-architecture.md) | How a CLI command becomes an `ansible-playbook` run; site.yml anatomy; role skeleton; `kolla_docker`; config overrides; inventory |
| 02 | [OpenStack Component Dependencies](docs/02-openstack-component-dependencies.md) | Installation, configuration, runtime and operational dependencies of infra and control-plane services |
| 03 | [Ansible Roles and Tags Mapping](docs/03-ansible-roles-and-tags-mapping.md) | What each tag executes, on which hosts, with which handlers, and why tag names mislead |
| 04 | [Deployment Execution Flow](docs/04-deployment-execution-flow.md) | Play order, intra-role order, handler flush points, batching; 5 Mermaid flow diagrams plus a batching Gantt chart |
| 05 | [Nova Deep Dive](docs/05-nova-deep-dive.md) | Nova roles, plays, cells, discovery, dependencies, libvirt restart semantics |
| 06 | [Compute Scaling and Performance](docs/06-compute-scaling-and-performance.md) | What grows with compute count; per-compute task chains; model for 10–500 computes; optimisations |
| 07 | [Day-2 Operational Impact](docs/07-day2-operational-impact.md) | Scenarios A–I (reconfigure Nova/Neutron/common, images, service tags, membership changes, adding computes) |
| 08 | [Operational Risk Matrix](docs/08-operational-risk-matrix.md) | 25 risks with blast radius, VM/API impact, precautions; pre-execution checklist |
| 09 | [Practical Command Reference](docs/09-practical-command-reference.md) | Real commands, their scope and impact; safe patterns |
| 10 | [Technical Findings and Open Questions](docs/10-technical-findings-and-open-questions.md) | Findings, bugs and limitations, open questions (each answered from the code or marked not available) |

Each document starts with its key answers, a table of contents and its closest related documents.

Annexes:

- [annex/index.md](annex/index.md) — navigation index: tag index, service index, glossary, and the list of everything
  marked [NOT AVAILABLE].
- [annex/service-cards.md](annex/service-cards.md) — one card per core service (22 cards): role, play, tags, task flow,
  templates, handlers, key variables, node types touched. Generated by [tools/service_cards.py](tools/service_cards.py).
- [annex/generated-inventory.md](annex/generated-inventory.md) — every play, container, role and handler, extracted from
  the source by [tools/extract_kolla_inventory.py](tools/extract_kolla_inventory.py).
- [annex/factsheets/](annex/factsheets/README.md) — per-role fact sheets with `path:line` evidence: A infra/LB/OVN, B
  MariaDB/RabbitMQ/Keystone, C Glance/Placement/Cinder/Horizon/Heat, D Barbican/Octavia/Swift/Manila and compute-side
  roles, E host bootstrap and operational playbooks. Read the correction in [docs/10
  §3](docs/10-technical-findings-and-open-questions.md#3-corrections-to-the-annex-fact-sheets).
- [annex/kolla-images.md](annex/kolla-images.md) — what the kolla images do at start and in one-shot containers:
  `kolla_start`, `kolla_set_configs` and its `--check`, `KOLLA_BOOTSTRAP`/`KOLLA_UPGRADE`/`KOLLA_OSM` per image; read
  from the kolla `ussuri-eol` image sources.
- [annex/listings/](annex/listings/README.md) — Ansible 2.9.27's own parse of the unmodified playbooks: the
  `--list-tags` output of `site.yml` and its `--list-tasks -t nova` output. Nothing was executed against a host.

## Ten things to know before running Kolla-Ansible Ussuri on production

1. **`reconfigure` is `deploy`** for 70 of the 72 roles that have a `reconfigure.yml`. It re-runs Keystone registration,
   DB creation and the DB-sync bootstrap containers for most services; Neutron's DB sync is the default exception. The
   only lightweight path is `genconfig` followed by `deploy-containers` ([docs/04
   §4](docs/04-deployment-execution-flow.md#4-action-matrix-what-each-kolla_action-does)).
2. **Config is applied by a full stop/start, never a reload, and the effective SIGKILL timeout is 10 s.**
   `docker_graceful_timeout` is silently ignored ([docs/01
   §6](docs/01-repository-architecture.md#6-custom-modules--container-lifecycle-via-kolla_docker)). The only signal
   Kolla sends is a `SIGHUP` to `nova_scheduler`, which refreshes its cell cache.
3. **One changed container restarts all containers of its role on that host** (Ansible 2.9 loop-notify). A nova-compute
   config change restarts **nova_libvirt** on every compute ([docs/03
   §2.4](docs/03-ansible-roles-and-tags-mapping.md#2-ansible-29-semantics-that-kolla-relies-on)).
4. **Without batching, handlers restart a service on every host of the play at once.** Batching is `ANSIBLE_SERIAL` for
   `reconfigure`/`upgrade` and `-e kolla_serial=N` for `deploy`, which ignores `ANSIBLE_SERIAL`. Only MariaDB (4 waves)
   and RabbitMQ (one by one) roll by themselves.
5. **A service tag is never just that service.** For a service with a frontend it also runs the haproxy frontend config
   (and can restart HAProxy). It runs the `common` role on every host of the play (memcached and multipathd excepted)
   and, for API services, Keystone registration and DB sync ([docs/03
   §3](docs/03-ansible-roles-and-tags-mapping.md#3-what-a-tag-really-executes-master-table), [docs/07
   §E](docs/07-day2-operational-impact.md#e-execute-a-service-specific-tag-implicit-effects)).
6. **`-t common` does nothing** ([docs/03
   §2.1](docs/03-ansible-roles-and-tags-mapping.md#21-dynamic-include_tasks-and-tag-inheritance-code)). Use `-t chrony`
   or a service tag to push fluentd/cron changes.
7. **Global settings land in per-host files.** `enable_*`, RabbitMQ/memcached membership and passwords end up in
   compute-side configs, so small central changes cause fleet-wide restarts ([docs/07
   §I](docs/07-day2-operational-impact.md#i-why-a-small-change-can-create-a-large-workload)).
8. **`deploy` never pulls an image that is already present.** Rebuilt images under the same tag need `pull`. A tag
   change applied with `deploy` recreates the entire fleet at once ([docs/07
   §D](docs/07-day2-operational-impact.md#d-update-container-images)).
9. **`--limit` does not contain everything.** Delegated tasks still run on `groups[x][0]` controllers, and all hosts'
   facts are gathered serially by the limited hosts ([docs/06](docs/06-compute-scaling-and-performance.md), [docs/07
   §G](docs/07-day2-operational-impact.md#g-add-a-compute-node)).
10. **`--list-tasks` cannot predict a run.** Use `genconfig` plus `kolla_set_configs --check`, or staging ([docs/09
    §1](docs/09-practical-command-reference.md#1-inspection-no-changes)). Two things to know about the check:
    - **It compares only the files listed in `config.json`**, not its `command` or `permissions`: memcached lists no
      files, so a change to its command line never shows as drift. A plain `reconfigure` still applies it (the changed
      `config.json` notifies the restart handler), but once `genconfig` has written it, no later run restarts the
      container for it; it takes effect at the next restart for another reason ([docs/09
      §2.5](docs/09-practical-command-reference.md#25-compute-changes-in-controlled-batches-recommended-pattern)).
    - **A newly rendered optional file** whose destination is not yet in the container makes `--check` exit 2, unless an
      entry listed before it already differs (then it exits 1 and the container restarts). Exit 2 is real drift, but the
      check task fails instead of restarting the container ([annex/kolla-images.md
      §3](annex/kolla-images.md#3-kolla_set_configs---check-what-it-compares-and-its-exit-codes)).

## Where the final-objective questions are answered

| Question | Short answer | Details |
|---|---|---|
| If I execute a specific tag, exactly what happens? | The tagged plays run on all their hosts. The haproxy frontend of that service, if it has one, is re-rendered. `common` runs on every host of the play (not for memcached or multipathd). For API services, Keystone registration and DB-sync containers run (Neutron's DB sync only on `deploy` by default, not on `reconfigure`). Handlers restart drifted containers, plus their role siblings | [docs/03 §3](docs/03-ansible-roles-and-tags-mapping.md#3-what-a-tag-really-executes-master-table), [docs/07 §E](docs/07-day2-operational-impact.md#e-execute-a-service-specific-tag-implicit-effects), [annex/service-cards.md](annex/service-cards.md) |
| Which OpenStack components are affected? | The tagged service, plus HAProxy (only if its frontend changed), plus fluentd/cron/kolla_toolbox (if `common` drifted) | [docs/07 §E](docs/07-day2-operational-impact.md#e-execute-a-service-specific-tag-implicit-effects) |
| Which compute nodes will receive changes? | Every compute in the play's host patterns (`nova`, `nova-cell`, `neutron`, `openvswitch`, `chrony`, `iscsi`, …) runs the tasks. Restarts happen where drift exists, usually all or none, because inputs are global | [docs/06 §2](docs/06-compute-scaling-and-performance.md#2-work-per-compute-host-read-from-the-task-files), [docs/07 §A.3](docs/07-day2-operational-impact.md#a3-are-all-compute-nodes-affected-does-nova-compute-restart-on-every-compute) |
| Will containers restart or be recreated? | Restart (stop 10 s → start) on config drift. Recreate on image or parameter change. Never on no-change runs, except containers whose `config.json` has an entry that `kolla_set_configs --check` always reports as drift (e.g. `prometheus_server` once files exist under `/etc/kolla/config/prometheus/extras/`: that `preserve_properties` entry has no `perm`); they restart on every deploy/reconfigure. Siblings in the same role restart too | [docs/01 §4.3](docs/01-repository-architecture.md#43-the-config--check--handler-pattern), [docs/03 §2.4](docs/03-ansible-roles-and-tags-mapping.md#24-loop-notify-one-changed-item-notifies-the-handlers-of-all-items-code), [annex/kolla-images.md §3](annex/kolla-images.md#3-kolla_set_configs---check-what-it-compares-and-its-exit-codes) |
| Can running VMs be impacted? | Directly through `nova_libvirt` restarts (frequent, via loop-notify) and OVS/vswitchd or L3-agent restarts. Whether VMs survive a libvirt restart is not available from the sources | [docs/05 §5](docs/05-nova-deep-dive.md#5-nova-libvirt-why-its-restart-is-special), [docs/08](docs/08-operational-risk-matrix.md) [R1](docs/08-operational-risk-matrix.md#1-matrix)/[R6](docs/08-operational-risk-matrix.md#1-matrix)/[R7](docs/08-operational-risk-matrix.md#1-matrix), [docs/10](docs/10-technical-findings-and-open-questions.md) [Q1–Q4](docs/10-technical-findings-and-open-questions.md#4-open-questions) |
| What is the execution order? | `site.yml` play order (no dependency resolver); within a role: register → config → check → bootstrap → flush | [docs/04](docs/04-deployment-execution-flow.md) |
| Which tasks can take hours with hundreds of computes? | Per-compute task chains multiplied by ⌈C/forks⌉ waves, serial fact gathering under `--limit`, image pulls (one per container placed on the compute, [docs/02 §5](docs/02-openstack-component-dependencies.md#5-compute-node-dependency-summary)), per-batch waits under `serial` | [docs/06 §3–4](docs/06-compute-scaling-and-performance.md#3-expensive-tasks-and-their-scaling-factors) |
| Why does a small change generate a large workload? | Global inputs are rendered into per-host files; loop-notify; every run re-executes the full per-host chain | [docs/06 §5](docs/06-compute-scaling-and-performance.md#5-why-a-small-change-becomes-a-large-workload), [docs/07 §I](docs/07-day2-operational-impact.md#i-why-a-small-change-can-create-a-large-workload) |
| How can I minimise the operational impact? | `genconfig` + diff + `deploy-containers --limit` batches; narrow tags with `--skip-tags haproxy`; `ANSIBLE_SERIAL`; pre-pull; fact caching and pipelining; avoid global drift | [docs/08 §3](docs/08-operational-risk-matrix.md#3-pre-execution-checklist-applies-to-every-production-run), [docs/09 §2](docs/09-practical-command-reference.md#2-day-2-commands), [docs/06 §8](docs/06-compute-scaling-and-performance.md#8-bottlenecks-and-optimisation-opportunities-ranked) |

## Method

| Phase | What was done |
|---|---|
| 1. Source exploration | Cloned `ussuri-eol`; read `tools/kolla-ansible`, `site.yml`, `nova.yml`, `gather-facts.yml`, `group_vars/all.yml`, the `kolla_docker`/`kolla_toolbox` modules, `merge_configs`, filters, and the `common`, `nova`, `nova-cell`, `neutron`, `openvswitch` and service-* helper roles in full. Also read the kolla image repository (`ussuri-eol`) for the image start path and the one-shot containers ([annex/kolla-images.md](annex/kolla-images.md)) |
| 2. Static analysis | Generated tables of all plays, containers, roles and handlers (`tools/extract_kolla_inventory.py`). Five parallel source-reading passes produced the fact sheets, which were then spot-checked |
| 3. Dependency mapping | Template references, transport URLs and group loops → [docs/02](docs/02-openstack-component-dependencies.md) |
| 4. Performance analysis | Per-host task chains read from the role sources and the `--list-tasks` listing → [docs/06](docs/06-compute-scaling-and-performance.md) |
| 5. Operational analysis | Day-2 scenarios traced through the role sources → [docs/07](docs/07-day2-operational-impact.md), [08](docs/08-operational-risk-matrix.md) |
| 6. Validation | Ansible 2.9.27 (the supported version): `--list-tags`/`--list-tasks` listings of the real playbook ([annex/listings/](annex/listings/README.md)); loop-notify and tag inheritance read in the Ansible 2.9.27 source; the `kolla_docker` timeout override read in the module source |

### Evidence labels

The same two labels are used everywhere, and this is their single definition. The study rests only on reading source
code; nothing was run against a host, and no run is used as evidence.

- **[CODE]** shown by the sources, with a `path:line` citation nearby: kolla-ansible `ussuri-eol` (unprefixed paths),
  the kolla image repository `ussuri-eol` when the path has a `kolla` prefix (e.g. kolla
  `docker/base/set_configs.py:407-410`), the Ansible source when the path has an `ansible 2.9.27` prefix (or `ansible
  2.8.20`, read for comparison), and the `--list-tags` and `--list-tasks` listings in
  [annex/listings/](annex/listings/README.md) (Ansible's own parse of the playbooks).
- **[NOT AVAILABLE]** the sources do not establish it.

The fact sheets use the words FACT and NOT AVAILABLE for the same two levels.

## Repository layout

```
README.md
docs/            01–10 deliverables
annex/
  index.md       tag index, service index, glossary, NOT AVAILABLE list
  generated-inventory.md
  kolla-images.md
  service-cards.md
  factsheets/    A–E per-role evidence
  listings/      --list-tags and --list-tasks outputs
tools/
  extract_kolla_inventory.py
  service_cards.py
```
