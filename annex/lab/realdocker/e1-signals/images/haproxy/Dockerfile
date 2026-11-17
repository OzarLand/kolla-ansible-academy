# e1-haproxy:ussuri - the kolla haproxy image steps (kolla docker/haproxy/Dockerfile.j2) on reallab/base:ussuri,
# with the REAL haproxy package from bionic (1.8.8).
FROM reallab/base:ussuri
# kolla docker/base/Dockerfile.j2:289-292 (not in reallab/base): enlarge the system uid range so packages accept the
# pre-created kolla users
RUN sed -i -e s/LAST_SYSTEM_UID=999/LAST_SYSTEM_UID=59999/g /etc/adduser.conf
# kolla base pre-creates the user with fixed ids (kolla/common/config.py:1053-1056), then configure_user
RUN groupadd --force --gid 42454 haproxy \
    && useradd -l -M --shell /usr/sbin/nologin --uid 42454 --gid 42454 haproxy \
    && usermod --append --home /var/lib/haproxy --groups kolla haproxy \
    && mkdir -p /var/lib/haproxy && chown -R 42454:42454 /var/lib/haproxy
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get -y install --no-install-recommends haproxy \
    && rm -rf /var/lib/apt/lists/*
RUN mkdir -p /var/lib/kolla/haproxy \
    && chown -R haproxy: /var/lib /run
