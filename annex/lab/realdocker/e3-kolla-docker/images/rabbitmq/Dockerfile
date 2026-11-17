# e3 stand-in for kolla ubuntu-binary-rabbitmq (ussuri-eol 9107c5f). Same wiring as kolla docker/rabbitmq/Dockerfile.j2:
# user rabbitmq (kolla uid/gid 42439, home /var/lib/rabbitmq, member of group kolla), the UNMODIFIED kolla
# docker/rabbitmq/extend_start.sh as /usr/local/bin/kolla_extend_start, USER rabbitmq.
# /usr/sbin/rabbitmq-server is a STAND-IN, not RabbitMQ: it logs every signal it receives and ignores SIGTERM.
FROM reallab/base:ussuri
RUN groupadd --gid 42439 rabbitmq \
    && useradd -l -M --shell /usr/sbin/nologin --uid 42439 --gid 42439 --home /var/lib/rabbitmq rabbitmq \
    && usermod --append --groups kolla rabbitmq \
    && mkdir -p /var/lib/rabbitmq /etc/rabbitmq && chown -R rabbitmq: /var/lib/rabbitmq /etc/rabbitmq
COPY rabbitmq-server-standin /usr/sbin/rabbitmq-server
COPY kolla-rabbitmq-extend_start.sh /usr/local/bin/kolla_extend_start
RUN chmod 755 /usr/sbin/rabbitmq-server /usr/local/bin/kolla_extend_start
USER rabbitmq
