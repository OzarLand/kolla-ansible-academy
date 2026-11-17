# e2-memcached:ussuri - the kolla ussuri-eol Ubuntu memcached image (kolla docker/memcached/Dockerfile.j2): base,
# configure_user(name='memcached', homedir='/run/memcache'), package memcached, USER memcached.
# memcached is the real binary, from bionic (1.5.6-0ubuntu1.x).
FROM reallab/base:ussuri
RUN groupadd --force --gid 42457 memcached && useradd -l -M --shell /usr/sbin/nologin --uid 42457 --gid 42457 memcached \
    && usermod --append --home /run/memcache --groups kolla memcached \
    && mkdir -p /run/memcache \
    && chown -R 42457:42457 /run/memcache
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get -y install --no-install-recommends memcached \
    && rm -rf /var/lib/apt/lists/*
USER memcached
