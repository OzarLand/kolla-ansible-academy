"""Angle-bracket placeholders.

Commands and handler names of the corpus use placeholders such as ``<svc>``
or ``<host>``. Inside a code span they are safe. In running text
Python-Markdown passes anything shaped like a tag through as raw HTML, and
the browser then swallows it as an unknown element: the placeholder vanishes
from the page without any warning.

This extension shows a tag-shaped token as text when its name is not an HTML
element::

    Restart <svc> container   ->   Restart &lt;svc&gt; container

Rules:

* only bare tokens are concerned (``<name>`` or ``</name>``, no attributes),
  so real HTML, autolinks (``<https://…>``) and comments are never touched;
* names of HTML elements keep their meaning (``<br>``, ``<kbd>``, ``<a>``…);
* code spans and code blocks are already protected when the pattern runs.

github.com removes an unknown tag as well, so the source should still put a
placeholder in a code span; ``tools/site/check_docs.py`` is the place to
report it. This extension only makes sure the site never loses the text.
"""

from __future__ import annotations

import re

from markdown import Extension, Markdown
from markdown.inlinepatterns import InlineProcessor
from markdown.util import AtomicString

__all__ = ["PlaceholdersExtension", "makeExtension", "HTML_ELEMENTS"]

# Elements of the HTML living standard, plus the obsolete ones browsers
# still render. SVG and MathML are written with attributes or inside an
# <svg>/<math> block, which Python-Markdown handles as a raw HTML block.
HTML_ELEMENTS = frozenset(
    """
    a abbr acronym address area article aside audio b base bdi bdo big
    blockquote body br button canvas caption center cite code col colgroup
    data datalist dd del details dfn dialog dir div dl dt em embed fieldset
    figcaption figure font footer form h1 h2 h3 h4 h5 h6 head header hgroup
    hr html i iframe img input ins kbd label legend li link main map mark
    math menu meta meter nav noscript object ol optgroup option output p
    param picture pre progress q rp rt ruby s samp script search section
    select slot small source span strike strong style sub summary sup svg
    table tbody td template textarea tfoot th thead time title tr track tt
    u ul var video wbr
    """.split()
)

PLACEHOLDER_PATTERN = r"</?([A-Za-z][A-Za-z0-9_.-]*)>"


class PlaceholderInlineProcessor(InlineProcessor):
    def handleMatch(  # type: ignore[override]
        self, m: re.Match[str], data: str
    ) -> tuple[str | None, int | None, int | None]:
        if m.group(1).lower() in HTML_ELEMENTS:
            return None, None, None
        return AtomicString(m.group(0)), m.start(0), m.end(0)


class PlaceholdersExtension(Extension):
    def extendMarkdown(self, md: Markdown) -> None:
        md.registerExtension(self)
        # After `backtick` (190) and `escape` (180): code spans are already
        # stashed. Before `autolink` (120) and `html` (90), which would take
        # the token as raw HTML.
        md.inlinePatterns.register(
            PlaceholderInlineProcessor(PLACEHOLDER_PATTERN, md), "portal-placeholders", 125
        )


def makeExtension(**kwargs: object) -> PlaceholdersExtension:
    return PlaceholdersExtension(**kwargs)
