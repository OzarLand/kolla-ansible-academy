#!/usr/bin/env python3
"""Render the REAL kolla-ansible ussuri-eol templates used by e1 into cfg/<set>/ (one config dir per container).

Usage: render.py <kolla-ansible checkout> <output cfg dir>
Only the variables the templates reference are supplied (values below). Rendering mimics Ansible's template module:
trim_blocks=True, plus lstrip_blocks when the template starts with '#jinja2: lstrip_blocks: True'.
Ports are moved into e1's range 18100-18199 and addresses to 127.0.0.1 (every kolla container is network_mode host).
"""
import json
import os
import shutil
import sys

import jinja2

KA = os.path.join(sys.argv[1], 'ansible', 'roles')
OUT = sys.argv[2]
CCD = '/var/lib/kolla/config_files'


def to_bool(v):
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in ('yes', 'on', '1', 'true', 'y')


def render(rel, **variables):
    path = os.path.join(KA, rel)
    with open(path) as f:
        src = f.read()
    lstrip = src.startswith('#jinja2:') and 'lstrip_blocks: True' in src.splitlines()[0]
    if src.startswith('#jinja2:'):
        src = src.split('\n', 1)[1]
    env = jinja2.Environment(trim_blocks=True, lstrip_blocks=lstrip, keep_trailing_newline=True,
                             undefined=jinja2.StrictUndefined)
    env.filters['bool'] = to_bool
    env.filters['put_address_in_context'] = lambda addr, ctx: addr  # IPv4 only here: unchanged

    def kolla_address(*a):  # compiled into the haproxy service template; not reached with a custom_member_list
        raise RuntimeError('kolla_address is not available in e1')
    env.filters['kolla_address'] = kolla_address
    return env.from_string(src).render(**variables)


def write(cfgset, name, text, mode=0o644):
    d = os.path.join(OUT, cfgset)
    os.makedirs(os.path.dirname(os.path.join(d, name)), exist_ok=True)
    with open(os.path.join(d, name), 'w') as f:
        f.write(text)
    os.chmod(os.path.join(d, name), mode)


def placeholder(cfgset, *names):
    for n in names:
        write(cfgset, n, '# e1 placeholder: the stand-in agent reads no configuration\n')


if os.path.isdir(OUT):
    shutil.rmtree(OUT)

# (a), (b), (g): a service that kolla_start execs directly. Not a kolla template: the minimal manifest shape.
write('sigsvc', 'config.json', json.dumps({'command': '/usr/local/bin/e1-sigsvc', 'config_files': []}, indent=4) + '\n')

# (c), (g): neutron-l3-agent, enable_neutron_agent_ha false and true.
for ha in ('false', 'true'):
    s = 'l3-ha-' + ha
    write(s, 'config.json', render('neutron/templates/neutron-l3-agent.json.j2', container_config_directory=CCD))
    write(s, 'neutron-l3-agent-wrapper.sh',
          render('neutron/templates/neutron-l3-agent-wrapper.sh.j2', enable_neutron_agent_ha=ha))
    placeholder(s, 'neutron.conf', 'neutron_vpnaas.conf', 'fwaas_driver.ini', 'l3_agent.ini')

# (d): openvswitch_db and openvswitch_vswitchd.
write('ovsdb', 'config.json', render('openvswitch/templates/openvswitch-db-server.json.j2', container_config_directory=CCD))
write('ovsdb', 'start-ovsdb-server', render('openvswitch/templates/start-ovsdb-server.j2', ovsdb_port='18120'))
write('ovsvswitchd', 'config.json',
      render('openvswitch/templates/openvswitch-vswitchd.json.j2', container_config_directory=CCD))
write('ovsvswitchd', 'start-ovs', render('openvswitch/templates/start-ovs.j2'))

# (e): haproxy. Real haproxy_main.cfg.j2 and the default service template haproxy_single_service_listen.cfg.j2
# (haproxy-config defaults) for one HTTP service whose member is the e1 backend.
hv = dict(container_config_directory=CCD, kolla_enable_tls_external='no', kolla_enable_tls_internal='no')
write('haproxy', 'config.json', render('haproxy/templates/haproxy.json.j2', **hv))
write('haproxy', 'haproxy_run.sh', render('haproxy/templates/haproxy_run.sh.j2'))
main_vars = dict(
    syslog_server='127.0.0.1', syslog_udp_port='18114', syslog_haproxy_facility='local1',
    haproxy_max_connections=40000, haproxy_processes=1, haproxy_process_cpu_map='no',
    kolla_enable_tls_external='no', kolla_enable_tls_internal='no', haproxy_backend_cacert_dir='/etc/ssl/certs',
    haproxy_http_request_timeout='10s', haproxy_queue_timeout='1m', haproxy_connect_timeout='10s',
    haproxy_client_timeout='1m', haproxy_server_timeout='1m', haproxy_check_timeout='10s',
    haproxy_defaults_balance='roundrobin', haproxy_defaults_max_connections=10000,
    api_interface_address='127.0.0.1', haproxy_stats_port='18110', haproxy_user='openstack',
    haproxy_password='e1-lab-only', haproxy_monitor_port='18111', kolla_internal_vip_address='127.0.0.1')
write('haproxy', 'haproxy.cfg', render('haproxy/templates/haproxy_main.cfg.j2', **main_vars))
service = {'group': 'e1', 'haproxy': {'e1_web': {
    'enabled': True, 'mode': 'http', 'external': False, 'port': '18112', 'listen_port': '18113',
    'custom_member_list': ['server e1-backend 127.0.0.1:18113 check inter 2000 rise 2 fall 5']}}}
write('haproxy', 'services.d/e1_web.cfg', render(
    'haproxy-config/templates/haproxy_single_service_listen.cfg.j2', service=service,
    kolla_enable_tls_external='no', kolla_enable_tls_internal='no', haproxy_enable_external_vip='no',
    kolla_internal_vip_address='127.0.0.1', kolla_external_vip_address='127.0.0.1',
    haproxy_frontend_http_extra=['option httplog', 'option forwardfor'], haproxy_frontend_tcp_extra=['option tcplog'],
    haproxy_backend_http_extra=[], haproxy_backend_tcp_extra=[]))
# Control for (e), NOT kolla: the same files, but haproxy itself is the command (kolla_start execs it).
shutil.copytree(os.path.join(OUT, 'haproxy'), os.path.join(OUT, 'haproxy-exec'))
m = json.load(open(os.path.join(OUT, 'haproxy-exec', 'config.json')))
m['command'] = ('/usr/sbin/haproxy -W -db -p /run/haproxy.pid -f /etc/haproxy/haproxy.cfg'
                ' -f /etc/haproxy/services.d/e1_web.cfg')
write('haproxy-exec', 'config.json', json.dumps(m, indent=4) + '\n')

# (f): mariadb, single node. memtotal_mb=640 gives innodb_buffer_pool_size 256M (the formula is 40 % of RAM).
db = dict(kolla_base_distro='ubuntu', container_config_directory=CCD, groups={'mariadb': ['e1-db']},
          api_interface_address='127.0.0.1', mariadb_port='18130', mariadb_wsrep_port='18131',
          mariadb_ist_port='18132', mariadb_sst_port='18133', api_address_family='ipv4',
          mariadb_wsrep_extra_provider_options=[], database_cluster_name='openstack', database_user='root',
          database_password='e1-lab-only', ansible_facts={'hostname': 'e1-db'}, inventory_hostname='e1-db',
          hostvars={'e1-db': {'ansible_facts': {'memtotal_mb': 640}}})
write('mariadb', 'config.json', render('mariadb/templates/mariadb.json.j2', **db))
write('mariadb', 'galera.cnf', render('mariadb/templates/galera.cnf.j2', **db))
write('mariadb', 'wsrep-notify.sh', render('mariadb/templates/wsrep-notify.sh.j2', **db))
print('rendered into', OUT)
