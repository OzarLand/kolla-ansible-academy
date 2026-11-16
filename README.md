# Kolla-Ansible Ussuri — Reverse Engineering for Day-2 Operations

A source-level and execution-level study of **Kolla-Ansible `ussuri-eol`** (`openstack/kolla-ansible`, tag
`ussuri-eol`, HEAD `8a94fe9`). It covers how Kolla-Ansible orchestrates an OpenStack platform, what each tag really
executes, how runs scale with the number of compute nodes, and what Kolla-Ansible commands do to a running production
platform.

All conclusions come from the Ussuri implementation, not from newer releases. Each one is labelled with its evidence
level.

## Documents

| # | Document | Answers |
|---|---|---|
| 01 | [Repository Architecture](docs/01-repository-architecture.md) | How a CLI command becomes an `ansible-playbook` run; site.yml anatomy; role skeleton; `kolla_docker`; config overrides; inventory |
| 02 | [OpenStack Component Dependencies](docs/02-openstack-component-dependencies.md) | Installation, configuration, runtime and operational dependencies of infra and control-plane services |
| 03 | [Ansible Roles and Tags Mapping](docs/03-ansible-roles-and-tags-mapping.md) | What each tag executes, on which hosts, with which handlers, and why tag names mislead |
| 04 | [Deployment Execution Flow](docs/04-deployment-execution-flow.md) | Play order, intra-role order, handler flush points, batching; 5 Mermaid diagrams |
| 05 | [Nova Deep Dive](docs/05-nova-deep-dive.md) | Nova roles, plays, cells, discovery, dependencies, libvirt restart semantics |
| 06 | [Compute Scaling and Performance](docs/06-compute-scaling-and-performance.md) | What grows with compute count; measured task counts; model for 10–500 computes; optimisations |
| 07 | [Day-2 Operational Impact](docs/07-day2-operational-impact.md) | Scenarios A–I (reconfigure Nova/Neutron/common, images, service tags, membership changes, adding computes) |
| 08 | [Operational Risk Matrix](docs/08-operational-risk-matrix.md) | 25 risks with blast radius, VM/API impact, precautions; pre-execution checklist |
| 09 | [Practical Command Reference](docs/09-practical-command-reference.md) | Real commands, their scope and impact; safe patterns |
| 10 | [Technical Findings and Open Questions](docs/10-technical-findings-and-open-questions.md) | Findings, bugs and limitations, open questions with experiment designs |

Annexes:

- [annex/generated-inventory.md](annex/generated-inventory.md) — every play, container, role and handler, extracted from
  the source by [tools/extract_kolla_inventory.py](tools/extract_kolla_inventory.py).
- [annex/factsheets/](annex/factsheets/) — per-role fact sheets with `path:line` evidence: A infra/LB/OVN,
  B MariaDB/RabbitMQ/Keystone, C Glance/Placement/Cinder/Horizon/Heat, D Barbican/Octavia/Swift/Manila and
  compute-side roles, E host bootstrap and operational playbooks. Read the correction in docs/10 §3.
- [annex/lab/](annex/lab/README.md) — the execution lab (real `site.yml` against simulated hosts), scenario results,
  and minimal reproductions of the Ansible behaviours Kolla depends on.

## Ten things to know before running Kolla-Ansible Ussuri on production

1. **`reconfigure` is `deploy`.** It re-runs Keystone registration, DB creation and the DB-sync bootstrap containers
   for most services. There is no lightweight path except `genconfig` followed by `deploy-containers` (docs/04 §4).
2. **Restarts are full stop/start, never reload, with an effective 10 s SIGKILL timeout.** `docker_graceful_timeout`
   is silently ignored (docs/01 §6, proven).
3. **One changed container restarts all containers of its role on that host** (Ansible 2.9 loop-notify). A
   nova-compute config change restarts **nova_libvirt** on every compute (docs/03 §2.4, proven).
4. **Without `ANSIBLE_SERIAL`, handlers restart a service on every host of the play at once.** Only MariaDB (4 waves)
   and RabbitMQ (one by one) roll by themselves.
5. **A service tag is never just that service.** It also runs the haproxy frontend config (and can restart HAProxy),
   the `common` role on every host of the play, Keystone registration and DB sync (docs/07 §E).
6. **`-t common` does nothing** (docs/03 §2.1, proven). Use `-t chrony` or a service tag to push fluentd/cron changes.
7. **Global settings land in per-host files.** `enable_*`, RabbitMQ/memcached membership and passwords end up in
   compute-side configs, so small central changes cause fleet-wide restarts (docs/07 §I).
8. **`deploy` never pulls an image that is already present.** Rebuilt images under the same tag need `pull`. A tag
   change applied with `deploy` recreates the entire fleet at once (docs/07 §D).
9. **`--limit` does not contain everything.** Delegated tasks still run on `groups[x][0]` controllers, and all hosts'
   facts are gathered serially by the limited hosts (docs/06, docs/07 §G).
10. **`--list-tasks` cannot predict a run.** Use `genconfig` plus `kolla_set_configs --check`, staging, or the lab
    approach (docs/09 §1).

## Method

| Phase | What was done |
|---|---|
| 1. Source exploration | Cloned `ussuri-eol`; read `tools/kolla-ansible`, `site.yml`, `nova.yml`, `gather-facts.yml`, `group_vars/all.yml`, the `kolla_docker`/`kolla_toolbox` modules, `merge_configs`, filters, and the `common`, `nova`, `nova-cell`, `neutron`, `openvswitch` and service-* helper roles in full |
| 2. Static analysis | Generated tables of all plays, containers, roles and handlers (`tools/extract_kolla_inventory.py`). Five parallel source-reading passes produced the fact sheets, which were then spot-checked |
| 3. Dependency mapping | Template references, transport URLs and group loops → docs/02 |
| 4. Performance analysis | Per-host task profiles and scale runs in the lab → docs/06 |
| 5. Operational analysis | 21 Day-2 scenarios executed in the lab → docs/07, 08 |
| 6. Validation | Ansible 2.9.27 (the supported version): `--list-tags`/`--list-tasks` on the real playbook; full execution with stub modules; minimal reproductions of loop-notify, tag inheritance and the `kolla_docker` timeout override |

Evidence labels used everywhere:

- **[CODE]** read in the source.
- **[ANSIBLE]** Ansible 2.9 semantics, verified.
- **[LAB]** observed when executing the real playbooks.
- **[HYPOTHESIS]** inferred.
- **[NEEDS-LAB]** needs a real environment; experiments are designed in docs/10 §4.

## Repository layout

```
README.md
docs/            01–10 deliverables
annex/
  generated-inventory.md
  factsheets/    A–E per-role evidence
  lab/           harness, results, minimal reproductions
tools/
  extract_kolla_inventory.py
```
