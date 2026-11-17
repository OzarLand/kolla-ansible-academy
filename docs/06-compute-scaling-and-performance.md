# 06 — Compute Scaling and Performance

Which Kolla-Ansible Ussuri operations grow with the number of compute nodes, why, and how to bound them.

> **No production timings are invented here.** Work is expressed as *operation counts* (measured in the lab by
> executing the real playbooks) and as formulas whose parameters you measure in your own environment. Every lab wall
> time in this document is labelled as such; lab runs use a local connection with no SSH, on a 4-vCPU deploy host.

---

## 1. How Ansible 2.9 spends time in Kolla-Ansible

| Factor | Mechanism | Consequence for Kolla |
|---|---|---|
| **Linear strategy (default)** | A task runs on **all hosts of the play** (up to `forks` at a time), and the **next task starts only when every host has finished the current one** | The slowest host sets the pace of every task. One slow compute (disk, SSH, Docker) slows the whole fleet |
| **forks** (Ansible default 5; Kolla docs suggest 20–100) | Max parallel host executions per task | A task on *H* hosts needs ⌈H/F⌉ waves |
| **Loops** (`with_dict: <role>_services`, `with_items`) | Items run **sequentially on each host**; each item that passes its `when` is a separate module execution (separate remote command); skipped items run no module | `config.yml` and `check-containers.yml` cost *items × invocation latency* per host |
| **Remote module invocation** | Without pipelining, each invocation = SSH exec to create a tmp dir, transfer the AnsiballZ payload, run it, clean up. With `become`, `sudo` is added | The fixed cost per invocation dominates idempotent runs |
| **Deploy-host templating** | `template` and `merge_configs` render **on the deploy host** for every host and item, then `copy` compares checksums remotely | Deploy-host CPU scales with hosts × templates. `nova.conf.j2` and `neutron.conf.j2` are large, with loops over groups |
| **Controller-side tasks** | `group_by`, `set_fact`, `include_*`, `meta` run in Ansible workers without SSH | Cheap per host, but not free: the 69-item `group_by` loop costs about 0.3 s of deploy-host CPU per host, measured with a single host [LAB]. In the 11-host runs each host's loop took ≈0.9 s of wall time because all hosts compete for the 4 vCPUs |
| **`run_once` / `delegate_to`** | Run once (per batch) on one host | Constant cost unless `serial` multiplies it |
| **Handlers** | Run at flush points on notified hosts, in parallel up to `forks` | Restart time of the slowest container on the slowest host |
| **`until`/`retries` loops** | e.g. compute registration wait (20 × 10 s), Keystone registration retries (5 × 10 s), `wait_for` | Add wall time even when nothing is wrong (first iteration usually succeeds) |
| **Fact gathering** | `setup` on every host at the start (`gather-facts.yml`). With `--limit`, the limited hosts gather **all other hosts' facts sequentially** in a delegated loop | O(total hosts) serial latency per limited run without fact caching |

---

## 2. Measured work per compute host (lab, real playbooks)

Counts below come from the execution trace of the unmodified `site.yml`
([annex/lab/results.md](../annex/lab/results.md)), for the default Ussuri service set with Cinder LVM (which adds
`iscsid` on computes).

- A "task result" is one task × one host, including skipped tasks.
- A "remote invocation" is one module execution on the host, counting each executed loop item. Loop items skipped by
  `when` run no module and are not counted (for example, on a compute at least 5 of the 8 items of each
  `nova_cell_services` loop are skipped).
- Controller-only work is excluded from the invocation count: `group_by`, `set_fact`, `include_*`.
- Each `template`, `copy` or `merge_configs` item counts as one invocation, although the copy action behind them runs
  two modules on the host when the file is unchanged (remote `stat`, then `file`). SSH round trips are therefore
  higher than the invocation count.
- Where a range is given, the higher figure is compute001, which also runs the delegated `run_once` steps (compute
  discovery on control01 and, in `-t nova` runs, four `find` calls on the deploy host).

| Action | Task results per compute | Executed (non-skipped) | Remote module invocations per compute | `compare_container` calls per compute (one `docker exec kolla_set_configs --check` each when the container exists) | Run |
|---|---|---|---|---|---|
| `deploy` (first time) | 141–146 | 80–85 | ≈91–94 | 11 calls, 0 execs (containers missing) | t0 |
| `deploy` (no change) | 127–132 | 66–71 | ≈77–80 | 11 | t1 |
| `reconfigure` (no tag, no change) | 127–132 | 66–71 | ≈77–80 | 11 | s18 |
| `-t nova reconfigure` (no change) | 56–65 | 33–42 | ≈46–53 | 6 (3 common + 3 nova) | s01 |
| `-t nova reconfigure --limit compute001` | 71 | 47 | ≈57 + delegated fact loop (10) | 6 | s13 |
| `-t nova deploy-containers --limit compute001` | 19 | 15 | 11 + delegated fact loop (10) | 6 | s15 |
| `pull` (all) | 30 | 19 | 13 (11 image pulls) | 0 | s10 |
| `-t haproxy reconfigure` | 5 (facts + group_by only) | 5 | 1 (`setup`) | 0 | s19 |

Breakdown of the ≈46 remote invocations of a no-change `-t nova` run on one compute (s01, compute002/003; compute001
adds 7 delegated invocations, for 53):

| Kind | Invocations | Source |
|---|---|---|
| `template` items (config.json ×3 common, td-agent, logrotate, module-load persistence, udev rule, config.json nova-cell ×3, libvirt ×2, SASL ×3, ssh files ×4) | 19 | common, module-load, nova-cell `config-host.yml` + `config.yml` |
| `file` items (config dirs ×3 common and ×3 nova-cell, ownership ×2, kolla_logs link) | 9 | common + nova-cell |
| `kolla_docker` (compare_container ×6, ensure_image, create_volume) | 8 | check-containers, common |
| `merge_configs` (nova.conf ×1 on a compute) | 1 | nova-cell `config.yml` |
| `sysctl` ×4, `modprobe`, `stat`, `copy`, `setup`, `docker_image_info` | 9 | facts, common, module-load, nova-cell `config-host.yml` |

Per **controller** the numbers are 2–3× higher (≈300–440 task results for a full deploy), but controllers are few.
Compute-side work is what scales.

### 2.1 Fleet totals scale linearly

Total task results ≈ `fixed + Σ_hosts per-host count`:

- **Full no-change `reconfigure`, 3 computes [LAB s18]:** 1,856 task results across 10 hosts, of which 386 are on the
  3 computes.
- **Each additional compute adds:**
  - ≈130 task results (≈77 remote invocations, 11 `kolla_set_configs --check` execs once its containers exist) to
    every no-change full `deploy`/`reconfigure` (a first deploy adds ≈141 task results and ≈91 invocations);
  - ≈60 task results (≈46 invocations, 6 checks) to every `-t nova` run.

Measured scaling runs (10 and 30 computes, forks 5/20/50) are in §6.

---

## 3. Expensive tasks and their scaling factors

Scope legend:

- **D** = once per deployment (`run_once`, delegated);
- **Ctl** = once per controller;
- **C** = once per compute;
- **C×S** = once per compute and per container/service;
- **H** = once per host of any kind;
- **Cond** = only when a condition holds (e.g. drift).

| Task | Role / file | Target hosts | Scope | Scaling factor | Why it can be slow | Optimisation |
|---|---|---|---|---|---|---|
| Fact gathering (`setup`) | `gather-facts.yml:5-21` | all | H | ⌈N/F⌉ waves | full `setup` collects hardware, network (many interfaces with OVS/Neutron), mounts; facter/ohai if present | `kolla_ansible_setup_filter: "ansible_[!qt]*"` (skips `qvo`/`tap` interface facts), `kolla_ansible_setup_gather_subset`, fact caching (`gathering = smart` + jsonfile) — documented in `doc/source/user/ansible-tuning.rst` |
| Delegated fact gathering under `--limit` | `gather-facts.yml:29-50` | limited hosts gather everyone | **N sequential per limited host** (N/L each) | O(N) serial | `delegate_to` loop runs items one after another | Fact cache; avoid `--limit` with a single host on huge inventories, or pre-warm the cache with a full facts run |
| `group_by` enabled services (69 items) | `site.yml:21-95` | all | H (deploy-host CPU) | N × 69 | templating each item | none needed below ~1,000 hosts; it *saves* time later by eliminating disabled plays |
| `common` config + check | `roles/common/tasks/config.yml`, `check-containers.yml` | every host, in the first matching play | H × ~18 invocations | N | 3 container checks (`docker exec` each) + ~12 templates/files | `--limit` batches; it cannot be skipped selectively (`-t common` is a no-op) |
| `nova-cell` config | `roles/nova-cell/tasks/config.yml` | computes + conductors | C × ~24 invocations (with `config-host.yml` and its `module-load` include) | C | `merge_configs` renders `nova.conf.j2` **on the deploy host for every compute**; per-item template loops | Deploy-host CPU (more cores, fewer forks than cores × ~2); `--limit` |
| `nova-cell` check-containers | `check-containers.yml` | computes | C×S (3 containers) | 3C `docker exec` | `kolla_set_configs --check` starts a Python process in each container | – |
| Compute registration wait | `nova-cell/tasks/wait_discover_computes.yml` | first compute of each batch, delegated to conductor | D per batch | up to 20 × 10 s per batch; **multiplied by the number of batches when `serial` is used** | waits until *all* computes of the batch appear in `compute service list` | Keep batches large for this play, or run it once at the end |
| `discover_hosts --by-service` | `discover_computes.yml` | conductor[0] | D per batch | cell size (it scans services) | one nova-manage call per batch | – |
| Keystone registration | `service-ks-register` | first host | D per play/batch | per service (×5 retries max) | runs `ansible` inside `kolla_toolbox` (container exec + Python startup) | – |
| DB-sync bootstrap containers | `<role>/tasks/bootstrap_service.yml` | first host | D (per batch with serial) | per service | container create + DB migration check | Skip by using `deploy-containers` for config-only applies |
| OVS post-config | `roles/openvswitch/tasks/post-config.yml` | network + computes | C (1 `docker exec`, `Set system-id`; the bridge check `kolla_ensure_openvswitch_configured` runs on network hosts, and on computes only when `computes_need_external_bridge` is true: DVR, provider networks or OVN distributed FIP) | C | always runs; `Set system-id` always "changed" | – |
| Neutron config-host | `roles/neutron/tasks/config-host.yml` | network + computes | C | C | module load, sysctl | – |
| Neutron config + check | `roles/neutron/tasks/config.yml` | network + computes + controllers | C × ~5 | C | `merge_configs` of `neutron.conf` and `openvswitch_agent.ini` per host | – |
| Image pull | `service-images-pull` | every host | C×S (11 images per compute in the lab profile) | C × image size | registry bandwidth, disk I/O, layer extraction | Local registry mirror close to the computes; pre-pull before maintenance; `--forks` to cap registry load |
| Container (re)creation | handlers | notified hosts | Cond, C×S | number of drifted containers | stop (10 s max), rm, create, start; `kolla_set_configs` on start | Batch with `--limit`/serial; avoid unnecessary drift (§5) |
| nova-libvirt restart | nova-cell handler | computes | Cond (any nova-compute drift) | C | `retries: 5`; SASL user re-creation after it | Avoid compute-side drift; batch |
| Fluentd/cron/toolbox restart | common handlers | all hosts reached | Cond (any service enabled/disabled) | N | – | Batch fleet-wide changes |
| `/etc/hosts` template | `roles/baremetal` (`bootstrap-servers`) | all | H, content O(N) | **N²** templating | loops over every baremetal host | Run `bootstrap-servers` only when adding hosts |
| Docker daemon restart | `roles/baremetal/tasks/post-install.yml:231-237` | all | Cond | N simultaneous | restarts every container on the host | `-e kolla_serial=…` with `bootstrap-servers` |
| SSH connection setup | Ansible ssh connection plugin | all | H (handshake once per host, again after 60 s idle) | invocations × SSH round trips | Ansible 2.9 already multiplexes connections without any `ansible.cfg` (default `ssh_args = -C -o ControlMaster=auto -o ControlPersist=60s`). Kolla ships no `ansible.cfg`, so `pipelining` stays off and each invocation still makes several round trips (tmp dir, transfer, exec, cleanup) | `pipelining = True` (requires no `requiretty`). On large fleets, a longer persistence such as `ssh_args = -C -o ControlMaster=auto -o ControlPersist=30m` |
| Certificate distribution | `service-cert-copy` (when `kolla_copy_ca_into_containers`) | every service config dir | C×S | per service | `copy` per service dir | Only enable when needed |

---

## 4. Performance model for 10 / 50 / 100 / 200 / 500 computes

### 4.1 Model

For a play whose tasks all run on the compute group (the nova-cell, openvswitch and neutron plays are dominated by
it):

```
T_play ≈ Σ_tasks [ ceil(H_task / F_eff) × items_task × t_inv ]      (remote work, per-task barrier)
       + Σ_tasks [ H_task × t_render_task / P ]                       (deploy-host templating, P cores)
       + Σ_delegated/run_once steps                                    (constant per batch)
       + T_handlers (if drift)                                         (≈ max over hosts of restart time)
```

- `H` = hosts in the play (computes + the few others).
- `F_eff` = min(forks, what the deploy host CPU and SSH can sustain).
- `t_inv` = latency of one remote module invocation: SSH round trips, AnsiballZ transfer, Python start, `sudo`. It is
  **not measured here**; measure it as the median per-task time on a single host with `-vvv` timestamps or the
  `profile_tasks` callback.
- `t_render` = deploy-host CPU time to render a template for one host.

Because of the per-task barrier, the critical path of a play is **(number of executed task-items on the slowest host) ×
⌈H/F⌉ waves**. Adding computes adds waves, not tasks.

### 4.2 Operation counts by fleet size

Built from the per-compute counts measured in §2. The "Waves per task" columns give ⌈C/F⌉ for compute hosts at
F = 20, 50 and 100; the worked examples below use F = 50. The waves multiply the per-host
invocation chain, they do not add tasks.

| Computes (C) | Compute task results, full `reconfigure` (≈130·C) | Compute remote invocations, full `reconfigure` (≈77·C) | `kolla_set_configs --check` execs on computes (11·C) | Compute task results, `-t nova` (≈60·C) | Invocations, `-t nova` (≈46·C) | Waves per task at F=20 | Waves per task at F=50 | Waves per task at F=100 | Image pulls for a full image update (11·C) | Delegated fact `setup` calls with `--limit <1 host>` (≈C + 7: every other inventory host of the lab layout) |
|---|---|---|---|---|---|---|---|---|---|---|
| 10 | 1,300 | 770 | 110 | 600 | 460 | 1 | 1 | 1 | 110 | ~17 |
| 50 | 6,500 | 3,850 | 550 | 3,000 | 2,300 | 3 | 1 | 1 | 550 | ~57 |
| 100 | 13,000 | 7,700 | 1,100 | 6,000 | 4,600 | 5 | 2 | 1 | 1,100 | ~107 |
| 200 | 26,000 | 15,400 | 2,200 | 12,000 | 9,200 | 10 | 4 | 2 | 2,200 | ~207 |
| 500 | 65,000 | 38,500 | 5,500 | 30,000 | 23,000 | 25 | 10 | 5 | 5,500 | ~507 |

Reading the table:

- **No-change `-t nova reconfigure`, C=500, F=50.** Each compute runs a chain of ≈46 remote invocations. With 10
  waves per task, the compute-side critical path is ≈ **460 × t_inv** plus deploy-host templating
  (500 × nova.conf renders) and the constant delegated steps. Nothing restarts, and yet the run still costs
  ~23,000 remote invocations and 3,000 `docker exec` config checks (6 per compute).
- **The same run after a global change** (e.g. `enable_barbican`) adds a handler phase: 500 × (nova_ssh + nova_libvirt
  + nova_compute + 3 common containers) = **3,000 container restarts**, all in the same flush unless batched.
- **Image updates multiply data volume.** A tag change downloads 11 images per compute: 5,500 image pulls at C=500.
  Registry egress ≈ C × Σ(size of the new layers) [measure image sizes, Q8 in docs/10]. With the default
  `forks`/serial, this traffic is concurrent across up to `forks` hosts.
- **Fact gathering with `--limit`.** Gathering all ~510 hosts serially from one host costs ≈510 × t_setup before any
  real work. Fact caching removes it.

### 4.3 What is constant, per batch, or per host

| Constant (D) | Per batch (with `serial`) | Per controller | Per compute | Per container | Conditional |
|---|---|---|---|---|---|
| Keystone registration, DB create/grant, DB-sync containers, cell create/update, `map_cell0`, haproxy frontend rendering (per haproxy host) | all `run_once` steps above, compute registration wait (≤200 s), `discover_hosts` | API configs, MariaDB/RabbitMQ rolling restarts (per DB/MQ node) | facts, `group_by`, common, config-host, nova-cell/OVS/neutron config, OVS post-config | `compare_container` exec, image pull, restart/recreate | handlers (drift), image download (new image), `update_cell` (URL change), Docker restart (`daemon.json` change) |

---

## 5. Why a small change becomes a large workload

Two independent multipliers apply:

1. **Work multiplier (always).** Every run that includes the `compute` group executes the full per-host chain on
   every compute, even with no change (§2): config re-rendering and comparison, container config checks, common
   role, sysctl and modules, OVS post-config, discovery. **Kolla has no "only if changed" short-circuit at play
   level.**
2. **Restart multiplier (when inputs are global).** Global inputs are rendered into every compute's files
   ([02](02-openstack-component-dependencies.md) §5). Loop-notify widens a single drifted container to the whole role
   on that host ([03](03-ansible-roles-and-tags-mapping.md) §2.4). Without `serial`, all restarts land in one handler
   flush.

---

## 6. Measured scaling in the lab

Unmodified `site.yml`, Ansible 2.9.27, simulated hosts with stub modules, a local connection (no SSH) and a 4-vCPU
deploy host. Fixed parts of every run: 3 controllers, 2 network nodes, 1 storage node, 1 monitoring node. Runs and
method: [annex/lab/README.md](../annex/lab/README.md), [results](../annex/lab/results.md).

| Run | Computes | forks | Task results (fleet) | per compute | `compare_container` calls (fleet) | Restarts/recreates | nova-cell play (lab s) | Total (lab s) |
|---|---|---|---|---|---|---|---|---|
| `t0-deploy` | 3 | 20 | 2,048 | 143 | 137 | 2 | 18 | 179 |
| `sc-deploy-10` | 10 | 20 | 3,035 | 142 | 214 | 2 | 39 | 266 |
| `sc-deploy-30` | 30 | 20 | 5,855 | 141 | 434 | 2 | 105 | 457 |
| `s01` `-t nova reconfigure` (no change) | 3 | 20 | 536 | 59 | 39 | 0 | 21 | 46 |
| `sc-reconf-nova-10` (no change) | 10 | 20 | 928 | 57 | 81 | 0 | 57 | 86 |
| `sc-reconf-nova-30` (no change) | 30 | 20 | 2,048 | 56 | 201 | 0 | 130 | 161 |
| `sc-reconf-nova-30-forks5` | 30 | 5 | 2,048 | 56 | 201 | 0 | 134 | 164 |
| `sc-reconf-nova-30-forks50` | 30 | 50 | 2,048 | 56 | 201 | 0 | 132 | 163 |
| `sc-reconf-nova-30-computeconf` (nova-compute override) | 30 | 20 | 2,169 | 60 | 201 | **90** (30 × nova_compute + nova_libvirt + nova_ssh) | 147 | 177 |
| `sc-reconf-nova-30-limit1` (`--limit compute001`) | 30 | 20 | 66 | 66 | 6 | 0 | 17 | 25 |

What the measurements show:

1. **Per-compute work is constant and fleet work is linear.**
   - Deploy: ≈141–143 task results per compute at 3, 10 and 30 computes. Fleet totals grow by exactly ≈141 per
     added compute (2,048 → 3,035 → 5,855).
   - `-t nova`: ≈56–59 per compute, with fleet totals growing by ≈56 per compute.
   - The number of `compare_container` calls grows by 11 per compute for a deploy and 6 per compute for `-t nova`.
     A call runs `docker exec kolla_set_configs --check` only when the container exists and no other attribute
     differs (`kolla_docker.py:326-332`). The first-time deploys (`t0`, `sc-deploy-*`) found every container
     missing and ran no check exec; the no-change runs do one exec per call.
2. **The compute-wide plays dominate as C grows.**
   - The nova-cell play went from 21 s to 130 s of lab time (3 → 30 computes) for a no-change `-t nova` run. That is
     45% → 81% of the run.
   - In a full deploy, the plays touching computes (chrony + common, nova-cell, openvswitch, neutron) take a growing
     share as well.
3. **forks did not matter in this lab, which shows the deploy host's CPU as a bottleneck.**
   - The 30-compute run took 164 s with forks 5, 161 s with forks 20 and 163 s with forks 50. With a local connection
     there is no network latency to overlap, so the 4 vCPUs are saturated by Ansible workers: module packaging
     (AnsiballZ), templating of `nova.conf.j2` and the per-host `group_by` loop.
   - In production the per-invocation latency is dominated by SSH and remote execution. Forks then do overlap
     latency, *until* the deploy host's CPU saturates in the same way.
   - Size the deploy host (cores) together with forks. [NEEDS-LAB Q7 for production numbers]
4. **A small change restarts the fleet in one step.** With one nova-compute-only override on 30 computes, 90
   container restarts were issued (`nova_compute`, `nova_libvirt` and `nova_ssh` on every compute). The 30
   `nova_libvirt` restarts were all issued within **2.3 s** of each other, in one handler step (two waves of
   forks=20).
5. **`--limit` bounds the restarts, but fact gathering stays O(inventory).**
   - With `--limit compute001` on the 30-compute inventory, compute001 executed **38 `setup` calls sequentially**:
     its own, plus one delegated call for each of the 37 other inventory hosts (localhost included). The delegated loop
     took 5.5 s in the lab (≈0.15 s per call locally),
     against 1.6 s for 11 hosts in the 3-compute inventory.
   - The delegated `discover_hosts`/`list_cells` work ran on control01.
   - With SSH, multiply the delegated count by the real per-host `setup` time; at 500 computes it is ≈510 sequential
     fact gatherings before any work starts.

---

## 7. Influence of the main variables

| Variable | Effect | Guidance |
|---|---|---|
| **Ansible forks** | Divides the number of waves per task (⌈H/F⌉). Bounded by deploy-host CPU (templating, AnsiballZ build per invocation) and memory (one worker process per fork) | Raise until deploy-host CPU saturates. The lab shows saturation with a 4-vCPU host (§6). Size the deploy host for templating |
| **Serial (`kolla_serial`)** | Bounds simultaneous *restarts* per play, but **adds** time: every batch re-runs `run_once` steps and the compute registration wait, and each batch waits for the slowest host | Use it for restart safety on changes with drift, not for no-change runs. Prefer `genconfig` + `deploy-containers --limit` batches |
| **Task delegation** | `delegate_to` steps serialise on one host (conductor[0], neutron-server[0], rabbitmq[0]) | That host's health gates the whole run |
| **SSH overhead** | Each remote invocation pays several SSH round trips (tmp dir, transfer, exec, cleanup). The connection itself is reused: Ansible 2.9 defaults to `ControlMaster=auto` with `ControlPersist=60s`, so a new handshake happens only after a host has been idle for 60 s | `pipelining = True` (requires no `requiretty` in sudoers) is the main lever. On large fleets, a longer `ControlPersist` (keep `-C -o ControlMaster=auto` in `ssh_args`) and a short `ControlPath` |
| **Docker image size** | Pull time and disk I/O per host | Local registry, pre-pull, avoid unnecessary tag churn |
| **Network bandwidth** | Concurrent pulls from up to `forks` hosts | Cap with `--forks` during `pull`; registry caching |
| **Disk I/O** | Image extraction, container creation, `/etc/kolla` writes | SSD for `/var/lib/docker` |
| **Container startup time** | Handlers wait for `docker start` (not for service readiness), except explicit waits (haproxy, OVS DB, MariaDB WSREP, RabbitMQ) | – |
| **Handler execution** | Runs at the flush in parallel; the 10 s SIGKILL bounds stop time | Batch to bound the blast radius |
| **Parallel vs sequential** | Hosts run in parallel within a task; items and tasks run sequentially per host; plays are sequential | Reduce items (disable unused services), use tags to skip plays, use `--limit` to skip hosts |

---

## 8. Bottlenecks and optimisation opportunities (ranked)

1. **Avoid running compute-wide plays when you do not need them.**
   - Use `-t nova-api` for API-only changes (no computes).
   - Use `--limit` for host-scoped changes.
   - Use `--skip-tags haproxy` when frontends are not changing.
2. **Separate config from apply.** `genconfig` once, then `deploy-containers --limit <batch>`. The apply step is
   ≈19 task results per compute instead of ≈60–130 [LAB s15], and runs no bootstrap or Keystone steps.
3. **Fact caching + setup filter.** This removes the O(N) serial delegated gathering under `--limit` and speeds the
   first play. All options are documented in Ussuri `ansible-tuning.rst`.
4. **SSH pipelining** cuts the per-invocation constant that multiplies ≈46–80 invocations per compute (≈91 on a
   first deploy). A longer
   `ControlPersist` than the 60 s default avoids repeated handshakes on large fleets.
5. **Size forks to the deploy host.** Templating of large Jinja templates (`nova.conf.j2`, `neutron.conf.j2`) happens
   on the deploy host, per compute.
6. **Pre-pull images** (`kolla-ansible pull`) before upgrade windows, from a nearby registry.
7. **Minimise global drift.**
   - Batch `enable_*` changes.
   - Avoid touching RabbitMQ/memcached membership casually.
   - Keep compute-relevant overrides in `nova/nova-compute.conf` rather than the global `nova.conf`.
   - Do not put server-only ML2 options in `neutron/ml2_conf.ini`.
8. **Keep batches large for the nova-cell play when using serial.** The compute registration wait and discovery run
   once per batch.
9. **Disable services you do not use.** The `group_by` optimisation removes their plays entirely (`site.yml:4-6`).
   Every enabled service adds tasks to the common role and to every host in its groups.
