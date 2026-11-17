# e5 helper, not a kolla image: holds a network namespace with one end of a veth pair (traffic probe), and runs
# iproute2 on the host network for the veth set-up (this sandbox host has no iproute2).
FROM reallab/base:ussuri
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get -y install --no-install-recommends iputils-ping \
    && apt-get clean && rm -rf /var/lib/apt/lists/*
ENTRYPOINT []
CMD ["sleep", "infinity"]
