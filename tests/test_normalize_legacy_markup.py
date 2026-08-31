"""Tests for two XHTMLCleaner fixes needed for real-world legacy pages
(paulgraham.com, kalzumeus.com style markup):

1. Inline-over-block nesting: an href-less <a> (or other inline tag) wrapping
   a block element must not emit <span><div>...</div></span> -- EPUBCheck
   rejects an inline element with block content (RSC-005). The contiguous run
   of open inline tags closes before the block tag opens.
2. Legacy presentational markup: <font> becomes <span> (dropping its
   presentational attributes), presentational attributes are stripped from
   every tag except width/height on <img>, and <map>/<area> are dropped
   entirely.
"""

import unittest
from xml.etree import ElementTree as ET

from quoin.normalize import INLINE_AUTOCLOSE, extract_article, visible_text


def normalized_text(markup: str) -> str:
    return " ".join(visible_text(markup).split())


def parse_fragment(fragment: str) -> ET.Element:
    return ET.fromstring(f"<root>{fragment}</root>")


def assert_no_block_under_inline(case: unittest.TestCase, root: ET.Element) -> None:
    """Walk the tree and fail if any inline element has a direct child that
    isn't itself inline (the shape EPUBCheck's RSC-005 rejects)."""
    for parent in root.iter():
        tag = parent.tag.rsplit("}", 1)[-1]
        if tag not in INLINE_AUTOCLOSE:
            continue
        for child in parent:
            child_tag = child.tag.rsplit("}", 1)[-1]
            case.assertIn(
                child_tag,
                INLINE_AUTOCLOSE,
                f"block element <{child_tag}> nested directly under inline <{tag}>",
            )


class InlineOverBlockAutocloseTests(unittest.TestCase):
    def test_div_in_href_less_anchor_is_not_nested_under_span(self) -> None:
        markup = "<html><body><article><a><div>Block text</div></a></article></body></html>"
        result = extract_article(markup)
        root = parse_fragment(result)
        assert_no_block_under_inline(self, root)
        self.assertEqual(normalized_text(result), "Block text")

    def test_div_in_href_less_anchor_produces_sibling_span_and_div(self) -> None:
        # The href-less <a> still becomes a <span> (existing behavior); it
        # must simply close before the <div> opens rather than wrap it.
        markup = "<html><body><article><a><div>x</div></a></article></body></html>"
        result = extract_article(markup)
        self.assertNotIn("<span><div>", result)
        self.assertIn("<span></span>", result)
        self.assertIn("<div>x</div>", result)

    def test_chain_of_inline_tags_all_close_before_block(self) -> None:
        markup = (
            "<html><body><article><span><b><i><div>Deep</div></i></b></span>"
            "</article></body></html>"
        )
        result = extract_article(markup)
        root = parse_fragment(result)
        assert_no_block_under_inline(self, root)
        self.assertEqual(normalized_text(result), "Deep")

    def test_inline_tags_after_a_normal_paragraph_are_unaffected(self) -> None:
        # Regression guard: ordinary text right before a block tag, with no
        # open inline run, should not trip the new autoclose loop.
        markup = "<html><body><article><p>First</p><div>Second</div></article></body></html>"
        result = extract_article(markup)
        self.assertEqual(normalized_text(result), "First Second")


class LegacyPresentationalMarkupTests(unittest.TestCase):
    def test_font_becomes_span_with_presentational_attrs_dropped(self) -> None:
        markup = (
            '<html><body><article><p><font size="3" face="Arial" color="red">'
            "Styled text</font></p></article></body></html>"
        )
        result = extract_article(markup)
        self.assert_fragment_parses(result)
        self.assertNotIn("<font", result)
        self.assertNotIn("</font>", result)
        self.assertIn("<span>Styled text</span>", result)
        self.assertEqual(normalized_text(result), "Styled text")

    def test_font_end_tag_matches_despite_rename(self) -> None:
        # original_tag must be captured before the font->span rename so the
        # matching </font> closes the emitted <span> immediately at that
        # point, rather than leaking open. Deliberately no block tag follows
        # the </font> here: a following block tag (p/div/etc.) would trigger
        # the separate inline-autoclose-before-block safety net, which also
        # closes a still-open <span> and would mask a mis-captured
        # original_tag (verified by mutation -- see plans/015).
        markup = "<html><body><article><font>Legacy</font> after</article></body></html>"
        result = extract_article(markup)
        self.assertEqual(result, "<span>Legacy</span> after")
        root = parse_fragment(result)
        # Exactly one span (from font) and the after-text sits outside it.
        spans = [el for el in root.iter() if el.tag.rsplit("}", 1)[-1] == "span"]
        self.assertEqual(len(spans), 1)
        self.assertEqual((spans[0].text or "").strip(), "Legacy")
        self.assertEqual(normalized_text(result), "Legacy after")

    def test_table_presentational_attrs_stripped_text_and_structure_survive(self) -> None:
        markup = (
            '<html><body><article><table align="center" bgcolor="#fff" border="1" '
            'cellpadding="2" cellspacing="2" width="400" height="100" background="x.gif">'
            '<tr valign="top"><td width="50" hspace="1" vspace="1" name="cell">'
            "Cell text</td></tr></table></article></body></html>"
        )
        result = extract_article(markup)
        self.assert_fragment_parses(result)
        for attr in (
            "align=",
            "bgcolor=",
            "border=",
            "cellpadding=",
            "cellspacing=",
            "width=",
            "height=",
            "background=",
            "valign=",
            "hspace=",
            "vspace=",
            "name=",
        ):
            self.assertNotIn(attr, result)
        self.assertIn("<table>", result)
        self.assertEqual(normalized_text(result), "Cell text")

    def test_img_keeps_width_and_height(self) -> None:
        markup = (
            '<html><body><article><img src="https://x/y.jpg" alt="a" '
            'width="200" height="100"/></article></body></html>'
        )
        result = extract_article(markup)
        self.assert_fragment_parses(result)
        self.assertIn('width="200"', result)
        self.assertIn('height="100"', result)

    def test_map_subtree_and_area_dropped(self) -> None:
        markup = (
            "<html><body><article><p>Keep</p>"
            '<map name="m"><area shape="rect" coords="0,0,1,1" href="https://x" '
            'alt="hotspot"/></map>'
            '<img src="https://x/y.jpg" usemap="#m" alt="pic"/>'
            "</article></body></html>"
        )
        result = extract_article(markup)
        self.assert_fragment_parses(result)
        self.assertNotIn("<map", result)
        self.assertNotIn("</map>", result)
        self.assertNotIn("<area", result)
        self.assertEqual(normalized_text(result), "Keep")

    def test_stray_area_without_map_is_skipped(self) -> None:
        markup = (
            "<html><body><article><p>Before</p>"
            '<area shape="rect" coords="0,0,1,1" href="https://x"/>'
            "<p>After</p></article></body></html>"
        )
        result = extract_article(markup)
        self.assert_fragment_parses(result)
        self.assertNotIn("<area", result)
        self.assertEqual(normalized_text(result), "Before After")

    def assert_fragment_parses(self, fragment: str) -> None:
        ET.fromstring(f"<root>{fragment}</root>")


if __name__ == "__main__":
    unittest.main()
