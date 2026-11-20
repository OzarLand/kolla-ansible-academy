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

## Progress

All 69 pages of the 2024.1 study are written (lots 1 to 10 of change-map.md §3), every page passed the citation
checker with 0 errors (each "suspect" citation was re-read in the 2024.1 tree), the learning blocks and the five stage
challenges pass `check_learning.py`, and `make docs-check docs-build STRICT=1` passes with 2024.1 registered as
available.

## Release steps (done)

Follow CONTRIBUTING.md "Making a release available": `docs/2024.1.toml` with the navigation, `status = "available"`
and `tag = "2024.1-eom"` in `versions.toml`, the learning blocks and the journey challenges for 2024.1, then
`make docs-check docs-build STRICT=1` with no error before merging into `main`.

## Review notes to close before release

- method-and-limits: re-read phase 6 once all pages exist; add the service cards to "Generated material" once
  `tools/service_cards.py` has been run on the 2024.1 component pages; restore the counts of "Related" (findings,
  fact sheets, open questions) once verified.
- conventions: restore the list of Critical risks in the `critical` class and the R3/R10 references in
  `maintenance-window` once the 2024.1 risk register is written.
- glossary: check the anchor `concepts/compute-scaling-and-performance.md#1-how-ansible-core-216-spends-time-in-kolla-ansible`
  and the R/F/Q identifier ranges once those pages exist.
- impact classes: in 2024.1 `genconfig` and `-t common` can pull the fluentd image (`roles/common/tasks/config.yml:42-51`).
  Decide whether the `writes-config` class text ("restarts no container") needs a note about that pull before release.
- components: openvswitch and ovn carry a "Key answers" note that the other component pages do not have; harmonise (keep on all or none) before release.
- fact sheets: A carries a "Key answers" note that the 2023.1 fact sheets do not; harmonise across A–E.
- risk/tag-index and risk/index: fill the risk column of the new rows (letsencrypt, etcd, removed services) and the risk count once the 2024.1 register is written.
