#!/bin/bash
set -o errexit
# same shape as neutron-l3-agent-wrapper.sh.j2: last command run WITHOUT exec
/usr/local/bin/svc.sh
