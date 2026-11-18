"""Unit tests for tools/site/serve_site.py (standard library only)."""

from __future__ import annotations

import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import serve_site  # noqa: E402


class ServeSiteTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        site = Path(self._tmp.name)
        (site / "2023.1").mkdir()
        (site / "index.html").write_text("landing", encoding="utf-8")
        (site / "404.html").write_text("portal not found", encoding="utf-8")
        (site / "2023.1/index.html").write_text("planned", encoding="utf-8")
        quiet = mock.patch.object(serve_site.Handler, "log_message", lambda *args: None)
        quiet.start()
        self.addCleanup(quiet.stop)
        self.server = serve_site.make_server(site, "/portal/", "127.0.0.1", 0)
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"

    def get(self, path: str) -> tuple[int, str]:
        try:
            with urllib.request.urlopen(self.base + path, timeout=10) as response:
                return response.status, response.read().decode("utf-8")
        except urllib.error.HTTPError as error:
            return error.code, error.read().decode("utf-8")

    def test_files_are_served_under_the_prefix(self) -> None:
        self.assertEqual(self.get("/portal/"), (200, "landing"))
        self.assertEqual(self.get("/portal/2023.1/"), (200, "planned"))
        self.assertEqual(self.get("/portal/2023.1/index.html?x=1"), (200, "planned"))

    def test_unknown_address_gets_the_root_not_found_page(self) -> None:
        self.assertEqual(self.get("/portal/operations/reconfigure-nova/"), (404, "portal not found"))
        self.assertEqual(self.get("/portal/2023.1/anything"), (404, "portal not found"))
        # Outside the prefix nothing is served, not even an existing file.
        self.assertEqual(self.get("/index.html"), (404, "portal not found"))


if __name__ == "__main__":
    unittest.main()
