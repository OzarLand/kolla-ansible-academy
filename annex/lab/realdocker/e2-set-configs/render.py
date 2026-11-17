#!/usr/bin/env python3
"""Render the config.json variants used by experiment e2 from the real kolla-ansible ussuri-eol templates.

Usage (inside e2-render:ussuri, bionic python3-jinja2 2.10): render.py <vendor dir> <output dir>

Rendering follows Ansible's template module: trim_blocks=True, and Ansible's 'bool' filter is re-implemented
(ansible/plugins/filter/core.py to_bool). Undefined variables raise (StrictUndefined), so every input is explicit.

Variants that kolla-ansible would produce from inputs this lab does not have (a changed command or permissions block,
a changed perm/owner, an entry shape taken from another role's template) are made by editing the rendered JSON. Each
such edit is named "edit:" in the variant table below and in variants.txt.
"""
import copy
import json
import os
import sys

import jinja2

CCD = '/var/lib/kolla/config_files'   # group_vars/all.yml:7 container_config_directory


def to_bool(a):
    # Ansible 2.9 ansible/plugins/filter/core.py to_bool
    if a is None or isinstance(a, bool):
        return a
    if isinstance(a, str):
        a = a.lower()
    if a in ('yes', 'on', '1', 'true', 1):
        return True
    return False


def env_for(path):
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(path), trim_blocks=True,
                             undefined=jinja2.StrictUndefined, keep_trailing_newline=True)
    env.filters['bool'] = to_bool
    return env


def main():
    vendor, out = sys.argv[1], sys.argv[2]
    ka = os.path.join(vendor, 'kolla-ansible/ansible/roles')
    notes = []

    def write(rel, text, note):
        p = os.path.join(out, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, 'w') as f:
            f.write(text)
        notes.append('%-34s %s' % (rel, note))

    def dump(obj):
        return json.dumps(obj, indent=4) + '\n'

    # ---- nova-compute (roles/nova-cell/templates/nova-compute.json.j2) ----
    nova_t = env_for(os.path.join(ka, 'nova-cell/templates')).get_template('nova-compute.json.j2')
    # Ussuri defaults: roles/nova-cell/defaults/main.yml libvirt_tls false (:414), libvirt_enable_sasl true (:431);
    # nova_backend 'default' and virt type kvm (no Ceph, no VMware). nova_policy_file is defined when a custom
    # policy file exists in node_custom_config (roles/nova-cell/tasks/config.yml:24-40).
    base_vars = dict(container_config_directory=CCD, nova_backend='default', nova_compute_virt_type='kvm',
                     vmware_vcenter_insecure=False, libvirt_tls=False, libvirt_enable_sasl=True,
                     nova_policy_file='policy.yaml')

    def nova(**over):
        v = dict(base_vars)
        for k, val in over.items():
            if val is None:
                v.pop(k, None)
            else:
                v[k] = val
        text = nova_t.render(**v)
        json.loads(text)   # must be valid JSON
        return text

    base_text = nova()
    base = json.loads(base_text)
    write('nova-compute/base.json', base_text, 'template, Ussuri defaults + custom policy.yaml (nova_policy_file)')
    write('nova-compute/nosasl.json', nova(libvirt_enable_sasl=False),
          'template, libvirt_enable_sasl: false (auth.conf entry dropped)')
    write('nova-compute/nopolicy.json', nova(nova_policy_file=None),
          'template, nova_policy_file undefined (policy entry dropped)')
    write('nova-compute/nosasl-nopolicy.json', nova(libvirt_enable_sasl=False, nova_policy_file=None),
          'template, both entries dropped')

    def edited(fn):
        c = copy.deepcopy(base)
        fn(c)
        return c

    def entry(c, dest):
        return [e for e in c['config_files'] if e['dest'] == dest][0]

    write('nova-compute/perm.json',
          dump(edited(lambda c: entry(c, '/etc/nova/nova.conf').update(perm='0640'))),
          'edit: nova.conf entry perm 0600 -> 0640')
    write('nova-compute/owner.json',
          dump(edited(lambda c: entry(c, '/etc/nova/nova.conf').update(owner='root:nova'))),
          'edit: nova.conf entry owner nova -> root:nova (shape of the libvirt_tls entries)')
    write('nova-compute/cmd.json',
          dump(edited(lambda c: c.update(command='nova-compute --e2-marker=command-v2'))),
          'edit: command "nova-compute" -> "nova-compute --e2-marker=command-v2"')
    write('nova-compute/permsonly.json',
          dump(edited(lambda c: c['permissions'][1].update(owner='nova:kolla'))),
          'edit: permissions /var/lib/nova owner nova:nova -> nova:kolla')
    # roles/prometheus/templates/prometheus-server.json.j2:10-15 (extras/*, preserve_properties, optional)
    write('nova-compute/preserve.json',
          dump(edited(lambda c: c['config_files'].append(
              {'source': CCD + '/extras/*', 'dest': '/etc/nova/extras/',
               'preserve_properties': True, 'optional': True}))),
          'edit: + prometheus-style extras/* entry (preserve_properties, optional, no owner/perm)')
    # roles/haproxy/templates/haproxy.json.j2:16-20 (services.d/ directory source)
    write('nova-compute/dir.json',
          dump(edited(lambda c: c['config_files'].append(
              {'source': CCD + '/e2.d/', 'dest': '/etc/nova/e2.d', 'owner': 'nova', 'perm': '0700'}))),
          'edit: + haproxy services.d-style directory entry e2.d/ -> /etc/nova/e2.d (nova, 0700)')
    write('nova-compute/invalid.json', base_text.rstrip().rstrip('}') + '\n',
          'edit: base with its closing brace removed (invalid JSON)')

    # ---- memcached (roles/memcached/templates/memcached.json.j2) ----
    mc_t = env_for(os.path.join(ka, 'memcached/templates')).get_template('memcached.json.j2')
    mc = dict(api_interface_address='127.0.0.1', memcached_port='18211',
              memcached_connection_limit='5000', memcached_max_memory='64')
    write('memcached/v1.json', mc_t.render(**mc), 'template, port 18211, max_memory 64')
    mc.update(memcached_port='18212', memcached_max_memory='128')
    write('memcached/v2.json', mc_t.render(**mc), 'template, port 18212, max_memory 128')

    # ---- heat-api (roles/heat/templates/heat-api.json.j2) ----
    heat_t = env_for(os.path.join(ka, 'heat/templates')).get_template('heat-api.json.j2')
    text = heat_t.render(container_config_directory=CCD, kolla_base_distro='ubuntu', heat_enable_tls_backend=False)
    json.loads(text)
    write('heat-api/config.json', text, 'template, ubuntu, no TLS backend, no custom policy')

    with open(os.path.join(out, 'variants.txt'), 'w') as f:
        f.write('\n'.join(notes) + '\n')


if __name__ == '__main__':
    main()
