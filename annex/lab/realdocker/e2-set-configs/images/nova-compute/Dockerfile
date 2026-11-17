# e2-nova-compute:ussuri - the start path of the kolla ussuri-eol Ubuntu nova-compute image:
# reallab/base:ussuri (unmodified kolla base scripts), the users and group membership kolla creates, the real
# nova-base and nova-compute start scripts, USER nova. The nova-compute binary is a stand-in (see nova-compute-standin).
FROM reallab/base:ussuri
# kolla docker/base/Dockerfile.j2:17-22 creates every user up front; uids/gids from kolla/common/config.py
RUN groupadd --force --gid 42436 nova && useradd -l -M --shell /usr/sbin/nologin --uid 42436 --gid 42436 nova \
    && groupadd --force --gid 42427 qemu && useradd -l -M --shell /usr/sbin/nologin --uid 42427 --gid 42427 qemu
# kolla docker/macros.j2:45-59 configure_user(name='nova', groups='qemu'), called at docker/nova/nova-base/Dockerfile.j2:10
RUN usermod --append --home /var/lib/nova --groups kolla nova \
    && usermod --append --groups qemu nova \
    && mkdir -p /var/lib/nova \
    && chown -R 42436:42436 /var/lib/nova
# kolla docker/nova/nova-base/Dockerfile.j2:130-133 and docker/nova/nova-compute/Dockerfile.j2:189-190
COPY vendor/kolla/docker/nova/nova-base/extend_start.sh /usr/local/bin/kolla_extend_start
COPY vendor/kolla/docker/nova/nova-compute/extend_start.sh /usr/local/bin/kolla_nova_extend_start
COPY images/nova-compute/nova-compute-standin /usr/bin/nova-compute
RUN chmod 755 /usr/local/bin/kolla_extend_start /usr/local/bin/kolla_nova_extend_start /usr/bin/nova-compute
# kolla docker/nova/nova-compute/Dockerfile.j2:196
USER nova
