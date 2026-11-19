#!/usr/bin/env python3
"""Definitions on hover: the glossary of a release as data for the pages.

``docs/<id>/reference/glossary.md`` holds a table ``| Term | Meaning | Defined in |``.
This module reads it and writes ``docs/<id>/assets/data/glossary.json``, which
``overrides/assets/javascripts/learning.js`` loads to show the meaning of a term
where it first appears on a page. Nothing is written by hand: the definitions
are the ones of the glossary, with their evidence labels.

    {
      "glossary": "reference/glossary/",
      "terms": [
        {"term": "drift",
         "keys": ["drift"],
         "html": "What <code>compare_container</code> detects: … [CODE].",
         "more": "operations/#drift",
         "more_text": "Operations, \\"Drift\\""}
      ]
    }

* ``keys`` are matched as the whole text of an inline code span
  (``kolla_action``, ``COPY_ONCE``). ``words``, the keys in lower-case
  letters, spaces and hyphens outside parentheses ("drift", "one-shot
  container"), are also matched in the text, case-insensitively, plural
  included.
* rows whose term is a notation rather than a word (``R*n*``, the scope
  legend, the evidence labels) are left out.
* ``more`` is the first link of the "Defined in" column, as a URL relative to
  the root of the release site.

Standard library only.
"""

from __future__ import annotations

import html
import json
import posixpath
import re
from pathlib import Path

GLOSSARY = "reference/glossary.md"
OUTPUT = "assets/data/glossary.json"

_LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
_CODE = re.compile(r"`([^`]+)`")
_STRONG = re.compile(r"\*\*([^*]+)\*\*")
_WORD_KEY = re.compile(r"^[a-z][a-z -]*[a-z]$")


def split_row(line: str) -> list[str]:
    """Cells of a Markdown table row (no escaped pipes in the glossary)."""
    cells = line.strip().strip("|").split("|")
    return [cell.strip() for cell in cells]


def _clean(parts: list[str]) -> list[str]:
    keys: list[str] = []
    for part in parts:
        key = part.replace("`", "").strip()
        if len(key) >= 3 and key not in keys:
            keys.append(key)
    return keys


def term_keys(term: str) -> tuple[list[str], list[str]]:
    """Keys of a term cell: (main keys, keys in parentheses).

    Alternatives are split on ' / ', ' vs ' and ', '. The keys in parentheses
    (`config.json (config_files, command, permissions)`) name parts of the
    term: they are matched only as code, never as words of the text.
    """
    inner: list[str] = []
    for group in re.findall(r"\(([^)]*)\)", term):
        inner.extend(group.split(","))
    main = re.sub(r"\([^)]*\)", "", term)
    return _clean(re.split(r"\s+/\s+|\s+vs\s+|,\s+", main)), _clean(inner)


def to_html(markdown: str) -> str:
    """The inline Markdown of a cell as safe HTML: code, bold, link text."""
    text = html.escape(markdown, quote=False)
    text = _LINK.sub(r"\1", text)
    text = _CODE.sub(r"<code>\1</code>", text)
    text = _STRONG.sub(r"<strong>\1</strong>", text)
    # The evidence labels, as the chips of the pages (portal_mdx.evidence).
    text = text.replace("[CODE]", '<span class="ev ev-code">CODE</span>')
    text = text.replace("[NOT AVAILABLE]", '<span class="ev ev-na">NOT AVAILABLE</span>')
    return text


def page_url(target: str, base_dir: str = "reference") -> str | None:
    """Site URL (relative to the release root) of a link written in the glossary."""
    if re.match(r"^[a-z]+:", target):
        return None
    path, _, fragment = target.partition("#")
    if not path.endswith(".md"):
        return None
    rel = posixpath.normpath(posixpath.join(base_dir, path))
    if rel.startswith("../"):
        return None
    stem = rel[: -len(".md")]
    if stem == "index":
        url = ""
    elif stem.endswith("/index"):
        url = stem[: -len("index")]
    else:
        url = stem + "/"
    return url + (f"#{fragment}" if fragment else "")


def is_notation(term: str) -> bool:
    return "*" in term or term.startswith("[") or term.lower().startswith("scope legend")


def extract(text: str) -> list[dict]:
    """Terms of the glossary table."""
    terms = []
    in_table = False
    for line in text.splitlines():
        if line.startswith("| Term |"):
            in_table = True
            continue
        if not in_table:
            continue
        if not line.startswith("|"):
            if terms:
                break
            continue
        cells = split_row(line)
        if len(cells) < 3 or set(cells[0]) <= {"-", ":"}:
            continue
        term, meaning, defined = cells[0], cells[1], cells[2]
        if is_notation(term):
            continue
        main_keys, inner_keys = term_keys(term)
        keys = main_keys + [key for key in inner_keys if key not in main_keys]
        if not keys:
            continue
        more = more_text = None
        for label, target in _LINK.findall(defined):
            url = page_url(target)
            if url is not None:
                more, more_text = url, re.sub(r"[`*]", "", label)
                break
        terms.append(
            {
                "term": term.replace("`", ""),
                "keys": keys,
                "words": [key for key in main_keys if _WORD_KEY.match(key)],
                "html": to_html(meaning),
                "more": more,
                "more_text": more_text,
            }
        )
    return terms


def write_glossary(root: Path, docs_dir: str, output: Path | None = None) -> int:
    """Write glossary.json of one docs directory. Returns the number of terms."""
    source = root / docs_dir / GLOSSARY
    terms = extract(source.read_text(encoding="utf-8")) if source.is_file() else []
    data = {"glossary": "reference/glossary/", "terms": terms}
    output = output or root / docs_dir / OUTPUT
    content = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    output.parent.mkdir(parents=True, exist_ok=True)
    if not output.is_file() or output.read_text(encoding="utf-8") != content:
        output.write_text(content, encoding="utf-8")
    print(f"prebuild: {len(terms)} glossary terms -> {output.relative_to(root)}")
    return len(terms)
