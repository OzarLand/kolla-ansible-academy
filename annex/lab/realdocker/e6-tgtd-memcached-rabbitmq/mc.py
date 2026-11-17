#!/usr/bin/env python3
"""Minimal memcached text-protocol client.

Usage: mc.py HOST PORT set KEY=VALUE...   store each key (flags 0, no expiry)
       mc.py HOST PORT get KEY...         one 'get' per key, print the raw reply
       mc.py HOST PORT stats              print pid, uptime, curr_items, total_items, version
"""
import socket
import sys

host, port, cmd, args = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4:]
s = socket.create_connection((host, port), timeout=5)
f = s.makefile('rwb')


def send(line):
    f.write(line.encode() + b'\r\n')
    f.flush()


def read_until(*ends):
    lines = []
    while True:
        line = f.readline().decode().rstrip('\r\n')
        lines.append(line)
        if line in ends or line.startswith(('ERROR', 'CLIENT_ERROR', 'SERVER_ERROR')):
            return lines


if cmd == 'set':
    for kv in args:
        k, v = kv.split('=', 1)
        send('set %s 0 0 %d' % (k, len(v)))
        send(v)
        print('set %s=%s -> %s' % (k, v, read_until('STORED', 'NOT_STORED')[-1]))
elif cmd == 'get':
    for k in args:
        send('get %s' % k)
        print('get %s -> %s' % (k, ' | '.join(read_until('END'))))
elif cmd == 'stats':
    send('stats')
    keep = ('pid', 'uptime', 'curr_items', 'total_items', 'version')
    for line in read_until('END'):
        p = line.split()
        if len(p) == 3 and p[1] in keep:
            print('STAT %s %s' % (p[1], p[2]))
send('quit')
