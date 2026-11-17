# e1-ovsvswitchd:ussuri - openvswitch-vswitchd start path with stand-ins (test d).
# Real kolla start scripts (openvswitch-base and openvswitch-vswitchd extend_start.sh, copied by run.sh);
# /usr/sbin/ovs-vswitchd is the signal-logging stand-in, /sbin/modprobe a logging stub (no openvswitch module here).
FROM reallab/base:ussuri
COPY e1-sigsvc /usr/sbin/ovs-vswitchd
COPY modprobe /sbin/modprobe
COPY kolla/openvswitch-base-extend_start.sh /usr/local/bin/kolla_extend_start
COPY kolla/openvswitch-vswitchd-extend_start.sh /usr/local/bin/kolla_openvswitch_extend_start
RUN chmod 755 /usr/sbin/ovs-vswitchd /sbin/modprobe /usr/local/bin/kolla_extend_start \
              /usr/local/bin/kolla_openvswitch_extend_start
