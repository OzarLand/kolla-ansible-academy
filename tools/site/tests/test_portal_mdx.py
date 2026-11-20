"""Unit tests for the portal Markdown helpers.

Run from the repository root with the documentation dependencies installed::

    PYTHONPATH=tools/site python3 -m unittest discover -s tools/site/tests -v
"""

from __future__ import annotations

import pickle
import re
import unittest

import markdown

from portal_mdx import GithubSlugger, gh_slug, gh_slugify

EXTENSIONS = [
    "admonition",
    "md_in_html",
    "tables",
    "def_list",
    "footnotes",
    "sane_lists",
    "toc",
    "pymdownx.highlight",
    "pymdownx.inlinehilite",
    "pymdownx.superfences",
    "pymdownx.details",
    "pymdownx.tabbed",
    "pymdownx.quotes",
    "portal_mdx",
]
CONFIGS = {
    "toc": {"permalink": True, "slugify": gh_slugify()},
    "pymdownx.quotes": {"callouts": True},
    "pymdownx.tabbed": {"alternate_style": True},
    "pymdownx.superfences": {
        "custom_fences": [{"name": "mermaid", "class": "mermaid"}]
    },
}

CODE = '<span class="ev ev-code">CODE</span>'
NA = '<span class="ev ev-na">NOT AVAILABLE</span>'


def render(source: str, extra_extensions: tuple[str, ...] = (), **portal_options: object) -> str:
    configs = dict(CONFIGS)
    if portal_options:
        configs["portal_mdx"] = portal_options
    md = markdown.Markdown(
        extensions=[*EXTENSIONS, *extra_extensions], extension_configs=configs
    )
    return md.convert(source)


def render_with_toc(source: str) -> tuple[str, list[dict]]:
    md = markdown.Markdown(extensions=EXTENSIONS, extension_configs=dict(CONFIGS))
    html = md.convert(source)
    return html, md.toc_tokens  # type: ignore[attr-defined]


def text_of(html: str) -> str:
    """Visible text, roughly what a search indexer extracts."""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html)).strip()


class SlugTest(unittest.TestCase):
    def test_matches_github_on_corpus_headings(self) -> None:
        cases = {
            "1. Matrix": "1-matrix",
            "2. Heat map (likelihood × severity)": "2-heat-map-likelihood--severity",
            "3. Pre-execution checklist (applies to every production run)":
                "3-pre-execution-checklist-applies-to-every-production-run",
            "A.2 What changes, per type of change [CODE]":
                "a2-what-changes-per-type-of-change-code",
            "2.9 Apply common changes (fluentd, cron, kolla_toolbox)":
                "29-apply-common-changes-fluentd-cron-kolla_toolbox",
            "Everything marked [NOT AVAILABLE]": "everything-marked-not-available",
            "3. Quick lookup: tag → scope → typical impact":
                "3-quick-lookup-tag--scope--typical-impact",
            "08 — Operational Risk Matrix": "08--operational-risk-matrix",
            "A.1 Execution sequence (kolla-ansible -t nova reconfigure)":
                "a1-execution-sequence-kolla-ansible--t-nova-reconfigure",
            "Écriture & lecture": "écriture--lecture",
            "R12": "r12",
        }
        for heading, slug in cases.items():
            with self.subTest(heading=heading):
                self.assertEqual(gh_slug(heading), slug)

    def test_no_collapsing_and_no_trimming_of_hyphens(self) -> None:
        self.assertEqual(gh_slug("a  -  b"), "a-----b")
        self.assertEqual(gh_slug("- leading"), "--leading")

    def test_factory_returns_picklable_callable(self) -> None:
        fn = gh_slugify()
        self.assertEqual(fn("Tag index", "-"), "tag-index")
        # Zensical pickles the extension configuration to hash it.
        self.assertIs(pickle.loads(pickle.dumps(fn)), fn)
        self.assertIs(gh_slugify(case="lower"), fn)

    def test_slugger_uses_github_duplicate_suffixes(self) -> None:
        slugger = GithubSlugger()
        self.assertEqual(
            [slugger.slug(h) for h in ["Risks", "Risks", "Risks", "Risks 1"]],
            ["risks", "risks-1", "risks-2", "risks-1-1"],
        )


class EvidenceTest(unittest.TestCase):
    def test_running_text(self) -> None:
        html = render("Restarts every agent [CODE]; flows are [NOT AVAILABLE].")
        self.assertEqual(
            html, f"<p>Restarts every agent {CODE}; flows are {NA}.</p>"
        )

    def test_only_brackets_are_removed_from_the_text(self) -> None:
        source = "Restarts every agent [CODE]; flows are [NOT AVAILABLE]."
        self.assertEqual(
            text_of(render(source)), source.replace("[", "").replace("]", "")
        )

    def test_token_followed_by_colon_or_punctuation(self) -> None:
        html = render("[CODE]: the block above is ansible 2.8.20 `x.py:540`, same.")
        self.assertIn(f"<p>{CODE}: the block above", html)
        self.assertIn(f"({NA})", render("Unknown ([NOT AVAILABLE])."))

    def test_emphasis_tables_lists_and_alerts(self) -> None:
        self.assertIn(f"<strong>{CODE}</strong>", render("**[CODE]**"))
        table = render("| a | b |\n|---|---|\n| x [CODE] | [NOT AVAILABLE] whether |")
        self.assertIn(f"<td>x {CODE}</td>", table)
        self.assertIn(f"<td>{NA} whether</td>", table)
        self.assertIn(f"<li>item {NA}</li>", render("- item [NOT AVAILABLE]"))
        alert = render("> [!WARNING]\n> Outcome is [NOT AVAILABLE].")
        self.assertIn('class="admonition warning"', alert)
        self.assertIn(f"Outcome is {NA}.", alert)

    def test_wrapped_label(self) -> None:
        self.assertIn(NA, render("whether running VMs keep running is [NOT\nAVAILABLE]."))
        self.assertIn(NA, render("> quoted text that wraps [NOT\n> AVAILABLE] here"))

    def test_code_spans_and_blocks_are_untouched(self) -> None:
        self.assertEqual(
            render("Use `[CODE]` and ``x [NOT AVAILABLE] y``."),
            "<p>Use <code>[CODE]</code> and <code>x [NOT AVAILABLE] y</code>.</p>",
        )
        fenced = render("```text\nlabel [CODE] and [NOT AVAILABLE]\n```")
        self.assertIn("[CODE]", fenced)
        self.assertIn("[NOT AVAILABLE]", fenced)
        self.assertNotIn('class="ev', fenced)
        indented = render("para\n\n    indented [CODE]\n")
        self.assertIn("indented [CODE]", indented)
        self.assertNotIn('class="ev', indented)
        mermaid = render('```mermaid\nflowchart TD\n  A["x [CODE]"] --> B[NOT AVAILABLE]\n```')
        self.assertIn('<pre class="mermaid">', mermaid)
        self.assertNotIn('class="ev', mermaid)

    def test_raw_html_is_untouched(self) -> None:
        html = render("<div>raw [CODE]</div>\n\ntext <kbd>[CODE]</kbd> [CODE]")
        self.assertIn("<div>raw [CODE]</div>", html)
        self.assertIn("<kbd>[CODE]</kbd>", html)
        self.assertEqual(html.count('class="ev'), 1)
        html = render('a <code class="x">[CODE] b</code> c [NOT AVAILABLE] <code>[CODE]</code>')
        self.assertIn('<code class="x">[CODE] b</code>', html)
        self.assertIn(f"c {NA} <code>[CODE]</code>", html)
        # Other inline HTML is ordinary Markdown context, as on GitHub.
        self.assertIn(f"<em>{CODE}</em>", render("x <em>[CODE]</em>"))
        self.assertIn(f"one<br>{NA}", render("| a |\n|---|\n| one<br>[NOT AVAILABLE] |"))

    def test_markdown_in_html_is_processed(self) -> None:
        html = render('<div class="grid cards" markdown>\n\n- item [CODE]\n\n</div>')
        self.assertIn(f"item {CODE}", html)

    def test_only_exact_tokens(self) -> None:
        # `[CODE: note]` variants are chips with a note: EvidenceNoteTest.
        for source in (
            "[code]",
            "[Code]",
            "[ CODE ]",
            "[NOT  AVAILABLE]",
            "[everything marked NOT AVAILABLE]",
            "CODE and NOT AVAILABLE without brackets",
            "\\[CODE\\]",
        ):
            with self.subTest(source=source):
                self.assertNotIn('class="ev', render(source))

    def test_links_stay_links(self) -> None:
        html = render("[CODE](https://example.org/x) and [NOT AVAILABLE](y.md)")
        self.assertNotIn('class="ev', html)
        self.assertIn('<a href="https://example.org/x">CODE</a>', html)
        html = render("[CODE][ref]\n\n[ref]: https://example.org/")
        self.assertNotIn('class="ev', html)
        self.assertIn('<a href="https://example.org/">CODE</a>', html)

    def test_token_inside_link_text_and_next_to_links(self) -> None:
        html = render("[all [NOT AVAILABLE] items](x.md#y) [CODE] [R12](r.md#r12)")
        self.assertIn(f'<a href="x.md#y">all {NA} items</a>', html)
        self.assertIn(f"{CODE} <a href=\"r.md#r12\">R12</a>", html)

    def test_option_disables_chips(self) -> None:
        self.assertEqual(render("x [CODE]", evidence=False), "<p>x [CODE]</p>")


class EvidenceNoteTest(unittest.TestCase):
    def test_variants_become_chip_and_note(self) -> None:
        html = render(
            "a [CODE: no `ansible.cfg` here; [sheet E](e.md#x)] b [CODE, `site.yml`] "
            "c [CODE; consequences NOT AVAILABLE] d [NOT AVAILABLE: Docker semantics]"
        )
        self.assertIn(
            '<span class="ev-note"><span class="ev ev-code">CODE</span> (no <code>ansible.cfg</code> here; '
            '<a href="e.md#x">sheet E</a>)</span>',
            html,
        )
        self.assertIn('<span class="ev ev-code">CODE</span> (<code>site.yml</code>)</span>', html)
        self.assertIn('<span class="ev ev-code">CODE</span> (consequences NOT AVAILABLE)</span>', html)
        self.assertIn('<span class="ev ev-na">NOT AVAILABLE</span> (Docker semantics)</span>', html)

    def test_unclosed_escaped_and_code_are_left_alone(self) -> None:
        for source in ("x [CODE unclosed", "`[CODE: in code]`", "\\[CODE: escaped]"):
            with self.subTest(source=source):
                self.assertNotIn("ev-note", render(source))
        self.assertIn("[CODE unclosed", render("x [CODE unclosed"))

    def test_exact_token_and_link_unchanged(self) -> None:
        html = render("[CODE] and [CODE](u)")
        self.assertIn('<span class="ev ev-code">CODE</span> and <a href="u">CODE</a>', html)


class HeadingIdTest(unittest.TestCase):
    def test_heading_with_token_keeps_github_id(self) -> None:
        html, toc = render_with_toc(
            "# T\n\n### A.2 What changes, per type of change [CODE]\n\n"
            "## Everything marked [NOT AVAILABLE]\n"
        )
        self.assertIn('<h3 id="a2-what-changes-per-type-of-change-code">', html)
        self.assertIn(f"per type of change {CODE}", html)
        self.assertIn('<h2 id="everything-marked-not-available">', html)
        ids = [child["id"] for child in toc[0]["children"]]
        self.assertEqual(
            ids,
            ["a2-what-changes-per-type-of-change-code", "everything-marked-not-available"],
        )

    def test_ids_equal_plain_github_slug_of_source_text(self) -> None:
        headings = [
            "2. Heat map (likelihood × severity)",
            "B.2 What restarts [CODE]",
            "2.9 Apply `common` changes (fluentd, cron, kolla_toolbox)",
            "3. Quick lookup: tag → scope → typical impact",
            "D.1 How image pulling and recreation work [CODE]",
            "A & B < C",
            "*Really* **bold** [link](x.md)",
        ]
        source = "\n\n".join(f"## {h}" for h in headings)
        html = render(source)
        ids = re.findall(r'<h2 id="([^"]*)"', html)
        expected = [
            "2-heat-map-likelihood--severity",
            "b2-what-restarts-code",
            "29-apply-common-changes-fluentd-cron-kolla_toolbox",
            "3-quick-lookup-tag--scope--typical-impact",
            "d1-how-image-pulling-and-recreation-work-code",
            "a--b--c",
            "really-bold-link",
        ]
        self.assertEqual(ids, expected)

    def test_toc_label_keeps_the_text(self) -> None:
        _, toc = render_with_toc("## B.2 What restarts [CODE]\n")
        self.assertEqual(toc[0]["name"], "B.2 What restarts CODE")

    def test_repeated_headings_get_github_suffixes(self) -> None:
        html = render("## Risks\n\n## Risks\n\n### Risks\n\n## Verification\n")
        self.assertEqual(
            re.findall(r'<h[23] id="([^"]*)"', html),
            ["risks", "risks-1", "risks-2", "verification"],
        )

    def test_explicit_ids_are_kept(self) -> None:
        # Only reachable when someone enables `attr_list`; the portal does not.
        html = render(
            "## Risks {#custom}\n\n## Custom\n\n## Risks\n", extra_extensions=("attr_list",)
        )
        self.assertEqual(
            re.findall(r'<h2 id="([^"]*)"', html), ["custom", "custom-1", "risks"]
        )

    def test_braces_are_text_as_on_github(self) -> None:
        html = render("## Exit codes {0,1}\n\n| a |\n|---|\n| fails if rc ∉ {0,1} |\n")
        self.assertIn('<h2 id="exit-codes-01">Exit codes {0,1}', html)
        self.assertIn("<td>fails if rc ∉ {0,1}</td>", html)

    def test_item_anchor_before_heading(self) -> None:
        # SPEC: `<a id="r12"></a>` then `### R12`. While the heading is the
        # bare identifier both would carry the same id: the redundant anchor
        # paragraph is dropped, the heading keeps the id.
        html = render('<a id="r12"></a>\n\n### R12\n\ntext\n')
        self.assertEqual(html.count('id="r12"'), 1)
        self.assertIn('<h3 id="r12">R12', html)
        self.assertNotIn("<p></p>", html)
        # Once the heading has a title the anchor is the stable target.
        html = render('<a id="r12"></a>\n\n### R12 — Tag change through deploy\n\ntext\n')
        self.assertIn('<a id="r12"></a>', html)
        self.assertIn('<h3 id="r12--tag-change-through-deploy">', html)
        # Other inline HTML and anchors with content are left alone.
        html = render('<a id="x"></a> text\n\n### X\n')
        self.assertIn('<a id="x"></a> text', html)
        self.assertIn('<h3 id="x">', html)

    def test_without_anchor_feature_toc_uses_the_slug_function(self) -> None:
        html = render("## Heat map (likelihood × severity)\n", anchors=False)
        self.assertIn('<h2 id="heat-map-likelihood--severity">', html)


class GithubListsTest(unittest.TestCase):
    """Structures taken from the corpus; expected trees are what GitHub shows."""

    @staticmethod
    def tree(html: str) -> str:
        """Compact list structure: `ol[li(a) ul[li(b)]]`."""
        html = re.sub(
            r"<(/?)(ul|ol|li)\b[^>]*>", lambda m: f"\x00{m.group(1)}{m.group(2)}\x00", html
        )
        out, text = [], ""
        for part in html.split("\x00"):
            if part in ("ul", "ol"):
                out.append(f"{part}[")
            elif part in ("/ul", "/ol"):
                out.append("]")
            elif part == "li":
                out.append("li(")
                text = "open"
            elif part == "/li":
                out.append(")")
            elif text == "open":
                words = re.sub(r"<[^>]+>", "", part).split()
                out.append(words[0] if words else "")
                text = ""
        return "".join(out)

    def test_nested_under_numbered_and_bullet_items(self) -> None:
        html = render(
            "1. **Know** the diff.\n"
            "   - Run `genconfig` with the same tags. This writes config but\n"
            "     restarts nothing.\n"
            "   - Then diff.\n"
            "2. **Restart** set.\n"
            "3. **Batch** size.\n"
            "   - `ANSIBLE_SERIAL` covers reconfigure.\n"
            "\n"
            "- top\n"
            "  - two\n"
            "    - four\n"
            "  - back\n"
        )
        self.assertEqual(
            self.tree(html),
            "ol[li(Knowul[li(Run)li(Then)])li(Restart)li(Batchul[li(ANSIBLE_SERIAL)])]"
            "ul[li(topul[li(twoul[li(four)])li(back)])]",
        )
        self.assertIn("restarts nothing.</li>", html)

    def test_list_right_after_a_paragraph(self) -> None:
        html = render("How the evidence was gathered:\n- **Code** reading.\n- **Ansible** semantics.\n")
        self.assertIn("<p>How the evidence was gathered:</p>", html)
        self.assertEqual(self.tree(html), "ul[li(Code)li(Ansible)]")

    def test_only_a_list_starting_at_one_interrupts_a_paragraph(self) -> None:
        html = render("released in\n2019. A second sentence\nfollows.\n")
        self.assertNotIn("<ol", html)
        html = render("Steps:\n1. first\n2. second\n")
        self.assertEqual(self.tree(html), "ol[li(first)li(second)]")

    def test_wrapped_item_text_is_not_a_new_item(self) -> None:
        html = render("- item that wraps\nlazily here\n  and here\n- next\n")
        self.assertEqual(self.tree(html), "ul[li(item)li(next)]")
        self.assertIn("lazily here", html)

    def test_fenced_code_inside_an_item(self) -> None:
        html = render(
            "- **Bug** (`:320-323`):\n"
            "  ```bash\n"
            "  (--ask-vault-pass)\n"
            "          VERBOSITY=\"$EXTRA_OPTS\"\n"
            "  - not an item\n"
            "  ```\n"
            "  It should append.\n"
            "- **Next** bug\n"
        )
        self.assertEqual(self.tree(html), "ul[li(Bug)li(Next)]")
        code = re.search(r"<pre>(.*?)</pre>", html, re.S).group(1)
        self.assertEqual(
            re.sub(r"<[^>]+>", "", code).replace("&quot;", '"'),
            '(--ask-vault-pass)\n        VERBOSITY="$EXTRA_OPTS"\n- not an item\n',
        )
        self.assertIn("It should append.", html)

    def test_parent_item_right_after_nested_block(self) -> None:
        # A parent-level item follows a nested code block, sub-list or table
        # without a blank line (fact sheet A, section 1.8).
        html = render(
            "- **(F)** Upgrade\n"
            "  ```yaml\n"
            "  vars: 1\n"
            "  ```\n"
            "  - On upgrade\n"
            "  - **Likely** bug\n"
            "    - So an interface\n"
            "- **(G)** Things\n"
            "  - sysctl\n"
            "- **(H)** Non-local\n"
        )
        self.assertEqual(
            self.tree(html),
            "ul[li((F)ul[li(On)li(Likelyul[li(So)])])li((G)ul[li(sysctl)])li((H))]",
        )

    def test_bullets_after_numbered_items_at_the_same_level(self) -> None:
        html = render(
            "- **reconfigure**\n"
            "  1. It builds\n"
            "  2. It fails\n"
            "  - Under COPY_ALWAYS\n"
            "- **upgrade**\n"
        )
        self.assertEqual(
            self.tree(html), "ul[li(reconfigureol[li(It)li(It)]ul[li(Under)])li(upgrade)]"
        )

    def test_table_inside_an_item_then_sibling(self) -> None:
        html = render(
            "- **Where** it runs:\n"
            "\n"
            "  | Command | Hosts |\n"
            "  |---|---|\n"
            "  | `-t nova` | all nova hosts |\n"
            "- **What** it can change:\n"
            "  - `td-agent.conf`\n"
        )
        self.assertEqual(self.tree(html), "ul[li(Wheretable)li(Whatul[li(td-agent.conf)])]".replace("table", ""))
        self.assertEqual(html.count("<tr>"), 2)

    def test_lists_inside_alerts(self) -> None:
        html = render(
            "> [!NOTE]\n> **Key answers**\n> - first\n>   - nested\n> - second\n"
        )
        self.assertIn('class="admonition note"', html)
        self.assertEqual(self.tree(html), "ul[li(firstul[li(nested)])li(second)]")

    def test_numbered_list_keeps_its_first_number_and_type(self) -> None:
        html = render("3. three\n4. four\n\n- bullet\n")
        self.assertIn('<ol start="3">', html)
        self.assertEqual(self.tree(html), "ol[li(three)li(four)]ul[li(bullet)]")

    def test_grid_cards(self) -> None:
        html = render(
            '<div class="grid cards" markdown>\n\n'
            "- **[Title](page.md)**\n\n    ---\n\n    Text.\n\n"
            "- **Second**\n\n    ---\n\n    More.\n\n</div>\n"
        )
        self.assertEqual(html.count("<li>"), 2)
        self.assertEqual(html.count("<hr"), 2)
        self.assertIn("<p>Text.</p>", html)
        self.assertIn('<div class="grid cards">', html)

    def test_second_paragraph_of_an_item(self) -> None:
        html = render("- item\n\n  second paragraph\n- next\n\nafter\n")
        self.assertEqual(self.tree(html), "ul[li(item)li(next)]")
        self.assertIn("<p>second paragraph</p>\n</li>", html)
        self.assertIn("<p>after</p>", html)

    def test_four_space_sources_are_unchanged(self) -> None:
        from portal_mdx.lists import normalize

        source = (
            "1. one\n    - nested\n        - deeper\n2. two\n\n"
            "```text\n- not a list\n  - at all\n```\n\n"
            "    indented code\n    - still code\n\n"
            "Title\n---\n\n* * *\n\n"
            "| a | b |\n|---|---|\n| 1 | 2 |\n"
        ).split("\n")
        self.assertEqual(normalize(source), source)

    def test_option_disables_the_normaliser(self) -> None:
        html = render("text:\n- item\n", lists=False)
        self.assertNotIn("<ul>", html)


class PlaceholdersTest(unittest.TestCase):
    def test_unknown_tag_shaped_tokens_stay_visible(self) -> None:
        html = render('Handlers are named "Restart <svc> container" on <host-1>, see </svc>.\n')
        self.assertIn("Restart &lt;svc&gt; container", html)
        self.assertIn("&lt;host-1&gt;", html)
        self.assertIn("&lt;/svc&gt;", html)

    def test_tables_lists_headings_and_alerts(self) -> None:
        html = render(
            "## Restart <svc>\n\n- item <svc>\n\n| a |\n|---|\n| <svc> x |\n\n> [!NOTE]\n> for <svc>\n"
        )
        self.assertEqual(html.count("&lt;svc&gt;"), 4)
        self.assertNotIn("<svc>", html)
        self.assertIn('id="restart-svc"', html)

    def test_html_elements_keep_their_meaning(self) -> None:
        html = render('one<br>two <kbd>Ctrl</kbd> <a id="r12"></a> <span class="x">y</span> <B>b</B>\n')
        for tag in ("<br>", "<kbd>Ctrl</kbd>", '<a id="r12"></a>', '<span class="x">y</span>', "<B>b</B>"):
            self.assertIn(tag, html)

    def test_code_autolinks_and_comments_are_untouched(self) -> None:
        html = render(
            "`docker exec <c> true` and <https://example.org/x>\n\n<!-- note <svc> -->\n\n"
            "```text\nroles/<svc>/\n```\n"
        )
        self.assertIn("<code>docker exec &lt;c&gt; true</code>", html)
        self.assertIn('<a href="https://example.org/x">', html)
        self.assertIn("<!-- note <svc> -->", html)
        self.assertIn("roles/&lt;svc&gt;/", html)
        self.assertNotIn("&amp;lt;", html)

    def test_evidence_chips_next_to_a_placeholder(self) -> None:
        html = render("Restart <svc> [CODE].\n")
        self.assertIn("&lt;svc&gt; " + CODE, html)

    def test_option_restores_raw_html(self) -> None:
        self.assertIn("<svc>", render("Restart <svc> now\n", placeholders=False))


class TablePipesTest(unittest.TestCase):
    def test_escaped_pipe_in_table_code(self) -> None:
        html = render(
            "| a | b |\n|---|---|\n"
            "| `{{ kolla_serial \\| default(\"0\") }}` and \\| | x |\n\n"
            "Outside a table `a \\| b` stays.\n"
        )
        self.assertIn('<td><code>{{ kolla_serial | default("0") }}</code> and |</td>', html)
        self.assertIn("<code>a \\| b</code> stays", html)

    def test_option_keeps_the_backslash(self) -> None:
        html = render("| a |\n|---|\n| `x \\| y` |\n", pipes=False)
        self.assertIn("<code>x \\| y</code>", html)


class TableBreaksTest(unittest.TestCase):
    @staticmethod
    def text_of(html: str) -> str:
        return re.sub(r"<[^>]+>", "", html)

    def test_paths_and_line_ranges_in_table_code(self) -> None:
        source = (
            "| Evidence |\n|---|\n"
            "| `roles/neutron/tasks/rolling_upgrade.yml:13-33,43-67` and `kolla_docker.py:781-803,873-875` |\n"
        )
        # Without the citation class, to see the breaks alone (CitesTest covers both).
        html = render(source, cites=False)
        self.assertIn(
            "<code>roles/<wbr>neutron/<wbr>tasks/<wbr>rolling_upgrade.yml:13-33,<wbr>43-67</code>", html
        )
        self.assertIn("<code>kolla_docker.py:781-803,<wbr>873-875</code>", html)
        # Same text with and without the feature.
        self.assertEqual(self.text_of(html), self.text_of(render(source, breaks=False, cites=False)))
        self.assertNotIn("<wbr>", render(source, breaks=False))

    def test_only_code_spans_of_table_cells(self) -> None:
        html = render(
            "Text `roles/neutron/tasks/config.yml:73-106` and a/long/path/in/running/text.\n\n"
            "| a |\n|---|\n| plain roles/neutron/tasks/config.yml and [a link](x/y/z/some/long/target.md) |\n\n"
            "```bash\ncat /etc/kolla/config/neutron/ml2_conf.ini\n```\n"
        )
        self.assertNotIn("<wbr>", html)

    def test_short_spans_urls_and_separators(self) -> None:
        html = render(
            "| a |\n|---|\n"
            "| `n/a` `rc in {0,1}` `https://example.org/some/page` `a / b / c / d / e / f` `x/` `/etc/kolla/config/`|\n"
        )
        self.assertIn("<code>n/a</code>", html)
        self.assertIn("<code>rc in {0,1}</code>", html)
        self.assertIn("<code>https://example.org/<wbr>some/<wbr>page</code>", html)
        self.assertIn("<code>a / b / c / d / e / f</code>", html)
        self.assertIn("<code>/etc/<wbr>kolla/<wbr>config/</code>", html)

    def test_escaped_text_and_pipes(self) -> None:
        html = render(
            "| a |\n|---|\n| `roles/<svc>/templates/<svc>.conf.j2 \\| path/with/pipe` |\n"
        )
        self.assertIn(
            "<code>roles/<wbr>&lt;svc&gt;/<wbr>templates/<wbr>&lt;svc&gt;.conf.j2 | path/<wbr>with/<wbr>pipe</code>",
            html,
        )


class ImpactTest(unittest.TestCase):
    def test_exact_name_gets_class(self) -> None:
        html = render("| Page | Impact |\n|---|---|\n| A | `read-only`, `writes-config` |\n")
        self.assertIn('<code class="impact impact--read-only">read-only</code>', html)
        self.assertIn('<code class="impact impact--writes-config">writes-config</code>', html)

    def test_all_eight_names(self) -> None:
        from portal_mdx.impact import IMPACT_CLASSES

        self.assertEqual(len(IMPACT_CLASSES), 8)
        html = render(" ".join(f"`{name}`" for name in sorted(IMPACT_CLASSES)))
        self.assertEqual(html.count('class="impact impact--'), 8)

    def test_other_code_is_left_alone(self) -> None:
        html = render("`--read-only` and `critical: true` and `nova`\n\n```text\ncritical\n```\n")
        self.assertNotIn("impact", html)

    def test_text_is_unchanged_and_option_turns_it_off(self) -> None:
        self.assertIn("<code>recovery</code>", render("`recovery`", impact=False))
        self.assertIn(">recovery</code>", render("`recovery`"))


class CitesTest(unittest.TestCase):
    def test_citations_get_the_class(self) -> None:
        html = render(
            "See `site.yml:88-103`, `roles/nova-cell/handlers/main.yml:74-168, :170`, "
            "`:140-203` and `tools/kolla-ansible:10-11`.\n"
        )
        self.assertIn('<code class="cite">site.yml:88-103</code>', html)
        self.assertIn('<code class="cite">roles/nova-cell/handlers/main.yml:74-168, :170</code>', html)
        self.assertIn('<code class="cite">:140-203</code>', html)
        self.assertIn('<code class="cite">tools/kolla-ansible:10-11</code>', html)

    def test_table_citations_keep_their_breaks(self) -> None:
        html = render("| Evidence |\n|---|\n| `roles/neutron/tasks/rolling_upgrade.yml:13-33,43-67` |\n")
        self.assertIn(
            '<code class="cite">roles/<wbr>neutron/<wbr>tasks/<wbr>rolling_upgrade.yml:13-33,<wbr>43-67</code>',
            html,
        )

    def test_other_code_is_left_alone(self) -> None:
        html = render(
            "`kolla-ansible -i multinode genconfig`, `site.yml`, `serial: 0`, `key: value`, "
            "`http://host:5000`, `a:b`, `-e kolla_serial=1`\n\n```yaml\nfoo: 1\n```\n"
        )
        self.assertNotIn("cite", html)

    def test_option_turns_it_off(self) -> None:
        self.assertIn("<code>site.yml:1</code>", render("`site.yml:1`", cites=False))


class LabelsTest(unittest.TestCase):
    def test_wide_table_cells_get_labels(self) -> None:
        html = render("| Tag | Hosts | Restarts | Risk |\n|---|---|---|---|\n| `nova` | computes | libvirt | R1 |\n")
        self.assertIn('<table data-portal-cards="">', html)
        self.assertIn('<td data-label="Tag"><code>nova</code></td>', html)
        self.assertIn('<td data-label="Risk">R1</td>', html)

    def test_narrow_tables_are_left_alone(self) -> None:
        html = render("| a | b | c |\n|---|---|---|\n| 1 | 2 | 3 |\n")
        self.assertNotIn("data-label", html)
        self.assertNotIn("data-portal-cards", html)

    def test_option_turns_it_off(self) -> None:
        html = render("| a | b | c | d |\n|---|---|---|---|\n| 1 | 2 | 3 | 4 |\n", labels=False)
        self.assertNotIn("data-label", html)


class SeverityTest(unittest.TestCase):
    SUMMARY = (
        "| # | Likelihood | Severity |\n|---|---|---|\n"
        "| R1 | High | High |\n| R11 | – | Low (bandwidth) |\n"
        "| R16 | Low | **Critical** |\n| R13 | – | Medium (drift) |\n| R0 | High | – |\n"
    )

    def test_severity_column(self) -> None:
        html = render(self.SUMMARY)
        self.assertEqual(html.count('class="sev '), 4)
        self.assertIn('<td class="sev sev-high">High</td>', html)
        self.assertIn('<td class="sev sev-low">Low (bandwidth)</td>', html)
        self.assertIn('<td class="sev sev-critical"><strong>Critical</strong></td>', html)
        self.assertIn('<td class="sev sev-medium">Medium (drift)</td>', html)
        # The likelihood column is not a severity column.
        self.assertIn("<td>R1</td>\n<td>High</td>", html)

    def test_key_value_row(self) -> None:
        html = render(
            "| | |\n|---|---|\n| **Operation / trigger** | High load |\n"
            "| **Likelihood** | High |\n| **Severity** | Critical |\n"
        )
        self.assertEqual(html.count('class="sev '), 1)
        self.assertIn('<td class="sev sev-critical">Critical</td>', html)
        self.assertIn("<td>High load</td>", html)

    def test_range_takes_the_higher_level(self) -> None:
        html = render(
            "| # | Severity |\n|---|---|\n| R2 | Medium–High |\n| R3 | Low - Medium |\n"
            "| R4 | High/Critical |\n| R5 | Highly unusual |\n| R6 | Lowest |\n"
            "| R23 | Low (time), Medium (drift) |\n| R25 | Low–Medium (surprise) |\n"
            "| R7 | Low (high confidence) |\n"
        )
        self.assertIn('<td class="sev sev-medium">Low (time), Medium (drift)</td>', html)
        self.assertIn('<td class="sev sev-medium">Low–Medium (surprise)</td>', html)
        self.assertIn('<td class="sev sev-low">Low (high confidence)</td>', html)
        self.assertIn('<td class="sev sev-high">Medium–High</td>', html)
        self.assertIn('<td class="sev sev-medium">Low - Medium</td>', html)
        self.assertIn('<td class="sev sev-critical">High/Critical</td>', html)
        self.assertIn("<td>Highly unusual</td>", html)
        self.assertIn("<td>Lowest</td>", html)

    def test_other_tables_are_untouched(self) -> None:
        html = render("| Tag | Impact |\n|---|---|\n| nova | High |\n")
        self.assertNotIn("sev", html)

    def test_option_disables_classes(self) -> None:
        self.assertNotIn('class="sev', render(self.SUMMARY, severity=False))


if __name__ == "__main__":
    unittest.main()
