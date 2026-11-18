"""GitHub-style lists.

The pages are written for github.com (CommonMark). Python-Markdown, which
builds the site, reads lists differently in ways that change the meaning of a
page:

* a nested list must be indented by four spaces. GitHub nests a list as soon
  as it is aligned with the text of its parent item (two spaces under
  ``- item``, three under ``1. item``). Without this module the sub-bullets of
  a numbered procedure become extra numbered steps;
* a list, or a fenced code block, must be preceded by a blank line. On GitHub
  both may start right after a paragraph line. Without this module such a
  list is swallowed by the paragraph.

This preprocessor rewrites the *indentation* of list blocks, in memory, into
the form Python-Markdown expects, following the CommonMark rules: an item's
children are the lines indented at least to the column where its text starts.
It also inserts the blank lines CommonMark does not require around a list or
a fenced code block that touches a paragraph. Text is never changed, and
fenced code keeps its content (only the indentation it shares with its list
item is adjusted).

Lists that already use four-space nesting and blank lines come out
unchanged. Use it together with the ``sane_lists`` extension, which keeps
bullet and numbered lists apart and honours the first number of a list, as
GitHub does.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from markdown import Extension, Markdown
from markdown.preprocessors import Preprocessor

__all__ = ["GithubListsExtension", "makeExtension", "normalize"]

# A list item, once leading spaces are removed: marker, then spaces and text
# (or nothing). `1)` is not a list for Python-Markdown and is left alone.
_ITEM = re.compile(r"^([-*+]|\d{1,9}\.)(?:( +)(\S.*)|\s*)$")
_HR = re.compile(r"^([-*_])(?: *\1){2,} *$")
_FENCE = re.compile(r"^(`{3,}|~{3,})(.*)$")
_QUOTE = re.compile(r"^ {0,3}>( ?)(.*)$")
# Lines that start a block of their own and so never continue a paragraph.
_BLOCK_START = re.compile(r"^(#{1,6}(\s|$)|>|<[A-Za-z/!?]|\||`{3,}|~{3,})")

_STEP = 4  # Python-Markdown's indentation unit


@dataclass
class _Item:
    content_col: int  # source column where the item's text starts
    ordered: bool


def _split(line: str) -> tuple[int, str]:
    text = line.lstrip(" ")
    return len(line) - len(text), text


def _fence_open(text: str) -> tuple[str, int] | None:
    m = _FENCE.match(text)
    if not m or (m.group(1)[0] == "`" and "`" in m.group(2)):
        return None
    return m.group(1)[0], len(m.group(1))


def _fence_close(text: str, fence: tuple[str, int]) -> bool:
    stripped = text.rstrip()
    return len(stripped) >= fence[1] and set(stripped) == {fence[0]}


def _content(line: str, stack: list[_Item]) -> str:
    """Re-indent a line that belongs to the innermost open item."""
    if not stack:
        return line
    indent, text = _split(line)
    extra = max(indent - stack[-1].content_col, 0)
    return " " * (_STEP * len(stack) + extra) + text


def normalize(lines: list[str]) -> list[str]:
    """Return `lines` with list blocks laid out the Python-Markdown way."""
    out: list[str] = []
    stack: list[_Item] = []
    fence: tuple[str, int] | None = None
    # Kind of the previous line: "blank", "itemtext" (first paragraph of the
    # innermost item), "para" (any other paragraph text), "fenced" (a fenced
    # block just closed) or "other".
    prev = "blank"
    i, n = 0, len(lines)

    # Nesting level of the first line of the current output block (a run of
    # non-blank lines). Python-Markdown removes that indentation from the
    # whole block, so a block must never climb back above its first line:
    # where the source does (a parent item right after a nested table, code
    # block or sub-list), a blank line starts a new block.
    block_level = 0

    def emit(text: str, level: int, blank_before: bool = False) -> None:
        nonlocal block_level
        in_block = bool(out) and out[-1] != ""
        if in_block and (blank_before or level < block_level):
            out.append("")
            in_block = False
        if not in_block:
            block_level = level
        out.append(text)

    while i < n:
        line = lines[i]
        i += 1
        indent, text = _split(line)

        if fence:
            out.append(_content(line, stack))
            if _fence_close(text, fence):
                fence, prev = None, "fenced"
            continue

        if not text:
            out.append("")
            prev = "blank"
            continue

        in_paragraph = prev in ("para", "itemtext")
        after_fence = prev == "fenced"
        is_hr = bool(_HR.match(text))
        starts_block = is_hr or bool(_BLOCK_START.match(text))

        # ---- list item? -------------------------------------------------
        item = None if is_hr else _ITEM.match(text)
        if item:
            marker, spaces, rest = item.group(1), item.group(2) or "", item.group(3) or ""
            ordered = marker[0].isdigit()
            # Close, on paper, the items this line is not indented under.
            depth, closed = len(stack), None
            while depth and indent < stack[depth - 1].content_col:
                depth -= 1
                closed = stack[depth]
            base = stack[depth - 1].content_col if depth else 0
            # Same list as the item just closed at this level?
            sibling = closed is not None and closed.ordered == ordered
            if indent - base > 3:
                item = None  # indented text or code, not an item
            elif in_paragraph and not sibling and ((ordered and marker != "1.") or not rest):
                # CommonMark: only a bullet list, or a numbered list starting
                # at 1, can interrupt a paragraph, and not with an empty item.
                item = None
            if item:
                # Python-Markdown needs a blank line where CommonMark needs
                # none: before a list that follows paragraph text, and
                # between an item and a list that is not its own sub-list.
                blank = prev == "para" or after_fence or (
                    prev == "itemtext" and not sibling and depth < len(stack)
                )
                del stack[depth:]
                emit(" " * (_STEP * depth) + marker + (" " + rest if rest else ""), depth, blank)
                width = len(spaces) if 1 <= len(spaces) <= 4 else 1
                stack.append(_Item(indent + len(marker) + width, ordered))
                prev = "itemtext" if rest else "other"
                continue

        # ---- not an item --------------------------------------------------
        # A plain text line right after paragraph text continues it whatever
        # its indentation (lazy continuation); anything else closes the items
        # it is not indented under.
        if not (in_paragraph and not starts_block):
            while stack and indent < stack[-1].content_col:
                stack.pop()

        # Block quote at the top level: its content is normalised on its own.
        if not stack and _QUOTE.match(line):
            inner = []
            j = i - 1
            while j < n and (m := _QUOTE.match(lines[j])):
                inner.append(m.group(2))
                j += 1
            i = j
            if after_fence and out and out[-1] != "":
                out.append("")
            out.extend(("> " + q) if q else ">" for q in normalize(inner))
            prev = "other"
            continue

        opened = _fence_open(text)
        if opened:
            # On GitHub a fence may interrupt a paragraph; here it must be a
            # block of its own.
            emit(_content(line, stack), len(stack), in_paragraph or after_fence)
            fence, prev = opened, "other"
            continue

        emit(_content(line, stack), len(stack), after_fence)
        if starts_block:
            prev = "other"
        elif not in_paragraph:
            prev = "para"
        # else: the paragraph (or the item's text) goes on; `prev` is kept.

    return out


class GithubListsPreprocessor(Preprocessor):
    def run(self, lines: list[str]) -> list[str]:
        return normalize(lines)


class GithubListsExtension(Extension):
    def extendMarkdown(self, md: Markdown) -> None:
        md.registerExtension(self)
        # After `normalize_whitespace` (30: tabs are spaces by now), before the
        # fenced-code (25) and raw-HTML (20) preprocessors, which must see the
        # final indentation.
        md.preprocessors.register(GithubListsPreprocessor(md), "portal-lists", 27)


def makeExtension(**kwargs: object) -> GithubListsExtension:
    return GithubListsExtension(**kwargs)
