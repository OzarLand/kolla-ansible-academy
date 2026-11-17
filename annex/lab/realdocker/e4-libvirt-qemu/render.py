#!/usr/bin/env python3
"""Render the real kolla-ansible ussuri-eol nova-libvirt templates with python jinja2.

usage: render.py <kolla-ansible checkout> <dest dir>
Ansible's template defaults are mirrored (trim_blocks=True). Variables are the role and group_vars defaults
(roles/nova-cell/defaults/main.yml:333,343,409-436, group_vars/all.yml:7,251) except: nova_libvirt_port 18409
(lab host-port range instead of 16509, because the container uses the host network like every kolla container),
migration_interface_address 127.0.0.1, a lab-only SASL password, and the qemu_max_* override below.
The Ansible 'bool' filter is re-implemented (ansible/plugins/filter/core.py semantics).
"""
import os
import sys

import jinja2


def to_bool(a):
    if isinstance(a, bool):
        return a
    if a is None:
        return False
    return str(a).lower() in ('yes', 'on', '1', 'true')


src, dest = sys.argv[1], sys.argv[2]
tdir = os.path.join(src, 'ansible/roles/nova-cell/templates')
env = jinja2.Environment(loader=jinja2.FileSystemLoader(tdir), keep_trailing_newline=True, trim_blocks=True,
                         undefined=jinja2.StrictUndefined)
env.filters['bool'] = to_bool
libvirt_tls = False
v = {
    'container_config_directory': '/var/lib/kolla/config_files',  # group_vars/all.yml:7
    'libvirt_tls': libvirt_tls,                                     # defaults/main.yml:414
    'libvirt_enable_sasl': True,                                    # defaults/main.yml:431
    'libvirt_sasl_authname': 'nova',                                # defaults/main.yml:433
    'libvirt_sasl_mech_list': ['SCRAM-SHA-256' if libvirt_tls else 'DIGEST-MD5'],  # :435-436
    'libvirt_sasl_password': 'e4-lab-only',                         # lab-only value, not a secret
    'nova_backend': 'default', 'cinder_backend_ceph': False,
    'nova_libvirt_logging_debug': False,                            # :333 -> nova_logging_debug -> False
    'nova_libvirt_port': '18409',                                   # lab port (default 16509, :343)
    'migration_interface_address': '127.0.0.1',
    'qemu_max_files': 32768, 'qemu_max_processes': 131072,          # :409-412
}
# Lab override (E4_QEMU_MAX_FILES / E4_QEMU_MAX_PROCESSES): the sandbox has no CAP_SYS_RESOURCE in its bounding
# set and its hard limits (nofile 20000, nproc 64272) are below the defaults, so libvirt's setrlimit for QEMU
# fails with EPERM. qemu_max_files / qemu_max_processes are ordinary kolla-ansible variables.
for var in ('qemu_max_files', 'qemu_max_processes'):
    if os.environ.get('E4_' + var.upper()):
        v[var] = int(os.environ['E4_' + var.upper()])
os.makedirs(dest, exist_ok=True)
for tpl, out in [('nova-libvirt.json.j2', 'config.json'), ('libvirtd.conf.j2', 'libvirtd.conf'),
                 ('qemu.conf.j2', 'qemu.conf'), ('sasl.conf.j2', 'sasl.conf'), ('auth.conf.j2', 'auth.conf')]:
    with open(os.path.join(dest, out), 'w') as f:
        f.write(env.get_template(tpl).render(**v))
    os.chmod(os.path.join(dest, out), 0o660)  # tasks/config.yml mode "0660"
print('rendered into', dest)
