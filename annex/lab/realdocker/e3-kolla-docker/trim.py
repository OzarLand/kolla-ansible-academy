#!/usr/bin/env python3
"""Trim a recorded step (work/json/<step>.jsonl, one line per result from plugins/e3_record.py) to its decisive keys.

Kept per result: changed, failed, skipped, msg (long tracebacks are cut in the middle), rc, result, stdout, stderr,
cmd, the failed_when outcome, State keys of get_container_state, and from invocation.module_args (which kolla_docker
replaces with its MERGED parameters, common_options included) the keys listed in ARGS.
"""
import json
import sys

KEEP = ['changed', 'failed', 'skipped', 'skip_reason', 'msg', 'rc', 'result', 'cmd', 'stdout', 'stderr',
        'failed_when_result', 'Status', 'Running', 'ExitCode', 'KOLLA_CONFIG_STRATEGY', 'exception']
ARGS = ['action', 'name', 'image', 'graceful_timeout', 'client_timeout', 'restart_policy', 'restart_retries',
        'detach', 'remove_on_exit', 'labels', 'environment', 'volumes', 'api_version']


def cut(s, head=700, tail=900):
    if isinstance(s, str) and len(s) > head + tail + 20:
        return s[:head] + ' [... %d chars cut ...] ' % (len(s) - head - tail) + s[-tail:]
    return s


def trim(r):
    if not isinstance(r, dict):
        return r
    out = {}
    if 'item' in r:
        it = r['item']
        out['item'] = it.get('key', it) if isinstance(it, dict) else it
    for k in KEEP:
        if k in r:
            out[k] = cut(r[k]) if k in ('msg', 'exception') else r[k]
    args = (r.get('invocation') or {}).get('module_args')
    if args:
        out['module_args(effective)'] = {k: args[k] for k in ARGS if k in args}
    if 'results' in r:
        out['results'] = [trim(x) for x in r['results']]
    return out


out = []
with open(sys.argv[1]) as f:
    for line in f:
        rec = json.loads(line)
        out.append({'task': rec['task'], 'status': rec['status'], 'result': trim(rec['result'])})
print(json.dumps(out, indent=1))
