#!/usr/bin/python
# LAB STUB of setup: synthesises facts for the simulated host named in LAB_HOST.
from ansible.module_utils.basic import AnsibleModule
#@@COMMON@@
def main():
    m = AnsibleModule(argument_spec=dict(filter=dict(), gather_subset=dict(type='list'), gather_timeout=dict(type='int'), fact_path=dict()), bypass_checks=True)
    idx = int(hashlib.sha256(HOST.encode()).hexdigest(), 16) % 60000 + 10
    a, b = divmod(idx, 250)
    ip0 = '10.0.%d.%d' % (a % 250, b + 2)
    ip1 = '10.1.%d.%d' % (a % 250, b + 2)
    f = {
        'ansible_hostname': HOST, 'ansible_nodename': HOST, 'ansible_fqdn': HOST,
        'ansible_os_family': 'RedHat', 'ansible_distribution': 'CentOS',
        'ansible_distribution_major_version': '8', 'ansible_distribution_version': '8.2',
        'ansible_architecture': 'x86_64', 'ansible_processor_vcpus': 32, 'ansible_memtotal_mb': 262144,
        'ansible_interfaces': ['eth0', 'eth1', 'lo'],
        'ansible_eth0': {'device': 'eth0', 'active': True, 'ipv4': {'address': ip0, 'netmask': '255.255.0.0'}},
        'ansible_eth1': {'device': 'eth1', 'active': True, 'ipv4': {'address': ip1, 'netmask': '255.255.0.0'}},
        'ansible_default_ipv4': {'address': ip0, 'interface': 'eth0'},
        'ansible_python': {'version': {'major': 3, 'minor': 6}}, 'ansible_python_version': '3.6.8',
        'ansible_service_mgr': 'systemd', 'ansible_kernel': '4.18.0',
    }
    log_event('setup', action='gather_facts')
    m.exit_json(changed=False, ansible_facts=f)
if __name__ == '__main__':
    main()
