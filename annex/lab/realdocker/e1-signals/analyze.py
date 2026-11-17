#!/usr/bin/env python3
"""Turn a host-side strace of an e1 container into a signal timeline and a per-process fate table.

  analyze.py <strace.raw> <proctab.json> <t0> <t1>

t0/t1: epoch seconds just before `docker stop` started and just after it returned. strace ran on the host with
-ttt -T -f --decode-pids=pidns -e trace=kill,tgkill,tkill,rt_sigtimedwait,wait4,exit_group,execve,clone,clone3,
fork,vfork -e signal=all, attached to every
process of the pre-stop table (proctab.py). It shows signals delivered to a handler or a default action
("receives", from the --- SIG lines), signals taken with sigwait/sigtimedwait ("takes": the call returns the signal),
the kill() calls a process makes, children it reaps, programs that new processes exec, and how each process ended.
Labels are "name(pid in the container's PID namespace)"; si_pid is given in the receiver's namespace (0 = the sender
is outside it, i.e. the container runtime); the pids passed to kill() and returned by wait4() are the caller's view.
Threads of a traced process (also those cloned during the trace) are folded into it; only their signal events are
kept. Processes forked during the trace are labelled with the program they exec and their parent.
"""
import json
import os
import re
import sys

raw, tab, t0, t1 = sys.argv[1], sys.argv[2], float(sys.argv[3]), float(sys.argv[4])
rows = {r['hpid']: r for r in json.load(open(tab))}
owner = {}                      # host tid -> host pid of the process it belongs to
for r in rows.values():
    for t in r.get('tids', [r['hpid']]):
        owner[t] = r['hpid']
newname = {}                    # host pid of a process forked during the trace -> program it exec'd
parent = {}                     # host pid of a process forked during the trace -> host tid of the forking thread
pending_clone = {}
pending_exec = {}


def name_of(r):
    cmd = r['cmd'].split()
    name = cmd[0] if cmd else '?'
    if name.endswith(('python3', 'python3.6', 'bash', 'sh')):
        args = [a for a in cmd[1:] if not a.startswith('-')]
        name = args[0] if args else name
    return os.path.basename(name)


def label(tid):
    hpid = owner.get(tid, tid)
    if hpid in rows:
        lab = '%s(%d)' % (name_of(rows[hpid]), rows[hpid]['nspid'])
        return lab if hpid == tid else lab + ' thread'
    if hpid in parent:
        return '%s<-%s' % (newname.get(hpid, 'fork'), label(parent[hpid]).replace(' thread', ''))
    return '%s [host pid %d]' % (newname.get(hpid, 'process'), hpid)


line_re = re.compile(r'^(\d+)\s+(\d+\.\d+) (.*)$')
events, fate, pending = [], {}, {}
for line in open(raw, errors='replace'):
    m = line_re.match(line.rstrip('\n'))
    if not m:
        continue
    tid, ts, what = int(m.group(1)), float(m.group(2)), m.group(3)
    # strace stamps a completed syscall with its entry time and -T appends the duration: use the return time,
    # except for '<... resumed>' lines, which are already stamped at the return.
    dm = re.search(r' <(\d+\.\d+)>$', what)
    if dm and 'resumed>' not in what:
        ts += float(dm.group(1))
    ev, kind = None, 'other'
    # clone/fork: the child's pid in strace's (host) namespace is annotated as /* N in strace's PID NS */
    cm = re.match(r"(<\.\.\. )?(clone3?|fork|vfork)\b", what)
    if cm:
        if '<unfinished' in what:
            pending_clone[tid] = 'CLONE_THREAD' in what
            continue
        rm = re.search(r"= (\d+)(?: /\* (\d+) in strace's PID NS \*/)?", what)
        if rm:
            child = int(rm.group(2) or rm.group(1))
            thread = pending_clone.pop(tid, False) if cm.group(1) else 'CLONE_THREAD' in what
            if thread:
                owner[child] = owner.get(tid, tid)
            else:
                parent[child] = owner.get(tid, tid)
        continue
    what = re.sub(r" /\* \d+ in strace's PID NS \*/", '', what)
    if what.startswith('--- SIG'):
        sm = re.match(r'--- (SIG\w+) \{.*?si_code=(\w+)(?:.*?si_pid=(\d+))?', what)
        if sm and sm.group(1) != 'SIGCHLD':
            ev, kind = 'receives %s (handler or default action), si_pid=%s %s' % (
                sm.group(1), sm.group(3), sm.group(2)), 'signal'
    elif what.startswith('+++'):
        ev, kind = what.strip('+ '), 'end'
        fate[tid] = (ts, ev)
    elif what.startswith('execve(') and '<unfinished' in what:
        pending_exec[tid] = what
    elif (what.startswith('execve(') or what.startswith('<... execve resumed>')) and re.search(r'= 0\b', what):
        call = pending_exec.pop(tid, what) if what.startswith('<...') else what
        args = re.findall(r'"([^"]*)"', call.split('], ')[0])[1:]
        if owner.get(tid, tid) not in rows and args:
            newname[owner.get(tid, tid)] = os.path.basename(args[0])
        ev = 'execs %s' % ' '.join(args)[:110]
    elif 'rt_sigtimedwait' in what:
        sm = re.search(r'= (\d+) \((SIG\w+)\)', what)
        fm = re.search(r'si_code=(\w+), si_pid=(\d+)', what)
        if sm and sm.group(2) != 'SIGCHLD':
            ev, kind = 'takes %s (sigwait/sigtimedwait), si_pid=%s %s' % (
                sm.group(2), fm.group(2) if fm else '?', fm.group(1) if fm else ''), 'signal'
    elif re.match(r'(kill|tgkill|tkill)\(.*<unfinished', what):
        pending[tid] = what.split(' <unfinished')[0]          # e.g. "kill(7, SIGTERM"
    elif re.match(r'<\.\.\. (kill|tgkill|tkill) resumed>', what) and tid in pending:
        rm = re.search(r'=\s*(-?\d+(?: E[A-Z]+)?)', what)
        ev, kind = 'calls %s) = %s' % (pending.pop(tid), rm.group(1) if rm else '?'), 'signal'
    elif re.match(r'(kill|tgkill|tkill)\(', what):
        sm = re.search(r'(kill|tgkill|tkill)\(([-\d, ]+?), (SIG\w+)\)\s*=\s*(-?\d+(?: E[A-Z]+)?)', what)
        if sm:
            ev, kind = 'calls %s(%s, %s) = %s' % sm.groups(), 'signal'
    elif 'wait4' in what:
        sm = re.search(r'WEXITSTATUS\(s\) == (\d+)|WTERMSIG\(s\) == (\w+)', what)
        rm = re.search(r'= (\d+)(?: <[\d.]+>)?\s*$', what)
        if rm and int(rm.group(1)) > 0:
            st = ('exit %s' % sm.group(1)) if sm and sm.group(1) else ('killed by %s' % sm.group(2) if sm else '?')
            ev = 'reaps child pid %s (%s)' % (rm.group(1), st)
    elif what.startswith('exit_group('):
        ev = what.split(' =')[0].strip()
    if ev is None:
        continue
    is_thread = tid in owner and owner[tid] != tid
    if is_thread and kind != 'signal':
        continue                # a thread's own exit, reaping or exec: noise
    if not is_thread and tid not in rows and kind != 'signal' and ev.startswith(('exit_group', 'reaps')):
        continue                # short-lived helpers: their exec and their end are enough
    events.append((ts, tid, ev))

print('# time relative to the start of `docker stop` (t0); docker stop returned at +%.3f s' % (t1 - t0))
for ts, tid, ev in sorted(events):
    if ts >= t0 - 0.5:
        print('%+8.3f s  %-36s %s' % (ts - t0, label(tid), ev))
print()
print('# fate of each process of the pre-stop table')
for hpid, r in sorted(rows.items()):
    got = sorted({e.split(',')[0] + ' from si_pid=' + e.split('si_pid=')[1].split()[0]
                  for _, t, e in events if owner.get(t, t) == hpid and e.startswith(('receives', 'takes'))})
    f = fate.get(hpid)
    end = ('%s at %+.3f s' % (f[1], f[0] - t0)) if f else 'no end seen by strace (survived, or not traced)'
    print('%-28s signals: %-58s end: %s' % (label(hpid), '; '.join(got) or 'none', end))
