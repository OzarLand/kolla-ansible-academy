"""GitHub-compatible heading ids.

Python-Markdown's ``toc`` extension makes repeated ids unique with ``_1``,
``_2``…; GitHub uses ``-1``, ``-2``…. This tree processor runs just before
``toc`` and gives every heading that has no explicit id the id GitHub would
give it, so the same ``#anchor`` works on github.com and on the site. ``toc``
keeps ids that are already set.

It also keeps ids unique where the corpus puts a stable anchor in front of a
record heading::

    <a id="r12"></a>

    ### R12

While the heading text is only the identifier, the anchor and the heading
would both be ``id="r12"``. The anchor paragraph is then left out of the page
(the heading is the target). As soon as the heading gets a title its id
changes and the anchor is kept.
"""

from __future__ import annotations

import html
import re
import xml.etree.ElementTree as etree

from markdown import Extension, Markdown
from markdown.extensions.toc import remove_fnrefs, render_inner_html, strip_tags
from markdown.treeprocessors import Treeprocessor
from markdown.util import HTML_PLACEHOLDER_RE

from .slug import GithubSlugger

__all__ = ["AnchorsExtension", "makeExtension"]

_HEADING = re.compile(r"^h[1-6]$", re.IGNORECASE)
_EMPTY_ANCHOR = re.compile(r"""^\s*<a\s+id=(["'])([^"']+)\1\s*>\s*</a>\s*$""", re.IGNORECASE)


class GithubAnchorsTreeprocessor(Treeprocessor):
    def _anchor_id(self, el: etree.Element) -> str | None:
        """Id of a paragraph that holds nothing but `<a id="…"></a>`."""
        if el.tag != "p" or len(el) or not el.text:
            return None
        blocks = self.md.htmlStash.rawHtmlBlocks

        def raw(m: re.Match[str]) -> str:
            index = int(m.group(1))
            return str(blocks[index]) if index < len(blocks) else m.group(0)

        m = _EMPTY_ANCHOR.match(HTML_PLACEHOLDER_RE.sub(raw, el.text))
        return m.group(2) if m else None

    def run(self, root: etree.Element) -> None:
        used = {el.get("id") for el in root.iter() if el.get("id")}
        slugger = GithubSlugger(used)  # explicit ids are never reused
        for parent in list(root.iter()):
            previous: etree.Element | None = None
            for el in list(parent):
                if isinstance(el.tag, str) and _HEADING.match(el.tag) and not el.get("id"):
                    # Same text extraction as the toc extension, so both agree.
                    text = strip_tags(render_inner_html(remove_fnrefs(el), self.md))
                    slug = slugger.slug(html.unescape(text))
                    if slug:
                        el.set("id", slug)
                    if previous is not None and slug and self._anchor_id(previous) == slug:
                        parent.remove(previous)
                previous = el


class AnchorsExtension(Extension):
    def extendMarkdown(self, md: Markdown) -> None:
        md.registerExtension(self)
        # inline = 20, attr_list = 8 (explicit `{#id}`), toc = 5.
        md.treeprocessors.register(GithubAnchorsTreeprocessor(md), "portal-anchors", 6)


def makeExtension(**kwargs: object) -> AnchorsExtension:
    return AnchorsExtension(**kwargs)
