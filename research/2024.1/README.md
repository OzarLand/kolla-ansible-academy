# 2024.1 study: work in progress

The 2024.1 (Caracal, Kolla-Ansible 18.x, tag `2024.1-eom`) study is being written on the branch
`claude/blissful-franklin-4brx25`. It is not registered as available in `versions.toml` yet: the release stays
"coming soon" on the published site until every page is written and checked.

## Method

- Sources: kolla-ansible `2024.1-eom` (commit `890396f`), kolla `2024.1-eom` (`ed7a36a`), ansible-collection-kolla
  `2024.1-eom` (`82a0f5c`), ansible-core 2.16.20.
- Each page is re-studied from its 2023.1 version: same structure and questions, every statement re-read in the
  2024.1 sources with 2024.1 `path:line` citations, or [NOT AVAILABLE].
- [change-map.md](change-map.md): the cross-cutting changes from 2023.1 to 2024.1, the impact on each page and the
  lots.
- Every page is passed through a citation checker (each `path:line` must exist in the 2024.1 tree; a citation copied
  from 2023.1 whose lines changed is re-checked by hand) and `tools/site/check_learning.py`.

## Progress (lots of change-map.md §3)

| Lot | Pages | Status |
|---|---|---|
| 1. Method and foundations | method-and-limits, repository-architecture, glossary, conventions | repository-architecture done; others in progress |
| 2. Regenerated material | listings, generated-inventory, service cards, tag index | listings and generated-inventory done |
| 3. Execution model | deployment-execution-flow, tags, controlled-batches, compute-scaling, findings | deployment-execution-flow done; others in progress |
| 4. Images and start path | kolla-images, open-questions | kolla-images done |
| 5–10 | shared infrastructure, stateful services, Nova and Neutron, other services, host and ops playbooks, synthesis | to do |

## To make the release available (last step)

Follow CONTRIBUTING.md "Making a release available": `docs/2024.1.toml` with the navigation, `status = "available"`
and `tag = "2024.1-eom"` in `versions.toml`, the learning blocks and the journey challenges for 2024.1, then
`make docs-check docs-build STRICT=1` with no error before merging into `main`.
