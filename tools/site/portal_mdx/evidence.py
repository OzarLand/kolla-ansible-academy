"""Evidence chips.

The corpus labels every statement with ``[CODE]`` (shown by the sources) or
``[NOT AVAILABLE]`` (the sources do not establish it). This extension renders
exactly those two bracket tokens as chips::

    [CODE]            ->  <span class="ev ev-code">CODE</span>
    [NOT AVAILABLE]   ->  <span class="ev ev-na">NOT AVAILABLE</span>

Rules:

* only the exact tokens are converted; ``[CODE: explanation]`` and other
  variants stay as written;
* code spans, fenced or indented code and raw HTML blocks are never touched
  (they are already protected when inline patterns run); text inside an
  inline raw ``<code>``, ``<kbd>``, ``<samp>``, ``<tt>``, ``<var>`` or
  ``<pre>`` element is skipped explicitly;
* a token used as link text (``[CODE](url)``, ``[CODE][ref]``) stays a link;
* the chip text is the label without its brackets, so heading ids (computed
  from the heading text, in which brackets are dropped anyway) and the text
  the search index sees do not change beyond the missing brackets.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as etree

from markdown import Extension, Markdown
from markdown.inlinepatterns import InlineProcessor
from markdown.util import AtomicString

__all__ = ["EvidenceExtension", "makeExtension", "EVIDENCE_PATTERN"]

# The label may be wrapped by the author's editor: one line break between NOT
# and AVAILABLE is accepted. `(?![(\[])` leaves Markdown links alone.
EVIDENCE_PATTERN = r"\[(CODE|NOT(?: |\n[ ]*)AVAILABLE)\](?![(\[])"

_CLASSES = {"CODE": "ev ev-code", "NOT AVAILABLE": "ev ev-na"}

# Inline raw HTML is still literal text when this pattern runs.
_RAW_CODE_TAG = re.compile(r"<(/?)(?:code|kbd|samp|tt|var|pre)\b[^>]*>", re.IGNORECASE)


def _inside_raw_code(prefix: str) -> bool:
    """True when `prefix` leaves a raw code-like HTML element open."""
    depth = 0
    for tag in _RAW_CODE_TAG.finditer(prefix):
        depth = max(depth - 1, 0) if tag.group(1) else depth + 1
    return depth > 0


class EvidenceInlineProcessor(InlineProcessor):
    """Turn an evidence token into a ``<span class="ev …">`` chip."""

    def handleMatch(  # type: ignore[override]
        self, m: re.Match[str], data: str
    ) -> tuple[etree.Element | None, int | None, int | None]:
        if _inside_raw_code(data[: m.start(0)]):
            return None, None, None
        label = " ".join(m.group(1).split())
        el = etree.Element("span")
        el.set("class", _CLASSES[label])
        el.text = AtomicString(label)
        return el, m.start(0), m.end(0)


class EvidenceExtension(Extension):
    """Register the evidence chip inline pattern."""

    def extendMarkdown(self, md: Markdown) -> None:
        md.registerExtension(self)
        # After `backtick` (190) and `escape` (180), so code spans and
        # backslash-escaped brackets are left alone; before `reference` (170)
        # and `link` (160), so a token inside a link text becomes a chip
        # inside the link.
        md.inlinePatterns.register(
            EvidenceInlineProcessor(EVIDENCE_PATTERN, md), "portal-evidence", 175
        )


def makeExtension(**kwargs: object) -> EvidenceExtension:
    return EvidenceExtension(**kwargs)
