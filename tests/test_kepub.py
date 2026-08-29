from __future__ import annotations

import json
import re
import tempfile
import unittest
import zipfile
from pathlib import Path

from PIL import Image

from quoin.assemble import build, kepub_path, make_kepub
from quoin.normalize import body_inner, replace_body_inner, word_count, wrap_kobo_spans
from quoin.record import sha256_bytes

SPAN_ID = re.compile(r'<span class="koboSpan" id="kobo\.(\d+)\.(\d+)">')


def span_ids(markup: str) -> list[tuple[int, int]]:
    return [(int(n), int(m)) for n, m in SPAN_ID.findall(markup)]


def assert_sequential(case: unittest.TestCase, ids: list[tuple[int, int]]) -> None:
    """Paragraph numbers appear in increasing run order starting at 1 with no gaps;
    within each paragraph, segment numbers start at 1 and increment with no gaps."""
    seen_paragraphs: list[int] = []
    segment_counts: dict[int, int] = {}
    for paragraph, segment in ids:
        if paragraph not in segment_counts:
            seen_paragraphs.append(paragraph)
            segment_counts[paragraph] = 0
        segment_counts[paragraph] += 1
        case.assertEqual(segment, segment_counts[paragraph], f"gap in {paragraph}: {ids}")
    case.assertEqual(seen_paragraphs, list(range(1, len(seen_paragraphs) + 1)), ids)


class WrapKoboSpansTests(unittest.TestCase):
    def test_wraps_paragraph_text(self) -> None:
        wrapped = wrap_kobo_spans("<p>Hello there.</p>")
        self.assertEqual(wrapped, '<p><span class="koboSpan" id="kobo.1.1">Hello there.</span></p>')

    def test_ids_unique_and_sequential_across_blocks(self) -> None:
        wrapped = wrap_kobo_spans("<p>First.</p><p>Second.</p><h1>Third.</h1>")
        ids = span_ids(wrapped)
        self.assertEqual(len(ids), len(set(ids)), "duplicate span id")
        assert_sequential(self, ids)
        self.assertEqual(ids, [(1, 1), (2, 1), (3, 1)])

    def test_nested_inline_tags_share_the_enclosing_block_frame(self) -> None:
        wrapped = wrap_kobo_spans("<p>Before <em>middle</em> after.</p>")
        ids = span_ids(wrapped)
        self.assertEqual(ids, [(1, 1), (1, 2), (1, 3)])
        self.assertIn("<em>", wrapped)
        self.assertIn("</em>", wrapped)

    def test_nested_block_opens_its_own_paragraph(self) -> None:
        wrapped = wrap_kobo_spans("<ul><li>One</li><li>Two</li></ul>")
        ids = span_ids(wrapped)
        assert_sequential(self, ids)
        self.assertEqual(len(ids), 2)

    def test_whitespace_between_list_items_is_not_wrapped(self) -> None:
        # Pretty-printed markup often puts whitespace-only text nodes directly
        # inside <ol>/<ul>, between/around <li> siblings. Wrapping those in a
        # <span> makes it a direct child of ol/ul, which only permits li,
        # script, or template there -- an EPUBCheck content-model error (see
        # plan 011's real-corpus regression). The indentation must survive
        # un-wrapped while the <li> contents still get spans.
        # <li> is not itself a BLOCK_TAGS frame-opener here (list items share
        # their enclosing ol/ul's paragraph, like nested inline runs do), so
        # both items land in paragraph 1 as successive segments.
        markup = "<ol>\n  <li>One</li>\n  <li>Two</li>\n</ol>"
        wrapped = wrap_kobo_spans(markup)
        self.assertNotIn("<ol><span", wrapped)
        self.assertNotIn("</li><span", wrapped)
        ids = span_ids(wrapped)
        assert_sequential(self, ids)
        self.assertEqual(ids, [(1, 1), (1, 2)])

    def test_tag_attributes_pass_through_unchanged(self) -> None:
        markup = '<p>See <img src="a.png" alt="A cat"/> here.</p>'
        wrapped = wrap_kobo_spans(markup)
        self.assertIn('<img src="a.png" alt="A cat"/>', wrapped)

    def test_no_block_ancestor_leaves_text_unwrapped(self) -> None:
        wrapped = wrap_kobo_spans("plain text, no block parent")
        self.assertNotIn("koboSpan", wrapped)
        self.assertEqual(wrapped, "plain text, no block parent")

    def test_adds_no_visible_text(self) -> None:
        markup = "<section><h1>Title</h1><p>Body copy right here.</p></section>"
        wrapped = wrap_kobo_spans(markup)
        self.assertEqual(word_count(wrapped), word_count(markup))

    def test_entities_round_trip(self) -> None:
        wrapped = wrap_kobo_spans("<p>Ampersands &amp; entities &amp; text.</p>")
        self.assertIn("&amp;", wrapped)
        self.assertNotIn(" & ", wrapped)


class ReplaceBodyInnerTests(unittest.TestCase):
    def test_replaces_only_the_body(self) -> None:
        source = (
            '<?xml version="1.0"?><html><head><title>T</title></head><body><p>old</p></body></html>'
        )
        result = replace_body_inner(source, "<p>new</p>")
        self.assertIn("<title>T</title>", result)
        self.assertIn("<body><p>new</p></body>", result)
        self.assertNotIn("old", result)

    def test_missing_body_raises(self) -> None:
        with self.assertRaises(ValueError):
            replace_body_inner("<html><head></head></html>", "<p>x</p>")


def _scaffold_book(root: Path) -> None:
    for directory in ("sources/normalized", "blocks"):
        (root / directory).mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (2, 2), "red").save(root / "cover.png")
    (root / "book.toml").write_text('cover_image = "cover.png"\n', encoding="utf-8")
    manifest = {
        "format_version": 1,
        "slug": "sample",
        "title": "Sample & Sons",
        "brand": "Quoin",
        "language": "en",
        "governing_question": "Why?",
        "privacy": {"forbidden_terms": []},
        "sources": [
            {
                "id": "one",
                "type": "file",
                "title": "One",
                "locator": "sources/one.html",
                "rights": {"access": "public"},
            }
        ],
        "movements": [{"id": "m1", "title": "Movement", "items": [{"ref": "source:one"}]}],
        "blocks": [],
    }
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (root / "sources/records.json").write_text(
        json.dumps({"one": {"word_count": 4, "url": "https://example.invalid/one"}}),
        encoding="utf-8",
    )
    (root / "sources/normalized/one.xhtml").write_text(
        (
            '<?xml version="1.0" encoding="utf-8"?><html xmlns="http://www.w3.org/1999/xhtml">'
            "<head><title>One</title></head><body><p>Four short plain words.</p>"
            "<ul><li>An item here.</li></ul></body></html>"
        ),
        encoding="utf-8",
    )


class MakeKepubTests(unittest.TestCase):
    def test_kepub_path_naming(self) -> None:
        self.assertEqual(kepub_path(Path("out/book.epub")), Path("out/book.kepub.epub"))

    def test_default_build_untouched_by_kepub_support(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _scaffold_book(root)
            target, record = build(root, draft=True)
            self.assertEqual(target, root / "out" / "sample.epub")
            self.assertNotIn("profile", record)
            self.assertNotIn("kepub_sha256", record)
            self.assertFalse(kepub_path(target).exists())

    def test_kepub_profile_produces_separate_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _scaffold_book(root)
            target, record = build(root, draft=True, profile="kepub")
            self.assertEqual(target, root / "out" / "sample.kepub.epub")
            self.assertTrue(target.exists())
            self.assertTrue((root / "out" / "sample.epub").exists())
            self.assertEqual(record["profile"], "kepub")
            self.assertEqual(record["kepub_sha256"], sha256_bytes(target.read_bytes()))

    def test_kepub_word_counts_match_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _scaffold_book(root)
            default_target, _ = build(root, draft=True)
            kepub_target, _ = build(root, draft=True, profile="kepub")
            with zipfile.ZipFile(default_target) as archive:
                default_text = archive.read("OEBPS/text/source-one.xhtml").decode("utf-8")
            with zipfile.ZipFile(kepub_target) as archive:
                kepub_text = archive.read("OEBPS/text/source-one.xhtml").decode("utf-8")
            self.assertIn("koboSpan", kepub_text)
            self.assertEqual(
                word_count(body_inner(default_text)), word_count(body_inner(kepub_text))
            )

    def test_kepub_span_ids_unique_and_sequential_per_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _scaffold_book(root)
            kepub_target, _ = build(root, draft=True, profile="kepub")
            with zipfile.ZipFile(kepub_target) as archive:
                for name in archive.namelist():
                    if not (name.startswith("OEBPS/text/") and name.endswith(".xhtml")):
                        continue
                    ids = span_ids(archive.read(name).decode("utf-8"))
                    self.assertEqual(len(ids), len(set(ids)), name)
                    assert_sequential(self, ids)

    def test_kepub_leaves_non_text_entries_byte_identical(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _scaffold_book(root)
            default_target, _ = build(root, draft=True)
            kepub_target, _ = build(root, draft=True, profile="kepub")
            with zipfile.ZipFile(default_target) as default_archive:
                with zipfile.ZipFile(kepub_target) as kepub_archive:
                    for name in ("mimetype", "OEBPS/styles/book.css", "OEBPS/images/cover.png"):
                        self.assertEqual(default_archive.read(name), kepub_archive.read(name), name)

    def test_make_kepub_is_idempotent_over_the_same_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _scaffold_book(root)
            target, _ = build(root, draft=True)
            first, second = root / "out" / "first.kepub.epub", root / "out" / "second.kepub.epub"
            make_kepub(target, first)
            make_kepub(target, second)
            self.assertEqual(first.read_bytes(), second.read_bytes())


if __name__ == "__main__":
    unittest.main()
