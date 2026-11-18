"""GitHub-compatible heading slugs.

GitHub derives a heading anchor from the heading's text: lowercase it, drop
every character that is not a word character, a hyphen or a space, then turn
each space into a hyphen. Runs of hyphens are not collapsed and nothing is
trimmed, so ``Heat map (likelihood × severity)`` becomes
``heat-map-likelihood--severity``.

Using the same algorithm on the site means a link such as
``risk-register.md#2-heat-map-likelihood--severity`` works both on github.com
and on the generated portal.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Callable

__all__ = ["gh_slug", "gh_slugify", "GithubSlugger"]

# Everything that is not a word character (letters, digits, underscore, in any
# script), a hyphen or a space is dropped.
_DROP = re.compile(r"[^\w\- ]", re.UNICODE)


def gh_slug(value: str, separator: str = "-") -> str:
    """Return the GitHub anchor for a heading text (without duplicate suffix).

    The signature is the one Python-Markdown's ``toc`` extension expects from
    its ``slugify`` option: ``slugify(value, separator)``.
    """
    value = unicodedata.normalize("NFC", value).strip().lower()
    value = _DROP.sub("", value)
    return value.replace(" ", separator)


def gh_slugify(**_kwds: object) -> Callable[[str, str], str]:
    """Factory used from ``zensical.base.toml``.

    Zensical resolves ``toc.slugify = { object = "portal_mdx.slug.gh_slugify",
    kwds = {} }`` by importing the object and calling it with ``kwds``; the
    result is the slugify function. The returned function is module-level on
    purpose: Zensical pickles the extension configuration to compute its cache
    key, and closures cannot be pickled.
    """
    return gh_slug


class GithubSlugger:
    """Slugs for one document, with GitHub's rule for repeated headings.

    The first heading with a given text gets the plain slug, the next ones get
    ``-1``, ``-2``… (Python-Markdown would append ``_1``, ``_2``).
    """

    def __init__(self, used: set[str] | None = None) -> None:
        self._seen: dict[str, int] = {slug: 0 for slug in (used or ())}

    def slug(self, value: str) -> str:
        base = gh_slug(value)
        result = base
        while result in self._seen:
            self._seen[base] = self._seen.get(base, 0) + 1
            result = f"{base}-{self._seen[base]}"
        self._seen[result] = 0
        return result
