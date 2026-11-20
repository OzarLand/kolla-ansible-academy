"""Column labels on the cells of wide tables.

A table of four columns or more cannot be read on a phone: the columns are
squeezed or the table scrolls sideways. So that the stylesheet can show each
row as a card on a narrow screen, with the column name in front of each
value, this tree processor copies the header text of each column into a
``data-label`` attribute of the cells of that column, and marks the table
with ``data-portal-cards`` (an attribute, not a class: the stylesheet styles
the Markdown tables as ``table:not([class])``)::

    <table data-portal-cards="">
      <tr><td data-label="Tag">nova</td><td data-label="Hosts">…</td></tr>

Tables with fewer columns, with no header row, or whose rows do not have the
same number of cells as the header, are left alone. The text of the page
never changes; on a wide screen the table looks as before.
"""

from __future__ import annotations

import xml.etree.ElementTree as etree

from markdown import Extension, Markdown
from markdown.treeprocessors import Treeprocessor

__all__ = ["LabelsExtension", "makeExtension", "MIN_COLUMNS"]

MIN_COLUMNS = 4


def _text(el: etree.Element) -> str:
    return " ".join("".join(el.itertext()).split())


class LabelsTreeprocessor(Treeprocessor):
    def run(self, root: etree.Element) -> None:
        for table in root.iter("table"):
            if table.get("class"):
                continue
            header = table.find("thead/tr")
            if header is None:
                continue
            names = [_text(cell) for cell in header]
            if len(names) < MIN_COLUMNS:
                continue
            rows = table.findall("tbody/tr")
            if not rows or any(len(row) != len(names) for row in rows):
                continue
            for row in rows:
                for cell, name in zip(row, names):
                    if name:
                        cell.set("data-label", name)
            table.set("data-portal-cards", "")


class LabelsExtension(Extension):
    def extendMarkdown(self, md: Markdown) -> None:
        md.registerExtension(self)
        # After the inline processor (20), when cell text is final.
        md.treeprocessors.register(LabelsTreeprocessor(md), "portal-labels", 5)


def makeExtension(**kwargs: object) -> LabelsExtension:
    return LabelsExtension(**kwargs)
