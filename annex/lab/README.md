# Execution lab: running the real `site.yml` against simulated hosts

`ansible-playbook --list-tasks` cannot show what Kolla-Ansible will do: every role is behind a dynamic
`include_tasks`, and host patterns depend on run-time `group_by` groups (see
[docs/03 §2.6](../../docs/03-ansible-roles-and-tags-mapping.md)). To observe real behaviour without a cloud, this lab
**executes the unmodified Kolla-Ansible `ussuri-eol` playbooks** with Ansible 2.9.27. Every host is simulated, and
only the modules that would touch Docker or the host OS are replaced.

## 1. What runs for real and what is stubbed

| Runs for real (unmodified) | Replaced by a stub (`harness/stub_*.py`) |
|---|---|
| `site.yml`, `nova.yml`, `gather-facts.yml`, all roles, tags, `when:` logic, loops, `run_once`, `delegate_to`, `serial`, handlers and their ordering | `kolla_docker`: mirrors `check_container_differs()`, `compare_config()` (config-dir hash ≈ `kolla_set_configs --check`), `recreate_or_restart_container()`, `start_container()` and `pull_image()` against a per-host JSON "container state" |
| Kolla filters (`service_enabled_and_mapped_to_host`, `kolla_address`, `extract_cell`, …), the `merge_configs` action plugin | `kolla_toolbox`, `kolla_container_facts`, `docker_image_info` |
| `template`, `copy`, `file`, `find`, `stat`, `set_fact`, `group_by`, `assert`, `fail`: config files are really rendered, per simulated host, under `runs/<run>/hosts/<host>/etc/kolla` | `command`/`shell` (canned output for `openstack compute service list`, `kolla_keystone_bootstrap`; the keystone fernet cron generator is executed for real) |
| Ansible 2.9.27 strategy, notify and tag semantics | `setup` (synthetic facts per host), `sysctl`, `modprobe`, `systemd`, `wait_for`, `slurp` |

**Per-host identity.** Each inventory host uses `ansible_connection=local` with an interpreter prefix
`LAB_HOST=<host> LAB_RUN=<run dir>`, so stubs know which simulated host they are acting for. `node_config_directory`
is set per host in the inventory (host vars beat `group_vars/all.yml`).

**Fidelity checks.**

- A second `deploy` on an unchanged state produced **zero** container restarts or recreates (`t1-redeploy`). It still
  ran the 8 DB-sync bootstrap containers and 3 cell-management one-shots, as the real code does.
- A first `deploy` created exactly the containers expected from the services dicts (`t0-deploy`).
- The loop-notify behaviour, which is the most surprising result, was reproduced independently with a 20-line
  playbook (`notify-loop.yml`, output in `notify-loop.out`). Ansible's own source confirms it
  (`plugins/strategy/__init__.py:616-623`).

**Limits.**

- Nothing about real container, VM or network behaviour can be observed (see docs/10 §5).
- Wall times use a local connection (no SSH) on a 4-vCPU host. They are useful only to compare runs and to count
  work, not as production estimates.

## 2. Files

| Path | Content |
|---|---|
| `harness/` | stubs, trace callback (`lab_trace.py`), `build_lab.sh`, `run_lab.py`, `analyze.py`, `results_md.py`, `scenarios.sh`, `scale.sh`, lab `globals.yml` |
| `results.md` | per-run summary of every scenario (generated) |
| `list-tags-site.txt`, `list-tasks-nova.txt` | real `--list-tags` / `--list-tasks -t nova` output |
| `notify-loop.yml` / `.out` | minimal reproduction of Ansible 2.9 loop-notify semantics |
| `tagdemo/`, `tagdemo.out` | minimal reproduction of `-t common` being a no-op |
| `kolla_docker_params.py` / `.out` | the real `kolla_docker.generate_module()` fed handler arguments: effective `graceful_timeout` = 10 |
| `haproxy-tag-toy/` | the haproxy-play tag toy used by fact sheet A |

## 3. Reproducing

```bash
export KOLLA_LAB_ROOT=$HOME/kolla-lab
mkdir -p $KOLLA_LAB_ROOT/src && cd $KOLLA_LAB_ROOT/src
git clone --depth 1 --branch ussuri-eol https://github.com/openstack/kolla-ansible.git
cd $KOLLA_LAB_ROOT
uv python install 3.8 && uv venv -p 3.8 venv-ansible && . venv-ansible/bin/activate
uv pip install 'ansible==2.9.27' 'jinja2<3.1' 'markupsafe<2.1' jmespath netaddr 'docker<5'
uv pip install -e src/kolla-ansible
mkdir -p lab/etc/kolla/config lab/inv
cp src/kolla-ansible/etc/kolla/passwords.yml lab/etc/kolla/ && python src/kolla-ansible/tools/generate_passwords.py -p lab/etc/kolla/passwords.yml
cp <this repo>/annex/lab/harness/lab-globals.yml lab/etc/kolla/globals.yml
# inventories: copy ansible/inventory/multinode to lab/inv/multinode-N, with compute001..N in [compute]
<this repo>/annex/lab/harness/build_lab.sh
python3 <this repo>/annex/lab/harness/run_lab.py --run t0-deploy --computes 3
python3 <this repo>/annex/lab/harness/analyze.py t0-deploy all
```

`scenarios.sh` and `scale.sh` contain the exact scenario commands used for the documentation. Two things the lab
needs from the sandbox:

- the paths `/var/lib/docker/volumes/kolla_logs/_data` and `/etc/udev/rules.d`, which `common` and `nova-cell` write
  outside `node_config_directory`;
- `sudo`.

## 4. Scenario index

| Run | What it shows | Used in |
|---|---|---|
| `t0-deploy`, `t1-redeploy` | first deploy; idempotency (no restarts; 8 DB-sync + 3 cell one-shots) | docs/04, 06 |
| `s01` … `s04` | `-t nova reconfigure`: no change, global override, compute-only override (libvirt and ssh restart), scheduler-only override (api restarts) | docs/05, 07 §A |
| `s05`, `s06` | `-t neutron`: ml2 override reaches every OVS agent; global neutron.conf | 07 §B |
| `s07`, `s08` | `enable_barbican`: fleet-wide common + nova restarts under `-t nova`; `-t common` is a no-op | 07 §C |
| `s09a-c`, `s10`, `s11` | image updates: same-tag rebuild not pulled by deploy; pull; recreate; tag change recreates everything | 07 §D |
| `s12` | adding a controller restarts every nova/neutron container on every compute | 07 §F |
| `s13` | `--limit compute001`: only that host restarts; facts for all hosts gathered serially | 07 §A, 06 |
| `s14`, `s15` | `genconfig` (no restarts), then `deploy-containers --limit` applies the drift | 07 §H |
| `s16` | `kolla_serial=1`: per-host restarts, `run_once` repeated per batch | 04 §5, 07 §A |
| `s17` | adding a compute with `--limit`: delegated work on control01 | 07 §G |
| `s18`, `s19` | full `reconfigure` and `-t haproxy` with no change: cost without restarts | 06, 07 §E |
| `sc-*` | scale runs (10 and 30 computes, forks 5/20/50, limit) | 06 |

## 5. Template dependency grep (used by docs/02 §3)

The command below lists which roles' templates reference which shared services (a reference, not proof of runtime
use). Run it from `ansible/roles` in the source tree; `docs/02` cites it as "template grep".

```python
import glob,re
pats={'MariaDB':r'mysql\+pymysql|database_address','RabbitMQ':r'transport_url','Memcached':r'memcache',
      'Keystone':r'keystone_(internal|admin|public)_url|www_authenticate_uri|auth_url',
      'Glance':r'glance_(internal|api)|\[glance\]','Placement':r'\[placement\]','Neutron':r'\[neutron\]|neutron_internal',
      'Nova':r'\[nova\]|nova_internal|nova_metadata','Cinder':r'\[cinder\]|cinder_internal','Barbican':r'\[barbican\]',
      'Swift':r'swift','Ceph':r'ceph|rbd','OVN':r'ovn_(nb|sb)'}
for r in ['keystone','glance','placement','nova','nova-cell','neutron','cinder','horizon','heat','barbican','octavia','swift','manila']:
    txt=''.join(open(f).read() for f in glob.glob(r+'/templates/**/*.j2',recursive=True))
    print(r, [k for k,p in pats.items() if re.search(p,txt)])
```

Result: keystone [MariaDB, RabbitMQ, Memcached]; glance [MariaDB, RabbitMQ, Memcached, Keystone, Glance, Barbican,
Swift, Ceph]; placement [MariaDB, RabbitMQ, Memcached, Keystone, Placement, Nova]; nova [MariaDB, RabbitMQ, Memcached,
Keystone, Glance, Placement, Neutron, Nova, Cinder, Barbican]; nova-cell [MariaDB, RabbitMQ, Keystone, Glance,
Placement, Neutron, Nova, Cinder, Barbican, Ceph]; neutron [MariaDB, RabbitMQ, Memcached, Keystone, Placement, Neutron,
Nova, OVN]; cinder [MariaDB, RabbitMQ, Memcached, Keystone, Glance, Nova, Barbican, Swift, Ceph]; horizon [MariaDB,
Memcached, Keystone, Swift]; heat [MariaDB, RabbitMQ, Memcached, Keystone]; barbican [MariaDB, RabbitMQ, Memcached,
Keystone, Barbican]; octavia [MariaDB, RabbitMQ, Memcached, Keystone, Glance, Neutron, Nova]; swift [RabbitMQ,
Memcached, Keystone, Swift]; manila [MariaDB, RabbitMQ, Memcached, Keystone, Glance, Neutron, Nova, Cinder, Ceph].
