#!/usr/bin/env python3
import json, sys, os, collections
S=os.environ.get('KOLLA_LAB_ROOT', os.path.expanduser('~/kolla-lab')) + '/lab/runs/'
run=sys.argv[1]; mode=sys.argv[2] if len(sys.argv)>2 else 'summary'
R=S+run
trace=[json.loads(l) for l in open(R+'/trace.jsonl')]
events=[json.loads(l) for l in open(R+'/events.jsonl')] if os.path.exists(R+'/events.jsonl') else []
res=[t for t in trace if t['kind']=='result']
res_json=json.load(open(R+'/result.json'))
def role(h):
    import re
    return re.sub(r'\d+$','',h)
if mode in ('summary','all'):
    print('run', run, 'rc', res_json['rc'], 'wall', res_json['seconds'], 's')
    per=collections.defaultdict(collections.Counter)
    for r in res:
        per[r['host']][r['status']]+=1
        if r['changed']: per[r['host']]['changed']+=1
        if r['handler'] and r['status']!='skipped': per[r['host']]['handlers_run']+=1
    print('%-12s %6s %6s %8s %8s %8s'%('host','ok','skip','changed','handlers','total'))
    for h in sorted(per):
        c=per[h]; print('%-12s %6d %6d %8d %8d %8d'%(h,c['ok'],c['skipped'],c['changed'],c['handlers_run'],c['ok']+c['skipped']+c['failed']))
    tot=collections.Counter(r['status'] for r in res)
    print('TOTAL task-host results:', dict(tot), 'sum', len(res))
if mode in ('containers','all'):
    act=[e for e in events if e['module']=='kolla_docker' and e['action'] in ('RESTART','RECREATE','create+start','STOP','REMOVE') or (e['module']=='kolla_docker' and e['action'].startswith('start('))]
    by=collections.defaultdict(lambda: collections.defaultdict(list))
    for e in act:
        by[e['action']][e['name']].append(e['host'])
    for a in sorted(by):
        print('==', a)
        for n in sorted(by[a]):
            hs=sorted(by[a][n]); print('   %-28s %3d hosts: %s'%(n,len(hs),' '.join(hs) if len(hs)<=12 else ' '.join(hs[:6])+' ... '+' '.join(hs[-3:])))
    one=[e for e in events if e['module']=='kolla_docker' and e['action']=='run-oneshot']
    if one:
        print('== one-shot (bootstrap/DB) containers')
        for e in one: print('   %-30s on %-10s %s'%(e['name'],e['host'],(e.get('command') or ' '.join(e.get('env') or []))[:90]))
    pulls=[e for e in events if e['action']=='pull_image']
    if pulls:
        c=collections.Counter((e['host']) for e in pulls if e['changed'])
        print('== image downloads (changed pulls):', sum(c.values()), 'across', len(c), 'hosts')
    other=collections.Counter((e['module'],e['action']) for e in events if e['module'] not in ('kolla_docker','setup'))
    print('== other stubbed ops:', dict(other))
if mode=='plays':
    plays=collections.OrderedDict()
    for t in trace:
        if t['kind']=='play': plays.setdefault(t['play'],collections.Counter())
        if t['kind']=='result':
            plays.setdefault(t['play'],collections.Counter())[t['status']]+=1
    for p,c in plays.items():
        if sum(c.values()): print('%-60s %s'%(p[:60],dict(c)))
if mode=='handlers':
    hs=collections.defaultdict(set)
    for r in res:
        if r['handler'] and r['status']!='skipped': hs[r['task']].add(r['host'])
    for k,v in sorted(hs.items()): print('%-55s %3d %s'%(k,len(v),' '.join(sorted(v)[:8])))
if mode=='changedtasks':
    ch=collections.defaultdict(set)
    for r in res:
        if r['changed'] and not r['handler']: ch[(r['play'][:28],r['task'])].add(r['host'])
    for k,v in sorted(ch.items()): print('%-30s %-55s %3d %s'%(k[0],k[1][:55],len(v),' '.join(sorted(v)[:6])))
if mode=='hosttasks':
    h=sys.argv[3]
    for r in res:
        if r['host']==h: print('%-8s %-7s %-28s %s'%(r['status'],'CHANGED' if r['changed'] else '',(r['role'] or '-')[:28], r['task'][:90]))
