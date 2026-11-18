# Contributing

The portal is generated from the Markdown under `docs/`. A change to the content is a change to those files; nothing
exists only in a template, a script or a stylesheet. This page says how to add or change a page.

## The evidence rule

The corpus is a source-code study of Kolla-Ansible `ussuri-eol`. Every statement is one of two things:

- **[CODE]**: shown by the sources, with a `path:line` citation nearby;
- **[NOT AVAILABLE]**: the sources do not establish it.

Nothing else is accepted: no observation from a run, no timing, no statement about a newer release. The definition of
the two labels, with the path prefixes used in citations, is in [Evidence
labels](docs/start/conventions.md#evidence-labels). Introductions, hub pages and descriptions only restate what a
section says, and link to it.

## Where a page goes

| Directory | Tab | What belongs there |
|---|---|---|
| `docs/start/` | Home | Entry pages: lookup by question, the short list to read first, the conventions |
| `docs/operations/` | Operations | One page per Day-2 operation: its commands, then what they do, the risks and the verification |
| `docs/troubleshooting/` | Troubleshooting | The symptom index, known bugs and limitations, open questions, what is not known |
| `docs/components/` | Components | One page per component, ending with its generated service card; pages that cut across components |
| `docs/risk/` | Risk and impact | The risk register, what a tag really executes, the tag index |
| `docs/concepts/` | Concepts | How Kolla-Ansible is built and how a run works |
| `docs/reference/` | Reference | Findings, glossary, generated inventory, fact sheets, Ansible listings, method and limits |

A new page is then listed in two places:

1. the hub of its tab (`index.md` of the directory): each hub lists every page of its tab, and the
   [Operations catalogue](docs/operations/index.md#operations-catalogue) has one row per operation page;
2. the `nav` list of [zensical.toml](zensical.toml), under its tab. Only the path is written there: the title comes
   from the front matter of the page.

## Page skeleton

An operation page, as an example. The other pages have the same parts, without `impact` and without the numbered
command section.

````markdown
---
title: Rotate the example setting
description: One sentence, at most 160 characters, that restates what the page answers.
tags: [nova, reconfigure, loop-notify]
impact: [restarts-on-drift]
---

# Rotate the example setting

One to three sentences: what the page answers, and for which command.

> [!NOTE]
> **Key answers**
>
> - **Short label:** the answer, with its evidence label ([§2](#2-what-restarts)).

## 1. Commands

### 1.1 Name of the command

```bash
kolla-ansible -i multinode -t nova reconfigure
```

- **Scope:** plays and hosts touched.
- **Restarts:** containers that can restart.

## 2. What restarts

[CODE] The statement, with its citation (`roles/nova/tasks/config.yml:10-20`).

## Related

- [Reconfigure Nova](reconfigure-nova.md) — why the reader would go there
````

- `title` has no numbering. `description` is required and has at most 160 characters.
- `tags` are lowercase names of the components and mechanisms the page really covers. Reuse the tags of the existing
  pages (they are the "Tags" filter of the search dialog) before adding a new one.
- `impact` is for operation pages only and uses the classes of [Operation impact
  classes](docs/start/conventions.md#operation-impact-classes). A class is used only where the corpus supports it; a
  new use is backed by a section, cited in that table.
- The command sections follow the [conventions used by the command
  sections](docs/operations/index.md#conventions-used-by-the-command-sections).
- How pages are built is summarised in [How pages are built](docs/start/conventions.md#how-pages-are-built).

## Writing rules

- English, plain and short sentences. Prose is wrapped at 120 columns; table rows are not wrapped.
- **Links** between pages are relative and end in `.md`, with a `#anchor` when they point to a section. They stay
  inside `docs/` and point to a file, not to a directory or to the published URL.
- **Anchors** are those of github.com: the heading in lowercase, every character that is not a letter, a digit, an
  underscore, a hyphen or a space dropped, each space replaced by a hyphen; a repeated heading gets `-1`, `-2`. The
  site is configured to produce the same anchors. Other pages link to the existing headings: renaming a heading breaks
  those links, and `make docs-check` reports them.
- **Callouts** are GitHub alerts only: `> [!NOTE]`, `> [!TIP]`, `> [!IMPORTANT]`, `> [!WARNING]`, `> [!CAUTION]`, with
  the marker alone on the first line of the blockquote.
- **Fenced code** always has a language: `bash`, `yaml`, `jinja`, `python`, `text` or `mermaid`.
- **Diagrams** are `mermaid` code blocks. The Mermaid bundle is vendored: it is not committed, `make docs-deps`
  downloads the pinned version and verifies its checksum, and the site loads it only on pages that contain a diagram.
  Version, checksums and the update procedure are in
  [docs/assets/vendor/mermaid/README.md](docs/assets/vendor/mermaid/README.md).

## Risks, findings and open questions

The items of the [Risk register](docs/risk/risk-register.md) (R), of the [Technical
findings](docs/reference/findings.md) (F) and of the [Open questions](docs/troubleshooting/open-questions.md) (Q) are
sections with an explicit anchor, so that a link such as `../risk/risk-register.md#r12` keeps working when the title of
the item changes. To add an item:

1. Take the next free number. Links target the existing anchors, so the existing items keep their number.
2. Add the section after the last item, in the form of the existing ones: the anchor, a blank line, the heading, then a
   two-column table with the same rows as the other items of the page.

   ```markdown
   <a id="r26"></a>

   ### R26 — Short title

   | | |
   |---|---|
   | **Operation / trigger** | … |
   ```

3. Add its row to the summary table of the page ("Matrix", "Headline findings" or "Summary").
4. Cite it from other pages by its number, linked to its anchor: `[R26](../risk/risk-register.md#r26)`.
5. Search `docs/` for the sentences that give the number of items ("25 risks", "R1–R25", "fifteen headline findings",
   "Q1–Q14") and update them.

## Generated content

Two parts of the tree are written by the generators of `tools/` and must not be edited by hand:

- the service card of each component page, between `<!-- BEGIN GENERATED: tools/service_cards.py <role> -->` and
  `<!-- END GENERATED -->`;
- [docs/reference/generated-inventory.md](docs/reference/generated-inventory.md), except its front matter.

To regenerate them, use a checkout of `openstack/kolla-ansible` at the tag `ussuri-eol`. Both scripts need PyYAML;
the first one also needs the example `multinode` inventory as JSON:

```bash
ansible-inventory -i <checkout>/ansible/inventory/multinode --list > inventory.json
python3 tools/service_cards.py <checkout> inventory.json      # rewrites the cards under docs/components/
python3 tools/extract_kolla_inventory.py <checkout>           # rewrites docs/reference/generated-inventory.md
```

`service_cards.py` rewrites only the text between the markers. `extract_kolla_inventory.py` keeps the front matter of
the output file and rewrites its body. A change to a card or to the inventory is a change to the generator.

## Before a pull request

```bash
python3 -m venv .venv     # once
make docs-deps            # once, and after a change of requirements-docs.txt
make docs-check           # the Markdown sources: front matter, links, anchors, callouts, code languages, nav
make docs-build           # unit tests, strict build into site/, checks on the built site
make docs-serve           # live preview, to read the page as the site shows it
```

`make docs-check STRICT=1` and `make docs-build STRICT=1` report the warnings as errors (for example a missing
`description`). The rules of both checks are listed in [tools/site/README.md](tools/site/README.md).

The workflow [.github/workflows/docs.yml](.github/workflows/docs.yml) runs on every pull request that changes `docs/`,
`overrides/`, `tools/site/`, `zensical.toml`, `requirements-docs.txt`, `Makefile`, `README.md`, `CONTRIBUTING.md` or
the workflow itself. It runs `make docs-deps`, `make docs-check STRICT=1` and `make docs-build STRICT=1`. A pull
request is never deployed: its built site is uploaded as the artifact `site`, kept 7 days. On `main`, the same build is
followed by the deployment to GitHub Pages.
