# Kolla Ansible Day 2

A source-level study of Kolla-Ansible `ussuri-eol` for Day-2 operations: what each tag really executes, how runs scale
with the number of compute nodes, and what Kolla-Ansible commands do to a running production platform. The study rests
only on reading source code; nothing was run against a host ([Method and limits of the
study](docs/reference/method-and-limits.md)).

## Versions studied

| Component | Version |
|---|---|
| OpenStack release | Ussuri (`openstack_release: "ussuri"`, `ansible/group_vars/all.yml:530`) |
| Kolla-Ansible | 10.x series, the Ussuri series: tag `ussuri-eol`, commit `8a94fe9`. The last numbered release tag of the series in `openstack/kolla-ansible` is `10.4.0`; `ussuri-eol` is a later commit |
| Kolla (images) | tag `ussuri-eol` of `openstack/kolla` |
| Ansible | 2.9.27 |

All conclusions come from the Ussuri implementation, not from newer releases.

## Portal

**<https://ozarland.github.io/kolla-ansible-day2/>**

The portal is the recommended way to read the study: it has a search on every page, a navigation by operator need and
the impact classes of each operation. The Docs workflow ([.github/workflows/docs.yml](.github/workflows/docs.yml))
rebuilds and publishes it on every push to `main` that changes the documentation.

The portal is generated from the Markdown under `docs/`, which is the single source. Every page can also be read here
on GitHub, starting from [docs/index.md](docs/index.md).

## How the content is organised

| Tab | What it holds |
|---|---|
| [Home](docs/index.md) | Entry page, [Find it fast](docs/start/find-it-fast.md), [Ten things to know before a production run](docs/start/ten-things-to-know.md), [Conventions and evidence labels](docs/start/conventions.md) |
| [Operations](docs/operations/index.md) | One page per Day-2 operation, with its commands, its impact classes and the risks it names |
| [Troubleshooting](docs/troubleshooting/index.md) | Symptom index, known bugs and limitations, open questions, what is not known |
| [Components](docs/components/index.md) | One page per OpenStack service and per infrastructure component, each ending with its service card |
| [Risk and impact](docs/risk/index.md) | The 25 rated risks, what a tag really executes, the tag index |
| [Concepts](docs/concepts/index.md) | Repository architecture, deployment execution flow, compute scaling, the kolla images |
| [Reference](docs/reference/index.md) | Findings, glossary, generated inventory, per-role fact sheets, Ansible listings, method and limits |

## Evidence labels

- **[CODE]** shown by the sources, with a `path:line` citation nearby.
- **[NOT AVAILABLE]** the sources do not establish it.

The full definition is in [Evidence labels](docs/start/conventions.md#evidence-labels).

## Build and check locally

Needed: Python 3.11 or newer, `git`, `make`. Only `make docs-deps` needs the network.

```bash
python3 -m venv .venv     # once; the Makefile uses .venv when it exists, no activation needed
make docs-deps
make docs-check
make docs-build
make docs-serve           # http://localhost:8000/kolla-ansible-day2/
```

| Target | What it does |
|---|---|
| `make docs-deps` | Installs the pinned build dependencies (`requirements-docs.txt`) and fetches the vendored Mermaid bundle |
| `make docs-check` | Checks the Markdown sources; no build needed |
| `make docs-build` | Runs the unit tests of `tools/site`, the strict build into `site/`, then the checks on the built site |
| `make docs-test` | Runs the unit tests of `tools/site` only |
| `make docs-serve` | Serves a live preview |
| `make docs-clean` | Removes what the build generates |

`STRICT=1` reports the warnings of the checks as errors, `PYTHON=<interpreter>` forces an interpreter and
`DEV_ADDR=<ip:port>` moves the preview. The rules of the checks and the CI workflow are described in
[tools/site/README.md](tools/site/README.md).

## Contributing

[CONTRIBUTING.md](CONTRIBUTING.md) says where a page goes, how it is built, which evidence is accepted and which checks
to run before a pull request.

## Tools

- [tools/extract_kolla_inventory.py](tools/extract_kolla_inventory.py) writes
  [docs/reference/generated-inventory.md](docs/reference/generated-inventory.md) from a Kolla-Ansible checkout.
- [tools/service_cards.py](tools/service_cards.py) rewrites the service cards of the pages under `docs/components/`,
  between their `GENERATED` markers.
- [tools/site/](tools/site/README.md) holds the site tooling: the checks, the pre-build step and the local Markdown
  extension.

## Licence

Apache License 2.0, see [LICENSE](LICENSE).
