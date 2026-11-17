# e1-mariadb:ussuri - the kolla mariadb image steps (kolla docker/mariadb/mariadb/Dockerfile.j2) on reallab/base:ussuri,
# with the REAL MariaDB server from bionic: mariadb-server 10.1 and galera-3 25.3.20 (Ussuri used MariaDB 10.3 from
# the MariaDB repository). mariadb-backup does not exist in bionic and is left out (only used for SST and backups).
# kolla/ is filled by run.sh from the kolla ussuri-eol checkout (KOLLA_SRC).
FROM reallab/base:ussuri
# kolla docker/base/Dockerfile.j2:289-292 (not in reallab/base): enlarge the system uid range so packages accept the
# pre-created kolla users
RUN sed -i -e s/LAST_SYSTEM_UID=999/LAST_SYSTEM_UID=59999/g /etc/adduser.conf
RUN groupadd --force --gid 42434 mysql \
    && useradd -l -M --shell /usr/sbin/nologin --uid 42434 --gid 42434 mysql \
    && usermod --append --home /var/lib/mysql --groups kolla mysql \
    && mkdir -p /var/lib/mysql && chown -R 42434:42434 /var/lib/mysql
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get -y install --no-install-recommends \
      expect mariadb-client mariadb-server galera-3 \
    && rm -rf /var/lib/apt/lists/*
COPY kolla/mariadb_sudoers /etc/sudoers.d/kolla_mariadb_sudoers
COPY kolla/extend_start.sh /usr/local/bin/kolla_extend_start
COPY kolla/security_reset.expect /usr/local/bin/kolla_security_reset
RUN chmod 755 /usr/local/bin/kolla_extend_start \
    && chmod 755 /usr/local/bin/kolla_security_reset \
    && chmod 750 /etc/sudoers.d \
    && chmod 440 /etc/sudoers.d/kolla_mariadb_sudoers \
    && rm -rf /var/lib/mysql/*
RUN mkdir -p /var/run/mysqld && chown mysql /var/run/mysqld && chmod 755 /var/run/mysqld
# kolla docker/mariadb/mariadb/Dockerfile.j2:65-76: no --single-child for MariaDB
ENTRYPOINT ["dumb-init", "--"]
CMD ["kolla_start"]
USER mysql
