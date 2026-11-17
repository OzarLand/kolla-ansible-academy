# e6 tgtd image: kolla ussuri-eol (9107c5f) docker/tgtd/Dockerfile.j2, deb branch, on reallab/base:ussuri.
# install_packages(['tgt']) expands to kolla/template/methods.py:55-62 (apt-get update; install
# --no-install-recommends; apt-get clean; rm lists). No USER: tgtd runs as root, like the kolla image.
FROM reallab/base:ussuri
RUN apt-get update && apt-get -y install --no-install-recommends tgt && apt-get clean && rm -rf /var/lib/apt/lists/*
# The real kolla line (docker/tgtd/Dockerfile.j2:19), unchanged.
RUN sed -i '1 i include /var/lib/cinder/volumes/*' /etc/tgt/targets.conf
