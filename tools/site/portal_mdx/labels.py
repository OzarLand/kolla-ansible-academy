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

It also measures the text of each column and marks a column whose cells are
long on average, or that holds one very long cell (prose), with ``data-col="long"`` and one whose cells are
short (a name, a number) with ``data-col="short"``, on its header and cells,
so that a wide table can give the room to its prose columns on a wide screen.

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
# Average number of characters per cell of a column.
LONG_COLUMN = 160
# ...or the length of its longest cell.
LONG_CELL = 400
SHORT_COLUMN = 24


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
            for index, head in enumerate(header):
                cells = [row[index] for row in rows]
                lengths = [len(_text(cell)) for cell in cells]
                average = sum(lengths) / len(lengths)
                if average >= LONG_COLUMN or max(lengths) >= LONG_CELL:
                    kind = "long"
                elif average <= SHORT_COLUMN:
                    kind = "short"
                else:
                    kind = None
                if kind:
                    for cell in (head, *cells):
                        cell.set("data-col", kind)
            table.set("data-portal-cards", "")


class LabelsExtension(Extension):
    def extendMarkdown(self, md: Markdown) -> None:
        md.registerExtension(self)
        # After the inline processor (20), when cell text is final.
        md.treeprocessors.register(LabelsTreeprocessor(md), "portal-labels", 5)


def makeExtension(**kwargs: object) -> LabelsExtension:
    return LabelsExtension(**kwargs)
