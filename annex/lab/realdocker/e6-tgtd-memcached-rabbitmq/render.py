#!/usr/bin/env python3
"""Render the REAL kolla-ansible ussuri-eol (8a94fe9) templates used by e6 into <out>/<service>/.

Usage: python3 -P render.py <kolla-ansible checkout> <out dir> <hostname>
Rendering mimics Ansible's template module (trim_blocks=True). Only the variables the templates reference are given.
Addresses are 127.0.0.1 and ports are moved into e6's range 18600-18699 (every kolla container is network_mode host,
kolla_docker.py:719). The filter put_address_in_context is the real one from kolla_ansible/.
"""
import json
import os
import shutil
import sys

import jinja2

KA_ROOT = sys.argv[1]
OUT = sys.argv[2]
HOSTNAME = sys.argv[3]


def _load(name, path):  # load one module file of the trusted checkout, without kolla_ansible/__init__ (needs pbr)
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


import types  # noqa: E402
sys.modules['kolla_ansible'] = types.ModuleType('kolla_ansible')
_load('kolla_ansible.exception', os.path.join(KA_ROOT, 'kolla_ansible', 'exception.py'))
put_address_in_context = _load('kolla_ansible.put_address_in_context', os.path.join(
    KA_ROOT, 'kolla_ansible', 'put_address_in_context.py')).put_address_in_context

ROLES = os.path.join(KA_ROOT, 'ansible', 'roles')
CCD = '/var/lib/kolla/config_files'
ADDR = '127.0.0.1'
PORTS = {'iscsi': 18601, 'memcached': 18611, 'epmd': 18641, 'cluster': 18642, 'amqp': 18643, 'mgmt': 18644}


def render(rel, **variables):
    with open(os.path.join(ROLES, rel)) as f:
        src = f.read()
    env = jinja2.Environment(trim_blocks=True, keep_trailing_newline=True, undefined=jinja2.StrictUndefined)
    env.filters['put_address_in_context'] = put_address_in_context
    return env.from_string(src).render(**variables)


def write(svc, name, text):
    d = os.path.join(OUT, svc)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, name), 'w') as f:
        f.write(text)


if os.path.isdir(OUT):
    shutil.rmtree(OUT)

# (a) tgtd: roles/iscsi/templates/tgtd.json.j2
write('tgtd', 'config.json', render('iscsi/templates/tgtd.json.j2', api_interface_address=ADDR,
                                     iscsi_port=PORTS['iscsi']))

# (b) memcached: roles/memcached/templates/memcached.json.j2 with the role defaults (connection limit 5000, 256 MB)
write('memcached', 'config.json', render('memcached/templates/memcached.json.j2', api_interface_address=ADDR,
                                          memcached_port=PORTS['memcached'], memcached_connection_limit='5000',
                                          memcached_max_memory='256'))

# (c) rabbitmq: every template of the role that the container reads (roles/rabbitmq/tasks/config.yml)
rv = dict(container_config_directory=CCD, project_name='rabbitmq', api_interface_address=ADDR,
          api_address_family='ipv4', ansible_facts={'hostname': HOSTNAME},
          role_rabbitmq_cluster_port=PORTS['cluster'], role_rabbitmq_epmd_port=PORTS['epmd'],
          role_rabbitmq_port=PORTS['amqp'], role_rabbitmq_management_port=PORTS['mgmt'],
          rabbitmq_pid_file='/var/lib/rabbitmq/mnesia/rabbitmq.pid',
          # role default (roles/rabbitmq/defaults/main.yml:72) is '+S 2:2 +sbwt none +sbwtdcpu none +sbwtdio none';
          # bionic's Erlang 20.2 rejects +sbwtdcpu/+sbwtdio (OTP 21+): beam.smp exits with
          # 'bad scheduler busy wait threshold: dcpu'. Lab deviation: the two OTP-21 flags are dropped.
          rabbitmq_server_additional_erl_args='+S 2:2 +sbwt none',
          role_rabbitmq_groups='rabbitmq', groups={'rabbitmq': ['host1']},
          hostvars={'host1': {'ansible_facts': {'hostname': HOSTNAME}}},
          role_rabbitmq_user='openstack', role_rabbitmq_password='e6-lab-not-a-secret',
          role_rabbitmq_monitoring_user='', role_rabbitmq_monitoring_password='')
cfg = json.loads(render('rabbitmq/templates/rabbitmq.json.j2', **rv))
for t in ('rabbitmq-env.conf', 'rabbitmq.conf', 'erl_inetrc', 'advanced.config', 'definitions.json'):
    write('rabbitmq', t, render('rabbitmq/templates/%s.j2' % t, **rv))

# Lab addition, needed only because bionic ships RabbitMQ 3.6.10: 3.6 reads neither rabbitmq.conf (new format)
# nor advanced.config (both 3.7+); it reads /etc/rabbitmq/rabbitmq.config (Erlang terms). This file carries the
# same settings as the rendered rabbitmq.conf + advanced.config; without it 3.6.10 would listen on 0.0.0.0:5672 and
# :15672 of the shared host network. classic_config peer discovery (3.7+) becomes the 3.6 cluster_nodes setting.
write('rabbitmq', 'rabbitmq.config', """%% e6 lab addition: RabbitMQ 3.6.10 translation of rabbitmq.conf + advanced.config
[
 {rabbit, [{tcp_listeners, [{"%(a)s", %(amqp)d}]},
           {cluster_partition_handling, pause_minority},
           {cluster_nodes, {['rabbit@%(h)s'], disc}}]},
 {rabbitmq_management, [{listener, [{ip, "%(a)s"}, {port, %(mgmt)d}]},
                        {load_definitions, "/etc/rabbitmq/definitions.json"}]},
 {kernel, [{inet_dist_use_interface, {%(ae)s}},
           {inet_dist_listen_min, %(cluster)d},
           {inet_dist_listen_max, %(cluster)d}]}
].
""" % dict(a=ADDR, ae=put_address_in_context(ADDR, 'rabbitmq'), h=HOSTNAME, **PORTS))
cfg['config_files'].append({'source': CCD + '/rabbitmq.config', 'dest': '/etc/rabbitmq/rabbitmq.config',
                            'owner': 'rabbitmq', 'perm': '0600'})
write('rabbitmq', 'config.json', json.dumps(cfg, indent=4) + '\n')
print('rendered into', OUT)
