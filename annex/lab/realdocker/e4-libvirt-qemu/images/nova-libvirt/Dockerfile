# e4: nova-libvirt image derived from reallab/base:ussuri, following kolla ussuri-eol (9107c5f)
# docker/base/Dockerfile.j2 (users) and docker/nova/nova-libvirt/Dockerfile.j2 (packages, network cleanup,
# extend_start.sh). Packages are bionic's (libvirt 4.0.0, QEMU 2.11), not the Ubuntu Cloud Archive ussuri pocket
# (libvirt 6.0, QEMU 4.2) that the Ussuri image used: UCA is not reachable from this lab.
FROM reallab/base:ussuri
# Kolla users (kolla/common/config.py: qemu 42427, nova 42436, libvirt 42473), created before any package as the
# base Dockerfile.j2 users loop does, then configure_user(name='nova', groups='qemu') from macros.j2.
RUN groupadd --force --gid 42427 qemu && useradd -l -M --shell /usr/sbin/nologin --uid 42427 --gid 42427 qemu \
    && groupadd --force --gid 42436 nova && useradd -l -M --shell /usr/sbin/nologin --uid 42436 --gid 42436 nova \
    && groupadd --force --gid 42473 libvirt && useradd -l -M --shell /usr/sbin/nologin --uid 42473 --gid 42473 libvirt \
    && usermod --append --home /var/lib/nova --groups kolla nova \
    && usermod --append --groups qemu nova \
    && mkdir -p /var/lib/nova && chown -R 42436:42436 /var/lib/nova
# Subset of the Ussuri deb package list that matters for libvirtd + QEMU (TCG). Left out: ceph-common,
# python3-ceph*, openvswitch-switch, xen-utils, trousers, ovmf, pm-utils (not on the stop/reconnect path).
# libsasl2-modules is added because SCRAM-SHA-1 (libvirt_sasl_mech_list default) lives there.
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get -y install --no-install-recommends \
      libvirt-clients libvirt-daemon-system qemu-system-x86 qemu-kvm qemu-block-extra \
      sasl2-bin libsasl2-modules libsasl2-modules-gssapi-mit ebtables dmidecode kmod \
    && rm -rf /var/lib/apt/lists/*
RUN rm -f /etc/libvirt/qemu/networks/default.xml /etc/libvirt/qemu/networks/autostart/default.xml
COPY extend_start.sh /usr/local/bin/kolla_extend_start
RUN chmod 755 /usr/local/bin/kolla_extend_start
