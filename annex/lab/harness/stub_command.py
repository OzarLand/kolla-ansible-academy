#!/usr/bin/python
# LAB STUB of the builtin command/shell module: never executes anything,
# logs the command line and returns canned output for the few commands whose
# output kolla-ansible parses.
from ansible.module_utils.basic import AnsibleModule
#@@COMMON@@
def main():
    m = AnsibleModule(argument_spec=dict(_raw_params=dict(), _uses_shell=dict(type='bool', default=False),
        argv=dict(type='list'), chdir=dict(type='path'), executable=dict(), creates=dict(type='path'),
        removes=dict(type='path'), warn=dict(type='bool', default=True), stdin=dict(required=False),
        stdin_add_newline=dict(type='bool', default=True), strip_empty_ends=dict(type='bool', default=True)))
    cmd = m.params['_raw_params'] or ' '.join(m.params['argv'] or [])
    out = ''
    if 'compute service list' in cmd:
        try:
            hosts = json.load(open(os.path.join(LAB_RUN, 'computes.json')))
        except Exception:
            hosts = []
        out = json.dumps([{'Host': h} for h in hosts])
    elif 'fernet_rotate_cron_generator.py' in cmd:
        # pure local helper script shipped in the keystone role: run it for real
        import subprocess, shlex
        out = subprocess.check_output(shlex.split(cmd)).decode()
    elif 'kolla_keystone_bootstrap' in cmd:
        out = json.dumps({'changed': False, 'failed': False})
    elif 'wsrep_local_state_comment' in cmd:
        out = 'wsrep_local_state_comment\tSynced'
    log_event('command', action='shell' if m.params['_uses_shell'] else 'command',
              cmd=re.sub(r'--os-password \S+', '--os-password ***', cmd)[:300])
    m.exit_json(changed=True, rc=0, stdout=out, stderr='', cmd=cmd, stdout_lines=out.splitlines())
if __name__ == '__main__':
    main()
