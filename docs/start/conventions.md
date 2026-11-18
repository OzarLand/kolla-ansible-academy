---
title: Conventions and evidence labels
---

# Conventions and evidence labels

<!-- TODO editorial -->

## Evidence labels

The same two labels are used everywhere, and this is their single definition. The study rests only on reading source
code; nothing was run against a host, and no run is used as evidence.

- **[CODE]** shown by the sources, with a `path:line` citation nearby: kolla-ansible `ussuri-eol` (unprefixed paths),
  the kolla image repository `ussuri-eol` when the path has a `kolla` prefix (e.g. kolla
  `docker/base/set_configs.py:407-410`), the Ansible source when the path has an `ansible 2.9.27` prefix (or
  `ansible 2.8.20`, read for comparison), and the `--list-tags` and `--list-tasks` listings in [Ansible
  listings](../reference/listings/index.md) (Ansible's own parse of the playbooks).
- **[NOT AVAILABLE]** the sources do not establish it.

The fact sheets use the words FACT and NOT AVAILABLE for the same two levels.
