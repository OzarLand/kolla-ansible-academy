# e3 stand-in for kolla ubuntu-binary-heat-api (ussuri-eol 9107c5f). Same wiring as kolla docker/heat/heat-base and
# heat-api Dockerfile.j2: user heat (kolla uid/gid 42418, group kolla), the UNMODIFIED heat-base extend_start.sh as
# kolla_extend_start and the UNMODIFIED heat-api extend_start.sh as kolla_heat_extend_start, USER heat.
# /usr/bin/heat-manage and /usr/bin/openstack are STAND-INS (see the files): only the bootstrap branch is exercised.
FROM reallab/base:ussuri
RUN groupadd --gid 42418 heat \
    && useradd -l -M --shell /usr/sbin/nologin --uid 42418 --gid 42418 --home /var/lib/heat heat \
    && usermod --append --groups kolla heat \
    && mkdir -p /var/lib/heat /etc/heat /etc/apache2/conf-enabled && chown -R heat: /var/lib/heat /etc/heat
COPY kolla-heat-base-extend_start.sh /usr/local/bin/kolla_extend_start
COPY kolla-heat-api-extend_start.sh /usr/local/bin/kolla_heat_extend_start
COPY heat-manage-standin /usr/bin/heat-manage
COPY openstack-standin /usr/bin/openstack
RUN chmod 755 /usr/local/bin/kolla_extend_start /usr/local/bin/kolla_heat_extend_start /usr/bin/heat-manage /usr/bin/openstack
USER heat
