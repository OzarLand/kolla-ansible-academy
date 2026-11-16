#!/usr/bin/python
import base64
from ansible.module_utils.basic import AnsibleModule
def main():
    m = AnsibleModule(argument_spec=dict(src=dict()), bypass_checks=True)
    m.exit_json(changed=False, content=base64.b64encode(b'CentOS Linux release 8.2.2004 (Core)\n').decode(), source=m.params.get('src'), encoding='base64')
if __name__ == '__main__':
    main()
