# 02 — OpenStack Component Dependencies (as implemented by Kolla-Ansible Ussuri)

This document maps **what depends on what**, and keeps four kinds of dependency apart:

| Kind | Question it answers | Where it lives in the code |
|---|---|---|
| **Installation (deploy-time) dependency** | What must already run for the *role* to succeed? | `kolla_toolbox` calls to MariaDB, Keystone and RabbitMQ in `bootstrap.yml`/`register.yml`, bootstrap containers, `delegate_to` targets |
| **Configuration dependency** | Whose hosts, addresses, flags or passwords end up in *my* config files? | `templates/*.j2`, `group_vars/all.yml` (e.g. `rpc_transport_url`) |
| **Runtime dependency** | What must be reachable for the *service* to work? | The same templates (URLs, connections); upstream OpenStack behaviour |
| **Operational dependency** | Which Kolla action on X changes or restarts Y? | Handlers, global `enable_*` flags, `common`, haproxy, loop-notify (see [07](07-day2-operational-impact.md)) |

Kolla-Ansible **never declares inter-service dependencies** explicitly. Role meta lists only `common`. Every
dependency below is implicit: play order in `site.yml`, a variable, a template, or a `delegate_to`.

A compact card per service (role, play, tags, task flow, templates, handlers, key variables, node types) is in
[annex/service-cards.md](../annex/service-cards.md). Per-role detail with line references is in the fact sheets
([A](../annex/factsheets/A-infra-lb-ovn.md), [B](../annex/factsheets/B-mariadb-rabbitmq-keystone.md),
[C](../annex/factsheets/C-glance-placement-cinder-horizon-heat.md),
[D](../annex/factsheets/D-barbican-octavia-swift-manila-compute-roles.md),
[E](../annex/factsheets/E-host-bootstrap-ops-playbooks.md)). Nova is covered in depth in [05](05-nova-deep-dive.md).

---

## 1. The shared substrate: what every OpenStack service uses

| Shared component | How services reach it | Evidence | Consequence |
|---|---|---|---|
| **MariaDB / Galera** | `database_address: "{{ kolla_internal_fqdn }}"`, i.e. through the **internal VIP and HAProxy** | `ansible/group_vars/all.yml:105` | Every DB connection depends on HAProxy and keepalived as well as on Galera. HAProxy sends DB traffic to **one** active backend; the others are `backup` (`roles/mariadb/defaults/main.yml:58`, fact sheet B §1.2) |
| **RabbitMQ** | `rpc_transport_url` / `notify_transport_url` list **every host** of `groups['rabbitmq']` directly. Clients use their own failover, **not** the VIP | `ansible/group_vars/all.yml:206,216` | Adding or removing a RabbitMQ node changes the config of every messaging service, including `nova-compute` and the neutron agents on **every compute** ([07](07-day2-operational-impact.md) §F) |
| **Memcached** | Templates loop `{% for host in groups['memcached'] %}` for `keystone_authtoken` / `[cache]` | e.g. `roles/ceilometer/templates/ceilometer.conf.j2:55`; templates of 37 roles contain this loop, and monasca builds the same list in `roles/monasca/defaults/main.yml:127` | Membership change = config change in about 38 services. A memcached restart flushes token caches and Horizon sessions (fact sheet A §3.8) |
| **Keystone** | `www_authenticate_uri`/`auth_url` → internal/admin VIP endpoints; `service-ks-register` at deploy time | `roles/service-ks-register/tasks/main.yml` (39 roles use it) | Hard deploy-time dependency (registration runs `run_once` against the admin endpoint). Runtime: every API request is validated by keystonemiddleware (cached in memcached) |
| **HAProxy + keepalived** | Every internal/admin/public endpoint and the DB address resolve to the VIPs | `roles/*/defaults/main.yml` `haproxy:` dicts → `roles/haproxy-config` | A single point of *path* failure for APIs and DB. HAProxy is **restarted, never reloaded**, on all haproxy hosts at once (fact sheet A §1.8) |
| **fluentd / cron / kolla_toolbox** (`common`) | Deployed on every host (`group: all`) | `roles/common/defaults/main.yml:6-36` | `kolla_toolbox` is a **deploy-time** dependency of every role that touches MySQL, Keystone or RabbitMQ (`kolla_toolbox` module needs it running). fluentd is runtime-optional (logging only) |

```mermaid
flowchart LR
  subgraph Substrate["Shared substrate (runtime)"]
    VIP["keepalived VIP"] --> HAP["HAProxy (haproxy hosts)"]
    HAP --> DB[("MariaDB/Galera<br/>1 active backend")]
    MQ[["RabbitMQ cluster<br/>(direct, all nodes listed)"]]
    MC[("Memcached<br/>(direct, all nodes listed)")]
  end
  KS["Keystone API"] -->|SQL via VIP| HAP
  KS -->|token cache| MC
  SVC["Any OpenStack API / agent"] -->|SQL via VIP| HAP
  SVC -->|RPC + notifications| MQ
  SVC -->|keystonemiddleware cache| MC
  SVC -->|token validation, via VIP| HAP
  HAP -->|"/v3"| KS
```

---

## 2. Infrastructure components

| Component | Role / play | Hosts (example inventory) | Deploy-time needs | Runtime needs | Who depends on it |
|---|---|---|---|---|---|
| **Keepalived** | `haproxy` role, `site.yml:126` | `haproxy` → `network` | `ip_vs` module, sysctl `ip_nonlocal_bind` | VRRP between haproxy hosts (multicast default, router id 51) | Everything addressed by VIP |
| **HAProxy** | `haproxy` role + 49 `loadbalancer.yml` includes | `haproxy` | facts of **all backend hosts** (backend lists use `hostvars[host].ansible_facts.hostname`) | backends | All APIs, MariaDB (DB address = VIP) |
| **MariaDB/Galera** | `mariadb` role, `site.yml:471` (no `serial`) | `mariadb` → `control` | `kolla_toolbox`; Galera bootstrap logic (fact sheet B §1) | HAProxy (clustercheck on port 4569) | Every service with a DB |
| **RabbitMQ** | `rabbitmq` role, `site.yml:535` (no `serial`) | `rabbitmq` → `control` | erlang cookie, `/etc/hosts` (from `bootstrap-servers`) | – | Every service with RPC/notifications |
| **Memcached** | `memcached` role, `site.yml:481` (no `common` dependency) | `memcached` → `control` | – | – | Keystone, all keystonemiddleware users, Horizon sessions |
| **Fluentd** | `common` | all | – | (optional) Elasticsearch/Monasca outputs | Logging only. HAProxy syslogs to fluentd UDP |
| **Open vSwitch** | `openvswitch` role, `site.yml:712` | `openvswitch` → `network`, `compute`, `manila-share` | kernel module `openvswitch`; `neutron_bridge_name`/`neutron_external_interface` on network nodes (and computes if `computes_need_external_bridge`) | – | neutron-openvswitch-agent, OVN controller, DHCP/L3 agents |
| **OVN** (if `neutron_plugin_agent: ovn`) | `ovn` role, `site.yml:734` | `ovn-database` → `control`; `ovn-controller` → `compute`, `network` | OVS running (ovn-controller writes OVS external_ids through `docker exec` into the OVS containers) | NB/SB DB cluster (Raft) | neutron-server (ML2/OVN), neutron-ovn-metadata-agent |
| **Chrony** | `chrony` role, `site.yml:114` (enabled by default) | `chrony-server` → `haproxy`; `chrony` → all physical groups | – | upstream NTP (`pool.ntp.org` by default) | Galera, RabbitMQ, Keystone token expiry, Ceph |
| **iscsid / tgtd** | `iscsi` role, `site.yml:512` | `iscsid` → `compute`, `storage` | only if `enable_iscsid` (cinder LVM/iSCSI or ironic) | – | nova-compute (volume attach), cinder-volume (LVM) |

### 2.1 Infrastructure dependency graph (runtime)

```mermaid
flowchart TB
  NTP["chrony (all hosts)"] -.time.-> DB & MQ & KS
  KA["keepalived"] -->|VIP| HAP["HAProxy"]
  HAP -->|"tcp 3306 (1 active)"| DB[("MariaDB/Galera")]
  HAP -->|HTTP| KS["Keystone"]
  KS --> MC[("Memcached")]
  KS -->|"SQL via VIP"| HAP
  OVS["openvswitch_db + vswitchd"] --> OVSAG["neutron-openvswitch-agent"]
  OVS --> OVNC["ovn-controller"]
  OVNC --> SB[("OVN SB DB")]
  NORTHD["ovn-northd"] --> NB[("OVN NB DB")] & SB
  FL["fluentd (all hosts)"] -.optional.-> ES[("Elasticsearch / Monasca")]
  TB["kolla_toolbox (all hosts)"] -.deploy-time only.-> DB & KS & MQ[["RabbitMQ"]]
```

---

## 3. Control-plane services

Legend: **DB** = MariaDB through the VIP, **MQ** = RabbitMQ (all nodes listed), **MC** = memcached, **KS** = Keystone.
A ✔ means the service's main config template references it [CODE, template grep in
[annex/lab/README.md](../annex/lab/README.md) §5].

| Service | DB | MQ | MC | KS | Other services referenced in config | Deploy-time actions | Notes (fact sheet) |
|---|---|---|---|---|---|---|---|
| **Keystone** | ✔ | ✔ (notifications) | ✔ | – | – | bootstrap container (db sync) **every deploy/reconfigure**; fernet keys distributed from first running node; admin bootstrap through `kolla_keystone_bootstrap` | B §3.6–3.10 |
| **Glance** | ✔ | ✔ | ✔ | ✔ | Cinder (store), Ceph, Swift, Barbican | db sync on every deploy/reconfigure; toggles **global** MariaDB `log_bin_trust_function_creators` | C §1. With the file backend only `groups['glance-api'][0]` runs glance |
| **Placement** | ✔ | ✔ (unused) | ✔ | ✔ | (Nova credentials in migration helper) | db sync on every deploy/reconfigure | C §2 |
| **Nova** | ✔ | ✔ | ✔ (API side only) | ✔ | Glance, Neutron, Placement, Cinder, Barbican, Ceph | API/cell0/cell DB sync on every deploy/reconfigure; cell create/update; host discovery | [05](05-nova-deep-dive.md) |
| **Neutron** | ✔ (server) | ✔ | ✔ | ✔ | Nova (notifications to Nova), Placement, OVN | DB, user and grants on every deploy/reconfigure; db sync container on **deploy only** while `neutron_enable_rolling_upgrade` is on (the default; `roles/neutron/tasks/bootstrap_service.yml:21-22`) | §4 below |
| **Cinder** | ✔ | ✔ | ✔ | ✔ | Glance, Nova (uses **nova** credentials), Barbican, Swift (backup), Ceph; etcd (first etcd host only) | db sync on every deploy/reconfigure | C §3 |
| **Horizon** | only if `horizon_backend_database` | – | ✔ (sessions) | ✔ | every enabled API (internal endpoint type) | no Keystone registration | C §4 |
| **Heat** | ✔ | ✔ | ✔ | ✔ | every API used by templates (internal); instances need the **external** CFN endpoint | db sync on every deploy/reconfigure; heat domain admin setup | C §5 |
| **Barbican** | ✔ | ✔ | ✔ | ✔ | – | db sync on every deploy/reconfigure; `barbican_crypto_key` from `passwords.yml` | D §1 |
| **Octavia** | ✔ | ✔ | ✔ | ✔ | Nova, Neutron, Glance (amphora image, flavor, network, secgroup — **all manual in Ussuri**) | db sync; no OpenStack resources created | D §2 |
| **Swift** | – | ✔ | ✔ | ✔ | – | rings are operator-built; old-style role with no handlers | D §3 |
| **Manila** | ✔ | ✔ | ✔ | ✔ | Glance, Neutron, Nova, Cinder, Ceph (CephFS) | db sync; manila-share hosts also get neutron agents | D §4 |

### 3.1 Control-plane runtime graph

```mermaid
flowchart LR
  USER(("API clients<br/>Horizon")) --> HAP["HAProxy VIP"]
  HAP --> KS["Keystone"] & GL["Glance API"] & PL["Placement API"] & NA["Nova API"] & NS["Neutron server"] & CA["Cinder API"] & HA["Heat API/CFN"] & BA["Barbican API"] & OA["Octavia API"] & SW["Swift proxy"] & MA["Manila API"]
  NA -->|RPC| NSC["nova-scheduler"] --> PL
  NA --> NCOND["nova-conductor"]
  NS -->|"port events (os-server-external-events)"| NA
  NA -->|ports| NS
  NA -->|images| GL
  NA -->|volumes| CA
  CA -->|images| GL
  CA -.->|"nova creds: volume events"| NA
  GL -.->|store| CA
  GL -.->|store| SW
  HA -->|"orchestrates (internal endpoints)"| NA & NS & CA & GL
  OA -->|amphorae| NA & NS & GL
  MA -->|share servers| NA & NS & CA
  NA & NS & CA & GL & PL & HA & BA & OA & MA -->|tokens| KS
```

The dotted edges are configuration couplings that are easy to overlook:

- **Cinder → Nova** with Nova's own credentials (`roles/cinder/templates/cinder.conf.j2:83-93`).
- **Glance → Cinder or Swift** as image stores. Enabling Swift *changes Glance's default backend*
  (`group_vars/all.yml:862-869`, fact sheet C §1.8).
- **Nova and Neutron → Placement** with the placement user (`roles/nova-cell/templates/nova.conf.j2:203-213`).

---

## 4. Networking components (ML2/OVS default, ML2/OVN optional)

| Container | Placement rule (`host_in_groups`) | Needs | Data-plane role |
|---|---|---|---|
| `openvswitch_db`, `openvswitch_vswitchd` | compute, manila-share (generic backend), dhcp/l3/metadata agent hosts (`roles/openvswitch/defaults/main.yml:2-31`) | kernel module, `/run/openvswitch` | **Forwards all VM traffic** |
| `neutron_openvswitch_agent` | compute (non-xenapi), manila-share (generic), dhcp/l3/metadata hosts (`roles/neutron/defaults/main.yml`) | OVS, RabbitMQ, (neutron-server via RPC) | Programs OVS flows; on restart it resyncs flows |
| `neutron_l3_agent` | `neutron-l3-agent`; **plus every compute** when `enable_neutron_dvr` | OVS, `/run/netns` | Routers (namespaces, keepalived for HA routers) |
| `neutron_dhcp_agent` | `neutron-dhcp-agent` | OVS | dnsmasq per network |
| `neutron_metadata_agent` | `neutron-metadata-agent`; plus computes with DVR | nova-api metadata via VIP (`nova_metadata`) | metadata proxy |
| `neutron_server` | `neutron-server` | DB, MQ, KS, Nova, Placement | control plane only |
| `ovn_controller` (OVN) | `ovn-controller` (compute + network) | OVS, SB DB | Programs OVS from SB DB |
| `neutron_ovn_metadata_agent` (OVN) | `neutron-ovn-metadata-agent` → compute | OVS, SB DB | metadata per chassis |

```mermaid
flowchart TB
  subgraph Compute["Compute host (ML2/OVS)"]
    NC["nova_compute"] -->|"vif plug (os-vif → ovsdb)"| OVSDB[("openvswitch_db")]
    NL["nova_libvirt / qemu"] -->|tap devices| VS["openvswitch_vswitchd"]
    OA["neutron_openvswitch_agent"] -->|flows| VS
    OA --> OVSDB
    VS --- OVSDB
  end
  subgraph Network["Network host"]
    L3["neutron_l3_agent<br/>(router namespaces, keepalived)"] --> VS2["openvswitch_vswitchd"]
    DHCP["neutron_dhcp_agent (dnsmasq)"] --> VS2
    MD["neutron_metadata_agent"]
    OA2["neutron_openvswitch_agent"] --> VS2
  end
  subgraph Control["Controller"]
    NS["neutron_server"]
  end
  OA & OA2 & L3 & DHCP & MD -->|RPC| MQ[["RabbitMQ"]]
  NS --> MQ
  NS -->|"port bound/unbound events"| NAPI["nova-api"]
  NC -->|"port create/update"| NS
  MD -->|"proxy to nova metadata (VIP)"| NAPI
```

Runtime facts [CODE]:

- **The L3 agent can wipe its namespaces on start.** With `enable_neutron_agent_ha: yes`, its start wrapper runs
  `neutron-netns-cleanup --force --agent-type l3` *before* starting the agent
  (`roles/neutron/templates/neutron-l3-agent-wrapper.sh.j2:5-12`). Every restart or recreate of `neutron_l3_agent`
  on such a host therefore deletes all router namespaces there, and the agent rebuilds them.
- **Agent containers do not share the host PID namespace.** They have no `pid_mode` (`roles/neutron/defaults/main.yml`).
  Processes they spawn (dnsmasq, keepalived, haproxy for metadata) live in the container's PID namespace.
  [HYPOTHESIS] They die with the container and are respawned by the agent on start. [NEEDS-LAB]: measure the DHCP
  and router outage per agent restart.
- **The OVS bridge layout is set in a post-config step.** It is ensured on every deploy/reconfigure by
  `kolla_ensure_openvswitch_configured` (`roles/openvswitch/tasks/post-config.yml:7-17`). The command reports
  `changed` only when it actually changes the bridge.

---

## 5. Compute-node dependency summary

Everything that lands on a compute host in a default Ussuri deployment (lab `t0-deploy`, 3 computes):

| Container | Role | Config source that is *global* (changes fleet-wide) |
|---|---|---|
| `fluentd`, `cron`, `kolla_toolbox` | common | `td-agent.conf` and `logrotate.conf` built from **all** `enable_*` flags |
| `chrony` | chrony | `kolla_internal_vip_address` and `external_ntp_servers` (`roles/chrony/templates/chrony.conf.j2:3-9`). `groups['chrony-server']` only selects the host's own server or client stanza (`:30-39`), so other hosts joining or leaving that group do not alter a compute's `chrony.conf` |
| `iscsid` | iscsi (if cinder LVM/iSCSI or ironic) | – |
| `nova_libvirt`, `nova_ssh`, `nova_compute` | nova-cell | `nova.conf`: `rpc_transport_url` (all RabbitMQ hosts), `enable_barbican/ceilometer/designate/watcher/cinder/osprofiler…` sections, Glance, Neutron and Placement endpoints, service passwords |
| `openvswitch_db`, `openvswitch_vswitchd` | openvswitch | – (bridge mappings only if `computes_need_external_bridge`) |
| `neutron_openvswitch_agent` | neutron | `neutron.conf` (all RabbitMQ hosts, memcached list) **and** `openvswitch_agent.ini`, which also merges the operator's `ml2_conf.ini` override |

Optional compute-side containers come from ceilometer, collectd, telegraf, prometheus exporters, masakari, zun, kuryr,
cyborg, skydive and monasca (fact sheet D §5). Each of them embeds host lists from other groups (RabbitMQ,
memcached, influxdb, etcd, prometheus) in its config. The full list of templates that loop over groups is in
[annex/generated-inventory.md §4](../annex/generated-inventory.md).

**Rule of thumb [CODE + LAB]:** a compute host's configuration depends on *global* state (enabled services, the
membership of the RabbitMQ, memcached and etcd groups, the internal VIP and external NTP servers, service passwords), not only on the compute host
itself. That is why changes that look small trigger fleet-wide restarts ([06](06-compute-scaling-and-performance.md),
[07](07-day2-operational-impact.md)).

---

## 6. Deployment order vs runtime dependency

Deployment order is the play order in `site.yml` ([04](04-deployment-execution-flow.md)). It mostly respects runtime
dependencies, with these caveats [CODE]:

| Observation | Evidence | Effect |
|---|---|---|
| HAProxy is configured for **all** services before any of them exists | `site.yml:126-392` | The first deploy puts frontends in place for backends not yet started. HAProxy health checks mark them down until the services come up |
| **Placement is deployed before Nova; Glance and Cinder too** | `site.yml:657-706` | Nova bootstrap can use Placement and Glance at once |
| **Nova is deployed *before* Open vSwitch and Neutron** | `site.yml:710` (`nova.yml`) vs `:712-780` | On a first deploy nova-compute starts before the OVS agent exists. Compute *registration* only needs the conductor, not Neutron. The NOTE at `site.yml:759-760` forbids changing the order ("workaround to fix bug 1546789") |
| Heat, Horizon and Octavia come after Nova and Neutron | `site.yml:793-1195` | – |
| Nothing enforces a dependency when you **use tags** | `--tags` filters plays | `-t nova` on a fresh cloud fails at Keystone registration if Keystone was never deployed. On an existing cloud it assumes MariaDB, RabbitMQ and Keystone are healthy |
| Bootstrap and registration tasks target `groups[...][0]` | e.g. `nova-cell/tasks/bootstrap.yml:14,32` | The first host of a group is a hidden dependency: it must be reachable and have `kolla_toolbox` running |
