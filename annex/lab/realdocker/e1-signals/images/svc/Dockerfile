# e1-svc:ussuri - reallab/base:ussuri plus signal-logging stand-ins (tests a, b, c, g).
# kolla/ is filled by run.sh from the kolla ussuri-eol checkout (KOLLA_SRC).
FROM reallab/base:ussuri
# kolla's base image creates every service user up front with fixed ids (kolla/common/config.py:977-980);
# configure_user (kolla docker/macros.j2:45-59) adds it to group kolla.
RUN groupadd --force --gid 42435 neutron \
    && useradd -l -M --shell /usr/sbin/nologin --uid 42435 --gid 42435 neutron \
    && usermod --append --home /var/lib/neutron --groups kolla neutron \
    && mkdir -p /var/lib/neutron && chown -R 42435:42435 /var/lib/neutron
COPY e1-sigsvc /usr/local/bin/e1-sigsvc
RUN chmod 755 /usr/local/bin/e1-sigsvc \
    && for n in e1-worker e1-daemon e1-qemu e1-rootwrap-daemon e1-keepalived e1-haproxy-ns \
                neutron-l3-agent neutron-netns-cleanup; do ln -s e1-sigsvc /usr/local/bin/$n; done
# neutron-base start script, unmodified (kolla docker/neutron/neutron-base/extend_start.sh); the l3-agent image adds
# nothing, so kolla_neutron_extend_start stays empty.
COPY kolla/neutron-base-extend_start.sh /usr/local/bin/kolla_extend_start
RUN chmod 755 /usr/local/bin/kolla_extend_start && touch /usr/local/bin/kolla_neutron_extend_start \
    && chmod 755 /usr/local/bin/kolla_neutron_extend_start
# kolla docker/neutron/neutron-l3-agent/Dockerfile.j2 ends with USER neutron
USER neutron
