#!/usr/bin/env python3
"""Releases of the portal: the registry and what is generated from it.

The portal is one self-contained site per release, published under its own
URL prefix, plus a small root site:

    site/index.html          landing page; opens the default release
    site/404.html            not-found page of the whole portal; redirects the
                             addresses published before the portal had releases
    site/versions.json       the registry, for scripts and other tools
    site/sitemap.xml         index of the sitemaps of the releases
    site/assets/             theme files used by the root pages
    site/<id>/               site of an available release (built by Zensical
                             from docs/<id>/)
    site/<id>/index.html     the only page of a planned release ("coming soon")

Sources:

    versions.toml            the registry: every release, the default one
    zensical.base.toml       site configuration shared by all releases
    docs/<id>.toml           settings of one available release (nav, description)
    docs/<id>/               its Markdown
    overrides/               templates and static files shared by all releases

This module reads the registry and writes what Zensical needs. Zensical only
accepts a docs directory inside the directory of its configuration file, and
its TOML format has no include, so the configurations that are built are
generated at the repository root and are git-ignored:

    .zensical.<id>.toml      zensical.base.toml merged with docs/<id>.toml
    .zensical._root.toml     configuration of the root site
    .build/root/docs/        Markdown stubs of the root site (landing page,
                             one page per planned release); the text of these
                             pages is in overrides/landing.html and
                             overrides/planned.html
    .build/root/site/        the root site as built, before `assemble` copies
                             it into site/

Command line (tools/site/build.py calls the same functions):

    python3 tools/site/releases.py list [--status available|planned|all]
    python3 tools/site/releases.py default
    python3 tools/site/releases.py config <id>     write .zensical.<id>.toml
    python3 tools/site/releases.py root            write the root docs and config
    python3 tools/site/releases.py assemble        copy the root site into site/

Standard library only (Python 3.11 or newer, for tomllib).
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

if sys.version_info < (3, 11):  # pragma: no cover - depends on the interpreter
    sys.exit("releases: Python 3.11 or newer is required (tomllib)")

import tomllib

ROOT = Path(__file__).resolve().parents[2]

REGISTRY_FILE = "versions.toml"
BASE_CONFIG = "zensical.base.toml"
#: Parent of the release directories. A release is DOCS_ROOT/<id>/ and its
#: settings are DOCS_ROOT/<id>.toml.
DOCS_ROOT = "docs"
#: Output directory. The site of a release is SITE_DIR/<id>/.
SITE_DIR = "site"
#: Generated files of the root site (git-ignored).
ROOT_BUILD = ".build/root"
#: Name used for the root site where a release id is expected.
ROOT_NAME = "_root"

AVAILABLE = "available"
PLANNED = "planned"
STATUSES = (AVAILABLE, PLANNED)

#: A release id is a directory name and a URL segment.
ID_PATTERN = re.compile(r"^[a-z0-9]+(?:[.-][a-z0-9]+)*$")
#: Names the root of the built portal uses for something else.
RESERVED_IDS = frozenset({"assets", "search", "index", "404", "versions", "sitemap"})

#: Keys of docs/<id>.toml that the tooling sets itself.
DERIVED_KEYS = ("docs_dir", "site_dir")

#: Theme features that need the navigation or the search of a release; the
#: root site has neither.
ROOT_DROPPED_FEATURES = ("navigation.", "toc.", "search.", "content.action.")

INDEX_NAMES = ("index.md", "README.md")
#: Not pages: generated data of a release (updates.json).
SKIPPED_TOP_DIRS = ("assets",)


class RegistryError(Exception):
    """versions.toml, or a file it refers to, cannot be used."""

    def __init__(self, problems: list[str]) -> None:
        super().__init__("; ".join(problems))
        self.problems = problems


@dataclass(frozen=True)
class Release:
    id: str
    status: str
    openstack: str
    kolla_ansible: str
    title: str
    tag: str = ""

    @property
    def available(self) -> bool:
        return self.status == AVAILABLE

    @property
    def docs_dir(self) -> str:
        return f"{DOCS_ROOT}/{self.id}"

    @property
    def settings_file(self) -> str:
        return f"{DOCS_ROOT}/{self.id}.toml"

    def as_dict(self) -> dict[str, str]:
        return {
            "id": self.id,
            "status": self.status,
            "title": self.title,
            "openstack": self.openstack,
            "kolla_ansible": self.kolla_ansible,
            "tag": self.tag,
        }


@dataclass(frozen=True)
class Registry:
    releases: tuple[Release, ...]
    default: str
    unprefixed: str

    def get(self, release_id: str) -> Release | None:
        return next((r for r in self.releases if r.id == release_id), None)

    @property
    def available(self) -> tuple[Release, ...]:
        return tuple(r for r in self.releases if r.available)

    @property
    def planned(self) -> tuple[Release, ...]:
        return tuple(r for r in self.releases if not r.available)

    @property
    def ids(self) -> tuple[str, ...]:
        return tuple(r.id for r in self.releases)


# --- registry ---------------------------------------------------------------


def parse_registry(data: object) -> Registry:
    """Build the registry from the content of versions.toml.

    Raises RegistryError with every problem found, not only the first one.
    """
    problems: list[str] = []
    if not isinstance(data, dict):
        raise RegistryError(["the file is not a TOML table"])
    blocks = data.get("release")
    if not isinstance(blocks, list) or not blocks:
        raise RegistryError(["no [[release]] block"])

    known = {"id", "status", "openstack", "kolla_ansible", "tag", "title"}
    releases: list[Release] = []
    seen: set[str] = set()
    for number, block in enumerate(blocks, 1):
        if not isinstance(block, dict):
            problems.append(f"[[release]] block {number} is not a table")
            continue
        release_id = block.get("id")
        where = f"release `{release_id}`" if isinstance(release_id, str) else f"[[release]] block {number}"
        if not isinstance(release_id, str) or not ID_PATTERN.match(release_id):
            problems.append(
                f"{where}: `id` must be made of lowercase letters, digits, dots and hyphens"
            )
            continue
        if release_id in RESERVED_IDS or release_id.startswith("_"):
            problems.append(f"{where}: this id is reserved for the root of the portal")
        if release_id in seen:
            problems.append(f"{where}: the id is used twice")
        seen.add(release_id)
        for key in sorted(set(block) - known):
            problems.append(f"{where}: unknown key `{key}`")
        values = {}
        for key in ("status", "openstack", "kolla_ansible", "tag", "title"):
            value = block.get(key, "")
            if not isinstance(value, str):
                problems.append(f"{where}: `{key}` is not a text")
                value = ""
            values[key] = value.strip()
        if values["status"] not in STATUSES:
            problems.append(f"{where}: `status` must be one of: {', '.join(STATUSES)}")
        for key in ("openstack", "kolla_ansible"):
            if not values[key]:
                problems.append(f"{where}: `{key}` is missing")
        if values["status"] == AVAILABLE and not values["tag"]:
            problems.append(f"{where}: an available release needs `tag`, the upstream tag that is studied")
        title = values["title"] or f"{values['openstack']} · Kolla-Ansible {values['kolla_ansible']}"
        releases.append(
            Release(
                id=release_id,
                status=values["status"],
                openstack=values["openstack"],
                kolla_ansible=values["kolla_ansible"],
                title=title,
                tag=values["tag"],
            )
        )

    by_id = {r.id: r for r in releases}
    default = data.get("default")
    if not isinstance(default, str) or default not in by_id:
        problems.append("`default` must be the id of a release of this file")
    elif by_id[default].status != AVAILABLE:
        problems.append(f"`default` is `{default}`, which is not available")
    unprefixed = data.get("unprefixed", default)
    if not isinstance(unprefixed, str) or unprefixed not in by_id:
        problems.append("`unprefixed` must be the id of a release of this file")
    elif by_id[unprefixed].status != AVAILABLE:
        problems.append(f"`unprefixed` is `{unprefixed}`, which is not available")
    for key in sorted(set(data) - {"release", "default", "unprefixed"}):
        problems.append(f"unknown key `{key}`")

    if problems:
        raise RegistryError(problems)
    return Registry(tuple(releases), default, unprefixed)


def load_registry(root: Path = ROOT) -> Registry:
    """Read versions.toml. Raises RegistryError."""
    path = root / REGISTRY_FILE
    try:
        with path.open("rb") as handle:
            data = tomllib.load(handle)
    except FileNotFoundError:
        raise RegistryError([f"{REGISTRY_FILE} does not exist"]) from None
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise RegistryError([f"cannot be read: {exc}"]) from exc
    return parse_registry(data)


def layout_problems(root: Path, registry: Registry) -> list[str]:
    """Differences between the registry and the docs tree.

    An available release has its directory and its settings file; a planned
    release has neither; nothing else sits directly under docs/.
    """
    problems = []
    for release in registry.releases:
        has_dir = (root / release.docs_dir).is_dir()
        has_settings = (root / release.settings_file).is_file()
        if release.available:
            if not has_dir:
                problems.append(f"release `{release.id}` is available but {release.docs_dir}/ does not exist")
            if not has_settings:
                problems.append(f"release `{release.id}` is available but {release.settings_file} does not exist")
        else:
            if has_dir:
                problems.append(
                    f"release `{release.id}` is planned but {release.docs_dir}/ exists: "
                    f"set its status to `{AVAILABLE}`, or remove the directory"
                )
            if has_settings:
                problems.append(
                    f"release `{release.id}` is planned but {release.settings_file} exists: "
                    f"set its status to `{AVAILABLE}`, or remove the file"
                )
    docs = root / DOCS_ROOT
    if docs.is_dir():
        for entry in sorted(docs.iterdir()):
            name = entry.name
            if entry.is_dir():
                if name not in registry.ids:
                    problems.append(f"{DOCS_ROOT}/{name}/ is not a release of {REGISTRY_FILE}")
            elif name.endswith(".toml"):
                if name[: -len(".toml")] not in registry.ids:
                    problems.append(f"{DOCS_ROOT}/{name} does not belong to a release of {REGISTRY_FILE}")
            elif not name.startswith("."):
                problems.append(
                    f"{DOCS_ROOT}/{name}: files belong to a release directory ({DOCS_ROOT}/<id>/), "
                    "shared files to overrides/assets/"
                )
    return problems


# --- configuration ----------------------------------------------------------


def merge(base: dict, override: dict) -> dict:
    """`override` over `base`: tables are merged, everything else is replaced."""
    result = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(result.get(key), dict) and isinstance(value, dict):
            result[key] = merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def load_project(path: Path) -> dict:
    """The `[project]` table of a TOML file. Raises RegistryError."""
    try:
        with path.open("rb") as handle:
            data = tomllib.load(handle)
    except FileNotFoundError:
        raise RegistryError([f"{path.name} does not exist"]) from None
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise RegistryError([f"{path.name} cannot be read: {exc}"]) from exc
    project = data.get("project", {})
    if not isinstance(project, dict):
        raise RegistryError([f"{path.name}: `project` is not a table"])
    return project


def portal_root_url(base: dict) -> str:
    url = base.get("site_url")
    if not isinstance(url, str) or not url:
        raise RegistryError([f"{BASE_CONFIG}: `site_url` (address of the portal root) is missing"])
    return url if url.endswith("/") else url + "/"


def portal_data(registry: Registry, base: dict, current: str) -> dict:
    """`extra.portal` of a built configuration: what the templates read.

    `up` is the path from the base of the built site to the portal root.
    """
    return {
        "kind": "release" if current else "root",
        "current": current,
        "up": "../" if current else "",
        "default": registry.default,
        "root_url": portal_root_url(base),
        "releases": [release.as_dict() for release in registry.releases],
    }


def release_project(root: Path, registry: Registry, release_id: str, site_dir: str = SITE_DIR) -> dict:
    """Configuration of the site of one available release."""
    release = registry.get(release_id)
    if release is None:
        raise RegistryError([f"`{release_id}` is not a release of {REGISTRY_FILE}"])
    if not release.available:
        raise RegistryError([f"release `{release_id}` is planned: it has no site to build"])
    base = load_project(root / BASE_CONFIG)
    own = load_project(root / release.settings_file)
    forbidden = [key for key in DERIVED_KEYS if key in own]
    if forbidden:
        raise RegistryError(
            [f"{release.settings_file}: `{key}` is set by the tooling and must not be set here" for key in forbidden]
        )
    project = merge(base, own)
    project["docs_dir"] = release.docs_dir
    project["site_dir"] = f"{site_dir}/{release.id}"
    if "site_url" not in own:
        project["site_url"] = f"{portal_root_url(base)}{release.id}/"
    if "edit_uri" not in own:
        prefix = base.get("edit_uri", "")
        prefix = prefix if not prefix or prefix.endswith("/") else prefix + "/"
        project["edit_uri"] = f"{prefix}{release.docs_dir}/"
    extra = project.setdefault("extra", {})
    extra["portal"] = portal_data(registry, base, release.id)
    return project


def page_url(rel: Path) -> str:
    """Directory URL of a page, relative to the site root (as Zensical builds it)."""
    if rel.name in INDEX_NAMES:
        parent = rel.parent.as_posix()
        return "" if parent == "." else f"{parent}/"
    return f"{rel.with_suffix('').as_posix()}/"


def page_urls(root: Path, release: Release) -> list[str]:
    """URLs of the pages of an available release, relative to its site root."""
    docs = root / release.docs_dir
    urls = []
    for path in sorted(docs.rglob("*.md")):
        rel = path.relative_to(docs)
        if rel.parts[0] not in SKIPPED_TOP_DIRS:
            urls.append(page_url(rel))
    return urls


def root_project(root: Path, registry: Registry) -> dict:
    """Configuration of the root site: landing, not-found and planned pages."""
    base = load_project(root / BASE_CONFIG)
    project = copy.deepcopy(base)
    project["docs_dir"] = f"{ROOT_BUILD}/docs"
    project["site_dir"] = f"{ROOT_BUILD}/site"
    project["nav"] = ["index.md", *(f"{release.id}/index.md" for release in registry.planned)]
    project.pop("edit_uri", None)
    theme = project.get("theme")
    if isinstance(theme, dict) and isinstance(theme.get("features"), list):
        theme["features"] = [
            feature for feature in theme["features"] if not str(feature).startswith(ROOT_DROPPED_FEATURES)
        ]
    extra = project.setdefault("extra", {})
    portal = portal_data(registry, base, "")
    unprefixed = registry.get(registry.unprefixed)
    portal["unprefixed"] = {
        "release": unprefixed.id,
        "pages": page_urls(root, unprefixed) if (root / unprefixed.docs_dir).is_dir() else [],
    }
    extra["portal"] = portal
    return project


# --- TOML output ------------------------------------------------------------


def _toml_string(value: str) -> str:
    # A JSON string is a TOML basic string, except for U+007F.
    return json.dumps(value, ensure_ascii=False).replace("\x7f", "\\u007F")


def _toml_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, str):
        return _toml_string(value)
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_toml_value(item) for item in value) + "]"
    if isinstance(value, dict):
        if not value:
            return "{}"
        return "{ " + ", ".join(f"{_toml_string(str(k))} = {_toml_value(v)}" for k, v in value.items()) + " }"
    raise TypeError(f"cannot write {type(value).__name__} as TOML")


def dump_toml(project: dict, header: str = "") -> str:
    """TOML text of a `[project]` table (nested tables are written inline)."""
    lines = [f"# {line}".rstrip() for line in header.splitlines()]
    if lines:
        lines.append("")
    lines.append("[project]")
    for key, value in project.items():
        if isinstance(value, list) and value:
            lines.append(f"{_toml_string(key)} = [")
            lines.extend(f"  {_toml_value(item)}," for item in value)
            lines.append("]")
        else:
            lines.append(f"{_toml_string(key)} = {_toml_value(value)}")
    text = "\n".join(lines) + "\n"
    if tomllib.loads(text) != {"project": project}:  # pragma: no cover - guards the writer
        raise RuntimeError("generated TOML does not read back as the configuration")
    return text


def write_if_changed(path: Path, content: str) -> None:
    if not path.is_file() or path.read_text(encoding="utf-8") != content:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def config_path(root: Path, name: str) -> Path:
    return root / f".zensical.{name}.toml"


def write_release_config(root: Path, registry: Registry, release_id: str, site_dir: str = SITE_DIR) -> Path:
    project = release_project(root, registry, release_id, site_dir)
    path = config_path(root, release_id)
    header = (
        f"Generated by tools/site/releases.py from {BASE_CONFIG}, {DOCS_ROOT}/{release_id}.toml\n"
        f"and {REGISTRY_FILE}. Do not edit and do not commit."
    )
    write_if_changed(path, dump_toml(project, header))
    return path


def write_root(root: Path, registry: Registry) -> Path:
    """Write the Markdown stubs and the configuration of the root site."""
    project = root_project(root, registry)
    docs = root / ROOT_BUILD / "docs"
    if docs.exists():
        shutil.rmtree(docs)
    name = project.get("site_name", "")
    stubs = {
        "index.md": {
            "template": "landing.html",
            "title": name,
            "description": project.get("site_description", ""),
        }
    }
    for release in registry.planned:
        stubs[f"{release.id}/index.md"] = {
            "template": "planned.html",
            "title": release.title,
            "description": f"The study of {release.title} is not available yet.",
            "portal_release": release.id,
        }
    for rel, front in stubs.items():
        # A JSON string is a YAML double-quoted scalar.
        lines = [f"{key}: {json.dumps(value, ensure_ascii=False)}" for key, value in front.items()]
        text = "---\n" + "\n".join(lines) + f"\n---\n\n# {front['title']}\n"
        write_if_changed(docs / rel, text)
    path = config_path(root, ROOT_NAME)
    header = (
        f"Generated by tools/site/releases.py from {BASE_CONFIG} and {REGISTRY_FILE}:\n"
        "the root site of the portal. Do not edit and do not commit."
    )
    write_if_changed(path, dump_toml(project, header))
    return path


# --- root of the built portal -----------------------------------------------


def versions_json(registry: Registry) -> list[dict]:
    """Content of site/versions.json.

    The list has the form the tool `mike` writes (`version`, `title`,
    `aliases`), so that other tools can read it; what the portal adds is under
    `properties`.
    """
    return [
        {
            "version": release.id,
            "title": release.title,
            "aliases": [],
            "properties": {
                "status": release.status,
                "default": release.id == registry.default,
                "openstack": release.openstack,
                "kolla_ansible": release.kolla_ansible,
                "tag": release.tag,
            },
        }
        for release in registry.releases
    ]


def sitemap_index(registry: Registry, root_url: str, site: Path) -> str:
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for release in registry.available:
        if (site / release.id / "sitemap.xml").is_file():
            lines.append(f"  <sitemap><loc>{root_url}{release.id}/sitemap.xml</loc></sitemap>")
    lines.append("</sitemapindex>")
    return "\n".join(lines) + "\n"


def assemble(root: Path, registry: Registry, site_dir: str = SITE_DIR) -> list[str]:
    """Copy the built root site into the output directory.

    The sites of the available releases are already in `site_dir`/<id>/.
    Returns the paths written, relative to the output directory.
    """
    built = root / ROOT_BUILD / "site"
    if not (built / "index.html").is_file():
        raise RegistryError([f"{ROOT_BUILD}/site/ is not built: run the build of the root site first"])
    site = root / site_dir
    site.mkdir(parents=True, exist_ok=True)
    written = []

    # Whatever is not a release of the registry is left from an earlier build.
    keep = {release.id for release in registry.available}
    for entry in sorted(site.iterdir()):
        if entry.is_dir() and entry.name not in keep:
            shutil.rmtree(entry)
        elif entry.is_file():
            entry.unlink()

    for name in ("index.html", "404.html"):
        shutil.copyfile(built / name, site / name)
        written.append(name)
    # The vendored Mermaid is not copied: no root page has a diagram.
    shutil.copytree(
        built / "assets",
        site / "assets",
        ignore=lambda directory, names: ["vendor"] if Path(directory) == built / "assets" else [],
    )
    written.append("assets/")
    for release in registry.planned:
        source = built / release.id / "index.html"
        if not source.is_file():
            raise RegistryError([f"the root site has no page for the planned release `{release.id}`"])
        (site / release.id).mkdir()
        shutil.copyfile(source, site / release.id / "index.html")
        written.append(f"{release.id}/index.html")

    base = load_project(root / BASE_CONFIG)
    data = json.dumps(versions_json(registry), indent=2, ensure_ascii=False) + "\n"
    (site / "versions.json").write_text(data, encoding="utf-8")
    (site / "sitemap.xml").write_text(sitemap_index(registry, portal_root_url(base), site), encoding="utf-8")
    written += ["versions.json", "sitemap.xml"]
    return written


# --- command line -------------------------------------------------------------


def select(registry: Registry, release_id: str | None) -> list[Release]:
    """Available releases to build or check: all of them, or the one named."""
    if not release_id:
        return list(registry.available)
    release = registry.get(release_id)
    if release is None:
        raise RegistryError(
            [f"`{release_id}` is not a release of {REGISTRY_FILE} (releases: {', '.join(registry.ids)})"]
        )
    if not release.available:
        raise RegistryError([f"release `{release_id}` is planned: it has no content to build or check"])
    return [release]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Releases of the portal: registry and generated files.")
    parser.add_argument("--root", type=Path, default=ROOT, help="repository root (default: the checkout)")
    commands = parser.add_subparsers(dest="command", required=True)
    listing = commands.add_parser("list", help="print the release ids, one per line")
    listing.add_argument("--status", choices=(*STATUSES, "all"), default="all")
    commands.add_parser("default", help="print the id of the default release")
    config = commands.add_parser("config", help="write .zensical.<id>.toml and print its path")
    config.add_argument("release")
    config.add_argument("--site-dir", default=SITE_DIR)
    commands.add_parser("root", help="write the docs and the configuration of the root site, print the path")
    assembling = commands.add_parser("assemble", help="copy the built root site into the output directory")
    assembling.add_argument("--site-dir", default=SITE_DIR)
    args = parser.parse_args(argv)

    root = args.root.resolve()
    try:
        registry = load_registry(root)
        if args.command == "list":
            for release in registry.releases:
                if args.status in ("all", release.status):
                    print(release.id)
        elif args.command == "default":
            print(registry.default)
        elif args.command == "config":
            print(os.path.relpath(write_release_config(root, registry, args.release, args.site_dir), root))
        elif args.command == "root":
            print(os.path.relpath(write_root(root, registry), root))
        elif args.command == "assemble":
            written = assemble(root, registry, args.site_dir)
            print(f"releases: root of the portal -> {args.site_dir}/ ({len(written)} entries)")
    except RegistryError as error:
        for problem in error.problems:
            print(f"releases: error: {problem}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
