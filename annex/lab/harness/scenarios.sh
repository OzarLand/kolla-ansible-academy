#!/bin/bash
# Day-2 scenario batch. Every scenario starts from the state of t0-deploy
# (3 controllers, 2 network, 3 compute, 1 storage, 1 monitoring) unless noted.
S=${KOLLA_LAB_ROOT:-$HOME/kolla-lab}
L=$S/lab
. $S/venv-ansible/bin/activate
cd "$(dirname "$0")"
R="python3 run_lab.py --quiet"
B="--state-from t0-deploy --computes 3"
$R --run s01-reconf-nova-nochange   $B --action reconfigure --tags nova
$R --run s02-reconf-nova-globalconf $B --action reconfigure --tags nova --custom-config $L/cc/nova-global
$R --run s03-reconf-nova-computeconf $B --action reconfigure --tags nova --custom-config $L/cc/nova-compute
$R --run s04-reconf-nova-schedconf  $B --action reconfigure --tags nova --custom-config $L/cc/nova-scheduler
$R --run s05-reconf-neutron-ml2     $B --action reconfigure --tags neutron --custom-config $L/cc/neutron-ml2
$R --run s06-reconf-neutron-global  $B --action reconfigure --tags neutron --custom-config $L/cc/neutron-global
$R --run s07-reconf-nova-enable-barbican $B --action reconfigure --tags nova --globals $L/etc/kolla/globals-barbican.yml
$R --run s08-reconf-common-enable-barbican $B --action reconfigure --tags common --globals $L/etc/kolla/globals-barbican.yml
$R --run s09a-deploy-nova-newdigest-nopull $B --action deploy --tags nova --registry $L/reg-nova-compute.json
$R --run s09b-pull-nova-newdigest  $B --action pull --tags nova --registry $L/reg-nova-compute.json
$R --run s09c-deploy-nova-after-pull --state-from s09b-pull-nova-newdigest --computes 3 --action deploy --tags nova
$R --run s10-pull-all-newtag       $B --action pull --globals $L/etc/kolla/globals-newtag.yml
$R --run s11-deploy-all-newtag     --state-from s10-pull-all-newtag --computes 3 --action deploy --globals $L/etc/kolla/globals-newtag.yml
$R --run s12-add-controller-reconf-nova-neutron $B --controllers 4 --action reconfigure --tags nova,neutron
$R --run s13-limit-compute-reconf-nova $B --action reconfigure --tags nova --limit compute001 --custom-config $L/cc/nova-compute
$R --run s14-genconfig-nova        $B --action config --tags nova --custom-config $L/cc/nova-global
$R --run s15-deploycontainers-compute001 --state-from s14-genconfig-nova --computes 3 --action deploy-containers --tags nova --limit compute001 --custom-config $L/cc/nova-global
$R --run s16-reconf-nova-serial1   $B --action reconfigure --tags nova --custom-config $L/cc/nova-global --extra kolla_serial=1
$R --run s17-add-compute004-limit  --state-from t0-deploy --computes 4 --action deploy --limit compute004
$R --run s18-reconfigure-all-nochange $B --action reconfigure
$R --run s19-reconf-haproxy-nochange $B --action reconfigure --tags haproxy
echo ALLDONE
