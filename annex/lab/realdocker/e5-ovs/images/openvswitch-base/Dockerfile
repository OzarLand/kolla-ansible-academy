# kolla ussuri-eol docker/openvswitch/openvswitch-base/Dockerfile.j2, rendered for base_package_type 'deb', on the
# lab base. The package list is kolla's (openvswitch-switch, python3-openvswitch, python3-netifaces, tcpdump) plus
# kmod, which kolla's own base image installs (kolla docker/base/Dockerfile.j2 base_apt_packages) and the lab base
# does not. Packages come from bionic (OVS 2.9.x); Ussuri's Ubuntu images took OVS 2.13 from the Ubuntu Cloud
# Archive bionic-updates/ussuri pocket (kolla docker/base/sources.list.ubuntu:13), unreachable from this lab.
FROM reallab/base:ussuri
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get -y install --no-install-recommends \
      openvswitch-switch python3-openvswitch python3-netifaces tcpdump kmod \
    && apt-get clean && rm -rf /var/lib/apt/lists/*
COPY kolla/openvswitch-base-extend_start.sh /usr/local/bin/kolla_extend_start
RUN mv /usr/sbin/tcpdump /usr/bin/tcpdump \
    && touch /usr/local/bin/kolla_openvswitch_extend_start \
    && chmod 755 /usr/local/bin/kolla_extend_start /usr/local/bin/kolla_openvswitch_extend_start
