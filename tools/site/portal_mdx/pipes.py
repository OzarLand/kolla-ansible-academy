"""Escaped pipes in table code spans.

In a GitHub table a literal pipe is written ``\\|``, also inside a code span:
``| `{{ x \\| default(0) }}` |`` shows ``{{ x | default(0) }}``. Python-Markdown
keeps the backslash inside code spans, so the site would show ``\\|``. This
postprocessor removes that backslash in the code spans of table cells, and
nowhere else: outside a table ``\\|`` in code is literal on GitHub too.
"""

from __future__ import annotations

import re

from markdown import Extension, Markdown
from markdown.postprocessors import Postprocessor

__all__ = ["TablePipesExtension", "makeExtension"]

_CELL = re.compile(r"<(t[dh])\b[^>]*>.*?</\1>", re.DOTALL)
_CODE = re.compile(r"<code\b[^>]*>.*?</code>", re.DOTALL)


def _fix_cell(cell: re.Match[str]) -> str:
    return _CODE.sub(lambda code: code.group(0).replace("\\|", "|"), cell.group(0))


class TablePipesPostprocessor(Postprocessor):
    def run(self, text: str) -> str:
        if "\\|" not in text:
            return text
        return _CELL.sub(_fix_cell, text)


class TablePipesExtension(Extension):
    def extendMarkdown(self, md: Markdown) -> None:
        md.registerExtension(self)
        # After `raw_html` (30) and `amp_substitute` (20): inline code is
        # back in the document by then.
        md.postprocessors.register(TablePipesPostprocessor(md), "portal-pipes", 5)


def makeExtension(**kwargs: object) -> TablePipesExtension:
    return TablePipesExtension(**kwargs)
