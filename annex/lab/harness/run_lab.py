#!/usr/bin/env python3
"""Run the real kolla-ansible ussuri-eol site.yml in the stub lab.

usage: run_lab.py --run NAME --computes N [--state-from RUN] [--action deploy]
                  [--tags t1,t2] [--limit X] [--extra k=v ...] [--forks F]
                  [--custom-config DIR]
"""
import argparse, os, re, shutil, subprocess, sys, json, time
S = os.environ.get('KOLLA_LAB_ROOT', os.path.expanduser('~/kolla-lab'))
LAB = S + '/lab'
PY = S + '/venv-ansible/bin/python'

ap = argparse.ArgumentParser()
ap.add_argument('--run', required=True)
ap.add_argument('--computes', type=int, default=3)
ap.add_argument('--state-from')
ap.add_argument('--action', default='deploy')
ap.add_argument('--tags')
ap.add_argument('--skip-tags')
ap.add_argument('--limit')
ap.add_argument('--forks', type=int, default=20)
ap.add_argument('--extra', action='append', default=[])
ap.add_argument('--globals', default=LAB + '/etc/kolla/globals.yml')
ap.add_argument('--playbook', default='site.yml')
ap.add_argument('--registry')
ap.add_argument('--controllers', type=int, default=3)
ap.add_argument('--custom-config', default=LAB + '/etc/kolla/config')
ap.add_argument('--quiet', action='store_true')
a = ap.parse_args()

run = os.path.join(LAB, 'runs', a.run)
if os.path.exists(run):
    shutil.rmtree(run)
os.makedirs(run)
if a.state_from:
    src = os.path.join(LAB, 'runs', a.state_from)
    shutil.copytree(os.path.join(src, 'state'), os.path.join(run, 'state'))
    shutil.copytree(os.path.join(src, 'hosts'), os.path.join(run, 'hosts'), symlinks=True)
    for f in ('cells.json', 'registry.json'):
        if os.path.exists(os.path.join(src, f)):
            shutil.copy(os.path.join(src, f), run)
if a.registry:
    shutil.copy(a.registry, os.path.join(run, 'registry.json'))

# inventory with per-host connection vars
inv_src = open(os.path.join(LAB, 'inv', 'multinode-%d' % a.computes)).read()
if a.controllers != 3:
    inv_src = inv_src.replace('control01\ncontrol02\ncontrol03', '\n'.join('control%02d' % i for i in range(1, a.controllers + 1)))
hosts = set()
out = []
section = ''
for line in inv_src.splitlines():
    s = line.strip()
    if s.startswith('['):
        section = s
    if (s and not s.startswith('#') and not s.startswith('[') and '=' not in s and ' ' not in s
            and ':children' not in section and ':vars' not in section):
        h = s
        hosts.add(h)
        line = ("%s ansible_connection=local ansible_python_interpreter='LAB_HOST=%s LAB_RUN=%s %s' "
                "node_config_directory=%s/hosts/%s/etc/kolla" % (h, h, run, PY, run, h))
    out.append(line)
out = [l.replace('localhost       ansible_connection=local', 'localhost ansible_connection=local ansible_python_interpreter=' + PY) for l in out]
open(os.path.join(run, 'inventory'), 'w').write('\n'.join(out) + '\n')
computes = sorted(h for h in hosts if h.startswith('compute'))
json.dump(computes, open(os.path.join(run, 'computes.json'), 'w'))

cmd = [S + '/venv-ansible/bin/ansible-playbook', '-i', os.path.join(run, 'inventory'),
       '-e', '@' + a.globals, '-e', '@' + LAB + '/etc/kolla/passwords.yml',
       '-e', 'CONFIG_DIR=' + LAB + '/etc/kolla', '-e', 'kolla_action=' + a.action,
       '-e', 'node_custom_config=' + a.custom_config,
       '--forks', str(a.forks)]
for e in a.extra:
    cmd += ['-e', e]
if a.tags:
    cmd += ['--tags', a.tags]
if a.skip_tags:
    cmd += ['--skip-tags', a.skip_tags]
if a.limit:
    cmd += ['--limit', a.limit]
cmd.append(os.path.join(LAB, 'kolla-ansible', 'ansible', a.playbook))
env = dict(os.environ, LAB_RUN=run, ANSIBLE_CALLBACK_PLUGINS=LAB + '/callback',
           ANSIBLE_CALLBACK_WHITELIST='lab_trace', ANSIBLE_HOST_KEY_CHECKING='False',
           ANSIBLE_RETRY_FILES_ENABLED='False', ANSIBLE_LOCAL_TEMP=run + '/.ansible-local',
           ANSIBLE_REMOTE_TEMP=run + '/.ansible-remote', ANSIBLE_NOCOLOR='1',
           ANSIBLE_DEPRECATION_WARNINGS='False', PYTHONWARNINGS='ignore')
open(os.path.join(run, 'cmd.txt'), 'w').write(' '.join(cmd) + '\n')
t0 = time.time()
with open(os.path.join(run, 'ansible.log'), 'w') as log:
    rc = subprocess.call(cmd, stdout=log, stderr=subprocess.STDOUT, env=env, cwd=run)
dt = time.time() - t0
json.dump({'rc': rc, 'seconds': round(dt, 1), 'cmd': cmd}, open(os.path.join(run, 'result.json'), 'w'), indent=1)
print('rc=%s seconds=%.1f run=%s' % (rc, dt, run))
tail = open(os.path.join(run, 'ansible.log')).read().splitlines()
recap = [l for l in tail if l.startswith('PLAY RECAP')]
idx = tail.index(recap[-1]) if recap else len(tail) - 25
if not a.quiet:
    print('\n'.join(tail[idx:idx+25]))
