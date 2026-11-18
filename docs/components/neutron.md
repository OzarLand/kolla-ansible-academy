---
title: Neutron
---

# Neutron

<!-- TODO editorial: intro -->

## Where to look

- **Dependencies:** [Component dependencies §3](dependencies.md#3-control-plane-services), [Component dependencies
  §4](dependencies.md#4-networking-components-ml2ovs-default-ml2ovn-optional)
- **Image side:** [Kolla images
  §4](../concepts/kolla-images.md#4-one-shot-containers-what-the-environment-variables-run) (row `neutron-server`),
  [Kolla images §5](../concepts/kolla-images.md#5-per-image-start-behaviour), [Kolla images
  §5.3](../concepts/kolla-images.md#53-neutron-l3-agent-the-wrapper)
- **Also:** [Reconfigure Neutron](../operations/reconfigure-neutron.md); handlers: [Tags
  §5](../risk/tags.md#5-role--handler-map-core-services)
- **What the tag executes (`neutron`):** [Tags §3](../risk/tags.md#3-what-a-tag-really-executes-master-table) and [Tags
  §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), rows `neutron`
- **Scenario:** [Reconfigure Neutron](../operations/reconfigure-neutron.md)
- **Command:** [Reconfigure Neutron §1.1](../operations/reconfigure-neutron.md#11-neutron)
- **Risks:** [R5](../risk/risk-register.md#r5), [R6](../risk/risk-register.md#r6), [R7](../risk/risk-register.md#r7);
  membership changes: [R3](../risk/risk-register.md#r3), [R4](../risk/risk-register.md#r4)

## Service card

<!-- BEGIN GENERATED: tools/service_cards.py neutron -->

| Item | Value |
|---|---|
| Play | site.yml:761 |
| Tags | neutron |
| Play host patterns | neutron-server, neutron-dhcp-agent, neutron-l3-agent, ironic-neutron-agent, neutron-metadata-agent, neutron-ovn-metadata-agent, neutron-metering-agent, neutron-bgp-dragent, neutron-infoblox-ipam-agent, compute, manila-share |
| Node types in play (example inventory) | compute, control, network |
| Node types running its containers | compute, control, network |
| Containers | `neutron_server`, `neutron_openvswitch_agent`, `neutron_openvswitch_agent_xenapi`, `neutron_linuxbridge_agent`, `neutron_dhcp_agent`, `neutron_l3_agent`, `neutron_sriov_agent`, `neutron_metadata_agent`, `neutron_ovn_metadata_agent`, `neutron_bgp_dragent`, `neutron_infoblox_ipam_agent`, `neutron_metering_agent`, `ironic_neutron_agent` |
| deploy/reconfigure flow (`tasks/deploy.yml`) | register → clone (if) → config-host → config → check-containers → config-neutron-fake (if) → bootstrap → flush handlers |
| Task files | bootstrap.yml, bootstrap_service.yml, check-containers.yml, check.yml, clone.yml, config-host.yml, config-neutron-fake.yml, config.yml, copy-certs.yml, deploy-containers.yml, deploy.yml, legacy_upgrade.yml, loadbalancer.yml, main.yml, precheck.yml, pull.yml, reconfigure.yml, register.yml, rolling_upgrade.yml, stop.yml, upgrade.yml |
| Templates | `bgp_dragent.ini.j2`, `dhcp_agent.ini.j2`, `dnsmasq.conf.j2`, `fwaas_driver.ini.j2`, `ironic-neutron-agent.json.j2`, `ironic_neutron_agent.ini.j2`, `l3_agent.ini.j2`, `linuxbridge_agent.ini.j2`, `metadata_agent.ini.j2`, `metering_agent.ini.j2`, `ml2_conf.ini.j2`, `neutron-bgp-dragent.json.j2`, `neutron-dhcp-agent.json.j2`, `neutron-infoblox-ipam-agent.json.j2`, `neutron-l3-agent-wrapper.sh.j2`, `neutron-l3-agent.json.j2`, `neutron-linuxbridge-agent.json.j2`, `neutron-metadata-agent.json.j2`, `neutron-metering-agent.json.j2`, `neutron-openvswitch-agent-xenapi.json.j2`, `neutron-openvswitch-agent.json.j2`, `neutron-ovn-metadata-agent.json.j2`, `neutron-server.json.j2`, `neutron-sriov-agent.json.j2`, `neutron.conf.j2` … (+6) |
| Handlers (definition order) | Restart neutron-server container; Restart neutron-openvswitch-agent container; Restart neutron-openvswitch-agent-xenapi container; Restart fake neutron-openvswitch-agent container; Restart neutron-linuxbridge-agent container; Restart neutron-dhcp-agent container; Restart neutron-l3-agent container; Restart neutron-sriov-agent container; Restart neutron-metadata-agent container; Restart neutron-ovn-metadata-agent container; Restart neutron-bgp-dragent container; Restart neutron-infoblox-ipam-agent container; Restart neutron-metering-agent container; Restart ironic-neutron-agent container |
| Key variables | `enable_neutron`, `neutron_plugin_agent`, `enable_neutron_dvr`, `enable_neutron_agent_ha`, `enable_neutron_provider_networks`, `neutron_enable_rolling_upgrade` |
| Role dependencies | `common` (meta) |

<!-- END GENERATED -->

<!-- TODO editorial: related -->
