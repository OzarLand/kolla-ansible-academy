# e2-heat-api:ussuri - the start path of the kolla ussuri-eol Ubuntu heat-api image: reallab/base:ussuri, user heat,
# the real heat-base extend_start.sh as kolla_extend_start and the real heat-api extend_start.sh as
# kolla_heat_extend_start. heat-api sets no USER (runs as root). heat-manage and openstack are stand-ins.
FROM reallab/base:ussuri
# kolla docker/base/Dockerfile.j2:17-22 (uid/gid 42418 from kolla/common/config.py), macros.j2 configure_user(name='heat')
RUN groupadd --force --gid 42418 heat && useradd -l -M --shell /usr/sbin/nologin --uid 42418 --gid 42418 heat \
    && usermod --append --home /var/lib/heat --groups kolla heat \
    && mkdir -p /var/lib/heat \
    && chown -R 42418:42418 /var/lib/heat
# kolla docker/heat/heat-base/Dockerfile.j2:74-77 and docker/heat/heat-api/Dockerfile.j2:19-20
COPY vendor/kolla/docker/heat/heat-base/extend_start.sh /usr/local/bin/kolla_extend_start
COPY vendor/kolla/docker/heat/heat-api/extend_start.sh /usr/local/bin/kolla_heat_extend_start
COPY images/heat-api/heat-manage-standin /usr/local/bin/heat-manage
COPY images/heat-api/openstack-standin /usr/local/bin/openstack
RUN chmod 755 /usr/local/bin/kolla_extend_start /usr/local/bin/kolla_heat_extend_start \
      /usr/local/bin/heat-manage /usr/local/bin/openstack
