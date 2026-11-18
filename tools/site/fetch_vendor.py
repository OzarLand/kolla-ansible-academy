#!/usr/bin/env python3
"""Fetch the Mermaid browser bundle the site serves from its own origin.

The portal makes no request to a third-party host: pages with a diagram load
``assets/vendor/mermaid/mermaid.min.js`` of the site they belong to (see
overrides/main.html). That file is 5.5 MB and is not committed. It is shared
by all releases: it sits once in ``overrides/assets/``, the static files of
the theme directory, which Zensical copies into every built site. This script puts it in place:

1. download the pinned tarball from the npm registry (``TARBALL_URL``);
2. check it against the SHA-512 integrity value the registry publishes for
   that version (``TARBALL_INTEGRITY``, the ``dist.integrity`` field of
   https://registry.npmjs.org/mermaid/<version>);
3. extract ``package/dist/mermaid.min.js`` and check its SHA-256
   (``FILE_SHA256``);
4. write it to ``overrides/assets/vendor/mermaid/mermaid.min.js``.

It is idempotent: when the file is already there with the expected SHA-256,
nothing is downloaded and nothing is written. Anything else is an error with
exit status 1: a failed download, a tarball or a file with another digest, a
tarball without the file. A file that fails a check is never left in place.

``tools/site/prebuild.py`` calls it when the file is missing, so a build from
a fresh clone needs access to registry.npmjs.org once. The browser never
does: the page only loads the local copy.

Usage (from anywhere):

    python3 tools/site/fetch_vendor.py            # fetch when missing or different
    python3 tools/site/fetch_vendor.py --check    # verify only, no network
    python3 tools/site/fetch_vendor.py --tarball mermaid-12.3.0.tgz   # offline

To change the version, see overrides/assets/vendor/mermaid/README.md.
Standard library only.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import http.client
import os
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# --- pinned release ----------------------------------------------------------
# The theme bundle asks for the Mermaid 12 release line: stay on 12.x.
PACKAGE = "mermaid"
VERSION = "12.3.0"
TARBALL_URL = f"https://registry.npmjs.org/{PACKAGE}/-/{PACKAGE}-{VERSION}.tgz"
# `dist.integrity` of https://registry.npmjs.org/mermaid/12.3.0
TARBALL_INTEGRITY = (
    "sha512-4113TdXeLAsMruJ79OpFL5O8+LTFXhQqZ260rF3tgUmiNAtRm4Uume04I+65PRN6yZ69J4f8rVYWW8zRk65UYw=="
)
# File taken from the tarball, and its own digest (checked on every run).
MEMBER = "package/dist/mermaid.min.js"
FILE_SHA256 = "336df803d87a38b70a01e736e666c8f7601d2ce42f5e47c8fafe5d721074b9a3"
# -----------------------------------------------------------------------------

# Where the file goes, relative to the theme directory (`custom_dir`).
THEME_DIR = "overrides"
TARGET = "assets/vendor/mermaid/mermaid.min.js"

# Upper bounds: a response or a member larger than this is not the pinned
# release (tarball: 26 MB, file: 5.5 MB).
MAX_TARBALL_BYTES = 64 * 1024 * 1024
MAX_FILE_BYTES = 16 * 1024 * 1024
ATTEMPTS = 3
TIMEOUT_SECONDS = 60
CHUNK = 1024 * 1024


class VendorError(Exception):
    """The vendored file could not be put in place."""


def target_path(root: Path = ROOT, theme_dir: str = THEME_DIR) -> Path:
    return root / theme_dir / TARGET


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_current(path: Path) -> bool:
    """True when `path` is the pinned file."""
    return path.is_file() and sha256_of(path) == FILE_SHA256


def integrity_of(path: Path, algorithm: str = "sha512") -> str:
    """Subresource-integrity string of a file, in the registry's format."""
    digest = hashlib.new(algorithm)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK), b""):
            digest.update(chunk)
    return f"{algorithm}-{base64.b64encode(digest.digest()).decode('ascii')}"


def check_tarball(path: Path) -> None:
    algorithm = TARBALL_INTEGRITY.partition("-")[0]
    found = integrity_of(path, algorithm)
    if found != TARBALL_INTEGRITY:
        raise VendorError(
            f"integrity mismatch for the {PACKAGE} {VERSION} tarball:\n"
            f"  expected {TARBALL_INTEGRITY}\n"
            f"  found    {found}"
        )


def download(url: str, destination: Path) -> None:
    """Download `url` to `destination`, a few attempts, bounded size."""
    if not url.startswith("https://"):
        raise VendorError(f"refusing to download from a URL that is not https: {url}")
    request = urllib.request.Request(url, headers={"User-Agent": "fetch_vendor.py"})
    last: Exception | None = None
    for attempt in range(1, ATTEMPTS + 1):
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                size = 0
                with destination.open("wb") as out:
                    while chunk := response.read(CHUNK):
                        size += len(chunk)
                        if size > MAX_TARBALL_BYTES:
                            raise VendorError(
                                f"{url}: more than {MAX_TARBALL_BYTES} bytes, not the pinned tarball"
                            )
                        out.write(chunk)
            return
        except urllib.error.HTTPError as error:
            last = error
            if error.code < 500 and error.code != 429:
                break  # 403, 404…: another attempt will not help
        except (OSError, EOFError, http.client.HTTPException) as error:
            # URLError, timeout, connection reset, incomplete read
            last = error
        if attempt < ATTEMPTS:
            time.sleep(2 * attempt)
    raise VendorError(f"download failed: {url}: {last}")


def extract_member(tarball: Path) -> bytes:
    """Content of `MEMBER` in the tarball (read in memory, nothing is unpacked)."""
    try:
        with tarfile.open(tarball, mode="r:gz") as archive:
            for member in archive:
                if member.name != MEMBER:
                    continue
                if not member.isfile() or member.size > MAX_FILE_BYTES:
                    raise VendorError(f"{MEMBER} in the tarball is not a regular file of a sane size")
                handle = archive.extractfile(member)
                if handle is None:
                    raise VendorError(f"{MEMBER} cannot be read from the tarball")
                return handle.read()
    except (tarfile.TarError, EOFError, OSError) as error:
        raise VendorError(f"cannot read the tarball {tarball}: {error}") from error
    raise VendorError(f"{MEMBER} is not in the tarball")


def install(content: bytes, target: Path) -> None:
    found = hashlib.sha256(content).hexdigest()
    if found != FILE_SHA256:
        raise VendorError(
            f"SHA-256 mismatch for {MEMBER} of {PACKAGE} {VERSION}:\n"
            f"  expected {FILE_SHA256}\n"
            f"  found    {found}"
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    # Written next to the target, then renamed: no partial file under its name.
    handle, name = tempfile.mkstemp(prefix=".mermaid-", suffix=".tmp", dir=target.parent)
    try:
        with os.fdopen(handle, "wb") as out:
            out.write(content)
        os.chmod(name, 0o644)
        os.replace(name, target)
    except BaseException:
        Path(name).unlink(missing_ok=True)
        raise


def ensure(
    root: Path = ROOT,
    theme_dir: str = THEME_DIR,
    *,
    tarball: Path | None = None,
    force: bool = False,
    log=print,
) -> bool:
    """Make sure the pinned file is in place. Return True when it was written.

    `tarball`: a local copy of the pinned tarball to use instead of the
    download (it goes through the same integrity check).
    """
    target = target_path(root, theme_dir)
    if not force and is_current(target):
        return False
    with tempfile.TemporaryDirectory(prefix="fetch-vendor-") as scratch:
        if tarball is None:
            tarball = Path(scratch) / f"{PACKAGE}-{VERSION}.tgz"
            log(f"fetch_vendor: downloading {TARBALL_URL}")
            download(TARBALL_URL, tarball)
        elif not tarball.is_file():
            raise VendorError(f"{tarball} is not a file")
        check_tarball(tarball)
        install(extract_member(tarball), target)
    log(f"fetch_vendor: {PACKAGE} {VERSION} -> {target.relative_to(root)}")
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=ROOT, help="repository root")
    parser.add_argument("--theme-dir", default=THEME_DIR, help="theme directory (custom_dir), relative to the root")
    parser.add_argument("--check", action="store_true", help="verify the file in place, download nothing")
    parser.add_argument("--force", action="store_true", help="fetch and rewrite even when the file is in place")
    parser.add_argument("--tarball", type=Path, help=f"local copy of {PACKAGE}-{VERSION}.tgz to use instead of the download")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    theme_dir = args.theme_dir.strip("/")
    target = target_path(root, theme_dir)
    try:
        if args.check:
            if not target.is_file():
                raise VendorError(f"{target} is missing: run python3 tools/site/fetch_vendor.py")
            if not is_current(target):
                raise VendorError(
                    f"{target} is not {MEMBER} of {PACKAGE} {VERSION} "
                    f"(SHA-256 {sha256_of(target)}, expected {FILE_SHA256})"
                )
            print(f"fetch_vendor: {target.relative_to(root)} is {PACKAGE} {VERSION}")
            return 0
        if not ensure(root, theme_dir, tarball=args.tarball, force=args.force):
            print(f"fetch_vendor: {target.relative_to(root)} is already {PACKAGE} {VERSION}")
        return 0
    except VendorError as error:
        print(f"fetch_vendor: error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
