"""Unit tests for plan 005's media helpers.

Covers the pure (I/O-free) pieces in normalize.py — magic-byte sniffing, the
ornamental threshold, and <img> discovery/rewriting — plus the namespacing and
fetch-time integration helpers in fetch.py. Modeled on plan 001's
test_normalize.py layout.
"""

import base64
import io
import unittest

from PIL import Image

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
        data += b"\x00" * (size_floor - len(data))  # PNG readers ignore trailing junk; Pillow reads header+IDAT only
    return data


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
        self.assertEqual(find_images(markup), [{"src": "a.png", "alt": ""}, {"src": "b.png", "alt": "B"}])

    def test_rewrite_images_applies_resolver(self) -> None:
        markup = '<p>Keep</p><img src="https://x.test/a.png" alt="short">'
        result = rewrite_images(markup, lambda src, alt: (src.replace("https://x.test/", "media/s1/"), "A longer alt"))
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


if __name__ == "__main__":
    unittest.main()
