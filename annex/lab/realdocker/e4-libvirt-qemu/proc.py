#!/usr/bin/env python3
"""Host-side /proc helpers for e4 (run with python3 -I).

  proc.py qemu NAME           host PIDs of qemu-system processes whose command line has guest=NAME
  proc.py show LABEL PID...   one block per PID: comm, parent, uid, cgroups, namespaces, exe
  proc.py kids PID            host PIDs of the direct children of PID
  proc.py rootmnt LABEL PID   the overlay mount at / in the process's mount namespace (upperdir)
  proc.py inside PID CID      per hierarchy: is PID inside the container cgroup /docker/CID?
  proc.py subtree DIR         PIDs in a cgroup directory and all its descendants
  proc.py shim RAW T0 QPID..  format a strace log of the containerd shim (runc execve, kill calls)
Docker's 64-hex container ids are shortened to 12 characters.
"""
import os
import re
import sys

HEX = re.compile(r'\b([0-9a-f]{12})[0-9a-f]{52}\b')


def rd(path, default=''):
    try:
        with open(path, 'rb') as f:
            return f.read().decode(errors='replace')
    except OSError:
        return default


def link(path):
    try:
        return os.readlink(path)
    except OSError as e:
        return '<%s>' % e.strerror


def status(pid):
    d = {}
    for line in rd('/proc/%s/status' % pid).splitlines():
        k, _, v = line.partition(':')
        d[k] = v.strip()
    return d


def qemu(name):
    for p in sorted(int(x) for x in os.listdir('/proc') if x.isdigit()):
        argv = rd('/proc/%d/cmdline' % p).split('\0')
        if argv and 'qemu-system' in os.path.basename(argv[0]) and any(
                a.startswith('guest=%s,' % name) or a == 'guest=%s' % name for a in argv):
            print(p)


def show(label, pids):
    for pid in pids:
        st = status(pid)
        if not st:
            print('[%s] pid %s: GONE (no /proc/%s)' % (label, pid, pid))
            continue
        pp = st.get('PPid', '?')
        print('[%s] pid %s comm=%s ppid=%s(%s) uid=%s nspid=%s' % (
            label, pid, st.get('Name'), pp, rd('/proc/%s/comm' % pp).strip(), st.get('Uid', '').split()[0],
            st.get('NSpid', '').replace('\t', ',')))
        groups = {}
        for line in rd('/proc/%s/cgroup' % pid).splitlines():
            _, ctrl, path = line.split(':', 2)
            groups.setdefault(HEX.sub(r'\1', path), []).append(ctrl or 'unified(v2)')
        for path, ctrls in groups.items():
            print('    cgroup %-52s <- %s' % (path, ','.join(ctrls)))
        print('    ns mnt=%s pid=%s  root=%s  exe=%s' % (
            link('/proc/%s/ns/mnt' % pid), link('/proc/%s/ns/pid' % pid), link('/proc/%s/root' % pid),
            link('/proc/%s/exe' % pid)))


def rootmnt(label, pid):
    """The overlay mount at / in the process's mount namespace: shows which container rootfs it runs from."""
    for line in rd('/proc/%s/mountinfo' % pid).splitlines():
        f = line.split()
        if len(f) > 4 and f[4] == '/':
            m = re.search(r'upperdir=([^,]+)', line)
            up = m.group(1) if m else ''
            print('[%s] pid %s root mount: %s upperdir=%s (%s on the host)' % (
                label, pid, f[f.index('-') + 1], up, 'exists' if up and os.path.isdir(up) else 'ABSENT'))
            return
    print('[%s] pid %s: no mountinfo' % (label, pid))


def subtree(path):
    """All PIDs in a cgroup directory and its descendants (what a recursive cgroup.procs walk returns)."""
    pids = []
    for d, _, files in os.walk(path):
        if 'cgroup.procs' in files:
            pids += rd(os.path.join(d, 'cgroup.procs')).split()
    print(' '.join(sorted(set(pids), key=int)) or '-')


def inside(pid, cid):
    """For each hierarchy: is PID inside the cgroup subtree /docker/<cid> (the container's cgroup)?"""
    res = []
    for line in rd('/proc/%s/cgroup' % pid).splitlines():
        _, ctrl, path = line.split(':', 2)
        res.append('%s=%s' % (ctrl or 'unified', 'IN' if path.startswith('/docker/' + cid) else 'out'))
    print(' '.join(res) if res else 'GONE')


def kids(pid):
    for tid in os.listdir('/proc/%s/task' % pid):
        for c in rd('/proc/%s/task/%s/children' % (pid, tid)).split():
            print(c)


def shim(raw, t0, qemu_pids):
    """Format a strace -ttt -f log of the containerd shim: runc invocations and kill() calls."""
    qemu_pids = set(qemu_pids)
    t0 = float(t0)
    for line in rd(raw).splitlines():
        m = re.match(r'(\d+)\s+(\d+\.\d+)\s+(.*)$', line)
        if not m:
            continue
        pid, ts, rest = m.group(1), float(m.group(2)), m.group(3)
        if rest.startswith('execve(') and '= -1' not in rest:
            am = re.search(r'\[(.*?)\]', rest)
            argv = [a.strip().strip('"') for a in am.group(1).split(', ')] if am else []
            out, skip = [], False
            for a in argv:  # drop "--root X", "--log X", "--log-format json" noise
                if skip:
                    skip = False
                    continue
                if a in ('--root', '--log', '--log-format'):
                    skip = True
                    continue
                out.append(a)
            text = 'execve ' + ' '.join(out)
        elif re.match(r'write\(\d+</sys/fs/cgroup/', rest):
            text = re.sub(r', \d+\) = ', ') = ', rest)
        elif rest.startswith('write(2<pipe') and 'unable to' in rest:
            text = 'runc stderr: ' + rest.split(', "', 1)[1][:170]  # runc's error message
        elif rest.startswith('write('):
            continue
        elif rest.startswith('rmdir(') and '/sys/fs/cgroup' in rest:
            text = rest
        elif re.match(r'(kill|tgkill)\(\d+, (\d+, )?SIGURG', rest):
            continue  # Go runtime preemption signals between the shim's own threads
        elif re.match(r'(kill|tgkill|pidfd_send_signal)\(', rest):
            km = re.match(r'kill\((-?\d+), (\w+)\)', rest)
            tag = ''
            if km and km.group(1) in qemu_pids:
                tag = '   <== the QEMU process'
            text = rest + tag
        else:
            continue
        print('%+8.3f s  pid %s  %s' % (ts - t0, pid, HEX.sub(r'\1', text)))


if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'qemu':
        qemu(sys.argv[2])
    elif cmd == 'show':
        show(sys.argv[2], sys.argv[3:])
    elif cmd == 'kids':
        kids(sys.argv[2])
    elif cmd == 'inside':
        inside(sys.argv[2], sys.argv[3])
    elif cmd == 'rootmnt':
        rootmnt(sys.argv[2], sys.argv[3])
    elif cmd == 'subtree':
        subtree(sys.argv[2])
    elif cmd == 'shim':
        shim(sys.argv[2], sys.argv[3], sys.argv[4:])
