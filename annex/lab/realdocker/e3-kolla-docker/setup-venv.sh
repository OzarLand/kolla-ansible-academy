#!/bin/bash
# Create the e3 venv: Ansible 2.9.27 and docker SDK 4.4.4 as in the study's venv, but requests 2.23.0 / urllib3
# 1.25.8 (Ussuri upper-constraints). docker SDK 4.4.4 cannot talk to the daemon with requests 2.32
# ("Not supported URL scheme http+docker"), which is what the shared venv has. Also installs the e3 compat shim
# (compat/e3_docker_compat.py: HostConfig.KernelMemory, see that file) through a .pth file. Idempotent.
set -euo pipefail
source "$(dirname "$0")/lib.sh"
pth() { printf '%s\nimport e3_docker_compat\n' "$E3/compat" > "$("$E3_VENV/bin/python" -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')/e3_docker_compat.pth"; }
if [ -x "$E3_VENV/bin/ansible-playbook" ] && "$E3_VENV/bin/python" -c 'import requests,docker; assert requests.__version__=="2.23.0"'; then
  pth; exit 0
fi
PY=${E3_PYTHON:-$(uv python find 3.8)}
uv venv --python "$PY" "$E3_VENV"
SSL_CERT_FILE=${SSL_CERT_FILE:-/root/.ccr/ca-bundle.crt} uv pip install --python "$E3_VENV/bin/python" \
  ansible==2.9.27 docker==4.4.4 requests==2.23.0 urllib3==1.25.8 idna==2.9 chardet==3.0.4 certifi \
  Jinja2==3.0.3 MarkupSafe==2.0.1 PyYAML==5.3.1
pth
