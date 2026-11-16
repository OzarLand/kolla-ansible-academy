#!/usr/bin/python
# LAB STUB of kolla_container_facts: answers from the lab container state.
from ansible.module_utils.basic import AnsibleModule
#@@COMMON@@
def main():
    m = AnsibleModule(argument_spec=dict(name=dict(type='list', default=[]), api_version=dict()))
    names = m.params['name'] or []
    st = state(lambda s: dict(s))
    res = dict(changed=False, _containers=[])
    for n, c in (st.get('containers') or {}).items():
        if c.get('state') != 'running':
            continue
        if names and n not in names:
            continue
        d = {'Names': ['/' + n], 'Image': c['image'], 'State': 'running'}
        res['_containers'].append(d); res[n] = d
    m.exit_json(**res)
if __name__ == '__main__':
    main()
