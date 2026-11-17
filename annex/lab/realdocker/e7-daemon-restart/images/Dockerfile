# e7 images: reallab/base:ussuri + the unmodified kolla ussuri-eol nova/heat start scripts + the e7-sigsvc stand-in.
# build.sh fills the build context: e7-sigsvc and kolla/*.sh copied from KOLLA_SRC (kolla ussuri-eol, 9107c5f).
# Users: kolla's base creates every service user with a fixed id (kolla/common/config.py:917-920 heat 42418,
# :981-984 nova 42436); configure_user (kolla docker/macros.j2) adds it to group kolla.

FROM reallab/base:ussuri AS nova-base
RUN groupadd --force --gid 42436 nova \
    && useradd -l -M --shell /usr/sbin/nologin --uid 42436 --gid 42436 nova \
    && usermod --append --home /var/lib/nova --groups kolla nova \
    && mkdir -p /var/lib/nova && chown -R 42436:42436 /var/lib/nova
COPY e7-sigsvc /usr/local/bin/e7-sigsvc
RUN chmod 755 /usr/local/bin/e7-sigsvc \
    && ln -s e7-sigsvc /usr/local/bin/nova-scheduler && ln -s e7-sigsvc /usr/local/bin/nova-manage
# kolla docker/nova/nova-base/Dockerfile.j2:130-133
COPY kolla/nova-base-extend_start.sh /usr/local/bin/kolla_extend_start
RUN touch /usr/local/bin/kolla_nova_extend_start \
    && chmod 755 /usr/local/bin/kolla_extend_start /usr/local/bin/kolla_nova_extend_start

# kolla docker/nova/nova-scheduler/Dockerfile.j2:32
FROM nova-base AS nova-scheduler
USER nova

# kolla docker/nova/nova-api/Dockerfile.j2:65-66,71 (the one-shot branches live in kolla_nova_extend_start)
FROM nova-base AS nova-api
COPY kolla/nova-api-extend_start.sh /usr/local/bin/kolla_nova_extend_start
RUN chmod 755 /usr/local/bin/kolla_nova_extend_start
USER nova

FROM reallab/base:ussuri AS heat-engine
RUN groupadd --force --gid 42418 heat \
    && useradd -l -M --shell /usr/sbin/nologin --uid 42418 --gid 42418 heat \
    && usermod --append --home /var/lib/heat --groups kolla heat \
    && mkdir -p /var/lib/heat && chown -R 42418:42418 /var/lib/heat
COPY e7-sigsvc /usr/local/bin/e7-sigsvc
RUN chmod 755 /usr/local/bin/e7-sigsvc && ln -s e7-sigsvc /usr/local/bin/heat-engine
# kolla docker/heat/heat-base/Dockerfile.j2:74-77
COPY kolla/heat-base-extend_start.sh /usr/local/bin/kolla_extend_start
RUN touch /usr/local/bin/kolla_heat_extend_start \
    && chmod 755 /usr/local/bin/kolla_extend_start /usr/local/bin/kolla_heat_extend_start
# kolla docker/heat/heat-engine/Dockerfile.j2:26
USER heat
