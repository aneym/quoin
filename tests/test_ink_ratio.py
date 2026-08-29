"""Unit tests for plan 012's ink_ratio() measurement function.

Synthetic PNGs only -- no renderer involved. ink_ratio() is a pure function
over PNG bytes (fraction of pixels darker than 50% gray), so these tests
build the images in-memory with Pillow rather than depending on any real
rendered page.
"""

import io
import unittest

from PIL import Image

from quoin.check import INK_RATIO_THRESHOLD, ink_ratio


def _png_bytes(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


class InkRatioTests(unittest.TestCase):
    def test_all_white_is_zero(self) -> None:
        image = Image.new("RGB", (100, 100), (255, 255, 255))
        self.assertEqual(ink_ratio(_png_bytes(image)), 0.0)

    def test_all_black_is_one(self) -> None:
        image = Image.new("RGB", (100, 100), (0, 0, 0))
        self.assertEqual(ink_ratio(_png_bytes(image)), 1.0)

    def test_text_like_page_is_above_threshold(self) -> None:
        # A mostly-white page with a solid dark band standing in for a heading
        # and a paragraph of body text -- comfortably above the threshold, the
        # way a real rendered page with actual content is.
        image = Image.new("RGB", (200, 200), (255, 255, 255))
        for y in range(20, 40):
            for x in range(20, 180):
                image.putpixel((x, y), (0, 0, 0))
        for y in range(60, 140):
            for x in range(20, 180, 2):
                image.putpixel((x, y), (10, 10, 10))
        ratio = ink_ratio(_png_bytes(image))
        self.assertGreater(ratio, INK_RATIO_THRESHOLD)

    def test_sparse_dark_pixels_is_below_threshold(self) -> None:
        # A handful of stray dark pixels on an otherwise blank page -- stands
        # in for a page whose stylesheet failed to load (or that is truly
        # empty): far too sparse to be real rendered content.
        image = Image.new("RGB", (1000, 1000), (255, 255, 255))
        for i in range(5):
            image.putpixel((i, 0), (0, 0, 0))
        ratio = ink_ratio(_png_bytes(image))
        self.assertLess(ratio, INK_RATIO_THRESHOLD)

    def test_boundary_gray_is_excluded(self) -> None:
        # A pixel exactly at 50% gray (bucket 128) is NOT counted as "dark" --
        # the threshold is pixels darker than 50% gray, i.e. buckets [0, 128).
        image = Image.new("L", (10, 10), 128)
        self.assertEqual(ink_ratio(_png_bytes(image)), 0.0)

    def test_just_under_boundary_counts(self) -> None:
        image = Image.new("L", (10, 10), 127)
        self.assertEqual(ink_ratio(_png_bytes(image)), 1.0)


if __name__ == "__main__":
    unittest.main()
