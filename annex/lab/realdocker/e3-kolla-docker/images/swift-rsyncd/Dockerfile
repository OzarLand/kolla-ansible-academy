# e3 copy of kolla ubuntu-binary-swift-rsyncd (ussuri-eol 9107c5f) wiring: bionic rsync (the real binary; rsync is from
# bionic main in the Ussuri image too), user swift (kolla uid/gid 42445, group kolla), the UNMODIFIED kolla
# swift-base swift_sudoers and swift-rsyncd extend_start.sh, USER swift. The swift packages themselves are not
# installed (rsyncd does not use them).
FROM reallab/base:ussuri
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get -y install --no-install-recommends rsync \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 42445 swift \
    && useradd -l -M --shell /usr/sbin/nologin --uid 42445 --gid 42445 --home /var/lib/swift swift \
    && usermod --append --groups kolla swift \
    && mkdir -p /var/lib/swift /etc/swift /srv/node && chown -R swift: /var/lib/swift /etc/swift \
    && chmod 750 /etc/sudoers.d
COPY kolla-swift_sudoers /etc/sudoers.d/kolla_swift_sudoers
COPY kolla-swift-rsyncd-extend_start.sh /usr/local/bin/kolla_extend_start
RUN chmod 440 /etc/sudoers.d/kolla_swift_sudoers && chmod 755 /usr/local/bin/kolla_extend_start
USER swift
