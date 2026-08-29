"""Characterization tests for normalize.py's public surface.

Frozen callables: TextCollector, visible_text, word_count, body_inner, xhtml,
XHTMLCleaner, extract_article, validate_xhtml, and normalized_path. Public
constants are WORD, CONTAMINATION, VOID, BLOCK_TAGS, DROP_SUBTREES, and
DROP_CLASSES.
"""

import re
import unittest
from xml.etree import ElementTree as ET

from quoin.normalize import CONTAMINATION, extract_article, visible_text, word_count


def normalized_text(markup: str) -> str:
    return " ".join(visible_text(markup).split())


class NormalizeCharacterizationTests(unittest.TestCase):
    def assert_fragment_parses(self, fragment: str) -> None:
        ET.fromstring(f"<root>{fragment}</root>")

    def test_mkdocs_unquoted_edit_attributes(self) -> None:
        markup = '<html><body><article><p>Keep</p><a class=md-content__button href=https://x rel=edit>Edit</a></article></body></html>'
        result = extract_article(markup)
        self.assert_fragment_parses(result)
        self.assertNotIn("Edit", result)
        self.assertNotIn("md-content__button", result)

    def test_headerlink_pilcrow_removed(self) -> None:
        markup = '<html><body><article><h2>Heading<a class="headerlink" href="#heading">¶</a></h2></article></body></html>'
        result = extract_article(markup)
        self.assertEqual(normalized_text(result), "Heading")
        self.assertNotIn("¶", result)

    def test_trailing_comments_removed_but_comments_policy_kept(self) -> None:
        markup = '<html><body><article><h2>Comments policy</h2><p>Keep this guidance.</p><h2>Comments</h2><p>Drop this discussion.</p></article></body></html>'
        result = extract_article(markup)
        self.assertIn("Comments policy", result)
        self.assertIn("Keep this guidance.", result)
        self.assertNotIn("Drop this discussion.", result)

    def test_substack_furniture_removed(self) -> None:
        markup = '<html><body><article><p>Keep</p><picture><source src="x"><span>fallback</span></picture><a href="https://x"><button>Act</button></a><svg><text>vector</text></svg><img src="https://substackcdn.com/image.jpg" alt="remote"></article></body></html>'
        result = extract_article(markup)
        self.assertEqual(normalized_text(result), "Keep")
        for furniture in ("picture", "button", "svg", "img", "substackcdn"):
            self.assertNotIn(furniture, result)

    def test_missing_cross_document_link_is_unwrapped(self) -> None:
        markup = '<html><body><article><a href="part0037.xhtml">linked text</a></article></body></html>'
        result = extract_article(markup)
        self.assertEqual(result, "<span>linked text</span>")

    def test_entities_preserve_visible_text(self) -> None:
        markup = '<html><body><article><p>A &amp; B&#8217;s&nbsp;work</p></article></body></html>'
        result = extract_article(markup)
        self.assert_fragment_parses(result)
        self.assertEqual(normalized_text(result), "A & B’s work")

    def test_clean_article_preserves_visible_text(self) -> None:
        body = '<h1>A title</h1><p>First <em>clean</em> paragraph.</p><blockquote>Quoted text.</blockquote>'
        markup = f"<html><body><article>{body}</article></body></html>"
        self.assertEqual(normalized_text(extract_article(markup)), normalized_text(body))

    def test_word_count_ignores_inter_tag_whitespace(self) -> None:
        compact = "<p>One <em>two</em> three</p>"
        spaced = "<p>One\n <em>two</em>\n three</p>"
        self.assertEqual(word_count(compact), word_count(spaced))
        self.assertEqual(word_count(compact), 3)

    def test_malformed_nesting_is_repaired_to_xml(self) -> None:
        markup = "<html><body><article><p>before<div>x</div></p></article></body></html>"
        result = extract_article(markup)
        self.assert_fragment_parses(result)
        self.assertEqual(normalized_text(result), "before x")

    def test_contamination_terms_and_mid_sentence_subscribe(self) -> None:
        terms = ("subscribe", "sign up", "newsletter", "cookie", "comments", "next post", "previous post")
        furniture = " | ".join(terms)
        for term in terms:
            with self.subTest(term=term):
                self.assertIsNotNone(CONTAMINATION.search(term))
        self.assertEqual([match.group(0).lower() for match in CONTAMINATION.finditer(furniture)], list(terms))
        # characterization: current behavior, revisit in plan 005
        self.assertIsNotNone(CONTAMINATION.search("Readers can subscribe to the journal mid-sentence."))

    def test_script_and_style_bodies_removed(self) -> None:
        markup = '<html><body><article><p>Keep</p><script>secretScript()</script><style>.secretStyle{}</style></article></body></html>'
        result = extract_article(markup)
        self.assertEqual(normalized_text(result), "Keep")
        self.assertNotRegex(result, re.compile("secretScript|secretStyle"))

    def test_empty_and_whitespace_only_input(self) -> None:
        # characterization: current behavior, revisit in plan 005
        self.assertEqual(extract_article("<html><body></body></html>"), "")
        self.assertEqual(extract_article("<html><body> \n\t </body></html>"), " \n\t ")


if __name__ == "__main__":
    unittest.main()
