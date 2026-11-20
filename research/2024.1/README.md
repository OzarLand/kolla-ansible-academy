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

## Review notes (closed)

- method-and-limits: service cards added to "Generated material"; counts of "Related" restored (F1–F17, A–E, Q1–Q21).
- conventions: the Critical list (R7, R12, R14, R15, R16) and the R3/R10 maintenance references restored.
- glossary and other pages: identifier ranges updated to R1–R30, F1–F17, Q1–Q21; the compute-scaling §1 anchor exists.
- impact classes: the `writes-config` row of conventions already says, with evidence, that `genconfig` can pull the
  fluentd image; the class name is kept.
- "Key answers" notes: kept where a page has one (component pages openvswitch and ovn, fact sheets A, C and E); a
  Key answers note is optional on any page, so no harmonisation is needed.
- risk/tag-index and risk/index: the new rows (letsencrypt, etcd, removed services) have no risk in the 2024.1
  register, so "–" is correct; the risk index names R26–R30.
