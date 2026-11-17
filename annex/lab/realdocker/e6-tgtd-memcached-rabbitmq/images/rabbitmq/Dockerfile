# e6 rabbitmq image: kolla ussuri-eol (9107c5f) docker/rabbitmq/Dockerfile.j2, deb branch, on reallab/base:ussuri.
# Deviation: rabbitmq-server is bionic's 3.6.10 (Erlang 20.2). The Ussuri Ubuntu image took RabbitMQ 3.8 from the
# rabbitmq/erlang extra repos (enable_extra_repos(['erlang', 'powertools', 'rabbitmq'])), which are not reachable here.
FROM reallab/base:ussuri
# kolla docker/base/Dockerfile.j2:17-22 (fixed id, kolla/common/config.py:993-996)
RUN groupadd --force --gid 42439 rabbitmq && useradd -l -M --shell /usr/sbin/nologin --uid 42439 --gid 42439 rabbitmq
# macros.configure_user(name='rabbitmq') (docker/macros.j2:44-58): home /var/lib/rabbitmq
RUN usermod --append --home /var/lib/rabbitmq --groups kolla rabbitmq \
    && mkdir -p /var/lib/rabbitmq \
    && chown -R 42439:42439 /var/lib/rabbitmq
RUN apt-get update && apt-get -y install --no-install-recommends logrotate rabbitmq-server \
    && apt-get clean && rm -rf /var/lib/apt/lists/*
# Dockerfile.j2:42-46. Deviation: rabbitmq_prometheus does not exist in 3.6.10, so only rabbitmq_management.
RUN rm -rf /var/lib/rabbitmq/* \
    && mkdir -p /usr/lib/rabbitmq/plugins \
    && /usr/lib/rabbitmq/bin/rabbitmq-plugins enable --offline \
       rabbitmq_management
# Dockerfile.j2:50-51: the REAL kolla docker/rabbitmq/extend_start.sh (copied into this context by build.sh)
COPY extend_start.sh /usr/local/bin/kolla_extend_start
RUN chmod 755 /usr/local/bin/kolla_extend_start
USER rabbitmq
