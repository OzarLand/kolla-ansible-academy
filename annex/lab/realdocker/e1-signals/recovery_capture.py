#!/usr/bin/env python3
"""Keep a copy of mysqld_safe's position-recovery log, which it deletes once the pass succeeds.

  recovery_capture.py <container init host pid> <out file>

mysqld_safe runs `mysqld --wsrep_recover` before every start and sends its stderr to /tmp/wsrep_recovery.XXXXXX in
the container, then removes the file. InnoDB's crash-recovery messages are only there. This opens the file from the
host through /proc/<pid>/root as soon as it appears and reads it after it is deleted (the open handle keeps it).
Read-only: nothing in the container is changed.
"""
import glob
import os
import sys
import time

root = '/proc/%s/root/tmp' % sys.argv[1]
end = time.time() + 60
f = None
while time.time() < end and f is None:
    for p in glob.glob(root + '/wsrep_recovery.*'):
        try:
            f = open(p, errors='replace')
            break
        except OSError:
            pass
    time.sleep(0.02)
if f is None:
    open(sys.argv[2], 'w').write('no wsrep_recovery file seen within 60 s\n')
    sys.exit(0)
name = os.path.basename(f.name)
while time.time() < end and os.path.exists(f.name):
    time.sleep(0.1)
with open(sys.argv[2], 'w') as out:
    out.write('# /tmp/%s, read through an open handle after mysqld_safe deleted it\n' % name)
    out.write(f.read())
