#!/usr/bin/env python3
"""Render the REAL kolla-ansible ussuri-eol openvswitch templates into cfg/<service>/, as the role's config tasks do.

Usage: render.py <kolla-ansible checkout> <output cfg dir>
Mirrors roles/openvswitch/tasks/config.yml: <svc>.json.j2 -> /etc/kolla/<svc>/config.json (mode 0660), start-ovs.j2
-> openvswitch-vswitchd/start-ovs and start-ovsdb-server.j2 -> openvswitch-db-server/start-ovsdb-server (mode 0770).
Rendering mimics Ansible's template module (trim_blocks=True). The only variable values: container_config_directory
(group_vars/all.yml:7) and ovsdb_port, moved from 6640 (group_vars/all.yml:427) to 18540 in e5's host-port range,
because every kolla container uses the host network and other experiments share this host.
"""
import os
import sys

import jinja2

KA = os.path.join(sys.argv[1], 'ansible', 'roles', 'openvswitch', 'templates')
OUT = sys.argv[2]
VARS = {'container_config_directory': '/var/lib/kolla/config_files', 'ovsdb_port': '18540'}
JOBS = [  # (template, service dir, dest name, mode)
    ('openvswitch-db-server.json.j2', 'openvswitch-db-server', 'config.json', 0o660),
    ('start-ovsdb-server.j2', 'openvswitch-db-server', 'start-ovsdb-server', 0o770),
    ('openvswitch-vswitchd.json.j2', 'openvswitch-vswitchd', 'config.json', 0o660),
    ('start-ovs.j2', 'openvswitch-vswitchd', 'start-ovs', 0o770),
]
env = jinja2.Environment(loader=jinja2.FileSystemLoader(KA), trim_blocks=True, keep_trailing_newline=True,
                         undefined=jinja2.StrictUndefined)
for tpl, svc, dest, mode in JOBS:
    os.makedirs(os.path.join(OUT, svc), exist_ok=True)
    path = os.path.join(OUT, svc, dest)
    with open(path, 'w') as f:
        f.write(env.get_template(tpl).render(**VARS))
    os.chmod(path, mode)
    print('rendered %s -> %s' % (tpl, os.path.relpath(path, os.path.dirname(OUT))))
