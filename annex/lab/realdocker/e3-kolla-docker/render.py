#!/usr/bin/env python3
"""Render the real kolla-ansible ussuri-eol templates used by e3 into <work>/etc-kolla/<service>/.

Only the templates whose content matters to the tests are rendered from the real files:
  rabbitmq:     roles/rabbitmq/templates/rabbitmq.json.j2      -> e3_rabbitmq/config.json
  heat-api:     roles/heat/templates/heat-api.json.j2          -> heat-api/config.json
  swift-rsyncd: roles/swift/templates/swift-rsyncd.json.j2     -> swift-rsyncd/config.json
                roles/swift/templates/rsyncd.conf.j2           -> swift-rsyncd/rsyncd.conf
The other files that config.json lists (rabbitmq.conf, heat.conf, ...) are one-line placeholders whose first line
carries a version marker: the stand-in services only read that marker.
Modes follow what Kolla-Ansible writes: directories 0770, files 0660, owner root (group_vars/all.yml:20-21).

Usage: render.py KOLLA_ANSIBLE_SRC WORK SERVICE [--marker TEXT] [--project NAME] [--swift-groups account,...]
"""
import argparse
import os

import jinja2

CONTAINER_CONFIG_DIRECTORY = '/var/lib/kolla/config_files'   # group_vars/all.yml:7


def env(src):
    e = jinja2.Environment(loader=jinja2.FileSystemLoader(os.path.join(src, 'ansible', 'roles')),
                           trim_blocks=True, keep_trailing_newline=True, undefined=jinja2.StrictUndefined)
    e.filters['bool'] = lambda v: str(v).lower() in ('1', 'true', 'yes', 'on')
    e.filters['kolla_address'] = lambda network: '127.0.0.1'   # the lab has one address; swift_replication -> lo
    return e


def write(path, text):
    with open(path, 'w') as f:
        f.write(text)
    os.chmod(path, 0o660)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('src')
    p.add_argument('work')
    p.add_argument('service', choices=['rabbitmq', 'heat-api', 'swift-rsyncd'])
    p.add_argument('--marker', default='v1')
    p.add_argument('--swift-groups', default='account')
    p.add_argument('--project', default='e3_rabbitmq')
    a = p.parse_args()
    e = env(a.src)
    base = os.path.join(a.work, 'etc-kolla')
    if a.service == 'rabbitmq':
        project_name = a.project
        d = os.path.join(base, project_name)
        os.makedirs(d, exist_ok=True)
        write(os.path.join(d, 'config.json'), e.get_template('rabbitmq/templates/rabbitmq.json.j2').render(
            container_config_directory=CONTAINER_CONFIG_DIRECTORY, project_name=project_name))
        for f in ('rabbitmq-env.conf', 'rabbitmq.conf', 'erl_inetrc', 'advanced.config', 'definitions.json'):
            write(os.path.join(d, f), '# e3 placeholder %s %s\n' % (f, a.marker))
    elif a.service == 'heat-api':
        d = os.path.join(base, 'heat-api')
        os.makedirs(d, exist_ok=True)
        write(os.path.join(d, 'config.json'), e.get_template('heat/templates/heat-api.json.j2').render(
            container_config_directory=CONTAINER_CONFIG_DIRECTORY, kolla_base_distro='ubuntu',
            heat_enable_tls_backend='no'))
        for f in ('heat.conf', 'wsgi-heat-api.conf'):
            write(os.path.join(d, f), '# e3 placeholder %s %s\n' % (f, a.marker))
    else:
        d = os.path.join(base, 'swift-rsyncd')
        os.makedirs(d, exist_ok=True)
        write(os.path.join(d, 'config.json'), e.get_template('swift/templates/swift-rsyncd.json.j2').render(
            container_config_directory=CONTAINER_CONFIG_DIRECTORY, swift_rsync_port='18373'))
        member = set(a.swift_groups.split(','))
        groups = {'swift-%s-server' % g: (['localhost'] if g in member else [])
                  for g in ('account', 'container', 'object')}
        write(os.path.join(d, 'rsyncd.conf'), e.get_template('swift/templates/rsyncd.conf.j2').render(
            inventory_hostname='localhost', groups=groups, swift_devices_mount_point='/srv/node'))
    os.chmod(base, 0o770)
    os.chmod(d, 0o770)


if __name__ == '__main__':
    main()
