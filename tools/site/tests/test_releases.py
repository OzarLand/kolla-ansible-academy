"""Unit tests for tools/site/releases.py (standard library only).

    python3 -m unittest discover -s tools/site/tests -v
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import releases  # noqa: E402

REGISTRY = """
default = "ussuri"

[[release]]
id = "ussuri"
status = "available"
openstack = "Ussuri"
kolla_ansible = "10.x"
tag = "ussuri-eol"

[[release]]
id = "2023.1"
status = "planned"
openstack = "2023.1 Antelope"
kolla_ansible = "16.x"
"""

BASE = """
[project]
site_name = "Portal"
site_url = "https://example.org/portal/"
site_description = "All releases."
repo_url = "https://github.com/example/portal"
edit_uri = "blob/main/"
extra_css = ["assets/stylesheets/portal.css"]

[project.theme]
custom_dir = "overrides"
features = ["navigation.tabs", "toc.follow", "search.highlight", "content.code.copy", "content.action.view"]

[project.extra]
generator = false

[project.markdown_extensions]
toc.permalink = true
"""

SETTINGS = """
[project]
site_description = "The Ussuri study."
nav = ["index.md", { "Operations" = ["operations/index.md", "operations/reconfigure-nova.md"] }]

[project.theme]
language = "en"
"""


def write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def make_repo(root: Path) -> None:
    write(root, "versions.toml", REGISTRY)
    write(root, "zensical.base.toml", BASE)
    write(root, "docs/ussuri.toml", SETTINGS)
    write(root, "docs/ussuri/index.md", "---\ntitle: Home\n---\n\n# Home\n")
    write(root, "docs/ussuri/operations/index.md", "---\ntitle: Operations\n---\n\n# Operations\n")
    write(root, "docs/ussuri/operations/reconfigure-nova.md", "---\ntitle: Nova\n---\n\n# Nova\n")
    write(root, "docs/ussuri/assets/data/notes.md", "not a page\n")


def parse(text: str) -> releases.Registry:
    return releases.parse_registry(tomllib.loads(text))


class RegistryTest(unittest.TestCase):
    def test_releases_in_order_with_default_title(self) -> None:
        registry = parse(REGISTRY)
        self.assertEqual(registry.ids, ("ussuri", "2023.1"))
        self.assertEqual(registry.default, "ussuri")
        self.assertEqual(registry.unprefixed, "ussuri")  # defaults to the default release
        self.assertEqual([r.id for r in registry.available], ["ussuri"])
        self.assertEqual([r.id for r in registry.planned], ["2023.1"])
        self.assertEqual(registry.get("ussuri").title, "Ussuri · Kolla-Ansible 10.x")
        self.assertEqual(registry.get("2023.1").title, "2023.1 Antelope · Kolla-Ansible 16.x")
        self.assertEqual(registry.get("2023.1").docs_dir, "docs/2023.1")
        self.assertIsNone(registry.get("victoria"))

    def test_explicit_title_and_unprefixed(self) -> None:
        text = REGISTRY.replace('tag = "ussuri-eol"', 'tag = "ussuri-eol"\ntitle = "Ussuri"')
        text = text.replace('default = "ussuri"', 'default = "ussuri"\nunprefixed = "ussuri"')
        self.assertEqual(parse(text).get("ussuri").title, "Ussuri")

    def assert_problem(self, text: str, expected: str) -> None:
        with self.assertRaises(releases.RegistryError) as caught:
            parse(text)
        self.assertTrue(
            any(expected in problem for problem in caught.exception.problems), caught.exception.problems
        )

    def test_problems_are_reported(self) -> None:
        self.assert_problem("", "no [[release]] block")
        self.assert_problem(REGISTRY.replace('id = "ussuri"', 'id = "Ussuri"'), "lowercase")
        self.assert_problem(REGISTRY.replace('id = "2023.1"', 'id = "2023/1"'), "lowercase")
        self.assert_problem(REGISTRY.replace('id = "2023.1"', 'id = "assets"'), "reserved")
        self.assert_problem(REGISTRY.replace('id = "2023.1"', 'id = "ussuri"'), "used twice")
        self.assert_problem(REGISTRY.replace('status = "planned"', 'status = "soon"'), "`status` must be one of")
        self.assert_problem(REGISTRY.replace('tag = "ussuri-eol"', ""), "needs `tag`")
        self.assert_problem(REGISTRY.replace('openstack = "Ussuri"', ""), "`openstack` is missing")
        self.assert_problem(REGISTRY.replace('default = "ussuri"', 'default = "2023.1"'), "not available")
        self.assert_problem(REGISTRY.replace('default = "ussuri"', 'default = "x"'), "`default` must be")
        self.assert_problem(REGISTRY.replace('default = "ussuri"', 'default = "ussuri"\nunprefixed = "2023.1"'), "`unprefixed`")
        self.assert_problem(REGISTRY + 'date = "2027"\n', "unknown key `date`")
        self.assert_problem(REGISTRY.replace('default = "ussuri"', 'default = "ussuri"\nlatest = "x"'), "unknown key `latest`")

    def test_every_problem_is_listed_at_once(self) -> None:
        text = REGISTRY.replace('tag = "ussuri-eol"', "").replace('status = "planned"', 'status = "soon"')
        with self.assertRaises(releases.RegistryError) as caught:
            parse(text)
        self.assertEqual(len(caught.exception.problems), 2)

    def test_the_registry_of_the_repository(self) -> None:
        registry = releases.load_registry(releases.ROOT)
        self.assertIn(registry.default, [r.id for r in registry.available])
        self.assertEqual(releases.layout_problems(releases.ROOT, registry), [])
        for release in registry.planned:
            self.assertFalse((releases.ROOT / release.docs_dir).exists(), release.id)


    def test_readme_lists_the_available_releases(self) -> None:
        registry = releases.load_registry(releases.ROOT)
        readme = (releases.ROOT / "README.md").read_text(encoding="utf-8")
        section = readme.split("## Releases", 1)[1].split("\n## ", 1)[0]
        listed = {}
        for row in section.splitlines():
            cells = [cell.strip() for cell in row.strip("|").split("|")]
            if row.startswith("| `") and len(cells) >= 2:
                listed[cells[0].strip("`")] = cells[1]
        self.assertEqual(
            listed,
            {release.id: release.openstack for release in registry.available},
            "the table of the section 'Releases' of README.md does not list the available releases of versions.toml",
        )


class RepoTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        make_repo(self.root)
        self.registry = releases.load_registry(self.root)


class LayoutTest(RepoTest):
    def test_consistent_tree(self) -> None:
        self.assertEqual(releases.layout_problems(self.root, self.registry), [])

    def test_differences(self) -> None:
        write(self.root, "docs/2023.1/index.md", "# Home\n")  # planned, with content
        write(self.root, "docs/victoria/index.md", "# Home\n")  # not registered
        write(self.root, "docs/victoria.toml", "[project]\n")
        write(self.root, "docs/index.md", "# Stray\n")
        (self.root / "docs/ussuri.toml").unlink()
        problems = "\n".join(releases.layout_problems(self.root, self.registry))
        self.assertIn("`2023.1` is planned but docs/2023.1/ exists", problems)
        self.assertIn("docs/victoria/ is not a release", problems)
        self.assertIn("docs/victoria.toml does not belong to a release", problems)
        self.assertIn("docs/index.md: files belong to a release directory", problems)
        self.assertIn("`ussuri` is available but docs/ussuri.toml does not exist", problems)


class ConfigTest(RepoTest):
    def test_release_configuration(self) -> None:
        project = releases.release_project(self.root, self.registry, "ussuri")
        self.assertEqual(project["docs_dir"], "docs/ussuri")
        self.assertEqual(project["site_dir"], "site/ussuri")
        self.assertEqual(project["site_url"], "https://example.org/portal/ussuri/")
        self.assertEqual(project["edit_uri"], "blob/main/docs/ussuri/")
        self.assertEqual(project["site_description"], "The Ussuri study.")  # of the release
        self.assertEqual(project["site_name"], "Portal")  # of the base
        # Tables are merged, lists are replaced.
        self.assertEqual(project["theme"]["custom_dir"], "overrides")
        self.assertEqual(project["theme"]["language"], "en")
        self.assertEqual(project["nav"][0], "index.md")
        portal = project["extra"]["portal"]
        self.assertFalse(project["extra"]["generator"])
        self.assertEqual((portal["kind"], portal["current"], portal["up"]), ("release", "ussuri", "../"))
        self.assertEqual(portal["root_url"], "https://example.org/portal/")
        self.assertEqual([r["id"] for r in portal["releases"]], ["ussuri", "2023.1"])
        self.assertEqual(portal["releases"][1]["status"], "planned")

    def test_release_may_override_site_url_and_edit_uri(self) -> None:
        write(self.root, "docs/ussuri.toml", SETTINGS.replace("nav =", 'site_url = "https://u.example/"\nedit_uri = "edit/x/"\nnav ='))
        project = releases.release_project(self.root, self.registry, "ussuri")
        self.assertEqual((project["site_url"], project["edit_uri"]), ("https://u.example/", "edit/x/"))

    def test_derived_keys_are_refused(self) -> None:
        write(self.root, "docs/ussuri.toml", SETTINGS.replace("nav =", 'docs_dir = "docs"\nnav ='))
        with self.assertRaises(releases.RegistryError) as caught:
            releases.release_project(self.root, self.registry, "ussuri")
        self.assertIn("`docs_dir` is set by the tooling", str(caught.exception))

    def test_planned_or_unknown_release_has_no_configuration(self) -> None:
        for name in ("2023.1", "victoria"):
            with self.assertRaises(releases.RegistryError):
                releases.release_project(self.root, self.registry, name)
        with self.assertRaises(releases.RegistryError):
            releases.select(self.registry, "2023.1")
        self.assertEqual([r.id for r in releases.select(self.registry, None)], ["ussuri"])

    def test_written_configuration_reads_back(self) -> None:
        path = releases.write_release_config(self.root, self.registry, "ussuri")
        self.assertEqual(path, self.root / ".zensical.ussuri.toml")
        text = path.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("# Generated by tools/site/releases.py"))
        self.assertEqual(
            tomllib.loads(text)["project"], releases.release_project(self.root, self.registry, "ussuri")
        )
        stamp = path.stat().st_mtime_ns
        releases.write_release_config(self.root, self.registry, "ussuri")
        self.assertEqual(path.stat().st_mtime_ns, stamp)  # not rewritten

    def test_toml_writer(self) -> None:
        project = {
            "text": 'quote " backslash \\ tab \t line\nbreak · é \x7f',
            "flag": True,
            "off": False,
            "number": 3,
            "ratio": 0.5,
            "empty": [],
            "table": {"a.b": {"c": [1, {"d": "e"}]}, "nothing": {}},
            "list": ["x", {"Title": ["a.md", {"Sub": "b.md"}]}],
        }
        self.assertEqual(tomllib.loads(releases.dump_toml(project, "note"))["project"], project)
        with self.assertRaises(TypeError):
            releases.dump_toml({"when": object()})

    def test_page_urls(self) -> None:
        self.assertEqual(
            releases.page_urls(self.root, self.registry.get("ussuri")),
            ["", "operations/", "operations/reconfigure-nova/"],
        )


class RootTest(RepoTest):
    def test_root_configuration_and_stubs(self) -> None:
        path = releases.write_root(self.root, self.registry)
        project = tomllib.loads(path.read_text(encoding="utf-8"))["project"]
        self.assertEqual(path.name, ".zensical._root.toml")
        self.assertEqual(project["docs_dir"], ".build/root/docs")
        self.assertEqual(project["site_dir"], ".build/root/site")
        self.assertEqual(project["site_url"], "https://example.org/portal/")
        self.assertEqual(project["nav"], ["index.md", "2023.1/index.md"])
        self.assertNotIn("edit_uri", project)
        self.assertEqual(project["theme"]["features"], ["content.code.copy"])
        portal = project["extra"]["portal"]
        self.assertEqual((portal["kind"], portal["current"], portal["up"]), ("root", "", ""))
        self.assertEqual(
            portal["unprefixed"],
            {"release": "ussuri", "pages": ["", "operations/", "operations/reconfigure-nova/"]},
        )
        docs = self.root / ".build/root/docs"
        self.assertEqual(
            sorted(p.relative_to(docs).as_posix() for p in docs.rglob("*.md")), ["2023.1/index.md", "index.md"]
        )
        stub = (docs / "2023.1/index.md").read_text(encoding="utf-8")
        self.assertIn('template: "planned.html"', stub)
        self.assertIn('portal_release: "2023.1"', stub)
        self.assertIn("# 2023.1 Antelope · Kolla-Ansible 16.x", stub)
        self.assertIn('template: "landing.html"', (docs / "index.md").read_text(encoding="utf-8"))

    def test_stub_of_a_release_that_is_no_longer_planned_is_removed(self) -> None:
        releases.write_root(self.root, self.registry)
        write(self.root, "versions.toml", REGISTRY.split("[[release]]\nid = \"2023.1\"")[0])
        releases.write_root(self.root, releases.load_registry(self.root))
        self.assertFalse((self.root / ".build/root/docs/2023.1").exists())

    def fake_root_build(self) -> None:
        for rel in ("index.html", "404.html", "2023.1/index.html", "assets/stylesheets/portal.css",
                    "assets/vendor/mermaid/mermaid.min.js", "search.json", "sitemap.xml"):
            write(self.root, f".build/root/site/{rel}", rel)

    def test_assemble(self) -> None:
        self.fake_root_build()
        write(self.root, "site/ussuri/index.html", "ussuri")
        write(self.root, "site/ussuri/sitemap.xml", "<urlset/>")
        write(self.root, "site/victoria/index.html", "left by an earlier build")
        write(self.root, "site/2023.1/old/index.html", "left by an earlier build")
        write(self.root, "site/stale.txt", "left by an earlier build")
        releases.assemble(self.root, self.registry)
        site = self.root / "site"
        self.assertEqual(
            sorted(p.relative_to(site).as_posix() for p in site.rglob("*") if p.is_file()),
            [
                "2023.1/index.html",
                "404.html",
                "assets/stylesheets/portal.css",
                "index.html",
                "sitemap.xml",
                "ussuri/index.html",
                "ussuri/sitemap.xml",
                "versions.json",
            ],
        )
        versions = json.loads((site / "versions.json").read_text(encoding="utf-8"))
        self.assertEqual(versions, releases.versions_json(self.registry))
        self.assertEqual([v["version"] for v in versions], ["ussuri", "2023.1"])
        self.assertEqual(versions[0]["title"], "Ussuri · Kolla-Ansible 10.x")
        self.assertEqual(versions[0]["aliases"], [])
        self.assertEqual(
            versions[0]["properties"],
            {"status": "available", "default": True, "openstack": "Ussuri", "kolla_ansible": "10.x", "tag": "ussuri-eol"},
        )
        self.assertEqual(versions[1]["properties"]["status"], "planned")
        sitemap = (site / "sitemap.xml").read_text(encoding="utf-8")
        self.assertIn("<loc>https://example.org/portal/ussuri/sitemap.xml</loc>", sitemap)
        self.assertNotIn("2023.1", sitemap)

    def test_assemble_needs_the_root_build(self) -> None:
        with self.assertRaises(releases.RegistryError):
            releases.assemble(self.root, self.registry)


class CommandLineTest(RepoTest):
    def run_main(self, *args: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            status = releases.main(["--root", str(self.root), *args])
        return status, out.getvalue(), err.getvalue()

    def test_commands(self) -> None:
        self.assertEqual(self.run_main("list")[1].split(), ["ussuri", "2023.1"])
        self.assertEqual(self.run_main("list", "--status", "available")[1].split(), ["ussuri"])
        self.assertEqual(self.run_main("list", "--status", "planned")[1].split(), ["2023.1"])
        self.assertEqual(self.run_main("default")[1].strip(), "ussuri")
        self.assertEqual(self.run_main("config", "ussuri")[1].strip(), ".zensical.ussuri.toml")
        self.assertEqual(self.run_main("root")[1].strip(), ".zensical._root.toml")
        status, _, err = self.run_main("config", "2023.1")
        self.assertEqual(status, 1)
        self.assertIn("planned", err)

    def test_unreadable_registry(self) -> None:
        write(self.root, "versions.toml", "default = ")
        status, _, err = self.run_main("list")
        self.assertEqual(status, 1)
        self.assertIn("cannot be read", err)


if __name__ == "__main__":
    unittest.main()
