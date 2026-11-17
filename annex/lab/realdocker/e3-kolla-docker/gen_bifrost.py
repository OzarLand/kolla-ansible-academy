#!/usr/bin/env python3
"""Generate two task files from the real roles/bifrost/tasks/reconfigure.yml (kolla-ansible ussuri-eol).

Changes to the real file, nothing else:
  - the container name 'bifrost-deploy' becomes 'e3-bifrost-deploy' (isolation prefix; the group stays bifrost-deploy);
  - 'import_tasks: config.yml' (renders /etc/kolla/bifrost) and 'include_tasks: start.yml' are dropped.
Variants:
  full       all remaining tasks, in order
  noguard    the same without the first task ('Ensuring the containers up'), to see what the later tasks do

Usage: gen_bifrost.py KOLLA_ANSIBLE_SRC WORK
"""
import os
import sys

import yaml

src, work = sys.argv[1], sys.argv[2]
with open(os.path.join(src, 'ansible/roles/bifrost/tasks/reconfigure.yml')) as f:
    text = f.read().replace('name: bifrost-deploy,', 'name: e3-bifrost-deploy,')
tasks = [t for t in yaml.safe_load(text) if 'import_tasks' not in t and 'include_tasks' not in t]
for variant, ts in (('full', tasks), ('noguard', tasks[1:])):
    with open(os.path.join(work, 'bifrost-%s.yml' % variant), 'w') as f:
        yaml.safe_dump(ts, f, sort_keys=False, width=120)
