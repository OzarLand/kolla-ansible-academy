# Contributing

The portal is generated from the Markdown under `docs/<release>/`, one directory and one site per release of
[versions.toml](versions.toml). A change to the content is a change to those files; nothing exists only in a template,
a script or a stylesheet. This page says how to add or change a page, and how to add a release.

One release is available today, `ussuri`. The paths below are those of that release; another release has the same
layout under its own directory.

## The evidence rule

Each release is a source-code study of one Kolla-Ansible tag: `ussuri-eol` for `docs/ussuri/`. Every statement is one
of two things:

- **[CODE]**: shown by the sources, with a `path:line` citation nearby;
- **[NOT AVAILABLE]**: the sources do not establish it.

Nothing else is accepted: no observation from a run, no timing, no statement about another release. A page of
`docs/<release>/` cites the sources of the tag of that release only. The definition of
the two labels, with the path prefixes used in citations, is in [Evidence
labels](docs/ussuri/start/conventions.md#evidence-labels). Introductions, hub pages and descriptions only restate what a
section says, and link to it.

## Where a page goes

| Directory | Tab | What belongs there |
|---|---|---|
| `docs/ussuri/start/` | Home | Entry pages: lookup by question, the short list to read first, the conventions |
| `docs/ussuri/operations/` | Operations | One page per Day-2 operation: its commands, then what they do, the risks and the verification |
| `docs/ussuri/troubleshooting/` | Troubleshooting | The symptom index, known bugs and limitations, open questions, what is not known |
| `docs/ussuri/components/` | Components | One page per component, ending with its generated service card; pages that cut across components |
| `docs/ussuri/risk/` | Risk and impact | The risk register, what a tag really executes, the tag index |
| `docs/ussuri/concepts/` | Concepts | How Kolla-Ansible is built and how a run works |
| `docs/ussuri/reference/` | Reference | Findings, glossary, generated inventory, fact sheets, Ansible listings, method and limits |

A new page is then listed in two places:

1. the hub of its tab (`index.md` of the directory): each hub lists every page of its tab, and the
   [Operations catalogue](docs/ussuri/operations/index.md#operations-catalogue) has one row per operation page;
2. the `nav` list of the release, in [docs/ussuri.toml](docs/ussuri.toml), under its tab. Only the path is written
   there, relative to `docs/ussuri/`: the title comes from the front matter of the page.

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
  classes](docs/ussuri/start/conventions.md#operation-impact-classes). A class is used only where the corpus supports it; a
  new use is backed by a section, cited in that table.
- The command sections follow the [conventions used by the command
  sections](docs/ussuri/operations/index.md#conventions-used-by-the-command-sections).
- How pages are built is summarised in [How pages are built](docs/ussuri/start/conventions.md#how-pages-are-built).

## Writing rules

- English, plain and short sentences. Prose is wrapped at 120 columns; table rows are not wrapped.
- **Links** between pages are relative and end in `.md`, with a `#anchor` when they point to a section. They stay
  inside the directory of the release (`docs/ussuri/`) and point to a file, not to a directory or to the published
  URL.
- **A link to a page of another release** is the one exception: each release is a separate site, so the link is the
  absolute address of the published page, for example
  `https://ozarland.github.io/kolla-ansible-academy/ussuri/operations/reconfigure-nova/#2-what-restarts`. A relative
  link such as `../../ussuri/operations/reconfigure-nova.md` is refused: it works on github.com but not on the site.
  `make docs-check` verifies that the release exists and has that page and that anchor. Such a link only points the
  reader to the other study; it is not evidence for the release being written.
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
  [overrides/assets/vendor/mermaid/README.md](overrides/assets/vendor/mermaid/README.md).

## Risks, findings and open questions

The items of the [Risk register](docs/ussuri/risk/risk-register.md) (R), of the [Technical
findings](docs/ussuri/reference/findings.md) (F) and of the [Open questions](docs/ussuri/troubleshooting/open-questions.md) (Q) are
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
5. Search `docs/ussuri/` for the sentences that give the number of items ("25 risks", "R1–R25", "fifteen headline findings",
   "Q1–Q14") and update them.

## Generated content

Two parts of each release are written by the generators of `tools/` and must not be edited by hand:

- the service card of each component page, between `<!-- BEGIN GENERATED: tools/service_cards.py <role> -->` and
  `<!-- END GENERATED -->`;
- [docs/ussuri/reference/generated-inventory.md](docs/ussuri/reference/generated-inventory.md), except its front
  matter.

To regenerate them, use a checkout of `openstack/kolla-ansible` at the tag of the release (`ussuri-eol` for `ussuri`;
the tag is in `versions.toml`). Both scripts need PyYAML; the first one also needs the example `multinode` inventory
as JSON. `--release` names the release to write into; without it, it is the default release of `versions.toml`:

```bash
ansible-inventory -i <checkout>/ansible/inventory/multinode --list > inventory.json
python3 tools/service_cards.py --release ussuri <checkout> inventory.json   # the cards under docs/ussuri/components/
python3 tools/extract_kolla_inventory.py --release ussuri <checkout>        # docs/ussuri/reference/generated-inventory.md
```

The scripts were written for the Ussuri tree. For another release, read their output against the sources of that
release before trusting it: a role or a file layout that changed upstream may need a change in the generator.

`service_cards.py` rewrites only the text between the markers. `extract_kolla_inventory.py` keeps the front matter of
the output file and rewrites its body. A change to a card or to the inventory is a change to the generator.

## Adding a release

A new release is a **new study**, made from the sources of that release. The pages of Ussuri must not be copied and
assumed valid: a task, a default, a handler or a tag may differ, and nothing in the copy would say so. Every statement
of the new release needs its own evidence, a `path:line` citation in the code of the tag that is studied, or the label
[NOT AVAILABLE]. A page may reuse the structure of an Ussuri page, never its statements.

The releases are listed in [versions.toml](versions.toml), one `[[release]]` block each. A release is either
`planned` or `available`.

### A planned release

A planned release has no directory and no content. To add one, add its block to `versions.toml`; to remove one, remove
the block. Nothing else changes.

```toml
[[release]]
id = "victoria"
status = "planned"
openstack = "Victoria"
kolla_ansible = "11.x"
```

The portal then lists it in the release selector under "Coming soon" and publishes one generated page at
`/victoria/`, which says that the study is not available yet and links to the available releases. Any other address
under `/victoria/` leads to that page. The text of the page is in `overrides/planned.html`, the same for every planned
release.

### Making a release available

The steps are the same for a release that is already planned and for one that is not in the registry yet. `<id>` is
the id of the release: lowercase letters, digits, dots and hyphens (`victoria`, `2023.1`). It is the name of the
directory, the URL segment and the key of the registry.

1. **Create the content** in `docs/<id>/`, with the layout of [Where a page goes](#where-a-page-goes). The minimum is
   a home page, `docs/<id>/index.md`, whose front matter has `template: home.html`, a `title` and a `description`.
   Write the pages from the sources of the tag that is studied (see above). Two things in the shared templates
   expect a page of the release: an operation page that sets `impact` gets chips that link to
   `start/conventions.md#operation-impact-classes`, so the release needs that page and that heading before its first
   `impact`; and the class names are fixed by `check_docs.py` (rule `impact`), the same for every release.
2. **Create `docs/<id>.toml`**, next to the directory, with the settings of the release: its description and its
   navigation. Start from [docs/ussuri.toml](docs/ussuri.toml) and keep only the pages that exist:

   ```toml
   [project]
   site_description = "Source-code study of Kolla-Ansible <tag> for Day-2 operations."

   nav = [
     { "Home" = [
       "index.md",
     ] },
   ]
   ```

   Everything else comes from [zensical.base.toml](zensical.base.toml), shared by all releases. The tooling sets
   `docs_dir`, `site_dir`, `site_url` (`<portal address><id>/`) and `edit_uri` (`blob/main/docs/<id>/`).
3. **Register the release** in `versions.toml`: set `status = "available"` in its block, or add the block, and give
   the upstream tag that is studied.

   ```toml
   [[release]]
   id = "victoria"
   status = "available"
   openstack = "Victoria"
   kolla_ansible = "11.x"
   tag = "<upstream tag that is studied>"
   ```

   The order of the blocks is the order of the release selector. Leave `default` and `unprefixed` as they are:
   `default` is the release the welcome page at the root address leads to, and changing it is a separate decision; `unprefixed` is the release
   whose pages were published without a release prefix (`ussuri`), and it does not change.
4. **Add the release to the table** of [README.md](README.md#releases), which lists the available releases. A unit
   test compares the table with `versions.toml`.
5. **Check and build.** `RELEASE=<id>` limits the checks and the build to the new release while it is being written:

   ```bash
   make docs-check RELEASE=<id>
   make docs-build RELEASE=<id>
   make docs-serve RELEASE=<id>      # live preview of that release
   make docs-check STRICT=1          # before the pull request: every release
   make docs-build STRICT=1
   make docs-preview                 # the built portal, to try the release selector
   ```

Nothing is copied per release: the templates, the stylesheet, the scripts, the logo and the vendored Mermaid are in
`overrides/` and are shared. The workflow needs no change: it builds every available release of `versions.toml`.

What the checks enforce for a release:

- `versions.toml` and the tree agree: an available release has `docs/<id>/` and `docs/<id>.toml`, a planned release
  has neither, and nothing else sits directly under `docs/` (rule `registry`). An available release without `tag`, an
  id that is not a valid directory name, or a `default` that is not available, is an error.
- Every page of `docs/<id>/` follows the rules of this file (front matter, links, anchors, callouts, code languages)
  and is listed once in the `nav` of `docs/<id>.toml`.
- A link never leaves the release, except as the absolute address of a page of another release that exists.
- In the built portal: every page of the release is built under `/<id>/`, its search index and its sitemap only list
  pages of that release, `versions.json`, the landing page and the not-found page match `versions.toml`, and a
  planned release has its "coming soon" page and no other.

The checks cannot tell whether a statement was verified in the sources of the new release. That is the review of the
pull request: it reads the citations against the tag named in `versions.toml`.

### Removing a release, changing the default

- To take a release offline, set its status back to `planned` and remove `docs/<id>/`, `docs/<id>.toml` and its row
  in the table of `README.md`, or remove its block as well. Its published pages then lead to the "coming soon" page, or to the not-found page of the portal.
- `default` may be changed to any available release. The root address then opens that release. The addresses
  published before the portal had releases still lead to `unprefixed`.

## Before a pull request

```bash
python3 -m venv .venv     # once
make docs-deps            # once, and after a change of requirements-docs.txt
make docs-check           # the Markdown sources of every release: front matter, links, anchors, callouts, nav
make docs-build           # unit tests, strict build into site/, checks on the built portal
make docs-serve           # live preview of one release, to read the page as the site shows it
```

`make docs-check STRICT=1` and `make docs-build STRICT=1` report the warnings as errors (for example a missing
`description`). The rules of both checks are listed in [tools/site/README.md](tools/site/README.md).

The workflow [.github/workflows/docs.yml](.github/workflows/docs.yml) runs on every pull request that changes `docs/`,
`overrides/`, `tools/site/`, `versions.toml`, `zensical.base.toml`, `requirements-docs.txt`, `Makefile`, `README.md`,
`CONTRIBUTING.md` or the workflow itself. It runs `make docs-deps`, `make docs-check STRICT=1` and `make docs-build STRICT=1`. A pull
request is never deployed: its built portal is uploaded as the artifact `site`, kept 7 days. On `main`, the same build is
followed by the deployment to GitHub Pages.

## Learning journey and levels

The beginner path of each release ("Your learning journey", `docs/<id>/start/learning-journey.md`) is defined once, in
`[project.extra.journey]` of `zensical.base.toml`: five stages, each with its pages (URL and title), a goal and an
illustration. Every release must have the pages it lists. The template `overrides/journey.html` shows the stages;
`overrides/main.html` adds, on every page it lists, the journey bar under the title, and at the end the "Mark this page
as read" box with the previous and next steps. The progress is kept in the reader's browser only
(`overrides/assets/javascripts/learning.js`).

Every page shows a level (Discover, Practise or Master), taken from its section in `[project.extra.journey.levels]`.
A page can set another one in its front matter: `level: discover`, `practise` or `master`.

The journey adds no technical statement: its texts only say what each stage covers and link to the pages, which keep
their evidence labels.

## Definitions on hover and quizzes

**Definitions.** The first time a term of the glossary appears on a page, the reader can hover, focus or click it to
see its meaning and the section that defines it. The data is generated at build time from the table of
`docs/<id>/reference/glossary.md` (`tools/site/glossary.py`, written to `docs/<id>/assets/data/glossary.json`, which
is git-ignored): to add or fix a definition, edit the glossary row. A term in lower-case words ("drift", "one-shot
container") is matched in the text; any other term, the parts in parentheses and the everyday words listed in
`EVERYDAY_WORDS` of `glossary.py` ("restart"), only as a whole code span.

**Quizzes.** A page can end with a "Check yourself" block: a `quiz` list in its front matter.

```yaml
quiz:
  - q: "How is a configuration change applied to a running container?"
    options: ["The service reloads its configuration", "By a full stop and start"]
    answer: 1                    # index of the right option, from 0
    explain: "Restates what the section establishes; inline HTML such as <code> is allowed."
    see: "43-the-config--check--handler-pattern"   # anchor of the section on this page (optional)
```

A quiz only restates what the page already establishes, with the same evidence, and `see` points to the section
that gives it (check_site checks the anchor); leave `see` out on a page without sections. Every page of the learning
journey has a quiz, except the lookup pages (glossary, find it fast, command quick lookup). The answers differ between
releases when the code does: write each release's quiz from its own page.

The score counts the first choice of each question. `learning.js` keeps the best score of each page in the reader's
browser (`kolla-ansible-academy:quiz:<release>`); the journey page shows it next to the page, with a "Continue where you
left off" link (`overrides/partials/resume.html`, also on the release home) to the first page not yet marked as read.
"Reset my progress" forgets both.

`make docs-check` runs `tools/site/check_learning.py`, which checks the shape of all these blocks (answers, one `best`
choice, allowed inline HTML, `see` targets): see [tools/site/README.md](tools/site/README.md#learning-blocks-check_learningpy).

**To remember.** A page of the journey can end with a `remember` list in its front matter: 3 to 5 short sentences, the
takeaways a reader would note before a production run, each restating the page with its evidence label. They are
rendered after the page, before the scenarios and the quiz, with a button that copies them as plain text.

```yaml
remember:
  - "A tag never restricts which hosts a play targets: use <code>--limit</code> for that."
```

**Scenarios.** Before the quiz, a page can hold "What would you do?": a `scenarios` list in its front matter, each a
situation from a real platform with three possible actions.

```yaml
scenarios:
  - title: "Short title of the situation"
    situation: "Two to four sentences, in the second person."
    ask: "What would you do?"
    choices:
      - text: "One action"
        verdict: "risky"
        why: "Why, restating the page."
      - text: "Another action"
        verdict: "best"
        why: "..."
      - text: "A third action"
        verdict: "avoid"
        why: "..."
    see: "anchor-of-a-section"
```

Exactly one choice is `best`; the others are `risky` (works, with a risk the page describes) or `avoid` (contradicted
by the page). The situation may be invented, the technical facts may not: every `why` restates the page with its
evidence labels, and a destructive action on production is never the best choice. Scenarios are on the operation and
risk pages and on the Nova deep dive.

**Final challenge of a stage.** The front matter of `docs/<id>/start/learning-journey.md` holds `challenges`, a quiz
per stage id of `extra.journey` (`discover`, `understand`, `practise`, `judge`, `master`). It has the format of a page
quiz, except that `see` is the path of the page that gives the answer, from the root of the release
(`risk/tags/#4-practical-consequences`). The questions cover the whole stage, at least three of its pages, and do not
repeat the quizzes of the pages. The seal of a stage lights up once its pages are marked as read and its challenge has
all answers but one right on the first try (`learning.js`, key `kolla-ansible-academy:challenge:<release>`); the seal
of the journey needs every stage seal.
