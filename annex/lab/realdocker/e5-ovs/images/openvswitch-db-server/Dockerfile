# kolla ussuri-eol docker/openvswitch/openvswitch-db-server/Dockerfile.j2 (unchanged steps).
FROM e5-openvswitch-base:ussuri
COPY kolla/ovs_ensure_configured.sh /usr/local/bin/kolla_ensure_openvswitch_configured
COPY kolla/openvswitch-db-server-extend_start.sh /usr/local/bin/kolla_openvswitch_extend_start
RUN chmod 755 /usr/local/bin/kolla_ensure_openvswitch_configured \
              /usr/local/bin/kolla_openvswitch_extend_start
