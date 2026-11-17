# e6 memcached image: kolla ussuri-eol (9107c5f) docker/memcached/Dockerfile.j2 on reallab/base:ussuri.
FROM reallab/base:ussuri
# kolla docker/base/Dockerfile.j2:17-22 creates every service user with its fixed id (kolla/common/config.py:1057-1060);
# reallab/base only creates the kolla group, so the memcached user is created here the same way.
RUN groupadd --force --gid 42457 memcached && useradd -l -M --shell /usr/sbin/nologin --uid 42457 --gid 42457 memcached
# macros.configure_user(name='memcached', homedir='/run/memcache') (docker/macros.j2:44-58)
RUN usermod --append --home /run/memcache --groups kolla memcached \
    && mkdir -p /run/memcache \
    && chown -R 42457:42457 /run/memcache
RUN apt-get update && apt-get -y install --no-install-recommends memcached && apt-get clean && rm -rf /var/lib/apt/lists/*
USER memcached
