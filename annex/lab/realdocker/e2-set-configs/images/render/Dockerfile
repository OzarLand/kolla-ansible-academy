# e2-render:ussuri - tools for experiment e2 only (not a service image): bionic python3-jinja2 2.10 to render the real
# kolla-ansible templates, openssl to make throw-away test CAs.
FROM reallab/base:ussuri
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get -y install --no-install-recommends python3-jinja2 openssl \
    && rm -rf /var/lib/apt/lists/*
