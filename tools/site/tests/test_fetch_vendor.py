"""Unit tests for tools/site/fetch_vendor.py (standard library only, no network).

    python3 -m unittest discover -s tools/site/tests -v

The download is replaced by a small tarball built in a temporary directory;
the pinned digests of the module are replaced by the digests of that tarball.
"""

from __future__ import annotations

import base64
import contextlib
import hashlib
import importlib.util
import io
import re
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SITE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("fetch_vendor", SITE / "fetch_vendor.py")
fetch_vendor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fetch_vendor)

BUNDLE = b"/* test bundle */ window.mermaid = {};\n"


def make_tarball(path: Path, members: dict[str, bytes]) -> None:
    with tarfile.open(path, mode="w:gz") as archive:
        for name, content in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(content)
            archive.addfile(info, io.BytesIO(content))


def integrity(path: Path) -> str:
    return "sha512-" + base64.b64encode(hashlib.sha512(path.read_bytes()).digest()).decode("ascii")


class FakeResponse(io.BytesIO):
    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


class FetchVendorTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.root = self.tmp / "repo"
        self.root.mkdir(parents=True)
        self.target = self.root / "overrides/assets/vendor/mermaid/mermaid.min.js"
        self.tarball = self.tmp / "mermaid.tgz"
        make_tarball(
            self.tarball,
            {"package/package.json": b"{}", fetch_vendor.MEMBER: BUNDLE, "package/LICENSE": b"MIT"},
        )
        # Pin the module to the test tarball.
        self.pin(TARBALL_INTEGRITY=integrity(self.tarball), FILE_SHA256=hashlib.sha256(BUNDLE).hexdigest())
        self.messages: list[str] = []

    def pin(self, **values: str) -> None:
        for name, value in values.items():
            patcher = mock.patch.object(fetch_vendor, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def ensure(self, **kwargs: object) -> bool:
        return fetch_vendor.ensure(self.root, log=self.messages.append, **kwargs)

    # -- pinned values ---------------------------------------------------------

    def test_pinned_values_are_well_formed(self) -> None:
        module = importlib.util.module_from_spec(SPEC)  # unpatched copy
        SPEC.loader.exec_module(module)
        self.assertRegex(module.VERSION, r"^12\.\d+\.\d+$")
        self.assertEqual(
            module.TARBALL_URL, f"https://registry.npmjs.org/mermaid/-/mermaid-{module.VERSION}.tgz"
        )
        algorithm, _, digest = module.TARBALL_INTEGRITY.partition("-")
        self.assertEqual(algorithm, "sha512")
        self.assertEqual(len(base64.b64decode(digest, validate=True)), 64)
        self.assertRegex(module.FILE_SHA256, r"^[0-9a-f]{64}$")
        self.assertEqual(module.MEMBER, "package/dist/mermaid.min.js")

    def test_vendor_readme_states_the_pinned_release(self) -> None:
        module = importlib.util.module_from_spec(SPEC)
        SPEC.loader.exec_module(module)
        readme = SITE.parents[1] / "overrides/assets/vendor/mermaid/README.md"
        if not readme.is_file():
            self.skipTest("overrides/assets/vendor/mermaid/README.md is not in this tree")
        text = readme.read_text(encoding="utf-8")
        self.assertIn(module.VERSION, text)
        self.assertIn(module.TARBALL_INTEGRITY, text)
        self.assertIn(module.FILE_SHA256, text)
        versions = set(re.findall(r"\b12\.\d+\.\d+\b", text))
        self.assertEqual(versions, {module.VERSION}, "the README names another 12.x version")

    # -- ensure ----------------------------------------------------------------

    def test_installs_from_a_verified_tarball(self) -> None:
        self.assertTrue(self.ensure(tarball=self.tarball))
        self.assertEqual(self.target.read_bytes(), BUNDLE)
        self.assertEqual(sorted(p.name for p in self.target.parent.iterdir()), ["mermaid.min.js"])
        self.assertTrue(fetch_vendor.is_current(self.target))

    def test_second_run_does_nothing(self) -> None:
        self.ensure(tarball=self.tarball)
        stamp = self.target.stat().st_mtime_ns
        with mock.patch.object(fetch_vendor, "download", side_effect=AssertionError("network used")):
            self.assertFalse(self.ensure())
        self.assertEqual(self.target.stat().st_mtime_ns, stamp)

    def test_a_different_file_is_replaced(self) -> None:
        self.target.parent.mkdir(parents=True)
        self.target.write_bytes(b"something else")
        self.assertTrue(self.ensure(tarball=self.tarball))
        self.assertEqual(self.target.read_bytes(), BUNDLE)

    def test_tarball_with_another_digest_is_refused(self) -> None:
        other = self.tmp / "other.tgz"
        make_tarball(other, {fetch_vendor.MEMBER: BUNDLE + b"tampered"})
        with self.assertRaisesRegex(fetch_vendor.VendorError, "integrity mismatch"):
            self.ensure(tarball=other)
        self.assertFalse(self.target.exists())

    def test_file_with_another_digest_is_refused_and_the_old_file_is_kept(self) -> None:
        self.target.parent.mkdir(parents=True)
        self.target.write_bytes(b"old copy")
        self.pin(FILE_SHA256="0" * 64)
        with self.assertRaisesRegex(fetch_vendor.VendorError, "SHA-256 mismatch"):
            self.ensure(tarball=self.tarball)
        self.assertEqual(self.target.read_bytes(), b"old copy")
        self.assertEqual(sorted(p.name for p in self.target.parent.iterdir()), ["mermaid.min.js"])

    def test_tarball_without_the_file(self) -> None:
        empty = self.tmp / "empty.tgz"
        make_tarball(empty, {"package/package.json": b"{}"})
        self.pin(TARBALL_INTEGRITY=integrity(empty))
        with self.assertRaisesRegex(fetch_vendor.VendorError, "is not in the tarball"):
            self.ensure(tarball=empty)

    def test_not_a_tarball(self) -> None:
        junk = self.tmp / "junk.tgz"
        junk.write_bytes(b"<html>proxy error</html>")
        self.pin(TARBALL_INTEGRITY=integrity(junk))
        with self.assertRaisesRegex(fetch_vendor.VendorError, "cannot read the tarball"):
            self.ensure(tarball=junk)

    # -- download --------------------------------------------------------------

    def test_download_is_verified_and_installed(self) -> None:
        data = self.tarball.read_bytes()
        with mock.patch.object(fetch_vendor.urllib.request, "urlopen", return_value=FakeResponse(data)) as urlopen:
            self.assertTrue(self.ensure())
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, fetch_vendor.TARBALL_URL)
        self.assertEqual(self.target.read_bytes(), BUNDLE)
        self.assertTrue(any(fetch_vendor.TARBALL_URL in message for message in self.messages))

    def test_truncated_download_is_refused(self) -> None:
        data = self.tarball.read_bytes()[:-20]
        with mock.patch.object(fetch_vendor.urllib.request, "urlopen", return_value=FakeResponse(data)):
            with self.assertRaisesRegex(fetch_vendor.VendorError, "integrity mismatch"):
                self.ensure()
        self.assertFalse(self.target.exists())

    def test_download_error_is_reported_after_the_attempts(self) -> None:
        with (
            mock.patch.object(fetch_vendor.urllib.request, "urlopen", side_effect=OSError("no route")) as urlopen,
            mock.patch.object(fetch_vendor.time, "sleep"),
        ):
            with self.assertRaisesRegex(fetch_vendor.VendorError, "download failed.*no route"):
                self.ensure()
        self.assertEqual(urlopen.call_count, fetch_vendor.ATTEMPTS)
        self.assertFalse(self.target.exists())

    def test_only_https(self) -> None:
        with self.assertRaisesRegex(fetch_vendor.VendorError, "not https"):
            fetch_vendor.download("http://registry.npmjs.org/x.tgz", self.tmp / "x.tgz")

    # -- command line ----------------------------------------------------------

    def run_main(self, *args: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            status = fetch_vendor.main(["--root", str(self.root), *args])
        return status, out.getvalue(), err.getvalue()

    def test_command_line(self) -> None:
        status, _, err = self.run_main("--check")
        self.assertEqual(status, 1)
        self.assertIn("is missing", err)

        status, out, _ = self.run_main("--tarball", str(self.tarball))
        self.assertEqual(status, 0)
        self.assertIn("overrides/assets/vendor/mermaid/mermaid.min.js", out)

        status, out, _ = self.run_main("--tarball", str(self.tarball))
        self.assertEqual(status, 0)
        self.assertIn("already", out)

        self.assertEqual(self.run_main("--check")[0], 0)

        self.target.write_bytes(b"edited")
        status, _, err = self.run_main("--check")
        self.assertEqual(status, 1)
        self.assertIn("is not package/dist/mermaid.min.js", err)

    def test_command_line_reports_errors(self) -> None:
        status, _, err = self.run_main("--tarball", str(self.tmp / "missing.tgz"))
        self.assertEqual(status, 1)
        self.assertIn("fetch_vendor: error:", err)


if __name__ == "__main__":
    unittest.main()
