#!/usr/bin/python
# LAB STUB of kolla_toolbox: logs the ansible module that would be executed
# inside the kolla_toolbox container. First call per (module,args) = changed.
from ansible.module_utils.basic import AnsibleModule
#@@COMMON@@
def main():
    m = AnsibleModule(argument_spec=dict(module_name=dict(required=True), module_args=dict(type='raw'),
                      module_extra_vars=dict(type='raw'), api_version=dict(), timeout=dict(type='int'),
                      user=dict()), bypass_checks=True)
    key = m.params['module_name'] + ':' + hashlib.sha256(json.dumps(m.params.get('module_args'), sort_keys=True, default=str).encode()).hexdigest()[:12]
    def mut(st):
        seen = st.setdefault('toolbox', [])
        if key in seen:
            return False
        seen.append(key); return True
    changed = state(mut)
    log_event('kolla_toolbox', action=m.params['module_name'], changed=changed)
    m.exit_json(changed=changed, stdout='', stdout_lines=[])
if __name__ == '__main__':
    main()
