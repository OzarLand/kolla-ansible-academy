"""Source citations.

Every statement of the study cites the source that shows it as a code span
holding a path and a line number or range, e.g. ``site.yml:88-103``,
``roles/nova-cell/handlers/main.yml:74-168, :170`` or a continuation such as
``:140-203``. Long table cells and paragraphs hold dozens of them, and in the
same style as commands they crowd the explanation. So that the stylesheet can
show citations more quietly than commands, without any markup in the
Markdown source, this postprocessor adds a class to every code span whose
whole text is a citation::

    `site.yml:88-103`   ->   <code class="cite">site.yml:88-103</code>

A citation is a path (no spaces), a colon and a line number or range,
optionally followed by more numbers or ranges (``:12, :40-44`` or
``:13-33,43-67``); or such a list of numbers alone, starting with a colon.
Anything else (a path without line, a command, ``key: value``) stays a plain
code span. The text is never changed, and on github.com the span stays a
plain code span. Code blocks are not concerned: their code carries
highlighting markup, and the optional line breaks that
:mod:`portal_mdx.breaks` adds inside table code spans (``<wbr>``) are allowed.

It works on the final HTML, like :mod:`portal_mdx.impact`, because
``pymdownx.inlinehilite`` keeps code spans out of the tree until the end.
"""

from __future__ import annotations

import re

from markdown import Extension, Markdown
from markdown.postprocessors import Postprocessor

__all__ = ["CitesExtension", "makeExtension", "is_citation"]

_RANGE = r"\d+(?:-\d+)?"
_MORE = rf"(?:\s*,\s*:?{_RANGE})*"
_CITATION = re.compile(
    rf"^(?:[A-Za-z0-9_.@+~/-]*[A-Za-z0-9_]:{_RANGE}{_MORE}|:{_RANGE}{_MORE})$"
)
# A code span with no markup inside, apart from the optional <wbr> breaks.
_SPAN = re.compile(r"<code>((?:[^<]|<wbr>)+)</code>")


def is_citation(text: str) -> bool:
    """True when `text` (the visible text of a code span) is a source citation."""
    return bool(_CITATION.match(text.strip()))


class CitesPostprocessor(Postprocessor):
    def run(self, text: str) -> str:
        if "<code>" not in text:
            return text

        def mark(match: re.Match[str]) -> str:
            if is_citation(match.group(1).replace("<wbr>", "")):
                return f'<code class="cite">{match.group(1)}</code>'
            return match.group(0)

        return _SPAN.sub(mark, text)


class CitesExtension(Extension):
    def extendMarkdown(self, md: Markdown) -> None:
        md.registerExtension(self)
        # Like portal-impact: after `raw_html` (30) and `amp_substitute` (20).
        md.postprocessors.register(CitesPostprocessor(md), "portal-cites", 3)


def makeExtension(**kwargs: object) -> CitesExtension:
    return CitesExtension(**kwargs)
