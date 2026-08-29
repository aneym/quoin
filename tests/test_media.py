"""Unit tests for plan 005's media helpers.

Covers the pure (I/O-free) pieces in normalize.py — magic-byte sniffing, the
ornamental threshold, and <img> discovery/rewriting — plus the namespacing,
in-archive matching, hotlink routing, and remote-snapshot integration in
fetch.py (_normalize_epub, _process_images). Modeled on plan 001's
test_normalize.py layout.
"""

import base64
import io
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from PIL import Image

from quoin.fetch import _media_dir, _normalize_epub, _process_images
from quoin.normalize import find_images, is_ornamental, rewrite_images, sniff_image_type

# A 1x1 transparent PNG, valid GIF89a, and minimal well-formed SVG, all tiny
# (under the 2.5 KB ornamental floor) so byte-size dropping is exercised too.
PNG_1PX = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)
GIF_1PX = base64.b64decode("R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw==")
JPEG_1PX_MARKER = b"\xff\xd8\xff\xe0" + b"\x00" * 200  # enough for a real magic-byte sniff
SVG_DOC = '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"></svg>'.encode()


def _large_png(width: int, height: int, size_floor: int = 2600) -> bytes:
    image = Image.new("RGB", (width, height), "red")
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    data = buffer.getvalue()
    if len(data) < size_floor:
        data += b"\x00" * (
            size_floor - len(data)
        )  # PNG readers ignore trailing junk; Pillow reads header+IDAT only
    return data


def _large_jpeg(width: int, height: int, color: str, size_floor: int = 2600) -> bytes:
    image = Image.new("RGB", (width, height), color)
    buffer = io.BytesIO()
    image.save(buffer, "JPEG")
    data = buffer.getvalue()
    if len(data) < size_floor:
        data += b"\x00" * (
            size_floor - len(data)
        )  # trailing bytes past JPEG EOF are ignored by decoders
    return data


def _make_epub(chapters: dict[str, str], members: dict[str, bytes], path: Path) -> None:
    """chapters: {archive_name: xhtml_body}. members: {archive_name: bytes} for images."""
    with zipfile.ZipFile(path, "w") as archive:
        for name, xhtml_body in chapters.items():
            archive.writestr(name, f"<html><body>{xhtml_body}</body></html>")
        for name, data in members.items():
            archive.writestr(name, data)


class SniffImageTypeTests(unittest.TestCase):
    def test_png_magic_bytes(self) -> None:
        self.assertEqual(sniff_image_type(PNG_1PX), "png")

    def test_gif_magic_bytes(self) -> None:
        self.assertEqual(sniff_image_type(GIF_1PX), "gif")

    def test_jpeg_magic_bytes(self) -> None:
        self.assertEqual(sniff_image_type(JPEG_1PX_MARKER), "jpeg")

    def test_webp_magic_bytes(self) -> None:
        data = b"RIFF" + (100).to_bytes(4, "little") + b"WEBPVP8 " + b"\x00" * 92
        self.assertEqual(sniff_image_type(data), "webp")

    def test_svg_by_root_tag(self) -> None:
        self.assertEqual(sniff_image_type(SVG_DOC), "svg")

    def test_jpeg_bytes_named_png_sniffs_as_jpeg(self) -> None:
        # The exact donated failure class: a JPEG served from a .png URL.
        real_jpeg = io.BytesIO()
        Image.new("RGB", (200, 200), "blue").save(real_jpeg, "JPEG")
        self.assertEqual(sniff_image_type(real_jpeg.getvalue()), "jpeg")

    def test_unrecognized_bytes_return_none(self) -> None:
        self.assertIsNone(sniff_image_type(b"not an image, just text"))

    def test_malformed_svg_is_not_sniffed(self) -> None:
        self.assertIsNone(sniff_image_type(b"<svg xmlns=unterminated"))


class OrnamentalTests(unittest.TestCase):
    def test_small_byte_count_is_ornamental(self) -> None:
        self.assertTrue(is_ornamental(PNG_1PX, "png"))

    def test_large_enough_image_is_not_ornamental(self) -> None:
        data = _large_png(400, 400)
        self.assertFalse(is_ornamental(data, "png"))

    def test_thin_edge_under_120px_is_ornamental(self) -> None:
        data = _large_png(400, 40)
        self.assertTrue(is_ornamental(data, "png"))

    def test_svg_skips_pixel_check_but_keeps_byte_floor(self) -> None:
        big_svg = SVG_DOC + b"<!--" + b"x" * 2600 + b"-->"
        self.assertFalse(is_ornamental(big_svg, "svg"))
        self.assertTrue(is_ornamental(SVG_DOC, "svg"))

    def test_undecodable_bytes_are_ornamental(self) -> None:
        self.assertTrue(is_ornamental(b"\x00" * 3000, "png"))


class FindAndRewriteImagesTests(unittest.TestCase):
    def test_find_images_extracts_src_and_alt(self) -> None:
        markup = '<p>text</p><img src="media/s1/a.jpg" alt="A chart"/>'
        self.assertEqual(find_images(markup), [{"src": "media/s1/a.jpg", "alt": "A chart"}])

    def test_find_images_handles_multiple_and_missing_alt(self) -> None:
        markup = '<img src="a.png"><p>x</p><img src="b.png" alt="B">'
        self.assertEqual(
            find_images(markup), [{"src": "a.png", "alt": ""}, {"src": "b.png", "alt": "B"}]
        )

    def test_rewrite_images_applies_resolver(self) -> None:
        markup = '<p>Keep</p><img src="https://x.test/a.png" alt="short">'
        result = rewrite_images(
            markup, lambda src, alt: (src.replace("https://x.test/", "media/s1/"), "A longer alt")
        )
        self.assertEqual(result, '<p>Keep</p><img src="media/s1/a.png" alt="A longer alt"/>')

    def test_rewrite_images_drops_on_none(self) -> None:
        markup = '<p>Keep</p><img src="https://x.test/a.png" alt="short"><p>After</p>'
        result = rewrite_images(markup, lambda src, alt: None)
        self.assertEqual(result, "<p>Keep</p><p>After</p>")

    def test_rewrite_images_escapes_new_values(self) -> None:
        markup = '<img src="a.png" alt="x">'
        result = rewrite_images(markup, lambda src, alt: (src, 'quote " and amp &'))
        self.assertIn("&amp;", result)
        self.assertIn("&quot;", result)


class NormalizeEpubMediaTests(unittest.TestCase):
    """fetch._normalize_epub: namespacing, exact-path matching, and hotlink routing (Step 1)."""

    def test_same_basename_different_bytes_both_packaged_and_correctly_referenced(self) -> None:
        img_a = _large_jpeg(200, 200, "red")
        img_b = _large_jpeg(200, 200, "blue")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            epub_path = root / "book.epub"
            _make_epub(
                chapters={
                    "OEBPS/ch1/page.xhtml": '<img src="img.png" alt="Figure one">',
                    "OEBPS/ch2/page.xhtml": '<img src="img.png" alt="Figure two">',
                },
                members={"OEBPS/ch1/img.png": img_a, "OEBPS/ch2/img.png": img_b},
                path=epub_path,
            )
            source = {
                "id": "book",
                "type": "epub",
                "chapter_locator": ["OEBPS/ch1/page.xhtml", "OEBPS/ch2/page.xhtml"],
            }
            notes: list[str] = []
            joined, media = _normalize_epub(root, source, epub_path, offline=False, notes=notes)
            pieces = joined.split("\n")
            self.assertEqual(len(media), 2)  # collision disambiguated: two distinct files stored
            srcs = [find_images(piece)[0]["src"] for piece in pieces]
            self.assertNotEqual(srcs[0], srcs[1])
            for src, expected in zip(srcs, (img_a, img_b)):
                packaged = root / "sources" / "media" / "book" / Path(src).name
                self.assertEqual(packaged.read_bytes(), expected)

    def test_exact_archive_path_preferred_over_basename_fallback(self) -> None:
        # CORRECTNESS-03: two same-named images in different directories: the
        # computed archive-relative path must resolve each <img> to ITS OWN file,
        # not whichever same-named member happens to sort first.
        wrong = _large_jpeg(200, 200, "green")
        right = _large_jpeg(200, 200, "yellow")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            epub_path = root / "book.epub"
            _make_epub(
                chapters={"OEBPS/ch2/page.xhtml": '<img src="img.png" alt="Right one">'},
                members={"OEBPS/ch1/img.png": wrong, "OEBPS/ch2/img.png": right},
                path=epub_path,
            )
            source = {"id": "book", "type": "epub", "chapter_locator": ["OEBPS/ch2/page.xhtml"]}
            joined, _ = _normalize_epub(root, source, epub_path, offline=False, notes=[])
            src = find_images(joined)[0]["src"]
            packaged = root / "sources" / "media" / "book" / Path(src).name
            self.assertEqual(packaged.read_bytes(), right)

    def test_hotlinked_image_in_epub_chapter_no_longer_aborts_fetch(self) -> None:
        remote = _large_jpeg(200, 200, "purple")
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = remote
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            epub_path = root / "book.epub"
            _make_epub(
                chapters={
                    "OEBPS/page.xhtml": (
                        '<img src="https://example.test/remote.jpg" alt="Remote figure">'
                    )
                },
                members={},
                path=epub_path,
            )
            source = {"id": "book", "type": "epub", "chapter_locator": ["OEBPS/page.xhtml"]}
            with patch("quoin.fetch.urllib.request.urlopen", return_value=response):
                joined, media = _normalize_epub(root, source, epub_path, offline=False, notes=[])
        self.assertEqual(len(media), 1)
        self.assertIn('src="media/book/', joined)

    def test_offline_hotlink_with_no_snapshot_drops_with_note_not_raise(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            epub_path = root / "book.epub"
            _make_epub(
                chapters={
                    "OEBPS/page.xhtml": (
                        '<img src="https://example.test/remote.jpg" alt="Remote figure">'
                    )
                },
                members={},
                path=epub_path,
            )
            source = {"id": "book", "type": "epub", "chapter_locator": ["OEBPS/page.xhtml"]}
            notes: list[str] = []
            joined, media = _normalize_epub(root, source, epub_path, offline=True, notes=notes)
        self.assertEqual(media, [])
        self.assertNotIn("<img", joined)
        self.assertTrue(any("offline" in note for note in notes))


class ProcessImagesWebFileTests(unittest.TestCase):
    """fetch._process_images: web/file remote snapshot + offline reuse (Step 2)."""

    def test_remote_image_downloaded_and_rewritten_to_namespaced_path(self) -> None:
        data = _large_jpeg(200, 200, "orange")
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = data
        source = {"id": "article", "type": "web", "locator": "https://example.test/a"}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            body = '<p>Keep</p><img src="https://example.test/x.jpg" alt="A chart">'
            with patch("quoin.fetch.urllib.request.urlopen", return_value=response):
                result, media = _process_images(root, source, body, offline=False, notes=[])
            self.assertEqual(len(media), 1)
            self.assertIn('src="media/article/', result)
            packaged = _media_dir(root, "article") / Path(media[0]).name
            self.assertEqual(packaged.read_bytes(), data)

    def test_offline_reuses_prior_snapshot_without_network(self) -> None:
        data = _large_jpeg(200, 200, "orange")
        source = {"id": "article", "type": "web", "locator": "https://example.test/a"}
        body = '<img src="https://example.test/x.jpg" alt="A chart">'
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            response = MagicMock()
            response.__enter__.return_value = response
            response.read.return_value = data
            with patch("quoin.fetch.urllib.request.urlopen", return_value=response):
                _process_images(root, source, body, offline=False, notes=[])
            with patch(
                "quoin.fetch.urllib.request.urlopen",
                side_effect=AssertionError("must not hit network"),
            ):
                result, media = _process_images(root, source, body, offline=True, notes=[])
        self.assertEqual(len(media), 1)
        self.assertIn('src="media/article/', result)

    def test_offline_with_no_snapshot_drops_with_note(self) -> None:
        source = {"id": "article", "type": "web", "locator": "https://example.test/a"}
        body = '<img src="https://example.test/never-fetched.jpg" alt="A chart">'
        notes: list[str] = []
        result, media = _process_images(
            Path(tempfile.mkdtemp()), source, body, offline=True, notes=notes
        )
        self.assertEqual(media, [])
        self.assertNotIn("<img", result)
        self.assertTrue(any("offline" in note for note in notes))


class SniffMismatchIntegrationTests(unittest.TestCase):
    """fetch._process_images: donated failure class — real type wins over URL extension (Step 3)."""

    def test_jpeg_bytes_served_from_png_url_packaged_as_jpeg_with_mismatch_note(self) -> None:
        real_jpeg = _large_jpeg(200, 200, "teal")
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = real_jpeg
        source = {"id": "article", "type": "web", "locator": "https://example.test/a"}
        body = '<img src="https://example.test/mislabeled.png" alt="A chart">'
        notes: list[str] = []
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch("quoin.fetch.urllib.request.urlopen", return_value=response):
                result, media = _process_images(root, source, body, offline=False, notes=notes)
        self.assertEqual(len(media), 1)
        self.assertTrue(media[0].endswith(".jpg"))
        self.assertIn('src="media/article/', result)
        self.assertTrue(any("sniffed as jpeg" in note for note in notes))


if __name__ == "__main__":
    unittest.main()
