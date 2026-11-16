#!/bin/bash
# Scale experiments (run after scenarios.sh). Timings are LAB timings
# (local connection, stub modules, 4 vCPU deploy host) - see annex/lab/README.md.
S=${KOLLA_LAB_ROOT:-$HOME/kolla-lab}
L=$S/lab
. $S/venv-ansible/bin/activate
cd "$(dirname "$0")"
until grep -q ALLDONE $L/scenarios.log; do sleep 20; done
R="python3 run_lab.py --quiet"
$R --run sc-deploy-10 --computes 10 --action deploy
$R --run sc-reconf-nova-10 --computes 10 --state-from sc-deploy-10 --action reconfigure --tags nova
$R --run sc-deploy-30 --computes 30 --action deploy
$R --run sc-reconf-nova-30 --computes 30 --state-from sc-deploy-30 --action reconfigure --tags nova
$R --run sc-reconf-nova-30-computeconf --computes 30 --state-from sc-deploy-30 --action reconfigure --tags nova --custom-config $L/cc/nova-compute
$R --run sc-reconf-nova-30-forks5 --computes 30 --state-from sc-deploy-30 --action reconfigure --tags nova --forks 5
$R --run sc-reconf-nova-30-forks50 --computes 30 --state-from sc-deploy-30 --action reconfigure --tags nova --forks 50
$R --run sc-reconf-nova-30-limit1 --computes 30 --state-from sc-deploy-30 --action reconfigure --tags nova --limit compute001
echo SCALEDONE
