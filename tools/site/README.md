# Site tooling

The portal is generated from the Markdown under `docs/` by [Zensical](https://github.com/zensical/zensical) 0.1.2.
This directory holds what the build needs besides the generator: the checks, the pre-build step and the local
Markdown extension. Nothing here holds content.

| File | Role |
|---|---|
| [check_docs.py](check_docs.py) | Checks on the Markdown sources. No build needed, standard library only. |
| [check_site.py](check_site.py) | Checks on the built site. Standard library only. |
| [prebuild.py](prebuild.py) | Writes `docs/assets/data/updates.json` (date of the last commit of each page) and makes sure the vendored Mermaid bundle is in place. |
| [fetch_vendor.py](fetch_vendor.py) | Downloads the pinned Mermaid bundle to `docs/assets/vendor/mermaid/mermaid.min.js` and verifies its checksums. The file is not committed. |
| `portal_mdx/` | Python-Markdown extension enabled in `zensical.toml`. The build finds it through `PYTHONPATH=tools/site`. |
| `tests/` | Unit tests of the files above (`unittest`). |

Related files at the root of the repository: [Makefile](../../Makefile),
[requirements-docs.txt](../../requirements-docs.txt), [zensical.toml](../../zensical.toml), `overrides/` and
[.github/workflows/docs.yml](../../.github/workflows/docs.yml).

## Build locally

Needed: Python 3.11 or newer (CI uses 3.13), `git`, `make`. Only `make docs-deps` needs the network: PyPI for the
build dependencies and `registry.npmjs.org` for the Mermaid bundle.

```bash
python3 -m venv .venv     # once; the Makefile uses .venv when it exists, no activation needed
make docs-deps
make docs-check
make docs-build
make docs-serve           # http://localhost:8000/kolla-ansible-day2/
```

Without `.venv` the Makefile runs `python3` from `PATH`, which is what CI does. `make PYTHON=/path/to/python ...`
forces another interpreter.

| Target | What it runs |
|---|---|
| `docs-deps` | `pip install -r requirements-docs.txt`, then `fetch_vendor.py`. |
| `docs-check` | `check_docs.py`. |
| `docs-build` | The unit tests of `tests/`, `prebuild.py`, `zensical build --clean --strict`, then `check_site.py site`. |
| `docs-test` | The unit tests of `tests/` only (`python3 -m unittest discover -s tools/site/tests`). |
| `docs-serve` | `prebuild.py`, then `zensical serve` (rebuilds on change). `DEV_ADDR=127.0.0.1:8001` moves it. |
| `docs-clean` | Removes `site/`, `.cache/`, `docs/assets/data/updates.json` and the `__pycache__` directories under `tools/`. The Mermaid bundle stays. |

`STRICT=1` (`make docs-check STRICT=1`, `make docs-build STRICT=1`) passes `--strict` to both check scripts:
their warnings become errors. CI runs both targets with `STRICT=1`, so run them the same way before opening a pull
request.

`site/`, `.cache/`, `.venv/`, `docs/assets/data/updates.json` and the Mermaid bundle are generated or downloaded.
They are listed in `.gitignore` and must not be committed.

## Source checks: check_docs.py

The script reads every Markdown page under `docs/` and `zensical.toml`. It also checks the links of `README.md`,
`CONTRIBUTING.md` and this file. It prints the findings by file with their line, then a summary, and exits with 1
when there is at least one error. On GitHub Actions each error is also an annotation on the file.

| Rule | Level | What is checked |
|---|---|---|
| `encoding` | error | The file is UTF-8. |
| `front-matter` | error | The page starts with a front matter block that can be read. |
| `title` | error | The front matter has a non-empty `title`. |
| `description` | error | `description` is not empty and has at most 160 characters. A missing `description` is a warning. |
| `impact` | error | Every `impact` value is one of `read-only`, `writes-config`, `pulls-images`, `restarts-on-drift`, `recreates-containers`, `critical`, `maintenance-window`, `recovery`. |
| `tags` | warning | `tags` is a list of lowercase names. |
| `link-file` | error | The target of a relative link or image exists, with the same letter case. |
| `link-anchor` | error | The fragment of a link is a heading anchor of the target or an explicit `id` (for example `<a id="r12"></a>`). |
| `link-style` | error | Links between pages are relative, stay inside `docs/` and point to a file, not to a directory or to the published URL. |
| `link-reference` | error | A reference-style link `[text][label]` uses a label defined in the file. |
| `link-repo-file` | error | An absolute link to a file of this repository on `main` points to a file that exists. |
| `code-language` | error | Every fenced code block has a language and is closed. |
| `removed-path` | error | No reference to a path of the former layout (`annex/`, `docs/01-...` to `docs/10-...`). Inside an HTML comment it is a warning. |
| `callout` | error | Callouts are GitHub alerts of the five types `[!NOTE]`, `[!TIP]`, `[!IMPORTANT]`, `[!WARNING]`, `[!CAUTION]`, with the marker alone on the first line of the blockquote. |
| `todo-editorial` | warning | No `<!-- TODO editorial` marker is left. |
| `nav` | error | Every page is listed in the `nav` of `zensical.toml`, and every `nav` entry exists, once. |
| `config` | error | `zensical.toml` exists and can be read. |

Heading anchors are computed the way github.com computes them: lowercase, every character that is not a letter,
a digit, an underscore, a hyphen or a space is dropped, each space becomes a hyphen, and a repeated heading gets
`-1`, `-2`. Lines inside fenced code are not headings. `zensical.toml` configures the site to produce the same
anchors, so a link that passes here works on github.com and on the site.

```bash
python3 tools/site/check_docs.py              # warnings do not fail the run
python3 tools/site/check_docs.py --strict     # warnings are errors
python3 tools/site/check_docs.py --list-rules
```

## Built-site checks: check_site.py

`zensical build --strict` already fails on a broken link or anchor in the Markdown. `check_site.py` looks at the
files written to `site/`, whatever produced them (Markdown, templates of `overrides/`, the theme).

| Rule | Level | What is checked |
|---|---|---|
| `link-file` | error | Every internal `href` and `src` of every HTML page, and every `url()` of every stylesheet, points to a file of the site. |
| `link-anchor` | error | Every internal link with a fragment points to an element `id` of the target page. |
| `external-resource` | error | No page or stylesheet loads a script, a stylesheet, a font, an image or a frame from another origin. Plain `<a href>` links to other sites are allowed and their hosts are listed in the summary. |
| `runtime-request` | error | Nothing makes the theme script call another host in the browser: a page with a Mermaid diagram loads the vendored Mermaid library, and no element requests the GitHub repository statistics. Loading Mermaid on a page without a diagram is a warning. |
| `page-missing` | error | Every Markdown page under `docs/` has its built page. |
| `page-empty` | error | No page has an empty content area. A page with a title and no other text is a warning. |
| `search-index` | error | `search.json` exists, is valid JSON, has at least one entry per page, and every entry points to an existing page and anchor. |
| `sitemap` | error | Every URL of `sitemap.xml` is a page of the site. |
| `updates` | error | Every entry of `assets/data/updates.json` is a built page. |
| `duplicate-id` | warning | An `id` is used twice in a page. |

The summary gives the number of pages, internal links, links with an anchor, element ids, search entries, and the
hosts of the external links.

```bash
python3 tools/site/check_site.py site
python3 tools/site/check_site.py site --strict
```

## Continuous integration

[.github/workflows/docs.yml](../../.github/workflows/docs.yml) runs on pull requests and on pushes to `main` that
change `docs/`, `overrides/`, `tools/site/`, `zensical.toml`, `requirements-docs.txt`, `Makefile` or the workflow
itself (pull requests: also `README.md` and `CONTRIBUTING.md`, whose links are checked). It can also be started by
hand (Actions, "Docs", "Run workflow").

| Job | When | What it does |
|---|---|---|
| `build` | Always | Full-history checkout (the "Last updated" dates come from the Git history), Python 3.13, `make docs-deps`, `make docs-check STRICT=1`, `make docs-build STRICT=1`. |
| `deploy` | Push to `main`, or manual run on `main`, after `build` succeeded | `actions/configure-pages`, then `actions/deploy-pages` to the `github-pages` environment. |

- Both check scripts run with `--strict`: a warning (a missing `description`, a leftover `<!-- TODO editorial`
  marker, a duplicate `id` in a built page) fails the `build` job like an error.
- A pull request is never deployed. Its built site is uploaded as the artifact `site`, kept 7 days: download it from
  the page of the run, unpack it and serve it with `python3 -m http.server --directory <unpacked directory>`.
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

The expected address is `https://ozarland.github.io/kolla-ansible-day2/`, the `site_url` of `zensical.toml`. If the
site is published at another address (custom domain, or a generated address when access is restricted), set
`site_url` to it: the canonical links and the sitemap use it.

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
  `make docs-deps docs-check docs-build` and look at a few pages with `make docs-serve`.
- **Upgrading Mermaid.** See `docs/assets/vendor/mermaid/README.md`. Changing `fetch_vendor.py` changes the cache
  key in CI.
- **Upgrading the actions.** The workflow references each action by commit. To upgrade, replace the commit with
  the one of the new version tag and update the comment, one action at a time, and read the release notes for
  changed inputs.
- **Required status checks.** The workflow only runs when one of the listed paths changes. If the `build` job is
  made a required check in a branch protection rule, a pull request that touches none of these paths waits for a
  check that never starts. Either leave the check optional or remove the `paths` filter of `pull_request`.
- **Private repository.** Runs on GitHub-hosted runners count against the Actions minutes of the account.
