#!/usr/bin/env python3
"""Turn the daemon's event stream (work/events.jsonl, from `docker events --format '{{json .}}'`) and the step
markers (work/markers.txt) into out/events.txt (events per step, time relative to the step start) and
out/timings.txt (playbook wall time per step, and for every stop: SIGTERM->SIGKILL and SIGTERM->die).

Usage: analyze.py WORK OUT
"""
import json
import os
import sys

work, out = sys.argv[1], sys.argv[2]
steps = []  # (name, t0, t1) in ns
begin = {}
with open(os.path.join(work, 'markers.txt')) as f:
    for line in f:
        t, kind, name = line.split()
        if kind == 'BEGIN':
            begin[name] = int(t)
        else:
            steps.append((name, begin.pop(name), int(t)))

events = []
with open(os.path.join(work, 'events.jsonl')) as f:
    for line in f:
        try:
            e = json.loads(line)
        except ValueError:
            continue
        a = e.get('Actor', {}).get('Attributes', {})
        if e.get('Type') == 'volume':
            if e.get('Action') in ('mount', 'unmount'):
                continue   # one pair per container start/stop: noise
            events.append((int(e['timeNano']), 'volume ' + e.get('Actor', {}).get('ID', '?'), e.get('Action', ''), {}))
            continue
        events.append((int(e['timeNano']), a.get('name', '?'), e.get('Action', ''), a))


def describe(action, a):
    extra = []
    for k in ('signal', 'exitCode'):
        if k in a:
            extra.append('%s=%s' % (k, a[k]))
    if action.startswith('exec_create') or action.startswith('exec_start'):
        action = action.split(':', 1)[0] + ' [' + action.split(':', 1)[1].strip() + ']' if ':' in action else action
    return action + ('  ' + ' '.join(extra) if extra else '')


ev_lines, tm_lines = [], []
for name, t0, t1 in steps:
    ev_lines.append('== %s  (playbook wall time %.2f s)' % (name, (t1 - t0) / 1e9))
    term = {}
    stops = []
    for t, cname, action, a in events:
        if not (t0 <= t <= t1):
            continue
        ev_lines.append('  +%7.3f s  %-22s %s' % ((t - t0) / 1e9, cname, describe(action, a)))
        if action == 'kill' and a.get('signal') == '15':
            term[cname] = {'term': t}
        elif action == 'kill' and a.get('signal') == '9' and cname in term:
            term[cname]['kill'] = t
        elif action == 'die' and cname in term:
            s = term.pop(cname)
            s['die'] = t
            stops.append((cname, s))
    tm_lines.append('%-34s playbook wall time %6.2f s' % (name, (t1 - t0) / 1e9))
    for cname, s in stops:
        k = '%.2f s' % ((s['kill'] - s['term']) / 1e9) if 'kill' in s else 'none (no SIGKILL)'
        tm_lines.append('    stop of %-20s SIGTERM->SIGKILL %-18s SIGTERM->die %.2f s' % (
            cname, k, (s['die'] - s['term']) / 1e9))

with open(os.path.join(out, 'events.txt'), 'w') as f:
    f.write('# docker events for the e3 containers, grouped by step; times relative to the step start\n')
    f.write('\n'.join(ev_lines) + '\n')
with open(os.path.join(out, 'timings.txt'), 'w') as f:
    f.write('# lab measurements (Docker 29.9.2, cgroup v1, this sandbox); not production numbers\n')
    f.write('\n'.join(tm_lines) + '\n')
