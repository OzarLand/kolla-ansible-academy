"""Unit tests for what check_docs.py and check_site.py check about releases.

    python3 -m unittest discover -s tools/site/tests -v
"""

from __future__ import annotations

import contextlib
import html
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_docs  # noqa: E402
import check_site  # noqa: E402
import releases  # noqa: E402
from test_releases import REGISTRY, make_repo, write  # noqa: E402

PORTAL = "https://example.org/portal/"

PAGE = """---
title: {title}
description: A page.
---

# {title}

## Details

{body}
"""

WALLABY = """
[[release]]
id = "wallaby"
status = "available"
openstack = "Wallaby"
kolla_ansible = "12.x"
tag = "wallaby-eol"
"""


def page(title: str, body: str = "Text.") -> str:
    return PAGE.format(title=title, body=body)


def run(module, *args: str) -> tuple[int, str]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        status = module.main(list(args))
    return status, out.getvalue()


class Repo(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        make_repo(self.root)
        write(self.root, "docs/ussuri/index.md", page("Home", "[Operations](operations/index.md)"))
        write(self.root, "docs/ussuri/operations/index.md", page("Operations", "[Nova](reconfigure-nova.md#details)"))
        write(self.root, "docs/ussuri/operations/reconfigure-nova.md", page("Nova"))
        (self.root / "docs/ussuri/assets/data/notes.md").unlink()

    def add_wallaby(self) -> None:
        write(self.root, "versions.toml", REGISTRY + WALLABY)
        write(self.root, "docs/wallaby.toml", '[project]\nnav = ["index.md"]\n')
        write(self.root, "docs/wallaby/index.md", page("Home"))


class CheckDocsTest(Repo):
    def check(self, *args: str) -> tuple[int, str]:
        return run(check_docs, "--root", str(self.root), *args)

    def test_consistent_repository(self) -> None:
        status, out = self.check("--strict")
        self.assertEqual(status, 0, out)
        self.assertIn("Releases checked (pages): ussuri (3). Planned, no content: 2023.1.", out)

    def test_every_available_release_is_checked(self) -> None:
        self.add_wallaby()
        write(self.root, "docs/wallaby/extra.md", page("Not in the nav"))
        status, out = self.check()
        self.assertEqual(status, 1)
        self.assertIn("docs/wallaby/extra.md", out)
        self.assertIn("page is not listed in the nav of docs/wallaby.toml", out)
        self.assertIn("ussuri (3), wallaby (2)", out)
        # One release only: the other one is not read.
        status, out = self.check("--release", "ussuri")
        self.assertEqual(status, 0, out)
        self.assertEqual(self.check("--release", "2023.1")[0], 1)  # planned: nothing to check

    def test_registry_and_tree_must_agree(self) -> None:
        write(self.root, "docs/2023.1/index.md", page("Home"))
        write(self.root, "docs/yoga/index.md", page("Home"))
        status, out = self.check()
        self.assertEqual(status, 1)
        self.assertIn("registry", out)
        self.assertIn("`2023.1` is planned but docs/2023.1/ exists", out)
        self.assertIn("docs/yoga/ is not a release of versions.toml", out)

    def test_unreadable_registry(self) -> None:
        write(self.root, "versions.toml", REGISTRY.replace('default = "ussuri"', 'default = "nope"'))
        status, out = self.check()
        self.assertEqual(status, 1)
        self.assertIn("`default` must be the id of a release", out)

    def test_nav_entry_that_does_not_exist(self) -> None:
        write(self.root, "docs/ussuri.toml", '[project]\nnav = ["index.md", "operations/index.md", "operations/reconfigure-nova.md", "gone.md"]\n')
        status, out = self.check()
        self.assertEqual(status, 1)
        self.assertIn("docs/ussuri.toml", out)
        self.assertIn("nav entry `gone.md` does not exist under docs/ussuri/", out)

    def link(self, target: str) -> str:
        """Findings for one link from a wallaby page."""
        self.add_wallaby()
        write(self.root, "docs/wallaby/index.md", page("Home", f"[there]({target})"))
        return self.check()[1]

    def test_relative_link_to_another_release_is_refused(self) -> None:
        out = self.link("../ussuri/operations/reconfigure-nova.md")
        self.assertIn("link-release", out)
        self.assertIn("is a file of another release (docs/ussuri/)", out)
        self.assertIn(f"{PORTAL}ussuri/operations/reconfigure-nova/", out)

    def test_absolute_address_of_a_page_of_another_release_is_accepted(self) -> None:
        for target in (
            PORTAL,
            f"{PORTAL}ussuri/",
            f"{PORTAL}ussuri/operations/",
            f"{PORTAL}ussuri/operations/reconfigure-nova/#details",
            f"{PORTAL}2023.1/",
        ):
            with self.subTest(target=target):
                self.assertIn("check_docs: OK", self.link(target))

    def test_absolute_address_that_leads_nowhere_is_reported(self) -> None:
        out = self.link(f"{PORTAL}ussuri/operations/reconfigure-neutron/")
        self.assertIn("the release `ussuri` has no page `operations/reconfigure-neutron/`", out)
        out = self.link(f"{PORTAL}ussuri/operations/reconfigure-nova/#nowhere")
        self.assertIn("`#nowhere` is not an anchor of docs/ussuri/operations/reconfigure-nova.md", out)
        out = self.link(f"{PORTAL}victoria/")
        self.assertIn("`victoria` is not a release of versions.toml", out)
        out = self.link(f"{PORTAL}2023.1/operations/")
        self.assertIn("the release `2023.1` is planned and has no page other than its home", out)

    def test_absolute_address_inside_the_same_release_is_still_refused(self) -> None:
        out = self.link(f"{PORTAL}wallaby/")
        self.assertIn("points to the site itself; use a relative link", out)


def html_page(title: str, body: str = "<p>Text.</p>", head: str = "", canonical: str = "") -> str:
    link = f'<link rel="canonical" href="{canonical}">' if canonical else ""
    return (
        f"<!doctype html><html><head><title>{title}</title>{link}{head}</head>"
        f"<body><main><article><h1>{title}</h1>{body}</article></main></body></html>"
    )


class CheckSiteTest(Repo):
    """A hand-made portal: one available release, one planned, the root."""

    def setUp(self) -> None:
        super().setUp()
        self.registry = releases.load_registry(self.root)
        self.build()

    def build(self) -> None:
        registry = releases.load_registry(self.root)
        site = "site/"
        pages = {"": "Home", "operations/": "Operations", "operations/reconfigure-nova/": "Nova"}
        for url, title in pages.items():
            up = "../" * (url.count("/") + 1)
            body = f'<p>Text.</p><a href="{up}2023.1/">2023.1</a>'
            write(self.root, f"{site}ussuri/{url}index.html", html_page(title, body, canonical=f"{PORTAL}ussuri/{url}"))
        write(self.root, f"{site}ussuri/search.json", json.dumps({"items": [{"location": url} for url in pages]}))
        locs = "".join(f"<url><loc>{PORTAL}ussuri/{url}</loc></url>" for url in pages)
        write(self.root, f"{site}ussuri/sitemap.xml", f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{locs}</urlset>')
        write(self.root, f"{site}ussuri/assets/data/updates.json", json.dumps({"pages": [{"url": url} for url in pages]}))
        lists = "".join(f'<a href="{r.id}/">{html.escape(r.title)}</a>' for r in registry.releases)
        write(self.root, f"{site}index.html", html_page("Portal", lists, head='<script data-portal-default="ussuri"></script>'))
        data = {
            "root_url": PORTAL,
            "releases": [r.as_dict() for r in registry.releases],
            "unprefixed": {"release": "ussuri", "pages": list(pages)},
        }
        script = f'<script id="portal-not-found" type="application/json">{json.dumps(data)}</script>'
        write(self.root, f"{site}404.html", html_page("Page not found", f'<a href="/portal/ussuri/">Ussuri</a>', head=script))
        for release in registry.planned:
            body = f'<p>The study is not available yet.</p><a href="../ussuri/">Ussuri</a>'
            write(self.root, f"{site}{release.id}/index.html", html_page(html.escape(release.title), body))
        write(self.root, f"{site}versions.json", json.dumps(releases.versions_json(registry)))
        write(self.root, f"{site}sitemap.xml", releases.sitemap_index(registry, PORTAL, self.root / "site"))

    def check(self, *args: str) -> tuple[int, str]:
        return run(check_site, str(self.root / "site"), "--root", str(self.root), *args)

    def test_consistent_portal(self) -> None:
        status, out = self.check("--strict")
        self.assertEqual(status, 0, out)
        self.assertIn("Release ussuri: 3 of 3 Markdown page(s) of docs/ussuri/ are built", out)
        self.assertIn("planned releases with their page: 2023.1", out)

    def expect(self, *messages: str) -> str:
        status, out = self.check()
        self.assertEqual(status, 1, out)
        for message in messages:
            self.assertIn(message, out)
        return out

    def test_versions_json_must_match_the_registry(self) -> None:
        write(self.root, "site/versions.json", json.dumps(releases.versions_json(self.registry)[:1]))
        self.expect("portal-root", "versions.json", "does not match versions.toml")
        write(self.root, "site/versions.json", "{")
        self.expect("not valid JSON")
        (self.root / "site/versions.json").unlink()
        self.expect("the file is missing")

    def test_landing_page_opens_the_default_release(self) -> None:
        text = (self.root / "site/index.html").read_text(encoding="utf-8")
        write(self.root, "site/index.html", text.replace('data-portal-default="ussuri"', 'data-portal-default="2023.1"'))
        self.expect("the landing page links to `2023.1`, the default release is `ussuri`")

    def test_redirections_of_the_not_found_page(self) -> None:
        path = self.root / "site/404.html"
        text = path.read_text(encoding="utf-8")
        write(self.root, "site/404.html", text.replace('"operations/"', '"operations/gone/"'))
        self.expect(
            "redirection target `ussuri/operations/gone/` is not a page of the portal",
            "`operations/` is a page of `ussuri` but an address without a release is not redirected to it",
        )
        write(self.root, "site/404.html", text.replace('"status": "planned"', '"status": "available"'))
        self.expect("the releases it knows do not match versions.toml")
        write(self.root, "site/404.html", html_page("Page not found"))
        self.expect("script #portal-not-found")

    def test_planned_release_has_one_page_that_says_so(self) -> None:
        write(self.root, "site/2023.1/operations/index.html", html_page("Operations"))
        self.expect("a planned release has one page only, found also: 2023.1/operations/index.html")
        (self.root / "site/2023.1/operations/index.html").unlink()
        write(self.root, "site/2023.1/index.html", html_page("Something else"))
        self.expect("does not name the release or does not say that it is not available yet")
        (self.root / "site/2023.1/index.html").unlink()
        self.expect("the page of the planned release `2023.1` is missing", "is not in the site")

    def test_available_release_must_be_built(self) -> None:
        self.add_wallaby()
        self.build()
        out = self.expect("the release `wallaby` is available but its site is not built")
        self.assertIn("page-missing", out)
        # Built alone, a release may link to releases that this run did not build.
        status, out = self.check("--release", "ussuri")
        self.assertEqual(status, 0, out)
        self.assertIn("Not built in this run", out)

    def test_directory_of_no_release(self) -> None:
        write(self.root, "site/victoria/index.html", html_page("Victoria"))
        self.expect("victoria/", "directory of no release of versions.toml")

    def test_links_between_releases_are_checked(self) -> None:
        text = (self.root / "site/ussuri/index.html").read_text(encoding="utf-8")
        write(self.root, "site/ussuri/index.html", text.replace('href="../2023.1/"', 'href="../zed/"'))
        self.expect("link-file", "`zed/index.html` is not in the site")

    def test_search_index_and_sitemap_stay_inside_the_release(self) -> None:
        write(self.root, "site/ussuri/search.json", json.dumps({"items": [{"location": "../2023.1/"}]}))
        self.expect("search-index", "which is not in the site", "page has no entry in ussuri/search.json")
        (self.root / "site/ussuri/search.json").unlink()
        self.expect("ussuri/search.json", "the search index file is missing")

    def test_canonical_address(self) -> None:
        text = (self.root / "site/ussuri/operations/index.html").read_text(encoding="utf-8")
        write(self.root, "site/ussuri/operations/index.html", text.replace(f"{PORTAL}ussuri/operations/", f"{PORTAL}operations/"))
        self.expect("canonical", "is not the address of this page")

    def test_page_without_built_file(self) -> None:
        write(self.root, "docs/ussuri/operations/new.md", page("New"))
        self.expect("page-missing", "docs/ussuri/operations/new.md")


if __name__ == "__main__":
    unittest.main()
