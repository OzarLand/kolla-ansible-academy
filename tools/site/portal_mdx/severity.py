"""Severity cells.

The risk register rates each risk ``Low``, ``Medium``, ``High`` or
``Critical``. So that the stylesheet can set those cells apart without any
markup in the Markdown source, this tree processor adds a class to:

* the cells of a table column whose header is ``Severity``;
* the value cell of a two-column row whose first cell is ``Severity``
  (the per-risk key/value tables).

The class is taken from the first word of the cell (``High``,
``Low (bandwidth)`` …): ``sev sev-low``, ``sev sev-medium``, ``sev sev-high``
or ``sev sev-critical``. A range or a list of ratings (``Medium–High``,
``Low (time), Medium (drift)``) takes its highest level. Cells that start
with any other word are left alone, and the cell text is never changed.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as etree

from markdown import Extension, Markdown
from markdown.treeprocessors import Treeprocessor

__all__ = ["SeverityExtension", "makeExtension", "LEVELS"]

LEVELS = ("low", "medium", "high", "critical")
_WORD = r"(low|medium|high|critical)\b"
# The cell must start with a level: `High`, `Low (bandwidth)`…
_FIRST = re.compile(rf"^\W*{_WORD}", re.IGNORECASE)
# …and may go on with more: `Medium–High`, `Low to High`, `Low (time), Medium (drift)`.
_MORE = re.compile(rf"(?:[-–—/,;]|\bto\b|\bor\b|\band\b)\s*{_WORD}", re.IGNORECASE)
_HEADER = "severity"


def _text(el: etree.Element) -> str:
    return "".join(el.itertext()).strip()


def _mark(cell: etree.Element) -> None:
    text = _text(cell)
    first = _FIRST.match(text)
    if not first:
        return
    found = [first.group(1), *_MORE.findall(text[first.end():])]
    level = max((word.lower() for word in found), key=LEVELS.index)
    classes = cell.get("class", "").split()
    for name in ("sev", f"sev-{level}"):
        if name not in classes:
            classes.append(name)
    cell.set("class", " ".join(classes))


class SeverityTreeprocessor(Treeprocessor):
    def run(self, root: etree.Element) -> None:
        for table in root.iter("table"):
            head = table.find("thead/tr")
            body_rows = table.findall("tbody/tr")
            columns = (
                [i for i, th in enumerate(head) if _text(th).lower() == _HEADER]
                if head is not None
                else []
            )
            for row in body_rows:
                cells = list(row)
                for i in columns:
                    if i < len(cells):
                        _mark(cells[i])
                if len(cells) == 2 and _text(cells[0]).lower() == _HEADER:
                    _mark(cells[1])


class SeverityExtension(Extension):
    def extendMarkdown(self, md: Markdown) -> None:
        md.registerExtension(self)
        # After `inline` (20): cell text such as `**Severity**` is parsed.
        md.treeprocessors.register(SeverityTreeprocessor(md), "portal-severity", 15)


def makeExtension(**kwargs: object) -> SeverityExtension:
    return SeverityExtension(**kwargs)
