# Faithful reproduction of the kolla ussuri-eol (9107c5f) Ubuntu base start path:
# ubuntu:18.04, dumb-init from bionic apt, and the unmodified kolla base scripts.
FROM ubuntu:18.04
ENV LANG=en_US.UTF-8 KOLLA_BASE_DISTRO=ubuntu
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get -y install --no-install-recommends \
      locales dumb-init sudo python3 ca-certificates procps iproute2 \
    && sed -e "s/# $LANG UTF-8/$LANG UTF-8/g" /etc/locale.gen -i && locale-gen "$LANG" \
    && groupadd --force --gid 42400 kolla \
    && rm -rf /var/lib/apt/lists/*
COPY set_configs.py /usr/local/bin/kolla_set_configs
COPY start.sh /usr/local/bin/kolla_start
COPY copy_cacerts.sh /usr/local/bin/kolla_copy_cacerts
COPY httpd_setup.sh /usr/local/bin/kolla_httpd_setup
COPY sudoers /etc/sudoers
ENTRYPOINT ["dumb-init", "--single-child", "--"]
RUN touch /usr/local/bin/kolla_extend_start \
    && chmod 755 /usr/local/bin/kolla_start /usr/local/bin/kolla_extend_start /usr/local/bin/kolla_set_configs /usr/local/bin/kolla_copy_cacerts /usr/local/bin/kolla_httpd_setup \
    && chmod 440 /etc/sudoers \
    && mkdir -p /var/log/kolla && chown :kolla /var/log/kolla && chmod 2775 /var/log/kolla
CMD ["kolla_start"]
