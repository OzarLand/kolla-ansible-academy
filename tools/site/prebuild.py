#!/usr/bin/env python3
"""Prepare the docs tree before the site is built.

1. Vendored Mermaid: ``docs/assets/vendor/mermaid/mermaid.min.js`` is not
   committed. When it is missing (or is not the pinned release) it is fetched
   by ``tools/site/fetch_vendor.py``, which verifies it. This is the only
   step that may need the network; ``--skip-vendor`` turns it off.

2. ``docs/assets/data/updates.json``: for every Markdown page under docs/ the
   date of the last commit that touched it. The page template shows it as
   "Last updated" and the home page lists the most recently updated pages
   (docs/assets/javascripts/portal.js reads the file in the browser).

    {
      "generated": "<ISO 8601 date of the HEAD commit>",
      "pages": [
        {"path": "operations/reconfigure-nova.md",
         "url": "operations/reconfigure-nova/",
         "title": "Reconfigure Nova",
         "updated": "YYYY-MM-DD"}
      ]
    }

Properties of updates.json:

* reproducible: every value comes from the Git history and the files, never
  from the wall clock, so the same commit always gives the same file;
* one pass over the history (a single ``git log``), whatever the page count;
* shallow clones: a page whose last change is not in the fetched history gets
  the date of the HEAD commit (use a full clone, e.g. ``fetch-depth: 0`` in
  CI, for exact dates);
* standard library only.

Both outputs are generated: they are git-ignored and must not be edited.

Usage (from anywhere):  python3 tools/site/prebuild.py [--docs-dir docs] [--skip-vendor]
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMMIT_MARK = "\x01"
INDEX_NAMES = ("index.md", "README.md")
# Not pages: theme assets (the vendored Mermaid ships a README.md).
SKIPPED_TOP_DIRS = ("assets",)


def load_fetch_vendor():
    """The module tools/site/fetch_vendor.py (it sits next to this file)."""
    spec = importlib.util.spec_from_file_location(
        "fetch_vendor", Path(__file__).resolve().with_name("fetch_vendor.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def ensure_vendor(root: Path, docs_dir: str) -> bool:
    """Put the vendored Mermaid bundle in place. False when that failed.

    Nothing is downloaded when the pinned file is already there.
    """
    fetch_vendor = load_fetch_vendor()
    try:
        fetch_vendor.ensure(root, docs_dir)
    except fetch_vendor.VendorError as error:
        print(f"prebuild: error: {error}", file=sys.stderr)
        print(
            "prebuild: the pages with a diagram need the vendored Mermaid bundle; "
            "see docs/assets/vendor/mermaid/README.md (or pass --skip-vendor)",
            file=sys.stderr,
        )
        return False
    return True


def git(root: Path, *args: str) -> str | None:
    """Run git in `root`; None when git or the repository is unavailable."""
    try:
        result = subprocess.run(
            ["git", "-c", "core.quotepath=off", *args],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout


def last_commit_dates(root: Path, docs_dir: str) -> dict[str, str]:
    """Map each path under `docs_dir` to the date of the last commit touching it.

    Single ``git log`` pass, newest commit first: the first time a path is
    seen is its last change. Commits at the edge of a shallow clone list the
    whole tree as added, so they say nothing about a file and are skipped.
    """
    log = git(
        root,
        "log",
        f"--format={COMMIT_MARK}%H %cI",
        "--name-only",
        "--relative",  # paths relative to `root`, even inside a larger repository
        "--",
        docs_dir,
    )
    if log is None:
        return {}
    shallow_file = git(root, "rev-parse", "--git-path", "shallow")
    boundary: set[str] = set()
    if shallow_file:
        path = Path(shallow_file.strip())
        path = path if path.is_absolute() else root / path
        if path.is_file():
            boundary = set(path.read_text(encoding="utf-8").split())

    dates: dict[str, str] = {}
    current: str | None = None
    for line in log.splitlines():
        if line.startswith(COMMIT_MARK):
            sha, _, iso = line[1:].partition(" ")
            current = None if sha in boundary else iso[:10]
        elif line and current is not None:
            dates.setdefault(line, current)
    return dates


def front_matter_title(text: str) -> str | None:
    """`title` of the YAML front matter (plain or quoted scalar on one line)."""
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    match = re.search(r"^title:[ \t]*(.+?)[ \t]*$", text[3:end], re.MULTILINE)
    if not match:
        return None
    value = match.group(1)
    if len(value) >= 2 and value[0] == value[-1] == "'":
        return value[1:-1].replace("''", "'")
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return value[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    return re.sub(r"\s+#.*$", "", value) or None


def first_heading(text: str) -> str | None:
    """Text of the first `# ` heading outside fenced code."""
    in_fence = False
    for line in text.splitlines():
        if line.lstrip().startswith(("```", "~~~")):
            in_fence = not in_fence
        elif not in_fence and line.startswith("# "):
            return re.sub(r"[`*_]", "", line[2:]).strip() or None
    return None


def page_url(rel: Path) -> str:
    """Directory URL of a page, relative to the site root (as Zensical builds it)."""
    if rel.name in INDEX_NAMES:
        parent = rel.parent.as_posix()
        return "" if parent == "." else f"{parent}/"
    return f"{rel.with_suffix('').as_posix()}/"


def collect(root: Path, docs_dir: str) -> dict:
    docs = root / docs_dir
    head = git(root, "log", "-1", "--format=%cI")
    head = head.strip() if head else None
    # Newer Git writes a UTC offset as "Z"; keep one spelling in the output.
    if head and head.endswith("Z"):
        head = head[:-1] + "+00:00"
    if head is None:
        print("prebuild: no Git history available; pages get no date", file=sys.stderr)
    dates = last_commit_dates(root, docs_dir) if head else {}

    pages = []
    missing = 0
    for path in sorted(docs.rglob("*.md")):
        rel = path.relative_to(docs)
        if rel.parts[0] in SKIPPED_TOP_DIRS:
            continue
        text = path.read_text(encoding="utf-8")
        updated = dates.get(f"{docs_dir}/{rel.as_posix()}")
        if updated is None and head:
            # Not committed yet, or last changed before the fetched history.
            updated = head[:10]
            missing += 1
        pages.append(
            {
                "path": rel.as_posix(),
                "url": page_url(rel),
                "title": front_matter_title(text) or first_heading(text) or rel.stem,
                "updated": updated,
            }
        )
    if missing and head:
        print(
            f"prebuild: {missing} page(s) without a commit in the available history "
            f"use the HEAD date {head[:10]}",
            file=sys.stderr,
        )
    return {"generated": head, "pages": pages}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=ROOT, help="repository root")
    parser.add_argument("--docs-dir", default="docs", help="docs directory, relative to the root")
    parser.add_argument(
        "--output",
        default=None,
        help="output file, relative to the root (default: <docs-dir>/assets/data/updates.json)",
    )
    parser.add_argument(
        "--skip-vendor",
        action="store_true",
        help="do not fetch the vendored Mermaid bundle (diagrams will not render without it)",
    )
    args = parser.parse_args(argv)

    root = args.root.resolve()
    docs_dir = args.docs_dir.strip("/")
    if not (root / docs_dir).is_dir():
        print(f"prebuild: {root / docs_dir} is not a directory", file=sys.stderr)
        return 1
    if not args.skip_vendor and not ensure_vendor(root, docs_dir):
        return 1
    output = root / (args.output or f"{docs_dir}/assets/data/updates.json")

    data = collect(root, docs_dir)
    content = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    output.parent.mkdir(parents=True, exist_ok=True)
    if not output.is_file() or output.read_text(encoding="utf-8") != content:
        output.write_text(content, encoding="utf-8")
    print(f"prebuild: {len(data['pages'])} pages -> {output.relative_to(root)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
