#!/usr/bin/python
# LAB STUB of kolla-ansible's kolla_docker module. Emulates the decision logic
# of ansible/library/kolla_docker.py (ussuri-eol) against a JSON "container
# state" per host instead of a Docker daemon, and logs every action.
from ansible.module_utils.basic import AnsibleModule
#@@COMMON@@

CONTAINER_CONFIG_DIR = '/var/lib/kolla/config_files'

def config_dir(volumes):
    for v in volumes or []:
        if not v:
            continue
        parts = v.split(':')
        if len(parts) >= 2 and parts[1].rstrip('/') == CONTAINER_CONFIG_DIR:
            return parts[0].rstrip('/')
    return None

def params_hash(p):
    keys = ['volumes', 'privileged', 'pid_mode', 'ipc_mode', 'dimensions',
            'environment', 'command', 'labels', 'cap_add', 'security_opt']
    d = {}
    for k in keys:
        v = p.get(k)
        if k == 'volumes' and v:
            v = [x for x in v if x]
        if k == 'environment' and isinstance(v, dict):
            v = {a: b for a, b in v.items()}
        d[k] = v
    return hashlib.sha256(json.dumps(d, sort_keys=True, default=str).encode()).hexdigest()[:16]

def main():
    m = AnsibleModule(argument_spec=dict(
        action=dict(required=True, type='str'),
        common_options=dict(type='dict', default={}),
        name=dict(type='str'), image=dict(type='str'),
        volumes=dict(type='list'), environment=dict(type='dict'),
        privileged=dict(type='bool', default=False), pid_mode=dict(type='str'),
        ipc_mode=dict(type='str'), dimensions=dict(type='dict', default={}),
        command=dict(type='str'), detach=dict(type='bool', default=True),
        labels=dict(type='dict', default={}), restart_policy=dict(type='str'),
        restart_retries=dict(type='int'), remove_on_exit=dict(type='bool', default=True),
        state=dict(type='str', default='running'), graceful_timeout=dict(type='int'),
        auth_email=dict(type='str'), auth_password=dict(type='str', no_log=True),
        auth_registry=dict(type='str'), auth_username=dict(type='str'),
        tls_verify=dict(type='bool'), tls_cert=dict(type='str'), tls_key=dict(type='str'),
        tls_cacert=dict(type='str'), volumes_from=dict(type='list'),
        cap_add=dict(type='list'), security_opt=dict(type='list'),
        client_timeout=dict(type='int'), ignore_missing=dict(type='bool', default=False),
        api_version=dict(type='str'), tty=dict(type='bool', default=False),
    ), supports_check_mode=False)
    p = dict(m.params)
    # emulate generate_module(): merge common_options
    co = p.pop('common_options') or {}
    env = dict((co.get('environment') or {}))
    env.update(p.get('environment') or {})
    p['environment'] = env
    for k, v in co.items():
        if k != 'environment' and p.get(k) is None:
            p[k] = v
    action = p['action']
    name = p.get('name')
    image = p.get('image')
    res = {'changed': False, 'result': False}

    def mutate(st):
        st.setdefault('containers', {})
        st.setdefault('images', {})
        st.setdefault('volumes', [])
        c = st['containers'].get(name) if name else None
        cdir = config_dir(p.get('volumes'))
        cur_cfg = dir_hash(cdir)

        def local_digest(img):
            return st['images'].get(img)

        def pull(img):
            new = image_digest(img)
            old = st['images'].get(img)
            st['images'][img] = new
            log_event('kolla_docker', action='pull_image', image=img,
                      changed=(old != new), detail='downloaded' if old != new else 'up-to-date')
            return old != new

        def norm_mode(v):
            return v if v else None

        def attrs():
            return dict(image=image, digest=local_digest(image),
                        volumes=sorted(x.replace(LAB_RUN, '@RUN') for x in (p.get('volumes') or []) if x),
                        privileged=bool(p.get('privileged')),
                        pid_mode=norm_mode(p.get('pid_mode')), ipc_mode=norm_mode(p.get('ipc_mode')),
                        env=dict(p.get('environment') or {}), dimensions=p.get('dimensions') or {},
                        command=p.get('command'), labels=p.get('labels') or {})

        def differs(c):
            # mirrors kolla_docker.check_container_differs() (ussuri-eol)
            if c is None:
                return ['missing']
            r = []
            if c.get('image') != image:
                r.append('image-name')
            elif local_digest(image) and c.get('digest') != local_digest(image):
                r.append('image-digest')
            new_ipc = norm_mode(p.get('ipc_mode'))
            if new_ipc is not None and new_ipc != c.get('ipc_mode'):
                r.append('ipc_mode')
            if norm_mode(p.get('pid_mode')) != c.get('pid_mode'):
                r.append('pid_mode')
            if bool(p.get('privileged')) != c.get('privileged'):
                r.append('privileged')
            if sorted(x.replace(LAB_RUN, '@RUN') for x in (p.get('volumes') or []) if x) != c.get('volumes'):
                r.append('volumes')
            for k, v in (p.get('environment') or {}).items():
                if (c.get('env') or {}).get(k, object()) != v:
                    r.append('environment'); break
            if (p.get('dimensions') or {}) != (c.get('dimensions') or {}):
                r.append('dimensions')
            if p.get('command') is not None and p.get('command') != c.get('command'):
                r.append('command')
            if (p.get('labels') or {}) != (c.get('labels') or {}):
                r.append('labels')
            if c.get('state') != 'running':
                r.append('state')
            return r

        def create(reason):
            if not local_digest(image):
                pull(image)
            a = attrs()
            a.update(config=cur_cfg, cfgdir=cdir, state='running')
            st['containers'][name] = a
            log_event('kolla_docker', action=reason, name=name, image=image)

        if action == 'pull_image':
            res['changed'] = pull(image)
        elif action == 'ensure_image':
            if not local_digest(image):
                res['changed'] = pull(image)
        elif action == 'compare_image':
            res['changed'] = bool(c is None or c.get('image') != image or
                                  c.get('digest') != image_digest(image))
        elif action == 'compare_container':
            why = differs(c)
            if not why and c.get('config') != cur_cfg:
                why = ['config-drift(kolla_set_configs --check)']
            res['changed'] = bool(why)
            log_event('kolla_docker', action='compare_container', name=name,
                      changed=bool(why), why=why)
        elif action == 'recreate_or_restart_container':
            res['changed'] = True
            strategy = (p.get('environment') or {}).get('KOLLA_CONFIG_STRATEGY')
            if c is None:
                create('create+start')
            else:
                why = differs(c)
                if strategy == 'COPY_ONCE' or why:
                    create('RECREATE')
                    log_event('kolla_docker', action='recreate-reason', name=name, why=why)
                else:
                    c['config'] = cur_cfg
                    c['state'] = 'running'
                    log_event('kolla_docker', action='RESTART', name=name, image=image)
        elif action == 'start_container':
            if not p.get('detach', True):
                # one-shot bootstrap container
                log_event('kolla_docker', action='run-oneshot', name=name, image=image,
                          command=p.get('command'), env=sorted((p.get('environment') or {}).keys()))
                res['changed'] = True
                res['rc'] = 0
                res['stdout'] = oneshot_stdout(st, name, p, cdir)
                res['stderr'] = ''
                st.setdefault('oneshots', {})[name] = st.get('oneshots', {}).get(name, 0) + 1
            else:
                why = differs(c)
                if why:
                    create('start(%s)' % ','.join(why))
                    res['changed'] = True
        elif action == 'stop_container':
            if c is None:
                if not p.get('ignore_missing'):
                    return ('fail', 'No such container: %s to stop' % name)
            elif c.get('state') != 'exited':
                c['state'] = 'exited'
                res['changed'] = True
                log_event('kolla_docker', action='STOP', name=name)
        elif action == 'restart_container':
            res['changed'] = True
            if c:
                c['config'] = cur_cfg
            log_event('kolla_docker', action='RESTART', name=name)
        elif action in ('remove_container', 'stop_and_remove_container'):
            if c:
                del st['containers'][name]
                res['changed'] = True
                log_event('kolla_docker', action='REMOVE', name=name)
        elif action == 'create_volume':
            if name not in st['volumes']:
                st['volumes'].append(name)
                res['changed'] = True
        elif action == 'remove_volume':
            if name in st['volumes']:
                st['volumes'].remove(name)
                res['changed'] = True
        elif action == 'remove_image':
            if image in st['images']:
                del st['images'][image]
                res['changed'] = True
        elif action == 'get_container_env':
            return ('exit', {'KOLLA_CONFIG_STRATEGY': 'COPY_ALWAYS'})
        elif action == 'get_container_state':
            return ('exit', {'Running': bool(c), 'Status': 'running' if c else 'missing'})
        return None

    out = state(mutate)
    if out and out[0] == 'fail':
        m.fail_json(msg=out[1])
    if out and out[0] == 'exit':
        m.exit_json(changed=False, **out[1])
    m.exit_json(**res)

def ini_get(path, section, key):
    try:
        sec = None
        for line in open(path):
            line = line.strip()
            if line.startswith('[') and line.endswith(']'):
                sec = line[1:-1]
            elif sec == section and '=' in line:
                k, v = line.split('=', 1)
                if k.strip() == key:
                    return v.strip()
    except Exception:
        return None

def oneshot_stdout(st, name, p, cdir):
    cmd = p.get('command') or ''
    if 'map_cell0' in cmd:
        if st.get('oneshots', {}).get(name):
            return 'Cell0 is already setup'
        return ''
    if 'list_cells' in cmd:
        cells = registry_cells()
        lines = ['+-------+------+---------------+---------------------+----------+']
        for cname, c in cells.items():
            lines.append('| %s | %s | %s | %s | False |' % (cname, c['uuid'], c['mq'], c['db']))
        return '\n'.join(lines)
    if 'create_cell' in cmd or 'update_cell' in cmd:
        conf = os.path.join(cdir or '', 'nova.conf')
        mq = ini_get(conf, 'DEFAULT', 'transport_url') or 'rabbit://x'
        db = ini_get(conf, 'database', 'connection') or 'mysql://x'
        def upd(cells):
            c = cells.setdefault('', {'uuid': '68a3f49e-27ec-422f-9e2e-2a4e5dc8291b'})
            c['mq'] = mq.replace(' ', '')
            c['db'] = db.replace(' ', '')
        _locked_rw(os.path.join(LAB_RUN, 'cells.json'), upd)
        log_event('kolla_docker', action='cell-registered', name=name, detail=cmd.split('&&')[-1].strip())
        return ''
    return ''

def registry_cells():
    try:
        return json.load(open(os.path.join(LAB_RUN, 'cells.json')))
    except Exception:
        return {}

if __name__ == '__main__':
    main()
