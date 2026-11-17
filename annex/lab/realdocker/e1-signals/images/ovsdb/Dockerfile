# e1-ovsdb:ussuri - openvswitch-db-server start path with stand-ins (test d).
# Real kolla start scripts (openvswitch-base and openvswitch-db-server extend_start.sh, copied by run.sh);
# /usr/sbin/ovsdb-server is the signal-logging stand-in and /usr/bin/ovsdb-tool a stub (e5 tests real OVS).
FROM reallab/base:ussuri
COPY e1-sigsvc /usr/sbin/ovsdb-server
COPY ovsdb-tool /usr/bin/ovsdb-tool
COPY kolla/openvswitch-base-extend_start.sh /usr/local/bin/kolla_extend_start
COPY kolla/openvswitch-db-server-extend_start.sh /usr/local/bin/kolla_openvswitch_extend_start
RUN chmod 755 /usr/sbin/ovsdb-server /usr/bin/ovsdb-tool /usr/local/bin/kolla_extend_start \
              /usr/local/bin/kolla_openvswitch_extend_start
