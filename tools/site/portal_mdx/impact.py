"""Impact class names.

The operation pages declare their impact in the front matter (``impact:``)
and the page template shows it as chips. The same class names are written in
the body of a few pages as code spans (the catalogue of
``operations/index.md`` of a release, the definitions of its ``start/conventions.md``).
So that the stylesheet can give those code spans the colour of the matching
chip, without any markup in the Markdown source, this postprocessor adds a
class to every code span whose whole text is one of the eight class names::

    `restarts-on-drift`   ->   <code class="impact impact--restarts-on-drift">

The text is never changed, and on github.com the code span stays a plain code
span. A code span that merely contains a name (`--read-only`, `critical: true`)
is left alone. Code blocks are not concerned: the
code of a block ends with a line break and carries highlighting markup.

It works on the final HTML rather than on the element tree because
``pymdownx.inlinehilite`` keeps code spans out of the tree until the end.
"""

from __future__ import annotations

import re

from markdown import Extension, Markdown
from markdown.postprocessors import Postprocessor

__all__ = ["ImpactExtension", "makeExtension", "IMPACT_CLASSES"]

# The vocabulary of the `impact` front matter key (start/conventions.md of a release).
IMPACT_CLASSES = frozenset(
    {
        "read-only",
        "writes-config",
        "pulls-images",
        "restarts-on-drift",
        "recreates-containers",
        "critical",
        "maintenance-window",
        "recovery",
    }
)

_SPAN = re.compile(r"<code>(%s)</code>" % "|".join(sorted(IMPACT_CLASSES)))


class ImpactPostprocessor(Postprocessor):
    def run(self, text: str) -> str:
        if "<code>" not in text:
            return text
        return _SPAN.sub(r'<code class="impact impact--\1">\1</code>', text)


class ImpactExtension(Extension):
    def extendMarkdown(self, md: Markdown) -> None:
        md.registerExtension(self)
        # After `raw_html` (30) and `amp_substitute` (20): inline code is
        # back in the document by then.
        md.postprocessors.register(ImpactPostprocessor(md), "portal-impact", 4)


def makeExtension(**kwargs: object) -> ImpactExtension:
    return ImpactExtension(**kwargs)
