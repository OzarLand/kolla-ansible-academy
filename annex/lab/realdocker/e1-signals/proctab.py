#!/usr/bin/env python3
"""Process table of one e1 container, read from the host's /proc.

  proctab.py snap <container> <tag> <out.json>   print the table, save it (with start times) as JSON
  proctab.py alive <in.json>                      print the processes of a saved table that still exist
  proctab.py tids <json>                          refresh the thread ids of a saved table

Members are the container's cgroup (docker top) plus every process whose argv carries "--tag <tag>" (e1 stand-in
children add it, so a process that left the container cgroup is still found). NS* columns are the values inside the
container's PID namespace (from /proc/<pid>/status), H* columns are host values.
"""
import json
import os
import subprocess
import sys


def read(path):
    try:
        with open(path, 'rb') as f:
            return f.read()
    except OSError:
        return None


def info(pid):
    st = read('/proc/%d/status' % pid)
    stat = read('/proc/%d/stat' % pid)
    if st is None or stat is None:
        return None
    fields = dict(l.split(':', 1) for l in st.decode().splitlines() if ':' in l)
    rest = stat.decode().rsplit(')', 1)[1].split()
    cg = '?'
    for line in (read('/proc/%d/cgroup' % pid) or b'').decode().splitlines():
        if ':devices:' in line:
            cg = line.split(':', 2)[2]
    cmd = (read('/proc/%d/cmdline' % pid) or b'').replace(b'\0', b' ').decode(errors='replace').strip()
    return {
        'hpid': pid, 'hppid': int(fields['PPid']), 'hpgid': int(rest[2]), 'hsid': int(rest[3]),
        'starttime': int(rest[19]),
        'nspid': int(fields.get('NSpid', '0').split()[-1]), 'nspgid': int(fields.get('NSpgid', '0').split()[-1]),
        'nssid': int(fields.get('NSsid', '0').split()[-1]), 'uid': int(fields['Uid'].split()[0]),
        'state': fields['State'].split()[0], 'cgroup': cg, 'cmd': cmd[:150] or '[' + fields['Name'].strip() + ']',
    }


def snap(container, tag, out):
    top = subprocess.run(['docker', 'top', container, '-eo', 'pid'], stdout=subprocess.PIPE,
                         universal_newlines=True).stdout.split()[1:]
    pids = {int(p) for p in top}
    marker = ('--tag %s' % tag).encode()
    for d in os.listdir('/proc'):
        if d.isdigit():
            c = read('/proc/%s/cmdline' % d)
            if c and marker in c.replace(b'\0', b' '):
                pids.add(int(d))
    rows = [r for r in (info(p) for p in sorted(pids)) if r]
    for r in rows:  # thread ids, so that a strace -f of a multi-threaded process can be labelled
        try:
            r['tids'] = sorted(int(t) for t in os.listdir('/proc/%d/task' % r['hpid']))
        except OSError:
            r['tids'] = [r['hpid']]
    ns_of = {r['hpid']: r['nspid'] for r in rows}
    for r in rows:
        r['nsppid'] = ns_of.get(r['hppid'], 0)
        r['incg'] = r['hpid'] in {int(p) for p in top}
    with open(out, 'w') as f:
        json.dump(rows, f, indent=1)
    show(rows)


def show(rows):
    print('%7s %6s %7s %6s %6s %6s %6s %1s %-3s %-22s %s' % (
        'HOSTPID', 'NSPID', 'HPPID', 'NSPPID', 'NSPGID', 'NSSID', 'UID', 'S', 'CG', 'DEVICES-CGROUP', 'CMD'))
    for r in rows:
        print('%7d %6d %7d %6d %6d %6d %6d %1s %-3s %-22s %s' % (
            r['hpid'], r['nspid'], r['hppid'], r.get('nsppid', -1), r['nspgid'], r['nssid'], r['uid'], r['state'],
            'ctr' if r.get('incg', True) else 'OUT', r['cgroup'][:22], r['cmd']))


def alive(path):
    rows = json.load(open(path))
    live = []
    for r in rows:
        now = info(r['hpid'])
        if now and now['starttime'] == r['starttime']:
            now['incg'] = False if now['cgroup'] != r['cgroup'] or not r.get('incg', True) else True
            live.append(now)
    if live:
        print('SURVIVORS (same host pid and start time as before the stop; NSPPID -1 = not computed):')
        show(live)
    else:
        print('SURVIVORS: none (all %d processes of the pre-stop table are gone)' % len(rows))


def tids(path):
    rows = json.load(open(path))
    for r in rows:
        try:
            r['tids'] = sorted(set(r.get('tids', [])) | {int(t) for t in os.listdir('/proc/%d/task' % r['hpid'])})
        except OSError:
            pass
    with open(path, 'w') as f:
        json.dump(rows, f, indent=1)


if __name__ == '__main__':
    if sys.argv[1] == 'snap':
        snap(*sys.argv[2:5])
    elif sys.argv[1] == 'tids':
        tids(sys.argv[2])
    else:
        alive(sys.argv[2])
