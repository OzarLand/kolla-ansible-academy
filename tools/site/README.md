# Site tooling

The portal is generated from the Markdown under `docs/<release>/` by
[Zensical](https://github.com/zensical/zensical) 0.1.2. This directory holds what the build needs besides the
generator: the registry of releases, the build, the checks, the pre-build step and the local Markdown extension.
Nothing here holds content.

| File | Role |
|---|---|
| [releases.py](releases.py) | Reads `versions.toml`, writes the configuration Zensical builds for each release and for the root of the portal, and assembles the root (`versions.json`, landing page, not-found page, pages of the planned releases). Standard library only. |
| [build.py](build.py) | Runs the whole build: `prebuild.py`, Zensical for each available release, Zensical for the root, then the assembly. Also starts the live preview of one release. |
| [check_docs.py](check_docs.py) | Checks on the registry and on the Markdown sources of every available release. No build needed, standard library only. |
| [check_learning.py](check_learning.py) | Checks the learning blocks of the front matter (`remember`, `scenarios`, `quiz`, `challenges`): shape, answers, one "best" choice, allowed inline HTML, `see` targets. Needs PyYAML, a pinned dependency. |
| [check_site.py](check_site.py) | Checks on the built portal. Standard library only. |
| [prebuild.py](prebuild.py) | Writes `docs/<id>/assets/data/updates.json` for each available release (date of the last change of each page) and makes sure the vendored Mermaid bundle is in place. |
| [fetch_vendor.py](fetch_vendor.py) | Downloads the pinned Mermaid bundle to `overrides/assets/vendor/mermaid/mermaid.min.js` and verifies its checksums. The file is not committed. |
| [serve_site.py](serve_site.py) | Serves the built portal locally under the path of its address, with the root `404.html` for unknown addresses, as GitHub Pages does. |
| `portal_mdx/` | Python-Markdown extension enabled in `zensical.base.toml`. The build finds it through `PYTHONPATH=tools/site`. |
| `tests/` | Unit tests of the files above (`unittest`). |

Related files at the root of the repository: [Makefile](../../Makefile),
[requirements-docs.txt](../../requirements-docs.txt), [versions.toml](../../versions.toml),
[zensical.base.toml](../../zensical.base.toml), `overrides/` and
[.github/workflows/docs.yml](../../.github/workflows/docs.yml).

## Releases: layout of the sources and of the portal

The portal is one self-contained site per release, published under its own URL prefix, so that the search, the
navigation and the "recently updated" list of a release cover that release only, and so that adding a release never
moves an existing address. How to add a release is in [CONTRIBUTING.md](../../CONTRIBUTING.md#adding-a-release).

| Source | What it is |
|---|---|
| `versions.toml` | The registry: one `[[release]]` block per release (`id`, `status`, `openstack`, `kolla_ansible`, `tag`, optional `title`), plus `default` (the release the welcome page leads to) and `unprefixed` (the release whose pages were published without a prefix). Every tool reads it; nothing else lists the releases. |
| `zensical.base.toml` | The site configuration shared by all releases: theme, palette, Markdown extensions, validation, the address of the portal root. It is not given to Zensical as it is. |
| `docs/<id>/` | The Markdown of an available release. |
| `docs/<id>.toml` | The settings of that release: `site_description` and `nav`. Its `[project]` table is merged over the one of `zensical.base.toml`: tables are merged, lists and plain values replace those of the base. |
| `overrides/` | The templates, and under `overrides/assets/` the static files shared by all releases: stylesheet, scripts, logo, favicon, vendored Mermaid. `overrides/` is the theme directory (`custom_dir`), and Zensical copies the static files of the theme directory into every site it builds, so these files exist once in the repository. |

A release is `available` or `planned`. A planned release has no `docs/<id>/` and no `docs/<id>.toml`.

What the build writes (all git-ignored):

| Path | Content |
|---|---|
| `.zensical.<id>.toml` | Configuration of one available release: base and release settings merged, then `docs_dir = "docs/<id>"`, `site_dir = "site/<id>"`, `site_url = "<portal address><id>/"`, `edit_uri = "blob/main/docs/<id>/"` and `extra.portal` (the releases of the registry, read by the templates). `site_url` and `edit_uri` may be set in `docs/<id>.toml`; `docs_dir` and `site_dir` may not. |
| `.zensical._root.toml`, `.build/root/` | Configuration, Markdown stubs and output of the root site: the landing page, the not-found page and one page per planned release. The text of these pages is in the templates `overrides/landing.html`, `overrides/planned.html` and `overrides/404.html`; the stubs only carry a title. |
| `docs/<id>/assets/data/updates.json` | Written by `prebuild.py`. |
| `site/<id>/` | Site of an available release. |
| `site/<id>/index.html` | The only page of a planned release ("coming soon"). |
| `site/index.html` | Welcome page (overrides/landing.html): why the project exists (to make learning easier), a suggested learning path in the default release, and the list of the releases. |
| `site/404.html` | Not-found page of the whole portal (GitHub Pages serves it for every unknown address). See below. |
| `site/versions.json` | The registry as JSON, in the form the tool `mike` writes (`version`, `title`, `aliases`), with `status`, `default`, `openstack`, `kolla_ansible` and `tag` under `properties`. No page of the portal needs it; it is there for scripts and other tools. |
| `site/sitemap.xml` | Index of the sitemaps of the available releases (`site/<id>/sitemap.xml`). |
| `site/assets/` | Theme files used by the root pages. |

The generated configurations are at the root of the repository because Zensical only accepts a `docs_dir` inside the
directory of its configuration file, and its TOML format has no include.

### Addresses

- A page of a release: `<portal address><id>/<path>/`, for example
  `https://ozarland.github.io/kolla-ansible-academy/ussuri/operations/reconfigure-nova/`. The canonical link, the sitemap
  and "View source" (`blob/main/docs/<id>/<path>.md`) follow.
- The root address is the welcome page; its main button opens the default release.
- An address without a release, such as `/kolla-ansible-academy/operations/reconfigure-nova/`, was published before the
  portal had releases. The not-found page redirects it to the same path under the release named by `unprefixed`
  (`/kolla-ansible-academy/ussuri/operations/reconfigure-nova/`), query and fragment kept, when that path is a page of
  that release; the list of those pages is written into the page at build time. Old path `P` becomes `ussuri/P`.
- Any address under a planned release leads to its one page, `/<id>/`.
- Anything else shows the not-found page, which lists the available and the planned releases.

### Release selector

The header of every page shows the release being read and, when the registry has more than one release, a list of all
of them: the available ones, then the planned ones under "Coming soon". The markup is
`overrides/partials/releases.html`, written into each page from `extra.portal`: without JavaScript every entry is a
plain link to the home page of a release. `portal.js` adds two things: Escape or a click outside closes the list, and
a link to another available release opens the page being read in that release when the `updates.json` of that
release lists it, and its home page otherwise. A planned release always opens its "coming soon" page.

The version selector that the theme has for sites published with `mike` is not used (`extra.version` is not set). It
does read a plain `versions.json` at the portal root, and it does switch to the same page, but it draws the list
inside the title area of the header, where this theme variant clips it; it disappears as soon as the page is
scrolled, because the title area then shows the page title; it shows nothing without JavaScript; and it cannot mark a
release as planned.

`overrides/partials/header.html` is a copy of the header of the theme with the selector added, and without drawer
button, search and tabs on the root pages. Compare it with the file of the theme when Zensical is upgraded.

## Build locally

Needed: Python 3.11 or newer (CI uses 3.13), `git`, `make`. Only `make docs-deps` needs the network: PyPI for the
build dependencies and `registry.npmjs.org` for the Mermaid bundle.

```bash
python3 -m venv .venv     # once; the Makefile uses .venv when it exists, no activation needed
make docs-deps
make docs-check
make docs-build
make docs-serve           # one release, rebuilt on change: http://localhost:8000/kolla-ansible-academy/ussuri/
make docs-preview         # the built portal, all releases: http://localhost:8000/kolla-ansible-academy/
```

Without `.venv` the Makefile runs `python3` from `PATH`, which is what CI does. `make PYTHON=/path/to/python ...`
forces another interpreter.

| Target | What it runs |
|---|---|
| `docs-deps` | `pip install -r requirements-docs.txt`, then `fetch_vendor.py`. |
| `docs-check` | `check_docs.py`: the registry and every available release; then `check_learning.py`: the learning blocks of the front matter. |
| `docs-build` | The unit tests of `tests/`, then `build.py --strict` (`prebuild.py`; `zensical build --clean --strict` for each available release into `site/<id>/`; the same for the root site; the assembly of the root into `site/`), then `check_site.py site`. |
| `docs-test` | The unit tests of `tests/` only (`python3 -m unittest discover -s tools/site/tests`). |
| `docs-serve` | `build.py --serve`: `prebuild.py`, then `zensical serve` for one release (rebuilds on change). The preview holds that release only: the links of the release selector to other releases do not work there. `DEV_ADDR=127.0.0.1:8001` moves it. |
| `docs-preview` | `serve_site.py site`: the built portal under the path of its address, with the root `404.html` for unknown addresses. Use it to try the release selector and the redirection of the old addresses. Run `make docs-build` first. |
| `docs-clean` | Removes `site/`, `.cache/`, `.build/`, the generated `.zensical.*.toml`, the `updates.json` of every release and the `__pycache__` directories under `tools/`. The Mermaid bundle stays. |

`RELEASE=<id>` limits a target to one available release: `make docs-check RELEASE=ussuri` checks that release (and
the registry); `make docs-build RELEASE=ussuri` rebuilds that release and the root, leaves the sites of the other
releases as they are in `site/`, and does not fail on a link to a release that is not built; `make docs-serve
RELEASE=ussuri` chooses the release of the preview (default: the default release of the registry). Without `RELEASE`,
`docs-build` empties `site/` first and builds everything.

`STRICT=1` (`make docs-check STRICT=1`, `make docs-build STRICT=1`) passes `--strict` to both check scripts:
their warnings become errors. CI runs both targets with `STRICT=1`, so run them the same way before opening a pull
request.

`site/`, `.cache/`, `.build/`, `.zensical.*.toml`, `.venv/`, `docs/<id>/assets/data/updates.json` and the Mermaid
bundle are generated or downloaded. They are listed in `.gitignore` and must not be committed.

## Source checks: check_docs.py

The script reads `versions.toml`, then, for every available release, the Markdown pages under `docs/<id>/` and the
`nav` of `docs/<id>.toml` (`--release <id>`: that release only). It also checks the links of `README.md`,
`CONTRIBUTING.md` and this file. It prints the findings by file with their line, then a summary, and exits with 1
when there is at least one error. On GitHub Actions each error is also an annotation on the file.

| Rule | Level | What is checked |
|---|---|---|
| `registry` | error | `versions.toml` can be read (ids, statuses, `default`, `unprefixed`, a `tag` for each available release) and matches the tree: an available release has `docs/<id>/` and `docs/<id>.toml`, a planned release has neither, and nothing else sits directly under `docs/`. |
| `encoding` | error | The file is UTF-8. |
| `front-matter` | error | The page starts with a front matter block that can be read. |
| `title` | error | The front matter has a non-empty `title`. |
| `description` | error | `description` is not empty and has at most 160 characters. A missing `description` is a warning. |
| `impact` | error | Every `impact` value is one of `read-only`, `writes-config`, `pulls-images`, `restarts-on-drift`, `recreates-containers`, `critical`, `maintenance-window`, `recovery`. |
| `tags` | warning | `tags` is a list of lowercase names. |
| `link-file` | error | The target of a relative link or image exists, with the same letter case. |
| `link-anchor` | error | The fragment of a link is a heading anchor of the target or an explicit `id` (for example `<a id="r12"></a>`). |
| `link-style` | error | Links between pages are relative, stay inside the release (`docs/<id>/`) and point to a file, not to a directory or to the published URL of the same release. |
| `link-release` | error | A link to another release is the absolute address of its published page (`<portal address><other id>/<path>/`), never a relative path into `docs/<other id>/`. The release is in the registry, the page exists in its sources, and so does the anchor (reported as `link-anchor`). For a planned release only its home address is accepted. |
| `link-reference` | error | A reference-style link `[text][label]` uses a label defined in the file. |
| `link-repo-file` | error | An absolute link to a file of this repository on `main` points to a file that exists. |
| `code-language` | error | Every fenced code block has a language and is closed. |
| `removed-path` | error | No reference to a path of the former layout (`annex/`, `docs/01-...` to `docs/10-...`). Inside an HTML comment it is a warning. |
| `callout` | error | Callouts are GitHub alerts of the five types `[!NOTE]`, `[!TIP]`, `[!IMPORTANT]`, `[!WARNING]`, `[!CAUTION]`, with the marker alone on the first line of the blockquote. |
| `todo-editorial` | warning | No `<!-- TODO editorial` marker is left. |
| `nav` | error | Every page of a release is listed in the `nav` of `docs/<id>.toml`, and every `nav` entry exists, once. |
| `config` | error | `zensical.base.toml` and `docs/<id>.toml` exist and can be read. |

Heading anchors are computed the way github.com computes them: lowercase, every character that is not a letter,
a digit, an underscore, a hyphen or a space is dropped, each space becomes a hyphen, and a repeated heading gets
`-1`, `-2`. Lines inside fenced code are not headings. `zensical.base.toml` configures the site to produce the same
anchors, so a link that passes here works on github.com and on the site.

```bash
python3 tools/site/check_docs.py              # warnings do not fail the run
python3 tools/site/check_docs.py --strict     # warnings are errors
python3 tools/site/check_docs.py --release ussuri
python3 tools/site/check_docs.py --list-rules
```

## Learning blocks: check_learning.py

The quizzes, scenarios, "To remember" cards and final challenges live in the front matter of the pages (format:
[CONTRIBUTING.md](../../CONTRIBUTING.md#definitions-on-hover-and-quizzes)). `check_learning.py` parses them with PyYAML
and fails on: an unknown key or a wrong type; an `answer` that is not an index of `options`; a scenario without
exactly one `best` choice among three, or with another verdict than `best`, `risky`, `avoid`; a `remember` list
outside 3 to 5 items; a text with Markdown backticks, a bracketed `[CODE]`/`[NOT AVAILABLE]` label, a tag other than
`<code>`, `<strong>`, `<em>` and the evidence chips, or an unbalanced tag; a quiz or scenario `see` that is not a bare
anchor (check_site then checks that the anchor exists); `challenges` outside `start/learning-journey.md`, a stage id
missing or unknown, or a challenge `see` whose page has no Markdown source in the release.

```bash
python3 tools/site/check_learning.py
python3 tools/site/check_learning.py --release 2023.1
```

## Built-portal checks: check_site.py

`zensical build --strict` already fails on a broken link or anchor in the Markdown. `check_site.py` looks at the
files written to `site/`, whatever produced them (Markdown, templates of `overrides/`, the theme, `releases.py`). It
reads the whole portal at once, so a link from one release to another, such as those of the release selector, is
checked like any other link.

On every page of the portal:

| Rule | Level | What is checked |
|---|---|---|
| `link-file` | error | Every internal `href` and `src` of every HTML page, and every `url()` of every stylesheet, points to a file of the portal. |
| `link-anchor` | error | Every internal link with a fragment points to an element `id` of the target page. |
| `external-resource` | error | No page or stylesheet loads a script, a stylesheet, a font, an image or a frame from another origin. Plain `<a href>` links to other sites are allowed and their hosts are listed in the summary. |
| `runtime-request` | error | Nothing makes the theme script call another host in the browser: a page with a Mermaid diagram loads the vendored Mermaid library, and no element requests the GitHub repository statistics. Loading Mermaid on a page without a diagram is a warning. |
| `page-empty` | error | No page has an empty content area. A page with a title and no other text is a warning. |
| `canonical` | error | The canonical address of a page is the address of that page, under the prefix of its release. |
| `duplicate-id` | warning | An `id` is used twice in a page. |

On the site of each available release (`site/<id>/`):

| Rule | Level | What is checked |
|---|---|---|
| `page-missing` | error | Every Markdown page under `docs/<id>/` has its built page. |
| `search-index` | error | `<id>/search.json` exists, is valid JSON, has at least one entry per page, and every entry points to an existing page and anchor of the same release. |
| `sitemap` | error | Every URL of `<id>/sitemap.xml` is a page of that release. |
| `updates` | error | Every entry of `<id>/assets/data/updates.json` is a built page. |

On the root of the portal:

| Rule | Level | What is checked |
|---|---|---|
| `portal-root` | error | `versions.json` is valid JSON and says what `versions.toml` says. The landing page links to the default release (`data-portal-default`), and that release is built. The not-found page knows the same releases with the same statuses, sends the addresses without a release to the release named by `unprefixed`, and its list of addresses to redirect is exactly the pages of that release. Every available release is built. Every planned release has its page, which names the release and says that it is not available yet, and has no other file. No directory of `site/` belongs to no release. |

The summary gives, for each release, the number of pages built and of search entries, then the number of pages,
internal links, links with an anchor and element ids of the portal, and the hosts of the external links.

```bash
python3 tools/site/check_site.py site
python3 tools/site/check_site.py site --strict
python3 tools/site/check_site.py site --release ussuri    # after a build with --release
```

## Continuous integration

[.github/workflows/docs.yml](../../.github/workflows/docs.yml) runs on pull requests and on pushes to `main` that
change `docs/`, `overrides/`, `tools/site/`, `versions.toml`, `zensical.base.toml`, `requirements-docs.txt`,
`Makefile` or the workflow itself (pull requests: also `README.md` and `CONTRIBUTING.md`, whose links are checked). It can also be started by
hand (Actions, "Docs", "Run workflow").

| Job | When | What it does |
|---|---|---|
| `build` | Always | Full-history checkout (the "Last updated" dates come from the Git history), Python 3.13, `make docs-deps`, `make docs-check STRICT=1`, `make docs-build STRICT=1`. One run covers every release of `versions.toml` and the root of the portal; adding a release needs no change of the workflow. |
| `deploy` | Push to `main`, or manual run on `main`, after `build` succeeded | `actions/configure-pages`, then `actions/deploy-pages` to the `github-pages` environment. |

- Both check scripts run with `--strict`: a warning (a missing `description`, a leftover `<!-- TODO editorial`
  marker, a duplicate `id` in a built page) fails the `build` job like an error.
- A pull request is never deployed. Its built portal is uploaded as the artifact `site`, kept 7 days: download it
  from the page of the run, unpack it and serve it with `python3 tools/site/serve_site.py <unpacked directory>`
  (a path relative to the repository root, or an absolute path).
- On `main` the `build` job uploads the Pages artifact that `deploy` publishes. The artifact is kept 1 day (the
  default of `actions/upload-pages-artifact`).
- The workflow token is read-only (`contents: read`). Only the `deploy` job gets more: `pages: write` and
  `id-token: write`.
- The pip download cache is keyed on `requirements-docs.txt`. The Mermaid bundle is cached with a key computed
  from `fetch_vendor.py`, which pins its version and checksums; `fetch_vendor.py` verifies the file in both cases.
- A newer commit on a pull request cancels the run in progress for that pull request. On `main` a run that has
  started always finishes, deployment included, and the next one waits. If several runs are waiting, only the newest
  is kept.

Actions used. The workflow references each one by the full commit of the version shown, with the version in a
comment: with a version tag such as `@v4`, every run in this repository ended with the conclusion `startup_failure`
before any job started, and the same step referenced by commit started.

| Action | Version |
|---|---|
| `actions/checkout` | `v7` |
| `actions/setup-python` | `v6` |
| `actions/cache` | `v6` |
| `actions/upload-artifact` | `v7` |
| `actions/upload-pages-artifact` | `v5` |
| `actions/configure-pages` | `v6` |
| `actions/deploy-pages` | `v5` |

### One-time setup: enable GitHub Pages

A repository administrator does this once:

1. Open **Settings**, then **Pages**.
2. Under **Build and deployment**, set **Source** to **GitHub Actions**.

GitHub creates the `github-pages` environment and, by default, limits its deployments to the default branch. The
workflow deploys from `main`, which must stay the default branch or be added under **Settings**, **Environments**,
**github-pages**, **Deployment branches**.

For a private repository:

- GitHub Pages needs a paid plan: GitHub Pro for a repository owned by a personal account, GitHub Team or GitHub
  Enterprise for a repository owned by an organization. With GitHub Free, Pages is offered for public repositories
  only.
- The published site is public even though the repository is private. Restricting the site to people who can read
  the repository requires GitHub Enterprise Cloud and a repository owned by an organization.

The other way is to make the repository public: Pages is then available with every plan.

The expected address is `https://ozarland.github.io/kolla-ansible-academy/`, the `site_url` of `zensical.base.toml`
(the address of the portal root; each release is one level below). If the portal is published at another address
(custom domain, or a generated address when access is restricted), set `site_url` to it: the canonical links, the
sitemaps and the not-found page use it.

After the setup, start a deployment: use "Run workflow" on `main` (Actions, "Docs"), or push a change of the site
to `main`. Re-running only the failed `deploy` job of an earlier run works while the Pages artifact of that run
still exists (1 day); after that, re-run all the jobs of the run.

### Before GitHub Pages is enabled

- Pull requests are not affected: they only run `build`.
- On `main`, `build` passes and uploads the Pages artifact. `deploy` then fails at its first step, "Check the
  GitHub Pages configuration" (`actions/configure-pages`), with this error:

  ```text
  Get Pages site failed. Please verify that the repository has Pages enabled and configured to build using GitHub Actions, or consider exploring the `enablement` parameter for this action.
  ```

  The message ends with the error returned by the GitHub API. Nothing is published and the run on `main` is
  marked as failed until the setup above is done.
- The workflow does not enable Pages itself: the `enablement` option of `actions/configure-pages` requires a token
  other than the workflow token (`GITHUB_TOKEN`), and the workflow uses no other token.

## Maintenance

- **Warnings as errors in CI.** CI runs `make docs-check STRICT=1` and `make docs-build STRICT=1`: every warning
  of the two check scripts fails the build. Without `STRICT=1`, which is the default of the Makefile, warnings are
  printed and do not fail the run.
- **Upgrading Zensical.** `requirements-docs.txt` pins Zensical and every package it depends on. Install the new
  version in an empty virtual environment, replace the pins with the output of `pip freeze`, then run
  `make docs-deps docs-check docs-build` and look at a few pages with `make docs-serve`. Compare
  `overrides/partials/header.html` with `partials/header.html` of the new theme (it is a copy with the release
  selector added), and try the release selector, a planned release and an old address with `make docs-preview`.
- **Upgrading Mermaid.** See `overrides/assets/vendor/mermaid/README.md`. Changing `fetch_vendor.py` changes the cache
  key in CI.
- **Upgrading the actions.** The workflow references each action by commit. To upgrade, replace the commit with
  the one of the new version tag and update the comment, one action at a time, and read the release notes for
  changed inputs.
- **Required status checks.** The workflow only runs when one of the listed paths changes. If the `build` job is
  made a required check in a branch protection rule, a pull request that touches none of these paths waits for a
  check that never starts. Either leave the check optional or remove the `paths` filter of `pull_request`.
- **Private repository.** Runs on GitHub-hosted runners count against the Actions minutes of the account.
