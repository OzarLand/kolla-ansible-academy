# e1-mariadb-upstreamtrap:ussuri - e1-mariadb:ussuri with ONE edit, which is NOT a kolla step: mysqld_safe gets the
# signal handling of upstream MariaDB (scripts/mysqld_safe.sh:41, trap '' 1 2 3 15: ignore HUP INT QUIT TERM).
# Ussuri's Ubuntu image installed MariaDB 10.3 from MariaDB's own repository (kolla/template/repos.yaml:78), whose
# packaging does not patch mysqld_safe; bionic's 10.1 is Debian-patched to trap TERM and run
# "mysqladmin --defaults-extra-file=/etc/mysql/debian.cnf shutdown" instead.
FROM e1-mariadb:ussuri
USER root
COPY e1-trap.sed /tmp/e1-trap.sed
RUN sed -i -f /tmp/e1-trap.sed /usr/bin/mysqld_safe && rm /tmp/e1-trap.sed \
    && test "$(grep -c '^trap' /usr/bin/mysqld_safe)" = 1 && grep -n '^trap' /usr/bin/mysqld_safe
USER mysql
