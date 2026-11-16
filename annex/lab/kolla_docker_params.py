"""Feed the REAL ussuri-eol kolla_docker.generate_module() the arguments a
Kolla handler sends (common_options = docker_common_options with the documented
defaults) and print the effective parameters."""
import json, sys
sys.path.insert(0, sys.argv[1])          # .../ansible/library
from ansible.module_utils import basic
from ansible.module_utils._text import to_bytes
args = {"ANSIBLE_MODULE_ARGS": {
    "action": "recreate_or_restart_container", "name": "nova_compute",
    "image": "kolla/centos-binary-nova-compute:ussuri",
    "common_options": {"auth_email": None, "auth_password": None, "auth_registry": None,
                       "auth_username": None,
                       "environment": {"KOLLA_CONFIG_STRATEGY": "COPY_ALWAYS"},
                       "restart_policy": "unless-stopped", "restart_retries": "10",
                       "graceful_timeout": "60", "client_timeout": "300"}}}
basic._ANSIBLE_ARGS = to_bytes(json.dumps(args))
import kolla_docker
m = kolla_docker.generate_module()
for k in ("graceful_timeout", "client_timeout", "restart_policy", "restart_retries", "environment"):
    print("%-17s common_options=%-14r -> effective=%r" % (k, args["ANSIBLE_MODULE_ARGS"]["common_options"].get(k), m.params.get(k)))
