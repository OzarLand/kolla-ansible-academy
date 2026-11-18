---
title: Database operations
---

# Database operations

<!-- TODO editorial: intro, key answers -->

```bash
kolla-ansible -i multinode mariadb_backup               # full (default) or --incremental
kolla-ansible -i multinode mariadb_recovery             # ONLY when the whole Galera cluster is down
```

<!-- TODO editorial: related -->
