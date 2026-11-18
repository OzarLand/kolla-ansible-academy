---
title: Stop and destroy
---

# Stop and destroy

<!-- TODO editorial: intro, key answers (old section heading: "Stop and destroy (dangerous)") -->

```bash
kolla-ansible -i multinode stop --yes-i-really-really-mean-it -t heat --limit control03
kolla-ansible -i multinode destroy --yes-i-really-really-mean-it   # never on production
```

- `stop` honours `skip_stop_containers` (e.g. `-e '{"skip_stop_containers": ["nova_libvirt"]}'`).

<!-- TODO editorial: related -->
