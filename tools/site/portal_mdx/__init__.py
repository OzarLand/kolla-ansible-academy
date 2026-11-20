r"""Markdown helpers of the Kolla-Ansible Academy portal.

``zensical.base.toml`` loads this package as one Python-Markdown extension
(``portal_mdx``) and uses :func:`portal_mdx.slug.gh_slugify` for heading ids.
The build runs with ``PYTHONPATH=tools/site`` so the package is importable.

The extension bundles ten small, independent features; each can be turned
off with an option of the same name:

``lists``
    lists written for GitHub (two- or three-space nesting, no blank line
    before a list) are read the way GitHub reads them (:mod:`portal_mdx.lists`).
``pipes``
    ``\\|`` in the code spans of a table shows as ``|``, as on GitHub
    (:mod:`portal_mdx.pipes`).
``breaks``
    long paths and line ranges in the code spans of a table may wrap after
    ``/`` and ``,`` (:mod:`portal_mdx.breaks`).
``evidence``
    ``[CODE]`` and ``[NOT AVAILABLE]`` become chips (:mod:`portal_mdx.evidence`).
``placeholders``
    a tag-shaped placeholder such as ``<svc>`` in running text stays visible
    instead of being swallowed as an unknown HTML element
    (:mod:`portal_mdx.placeholders`).
``anchors``
    repeated headings get GitHub's ``-1``, ``-2`` suffixes
    (:mod:`portal_mdx.anchors`).
``severity``
    severity cells of the risk tables get a class (:mod:`portal_mdx.severity`).
``impact``
    a code span that is exactly an impact class name gets a class
    (:mod:`portal_mdx.impact`).
``cites``
    a code span that is a source citation (``path:line``) gets a class, so
    that citations read more quietly than commands (:mod:`portal_mdx.cites`).
``labels``
    the cells of a table of four columns or more carry their column name, so
    that a phone shows each row as a card (:mod:`portal_mdx.labels`).

None of them changes the text of a page: the Markdown source stays the single
source of truth and renders the same way on github.com.
"""

from __future__ import annotations

from markdown import Extension, Markdown

from .anchors import AnchorsExtension
from .breaks import TableBreaksExtension
from .cites import CitesExtension
from .labels import LabelsExtension
from .evidence import EvidenceExtension
from .impact import ImpactExtension
from .lists import GithubListsExtension
from .pipes import TablePipesExtension
from .placeholders import PlaceholdersExtension
from .severity import SeverityExtension
from .slug import GithubSlugger, gh_slug, gh_slugify

__all__ = [
    "PortalExtension",
    "makeExtension",
    "gh_slug",
    "gh_slugify",
    "GithubSlugger",
]


class PortalExtension(Extension):
    def __init__(self, **kwargs: object) -> None:
        self.config = {
            "lists": [True, "Read GitHub-style nested lists as GitHub does"],
            "pipes": [True, "Show an escaped pipe in table code spans as a pipe"],
            "breaks": [True, "Optional line breaks after / and , in table code spans"],
            "evidence": [True, "Render [CODE] and [NOT AVAILABLE] as chips"],
            "placeholders": [True, "Show <name> placeholders that are not HTML elements as text"],
            "anchors": [True, "GitHub suffixes (-1, -2) for repeated headings"],
            "severity": [True, "Add a class to severity cells of risk tables"],
            "impact": [True, "Add a class to code spans that name an impact class"],
            "cites": [True, "Add a class to code spans that are path:line citations"],
            "labels": [True, "Copy column names onto the cells of wide tables"],
        }
        super().__init__(**kwargs)

    def extendMarkdown(self, md: Markdown) -> None:
        md.registerExtension(self)
        if self.getConfig("lists"):
            GithubListsExtension().extendMarkdown(md)
        if self.getConfig("pipes"):
            TablePipesExtension().extendMarkdown(md)
        if self.getConfig("breaks"):
            TableBreaksExtension().extendMarkdown(md)
        if self.getConfig("evidence"):
            EvidenceExtension().extendMarkdown(md)
        if self.getConfig("placeholders"):
            PlaceholdersExtension().extendMarkdown(md)
        if self.getConfig("anchors"):
            AnchorsExtension().extendMarkdown(md)
        if self.getConfig("severity"):
            SeverityExtension().extendMarkdown(md)
        if self.getConfig("impact"):
            ImpactExtension().extendMarkdown(md)
        if self.getConfig("cites"):
            CitesExtension().extendMarkdown(md)
        if self.getConfig("labels"):
            LabelsExtension().extendMarkdown(md)


def makeExtension(**kwargs: object) -> PortalExtension:
    return PortalExtension(**kwargs)
