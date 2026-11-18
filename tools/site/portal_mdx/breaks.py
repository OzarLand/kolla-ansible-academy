"""Line-break opportunities in the code spans of table cells.

The tables of the corpus cite their evidence as code spans: file paths and
line ranges such as ``roles/neutron/tasks/rolling_upgrade.yml:13-33,43-67``.
A browser does not break a line after ``/`` or between ``,`` and a digit, so
one long citation makes its column, and then the whole table, wider than the
page.

This postprocessor adds a ``<wbr>`` (an optional break, no character) after
each ``/`` and after each ``,`` that separates two line ranges, in the code
spans of table cells and nowhere else. The text is unchanged: what is
displayed, selected, copied and indexed for the search is the same string.
"""

from __future__ import annotations

import re

from markdown import Extension, Markdown
from markdown.postprocessors import Postprocessor

__all__ = ["TableBreaksExtension", "makeExtension", "soften"]

_CELL = re.compile(r"<(t[dh])\b[^>]*>.*?</\1>", re.DOTALL)
_CODE = re.compile(r"(<code\b[^>]*>)(.*?)(</code>)", re.DOTALL)
_TAG = re.compile(r"(<[^>]*>)")
# After a slash inside a path (not the leading one, not `//`, not the last
# character), and after the comma of a list of line ranges
# (`781-803,873-875`, `:57,:119`).
_AFTER = re.compile(r"(?<=[^\s/(])/(?=[^\s/,;:)])|(?<=\d),(?=[\d:])")
# Only spans long enough to matter get breaks: `a/b`, `n/a`, `0,1` stay whole.
_MIN_LENGTH = 16


def soften(text: str) -> str:
    """Return the content of a code span with ``<wbr>`` at its break points."""
    if "<wbr" in text:
        return text  # already done
    plain = _TAG.sub("", text)
    if len(plain) < _MIN_LENGTH or ("/" not in plain and "," not in plain):
        return text
    parts = _TAG.split(text)
    for index, part in enumerate(parts):
        if not part.startswith("<"):
            parts[index] = _AFTER.sub(lambda m: m.group(0) + "<wbr>", part)
    return "".join(parts)


def _fix_cell(cell: re.Match[str]) -> str:
    return _CODE.sub(lambda code: code.group(1) + soften(code.group(2)) + code.group(3), cell.group(0))


class TableBreaksPostprocessor(Postprocessor):
    def run(self, text: str) -> str:
        if "<td" not in text and "<th" not in text:
            return text
        return _CELL.sub(_fix_cell, text)


class TableBreaksExtension(Extension):
    def extendMarkdown(self, md: Markdown) -> None:
        md.registerExtension(self)
        # After `portal-pipes` (5): it works on the final text of the spans.
        md.postprocessors.register(TableBreaksPostprocessor(md), "portal-breaks", 4)


def makeExtension(**kwargs: object) -> TableBreaksExtension:
    return TableBreaksExtension(**kwargs)
