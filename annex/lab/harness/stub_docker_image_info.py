#!/usr/bin/python
from ansible.module_utils.basic import AnsibleModule
#@@COMMON@@
def main():
    m = AnsibleModule(argument_spec=dict(name=dict(type='list')), bypass_checks=True)
    m.exit_json(changed=False, images=[{'ContainerConfig': {'Labels': {'fluentd_binary': 'td-agent', 'fluentd_version': '0.12'}}}])
if __name__ == '__main__':
    main()
