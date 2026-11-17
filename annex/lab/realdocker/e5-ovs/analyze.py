#!/usr/bin/env python3
"""Summarise one e5 test directory: timeline.txt (events relative to T0), strace.txt, ping.txt.

Usage: analyze.py <test dir>
Inputs written by run.sh: timeline.raw ("<epoch> <text>", the T0 line starts with "T0 "), events.raw (docker events,
"<epoch ns> <action> [exitCode=N]"), pids.txt ("<host pid> <name>"), strace.raw (strace -ttt -f), ping-<dst>.raw
(ping -D -O output).
"""
import glob
import os
import re
import sys

T = sys.argv[1]


def read(name):
    p = os.path.join(T, name)
    return open(p).read().splitlines() if os.path.exists(p) else []


events = []
for line in read('timeline.raw'):
    ts, text = line.split(' ', 1)
    events.append((float(ts), text))
t0 = next(ts for ts, text in events if text.startswith('T0 '))
for line in read('events.raw'):
    parts = line.split()
    events.append((int(parts[0]) / 1e9, 'docker event: ' + ' '.join(parts[1:])))
events.sort()


def rel(ts):
    return '%+9.3f s' % (ts - t0)


# ---- strace: signals only, renamed by pid
names = dict(l.split(None, 1) for l in read('pids.txt'))
strace_lines = []
for line in read('strace.raw'):
    pid, ts, rest = line.split(None, 2)
    who = names.get(pid, 'thread %s' % pid)
    # -T appends the time spent in the syscall: a syscall that was in progress when strace attached is printed with
    # its entry time, so report the return time (entry + duration) for completed calls.
    # A "<... resumed>" line is already stamped at the return.
    m = re.search(r' <(\d+\.\d+)>$', rest)
    resumed = 'resumed>' in rest
    t = float(ts) + float(m.group(1)) if m and not resumed else float(ts)
    if m and resumed:
        rest = rest[:m.start()]
    elif m:
        rest = rest[:m.start()] + '  [returned; entry %s]' % rel(float(ts)).strip()
    strace_lines.append((t, '%s  %-22s %s' % (rel(t), who, rest)))
strace_lines = [l for t, l in sorted(strace_lines, key=lambda x: x[0])]
if strace_lines:
    with open(os.path.join(T, 'strace.txt'), 'w') as f:
        f.write('# strace -T -f -e trace=rt_sigtimedwait,kill,exit_group[,...] -e signal=all on the host; times relative\n'
                '# to T0 (return time for completed syscalls); "thread N" = another thread of the daemon (host tid)\n')
        f.write('\n'.join(strace_lines) + '\n')

# ---- pings
ping_out, excerpt, any_gap = [], [], False
REPLY = re.compile(r'^\[(\d+\.\d+)\] \d+ bytes from [\d.]+: icmp_seq=(\d+)')
MISS = re.compile(r'^\[(\d+\.\d+)\] no answer yet for icmp_seq=(\d+)')
for path in sorted(glob.glob(os.path.join(T, 'ping-*.raw'))):
    dst = os.path.basename(path)[5:-4]
    replies, misses, stats = [], [], ''
    lines = open(path).read().splitlines()
    for line in lines:
        m = REPLY.match(line)
        if m:
            replies.append((float(m.group(1)), int(m.group(2))))
            continue
        m = MISS.match(line)
        if m:
            misses.append((float(m.group(1)), int(m.group(2))))
        elif 'packets transmitted' in line:
            stats = line.strip()
    ping_out.append('== %s (%s)' % (dst, stats))
    if not replies:
        ping_out.append('   no reply at all')
        continue
    ping_out.append('   first reply %s (seq %d), last reply %s (seq %d)'
                    % (rel(replies[0][0]), replies[0][1], rel(replies[-1][0]), replies[-1][1]))
    gaps = []
    for (ta, sa), (tb, sb) in zip(replies, replies[1:]):
        if tb - ta > 0.25:
            gaps.append((ta, sa, tb, sb))
    any_gap = any_gap or bool(gaps)
    if not gaps:
        ping_out.append('   no interruption (no gap > 0.25 s between consecutive replies)')
    for ta, sa, tb, sb in gaps:
        ping_out.append('   GAP: last reply before %s (seq %d) -> next reply %s (seq %d): %.3f s without reply, '
                        '%d requests unanswered' % (rel(ta), sa, rel(tb), sb, tb - ta, sb - sa - 1))
    # excerpt: the raw lines around each gap (2 replies before, the first misses, 2 replies after), prefixed by T0 time
    keep = set()
    for ta, sa, tb, sb in gaps:
        keep.update(range(sa - 1, sa + 4))
        keep.update(range(sb - 2, sb + 2))
    excerpt.append('== %s' % dst)
    last = None
    for line in lines:
        m = REPLY.match(line) or MISS.match(line)
        if m and int(m.group(2)) in keep:
            if last is not None and int(m.group(2)) > last + 1:
                excerpt.append('   ...')
            excerpt.append('%s  %s' % (rel(float(m.group(1))), line))
            last = int(m.group(2))
        elif 'packets transmitted' in line:
            excerpt.append(line)
    if misses and misses[-1][1] > replies[-1][1]:
        ping_out.append('   still unanswered at the end: seq %d..%d (last miss report %s)'
                        % (replies[-1][1] + 1, misses[-1][1], rel(misses[-1][0])))
if ping_out:
    with open(os.path.join(T, 'ping.txt'), 'w') as f:
        f.write('# ping -D -O -i 0.05 from e5-peer1; times relative to T0; a gap is > 0.25 s between replies\n')
        f.write('\n'.join(ping_out) + '\n')

if any_gap:
    with open(os.path.join(T, 'ping-excerpt.txt'), 'w') as f:
        f.write('# raw ping -D -O lines around each gap; left column: time relative to T0\n')
        f.write('\n'.join(excerpt) + '\n')
with open(os.path.join(T, 'timeline.txt'), 'w') as f:
    f.write('# times relative to T0 = %.6f (%s)\n' % (t0, next(text for ts, text in events if text.startswith('T0 '))))
    for ts, text in events:
        f.write('%s  %s\n' % (rel(ts), text))
print(open(os.path.join(T, 'timeline.txt')).read() + '\n'.join(ping_out))
