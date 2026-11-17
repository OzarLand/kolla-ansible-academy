ovs-ofctl add-tlv-map e5-br-sec ''
ovs-ofctl -O OpenFlow13 add-groups e5-br-sec               "/run/openvswitch/ovs-save.XXXX/e5-br-sec.groups.dump" 
ovs-ofctl -O OpenFlow13 replace-flows e5-br-sec               "/run/openvswitch/ovs-save.XXXX/e5-br-sec.flows.dump" 
ovs-ofctl add-tlv-map e5-br-std ''
ovs-ofctl -O OpenFlow14 add-groups e5-br-std               "/run/openvswitch/ovs-save.XXXX/e5-br-std.groups.dump"  --bundle
ovs-ofctl -O OpenFlow14 replace-flows e5-br-std               "/run/openvswitch/ovs-save.XXXX/e5-br-std.flows.dump"  --bundle
rm -rf "/run/openvswitch/ovs-save.XXXX"
