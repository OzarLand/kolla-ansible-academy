"""Unit tests for tools/site/glossary.py (standard library only).

    python3 -m unittest discover -s tools/site/tests -v
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "glossary", Path(__file__).resolve().parents[1] / "glossary.py"
)
glossary = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(glossary)

TABLE = """# Glossary

| Term | Meaning in this study | Defined in |
|---|---|---|
| drift | What `compare_container` detects [CODE]. | [Operations, "Drift"](../operations/index.md#drift) |
| serial / batch (`kolla_serial`, `ANSIBLE_SERIAL`) | `serial` splits a play into **batches**. | [Execution flow §5](../concepts/deployment-execution-flow.md#5-batching) |
| restart vs recreate | Both are full stop/start cycles. | [Findings](findings.md#f1) |
| R*n*, F*n* | Risk and finding numbers. | [Risk register](../risk/risk-register.md#matrix) |
| [CODE] / [NOT AVAILABLE] | The two evidence labels. | [Conventions](../start/conventions.md) |
| scope legend D, Ctl | How often a task runs. | [Compute scaling §3](../concepts/compute-scaling.md#3) |

## Related

| Not | a | term |
"""


class ExtractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.terms = {term["term"]: term for term in glossary.extract(TABLE)}

    def test_notations_are_left_out(self) -> None:
        self.assertEqual(sorted(self.terms), ["drift", "restart vs recreate", "serial / batch (kolla_serial, ANSIBLE_SERIAL)"])

    def test_keys_and_words(self) -> None:
        serial = self.terms["serial / batch (kolla_serial, ANSIBLE_SERIAL)"]
        self.assertEqual(serial["keys"], ["serial", "batch", "kolla_serial", "ANSIBLE_SERIAL"])
        # The keys in parentheses are matched only as code.
        self.assertEqual(serial["words"], ["serial", "batch"])
        # "restart" is an everyday word of the pages: matched as code only.
        self.assertEqual(self.terms["restart vs recreate"]["keys"], ["restart", "recreate"])
        self.assertEqual(self.terms["restart vs recreate"]["words"], ["recreate"])

    def test_html_is_escaped_and_keeps_code_bold_and_evidence(self) -> None:
        self.assertEqual(
            self.terms["drift"]["html"],
            'What <code>compare_container</code> detects <span class="ev ev-code">CODE</span>.',
        )
        self.assertIn("<strong>batches</strong>", self.terms["serial / batch (kolla_serial, ANSIBLE_SERIAL)"]["html"])
        self.assertEqual(glossary.to_html("a <b> & [x](y.md)"), "a &lt;b&gt; &amp; x")

    def test_more_is_a_site_url_of_the_release(self) -> None:
        self.assertEqual(self.terms["drift"]["more"], "operations/#drift")
        self.assertEqual(self.terms["drift"]["more_text"], 'Operations, "Drift"')
        self.assertEqual(self.terms["restart vs recreate"]["more"], "reference/findings/#f1")

    def test_page_url(self) -> None:
        self.assertEqual(glossary.page_url("../risk/tags.md#24-x"), "risk/tags/#24-x")
        self.assertEqual(glossary.page_url("../index.md"), "")
        self.assertIsNone(glossary.page_url("https://example.org/a.md"))
        self.assertIsNone(glossary.page_url("../../outside.md"))


class WriteTest(unittest.TestCase):
    def test_writes_the_json_of_a_release(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "docs/r1/reference/glossary.md"
            source.parent.mkdir(parents=True)
            source.write_text(TABLE, encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                count = glossary.write_glossary(root, "docs/r1")
            self.assertEqual(count, 3)
            data = json.loads((root / "docs/r1/assets/data/glossary.json").read_text(encoding="utf-8"))
            self.assertEqual(data["glossary"], "reference/glossary/")
            self.assertEqual(len(data["terms"]), 3)

    def test_a_release_without_glossary_gets_no_terms(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs/r1").mkdir(parents=True)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(glossary.write_glossary(root, "docs/r1"), 0)


if __name__ == "__main__":
    unittest.main()
