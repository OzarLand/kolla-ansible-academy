---
title: Ansible listings
---

# Ansible listings

These two files are Ansible 2.9.27's own parse of the unmodified Kolla-Ansible `ussuri-eol` playbooks. They list
what the playbooks contain; nothing was executed against a host.

| File | Command (from the kolla-ansible checkout, multinode inventory) |
|---|---|
| [list-tags-site.txt](list-tags-site.txt) | `ansible-playbook -i <inventory> ansible/site.yml --list-tags` |
| [list-tasks-nova.txt](list-tasks-nova.txt) | `ansible-playbook -i <inventory> ansible/site.yml --list-tasks -t nova` |

Limits of these listings, read from the playbooks ([Tags
§2.6](../../risk/tags.md#26---list-tasks-is-not-usable-for-kolla-code)): every role is reached through a dynamic
`include_tasks`, so the listings show the plays and the include tasks, not the tasks inside the included files, and tags
set only inside dynamic includes (e.g. `service-rabbitmq`) do not appear in `--list-tags`.
